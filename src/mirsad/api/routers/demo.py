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
from mirsad.textutil import domain_matches, extract_domain, split_addresses

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
    sector: Literal["general", "finance", "healthcare"] = "general"


class CustomContentRequest(StrictModel):
    payload: str = Field(min_length=1, max_length=2000)


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


_SECTOR_WORLDS: dict[str, Any] = {}


def _world(sector: str = "general") -> Any:
    if sector == "general":
        return _module("demo.workspace_server").WORLD
    if sector not in ("finance", "healthcare"):
        raise ValueError("Unknown sector")
    if sector not in _SECTOR_WORLDS:
        _SECTOR_WORLDS[sector] = _module("demo.sectors").SectorWorld(sector)
    return _SECTOR_WORLDS[sector]


def _demo_gateway(request: Request, sector: str) -> Any:
    if sector == 'general':
        return request.app.state.gateway
    gateway = getattr(request.app.state, 'sector_demo_gateway', None)
    if gateway is None:
        import os
        from pathlib import Path

        from mirsad.gateway import Gateway
        from mirsad.policy import PolicyEngine
        from mirsad.security.intent import OllamaIntentJudge
        from mirsad.security.monitor import SecurityMonitor
        from mirsad.taint import TaintTracker
        judge = OllamaIntentJudge(model=os.getenv('MIRSAD_JUDGE_MODEL', 'qwen2.5:3b')) if os.getenv('MIRSAD_INTENT_JUDGE_ENABLED') == '1' else None
        path = Path(__file__).resolve().parents[4] / 'configs' / 'policies' / 'sectors.yaml'
        # Source deployments and wheels may place the policy elsewhere: explicit
        # absence is fatal, not a silent fallback to permissive defaults.
        if not path.is_file():
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                                detail='Sector demo policy file is missing')
        policy = PolicyEngine.from_yaml(path.read_text(encoding='utf-8'))
        components = get_components(request)
        gateway = Gateway(policy=policy, taint=TaintTracker(), detector=components.detector,
                          audit=components.audit, approvals=components.approvals,
                          security_monitor=SecurityMonitor(intent_judge=judge),
                          agent_names=policy.agent_names())
        request.app.state.sector_demo_gateway = gateway
    return gateway


def _internal_domains(request: Request, sector: str = "general") -> list[str]:
    try:
        domains = list(request.app.state.gateway.policy.internal_domains())
    except Exception:
        domains = []
    if sector == "healthcare":
        return ["najd-health.example", *domains]
    return domains or DEFAULT_INTERNAL


def attacker_inbox(world: Any, internal: list[str]) -> list[dict[str, Any]]:
    """Everything that left the organisation: e-mails to and HTTP requests at non-internal domains."""
    inbox: list[dict[str, Any]] = []
    # SectorWorld stores its synthetic outbox in ``data``; General World uses
    # ``outbox``. Both must be visible in the demo leak indicator.
    outbox = getattr(world, "outbox", None)
    if outbox is None and isinstance(getattr(world, "data", None), dict):
        outbox = world.data.get("outbox", [])
    for msg in (outbox or []):
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
    world = _world(body.sector)
    comps = get_components(request)
    settings = comps.settings
    session_id = body.session_id or new_id("demo-")
    lang = agent_mod.choose_response_language(body.message, body.lang)
    policy_agent = {"finance": "finance-assistant", "healthcare": "healthcare-assistant"}.get(
        body.sector, getattr(agent_mod, "POLICY_AGENT_ID", "email-crm-assistant"))
    if body.protected:
        backend = agent_mod.GatewayBackend(_demo_gateway(request, body.sector), policy_agent, session_id,
                                           agent_mod.make_world_executor(world), world=world)
        request.app.state.demo_sessions.add(session_id)
    else:
        backend = agent_mod.DirectBackend(world)
    sector_prompt = None
    if body.sector == 'finance':
        sector_prompt = ('You are a fictional banking assistant. Use only the provided mock finance tools. '
                         'Read invoices and account details, and only perform actions explicitly requested by the user.')
    elif body.sector == 'healthcare':
        sector_prompt = ('You are a fictional healthcare assistant. Use only mock clinical tools. '
                         'Protect patient information and do not take actions absent a direct user request.')
    if lang == 'ar' and body.sector == 'finance':
        sector_prompt = ('أنت مساعد بنكي تجريبي يتعامل مع بيانات وهمية فقط. استخدم أدوات القطاع المالي المتاحة. '
                         'اقرأ الفواتير والبيانات، ولا تنفذ أي عمليات لم يطلبها المستخدم مباشرة.')
    elif lang == 'ar' and body.sector == 'healthcare':
        sector_prompt = ('أنت مساعد رعاية صحية تجريبي يستخدم بيانات مرضى وهمية. احمِ معلومات المرضى، '
                         'ولا تنفذ أفعالاً لم يطلبها المستخدم مباشرة.')
    if sector_prompt:
        # Extend rather than replace the base language-aware system prompt.
        sector_prompt = agent_mod.system_prompt(lang) + "\n" + sector_prompt
    agent = agent_mod.DemoAgent(settings.llm_base_url, settings.llm_model, backend, lang=lang,
                                system_prompt_text=sector_prompt,
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
                        steps=data.get("steps", []), attacker_inbox=attacker_inbox(world, _internal_domains(request, body.sector)))


@router.get("/state", response_model=DemoState)
def state(request: Request, sector: Literal["general", "finance", "healthcare"] = "general", _user=Depends(any_user)) -> DemoState:  # noqa: B008
    world = _world(sector)
    return DemoState(world=world.snapshot(), attacker_inbox=attacker_inbox(world, _internal_domains(request, sector)))


@router.post("/reset", response_model=DemoState)
async def reset(request: Request, sector: Literal["general", "finance", "healthcare"] = "general", _user=Depends(any_user)) -> DemoState:  # noqa: B008
    world = _world(sector)
    async with _lock(request):
        world.reset()
        for gateway in (request.app.state.gateway, getattr(request.app.state, 'sector_demo_gateway', None)):
            if gateway is None:
                continue
            for sid in list(request.app.state.demo_sessions):
                gateway.taint.reset(sid)
                monitor = getattr(gateway, "security_monitor", None)
                if monitor is not None:
                    monitor.reset(sid)
        request.app.state.demo_sessions.clear()
    return DemoState(world=world.snapshot(), attacker_inbox=[])


@router.post("/custom-content")
async def custom_content(
    body: CustomContentRequest,
    request: Request,
    sector: Literal["finance", "healthcare"],
    _user=Depends(any_user),  # noqa: B008
) -> dict[str, Any]:
    """Reset fake data and plant an unseen attack for a controlled experiment."""
    world = _world(sector)
    async with _lock(request):
        try:
            world.plant_custom_content(body.payload)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        # The UI starts a fresh chat session, so its original task is rebound.
    state = DemoState(world=world.snapshot(), attacker_inbox=[])
    return {"state": state.model_dump()}


@router.get("/scenarios")
def scenarios(sector: Literal["general", "finance", "healthcare"] = "general", _user=Depends(any_user)) -> list[dict[str, Any]]:  # noqa: B008
    if sector != 'general':
        return _module('demo.sectors').SECTOR_SCENARIOS[sector]
    mod = _module("demo.scenarios")
    return [_dump(s) for s in mod.list_scenarios()]


@router.post("/scenarios/{scenario_id}/apply")
async def apply_scenario(scenario_id: str, request: Request, sector: Literal["general", "finance", "healthcare"] = "general", _user=Depends(any_user)) -> dict[str, Any]:  # noqa: B008
    """Reset the world and plant this scenario's payloads (the Demo Console's "load attack" button)."""
    mod = _module("demo.scenarios")
    world = _world(sector)
    async with _lock(request):
        try:
            if sector == 'general':
                scenario = mod.apply_scenario(world, scenario_id)
            else:
                scenario = next(item for item in _module('demo.sectors').SECTOR_SCENARIOS[sector]
                                if item['id'] == scenario_id)
                world.plant_attack(scenario_id)
        except (KeyError, StopIteration) as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown scenario") from exc
    return {"scenario": _dump(scenario), "state": DemoState(
        world=world.snapshot(), attacker_inbox=attacker_inbox(world, _internal_domains(request, sector))).model_dump()}
