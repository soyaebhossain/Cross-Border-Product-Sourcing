from __future__ import annotations

import importlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db import Base, get_session

auth = importlib.import_module("app.auth")
auth_routes = importlib.import_module("app.api.routes.auth")


@pytest.fixture()
def client(monkeypatch):
    settings = Settings(
        environment="development",
        database_url="sqlite:///:memory:",
        jwt_secret="session-test-secret-with-more-than-thirty-two-characters",
        password_min_characters=8,
    )
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    monkeypatch.setattr(auth_routes, "settings", settings)
    auth_routes.auth_rate_limiter.clear()
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)

    def override_session():
        yield session

    app = FastAPI()
    app.include_router(auth_routes.router)
    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    session.close()
    engine.dispose()


def _register(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register/",
        json={"username": "session-user", "email": "session-user@example.test", "password": "Aa1!bcde"},
    )
    assert response.status_code == 201


def test_signed_out_session_is_a_normal_200_response(client: TestClient) -> None:
    response = client.get("/api/auth/session/")

    assert response.status_code == 200
    assert response.json() == {"authenticated": False, "can_refresh": False, "user": None}


def test_signed_in_session_returns_the_user(client: TestClient) -> None:
    _register(client)

    body = client.get("/api/auth/session/").json()

    assert body["authenticated"] is True
    assert body["can_refresh"] is True
    assert body["user"]["username"] == "session-user"
    assert "password_hash" not in body["user"]


def test_expired_access_cookie_reports_that_refresh_is_possible(client: TestClient) -> None:
    _register(client)
    client.cookies.delete("sourceai_access")
    client.cookies.set("sourceai_access", "not-a-valid-token")

    body = client.get("/api/auth/session/").json()

    assert body == {"authenticated": False, "can_refresh": True, "user": None}
    # The existing endpoint keeps its contract for callers that need a hard 401.
    assert client.get("/api/auth/me/").status_code == 401
