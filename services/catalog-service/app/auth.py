from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_session
from .models import AccountUser


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login/", auto_error=False)
ACCESS_TOKEN_MINUTES = 60
REFRESH_TOKEN_DAYS = 14
ALLOWED_ROLES = {"customer", "seller", "operator", "admin"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _encode_token(user: dict[str, Any], token_type: str, expires_delta: timedelta) -> str:
    settings = get_settings()
    payload = {
        "sub": str(user["id"]),
        "role": user.get("role") or "customer",
        "type": token_type,
        "exp": _now() + expires_delta,
        "iat": _now(),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def build_token_response(user: dict[str, Any]) -> dict[str, Any]:
    access = _encode_token(user, "access", timedelta(minutes=ACCESS_TOKEN_MINUTES))
    refresh = _encode_token(user, "refresh", timedelta(days=REFRESH_TOKEN_DAYS))
    return {
        "access": access,
        "refresh": refresh,
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "user": serialize_user(user),
        "roles": [user.get("role") or "customer"],
    }


def serialize_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "username": user.get("username"),
        "email": user.get("email"),
        "phone": user.get("phone"),
        "role": user.get("role") or "customer",
    }


def make_password(password: str, iterations: int = 1_200_000) -> str:
    salt = secrets.token_urlsafe(12)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${base64.b64encode(dk).decode()}"


def check_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        algorithm, iterations_raw, salt, digest = encoded.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    iterations = int(iterations_raw)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations)
    calculated = base64.b64encode(dk).decode()
    return hmac.compare_digest(calculated, digest)


def _role_from_legacy(row: sqlite3.Row) -> str:
    role = row["role"] if "role" in row.keys() else None
    if role:
        return role
    if row["is_superuser"] or row["is_staff"]:
        return "admin"
    return "customer"


def _legacy_user_by_identifier(identifier: str) -> dict[str, Any] | None:
    legacy_path = get_settings().resolved_legacy_sqlite_path()
    if not legacy_path.exists():
        return None
    query = """
        SELECT id, username, email, phone, password, role, is_superuser, is_staff, is_active
        FROM accounts_user
        WHERE username = ? OR email = ? OR phone = ?
        LIMIT 1
    """
    with sqlite3.connect(legacy_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(query, (identifier, identifier, identifier)).fetchone()
    if row is None or not row["is_active"]:
        return None
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "phone": row["phone"],
        "password_hash": row["password"],
        "role": _role_from_legacy(row),
    }


def _legacy_max_user_id() -> int:
    legacy_path = get_settings().resolved_legacy_sqlite_path()
    if not legacy_path.exists():
        return 0
    with sqlite3.connect(legacy_path) as conn:
        row = conn.execute("SELECT MAX(id) FROM accounts_user").fetchone()
    return int(row[0] or 0)


def _local_user_to_dict(user: AccountUser) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "phone": user.phone,
        "password_hash": user.password_hash,
        "role": user.role,
    }


def authenticate_user(session: Session, identifier: str, password: str) -> dict[str, Any] | None:
    legacy_user = _legacy_user_by_identifier(identifier)
    if legacy_user and check_password(password, legacy_user["password_hash"]):
        return legacy_user

    user = session.scalar(
        select(AccountUser).where(
            or_(
                AccountUser.username == identifier,
                AccountUser.email == identifier,
                AccountUser.phone == identifier,
            )
        )
    )
    if user and user.is_active and check_password(password, user.password_hash):
        return _local_user_to_dict(user)
    return None


def create_user(session: Session, *, username: str | None, email: str | None, phone: str | None, password: str, role: str) -> dict[str, Any]:
    normalized_role = role if role in ALLOWED_ROLES else "customer"
    identifier = username or email or phone
    if not identifier:
        raise HTTPException(status_code=400, detail="username, email, or phone required")
    if email and _legacy_user_by_identifier(email):
        raise HTTPException(status_code=400, detail="Account already exists")
    if phone and _legacy_user_by_identifier(phone):
        raise HTTPException(status_code=400, detail="Account already exists")
    if username and _legacy_user_by_identifier(username):
        raise HTTPException(status_code=400, detail="Account already exists")

    checks = [AccountUser.username == identifier]
    if email:
        checks.append(AccountUser.email == email)
    if phone:
        checks.append(AccountUser.phone == phone)
    existing = session.scalar(select(AccountUser).where(or_(*checks)))
    if existing:
        raise HTTPException(status_code=400, detail="Account already exists")

    next_id = max(session.scalar(select(func.max(AccountUser.id))) or 0, _legacy_max_user_id() + 100_000) + 1
    user = AccountUser(
        id=next_id,
        username=identifier,
        email=email,
        phone=phone,
        password_hash=make_password(password),
        role=normalized_role,
        is_staff=normalized_role in {"admin", "operator"},
        is_superuser=normalized_role == "admin",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return _local_user_to_dict(user)


def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(refresh_token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    user = {
        "id": int(payload["sub"]),
        "username": None,
        "email": None,
        "phone": None,
        "role": payload.get("role") or "customer",
    }
    return build_token_response(user)


def get_current_user(request: Request, token: str | None = Depends(oauth2_scheme)) -> dict[str, Any]:
    token = token or request.cookies.get("sourceai_access")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token") from exc

    if payload.get("type") not in {None, "access"}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")
    user_id = payload.get("sub")
    role = payload.get("role")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing user in token")

    return {
        "sub": int(user_id),
        "role": role or "customer",
    }


def get_current_user_detail(
    current_user: dict[str, Any] = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    user = session.get(AccountUser, current_user["sub"])
    if user:
        return serialize_user(_local_user_to_dict(user))

    legacy_path = get_settings().resolved_legacy_sqlite_path()
    if legacy_path.exists():
        with sqlite3.connect(legacy_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT id, username, email, phone, role, is_superuser, is_staff, is_active FROM accounts_user WHERE id = ? LIMIT 1",
                (current_user["sub"],),
            ).fetchone()
        if row and row["is_active"]:
            return serialize_user(
                {
                    "id": row["id"],
                    "username": row["username"],
                    "email": row["email"],
                    "phone": row["phone"],
                    "role": _role_from_legacy(row),
                }
            )
    return {
        "id": current_user["sub"],
        "username": None,
        "email": None,
        "phone": None,
        "role": current_user["role"],
    }
