"""Metric math on synthetic episode records."""

from __future__ import annotations

import pytest
from bench.metrics import asr_reduction, attack_success_rate, percentile, summarize, summarize_episodes


def call(**kw):
    base = {"executed": True, "final_action": "allow", "pre_human_action": "allow", "escalated": False,
            "inspection_action": "pass", "gateway_ms": 2.0, "decision_ms": 1.0, "reason_codes": []}
    base.update(kw)
    return base


def episode(task_id, calls, *, utility=True, lang="en", variety="en", expect_approval=False, **kw):
    e = {"kind": "benign", "agent": "scripted", "defense": "full", "approver": "oracle", "task_id": task_id,
         "lang": lang, "variety": variety, "category": "email_read", "expect_approval": expect_approval,
         "utility": utility, "calls": calls, "error": None}
    e.update(kw)
    return e


def test_percentile_linear_interpolation():
    assert percentile([], 50) is None
    assert percentile([5], 95) == 5
    assert percentile([1, 2, 3, 4], 50) == pytest.approx(2.5)
    assert percentile(range(1, 101), 95) == pytest.approx(95.05)
    with pytest.raises(ValueError):
        percentile([1], 101)


def test_fpr_friction_and_utility():
    eps = [
        episode("a", [call(), call(pre_human_action="deny", final_action="deny", executed=False,
                                   reason_codes=["TAINT_UNTRUSTED_DESTINATION"])], utility=False),
        episode("b", [call(escalated=True, pre_human_action="require_approval", approval_status="approved",
                           reason_codes=["CONSTRAINT_VIOLATION", "APPROVED_BY_HUMAN"])]),
        episode("c", [call(escalated=True, pre_human_action="require_approval", final_action="deny",
                           executed=False)], utility=False, expect_approval=True),
        episode("d", [call(inspection_action="sanitize"), call(inspection_action="flag")]),
    ]
    m = summarize_episodes(eps)
    assert m["calls"] == 6 and m["episodes"] == 4
    assert m["fpr"] == pytest.approx(1 / 6, abs=1e-4)
    assert m["friction"] == pytest.approx(2 / 6, abs=1e-4)
    assert m["unexpected_friction"] == pytest.approx(1 / 5, abs=1e-4)
    assert m["final_block_rate"] == pytest.approx(2 / 6, abs=1e-4)
    assert m["utility"] == 0.5
    assert m["utility_no_approval_tasks"] == pytest.approx(2 / 3, abs=1e-4)
    assert m["result_fp_rate"] == pytest.approx(1 / 6, abs=1e-4)
    assert m["result_flag_rate"] == pytest.approx(1 / 6, abs=1e-4)
    assert m["approval_recall"] == 1.0
    assert m["episodes_with_auto_deny"] == 0.25
    assert m["blocking_reasons"] == {"CONSTRAINT_VIOLATION": 1, "TAINT_UNTRUSTED_DESTINATION": 1}
    assert m["latency_ms"]["gateway_p50"] == 2.0 and m["latency_ms"]["samples"] == 6


def test_ungated_calls_have_no_latency_samples():
    m = summarize_episodes([episode("a", [call(final_action=None, pre_human_action=None,
                                               inspection_action=None)], defense="none")])
    assert m["latency_ms"]["samples"] == 0 and m["latency_ms"]["gateway_p50"] is None
    assert m["fpr"] == 0.0 and m["results_inspected"] == 0 and m["result_fp_rate"] is None


def test_summarize_groups_and_language_breakdown():
    eps = [episode("a", [call()]), episode("b", [call(escalated=True)], lang="ar", variety="gulf"),
           episode("c", [call()], defense="none", approver="none")]
    s = summarize(eps)
    assert [(c["defense"], c["approver"]) for c in s["configs"]] == [("full", "oracle"), ("none", "none")]
    full = s["configs"][0]
    assert set(full["by_lang"]) == {"en", "ar"} and full["by_lang"]["ar"]["friction"] == 1.0
    assert full["by_variety"]["gulf"]["episodes"] == 1
    assert full["asr"] is None and s["attack_episodes"] == 0


def test_attack_success_rate_math():
    assert attack_success_rate([episode("a", [])]) is None
    attacks = [{"kind": "attack", "attack_success": ok} for ok in (True, False, False, False)]
    assert attack_success_rate(attacks) == 0.25
    assert asr_reduction(0.05, 0.5) == pytest.approx(0.9)
    assert asr_reduction(None, 0.5) is None and asr_reduction(0.1, 0.0) is None
