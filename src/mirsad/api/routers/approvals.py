"""Human-in-the-loop approval queue for approvers and admins."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BeforeValidator, Field
from starlette.concurrency import run_in_threadpool

from mirsad.api.deps import get_components, require_user
from mirsad.api.schemas import ErrorResponses, Problem, StrictModel
from mirsad.models import ApprovalRecord, ApprovalStatus

log = logging.getLogger("mirsad.api")

router = APIRouter(prefix="/api/approvals", tags=["approvals"], responses=ErrorResponses.AUTH)
approver = require_user("approver", "admin")


# ``?status=`` (empty, as in the spec's ``status=&limit=``) means "any status".
StatusFilter = Annotated[ApprovalStatus | None, BeforeValidator(lambda v: v or None),
                         Query(alias="status", description="pending | approved | denied | expired | cancelled; "
                                                           "empty or omitted = any")]


class DecisionRequest(StrictModel):
    approve: bool
    note: str | None = Field(default=None, max_length=2000)


@router.get("", response_model=list[ApprovalRecord])
def list_approvals(request: Request, status_: StatusFilter = None,
                   limit: int = Query(100, ge=1, le=1000), _user=Depends(approver)) -> list[ApprovalRecord]:  # noqa: B008
    return get_components(request).approvals.list(status=status_, limit=limit)


@router.get("/{approval_id}", response_model=ApprovalRecord, responses=ErrorResponses.NOT_FOUND)
def get_approval(approval_id: str, request: Request, _user=Depends(approver)) -> ApprovalRecord:  # noqa: B008
    record = get_components(request).approvals.get(approval_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Approval not found")
    return record


@router.post("/{approval_id}/decision", response_model=ApprovalRecord,
             responses={**ErrorResponses.NOT_FOUND, 409: {"model": Problem, "description": "Already decided/expired"}})
async def decide(approval_id: str, body: DecisionRequest, request: Request,
                 user=Depends(approver)) -> ApprovalRecord:  # noqa: B008
    comps = get_components(request)
    if comps.approvals.get(approval_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Approval not found")
    # The gateway audits the outcome of approvals it is waiting on; orphaned ones are audited here.
    gateway_waiting = request.app.state.gateway.is_waiting_for(approval_id)
    try:
        record = await comps.approvals.decide(approval_id, approve=body.approve, user=user.username, note=body.note)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc) or "Approval already decided") from exc
    except KeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Approval not found") from exc
    if not gateway_waiting:
        await run_in_threadpool(
            comps.audit.append, "approval.decided", session_id=record.session_id, agent_id=record.agent_id,
            tool=record.tool, call_id=record.call_id, action="allow" if body.approve else "deny",
            risk=record.risk.value, payload={"approval_id": record.id, "status": record.status.value,
                                             "decided_by": user.username, "note": body.note, "source": "api"})
    return record
