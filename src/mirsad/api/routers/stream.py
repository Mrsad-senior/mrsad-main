"""Server-Sent Events: live approval events and new audit events for the dashboard and approver PWA.

Authentication uses the ``Authorization`` header (the web clients use fetch-based SSE), never a
query-string token, so credentials do not end up in access logs. Audit events reach the
notifier through an ``AuditLog`` listener registered at startup; with an audit log that has no
listener support the stream falls back to polling the chain head.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Request
from sse_starlette import EventSourceResponse
from starlette.concurrency import run_in_threadpool

from mirsad.api.deps import get_components, require_user
from mirsad.api.schemas import ErrorResponses

log = logging.getLogger("mirsad.api")

router = APIRouter(prefix="/api", tags=["stream"], responses=ErrorResponses.AUTH)

HEARTBEAT_S = 15.0
AUDIT_POLL_S = 1.0
AUDIT_BATCH = 200
FULL_AUDIT_ROLES = ("admin", "auditor")
_SUMMARY_FIELDS = ("seq", "ts", "event_type", "tool", "action", "risk")


def _encode(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def audit_view(data: dict[str, Any], full: bool) -> dict[str, Any]:
    """Approvers may not read audit payloads (that needs admin/auditor), so they get a summary."""
    return data if full else {k: data.get(k) for k in _SUMMARY_FIELDS}


async def _poll_audit(audit: Any, out: asyncio.Queue[tuple[str, Any]], poll_s: float) -> None:
    last, _ = await run_in_threadpool(audit.head)
    while True:
        await asyncio.sleep(poll_s)
        head, _ = await run_in_threadpool(audit.head)
        if head <= last:
            continue
        n = min(head - last, AUDIT_BATCH)
        events, _total = await run_in_threadpool(lambda n=n: audit.query(limit=n, order="desc"))
        for event in sorted((e for e in events if e.seq > last), key=lambda e: e.seq):
            out.put_nowait(("audit.event", event.model_dump(mode="json")))
        last = head


async def _pump(sub: Any, out: asyncio.Queue[tuple[str, Any]]) -> None:
    async for event, data in sub:
        out.put_nowait((event, data))


@router.get("/stream", response_class=EventSourceResponse,
            description="SSE stream. Events: `ready`, `approval.requested`, `approval.decided`, `audit.event`. "
                        "Heartbeat comments every 15 s. Admins/auditors receive full audit events; "
                        "approvers receive a summary without payload.")
async def stream(request: Request, user=Depends(require_user())) -> EventSourceResponse:  # noqa: B008
    comps = get_components(request)
    state = request.app.state
    full = user.role in FULL_AUDIT_ROLES
    ping = getattr(state, "sse_ping_s", HEARTBEAT_S)
    poll = getattr(state, "sse_audit_poll_s", AUDIT_POLL_S)
    sub = comps.notifier.subscribe()  # registered now: nothing published after this point is missed

    async def events() -> AsyncIterator[dict[str, str]]:
        queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
        tasks = [asyncio.create_task(_pump(sub, queue))]
        if not getattr(state, "audit_events_via_notifier", False):
            tasks.append(asyncio.create_task(_poll_audit(comps.audit, queue, poll)))
        try:
            yield {"event": "ready", "data": _encode({"user": user.username, "role": user.role})}
            while True:
                event, data = await queue.get()
                if event == "audit.event" and isinstance(data, dict):
                    data = audit_view(data, full)
                yield {"event": event, "data": _encode(data)}
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            with contextlib.suppress(Exception):
                await sub.aclose()

    return EventSourceResponse(events(), ping=ping, headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
