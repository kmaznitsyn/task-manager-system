"""Tests for the synchronous processing pipeline + events."""
from __future__ import annotations


_BL_TEXT = """
B/L number: BL-7788
Consignor: ACME Logistics
Consignee: Beta Imports GmbH
Weight: 1250 kg
"""

_INVOICE_TEXT = """
Invoice number: INV-9001
Total: 4,250.00
Currency: EUR
"""


def _create(c, **overrides):
    body = {
        "doc_type": "bill_of_lading",
        "reference_number": "BL-7788",
        "raw_text": _BL_TEXT,
    } | overrides
    r = c.post("/documents", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_process_extracts_fields_and_marks_processed(client_as_alice, stub_publisher):
    d = _create(client_as_alice)
    r = client_as_alice.post(f"/documents/{d['id']}/process")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "processed"
    assert body["extracted"]["bol_number"] == "BL-7788"
    assert body["extracted"]["consignor"].startswith("ACME")
    assert body["processed_at"] is not None

    types = [e.type for e in stub_publisher]
    assert types == ["document.received", "document.processed"]


def test_process_invoice(client_as_alice):
    d = _create(
        client_as_alice,
        doc_type="invoice",
        reference_number="INV-9001",
        raw_text=_INVOICE_TEXT,
    )
    body = client_as_alice.post(f"/documents/{d['id']}/process").json()
    assert body["status"] == "processed"
    assert body["extracted"]["invoice_number"] == "INV-9001"
    assert body["extracted"]["currency"] == "EUR"


def test_process_marks_failed_when_required_field_missing(client_as_alice, stub_publisher):
    d = _create(
        client_as_alice,
        doc_type="invoice",
        reference_number="X",
        raw_text="no useful fields here",
    )
    r = client_as_alice.post(f"/documents/{d['id']}/process")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "failed"
    assert "invoice_number" in body["failure_reason"]
    assert stub_publisher[-1].type == "document.failed"


def test_process_twice_returns_409(client_as_alice):
    d = _create(client_as_alice)
    client_as_alice.post(f"/documents/{d['id']}/process")
    r = client_as_alice.post(f"/documents/{d['id']}/process")
    assert r.status_code == 409


def test_process_other_users_doc_returns_404(client_factory, alice, bob):
    d = _create(client_factory(alice))
    r = client_factory(bob).post(f"/documents/{d['id']}/process")
    assert r.status_code == 404
