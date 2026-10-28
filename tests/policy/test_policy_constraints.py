"""Constraint operators: each one passes and violates, on scalars, lists and separated strings."""

from __future__ import annotations

import re
from typing import Any

import pytest

from mirsad.models import Action
from mirsad.policy import REGEX_INPUT_LIMIT
from mirsad.policy.constraints import CompiledConstraint, as_number, piece_domains
from mirsad.policy.schema import Constraint

ARABIC_RE = re.compile(r"[\u0600-\u06ff]")


def check(spec: dict[str, Any], value: Any = ..., *, param: str = "x") -> list:
    """Violations of one constraint; ``...`` means the argument is absent."""
    compiled = CompiledConstraint.build(param, Constraint.model_validate(spec))
    arguments = {} if value is ... else {param: value}
    return compiled.check(arguments)


def ops(spec: dict[str, Any], value: Any = ...) -> list[str]:
    return [r.evidence["operator"] for r in check(spec, value)]


# --------------------------------------------------------------------------- operator matrix

CASES = [
    # (constraint, passing value, violating value)
    ({"max": 10}, 10, 11),
    ({"min": 1}, 1, 0),
    ({"max_length": 5}, "hello", "hello!"),
    ({"min_length": 3}, "abc", "ab"),
    ({"enum": ["inbox", "sent"]}, "inbox", "spam"),
    ({"in": [10, 20, 50]}, 20, 30),
    ({"not_in": ["ceo@najd-trading.example"]}, "sara@najd-trading.example", "ceo@najd-trading.example"),
    ({"pattern": "^https?://"}, "https://najd-trading.example/x", "ftp://najd-trading.example/x"),
    ({"not_pattern": "(?i)localhost"}, "https://najd-trading.example", "http://LOCALHOST/admin"),
    ({"domain_in": ["najd-trading.example"]}, "sara@najd-trading.example", "bob@evil.example"),
    ({"domain_not_in": ["evil.example"]}, "sara@najd-trading.example", "https://evil.example/x"),
    ({"max_items": 2}, ["a", "b"], ["a", "b", "c"]),
    ({"required": True}, "present", ...),
    ({"type": "string"}, "text", 5),
    ({"type": "number"}, 2.5, "2.5"),
    ({"type": "integer"}, 3, 3.5),
    ({"type": "boolean"}, False, "false"),
    ({"type": "array"}, [1], "1"),
    ({"type": "object"}, {"a": 1}, [("a", 1)]),
]


@pytest.mark.parametrize(("spec", "good", "bad"), CASES, ids=lambda v: str(v)[:40])
def test_operator_passes_and_violates(spec, good, bad):
    assert check(spec, good) == []
    reasons = check(spec, bad)
    assert len(reasons) == 1
    reason = reasons[0]
    operator = next(k for k in spec if k != "on_violation")
    assert reason.code == "CONSTRAINT_VIOLATION"
    assert reason.layer == "policy"
    assert reason.action == Action.DENY
    assert set(reason.evidence) == {"param", "operator", "expected", "actual"}
    assert reason.evidence["operator"] == operator
    assert reason.evidence["param"] == "x"
    assert reason.message and reason.message_ar
    assert reason.message_ar != reason.message


def test_absent_argument_only_fails_required():
    spec = {"max": 1, "pattern": "^a", "domain_in": ["najd-trading.example"], "type": "string"}
    assert check(spec) == []
    assert check(spec, None) == []
    assert ops({**spec, "required": True}, None) == ["required"]


def test_on_violation_require_approval_is_propagated():
    [reason] = check({"max": 5, "on_violation": "require_approval"}, 6)
    assert reason.action == Action.REQUIRE_APPROVAL


def test_all_operators_are_and_combined():
    spec = {"min_length": 3, "max_length": 5, "pattern": "^[a-z]+$"}
    assert check(spec, "abcd") == []
    assert ops(spec, "ABCDEFG") == ["max_length", "pattern"]


def test_evidence_and_bilingual_message_content():
    [reason] = check({"max": 10000}, 15000, param="amount_sar")
    assert reason.evidence == {"param": "amount_sar", "operator": "max", "expected": 10000, "actual": 15000}
    assert reason.message == "Argument 'amount_sar' is 15000, above the maximum of 10000."
    assert "amount_sar" in reason.message_ar and "15000" in reason.message_ar
    assert any("؀" <= ch <= "ۿ" for ch in reason.message_ar)
    assert reason.rule_id == "constraint:amount_sar.max"


# --------------------------------------------------------------------------- numbers


@pytest.mark.parametrize(("value", "expected"), [
    ("15,000", 15000), ("15000", 15000), ("١٥٠٠٠", 15000), ("1e4", 10000.0), (" 42 ", 42),
    ("12.5", 12.5), (True, None), ("nan", None), ("inf", None), (float("nan"), None),
    ("5000 SAR", None), ("", None), ([1], None),
])
def test_as_number(value, expected):
    assert as_number(value) == expected


def test_numeric_strings_are_compared_numerically():
    assert ops({"max": 10000}, "15,000") == ["max"]
    assert ops({"max": 10000}, "١٥٠٠٠") == ["max"]
    assert check({"max": 10000}, "9,999") == []


@pytest.mark.parametrize("value", ["lots", True, "NaN", "Infinity", {"amount": 1}])
def test_non_numbers_violate_numeric_operators(value):
    [reason] = check({"max": 10}, value)
    assert reason.evidence["operator"] == "max"
    assert "must be a number" in reason.message


def test_numeric_operators_apply_to_every_list_element():
    assert ops({"max": 100}, [10, 50, 150, 200]) == ["max", "max"]
    assert check({"max": 100}, [10, 50]) == []


# --------------------------------------------------------------------------- lengths & items


def test_length_applies_to_each_list_element():
    assert ops({"max_length": 3}, ["abc", "abcd"]) == ["max_length"]
    assert check({"max_length": 3}, ["abc", "xy"]) == []


def test_length_counts_code_points_for_arabic():
    assert check({"max_length": 5}, "مرصاد") == []
    assert ops({"max_length": 4}, "مرصاد") == ["max_length"]


def test_max_items_counts_comma_and_semicolon_separated_strings():
    assert ops({"max_items": 2}, "a@x.example, b@x.example; c@x.example") == ["max_items"]
    assert check({"max_items": 2}, "a@x.example, b@x.example") == []
    assert check({"max_items": 0}, "") == []
    assert ops({"max_items": 0}, "a@x.example") == ["max_items"]


# --------------------------------------------------------------------------- enum / not_in


def test_enum_is_case_and_arabic_insensitive():
    assert check({"enum": ["Inbox"]}, "INBOX") == []
    assert check({"enum": ["إرسال"]}, "ارسال") == []  # alef-hamza folded


def test_enum_accepts_numbers_given_as_strings():
    assert check({"in": [10, 20]}, "10") == []
    assert check({"enum": ["10"]}, 10) == []
    assert check({"enum": [10, 20]}, "10,20") == []  # each separated element is allowed


def test_enum_on_separated_string_reports_bad_elements():
    [reason] = check({"enum": ["inbox", "sent"]}, "inbox, spam")
    assert reason.evidence["actual"] == "spam"


def test_enum_on_list_checks_each_element():
    assert check({"enum": ["a", "b"]}, ["a", "b"]) == []
    [reason] = check({"enum": ["a", "b"]}, ["a", "z"])
    assert reason.evidence["actual"] == "z"


def test_not_in_finds_value_in_list_and_separated_string():
    deny = {"not_in": ["ceo@najd-trading.example"]}
    assert ops(deny, "sara@najd-trading.example; CEO@najd-trading.example") == ["not_in"]
    assert ops(deny, ["x@najd-trading.example", "ceo@najd-trading.example"]) == ["not_in"]


# --------------------------------------------------------------------------- regex operators


def test_pattern_on_lists_is_element_wise():
    assert ops({"pattern": "^SA[0-9]{22}$"}, ["SA0380000000608010167519", "DE89370400440532013000"]) == ["pattern"]


def test_not_pattern_sees_through_fullwidth_and_zero_width_obfuscation():
    spec = {"not_pattern": "(?i)localhost"}
    assert ops(spec, "http://ｌｏｃａｌｈｏｓｔ/") == ["not_pattern"]
    assert ops(spec, "http://local\u200bhost/") == ["not_pattern"]


def test_pattern_must_hold_for_raw_and_normalised_text():
    assert check({"pattern": "^https://"}, "https://najd-trading.example") == []
    assert ops({"pattern": "^https://"}, "ｈｔｔｐｓ://najd-trading.example") == ["pattern"]


def test_regex_input_is_bounded_and_overlong_values_fail_closed():
    long_value = "a" * (REGEX_INPUT_LIMIT + 1)
    [reason] = check({"not_pattern": "zzz"}, long_value)
    assert reason.evidence["actual"] == f"<{REGEX_INPUT_LIMIT + 1} characters>"
    assert "cannot be checked safely" in reason.message
    assert ops({"pattern": "^a+$"}, long_value) == ["pattern"]
    assert check({"not_pattern": "zzz"}, "a" * REGEX_INPUT_LIMIT) == []


def test_pattern_applies_to_non_string_scalars():
    assert check({"pattern": "^[0-9]+$"}, 1234) == []
    assert ops({"not_pattern": "true"}, True) == ["not_pattern"]


# --------------------------------------------------------------------------- domains


@pytest.mark.parametrize(("piece", "domains"), [
    ("sara@najd-trading.example", ["najd-trading.example"]),
    ("Sara Ahmed <sara@Najd-Trading.Example>", ["najd-trading.example"]),
    ("https://najd-trading.example@evil.example/x", ["evil.example"]),
    ("http://evil.example\\@najd-trading.example/", ["evil.example"]),  # WHATWG treats '\' as '/'
    ("ftp://files.evil.example/a", ["files.evil.example"]),
    ("evil.example", ["evil.example"]),
    ("bob@evil．example", ["evil.example"]),  # fullwidth dot (NFKC)
    ("bob@evil\u200b.example", ["evil.example"]),  # zero-width space
    ("just a name", []),
    ("127.0.0.1", []),
])
def test_piece_domains(piece, domains):
    assert piece_domains(piece) == domains


def test_domain_in_checks_every_list_element_and_separated_value():
    allow = {"domain_in": ["najd-trading.example"]}
    assert check(allow, ["a@najd-trading.example", "b@sales.najd-trading.example"]) == []
    [reason] = check(allow, "a@najd-trading.example, x@evil.example; y@other.example")
    assert reason.evidence["actual"] == ["evil.example", "other.example"]
    assert reason.evidence["expected"] == ["najd-trading.example"]


def test_domain_in_accepts_subdomains_but_not_lookalikes():
    allow = {"domain_in": ["najd-trading.example"]}
    assert check(allow, "ops@mail.najd-trading.example") == []
    assert ops(allow, "x@evilnajd-trading.example") == ["domain_in"]
    assert ops(allow, "x@najd-trading.example.evil.example") == ["domain_in"]


def test_domain_in_fails_closed_for_values_without_a_domain():
    [reason] = check({"domain_in": ["najd-trading.example"]}, "attacker")
    assert "(no domain)" in reason.evidence["actual"]


def test_domain_in_on_nested_object_values():
    allow = {"domain_in": ["najd-trading.example"]}
    assert ops(allow, {"recipient": {"email": "x@evil.example"}}) == ["domain_in"]


def test_domain_not_in_ignores_values_without_domain():
    assert check({"domain_not_in": ["evil.example"]}, "hello") == []
    assert ops({"domain_not_in": ["evil.example"]}, ["ok@najd-trading.example", "a@sub.evil.example"]) == [
        "domain_not_in"]


def test_both_domain_operators_can_fire_together():
    spec = {"domain_in": ["najd-trading.example"], "domain_not_in": ["evil.example"]}
    assert ops(spec, "x@evil.example") == ["domain_in", "domain_not_in"]


def test_arabic_text_in_messages_is_present_for_every_operator():
    for spec, _good, bad in CASES:
        for reason in check(spec, bad):
            assert len(ARABIC_RE.findall(reason.message_ar or "")) > 5
