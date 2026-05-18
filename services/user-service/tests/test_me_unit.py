"""Unit tests for GET /me — no Postgres, no Keycloak."""
from __future__ import annotations

import uuid


def test_first_call_creates_row(unit_client, claims):
    r = unit_client.get("/me")
    assert r.status_code == 200, r.text
    body = r.json()

    # Returns the DB row shape, not the raw token claims.
    assert set(body.keys()) == {
        "id",
        "keycloak_sub",
        "email",
        "display_name",
        "created_at",
        "updated_at",
    }
    assert body["keycloak_sub"] == claims["sub"]
    assert body["email"] == claims["email"]
    assert body["display_name"] == claims["name"]
    uuid.UUID(body["id"])  # well-formed UUID


def test_subsequent_call_returns_same_row(unit_client):
    first = unit_client.get("/me").json()
    second = unit_client.get("/me").json()
    third = unit_client.get("/me").json()

    assert first["id"] == second["id"] == third["id"]
    assert first["created_at"] == second["created_at"] == third["created_at"]


def test_no_duplicate_rows_for_same_sub(unit_client, sqlite_session_factory):
    from app.models import User
    from sqlalchemy import func, select

    for _ in range(5):
        unit_client.get("/me")

    with sqlite_session_factory() as db:
        n = db.scalar(select(func.count()).select_from(User))
        assert n == 1


def test_response_does_not_leak_token_claims(unit_client, claims):
    r = unit_client.get("/me")
    body = r.json()
    # claims-only keys should NOT be in the response — this is the DB row.
    assert "sub" not in body
    assert "email_verified" not in body
    assert "preferred_username" not in body


def test_different_sub_creates_separate_row(unit_client, sqlite_session_factory):
    from fastapi.testclient import TestClient

    from app.main import app
    from cf_auth import get_current_user

    first = unit_client.get("/me").json()

    other_claims = {"sub": "kc-user-2", "email": "bob@example.com", "name": "Bob"}
    app.dependency_overrides[get_current_user] = lambda: other_claims
    with TestClient(app) as c:
        second = c.get("/me").json()

    assert first["id"] != second["id"]
    assert second["keycloak_sub"] == "kc-user-2"
