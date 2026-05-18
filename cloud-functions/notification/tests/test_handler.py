"""Unit tests for handle_task_event — Keycloak + SendGrid are mocked."""
from __future__ import annotations

import base64
import json
from types import SimpleNamespace

import pytest


def _cloud_event(payload: dict) -> SimpleNamespace:
    encoded = base64.b64encode(json.dumps(payload).encode()).decode()
    return SimpleNamespace(data={"message": {"data": encoded}})


@pytest.fixture
def handle(monkeypatch):
    """Import the handler with Keycloak + SendGrid stubbed out."""
    import keycloak as kc_module
    import notifier as notif_module
    import main as main_module

    sent: list = []

    def fake_email(sub):
        return {"kc-alice": "alice@example.com", "kc-no-mail": None}.get(sub, None)

    def fake_send(to_email, subject, html):
        sent.append({"to": to_email, "subject": subject, "html": html})

    monkeypatch.setattr(kc_module, "get_user_email", fake_email)
    monkeypatch.setattr(main_module, "get_user_email", fake_email)
    monkeypatch.setattr(notif_module, "send_notification", fake_send)
    monkeypatch.setattr(main_module, "send_notification", fake_send)

    return SimpleNamespace(fn=main_module.handle_task_event, sent=sent)


def test_task_created_sends_notification(handle):
    handle.fn(_cloud_event({
        "type": "task.created",
        "task_id": "t-1",
        "owner_sub": "kc-alice",
    }))
    assert len(handle.sent) == 1
    msg = handle.sent[0]
    assert msg["to"] == "alice@example.com"
    assert msg["subject"] == "New task created"
    assert "t-1" in msg["html"]


def test_task_completed_uses_completed_subject(handle):
    handle.fn(_cloud_event({
        "type": "task.completed",
        "task_id": "t-2",
        "owner_sub": "kc-alice",
    }))
    assert handle.sent[-1]["subject"] == "Your task is done"


def test_user_without_email_is_skipped(handle, caplog):
    with caplog.at_level("WARNING"):
        handle.fn(_cloud_event({
            "type": "task.created",
            "task_id": "t-3",
            "owner_sub": "kc-no-mail",
        }))
    assert handle.sent == []
    assert "no email for user" in caplog.text


def test_unknown_user_is_skipped(handle):
    handle.fn(_cloud_event({
        "type": "task.created",
        "task_id": "t-4",
        "owner_sub": "kc-ghost",
    }))
    assert handle.sent == []


def test_malformed_payload_is_logged_not_raised(handle, caplog):
    with caplog.at_level("WARNING"):
        handle.fn(_cloud_event({"type": "task.created"}))  # missing fields
    assert handle.sent == []
    assert "malformed event" in caplog.text


def test_undecodable_message_is_swallowed(handle, caplog):
    bad = SimpleNamespace(data={"message": {"data": "!!!not-base64!!!"}})
    with caplog.at_level("ERROR"):
        handle.fn(bad)
    assert handle.sent == []
    assert "failed to decode" in caplog.text


def test_keycloak_failure_propagates_for_retry(handle, monkeypatch):
    """Pub/Sub will retry on a 500 — re-raising is the right behavior here."""
    import main as main_module

    def boom(_sub):
        raise RuntimeError("kc down")

    monkeypatch.setattr(main_module, "get_user_email", boom)

    with pytest.raises(RuntimeError):
        handle.fn(_cloud_event({
            "type": "task.created",
            "task_id": "t-5",
            "owner_sub": "kc-alice",
        }))
