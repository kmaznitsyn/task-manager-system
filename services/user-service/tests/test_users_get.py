"""Tests for GET /users/{id}."""
from __future__ import annotations

import uuid


def test_returns_existing_user(unit_client):
    me = unit_client.get("/me").json()

    r = unit_client.get(f"/users/{me['id']}")
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["id"] == me["id"]
    assert body["keycloak_sub"] == me["keycloak_sub"]
    assert body["email"] == me["email"]


def test_404_for_unknown_id(unit_client):
    # ensure auth/db are wired by warming /me first
    unit_client.get("/me")

    missing = uuid.uuid4()
    r = unit_client.get(f"/users/{missing}")
    assert r.status_code == 404
    assert r.json() == {"detail": "User not found"}


def test_422_for_malformed_uuid(unit_client):
    r = unit_client.get("/users/not-a-uuid")
    assert r.status_code == 422


def test_requires_auth(sqlite_session_factory):
    """No auth override → HTTPBearer rejects with 403."""
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app

    def _get_db():
        db = sqlite_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides = {get_db: _get_db}
    try:
        with TestClient(app) as c:
            r = c.get(f"/users/{uuid.uuid4()}")
        assert r.status_code in (401, 403)
    finally:
        app.dependency_overrides.clear()


def test_can_fetch_other_user(unit_client, sqlite_session_factory):
    """Any authenticated caller can look up any user by id."""
    from fastapi.testclient import TestClient

    from app.main import app
    from cf_auth import get_current_user

    me = unit_client.get("/me").json()  # creates user A as 'kc-user-1'

    # Switch caller identity to user B; should still be able to fetch user A.
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "kc-user-2",
        "email": "bob@example.com",
        "name": "Bob",
    }
    with TestClient(app) as c:
        r = c.get(f"/users/{me['id']}")
    assert r.status_code == 200
    assert r.json()["keycloak_sub"] == "kc-user-1"
