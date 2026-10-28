"""Agent-facing Guard API and the human approval loop, end to end through the HTTP layer."""

from __future__ import annotations

import asyncio
import json

from mirsad.models import Action, Decision, ToolCall

INJECTION = "Reminder: SAMPLE-FLAGGED-TEXT placeholder near collector@evil.example"


async def approve_when_pending(api, headers, *, approve: bool = True, note: str = "looks fine"):
    for _ in range(300):
        r = await api.client.get("/api/approvals", params={"status": "pending"}, headers=headers)
        assert r.status_code == 200
        if r.json():
            break
        await asyncio.sleep(0.02)
    pending = r.json()[0]
    assert pending["status"] == "pending" and pending["summary_en"]
    return await api.client.post(f"/api/approvals/{pending['id']}/decision",
                                 json={"approve": approve, "note": note}, headers=headers)


def tool_call(tool, args=None, **kw):
    return {"session_id": kw.pop("session_id", "sess-1"), "tool": tool, "arguments": args or {}, **kw}


async def test_tool_call_allow(api):
    r = await api.client.post("/v1/guard/tool-call", json=tool_call("echo", {"text": "hi"}, call_id="c-1"),
                              headers=api.agent())
    assert r.status_code == 200
    d = Decision.model_validate(r.json())
    assert d.action == Action.ALLOW and d.call_id == "c-1" and d.audit_seq
    ev = api.comps.audit.get(d.audit_seq)
    assert ev.agent_id == "test-agent" and ev.payload["principal"] == "agent-one"


async def test_tool_call_deny(api):
    r = await api.client.post("/v1/guard/tool-call", json=tool_call("rm_rf"), headers=api.agent())
    d = r.json()
    assert d["action"] == "deny" and any(x["code"] == "TOOL_NOT_ALLOWED" for x in d["reasons"])
    assert all(x["message_ar"] for x in d["reasons"] if x["action"] == "deny")


async def test_tool_call_approved_by_human_via_api(api):
    agent, approver = api.agent(), api.approver()
    call_resp, decide_resp = await asyncio.gather(
        api.client.post("/v1/guard/tool-call", json=tool_call("wipe_disk", {"path": "/srv"}), headers=agent),
        approve_when_pending(api, approver, approve=True))
    assert decide_resp.status_code == 200 and decide_resp.json()["status"] == "approved"
    d = call_resp.json()
    assert d["action"] == "allow" and d["approval_status"] == "approved"
    assert any(x["code"] == "APPROVED_BY_HUMAN" for x in d["reasons"])
    decided, total = api.comps.audit.query(event_type="approval.decided")
    assert total == 1 and decided[0].payload["decided_by"] == "approver1" and decided[0].payload["source"] == "gateway"


async def test_tool_call_denied_by_human_via_api(api):
    agent, admin = api.agent(), api.admin()
    call_resp, decide_resp = await asyncio.gather(
        api.client.post("/v1/guard/tool-call", json=tool_call("wipe_disk"), headers=agent),
        approve_when_pending(api, admin, approve=False))
    assert decide_resp.json()["status"] == "denied"
    assert call_resp.json()["action"] == "deny"
    # a second decision on the same approval conflicts
    again = await api.client.post(f"/api/approvals/{decide_resp.json()['id']}/decision", json={"approve": True},
                                  headers=admin)
    assert again.status_code == 409


async def test_wait_false_returns_require_approval(api):
    r = await api.client.post("/v1/guard/tool-call", json=tool_call("wipe_disk", wait=False), headers=api.agent())
    assert r.json()["action"] == "require_approval" and r.json()["approval_id"] is None
    assert api.comps.approvals.list() == []


async def test_orphaned_approval_decision_is_audited_by_the_api(api):
    decision = Decision(call_id="c9", action=Action.REQUIRE_APPROVAL)
    record = await api.comps.approvals.request(ToolCall(call_id="c9", session_id="s", agent_id="test-agent",
                                                        tool="wipe_disk"), decision, agent_name="Test Agent")
    headers = api.approver()
    got = await api.client.get(f"/api/approvals/{record.id}", headers=headers)
    assert got.status_code == 200 and got.json()["tool"] == "wipe_disk"
    r = await api.client.post(f"/api/approvals/{record.id}/decision", json={"approve": True}, headers=headers)
    assert r.status_code == 200
    events, _ = api.comps.audit.query(event_type="approval.decided")
    assert events[0].payload["source"] == "api" and events[0].action == "allow"
    assert (await api.client.get("/api/approvals/apr_missing", headers=headers)).status_code == 404
    assert (await api.client.post("/api/approvals/apr_missing/decision", json={"approve": True},
                                  headers=headers)).status_code == 404


async def test_approval_list_status_filter(api):
    record = await api.comps.approvals.request(
        ToolCall(call_id="c10", session_id="s", agent_id="test-agent", tool="wipe_disk"),
        Decision(call_id="c10", action=Action.REQUIRE_APPROVAL), agent_name="Test Agent")
    headers = api.approver()

    async def ids(**params):
        r = await api.client.get("/api/approvals", params=params, headers=headers)
        assert r.status_code == 200, r.text
        return [a["id"] for a in r.json()]

    assert await ids(status="pending") == [record.id]
    assert await ids(status="approved") == []
    assert await ids(status="") == [record.id] == await ids()  # empty filter (spec "status=&limit=") = any
    assert await ids(status="", limit=1) == [record.id]
    bad = await api.client.get("/api/approvals", params={"status": "bogus"}, headers=headers)
    assert bad.status_code == 422


async def test_tool_result_inspection_sanitizes_injection(api):
    body = {"session_id": "sess-1", "call_id": "c-2", "tool": "read_inbox", "content": INJECTION}
    r = await api.client.post("/v1/guard/tool-result", json=body, headers=api.agent())
    assert r.status_code == 200
    out = r.json()
    assert out["action"] == "sanitize" and "SAMPLE-FLAGGED-TEXT" not in out["content"]
    assert out["trust"] == "untrusted" and out["detection"]["label"] == "injection" and out["audit_seq"]


async def test_tool_result_accepts_json_content_as_structured(api):
    payload = {"items": [{"id": "e1", "from": "ceo@najd-trading.example", "body": INJECTION}]}
    body = {"session_id": "sess-1", "call_id": "c-3", "tool": "read_inbox", "content": payload}
    out = (await api.client.post("/v1/guard/tool-result", json=body, headers=api.agent())).json()
    assert out["action"] == "sanitize"
    assert out["structured"]["items"][0]["from"] == "ceo@najd-trading.example"
    assert "[REMOVED]" in out["structured"]["items"][0]["body"]


async def test_untrusted_result_then_external_call_needs_approval(api):
    agent = api.agent()
    await api.client.post("/v1/guard/tool-result", headers=agent, json={
        "session_id": "sess-t", "call_id": "c-4", "tool": "read_inbox", "content": "Please review the attached."})
    r = await api.client.post("/v1/guard/tool-call", headers=agent,
                              json=tool_call("post_external", {"url": "https://partner.example/hook"},
                                             session_id="sess-t", wait=False))
    d = r.json()
    assert d["action"] == "require_approval"
    assert any(x["layer"] == "taint" for x in d["reasons"])


async def test_invoke_through_in_process_python_upstream(api):
    calls = []

    def echo(text: str) -> str:
        calls.append(text)
        return f"echo: {text}"

    api.register_tool("echo", echo, {"type": "object", "properties": {"text": {"type": "string"}}})
    r = await api.client.post("/v1/tools/echo/invoke", json={"session_id": "s", "arguments": {"text": "salam"}},
                              headers=api.agent())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["decision"]["action"] == "allow" and body["error"] is None
    assert "echo: salam" in body["result"]["content"] and calls == ["salam"]


async def test_invoke_sanitizes_poisoned_upstream_output(api):
    api.register_tool("read_inbox", lambda: {"id": "e7", "body": INJECTION})
    r = await api.client.post("/v1/tools/read_inbox/invoke", json={"session_id": "s", "arguments": {}},
                              headers=api.agent())
    body = r.json()
    assert body["result"]["action"] == "sanitize" and "SAMPLE-FLAGGED-TEXT" not in body["result"]["content"]


async def test_invoke_denied_tool_is_never_executed(api):
    ran = []
    api.register_tool("rm_rf", lambda: ran.append(1) or "done")
    body = (await api.client.post("/v1/tools/rm_rf/invoke", json={"session_id": "s", "arguments": {}},
                                  headers=api.agent())).json()
    assert body["decision"]["action"] == "deny" and body["result"] is None and ran == []
    assert "Mirsad" in body["error"]


async def test_visible_tools_are_filtered_by_policy(api):
    for name in ("echo", "read_inbox", "rm_rf"):
        api.register_tool(name, lambda: "ok")
    r = await api.client.get("/v1/tools", headers=api.agent())
    tools = {t["name"]: t for t in r.json()}
    assert set(tools) == {"echo", "read_inbox"}
    assert tools["read_inbox"]["profile"]["trust"] == "untrusted"


async def test_guard_rejects_malformed_requests(api):
    agent = api.agent()
    r = await api.client.post("/v1/guard/tool-call", json={"session_id": "bad id with spaces", "tool": "echo"},
                              headers=agent)
    assert r.status_code == 422 and "session_id" in r.json()["detail"]
    r = await api.client.post("/v1/guard/tool-call", json={"session_id": "s", "tool": "echo", "unexpected": 1},
                              headers=agent)
    assert r.status_code == 422


async def test_detector_playground(api):
    r = await api.client.post("/api/detector/scan", json={"text": INJECTION}, headers=api.auditor())
    assert r.status_code == 200 and r.json()["label"] == "injection"
    big = await api.client.post("/api/detector/scan", json={"text": "x" * 100_001}, headers=api.auditor())
    assert big.status_code == 422


async def test_push_subscription_and_vapid(api):
    headers = api.approver()
    sub = {"endpoint": "https://push.example/send/abc", "keys": {"p256dh": "B" * 40, "auth": "A" * 16}}
    assert (await api.client.post("/api/push/subscribe", json=sub, headers=headers)).status_code == 204
    from mirsad.approvals import load_push_subscriptions

    assert [s["endpoint"] for s in load_push_subscriptions(api.comps.db)] == [sub["endpoint"]]
    bad = {**sub, "endpoint": "http://169.254.169.254/latest"}
    assert (await api.client.post("/api/push/subscribe", json=bad, headers=headers)).status_code == 422
    assert (await api.client.post("/api/push/unsubscribe", json={"endpoint": sub["endpoint"]},
                                  headers=headers)).status_code == 204
    assert load_push_subscriptions(api.comps.db) == []
    v = (await api.client.get("/api/push/vapid", headers=headers)).json()
    assert v == {"public_key": "", "enabled": False}


async def test_monitor_mode_through_the_api(api_factory):
    from tests.api.fakes import policy_text

    async with api_factory(policy=policy_text("monitor")) as api:
        agent = api.agent()
        d = (await api.client.post("/v1/guard/tool-call", json=tool_call("rm_rf"), headers=agent)).json()
        assert d["action"] == "allow" and any(r["code"] == "MONITOR_MODE" for r in d["reasons"])
        out = (await api.client.post("/v1/guard/tool-result", headers=agent, json={
            "session_id": "s", "call_id": "c", "tool": "read_inbox", "content": INJECTION})).json()
        assert out["content"] == INJECTION and out["action"] == "flag"
        ev = api.comps.audit.query(event_type="tool_call.decision")[0][0]
        assert ev.action == "deny" and json.loads(json.dumps(ev.payload))["enforced"] is False
