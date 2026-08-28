from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import jwt
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_session
from .identity import normalize_email_address, normalize_identifier_key, normalize_username
from .models import AccountUser, AdminAuditEvent, AuthChallenge, RefreshSession, SocialIdentity


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login/", auto_error=False)
ALLOWED_ROLES = {"customer", "operator", "admin"}
PRIVILEGED_ROLES = {"operator", "admin"}
RECOVERY_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
DUMMY_PASSWORD_HASH = (
    "pbkdf2_sha256$1200000$sourceai-fixed-dummy-salt$"
    "snMLG5ym8RarDIp4A1yeado8JFAlYRfKDflV/gb3+To="
)


class AccountLockedError(Exception):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = max(1, retry_after)
        super().__init__("Account is temporarily locked")


class AmbiguousLoginIdentifierError(Exception):
    """Raised when legacy data maps one login identifier to multiple accounts."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _user_to_dict(user: AccountUser) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "phone": user.phone,
        "password_hash": user.password_hash,
        "role": user.role,
        "is_active": user.is_active,
        "auth_version": user.auth_version,
        "mfa_enabled": user.mfa_enabled,
    }


def serialize_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "username": user.get("username"),
        "email": user.get("email"),
        "phone": user.get("phone"),
        "role": user.get("role") or "customer",
        "mfa_enabled": bool(user.get("mfa_enabled")),
    }


def make_password(password: str, iterations: int = 1_200_000) -> str:
    salt = secrets.token_urlsafe(12)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${base64.b64encode(digest).decode()}"


def check_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        algorithm, iterations_raw, salt, digest = encoded.split("$", 3)
        iterations = int(iterations_raw)
    except (TypeError, ValueError):
        return False
    if algorithm != "pbkdf2_sha256" or iterations < 100_000 or iterations > 2_000_000:
        return False
    calculated = base64.b64encode(
        hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations)
    ).decode()
    return hmac.compare_digest(calculated, digest)


def validate_password_strength(password: str, identifiers: tuple[str | None, ...] = ()) -> None:
    settings = get_settings()
    errors: list[str] = []
    if len(password) < settings.password_min_characters:
        errors.append(f"at least {settings.password_min_characters} characters")
    if len(password) > settings.password_max_characters:
        errors.append(f"at most {settings.password_max_characters} characters")
    if not any(character.islower() for character in password):
        errors.append("a lowercase letter")
    if not any(character.isupper() for character in password):
        errors.append("an uppercase letter")
    if not any(character.isdigit() for character in password):
        errors.append("a number")
    if not any(not character.isalnum() for character in password):
        errors.append("a symbol")
    normalized_password = password.casefold()
    for identifier in identifiers:
        candidate = (identifier or "").strip().casefold()
        local_part = candidate.split("@", 1)[0]
        if len(local_part) >= 4 and local_part in normalized_password:
            errors.append("no username/email fragments")
            break
    if normalized_password in {
        "password123!",
        "admin123456!",
        "qwerty123456!",
        "changeme123!",
    }:
        errors.append("a non-common password")
    if errors:
        raise ValueError("Password must contain " + ", ".join(dict.fromkeys(errors)))


def _login_identifier_conditions(*identifiers: str | None) -> list[Any]:
    normalized = {
        key
        for identifier in identifiers
        if (key := normalize_identifier_key(identifier)) is not None
    }
    conditions: list[Any] = []
    for value in normalized:
        conditions.extend(
            (
                AccountUser.username_normalized == value,
                AccountUser.email_normalized == value,
                AccountUser.phone_normalized == value,
                # Compatibility for test fixtures and legacy rows awaiting the
                # normalized-identity backfill migration.
                func.lower(AccountUser.username) == value,
                func.lower(AccountUser.email) == value,
                func.lower(AccountUser.phone) == value,
            )
        )
    return conditions


def login_identifier_exists(session: Session, *identifiers: str | None) -> bool:
    """Return whether any value could log in as an existing account."""

    conditions = _login_identifier_conditions(*identifiers)
    if not conditions:
        return False
    return session.scalar(select(AccountUser.id).where(or_(*conditions)).limit(1)) is not None


def find_unique_user_by_identifier(
    session: Session,
    identifier: str,
    *,
    for_update: bool = False,
) -> AccountUser | None:
    conditions = _login_identifier_conditions(identifier)
    if not conditions:
        return None
    statement = select(AccountUser).where(or_(*conditions)).limit(2)
    if for_update:
        statement = statement.with_for_update()
    matches = list(session.scalars(statement))
    if len(matches) > 1:
        raise AmbiguousLoginIdentifierError("Login identifier maps to multiple accounts")
    return matches[0] if matches else None


def _find_user_by_identifier(
    session: Session,
    identifier: str,
    *,
    for_update: bool = False,
) -> AccountUser | None:
    """Backward-compatible internal wrapper around ambiguity-safe lookup."""

    return find_unique_user_by_identifier(session, identifier, for_update=for_update)


def authenticate_user(session: Session, identifier: str, password: str) -> dict[str, Any] | None:
    settings = get_settings()
    try:
        user = find_unique_user_by_identifier(session, identifier, for_update=True)
    except AmbiguousLoginIdentifierError:
        # Fail closed for legacy cross-field collisions without revealing which
        # accounts matched the submitted identifier.
        check_password(password, DUMMY_PASSWORD_HASH)
        return None
    if user is None or not user.is_active:
        # Bound work for nonexistent/disabled accounts without revealing which
        # identifier exists. The per-IP and per-account request limits still
        # provide the primary CPU-exhaustion protection.
        check_password(password, DUMMY_PASSWORD_HASH)
        return None

    now = _now()
    if user.locked_until and _as_utc(user.locked_until) > now:
        if not check_password(password, user.password_hash):
            return None
        retry_after = int((_as_utc(user.locked_until) - now).total_seconds())
        raise AccountLockedError(retry_after)
    if user.locked_until:
        user.locked_until = None
        user.failed_login_attempts = 0

    if not check_password(password, user.password_hash):
        user.failed_login_attempts += 1
        user.last_failed_login_at = now
        if user.failed_login_attempts >= settings.login_failure_limit:
            user.locked_until = now + timedelta(seconds=settings.login_lockout_seconds)
        session.commit()
        return None

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    session.commit()
    session.refresh(user)
    return _user_to_dict(user)


def create_user(
    session: Session,
    *,
    username: str | None,
    email: str | None,
    phone: str | None,
    password: str,
    role: str,
) -> dict[str, Any]:
    try:
        validate_password_strength(password, (username, email, phone))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    normalized_role = role if role in ALLOWED_ROLES else "customer"
    identifier = next(
        (
            normalize_username(candidate)
            for candidate in (username, email, phone)
            if candidate is not None and candidate.strip()
        ),
        "",
    )
    if not identifier:
        raise HTTPException(status_code=400, detail="username, email, or phone required")

    if login_identifier_exists(session, identifier, email, phone):
        raise HTTPException(status_code=400, detail="Account already exists")

    normalized_email = normalize_email_address(email) if email else None
    normalized_phone = phone.strip() if phone else None
    user = AccountUser(
        username=identifier,
        username_normalized=normalize_identifier_key(identifier),
        email=normalized_email,
        email_normalized=normalize_identifier_key(normalized_email),
        phone=normalized_phone,
        phone_normalized=normalize_identifier_key(normalized_phone),
        password_hash=make_password(password),
        role=normalized_role,
        is_staff=normalized_role in PRIVILEGED_ROLES,
        is_superuser=normalized_role == "admin",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return _user_to_dict(user)


def get_or_create_social_user(
    session: Session,
    *,
    provider: str,
    provider_id: str,
    email: str,
    name: str | None = None,
    avatar_url: str | None = None,
) -> dict[str, Any]:
    identity = session.scalar(
        select(SocialIdentity).where(
            SocialIdentity.provider == provider,
            SocialIdentity.provider_subject == provider_id,
        )
    )
    if identity:
        user = session.get(AccountUser, identity.user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=403, detail="Linked account is unavailable")
        if user.role in PRIVILEGED_ROLES:
            raise HTTPException(status_code=403, detail="Privileged accounts must use password sign-in")
        return _user_to_dict(user)

    normalized_email = normalize_email_address(email)
    if login_identifier_exists(session, normalized_email):
        raise HTTPException(
            status_code=409,
            detail="An existing account uses this email. Sign in first before linking Google.",
        )
    created = create_user(
        session,
        username=normalized_email,
        email=normalized_email,
        phone=None,
        password=f"{secrets.token_urlsafe(32)}aA1!",
        role="customer",
    )
    user = session.get(AccountUser, created["id"])
    if not user:
        raise HTTPException(status_code=500, detail="Social account could not be created")
    session.add(
        SocialIdentity(
            user_id=user.id,
            provider=provider,
            provider_subject=provider_id,
            email=normalized_email,
            display_name=name,
            avatar_url=avatar_url,
        )
    )
    session.commit()
    return _user_to_dict(user)


def _encode_token(
    user: dict[str, Any],
    token_type: str,
    expires_delta: timedelta,
    *,
    persistent: bool,
    extra: dict[str, Any] | None = None,
) -> str:
    now = _now()
    payload: dict[str, Any] = {
        "sub": str(user["id"]),
        "role": user.get("role") or "customer",
        "type": token_type,
        "remember": persistent,
        "ver": int(user.get("auth_version") or 1),
        "exp": now + expires_delta,
        "iat": now,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, get_settings().jwt_secret, algorithm="HS256")


def build_token_response(
    user: dict[str, Any],
    *,
    session: Session | None = None,
    persistent: bool = True,
    family_id: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    refresh_id = secrets.token_urlsafe(32)
    refresh_family = family_id or secrets.token_urlsafe(32)
    access = _encode_token(
        user,
        "access",
        timedelta(minutes=settings.access_token_minutes),
        persistent=persistent,
        extra={"jti": secrets.token_urlsafe(24)},
    )
    refresh = _encode_token(
        user,
        "refresh",
        timedelta(days=settings.refresh_token_days),
        persistent=persistent,
        extra={"jti": refresh_id, "family": refresh_family},
    )
    if session is not None:
        session.add(
            RefreshSession(
                id=refresh_id,
                user_id=int(user["id"]),
                family_id=refresh_family,
                token_hash=_token_hash(refresh),
                remember=persistent,
                expires_at=_now() + timedelta(days=settings.refresh_token_days),
            )
        )
        session.commit()
    return {
        "access": access,
        "refresh": refresh,
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "user": serialize_user(user),
        "roles": [user.get("role") or "customer"],
        "persistent": persistent,
    }


def _decode_token(token: str, expected_type: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid {expected_type} token") from exc
    if payload.get("type") != expected_type:
        raise HTTPException(status_code=401, detail=f"Invalid {expected_type} token")
    return payload


def _active_local_user(session: Session, user_id: int) -> AccountUser | None:
    user = session.get(AccountUser, user_id)
    return user if user and user.is_active else None


def refresh_access_token(refresh_token: str, session: Session) -> dict[str, Any]:
    payload = _decode_token(refresh_token, "refresh")
    try:
        user_id = int(payload["sub"])
        refresh_id = str(payload["jti"])
        family_id = str(payload["family"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc

    stored = session.scalar(
        select(RefreshSession)
        .where(RefreshSession.id == refresh_id)
        .with_for_update()
    )
    now = _now()
    if stored is None or not hmac.compare_digest(stored.token_hash, _token_hash(refresh_token)):
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if stored.revoked_at is not None:
        if stored.replaced_by_id:
            session.execute(
                update(RefreshSession)
                .where(
                    RefreshSession.family_id == stored.family_id,
                    RefreshSession.revoked_at.is_(None),
                )
                .values(revoked_at=now, revoke_reason="replay-detected")
            )
            session.commit()
        raise HTTPException(status_code=401, detail="Refresh token has already been used")
    if _as_utc(stored.expires_at) <= now or stored.family_id != family_id:
        stored.revoked_at = now
        stored.revoke_reason = "expired"
        session.commit()
        raise HTTPException(status_code=401, detail="Refresh token expired")

    user = _active_local_user(session, user_id)
    if user is None or int(payload.get("ver") or 0) != user.auth_version:
        stored.revoked_at = now
        stored.revoke_reason = "account-changed"
        session.commit()
        raise HTTPException(status_code=401, detail="Account is unavailable")

    replacement_id = secrets.token_urlsafe(32)
    stored.revoked_at = now
    stored.revoke_reason = "rotated"
    stored.last_used_at = now
    stored.replaced_by_id = replacement_id
    user_dict = _user_to_dict(user)
    settings = get_settings()
    access = _encode_token(
        user_dict,
        "access",
        timedelta(minutes=settings.access_token_minutes),
        persistent=stored.remember,
        extra={"jti": secrets.token_urlsafe(24)},
    )
    refresh = _encode_token(
        user_dict,
        "refresh",
        timedelta(days=settings.refresh_token_days),
        persistent=stored.remember,
        extra={"jti": replacement_id, "family": family_id},
    )
    session.add(
        RefreshSession(
            id=replacement_id,
            user_id=user.id,
            family_id=family_id,
            token_hash=_token_hash(refresh),
            remember=stored.remember,
            expires_at=now + timedelta(days=settings.refresh_token_days),
        )
    )
    session.commit()
    return {
        "access": access,
        "refresh": refresh,
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "user": serialize_user(user_dict),
        "roles": [user.role],
        "persistent": stored.remember,
    }


def revoke_refresh_token(session: Session, refresh_token: str | None, *, reason: str = "logout") -> None:
    if not refresh_token:
        return
    try:
        payload = jwt.decode(
            refresh_token,
            get_settings().jwt_secret,
            algorithms=["HS256"],
            options={"verify_exp": False},
        )
        refresh_id = str(payload["jti"])
    except (jwt.PyJWTError, KeyError, TypeError):
        return
    stored = session.get(RefreshSession, refresh_id)
    if stored and hmac.compare_digest(stored.token_hash, _token_hash(refresh_token)) and stored.revoked_at is None:
        stored.revoked_at = _now()
        stored.revoke_reason = reason
        session.commit()


def revoke_all_user_sessions(session: Session, user_id: int, *, reason: str) -> None:
    session.execute(
        update(RefreshSession)
        .where(RefreshSession.user_id == user_id, RefreshSession.revoked_at.is_(None))
        .values(revoked_at=_now(), revoke_reason=reason)
    )
    session.commit()


def create_password_reset_challenge(session: Session, user: AccountUser) -> str:
    """Issue one opaque reset credential while persisting only its SHA-256 digest."""

    now = _now()
    session.execute(
        update(AuthChallenge)
        .where(
            AuthChallenge.user_id == user.id,
            AuthChallenge.purpose == "password_reset",
            AuthChallenge.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )
    token = secrets.token_urlsafe(48)
    session.add(
        AuthChallenge(
            id=_token_hash(token),
            user_id=user.id,
            purpose="password_reset",
            remember=False,
            expires_at=now + timedelta(seconds=get_settings().password_reset_seconds),
        )
    )
    session.commit()
    return token


def complete_password_reset(
    session: Session,
    *,
    token: str,
    password: str,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Atomically replace a password and invalidate every outstanding auth credential."""

    now = _now()
    challenge = session.scalar(
        select(AuthChallenge)
        .where(AuthChallenge.id == _token_hash(token))
        .with_for_update()
    )
    if (
        challenge is None
        or challenge.purpose != "password_reset"
        or challenge.consumed_at is not None
        or _as_utc(challenge.expires_at) <= now
    ):
        raise ValueError("This reset link is invalid, expired, or already used")

    user = session.scalar(
        select(AccountUser)
        .where(AccountUser.id == challenge.user_id, AccountUser.is_active.is_(True))
        .with_for_update()
    )
    if user is None:
        raise ValueError("This reset link is invalid, expired, or already used")

    validate_password_strength(password, (user.username, user.email, user.phone))
    if check_password(password, user.password_hash):
        raise ValueError("New password must differ from the current password")

    user.password_hash = make_password(password)
    user.auth_version += 1
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_failed_login_at = None
    session.execute(
        update(RefreshSession)
        .where(RefreshSession.user_id == user.id, RefreshSession.revoked_at.is_(None))
        .values(revoked_at=now, revoke_reason="password_reset")
    )
    session.execute(
        update(AuthChallenge)
        .where(AuthChallenge.user_id == user.id, AuthChallenge.consumed_at.is_(None))
        .values(consumed_at=now)
    )
    session.add(
        AdminAuditEvent(
            actor_user_id=user.id,
            actor_role=user.role,
            action="auth.password_reset.completed",
            entity_type="account",
            entity_id=str(user.id),
            request_id=request_id,
            after_data={"auth_version": user.auth_version, "sessions_revoked": True},
            note="Self-service password reset completed; authentication state invalidated.",
        )
    )
    session.commit()
    session.refresh(user)
    return _user_to_dict(user)


def create_mfa_challenge(
    session: Session,
    user: dict[str, Any],
    *,
    purpose: str,
    persistent: bool,
) -> str:
    settings = get_settings()
    challenge_id = secrets.token_urlsafe(32)
    expiry = _now() + timedelta(seconds=settings.mfa_challenge_seconds)
    session.add(
        AuthChallenge(
            id=challenge_id,
            user_id=int(user["id"]),
            purpose=purpose,
            remember=persistent,
            expires_at=expiry,
        )
    )
    session.commit()
    return _encode_token(
        user,
        "mfa_challenge",
        timedelta(seconds=settings.mfa_challenge_seconds),
        persistent=persistent,
        extra={"jti": challenge_id, "purpose": purpose},
    )


def _load_mfa_challenge(
    session: Session,
    token: str,
    *,
    purpose: str,
) -> tuple[AuthChallenge, AccountUser]:
    payload = _decode_token(token, "mfa_challenge")
    if payload.get("purpose") != purpose:
        raise HTTPException(status_code=401, detail="Invalid MFA challenge")
    try:
        user_id = int(payload["sub"])
        challenge_id = str(payload["jti"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid MFA challenge") from exc
    # Serialize confirmation/restart attempts so a challenge remains truly
    # one-use when multiple requests arrive at the same time.
    challenge = session.scalar(
        select(AuthChallenge)
        .where(AuthChallenge.id == challenge_id)
        .with_for_update()
    )
    user = session.scalar(
        select(AccountUser)
        .where(AccountUser.id == user_id, AccountUser.is_active.is_(True))
        .with_for_update()
    )
    now = _now()
    if (
        challenge is None
        or user is None
        or challenge.user_id != user_id
        or challenge.purpose != purpose
        or challenge.consumed_at is not None
        or _as_utc(challenge.expires_at) <= now
        or int(payload.get("ver") or 0) != user.auth_version
    ):
        raise HTTPException(status_code=401, detail="MFA challenge expired or already used")
    if user.mfa_locked_until and _as_utc(user.mfa_locked_until) > now:
        retry_after = max(1, int((_as_utc(user.mfa_locked_until) - now).total_seconds()))
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Authenticator verification is temporarily locked. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )
    if user.mfa_locked_until:
        user.mfa_locked_until = None
        user.mfa_failed_attempts = 0
    return challenge, user


def _fernet() -> Fernet:
    try:
        return Fernet(get_settings().resolved_mfa_encryption_key())
    except (TypeError, ValueError) as exc:
        raise RuntimeError("MFA encryption key is invalid") from exc


def _new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _decrypt_totp_secret(encrypted: str | None) -> str:
    if not encrypted:
        raise HTTPException(status_code=409, detail="MFA enrollment has not started")
    try:
        return _fernet().decrypt(encrypted.encode()).decode()
    except (InvalidToken, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=500, detail="Stored MFA credential is unavailable") from exc


def _totp(secret: str, counter: int) -> str:
    padded = secret + ("=" * ((8 - len(secret) % 8) % 8))
    key = base64.b32decode(padded, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{value:06d}"


def matching_totp_counter(
    secret: str,
    code: str,
    *,
    timestamp: float | None = None,
    window: int = 1,
) -> int | None:
    normalized = "".join(character for character in code if character.isdigit())
    if len(normalized) != 6:
        return None
    counter = int((timestamp if timestamp is not None else time.time()) // 30)
    for offset in range(-window, window + 1):
        candidate = counter + offset
        if hmac.compare_digest(_totp(secret, candidate), normalized):
            return candidate
    return None


def verify_totp(secret: str, code: str, *, timestamp: float | None = None, window: int = 1) -> bool:
    return matching_totp_counter(
        secret,
        code,
        timestamp=timestamp,
        window=window,
    ) is not None


def _recovery_hash(code: str) -> str:
    normalized = "".join(character for character in code.upper() if character.isalnum())
    return hmac.new(
        get_settings().resolved_mfa_encryption_key(),
        normalized.encode(),
        hashlib.sha256,
    ).hexdigest()


def _new_recovery_codes(count: int = 10) -> list[str]:
    codes: list[str] = []
    for _ in range(count):
        raw = "".join(secrets.choice(RECOVERY_ALPHABET) for _ in range(15))
        codes.append(f"{raw[:5]}-{raw[5:10]}-{raw[10:]}")
    return codes


def begin_mfa_enrollment(session: Session, challenge_token: str) -> dict[str, str]:
    _, user = _load_mfa_challenge(session, challenge_token, purpose="enroll")
    if user.mfa_enabled:
        raise HTTPException(status_code=409, detail="MFA is already enabled")
    if user.mfa_secret_encrypted:
        secret = _decrypt_totp_secret(user.mfa_secret_encrypted)
    else:
        secret = _new_totp_secret()
        user.mfa_secret_encrypted = _fernet().encrypt(secret.encode()).decode()
        user.mfa_recovery_hashes = []
        session.commit()
    label = quote(f"{get_settings().mfa_issuer}:{user.username}", safe="")
    issuer = quote(get_settings().mfa_issuer, safe="")
    uri = f"otpauth://totp/{label}?secret={secret}&issuer={issuer}&algorithm=SHA1&digits=6&period=30"
    return {"secret": secret, "otpauth_uri": uri}


def restart_mfa_enrollment(
    session: Session,
    challenge_token: str,
) -> tuple[dict[str, str], dict[str, Any]]:
    """Rotate an unconfirmed TOTP credential behind an active password challenge."""

    challenge, user = _load_mfa_challenge(session, challenge_token, purpose="enroll")
    if user.mfa_enabled:
        raise HTTPException(status_code=409, detail="MFA is already enabled")

    secret = _new_totp_secret()
    user.mfa_secret_encrypted = _fernet().encrypt(secret.encode()).decode()
    user.mfa_recovery_hashes = []
    challenge.failed_attempts = 0
    session.commit()

    label = quote(f"{get_settings().mfa_issuer}:{user.username}", safe="")
    issuer = quote(get_settings().mfa_issuer, safe="")
    uri = f"otpauth://totp/{label}?secret={secret}&issuer={issuer}&algorithm=SHA1&digits=6&period=30"
    return {"secret": secret, "otpauth_uri": uri}, _user_to_dict(user)


def _record_mfa_failure(session: Session, challenge: AuthChallenge, user: AccountUser) -> None:
    settings = get_settings()
    challenge.failed_attempts += 1
    user.mfa_failed_attempts += 1
    if (
        challenge.failed_attempts >= settings.mfa_challenge_attempt_limit
        or user.mfa_failed_attempts >= settings.mfa_challenge_attempt_limit
    ):
        now = _now()
        challenge.consumed_at = now
        user.mfa_locked_until = now + timedelta(seconds=settings.login_lockout_seconds)
        user.failed_login_attempts = settings.login_failure_limit
        user.locked_until = now + timedelta(seconds=settings.login_lockout_seconds)
        user.last_failed_login_at = now
    session.commit()


def confirm_mfa_enrollment(
    session: Session,
    challenge_token: str,
    code: str,
) -> tuple[dict[str, Any], list[str], bool]:
    challenge, user = _load_mfa_challenge(session, challenge_token, purpose="enroll")
    secret = _decrypt_totp_secret(user.mfa_secret_encrypted)
    matched_counter = matching_totp_counter(secret, code)
    if matched_counter is None or (
        user.last_totp_counter is not None
        and matched_counter <= user.last_totp_counter
    ):
        _record_mfa_failure(session, challenge, user)
        raise HTTPException(status_code=401, detail="Invalid authentication code")
    recovery_codes = _new_recovery_codes()
    user.mfa_recovery_hashes = [_recovery_hash(item) for item in recovery_codes]
    user.mfa_enabled = True
    user.mfa_enrolled_at = _now()
    user.mfa_failed_attempts = 0
    user.mfa_locked_until = None
    user.auth_version += 1
    challenge.consumed_at = _now()
    session.commit()
    session.refresh(user)
    return _user_to_dict(user), recovery_codes, challenge.remember


def verify_mfa_login(
    session: Session,
    challenge_token: str,
    *,
    code: str | None,
    recovery_code: str | None,
) -> tuple[dict[str, Any], bool, bool]:
    challenge, user = _load_mfa_challenge(session, challenge_token, purpose="login")
    if not user.mfa_enabled:
        raise HTTPException(status_code=409, detail="MFA is not enabled")
    secret = _decrypt_totp_secret(user.mfa_secret_encrypted)
    used_recovery = False
    matched_counter = matching_totp_counter(secret, code) if code else None
    valid = bool(
        matched_counter is not None
        and (
            user.last_totp_counter is None
            or matched_counter > user.last_totp_counter
        )
    )
    if not valid and recovery_code:
        candidate = _recovery_hash(recovery_code)
        stored_hashes = list(user.mfa_recovery_hashes or [])
        match = next((item for item in stored_hashes if hmac.compare_digest(item, candidate)), None)
        if match:
            stored_hashes.remove(match)
            user.mfa_recovery_hashes = stored_hashes
            valid = True
            used_recovery = True
    if not valid:
        _record_mfa_failure(session, challenge, user)
        raise HTTPException(status_code=401, detail="Invalid authentication code")
    user.mfa_failed_attempts = 0
    user.mfa_locked_until = None
    if not used_recovery:
        user.last_totp_counter = matched_counter
    challenge.consumed_at = _now()
    session.commit()
    session.refresh(user)
    return _user_to_dict(user), challenge.remember, used_recovery


def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    token = token or request.cookies.get("sourceai_access")
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    payload = _decode_token(token, "access")
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Missing user in token") from exc
    user = _active_local_user(session, user_id)
    if user is None or int(payload.get("ver") or 0) != user.auth_version:
        raise HTTPException(status_code=401, detail="Account is unavailable")
    return {"sub": user.id, "role": user.role}


def get_current_privileged_user(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    if current_user["role"] not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin or operator access required")
    return current_user


def get_current_user_detail(
    current_user: dict[str, Any] = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    user = _active_local_user(session, current_user["sub"])
    if user is None:
        raise HTTPException(status_code=401, detail="Account is unavailable")
    return serialize_user(_user_to_dict(user))
