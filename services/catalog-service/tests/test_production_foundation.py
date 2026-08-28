from __future__ import annotations

import asyncio
import hashlib
import hmac
import importlib
import json
import logging
import time
from types import SimpleNamespace

from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.api.routes.catalog import readiness
from app.config import Settings
from app.db import Base, configure_sqlite_foreign_keys
from app.security import RequestLoggingMiddleware, client_rate_key


security_module = importlib.import_module("app.security")


app_module = importlib.import_module("app.api.app")


def _request(
    path: str,
    *,
    query: str = "",
    request_id: str | None = None,
    extra_headers: dict[str, str] | None = None,
) -> Request:
    headers: list[tuple[bytes, bytes]] = [
        (b"authorization", b"Bearer header-secret"),
        (b"cookie", b"sourceai_access=cookie-secret"),
    ]
    if request_id is not None:
        headers.append((b"x-request-id", request_id.encode()))
    for key, value in (extra_headers or {}).items():
        headers.append((key.lower().encode(), value.encode()))
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


def test_provider_postgres_urls_use_the_installed_psycopg_v3_driver() -> None:
    assert (
        _settings(
            database_url="postgres://sourceai:unique-password@db.example.com:5432/cross_border"
        ).database_url
        == "postgresql+psycopg://sourceai:unique-password@db.example.com:5432/cross_border"
    )
    assert (
        _settings(
            database_url="postgresql://sourceai:unique-password@db.example.com:5432/cross_border"
        ).database_url
        == "postgresql+psycopg://sourceai:unique-password@db.example.com:5432/cross_border"
    )


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


def test_rate_limit_uses_only_cryptographically_signed_proxy_client_ip(
    monkeypatch,
) -> None:
    secret = "proxy-test-secret-that-is-longer-than-thirty-two-characters"
    timestamp = int(time.time())
    client_ip = "203.0.113.25"
    signature = hmac.new(
        secret.encode(),
        f"{client_ip}\n{timestamp}".encode(),
        hashlib.sha256,
    ).hexdigest()
    monkeypatch.setattr(
        security_module,
        "get_settings",
        lambda: _settings(proxy_shared_secret=secret),
    )
    signed = _request(
        "/api/auth/login/",
        extra_headers={
            "x-sourceai-client-ip": client_ip,
            "x-sourceai-proxy-timestamp": str(timestamp),
            "x-sourceai-proxy-signature": signature,
        },
    )
    forged = _request(
        "/api/auth/login/",
        extra_headers={
            "x-sourceai-client-ip": "198.51.100.99",
            "x-sourceai-proxy-timestamp": str(timestamp),
            "x-sourceai-proxy-signature": signature,
        },
    )

    assert client_rate_key(signed, "login") == f"login:{client_ip}"
    assert client_rate_key(forged, "login") == "login:127.0.0.1"


def test_readiness_checks_database_and_required_schema() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    configured = _settings(
        resend_api_key="re_test_only_not_a_secret",
        resend_from_email="security@example.test",
    )

    with Session(engine) as session:
        result = readiness(session, configured)
    assert result["status"] == "ready"
    assert result["password_reset_email_configured"] is True
    assert "re_test_only_not_a_secret" not in json.dumps(result)
    assert "security@example.test" not in json.dumps(result)

    with engine.begin() as connection:
        connection.execute(text("DROP TABLE admin_audit_events"))
    with Session(engine) as session:
        unavailable = readiness(session, _settings())
    assert unavailable.status_code == 503
    unavailable_payload = json.loads(unavailable.body)
    assert unavailable_payload["database"] == "unavailable"
    assert unavailable_payload["password_reset_email_configured"] is False


def test_sqlite_connections_enforce_foreign_keys() -> None:
    engine = create_engine("sqlite:///:memory:")
    configure_sqlite_foreign_keys(engine)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE parent (id INTEGER PRIMARY KEY)"))
        connection.execute(
            text(
                "CREATE TABLE child (id INTEGER PRIMARY KEY, parent_id INTEGER "
                "REFERENCES parent(id))"
            )
        )
        try:
            connection.execute(text("INSERT INTO child (id, parent_id) VALUES (1, 999)"))
        except IntegrityError:
            pass
        else:
            raise AssertionError("SQLite accepted an orphaned foreign key")
    engine.dispose()


def test_password_reset_email_capability_requires_host_and_sender() -> None:
    assert _settings().password_reset_email_configured is False
    assert _settings(resend_api_key="re_test_only").password_reset_email_configured is False
    assert _settings(resend_from_email="security@example.test").password_reset_email_configured is False
    resend = _settings(
        resend_api_key="re_test_only",
        resend_from_email="security@example.test",
    )
    assert resend.resend_email_configured is True
    assert resend.password_reset_email_configured is True
    assert "re_test_only" not in repr(resend)
    assert _settings(smtp_host="smtp.example.test").password_reset_email_configured is False
    assert _settings(smtp_from_email="security@example.test").password_reset_email_configured is False
    assert _settings(
        smtp_host="smtp.example.test",
        smtp_from_email="security@example.test",
    ).password_reset_email_configured is True


def test_production_rejects_partial_placeholder_and_sandbox_resend_configuration() -> None:
    for values, message in (
        ({"resend_api_key": "re_test_only"}, "configured together"),
        ({"resend_from_email": "security@example.test"}, "configured together"),
        (
            {"resend_api_key": "re_xxxxxxxxx", "resend_from_email": "security@example.test"},
            "non-placeholder",
        ),
        (
            {"resend_api_key": "re_test_only", "resend_from_email": "onboarding@resend.dev"},
            "verified production domain",
        ),
    ):
        settings = _settings(environment="production", **values)
        try:
            settings.validate_runtime_security()
        except RuntimeError as exc:
            assert message in str(exc)
            assert "re_test_only" not in str(exc)
        else:
            raise AssertionError("Expected invalid Resend production configuration")


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


def test_noncanonical_api_paths_do_not_redirect_to_backend_origin() -> None:
    app = app_module.create_app(_settings())
    client = TestClient(app, follow_redirects=False)

    responses = [
        client.get("/api/categories"),
        client.get("/api/health/"),
        client.post("/api/auth/login", json={}),
    ]

    for response in responses:
        assert response.status_code == 404
        assert "location" not in response.headers


def test_health_supports_head_for_platform_probes() -> None:
    app = app_module.create_app(_settings())
    client = TestClient(app)

    response = client.head("/api/health")

    assert response.status_code == 200
    assert response.content == b""
