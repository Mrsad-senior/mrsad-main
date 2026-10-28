"""ReDoS defences for administrator-written regexes."""

from __future__ import annotations

import re

import pytest

from mirsad.policy.globs import globs_overlap
from mirsad.policy.regex_guard import (
    REGEX_INPUT_LIMIT,
    bounded_search,
    compile_user_regex,
    nested_quantifier_problem,
)

DANGEROUS = [
    r"(?s)(.*@.*){51,}", r"(a+)+", r"(a*)*", r"(\w+\s?)+$", r"(x+x+)+y", r"(.*)*",
    r"(?:(?:a|b)+)+", r"(?i)(A+a)+", r"([a-z]+[0-9a-z])*!", r"(\d+)*\d", r"(?s)(.*,){20}",
    r"(?=(a+)+b)",
]
SAFE = [
    r"(?s)\A(?:[^@]*@){51}", r"^https?://", r"(?i)(localhost|127\.0\.0\.1|169\.254\.|\.internal)",
    r"^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$", r"(\d+,)*\d+", r"^(\w+\.)*\w+@", r"(?:\s*,\s*\w+)*",
    r"(?:ab+)*", r"(?s).*@evil", r"(a++)+", r"(?>a+)+", r"SA\d{22}", r"[؀-ۿ]+",
    r"(?<![0-9])(?:[0-9][ -]?){13,19}(?![0-9])",
]


@pytest.mark.parametrize("pattern", DANGEROUS)
def test_nested_ambiguous_quantifiers_are_detected(pattern):
    assert nested_quantifier_problem(pattern)
    with pytest.raises(ValueError, match="catastrophic backtracking"):
        compile_user_regex(pattern)


@pytest.mark.parametrize("pattern", SAFE)
def test_safe_patterns_are_accepted(pattern):
    assert nested_quantifier_problem(pattern) is None
    assert isinstance(compile_user_regex(pattern), re.Pattern)


def test_compile_reports_invalid_and_oversized_patterns():
    with pytest.raises(ValueError, match="unterminated character set at position 0"):
        compile_user_regex("[abc")
    with pytest.raises(ValueError, match="longer than"):
        compile_user_regex("a" * 2001)


def test_bounded_search_truncates_input():
    rx = re.compile("needle")
    hidden = "x" * REGEX_INPUT_LIMIT + "needle"
    outcome = bounded_search(rx, hidden)
    assert outcome.truncated and not outcome.matched_any
    assert bounded_search(rx, "a needle").matched_all


def test_bounded_search_matches_normalised_form():
    rx = re.compile("(?i)localhost")
    outcome = bounded_search(rx, "ｌｏｃａｌｈｏｓｔ")
    assert not outcome.matched_raw and outcome.matched_normalized and outcome.matched_any
    assert not outcome.matched_all


@pytest.mark.parametrize(("a", "b", "overlap"), [
    ("crm_*", "*_crm", True), ("crm_*", "erp_*", False), ("a?c", "ab?", True), ("a[bc]d", "a[de]d", False),
    ("a[bc]d", "a[cd]d", True), ("x*y", "x*z", False), ("*", "anything", True), ("ab", "ab", True),
])
def test_glob_overlap(a, b, overlap):
    assert globs_overlap(a, b) is overlap
    assert globs_overlap(b, a) is overlap
