"""Agent-facing Guard API: check a tool call, inspect a tool result, or invoke a tool through Mirsad."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from mirsad.api.deps import get_components, require_agent
from mirsad.api.schemas import ErrorResponses, StrictModel
from mirsad.models import (
    Decision,
    GatewayResponse,
    InspectionOutcome,
    ToolCall,
    ToolProfile,
    ToolResult,
    new_id,
)

log = logging.getLogger("mirsad.api")

router = APIRouter(tags=["agent"], responses=ErrorResponses.AGENT)

_ID = r"^[A-Za-z0-9_.:@/+=-]{1,200}$"
_TOOL = r"^[A-Za-z0-9_.:/-]{1,128}$"
_TASK_MAX = 4_000


class ToolCallRequest(StrictModel):
    session_id: str = Field(pattern=_ID, description="Agent conversation/session id (taint is tracked per session)")
    tool: str = Field(pattern=_TOOL)
    arguments: dict[str, Any] = Field(default_factory=dict)
    call_id: str | None = Field(default=None, pattern=_ID)
    wait: bool = Field(default=True, description="Block until a human decides when approval is required")
    original_task: str | None = Field(
        default=None, min_length=1, max_length=_TASK_MAX,
        description="Original authenticated user task supplied by the trusted host; never copy this from tool output",
    )


class ToolResultRequest(StrictModel):
    session_id: str = Field(pattern=_ID)
    call_id: str = Field(pattern=_ID)
    tool: str = Field(pattern=_TOOL)
    content: Any = Field(description="Text, or any JSON value (then also used as `structured`)")
    structured: Any | None = None
    is_error: bool = False


class InvokeRequest(StrictModel):
    session_id: str = Field(pattern=_ID)
    arguments: dict[str, Any] = Field(default_factory=dict)
    call_id: str | None = Field(default=None, pattern=_ID)
    original_task: str | None = Field(
        default=None, min_length=1, max_length=_TASK_MAX,
        description="Original authenticated user task supplied by the trusted host; never copy this from tool output",
    )


class VisibleTool(BaseModel):
    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    profile: ToolProfile


def _bind_original_task(request: Request, agent: Any, session_id: str, original_task: str | None) -> None:
    """Bind trusted task context before evaluating a state-changing call.

    The field lives beside, not inside, tool arguments so retrieved/untrusted content
    cannot masquerade as the user's task. Agent authentication identifies the host
    responsible for supplying it; missing context continues to fail closed.
    """
    if original_task is None:
        return
    monitor = getattr(request.app.state.gateway, "security_monitor", None)
    if monitor is not None:
        monitor.bind_task(session_id, agent.policy_agent_id, original_task)


@router.post("/v1/guard/tool-call", response_model=Decision)
async def guard_tool_call(body: ToolCallRequest, request: Request, agent=Depends(require_agent)) -> Decision:  # noqa: B008
    _bind_original_task(request, agent, body.session_id, body.original_task)
    call = ToolCall(call_id=body.call_id or new_id("call_"), session_id=body.session_id,
                    agent_id=agent.policy_agent_id, tool=body.tool, arguments=body.arguments)
    return await request.app.state.gateway.check_call(call, wait_for_approval=body.wait)


@router.post("/v1/guard/tool-result", response_model=InspectionOutcome)
async def guard_tool_result(body: ToolResultRequest, request: Request,
                            agent=Depends(require_agent)) -> InspectionOutcome:  # noqa: B008
    content, structured = body.content, body.structured
    if not isinstance(content, str):
        if structured is None:
            structured = content
        content = json.dumps(content, ensure_ascii=False, default=str)
    elif structured is None:
        try:
            parsed = json.loads(content)
            structured = parsed if isinstance(parsed, (dict, list)) else None
        except ValueError:
            structured = None
    result = ToolResult(call_id=body.call_id, session_id=body.session_id, agent_id=agent.policy_agent_id,
                        tool=body.tool, content=content, structured=structured, is_error=body.is_error)
    return await request.app.state.gateway.inspect_result(result)


@router.post("/v1/tools/{tool}/invoke", response_model=GatewayResponse,
             responses={503: {"description": "No upstream tool runtime configured"}})
async def invoke_tool(tool: str, body: InvokeRequest, request: Request,
                      agent=Depends(require_agent)) -> GatewayResponse:  # noqa: B008
    upstreams = get_components(request).upstreams
    if upstreams is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="No upstream tool runtime configured")
    if len(tool) > 128:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Tool name too long")
    _bind_original_task(request, agent, body.session_id, body.original_task)
    call = ToolCall(call_id=body.call_id or new_id("call_"), session_id=body.session_id,
                    agent_id=agent.policy_agent_id, tool=tool, arguments=body.arguments)
    return await request.app.state.gateway.execute(call, upstreams.call)


async def visible_tools(request: Request, policy_agent_id: str) -> list[VisibleTool]:
    comps = get_components(request)
    if comps.upstreams is None:
        return []
    tools = await comps.upstreams.list_tools()
    policy = request.app.state.gateway.policy
    names = [t.name for t in tools]
    allowed = set(policy.visible_tools(policy_agent_id, names))
    return [VisibleTool(name=t.name, description=getattr(t, "description", "") or "",
                        input_schema=getattr(t, "input_schema", None) or {},
                        profile=policy.tool_profile(policy_agent_id, t.name))
            for t in tools if t.name in allowed]


@router.get("/v1/tools", response_model=list[VisibleTool])
async def list_visible_tools(request: Request, agent=Depends(require_agent)) -> list[VisibleTool]:  # noqa: B008
    return await visible_tools(request, agent.policy_agent_id)
