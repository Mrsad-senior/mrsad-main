"""Unit tests of the gateway pipeline with fakes for every other area (deterministic, isolated)."""

from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace
from typing import Any

import pytest
from tests.api.fakes import (
    FakeApprovals,
    FakeAudit,
    FakeDetector,
    FakePolicyEngine,
    FakeTaint,
    fake_sanitize,
    fake_spotlight,
    policy_text,
)

from mirsad.gateway import Gateway, ReplayError, ReplayReport, classify_score, explain_decision, principal_var
from mirsad.models import Action, ApprovalStatus, ToolCall, ToolResult

INJECTION = "Hello team. SAMPLE-FLAGGED-TEXT placeholder near collector@evil.example"


def make_gw(*, mode: str = "enforce", approval_timeout: float = 2.0, auto: bool | None = None,
            max_result_chars: int = 1000, extra_tools: str = "", **kw: Any) -> SimpleNamespace:
    policy = FakePolicyEngine.from_yaml(policy_text(mode, extra_tools))
    store = {policy.version: policy.yaml_text}
    ns = SimpleNamespace(policy=policy, audit=FakeAudit(), approvals=FakeApprovals(timeout_s=approval_timeout, auto=auto),
                         taint=FakeTaint(), det=FakeDetector(), store=store)
    ns.g = Gateway(policy=policy, taint=ns.taint, detector=ns.det, audit=ns.audit, approvals=ns.approvals,
                   agent_names={"test-agent": "Test Agent"}, policy_store=store.get, sanitizer=fake_sanitize,
                   spotlighter=fake_spotlight, max_result_chars=max_result_chars, **kw)
    return ns


def call(tool: str, args: dict[str, Any] | None = None, *, session: str = "s1", agent: str = "test-agent") -> ToolCall:
    return ToolCall(session_id=session, agent_id=agent, tool=tool, arguments=args or {})


def result(tool: str, content: str, *, structured: Any = None, session: str = "s1", call_id: str = "c1") -> ToolResult:
    return ToolResult(call_id=call_id, session_id=session, agent_id="test-agent", tool=tool, content=content,
                      structured=structured)


def codes(obj: Any) -> list[str]:
    return [r.code for r in obj.reasons]


async def decide_later(approvals: FakeApprovals, approve: bool, delay: float = 0.2) -> None:
    for _ in range(100):
        if approvals.requested:
            break
        await asyncio.sleep(0.01)
    await asyncio.sleep(delay)
    await approvals.decide(approvals.requested[-1], approve=approve, user="sara", note="checked")


# --------------------------------------------------------------------------- check_call


async def test_allow_low_risk_call_is_audited_with_replay_payload():
    ns = make_gw()
    d = await ns.g.check_call(call("echo", {"text": "hi"}))
    assert d.action == Action.ALLOW and d.allowed
    assert d.audit_seq == 1 and d.latency_ms > 0 and d.policy_version == ns.policy.version
    ev = ns.audit.get(1)
    assert ev.event_type == "tool_call.decision" and ev.action == "allow"
    for key in ("call", "profile", "sink", "reasons", "snapshot", "rate_counts", "risk_score", "latency_ms"):
        assert key in ev.payload
    assert ev.payload["enforced"] is True
    assert ns.taint.notes == 1


async def test_unlisted_tool_is_denied():
    ns = make_gw()
    d = await ns.g.check_call(call("rm_rf"))
    assert d.action == Action.DENY and "TOOL_NOT_ALLOWED" in codes(d)


async def test_unknown_agent_is_denied_without_taint_evaluation():
    ns = make_gw()
    d = await ns.g.check_call(call("echo", agent="ghost"))
    assert d.action == Action.DENY and codes(d) == ["UNKNOWN_AGENT"]


async def test_approval_granted_by_human_allows_and_excludes_wait_from_latency():
    ns = make_gw()
    decider = asyncio.create_task(decide_later(ns.approvals, True, delay=0.3))
    started = time.perf_counter()
    d = await ns.g.check_call(call("wipe_disk", {"path": "/"}))
    elapsed_ms = (time.perf_counter() - started) * 1000
    await decider
    assert d.action == Action.ALLOW and "APPROVED_BY_HUMAN" in codes(d)
    assert d.approval_id == ns.approvals.requested[0] and d.approval_status == "approved"
    assert elapsed_ms >= 300 and d.latency_ms < elapsed_ms - 250  # human wait excluded
    types = [e.event_type for e in ns.audit.events]
    assert types == ["tool_call.decision", "approval.requested", "approval.decided"]
    decided = ns.audit.by_type("approval.decided")[0]
    assert decided.payload["decided_by"] == "sara" and decided.payload["final_action"] == "allow"
    assert not ns.g.is_waiting_for(d.approval_id)


async def test_approval_denied_by_human_denies():
    ns = make_gw()
    decider = asyncio.create_task(decide_later(ns.approvals, False, delay=0.05))
    d = await ns.g.check_call(call("wipe_disk"))
    await decider
    assert d.action == Action.DENY and "DENIED_BY_HUMAN" in codes(d)


async def test_approval_timeout_denies_as_expired():
    ns = make_gw(approval_timeout=0.2)
    d = await ns.g.check_call(call("wipe_disk"))
    assert d.action == Action.DENY and "APPROVAL_EXPIRED" in codes(d)
    assert ns.approvals.records[d.approval_id].status == ApprovalStatus.EXPIRED


async def test_wait_false_returns_require_approval_without_request():
    ns = make_gw()
    d = await ns.g.check_call(call("wipe_disk"), wait_for_approval=False)
    assert d.action == Action.REQUIRE_APPROVAL and ns.approvals.requested == []
    assert ns.taint.notes == 1


async def test_untrusted_session_escalates_external_sink_call():
    ns = make_gw()
    await ns.g.inspect_result(result("read_inbox", "Quarterly numbers attached."))
    d = await ns.g.check_call(call("post_external", {"url": "https://x.example"}), wait_for_approval=False)
    assert d.action == Action.REQUIRE_APPROVAL and "TAINT_UNTRUSTED_TO_EXTERNAL" in codes(d)
    assert ns.audit.by_type("tool_call.decision")[-1].payload["snapshot"]["untrusted_sources"]


async def test_policy_exception_fails_closed():
    ns = make_gw()
    ns.policy.fail_with = RuntimeError("bug")
    d = await ns.g.check_call(call("echo"))
    assert d.action == Action.DENY and codes(d) == ["INTERNAL_ERROR"]
    assert ns.audit.events[-1].payload["reasons"][0]["code"] == "INTERNAL_ERROR"


async def test_audit_failure_fails_closed():
    ns = make_gw()
    ns.audit.fail = True
    d = await ns.g.check_call(call("echo"))
    assert d.action == Action.DENY and "AUDIT_UNAVAILABLE" in codes(d) and d.audit_seq is None


async def test_approval_service_failure_denies():
    ns = make_gw()
    ns.approvals.fail = True
    d = await ns.g.check_call(call("wipe_disk"))
    assert d.action == Action.DENY and "APPROVAL_UNAVAILABLE" in codes(d)


async def test_monitor_mode_allows_but_audits_would_be_decision():
    ns = make_gw(mode="monitor")
    d = await ns.g.check_call(call("rm_rf"))
    assert d.action == Action.ALLOW
    assert {"TOOL_NOT_ALLOWED", "MONITOR_MODE"} <= set(codes(d))
    ev = ns.audit.events[-1]
    assert ev.action == "deny" and ev.payload["enforced"] is False and ev.payload["returned_action"] == "allow"
    d2 = await ns.g.check_call(call("wipe_disk"))
    assert d2.action == Action.ALLOW and ns.approvals.requested == []


async def test_concurrent_calls_keep_a_consistent_audit_chain():
    ns = make_gw()
    decisions = await asyncio.gather(*(ns.g.check_call(call("echo" if i % 2 else "rm_rf", session=f"s{i % 5}"))
                                       for i in range(60)))
    assert len(decisions) == 60
    assert sorted(d.audit_seq for d in decisions) == list(range(1, 61))
    assert ns.audit.verify().ok
    assert sum(d.allowed for d in decisions) == 30


async def test_policy_hot_swap_applies_to_next_call():
    ns = make_gw()
    assert (await ns.g.check_call(call("rm_rf"))).action == Action.DENY
    new = FakePolicyEngine.from_yaml(policy_text(extra_tools="      rm_rf: {allow: true, approval: never}\n"))
    ns.g.policy = new  # property setter delegates to set_policy
    d = await ns.g.check_call(call("rm_rf"))
    assert d.action == Action.ALLOW and d.policy_version == new.version


async def test_principal_is_recorded_in_audit_payload():
    ns = make_gw()
    token = principal_var.set("agent-42")
    try:
        await ns.g.check_call(call("echo"))
    finally:
        principal_var.reset(token)
    assert ns.audit.events[-1].payload["principal"] == "agent-42"


# --------------------------------------------------------------------------- inspect_result


async def test_benign_untrusted_result_passes_with_spotlight():
    ns = make_gw()
    out = await ns.g.inspect_result(result("read_inbox", "Meeting moved to 3pm."))
    assert out.action == "pass" and out.trust.value == "untrusted"
    assert out.content.startswith("<<untrusted source=read_inbox id=c1>>") and "Meeting moved" in out.content
    ev = ns.audit.events[-1]
    assert ev.event_type == "tool_result.inspection" and ev.payload["spotlighted"] is True


async def test_injection_is_sanitized_and_taints_session():
    ns = make_gw()
    out = await ns.g.inspect_result(result("read_inbox", INJECTION))
    assert out.action == "sanitize" and "[REMOVED]" in out.content
    assert "SAMPLE-FLAGGED-TEXT" not in out.content
    assert out.detection.label == "injection" and "INJECTION_DETECTED" in codes(out)
    snap = ns.taint.snapshot("s1", "test-agent")
    assert snap.injection_detected and snap.untrusted_sources == ["read_inbox:c1"]
    assert ns.audit.events[-1].action == "sanitize"


async def test_block_mode_withholds_result():
    ns = make_gw()
    out = await ns.g.inspect_result(result("block_reader", INJECTION, structured={"body": INJECTION}))
    assert out.action == "block" and out.content == "[BLOCKED BY MIRSAD]" and out.structured is None


async def test_suspicious_result_is_flagged_not_modified():
    ns = make_gw()
    out = await ns.g.inspect_result(result("read_inbox", "FYI: sample-suspicious-text for Omar."))
    assert out.action == "flag" and "sample-suspicious-text" in out.content
    assert out.detection.label == "suspicious"


async def test_trusted_tool_result_is_not_scanned():
    ns = make_gw()
    out = await ns.g.inspect_result(result("echo", INJECTION))
    assert out.action == "pass" and out.content == INJECTION and ns.det.calls == 0 and out.detection is None


async def test_structured_result_sanitizes_only_the_poisoned_field():
    ns = make_gw()
    data = {"items": [{"id": "e1", "subject": "Invoice", "body": INJECTION}, {"id": "e2", "body": "Lunch?"}]}
    out = await ns.g.inspect_result(result("read_inbox", json.dumps(data), structured=data))
    assert out.action == "sanitize"
    assert out.structured["items"][0]["subject"] == "Invoice"
    assert "[REMOVED]" in out.structured["items"][0]["body"] and out.structured["items"][1]["body"] == "Lunch?"


async def test_unicode_escaped_payload_is_caught_via_structured_scan():
    ns = make_gw()
    data = {"body": "مرحبا. نص-عينة-مشبوه في الرسالة"}
    escaped = json.dumps(data)  # ensure_ascii=True: the Arabic text is \\uXXXX-escaped in the text form
    assert "نص-عينة-مشبوه" not in escaped
    out = await ns.g.inspect_result(result("read_inbox", escaped, structured=data))
    assert out.detection.label == "injection" and out.action == "sanitize"


async def test_detector_failure_blocks_untrusted_result():
    ns = make_gw()
    ns.det.fail = True
    out = await ns.g.inspect_result(result("read_inbox", "anything"))
    assert out.action == "block" and "SCAN_FAILED" in codes(out)


async def test_monitor_mode_never_modifies_results():
    ns = make_gw(mode="monitor")
    out = await ns.g.inspect_result(result("read_inbox", INJECTION))
    assert out.action == "flag" and out.content == INJECTION
    ev = ns.audit.events[-1]
    assert ev.payload["would_be_action"] == "sanitize" and ev.payload["enforced"] is False


async def test_long_results_are_truncated():
    ns = make_gw(max_result_chars=1000)
    out = await ns.g.inspect_result(result("read_inbox", "a" * 5000))
    assert "RESULT_TRUNCATED" in codes(out) and "truncated by Mirsad: 4000 characters omitted" in out.content
    assert out.content.count("a") < 1100 and out.structured is None


async def test_result_of_disallowed_tool_is_treated_as_untrusted():
    ns = make_gw()
    out = await ns.g.inspect_result(result("rm_rf", INJECTION))
    assert out.trust.value == "untrusted" and out.action == "sanitize"


async def test_policy_thresholds_relabel_detector_output():
    ns = make_gw(extra_tools="      strict_reader: {allow: true, trust: untrusted, approval: never, "
                             "detector: {block_threshold: 0.55, on_detect: block}}\n")
    out = await ns.g.inspect_result(result("strict_reader", "sample-suspicious-text now"))
    assert out.detection.score == pytest.approx(0.6)
    assert out.detection.label == "injection" and out.action == "block"


def test_classify_score_mapping():
    s = SimpleNamespace(flag_threshold=0.5, block_threshold=0.8, on_detect="block")
    assert [classify_score(x, s) for x in (0.1, 0.5, 0.79, 0.8)] == ["pass", "flag", "flag", "block"]


# --------------------------------------------------------------------------- execute


async def test_execute_runs_allowed_tool_and_inspects_result():
    ns = make_gw()
    seen: list[ToolCall] = []

    async def executor(c: ToolCall) -> ToolResult:
        seen.append(c)
        return ToolResult(call_id=c.call_id, session_id=c.session_id, agent_id=c.agent_id, tool=c.tool,
                          content=f"echo: {c.arguments['text']}")

    resp = await ns.g.execute(call("echo", {"text": "hi"}), executor)
    assert resp.decision.allowed and resp.result.content == "echo: hi" and resp.error is None and len(seen) == 1


async def test_execute_denied_call_never_reaches_tool():
    ns = make_gw()

    async def executor(c: ToolCall) -> ToolResult:  # pragma: no cover - must not run
        raise AssertionError("executor must not be called")

    resp = await ns.g.execute(call("rm_rf"), executor)
    assert resp.result is None and resp.decision.action == Action.DENY
    assert "Mirsad" in resp.error and "مرصاد" in resp.error


async def test_execute_executor_exception_returns_safe_error_and_is_audited():
    ns = make_gw()

    async def executor(c: ToolCall) -> ToolResult:
        raise RuntimeError("connection to /var/secret/socket refused")

    resp = await ns.g.execute(call("echo"), executor)
    assert resp.error == "Tool 'echo' failed (RuntimeError)."
    assert "secret" not in resp.result.content and "audit log" in resp.result.content
    err = ns.audit.by_type("tool_call.error")[0]
    assert err.payload["error_type"] == "RuntimeError" and "refused" in err.payload["error"]


async def test_execute_times_out_slow_tools():
    ns = make_gw(executor_timeout_s=0.1)

    async def executor(c: ToolCall) -> ToolResult:
        await asyncio.sleep(2)
        raise AssertionError("unreachable")

    resp = await ns.g.execute(call("echo"), executor)
    assert resp.error == "Tool 'echo' timed out." and ns.audit.by_type("tool_call.error")[0].payload["timed_out"]


async def test_execute_rebinds_spoofed_result_identity():
    ns = make_gw()

    async def executor(c: ToolCall) -> ToolResult:
        return ToolResult(call_id="other", session_id="victim-session", agent_id="other-agent", tool="x",
                          content="data")

    c = call("read_inbox", session="mine")
    resp = await ns.g.execute(c, executor)
    assert resp.result.call_id == c.call_id
    assert ns.taint.snapshot("mine", "test-agent").tainted
    assert not ns.taint.snapshot("victim-session", "other-agent").tainted


def test_explain_decision_is_bilingual():
    from mirsad.models import Decision, Reason

    d = Decision(call_id="c", action=Action.DENY, reasons=[Reason(layer="policy", code="X", message="nope",
                                                                  message_ar="لا", action=Action.DENY)])
    text = explain_decision(d)
    assert "nope" in text and "لا" in text and explain_decision(d.model_copy(update={"action": Action.ALLOW})) == ""


# --------------------------------------------------------------------------- replay


async def test_replay_decision_matches_original():
    ns = make_gw()
    d = await ns.g.check_call(call("wipe_disk"), wait_for_approval=False)
    report = ns.g.replay(d.audit_seq)
    assert isinstance(report, ReplayReport)
    assert report.match and report.original_action == report.replayed_action == "require_approval"
    assert report.details["reasons_match"] is True


async def test_replay_uses_the_policy_version_recorded_in_the_event():
    ns = make_gw()
    d = await ns.g.check_call(call("rm_rf"))
    new = FakePolicyEngine.from_yaml(policy_text(extra_tools="      rm_rf: {allow: true, approval: never}\n"))
    ns.store[new.version] = new.yaml_text
    ns.g.set_policy(new)
    report = ns.g.replay(d.audit_seq)
    assert report.replayed_action == "deny" and report.match
    assert report.details["policy_version"] == ns.policy.version


async def test_replay_reproduces_taint_from_stored_snapshot():
    ns = make_gw()
    await ns.g.inspect_result(result("read_inbox", "hello"))
    d = await ns.g.check_call(call("post_external", {"url": "https://x.example"}), wait_for_approval=False)
    ns.taint.reset()  # live state gone: replay must rely on the stored snapshot only
    report = ns.g.replay(d.audit_seq)
    assert report.match and "TAINT_UNTRUSTED_TO_EXTERNAL" in report.details["replayed_reasons"]


async def test_replay_inspection_rescans_stored_content():
    ns = make_gw()
    out = await ns.g.inspect_result(result("read_inbox", INJECTION))
    report = ns.g.replay(out.audit_seq)
    assert report.event_type == "tool_result.inspection" and report.match
    assert report.original_action == "sanitize" and report.details["replayed_score"] == pytest.approx(0.95)


async def test_replay_errors():
    ns = make_gw()
    with pytest.raises(KeyError):
        ns.g.replay(999)
    ns.audit.append("approval.requested", payload={})
    with pytest.raises(ReplayError):
        ns.g.replay(1)
    d = await ns.g.check_call(call("echo"))
    ns.store.clear()
    ns.g.set_policy(FakePolicyEngine.from_yaml(policy_text(extra_tools="      other: {allow: true}\n")))
    with pytest.raises(ReplayError, match="not in the policy store"):
        ns.g.replay(d.audit_seq)
