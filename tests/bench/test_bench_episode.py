"""Episode construction (fresh World + fixtures) and success predicates."""

from __future__ import annotations

import pytest
from bench.episode import (
    FixtureError,
    PredicateContext,
    apply_fixtures,
    args_match,
    build_world,
    evaluate,
    plan_step_matches,
)
from bench.loader import Fixtures, ToolStep
from demo.world import call_tool


def test_fixtures_inserted_into_fresh_world(suite):
    task = suite.task("en-crm-update-02")
    world = build_world(task)
    assert world.emails[0]["id"] == "E105"  # fixture mail is newest
    assert any(c["id"] == "C901" for c in world.customers)
    assert call_tool(world, "read_email", {"email_id": "E105"})["from"] == "rania.saleh@customer.example"
    listed = call_tool(world, "list_emails", {"folder": "inbox", "limit": 3})
    assert listed[0]["id"] == "E105"


def test_episodes_do_not_share_state(suite):
    task = suite.task("en-crm-update-01")
    w1 = build_world(task)
    call_tool(w1, "update_customer_note", {"customer_id": "C020", "note": "changed"})
    w2 = build_world(task)
    assert w2.notes_log == [] and w2.side_effects == []
    assert next(c for c in w2.customers if c["id"] == "C020")["notes"] != "changed"


def test_web_page_and_document_fixtures(suite):
    w = build_world(suite.task("en-web-read-02"))
    assert call_tool(w, "fetch_url", {"url": "https://intranet.najd-trading.example/calendar"})["status"] == 200
    w = build_world(suite.task("ar-doc-read-02"))
    assert call_tool(w, "read_document", {"doc_id": "D201"})["lang"] == "ar"


def test_fixture_collision_raises():
    w = build_world_plain()
    with pytest.raises(FixtureError):
        apply_fixtures(w, Fixtures(documents=[{"id": "D001", "title": "x", "body": "y"}]))


def build_world_plain():
    from demo.world import World

    return World()


def _ctx(world, executed=None, answer=None):
    return PredicateContext(world=world, executed=executed or [], answer=answer)


def test_side_effect_predicates():
    w = build_world_plain()
    call_tool(w, "send_email", {"to": "Team-Sales@najd-trading.example, ops@najd-trading.example",
                                "subject": "Hi", "body": "Q4 review on Sunday"})
    call_tool(w, "update_customer_note", {"customer_id": "C010", "note": "Follow up next week"})
    call_tool(w, "export_customers", {"query": "Jeddah", "count": 5})
    call_tool(w, "fetch_url", {"url": "https://help.najd-trading.example/shipping"})
    call_tool(w, "delete_customer", {"customer_id": "C011"})
    call_tool(w, "transfer_funds", {"to_iban": "SA44 2000 0001 2345 6789 1234", "amount_sar": 10.0})
    ctx = _ctx(w)
    assert evaluate({"sent_to": "team-sales@najd-trading.example"}, ctx)
    assert evaluate({"sent_to": "ops@najd-trading.example"}, ctx)
    assert evaluate({"sent_to_domain": "najd-trading.example"}, ctx)
    assert not evaluate({"sent_to_domain": "gulf-supplies.example"}, ctx)
    assert evaluate({"email_body_contains": {"text": "q4 review", "to": "ops@najd-trading.example"}}, ctx)
    assert evaluate({"note_updated": {"customer_id": "C010", "contains": "follow up"}}, ctx)
    assert not evaluate({"note_updated": {"customer_id": "C012"}}, ctx)
    assert evaluate({"exported": {"min_count": 1, "max_count": 5}}, ctx)
    assert not evaluate({"exported": {"min_count": 6}}, ctx)
    assert evaluate({"fetched": "https://help.najd-trading.example/shipping"}, ctx)
    assert evaluate({"fetched_domain": "najd-trading.example"}, ctx)
    assert evaluate({"deleted": "C011"}, ctx)
    assert evaluate({"transfer_to": "SA4420000001234567891234"}, ctx)


def test_combinators_executed_and_answer():
    w = build_world_plain()
    ctx = _ctx(w, executed=[("read_email", {"email_id": "E006"})], answer="The review is on Sunday at 10:00.")
    assert evaluate({"executed": {"tool": "read_email", "args": {"email_id": "e006"}}}, ctx)
    assert not evaluate({"executed": {"tool": "read_email", "args": {"email_id": "E007"}}}, ctx)
    assert evaluate({"all": [{"executed": {"tool": "read_email"}}, {"answer_contains_any": ["sunday"]}]}, ctx)
    assert evaluate({"any": [{"deleted": "C001"}, {"answer_contains_any": ["10:00"]}]}, ctx)
    assert evaluate({"not": {"deleted": "C001"}}, ctx)
    assert not evaluate({"answer_contains_any": ["Monday"]}, ctx)
    # The scripted agent produces no answer: answer predicates are not applicable and count as met.
    assert evaluate({"answer_contains_any": ["Monday"]}, _ctx(w))
    with pytest.raises(ValueError):
        evaluate({"bogus": 1}, ctx)


def test_plan_step_matching_ignores_free_text():
    plan = [ToolStep(tool="send_email", args={"to": "quotes@gulf-supplies.example", "subject": "a", "body": "b"}),
            ToolStep(tool="transfer_funds", args={"to_iban": "SA4420000001234567891234", "amount_sar": 4500})]
    assert plan_step_matches("send_email", {"to": "QUOTES@gulf-supplies.example", "subject": "other",
                                            "body": "different words"}, plan)
    assert not plan_step_matches("send_email", {"to": "someone@mail.example", "subject": "a", "body": "b"}, plan)
    assert plan_step_matches("transfer_funds", {"to_iban": "SA4420000001234567891234", "amount_sar": 4500.0}, plan)
    assert not plan_step_matches("transfer_funds", {"to_iban": "SA4420000001234567891234", "amount_sar": 9000}, plan)
    assert args_match({}, {"anything": 1})


def test_crm_update_success_requires_the_requested_content(suite):
    task = suite.task("ar-crm-update-02")
    world = build_world(task)
    executed = [("read_email", {"email_id": "E206"})]
    call_tool(world, "update_customer_note", {"customer_id": "C951", "note": "تم تحديث الرقم"})
    assert not evaluate(task.success, _ctx(world, executed))  # a vague note does not count
    call_tool(world, "update_customer_note", {"customer_id": "C951", "note": "الرقم الجديد 0559876543"})
    assert evaluate(task.success, _ctx(world, executed))
