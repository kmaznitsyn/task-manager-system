"""End-to-end happy path + parametrized ownership matrix.

Complements `test_tasks_crud.py` (per-endpoint cases) with:
  * one full create → get → list → patch → delete lifecycle, and
  * one ownership matrix that proves every endpoint that touches a
    specific task id rejects cross-user access with 404.
"""
from __future__ import annotations

import uuid

import pytest


def test_full_lifecycle(client_as_alice, alice):
    c = client_as_alice

    # CREATE
    created = c.post(
        "/tasks",
        json={
            "title": "ship release",
            "description": "v1.0",
            "due_date": "2026-06-01",
        },
    ).json()
    task_id = created["id"]
    assert created["owner_sub"] == alice["sub"]
    assert created["status"] == "todo"

    # GET single
    fetched = c.get(f"/tasks/{task_id}").json()
    assert fetched == created

    # LIST contains it
    listed = c.get("/tasks").json()
    assert any(t["id"] == task_id for t in listed)

    # PATCH advances status + edits title
    patched = c.patch(
        f"/tasks/{task_id}", json={"status": "doing", "title": "ship release v1"}
    ).json()
    assert patched["status"] == "doing"
    assert patched["title"] == "ship release v1"
    assert patched["description"] == "v1.0"  # untouched
    assert patched["due_date"] == "2026-06-01"

    # PATCH again → done
    done = c.patch(f"/tasks/{task_id}", json={"status": "done"}).json()
    assert done["status"] == "done"
    assert done["updated_at"] >= patched["updated_at"]

    # LIST with status filter sees it as done, not as todo/doing
    assert [t["id"] for t in c.get("/tasks?status=done").json()] == [task_id]
    assert task_id not in [t["id"] for t in c.get("/tasks?status=todo").json()]

    # DELETE
    assert c.delete(f"/tasks/{task_id}").status_code == 204

    # Gone everywhere
    assert c.get(f"/tasks/{task_id}").status_code == 404
    assert c.delete(f"/tasks/{task_id}").status_code == 404
    assert c.patch(f"/tasks/{task_id}", json={"title": "x"}).status_code == 404
    assert task_id not in [t["id"] for t in c.get("/tasks").json()]


@pytest.mark.parametrize(
    "method,body,expected",
    [
        ("get", None, 404),
        ("patch", {"title": "stolen"}, 404),
        ("patch", {"status": "done"}, 404),
        ("delete", None, 404),
    ],
)
def test_ownership_enforced_on_every_endpoint(
    client_factory, alice, bob, method, body, expected
):
    """Bob may not read, modify, or delete Alice's task — and the
    response must be 404 (no existence leak), never 403 or 200.
    """
    a_task = client_factory(alice).post("/tasks", json={"title": "alice"}).json()

    b = client_factory(bob)
    call = getattr(b, method)
    r = call(f"/tasks/{a_task['id']}", json=body) if body else call(f"/tasks/{a_task['id']}")

    assert r.status_code == expected

    # And the row is untouched / still owned by Alice.
    a = client_factory(alice)
    after = a.get(f"/tasks/{a_task['id']}")
    if method == "delete":
        # delete returned 404 for bob, so the task should still exist for alice
        assert after.status_code == 200
        assert after.json()["title"] == "alice"
    else:
        assert after.status_code == 200
        assert after.json()["title"] == "alice"
        assert after.json()["status"] == "todo"


def test_list_never_includes_other_users_tasks(client_factory, alice, bob):
    a = client_factory(alice)
    b = client_factory(bob)

    a_ids = {a.post("/tasks", json={"title": f"a{i}"}).json()["id"] for i in range(3)}
    b_ids = {b.post("/tasks", json={"title": f"b{i}"}).json()["id"] for i in range(2)}

    a_listed = {t["id"] for t in a.get("/tasks").json()}
    b_listed = {t["id"] for t in b.get("/tasks").json()}

    assert a_listed == a_ids
    assert b_listed == b_ids
    assert a_listed.isdisjoint(b_listed)


def test_unknown_id_indistinguishable_from_unauthorized(client_factory, alice, bob):
    """An attacker probing for valid task ids should get the same 404 whether
    the id doesn't exist at all or belongs to another user — no oracle."""
    a_task = client_factory(alice).post("/tasks", json={"title": "x"}).json()

    b = client_factory(bob)
    cross_user = b.get(f"/tasks/{a_task['id']}")
    nonexistent = b.get(f"/tasks/{uuid.uuid4()}")

    assert cross_user.status_code == nonexistent.status_code == 404
    assert cross_user.json() == nonexistent.json() == {"detail": "Task not found"}
