"""Trusted-intent and cross-call behavioral controls.

This is independent of keyword content detection. Task context is registered
only by the trusted caller, never extracted from an untrusted email or document.
All decisions are explainable, and missing task context on sensitive operations
is denied (not silently assumed legitimate).
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from typing import Any

from mirsad.models import Action, Reason, ToolCall
from mirsad.security.intent import IntentJudge
from mirsad.security.sensitive import find_sensitive

_READ = {'read_email', 'list_emails', 'fetch_url', 'read_document', 'list_documents',
         'get_account_balance', 'get_customer_profile', 'get_patient_record', 'search_customers',
         'get_customer', 'export_customers'}
_WRITE = {'transfer_funds', 'approve_payment', 'update_prescription', 'delete_customer',
          'update_customer_note', 'send_email', 'send_lab_results', 'book_appointment'}
_SUMMARIZE = ('summar', 'review', 'read', 'explain', 'look up', 'check', 'show', 'what is',
              'ملخص', 'لخص', 'تلخيص', 'اقرأ', 'اعرض', 'استعرض', 'راجع', 'تفاصيل')
_TRANSFER = ('transfer', 'pay ', 'payment', 'تحويل', 'حوّل', 'ادفع', 'سدد', 'تسديد')
_SEND = ('send', 'email', 'share', 'forward', 'أرسل', 'ارسل', 'شارك')
_PRESCRIBE = ('prescri', 'medication', 'دواء', 'وصفة', 'علاج')


def _reason(code: str, action: Action, detail: str, score: float, **evidence: Any) -> Reason:
    # Existing policy layer type is intentionally reused for compatibility with dashboards/replay.
    return Reason(layer='system', code=code, action=action, message=detail,
                  risk_score=score, evidence=evidence)


@dataclass
class _Session:
    task: str
    agent_id: str
    calls: list[str] = field(default_factory=list)
    read_count: int = 0
    exports: int = 0


class SecurityMonitor:
    def __init__(self, *, max_reads_before_send: int = 8, intent_judge: IntentJudge | None = None):
        self._lock = threading.RLock()
        self.sessions: dict[str, _Session] = {}
        self.max_reads_before_send = max_reads_before_send
        self.intent_judge = intent_judge
        self.benign_transitions: set[tuple[str, str]] | None = None

    def fit_benign_traces(self, traces: list[list[str]]) -> None:
        """Initialize optional transition-based anomalies from reviewed benign runs.

        Never learn from unreviewed or adversarial sessions.
        """
        with self._lock:
            self.benign_transitions = {
                pair for trace in traces for pair in zip(trace, trace[1:], strict=False)
            }

    def bind_task(self, session_id: str, agent_id: str, task: str) -> None:
        if not task or not task.strip():
            raise ValueError('Trusted user task cannot be empty')
        with self._lock:
            # Keep task immutable within an existing session to prevent task laundering.
            prior = self.sessions.get(session_id)
            if prior and (prior.task != task or prior.agent_id != agent_id):
                # A new authenticated chat request begins a new trusted task.
                self.sessions[session_id] = _Session(task=task, agent_id=agent_id)
            if not prior:
                self.sessions[session_id] = _Session(task=task, agent_id=agent_id)

    def reset(self, session_id: str) -> None:
        with self._lock:
            self.sessions.pop(session_id, None)

    def check(self, call: ToolCall, *, sector: str | None = None) -> list[Reason]:
        with self._lock:
            sess = self.sessions.get(call.session_id)
            if sess is None or sess.agent_id != call.agent_id:
                if call.tool in _WRITE:
                    return [_reason('UNBOUND_TASK', Action.DENY,
                                    'Sensitive action has no authenticated original user task.', 1.0)]
                return []
            task = sess.task.lower()
            # Explicit read-only constraints override words like "payment" in
            # "summarize the invoice without making a payment".
            read_only = (any(w in task for w in ('only', 'just', 'without', 'do not', "don't", 'فقط', 'دون', 'بدون'))
                         and any(w in task for w in _SUMMARIZE))
            reasons: list[Reason] = []
            tool = call.tool
            if tool in _WRITE:
                requested = (
                    (tool in {'transfer_funds', 'approve_payment'} and any(k in task for k in _TRANSFER))
                    or (tool in {'send_email', 'send_lab_results'} and any(k in task for k in _SEND))
                    or (tool == 'book_appointment' and any(k in task for k in ('appointment', 'book', 'schedule', 'موعد', 'احجز')) )
                    or (tool == 'update_prescription' and any(k in task for k in _PRESCRIBE)
                        and any(k in task for k in ('update', 'change', 'modify', 'غير', 'عدل', 'تعديل')))
                    or (tool in {'delete_customer', 'update_customer_note'} and any(k in task for k in ('delete', 'update', 'حذف', 'تعديل')))
                )
                if read_only:
                    requested = False
                if not requested:
                    reasons.append(_reason('TASK_INTENT_MISMATCH', Action.DENY,
                          f"Tool '{tool}' performs an operation not authorized by the original user task.",
                          0.98, tool=tool, task_binding='trusted'))
            if tool in _WRITE and self.intent_judge is not None:
                # A required judge failure raises to the gateway evaluation handler,
                # which denies the action and audits the failure.
                judgment = self.intent_judge.assess(sess.task, tool, call.arguments)
                if not judgment.authorized:
                    action = Action.DENY if judgment.confidence >= 0.85 else Action.REQUIRE_APPROVAL
                    reasons.append(_reason('SEMANTIC_TASK_MISMATCH', action,
                                          'Local semantic intent judge: ' + judgment.reason,
                                          judgment.confidence, judge='local_llm'))
            if (tool in _WRITE and sess.calls and self.benign_transitions is not None
                    and (sess.calls[-1], tool) not in self.benign_transitions):
                reasons.append(_reason('UNSEEN_TOOL_SEQUENCE', Action.REQUIRE_APPROVAL,
                                       'This state-changing tool transition was not present in reviewed benign traces.',
                                       0.74, prior_tool=sess.calls[-1], current_tool=tool))
            if tool in {'send_email', 'send_lab_results', 'transfer_funds'} and sess.read_count >= self.max_reads_before_send:
                reasons.append(_reason('UNUSUAL_READ_THEN_SEND', Action.REQUIRE_APPROVAL,
                                       'High-volume reads followed by an outbound operation.', 0.91,
                                       prior_reads=sess.read_count))
            if tool == 'export_customers' and sess.exports >= 2:
                reasons.append(_reason('REPEATED_EXPORT', Action.REQUIRE_APPROVAL,
                                       'Repeated bulk exports in a single session.', 0.86,
                                       prior_exports=sess.exports))
            if sector == 'finance' and tool in {'transfer_funds', 'approve_payment'}:
                beneficiary = str(call.arguments.get('to_iban') or '')
                # Synthetic allowlist only; real deployments need trusted bank-side beneficiary status.
                trusted_beneficiaries = {'SA1234567890123456789012'}
                if beneficiary and beneficiary not in trusted_beneficiaries:
                    reasons.append(_reason('NEW_BENEFICIARY', Action.REQUIRE_APPROVAL,
                                           'Beneficiary is not in the trusted mock beneficiary registry.', 0.9))
            if sector == 'healthcare' and tool == 'send_lab_results':
                to = str(call.arguments.get('to') or '').lower()
                if not to.endswith('@najd-health.example'):
                    reasons.append(_reason('HEALTH_DATA_EXTERNAL', Action.DENY,
                                           'Patient information cannot be sent outside the simulated hospital.', 1.0))
            if sector in ('finance', 'healthcare') and tool in {'send_email', 'send_lab_results'}:
                categories = find_sensitive(json.dumps(call.arguments, ensure_ascii=False), sector)
                if categories:
                    # No sensitive values are copied into audit evidence.
                    reasons.append(_reason('SENSITIVE_OUTBOUND', Action.REQUIRE_APPROVAL,
                                           'Outbound data contains sensitive sector-specific categories.', 0.88,
                                           categories=categories))
            return reasons

    def note(self, call: ToolCall) -> None:
        with self._lock:
            sess = self.sessions.get(call.session_id)
            if not sess:
                return
            sess.calls.append(call.tool)
            if len(sess.calls) > 100:
                sess.calls = sess.calls[-100:]
            if call.tool in _READ:
                sess.read_count += 1
            if call.tool == 'export_customers':
                sess.exports += 1
