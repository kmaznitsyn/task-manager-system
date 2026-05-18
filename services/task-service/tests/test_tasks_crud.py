"""CRUD + ownership tests for /tasks."""
from __future__ import annotations

import uuid


def _create(c, **overrides):
    body = {"title": "buy milk"} | overrides
    r = c.post("/tasks", json=body)
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------- create

def test_create_sets_owner_from_jwt(client_as_alice, alice):
    body = _create(client_as_alice, title="t1", description="d", due_date="2026-12-31")
    assert body["owner_sub"] == alice["sub"]
    assert body["title"] == "t1"
    assert body["description"] == "d"
    assert body["status"] == "todo"  # default
    assert body["due_date"] == "2026-12-31"
    uuid.UUID(body["id"])


def test_create_ignores_owner_sub_in_body(client_as_alice, alice):
    """Even if a malicious client sends owner_sub, the JWT sub wins."""
    r = client_as_alice.post(
        "/tasks", json={"title": "x", "owner_sub": "kc-someone-else"}
    )
    # TaskCreate has no owner_sub field — pydantic ignores extra by default,
    # so the row is created with the JWT sub.
    assert r.status_code == 201
    assert r.json()["owner_sub"] == alice["sub"]


def test_create_rejects_empty_title(client_as_alice):
    r = client_as_alice.post("/tasks", json={"title": ""})
    assert r.status_code == 422


# ---------------------------------------------------------------- list

def test_list_only_returns_callers_tasks(client_factory, alice, bob):
    a = client_factory(alice)
    _create(a, title="a1")
    _create(a, title="a2")

    b = client_factory(bob)
    _create(b, title="b1")

    assert {t["title"] for t in a.get("/tasks").json()} == {"a1", "a2"}
    assert {t["title"] for t in b.get("/tasks").json()} == {"b1"}


def test_list_filters_by_status(client_as_alice):
    _create(client_as_alice, title="x")
    done_id = _create(client_as_alice, title="y")["id"]
    client_as_alice.patch(f"/tasks/{done_id}", json={"status": "done"})

    todo = client_as_alice.get("/tasks?status=todo").json()
    done = client_as_alice.get("/tasks?status=done").json()

    assert {t["title"] for t in todo} == {"x"}
    assert {t["title"] for t in done} == {"y"}


# ---------------------------------------------------------------- get

def test_get_own_task(client_as_alice):
    created = _create(client_as_alice, title="hi")
    r = client_as_alice.get(f"/tasks/{created['id']}")
    assert r.status_code == 200
    assert r.json() == created


def test_get_other_users_task_returns_404(client_factory, alice, bob):
    a_task = _create(client_factory(alice), title="alice-only")

    b = client_factory(bob)
    r = b.get(f"/tasks/{a_task['id']}")
    assert r.status_code == 404
    assert r.json() == {"detail": "Task not found"}


def test_get_unknown_id_404(client_as_alice):
    r = client_as_alice.get(f"/tasks/{uuid.uuid4()}")
    assert r.status_code == 404


# ---------------------------------------------------------------- update

def test_patch_only_sets_provided_fields(client_as_alice):
    t = _create(client_as_alice, title="orig", description="d")
    r = client_as_alice.patch(f"/tasks/{t['id']}", json={"title": "new"})

    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "new"
    assert body["description"] == "d"  # untouched
    assert body["status"] == "todo"


def test_patch_changes_status(client_as_alice):
    t = _create(client_as_alice, title="x")
    r = client_as_alice.patch(f"/tasks/{t['id']}", json={"status": "doing"})
    assert r.status_code == 200
    assert r.json()["status"] == "doing"


def test_patch_other_users_task_returns_404(client_factory, alice, bob):
    a_task = _create(client_factory(alice), title="a")

    b = client_factory(bob)
    r = b.patch(f"/tasks/{a_task['id']}", json={"title": "stolen"})
    assert r.status_code == 404


# ---------------------------------------------------------------- delete

def test_delete_own_task(client_as_alice):
    t = _create(client_as_alice, title="bye")
    r = client_as_alice.delete(f"/tasks/{t['id']}")
    assert r.status_code == 204
    assert client_as_alice.get(f"/tasks/{t['id']}").status_code == 404


def test_delete_other_users_task_returns_404(client_factory, alice, bob):
    a_task = _create(client_factory(alice), title="a")

    b = client_factory(bob)
    r = b.delete(f"/tasks/{a_task['id']}")
    assert r.status_code == 404

    # Task still exists for alice.
    a = client_factory(alice)
    assert a.get(f"/tasks/{a_task['id']}").status_code == 200
