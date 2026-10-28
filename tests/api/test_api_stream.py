"""SSE stream against a real uvicorn server (ASGI test transports buffer whole responses)."""

from __future__ import annotations

import asyncio
import json
import socket
import threading
import time
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import pytest
import uvicorn
from tests.api.conftest import PASSWORD


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def live(make_app) -> Iterator[tuple[Any, str]]:
    app = make_app()
    app.state.sse_ping_s = 0.5
    app.state.maintenance_interval_s = 0.5
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="on"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    assert server.started, "uvicorn did not start"
    yield app, f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=15)


async def sse_events(resp: httpx.Response) -> AsyncIterator[tuple[str, Any]]:
    """Yield (event, data) pairs; heartbeat comments are yielded as ("comment", text)."""
    event, data = "message", []
    async for line in resp.aiter_lines():
        if line.startswith(":"):
            yield "comment", line
        elif line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].strip())
        elif line == "" and data:
            yield event, json.loads("\n".join(data))
            event, data = "message", []


async def next_event(it: AsyncIterator[tuple[str, Any]], wanted: str, timeout: float = 10) -> tuple[Any, list[str]]:
    seen: list[str] = []

    async def scan() -> Any:
        async for name, data in it:
            seen.append(name)
            if name == wanted:
                return data
        raise AssertionError(f"stream ended before {wanted}")

    return await asyncio.wait_for(scan(), timeout), seen


def _creds(app: Any) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    comps = app.state.components
    auth, db = comps.auth, comps.db
    auth.create_user(db, "admin1", PASSWORD, "admin")
    auth.create_user(db, "approver1", PASSWORD, "approver")
    _info, key = auth.create_agent(db, "agent-one", "Agent One", "test-agent")
    admin = {"Authorization": f"Bearer {auth.create_token('admin1', 'admin', comps.secret, 1)}"}
    approver = {"Authorization": f"Bearer {auth.create_token('approver1', 'approver', comps.secret, 1)}"}
    return admin, approver, {"Authorization": f"Bearer {key}"}


async def test_sse_relays_approval_lifecycle_and_audit_events(live):
    app, base = live
    admin, _approver, agent = _creds(app)
    async with httpx.AsyncClient(base_url=base, timeout=30) as client:
        async with client.stream("GET", "/api/stream", headers=admin) as resp:
            assert resp.status_code == 200 and resp.headers["content-type"].startswith("text/event-stream")
            it = sse_events(resp)
            ready, _ = await next_event(it, "ready")
            assert ready == {"user": "admin1", "role": "admin"}
            call = asyncio.create_task(client.post("/v1/guard/tool-call", headers=agent, json={
                "session_id": "s1", "tool": "wipe_disk", "arguments": {"path": "/srv"}}))
            requested, seen = await next_event(it, "approval.requested")
            assert requested["tool"] == "wipe_disk" and requested["status"] == "pending" and requested["summary_ar"]
            assert "audit.event" in seen  # the decision event was relayed before the approval request
            r = await client.post(f"/api/approvals/{requested['id']}/decision", json={"approve": True}, headers=admin)
            assert r.status_code == 200
            decided, _ = await next_event(it, "approval.decided")
            assert decided["id"] == requested["id"] and decided["status"] == "approved"
            audit, _ = await next_event(it, "audit.event")
            assert "payload" in audit and audit["seq"] > 0
            assert (await call).json()["action"] == "allow"


async def test_sse_heartbeat_and_approver_audit_summary(live):
    app, base = live
    _admin, approver, agent = _creds(app)
    async with httpx.AsyncClient(base_url=base, timeout=30) as client:
        async with client.stream("GET", "/api/stream", headers=approver) as resp:
            it = sse_events(resp)
            await next_event(it, "ready")
            await next_event(it, "comment", timeout=5)  # heartbeat
            await client.post("/v1/guard/tool-call", headers=agent, json={"session_id": "s", "tool": "echo"})
            audit, _ = await next_event(it, "audit.event")
            assert set(audit) == {"seq", "ts", "event_type", "tool", "action", "risk"}  # no payload for approvers


async def test_sse_requires_authorization_header(live):
    _app, base = live
    async with httpx.AsyncClient(base_url=base, timeout=10) as client:
        assert (await client.get("/api/stream")).status_code == 401
        assert (await client.get("/api/stream", params={"token": "x"})).status_code == 401


async def test_sse_polling_fallback_without_audit_listener(make_app):
    """Audit logs without listener support are tailed by polling the chain head."""
    from tests.api.fakes import FakeAudit

    from mirsad.api.routers.stream import _poll_audit

    audit = FakeAudit()
    audit.append("a")
    queue: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(_poll_audit(audit, queue, 0.05))
    await asyncio.sleep(0.1)
    audit.append("b")
    audit.append("c")
    got = [await asyncio.wait_for(queue.get(), 2) for _ in range(2)]
    task.cancel()
    assert [d["event_type"] for _, d in got] == ["b", "c"]
