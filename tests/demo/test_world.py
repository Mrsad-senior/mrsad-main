"""Tests for the simulated Najd Trading Co. world and its tools."""

from __future__ import annotations

import csv
import io

import pytest
from demo.world import (
    INTERNAL_DOMAIN,
    TOOLS,
    ToolArgumentError,
    World,
    call_tool,
    to_text,
    tool_schemas,
)


@pytest.fixture
def world() -> World:
    return World()


def test_seed_determinism():
    a, b = World(), World()
    assert a.customers == b.customers
    assert a.emails == b.emails
    assert a.web_pages == b.web_pages
    assert a.documents == b.documents


def test_different_seed_differs():
    assert World(seed=1).customers != World(seed=2).customers


def test_seed_counts(world: World):
    assert len(world.customers) == 120
    assert len(world.emails) == 30
    assert len(world.web_pages) == 12
    assert len(world.documents) == 12
    assert len(TOOLS) == 12


def test_stable_ids(world: World):
    assert world.customers[0]["id"] == "C001"
    assert world.customers[-1]["id"] == "C120"
    assert world.emails[0]["id"] == "E001"
    assert "D001" in world.documents and "D010" in world.documents


def test_customer_shape(world: World):
    c = world.customers[0]
    for key in ("id", "name", "name_ar", "email", "phone", "city", "tier", "balance_sar", "notes"):
        assert key in c
    assert c["phone"].startswith("05") and len(c["phone"]) == 10
    assert c["email"].endswith(("@mail.example", "@customer.example"))


def test_data_is_fake(world: World):
    # Every address uses the reserved .example TLD.
    for c in world.customers:
        assert c["email"].endswith(".example")
    for e in world.emails:
        assert e["from"].endswith(".example") and e["to"].endswith(".example")
    assert INTERNAL_DOMAIN.endswith(".example")


def test_bilingual_content(world: World):
    assert any(e["lang"] == "ar" for e in world.emails)
    assert any(e["lang"] == "en" for e in world.emails)
    assert any(c["name_ar"] for c in world.customers)
    assert any(d["lang"] == "ar" for d in world.documents.values())


def test_external_document_sources(world: World):
    sources = {d["source"] for d in world.documents.values()}
    assert sources == {"internal", "external"}
    assert world.documents["D010"]["source"] == "external"  # applicant CV
    assert world.documents["D009"]["source"] == "external"  # vendor invoice


# --------------------------------------------------------------------------- happy paths


def test_list_emails(world: World):
    rows = call_tool(world, "list_emails", {"folder": "inbox", "limit": 5})
    assert len(rows) == 5
    assert all(set(r) == {"id", "from", "to", "subject", "date", "lang"} for r in rows)


def test_list_emails_defaults(world: World):
    rows = call_tool(world, "list_emails", {})
    assert len(rows) == 10


def test_read_email(world: World):
    e = call_tool(world, "read_email", {"email_id": "E001"})
    assert e["id"] == "E001" and "body" in e


def test_search_customers(world: World):
    rows = call_tool(world, "search_customers", {"query": "Riyadh", "limit": 50})
    assert all("riyadh" in " ".join(str(v) for v in r.values()).lower() for r in rows)


def test_search_customers_by_id(world: World):
    rows = call_tool(world, "search_customers", {"query": "C001"})
    assert rows and rows[0]["id"] == "C001"


def test_get_customer(world: World):
    c = call_tool(world, "get_customer", {"customer_id": "C005"})
    assert c["id"] == "C005"


def test_list_documents(world: World):
    docs = call_tool(world, "list_documents", {})
    assert len(docs) == 12
    assert all(set(d) == {"id", "title", "owner", "lang", "source"} for d in docs)


def test_read_document(world: World):
    d = call_tool(world, "read_document", {"doc_id": "D001"})
    assert d["id"] == "D001" and "body" in d


# --------------------------------------------------------------------------- side effects


def test_send_email_records_side_effect(world: World):
    out = call_tool(world, "send_email", {"to": "a@x.example", "subject": "hi", "body": "b"})
    assert out["status"] == "sent"
    assert len(world.outbox) == 1
    assert world.side_effects[-1]["tool"] == "send_email"


def test_export_customers_csv_and_side_effect(world: World):
    text = call_tool(world, "export_customers", {"count": 3})
    rows = list(csv.reader(io.StringIO(text)))
    assert rows[0][0] == "id"
    assert len(rows) == 4  # header + 3
    assert len(world.exports) == 1
    assert "export_customers" in {s["tool"] for s in world.side_effects}


def test_update_customer_note_mutates(world: World):
    call_tool(world, "update_customer_note", {"customer_id": "C002", "note": "VIP now"})
    assert call_tool(world, "get_customer", {"customer_id": "C002"})["notes"] == "VIP now"
    assert world.notes_log[-1]["customer_id"] == "C002"


def test_delete_customer(world: World):
    call_tool(world, "delete_customer", {"customer_id": "C003"})
    assert "C003" in world.deleted
    with pytest.raises(ToolArgumentError):
        call_tool(world, "get_customer", {"customer_id": "C003"})


def test_deleted_customer_hidden_from_search(world: World):
    call_tool(world, "delete_customer", {"customer_id": "C004"})
    rows = call_tool(world, "search_customers", {"query": "C004"})
    assert all(r["id"] != "C004" for r in rows)


def test_fetch_url_known_and_unknown(world: World):
    page = call_tool(world, "fetch_url", {"url": "https://help.najd-trading.example/faq"})
    assert page["status"] == 200 and page["body"]
    missing = call_tool(world, "fetch_url", {"url": "https://nowhere.example/x"})
    assert missing["status"] == 404
    assert len(world.http_log) == 2


def test_transfer_funds_records(world: World):
    out = call_tool(world, "transfer_funds", {"to_iban": "SA123", "amount_sar": 500, "memo": "m"})
    assert out["status"] == "transferred"
    assert world.transfers[-1]["to_iban"] == "SA123"


# --------------------------------------------------------------------------- validation errors


def test_unknown_tool(world: World):
    with pytest.raises(ToolArgumentError, match="unknown tool"):
        call_tool(world, "nope", {})


def test_missing_required_arg(world: World):
    with pytest.raises(ToolArgumentError, match="missing required argument 'email_id'"):
        call_tool(world, "read_email", {})


def test_unknown_arg(world: World):
    with pytest.raises(ToolArgumentError, match="unknown argument"):
        call_tool(world, "read_email", {"email_id": "E001", "extra": 1})


def test_enum_violation(world: World):
    with pytest.raises(ToolArgumentError, match="must be one of"):
        call_tool(world, "list_emails", {"folder": "spam"})


def test_type_violation(world: World):
    with pytest.raises(ToolArgumentError, match="must be a integer"):
        call_tool(world, "list_emails", {"limit": "five"})


def test_bool_rejected_as_number(world: World):
    with pytest.raises(ToolArgumentError, match="must be a integer"):
        call_tool(world, "list_emails", {"limit": True})


def test_min_max_bounds(world: World):
    with pytest.raises(ToolArgumentError, match="<= 200"):
        call_tool(world, "export_customers", {"count": 9999})
    with pytest.raises(ToolArgumentError, match=">= 1"):
        call_tool(world, "list_emails", {"limit": 0})


def test_unknown_ids_raise(world: World):
    with pytest.raises(ToolArgumentError):
        call_tool(world, "read_email", {"email_id": "E999"})
    with pytest.raises(ToolArgumentError):
        call_tool(world, "get_customer", {"customer_id": "C999"})
    with pytest.raises(ToolArgumentError):
        call_tool(world, "read_document", {"doc_id": "D999"})


# --------------------------------------------------------------------------- plant / reset / snapshot


@pytest.mark.parametrize("position", ["start", "middle", "end"])
def test_plant_email_positions(world: World, position: str):
    payload = "INJECTED-PAYLOAD-XYZ"
    world.plant("email", "E001", payload, position=position)
    body = call_tool(world, "read_email", {"email_id": "E001"})["body"]
    assert payload in body


def test_plant_all_vectors(world: World):
    world.plant("email", "E002", "P1")
    world.plant("web", "https://help.najd-trading.example/faq", "P2")
    world.plant("document", "D001", "P3")
    world.plant("crm_note", "C001", "P4")
    assert "P1" in call_tool(world, "read_email", {"email_id": "E002"})["body"]
    assert "P2" in call_tool(world, "fetch_url", {"url": "https://help.najd-trading.example/faq"})["body"]
    assert "P3" in call_tool(world, "read_document", {"doc_id": "D001"})["body"]
    assert "P4" in call_tool(world, "get_customer", {"customer_id": "C001"})["notes"]


def test_plant_unknown_target(world: World):
    with pytest.raises(ToolArgumentError):
        world.plant("email", "E999", "x")
    with pytest.raises(ToolArgumentError):
        world.plant("web", "https://nope.example", "x")
    with pytest.raises(ToolArgumentError):
        world.plant("crm_note", "C999", "x")


def test_reset_restores_and_clears(world: World):
    world.plant("email", "E001", "PLANT")
    call_tool(world, "send_email", {"to": "a@x.example", "subject": "s", "body": "b"})
    call_tool(world, "delete_customer", {"customer_id": "C001"})
    world.reset()
    assert "PLANT" not in call_tool(world, "read_email", {"email_id": "E001"})["body"]
    assert world.outbox == [] and world.deleted == [] and world.side_effects == []


def test_snapshot(world: World):
    call_tool(world, "send_email", {"to": "a@x.example", "subject": "s", "body": "b"})
    call_tool(world, "transfer_funds", {"to_iban": "SA1", "amount_sar": 10})
    snap = world.snapshot()
    assert snap["counts"]["customers"] == 120
    assert len(snap["outbox"]) == 1 and len(snap["transfers"]) == 1
    assert len(snap["side_effects"]) == 2
    # exports in snapshot omit the raw CSV payload
    call_tool(world, "export_customers", {"count": 1})
    assert "csv" not in world.snapshot()["exports"][0]


# --------------------------------------------------------------------------- schemas / helpers


def test_tool_schemas_shape():
    schemas = tool_schemas()
    assert len(schemas) == 12
    for s in schemas:
        assert s["type"] == "function"
        fn = s["function"]
        assert fn["name"] in TOOLS
        assert fn["description"]
        assert fn["parameters"]["type"] == "object"


def test_to_text():
    assert to_text("hi") == "hi"
    assert to_text({"a": 1}) == '{"a": 1}'
    assert "نورة" in to_text({"name": "نورة"})  # non-ASCII preserved
