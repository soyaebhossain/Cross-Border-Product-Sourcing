from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import get_settings


class SocialAuthError(Exception):
    pass


def google_authorization_url(*, redirect_uri: str, state: str, code_challenge: str) -> str:
    settings = get_settings()
    if not settings.google_client_id:
        raise SocialAuthError("Google login is not configured yet")
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
        "include_granted_scopes": "true",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


def _json_request(url: str, *, data: dict[str, str] | None = None, access_token: str | None = None) -> dict[str, Any]:
    body = urlencode(data).encode() if data else None
    headers = {"Accept": "application/json"}
    if body:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    request = Request(url, data=body, headers=headers, method="POST" if body else "GET")
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode())
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise SocialAuthError("Google authentication request failed") from exc


def exchange_google_code(*, code: str, redirect_uri: str, code_verifier: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise SocialAuthError("Google login is not configured yet")
    tokens = _json_request(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "code_verifier": code_verifier,
        },
    )
    access_token = tokens.get("access_token")
    if not access_token:
        raise SocialAuthError("Google did not return an access token")
    profile = _json_request("https://openidconnect.googleapis.com/v1/userinfo", access_token=access_token)
    if not profile.get("email") or profile.get("email_verified") is not True:
        raise SocialAuthError("A verified Google email is required")
    return profile
