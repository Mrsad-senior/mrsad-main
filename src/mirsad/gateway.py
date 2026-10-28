"""The Mirsad gateway: the decision pipeline every tool call and tool result passes through.

``check_call``      Policy -> RateLimit -> Taint -> combine (deny-overrides) -> Approval?
``inspect_result``  Detector -> Sanitize/Spotlight -> Taint register
``execute``         check -> run (if allowed) -> inspect
``replay``          deterministic re-evaluation of a stored audit event

Every step is written to the hash-chained audit log. Synchronous work (policy, taint,
audit writes, detector scans) runs in worker threads so the event loop stays responsive;
taint state and audit ordering are protected by one re-entrant lock.
"""

from __future__ import annotations

import asyncio
import contextvars
import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

from mirsad.models import (
    Action,
    ApprovalStatus,
    Decision,
    DetectionResult,
    GatewayResponse,
    InspectionOutcome,
    Reason,
    Risk,
    SessionSnapshot,
    SinkKind,
    ToolCall,
    ToolProfile,
    ToolResult,
    Trust,
    combine_reasons,
)

if TYPE_CHECKING:  # pragma: no cover - imported for type checking only
    from mirsad.approvals import ApprovalService
    from mirsad.audit import AuditLog
    from mirsad.detector import InjectionDetector
    from mirsad.policy import PolicyEngine
    from mirsad.taint import TaintTracker

log = logging.getLogger("mirsad.gateway")

Executor = Callable[[ToolCall], Awaitable[ToolResult]]
InspectionAction = Literal["pass", "flag", "sanitize", "block"]

#: Identity of the authenticated credential (API agent id) making the current request.
#: Set by the API layer; recorded in audit payloads without changing the public signatures.
principal_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("mirsad_principal", default=None)

_ACTION_AR = {"allow": "السماح بـ", "deny": "رفض", "require_approval": "طلب موافقة على"}
_MAX_SANITIZE_LEAVES = 2000
_REPLAY_ENGINE_CACHE = 8


class ReplayReport(BaseModel):
    """Result of re-evaluating a stored audit event against the policy version it recorded."""

    seq: int
    event_type: str
    original_action: str | None = None
    replayed_action: str | None = None
    match: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class ReplayError(ValueError):
    """The audit event exists but cannot be replayed (wrong type or incomplete payload)."""


@dataclass
class _Core:
    decision: Decision
    needs_human: bool
    check_ms: float


# --------------------------------------------------------------------------- helpers


def _mode(policy: Any) -> str:
    mode = getattr(policy, "mode", "enforce") or "enforce"
    return str(getattr(mode, "value", mode)).lower()


def _setting(obj: Any, name: str, default: Any) -> Any:
    value = getattr(obj, name, None)
    if value is None and isinstance(obj, dict):
        value = obj.get(name)
    return default if value is None else value


def classify_score(score: float, settings: Any) -> InspectionAction:
    """Map a detector score to an inspection action using the tool's detector settings."""
    flag_t = float(_setting(settings, "flag_threshold", 0.5))
    block_t = float(_setting(settings, "block_threshold", 0.8))
    if score >= block_t:
        on_detect = str(getattr(_setting(settings, "on_detect", "sanitize"), "value",
                                _setting(settings, "on_detect", "sanitize")))
        return on_detect if on_detect in ("sanitize", "block", "flag") else "sanitize"  # type: ignore[return-value]
    if score >= flag_t:
        return "flag"
    return "pass"


def _relabel(detection: DetectionResult, settings: Any) -> DetectionResult:
    """Re-threshold the detector label with the policy's thresholds (callers own the thresholds)."""
    flag_t = float(_setting(settings, "flag_threshold", 0.5))
    block_t = float(_setting(settings, "block_threshold", 0.8))
    if detection.score >= block_t:
        label = "injection"
    elif detection.score >= flag_t:
        label = "suspicious"
    else:
        label = "benign"
    if label == detection.label:
        return detection
    return detection.model_copy(update={"label": label})


def _dump(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def _json_size(value: Any) -> int:
    try:
        return len(json.dumps(value, ensure_ascii=False, default=str))
    except (TypeError, ValueError):
        return 1 << 62


def _same_json(text: str, structured: Any) -> bool:
    try:
        return json.loads(text) == structured
    except (TypeError, ValueError):
        return False


def _reason(layer: str, code: str, action: Action, message: str, message_ar: str, *,
            risk_score: float = 0.0, evidence: dict[str, Any] | None = None) -> Reason:
    return Reason(layer=layer, code=code, action=action, message=message, message_ar=message_ar,  # type: ignore[arg-type]
                  risk_score=risk_score, evidence=evidence or {})


def explain_decision(decision: Decision) -> str:
    """Bilingual one-line explanation of a non-ALLOW decision (used as an error message for agents)."""
    if decision.action == Action.ALLOW:
        return ""
    worst = [r for r in decision.reasons if r.action == decision.action] or decision.reasons
    primary = max(worst, key=lambda r: r.risk_score) if worst else None
    en = primary.message if primary else "blocked by policy"
    ar = (primary.message_ar if primary and primary.message_ar else "تم الحظر وفق السياسة")
    verb = "requires human approval" if decision.action == Action.REQUIRE_APPROVAL else "was blocked"
    verb_ar = "يتطلب موافقة بشرية" if decision.action == Action.REQUIRE_APPROVAL else "تم حظره"
    return f"Mirsad: this tool call {verb}. {en} | مرصاد: هذا الاستدعاء {verb_ar}. {ar}"


def _walk_strings(value: Any, fn: Callable[[str], str], counter: list[int]) -> Any:
    if isinstance(value, str):
        counter[0] += 1
        return fn(value)
    if isinstance(value, dict):
        return {k: _walk_strings(v, fn, counter) for k, v in value.items()}
    if isinstance(value, list):
        return [_walk_strings(v, fn, counter) for v in value]
    return value


# --------------------------------------------------------------------------- gateway


class Gateway:
    """Runtime enforcement point between an agent and its tools."""

    def __init__(
        self,
        *,
        policy: PolicyEngine,
        taint: TaintTracker,
        detector: InjectionDetector,
        audit: AuditLog,
        approvals: ApprovalService,
        agent_names: dict[str, str] | None = None,
        policy_store: Callable[[str], str | None] | None = None,
        max_result_chars: int = 200_000,
        audit_content_chars: int = 8_000,
        executor_timeout_s: float | None = 120.0,
        sanitizer: Callable[..., str] | None = None,
        spotlighter: Callable[..., str] | None = None,
    ) -> None:
        self._policy = policy
        self.taint = taint
        self.detector = detector
        self.audit = audit
        self.approvals = approvals
        self.agent_names: dict[str, str] = dict(agent_names or {})
        self.policy_store = policy_store
        self.max_result_chars = max_result_chars
        self.audit_content_chars = audit_content_chars
        self.executor_timeout_s = executor_timeout_s
        self._sanitizer = sanitizer
        self._spotlighter = spotlighter
        self._lock = threading.RLock()
        self._waiting: set[str] = set()
        self._replay_engines: OrderedDict[str, Any] = OrderedDict()
        self._sync_org_name(self._policy)

    # ------------------------------------------------------------------ policy hot swap

    @property
    def policy(self) -> PolicyEngine:
        return self._policy

    @policy.setter
    def policy(self, engine: PolicyEngine) -> None:
        self.set_policy(engine)

    def set_policy(self, engine: PolicyEngine) -> None:
        """Atomically swap the active policy; in-flight evaluations keep the engine they started with."""
        with self._lock:
            old = self._policy
            self._policy = engine
        self._sync_org_name(engine)
        log.info("policy swapped %s -> %s (mode=%s)", getattr(old, "version", "?")[:12],
                 getattr(engine, "version", "?")[:12], _mode(engine))

    def _sync_org_name(self, engine: PolicyEngine) -> None:
        """Approver summaries say "outside <organisation>"; keep the name in step with the active policy."""
        try:
            name = engine.document.organization.name
        except AttributeError:
            return
        if name and hasattr(self.approvals, "org_name"):
            self.approvals.org_name = name

    def is_waiting_for(self, approval_id: str) -> bool:
        """True while a ``check_call`` is blocked on this approval (the gateway will audit its outcome)."""
        return approval_id in self._waiting

    # ------------------------------------------------------------------ check_call

    async def check_call(self, call: ToolCall, *, wait_for_approval: bool = True) -> Decision:
        started = time.perf_counter()
        policy = self._policy
        core = await asyncio.to_thread(self._decide, call, policy, started, wait_for_approval)
        if not core.needs_human:
            return core.decision
        try:
            return await self._await_human(call, core.decision, policy, started)
        finally:
            await asyncio.to_thread(self._note_call, call)

    def _note_call(self, call: ToolCall) -> None:
        with self._lock:
            try:
                self.taint.note_call(call)
            except Exception:  # bookkeeping only; never block on it
                log.exception("taint.note_call failed for %s", call.call_id)

    def _evaluate(self, call: ToolCall, policy: PolicyEngine, snapshot: SessionSnapshot | None,
                  rate_counts: dict[str, int] | None) -> tuple[Action, float, list[Reason], Any, SinkKind,
                                                                dict[str, int], SessionSnapshot]:
        """Pure policy + taint evaluation; with ``snapshot``/``rate_counts`` given it is replay mode."""
        live = snapshot is None
        snap = self.taint.snapshot(call.session_id, call.agent_id) if live else snapshot
        assert snap is not None
        kwargs: dict[str, Any] = {"session_tainted": snap.tainted}
        if not live:
            kwargs["now"] = call.ts
            kwargs["rate_counts"] = rate_counts or {}
        evaluation = policy.evaluate_call(call, **kwargs)
        reasons: list[Reason] = list(evaluation.reasons)
        taint_reasons: list[Reason] = []
        taint_settings = None
        if not any(r.code == "UNKNOWN_AGENT" for r in reasons):
            settings = policy.taint_settings(call.agent_id)
            if _setting(settings, "enabled", True):
                taint_settings = settings
                if live:
                    taint_reasons = list(self.taint.evaluate_call(call, evaluation.profile, evaluation.sink, settings))
                else:
                    taint_reasons = list(self.taint.evaluate_call(call, evaluation.profile, evaluation.sink,
                                                                  settings, snapshot=snap))
        reasons.extend(taint_reasons)
        if live and taint_settings is None:
            snap = snap.model_copy(update={"values": []})  # values are only consulted by the taint rules
        elif live and hasattr(self.taint, "minimal_snapshot"):
            # Only the values the taint rules consulted: keeps audit payloads small, replay exact.
            snap = self.taint.minimal_snapshot(call, evaluation.profile, evaluation.sink, taint_settings)
        action, _ = combine_reasons(reasons)
        # A taint rule an admin downgraded to "allow" stays visible as evidence but must not raise the risk
        # score or count as "taint fired"; otherwise it would still force approval through approval: on_risk.
        _, risk_score = combine_reasons([r for r in reasons if not (r.layer == "taint" and r.action == Action.ALLOW)])
        taint_fired = any(r.action != Action.ALLOW for r in taint_reasons)
        if action == Action.ALLOW and policy.approval_required(evaluation.profile, risk_score, taint_fired):
            reasons.append(_reason(
                "approval", "APPROVAL_POLICY", Action.REQUIRE_APPROVAL,
                f"Combined risk {risk_score:.2f} on tool '{call.tool}' requires human approval.",
                f"درجة الخطورة المجمعة {risk_score:.2f} للأداة '{call.tool}' تتطلب موافقة بشرية.",
                risk_score=risk_score))
            action = Action.REQUIRE_APPROVAL
        return (action, risk_score, reasons, evaluation.profile, SinkKind(evaluation.sink),
                dict(evaluation.rate_counts or {}), snap)

    def _decide(self, call: ToolCall, policy: PolicyEngine, started: float, wait: bool) -> _Core:
        enforced = _mode(policy) != "monitor"
        with self._lock:
            profile: Any = None
            snapshot_json: dict[str, Any] | None = None
            rate_counts: dict[str, int] = {}
            sink = SinkKind.NONE
            try:
                action, risk_score, reasons, profile, sink, rate_counts, snap = self._evaluate(
                    call, policy, None, None)
                snapshot_json = snap.model_dump(mode="json")
            except Exception as exc:  # fail closed: a broken layer must never let a call through
                log.exception("evaluation failed for call %s (%s)", call.call_id, call.tool)
                action, risk_score = Action.DENY, 1.0
                reasons = [_reason(
                    "system", "INTERNAL_ERROR", Action.DENY,
                    "Mirsad could not evaluate this call safely, so it was blocked (fail-closed).",
                    "تعذّر على مرصاد تقييم هذا الاستدعاء بأمان، لذلك تم حظره احترازياً.",
                    risk_score=1.0, evidence={"error_type": type(exc).__name__})]

            returned = action if enforced else Action.ALLOW
            out_reasons = list(reasons)
            if not enforced and action != Action.ALLOW:
                out_reasons.append(_reason(
                    "system", "MONITOR_MODE", Action.ALLOW,
                    f"Monitor mode: this call would have been '{action.value}', but enforcement is off.",
                    f"وضع المراقبة: كان القرار سيكون {_ACTION_AR[action.value]} هذا الاستدعاء، لكن التطبيق معطّل.",
                    evidence={"would_be_action": action.value}))
            needs_human = enforced and wait and action == Action.REQUIRE_APPROVAL
            check_ms = (time.perf_counter() - started) * 1000
            payload = {
                "call": call.model_dump(mode="json"),
                "profile": _dump(profile),
                "sink": sink.value,
                "reasons": [r.model_dump(mode="json") for r in reasons],
                "snapshot": snapshot_json,
                "rate_counts": rate_counts,
                "risk_score": risk_score,
                "enforced": enforced,
                "returned_action": returned.value,
                "wait_for_approval": wait,
                "latency_ms": round(check_ms, 3),
                "principal": principal_var.get(),
            }
            audit_seq: int | None = None
            try:
                event = self.audit.append(
                    "tool_call.decision", session_id=call.session_id, agent_id=call.agent_id, tool=call.tool,
                    call_id=call.call_id, action=action.value, risk=Risk.from_score(risk_score).value,
                    policy_version=getattr(policy, "version", None), payload=payload)
                audit_seq = getattr(event, "seq", None)
            except Exception:
                log.exception("audit append failed for call %s", call.call_id)
                if enforced:  # no audit trail -> no action (tamper-evidence is a hard requirement)
                    returned, needs_human = Action.DENY, False
                    out_reasons.append(_reason(
                        "system", "AUDIT_UNAVAILABLE", Action.DENY,
                        "The audit log is unavailable, so the call was blocked (fail-closed).",
                        "سجل التدقيق غير متاح، لذلك تم حظر الاستدعاء احترازياً.", risk_score=1.0))
            decision = Decision(
                call_id=call.call_id, action=returned, reasons=out_reasons, risk=Risk.from_score(risk_score),
                risk_score=risk_score, sink=sink, policy_version=getattr(policy, "version", "") or "",
                latency_ms=(time.perf_counter() - started) * 1000, audit_seq=audit_seq)
            if not needs_human:
                try:
                    self.taint.note_call(call)
                except Exception:
                    log.exception("taint.note_call failed for %s", call.call_id)
        return _Core(decision=decision, needs_human=needs_human, check_ms=check_ms)

    async def _await_human(self, call: ToolCall, decision: Decision, policy: PolicyEngine,
                           started: float) -> Decision:
        agent_name = self.agent_names.get(call.agent_id, call.agent_id)
        try:
            record = await self.approvals.request(call, decision, agent_name=agent_name)
        except Exception:
            log.exception("approval request failed for call %s", call.call_id)
            reason = _reason("approval", "APPROVAL_UNAVAILABLE", Action.DENY,
                             "Human approval was required but the approval service failed.",
                             "كانت الموافقة البشرية مطلوبة لكن خدمة الموافقات تعطلت.", risk_score=decision.risk_score)
            return decision.model_copy(update={
                "action": Action.DENY, "reasons": [*decision.reasons, reason],
                "latency_ms": (time.perf_counter() - started) * 1000})

        self._waiting.add(record.id)
        human_wait = 0.0
        try:
            await asyncio.to_thread(self._audit_safe, "approval.requested", call, {
                "approval_id": record.id, "expires_at": record.expires_at, "summary_en": record.summary_en,
                "summary_ar": record.summary_ar, "decision_seq": decision.audit_seq,
            }, Action.REQUIRE_APPROVAL.value, decision.risk.value, policy)
            timeout = max(0.0, record.expires_at - time.time())
            policy_timeout = self._policy_approval_timeout(policy)
            if policy_timeout is not None:
                timeout = min(timeout, policy_timeout)
            wait_started = time.perf_counter()
            try:
                record = await self.approvals.wait(record.id, timeout)
            finally:
                human_wait = time.perf_counter() - wait_started

            if record.status == ApprovalStatus.APPROVED:
                final = Action.ALLOW
                reason = _reason("approval", "APPROVED_BY_HUMAN", Action.ALLOW,
                                 f"Approved by {record.decided_by or 'an approver'}.",
                                 f"تمت الموافقة من قبل {record.decided_by or 'أحد المعتمدين'}.",
                                 evidence={"approval_id": record.id, "note": record.note})
            elif record.status == ApprovalStatus.DENIED:
                final = Action.DENY
                reason = _reason("approval", "DENIED_BY_HUMAN", Action.DENY,
                                 f"Denied by {record.decided_by or 'an approver'}.",
                                 f"تم الرفض من قبل {record.decided_by or 'أحد المعتمدين'}.",
                                 risk_score=decision.risk_score,
                                 evidence={"approval_id": record.id, "note": record.note})
            else:
                final = Action.DENY
                reason = _reason("approval", "APPROVAL_EXPIRED", Action.DENY,
                                 "No approver responded before the request expired.",
                                 "انتهت مهلة طلب الموافقة دون رد من أي معتمد.",
                                 risk_score=decision.risk_score,
                                 evidence={"approval_id": record.id, "status": record.status.value})
            latency = (time.perf_counter() - started - human_wait) * 1000
            final_decision = decision.model_copy(update={
                "action": final, "reasons": [*decision.reasons, reason], "approval_id": record.id,
                "approval_status": record.status.value, "latency_ms": latency})
            await asyncio.to_thread(self._audit_safe, "approval.decided", call, {
                "approval_id": record.id, "status": record.status.value, "decided_by": record.decided_by,
                "note": record.note, "final_action": final.value, "human_wait_ms": round(human_wait * 1000, 1),
                "decision_seq": decision.audit_seq, "source": "gateway",
            }, final.value, decision.risk.value, policy)
            return final_decision
        finally:
            self._waiting.discard(record.id)

    @staticmethod
    def _policy_approval_timeout(policy: Any) -> float | None:
        value = getattr(policy, "approval_timeout_s", None)
        if value is None:
            defaults = getattr(getattr(policy, "document", None), "defaults", None)
            value = _setting(defaults, "approval_timeout_s", None) if defaults is not None else None
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _audit_safe(self, event_type: str, call: ToolCall, payload: dict[str, Any], action: str | None,
                    risk: str | None, policy: Any) -> int | None:
        payload = {**payload, "principal": principal_var.get()}
        with self._lock:
            try:
                event = self.audit.append(event_type, session_id=call.session_id, agent_id=call.agent_id,
                                          tool=call.tool, call_id=call.call_id, action=action, risk=risk,
                                          policy_version=getattr(policy, "version", None), payload=payload)
                return getattr(event, "seq", None)
            except Exception:
                log.exception("audit append (%s) failed for call %s", event_type, call.call_id)
                return None

    # ------------------------------------------------------------------ inspect_result

    async def inspect_result(self, result: ToolResult) -> InspectionOutcome:
        started = time.perf_counter()
        policy = self._policy
        enforced = _mode(policy) != "monitor"
        reasons: list[Reason] = []
        try:
            profile: ToolProfile = policy.tool_profile(result.agent_id, result.tool)
            dsettings = policy.detector_settings(result.agent_id, result.tool)
        except Exception:
            log.exception("policy lookup failed while inspecting %s", result.call_id)
            profile = ToolProfile(tool=result.tool, allowed=False, trust=Trust.UNTRUSTED, scan=True)
            dsettings = None
        # Results of tools the policy does not allow (or does not know) are never trusted.
        if not profile.allowed and profile.trust != Trust.UNTRUSTED:
            profile = profile.model_copy(update={"trust": Trust.UNTRUSTED, "scan": True})

        raw = result.content or ""
        structured = result.structured
        if not raw and structured is not None:
            raw = json.dumps(structured, ensure_ascii=False, default=str)
        truncated = len(raw) > self.max_result_chars
        omitted = 0
        if truncated:
            omitted = len(raw) - self.max_result_chars
            raw = raw[: self.max_result_chars]
            structured = None  # the structured form would leak the omitted tail
            reasons.append(_reason("system", "RESULT_TRUNCATED", Action.ALLOW,
                                   f"Result truncated to {self.max_result_chars} characters ({omitted} omitted).",
                                   f"تم اقتطاع النتيجة إلى {self.max_result_chars} حرفاً (حُذف {omitted}).",
                                   evidence={"omitted_chars": omitted}))

        should_scan = bool(profile.scan or profile.trust == Trust.UNTRUSTED)
        detection: DetectionResult | None = None
        source = "text"
        would_be: InspectionAction = "pass"
        if should_scan and (raw or structured is not None):
            try:
                detection, source = await asyncio.to_thread(self._scan, raw, structured)
                detection = _relabel(detection, dsettings)
                would_be = classify_score(detection.score, dsettings)
            except Exception as exc:
                log.exception("detector failed on result %s; blocking (fail-closed)", result.call_id)
                would_be = "block"
                reasons.append(_reason("detector", "SCAN_FAILED", Action.DENY,
                                       "The injection detector failed, so the untrusted result was withheld.",
                                       "تعطل كاشف الحقن، لذلك تم حجب النتيجة غير الموثوقة.", risk_score=1.0,
                                       evidence={"error_type": type(exc).__name__}))
        if detection is not None and would_be != "pass":
            injection = detection.label == "injection"
            reasons.append(_reason(
                "detector", "INJECTION_DETECTED" if injection else "INJECTION_SUSPECTED",
                Action.DENY if would_be == "block" else Action.ALLOW,
                f"Prompt-injection {'detected' if injection else 'suspected'} in the result of '{result.tool}' "
                f"(score {detection.score:.2f}); action: {would_be}.",
                f"{'تم اكتشاف' if injection else 'يُشتبه في'} حقن أوامر في نتيجة الأداة '{result.tool}' "
                f"(الدرجة {detection.score:.2f})؛ الإجراء: {would_be}.",
                risk_score=detection.score,
                evidence={"spans": [s.model_dump(mode="json") for s in detection.spans[:20]],
                          "signals": detection.signals[:20], "model_score": detection.model_score,
                          "rule_score": detection.rule_score, "language": detection.language}))

        action: InspectionAction
        content = raw
        out_structured = structured
        sanitized = spotlighted = False
        if not enforced:
            action = "flag" if would_be != "pass" else "pass"
            if truncated:
                content += self._truncation_note(omitted)
        else:
            action = would_be
            if action == "sanitize" and detection is not None:
                content, out_structured, ok = await asyncio.to_thread(
                    self._sanitize, raw, structured, detection, source, dsettings)
                sanitized = ok
                if not ok:
                    action = "block"
            if action == "block":
                content = self._block_text(raw, detection)
                out_structured = None
            elif truncated:
                content += self._truncation_note(omitted)
            spotlight_on = bool(_setting(dsettings, "spotlight", True))
            if action != "block" and profile.trust == Trust.UNTRUSTED and spotlight_on:
                try:
                    content = self._spotlight(content, source=result.tool, call_id=result.call_id)
                    spotlighted = True
                except Exception:
                    log.exception("spotlight failed for %s", result.call_id)

        tsettings = None
        try:
            tsettings = policy.taint_settings(result.agent_id)
        except Exception:
            log.debug("no taint settings for agent %s", result.agent_id)
        audit_seq = await asyncio.to_thread(
            self._register_and_audit, result, profile, detection, tsettings, policy, {
                "action": action, "would_be_action": would_be, "enforced": enforced, "sanitized": sanitized,
                "spotlighted": spotlighted, "truncated": truncated, "scan_source": source if detection else None,
                "reasons": [r.model_dump(mode="json") for r in reasons],
                "detector_settings": _dump(dsettings) if dsettings is not None else None,
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            })
        return InspectionOutcome(
            call_id=result.call_id, action=action, content=content, structured=out_structured,
            trust=profile.trust, sensitivity=profile.sensitivity, detection=detection, reasons=reasons,
            latency_ms=(time.perf_counter() - started) * 1000, audit_seq=audit_seq)

    def _scan(self, text: str, structured: Any) -> tuple[DetectionResult, str]:
        """Scan text or structured content. Structured scanning walks JSON strings, which defeats
        ``\\uXXXX``-escaped payloads; the text form is also scanned when it differs."""
        if structured is not None and hasattr(self.detector, "scan_structured"):
            det = self.detector.scan_structured(structured)
            if text and not _same_json(text, structured):
                other = self.detector.scan(text)
                if other.score > det.score:
                    return other, "text"
            return det, "structured"
        return self.detector.scan(text), "text"

    def _sanitize(self, text: str, structured: Any, detection: DetectionResult, source: str,
                  settings: Any) -> tuple[str, Any, bool]:
        """Neutralise detected spans. Returns (content, structured, ok); ok=False means escalate to block."""
        if source == "text" or structured is None:
            return self._sanitize_text(text, detection), None, True
        flag_t = float(_setting(settings, "flag_threshold", 0.5))
        changed = [0]
        counter = [0]

        def fix(leaf: str) -> str:
            if counter[0] > _MAX_SANITIZE_LEAVES or len(leaf) < 8:
                return leaf
            d = self.detector.scan(leaf)
            if d.score >= flag_t:
                changed[0] += 1
                return self._sanitize_text(leaf, d)
            return leaf

        cleaned = _walk_strings(structured, fix, counter)
        if counter[0] > _MAX_SANITIZE_LEAVES or not changed[0]:
            return text, None, False  # payload split across fields / too large: cannot sanitise reliably
        return json.dumps(cleaned, ensure_ascii=False, default=str), cleaned, True

    @staticmethod
    def _truncation_note(omitted: int) -> str:
        return f"\n[... truncated by Mirsad: {omitted} characters omitted | اقتطع مرصاد {omitted} حرفاً من النتيجة]"

    def _sanitize_text(self, text: str, detection: DetectionResult) -> str:
        fn = self._sanitizer or _lazy_detector_fn("sanitize")
        return fn(text, detection, mode="sanitize")

    def _block_text(self, text: str, detection: DetectionResult | None) -> str:
        if detection is not None:
            try:
                fn = self._sanitizer or _lazy_detector_fn("sanitize")
                return fn(text, detection, mode="block")
            except Exception:
                log.exception("block-mode sanitizer failed; using generic notice")
        return ("[Mirsad withheld this tool result because it contained instructions aimed at the AI agent.] "
                "[حجب مرصاد نتيجة الأداة لأنها تضمنت تعليمات موجهة إلى الوكيل الذكي.]")

    def _spotlight(self, text: str, *, source: str, call_id: str) -> str:
        fn = self._spotlighter or _lazy_detector_fn("spotlight")
        return fn(text, source=source, call_id=call_id)

    def _register_and_audit(self, result: ToolResult, profile: ToolProfile, detection: DetectionResult | None,
                            tsettings: Any, policy: Any, extra: dict[str, Any]) -> int | None:
        content = result.content or ""
        stored_structured = None
        if result.structured is not None and _json_size(result.structured) <= self.audit_content_chars:
            stored_structured = result.structured
        payload = {
            "result": {
                "call_id": result.call_id, "tool": result.tool, "is_error": result.is_error,
                "content": content[: self.audit_content_chars], "content_chars": len(content),
                "content_sha256": hashlib.sha256(content.encode("utf-8", "surrogatepass")).hexdigest(),
                "structured": stored_structured,
            },
            "detection": detection.model_dump(mode="json") if detection else None,
            "profile": profile.model_dump(mode="json"),
            "principal": principal_var.get(),
            **extra,
        }
        risk = Risk.from_score(detection.score).value if detection else Risk.LOW.value
        with self._lock:
            if tsettings is not None and _setting(tsettings, "enabled", True):
                try:
                    self.taint.register_result(result, profile, detection, tsettings)
                except Exception:
                    log.exception("taint registration failed for %s", result.call_id)
            try:
                event = self.audit.append(
                    "tool_result.inspection", session_id=result.session_id, agent_id=result.agent_id,
                    tool=result.tool, call_id=result.call_id, action=extra["would_be_action"], risk=risk,
                    policy_version=getattr(policy, "version", None), payload=payload)
                return getattr(event, "seq", None)
            except Exception:
                log.exception("audit append failed for result %s", result.call_id)
                return None

    # ------------------------------------------------------------------ execute

    async def execute(self, call: ToolCall, executor: Executor) -> GatewayResponse:
        decision = await self.check_call(call, wait_for_approval=True)
        if not decision.allowed:
            return GatewayResponse(decision=decision, result=None, error=explain_decision(decision))
        error: str | None = None
        try:
            if self.executor_timeout_s:
                raw = await asyncio.wait_for(executor(call), timeout=self.executor_timeout_s)
            else:
                raw = await executor(call)
            if not isinstance(raw, ToolResult):
                raise TypeError(f"executor returned {type(raw).__name__}, expected ToolResult")
        except Exception as exc:
            timed_out = isinstance(exc, TimeoutError)
            log.warning("tool %s failed for call %s: %s", call.tool, call.call_id, type(exc).__name__)
            await asyncio.to_thread(self._audit_safe, "tool_call.error", call, {
                "error_type": type(exc).__name__, "error": str(exc)[:500], "timed_out": timed_out,
            }, None, None, self._policy)
            error = (f"Tool '{call.tool}' timed out." if timed_out
                     else f"Tool '{call.tool}' failed ({type(exc).__name__}).")
            raw = ToolResult(call_id=call.call_id, session_id=call.session_id, agent_id=call.agent_id,
                             tool=call.tool, is_error=True,
                             content=f"{error} The details were recorded in the Mirsad audit log.")
        # An upstream must not be able to attribute its output to another call or session.
        result = raw.model_copy(update={"call_id": call.call_id, "session_id": call.session_id,
                                        "agent_id": call.agent_id, "tool": call.tool})
        outcome = await self.inspect_result(result)
        if error is None and result.is_error:
            error = f"Tool '{call.tool}' returned an error."
        return GatewayResponse(decision=decision, result=outcome, error=error)

    # ------------------------------------------------------------------ replay

    def replay(self, seq: int) -> ReplayReport:
        """Re-evaluate a stored decision/inspection event. Raises ``KeyError`` if missing,
        ``ReplayError`` if the event is not replayable."""
        event = self.audit.get(seq)
        if event is None:
            raise KeyError(seq)
        if event.event_type == "tool_call.decision":
            return self._replay_decision(event)
        if event.event_type == "tool_result.inspection":
            return self._replay_inspection(event)
        raise ReplayError(f"events of type '{event.event_type}' cannot be replayed")

    def _engine_for(self, version: str | None) -> tuple[Any, list[str]]:
        notes: list[str] = []
        current = self._policy
        if not version or version == getattr(current, "version", None):
            if not version:
                notes.append("event has no policy version; replayed with the active policy")
            return current, notes
        if version in self._replay_engines:
            self._replay_engines.move_to_end(version)
            return self._replay_engines[version], notes
        yaml_text = self.policy_store(version) if self.policy_store else None
        if yaml_text is None:
            raise ReplayError(f"policy version {version[:12]} is not in the policy store")
        engine = type(current).from_yaml(yaml_text)
        if getattr(engine, "version", version) != version:
            notes.append("stored policy text re-hashes to a different version")
        self._replay_engines[version] = engine
        while len(self._replay_engines) > _REPLAY_ENGINE_CACHE:
            self._replay_engines.popitem(last=False)
        return engine, notes

    def _replay_decision(self, event: Any) -> ReplayReport:
        payload = event.payload or {}
        if not isinstance(payload.get("call"), dict) or not isinstance(payload.get("snapshot"), dict):
            raise ReplayError("event payload is incomplete (call/snapshot missing, possibly truncated)")
        engine, notes = self._engine_for(event.policy_version)
        call = ToolCall.model_validate(payload["call"])
        snapshot = SessionSnapshot.model_validate(payload["snapshot"])
        with self._lock:
            action, risk_score, reasons, profile, sink, _, _ = self._evaluate(
                call, engine, snapshot, dict(payload.get("rate_counts") or {}))
        original_codes = [r.get("code") for r in payload.get("reasons", []) if isinstance(r, dict)]
        replayed_codes = [r.code for r in reasons]
        call_text = json.dumps(payload["call"], ensure_ascii=False).lower()
        if "redacted" in call_text or "***" in call_text:
            notes.append("call arguments were redacted in the audit log; replay used the redacted values")
        if payload.get("_truncated"):
            notes.append("the audit payload was truncated to the size limit; replay used the clipped values")
        details = {
            "policy_version": event.policy_version, "tool": call.tool, "agent_id": call.agent_id,
            "original_reasons": original_codes, "replayed_reasons": replayed_codes,
            "added_reasons": sorted(set(replayed_codes) - set(original_codes)),
            "removed_reasons": sorted(set(original_codes) - set(replayed_codes)),
            "reasons_match": sorted(original_codes) == sorted(replayed_codes),
            "original_risk_score": payload.get("risk_score"), "replayed_risk_score": risk_score,
            "sink": sink.value, "enforced": payload.get("enforced", True), "notes": notes,
        }
        return ReplayReport(seq=event.seq, event_type=event.event_type, original_action=event.action,
                            replayed_action=action.value, match=event.action == action.value, details=details)

    def _replay_inspection(self, event: Any) -> ReplayReport:
        payload = event.payload or {}
        stored = payload.get("result")
        if not isinstance(stored, dict) or not isinstance(stored.get("content"), str):
            raise ReplayError("event payload is incomplete (result content missing, possibly truncated)")
        engine, notes = self._engine_for(event.policy_version)
        agent_id = event.agent_id or ""
        tool = event.tool or stored.get("tool") or ""
        profile = engine.tool_profile(agent_id, tool)
        dsettings = engine.detector_settings(agent_id, tool)
        if not profile.allowed and profile.trust != Trust.UNTRUSTED:
            profile = profile.model_copy(update={"trust": Trust.UNTRUSTED, "scan": True})
        content = stored["content"]
        structured = stored.get("structured")
        if stored.get("content_chars", len(content)) > len(content) or payload.get("_truncated"):
            notes.append("only part of the result was stored in the audit log; the stored part was rescanned")
        replayed: str = "pass"
        score = None
        if profile.scan or profile.trust == Trust.UNTRUSTED:
            detection, _ = self._scan(content, structured if not payload.get("truncated") else None)
            score = detection.score
            replayed = classify_score(detection.score, dsettings)
        original = payload.get("would_be_action") or event.action
        original_score = (payload.get("detection") or {}).get("score")
        details = {
            "policy_version": event.policy_version, "tool": tool, "agent_id": agent_id,
            "original_score": original_score, "replayed_score": score,
            "detector_version": getattr(self.detector, "version", None), "notes": notes,
        }
        return ReplayReport(seq=event.seq, event_type=event.event_type, original_action=original,
                            replayed_action=replayed, match=original == replayed, details=details)


def _lazy_detector_fn(name: str) -> Callable[..., str]:
    from mirsad import detector as detector_module  # imported lazily: loads numpy/sklearn

    return getattr(detector_module, name)
