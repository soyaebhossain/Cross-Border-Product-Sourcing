from __future__ import annotations

import asyncio
import importlib
import json
import logging
from types import SimpleNamespace

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.api.routes.catalog import readiness
from app.config import Settings
from app.db import Base
from app.security import RequestLoggingMiddleware


app_module = importlib.import_module("app.api.app")


def _request(
    path: str,
    *,
    query: str = "",
    request_id: str | None = None,
) -> Request:
    headers: list[tuple[bytes, bytes]] = [
        (b"authorization", b"Bearer header-secret"),
        (b"cookie", b"sourceai_access=cookie-secret"),
    ]
    if request_id is not None:
        headers.append((b"x-request-id", request_id.encode()))
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "https",
            "path": path,
            "raw_path": path.encode(),
            "query_string": query.encode(),
            "headers": headers,
            "client": ("127.0.0.1", 50000),
            "server": ("api.example.com", 443),
        }
    )


async def _matched_response(request: Request) -> JSONResponse:
    request.scope["route"] = SimpleNamespace(path="/items/{item_id}")
    return JSONResponse({"status": "ok"})


def _settings(**overrides) -> Settings:
    values = {
        "environment": "development",
        "database_url": "sqlite:///:memory:",
        "jwt_secret": "test-secret-that-is-long-enough-for-unit-tests",
        "cors_origins": "https://app.example.com",
        "frontend_url": "https://app.example.com",
        "secure_cookies": True,
        "mfa_encryption_key": "EnFxjaW8RPNIWnzKAp9uQz891m0RVLkLxn1QV9gaf0c=",
        "payment_proof_allowed_hosts": "proofs.example.com",
        "error_monitoring_dsn": "https://public-key@errors.example.com/1",
    }
    values.update(overrides)
    return Settings(**values)


def test_request_log_is_correlated_structured_and_redacted(caplog) -> None:
    logger = logging.getLogger("test.catalog.request")
    logger.handlers.clear()
    logger.propagate = True
    logger.setLevel(logging.INFO)

    middleware = RequestLoggingMiddleware(lambda *_args: None, logger=logger)
    with caplog.at_level(logging.INFO, logger=logger.name):
        response = asyncio.run(
            middleware.dispatch(
                _request(
                    "/items/customer-123",
                    query="access_token=query-secret",
                    request_id="edge-request-123",
                ),
                _matched_response,
            )
        )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "edge-request-123"
    event = json.loads(caplog.records[-1].message)
    assert event["event"] == "http_request"
    assert event["level"] == "info"
    assert event["service"] == "catalog-service"
    assert event["request_id"] == "edge-request-123"
    assert event["route"] == "/items/{item_id}"
    assert event["status_code"] == 200
    serialized = caplog.records[-1].message
    assert "customer-123" not in serialized
    assert "query-secret" not in serialized
    assert "header-secret" not in serialized
    assert "cookie-secret" not in serialized


def test_invalid_incoming_request_id_is_replaced(caplog) -> None:
    logger = logging.getLogger("test.catalog.invalid-request-id")
    logger.handlers.clear()
    logger.propagate = True
    logger.setLevel(logging.INFO)

    middleware = RequestLoggingMiddleware(lambda *_args: None, logger=logger)
    with caplog.at_level(logging.INFO, logger=logger.name):
        response = asyncio.run(
            middleware.dispatch(
                _request("/ok", request_id="bad forged-log-line"),
                _matched_response,
            )
        )

    request_id = response.headers["x-request-id"]
    assert request_id != "bad forged-log-line"
    assert len(request_id) == 32
    assert json.loads(caplog.records[-1].message)["request_id"] == request_id


def test_readiness_checks_database_and_required_schema() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        result = readiness(session)
    assert result["status"] == "ready"

    with engine.begin() as connection:
        connection.execute(text("DROP TABLE admin_audit_events"))
    with Session(engine) as session:
        unavailable = readiness(session)
    assert unavailable.status_code == 503
    assert json.loads(unavailable.body)["database"] == "unavailable"


def test_production_lifespan_never_bootstraps_schema_or_seed(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        app_module.Base.metadata,
        "create_all",
        lambda **_kwargs: calls.append("create_all"),
    )
    monkeypatch.setattr(
        app_module,
        "seed_database",
        lambda *_args, **_kwargs: calls.append("seed"),
    )
    production = _settings(
        environment="production",
        database_url="postgresql+psycopg://sourceai:unique-database-password@db:5432/cross_border",
        jwt_secret="a-unique-random-production-jwt-secret-value-123456789",
    )

    app_module._initialize_database(production)
    app = app_module.create_app(production)

    async def run_lifespan() -> None:
        async with app.router.lifespan_context(app):
            pass

    asyncio.run(run_lifespan())
    assert calls == []
    assert app.router.on_startup == []
