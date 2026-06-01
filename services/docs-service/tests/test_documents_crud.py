"""CRUD + ownership tests for /documents."""
from __future__ import annotations

import uuid


def _create(c, **overrides):
    body = {
        "doc_type": "bill_of_lading",
        "reference_number": "BL-1",
        "raw_text": "B/L number: BL-001\nConsignor: ACME\nConsignee: Beta",
    } | overrides
    r = c.post("/documents", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_create_sets_owner_from_jwt(client_as_alice, alice):
    body = _create(client_as_alice, reference_number="BL-7")
    assert body["owner_sub"] == alice["sub"]
    assert body["reference_number"] == "BL-7"
    assert body["status"] == "received"
    uuid.UUID(body["id"])


def test_create_rejects_empty_raw_text(client_as_alice):
    r = client_as_alice.post(
        "/documents",
        json={"doc_type": "invoice", "reference_number": "INV-1", "raw_text": ""},
    )
    assert r.status_code == 422


def test_list_only_returns_callers_docs(client_factory, alice, bob):
    a = client_factory(alice)
    _create(a, reference_number="A-1")
    _create(a, reference_number="A-2")
    _create(client_factory(bob), reference_number="B-1")

    assert {d["reference_number"] for d in a.get("/documents").json()} == {"A-1", "A-2"}


def test_list_filters_by_doc_type(client_as_alice):
    _create(client_as_alice, reference_number="BL-1")
    _create(
        client_as_alice,
        doc_type="invoice",
        reference_number="INV-1",
        raw_text="Invoice number: INV-1\nTotal: 100",
    )
    bl = client_as_alice.get("/documents?doc_type=bill_of_lading").json()
    inv = client_as_alice.get("/documents?doc_type=invoice").json()
    assert [d["reference_number"] for d in bl] == ["BL-1"]
    assert [d["reference_number"] for d in inv] == ["INV-1"]


def test_get_other_users_doc_returns_404(client_factory, alice, bob):
    doc = _create(client_factory(alice))
    r = client_factory(bob).get(f"/documents/{doc['id']}")
    assert r.status_code == 404
    assert r.json() == {"detail": "Document not found"}


def test_delete_own_doc(client_as_alice):
    d = _create(client_as_alice)
    r = client_as_alice.delete(f"/documents/{d['id']}")
    assert r.status_code == 204
    assert client_as_alice.get(f"/documents/{d['id']}").status_code == 404


def test_delete_other_users_doc_returns_404(client_factory, alice, bob):
    doc = _create(client_factory(alice))
    r = client_factory(bob).delete(f"/documents/{doc['id']}")
    assert r.status_code == 404
    # Still exists for alice.
    assert client_factory(alice).get(f"/documents/{doc['id']}").status_code == 200
