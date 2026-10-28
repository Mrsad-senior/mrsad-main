"""The four taint rules, as a pure function of (call, profile, sink, settings, state view).

Both live evaluation and audit replay go through :func:`evaluate_rules` with a
:class:`TaintView` built by the same code, so a stored snapshot always reproduces the
original verdict.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from mirsad.models import Action, Reason, Risk, Sensitivity, SinkKind, ToolCall, ToolProfile, Trust
from mirsad.taint import messages
from mirsad.taint.extract import (
    NGRAM_SIZE,
    ArgCandidate,
    DestinationItem,
    argument_candidates,
    destination_items,
    domain_suffixes,
)
from mirsad.textutil import domain_matches

logger = logging.getLogger("mirsad.taint")

CODE_UNTRUSTED_TO_EXTERNAL = "TAINT_UNTRUSTED_TO_EXTERNAL"
CODE_CONFIDENTIAL_TO_EXTERNAL = "TAINT_CONFIDENTIAL_TO_EXTERNAL"
CODE_UNTRUSTED_DESTINATION = "TAINT_UNTRUSTED_DESTINATION"
CODE_AFTER_INJECTION = "TAINT_AFTER_INJECTION"
TAINT_CODES = (
    CODE_UNTRUSTED_TO_EXTERNAL,
    CODE_CONFIDENTIAL_TO_EXTERNAL,
    CODE_UNTRUSTED_DESTINATION,
    CODE_AFTER_INJECTION,
)

RISK_UNTRUSTED_TO_EXTERNAL = 0.6
RISK_CONFIDENTIAL_TO_EXTERNAL = 0.7
RISK_UNTRUSTED_DESTINATION = 0.9
RISK_AFTER_INJECTION = 0.8

# Kinds that count as "confidential data" for TAINT_CONFIDENTIAL_TO_EXTERNAL (spec section 3).
CONFIDENTIAL_KINDS = frozenset({"email", "phone", "iban", "id", "number", "ngram"})
# Destination kinds a data-subject record can be keyed by (see _data_subject_records).
SUBJECT_KINDS = frozenset({"email", "phone", "iban"})

MAX_EVIDENCE_ITEMS = 5
EVIDENCE_VALUE_CHARS = 80

DEFAULT_DESTINATION_PARAMS = ("to", "cc", "bcc", "recipient", "url", "to_iban", "webhook")
DEFAULT_TRUSTED_FIELDS = ("from", "sender", "id", "email_id", "date", "received_at", "customer_id", "doc_id")
DEFAULT_ACTIONS: dict[str, Action] = {
    "untrusted_to_external_sink": Action.REQUIRE_APPROVAL,
    "confidential_to_external_sink": Action.REQUIRE_APPROVAL,
    "untrusted_controls_destination": Action.DENY,
    "after_injection_high_risk": Action.REQUIRE_APPROVAL,
}


class ValueLike(Protocol):
    """Anything shaped like :class:`mirsad.models.TaintedValue`."""

    value: str
    kind: str
    field: str | None
    source_tool: str
    source_call_id: str
    trust: Trust
    sensitivity: Sensitivity
    trusted_field: bool


# --------------------------------------------------------------------------- settings


def _get(settings: Any, name: str, default: Any) -> Any:
    if settings is None:
        return default
    if isinstance(settings, Mapping):
        value = settings.get(name, default)
    else:
        value = getattr(settings, name, default)
    return default if value is None else value


def _action(value: Any, name: str) -> Action:
    try:
        return Action(str(getattr(value, "value", value)).strip().lower())
    except ValueError:
        # Fall back to the (restrictive) default rather than silently weakening the rule.
        logger.warning("invalid taint action %r for %s; using %s", value, name, DEFAULT_ACTIONS[name].value)
        return DEFAULT_ACTIONS[name]


@dataclass(frozen=True)
class ResolvedTaintSettings:
    """``policy.TaintSettings`` (or a dict / None) normalised for the rules."""

    enabled: bool
    destination_params: frozenset[str]
    trusted_fields: tuple[str, ...]
    untrusted_to_external_sink: Action
    confidential_to_external_sink: Action
    untrusted_controls_destination: Action
    after_injection_high_risk: Action
    # Optional (not in the spec's TaintSettings): organisation domains, never matched at domain level.
    internal_domains: tuple[str, ...] = ()

    @classmethod
    def from_any(cls, settings: Any, *, internal_domains: Iterable[str] = ()) -> ResolvedTaintSettings:
        if isinstance(settings, ResolvedTaintSettings):
            return settings
        domains = [*_get(settings, "internal_domains", ()), *internal_domains]
        return cls(
            enabled=bool(_get(settings, "enabled", True)),
            destination_params=frozenset(
                str(p).strip().lower()
                for p in _get(settings, "destination_params", DEFAULT_DESTINATION_PARAMS)
            ),
            trusted_fields=tuple(str(f) for f in _get(settings, "trusted_fields", DEFAULT_TRUSTED_FIELDS)),
            **{
                name: _action(_get(settings, name, default), name)
                for name, default in DEFAULT_ACTIONS.items()
            },
            internal_domains=tuple(dict.fromkeys(str(d).strip().lower() for d in domains if str(d).strip())),
        )


# --------------------------------------------------------------------------- state view


def _record_key(v: ValueLike) -> tuple[str, str] | None:
    """The record (top-level list element, or the whole object) a structured value belongs to."""
    if v.field is None:
        return None
    end = v.field.find("]")
    return v.source_call_id, (v.field[: end + 1] if end >= 0 else "")


def _freeze(index: dict[Any, list[int]]) -> dict[Any, tuple[int, ...]]:
    return {k: tuple(v) for k, v in index.items()}


@dataclass(frozen=True)
class TaintView:
    """Immutable, indexed view of one session's taint state (never mutated after build)."""

    untrusted_sources: tuple[str, ...]
    injection_detected: bool
    values: tuple[ValueLike, ...]
    trusted_ctx: tuple[bool, ...]  # value seen in a trusted result or a trusted field
    untrusted_free: tuple[bool, ...]  # value seen in untrusted free text
    confidential: tuple[bool, ...]
    exact: Mapping[tuple[str, str], tuple[int, ...]]
    untrusted_domains: Mapping[str, tuple[int, ...]]
    trusted_domains: Mapping[str, tuple[int, ...]]
    trusted_domain_suffixes: Mapping[str, tuple[int, ...]]
    records: Mapping[tuple[str, str], tuple[int, ...]]

    @classmethod
    def build(
        cls, *, untrusted_sources: Iterable[str], injection_detected: bool, values: Iterable[ValueLike]
    ) -> TaintView:
        vals = tuple(values)
        trusted_ctx: list[bool] = []
        untrusted_free: list[bool] = []
        confidential: list[bool] = []
        exact: dict[tuple[str, str], list[int]] = {}
        untrusted_domains: dict[str, list[int]] = {}
        trusted_domains: dict[str, list[int]] = {}
        trusted_suffixes: dict[str, list[int]] = {}
        records: dict[tuple[str, str], list[int]] = {}
        for i, v in enumerate(vals):
            is_trusted = Trust(v.trust) == Trust.TRUSTED or bool(v.trusted_field)
            is_conf = Sensitivity(v.sensitivity) == Sensitivity.CONFIDENTIAL
            trusted_ctx.append(is_trusted)
            untrusted_free.append(not is_trusted)
            confidential.append(is_conf)
            exact.setdefault((v.kind, v.value), []).append(i)
            if v.kind == "domain":
                if is_trusted:
                    trusted_domains.setdefault(v.value, []).append(i)
                    for suffix in domain_suffixes(v.value):
                        trusted_suffixes.setdefault(suffix, []).append(i)
                else:
                    untrusted_domains.setdefault(v.value, []).append(i)
            if is_conf:
                rec = _record_key(v)
                if rec is not None:
                    records.setdefault(rec, []).append(i)
        return cls(
            untrusted_sources=tuple(untrusted_sources),
            injection_detected=bool(injection_detected),
            values=vals,
            trusted_ctx=tuple(trusted_ctx),
            untrusted_free=tuple(untrusted_free),
            confidential=tuple(confidential),
            exact=_freeze(exact),
            untrusted_domains=_freeze(untrusted_domains),
            trusted_domains=_freeze(trusted_domains),
            trusted_domain_suffixes=_freeze(trusted_suffixes),
            records=_freeze(records),
        )

    @classmethod
    def empty(cls) -> TaintView:
        return cls.build(untrusted_sources=(), injection_detected=False, values=())


# --------------------------------------------------------------------------- helpers


def _split_source(entry: str) -> tuple[str, str]:
    tool, sep, call_id = entry.partition(":")
    return (tool, call_id) if sep else (entry, "")


def _trunc(value: str) -> str:
    return messages.truncate(value, EVIDENCE_VALUE_CHARS)


def _source_evidence(v: ValueLike) -> dict[str, Any]:
    return {
        "source_tool": v.source_tool,
        "source_call_id": v.source_call_id,
        "field": v.field,
        "source_trust": Trust(v.trust).value,
        "source_sensitivity": Sensitivity(v.sensitivity).value,
    }


def _destination_params(
    call: ToolCall, profile: ToolProfile, cfg: ResolvedTaintSettings
) -> list[tuple[str, Any]]:
    """``(path, value)`` of every argument (at any depth) whose name marks a destination."""
    names = cfg.destination_params | {p.lower() for p in profile.sink_params}
    found: list[tuple[str, Any]] = []

    def walk(value: Any, path: str, depth: int) -> None:
        if depth > 16:
            return
        if isinstance(value, Mapping):
            for k, v in value.items():
                child = f"{path}.{k}" if path else str(k)
                if str(k).lower() in names:
                    found.append((child, v))
                else:
                    walk(v, child, depth + 1)
        elif isinstance(value, (list, tuple)):
            for i, v in enumerate(value):
                walk(v, f"{path}[{i}]", depth + 1)

    walk(call.arguments, "", 0)
    return found


def _reason(
    code: str, setting: str, action: Action, risk: float, en_ar: tuple[str, str], evidence: dict
) -> Reason:
    return Reason(
        layer="taint",
        code=code,
        message=en_ar[0],
        message_ar=en_ar[1],
        action=action,
        rule_id=f"taint.{setting}",
        risk_score=risk,
        evidence=evidence,
    )


# --------------------------------------------------------------------------- rules


def _rule_untrusted_to_external(call: ToolCall, sink: SinkKind, cfg: ResolvedTaintSettings, view: TaintView):
    if sink != SinkKind.EXTERNAL or not view.untrusted_sources:
        return None
    recent = [_split_source(s) for s in view.untrusted_sources[-MAX_EVIDENCE_ITEMS:]][::-1]
    tools = list(dict.fromkeys(tool for tool, _ in recent))
    evidence = {
        "tool": call.tool,
        "sink": sink.value,
        "source_tool": recent[0][0],
        "source_call_id": recent[0][1],
        "field": None,
        "sources": [{"tool": t, "call_id": c} for t, c in recent],
        "source_count": len(view.untrusted_sources),
    }
    return _reason(
        CODE_UNTRUSTED_TO_EXTERNAL,
        "untrusted_to_external_sink",
        cfg.untrusted_to_external_sink,
        RISK_UNTRUSTED_TO_EXTERNAL,
        messages.untrusted_to_external(call.tool, tools),
        evidence,
    )


def _data_subject_records(
    items: Sequence[DestinationItem], view: TaintView, touched: set[int]
) -> frozenset[tuple[str, str]]:
    """Records whose own contact details are the (only) destinations of this call.

    Sending a customer their own data is not a disclosure, so values from that customer's
    record are exempt from TAINT_CONFIDENTIAL_TO_EXTERNAL. This applies only when *every*
    destination is the single e-mail/phone/IBAN of a structured confidential record; one
    unknown recipient (or a record listing several contacts) cancels the exemption.
    """
    if not items or any(item.kind not in SUBJECT_KINDS for item in items):
        return frozenset()
    exempt: set[tuple[str, str]] = set()
    for item in items:
        matched = False
        for i in view.exact.get((item.kind, item.value), ()):
            rec = _record_key(view.values[i]) if view.confidential[i] else None
            if rec is None:
                continue
            members = view.records.get(rec, ())
            touched.add(i)
            touched.update(members)
            same_kind = {view.values[j].value for j in members if view.values[j].kind == item.kind}
            if same_kind == {item.value}:
                exempt.add(rec)
                matched = True
        if not matched:
            return frozenset()
    return frozenset(exempt)


def _rule_confidential_to_external(
    call: ToolCall,
    sink: SinkKind,
    cfg: ResolvedTaintSettings,
    view: TaintView,
    dest_items: Sequence[DestinationItem],
    touched: set[int],
    ngram_size: int,
):
    if sink != SinkKind.EXTERNAL or not any(view.confidential):
        return None
    exempt = _data_subject_records(dest_items, view, touched)
    matches: list[tuple[ArgCandidate, ValueLike]] = []
    seen: set[tuple[str, str]] = set()
    for cand in argument_candidates(call.arguments, ngram_size=ngram_size):
        if cand.kind not in CONFIDENTIAL_KINDS or (cand.kind, cand.value) in seen:
            continue
        conf = [i for i in view.exact.get((cand.kind, cand.value), ()) if view.confidential[i]]
        if not conf:
            continue
        touched.update(conf)
        if exempt and any(_record_key(view.values[i]) in exempt for i in conf):
            continue
        seen.add((cand.kind, cand.value))
        matches.append((cand, view.values[conf[0]]))
    if not matches:
        return None
    items = [
        {
            "param": cand.param,
            "kind": cand.kind,
            "value": _trunc(cand.excerpt),
            **_source_evidence(src),
        }
        for cand, src in matches[:MAX_EVIDENCE_ITEMS]
    ]
    first_cand, first_src = matches[0]
    evidence = {
        "tool": call.tool,
        "sink": sink.value,
        **items[0],
        "matches": items,
        "match_count": len(matches),
    }
    return _reason(
        CODE_CONFIDENTIAL_TO_EXTERNAL,
        "confidential_to_external_sink",
        cfg.confidential_to_external_sink,
        RISK_CONFIDENTIAL_TO_EXTERNAL,
        messages.confidential_to_external(
            call.tool,
            first_cand.kind,
            first_cand.excerpt,
            first_src.source_tool,
            first_src.field,
            len(matches) - 1,
        ),
        evidence,
    )


def _untrusted_domain_hit(domain: str, view: TaintView, touched: set[int]) -> int | None:
    """Index of the first untrusted-only sighting of ``domain`` (or a parent domain), if any."""
    suffixes = domain_suffixes(domain)
    trusted_hits = [i for s in suffixes for i in view.trusted_domains.get(s, ())]
    trusted_hits.extend(view.trusted_domain_suffixes.get(domain, ()))
    touched.update(trusted_hits)
    if trusted_hits:
        return None
    untrusted_hits = [i for s in suffixes for i in view.untrusted_domains.get(s, ())]
    touched.update(untrusted_hits)
    return min(untrusted_hits) if untrusted_hits else None


def _rule_untrusted_destination(
    call: ToolCall,
    sink: SinkKind,
    cfg: ResolvedTaintSettings,
    view: TaintView,
    dest_items: Sequence[DestinationItem],
    touched: set[int],
):
    matches: list[tuple[DestinationItem, str, int]] = []
    for item in dest_items:
        hits = view.exact.get((item.kind, item.value), ())
        if hits:
            touched.update(hits)
            if any(view.trusted_ctx[i] for i in hits):
                continue  # e.g. the "from" of the e-mail being answered, or a CRM address
            untrusted = [i for i in hits if view.untrusted_free[i]]
            if untrusted:
                matches.append((item, "exact", untrusted[0]))
                continue
        # Domain-level: an attacker domain controls the destination even if the address differs.
        # Never applied to the organisation's own domains, so colleagues stay reachable.
        if (
            item.domain
            and sink != SinkKind.INTERNAL
            and not domain_matches(item.domain, list(cfg.internal_domains))
        ):
            hit = _untrusted_domain_hit(item.domain, view, touched)
            if hit is not None:
                matches.append((item, "domain", hit))
    if not matches:
        return None
    items = [
        {
            "param": item.param,
            "destination": _trunc(item.raw),
            "match": how,
            "domain": item.domain,
            "kind": view.values[i].kind,
            "value": _trunc(view.values[i].value),
            **_source_evidence(view.values[i]),
        }
        for item, how, i in matches[:MAX_EVIDENCE_ITEMS]
    ]
    first_item, first_how, first_i = matches[0]
    first_src = view.values[first_i]
    evidence = {
        "tool": call.tool,
        "sink": sink.value,
        **items[0],
        "matches": items,
        "match_count": len(matches),
    }
    return _reason(
        CODE_UNTRUSTED_DESTINATION,
        "untrusted_controls_destination",
        cfg.untrusted_controls_destination,
        RISK_UNTRUSTED_DESTINATION,
        messages.untrusted_destination(
            call.tool,
            first_item.raw,
            first_how,
            first_item.domain,
            first_src.source_tool,
            first_src.field,
            len(matches) - 1,
        ),
        evidence,
    )


def _rule_after_injection(call: ToolCall, profile: ToolProfile, cfg: ResolvedTaintSettings, view: TaintView):
    risk = Risk(profile.risk)
    if not view.injection_detected or risk.rank < Risk.HIGH.rank:
        return None
    recent = [_split_source(s) for s in view.untrusted_sources[-MAX_EVIDENCE_ITEMS:]][::-1]
    evidence = {
        "tool": call.tool,
        "tool_risk": risk.value,
        "source_tool": recent[0][0] if recent else None,
        "source_call_id": recent[0][1] if recent else None,
        "field": None,
        "sources": [{"tool": t, "call_id": c} for t, c in recent],
    }
    return _reason(
        CODE_AFTER_INJECTION,
        "after_injection_high_risk",
        cfg.after_injection_high_risk,
        RISK_AFTER_INJECTION,
        messages.after_injection(call.tool, risk.value),
        evidence,
    )


def evaluate_rules(
    call: ToolCall,
    profile: ToolProfile,
    sink: SinkKind | str,
    settings: Any,
    view: TaintView,
    *,
    touched: set[int] | None = None,
    ngram_size: int = NGRAM_SIZE,
    internal_domains: Iterable[str] = (),
) -> list[Reason]:
    """Apply the four taint rules; deterministic and side-effect free.

    ``touched`` (optional) collects the indices of every value the rules consulted, which is
    exactly what a minimal replay snapshot must contain. ``internal_domains`` is merged with
    ``settings.internal_domains`` when the settings object provides one.
    """
    cfg = ResolvedTaintSettings.from_any(settings, internal_domains=internal_domains)
    if not cfg.enabled:
        return []
    sink = SinkKind(sink)
    touched = touched if touched is not None else set()
    dest_items = [
        item
        for path, value in _destination_params(call, profile, cfg)
        for item in destination_items(path, value)
    ]
    candidates = (
        _rule_untrusted_to_external(call, sink, cfg, view),
        _rule_confidential_to_external(call, sink, cfg, view, dest_items, touched, ngram_size),
        _rule_untrusted_destination(call, sink, cfg, view, dest_items, touched),
        _rule_after_injection(call, profile, cfg, view),
    )
    reasons = [r for r in candidates if r is not None]
    if reasons:
        logger.debug("taint rules fired for %s/%s: %s", call.session_id, call.tool, [r.code for r in reasons])
    return reasons
