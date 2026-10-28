"""Discovered upstream tools and their resolved policy profile per agent (admin/auditor)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from mirsad.api.deps import get_components, require_user
from mirsad.api.schemas import ErrorResponses
from mirsad.models import ToolProfile

log = logging.getLogger("mirsad.api")

router = APIRouter(prefix="/api/tools", tags=["tools"], responses=ErrorResponses.AUTH)


class ToolInfo(BaseModel):
    name: str
    description: str = ""
    upstream: str | None = None
    input_schema: dict[str, Any] = Field(default_factory=dict)
    profiles: dict[str, ToolProfile] = Field(default_factory=dict, description="policy agent id -> profile")


@router.get("", response_model=list[ToolInfo])
async def list_tools(request: Request, _user=Depends(require_user("admin", "auditor"))) -> list[ToolInfo]:  # noqa: B008
    comps = get_components(request)
    if comps.upstreams is None:
        return []
    try:
        tools = await comps.upstreams.list_tools()
    except Exception:
        log.exception("listing upstream tools failed")
        tools = []
    policy = request.app.state.gateway.policy
    agent_ids = list(policy.agent_ids())
    return [ToolInfo(name=t.name, description=getattr(t, "description", "") or "",
                     upstream=getattr(t, "upstream", None), input_schema=getattr(t, "input_schema", None) or {},
                     profiles={a: policy.tool_profile(a, t.name) for a in agent_ids})
            for t in tools]
