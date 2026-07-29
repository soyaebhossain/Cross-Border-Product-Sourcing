from __future__ import annotations

import jwt
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.api.routes.research import (
    ACTIVE_ORDER_STATUSES,
    _safe_decimal,
    _spreadsheet_safe,
    get_research_admin,
)
from app.auth import build_token_response, get_current_privileged_user, get_current_user
from app.config import Settings
from app.db import Base
from app.models import AccountUser
from app.security import BrowserSecurityMiddleware, SlidingWindowRateLimiter, normalize_origin


def _request(
    *,
    method: str = "POST",
    origin: str | None = None,
    referer: str | None = None,
    cookie: str | None = None,
) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    for name, value in (("origin", origin), ("referer", referer), ("cookie", cookie)):
        if value is not None:
            headers.append((name.encode(), value.encode()))
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "https",
            "path": "/api/orders/1/status/",
            "raw_path": b"/api/orders/1/status/",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 50000),
            "server": ("api.example.com", 443),
        }
    )


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


def test_production_rejects_default_secrets() -> None:
    settings = _settings(
        environment="production",
        database_url="postgresql+psycopg://postgres:postgres@db:5432/cross_border",
        jwt_secret="change-me-access",
    )
    with pytest.raises(RuntimeError, match="CATALOG_JWT_SECRET"):
        settings.validate_runtime_security()


def test_production_accepts_explicit_secure_configuration() -> None:
    settings = _settings(
        environment="production",
        database_url="postgresql+psycopg://sourceai:a-unique-database-password@db:5432/cross_border",
        jwt_secret="a-unique-random-production-jwt-secret-value-123456789",
    )
    settings.validate_runtime_security()


def test_production_requires_error_monitoring() -> None:
    settings = _settings(
        environment="production",
        database_url="postgresql+psycopg://sourceai:a-unique-database-password@db:5432/cross_border",
        jwt_secret="a-unique-random-production-jwt-secret-value-123456789",
        error_monitoring_dsn=None,
    )
    with pytest.raises(RuntimeError, match="CATALOG_ERROR_MONITORING_DSN"):
        settings.validate_runtime_security()


def test_production_requires_privileged_mfa() -> None:
    settings = _settings(
        environment="production",
        database_url="postgresql+psycopg://sourceai:a-unique-database-password@db:5432/cross_border",
        jwt_secret="a-unique-random-production-jwt-secret-value-123456789",
        privileged_mfa_required=False,
    )
    with pytest.raises(RuntimeError, match="CATALOG_PRIVILEGED_MFA_REQUIRED"):
        settings.validate_runtime_security()


def test_production_requires_separate_mfa_encryption_key() -> None:
    settings = _settings(
        environment="production",
        database_url="postgresql+psycopg://sourceai:a-unique-database-password@db:5432/cross_border",
        jwt_secret="a-unique-random-production-jwt-secret-value-123456789",
        mfa_encryption_key=None,
    )
    with pytest.raises(RuntimeError, match="CATALOG_MFA_ENCRYPTION_KEY"):
        settings.validate_runtime_security()


def test_origin_guard_is_exact_and_allows_local_development_referer() -> None:
    middleware = BrowserSecurityMiddleware(lambda *_args: None, settings=_settings())
    assert middleware._origin_rejection(_request(origin="https://app.example.com")) is None
    assert middleware._origin_rejection(_request(origin="https://app.example.com.evil.test")).status_code == 403
    assert middleware._origin_rejection(
        _request(referer="https://app.example.com/orders/1", cookie="sourceai_access=token")
    ) is None
    assert middleware._origin_rejection(_request(cookie="sourceai_access=token")).status_code == 403
    assert normalize_origin("https://Example.com:443") == "https://example.com"


def test_sliding_window_rate_limit_is_bounded() -> None:
    now = [100.0]
    limiter = SlidingWindowRateLimiter(clock=lambda: now[0])
    limiter.enforce("login:127.0.0.1", limit=2, window_seconds=60)
    limiter.enforce("login:127.0.0.1", limit=2, window_seconds=60)
    with pytest.raises(HTTPException) as error:
        limiter.enforce("login:127.0.0.1", limit=2, window_seconds=60)
    assert error.value.status_code == 429
    now[0] = 161.0
    limiter.enforce("login:127.0.0.1", limit=2, window_seconds=60)


def test_research_values_are_safe_and_statuses_match_current_order_flow() -> None:
    assert _safe_decimal("1250.25") is not None
    assert _safe_decimal("NaN") is None
    assert _safe_decimal("-1") is None
    assert _safe_decimal("9" * 65) is None
    assert _spreadsheet_safe("=HYPERLINK(\"https://evil.test\")").startswith("'")
    assert "CONFIRMED" in ACTIVE_ORDER_STATUSES
    assert "IN_TRANSIT" in ACTIVE_ORDER_STATUSES
    assert "DELIVERED" not in ACTIVE_ORDER_STATUSES
    assert "CANCELLED" not in ACTIVE_ORDER_STATUSES


def test_sensitive_auth_reloads_current_role_and_active_state(monkeypatch: pytest.MonkeyPatch) -> None:
    test_settings = _settings()
    monkeypatch.setattr("app.auth.get_settings", lambda: test_settings)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    user = AccountUser(
        id=100_001,
        username="security-test-user",
        email="security@example.com",
        phone=None,
        password_hash="unused",
        role="customer",
        is_active=True,
        is_staff=False,
        is_superuser=False,
    )
    with Session(engine) as session:
        session.add(user)
        session.commit()
        tokens = build_token_response(
            {"id": user.id, "username": user.username, "email": user.email, "phone": None, "role": "customer"}
        )
        payload = jwt.decode(tokens["access"], test_settings.jwt_secret, algorithms=["HS256"])
        assert payload["remember"] is True

        user.role = "operator"
        user.is_staff = True
        session.commit()
        current = get_current_user(_request(method="GET"), tokens["access"], session)
        assert current["role"] == "operator"
        assert get_current_privileged_user(current)["role"] == "operator"

        user.is_active = False
        session.commit()
        with pytest.raises(HTTPException) as error:
            get_current_user(_request(method="GET"), tokens["access"], session)
        assert error.value.status_code == 401


def test_customer_cannot_use_privileged_dependency() -> None:
    with pytest.raises(HTTPException) as error:
        get_current_privileged_user({"sub": 1, "role": "customer"})
    assert error.value.status_code == 403


def test_research_requires_admin_not_operator() -> None:
    assert get_research_admin({"sub": 1, "role": "admin"})["role"] == "admin"
    with pytest.raises(HTTPException) as error:
        get_research_admin({"sub": 2, "role": "operator"})
    assert error.value.status_code == 403
