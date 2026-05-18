"""Integration tests for GET /me — real Postgres via testcontainers,
real alembic migrations, real `INSERT ... ON CONFLICT DO NOTHING` path.
"""
from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.integration


def test_first_call_creates_row(integration_client, clean_users, claims):
    from app.models import User
    from sqlalchemy import select

    r = integration_client.get("/me")
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["keycloak_sub"] == claims["sub"]
    assert body["email"] == claims["email"]
    uuid.UUID(body["id"])

    with clean_users() as db:
        row = db.scalar(select(User).where(User.keycloak_sub == claims["sub"]))
        assert row is not None
        assert str(row.id) == body["id"]


def test_subsequent_calls_return_same_row(integration_client):
    first = integration_client.get("/me").json()
    second = integration_client.get("/me").json()
    third = integration_client.get("/me").json()

    assert first["id"] == second["id"] == third["id"]


def test_no_duplicates_under_repeated_calls(
    integration_client, clean_users, claims
):
    from app.models import User
    from sqlalchemy import func, select

    for _ in range(10):
        assert integration_client.get("/me").status_code == 200

    with clean_users() as db:
        n = db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.keycloak_sub == claims["sub"])
        )
        assert n == 1


def test_email_is_synced_from_claims(integration_client, clean_users, claims):
    """Updating claims on a subsequent call updates the persisted row."""
    from app.main import app
    from cf_auth import get_current_user
    from app.models import User
    from sqlalchemy import select

    first = integration_client.get("/me").json()
    assert first["email"] == claims["email"]

    new_claims = dict(claims, email="alice2@example.com", name="Alice Renamed")
    app.dependency_overrides[get_current_user] = lambda: new_claims

    second = integration_client.get("/me").json()
    assert second["id"] == first["id"]
    assert second["email"] == "alice2@example.com"
    assert second["display_name"] == "Alice Renamed"

    with clean_users() as db:
        row = db.scalar(select(User).where(User.keycloak_sub == claims["sub"]))
        assert row.email == "alice2@example.com"
