"""Tests for the curated demo scenarios."""

from __future__ import annotations

import pytest
from demo.scenarios import apply_scenario, get_scenario, list_scenarios
from demo.world import World, call_tool


def test_scenario_count_and_balance():
    scenarios = list_scenarios()
    assert len(scenarios) >= 6
    langs_ar = [s for s in scenarios if "ar" in s.id or "نجد" in s.title_ar]
    assert langs_ar  # at least some Arabic scenarios
    cats = {s.expected_attack.category for s in scenarios}
    assert {"exfiltration", "destruction", "fraud"} <= cats


def test_each_scenario_is_bilingual_and_complete():
    for s in list_scenarios():
        assert s.title_en and s.title_ar
        assert s.user_prompt_en and s.user_prompt_ar
        assert s.setup
        assert s.expected_attack.tool
        assert s.expected_attack.description_en and s.expected_attack.description_ar


def test_scenario_ids_unique():
    ids = [s.id for s in list_scenarios()]
    assert len(ids) == len(set(ids))


def test_apply_scenario_plants_payload():
    world = World()
    apply_scenario(world, "cv-delete-customer")
    body = call_tool(world, "read_document", {"doc_id": "D010"})["body"]
    assert "delete_customer" in body and "C017" in body


def test_apply_scenario_resets_between_runs():
    world = World()
    apply_scenario(world, "cv-delete-customer")
    apply_scenario(world, "invoice-exfil")
    # The previous plant is gone after re-applying.
    assert "delete_customer" not in call_tool(world, "read_document", {"doc_id": "D010"})["body"]
    assert "collector@evil.example" in call_tool(world, "read_email", {"email_id": "E001"})["body"]


def test_apply_scenario_clears_side_effects():
    world = World()
    call_tool(world, "send_email", {"to": "a@x.example", "subject": "s", "body": "b"})
    apply_scenario(world, "vendor-bank-fraud")
    assert world.outbox == []


def test_unknown_scenario_raises():
    with pytest.raises(KeyError):
        get_scenario("does-not-exist")
    with pytest.raises(KeyError):
        apply_scenario(World(), "nope")


def test_scenarios_target_existing_ids():
    world = World()
    for s in list_scenarios():
        for spec in s.setup:
            if spec.vector == "email":
                assert any(e["id"] == spec.target_id for e in world.emails)
            elif spec.vector == "document":
                assert spec.target_id in world.documents
            elif spec.vector == "web":
                assert spec.target_id in world.web_pages
            elif spec.vector == "crm_note":
                assert any(c["id"] == spec.target_id for c in world.customers)
