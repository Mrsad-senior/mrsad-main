"""PolicyEngine: tool resolution, sinks, evaluation order, rate limits, rules, approval and versioning."""

from __future__ import annotations

import json
import threading
import time

import pytest
from policy_helpers import AGENT, POLICY_DIR, codes, make_call, policy_text

from mirsad.models import Action, Risk, SinkKind, ToolProfile, combine_reasons
from mirsad.policy import PolicyEngine, PolicyError, RateLimiter, canonical_json, load_policy

GLOB_AGENT = """\
- id: a
  tools:
    crm_get_customer: {allow: false}
    "crm_*":          {allow: true, risk: medium}
    "crm_admin_*":    {allow: false}
    "*":              {allow: false}
"""


# --------------------------------------------------------------------------- tool resolution


@pytest.mark.parametrize(("tool", "allowed", "entry"), [
    ("crm_get_customer", False, "crm_get_customer"),  # exact beats any glob
    ("crm_list", True, "crm_*"),
    ("crm_admin_delete", False, "crm_admin_*"),       # longer glob beats shorter glob
    ("erp_export", False, "*"),                       # catch-all last
    ("CRM_list", False, "*"),                         # tool names are case-sensitive
])
def test_tool_resolution_precedence(build, tool, allowed, entry):
    profile = build(GLOB_AGENT).tool_profile("a", tool)
    assert profile.allowed is allowed
    assert profile.matched_rule == entry
    assert profile.tool == tool


def test_unmatched_tool_with_default_deny(build):
    engine = build("- id: a\n  tools:\n    t: {allow: true}\n")
    ev = engine.evaluate_call(make_call("other", agent="a"))
    assert codes(ev.reasons) == ["TOOL_NOT_ALLOWED"]
    assert ev.reasons[0].evidence["matched_entry"] == "defaults.decision"


def test_unmatched_tool_with_default_allow_gets_conservative_profile(build):
    engine = build("- id: a\n", extra="defaults: {decision: allow}\n")
    profile = engine.tool_profile("a", "mystery_tool")
    assert profile.allowed and profile.scan
    assert profile.trust.value == "untrusted" and profile.sink == "external" and profile.risk == Risk.MEDIUM
    assert engine.evaluate_call(make_call("mystery_tool", agent="a")).action == Action.ALLOW


def test_unmatched_tool_with_default_require_approval(build):
    engine = build("- id: a\n", extra="defaults: {decision: require_approval}\n")
    ev = engine.evaluate_call(make_call("mystery_tool", agent="a"))
    assert ev.action == Action.REQUIRE_APPROVAL
    assert "APPROVAL_ALWAYS" in codes(ev.reasons)


def test_profile_of_default_tools(engine):
    send = engine.tool_profile(AGENT, "send_email")
    assert send == ToolProfile(tool="send_email", allowed=True, sink="dynamic", sink_params=("to", "cc", "bcc"),
                               risk=Risk.MEDIUM, approval="on_risk", scan=False, matched_rule="send_email")
    assert engine.tool_profile(AGENT, "read_email").scan is True
    assert engine.tool_profile(AGENT, "get_customer").sensitivity.value == "confidential"


def test_unknown_agent_profile_and_visible_tools(engine):
    assert engine.tool_profile("ghost", "send_email").allowed is False
    assert engine.visible_tools("ghost", ["send_email"]) == []
    tools = ["send_email", "rm_rf", "read_email", "transfer_funds"]
    assert engine.visible_tools(AGENT, tools) == ["send_email", "read_email", "transfer_funds"]


# --------------------------------------------------------------------------- sink resolution


@pytest.mark.parametrize(("arguments", "sink"), [
    ({"to": "sara@najd-trading.example"}, SinkKind.INTERNAL),
    ({"to": "ops@mail.najd-trading.example"}, SinkKind.INTERNAL),            # subdomain is internal
    ({"to": "Sara <SARA@NAJD-TRADING.EXAMPLE>"}, SinkKind.INTERNAL),
    ({"to": "bob@evil.example"}, SinkKind.EXTERNAL),
    ({"to": "x@najd-trading.example.evil.example"}, SinkKind.EXTERNAL),     # suffix trick
    ({"to": ["a@najd-trading.example"], "cc": "x@evil.example"}, SinkKind.EXTERNAL),  # mixed params
    ({"to": "a@najd-trading.example; b@evil.example"}, SinkKind.EXTERNAL),  # mixed separated string
    ({"to": ["a@najd-trading.example", "b@najd-trading.example"], "bcc": []}, SinkKind.INTERNAL),
    ({"to": "manager"}, SinkKind.EXTERNAL),                                  # unknown destination fails closed
    ({}, SinkKind.NONE),
    ({"to": "", "cc": None, "bcc": []}, SinkKind.NONE),
    ({"subject": "x@evil.example"}, SinkKind.NONE),                         # only sink_params count
])
def test_dynamic_sink_resolution(engine, arguments, sink):
    call = make_call("send_email", **arguments)
    assert engine.resolve_sink(call, engine.tool_profile(AGENT, "send_email")) == sink


@pytest.mark.parametrize(("tool", "sink"), [
    ("fetch_url", SinkKind.EXTERNAL), ("transfer_funds", SinkKind.EXTERNAL), ("list_emails", SinkKind.NONE),
])
def test_static_sinks_are_returned_as_declared(engine, tool, sink):
    call = make_call(tool, url="https://najd-trading.example")
    assert engine.resolve_sink(call, engine.tool_profile(AGENT, tool)) == sink


def test_dynamic_sink_without_internal_domains_is_always_external():
    engine = PolicyEngine.from_yaml(
        "version: 1\nagents:\n  - id: a\n    tools:\n      t: {allow: true, sink: dynamic, sink_params: [to]}\n")
    call = make_call("t", agent="a", to="sara@najd-trading.example")
    assert engine.resolve_sink(call, engine.tool_profile("a", "t")) == SinkKind.EXTERNAL
    assert engine.internal_domains() == []


# --------------------------------------------------------------------------- evaluation order & reasons


def test_unknown_agent_is_denied(engine):
    ev = engine.evaluate_call(make_call("send_email", agent="ghost", to="x@najd-trading.example"))
    assert codes(ev.reasons) == ["UNKNOWN_AGENT"]
    reason = ev.reasons[0]
    assert reason.action == Action.DENY and reason.layer == "policy"
    assert "ghost" in reason.message and "ghost" in reason.message_ar
    assert ev.rate_counts == {}


def test_tool_not_allowed_is_denied_without_other_reasons(engine):
    ev = engine.evaluate_call(make_call("drop_database"))
    assert codes(ev.reasons) == ["TOOL_NOT_ALLOWED"]
    assert ev.reasons[0].evidence == {"tool": "drop_database", "agent_id": AGENT, "matched_entry": "*"}
    assert ev.action == Action.DENY


@pytest.mark.parametrize(("tool", "risk", "score"), [
    ("update_customer_note", "low", 0.1), ("send_email", "medium", 0.3),
    ("export_customers", "high", 0.6), ("delete_customer", "critical", 0.9),
])
def test_tool_risk_reason_is_informational(engine, tool, risk, score):
    ev = engine.evaluate_call(make_call(tool), now=0.0)
    reason = next(r for r in ev.reasons if r.code == "TOOL_RISK")
    assert reason.action == Action.ALLOW
    assert reason.risk_score == score
    assert reason.evidence["risk"] == risk
    assert ev.risk_score >= score


def test_allowed_call_has_only_the_risk_reason(engine):
    ev = engine.evaluate_call(make_call("send_email", to="sara@najd-trading.example", body="Hi"))
    assert codes(ev.reasons) == ["TOOL_RISK"]
    assert ev.action == Action.ALLOW
    assert ev.sink == SinkKind.INTERNAL
    assert combine_reasons(ev.reasons) == (Action.ALLOW, 0.3)


def test_approval_always_tool(engine):
    ev = engine.evaluate_call(make_call("delete_customer", customer_id="C017"))
    assert codes(ev.reasons) == ["TOOL_RISK", "APPROVAL_ALWAYS"]
    assert ev.action == Action.REQUIRE_APPROVAL
    assert ev.reasons[-1].risk_score == 0.9


def test_constraint_violations_combine_with_deny_overrides(engine):
    ev = engine.evaluate_call(make_call("transfer_funds", to_iban="SA0380000000608010167519", amount_sar=20000))
    assert codes(ev.reasons) == ["TOOL_RISK", "CONSTRAINT_VIOLATION", "APPROVAL_ALWAYS"]
    assert ev.action == Action.DENY  # deny beats require_approval


def test_external_recipient_needs_approval_by_constraint(engine):
    ev = engine.evaluate_call(make_call("send_email", to="attacker@evil.example", body="data"))
    assert ev.action == Action.REQUIRE_APPROVAL
    assert ev.sink == SinkKind.EXTERNAL
    violation = next(r for r in ev.reasons if r.code == "CONSTRAINT_VIOLATION")
    assert violation.evidence["actual"] == "evil.example"


def test_evaluation_is_json_serialisable_for_audit(engine):
    ev = engine.evaluate_call(make_call("send_email", to="x@evil.example"))
    data = json.loads(ev.model_dump_json())
    assert set(data) == {"reasons", "profile", "sink", "rate_counts"}


# --------------------------------------------------------------------------- rate limiting


def test_rate_limit_window_on_export_customers(engine):
    call = make_call("export_customers", count=10)
    results = [engine.evaluate_call(call, now=t) for t in (0, 1, 2, 3)]
    # on_risk escalation of this high-risk tool is the gateway's job (approval_required), not evaluate_call's
    assert [r.action for r in results[:3]] == [Action.ALLOW] * 3
    assert all("RATE_LIMIT" not in codes(r.reasons) for r in results[:3])
    limited = results[3]
    reason = next(r for r in limited.reasons if r.code == "RATE_LIMIT")
    assert reason.layer == "ratelimit" and reason.action == Action.DENY
    assert reason.evidence["count"] == 4 and reason.evidence["max_calls"] == 3
    key = engine.rate_key(call, engine.document.agents[0].tools["export_customers"].rate_limit)
    assert limited.rate_counts == {key: 4}
    assert "RATE_LIMIT" not in codes(engine.evaluate_call(call, now=3 + 3600).reasons)  # window has slid


def test_replay_uses_recorded_counts_and_never_touches_the_limiter(engine):
    call = make_call("export_customers", count=10)
    live = [engine.evaluate_call(call, now=t) for t in range(4)]
    before = engine.rate_limiter.peek(next(iter(live[-1].rate_counts)), 3600, 10)

    replayed = [engine.evaluate_call(call, now=99999, rate_counts=ev.rate_counts) for ev in live]
    assert [codes(r.reasons) for r in replayed] == [codes(r.reasons) for r in live]
    assert [r.rate_counts for r in replayed] == [r.rate_counts for r in live]
    assert engine.rate_limiter.peek(next(iter(live[-1].rate_counts)), 3600, 10) == before == 4


def test_replay_with_missing_counter_assumes_a_single_call(engine):
    ev = engine.evaluate_call(make_call("export_customers", count=1), rate_counts={})
    assert "RATE_LIMIT" not in codes(ev.reasons)
    assert list(ev.rate_counts.values()) == [1]
    assert len(engine.rate_limiter) == 0


def test_rate_limit_scope_agent_spans_sessions_and_scope_session_does_not(build):
    engine = build("""\
        - id: a
          tools:
            per_agent:   {allow: true, rate_limit: {max_calls: 1, per_seconds: 60}}
            per_session: {allow: true, rate_limit: {max_calls: 1, per_seconds: 60, scope: session}}
        """)
    first = engine.evaluate_call(make_call("per_agent", agent="a", session="s1"), now=0)
    second = engine.evaluate_call(make_call("per_agent", agent="a", session="s2"), now=1)
    assert "RATE_LIMIT" not in codes(first.reasons) and "RATE_LIMIT" in codes(second.reasons)
    s1 = engine.evaluate_call(make_call("per_session", agent="a", session="s1"), now=0)
    s2 = engine.evaluate_call(make_call("per_session", agent="a", session="s2"), now=1)
    assert "RATE_LIMIT" not in codes(s1.reasons) + codes(s2.reasons)
    assert list(s1.rate_counts) != list(s2.rate_counts)


def test_rate_keys_cannot_collide_between_agents_and_tools():
    a = PolicyEngine.rate_key(make_call("b;tool=c", agent="a"), _limit())
    b = PolicyEngine.rate_key(make_call("c", agent="a;tool=b"), _limit())
    assert a != b
    assert a == "rl:agent=a;tool=b%3Btool%3Dc"


def _limit():
    from mirsad.policy.schema import RateLimit

    return RateLimit(max_calls=1, per_seconds=1)


def test_concurrent_evaluations_respect_the_limit(engine):
    results: list[bool] = []
    lock = threading.Lock()

    def worker() -> None:
        for _ in range(10):
            ev = engine.evaluate_call(make_call("export_customers", count=1), now=5.0)
            with lock:
                results.append("RATE_LIMIT" in codes(ev.reasons))

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count(False) == 3 and len(results) == 80


def test_denied_tools_do_not_consume_rate_limit(engine):
    engine.evaluate_call(make_call("not_a_tool"), now=0)
    engine.evaluate_call(make_call("send_email", agent="ghost"), now=0)
    assert len(engine.rate_limiter) == 0


# --------------------------------------------------------------------------- global rules


def test_default_bulk_export_rule(engine):
    many = ", ".join(f"c{i}@najd-trading.example" for i in range(51))
    ev = engine.evaluate_call(make_call("send_email", to="sara@najd-trading.example", body=many))
    rule = next(r for r in ev.reasons if r.code == "RULE_MATCH")
    assert rule.rule_id == "no-bulk-export-to-email" and rule.action == Action.DENY
    assert rule.evidence["matched"]["arg_matches"] == {"body": "(?s)\\A(?:[^@]*@){51}"}
    few = ", ".join(f"c{i}@najd-trading.example" for i in range(50))
    assert "RULE_MATCH" not in codes(engine.evaluate_call(make_call("send_email", body=few)).reasons)


def test_default_rule_regex_is_linear_on_adversarial_bodies(engine):
    started = time.perf_counter()
    for body in ("x@ " * 50, "@" * 20_000, "a@b " * 12_000):
        engine.evaluate_call(make_call("send_email", to="sara@najd-trading.example", body=body))
    assert time.perf_counter() - started < 1.0


RULES = """\
- id: tainted-external
  when: {sink: external, session_tainted: true}
  action: require_approval
- id: high-risk
  description: High risk tools are logged.
  when: {min_risk: high}
  action: allow
- id: crm-for-b
  when: {tool: 'crm_*', agent: [b]}
  action: deny
  message: CRM is off limits.
  message_ar: نظام إدارة العملاء غير متاح.
  risk_score: 0.9
- id: secret-in-args
  when: {arg_matches: {note: "(?i)password"}}
  action: deny
"""

RULE_AGENTS = """\
- id: a
  tools:
    send: {allow: true, sink: external}
    big:  {allow: true, risk: high}
    crm_x: {allow: true}
    note: {allow: true}
- id: b
  tools:
    crm_x: {allow: true}
"""


def test_rule_session_tainted_and_sink_conditions(build):
    engine = build(RULE_AGENTS, rules_yaml=RULES)
    assert "RULE_MATCH" not in codes(engine.evaluate_call(make_call("send", agent="a")).reasons)
    ev = engine.evaluate_call(make_call("send", agent="a"), session_tainted=True)
    rule = next(r for r in ev.reasons if r.code == "RULE_MATCH")
    assert rule.rule_id == "tainted-external" and rule.action == Action.REQUIRE_APPROVAL
    assert rule.evidence["matched"] == {"sink": "external", "session_tainted": True}


def test_rule_min_risk_and_allow_action_is_informational(build):
    engine = build(RULE_AGENTS, rules_yaml=RULES)
    ev = engine.evaluate_call(make_call("big", agent="a"))
    rule = next(r for r in ev.reasons if r.code == "RULE_MATCH")
    assert rule.action == Action.ALLOW and rule.risk_score == 0.0
    assert rule.message == "Policy rule 'high-risk' matched: High risk tools are logged."
    assert ev.action == Action.ALLOW
    assert "RULE_MATCH" not in codes(engine.evaluate_call(make_call("note", agent="a")).reasons)


def test_rule_tool_glob_agent_and_custom_messages(build):
    engine = build(RULE_AGENTS, rules_yaml=RULES)
    assert engine.evaluate_call(make_call("crm_x", agent="a")).action == Action.ALLOW
    ev = engine.evaluate_call(make_call("crm_x", agent="b"))
    rule = next(r for r in ev.reasons if r.code == "RULE_MATCH")
    assert (rule.message, rule.message_ar, rule.risk_score) == (
        "CRM is off limits.", "نظام إدارة العملاء غير متاح.", 0.9)
    assert ev.action == Action.DENY


def test_rule_arg_matches_lists_missing_args_and_overlong_values(build):
    engine = build(RULE_AGENTS, rules_yaml=RULES)

    def fired(**args: object) -> bool:
        return "RULE_MATCH" in codes(engine.evaluate_call(make_call("note", agent="a", **args)).reasons)

    assert fired(note="my PASSWORD is x")
    assert fired(note=["fine", "password=1"])
    assert not fired(note="fine")
    assert not fired(other="password")
    assert fired(note="x" * 60_000)  # cannot be checked within the regex input bound: fail closed


# --------------------------------------------------------------------------- approval semantics


@pytest.mark.parametrize(("approval", "risk", "score", "taint", "expected"), [
    ("never", Risk.CRITICAL, 0.95, True, False),
    ("always", Risk.LOW, 0.0, False, True),
    ("on_risk", Risk.MEDIUM, 0.59, False, False),
    ("on_risk", Risk.MEDIUM, 0.6, False, True),
    ("on_risk", Risk.MEDIUM, 0.3, True, False),
    ("on_risk", Risk.HIGH, 0.3, True, True),
    ("on_risk", Risk.CRITICAL, 0.1, True, True),
])
def test_approval_required(engine, approval, risk, score, taint, expected):
    profile = ToolProfile(tool="t", allowed=True, risk=risk, approval=approval)
    assert engine.approval_required(profile, score, taint) is expected


# --------------------------------------------------------------------------- settings accessors


def test_detector_settings_merge_global_agent_and_tool(build):
    engine = build("""\
        - id: a
          detector: {block_threshold: 0.9, on_detect: block}
          tools:
            t: {allow: true, detector: {flag_threshold: 0.2}}
            "web_*": {allow: true, detector: {spotlight: false}}
            u: {allow: true}
        """)
    assert engine.detector_settings("a", "t").model_dump() == {
        "flag_threshold": 0.2, "block_threshold": 0.9, "on_detect": "block", "spotlight": True}
    assert engine.detector_settings("a", "web_fetch").spotlight is False
    assert engine.detector_settings("a", "u").flag_threshold == 0.5
    assert engine.detector_settings("ghost", "t").on_detect == "sanitize"
    assert engine.detector_settings("a", "unknown").block_threshold == 0.9


def test_taint_settings_global_and_agent_override(build, engine):
    assert engine.taint_settings(AGENT).untrusted_controls_destination == Action.DENY
    custom = build("""\
        - id: a
          taint: {untrusted_to_external_sink: deny, trusted_fields: [id]}
        - id: b
        """)
    assert custom.taint_settings("a").untrusted_to_external_sink == Action.DENY
    assert custom.taint_settings("a").trusted_fields == ["id"]
    assert custom.taint_settings("a").destination_params == custom.taint_settings("b").destination_params
    assert custom.taint_settings("b").untrusted_to_external_sink == Action.REQUIRE_APPROVAL
    assert custom.taint_settings("ghost") == custom.document.taint


def test_simple_accessors(engine):
    assert engine.agent_ids() == [AGENT]
    assert engine.agent_names() == {AGENT: "Email & CRM Assistant"}
    assert engine.internal_domains() == ["najd-trading.example"]
    assert engine.approval_timeout_s == 120


# --------------------------------------------------------------------------- monitor mode


def test_monitor_mode_engine_still_reports_would_be_decisions(engine):
    monitor = PolicyEngine.from_file(POLICY_DIR / "monitor.yaml", rate_limiter=RateLimiter())
    assert engine.mode == "enforce" and monitor.mode == "monitor"
    call = make_call("transfer_funds", to_iban="SA0380000000608010167519", amount_sar=50000)
    enforced, shadow = engine.evaluate_call(call), monitor.evaluate_call(call)
    assert shadow.action == Action.DENY
    assert [r.model_dump() for r in shadow.reasons] == [r.model_dump() for r in enforced.reasons]
    assert monitor.version != engine.version


# --------------------------------------------------------------------------- version & construction


def test_version_is_sha256_of_canonical_json(engine):
    import hashlib

    assert len(engine.version) == 64
    assert engine.version == hashlib.sha256(canonical_json(engine.document).encode()).hexdigest()


def test_version_is_stable_across_formatting_comments_and_key_order():
    a = PolicyEngine.from_yaml(policy_text("- {id: a, tools: {t: {allow: true, risk: high}}}\n"))
    b = PolicyEngine.from_yaml(
        "# comment\nagents:\n- tools:\n    t:\n      risk: high   # note\n      allow: true\n  id: a\n"
        "organization:\n  internal_domains: [Najd-Trading.Example]\n  name: Test Org\nversion: 1\n")
    assert a.version == b.version
    assert a.yaml_text != b.yaml_text


def test_version_changes_with_semantics():
    a = PolicyEngine.from_yaml(policy_text("- {id: a, tools: {t: {allow: true}}}\n"))
    b = PolicyEngine.from_yaml(policy_text("- {id: a, tools: {t: {allow: false}}}\n"))
    assert a.version != b.version


def test_engine_built_from_document_matches_yaml_engine(default_text):
    from_yaml = PolicyEngine.from_yaml(default_text)
    from_doc = PolicyEngine(load_policy(default_text))
    assert from_doc.version == from_yaml.version
    assert from_yaml.yaml_text == default_text
    assert PolicyEngine.from_yaml(from_doc.yaml_text).version == from_yaml.version


def test_from_file_errors_are_policy_errors(tmp_path):
    with pytest.raises(PolicyError, match="cannot read policy file"):
        PolicyEngine.from_file(tmp_path / "missing.yaml")
    bad = tmp_path / "bad.yaml"
    bad.write_text("version: 2\nagents: []\n", encoding="utf-8")
    with pytest.raises(PolicyError, match="version"):
        PolicyEngine.from_file(bad)


def test_engine_uses_given_rate_limiter_even_when_empty():
    limiter = RateLimiter()
    engine = PolicyEngine.from_file(POLICY_DIR / "default.yaml", rate_limiter=limiter)
    assert engine.rate_limiter is limiter
