"""Authentication, login throttling and role enforcement on every protected route family."""

from __future__ import annotations

import pytest
from tests.api.conftest import PASSWORD

ANY = ("admin", "approver", "auditor")

# (method, path, roles allowed). Bodies are irrelevant: auth is checked before validation.
USER_ROUTES = [
    ("GET", "/api/auth/me", ANY),
    ("POST", "/api/detector/scan", ANY),
    ("GET", "/api/approvals", ("approver", "admin")),
    ("GET", "/api/approvals/apr_x", ("approver", "admin")),
    ("POST", "/api/approvals/apr_x/decision", ("approver", "admin")),
    ("GET", "/api/stream", ANY),
    ("GET", "/api/push/vapid", ANY),
    ("POST", "/api/push/subscribe", ANY),
    ("GET", "/api/audit/events", ("admin", "auditor")),
    ("GET", "/api/audit/events/1", ("admin", "auditor")),
    ("POST", "/api/audit/verify", ("admin", "auditor")),
    ("POST", "/api/audit/events/1/replay", ("admin", "auditor")),
    ("GET", "/api/audit/export", ("admin", "auditor")),
    ("GET", "/api/stats/overview", ANY),
    ("GET", "/api/stats/timeseries", ANY),
    ("GET", "/api/policies", ("admin", "auditor")),
    ("GET", "/api/policies/abc", ("admin", "auditor")),
    ("POST", "/api/policies/validate", ("admin",)),
    ("PUT", "/api/policies", ("admin",)),
    ("POST", "/api/policies/abc/activate", ("admin",)),
    ("GET", "/api/agents", ("admin",)),
    ("POST", "/api/agents", ("admin",)),
    ("POST", "/api/agents/x/rotate-key", ("admin",)),
    ("PATCH", "/api/agents/x", ("admin",)),
    ("DELETE", "/api/agents/x", ("admin",)),
    ("GET", "/api/users", ("admin",)),
    ("POST", "/api/users", ("admin",)),
    ("PATCH", "/api/users/x", ("admin",)),
    ("DELETE", "/api/users/x", ("admin",)),
    ("GET", "/api/tools", ("admin", "auditor")),
]
AGENT_ROUTES = [
    ("POST", "/v1/guard/tool-call"),
    ("POST", "/v1/guard/tool-result"),
    ("POST", "/v1/tools/echo/invoke"),
    ("GET", "/v1/tools"),
    ("POST", "/v1/chat/completions"),
]


async def test_healthz(api):
    r = await api.client.get("/healthz")
    assert r.status_code == 200 and r.json()["status"] == "ok" and r.json()["version"]


async def test_login_success_returns_token_and_user(api):
    api.user("sara", "approver")
    r = await api.client.post("/api/auth/login", json={"username": "sara", "password": PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["user"] == {"username": "sara", "role": "approver",
                                                               "display_name": "", "lang": "en"}
    me = await api.client.get("/api/auth/me", headers=api.h(body["access_token"]))
    assert me.status_code == 200 and me.json()["username"] == "sara"
    assert api.comps.audit.query(event_type="auth.login")[1] == 1


async def test_require_user_resolves_to_auth_userinfo(api):
    """Spec section 14: ``require_user(*roles)`` yields ``mirsad.auth.UserInfo``; ``require_agent`` ``AgentInfo``."""
    from mirsad.api.deps import authenticate_agent, resolve_user
    from mirsad.auth import AgentInfo, UserInfo

    user = resolve_user(api.comps, api.user("lina", "auditor"))
    assert isinstance(user, UserInfo) and (user.username, user.role) == ("lina", "auditor")
    key = api.agent("agent-two")["Authorization"].removeprefix("Bearer ")
    agent = authenticate_agent(api.comps, key)
    assert isinstance(agent, AgentInfo) and agent.policy_agent_id == "test-agent"


async def test_login_failure_is_401_and_audited_without_password(api):
    api.user("sara", "approver")
    r = await api.client.post("/api/auth/login", json={"username": "sara", "password": "wrong-password"})
    assert r.status_code == 401 and r.json() == {"detail": "Invalid username or password"}
    events, total = api.comps.audit.query(event_type="auth.login_failed")
    assert total == 1 and events[0].payload["username"] == "sara"
    assert "wrong-password" not in events[0].model_dump_json()


async def test_login_is_throttled_after_five_failures(api):
    api.user("sara", "approver")
    for _ in range(5):
        r = await api.client.post("/api/auth/login", json={"username": "sara", "password": "bad-password"})
        assert r.status_code == 401
    r = await api.client.post("/api/auth/login", json={"username": "sara", "password": PASSWORD})
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0
    # other usernames from the same client are not locked out by this counter
    api.user("omar", "auditor")
    ok = await api.client.post("/api/auth/login", json={"username": "omar", "password": PASSWORD})
    assert ok.status_code == 200


async def test_unknown_user_login_fails(api):
    r = await api.client.post("/api/auth/login", json={"username": "nobody", "password": "whatever-123"})
    assert r.status_code == 401


async def test_validation_errors_do_not_echo_input(api):
    r = await api.client.post("/api/auth/login", json={"username": "sara", "password": 12345, "extra": "s3cret"})
    assert r.status_code == 422
    body = r.json()
    assert isinstance(body["detail"], str) and "s3cret" not in r.text and "12345" not in r.text


@pytest.mark.parametrize(("method", "path", "roles"), USER_ROUTES, ids=[f"{m} {p}" for m, p, _ in USER_ROUTES])
async def test_user_routes_require_a_token(api, method, path, roles):
    r = await api.client.request(method, path, json={})
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"


FORBIDDEN = [(m, p, next(r for r in ANY if r not in roles)) for m, p, roles in USER_ROUTES if set(roles) != set(ANY)]


@pytest.mark.parametrize(("method", "path", "role"), FORBIDDEN, ids=[f"{m} {p} as {r}" for m, p, r in FORBIDDEN])
async def test_user_routes_enforce_roles(api, method, path, role):
    token = api.user(f"user-{role}", role)
    r = await api.client.request(method, path, json={}, headers=api.h(token))
    assert r.status_code == 403 and "Requires role" in r.json()["detail"]


async def test_invalid_and_expired_tokens_are_rejected(api):
    import jwt

    r = await api.client.get("/api/auth/me", headers=api.h("not-a-jwt"))
    assert r.status_code == 401
    expired = jwt.encode({"sub": "x", "role": "admin", "iat": 1, "exp": 2, "iss": "mirsad"}, "test-secret-key-0123456789abcdef0123456789")
    assert (await api.client.get("/api/auth/me", headers=api.h(expired))).status_code == 401
    forged = jwt.encode({"sub": "x", "role": "admin", "iat": 1, "exp": 4102444800, "iss": "mirsad"}, "a-different-signing-key-0123456789abcdef")
    assert (await api.client.get("/api/auth/me", headers=api.h(forged))).status_code == 401


async def test_disabled_user_and_role_change_take_effect_immediately(api):
    token = api.user("sara", "admin")
    api.user("root", "admin")
    assert (await api.client.get("/api/users", headers=api.h(token))).status_code == 200
    api.comps.auth.update_user(api.comps.db, "sara", role="auditor")
    assert (await api.client.get("/api/users", headers=api.h(token))).status_code == 403
    api.comps.auth.update_user(api.comps.db, "sara", disabled=True)
    assert (await api.client.get("/api/auth/me", headers=api.h(token))).status_code == 401


@pytest.mark.parametrize(("method", "path"), AGENT_ROUTES)
async def test_agent_routes_require_an_agent_key(api, method, path):
    assert (await api.client.request(method, path, json={})).status_code == 401
    bad = {"Authorization": "Bearer mk_abcdefgh_" + "x" * 40}
    assert (await api.client.request(method, path, json={}, headers=bad)).status_code == 401
    user_token = api.h(api.user("admin1", "admin"))
    assert (await api.client.request(method, path, json={}, headers=user_token)).status_code == 401


async def test_agent_key_is_rejected_on_management_routes(api):
    key = api.agent()["Authorization"].split()[1]
    r = await api.client.get("/api/auth/me", headers=api.h(key))
    assert r.status_code == 401 and "Agent keys" in r.json()["detail"]


async def test_x_mirsad_key_header_and_disabled_agent(api):
    key = api.agent()["Authorization"].split()[1]
    body = {"session_id": "s1", "tool": "echo", "arguments": {}}
    r = await api.client.post("/v1/guard/tool-call", json=body, headers={"X-Mirsad-Key": key})
    assert r.status_code == 200
    api.comps.auth.update_agent(api.comps.db, "agent-one", disabled=True)
    r = await api.client.post("/v1/guard/tool-call", json=body, headers={"X-Mirsad-Key": key})
    assert r.status_code == 401


async def test_bootstrap_admin_from_environment(make_app, monkeypatch):
    import httpx

    monkeypatch.setenv("MIRSAD_ADMIN_PASSWORD", "bootstrap-password-1")
    app = make_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as client:
        r = await client.post("/api/auth/login", json={"username": "admin", "password": "bootstrap-password-1"})
        assert r.status_code == 200 and r.json()["user"]["role"] == "admin"
    assert app.state.components.audit.query(event_type="user.created")[1] == 1
