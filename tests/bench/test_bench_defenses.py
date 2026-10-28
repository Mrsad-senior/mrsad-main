"""Defense configurations, policy ablations and approver modes."""

from __future__ import annotations

import pytest
import yaml
from bench.defenses import (
    DEFAULT_POLICY_PATH,
    DEFENSES,
    Approver,
    DefenseRuntime,
    NullDetector,
    policy_yaml_for,
)
from bench.loader import ToolStep

from mirsad.policy import PolicyEngine

BASE = DEFAULT_POLICY_PATH.read_text(encoding="utf-8")


def _tools(doc):
    return doc["agents"][0]["tools"]


def test_every_ablation_is_a_valid_policy():
    for defense in DEFENSES[1:]:
        engine = PolicyEngine.from_yaml(policy_yaml_for(defense, BASE))
        assert engine.agent_ids() == ["email-crm-assistant"]
    with pytest.raises(ValueError):
        policy_yaml_for("none", BASE)
    with pytest.raises(ValueError):
        policy_yaml_for("everything", BASE)


def test_ablation_transforms():
    full = yaml.safe_load(policy_yaml_for("full", BASE))
    pol = yaml.safe_load(policy_yaml_for("policy_only", BASE))
    taint = yaml.safe_load(policy_yaml_for("taint_only", BASE))
    det = yaml.safe_load(policy_yaml_for("detector_only", BASE))
    assert full["taint"]["enabled"] is True and full["rules"]
    assert pol["taint"]["enabled"] is False and pol["detector"]["spotlight"] is False
    assert _tools(pol)["send_email"]["constraints"] == _tools(full)["send_email"]["constraints"]
    assert taint["taint"]["enabled"] is True and taint["rules"] == []
    assert "constraints" not in _tools(taint)["send_email"] and _tools(taint)["delete_customer"]["approval"] == "never"
    assert _tools(taint)["fetch_url"]["trust"] == "untrusted"  # profiles kept so taint rules can fire
    assert det["taint"]["enabled"] is False and det["detector"]["spotlight"] is True
    assert "rate_limit" not in _tools(det)["export_customers"]


def test_runtime_construction(tmp_path):
    none = DefenseRuntime("none", "deny", workdir=tmp_path)
    assert not none.protected
    with pytest.raises(RuntimeError):
        none.gateway()
    pol = DefenseRuntime("policy_only", "oracle", workdir=tmp_path)
    assert isinstance(pol.detector, NullDetector)
    gw1, gw2 = pol.gateway(), pol.gateway()
    assert gw1.policy is not gw2.policy and gw1.taint is not gw2.taint  # fresh limiter + taint per episode
    assert pol.verify_audit()["ok"] is True
    full = DefenseRuntime("full", "deny", workdir=tmp_path, detector=NullDetector())
    assert full.gateway().policy.version == PolicyEngine.from_yaml(BASE).version
    with pytest.raises(ValueError):
        DefenseRuntime("bogus", "deny", workdir=tmp_path)
    with pytest.raises(ValueError):
        DefenseRuntime("full", "maybe", workdir=tmp_path)


def test_null_detector_is_benign():
    d = NullDetector()
    assert d.scan("SAMPLE-FLAGGED-TEXT").score == 0.0
    assert d.scan_structured({"a": ["b"]}).label == "benign"


def test_approver_modes():
    plan = [ToolStep(tool="delete_customer", args={"customer_id": "C902"})]

    class Rec:
        def __init__(self, tool, arguments):
            self.tool, self.arguments = tool, arguments

    oracle = Approver("oracle")
    oracle.begin(plan)
    assert oracle.decide(Rec("delete_customer", {"customer_id": "C902"})) is True
    assert oracle.decide(Rec("delete_customer", {"customer_id": "C001"})) is False
    assert (oracle.requested, oracle.approved, oracle.denied) == (2, 1, 1)
    assert Approver("approve").decide(Rec("delete_customer", {"customer_id": "C001"})) is True
    assert Approver("deny").decide(Rec("delete_customer", {"customer_id": "C902"})) is False
