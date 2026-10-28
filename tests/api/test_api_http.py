"""HTTP hardening (headers, CSP, body limit, CORS), static SPA serving, OpenAPI and lifespan wiring."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient


async def test_security_headers_on_every_response(api):
    for path in ("/healthz", "/api/auth/me", "/does-not-exist"):
        r = await api.client.get(path)
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["x-frame-options"] == "DENY"
        assert r.headers["referrer-policy"] == "no-referrer"
        csp = r.headers["content-security-policy"]
        assert "default-src 'self'" in csp and "frame-ancestors 'none'" in csp and "script-src 'self';" in csp
    api_resp = await api.client.get("/api/auth/me")
    assert api_resp.headers["cache-control"] == "no-store"


async def test_docs_are_served_with_a_docs_specific_csp(api):
    r = await api.client.get("/docs")
    assert r.status_code == 200 and "swagger" in r.text.lower()
    assert "cdn.jsdelivr.net" in r.headers["content-security-policy"]
    spec = (await api.client.get("/openapi.json")).json()
    assert spec["info"]["title"] == "Mirsad API"
    for path in ("/v1/guard/tool-call", "/api/approvals/{approval_id}/decision", "/api/stats/overview",
                 "/api/audit/events/{seq}/replay", "/v1/chat/completions"):
        assert path in spec["paths"]


async def test_request_body_over_1mb_is_rejected(api):
    big = b'{"text": "' + b"a" * (1024 * 1024 + 10) + b'"}'
    r = await api.client.post("/api/detector/scan", content=big, headers={"content-type": "application/json"})
    assert r.status_code == 413 and "too large" in r.json()["detail"]
    assert r.headers["x-frame-options"] == "DENY"


async def test_chunked_body_over_limit_is_rejected(api):
    async def chunks():
        for _ in range(20):
            yield b"x" * 65536

    r = await api.client.post("/v1/guard/tool-call", content=chunks(), headers={**api.agent(),
                                                                                  "content-type": "application/json"})
    assert r.status_code == 413


async def test_cors_allows_configured_origin_only(api):
    pre = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization,content-type"}
    ok = await api.client.options("/api/auth/login", headers={"Origin": "http://localhost:5173", **pre})
    assert ok.status_code == 200 and ok.headers["access-control-allow-origin"] == "http://localhost:5173"
    evil = await api.client.options("/api/auth/login", headers={"Origin": "https://evil.example", **pre})
    assert "access-control-allow-origin" not in evil.headers


def _build_static(root: Path) -> Path:
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<html>dashboard</html>")
    (root / "approve.html").write_text("<html>approver pwa</html>")
    (root / "assets" / "app-123.js").write_text("console.log('x')")
    (root / "sw.js").write_text("self.addEventListener('fetch', () => {})")
    return root


async def test_spa_static_serving_and_fallbacks(api_factory, tmp_path):
    static = _build_static(tmp_path / "static")
    async with api_factory(static_dir=static) as api:
        c = api.client
        assert (await c.get("/")).text == "<html>dashboard</html>"
        assert (await c.get("/activity/audit")).text == "<html>dashboard</html>"
        assert (await c.get("/approve")).text == "<html>approver pwa</html>"
        assert (await c.get("/approve/apr_123")).text == "<html>approver pwa</html>"
        js = await c.get("/assets/app-123.js")
        assert js.status_code == 200 and "javascript" in js.headers["content-type"]
        assert (await c.get("/sw.js")).status_code == 200
        assert (await c.get("/missing.js")).status_code == 404
        secret = static.parent / "secret.txt"
        secret.write_text("TOP-SECRET")
        traversal = await c.get("/..%2Fsecret.txt")
        assert "TOP-SECRET" not in traversal.text
        api_404 = await c.get("/api/does-not-exist")
        assert api_404.status_code == 404 and api_404.json() == {"detail": "Not found"}
        assert (await c.get("/")).headers["cache-control"] == "no-cache"


async def test_missing_static_dir_serves_json_note(api):
    r = await api.client.get("/")
    assert r.status_code == 200 and "not been built" in r.json()["detail"] and r.json()["api_docs"] == "/docs"


async def test_demo_routes_absent_unless_enabled(api):
    r = await api.client.get("/api/demo/scenarios", headers=api.admin())
    assert r.status_code == 404


async def test_unknown_override_key_is_rejected(make_app):
    import pytest

    with pytest.raises(ValueError, match="unknown override"):
        make_app(overrides={"detectr": object()})


def test_lifespan_starts_and_stops_cleanly(make_app):
    app = make_app()
    comps = app.state.components
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        assert app.state.audit_events_via_notifier is True
        started = comps.audit.query(event_type="system.started")[0]
        assert started and started[0].payload["version"]
    assert app.state.audit_events_via_notifier is False


def test_upstreams_file_or_demo_workspace_fallback(tmp_path):
    """No upstreams file: empty manager, except in demo mode where the in-process demo workspace is used."""
    import pytest

    pytest.importorskip("mirsad.adapters.upstreams")
    from tests.api.conftest import make_settings

    from mirsad.api.components import DEMO_WORKSPACE_TARGET, load_upstreams

    def names(manager):
        return [(s["name"], s["transport"]) for s in manager.status()]

    assert names(load_upstreams(make_settings(tmp_path, enable_demo=False))) == []
    if importlib.util.find_spec(DEMO_WORKSPACE_TARGET.split(":")[0]) is not None:
        assert names(load_upstreams(make_settings(tmp_path, enable_demo=True))) == [("workspace", "inprocess")]
    configured = tmp_path / "upstreams.yaml"
    configured.write_text("upstreams:\n  - {name: files, transport: stdio, command: [python, -m, x]}\n")
    for demo in (False, True):  # an explicit file always wins
        settings = make_settings(tmp_path, enable_demo=demo, upstreams_path=configured)
        assert names(load_upstreams(settings)) == [("files", "stdio")]


async def test_mcp_endpoint_requires_agent_key(api):
    r = await api.client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert r.status_code == 401
    r2 = await api.client.post("/mcp/", json={}, headers={"Authorization": "Bearer not-a-key"})
    assert r2.status_code == 401


async def test_openai_proxy_is_mounted_with_agent_auth(api):
    r = await api.client.post("/v1/chat/completions", json={"model": "m", "messages": [], "stream": True},
                              headers=api.agent())
    assert r.status_code in (400, 422)  # mounted, authenticated, request rejected by the adapter
