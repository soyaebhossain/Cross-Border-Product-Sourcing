from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from typing import Any
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ...auth import (
    AccountLockedError,
    authenticate_user,
    begin_mfa_enrollment,
    build_token_response,
    confirm_mfa_enrollment,
    create_mfa_challenge,
    create_user,
    get_or_create_social_user,
    get_current_user_detail,
    refresh_access_token,
    revoke_refresh_token,
    verify_mfa_login,
)
from ...config import get_settings
from ...db import get_session
from ...models import AdminAuditEvent
from ...schemas import (
    LoginIn,
    MFAChallengeIn,
    MFAEnrollmentConfirmIn,
    MFAVerifyIn,
    RegisterIn,
)
from ...security import auth_rate_limiter, client_rate_key
from ...social import SocialAuthError, exchange_google_code, google_authorization_url


router = APIRouter()
settings = get_settings()


def _set_auth_cookies(response: Response, tokens: dict[str, Any], *, secure: bool, persistent: bool = True) -> None:
    access_max_age = settings.access_token_minutes * 60 if persistent else None
    refresh_max_age = settings.refresh_token_days * 86400 if persistent else None
    response.set_cookie(
        "sourceai_access",
        tokens["access"],
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=access_max_age,
        path="/",
    )
    response.set_cookie(
        "sourceai_refresh",
        tokens["refresh"],
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=refresh_max_age,
        path="/api/auth/",
    )


def _request_uses_secure_cookies(request: Request) -> bool:
    return settings.cookie_secure_for_scheme(request.url.scheme)


def _social_callback_uri(provider: str) -> str:
    return (
        f"{settings.frontend_url.rstrip('/')}"
        f"/api/auth/social/{provider}/callback/"
    )


async def _bounded_body(request: Request) -> bytes:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            declared_length = int(content_length)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid Content-Length") from exc
        if declared_length < 0 or declared_length > settings.auth_body_max_bytes:
            raise HTTPException(status_code=413, detail="Authentication request is too large")
    body = await request.body()
    if len(body) > settings.auth_body_max_bytes:
        raise HTTPException(status_code=413, detail="Authentication request is too large")
    return body


def _validate_password_length(password: str, *, registration: bool = False) -> None:
    if len(password) > settings.password_max_characters:
        raise HTTPException(status_code=400, detail="Password is too long")
    if registration and len(password) < settings.password_min_characters:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at least {settings.password_min_characters} characters",
        )


def _audit_mfa(
    session: Session,
    *,
    user: dict[str, Any],
    action: str,
    request: Request,
    note: str | None = None,
) -> None:
    session.add(
        AdminAuditEvent(
            actor_user_id=int(user["id"]),
            actor_role=str(user.get("role") or "customer"),
            action=action,
            entity_type="account",
            entity_id=str(user["id"]),
            request_id=getattr(request.state, "request_id", None),
            note=note,
        )
    )
    session.commit()


def _model_or_422(model_type, data: Any):
    try:
        return model_type.model_validate(data)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Invalid authentication payload") from exc


async def _read_login_payload(request: Request) -> LoginIn:
    content_type = request.headers.get("content-type", "")
    body = await _bounded_body(request)
    if "application/json" in content_type:
        try:
            data = json.loads(body.decode() or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON body") from exc
        return _model_or_422(LoginIn, data)

    raw = body.decode()
    form = {key: values[-1] for key, values in parse_qs(raw).items()}
    return _model_or_422(
        LoginIn,
        {
            "identifier": form.get("identifier") or form.get("username"),
            "username": form.get("username"),
            "password": form.get("password") or "",
            "remember": str(form.get("remember", "true")).lower() not in {"0", "false", "off", "no"},
            "portal": form.get("portal") or "customer",
        },
    )


@router.post("/api/auth/login/")
async def login(request: Request, response: Response, session: Session = Depends(get_session)) -> dict[str, Any]:
    auth_rate_limiter.enforce(
        client_rate_key(request, "login"),
        limit=settings.login_rate_limit,
        window_seconds=settings.login_rate_window_seconds,
    )
    payload = await _read_login_payload(request)
    identifier = payload.identifier or payload.email or payload.username or payload.phone
    if not identifier or not payload.password:
        raise HTTPException(status_code=400, detail="identifier and password required")
    if len(identifier) > 320:
        raise HTTPException(status_code=400, detail="Identifier is too long")
    _validate_password_length(payload.password)
    auth_rate_limiter.enforce(
        client_rate_key(request, "login-account", identifier),
        limit=settings.login_account_rate_limit,
        window_seconds=settings.login_account_rate_window_seconds,
    )

    try:
        user = authenticate_user(session, identifier, payload.password)
    except AccountLockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account is temporarily locked. Try again later.",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    is_privileged = user.get("role") in {"admin", "operator"}
    if payload.portal == "admin" and not is_privileged:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account does not have admin access")
    if payload.portal == "customer" and is_privileged:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Use the admin login for this account")
    if is_privileged and (user.get("mfa_enabled") or settings.privileged_mfa_required):
        enrollment_required = not bool(user.get("mfa_enabled"))
        mfa_token = create_mfa_challenge(
            session,
            user,
            purpose="enroll" if enrollment_required else "login",
            persistent=payload.remember,
        )
        response.status_code = status.HTTP_202_ACCEPTED
        return {
            "mfa_required": True,
            "mfa_enrollment_required": enrollment_required,
            "mfa_token": mfa_token,
            "expires_in": settings.mfa_challenge_seconds,
        }
    tokens = build_token_response(user, session=session, persistent=payload.remember)
    _set_auth_cookies(
        response,
        tokens,
        secure=_request_uses_secure_cookies(request),
        persistent=payload.remember,
    )
    return {"user": tokens["user"], "roles": tokens["roles"]}


@router.post("/api/auth/register/", status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    auth_rate_limiter.enforce(
        client_rate_key(request, "register"),
        limit=settings.register_rate_limit,
        window_seconds=settings.register_rate_window_seconds,
    )
    content_type = request.headers.get("content-type", "")
    if "application/json" not in content_type:
        raise HTTPException(status_code=415, detail="Registration requires application/json")
    body = await _bounded_body(request)
    try:
        data = json.loads(body.decode() or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc
    payload = _model_or_422(RegisterIn, data)
    _validate_password_length(payload.password, registration=True)
    if payload.username and len(payload.username) > 150:
        raise HTTPException(status_code=400, detail="Username is too long")
    if payload.email and len(payload.email) > 254:
        raise HTTPException(status_code=400, detail="Email is too long")
    if payload.phone and len(payload.phone) > 40:
        raise HTTPException(status_code=400, detail="Phone is too long")
    user = create_user(
        session,
        username=payload.username,
        email=payload.email,
        phone=payload.phone,
        password=payload.password,
        role="customer",
    )
    tokens = build_token_response(user, session=session, persistent=True)
    _set_auth_cookies(
        response,
        tokens,
        secure=_request_uses_secure_cookies(request),
        persistent=True,
    )
    return {"user": tokens["user"], "roles": tokens["roles"], "message": "Account created and signed in."}


@router.post("/api/auth/mfa/enroll/start/")
def mfa_enroll_start(
    payload: MFAChallengeIn,
    request: Request,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    auth_rate_limiter.enforce(
        client_rate_key(request, "mfa-enroll"),
        limit=settings.login_rate_limit,
        window_seconds=settings.login_rate_window_seconds,
    )
    enrollment = begin_mfa_enrollment(session, payload.mfa_token)
    return {
        **enrollment,
        "message": "Scan the QR/URI, then confirm with a current authenticator code.",
    }


@router.post("/api/auth/mfa/enroll/confirm/")
def mfa_enroll_confirm(
    payload: MFAEnrollmentConfirmIn,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    auth_rate_limiter.enforce(
        client_rate_key(request, "mfa-confirm"),
        limit=settings.login_rate_limit,
        window_seconds=settings.login_rate_window_seconds,
    )
    user, recovery_codes, persistent = confirm_mfa_enrollment(
        session,
        payload.mfa_token,
        payload.code,
    )
    _audit_mfa(session, user=user, action="auth.mfa.enrolled", request=request)
    tokens = build_token_response(user, session=session, persistent=persistent)
    _set_auth_cookies(
        response,
        tokens,
        secure=_request_uses_secure_cookies(request),
        persistent=persistent,
    )
    return {
        "user": tokens["user"],
        "roles": tokens["roles"],
        "recovery_codes": recovery_codes,
        "message": "MFA enabled. Store these one-time recovery codes securely; they will not be shown again.",
    }


@router.post("/api/auth/mfa/verify/")
def mfa_verify(
    payload: MFAVerifyIn,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    auth_rate_limiter.enforce(
        client_rate_key(request, "mfa-verify"),
        limit=settings.login_rate_limit,
        window_seconds=settings.login_rate_window_seconds,
    )
    user, persistent, used_recovery = verify_mfa_login(
        session,
        payload.mfa_token,
        code=payload.code,
        recovery_code=payload.recovery_code,
    )
    if used_recovery:
        _audit_mfa(
            session,
            user=user,
            action="auth.mfa.recovery_code_used",
            request=request,
            note="One recovery code was consumed.",
        )
    tokens = build_token_response(user, session=session, persistent=persistent)
    _set_auth_cookies(
        response,
        tokens,
        secure=_request_uses_secure_cookies(request),
        persistent=persistent,
    )
    return {
        "user": tokens["user"],
        "roles": tokens["roles"],
        "recovery_code_used": used_recovery,
    }


@router.post("/api/auth/refresh/")
async def refresh(request: Request, response: Response, session: Session = Depends(get_session)) -> dict[str, Any]:
    auth_rate_limiter.enforce(
        client_rate_key(request, "refresh"),
        limit=settings.refresh_rate_limit,
        window_seconds=settings.refresh_rate_window_seconds,
    )
    data: dict[str, Any] = {}
    if request.headers.get("content-type", "").startswith("application/json"):
        body = await _bounded_body(request)
        try:
            decoded = json.loads(body.decode() or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON body") from exc
        if not isinstance(decoded, dict):
            raise HTTPException(status_code=400, detail="Invalid refresh payload")
        data = decoded
    token = data.get("refresh") or data.get("refresh_token") or request.cookies.get("sourceai_refresh")
    if not token:
        raise HTTPException(status_code=400, detail="refresh token required")
    tokens = refresh_access_token(token, session)
    _set_auth_cookies(
        response,
        tokens,
        secure=_request_uses_secure_cookies(request),
        persistent=bool(tokens["persistent"]),
    )
    return {"user": tokens["user"], "roles": tokens["roles"]}


@router.get("/api/auth/social/{provider}/start/")
def social_start(provider: str, request: Request) -> Response:
    if provider != "google":
        raise HTTPException(status_code=400, detail="Unsupported social provider")
    state = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b"=").decode()
    redirect_uri = _social_callback_uri(provider)
    try:
        auth_url = google_authorization_url(redirect_uri=redirect_uri, state=state, code_challenge=code_challenge)
    except SocialAuthError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    response = JSONResponse({"auth_url": auth_url})
    response.set_cookie(
        "sourceai_oauth_state",
        state,
        httponly=True,
        secure=_request_uses_secure_cookies(request),
        samesite="lax",
        max_age=600,
        path="/api/auth/social/",
    )
    response.set_cookie(
        "sourceai_oauth_verifier",
        code_verifier,
        httponly=True,
        secure=_request_uses_secure_cookies(request),
        samesite="lax",
        max_age=600,
        path="/api/auth/social/",
    )
    return response


@router.get("/api/auth/social/{provider}/callback/", name="social_callback")
def social_callback(
    provider: str,
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    session: Session = Depends(get_session),
) -> Response:
    frontend_login = f"{settings.frontend_url.rstrip('/')}/login"
    if error:
        return RedirectResponse(f"{frontend_login}?social_error=access_denied", status_code=303)
    expected_state = request.cookies.get("sourceai_oauth_state")
    code_verifier = request.cookies.get("sourceai_oauth_verifier")
    if not code or not state or not expected_state or not code_verifier or not hmac.compare_digest(state, expected_state):
        return RedirectResponse(f"{frontend_login}?social_error=invalid_state", status_code=303)
    if provider != "google":
        return RedirectResponse(f"{frontend_login}?social_error=unsupported_provider", status_code=303)
    redirect_uri = _social_callback_uri(provider)
    try:
        profile = exchange_google_code(code=code, redirect_uri=redirect_uri, code_verifier=code_verifier)
        user = get_or_create_social_user(
            session,
            provider=provider,
            provider_id=str(profile["sub"]),
            email=str(profile["email"]),
            name=profile.get("name"),
            avatar_url=profile.get("picture"),
        )
    except (SocialAuthError, HTTPException):
        return RedirectResponse(f"{frontend_login}?social_error=authentication_failed", status_code=303)

    tokens = build_token_response(user, session=session, persistent=True)
    destination = "/admin" if user.get("role") in {"admin", "operator"} else "/account/saved-quotes"
    response = RedirectResponse(f"{settings.frontend_url.rstrip('/')}{destination}", status_code=303)
    _set_auth_cookies(
        response,
        tokens,
        secure=_request_uses_secure_cookies(request),
        persistent=True,
    )
    response.delete_cookie("sourceai_oauth_state", path="/api/auth/social/")
    response.delete_cookie("sourceai_oauth_verifier", path="/api/auth/social/")
    return response


@router.post("/api/auth/logout/")
def logout(
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    revoke_refresh_token(session, request.cookies.get("sourceai_refresh"))
    response.delete_cookie("sourceai_access", path="/")
    response.delete_cookie("sourceai_refresh", path="/api/auth/")
    return {"ok": True}


@router.get("/api/auth/me/")
def me(current_user: dict[str, Any] = Depends(get_current_user_detail)) -> dict[str, Any]:
    return current_user
