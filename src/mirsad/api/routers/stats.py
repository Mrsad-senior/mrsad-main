"""Dashboard statistics, aggregated in SQL over ``audit_events``.

Counts use the indexed ``event_type``/``ts``/``action``/``tool`` columns. Latency and per-layer
breakdowns live inside the JSON payload; on SQLite they are extracted with the JSON1 functions,
on other databases the payloads of the window are parsed in Python.
"""

from __future__ import annotations

import json
import logging
import math
import statistics
import time
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from mirsad.api.components import Components
from mirsad.api.deps import get_components, require_user
from mirsad.api.schemas import ErrorResponses
from mirsad.models import ApprovalStatus

log = logging.getLogger("mirsad.api")

router = APIRouter(prefix="/api/stats", tags=["stats"], responses=ErrorResponses.AUTH)

DECISION = "tool_call.decision"
INSPECTION = "tool_result.inspection"
VERIFY_CACHE_S = 30.0


class ToolStats(BaseModel):
    tool: str
    allowed: int = 0
    denied: int = 0
    approval: int = 0


class LayerStats(BaseModel):
    layer: str
    count: int


class Overview(BaseModel):
    hours: float
    total_calls: int
    allowed: int
    denied: int
    approvals_required: int
    approvals_pending: int
    injections_detected: int
    results_sanitized: int
    results_blocked: int
    results_inspected: int
    median_latency_ms: float | None
    p95_latency_ms: float | None
    audit_ok: bool | None
    audit_head_seq: int | None
    by_tool: list[ToolStats]
    by_layer: list[LayerStats]


class Bucket(BaseModel):
    t: float
    allowed: int = 0
    denied: int = 0
    require_approval: int = 0
    injections: int = 0


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, math.ceil(pct / 100 * len(ordered)) - 1))
    return round(ordered[k], 3)


def _rows(comps: Components, sql: str, **params: Any) -> list[Any]:
    with comps.tables.engine.connect() as conn:
        return list(conn.execute(text(sql), params).all())


def _json_rows(comps: Components, since: float, until: float) -> tuple[list[float], dict[str, int], int]:
    """Latencies, per-layer objecting call counts and injection count for the window."""
    if comps.tables.dialect == "sqlite":
        try:
            return _json_rows_sqlite(comps, since, until)
        except DBAPIError:
            log.warning("SQLite JSON1 unavailable; aggregating payloads in Python")
    return _json_rows_python(comps, since, until)


def _json_rows_sqlite(comps: Components, since: float, until: float) -> tuple[list[float], dict[str, int], int]:
    p = {"since": since, "until": until, "d": DECISION, "i": INSPECTION}
    latencies = [float(r[0]) for r in _rows(
        comps, "SELECT json_extract(payload_json, '$.latency_ms') FROM audit_events "
               "WHERE event_type = :d AND ts >= :since AND ts < :until AND json_valid(payload_json) "
               "AND json_extract(payload_json, '$.latency_ms') IS NOT NULL", **p)]
    layers = {str(r[0]): int(r[1]) for r in _rows(
        comps, "SELECT json_extract(r.value, '$.layer') AS layer, COUNT(DISTINCT e.seq) FROM audit_events e, "
               "json_each(e.payload_json, '$.reasons') r WHERE e.event_type = :d AND e.ts >= :since "
               "AND e.ts < :until AND json_valid(e.payload_json) AND json_extract(r.value, '$.action') != 'allow' "
               "GROUP BY layer", **p) if r[0]}
    detector_rows = _rows(
        comps, "SELECT SUM(CASE WHEN json_extract(payload_json, '$.detection.label') = 'injection' THEN 1 ELSE 0 END), "
               "SUM(CASE WHEN action != 'pass' THEN 1 ELSE 0 END) FROM audit_events WHERE event_type = :i "
               "AND ts >= :since AND ts < :until AND json_valid(payload_json)", **p)
    injections = int(detector_rows[0][0] or 0) if detector_rows else 0
    flagged = int(detector_rows[0][1] or 0) if detector_rows else 0
    if flagged:
        layers["detector"] = layers.get("detector", 0) + flagged
    return latencies, layers, injections


def _json_rows_python(comps: Components, since: float, until: float) -> tuple[list[float], dict[str, int], int]:
    latencies: list[float] = []
    layers: dict[str, int] = {}
    injections = 0
    for event_type, action, payload_json in _rows(
            comps, "SELECT event_type, action, payload_json FROM audit_events WHERE event_type IN (:d, :i) "
                   "AND ts >= :since AND ts < :until", d=DECISION, i=INSPECTION, since=since, until=until):
        try:
            payload = json.loads(payload_json or "{}")
        except ValueError:
            continue
        if event_type == DECISION:
            if isinstance(payload.get("latency_ms"), (int, float)):
                latencies.append(float(payload["latency_ms"]))
            for layer in {r.get("layer") for r in payload.get("reasons", []) if r.get("action") != "allow"}:
                if layer:
                    layers[layer] = layers.get(layer, 0) + 1
        else:
            if (payload.get("detection") or {}).get("label") == "injection":
                injections += 1
            if action != "pass":
                layers["detector"] = layers.get("detector", 0) + 1
    return latencies, layers, injections


def _audit_ok(request: Request, comps: Components) -> tuple[bool | None, int | None]:
    """Chain verification is O(n); reuse a recent result while the head has not moved."""
    try:
        head_seq, _ = comps.audit.head()
    except Exception:
        log.exception("audit head unavailable")
        return None, None
    cached = getattr(request.app.state, "audit_verify_cache", None)
    if cached and cached[0] == head_seq and time.time() - cached[2] < VERIFY_CACHE_S:
        return cached[1], head_seq
    try:
        report = comps.audit.verify()
    except Exception:
        log.exception("audit verification failed to run")
        return None, head_seq
    ok = bool(getattr(report, "ok", False))
    request.app.state.audit_verify_cache = (head_seq, ok, time.time())
    return ok, head_seq


def compute_overview(request: Request, comps: Components, hours: float) -> Overview:
    until = time.time() + 1
    since = until - hours * 3600
    p = {"since": since, "until": until}
    by_action: dict[str, int] = {}
    tools: dict[str, ToolStats] = {}
    for tool, action, count in _rows(
            comps, "SELECT tool, action, COUNT(*) FROM audit_events WHERE event_type = :d AND ts >= :since "
                   "AND ts < :until GROUP BY tool, action", d=DECISION, **p):
        by_action[action] = by_action.get(action, 0) + int(count)
        ts = tools.setdefault(tool or "?", ToolStats(tool=tool or "?"))
        if action == "allow":
            ts.allowed += int(count)
        elif action == "deny":
            ts.denied += int(count)
        elif action == "require_approval":
            ts.approval += int(count)
    inspections = {a: int(c) for a, c in _rows(
        comps, "SELECT action, COUNT(*) FROM audit_events WHERE event_type = :i AND ts >= :since AND ts < :until "
               "GROUP BY action", i=INSPECTION, **p)}
    latencies, layers, injections = _json_rows(comps, since, until)
    try:
        pending = len(comps.approvals.list(status=ApprovalStatus.PENDING, limit=10_000))
    except Exception:
        log.exception("approvals list failed")
        pending = 0
    audit_ok, head_seq = _audit_ok(request, comps)
    return Overview(
        hours=hours, total_calls=sum(by_action.values()), allowed=by_action.get("allow", 0),
        denied=by_action.get("deny", 0), approvals_required=by_action.get("require_approval", 0),
        approvals_pending=pending, injections_detected=injections, results_sanitized=inspections.get("sanitize", 0),
        results_blocked=inspections.get("block", 0), results_inspected=sum(inspections.values()),
        median_latency_ms=round(statistics.median(latencies), 3) if latencies else None,
        p95_latency_ms=_percentile(latencies, 95), audit_ok=audit_ok, audit_head_seq=head_seq,
        by_tool=sorted(tools.values(), key=lambda t: -(t.allowed + t.denied + t.approval)),
        by_layer=[LayerStats(layer=k, count=v) for k, v in sorted(layers.items(), key=lambda kv: -kv[1])])


@router.get("/overview", response_model=Overview)
def overview(request: Request, hours: float = Query(24, gt=0, le=24 * 366),  # noqa: B008
             _user=Depends(require_user())) -> Overview:  # noqa: B008
    return compute_overview(request, get_components(request), hours)


def compute_timeseries(comps: Components, hours: float, bucket_minutes: int) -> list[Bucket]:
    bucket_s = bucket_minutes * 60
    n = max(1, min(1000, math.ceil(hours * 3600 / bucket_s)))
    end = math.ceil(time.time() / bucket_s) * bucket_s
    start = end - n * bucket_s
    buckets = [Bucket(t=start + i * bucket_s) for i in range(n)]
    floor_expr = ("CAST((ts - :start) / :b AS INTEGER)" if comps.tables.dialect == "sqlite"
                  else "FLOOR((ts - :start) / :b)")
    p = {"start": start, "end": end, "b": bucket_s}
    for idx, action, count in _rows(
            comps, f"SELECT {floor_expr} AS bucket, action, COUNT(*) FROM audit_events "  # noqa: S608  # nosec B608 - floor_expr is one of two constants; values are bound
                   "WHERE event_type = :d AND ts >= :start AND ts < :end GROUP BY bucket, action", d=DECISION, **p):
        i = int(idx)
        if 0 <= i < n and action in ("allow", "deny", "require_approval"):
            field = {"allow": "allowed", "deny": "denied", "require_approval": "require_approval"}[action]
            setattr(buckets[i], field, getattr(buckets[i], field) + int(count))
    if comps.tables.dialect == "sqlite":
        try:
            rows = _rows(comps, f"SELECT {floor_expr} AS bucket, COUNT(*) FROM audit_events "  # noqa: S608  # nosec B608
                                "WHERE event_type = :i AND ts >= :start AND ts < :end AND json_valid(payload_json) "
                                "AND json_extract(payload_json, '$.detection.label') = 'injection' GROUP BY bucket",
                         i=INSPECTION, **p)
            for idx, count in rows:
                if 0 <= int(idx) < n:
                    buckets[int(idx)].injections += int(count)
            return buckets
        except DBAPIError:
            log.warning("SQLite JSON1 unavailable; counting injections in Python")
    for ts, payload_json in _rows(comps, "SELECT ts, payload_json FROM audit_events WHERE event_type = :i "
                                         "AND ts >= :start AND ts < :end", i=INSPECTION, start=start, end=end):
        try:
            label = (json.loads(payload_json or "{}").get("detection") or {}).get("label")
        except ValueError:
            continue
        i = int((ts - start) // bucket_s)
        if label == "injection" and 0 <= i < n:
            buckets[i].injections += 1
    return buckets


@router.get("/timeseries", response_model=list[Bucket],
            description="Buckets aligned to `bucket_minutes`; `t` is the bucket start in epoch seconds.")
def timeseries(request: Request, hours: float = Query(24, gt=0, le=24 * 366),  # noqa: B008
               bucket_minutes: int = Query(60, ge=1, le=24 * 60),  # noqa: B008
               _user=Depends(require_user())) -> list[Bucket]:  # noqa: B008
    return compute_timeseries(get_components(request), hours, bucket_minutes)
