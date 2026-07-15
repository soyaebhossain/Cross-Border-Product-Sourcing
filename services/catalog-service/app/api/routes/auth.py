from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from ...auth import (
    authenticate_user,
    build_token_response,
    create_user,
    get_current_user_detail,
    refresh_access_token,
)
from ...db import get_session
from ...schemas import LoginIn, RegisterIn


router = APIRouter()


async def _read_login_payload(request: Request) -> LoginIn:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        return LoginIn.model_validate(await request.json())

    raw = (await request.body()).decode()
    form = {key: values[-1] for key, values in parse_qs(raw).items()}
    return LoginIn(
        identifier=form.get("identifier") or form.get("username"),
        username=form.get("username"),
        password=form.get("password") or "",
    )


@router.post("/api/auth/login/")
async def login(request: Request, response: Response, session: Session = Depends(get_session)) -> dict[str, Any]:
    payload = await _read_login_payload(request)
    identifier = payload.identifier or payload.email or payload.username or payload.phone
    if not identifier or not payload.password:
        raise HTTPException(status_code=400, detail="identifier and password required")

    user = authenticate_user(session, identifier, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    tokens = build_token_response(user)
    secure = request.url.scheme == "https"
    response.set_cookie("sourceai_access", tokens["access"], httponly=True, secure=secure, samesite="lax", max_age=3600, path="/")
    response.set_cookie("sourceai_refresh", tokens["refresh"], httponly=True, secure=secure, samesite="lax", max_age=14 * 86400, path="/api/auth/")
    return {"user": tokens["user"], "roles": tokens["roles"]}


@router.post("/api/auth/register/", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, session: Session = Depends(get_session)) -> dict[str, Any]:
    user = create_user(
        session,
        username=payload.username,
        email=payload.email,
        phone=payload.phone,
        password=payload.password,
        role="customer",
    )
    return {"user": build_token_response(user)["user"], "message": "Account created. Please sign in."}


@router.post("/api/auth/refresh/")
async def refresh(request: Request, response: Response) -> dict[str, Any]:
    data = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    token = data.get("refresh") or data.get("refresh_token") or request.cookies.get("sourceai_refresh")
    if not token:
        raise HTTPException(status_code=400, detail="refresh token required")
    tokens = refresh_access_token(token)
    response.set_cookie("sourceai_access", tokens["access"], httponly=True, secure=request.url.scheme == "https", samesite="lax", max_age=3600, path="/")
    return {"user": tokens["user"], "roles": tokens["roles"]}


@router.post("/api/auth/logout/")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie("sourceai_access", path="/")
    response.delete_cookie("sourceai_refresh", path="/api/auth/")
    return {"ok": True}


@router.get("/api/auth/me/")
def me(current_user: dict[str, Any] = Depends(get_current_user_detail)) -> dict[str, Any]:
    return current_user
