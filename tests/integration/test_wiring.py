"""Regression tests for cross-module wiring found during integration review."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = (ROOT / "configs" / "policies" / "default.yaml").read_text(encoding="utf-8")


async def test_taint_tracker_follows_the_active_policy_internal_domains(api_factory):
    async with api_factory(policy=DEFAULT_POLICY) as api:
        taint = api.comps.taint
        assert "najd-trading.example" in taint.internal_domains
        changed = DEFAULT_POLICY.replace("internal_domains: [najd-trading.example]",
                                         "internal_domains: [najd-trading.example, branch.example]")
        r = await api.client.put("/api/policies", headers=api.admin(), json={"yaml_text": changed})
        assert r.status_code == 200, r.text
        assert "branch.example" in taint.internal_domains


async def test_approval_summaries_use_the_policy_organisation_name(api_factory):
    async with api_factory(policy=DEFAULT_POLICY) as api:
        assert api.comps.approvals.org_name == "Najd Trading Co."


@pytest.mark.parametrize("downgraded", [True, False])
async def test_taint_reasons_downgraded_to_allow_do_not_force_approval(api_factory, downgraded):
    policy = DEFAULT_POLICY
    if downgraded:
        policy = policy.replace("untrusted_to_external_sink: require_approval", "untrusted_to_external_sink: allow")
    async with api_factory(policy=policy) as api:
        agent = api.agent("wiring-agent", policy_agent="email-crm-assistant")
        api.register_tool("fetch_url", lambda url: {"url": url, "body": "Supplier price list"},
                          {"type": "object", "properties": {"url": {"type": "string"}}})
        api.register_tool("list_documents", lambda: [{"doc_id": "D1", "title": "Policy"}])
        read = await api.client.post("/v1/tools/fetch_url/invoke", headers=agent,
                                     json={"session_id": "w1", "arguments": {"url": "https://supplier.example/prices"}})
        assert read.status_code == 200
        # fetch_url is an external sink; after untrusted content was read the taint rule fires.
        r = await api.client.post("/v1/guard/tool-call", headers=agent,
                                  json={"session_id": "w1", "tool": "fetch_url",
                                        "arguments": {"url": "https://other-vendor.example/terms"}, "wait": False})
        action = r.json()["action"]
        assert action == ("allow" if downgraded else "require_approval"), r.json()
