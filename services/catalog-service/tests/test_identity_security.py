from __future__ import annotations

import importlib
import time
from datetime import timedelta

import jwt
import pytest
from fastapi import FastAPI, HTTPException, Response
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db import Base, get_session
from app.models import AccountUser, AdminAuditEvent, AuthChallenge, RefreshSession
from app.schemas import RegisterIn


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
        password_min_characters=8,
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


def test_password_policy_accepts_eight_characters_and_rejects_seven(
    settings: Settings,
) -> None:
    auth.validate_password_strength("Aa1!bcde")

    with pytest.raises(ValueError, match="at least 8 characters"):
        auth.validate_password_strength("Aa1!bcd")


@pytest.mark.parametrize(
    "password",
    [
        "aa1!bcde",
        "AA1!BCDE",
        "Aa!!bcde",
        "Aa12bcde",
    ],
)
def test_eight_character_password_keeps_every_composition_requirement(
    settings: Settings,
    password: str,
) -> None:
    with pytest.raises(ValueError, match="Password must contain"):
        auth.validate_password_strength(password)


def test_registration_route_accepts_exactly_eight_strong_characters(
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
    monkeypatch.setattr(auth_routes, "settings", settings)
    auth_routes.auth_rate_limiter.clear()

    def override_session():
        yield session

    app = FastAPI()
    app.include_router(auth_routes.router)
    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as client:
        response = client.post(
            "/api/auth/register/",
            json={
                "username": "eight-char-user",
                "email": "eight-char-user@example.test",
                "password": "Aa1!bcde",
            },
        )

    assert response.status_code == 201
    assert response.json()["user"]["username"] == "eight-char-user"
    session.close()
    engine.dispose()


def test_remember_me_controls_secure_cookie_persistence(monkeypatch, settings: Settings) -> None:
    monkeypatch.setattr(auth_routes, "settings", settings)
    tokens = {"access": "access-token", "refresh": "refresh-token"}

    persistent_response = Response()
    auth_routes._set_auth_cookies(
        persistent_response,
        tokens,
        secure=True,
        persistent=True,
    )
    persistent_cookies = persistent_response.headers.getlist("set-cookie")
    assert len(persistent_cookies) == 2
    assert all("HttpOnly" in cookie and "SameSite=lax" in cookie and "Secure" in cookie for cookie in persistent_cookies)
    assert any(f"Max-Age={settings.access_token_minutes * 60}" in cookie for cookie in persistent_cookies)
    assert any(f"Max-Age={settings.refresh_token_days * 86400}" in cookie for cookie in persistent_cookies)

    session_response = Response()
    auth_routes._set_auth_cookies(
        session_response,
        tokens,
        secure=True,
        persistent=False,
    )
    session_cookies = session_response.headers.getlist("set-cookie")
    assert len(session_cookies) == 2
    assert all("Max-Age=" not in cookie and "Expires=" not in cookie for cookie in session_cookies)


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
    # The threshold-crossing response remains the same generic authentication
    # failure as the earlier attempts. Revealing the lock only after a correct
    # password prevents the lock state from becoming an account oracle.
    assert auth.authenticate_user(session, created["username"], "wrong-password") is None

    stored = session.get(AccountUser, created["id"])
    assert stored is not None
    assert stored.failed_login_attempts == settings.login_failure_limit
    assert stored.locked_until is not None
    assert auth.authenticate_user(session, created["username"], "wrong-password") is None
    with pytest.raises(auth.AccountLockedError) as locked:
        auth.authenticate_user(session, created["username"], "G7!vB2#qL9@xSecure")
    assert 0 < locked.value.retry_after <= settings.login_lockout_seconds


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


def test_registration_rejects_header_injection_email() -> None:
    with pytest.raises(ValueError, match="line breaks"):
        RegisterIn(
            username="safe-user",
            email="buyer@example.com\r\nBcc: attacker@example.com",
            password="G7!vB2#qL9@xSecure",
        )


def test_unicode_casefold_identity_is_unique_and_login_stable(
    session: Session,
) -> None:
    created = auth.create_user(
        session,
        username="StraßeBuyer",
        email="unicode-buyer@example.test",
        phone=None,
        password="G7!vB2#qL9@xSecure",
        role="customer",
    )

    authenticated = auth.authenticate_user(
        session,
        "STRASSEBUYER",
        "G7!vB2#qL9@xSecure",
    )
    assert authenticated is not None
    assert authenticated["id"] == created["id"]
    with pytest.raises(HTTPException, match="Account already exists"):
        auth.create_user(
            session,
            username="STRASSEBUYER",
            email="other-unicode@example.test",
            phone=None,
            password="V8!nM4@qZ7#cSecure",
            role="customer",
        )


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

    replay_token = auth.create_mfa_challenge(
        session,
        verified_user,
        purpose="login",
        persistent=False,
    )
    with pytest.raises(HTTPException, match="Invalid authentication code"):
        auth.verify_mfa_login(
            session,
            replay_token,
            code=_current_totp(enrollment["secret"]),
            recovery_code=None,
        )

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


def test_pending_mfa_enrollment_retry_reuses_the_same_provisioning_uri(
    session: Session,
) -> None:
    """A harmless enroll/start retry must not silently change the app credential."""

    created = _user(session)
    enroll_token = auth.create_mfa_challenge(
        session,
        created,
        purpose="enroll",
        persistent=True,
    )

    first = auth.begin_mfa_enrollment(session, enroll_token)
    retried = auth.begin_mfa_enrollment(session, enroll_token)

    assert retried == first
    assert retried["otpauth_uri"].startswith("otpauth://totp/")


def test_restart_mfa_enrollment_rotates_pending_secret_and_resets_challenge_attempts(
    session: Session,
    settings: Settings,
) -> None:
    created = _user(session)
    enroll_token = auth.create_mfa_challenge(
        session,
        created,
        purpose="enroll",
        persistent=True,
    )
    first = auth.begin_mfa_enrollment(session, enroll_token)
    challenge_id = jwt.decode(
        enroll_token,
        settings.jwt_secret,
        algorithms=["HS256"],
    )["jti"]
    challenge = session.get(AuthChallenge, challenge_id)
    assert challenge is not None
    challenge.failed_attempts = 2
    session.commit()

    restarted, user = auth.restart_mfa_enrollment(session, enroll_token)

    assert user["id"] == created["id"]
    assert restarted["secret"] != first["secret"]
    assert restarted["otpauth_uri"] != first["otpauth_uri"]
    assert challenge.failed_attempts == 0
    stored = session.get(AccountUser, created["id"])
    assert stored is not None
    assert stored.mfa_enabled is False
    assert stored.mfa_secret_encrypted != restarted["secret"]
    assert auth._decrypt_totp_secret(stored.mfa_secret_encrypted) == restarted["secret"]


def test_expired_mfa_enrollment_challenge_cannot_be_restarted(
    session: Session,
    settings: Settings,
) -> None:
    """An expired token cannot mint or recover a credential without a new password login."""

    created = _user(session)
    enroll_token = auth.create_mfa_challenge(
        session,
        created,
        purpose="enroll",
        persistent=True,
    )
    challenge_id = jwt.decode(
        enroll_token,
        settings.jwt_secret,
        algorithms=["HS256"],
    )["jti"]
    challenge = session.get(AuthChallenge, challenge_id)
    assert challenge is not None
    challenge.expires_at = auth._now() - timedelta(seconds=1)
    session.commit()

    with pytest.raises(HTTPException, match="expired or already used"):
        auth.begin_mfa_enrollment(session, enroll_token)
    with pytest.raises(HTTPException, match="expired or already used"):
        auth.restart_mfa_enrollment(session, enroll_token)


def test_totp_validation_allows_only_one_adjacent_time_step(settings: Settings) -> None:
    secret = "JBSWY3DPEHPK3PXP"
    counter = 60_000_000
    timestamp = (counter * 30) + 15

    assert auth.verify_totp(secret, auth._totp(secret, counter), timestamp=timestamp)
    assert auth.verify_totp(secret, auth._totp(secret, counter - 1), timestamp=timestamp)
    assert auth.verify_totp(secret, auth._totp(secret, counter + 1), timestamp=timestamp)
    assert not auth.verify_totp(secret, auth._totp(secret, counter - 2), timestamp=timestamp)
    assert not auth.verify_totp(secret, auth._totp(secret, counter + 2), timestamp=timestamp)


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
    assert user.mfa_locked_until is not None


def test_mfa_failures_accumulate_across_rotated_challenges(
    session: Session,
    settings: Settings,
) -> None:
    created = _user(session)
    user = session.get(AccountUser, created["id"])
    assert user is not None
    secret = auth._new_totp_secret()
    user.mfa_enabled = True
    user.mfa_secret_encrypted = auth._fernet().encrypt(secret.encode()).decode()
    session.commit()

    for _ in range(settings.mfa_challenge_attempt_limit):
        challenge_token = auth.create_mfa_challenge(
            session,
            auth._user_to_dict(user),
            purpose="login",
            persistent=False,
        )
        with pytest.raises(HTTPException):
            auth.verify_mfa_login(
                session,
                challenge_token,
                code="000000",
                recovery_code=None,
            )

    session.refresh(user)
    assert user.mfa_failed_attempts == settings.mfa_challenge_attempt_limit
    assert user.mfa_locked_until is not None


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
        restarted = client.post(
            "/api/auth/mfa/enroll/restart/",
            json={"mfa_token": challenge_token},
        )
        assert restarted.status_code == 200
        assert restarted.json()["secret"] != enrollment.json()["secret"]
        assert restarted.json()["otpauth_uri"].startswith("otpauth://totp/")
        audit = session.scalar(
            select(AdminAuditEvent).where(
                AdminAuditEvent.action == "auth.mfa.enrollment_restarted"
            )
        )
        assert audit is not None
        assert audit.actor_user_id == created["id"]
        assert audit.before_data is None
        assert audit.after_data is None
        assert enrollment.json()["secret"] not in (audit.note or "")
        assert restarted.json()["secret"] not in (audit.note or "")
        confirmation = client.post(
            "/api/auth/mfa/enroll/confirm/",
            json={
                "mfa_token": challenge_token,
                "code": _current_totp(restarted.json()["secret"]),
            },
        )
        assert confirmation.status_code == 200
        assert len(confirmation.json()["recovery_codes"]) == 10
        cookies = confirmation.headers.get("set-cookie", "")
        assert "sourceai_access=" in cookies
        assert "sourceai_refresh=" in cookies
    session.close()
    engine.dispose()
