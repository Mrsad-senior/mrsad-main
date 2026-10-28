"""Audit log: search, detail, chain verification, deterministic replay and export."""

from __future__ import annotations

import time
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from mirsad.api.deps import get_components, require_user
from mirsad.api.schemas import ErrorResponses
from mirsad.gateway import ReplayError, ReplayReport
from mirsad.models import AuditEvent

router = APIRouter(prefix="/api/audit", tags=["audit"], responses=ErrorResponses.AUTH)
auditor = require_user("admin", "auditor")


class AuditPage(BaseModel):
    items: list[AuditEvent]
    total: int


def _filters(agent_id: str | None, tool: str | None, action: str | None, event_type: str | None,
             session_id: str | None, call_id: str | None, since: float | None, until: float | None,
             q: str | None) -> dict[str, Any]:
    raw = {"agent_id": agent_id, "tool": tool, "action": action, "event_type": event_type,
           "session_id": session_id, "call_id": call_id, "since": since, "until": until, "text": q}
    return {k: v for k, v in raw.items() if v not in (None, "")}


@router.get("/events", response_model=AuditPage)
def list_events(
    request: Request,
    agent_id: str | None = None, tool: str | None = None, action: str | None = None,
    event_type: str | None = None, session_id: str | None = None, call_id: str | None = None,
    since: float | None = Query(None, description="epoch seconds"),  # noqa: B008
    until: float | None = Query(None, description="epoch seconds"),  # noqa: B008
    q: str | None = Query(None, max_length=200, description="free-text search"),  # noqa: B008
    limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0),  # noqa: B008
    order: Literal["asc", "desc"] = "desc",
    _user=Depends(auditor),  # noqa: B008
) -> AuditPage:
    filters = _filters(agent_id, tool, action, event_type, session_id, call_id, since, until, q)
    items, total = get_components(request).audit.query(limit=limit, offset=offset, order=order, **filters)
    return AuditPage(items=items, total=total)


@router.get("/events/{seq}", response_model=AuditEvent, responses=ErrorResponses.NOT_FOUND)
def get_event(seq: int, request: Request, _user=Depends(auditor)) -> AuditEvent:  # noqa: B008
    event = get_components(request).audit.get(seq)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Audit event not found")
    return event


@router.post("/verify")
async def verify(request: Request, user=Depends(auditor)) -> Any:  # noqa: B008
    """Recompute the HMAC hash chain; returns the AuditVerifyReport (ok, checked, head_seq, ...)."""
    comps = get_components(request)
    report = await run_in_threadpool(comps.audit.verify)
    data = report.model_dump(mode="json") if hasattr(report, "model_dump") else dict(report)
    request.app.state.audit_verify_cache = (data.get("head_seq"), bool(data.get("ok")), time.time())
    await run_in_threadpool(comps.audit.append, "audit.verified",
                            payload={"by": user.username, "ok": data.get("ok"), "checked": data.get("checked"),
                                     "first_bad_seq": data.get("first_bad_seq")})
    return data


@router.post("/events/{seq}/replay", response_model=ReplayReport,
             responses={**ErrorResponses.NOT_FOUND, 400: {"description": "Event cannot be replayed"}})
async def replay(seq: int, request: Request, _user=Depends(auditor)) -> ReplayReport:  # noqa: B008
    gateway = request.app.state.gateway
    try:
        return await run_in_threadpool(gateway.replay, seq)
    except KeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Audit event not found") from exc
    except ReplayError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/export", response_class=Response,
            responses={200: {"content": {"application/json": {}, "text/csv": {}}}})
def export(
    request: Request,
    format: Literal["json", "csv"] = "json",  # noqa: A002 - public query parameter name
    agent_id: str | None = None, tool: str | None = None, action: str | None = None,
    event_type: str | None = None, session_id: str | None = None, call_id: str | None = None,
    since: float | None = None, until: float | None = None,
    q: str | None = Query(None, max_length=200),  # noqa: B008
    _user=Depends(auditor),  # noqa: B008
) -> Response:
    filters = _filters(agent_id, tool, action, event_type, session_id, call_id, since, until, q)
    body = get_components(request).audit.export(format, **filters)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    media = "application/json" if format == "json" else "text/csv; charset=utf-8"
    return Response(content=body, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="mirsad-audit-{stamp}.{format}"'})
