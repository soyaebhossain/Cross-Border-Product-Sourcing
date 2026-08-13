from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import auth
from app.api.routes import auth as auth_routes
from app.config import Settings
from app.db import Base, get_session
from app.models import AccountUser, AdminAuditEvent, AuthChallenge, RefreshSession


CURRENT_PASSWORD = "G7!vB2#qL9@xSecure"
NEW_PASSWORD = "N8!qZ4@tK2#vFresh"


@pytest.fixture
def reset_app(monkeypatch):
    settings = Settings(
        environment="development",
        database_url="sqlite:///:memory:",
        jwt_secret="password-reset-test-secret-more-than-thirty-two-characters",
        frontend_url="https://app.example.test",
        password_min_characters=8,
        password_reset_seconds=1800,
        password_reset_request_rate_limit=100,
        password_reset_identifier_rate_limit=100,
        password_reset_confirm_rate_limit=100,
        smtp_host="smtp.example.test",
        smtp_from_email="security@example.test",
    )
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    monkeypatch.setattr(auth_routes, "settings", settings)
    auth_routes.auth_rate_limiter.clear()

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)

    def override_session():
        yield session

    app = FastAPI()
    app.include_router(auth_routes.router)
    app.dependency_overrides[get_session] = override_session
    captured_links: list[tuple[str, str]] = []
    changed_notices: list[str] = []
    monkeypatch.setattr(
        auth_routes,
        "send_password_reset_email",
        lambda destination, reset_url, **kwargs: captured_links.append((destination, reset_url)),
    )
    monkeypatch.setattr(
        auth_routes,
        "send_password_changed_email",
        lambda destination, **kwargs: changed_notices.append(destination),
    )

    with TestClient(app) as client:
        yield client, session, captured_links, changed_notices
    session.close()
    engine.dispose()


def _create_user(session: Session, *, role: str = "customer", email: str | None = "reset@example.test") -> dict:
    return auth.create_user(
        session,
        username=f"reset-{role}",
        email=email,
        phone=None,
        password=CURRENT_PASSWORD,
        role=role,
    )


def _request_token(client: TestClient, captured_links: list[tuple[str, str]], identifier: str) -> str:
    response = client.post("/api/auth/password-reset/request/", json={"identifier": identifier})
    assert response.status_code == 202
    assert captured_links
    reset_url = captured_links[-1][1]
    return parse_qs(urlsplit(reset_url).fragment)["token"][0]


def test_known_and_unknown_reset_requests_are_indistinguishable(reset_app) -> None:
    client, session, captured_links, _ = reset_app
    _create_user(session)

    known = client.post("/api/auth/password-reset/request/", json={"identifier": "reset@example.test"})
    unknown = client.post("/api/auth/password-reset/request/", json={"identifier": "missing@example.test"})

    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json() == {"message": auth_routes.PASSWORD_RESET_REQUEST_MESSAGE}
    assert known.headers["cache-control"] == unknown.headers["cache-control"] == "no-store"
    assert len(captured_links) == 1


def test_reset_token_is_hashed_single_use_and_revokes_authentication_state(reset_app) -> None:
    client, session, captured_links, changed_notices = reset_app
    created = _create_user(session)
    account = session.get(AccountUser, created["id"])
    assert account is not None
    account.failed_login_attempts = 4
    account.locked_until = datetime.now(timezone.utc) + timedelta(minutes=5)
    account.mfa_enabled = True
    session.add(
        RefreshSession(
            id="active-reset-session",
            user_id=account.id,
            family_id="reset-family",
            token_hash="a" * 64,
            remember=True,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
    )
    session.add(
        AuthChallenge(
            id="other-active-challenge",
            user_id=account.id,
            purpose="login",
            remember=True,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
    )
    session.commit()
    original_auth_version = account.auth_version

    token = _request_token(client, captured_links, "reset@example.test")
    digest = hashlib.sha256(token.encode()).hexdigest()
    challenge = session.get(AuthChallenge, digest)
    assert challenge is not None
    assert challenge.id != token
    assert token not in str(challenge.__dict__)

    response = client.post(
        "/api/auth/password-reset/confirm/",
        json={"token": token, "password": NEW_PASSWORD},
    )
    assert response.status_code == 200
    assert response.json()["message"].startswith("Password updated")
    session.refresh(account)
    assert not auth.check_password(CURRENT_PASSWORD, account.password_hash)
    assert auth.check_password(NEW_PASSWORD, account.password_hash)
    assert account.auth_version == original_auth_version + 1
    assert account.failed_login_attempts == 0
    assert account.locked_until is None
    assert account.mfa_enabled is True
    assert session.get(RefreshSession, "active-reset-session").revoke_reason == "password_reset"
    assert all(
        item.consumed_at is not None
        for item in session.scalars(select(AuthChallenge).where(AuthChallenge.user_id == account.id))
    )
    audit = session.scalar(select(AdminAuditEvent).where(AdminAuditEvent.action == "auth.password_reset.completed"))
    assert audit is not None
    assert token not in str(audit.__dict__)
    assert NEW_PASSWORD not in str(audit.__dict__)
    assert changed_notices == ["reset@example.test"]

    replay = client.post(
        "/api/auth/password-reset/confirm/",
        json={"token": token, "password": "T9!xK4@pM7#zAgain"},
    )
    assert replay.status_code == 400
    assert replay.json()["detail"] == "This reset link is invalid, expired, or already used"


def test_invalid_policy_does_not_consume_reset_link(reset_app) -> None:
    client, session, captured_links, _ = reset_app
    _create_user(session)
    token = _request_token(client, captured_links, "reset@example.test")
    digest = hashlib.sha256(token.encode()).hexdigest()

    weak = client.post(
        "/api/auth/password-reset/confirm/",
        json={"token": token, "password": "lowercase1!"},
    )
    assert weak.status_code == 400
    assert "uppercase" in weak.json()["detail"]
    assert session.get(AuthChallenge, digest).consumed_at is None

    valid = client.post(
        "/api/auth/password-reset/confirm/",
        json={"token": token, "password": NEW_PASSWORD},
    )
    assert valid.status_code == 200


def test_expired_and_no_email_requests_fail_safely(reset_app) -> None:
    client, session, captured_links, _ = reset_app
    _create_user(session)
    _create_user(session, role="operator", email=None)
    token = _request_token(client, captured_links, "reset@example.test")
    challenge = session.get(AuthChallenge, hashlib.sha256(token.encode()).hexdigest())
    challenge.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    session.commit()

    expired = client.post(
        "/api/auth/password-reset/confirm/",
        json={"token": token, "password": NEW_PASSWORD},
    )
    no_email = client.post(
        "/api/auth/password-reset/request/",
        json={"identifier": "reset-operator"},
    )
    assert expired.status_code == 400
    assert expired.json()["detail"] == "This reset link is invalid, expired, or already used"
    assert no_email.status_code == 202
    assert len(captured_links) == 1
