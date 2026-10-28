"""Agent registry (admin): API keys are returned exactly once, on create and rotate."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import Field

from mirsad.api.components import Components
from mirsad.api.deps import get_components, require_user
from mirsad.api.schemas import SLUG_PATTERN, AgentOut, AgentWithKey, ErrorResponses, Problem, StrictModel

log = logging.getLogger("mirsad.api")

router = APIRouter(prefix="/api/agents", tags=["agents"], responses=ErrorResponses.AUTH)
admin = require_user("admin")


class AgentCreate(StrictModel):
    id: str = Field(pattern=SLUG_PATTERN, description="Slug, e.g. `email-crm-assistant-prod`")
    name: str = Field(min_length=1, max_length=128)
    policy_agent_id: str = Field(min_length=1, max_length=64, description="Agent id in the policy YAML")
    description: str = Field(default="", max_length=1000)


class AgentPatch(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=1000)
    policy_agent_id: str | None = Field(default=None, min_length=1, max_length=64)
    disabled: bool | None = None


def _out(row: Any) -> AgentOut:
    return AgentOut(id=row.id, name=row.name, description=row.description or "", policy_agent_id=row.policy_agent_id,
                    key_prefix=row.key_prefix, created_at=row.created_at, disabled=bool(row.disabled),
                    last_seen_at=row.last_seen_at)


def _policy_warnings(request: Request, policy_agent_id: str) -> list[str]:
    try:
        known = list(request.app.state.gateway.policy.agent_ids())
    except Exception:
        return []
    if policy_agent_id not in known:
        return [f"policy agent '{policy_agent_id}' is not defined in the active policy; its calls will be denied"]
    return []


def _get_or_404(comps: Components, agent_id: str) -> Any:
    row = comps.auth.get_agent(comps.db, agent_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return row


@router.get("", response_model=list[AgentOut])
def list_agents(request: Request, _user=Depends(admin)) -> list[AgentOut]:  # noqa: B008
    comps = get_components(request)
    return [_out(a) for a in comps.auth.list_agents(comps.db)]


@router.post("", response_model=AgentWithKey, status_code=status.HTTP_201_CREATED,
             responses={409: {"model": Problem}})
def create_agent(body: AgentCreate, request: Request, user=Depends(admin)) -> AgentWithKey:  # noqa: B008
    comps = get_components(request)
    if comps.auth.get_agent(comps.db, body.id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Agent id already exists")
    try:
        _info, key = comps.auth.create_agent(comps.db, body.id, body.name, body.policy_agent_id,
                                             description=body.description)
    except ValueError as exc:
        code = status.HTTP_409_CONFLICT if "exists" in str(exc) else status.HTTP_422_UNPROCESSABLE_CONTENT
        raise HTTPException(code, detail=str(exc)) from exc
    request.app.state.gateway.agent_names.setdefault(body.policy_agent_id, body.name)
    comps.audit.append("agent.created", agent_id=body.policy_agent_id,
                       payload={"id": body.id, "name": body.name, "policy_agent_id": body.policy_agent_id,
                                "created_by": user.username})
    return AgentWithKey(agent=_out(_get_or_404(comps, body.id)), api_key=key,
                        warnings=_policy_warnings(request, body.policy_agent_id))


@router.post("/{agent_id}/rotate-key", response_model=AgentWithKey, responses=ErrorResponses.NOT_FOUND)
def rotate_key(agent_id: str, request: Request, user=Depends(admin)) -> AgentWithKey:  # noqa: B008
    comps = get_components(request)
    agent = _get_or_404(comps, agent_id)
    key = comps.auth.rotate_agent_key(comps.db, agent_id)
    comps.audit.append("agent.key_rotated", agent_id=agent.policy_agent_id,
                       payload={"id": agent_id, "rotated_by": user.username})
    return AgentWithKey(agent=_out(_get_or_404(comps, agent_id)), api_key=key)


@router.patch("/{agent_id}", response_model=AgentOut, responses=ErrorResponses.NOT_FOUND)
def update_agent(agent_id: str, body: AgentPatch, request: Request, user=Depends(admin)) -> AgentOut:  # noqa: B008
    comps = get_components(request)
    _get_or_404(comps, agent_id)
    changes = body.model_dump(exclude_none=True)
    updated = comps.auth.update_agent(comps.db, agent_id, **changes)
    comps.audit.append("agent.updated", agent_id=updated.policy_agent_id,
                       payload={"id": agent_id, "changes": changes, "updated_by": user.username})
    return _out(updated)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response,
               responses=ErrorResponses.NOT_FOUND)
def delete_agent(agent_id: str, request: Request, user=Depends(admin)) -> Response:  # noqa: B008
    comps = get_components(request)
    agent = _get_or_404(comps, agent_id)
    comps.auth.delete_agent(comps.db, agent_id)
    comps.audit.append("agent.deleted", agent_id=agent.policy_agent_id,
                       payload={"id": agent_id, "deleted_by": user.username})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
