import os
import requests
from django.conf import settings


class SocialError(Exception):
    pass


def exchange_google_code(code: str, redirect_uri: str):
    client_id = settings.GOOGLE_CLIENT_ID
    client_secret = settings.GOOGLE_CLIENT_SECRET
    if not client_id or not client_secret:
        raise SocialError("Google client not configured")
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    resp = requests.post(token_url, data=data, timeout=10)
    if resp.status_code != 200:
        raise SocialError("Failed to exchange Google code")
    tokens = resp.json()
    info = requests.get(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {tokens.get('access_token')}"},
        timeout=10,
    )
    if info.status_code != 200:
        raise SocialError("Failed to fetch Google profile")
    profile = info.json()
    return {
        "email": profile.get("email"),
        "name": profile.get("name"),
        "id": profile.get("sub"),
        "picture": profile.get("picture"),
    }


def exchange_facebook_code(code: str, redirect_uri: str):
    app_id = settings.FACEBOOK_APP_ID
    app_secret = settings.FACEBOOK_APP_SECRET
    if not app_id or not app_secret:
        raise SocialError("Facebook app not configured")
    token_url = "https://graph.facebook.com/v19.0/oauth/access_token"
    params = {
        "client_id": app_id,
        "client_secret": app_secret,
        "redirect_uri": redirect_uri,
        "code": code,
    }
    resp = requests.get(token_url, params=params, timeout=10)
    if resp.status_code != 200:
        raise SocialError("Failed to exchange Facebook code")
    access_token = resp.json().get("access_token")
    info = requests.get(
        "https://graph.facebook.com/me",
        params={"fields": "id,name,email", "access_token": access_token},
        timeout=10,
    )
    if info.status_code != 200:
        raise SocialError("Failed to fetch Facebook profile")
    profile = info.json()
    return {
        "email": profile.get("email"),
        "name": profile.get("name"),
        "id": profile.get("id"),
        "picture": None,
    }
