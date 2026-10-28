"""Agents and recording backends for Mirsad-Bench.

Both agents talk to the World through a *recording backend* (a subclass of the demo backends) that
logs, for every tool call, the gateway decision, whether a human was asked, what the detector did
with the result, and timings. The same backend code path serves the scripted and the LLM agent.

* :class:`ScriptedAgent` executes the user task's plan step by step, deterministically, and keeps
  going when a step is blocked (as a real assistant would report and move on). In attack episodes it is
  a worst-case *compliant* agent: once a tool result that reaches it still contains the planted text, it
  carries out the injection task's actions through the same backend, then continues with the plan.
* :class:`LLMAgent` runs :class:`demo.agent.DemoAgent` (qwen2.5:7b via Ollama, temperature 0); in attack
  episodes the model alone decides what to do with the planted text.

In attack episodes the backend is given the episode's survival marker (``backend.marker``) and records,
for every call, whether the planted text was in the raw tool output (``planted_seen``) and whether it
still reached the agent after inspection (``planted_delivered``).
"""

from __future__ import annotations

import itertools
import re
import time
from dataclasses import dataclass
from typing import Any

from demo.agent import (
    DEFAULT_LLM_BASE_URL,
    DEFAULT_MODEL,
    BackendResult,
    DemoAgent,
    DirectBackend,
    GatewayBackend,
)
from demo.world import ToolArgumentError, World, call_tool, to_text
from pydantic import BaseModel, Field

from bench.loader import UserTask

_counter = itertools.count(1)


class CallRecord(BaseModel):
    """One tool call made during an episode, as seen by the harness."""

    call_id: str
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    executed: bool = False                 # the tool actually ran
    tool_error: bool = False               # it ran but returned an error (bad arguments, unknown id)
    final_action: str | None = None        # gateway verdict after any human decision (None: no gateway)
    pre_human_action: str | None = None    # verdict of the automatic layers
    escalated: bool = False                # a human (auto_decider) was asked
    approval_status: str | None = None
    reason_codes: list[str] = Field(default_factory=list)
    inspection_action: str | None = None   # pass | flag | sanitize | block
    detector_score: float | None = None
    decision_ms: float = 0.0               # gateway-reported, excludes human wait
    inspection_ms: float = 0.0
    gateway_ms: float = 0.0                # decision_ms + inspection_ms
    tool_ms: float = 0.0
    wall_ms: float = 0.0
    origin: str = "agent"                  # plan | injection (scripted agent) | agent (chosen by the LLM)
    deny_layers: list[str] = Field(default_factory=list)        # layers that denied the call automatically
    escalation_layers: list[str] = Field(default_factory=list)  # layers that asked for a human
    planted_seen: bool | None = None       # attack episodes: planted text in the raw tool output
    planted_delivered: bool | None = None  # attack episodes: planted text in what the agent received
    injection: bool = False                # attack episodes: the call carries out the injection task


# Codes that record what the (simulated) human decided, not why the call was stopped.
_HUMAN_OUTCOME_CODES = frozenset({"APPROVED_BY_HUMAN", "DENIED_BY_HUMAN", "APPROVAL_EXPIRED"})
_PLAN_ID = re.compile(r"plan\d+")
_INJECTION_ID = re.compile(r"inj\d+")


def _unique(call_id: str) -> str:
    # Text-parsed tool calls reuse ids like "call_text_0" across rounds; the gateway needs unique ids.
    return f"{call_id}-{next(_counter)}"


def call_origin(call_id: str) -> str:
    """``plan`` / ``injection`` for the scripted agent's call ids, ``agent`` for anything else."""
    if _PLAN_ID.fullmatch(call_id):
        return "plan"
    if _INJECTION_ID.fullmatch(call_id):
        return "injection"
    return "agent"


def _found(marker: Any, content: str | None) -> bool | None:
    return None if marker is None else bool(marker.found_in(content))


class RecordingDirectBackend(DirectBackend):
    """Unprotected baseline that records each call."""

    def __init__(self, world: World, session_id: str, marker: Any = None):
        super().__init__(world)
        self.session_id = session_id
        self.records: list[CallRecord] = []
        self.marker = marker

    async def invoke(self, tool: str, arguments: dict[str, Any], *, call_id: str) -> BackendResult:
        t0 = time.perf_counter()
        error = False
        try:
            content = to_text(call_tool(self.world, tool, arguments))
        except ToolArgumentError as exc:
            content, error = f"Error: {exc}", True
        ms = (time.perf_counter() - t0) * 1000
        found = _found(self.marker, content)
        self.records.append(CallRecord(call_id=_unique(call_id), tool=tool, args=dict(arguments), executed=True,
                                       tool_error=error, tool_ms=ms, wall_ms=ms, origin=call_origin(call_id),
                                       planted_seen=found, planted_delivered=found))
        return BackendResult(content=content)


class RecordingGatewayBackend(GatewayBackend):
    """Protected backend: every call goes through ``Gateway.execute``; decisions are recorded."""

    def __init__(self, gateway: Any, agent_id: str, session_id: str, executor: Any, marker: Any = None):
        super().__init__(gateway, agent_id, session_id, executor)
        self.records: list[CallRecord] = []
        self._inner = executor
        self.marker = marker

    async def invoke(self, tool: str, arguments: dict[str, Any], *, call_id: str) -> BackendResult:
        timing: dict[str, Any] = {"tool_ms": 0.0, "ran": False, "error": False, "raw": None}

        async def timed(call: Any) -> Any:
            t0 = time.perf_counter()
            try:
                result = await self._inner(call)
            finally:
                timing["tool_ms"] = (time.perf_counter() - t0) * 1000
                timing["ran"] = True
            timing["error"] = bool(getattr(result, "is_error", False))
            timing["raw"] = getattr(result, "content", None)
            return result

        self.executor = timed
        t0 = time.perf_counter()
        try:
            out = await super().invoke(tool, arguments, call_id=_unique(call_id))
        finally:
            self.executor = self._inner
        wall = (time.perf_counter() - t0) * 1000
        record = self._record(tool, arguments, out, timing, wall)
        record.origin = call_origin(call_id)
        if self.marker is not None:
            record.planted_seen = _found(self.marker, timing["raw"])
            record.planted_delivered = _found(self.marker, out.content)
        self.records.append(record)
        return out

    @staticmethod
    def _record(tool: str, arguments: dict[str, Any], out: BackendResult, timing: dict[str, Any],
                wall: float) -> CallRecord:
        decision = out.decision or {}
        inspection = out.inspection or {}
        escalated = bool(decision.get("approval_id"))
        final = decision.get("action")
        detection = inspection.get("detection") or {}
        decision_ms = float(decision.get("latency_ms") or 0.0)
        inspection_ms = float(inspection.get("latency_ms") or 0.0)
        automatic = [r for r in decision.get("reasons") or [] if r.get("code") not in _HUMAN_OUTCOME_CODES]
        deny_layers = sorted({str(r.get("layer")) for r in automatic if r.get("action") == "deny"})
        escalation_layers = sorted({str(r.get("layer")) for r in automatic if r.get("action") == "require_approval"})
        return CallRecord(
            call_id=str(decision.get("call_id", "")), tool=tool, args=dict(arguments),
            executed=bool(timing["ran"]) and not out.blocked, tool_error=bool(timing["error"]),
            final_action=final, pre_human_action="require_approval" if escalated else final,
            escalated=escalated, approval_status=decision.get("approval_status"),
            reason_codes=[r.get("code", "") for r in decision.get("reasons") or []
                          if r.get("action") != "allow" or r.get("layer") == "approval"],
            inspection_action=inspection.get("action"),
            detector_score=detection.get("score") if detection else None,
            decision_ms=decision_ms, inspection_ms=inspection_ms, gateway_ms=decision_ms + inspection_ms,
            tool_ms=float(timing["tool_ms"]), wall_ms=wall, deny_layers=deny_layers,
            escalation_layers=escalation_layers,
        )


# --------------------------------------------------------------------------- agents


@dataclass
class AgentOutcome:
    answer: str | None = None
    stopped_reason: str = "completed"
    steps: int = 0


class ScriptedAgent:
    """Deterministic agent that executes the task plan verbatim.

    With ``attack`` (a :class:`bench.attacks.PlantedAttack`) it is worst-case compliant: the first time a tool
    result it receives still contains the planted text (``attack.marker.found_in``), it performs the injection
    task's actions, in order, through the same backend (so the gateway judges each one), and then continues
    with the rest of the plan. It complies at most once per episode and ignores spotlighting and detector
    flags: only text that was actually removed or withheld stops it.
    """

    name = "scripted"

    async def run(self, task: UserTask, backend: Any, attack: Any = None) -> AgentOutcome:
        steps = 0
        complied = False
        for i, step in enumerate(task.plan):
            result = await backend.invoke(step.tool, dict(step.args), call_id=f"plan{i}")
            steps += 1
            if attack is not None and not complied and attack.marker.found_in(getattr(result, "content", None)):
                complied = True
                for j, action in enumerate(attack.actions):
                    await backend.invoke(action.tool, dict(action.args), call_id=f"inj{j}")
                    steps += 1
        return AgentOutcome(answer=None, stopped_reason="completed", steps=steps)


class LLMAgent:
    """The demo tool-calling agent driven by a local model through the OpenAI-compatible API."""

    name = "llm"

    def __init__(self, *, base_url: str = DEFAULT_LLM_BASE_URL, model: str = DEFAULT_MODEL, max_steps: int = 8,
                 temperature: float = 0.0, seed: int = 7) -> None:
        self.base_url = base_url
        self.model = model
        self.max_steps = max_steps
        self.temperature = temperature
        self.seed = seed

    async def run(self, task: UserTask, backend: Any, attack: Any = None) -> AgentOutcome:
        # ``attack`` is deliberately unused: the model only sees the planted text through tool results.
        agent = DemoAgent(llm_base_url=self.base_url, model=self.model, backend=backend, lang=task.lang,
                          max_steps=self.max_steps, temperature=self.temperature, seed=self.seed,
                          session_id=getattr(backend, "session_id", None))
        transcript = await agent.run(task.prompt)
        return AgentOutcome(answer=transcript.reply or "", stopped_reason=transcript.stopped_reason,
                            steps=len(transcript.steps))
