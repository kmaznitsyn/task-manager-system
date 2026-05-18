"""Pub/Sub event publication on create + status->done."""
from __future__ import annotations

import pytest


def test_create_publishes_task_created(client_as_alice, alice, stub_publisher):
    body = client_as_alice.post("/tasks", json={"title": "x"}).json()

    assert len(stub_publisher) == 1
    event = stub_publisher[0]
    assert event.type == "task.created"
    assert event.task_id == body["id"]
    assert event.owner_sub == alice["sub"]


def test_status_transition_to_done_publishes_completed(
    client_as_alice, alice, stub_publisher
):
    created = client_as_alice.post("/tasks", json={"title": "x"}).json()
    stub_publisher.clear()  # ignore the create event for this test

    client_as_alice.patch(f"/tasks/{created['id']}", json={"status": "doing"})
    assert stub_publisher == []  # only done triggers an event

    client_as_alice.patch(f"/tasks/{created['id']}", json={"status": "done"})
    assert len(stub_publisher) == 1
    event = stub_publisher[0]
    assert event.type == "task.completed"
    assert event.task_id == created["id"]
    assert event.owner_sub == alice["sub"]


def test_done_to_done_does_not_publish_again(client_as_alice, stub_publisher):
    created = client_as_alice.post("/tasks", json={"title": "x"}).json()
    client_as_alice.patch(f"/tasks/{created['id']}", json={"status": "done"})
    stub_publisher.clear()

    # Second PATCH that doesn't change the status — no event.
    client_as_alice.patch(f"/tasks/{created['id']}", json={"status": "done"})
    assert stub_publisher == []

    # Editing other fields while already done — still no event.
    client_as_alice.patch(f"/tasks/{created['id']}", json={"title": "renamed"})
    assert stub_publisher == []


def test_other_status_changes_do_not_publish(client_as_alice, stub_publisher):
    created = client_as_alice.post("/tasks", json={"title": "x"}).json()
    stub_publisher.clear()

    for new_status in ("doing", "todo", "doing"):
        client_as_alice.patch(
            f"/tasks/{created['id']}", json={"status": new_status}
        )
    assert stub_publisher == []


def test_publish_failure_does_not_roll_back_create(
    client_as_alice, monkeypatch, caplog
):
    """If publish raises, the task must still be persisted and 201 returned."""
    from app import publisher as publisher_module

    def _boom(event):
        raise RuntimeError("pubsub down")

    monkeypatch.setattr(publisher_module, "publish_task_event", _boom)

    with caplog.at_level("ERROR"):
        r = client_as_alice.post("/tasks", json={"title": "still saved"})

    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "still saved"
    assert "failed to publish" in caplog.text

    # Row really is persisted: list endpoint sees it.
    listed = client_as_alice.get("/tasks").json()
    assert any(t["id"] == body["id"] for t in listed)


def test_publish_failure_does_not_roll_back_completion(
    client_as_alice, monkeypatch, caplog
):
    from app import publisher as publisher_module

    created = client_as_alice.post("/tasks", json={"title": "y"}).json()

    def _boom(event):
        raise RuntimeError("pubsub down")

    monkeypatch.setattr(publisher_module, "publish_task_event", _boom)

    with caplog.at_level("ERROR"):
        r = client_as_alice.patch(
            f"/tasks/{created['id']}", json={"status": "done"}
        )

    assert r.status_code == 200
    assert r.json()["status"] == "done"
    assert "failed to publish" in caplog.text


@pytest.mark.no_stub_publisher
def test_publish_skipped_when_disabled(monkeypatch, caplog):
    """publish_task_event is a no-op when neither PUBSUB_EMULATOR_HOST nor
    settings.pubsub_enabled is set. Crucially it never builds a PublisherClient,
    so dev environments without GCP creds don't blow up."""
    from app import publisher as pub
    from app.schemas import TaskEvent

    def _explode():
        raise AssertionError("must not construct PublisherClient when disabled")

    monkeypatch.setattr(pub, "_topic", _explode)
    monkeypatch.delenv("PUBSUB_EMULATOR_HOST", raising=False)
    monkeypatch.setattr(pub.settings, "pubsub_enabled", False)

    event = TaskEvent(type="task.created", task_id="abc", owner_sub="kc-x")
    with caplog.at_level("INFO"):
        pub.publish_task_event(event)

    assert "pubsub disabled" in caplog.text


@pytest.mark.no_stub_publisher
def test_publish_attempts_when_emulator_host_set(monkeypatch):
    """With PUBSUB_EMULATOR_HOST set, the publisher actually tries to publish."""
    from app import publisher as pub
    from app.schemas import TaskEvent

    called = {}

    class _FakeFuture:
        def result(self, timeout):
            return "msg-1"

    class _FakeClient:
        def publish(self, path, data):
            called["path"] = path
            called["data"] = data
            return _FakeFuture()

    monkeypatch.setattr(pub, "_topic", lambda: (_FakeClient(), "projects/p/topics/t"))
    monkeypatch.setenv("PUBSUB_EMULATOR_HOST", "localhost:8085")

    pub.publish_task_event(
        TaskEvent(type="task.created", task_id="abc", owner_sub="kc-x")
    )

    assert called["path"] == "projects/p/topics/t"
    assert b'"task.created"' in called["data"]


@pytest.mark.parametrize("op", ["delete", "get"])
def test_non_mutating_or_delete_does_not_publish(
    client_as_alice, stub_publisher, op
):
    created = client_as_alice.post("/tasks", json={"title": "x"}).json()
    stub_publisher.clear()

    if op == "delete":
        client_as_alice.delete(f"/tasks/{created['id']}")
    else:
        client_as_alice.get(f"/tasks/{created['id']}")

    assert stub_publisher == []
