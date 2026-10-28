"""Security tests of the gateway itself, organised by STRIDE category (test IDs ST-xx in the D5 test spec).

These replace a manual Burp Suite / OWASP ZAP pass with checks that run in CI on every change.
"""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path

import jwt
import pytest
from sqlalchemy import text
from tests.api.conftest import SECRET

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = (ROOT / "configs" / "policies" / "default.yaml").read_text(encoding="utf-8")

ADMIN_ROUTES = [("GET", "/api/users"), ("GET", "/api/agents"), ("POST", "/api/policies/validate"),
                ("PUT", "/api/policies"), ("GET", "/api/audit/events"), ("POST", "/api/audit/verify"),
                ("GET", "/api/audit/export?format=json"), ("GET", "/api/approvals"), ("GET", "/api/stats/overview"),
                ("GET", "/api/tools")]


def _forge(payload: dict, *, alg: str = "HS256", key: str = SECRET) -> str:
    return jwt.encode(payload, key, algorithm=alg)


def _none_alg_token(payload: dict) -> str:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(b"=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")
    return f"{header.decode()}.{body.decode()}."


# --------------------------------------------------------------------------- Spoofing


@pytest.mark.parametrize(("method", "path"), ADMIN_ROUTES)
async def test_st01_every_management_route_requires_authentication(api, method, path):
    r = await api.client.request(method, path, json={} if method in ("POST", "PUT") else None)
    assert r.status_code == 401


async def test_st02_forged_and_unsigned_tokens_are_rejected(api):
    now = int(time.time())
    claims = {"sub": "mallory", "role": "admin", "iat": now, "exp": now + 600}
    for token in (_forge(claims, key="not-the-server-secret-0123456789abcdef"), _none_alg_token(claims),
                  _forge({**claims, "exp": now - 10}), "not-a-jwt", ""):
        r = await api.client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401, token


async def test_st03_role_claim_tampering_does_not_escalate(api):
    token = api.user("appr", "approver")
    header, body, sig = token.split(".")
    claims = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    claims["role"] = "admin"
    tampered_body = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    r = await api.client.get("/api/users", headers={"Authorization": f"Bearer {header}.{tampered_body}.{sig}"})
    assert r.status_code == 401


async def test_st04_agent_key_rotation_revokes_old_key(api):
    created = await api.client.post("/api/agents", headers=api.admin(),
                                    json={"id": "rot-agent", "name": "Rot", "policy_agent_id": "test-agent"})
    assert created.status_code == 201
    old_key = created.json()["api_key"]
    assert (await api.client.get("/v1/tools", headers={"Authorization": f"Bearer {old_key}"})).status_code == 200
    rotated = await api.client.post("/api/agents/rot-agent/rotate-key", headers=api.admin())
    new_key = rotated.json()["api_key"]
    assert new_key != old_key
    assert (await api.client.get("/v1/tools", headers={"Authorization": f"Bearer {old_key}"})).status_code == 401
    assert (await api.client.get("/v1/tools", headers={"Authorization": f"Bearer {new_key}"})).status_code == 200


async def test_st05_garbage_agent_keys_are_rejected(api):
    for key in ("mk_deadbeef_" + "x" * 40, "mk_", "sk-123", "' OR 1=1 --"):
        r = await api.client.get("/v1/tools", headers={"X-Mirsad-Key": key})
        assert r.status_code == 401


# --------------------------------------------------------------------------- Tampering


async def test_st06_audit_tampering_is_detected(api):
    agent = api.agent()
    api.register_tool("echo", lambda **kw: {"echo": kw})
    for i in range(3):
        r = await api.client.post("/v1/tools/echo/invoke", headers=agent,
                                  json={"session_id": "s1", "arguments": {"n": i}})
        assert r.status_code == 200
    ok = await api.client.post("/api/audit/verify", headers=api.admin())
    assert ok.json()["ok"] is True
    with api.comps.db.session() as s:
        seq = s.execute(text("SELECT seq FROM audit_events ORDER BY seq LIMIT 1 OFFSET 1")).scalar_one()
        s.execute(text("UPDATE audit_events SET action = 'allow', payload_json = '{}' WHERE seq = :q"), {"q": seq})
        s.commit()
    bad = (await api.client.post("/api/audit/verify", headers=api.admin())).json()
    assert bad["ok"] is False and bad["first_bad_seq"] == seq


async def test_st07_audit_row_deletion_is_detected(api):
    agent = api.agent()
    api.register_tool("echo", lambda **kw: {"echo": kw})
    for i in range(3):
        await api.client.post("/v1/tools/echo/invoke", headers=agent, json={"session_id": "s1", "arguments": {"n": i}})
    with api.comps.db.session() as s:
        seq = s.execute(text("SELECT seq FROM audit_events ORDER BY seq LIMIT 1 OFFSET 2")).scalar_one()
        s.execute(text("DELETE FROM audit_events WHERE seq = :q"), {"q": seq})
        s.commit()
    assert (await api.client.post("/api/audit/verify", headers=api.admin())).json()["ok"] is False


async def test_st08_policy_with_catastrophic_regex_is_rejected(api):
    bad = DEFAULT_POLICY.replace("^https?://", "^(a+)+$")
    r = await api.client.post("/api/policies/validate", headers=api.admin(), json={"yaml_text": bad})
    assert r.status_code == 200 and r.json()["valid"] is False
    act = await api.client.put("/api/policies", headers=api.admin(), json={"yaml_text": bad})
    assert act.status_code == 422


# --------------------------------------------------------------------------- Repudiation


async def test_st09_approval_decisions_are_attributed_and_final(api_factory):
    import asyncio

    async with api_factory() as api:
        agent = api.agent()
        api.register_tool("wipe_disk", lambda **kw: {"ok": True})
        call = asyncio.create_task(api.client.post("/v1/tools/wipe_disk/invoke", headers=agent,
                                                   json={"session_id": "s9", "arguments": {}}))
        approver = api.approver()
        pending: list = []
        for _ in range(100):
            pending = (await api.client.get("/api/approvals?status=pending", headers=approver)).json()
            if pending:
                break
            await asyncio.sleep(0.02)
        assert pending, "the critical call should be waiting for approval"
        approval_id = pending[0]["id"]
        first = await api.client.post(f"/api/approvals/{approval_id}/decision", headers=approver,
                                      json={"approve": False, "note": "not expected"})
        assert first.status_code == 200 and first.json()["decided_by"] == "approver1"
        result = (await call).json()
        assert result["decision"]["action"] == "deny"
        again = await api.client.post(f"/api/approvals/{approval_id}/decision", headers=approver,
                                      json={"approve": True})
        assert again.status_code == 409
        events = (await api.client.get("/api/audit/events?event_type=approval.decided", headers=api.admin())).json()
        assert events["total"] >= 1


async def test_st10_failed_logins_are_audited_without_the_password(api):
    await api.client.post("/api/auth/login", json={"username": "admin1", "password": "WrongPassword!42"})
    page = (await api.client.get("/api/audit/events?event_type=auth.login_failed", headers=api.admin())).json()
    assert page["total"] >= 1
    assert "WrongPassword!42" not in json.dumps(page)


# --------------------------------------------------------------------------- Information disclosure


async def test_st11_secrets_in_tool_arguments_are_redacted_in_audit(api):
    agent = api.agent()
    api.register_tool("echo", lambda **kw: {"ok": True})
    secret = "sk-live-0123456789abcdefABCDEF0123456789"
    await api.client.post("/v1/tools/echo/invoke", headers=agent,
                          json={"session_id": "s11", "arguments": {"note": f"use key {secret}", "password": "hunter22"}})
    export = await api.client.get("/api/audit/export?format=json", headers=api.admin())
    assert export.status_code == 200
    assert secret not in export.text and "hunter22" not in export.text


async def test_st12_user_and_agent_listings_never_expose_hashes_or_keys(api):
    await api.client.post("/api/agents", headers=api.admin(),
                          json={"id": "list-agent", "name": "L", "policy_agent_id": "test-agent"})
    users = (await api.client.get("/api/users", headers=api.admin())).text
    agents = (await api.client.get("/api/agents", headers=api.admin())).text
    assert "scrypt" not in users and "password_hash" not in users
    assert "key_hash" not in agents and "mk_" not in agents.replace('"key_prefix"', "")


async def test_st13_unhandled_errors_do_not_leak_internals(api):
    agent = api.agent()

    def boom(**kw):
        raise RuntimeError("internal path /etc/shadow and stack details")

    api.register_tool("echo", boom)
    r = await api.client.post("/v1/tools/echo/invoke", headers=agent, json={"session_id": "s13", "arguments": {}})
    assert r.status_code in (200, 502)
    assert "/etc/shadow" not in r.text and "Traceback" not in r.text


@pytest.mark.parametrize("path", ["/../../etc/passwd", "/assets/..%2f..%2fpyproject.toml", "/%2e%2e/%2e%2e/pyproject.toml",
                                  "/approve/../../../pyproject.toml"])
async def test_st14_static_paths_cannot_escape_the_web_root(make_app, tmp_path, path):
    import httpx

    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<html>index</html>")
    (static / "approve.html").write_text("<html>approve</html>")
    app = make_app(static_dir=static)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get(path)
    assert "[project]" not in r.text and "root:" not in r.text


async def test_st15_security_headers_on_api_responses(api):
    r = await api.client.get("/healthz")
    assert r.headers.get("x-frame-options") == "DENY"
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert "frame-ancestors 'none'" in r.headers.get("content-security-policy", "")
    assert r.headers.get("referrer-policy")


async def test_st16_cors_rejects_unknown_origins(api):
    evil = await api.client.options("/api/auth/login", headers={"Origin": "https://evil.example",
                                                                "Access-Control-Request-Method": "POST"})
    assert evil.headers.get("access-control-allow-origin") != "https://evil.example"
    good = await api.client.options("/api/auth/login", headers={"Origin": "http://localhost:5173",
                                                                "Access-Control-Request-Method": "POST"})
    assert good.headers.get("access-control-allow-origin") == "http://localhost:5173"


@pytest.mark.parametrize("q", ["' OR '1'='1", "1; DROP TABLE audit_events; --", "%' UNION SELECT * FROM users --"])
async def test_st17_injection_style_filter_values_are_treated_as_data(api, q):
    r = await api.client.get("/api/audit/events", headers=api.admin(), params={"q": q, "tool": q, "agent_id": q})
    assert r.status_code == 200
    assert r.json()["total"] == 0
    assert (await api.client.post("/api/audit/verify", headers=api.admin())).json()["ok"] is True


# --------------------------------------------------------------------------- Denial of service


async def test_st18_oversized_bodies_are_rejected(api):
    agent = api.agent()
    big = {"session_id": "s", "tool": "echo", "arguments": {"blob": "A" * (1024 * 1024 + 10)}}
    r = await api.client.post("/v1/guard/tool-call", headers=agent, content=json.dumps(big),
                              params={}, )
    assert r.status_code == 413


async def test_st19_login_brute_force_is_throttled(api):
    api.user("victim", "approver")
    codes = [(await api.client.post("/api/auth/login", json={"username": "victim", "password": f"guess-{i}xx"})).status_code
             for i in range(7)]
    assert 429 in codes
    blocked = await api.client.post("/api/auth/login", json={"username": "victim", "password": "correct-horse-battery"})
    assert blocked.status_code == 429


# --------------------------------------------------------------------------- Elevation of privilege


@pytest.mark.parametrize(("role", "method", "path"), [
    ("approver", "GET", "/api/users"), ("approver", "PUT", "/api/policies"), ("approver", "POST", "/api/agents"),
    ("auditor", "POST", "/api/agents"), ("auditor", "PUT", "/api/policies"), ("auditor", "POST", "/api/users"),
])
async def test_st20_roles_cannot_perform_admin_actions(api, role, method, path):
    headers = api.approver() if role == "approver" else api.auditor()
    r = await api.client.request(method, path, headers=headers, json={"yaml_text": "x", "id": "x", "name": "x",
                                                                       "policy_agent_id": "x", "username": "x",
                                                                       "password": "x" * 12, "role": "admin"})
    assert r.status_code == 403


async def test_st21_agent_keys_cannot_use_human_apis_and_humans_cannot_act_as_agents(api):
    agent = api.agent()
    assert (await api.client.get("/api/users", headers=agent)).status_code == 401
    assert (await api.client.get("/v1/tools", headers=api.admin())).status_code == 401


async def test_st22_default_deny_for_unlisted_tools_and_unknown_policy_agents(api):
    agent = api.agent()
    r = await api.client.post("/v1/guard/tool-call", headers=agent,
                              json={"session_id": "s", "tool": "format_hard_drive", "arguments": {}, "wait": False})
    assert r.json()["action"] == "deny"
    ghost = api.agent("ghost-agent", policy_agent="no-such-policy-agent")
    r = await api.client.post("/v1/guard/tool-call", headers=ghost,
                              json={"session_id": "s", "tool": "echo", "arguments": {}, "wait": False})
    assert r.json()["action"] == "deny"


@pytest.mark.parametrize("url", ["http://127.0.0.1:8700/api/users", "http://169.254.169.254/latest/meta-data/",
                                 "http://localhost/admin", "file:///etc/passwd"])
async def test_st23_default_policy_blocks_ssrf_targets_for_fetch_url(api_factory, url):
    async with api_factory(policy=DEFAULT_POLICY) as api:
        agent = api.agent("ssrf-agent", policy_agent="email-crm-assistant")
        r = await api.client.post("/v1/guard/tool-call", headers=agent,
                                  json={"session_id": "s23", "tool": "fetch_url", "arguments": {"url": url},
                                        "wait": False})
        assert r.json()["action"] == "deny", r.json()
