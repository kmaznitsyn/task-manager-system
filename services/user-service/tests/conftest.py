"""Shared fixtures.

Two flavours of tests:

* unit:        in-process FastAPI TestClient, DB and auth dependencies
               overridden — no Postgres, no Keycloak.
* integration: real Postgres in a throwaway Docker container
               (testcontainers), alembic-migrated, only auth is mocked.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from cf_auth import get_current_user

DEFAULT_CLAIMS = {
    "sub": "kc-user-1",
    "email": "alice@example.com",
    "name": "Alice Example",
    "email_verified": True,
}


@pytest.fixture
def claims() -> dict:
    return dict(DEFAULT_CLAIMS)


def _override_auth(app, claims: dict) -> None:
    app.dependency_overrides[get_current_user] = lambda: claims


def _override_db(app, sessionmaker_: sessionmaker) -> None:
    def _get_db() -> Iterator[Session]:
        db = sessionmaker_()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db


# ---------------------------------------------------------------------------
# UNIT — Postgres-shaped engine via the `postgresql+psycopg` dialect URL is
# not available in unit tests, so we use SQLite with a small UUID adapter.
# ---------------------------------------------------------------------------


@pytest.fixture
def sqlite_session_factory(monkeypatch) -> sessionmaker:
    """In-memory SQLite, schema created from SQLAlchemy metadata.

    SQLite has no native UUID and no ON CONFLICT (...) on a named index by
    column name — but our `users.py` uses `postgresql.insert(...).
    on_conflict_do_nothing(index_elements=[...])` which won't run on SQLite.
    For the unit tests we monkey-patch `get_or_create_from_claims` with a
    portable implementation; integration tests exercise the real Postgres
    code path.
    """
    from app import users as users_module
    from app.models import User
    from sqlalchemy import select

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _portable_get_or_create(db, claims):
        sub = claims["sub"]
        user = db.scalar(select(User).where(User.keycloak_sub == sub))
        if user is None:
            user = User(
                keycloak_sub=sub,
                email=claims.get("email") or f"{sub}@unknown.local",
                display_name=claims.get("name") or claims.get("preferred_username"),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    monkeypatch.setattr(
        users_module, "get_or_create_from_claims", _portable_get_or_create
    )
    # main.py imported the symbol directly — patch there too.
    import app.main as main_module

    monkeypatch.setattr(
        main_module, "get_or_create_from_claims", _portable_get_or_create
    )

    return SessionLocal


@pytest.fixture
def unit_client(sqlite_session_factory, claims) -> Iterator[TestClient]:
    _override_auth(app, claims)
    _override_db(app, sqlite_session_factory)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# INTEGRATION — testcontainers Postgres + real alembic migrations.
# Only spun up when the integration tests are collected.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def pg_url() -> Iterator[str]:
    pytest.importorskip("testcontainers.postgres")
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16-alpine", driver="psycopg") as pg:
        yield pg.get_connection_url()


@pytest.fixture(scope="session")
def pg_session_factory(pg_url) -> sessionmaker:
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", pg_url)
    command.upgrade(cfg, "head")

    engine = create_engine(pg_url, future=True)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture
def clean_users(pg_session_factory) -> sessionmaker:
    from app.models import User

    db = pg_session_factory()
    try:
        db.query(User).delete()
        db.commit()
    finally:
        db.close()
    return pg_session_factory


@pytest.fixture
def integration_client(clean_users, claims) -> Iterator[TestClient]:
    _override_auth(app, claims)
    _override_db(app, clean_users)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
