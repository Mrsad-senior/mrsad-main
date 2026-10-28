"""Per-session taint state: which untrusted and confidential data each agent session has seen."""

from __future__ import annotations

import heapq
import logging
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any, NamedTuple

from mirsad.models import (
    DetectionResult,
    Reason,
    Sensitivity,
    SessionSnapshot,
    SinkKind,
    TaintedValue,
    ToolCall,
    ToolProfile,
    ToolResult,
    Trust,
)
from mirsad.taint.extract import NGRAM_SIZE, ExtractedValue, extract_values
from mirsad.taint.rules import ResolvedTaintSettings, TaintView, ValueLike, evaluate_rules

if TYPE_CHECKING:
    from mirsad.policy import TaintSettings

logger = logging.getLogger("mirsad.taint")

MAX_UNTRUSTED_SOURCES = 100  # most recent untrusted source entries kept per session


class _Val(NamedTuple):
    """Internal, immutable twin of :class:`mirsad.models.TaintedValue` (cheaper to store)."""

    value: str
    kind: str
    field: str | None
    source_tool: str
    source_call_id: str
    trust: Trust
    sensitivity: Sensitivity
    trusted_field: bool


def _to_model(v: ValueLike) -> TaintedValue:
    if isinstance(v, TaintedValue):
        return v.model_copy()
    # Fields were validated when the _Val was built, so skip re-validation.
    return TaintedValue.model_construct(**v._asdict())  # type: ignore[attr-defined]


class _Session:
    __slots__ = (
        "session_id",
        "agent_id",
        "untrusted_sources",
        "max_sensitivity",
        "injection_detected",
        "call_count",
        "atomic",
        "ngrams",
        "seq",
        "last_seen",
        "evicted",
        "_view",
    )

    def __init__(self, session_id: str, agent_id: str, now: float) -> None:
        self.session_id = session_id
        self.agent_id = agent_id
        self.untrusted_sources: list[str] = []
        self.max_sensitivity = Sensitivity.PUBLIC
        self.injection_detected = False
        self.call_count = 0
        # key -> (insertion sequence, value); two pools so long texts cannot flush identifiers.
        self.atomic: OrderedDict[tuple, tuple[int, _Val]] = OrderedDict()
        self.ngrams: OrderedDict[tuple, tuple[int, _Val]] = OrderedDict()
        self.seq = 0
        self.last_seen = now
        self.evicted = 0
        self._view: TaintView | None = None

    def mark_injection(self) -> None:
        if not self.injection_detected:
            self.injection_detected = True
            self._view = None

    def add_source(self, entry: str) -> None:
        if entry in self.untrusted_sources:
            return
        self.untrusted_sources.append(entry)
        if len(self.untrusted_sources) > MAX_UNTRUSTED_SOURCES:
            del self.untrusted_sources[0]
        self._view = None

    def add_value(self, val: _Val, max_values: int, max_ngrams: int) -> None:
        pool = self.ngrams if val.kind == "ngram" else self.atomic
        key = (val.kind, val.value, val.source_call_id, val.field, val.trusted_field)
        if key in pool:
            return
        self.seq += 1
        pool[key] = (self.seq, val)
        self._view = None
        while len(self.ngrams) > max_ngrams:
            self.ngrams.popitem(last=False)
            self.evicted += 1
        while len(self.atomic) + len(self.ngrams) > max_values:
            oldest_atomic = next(iter(self.atomic.values()))[0] if self.atomic else None
            oldest_ngram = next(iter(self.ngrams.values()))[0] if self.ngrams else None
            if oldest_ngram is not None and (oldest_atomic is None or oldest_ngram < oldest_atomic):
                self.ngrams.popitem(last=False)
            else:
                self.atomic.popitem(last=False)
            self.evicted += 1

    def ordered_values(self) -> list[_Val]:
        merged = heapq.merge(self.atomic.values(), self.ngrams.values(), key=lambda item: item[0])
        return [val for _, val in merged]

    def view(self) -> TaintView:
        if self._view is None:
            self._view = TaintView.build(
                untrusted_sources=self.untrusted_sources,
                injection_detected=self.injection_detected,
                values=self.ordered_values(),
            )
        return self._view

    def to_snapshot(self, values: Iterable[ValueLike] | None = None) -> SessionSnapshot:
        return SessionSnapshot(
            session_id=self.session_id,
            agent_id=self.agent_id,
            untrusted_sources=list(self.untrusted_sources),
            max_sensitivity=self.max_sensitivity,
            injection_detected=self.injection_detected,
            values=[_to_model(v) for v in (self.ordered_values() if values is None else values)],
            call_count=self.call_count,
        )


class TaintTracker:
    """Thread-safe per-session taint state plus the four taint rules (spec section 3).

    Sessions are keyed by ``(agent_id, session_id)``. Each session keeps at most
    ``max_values_per_session`` values (n-grams may use at most half of that budget); the
    oldest are evicted first. Sessions idle for longer than ``session_ttl_s`` are dropped.
    """

    def __init__(
        self,
        *,
        max_values_per_session: int = 2000,
        session_ttl_s: float = 6 * 3600,
        ngram_size: int = NGRAM_SIZE,
        ngram_stride: int = 1,
        internal_domains: Iterable[str] | Callable[[], Iterable[str]] = (),
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_values_per_session < 2:
            raise ValueError("max_values_per_session must be >= 2")
        if session_ttl_s <= 0:
            raise ValueError("session_ttl_s must be > 0")
        if ngram_size < 2 or ngram_stride < 1:
            raise ValueError("ngram_size must be >= 2 and ngram_stride >= 1")
        self.max_values_per_session = max_values_per_session
        self.max_ngrams_per_session = max_values_per_session // 2
        self.session_ttl_s = float(session_ttl_s)
        self.ngram_size = ngram_size
        self.ngram_stride = ngram_stride
        # A callable lets the app pass the *active* policy's domains (policies are hot-swappable).
        self._internal_domains = internal_domains if callable(internal_domains) else tuple(internal_domains)
        self._clock = clock
        self._lock = threading.RLock()
        self._sessions: dict[tuple[str, str], _Session] = {}
        self._sweep_interval = min(60.0, self.session_ttl_s / 4)
        self._last_sweep = clock()

    @property
    def internal_domains(self) -> tuple[str, ...]:
        """Organisation domains never matched at domain level (in addition to ``settings``)."""
        source = self._internal_domains() if callable(self._internal_domains) else self._internal_domains
        return tuple(d.strip().lower() for d in source if d and d.strip())

    # ------------------------------------------------------------------ session store

    def _sweep(self, now: float, *, force: bool = False) -> None:
        if not force and now - self._last_sweep < self._sweep_interval:
            return
        self._last_sweep = now
        expired = [k for k, s in self._sessions.items() if now - s.last_seen > self.session_ttl_s]
        for key in expired:
            del self._sessions[key]
        if expired:
            logger.info("evicted %d idle taint session(s)", len(expired))

    def _find(self, agent_id: str, session_id: str) -> _Session | None:
        """Live session or None; touches it. Caller holds the lock."""
        now = self._clock()
        self._sweep(now)
        key = (agent_id, session_id)
        session = self._sessions.get(key)
        if session is not None and now - session.last_seen > self.session_ttl_s:
            del self._sessions[key]
            return None
        if session is not None:
            session.last_seen = now
        return session

    def _get_or_create(self, agent_id: str, session_id: str) -> _Session:
        session = self._find(agent_id, session_id)
        if session is None:
            session = _Session(session_id, agent_id, self._clock())
            self._sessions[(agent_id, session_id)] = session
        return session

    def active_sessions(self) -> int:
        """Number of sessions currently held (after evicting idle ones)."""
        with self._lock:
            self._sweep(self._clock(), force=True)
            return len(self._sessions)

    # ------------------------------------------------------------------ public API

    def snapshot(self, session_id: str, agent_id: str) -> SessionSnapshot:
        """Deep copy of the session's taint state; an unknown session is created empty."""
        with self._lock:
            return self._get_or_create(agent_id, session_id).to_snapshot()

    def register_result(
        self,
        result: ToolResult,
        profile: ToolProfile,
        detection: DetectionResult | None,
        settings: TaintSettings | Any,
    ) -> SessionSnapshot:
        """Record what a tool result revealed to the session and return the updated snapshot.

        Untrusted results taint the session. A result whose detection label is ``injection``
        is treated as untrusted even when the tool is declared trusted: evidence of an attack
        overrides the declared trust.
        """
        cfg = ResolvedTaintSettings.from_any(settings)
        injection = detection is not None and detection.label == "injection"
        trust = Trust.UNTRUSTED if injection else Trust(profile.trust)
        sensitivity = Sensitivity(profile.sensitivity)
        # n-grams only matter for TAINT_CONFIDENTIAL_TO_EXTERNAL, so only confidential text is hashed.
        extracted = self._extract(
            result, cfg.trusted_fields, include_ngrams=sensitivity == Sensitivity.CONFIDENTIAL
        )
        with self._lock:
            session = self._get_or_create(result.agent_id, result.session_id)
            if trust == Trust.UNTRUSTED:
                session.add_source(f"{result.tool}:{result.call_id}")
            if sensitivity.rank > session.max_sensitivity.rank:
                session.max_sensitivity = sensitivity
            if injection:
                session.mark_injection()
            evicted_before = session.evicted
            for ev in extracted:
                session.add_value(
                    _Val(
                        ev.value,
                        ev.kind,
                        ev.field,
                        result.tool,
                        result.call_id,
                        trust,
                        sensitivity,
                        ev.trusted_field,
                    ),
                    self.max_values_per_session,
                    self.max_ngrams_per_session,
                )
            logger.debug(
                "registered %s/%s (%s, %s): %d values, %d evicted",
                result.session_id,
                result.tool,
                trust.value,
                sensitivity.value,
                len(extracted),
                session.evicted - evicted_before,
            )
            return session.to_snapshot()

    def evaluate_call(
        self,
        call: ToolCall,
        profile: ToolProfile,
        sink: SinkKind,
        settings: TaintSettings | Any,
        snapshot: SessionSnapshot | None = None,
    ) -> list[Reason]:
        """Taint reasons for a pending call.

        With ``snapshot`` this is a pure function of its arguments (audit replay); otherwise
        the live session state is used. It never changes tracker state.
        """
        return evaluate_rules(
            call,
            profile,
            sink,
            settings,
            self._view_for(call, snapshot),
            ngram_size=self.ngram_size,
            internal_domains=self.internal_domains,
        )

    def minimal_snapshot(
        self,
        call: ToolCall,
        profile: ToolProfile,
        sink: SinkKind,
        settings: TaintSettings | Any,
        snapshot: SessionSnapshot | None = None,
    ) -> SessionSnapshot:
        """A reduced snapshot for which ``evaluate_call`` returns exactly the same reasons.

        It keeps the session flags and only the values the rules consulted for this call,
        which keeps audit payloads small while preserving deterministic replay.
        """
        if snapshot is None:
            with self._lock:
                session = self._find(call.agent_id, call.session_id)
                if session is None:
                    view = TaintView.empty()
                    base = SessionSnapshot(session_id=call.session_id, agent_id=call.agent_id)
                else:
                    view = session.view()
                    base = session.to_snapshot(values=())
        else:
            view = self._view_from_snapshot(snapshot)
            base = SessionSnapshot(
                session_id=snapshot.session_id,
                agent_id=snapshot.agent_id,
                untrusted_sources=list(snapshot.untrusted_sources),
                max_sensitivity=snapshot.max_sensitivity,
                injection_detected=snapshot.injection_detected,
                call_count=snapshot.call_count,
            )
        touched: set[int] = set()
        evaluate_rules(
            call,
            profile,
            sink,
            settings,
            view,
            touched=touched,
            ngram_size=self.ngram_size,
            internal_domains=self.internal_domains,
        )
        base.values = [_to_model(view.values[i]) for i in sorted(touched)]
        return base

    def note_call(self, call: ToolCall) -> None:
        """Count a tool call against its session (called by the gateway after each decision)."""
        with self._lock:
            self._get_or_create(call.agent_id, call.session_id).call_count += 1

    def reset(self, session_id: str | None = None) -> None:
        """Forget one session (for every agent using that id) or, with no argument, all sessions."""
        with self._lock:
            if session_id is None:
                self._sessions.clear()
                return
            for key in [k for k in self._sessions if k[1] == session_id]:
                del self._sessions[key]

    # ------------------------------------------------------------------ internals

    @staticmethod
    def _view_from_snapshot(snapshot: SessionSnapshot) -> TaintView:
        return TaintView.build(
            untrusted_sources=snapshot.untrusted_sources,
            injection_detected=snapshot.injection_detected,
            values=snapshot.values,
        )

    def _view_for(self, call: ToolCall, snapshot: SessionSnapshot | None) -> TaintView:
        if snapshot is not None:
            return self._view_from_snapshot(snapshot)
        with self._lock:
            session = self._find(call.agent_id, call.session_id)
            return session.view() if session is not None else TaintView.empty()

    def _extract(
        self, result: ToolResult, trusted_fields: tuple[str, ...], *, include_ngrams: bool
    ) -> list[ExtractedValue]:
        common: dict[str, Any] = {
            "trusted_fields": trusted_fields,
            "ngram_size": self.ngram_size,
            "ngram_stride": self.ngram_stride,
        }
        if result.structured is None:
            return extract_values(result.content, include_ngrams=include_ngrams, **common)
        primary = extract_values(result.structured, include_ngrams=include_ngrams, **common)
        # The text form may carry extra values (e.g. an MCP text block next to structured content).
        seen = {(v.value, v.kind) for v in primary}
        extra = [
            v
            for v in extract_values(result.content, include_ngrams=False, **common)
            if (v.value, v.kind) not in seen
        ]
        return primary + extra
