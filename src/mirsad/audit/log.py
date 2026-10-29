"""Tamper-evident audit log: an HMAC-SHA256 hash chain stored in ``audit_events``.

Every event stores ``prev_hash`` (the hash of the event before it, or
``GENESIS_HASH`` for the first) and ``hash = HMAC(key, prev_hash | canonical_json(event))``.
Editing, deleting, inserting or reordering a stored event therefore breaks the chain
at that point, and recomputing the hashes requires the HMAC key. Truncating the
tail of the chain or a full rewrite by someone holding the key are only detectable
against an externally stored anchor (see :meth:`AuditLog.anchor`).
"""

from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import logging
import random
import threading
import time
from collections.abc import Callable, Iterable, Iterator
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.exc import IntegrityError

from mirsad.audit.redact import redact, to_jsonable
from mirsad.models import AuditEvent
from mirsad.storage import AuditEventRow, Database

log = logging.getLogger("mirsad.audit")

GENESIS_HASH = "0" * 64
EXPORT_FORMAT = "mirsad-audit-export/1"
_MAX_APPEND_RETRIES = 30
# Jittered exponential backoff between seq-conflict retries: without it two writers re-read the head in
# lockstep and keep colliding until one of them gives up.
_RETRY_BASE_DELAY_S = 0.001
_RETRY_MAX_DELAY_S = 0.05
_VERIFY_BATCH = 1000
_MIN_STRING_BUDGET = 64
_CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
_CSV_COLUMNS = (
    "seq", "ts", "ts_iso", "event_type", "session_id", "agent_id", "tool", "call_id",
    "action", "risk", "policy_version", "payload_json", "prev_hash", "hash",
)


class AuditVerifyReport(BaseModel):
    """Outcome of verifying the hash chain."""

    ok: bool
    checked: int = 0                     # events whose link and HMAC were verified
    head_seq: int = 0                    # last event in the log (0 when empty)
    head_hash: str = GENESIS_HASH
    first_bad_seq: int | None = None     # first event that failed verification
    message: str = ""
    anchor_ok: bool | None = None        # None when no anchor was supplied
    verified_at: float = Field(default_factory=time.time)


# ----------------------------------------------------------------------------- hashing helpers


def canonical_json(value: Any) -> str:
    """Deterministic JSON: sorted keys, no whitespace, UTF-8 (``ensure_ascii=False``)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def audit_key_from_secret(secret: str | bytes) -> bytes:
    """Derive a dedicated audit HMAC key from the application secret (key separation from JWTs)."""
    raw = secret.encode() if isinstance(secret, str) else secret
    return hmac.new(raw, b"mirsad/audit-hmac/v1", hashlib.sha256).digest()


_HASHED_FIELDS = tuple(f for f in AuditEvent.model_fields if f != "hash")


def _event_body(event: AuditEvent | dict[str, Any]) -> dict[str, Any]:
    # Attribute access (not model_dump) so the hashed values are exactly what was stored.
    if isinstance(event, AuditEvent):
        return {f: getattr(event, f) for f in _HASHED_FIELDS}
    return {f: event.get(f) for f in _HASHED_FIELDS}


def compute_hash(key: bytes, prev_hash: str, event: AuditEvent | dict[str, Any]) -> str:
    """``HMAC-SHA256(key, prev_hash + "|" + canonical_json(event_without_hash))`` as hex."""
    message = f"{prev_hash}|{canonical_json(_event_body(event))}".encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def verify_events(
    events: Iterable[AuditEvent | dict[str, Any]],
    hmac_key: bytes,
    *,
    anchor: dict[str, Any] | None = None,
    start_prev_hash: str = GENESIS_HASH,
    start_seq: int = 1,
) -> AuditVerifyReport:
    """Verify a sequence of events (ordered by seq) against the key.

    Usable on a live log or on an offline JSON export. ``anchor`` is an object
    previously returned by :meth:`AuditLog.anchor`; the event with that seq must
    exist with exactly that hash, which detects tail truncation and rewrites.
    """
    expected_seq = start_seq
    prev_hash = start_prev_hash
    checked = 0
    head_seq, head_hash = 0, GENESIS_HASH
    anchor_seq = int(anchor["seq"]) if anchor else None
    anchor_ok: bool | None = None if anchor is None else False
    if anchor is not None and anchor_seq == 0:
        anchor_ok = anchor.get("hash") == GENESIS_HASH

    def fail(seq: int, message: str) -> AuditVerifyReport:
        log.warning("audit chain verification failed at seq %s: %s", seq, message)
        return AuditVerifyReport(
            ok=False, checked=checked, head_seq=head_seq, head_hash=head_hash,
            first_bad_seq=seq, message=message, anchor_ok=anchor_ok,
        )

    for raw in events:
        event = raw if isinstance(raw, AuditEvent) else AuditEvent.model_validate(raw)
        head_seq, head_hash = event.seq, event.hash
        if event.seq != expected_seq:
            if event.seq > expected_seq:
                missing = f"{expected_seq}" if event.seq == expected_seq + 1 else f"{expected_seq}-{event.seq - 1}"
                return fail(event.seq, f"event(s) missing before seq {event.seq} (seq {missing} deleted?)")
            return fail(event.seq, f"seq {event.seq} out of order (expected {expected_seq}): rows reordered or duplicated")
        if not hmac.compare_digest(event.prev_hash, prev_hash):
            return fail(event.seq, f"seq {event.seq}: prev_hash does not link to the previous event "
                                   "(event inserted, removed or reordered)")
        expected = compute_hash(hmac_key, event.prev_hash, event)
        if not hmac.compare_digest(expected, event.hash):
            return fail(event.seq, f"seq {event.seq}: HMAC mismatch, the event was modified or its hash forged")
        if anchor_seq is not None and event.seq == anchor_seq:
            anchor_ok = hmac.compare_digest(event.hash, str(anchor.get("hash", "")))
            if not anchor_ok:
                return fail(event.seq, f"seq {event.seq}: hash differs from the external anchor (chain rewritten)")
        checked += 1
        prev_hash = event.hash
        expected_seq += 1

    if anchor_seq is not None and anchor_seq > head_seq:
        anchor_ok = False
        return fail(head_seq + 1, f"anchored seq {anchor_seq} is missing: the log was truncated after seq {head_seq}")
    message = f"OK: {checked} event(s) verified" + (", anchor matches" if anchor_ok else "")
    return AuditVerifyReport(ok=True, checked=checked, head_seq=head_seq, head_hash=head_hash,
                             message=message, anchor_ok=anchor_ok)


# ----------------------------------------------------------------------------- payload sizing


def _iter_strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _iter_strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _iter_strings(v)


def _clip_strings(value: Any, budget: int) -> Any:
    if isinstance(value, str):
        if len(value) <= budget:
            return value
        return value[:budget] + f"…[+{len(value) - budget} chars]"
    if isinstance(value, dict):
        return {k: _clip_strings(v, budget) for k, v in value.items()}
    if isinstance(value, list):
        return [_clip_strings(v, budget) for v in value]
    return value


def truncate_payload(payload: dict[str, Any], max_chars: int) -> dict[str, Any]:
    """Shrink a payload so its canonical JSON fits ``max_chars``, marking it ``_truncated``.

    Long strings are clipped first (largest budget that fits, found by binary search)
    so the payload keeps its structure; if that is not enough the payload is
    replaced by a JSON preview.
    """
    original = len(canonical_json(payload))
    if original <= max_chars:
        return payload
    marker = {"_truncated": True, "_original_chars": original}
    longest = max((len(s) for s in _iter_strings(payload)), default=0)
    lo, hi, best = _MIN_STRING_BUDGET, max(longest, _MIN_STRING_BUDGET), None
    while lo <= hi:
        mid = (lo + hi) // 2
        candidate = {**_clip_strings(payload, mid), **marker}
        if len(canonical_json(candidate)) <= max_chars:
            best, lo = candidate, mid + 1
        else:
            hi = mid - 1
    if best is not None:
        return best
    preview_len = max(0, max_chars - 200)
    return {**marker, "_preview": canonical_json(payload)[:preview_len]}


# ----------------------------------------------------------------------------- the log


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(value.value) if isinstance(value, Enum) else str(value)


def _to_ts(value: float | int | datetime | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.timestamp()
    return float(value)


def _row_to_event(row: AuditEventRow) -> AuditEvent:
    return AuditEvent(
        seq=row.seq, ts=row.ts, event_type=row.event_type, session_id=row.session_id,
        agent_id=row.agent_id, tool=row.tool, call_id=row.call_id, action=row.action, risk=row.risk,
        policy_version=row.policy_version, payload=json.loads(row.payload_json or "{}"),
        prev_hash=row.prev_hash, hash=row.hash,
    )


def _csv_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    # Neutralise spreadsheet formula injection: payloads carry attacker-controlled text.
    if text.startswith(_CSV_FORMULA_PREFIXES):
        return "'" + text
    return text


class AuditLog:
    """Append-only, hash-chained audit trail backed by the ``audit_events`` table."""

    def __init__(self, db: Database, hmac_key: bytes, *, payload_max_chars: int = 20_000) -> None:
        if isinstance(hmac_key, str):
            hmac_key = hmac_key.encode()
        if not hmac_key:
            raise ValueError("audit HMAC key must not be empty")
        if payload_max_chars < 256:
            raise ValueError("payload_max_chars must be at least 256")
        self.db = db
        self._key = bytes(hmac_key)
        self.payload_max_chars = payload_max_chars
        self._lock = threading.Lock()
        self._listeners: list[Callable[[AuditEvent], None]] = []

    # -- listeners ---------------------------------------------------------------------------

    def add_listener(self, fn: Callable[[AuditEvent], None]) -> None:
        """Call ``fn(event)`` after every committed append (e.g. to fan out SSE ``audit.event``)."""
        self._listeners.append(fn)

    def remove_listener(self, fn: Callable[[AuditEvent], None]) -> None:
        if fn in self._listeners:
            self._listeners.remove(fn)

    # -- write -------------------------------------------------------------------------------

    def append(
        self,
        event_type: str,
        *,
        session_id: str | None = None,
        agent_id: str | None = None,
        tool: str | None = None,
        call_id: str | None = None,
        action: Any = None,
        risk: Any = None,
        policy_version: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Redact, truncate, chain and persist one event. Thread-safe (single writer)."""
        if not event_type:
            raise ValueError("event_type is required")
        clean = redact(payload or {})
        if not isinstance(clean, dict):
            clean = {"value": clean}
        clean = truncate_payload(clean, self.payload_max_chars)
        payload_json = canonical_json(clean)
        fields = {
            "event_type": event_type, "session_id": session_id, "agent_id": agent_id, "tool": tool,
            "call_id": call_id, "action": _enum_value(action), "risk": _enum_value(risk),
            "policy_version": policy_version,
        }

        event: AuditEvent | None = None
        with self._lock:
            for attempt in range(_MAX_APPEND_RETRIES):
                try:
                    event = self._append_locked(fields, clean, payload_json)
                    break
                except IntegrityError:
                    # Another process appended the same seq first: back off, re-read the head and retry.
                    log.info("audit seq conflict, retrying (attempt %d)", attempt + 1)
                    delay = min(_RETRY_MAX_DELAY_S, _RETRY_BASE_DELAY_S * 2**attempt)
                    time.sleep(random.uniform(0, delay))  # noqa: S311  # nosec B311 - timing jitter, not crypto
            else:
                raise RuntimeError("could not append audit event after repeated seq conflicts")

        for listener in list(self._listeners):
            try:
                listener(event)
            except Exception:
                log.exception("audit listener failed")
        return event

    def _append_locked(self, fields: dict[str, Any], payload: dict[str, Any], payload_json: str) -> AuditEvent:
        with self.db.session() as sess:
            last = sess.execute(
                select(AuditEventRow.seq, AuditEventRow.hash).order_by(AuditEventRow.seq.desc()).limit(1)
            ).first()
            prev_seq, prev_hash = (last[0], last[1]) if last else (0, GENESIS_HASH)
            body = {**fields, "seq": prev_seq + 1, "ts": round(time.time(), 6), "payload": payload,
                    "prev_hash": prev_hash}
            digest = compute_hash(self._key, prev_hash, body)
            sess.add(AuditEventRow(
                seq=body["seq"], ts=body["ts"], payload_json=payload_json, prev_hash=prev_hash, hash=digest,
                **fields,
            ))
        return AuditEvent(**body, hash=digest)

    # -- read --------------------------------------------------------------------------------

    def get(self, seq: int) -> AuditEvent | None:
        with self.db.session() as sess:
            row = sess.get(AuditEventRow, seq)
            return _row_to_event(row) if row else None

    def head(self) -> tuple[int, str]:
        """``(seq, hash)`` of the newest event, ``(0, GENESIS_HASH)`` when empty."""
        with self.db.session() as sess:
            last = sess.execute(
                select(AuditEventRow.seq, AuditEventRow.hash).order_by(AuditEventRow.seq.desc()).limit(1)
            ).first()
        return (last[0], last[1]) if last else (0, GENESIS_HASH)

    def anchor(self) -> dict[str, Any]:
        """Current head as ``{seq, hash, ts}`` to publish or store outside the database."""
        seq, digest = self.head()
        return {"seq": seq, "hash": digest, "ts": time.time()}

    def _iter_rows(self, *, start_after: int = 0) -> Iterator[AuditEvent]:
        last = start_after
        while True:
            with self.db.session() as sess:
                rows = sess.scalars(
                    select(AuditEventRow).where(AuditEventRow.seq > last)
                    .order_by(AuditEventRow.seq.asc()).limit(_VERIFY_BATCH)
                ).all()
                batch = [_row_to_event(r) for r in rows]
            if not batch:
                return
            yield from batch
            last = batch[-1].seq

    def verify(self, *, anchor: dict[str, Any] | None = None) -> AuditVerifyReport:
        """Re-walk the whole chain; optionally also check an external ``anchor``."""
        report = verify_events(self._iter_rows(), self._key, anchor=anchor)
        if report.ok:
            log.info("audit chain verified: %s", report.message)
        return report

    @staticmethod
    def _filters(
        *, agent_id: str | None = None, tool: str | None = None, action: str | None = None,
        event_type: str | None = None, session_id: str | None = None, call_id: str | None = None,
        since: float | datetime | None = None, until: float | datetime | None = None, text: str | None = None,
    ) -> list[ColumnElement[bool]]:
        conds: list[ColumnElement[bool]] = []
        for column, value in (
            (AuditEventRow.agent_id, agent_id), (AuditEventRow.tool, tool),
            (AuditEventRow.action, _enum_value(action)), (AuditEventRow.event_type, event_type),
            (AuditEventRow.session_id, session_id), (AuditEventRow.call_id, call_id),
        ):
            if value not in (None, ""):
                conds.append(column == value)
        since_ts, until_ts = _to_ts(since), _to_ts(until)
        if since_ts is not None:
            conds.append(AuditEventRow.ts >= since_ts)
        if until_ts is not None:
            conds.append(AuditEventRow.ts <= until_ts)
        if text:
            needle = text.lower()
            conds.append(or_(
                func.lower(AuditEventRow.payload_json).contains(needle, autoescape=True),
                func.lower(AuditEventRow.tool).contains(needle, autoescape=True),
                func.lower(AuditEventRow.agent_id).contains(needle, autoescape=True),
            ))
        return conds

    def query(
        self,
        *,
        agent_id: str | None = None,
        tool: str | None = None,
        action: str | None = None,
        event_type: str | None = None,
        session_id: str | None = None,
        call_id: str | None = None,
        since: float | datetime | None = None,
        until: float | datetime | None = None,
        text: str | None = None,
        limit: int = 100,
        offset: int = 0,
        order: Literal["asc", "desc"] = "desc",
    ) -> tuple[list[AuditEvent], int]:
        """Filtered page of events plus the total number of matches (ignoring limit/offset)."""
        if order not in ("asc", "desc"):
            raise ValueError("order must be 'asc' or 'desc'")
        limit = max(0, min(int(limit), 10_000))
        offset = max(0, int(offset))
        conds = self._filters(agent_id=agent_id, tool=tool, action=action, event_type=event_type,
                              session_id=session_id, call_id=call_id, since=since, until=until, text=text)
        where = and_(*conds) if conds else None
        order_by = AuditEventRow.seq.asc() if order == "asc" else AuditEventRow.seq.desc()
        with self.db.session() as sess:
            count_stmt = select(func.count()).select_from(AuditEventRow)
            stmt = select(AuditEventRow).order_by(order_by).limit(limit).offset(offset)
            if where is not None:
                count_stmt = count_stmt.where(where)
                stmt = stmt.where(where)
            total = int(sess.scalar(count_stmt) or 0)
            rows = sess.scalars(stmt).all()
            return [_row_to_event(r) for r in rows], total

    def _iter_query(self, filters: dict[str, Any]) -> Iterator[AuditEvent]:
        filters = dict(filters)
        order = filters.pop("order", "asc")
        limit = filters.pop("limit", None)
        offset = int(filters.pop("offset", 0) or 0)
        remaining = None if limit is None else max(0, int(limit))
        while remaining is None or remaining > 0:
            page_size = _VERIFY_BATCH if remaining is None else min(_VERIFY_BATCH, remaining)
            items, _ = self.query(**filters, limit=page_size, offset=offset, order=order)
            if not items:
                return
            yield from items
            offset += len(items)
            if remaining is not None:
                remaining -= len(items)
            if len(items) < page_size:
                return

    def export(self, fmt: Literal["json", "csv"], **filters: Any) -> str:
        """Export matching events (all of them unless ``limit`` is given), oldest first by default.

        JSON keeps the exact chained fields so an unfiltered export can be verified
        offline with :func:`verify_events`; CSV is meant for spreadsheet review.
        """
        if fmt not in ("json", "csv"):
            raise ValueError("fmt must be 'json' or 'csv'")
        unknown = set(filters) - {"agent_id", "tool", "action", "event_type", "session_id", "call_id",
                                  "since", "until", "text", "limit", "offset", "order"}
        if unknown:
            raise TypeError(f"unknown export filter(s): {', '.join(sorted(unknown))}")
        events = self._iter_query(filters)
        if fmt == "json":
            seq, digest = self.head()
            doc = {
                "format": EXPORT_FORMAT,
                "exported_at": time.time(),
                "filters": to_jsonable({k: v for k, v in filters.items() if v is not None}),
                "head": {"seq": seq, "hash": digest},
                "events": [e.model_dump(mode="json") for e in events],
            }
            doc["count"] = len(doc["events"])
            return json.dumps(doc, ensure_ascii=False, indent=2)

        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(_CSV_COLUMNS)
        for e in events:
            iso = datetime.fromtimestamp(e.ts, tz=UTC).isoformat()
            writer.writerow([_csv_cell(v) for v in (
                e.seq, e.ts, iso, e.event_type, e.session_id, e.agent_id, e.tool, e.call_id, e.action,
                e.risk, e.policy_version, canonical_json(e.payload), e.prev_hash, e.hash,
            )])
        return buf.getvalue()
