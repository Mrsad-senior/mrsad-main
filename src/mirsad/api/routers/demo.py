"""Demo Console endpoints (mounted only when ``settings.enable_demo``).

The protected agent runs through the app's own gateway in-process (``GatewayBackend``); the
unprotected agent calls the world directly (``DirectBackend``). Both share the world object of
``demo.workspace_server`` so the dashboard and the in-process MCP upstream see the same state.
``demo.*`` is imported lazily: it is optional at runtime.
"""

from __future__ import annotations

import asyncio
import importlib
import logging
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from mirsad.api.deps import get_components, require_user
from mirsad.api.schemas import ErrorResponses, StrictModel
from mirsad.gateway import principal_var
from mirsad.models import new_id
from mirsad.textutil import arabic_ratio, domain_matches, extract_domain, split_addresses

log = logging.getLogger("mirsad.api")

router = APIRouter(prefix="/api/demo", tags=["demo"], responses=ErrorResponses.AUTH)
any_user = require_user()

DEFAULT_INTERNAL = ["najd-trading.example"]
PREVIEW = 300


class ChatRequest(StrictModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.:-]{1,100}$")
    protected: bool = True
    lang: Literal["en", "ar"] | None = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    protected: bool
    stopped_reason: str = "completed"
    steps: list[dict[str, Any]]
    attacker_inbox: list[dict[str, Any]]


class DemoState(BaseModel):
    world: dict[str, Any]
    attacker_inbox: list[dict[str, Any]]


def _module(name: str) -> Any:
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Demo module {name} is unavailable") from exc


def _world() -> Any:
    return _module("demo.workspace_server").WORLD


def _internal_domains(request: Request) -> list[str]:
    try:
        domains = list(request.app.state.gateway.policy.internal_domains())
    except Exception:
        domains = []
    return domains or DEFAULT_INTERNAL


def attacker_inbox(world: Any, internal: list[str]) -> list[dict[str, Any]]:
    """Everything that left the organisation: e-mails to and HTTP requests at non-internal domains."""
    inbox: list[dict[str, Any]] = []
    for msg in getattr(world, "outbox", []):
        recipients = [*split_addresses(msg.get("to")), *split_addresses(msg.get("cc")), *split_addresses(msg.get("bcc"))]
        external = [r for r in recipients if (d := extract_domain(r)) and not domain_matches(d, internal)]
        if external:
            body = str(msg.get("body") or "")
            inbox.append({"channel": "email", "to": external, "subject": msg.get("subject"),
                          "body_preview": body[:PREVIEW], "body_chars": len(body), "ts": msg.get("ts")})
    for entry in getattr(world, "http_log", []):
        url = str(entry.get("url") or "")
        domain = extract_domain(url)
        if domain and not domain_matches(domain, internal):
            inbox.append({"channel": "http", "url": url, "domain": domain, "ts": entry.get("ts")})
    return sorted(inbox, key=lambda e: e.get("ts") or 0)


def _lock(request: Request) -> asyncio.Lock:
    lock = getattr(request.app.state, "demo_lock", None)
    if lock is None:
        lock = request.app.state.demo_lock = asyncio.Lock()
    return lock


def _dump(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return dict(value)


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, request: Request, user=Depends(any_user)) -> ChatResponse:  # noqa: B008
    agent_mod = _module("demo.agent")
    world = _world()
    comps = get_components(request)
    settings = comps.settings
    session_id = body.session_id or new_id("demo-")
    lang = body.lang or ("ar" if arabic_ratio(body.message) > 0.3 else "en")
    policy_agent = getattr(agent_mod, "POLICY_AGENT_ID", "email-crm-assistant")
    if body.protected:
        backend = agent_mod.GatewayBackend(request.app.state.gateway, policy_agent, session_id,
                                           agent_mod.make_world_executor(world))
        request.app.state.demo_sessions.add(session_id)
    else:
        backend = agent_mod.DirectBackend(world)
    agent = agent_mod.DemoAgent(settings.llm_base_url, settings.llm_model, backend, lang=lang,
                                api_key=settings.llm_api_key, session_id=session_id)
    principal_var.set(f"demo:{user.username}")
    async with _lock(request):  # one simulated world: serialise demo runs
        try:
            transcript = await agent.run(body.message)
        except httpx.HTTPError as exc:
            log.warning("demo LLM call failed: %s", type(exc).__name__)
            raise HTTPException(status.HTTP_502_BAD_GATEWAY,
                                detail=f"The demo LLM at {settings.llm_base_url} is unavailable") from exc
    data = _dump(transcript)
    return ChatResponse(reply=data.get("reply", ""), session_id=data.get("session_id", session_id),
                        protected=body.protected, stopped_reason=data.get("stopped_reason", "completed"),
                        steps=data.get("steps", []), attacker_inbox=attacker_inbox(world, _internal_domains(request)))


@router.get("/state", response_model=DemoState)
def state(request: Request, _user=Depends(any_user)) -> DemoState:  # noqa: B008
    world = _world()
    return DemoState(world=world.snapshot(), attacker_inbox=attacker_inbox(world, _internal_domains(request)))


@router.post("/reset", response_model=DemoState)
async def reset(request: Request, _user=Depends(any_user)) -> DemoState:  # noqa: B008
    world = _world()
    async with _lock(request):
        world.reset()
        taint = get_components(request).taint
        for sid in list(request.app.state.demo_sessions):
            taint.reset(sid)
        request.app.state.demo_sessions.clear()
    return DemoState(world=world.snapshot(), attacker_inbox=[])


@router.get("/scenarios")
def scenarios(_user=Depends(any_user)) -> list[dict[str, Any]]:  # noqa: B008
    mod = _module("demo.scenarios")
    return [_dump(s) for s in mod.list_scenarios()]


@router.post("/scenarios/{scenario_id}/apply")
async def apply_scenario(scenario_id: str, request: Request, _user=Depends(any_user)) -> dict[str, Any]:  # noqa: B008
    """Reset the world and plant this scenario's payloads (the Demo Console's "load attack" button)."""
    mod = _module("demo.scenarios")
    world = _world()
    async with _lock(request):
        try:
            scenario = mod.apply_scenario(world, scenario_id)
        except KeyError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown scenario") from exc
    return {"scenario": _dump(scenario), "state": DemoState(
        world=world.snapshot(), attacker_inbox=attacker_inbox(world, _internal_domains(request))).model_dump()}
