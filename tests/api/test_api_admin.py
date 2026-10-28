"""Audit, statistics, policies (hot reload), agents, users and tools management endpoints."""

from __future__ import annotations

import csv
import io
import json

from tests.api.fakes import policy_text

INJECTION = "SAMPLE-FLAGGED-TEXT placeholder, 9000 SAR"


async def _traffic(api) -> dict[str, str]:
    """A few decisions and inspections so the audit log and stats have content."""
    agent = api.agent()
    for tool in ("echo", "echo", "rm_rf"):
        await api.client.post("/v1/guard/tool-call", json={"session_id": "s1", "tool": tool}, headers=agent)
    await api.client.post("/v1/guard/tool-call", json={"session_id": "s1", "tool": "wipe_disk", "wait": False},
                          headers=agent)
    await api.client.post("/v1/guard/tool-result", headers=agent, json={
        "session_id": "s1", "call_id": "c1", "tool": "read_inbox", "content": INJECTION})
    return agent


# --------------------------------------------------------------------------- audit


async def test_audit_list_filter_and_detail(api):
    await _traffic(api)
    h = api.auditor()
    r = await api.client.get("/api/audit/events", params={"event_type": "tool_call.decision", "limit": 2},
                             headers=h)
    page = r.json()
    assert r.status_code == 200 and page["total"] == 4 and len(page["items"]) == 2
    assert page["items"][0]["seq"] > page["items"][1]["seq"]  # newest first
    denied = (await api.client.get("/api/audit/events", params={"action": "deny"}, headers=h)).json()
    assert denied["total"] == 1 and denied["items"][0]["tool"] == "rm_rf"
    seq = denied["items"][0]["seq"]
    detail = (await api.client.get(f"/api/audit/events/{seq}", headers=h)).json()
    assert detail["payload"]["reasons"][0]["code"] == "TOOL_NOT_ALLOWED" and len(detail["hash"]) == 64
    assert (await api.client.get("/api/audit/events/99999", headers=h)).status_code == 404


async def test_audit_verify_detects_tampering(api):
    await _traffic(api)
    h = api.admin()
    ok = (await api.client.post("/api/audit/verify", headers=h)).json()
    assert ok["ok"] is True and ok["checked"] >= 5
    from sqlalchemy import text

    with api.comps.tables.engine.begin() as conn:  # an attacker edits a stored decision
        conn.execute(text("UPDATE audit_events SET action = 'allow' WHERE tool = 'rm_rf'"))
    bad = (await api.client.post("/api/audit/verify", headers=h)).json()
    assert bad["ok"] is False and bad["first_bad_seq"] is not None
    assert api.comps.audit.query(event_type="audit.verified")[1] == 2


async def test_audit_replay_decision_and_inspection(api):
    await _traffic(api)
    h = api.auditor()
    events = api.comps.audit.query(event_type="tool_call.decision", order="asc")[0]
    rep = (await api.client.post(f"/api/audit/events/{events[2].seq}/replay", headers=h)).json()
    assert rep["match"] is True and rep["original_action"] == rep["replayed_action"] == "deny"
    insp = api.comps.audit.query(event_type="tool_result.inspection")[0][0]
    rep2 = (await api.client.post(f"/api/audit/events/{insp.seq}/replay", headers=h)).json()
    assert rep2["event_type"] == "tool_result.inspection" and rep2["match"] is True
    login = api.comps.audit.append("system.note", payload={})
    assert (await api.client.post(f"/api/audit/events/{login.seq}/replay", headers=h)).status_code == 400
    assert (await api.client.post("/api/audit/events/424242/replay", headers=h)).status_code == 404


async def test_replay_after_policy_change_uses_recorded_version(api):
    agent = api.agent()
    d = (await api.client.post("/v1/guard/tool-call", json={"session_id": "s", "tool": "rm_rf"},
                               headers=agent)).json()
    new_policy = policy_text(extra_tools="      rm_rf: {allow: true, approval: never}\n")
    act = await api.client.put("/api/policies", json={"yaml_text": new_policy}, headers=api.admin())
    assert act.status_code == 200
    now = (await api.client.post("/v1/guard/tool-call", json={"session_id": "s", "tool": "rm_rf"},
                                 headers=agent)).json()
    assert now["action"] == "allow"
    rep = (await api.client.post(f"/api/audit/events/{d['audit_seq']}/replay", headers=api.auditor())).json()
    assert rep["replayed_action"] == "deny" and rep["match"] is True
    assert rep["details"]["policy_version"] == d["policy_version"] != now["policy_version"]


async def test_audit_export_json_and_csv(api):
    await _traffic(api)
    h = api.auditor()
    r = await api.client.get("/api/audit/export", params={"format": "json", "event_type": "tool_call.decision"},
                             headers=h)
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/json")
    assert "attachment" in r.headers["content-disposition"]
    doc = json.loads(r.text)
    assert doc["count"] == 4 and {e["event_type"] for e in doc["events"]} == {"tool_call.decision"}
    c = await api.client.get("/api/audit/export", params={"format": "csv"}, headers=h)
    assert c.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(c.text)))
    assert len(rows) >= 5 and "hash" in rows[0]
    assert (await api.client.get("/api/audit/export", params={"format": "xml"}, headers=h)).status_code == 422


# --------------------------------------------------------------------------- stats


async def test_stats_overview_shape_and_counts(api):
    await _traffic(api)
    o = (await api.client.get("/api/stats/overview", params={"hours": 1}, headers=api.approver())).json()
    for key in ("total_calls", "allowed", "denied", "approvals_required", "approvals_pending", "injections_detected",
                "results_sanitized", "median_latency_ms", "p95_latency_ms", "audit_ok", "by_tool", "by_layer"):
        assert key in o
    assert (o["total_calls"], o["allowed"], o["denied"], o["approvals_required"]) == (4, 2, 1, 1)
    assert o["injections_detected"] == 1 and o["results_sanitized"] == 1 and o["audit_ok"] is True
    assert o["median_latency_ms"] > 0 and o["p95_latency_ms"] >= o["median_latency_ms"]
    by_tool = {t["tool"]: t for t in o["by_tool"]}
    assert by_tool["echo"]["allowed"] == 2 and by_tool["rm_rf"]["denied"] == 1 and by_tool["wipe_disk"]["approval"] == 1
    layers = {x["layer"]: x["count"] for x in o["by_layer"]}
    assert layers["policy"] == 2 and layers["detector"] == 1


async def test_stats_python_fallback_matches_sqlite_path(api):
    import time

    from mirsad.api.routers import stats

    await _traffic(api)
    now = time.time() + 1
    fast = stats._json_rows_sqlite(api.comps, now - 3600, now)
    slow = stats._json_rows_python(api.comps, now - 3600, now)
    assert sorted(fast[0]) == sorted(slow[0]) and fast[1] == slow[1] and fast[2] == slow[2]


async def test_stats_timeseries_buckets(api):
    await _traffic(api)
    r = await api.client.get("/api/stats/timeseries", params={"hours": 2, "bucket_minutes": 30},
                             headers=api.auditor())
    buckets = r.json()
    assert len(buckets) == 4 and all(set(b) == {"t", "allowed", "denied", "require_approval", "injections"}
                                     for b in buckets)
    assert buckets[-1]["allowed"] == 2 and buckets[-1]["denied"] == 1 and buckets[-1]["injections"] == 1
    assert buckets[1]["t"] - buckets[0]["t"] == 1800


async def test_stats_empty_database(api):
    o = (await api.client.get("/api/stats/overview", headers=api.auditor())).json()
    assert o["total_calls"] == 0 and o["median_latency_ms"] is None and o["by_tool"] == []


# --------------------------------------------------------------------------- policies


async def test_policy_list_and_get(api):
    h = api.auditor()
    listing = (await api.client.get("/api/policies", headers=h)).json()
    assert listing["active"]["version"] == api.comps.gateway.policy.version
    assert "test-agent" in listing["active"]["yaml_text"] and len(listing["versions"]) == 1
    v = listing["active"]["version"]
    assert (await api.client.get(f"/api/policies/{v}", headers=h)).json()["active"] is True
    assert (await api.client.get("/api/policies/nope", headers=h)).status_code == 404


async def test_policy_validate(api):
    h = api.admin()
    ok = (await api.client.post("/api/policies/validate", json={"yaml_text": policy_text()}, headers=h)).json()
    assert ok == {"valid": True, "errors": []}
    bad = (await api.client.post("/api/policies/validate", json={"yaml_text": "version: 2\nagents: 7\n"},
                                 headers=h)).json()
    assert bad["valid"] is False and bad["errors"]


async def test_policy_activation_hot_reloads_the_gateway_and_is_audited(api):
    agent, h = api.agent(), api.admin()
    before = (await api.client.post("/v1/guard/tool-call", json={"session_id": "s", "tool": "rm_rf"},
                                    headers=agent)).json()
    assert before["action"] == "deny"
    limiter = api.comps.gateway.policy.rate_limiter
    new = policy_text(extra_tools="      rm_rf: {allow: true, approval: never}\n")
    r = await api.client.put("/api/policies", json={"yaml_text": new, "comment": "allow rm_rf"}, headers=h)
    assert r.status_code == 200
    assert api.comps.gateway.policy.rate_limiter is limiter  # counters survive the hot reload
    act = r.json()
    assert act["active"] is True and act["previous_version"] == before["policy_version"]
    assert act["created_by"] == "admin1" and act["comment"] == "allow rm_rf"
    after = (await api.client.post("/v1/guard/tool-call", json={"session_id": "s", "tool": "rm_rf"},
                                   headers=agent)).json()
    assert after["action"] == "allow" and after["policy_version"] == act["version"]
    events, total = api.comps.audit.query(event_type="policy.activated")
    assert total == 1 and events[0].payload["activated_by"] == "admin1"
    versions = (await api.client.get("/api/policies", headers=h)).json()["versions"]
    assert [v["active"] for v in versions].count(True) == 1 and len(versions) == 2
    # rollback to the first version
    rb = await api.client.post(f"/api/policies/{before['policy_version']}/activate", headers=h)
    assert rb.status_code == 200 and api.comps.gateway.policy.version == before["policy_version"]


async def test_invalid_policy_is_rejected_and_not_activated(api):
    current = api.comps.gateway.policy.version
    r = await api.client.put("/api/policies", json={"yaml_text": "version: 1\nagents: [1, 2]\n"}, headers=api.admin())
    assert r.status_code == 422 and r.json()["detail"].startswith("Invalid policy")
    assert api.comps.gateway.policy.version == current


async def test_policy_activated_elsewhere_is_picked_up(api):
    from mirsad.api.app import sync_active_policy

    engine = api.comps.policy_module.PolicyEngine.from_yaml(policy_text(extra_tools="      zz: {allow: true}\n"))
    store = api.comps.policy_store
    store.save(engine.version, engine.yaml_text, created_by="cli:test")
    store.activate(engine.version)
    assert sync_active_policy(api.app) is True and api.comps.gateway.policy.version == engine.version
    assert sync_active_policy(api.app) is False


# --------------------------------------------------------------------------- agents & users


async def test_agent_crud_shows_key_once(api):
    h = api.admin()
    r = await api.client.post("/api/agents", headers=h, json={
        "id": "crm-bot", "name": "CRM Bot", "policy_agent_id": "test-agent", "description": "prod"})
    assert r.status_code == 201
    created = r.json()
    key = created["api_key"]
    assert key.startswith("mk_") and created["agent"]["key_prefix"] in key and created["warnings"] == []
    listing = await api.client.get("/api/agents", headers=h)
    assert key not in listing.text and "key_hash" not in listing.text and listing.json()[0]["id"] == "crm-bot"
    # the key works, then rotation invalidates it
    call = {"session_id": "s", "tool": "echo"}
    assert (await api.client.post("/v1/guard/tool-call", json=call, headers=api.h(key))).status_code == 200
    rot = (await api.client.post("/api/agents/crm-bot/rotate-key", headers=h)).json()
    assert rot["api_key"] != key
    assert (await api.client.post("/v1/guard/tool-call", json=call, headers=api.h(key))).status_code == 401
    assert (await api.client.post("/v1/guard/tool-call", json=call, headers=api.h(rot["api_key"]))).status_code == 200
    # patch + delete
    p = await api.client.patch("/api/agents/crm-bot", json={"disabled": True, "name": "CRM Bot v2"}, headers=h)
    assert p.json()["disabled"] is True and p.json()["name"] == "CRM Bot v2"
    assert (await api.client.delete("/api/agents/crm-bot", headers=h)).status_code == 204
    assert (await api.client.delete("/api/agents/crm-bot", headers=h)).status_code == 404
    types = [e.event_type for e in api.comps.audit.query(order="asc", limit=50)[0]]
    assert {"agent.created", "agent.key_rotated", "agent.updated", "agent.deleted"} <= set(types)
    assert key not in json.dumps([e.model_dump() for e in api.comps.audit.query(limit=50)[0]])


async def test_agent_create_validation_and_conflicts(api):
    h = api.admin()
    body = {"id": "bot-1", "name": "Bot", "policy_agent_id": "unknown-policy-agent"}
    first = (await api.client.post("/api/agents", json=body, headers=h)).json()
    assert first["warnings"] and "not defined" in first["warnings"][0]
    assert (await api.client.post("/api/agents", json=body, headers=h)).status_code == 409
    bad = {**body, "id": "Bad Id!"}
    assert (await api.client.post("/api/agents", json=bad, headers=h)).status_code == 422


async def test_user_crud_never_returns_hashes(api):
    h = api.admin()
    r = await api.client.post("/api/users", json={"username": "noura", "role": "approver", "lang": "ar"}, headers=h)
    assert r.status_code == 201
    generated = r.json()["generated_password"]
    assert generated and len(generated) >= 16 and r.json()["user"]["lang"] == "ar"
    login = await api.client.post("/api/auth/login", json={"username": "noura", "password": generated})
    assert login.status_code == 200
    listing = await api.client.get("/api/users", headers=h)
    assert "password" not in listing.text and "scrypt" not in listing.text
    p = await api.client.patch("/api/users/noura", json={"role": "auditor", "password": "a-new-password-42"},
                               headers=h)
    assert p.status_code == 200 and p.json()["role"] == "auditor"
    assert (await api.client.post("/api/auth/login", json={"username": "noura", "password": "a-new-password-42"}
                                  )).status_code == 200
    assert (await api.client.post("/api/users", json={"username": "noura", "role": "admin",
                                                      "password": "long-enough-pw"}, headers=h)).status_code == 409
    assert (await api.client.delete("/api/users/noura", headers=h)).status_code == 204
    assert (await api.client.patch("/api/users/noura", json={"lang": "en"}, headers=h)).status_code == 404
    updated = [e for e in api.comps.audit.query(event_type="user.updated")[0]]
    assert updated[0].payload["password_changed_at"] > 0 and "a-new-password-42" not in updated[0].model_dump_json()


async def test_last_admin_is_protected(api):
    h = api.admin()
    assert (await api.client.patch("/api/users/admin1", json={"role": "auditor"}, headers=h)).status_code == 409
    assert (await api.client.patch("/api/users/admin1", json={"disabled": True}, headers=h)).status_code == 409
    assert (await api.client.delete("/api/users/admin1", headers=h)).status_code == 409
    api.user("admin2", "admin")
    assert (await api.client.delete("/api/users/admin2", headers=h)).status_code == 204


async def test_tools_listing_shows_profiles_per_agent(api):
    api.register_tool("read_inbox", lambda: "x")
    api.register_tool("rm_rf", lambda: "x")
    tools = {t["name"]: t for t in (await api.client.get("/api/tools", headers=api.auditor())).json()}
    assert tools["read_inbox"]["profiles"]["test-agent"]["trust"] == "untrusted"
    assert tools["rm_rf"]["profiles"]["test-agent"]["allowed"] is False
    assert tools["read_inbox"]["upstream"]
