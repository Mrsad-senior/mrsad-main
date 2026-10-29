"""Human-in-the-loop approval workflow.

State machine: ``pending`` -> ``approved`` | ``denied`` | ``expired`` | ``cancelled``.
Every transition is a conditional ``UPDATE ... WHERE status = 'pending'`` so exactly
one decision wins even with concurrent approvers or several processes sharing the
database. Waiters block on per-approval ``asyncio.Event`` objects (no busy
polling); a slow re-check of the database every few seconds covers decisions
made by another process.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from sqlalchemy import select, update

from mirsad.approvals.notifier import Notifier, delete_push_subscriptions, load_push_subscriptions
from mirsad.approvals.summary import summarize
from mirsad.audit.redact import redact
from mirsad.models import ApprovalRecord, ApprovalStatus, Decision, ToolCall, new_id
from mirsad.storage import ApprovalRow, Database

log = logging.getLogger("mirsad.approvals")

AUTO_DECIDER_USER = "auto-decider"
CROSS_PROCESS_RECHECK_S = 5.0
_TERMINAL = {ApprovalStatus.APPROVED, ApprovalStatus.DENIED, ApprovalStatus.EXPIRED, ApprovalStatus.CANCELLED}


class ApprovalNotFound(KeyError):
    """No approval with the given id (a ``KeyError``, hence also a ``LookupError``)."""

    def __str__(self) -> str:
        return f"approval {self.args[0]!s} not found" if self.args else "approval not found"


def _row_to_record(row: ApprovalRow) -> ApprovalRecord:
    return ApprovalRecord(
        id=row.id, created_at=row.created_at, expires_at=row.expires_at, status=ApprovalStatus(row.status),
        agent_id=row.agent_id, session_id=row.session_id, call_id=row.call_id, tool=row.tool,
        arguments=json.loads(row.arguments_json or "{}"),
        decision=Decision.model_validate_json(row.decision_json),
        summary_en=row.summary_en, summary_ar=row.summary_ar, risk=row.risk,
        decided_by=row.decided_by, decided_at=row.decided_at, note=row.note,
    )


class ApprovalService:
    """Creates, waits on, decides and expires approval requests."""

    def __init__(
        self,
        db: Database,
        notifier: Notifier,
        *,
        timeout_s: float = 120.0,
        auto_decider: Callable[[ApprovalRecord], bool | None] | None = None,
        org_name: str | None = None,
        org_name_ar: str | None = None,
        redact_arguments: bool = True,
    ) -> None:
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        self.db = db
        self.notifier = notifier
        self.timeout_s = float(timeout_s)
        self.auto_decider = auto_decider
        self.org_name = org_name
        self.org_name_ar = org_name_ar
        self.redact_arguments = redact_arguments
        self._waiters: dict[str, list[tuple[asyncio.AbstractEventLoop, asyncio.Event]]] = {}
        self._waiters_lock = threading.Lock()
        self._background: set[asyncio.Task[Any]] = set()
        self._created_at_lock = threading.Lock()
        self._last_created_at = 0.0

    # -- create ------------------------------------------------------------------------------

    async def request(self, call: ToolCall, decision: Decision, *, agent_name: str) -> ApprovalRecord:
        """Persist a pending approval, notify approvers, and apply the auto-decider if configured."""
        # Windows' wall clock can return the same value for several quick calls.
        # Keep creation timestamps strictly increasing so "newest first" is stable
        # across different SQLite query plans (including status-filtered indexes).
        with self._created_at_lock:
            now = max(time.time(), self._last_created_at + 1e-6)
            self._last_created_at = now
        approval_id = new_id("apr_")
        arguments = redact(call.arguments) if self.redact_arguments else dict(call.arguments)
        shown_call = call.model_copy(update={"arguments": arguments})
        stored_decision = decision.model_copy(update={"approval_id": approval_id,
                                                      "approval_status": ApprovalStatus.PENDING.value})
        record = ApprovalRecord(
            id=approval_id, created_at=now, expires_at=now + self.timeout_s, agent_id=call.agent_id,
            session_id=call.session_id, call_id=call.call_id, tool=call.tool, arguments=arguments,
            decision=stored_decision, risk=decision.risk,
            summary_en=summarize(shown_call, decision, agent_name=agent_name, lang="en",
                                 org_name=self.org_name, org_name_ar=self.org_name_ar),
            summary_ar=summarize(shown_call, decision, agent_name=agent_name, lang="ar",
                                 org_name=self.org_name, org_name_ar=self.org_name_ar),
        )
        with self.db.session() as sess:
            sess.add(ApprovalRow(
                id=record.id, created_at=record.created_at, expires_at=record.expires_at,
                status=record.status.value, agent_id=record.agent_id, session_id=record.session_id,
                call_id=record.call_id, tool=record.tool, arguments_json=json.dumps(arguments, ensure_ascii=False),
                decision_json=stored_decision.model_dump_json(), summary_en=record.summary_en,
                summary_ar=record.summary_ar, risk=record.risk.value,
            ))
        log.info("approval %s requested for %s/%s (%s risk)", record.id, record.agent_id, record.tool,
                 record.risk.value)
        await self.notifier.publish("approval.requested", record.model_dump(mode="json"))
        self._schedule_push(record)

        if self.auto_decider is not None:
            verdict = self._run_auto_decider(record)
            if verdict is not None:
                return await self.decide(record.id, approve=verdict, user=AUTO_DECIDER_USER,
                                         note="decided automatically")
        return record

    def _run_auto_decider(self, record: ApprovalRecord) -> bool | None:
        try:
            verdict = self.auto_decider(record) if self.auto_decider else None
        except Exception:
            log.exception("auto_decider failed for approval %s; leaving it to a human", record.id)
            return None
        if verdict is None:
            return None
        return bool(verdict)

    def _schedule_push(self, record: ApprovalRecord) -> None:
        if not self.notifier.push_enabled:
            return
        task = asyncio.get_running_loop().create_task(self._push(record))
        self._background.add(task)
        task.add_done_callback(self._background.discard)

    async def _push(self, record: ApprovalRecord) -> None:
        try:
            subs = load_push_subscriptions(self.db)
            payload = {
                "type": "approval.requested", "id": record.id, "tool": record.tool, "risk": record.risk.value,
                "title": "Mirsad: approval needed", "title_ar": "مرصاد: مطلوب موافقتك",
                "body": record.summary_en, "body_ar": record.summary_ar,
                "url": f"/approve#/approvals/{record.id}", "expires_at": record.expires_at,
            }
            report = await self.notifier.web_push_detailed(subs, payload)
            if report.stale_endpoints:
                delete_push_subscriptions(self.db, report.stale_endpoints)
            log.info("web push for %s: %d sent, %d failed", record.id, report.sent, report.failed)
        except Exception:
            log.exception("web push for approval %s failed", record.id)

    # -- read --------------------------------------------------------------------------------

    def get(self, approval_id: str) -> ApprovalRecord | None:
        with self.db.session() as sess:
            row = sess.get(ApprovalRow, approval_id)
            return _row_to_record(row) if row else None

    def list(self, *, status: ApprovalStatus | None = None, limit: int = 100) -> list[ApprovalRecord]:
        """Newest first, optionally filtered by status."""
        stmt = select(ApprovalRow).order_by(ApprovalRow.created_at.desc()).limit(max(1, min(int(limit), 1000)))
        if status is not None:
            stmt = stmt.where(ApprovalRow.status == ApprovalStatus(status).value)
        with self.db.session() as sess:
            return [_row_to_record(r) for r in sess.scalars(stmt).all()]

    # -- transitions -------------------------------------------------------------------------

    def _transition(self, approval_id: str, status: ApprovalStatus, *, user: str | None,
                    note: str | None, now: float) -> bool:
        """Atomically move a pending approval to ``status``; False if it was no longer pending."""
        with self.db.session() as sess:
            row = sess.get(ApprovalRow, approval_id)
            if row is None:
                raise ApprovalNotFound(approval_id)
            decision = Decision.model_validate_json(row.decision_json)
            decision_json = decision.model_copy(update={"approval_status": status.value}).model_dump_json()
            result = sess.execute(
                update(ApprovalRow)
                .where(ApprovalRow.id == approval_id, ApprovalRow.status == ApprovalStatus.PENDING.value)
                .values(status=status.value, decided_by=user, decided_at=now, note=note, decision_json=decision_json)
                .execution_options(synchronize_session=False)
            )
            return bool(result.rowcount)

    def _notify_waiters(self, approval_id: str) -> None:
        with self._waiters_lock:
            waiters = list(self._waiters.get(approval_id, ()))
        current = None
        try:
            current = asyncio.get_running_loop()
        except RuntimeError:
            pass
        for loop, event in waiters:
            if loop is current:
                event.set()
            elif not loop.is_closed():
                loop.call_soon_threadsafe(event.set)

    async def decide(self, approval_id: str, *, approve: bool, user: str, note: str | None = None) -> ApprovalRecord:
        """Approve or deny a pending request.

        Raises :class:`ApprovalNotFound` for an unknown id and ``ValueError`` when the
        approval was already decided, cancelled or has expired.
        """
        if not user:
            raise ValueError("user is required")
        now = time.time()
        current = self.get(approval_id)
        if current is None:
            raise ApprovalNotFound(approval_id)
        if current.status != ApprovalStatus.PENDING:
            raise ValueError(f"approval {approval_id} is already {current.status.value}")
        if current.expires_at <= now:
            await self._expire(approval_id, now)
            raise ValueError(f"approval {approval_id} has expired")
        status = ApprovalStatus.APPROVED if approve else ApprovalStatus.DENIED
        if not self._transition(approval_id, status, user=user, note=note, now=now):
            latest = self.get(approval_id)
            raise ValueError(f"approval {approval_id} is already {latest.status.value if latest else 'gone'}")
        record = self.get(approval_id)
        assert record is not None
        log.info("approval %s %s by %s", approval_id, status.value, user)
        self._notify_waiters(approval_id)
        await self.notifier.publish("approval.decided", record.model_dump(mode="json"))
        return record

    async def cancel(self, approval_id: str, *, user: str = "system", note: str | None = None) -> ApprovalRecord:
        """Withdraw a pending request (e.g. the agent session ended). Raises like :meth:`decide`."""
        now = time.time()
        if not self._transition(approval_id, ApprovalStatus.CANCELLED, user=user, note=note, now=now):
            latest = self.get(approval_id)
            raise ValueError(f"approval {approval_id} is already {latest.status.value if latest else 'gone'}")
        record = self.get(approval_id)
        assert record is not None
        self._notify_waiters(approval_id)
        await self.notifier.publish("approval.decided", record.model_dump(mode="json"))
        return record

    async def _expire(self, approval_id: str, now: float) -> bool:
        if not self._transition(approval_id, ApprovalStatus.EXPIRED, user=None, note="no decision before the deadline",
                                now=now):
            return False
        log.info("approval %s expired", approval_id)
        self._notify_waiters(approval_id)
        record = self.get(approval_id)
        if record is not None:
            await self.notifier.publish("approval.decided", record.model_dump(mode="json"))
        return True

    def expire_overdue(self) -> int:
        """Expire every pending approval past its deadline; returns how many were expired."""
        now = time.time()
        with self.db.session() as sess:
            ids = list(sess.scalars(
                select(ApprovalRow.id).where(ApprovalRow.status == ApprovalStatus.PENDING.value,
                                             ApprovalRow.expires_at <= now)
            ).all())
        expired = 0
        for approval_id in ids:
            if self._transition(approval_id, ApprovalStatus.EXPIRED, user=None,
                                note="no decision before the deadline", now=now):
                expired += 1
                self._notify_waiters(approval_id)
                record = self.get(approval_id)
                if record is not None:
                    self.notifier.publish_nowait("approval.decided", record.model_dump(mode="json"))
        if expired:
            log.info("expired %d overdue approval(s)", expired)
        return expired

    # -- wait --------------------------------------------------------------------------------

    async def wait(self, approval_id: str, timeout_s: float | None = None) -> ApprovalRecord:
        """Block until the approval leaves ``pending``; at the deadline it becomes EXPIRED.

        The deadline is the record's ``expires_at``, or ``timeout_s`` from now if that
        is sooner. Expiring on timeout prevents a late approval of an action the agent
        was already told was denied.
        """
        loop = asyncio.get_running_loop()
        event = asyncio.Event()
        entry = (loop, event)
        with self._waiters_lock:
            self._waiters.setdefault(approval_id, []).append(entry)
        try:
            deadline: float | None = None
            while True:
                # Clear before reading: a decision committed after the read still sets the event.
                event.clear()
                record = self.get(approval_id)
                if record is None:
                    raise ApprovalNotFound(approval_id)
                if deadline is None:
                    deadline = record.expires_at
                    if timeout_s is not None:
                        deadline = min(deadline, time.time() + max(0.0, timeout_s))
                if record.status in _TERMINAL:
                    return record
                remaining = deadline - time.time()
                if remaining <= 0:
                    await self._expire(approval_id, time.time())
                    return self.get(approval_id) or record
                try:
                    await asyncio.wait_for(event.wait(), timeout=min(remaining, CROSS_PROCESS_RECHECK_S))
                except TimeoutError:
                    pass
        finally:
            with self._waiters_lock:
                entries = self._waiters.get(approval_id, [])
                if entry in entries:
                    entries.remove(entry)
                if not entries:
                    self._waiters.pop(approval_id, None)

    async def aclose(self) -> None:
        """Wait for background Web Push deliveries (call on shutdown)."""
        if self._background:
            await asyncio.gather(*self._background, return_exceptions=True)
