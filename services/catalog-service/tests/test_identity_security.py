from __future__ import annotations

import importlib
import time

import jwt
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db import Base, get_session
from app.models import AccountUser, AuthChallenge, RefreshSession


auth = importlib.import_module("app.auth")
auth_routes = importlib.import_module("app.api.routes.auth")
TEST_MFA_KEY = "EnFxjaW8RPNIWnzKAp9uQz891m0RVLkLxn1QV9gaf0c="


@pytest.fixture
def settings(monkeypatch) -> Settings:
    value = Settings(
        environment="development",
        database_url="sqlite:///:memory:",
        jwt_secret="identity-test-secret-with-more-than-thirty-two-characters",
        mfa_encryption_key=TEST_MFA_KEY,
        password_min_characters=12,
        login_failure_limit=3,
        login_lockout_seconds=120,
        mfa_challenge_attempt_limit=3,
    )
    monkeypatch.setattr(auth, "get_settings", lambda: value)
    return value


@pytest.fixture
def session(settings):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as value:
        yield value
    engine.dispose()


def _user(session: Session, *, role: str = "admin") -> dict:
    return auth.create_user(
        session,
        username=f"{role}-security",
        email=f"{role}-security@example.test",
        phone=None,
        password="G7!vB2#qL9@xSecure",
        role=role,
    )


def _current_totp(secret: str) -> str:
    return auth._totp(secret, int(time.time() // 30))


def test_social_callback_uses_the_configured_frontend_origin(monkeypatch) -> None:
    monkeypatch.setattr(
        auth_routes.settings,
        "frontend_url",
        "https://cross-border-product-sourcing.vercel.app/",
    )
    assert auth_routes._social_callback_uri("google") == (
        "https://cross-border-product-sourcing.vercel.app"
        "/api/auth/social/google/callback/"
    )


def test_failed_passwords_persist_and_lock_the_account(
    session: Session,
    settings: Settings,
) -> None:
    created = _user(session)
    assert auth.authenticate_user(session, created["username"], "wrong-password") is None
    assert auth.authenticate_user(session, created["username"], "wrong-password") is None
    with pytest.raises(auth.AccountLockedError) as locked:
        auth.authenticate_user(session, created["username"], "wrong-password")
    assert locked.value.retry_after == settings.login_lockout_seconds

    stored = session.get(AccountUser, created["id"])
    assert stored is not None
    assert stored.failed_login_attempts == settings.login_failure_limit
    assert stored.locked_until is not None
    with pytest.raises(auth.AccountLockedError):
        auth.authenticate_user(session, created["username"], "G7!vB2#qL9@xSecure")


@pytest.mark.parametrize(
    ("username", "email", "phone"),
    [
        ("customer-security@example.test", "another@example.test", None),
        ("another-customer", "customer-security", None),
        ("another-customer", "another@example.test", "CUSTOMER-SECURITY"),
    ],
)
def test_registration_rejects_cross_field_login_identifier_collisions(
    session: Session,
    username: str,
    email: str,
    phone: str | None,
) -> None:
    auth.create_user(
        session,
        username="customer-security",
        email="customer-security@example.test",
        phone=None,
        password="G7!vB2#qL9@xSecure",
        role="customer",
    )

    with pytest.raises(HTTPException, match="Account already exists"):
        auth.create_user(
            session,
            username=username,
            email=email,
            phone=phone,
            password="V8!nM4@qZ7#cSecure",
            role="customer",
        )


def test_legacy_ambiguous_login_identifier_fails_closed(
    session: Session,
) -> None:
    first = AccountUser(
        username="shared-login",
        email="first@example.test",
        password_hash=auth.make_password("G7!vB2#qL9@xSecure"),
        role="customer",
    )
    second = AccountUser(
        username="second-user",
        email="shared-login",
        password_hash=auth.make_password("V8!nM4@qZ7#cSecure"),
        role="customer",
    )
    session.add_all((first, second))
    session.commit()

    with pytest.raises(auth.AmbiguousLoginIdentifierError):
        auth.find_unique_user_by_identifier(session, "shared-login")
    assert auth.authenticate_user(session, "shared-login", "G7!vB2#qL9@xSecure") is None
    assert first.failed_login_attempts == 0
    assert second.failed_login_attempts == 0


def test_admin_mfa_enrollment_totp_and_one_time_recovery(
    session: Session,
) -> None:
    created = _user(session)
    enroll_token = auth.create_mfa_challenge(
        session,
        created,
        purpose="enroll",
        persistent=True,
    )
    enrollment = auth.begin_mfa_enrollment(session, enroll_token)
    assert enrollment["secret"] not in session.get(AccountUser, created["id"]).mfa_secret_encrypted
    assert enrollment["otpauth_uri"].startswith("otpauth://totp/")

    enrolled_user, recovery_codes, persistent = auth.confirm_mfa_enrollment(
        session,
        enroll_token,
        _current_totp(enrollment["secret"]),
    )
    assert persistent is True
    assert len(recovery_codes) == 10
    stored = session.get(AccountUser, created["id"])
    assert stored is not None and stored.mfa_enabled
    assert stored.mfa_secret_encrypted != enrollment["secret"]
    assert all(code not in stored.mfa_recovery_hashes for code in recovery_codes)
    with pytest.raises(HTTPException, match="already used"):
        auth.confirm_mfa_enrollment(
            session,
            enroll_token,
            _current_totp(enrollment["secret"]),
        )

    login_token = auth.create_mfa_challenge(
        session,
        enrolled_user,
        purpose="login",
        persistent=False,
    )
    verified_user, remember, used_recovery = auth.verify_mfa_login(
        session,
        login_token,
        code=_current_totp(enrollment["secret"]),
        recovery_code=None,
    )
    assert verified_user["id"] == created["id"]
    assert remember is False
    assert used_recovery is False

    recovery_token = auth.create_mfa_challenge(
        session,
        verified_user,
        purpose="login",
        persistent=True,
    )
    _, _, used_recovery = auth.verify_mfa_login(
        session,
        recovery_token,
        code=None,
        recovery_code=recovery_codes[0],
    )
    assert used_recovery is True
    assert len(session.get(AccountUser, created["id"]).mfa_recovery_hashes) == 9


def test_refresh_tokens_rotate_and_replay_revokes_the_family(
    session: Session,
    settings: Settings,
) -> None:
    created = _user(session, role="customer")
    initial = auth.build_token_response(created, session=session, persistent=True)
    payload = jwt.decode(initial["refresh"], settings.jwt_secret, algorithms=["HS256"])
    stored = session.get(RefreshSession, payload["jti"])
    assert stored is not None
    assert stored.token_hash != initial["refresh"]

    rotated = auth.refresh_access_token(initial["refresh"], session)
    rotated_payload = jwt.decode(rotated["refresh"], settings.jwt_secret, algorithms=["HS256"])
    assert rotated_payload["family"] == payload["family"]
    assert session.get(RefreshSession, payload["jti"]).revoke_reason == "rotated"

    with pytest.raises(HTTPException, match="already been used"):
        auth.refresh_access_token(initial["refresh"], session)
    replacement = session.get(RefreshSession, rotated_payload["jti"])
    assert replacement is not None
    assert replacement.revoke_reason == "replay-detected"
    with pytest.raises(HTTPException, match="already been used"):
        auth.refresh_access_token(rotated["refresh"], session)


def test_mfa_challenge_attempt_limit_locks_account(
    session: Session,
    settings: Settings,
) -> None:
    created = _user(session)
    challenge_token = auth.create_mfa_challenge(
        session,
        created,
        purpose="enroll",
        persistent=True,
    )
    auth.begin_mfa_enrollment(session, challenge_token)
    for attempt in range(settings.mfa_challenge_attempt_limit):
        with pytest.raises(HTTPException):
            auth.confirm_mfa_enrollment(session, challenge_token, "000000")
        if attempt + 1 == settings.mfa_challenge_attempt_limit:
            break
    challenge_id = jwt.decode(
        challenge_token,
        settings.jwt_secret,
        algorithms=["HS256"],
    )["jti"]
    challenge = session.get(AuthChallenge, challenge_id)
    user = session.get(AccountUser, created["id"])
    assert challenge is not None and challenge.consumed_at is not None
    assert user is not None and user.locked_until is not None


def test_access_token_version_invalidates_after_security_change(
    session: Session,
    settings: Settings,
) -> None:
    created = _user(session, role="customer")
    initial = auth.build_token_response(created, session=session)
    user = session.get(AccountUser, created["id"])
    user.auth_version += 1
    session.commit()
    payload = jwt.decode(initial["access"], settings.jwt_secret, algorithms=["HS256"])
    assert payload["ver"] != user.auth_version
    assert session.scalar(select(RefreshSession).where(RefreshSession.user_id == user.id)) is not None


def test_privileged_login_issues_no_session_before_mfa_confirmation(
    monkeypatch,
    settings: Settings,
) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    created = _user(session)
    monkeypatch.setattr(auth_routes, "settings", settings)

    def override_session():
        yield session

    app = FastAPI()
    app.include_router(auth_routes.router)
    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login/",
            json={
                "identifier": created["username"],
                "password": "G7!vB2#qL9@xSecure",
                "portal": "admin",
                "remember": True,
            },
        )
        assert login.status_code == 202
        assert login.json()["mfa_enrollment_required"] is True
        assert "set-cookie" not in login.headers
        challenge_token = login.json()["mfa_token"]

        enrollment = client.post(
            "/api/auth/mfa/enroll/start/",
            json={"mfa_token": challenge_token},
        )
        assert enrollment.status_code == 200
        confirmation = client.post(
            "/api/auth/mfa/enroll/confirm/",
            json={
                "mfa_token": challenge_token,
                "code": _current_totp(enrollment.json()["secret"]),
            },
        )
        assert confirmation.status_code == 200
        assert len(confirmation.json()["recovery_codes"]) == 10
        cookies = confirmation.headers.get("set-cookie", "")
        assert "sourceai_access=" in cookies
        assert "sourceai_refresh=" in cookies
    session.close()
    engine.dispose()
