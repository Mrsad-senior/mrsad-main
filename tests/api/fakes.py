"""Small, deterministic stand-ins for other areas' components (policy, taint, detector, audit, approvals).

They implement just enough of the BUILD_SPEC interfaces for the gateway/API tests to be meaningful
while those areas evolve independently.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import re
import threading
import time
from types import SimpleNamespace
from typing import Any

import yaml
from pydantic import BaseModel, Field

from mirsad.models import (
    Action,
    ApprovalRecord,
    ApprovalStatus,
    AuditEvent,
    DetectionResult,
    DetectionSpan,
    Reason,
    Risk,
    SessionSnapshot,
    SinkKind,
    ToolCall,
    ToolProfile,
    Trust,
    new_id,
)

RISK_SCORES = {"low": 0.1, "medium": 0.3, "high": 0.6, "critical": 0.9}

TEST_POLICY = """\
version: 1
organization:
  name: Test Org
  internal_domains: [najd-trading.example]
defaults:
  decision: deny
  approval_timeout_s: 30
detector:
  flag_threshold: 0.5
  block_threshold: 0.8
  on_detect: sanitize
  spotlight: true
taint:
  enabled: true
  destination_params: [to, url]
  trusted_fields: [id, from]
  untrusted_to_external_sink: require_approval
  confidential_to_external_sink: require_approval
  untrusted_controls_destination: deny
  after_injection_high_risk: require_approval
agents:
  - id: test-agent
    name: Test Agent
    tools:
      echo: {allow: true, risk: low, approval: never}
      read_inbox: {allow: true, trust: untrusted, scan: true, approval: never}
      read_secret: {allow: true, sensitivity: confidential, approval: never}
      wipe_disk: {allow: true, risk: critical, approval: always}
      block_reader: {allow: true, trust: untrusted, scan: true, approval: never, detector: {on_detect: block}}
      post_external: {allow: true, sink: external, risk: medium}
      "*": {allow: false}
"""


def policy_text(mode: str = "enforce", extra_tools: str = "") -> str:
    text = TEST_POLICY if mode == "enforce" else TEST_POLICY.replace("version: 1\n", f"version: 1\nmode: {mode}\n", 1)
    if extra_tools:
        text = text.replace('      "*": {allow: false}\n', extra_tools + '      "*": {allow: false}\n')
    return text


# --------------------------------------------------------------------------- policy


class FakeDetectorSettings(BaseModel):
    flag_threshold: float = 0.5
    block_threshold: float = 0.8
    on_detect: str = "sanitize"
    spotlight: bool = True


class FakeTaintSettings(BaseModel):
    enabled: bool = True
    destination_params: list[str] = Field(default_factory=list)
    trusted_fields: list[str] = Field(default_factory=list)
    untrusted_to_external_sink: Action = Action.REQUIRE_APPROVAL
    confidential_to_external_sink: Action = Action.REQUIRE_APPROVAL
    untrusted_controls_destination: Action = Action.DENY
    after_injection_high_risk: Action = Action.REQUIRE_APPROVAL


class FakeEvaluation(BaseModel):
    reasons: list[Reason]
    profile: ToolProfile
    sink: SinkKind
    rate_counts: dict[str, int] = Field(default_factory=dict)


class FakeRateLimiter:
    pass


class FakePolicyEngine:
    """Subset of PolicyEngine: allow/deny, trust/sensitivity/sink/risk/approval/scan, detector overrides, mode."""

    def __init__(self, data: dict[str, Any], yaml_text: str, *, rate_limiter: Any = None) -> None:
        self.data = data
        self.yaml_text = yaml_text
        self.version = hashlib.sha256(yaml_text.encode()).hexdigest()
        self.rate_limiter = rate_limiter or FakeRateLimiter()
        self.document = SimpleNamespace(agents=[SimpleNamespace(id=a["id"], name=a.get("name"))
                                                for a in data.get("agents", [])])
        self.fail_with: Exception | None = None
        self.evaluations = 0

    @classmethod
    def from_yaml(cls, text: str, *, rate_limiter: Any = None) -> FakePolicyEngine:
        data = yaml.safe_load(text)
        if not isinstance(data, dict) or data.get("version") != 1:
            raise ValueError("policy must be a mapping with version: 1")
        return cls(data, text, rate_limiter=rate_limiter)

    @property
    def mode(self) -> str:
        return self.data.get("mode", "enforce")

    @property
    def approval_timeout_s(self) -> float:
        return float(self.data.get("defaults", {}).get("approval_timeout_s", 120))

    def _agent(self, agent_id: str) -> dict[str, Any] | None:
        return next((a for a in self.data.get("agents", []) if a["id"] == agent_id), None)

    def agent_ids(self) -> list[str]:
        return [a["id"] for a in self.data.get("agents", [])]

    def agent_names(self) -> dict[str, str]:
        return {a["id"]: a.get("name", a["id"]) for a in self.data.get("agents", [])}

    def internal_domains(self) -> list[str]:
        return list(self.data.get("organization", {}).get("internal_domains", []))

    def _entry(self, agent_id: str, tool: str) -> tuple[str | None, dict[str, Any]]:
        agent = self._agent(agent_id)
        if agent is None:
            return None, {}
        tools = agent.get("tools", {})
        if tool in tools:
            return tool, tools[tool]
        if "*" in tools:
            return "*", tools["*"]
        return None, {}

    def tool_profile(self, agent_id: str, tool: str) -> ToolProfile:
        key, e = self._entry(agent_id, tool)
        trust = e.get("trust", "trusted")
        return ToolProfile(tool=tool, allowed=bool(e.get("allow", False)), trust=trust,
                           sensitivity=e.get("sensitivity", "internal"), sink=e.get("sink", "none"),
                           risk=e.get("risk", "low"), approval=e.get("approval", "on_risk"),
                           scan=bool(e.get("scan", trust == "untrusted")), matched_rule=key)

    def visible_tools(self, agent_id: str, tools: list[str]) -> list[str]:
        return [t for t in tools if self.tool_profile(agent_id, t).allowed]

    def detector_settings(self, agent_id: str, tool: str) -> FakeDetectorSettings:
        base = dict(self.data.get("detector", {}))
        base.update(self._entry(agent_id, tool)[1].get("detector", {}))
        return FakeDetectorSettings(**base)

    def taint_settings(self, agent_id: str) -> FakeTaintSettings:
        return FakeTaintSettings(**self.data.get("taint", {}))

    def resolve_sink(self, call: ToolCall, profile: ToolProfile) -> SinkKind:
        return SinkKind(profile.sink) if profile.sink != "dynamic" else SinkKind.EXTERNAL

    def evaluate_call(self, call: ToolCall, *, now: float | None = None, rate_counts: dict[str, int] | None = None,
                      session_tainted: bool = False) -> FakeEvaluation:
        self.evaluations += 1
        if self.fail_with is not None:
            raise self.fail_with
        profile = self.tool_profile(call.agent_id, call.tool)
        sink = self.resolve_sink(call, profile)
        if self._agent(call.agent_id) is None:
            return FakeEvaluation(reasons=[Reason(layer="policy", code="UNKNOWN_AGENT", message="unknown agent",
                                                  action=Action.DENY, risk_score=0.5)], profile=profile, sink=sink)
        if not profile.allowed:
            return FakeEvaluation(reasons=[Reason(layer="policy", code="TOOL_NOT_ALLOWED", message="not allowed",
                                                  message_ar="غير مسموح", action=Action.DENY, risk_score=0.5)],
                                  profile=profile, sink=sink)
        score = RISK_SCORES[profile.risk.value]
        reasons = [Reason(layer="policy", code="TOOL_RISK", message="risk", action=Action.ALLOW, risk_score=score)]
        if profile.approval == "always":
            reasons.append(Reason(layer="policy", code="APPROVAL_ALWAYS", message="approval always",
                                  action=Action.REQUIRE_APPROVAL, risk_score=score))
        return FakeEvaluation(reasons=reasons, profile=profile, sink=sink)

    def approval_required(self, profile: ToolProfile, risk_score: float, taint_fired: bool) -> bool:
        if profile.approval == "never":
            return False
        if profile.approval == "always":
            return True
        return risk_score >= 0.6 or (profile.risk.rank >= Risk.HIGH.rank and taint_fired)


def fake_validate_policy(text: str) -> list[str]:
    try:
        FakePolicyEngine.from_yaml(text)
    except Exception as exc:
        return [str(exc)]
    return []


FAKE_POLICY_MODULE = SimpleNamespace(PolicyEngine=FakePolicyEngine, validate_policy=fake_validate_policy)


# --------------------------------------------------------------------------- detector

# Neutral placeholders (no attack text in the repository): the fake detector scores them as an
# injection / a suspicious phrase. Matching is case-insensitive.
INJECTION_MARKERS = ("sample-flagged-text", "نص-عينة-مشبوه")
SUSPICIOUS_MARKER = "sample-suspicious-text"


class FakeDetector:
    version = "fake-detector-1"

    def __init__(self) -> None:
        self.calls = 0
        self.fail = False

    def scan(self, text: str) -> DetectionResult:
        self.calls += 1
        if self.fail:
            raise RuntimeError("model file corrupt")
        low = text.lower()
        spans = []
        for marker in INJECTION_MARKERS:
            idx = low.find(marker)
            if idx >= 0:
                spans.append(DetectionSpan(start=idx, end=idx + len(marker), text=text[idx: idx + len(marker)]))
        if spans:
            score = 0.95
        elif SUSPICIOUS_MARKER in low:
            idx = low.find(SUSPICIOUS_MARKER)
            spans.append(DetectionSpan(start=idx, end=idx + len(SUSPICIOUS_MARKER), text=SUSPICIOUS_MARKER))
            score = 0.6
        else:
            score = 0.02
        label = "injection" if score >= 0.8 else "suspicious" if score >= 0.5 else "benign"
        return DetectionResult(score=score, label=label, language="en", spans=spans)

    def scan_structured(self, value: Any) -> DetectionResult:
        strings: list[str] = []

        def walk(v: Any) -> None:
            if isinstance(v, str):
                strings.append(v)
            elif isinstance(v, dict):
                for x in v.values():
                    walk(x)
            elif isinstance(v, list):
                for x in v:
                    walk(x)

        walk(value)
        results = [self.scan(s) for s in strings] or [self.scan("")]
        return max(results, key=lambda r: r.score)


def fake_sanitize(text: str, detection: DetectionResult, *, mode: str) -> str:
    if mode == "block":
        return "[BLOCKED BY MIRSAD]"
    out = text
    for span in sorted(detection.spans, key=lambda s: -s.start):
        out = out[: span.start] + "[REMOVED]" + out[span.end:]
    return out


def fake_spotlight(text: str, *, source: str, call_id: str) -> str:
    return f"<<untrusted source={source} id={call_id}>>{text}<</untrusted>>"


# --------------------------------------------------------------------------- taint


class FakeTaint:
    """Session taint: untrusted results taint the session; tainted + external sink -> reason."""

    def __init__(self) -> None:
        self.sessions: dict[tuple[str, str], SessionSnapshot] = {}
        self.notes = 0
        self.lock = threading.Lock()

    def snapshot(self, session_id: str, agent_id: str) -> SessionSnapshot:
        snap = self.sessions.setdefault((agent_id, session_id), SessionSnapshot(session_id=session_id,
                                                                                  agent_id=agent_id))
        return snap.model_copy(deep=True)

    def register_result(self, result: Any, profile: ToolProfile, detection: Any, settings: Any) -> SessionSnapshot:
        snap = self.sessions.setdefault((result.agent_id, result.session_id),
                                        SessionSnapshot(session_id=result.session_id, agent_id=result.agent_id))
        if profile.trust == Trust.UNTRUSTED or (detection is not None and detection.label == "injection"):
            snap.untrusted_sources.append(f"{result.tool}:{result.call_id}")
        if detection is not None and detection.label == "injection":
            snap.injection_detected = True
        return snap.model_copy(deep=True)

    def evaluate_call(self, call: ToolCall, profile: ToolProfile, sink: SinkKind, settings: Any,
                      snapshot: SessionSnapshot | None = None) -> list[Reason]:
        snap = snapshot or self.sessions.get((call.agent_id, call.session_id))
        if snap is not None and snap.tainted and sink == SinkKind.EXTERNAL:
            return [Reason(layer="taint", code="TAINT_UNTRUSTED_TO_EXTERNAL", message="untrusted -> external",
                           action=Action(settings.untrusted_to_external_sink), risk_score=0.6,
                           evidence={"sources": list(snap.untrusted_sources)})]
        return []

    def note_call(self, call: ToolCall) -> None:
        self.notes += 1

    def reset(self, session_id: str | None = None) -> None:
        self.sessions = {k: v for k, v in self.sessions.items() if session_id is not None and k[1] != session_id}


# --------------------------------------------------------------------------- audit


class FakeAudit:
    """In-memory HMAC hash chain (same algorithm family as the real AuditLog)."""

    def __init__(self, key: bytes = b"k") -> None:
        self.key = key
        self.events: list[AuditEvent] = []
        self.lock = threading.Lock()
        self.fail = False

    def _hash(self, prev: str, body: dict[str, Any]) -> str:
        data = prev + "|" + json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
        return hmac.new(self.key, data.encode(), hashlib.sha256).hexdigest()

    def append(self, event_type: str, *, session_id=None, agent_id=None, tool=None, call_id=None, action=None,
               risk=None, policy_version=None, payload=None) -> AuditEvent:
        if self.fail:
            raise RuntimeError("database is locked")
        with self.lock:
            prev = self.events[-1].hash if self.events else "0" * 64
            body = {"seq": len(self.events) + 1, "ts": time.time(), "event_type": event_type,
                    "session_id": session_id, "agent_id": agent_id, "tool": tool, "call_id": call_id,
                    "action": getattr(action, "value", action), "risk": getattr(risk, "value", risk),
                    "policy_version": policy_version,
                    "payload": json.loads(json.dumps(payload or {}, default=str)), "prev_hash": prev}
            event = AuditEvent(**body, hash=self._hash(prev, body))
            self.events.append(event)
            return event

    def get(self, seq: int) -> AuditEvent | None:
        return self.events[seq - 1] if 0 < seq <= len(self.events) else None

    def head(self) -> tuple[int, str]:
        return (len(self.events), self.events[-1].hash if self.events else "0" * 64)

    def by_type(self, event_type: str) -> list[AuditEvent]:
        return [e for e in self.events if e.event_type == event_type]

    def verify(self) -> SimpleNamespace:
        prev = "0" * 64
        for e in self.events:
            body = e.model_dump(exclude={"hash"})
            if e.prev_hash != prev or self._hash(prev, body) != e.hash:
                return SimpleNamespace(ok=False, checked=e.seq - 1, first_bad_seq=e.seq)
            prev = e.hash
        return SimpleNamespace(ok=True, checked=len(self.events), first_bad_seq=None)

    def query(self, *, limit: int = 100, order: str = "desc", **filters: Any) -> tuple[list[AuditEvent], int]:
        items = [e for e in self.events if all(getattr(e, k) == v for k, v in filters.items() if v is not None)]
        if order == "desc":
            items = items[::-1]
        return items[:limit], len(items)


# --------------------------------------------------------------------------- approvals


class FakeApprovals:
    """In-memory approval workflow with the spec semantics (decide twice -> ValueError, timeout -> EXPIRED)."""

    def __init__(self, *, timeout_s: float = 30.0, auto: bool | None = None) -> None:
        self.timeout_s = timeout_s
        self.auto = auto
        self.records: dict[str, ApprovalRecord] = {}
        self.events: dict[str, asyncio.Event] = {}
        self.requested: list[str] = []
        self.fail = False

    async def request(self, call: ToolCall, decision: Any, *, agent_name: str) -> ApprovalRecord:
        if self.fail:
            raise RuntimeError("approvals DB unavailable")
        now = time.time()
        record = ApprovalRecord(id=new_id("apr_"), created_at=now, expires_at=now + self.timeout_s,
                                agent_id=call.agent_id, session_id=call.session_id, call_id=call.call_id,
                                tool=call.tool, arguments=call.arguments, decision=decision,
                                summary_en=f"{agent_name} wants to run {call.tool}", risk=decision.risk)
        self.records[record.id] = record
        self.events[record.id] = asyncio.Event()
        self.requested.append(record.id)
        if self.auto is not None:
            return await self.decide(record.id, approve=self.auto, user="auto")
        return record

    async def wait(self, approval_id: str, timeout_s: float | None = None) -> ApprovalRecord:
        record = self.records[approval_id]
        if record.status != ApprovalStatus.PENDING:
            return record
        try:
            await asyncio.wait_for(self.events[approval_id].wait(), timeout_s or self.timeout_s)
        except TimeoutError:
            if self.records[approval_id].status == ApprovalStatus.PENDING:
                self.records[approval_id] = record.model_copy(update={"status": ApprovalStatus.EXPIRED})
        return self.records[approval_id]

    async def decide(self, approval_id: str, *, approve: bool, user: str, note: str | None = None) -> ApprovalRecord:
        record = self.records[approval_id]
        if record.status != ApprovalStatus.PENDING:
            raise ValueError("already decided")
        record = record.model_copy(update={"status": ApprovalStatus.APPROVED if approve else ApprovalStatus.DENIED,
                                           "decided_by": user, "decided_at": time.time(), "note": note})
        self.records[approval_id] = record
        self.events[approval_id].set()
        return record

    def get(self, approval_id: str) -> ApprovalRecord | None:
        return self.records.get(approval_id)

    def list(self, *, status: ApprovalStatus | None = None, limit: int = 100) -> list[ApprovalRecord]:
        return [r for r in self.records.values() if status is None or r.status == status][:limit]

    def expire_overdue(self) -> int:
        return 0


def strip_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text)
