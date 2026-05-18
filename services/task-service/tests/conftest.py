"""Test fixtures for task-service.

Unit tests use SQLite via StaticPool; the Postgres-only enum is mapped to
TEXT under SQLite by SQLAlchemy automatically since `TaskStatus` is a
Python Enum and `Enum(...)` falls back to a CHECK-constrained VARCHAR.
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

ALICE = {"sub": "kc-alice", "email": "alice@example.com", "name": "Alice"}
BOB = {"sub": "kc-bob", "email": "bob@example.com", "name": "Bob"}


@pytest.fixture
def alice() -> dict:
    return dict(ALICE)


@pytest.fixture
def bob() -> dict:
    return dict(BOB)


@pytest.fixture(autouse=True)
def stub_publisher(monkeypatch, request):
    """Replace publish_task_event with a no-op spy on every test, so we never
    hit Pub/Sub during tests and individual tests can inspect calls.

    Tests that need the real implementation can opt out with
    `@pytest.mark.no_stub_publisher`.
    """
    calls: list = []

    def _fake_publish(event):
        calls.append(event)

    from app import publisher as publisher_module

    if request.node.get_closest_marker("no_stub_publisher") is None:
        monkeypatch.setattr(publisher_module, "publish_task_event", _fake_publish)
    return calls


@pytest.fixture
def session_factory() -> sessionmaker:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _override_db(app, factory: sessionmaker) -> None:
    def _get_db() -> Iterator[Session]:
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db


def _override_auth(app, claims: dict) -> None:
    app.dependency_overrides[get_current_user] = lambda: claims


@pytest.fixture
def client_as_alice(session_factory, alice) -> Iterator[TestClient]:
    _override_db(app, session_factory)
    _override_auth(app, alice)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class _ActingClient:
    """TestClient that re-applies its identity override before every request,
    so multiple `_ActingClient`s sharing the same `app` don't trample each
    other's auth via the global `app.dependency_overrides` dict.
    """

    def __init__(self, app, claims: dict):
        self._app = app
        self._claims = claims
        self._client = TestClient(app)

    def _activate(self):
        self._app.dependency_overrides[get_current_user] = lambda: self._claims

    def get(self, *a, **kw):
        self._activate()
        return self._client.get(*a, **kw)

    def post(self, *a, **kw):
        self._activate()
        return self._client.post(*a, **kw)

    def patch(self, *a, **kw):
        self._activate()
        return self._client.patch(*a, **kw)

    def delete(self, *a, **kw):
        self._activate()
        return self._client.delete(*a, **kw)


@pytest.fixture
def client_factory(session_factory):
    """Build acting-as clients that share one in-memory DB."""
    _override_db(app, session_factory)

    def _make(claims: dict) -> _ActingClient:
        return _ActingClient(app, claims)

    yield _make
    app.dependency_overrides.clear()
