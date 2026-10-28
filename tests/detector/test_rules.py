"""Rule engine mechanics with stub rules on neutral placeholder text.

The packaged rule base is only checked structurally here (it loads, ids are unique, patterns compile,
benign text stays quiet); its attack ``examples`` are maintained and reviewed by the human team.
"""

from __future__ import annotations

import base64
import re

import pytest
from pydantic import ValidationError

from mirsad.detector import Rule, RuleHit, RuleSet, normalize, rule_score
from mirsad.detector.rules import BASE64_RULE_ID, QUOTE_DAMPING, SCORE_CAP, expand_macros

from .neutral_data import PLACEHOLDER

P = PLACEHOLDER


def stub(rule_id: str = "test.placeholder", *, weight: float = 0.6, pattern: str = "sample-flagged-text",
         **kw) -> Rule:
    return Rule(id=rule_id, category="goal_hijack", weight=weight, description="test stub rule",
                pattern=pattern, examples=(P,), **kw)


def hit(rule_id: str, weight: float) -> RuleHit:
    return RuleHit(rule_id=rule_id, category="goal_hijack", weight=weight, start=0, end=1, orig_start=0,
                   orig_end=1, text="x")


# --------------------------------------------------------------------------- packaged rule base (structure only)


def test_packaged_rule_base_loads_with_unique_ids(rules):
    assert len(rules) > 50
    ids = [r.id for r in rules.rules]
    assert len(ids) == len(set(ids))
    assert {r.lang for r in rules.rules} <= {"en", "ar", "arabizi", "any"}
    assert all(0.0 < r.weight < 1.0 for r in rules.rules)
    described = rules.describe()
    assert len(described) == len(rules) and set(described[0]) == {"id", "category", "weight", "lang", "description"}
    assert rules.get(ids[0]) is rules.rules[0] and rules.get("no.such.rule") is None
    assert RuleSet.default() is RuleSet.default()  # cached


def test_packaged_rule_base_is_quiet_on_neutral_text(rules):
    for text in ("Quarterly report attached.", "تقرير المبيعات الربعي مرفق.", "", "12345"):
        assert rules.match(normalize(text)) == []


# --------------------------------------------------------------------------- Rule model validation


@pytest.mark.parametrize("bad", [
    {"id": "Bad Id"},
    {"weight": 1.0},
    {"weight": 0.0},
    {"examples": ()},
    {"category": "not_a_category"},
    {"unexpected": "field"},
])
def test_rule_validation(bad):
    data = {"id": "test.ok", "category": "goal_hijack", "weight": 0.5, "description": "stub", "pattern": "x",
            "examples": ("x",)} | bad
    with pytest.raises(ValidationError):
        Rule.model_validate(data)


def test_ruleset_rejects_duplicates_and_bad_regex():
    with pytest.raises(ValueError, match="duplicate"):
        RuleSet([stub("test.a"), stub("test.a")])
    with pytest.raises(ValueError, match="invalid regex"):
        RuleSet([stub(pattern="(unclosed")])


# --------------------------------------------------------------------------- macros & YAML loading


def test_expand_macros_nested_unknown_and_cycles():
    macros = {"A": "(?:{{B}}|alpha)", "B": "beta"}
    assert expand_macros("x {{A}} y", macros) == "x (?:beta|alpha) y"
    with pytest.raises(ValueError, match="unknown macro"):
        expand_macros("{{MISSING}}", macros)
    with pytest.raises(ValueError, match="too deep"):
        expand_macros("{{L}}", {"L": "{{L}}"})


def test_from_yaml_and_from_dir(tmp_path):
    rules_yaml = (
        "rules:\n"
        "  - id: test.yaml\n"
        "    category: goal_hijack\n"
        "    weight: 0.7\n"
        "    description: stub loaded from yaml\n"
        "    pattern: '{{TOKEN}}'\n"
        "    examples: ['SAMPLE-FLAGGED-TEXT']\n"
    )
    macros_yaml = "macros:\n  TOKEN: 'sample-flagged-text'\n"
    rs = RuleSet.from_yaml([rules_yaml], macros_text=macros_yaml)
    assert [h.rule_id for h in rs.match(normalize(f"a {P} b"))] == ["test.yaml"]
    (tmp_path / "en.yaml").write_text(rules_yaml, encoding="utf-8")
    (tmp_path / "macros.yaml").write_text(macros_yaml, encoding="utf-8")
    (tmp_path / "zz-extra.yaml").write_text(rules_yaml.replace("test.yaml", "test.extra"), encoding="utf-8")
    from_dir = RuleSet.from_dir(tmp_path)
    assert [r.id for r in from_dir.rules] == ["test.yaml", "test.extra"]


def test_arabic_patterns_are_folded_at_load_time():
    rs = RuleSet([stub(pattern="فاتورة\\s+مُعلّقة")])  # pattern written with ta marbuta and diacritics
    assert rs.match(normalize("هذه فاتوره معلقه للمراجعة"))
    assert rs.match(normalize("هذه فاتورة مُعَلَّقة للمراجعة"))


# --------------------------------------------------------------------------- matching behaviour


def test_triggers_and_guard():
    # the regex only runs when one of the (normalised) trigger substrings occurs in the text
    triggered = RuleSet([stub(triggers=("Ledger",))])
    assert triggered.match(normalize(f"ledger: {P}"))
    assert not triggered.match(normalize(f"notes: {P}"))
    guarded = RuleSet([stub(pattern="ref\\s+\\w+", guard="\\d")])
    assert guarded.match(normalize("see ref 1042"))
    assert not guarded.match(normalize("see ref above"))


def test_hits_are_capped_per_rule_and_counted_once_in_score():
    rs = RuleSet([stub(weight=0.6)])
    text = " ".join([P] * 40)
    hits = rs.match(normalize(text))
    assert len(hits) == 25
    assert rule_score(hits) == pytest.approx(0.6)


def test_signals_declared_by_rules():
    rs = RuleSet([stub(signal="placeholder_seen")])
    hits = rs.match(normalize(P))
    assert rs.signals_for(hits) == ["placeholder_seen"]
    assert rs.signals_for([]) == []


def test_quoted_mentions_in_discussion_text_are_dampened():
    rs = RuleSet([stub(weight=0.8)])
    discussed = rs.match(normalize(f'For example, the phrase "{P}" is used in this guide.'))
    assert len(discussed) == 1 and discussed[0].dampened
    assert discussed[0].weight == pytest.approx(0.8 * QUOTE_DAMPING)
    plain = rs.match(normalize(f"The phrase {P} is used in this guide."))
    assert not plain[0].dampened and plain[0].weight == pytest.approx(0.8)


def test_base64_wrapped_text_is_decoded_and_matched():
    rs = RuleSet([stub(weight=0.7)])
    blob = base64.b64encode(f"Shipment note 2026 with {P} inside the archived record.".encode()).decode()
    assert re.search(r"\d", blob) and len(blob) >= 40
    hits = rs.match(normalize(f"Attachment: {blob}"))
    b64 = [h for h in hits if h.rule_id == BASE64_RULE_ID]
    assert len(b64) == 1
    assert b64[0].text == blob
    assert 0.6 <= b64[0].weight <= 0.95


# --------------------------------------------------------------------------- score arithmetic


def test_rule_score_noisy_or_over_distinct_rules():
    assert rule_score([]) == 0.0
    assert rule_score([hit("a", 0.5), hit("b", 0.5)]) == pytest.approx(0.75)
    assert rule_score([hit("a", 0.5), hit("a", 0.3)]) == pytest.approx(0.5)  # best weight per rule
    assert rule_score([hit(f"r{i}", 0.9) for i in range(10)]) == SCORE_CAP


def test_evasion_signals_amplify_only_real_hits():
    assert rule_score([], ["zero_width_chars", "homoglyphs"]) == 0.0
    one = rule_score([hit("a", 0.5)], ["zero_width_chars"])
    assert one == pytest.approx(1 - 0.5 * 0.9)
    many = rule_score([hit("a", 0.5)], ["zero_width_chars", "homoglyphs", "bidi_controls", "letter_spacing"])
    assert many == pytest.approx(1 - 0.5 * 0.9 ** 3)  # at most three evasion terms
    assert rule_score([hit("a", 0.5)], ["base64_blob"]) == pytest.approx(0.5)  # not an evasion signal
