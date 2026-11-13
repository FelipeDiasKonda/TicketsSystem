from datetime import timedelta

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.dependencies import require_support
from app.core.config import get_settings
from app.core.security import hash_token
from app.db.database import Base, get_db
from app.main import create_app
from app.models import AuthSession, User
from app.models.auth import utc_now

PASSWORD = "correct-password-123"
HEADERS = {"X-CSRF-Protection": "1"}


@pytest.fixture
def auth_context():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    app = create_app()
    with Session(engine) as db:
        app.dependency_overrides[get_db] = lambda: db

        @app.get("/api/test-support", dependencies=[Depends(require_support)])
        def support_only():
            return {"ok": True}

        with TestClient(app) as client:
            yield client, db
    engine.dispose()


def registration(role="employee", **changes):
    return {
        "name": "  Felipe Konda  ",
        "email": "Felipe@EXAMPLE.com",
        "password": PASSWORD,
        "password_confirmation": PASSWORD,
        "role": role,
        **changes,
    }


def register(client, **changes):
    return client.post("/api/auth/register", json=registration(**changes), headers=HEADERS)


def login(client, email="felipe@example.com", password=PASSWORD):
    return client.post(
        "/api/auth/login", json={"email": email, "password": password}, headers=HEADERS
    )


@pytest.mark.parametrize("role", ["employee", "support"])
def test_registration_starts_session_and_stores_only_hashes(auth_context, role):
    client, db = auth_context
    response = register(client, role=role)
    assert response.status_code == 201
    assert response.json() == {
        "id": 1,
        "name": "Felipe Konda",
        "email": "felipe@example.com",
        "role": role,
        "is_active": True,
    }
    assert response.headers["cache-control"] == "no-store"
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "path=/api" in cookie
    user = db.scalar(select(User))
    assert user.password_hash.startswith("$argon2id$")
    assert PASSWORD not in user.password_hash
    token = client.cookies.get(get_settings().session_cookie_name)
    session = db.scalar(select(AuthSession))
    assert session.token_hash == hash_token(token)
    assert session.token_hash != token
    assert client.get("/api/auth/me").json() == response.json()
    assert client.get("/api/test-support").status_code == (200 if role == "support" else 403)


def test_duplicate_email_is_case_insensitive(auth_context):
    client, _ = auth_context
    assert register(client).status_code == 201
    assert register(client, email="FELIPE@example.com").status_code == 409


@pytest.mark.parametrize(
    "changes",
    [
        {"role": "admin"},
        {"name": " "},
        {"email": "invalid"},
        {"password": "short", "password_confirmation": "short"},
        {"password": "x" * 129, "password_confirmation": "x" * 129},
        {"password_confirmation": "different-password"},
        {"is_active": False},
        {"company_id": 42},
    ],
)
def test_registration_validation_does_not_echo_passwords(auth_context, changes):
    client, db = auth_context
    response = register(client, **changes)
    assert response.status_code == 422
    assert PASSWORD not in response.text
    assert "different-password" not in response.text
    assert db.scalar(select(User)) is None


def test_login_rotates_session_and_logout_revokes_it(auth_context):
    client, db = auth_context
    register(client)
    old_token = client.cookies.get(get_settings().session_cookie_name)
    response = login(client, email="FELIPE@EXAMPLE.COM")
    assert response.status_code == 200
    token = client.cookies.get(get_settings().session_cookie_name)
    assert token != old_token
    assert (
        db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(old_token)))
        is None
    )
    assert client.post("/api/auth/logout", headers=HEADERS).status_code == 204
    assert client.cookies.get(get_settings().session_cookie_name) is None
    assert db.scalar(select(AuthSession)) is None
    client.cookies.set(get_settings().session_cookie_name, token)
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/logout", headers=HEADERS).status_code == 204


def test_invalid_credentials_have_identical_errors(auth_context):
    client, db = auth_context
    register(client)
    wrong = login(client, password="wrong-password")
    missing = login(client, email="missing@example.com")
    user = db.scalar(select(User))
    user.is_active = False
    db.commit()
    inactive = login(client)
    assert wrong.status_code == missing.status_code == inactive.status_code == 401
    assert wrong.json() == missing.json() == inactive.json()
    assert client.get("/api/auth/me").status_code == 401


def test_session_expiration_and_anonymous_access(auth_context):
    client, db = auth_context
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/test-support").status_code == 401
    register(client)
    session = db.scalar(select(AuthSession))
    session.expires_at = utc_now() - timedelta(seconds=1)
    db.commit()
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.set(get_settings().session_cookie_name, "invented-token")
    assert client.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize("path", ["register", "login", "logout"])
def test_csrf_protection(auth_context, path):
    client, _ = auth_context
    body = (
        registration() if path == "register" else {"email": "a@example.com", "password": PASSWORD}
    )
    assert client.post(f"/api/auth/{path}", json=body).status_code == 403
    assert (
        client.post(
            f"/api/auth/{path}",
            json=body,
            headers={
                **HEADERS,
                "Origin": "https://untrusted.example",
            },
        ).status_code
        == 403
    )


def test_cors_only_allows_configured_origin(auth_context):
    client, _ = auth_context
    headers = {
        "Origin": get_settings().cors_origins[0],
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,x-csrf-protection",
    }
    response = client.options("/api/auth/login", headers=headers)
    assert response.status_code == 200
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers["access-control-allow-origin"] == headers["Origin"]
    headers["Origin"] = "https://untrusted.example"
    assert client.options("/api/auth/login", headers=headers).status_code == 400


def test_secure_cookie_setting(auth_context, monkeypatch):
    client, _ = auth_context
    monkeypatch.setattr(get_settings(), "cookie_secure", True)
    response = register(client)
    assert "; secure" in response.headers["set-cookie"].lower()
