"""Shared data model for every Mirsad component.

All layers (policy, taint, detector, audit, approvals, adapters) exchange these
types, so they are deliberately small, serialisable and free of behaviour.
"""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:16]}"


class Action(str, Enum):
    """Outcome of evaluating a tool call. Ordered by severity for deny-overrides."""

    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"

    @property
    def severity(self) -> int:
        return {"allow": 0, "require_approval": 1, "deny": 2}[self.value]


class Trust(str, Enum):
    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"


class Sensitivity(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"

    @property
    def rank(self) -> int:
        return {"public": 0, "internal": 1, "confidential": 2}[self.value]


class SinkKind(str, Enum):
    """Where a tool call sends data. EXTERNAL sinks leave the organisation."""

    NONE = "none"
    INTERNAL = "internal"
    EXTERNAL = "external"


class Risk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return {"low": 0, "medium": 1, "high": 2, "critical": 3}[self.value]

    @staticmethod
    def from_score(score: float) -> Risk:
        if score >= 0.85:
            return Risk.CRITICAL
        if score >= 0.6:
            return Risk.HIGH
        if score >= 0.3:
            return Risk.MEDIUM
        return Risk.LOW


Layer = Literal["policy", "ratelimit", "taint", "detector", "approval", "system"]


# --------------------------------------------------------------------------- calls & results


class ToolCall(BaseModel):
    """A request by an agent to invoke a tool, intercepted before execution."""

    call_id: str = Field(default_factory=lambda: new_id("call_"))
    session_id: str
    agent_id: str
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    ts: float = Field(default_factory=time.time)


class ToolResult(BaseModel):
    """What a tool returned, intercepted before it reaches the model.

    ``content`` is always the text form. ``structured`` carries the parsed JSON
    value when the tool returned JSON, so the taint tracker can see field names.
    """

    call_id: str
    session_id: str
    agent_id: str
    tool: str
    content: str
    structured: Any | None = None
    is_error: bool = False


# --------------------------------------------------------------------------- decisions


class Reason(BaseModel):
    """One piece of evidence for (or against) a decision, produced by a single layer."""

    layer: Layer
    code: str
    message: str
    message_ar: str | None = None
    action: Action
    rule_id: str | None = None
    risk_score: float = 0.0
    evidence: dict[str, Any] = Field(default_factory=dict)


class Decision(BaseModel):
    """Final verdict for a tool call after all layers ran (deny-overrides)."""

    call_id: str
    action: Action
    reasons: list[Reason] = Field(default_factory=list)
    risk: Risk = Risk.LOW
    risk_score: float = 0.0
    sink: SinkKind = SinkKind.NONE
    policy_version: str = ""
    approval_id: str | None = None
    approval_status: str | None = None
    latency_ms: float = 0.0
    audit_seq: int | None = None

    @property
    def allowed(self) -> bool:
        return self.action == Action.ALLOW


def combine_reasons(reasons: list[Reason]) -> tuple[Action, float]:
    """Deny-overrides combination: the most severe action wins; risk is the max score."""
    action = Action.ALLOW
    score = 0.0
    for r in reasons:
        if r.action.severity > action.severity:
            action = r.action
        score = max(score, r.risk_score)
    return action, score


# --------------------------------------------------------------------------- detector


class DetectionSpan(BaseModel):
    start: int
    end: int
    text: str
    rule_id: str | None = None
    score: float = 1.0


class DetectionResult(BaseModel):
    score: float
    label: Literal["benign", "suspicious", "injection"]
    language: Literal["en", "ar", "mixed", "other"]
    spans: list[DetectionSpan] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)
    model_score: float = 0.0
    rule_score: float = 0.0
    latency_ms: float = 0.0


class InspectionOutcome(BaseModel):
    """Verdict for a tool result: pass it through, sanitise it, or block it."""

    call_id: str
    action: Literal["pass", "flag", "sanitize", "block"]
    content: str
    structured: Any | None = None
    trust: Trust
    sensitivity: Sensitivity
    detection: DetectionResult | None = None
    reasons: list[Reason] = Field(default_factory=list)
    latency_ms: float = 0.0
    audit_seq: int | None = None


class GatewayResponse(BaseModel):
    """Full proxy round-trip: decision, and the inspected result when the call ran."""

    decision: Decision
    result: InspectionOutcome | None = None
    error: str | None = None


# --------------------------------------------------------------------------- policy profile


class ToolProfile(BaseModel):
    """Security attributes of one tool for one agent, resolved from the policy."""

    model_config = ConfigDict(frozen=True)

    tool: str
    allowed: bool = False
    trust: Trust = Trust.TRUSTED
    sensitivity: Sensitivity = Sensitivity.INTERNAL
    sink: Literal["none", "internal", "external", "dynamic"] = "none"
    sink_params: tuple[str, ...] = ()
    risk: Risk = Risk.LOW
    approval: Literal["never", "on_risk", "always"] = "on_risk"
    scan: bool = False
    matched_rule: str | None = None


# --------------------------------------------------------------------------- taint


class TaintedValue(BaseModel):
    value: str
    kind: Literal["email", "url", "domain", "iban", "phone", "number", "id", "ngram"]
    field: str | None = None
    source_tool: str
    source_call_id: str
    trust: Trust
    sensitivity: Sensitivity
    trusted_field: bool = False


class SessionSnapshot(BaseModel):
    """Serialisable taint state of one agent session (stored in audit events for replay)."""

    session_id: str
    agent_id: str
    untrusted_sources: list[str] = Field(default_factory=list)
    max_sensitivity: Sensitivity = Sensitivity.PUBLIC
    injection_detected: bool = False
    values: list[TaintedValue] = Field(default_factory=list)
    call_count: int = 0

    @property
    def tainted(self) -> bool:
        return bool(self.untrusted_sources)


# --------------------------------------------------------------------------- audit & approvals


class AuditEvent(BaseModel):
    seq: int
    ts: float
    event_type: str
    session_id: str | None = None
    agent_id: str | None = None
    tool: str | None = None
    call_id: str | None = None
    action: str | None = None
    risk: str | None = None
    policy_version: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    prev_hash: str
    hash: str


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ApprovalRecord(BaseModel):
    id: str
    created_at: float
    expires_at: float
    status: ApprovalStatus = ApprovalStatus.PENDING
    agent_id: str
    session_id: str
    call_id: str
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    decision: Decision
    summary_en: str = ""
    summary_ar: str = ""
    risk: Risk = Risk.LOW
    decided_by: str | None = None
    decided_at: float | None = None
    note: str | None = None
