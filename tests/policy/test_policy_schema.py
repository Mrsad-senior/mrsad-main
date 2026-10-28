"""Policy YAML schema: strictness, readable errors and line numbers."""

from __future__ import annotations

import pytest
from policy_helpers import POLICY_DIR, policy_text
from pydantic import ValidationError

from mirsad.models import Action, Risk
from mirsad.policy import PolicyDocument, PolicyError, load_policy, validate_policy
from mirsad.policy.schema import Constraint, ToolPolicy


def only_error(text: str) -> str:
    errors = validate_policy(text)
    assert len(errors) == 1, errors
    return errors[0]


# --------------------------------------------------------------------------- shipped policies


@pytest.mark.parametrize("path", sorted(POLICY_DIR.glob("*.yaml")), ids=lambda p: p.name)
def test_every_shipped_policy_validates(path):
    text = path.read_text(encoding="utf-8")
    assert validate_policy(text) == []
    doc = load_policy(text)
    assert doc.agents, "a shipped policy must define at least one agent"


def test_shipped_policy_set_is_complete():
    names = {p.name for p in POLICY_DIR.glob("*.yaml")}
    assert {"default.yaml", "strict-banking.yaml", "monitor.yaml"} <= names


def test_default_policy_keeps_spec_agent_and_tool_names():
    doc = load_policy((POLICY_DIR / "default.yaml").read_text(encoding="utf-8"))
    assert [a.id for a in doc.agents] == ["email-crm-assistant"]
    expected = {"list_emails", "read_email", "send_email", "search_customers", "get_customer",
                "export_customers", "update_customer_note", "delete_customer", "fetch_url",
                "list_documents", "read_document", "transfer_funds", "*"}
    assert set(doc.agents[0].tools) == expected
    assert doc.mode == "enforce"


def test_monitor_policy_is_default_with_monitor_mode():
    default = load_policy((POLICY_DIR / "default.yaml").read_text(encoding="utf-8"))
    monitor = load_policy((POLICY_DIR / "monitor.yaml").read_text(encoding="utf-8"))
    assert monitor.mode == "monitor"
    assert monitor.model_copy(update={"mode": "enforce"}) == default


def test_mode_defaults_to_enforce_and_rejects_unknown_values():
    assert load_policy(policy_text("[]")).mode == "enforce"
    err = only_error("version: 1\nmode: shadow\nagents: []\n")
    assert err.startswith("line 2, column 7: mode: invalid value 'shadow'")


# --------------------------------------------------------------------------- strictness & messages


def test_unknown_key_reports_line_and_suggestion():
    text = policy_text("""\
        - id: a
          tools:
            send_email: {allow: true, risk: low, sinkk: external}
        """)
    err = only_error(text)
    assert err.startswith("line 8, column 44: agents[0].tools.send_email.sinkk: unknown key 'sinkk'")
    assert "did you mean 'sink'?" in err


def test_unknown_constraint_operator_is_named_as_operator():
    text = policy_text("""\
        - id: a
          tools:
            send_email:
              allow: true
              constraints:
                to: {domian_in: [najd-trading.example]}
        """)
    err = only_error(text)
    assert "line 11, column 16" in err
    assert "unknown constraint operator 'domian_in' (did you mean 'domain_in'?)" in err


@pytest.mark.parametrize(
    ("field", "bad", "hint"),
    [("risk", "hihg", "high"), ("trust", "untrustd", "untrusted"), ("sensitivity", "secret", None),
     ("sink", "externl", "external"), ("approval", "allways", "always")],
)
def test_bad_enum_values_are_reported(field, bad, hint):
    text = policy_text(f"""\
        - id: a
          tools:
            t: {{allow: true, {field}: {bad}}}
        """)
    err = only_error(text)
    assert f"agents[0].tools.t.{field}: invalid value '{bad}'" in err
    assert err.startswith("line 8")
    if hint:
        assert f"did you mean '{hint}'?" in err


def test_invalid_regex_reports_position():
    text = policy_text("""\
        - id: a
          tools:
            t:
              allow: true
              constraints:
                q: {pattern: "([a-z"}
        """)
    err = only_error(text)
    assert err.startswith("line 11, column 24: agents[0].tools.t.constraints.q.pattern")
    assert "invalid regular expression '([a-z'" in err


@pytest.mark.parametrize("pattern", ["(a+)+$", "(.*@.*){51,}", "(\\\\w+\\\\s?)+$", "(x+x+)+y"])
def test_redos_prone_regex_is_rejected(pattern):
    text = policy_text(f"""\
        - id: a
          tools:
            t:
              allow: true
              constraints:
                q: {{not_pattern: "{pattern}"}}
        """)
    err = only_error(text)
    assert "catastrophic backtracking" in err


def test_rule_regex_is_validated_with_its_path():
    text = policy_text("- id: a\n", rules_yaml="""\
        - id: r1
          when: {arg_matches: {body: "(a*)*"}}
          action: deny
        """)
    err = only_error(text)
    assert err.startswith("line 9, column 32: rules[0].when.arg_matches.body")


def test_duplicate_yaml_keys_are_errors():
    text = policy_text("""\
        - id: a
          tools:
            send_email: {allow: false}
            send_email: {allow: true}
        """)
    err = only_error(text)
    assert err == ("line 9, column 7: duplicate key 'send_email' (first defined at line 8); "
                   "YAML would silently keep only the last value")


def test_duplicate_agent_ids_point_at_second_definition():
    text = policy_text("- id: a\n- id: b\n- id: a\n")
    err = only_error(text)
    assert err == "line 8, column 5: agents[2].id: duplicate agent id 'a' (already defined at agents[0])"


def test_duplicate_rule_ids():
    text = policy_text("- id: a\n", rules_yaml="""\
        - {id: r, when: {tool: x}, action: deny}
        - {id: r, when: {tool: y}, action: deny}
        """)
    assert "duplicate rule id 'r'" in only_error(text)


def test_conflicting_globs_of_equal_length_are_rejected():
    text = policy_text("""\
        - id: a
          tools:
            "crm_*": {allow: true}
            "*_crm": {allow: false}
        """)
    err = only_error(text)
    assert "glob '*_crm' conflicts with glob 'crm_*'" in err
    assert err.startswith("line 9")


@pytest.mark.parametrize("tools", [
    '"crm_*": {allow: true}\n    "erp_*": {allow: true}',           # same length, disjoint
    '"crm_*": {allow: true}\n    "crm_get_*": {allow: false}',      # different length: longer wins
    '"crm_*": {allow: true}\n    "*": {allow: false}',              # catch-all is always last
])
def test_non_conflicting_globs_are_accepted(tools):
    text = policy_text(f"- id: a\n  tools:\n    {tools}\n")
    assert validate_policy(text) == []


def test_rule_referring_to_unknown_agent():
    text = policy_text("- id: a\n", rules_yaml="- {id: r, when: {agent: ghost}, action: deny}\n")
    assert "rule refers to unknown agent 'ghost' (known agents: a)" in only_error(text)


def test_rule_agent_globs_are_not_checked_against_known_agents():
    text = policy_text("- id: a\n", rules_yaml="- {id: r, when: {agent: 'team-*'}, action: deny}\n")
    assert validate_policy(text) == []


def test_dynamic_sink_requires_sink_params():
    text = policy_text("- id: a\n  tools:\n    t: {allow: true, sink: dynamic}\n")
    assert "sink: dynamic needs sink_params" in only_error(text)


def test_sink_params_require_dynamic_sink():
    text = policy_text("- id: a\n  tools:\n    t: {allow: true, sink: external, sink_params: [to]}\n")
    assert "sink_params is only used with sink: dynamic" in only_error(text)


@pytest.mark.parametrize(("constraint", "message"), [
    ("{min: 5, max: 1}", "min (5) is greater than max (1)"),
    ("{min_length: 9, max_length: 2}", "min_length (9) is greater than max_length (2)"),
    ("{on_violation: deny}", "constraint has no operators"),
    ("{enum: [a], in: [b]}", "'enum' and 'in' are synonyms"),
    ("{enum: []}", "'enum' must not be an empty list"),
    ("{max: true}", "expected a number, got a boolean"),
    ("{domain_in: ['@najd-trading.example']}", "is not a bare domain"),
    ("{domain_in: ['https://najd-trading.example']}", "is not a bare domain"),
    ("{max_items: -1}", "greater than or equal to 0"),
    ("{type: str}", "invalid value 'str'"),
    ("{max: .nan}", "finite number"),
    ("{enum: [a, {b: c}]}", "list values must be strings, numbers or booleans, got a mapping"),
    ("{not_in: [1, .inf]}", "list values must be finite numbers"),
    ("{on_violation: allow, max: 1}", "invalid value 'allow'"),
])
def test_constraint_level_errors(constraint, message):
    text = policy_text(f"- id: a\n  tools:\n    t:\n      allow: true\n      constraints:\n        x: {constraint}\n")
    assert message in only_error(text)


def test_detector_thresholds_must_be_ordered_after_merging():
    text = policy_text("""\
        - id: a
          detector: {flag_threshold: 0.7}
          tools:
            t: {allow: true, detector: {block_threshold: 0.6}}
        """)
    errors = validate_policy(text)
    assert len(errors) == 1
    assert errors[0].startswith("line 9")
    assert "flag_threshold (0.7) must not be greater than block_threshold (0.6)" in errors[0]


def test_global_detector_thresholds_out_of_range():
    text = policy_text("- id: a\n", extra="detector: {flag_threshold: 1.5}\n")
    assert "detector.flag_threshold" in only_error(text)


def test_missing_required_keys():
    errors = validate_policy("organization: {name: x}\n")
    assert any("version: missing required key 'version'" in e for e in errors)
    assert any("agents: missing required key 'agents'" in e for e in errors)


def test_unquoted_boolean_tool_key_gets_a_hint():
    err = only_error(policy_text("- id: a\n  tools:\n    on: {allow: true}\n"))
    assert err.startswith("line 8, column 7: agents[0].tools[true]")
    assert "put the value in quotes" in err


def test_null_tool_entry_explains_expected_mapping():
    err = only_error(policy_text("- id: a\n  tools:\n    t:\n"))
    assert "expected a mapping (for example {allow: true}), got null" in err


def test_invalid_agent_id():
    err = only_error(policy_text("- id: 'bad id!'\n"))
    assert "is not a valid id" in err


# --------------------------------------------------------------------------- YAML-level problems


def test_yaml_syntax_error_has_line_number():
    err = only_error("version: 1\nagents: [\n  - id: x\n")
    assert err.startswith("line 3, column 3: YAML syntax error")


def test_empty_and_non_mapping_documents():
    assert validate_policy("") == ["policy is empty"]
    assert validate_policy("# only a comment\n") == ["policy is empty"]
    assert "must be a YAML mapping" in only_error("- 1\n- 2\n")


def test_multiple_documents_are_rejected():
    assert "YAML syntax error" in only_error("version: 1\nagents: []\n---\nversion: 1\n")


def test_alias_bomb_is_rejected_before_construction():
    lines = ["a0: &a0 [x, x, x, x, x, x, x, x, x, x]"]
    for i in range(1, 8):
        prev = f"*a{i - 1}"
        lines.append(f"a{i}: &a{i} [{', '.join([prev] * 10)}]")
    err = only_error("\n".join(lines) + "\n")
    assert "excessive or recursive aliases" in err


def test_recursive_alias_is_rejected():
    assert "excessive or recursive aliases" in only_error("a: &a [*a]\n")


def test_oversized_policy_is_rejected():
    assert "larger than" in only_error("#" * 1_000_001)


def test_errors_are_sorted_by_line():
    text = policy_text("""\
        - id: a
          tools:
            t: {allow: true, risk: nope}
            u: {allow: true, trust: nope}
        """, extra="mode: nope\n")
    lines = [int(e.split(",")[0].removeprefix("line ")) for e in validate_policy(text)]
    assert lines == sorted(lines) and len(lines) == 3


# --------------------------------------------------------------------------- API behaviour


def test_load_policy_raises_policy_error_with_all_messages():
    text = policy_text("- id: a\n  tools:\n    t: {allow: maybe, risk: nope}\n")
    with pytest.raises(PolicyError) as info:
        load_policy(text)
    assert len(info.value.errors) == 2
    assert "invalid policy (2 error(s))" in str(info.value)


def test_direct_model_validation_still_runs_semantic_checks():
    data = {"version": 1, "agents": [{"id": "a"}, {"id": "a"}]}
    with pytest.raises(ValidationError, match="duplicate agent id 'a'"):
        PolicyDocument.model_validate(data)


def test_merge_keys_and_anchors_are_supported():
    text = policy_text("""\
        - id: a
          tools:
            read_email: &untrusted {allow: true, trust: untrusted, scan: true}
            read_document:
              <<: *untrusted
              sensitivity: confidential
        """)
    doc = load_policy(text)
    tool = doc.agents[0].tools["read_document"]
    assert tool.trust.value == "untrusted" and tool.sensitivity.value == "confidential"


def test_defaults_are_filled_in():
    doc = load_policy("version: 1\nagents: []\n")
    assert doc.defaults.decision == Action.DENY
    assert doc.defaults.approval_timeout_s == 120
    assert doc.detector.block_threshold == 0.8
    assert doc.taint.untrusted_controls_destination == Action.DENY
    assert "to_iban" in doc.taint.destination_params


def test_tool_policy_defaults_fail_closed():
    tool = ToolPolicy()
    assert tool.allow is False
    assert tool.risk == Risk.LOW and tool.approval == "on_risk"
    assert ToolPolicy(trust="untrusted").effective_scan is True
    assert ToolPolicy(trust="untrusted", scan=False).effective_scan is False


def test_constraint_in_alias_and_domain_normalisation():
    c = Constraint.model_validate({"in": ["a", "b"], "domain_in": ["*.Najd-Trading.Example."]})
    assert c.allowed_values == ["a", "b"]
    assert c.domain_in == ["najd-trading.example"]
