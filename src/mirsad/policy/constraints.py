"""Evaluation of per-argument constraints (spec section 2.1).

Value handling, chosen to fail closed:

* ``None`` and missing arguments are *absent*: only ``required`` can fire.
* Lists (and nested lists) are checked element by element. ``max_items`` and
  ``type`` look at the whole value.
* Strings are split on ``,`` / ``;`` for the address-like operators
  (``domain_in``, ``domain_not_in``, ``enum``/``in``, ``not_in``, ``max_items``).
  Length, numeric and regex operators see the whole string, because a comma is
  ordinary text in a body or a thousands separator in an amount.
* Numeric operators accept numbers and numeric strings (``"15,000"``,
  Arabic-Indic digits). Anything else, including booleans, NaN and infinity,
  is a violation.
* Regex operators see at most ``REGEX_INPUT_LIMIT`` characters. Longer values
  are violations because they cannot be checked completely. Both the raw and
  the NFKC/invisible-stripped form are tested.
* ``domain_in`` needs every element to carry an allowed e-mail/URL/host domain.
  An element with no recognisable domain is a violation. ``domain_not_in``
  flags any element whose domain is on the list.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from mirsad.models import Action, Reason
from mirsad.policy.messages import fmt_value, render
from mirsad.policy.regex_guard import REGEX_INPUT_LIMIT, bounded_search, normalize_for_match
from mirsad.policy.schema import Constraint
from mirsad.textutil import EMAIL_RE, URL_RE, domain_matches, extract_domain, fold

OBJECTION_RISK_SCORE = 0.5
"""Risk score of policy objections that carry no risk of their own (dashboards show it as MEDIUM)."""
_EVIDENCE_LIMIT = 200

_ANY_URL_RE = re.compile(r"\b[a-z][a-z0-9+.\-]*://[^\s<>\"']+", re.IGNORECASE)
_HOST_RE = re.compile(r"(?:[a-z0-9_](?:[a-z0-9_\-]{0,61}[a-z0-9_])?\.)+[a-z][a-z0-9\-]{0,62}")
_PIECE_SPLIT_RE = re.compile(r"[,;]")
_THOUSANDS_RE = re.compile(r"[,_\s٬  ]")


# --------------------------------------------------------------------------- value helpers


def iter_pieces(value: Any) -> Iterator[str]:
    """Flatten a value into string pieces: lists/dicts recursively, strings split on ``,``/``;``."""
    if value is None:
        return
    if isinstance(value, str):
        for part in _PIECE_SPLIT_RE.split(value):
            part = part.strip()
            if part:
                yield part
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            yield from iter_pieces(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_pieces(item)
    else:
        yield as_text(value)


def piece_domains(piece: str) -> list[str]:
    """Domains of every e-mail address, URL or bare host name found in one piece of text."""
    text = normalize_for_match(piece).replace("\\", "/")  # browsers treat '\' as '/' in http(s) URLs
    found: list[str] = []
    for rx in (_ANY_URL_RE, URL_RE, EMAIL_RE):
        for match in rx.finditer(text):
            domain = extract_domain(match.group(0))
            if domain and domain not in found:
                found.append(domain)
    if not found:
        bare = text.strip().strip("<>\"'").lower().rstrip(".")
        if _HOST_RE.fullmatch(bare):
            found.append(bare)
    return found


def as_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(int(value)) if isinstance(value, float) and value.is_integer() else str(value)
    if value is None:
        return "null"
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def leaves(value: Any) -> Iterator[Any]:
    """Elements of (nested) lists; any other value is a single leaf."""
    if isinstance(value, (list, tuple, set)):
        for item in value:
            yield from leaves(item)
    else:
        yield value


def as_number(value: Any) -> int | float | None:
    """Finite number from a number or numeric string, else ``None``."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        text = _THOUSANDS_RE.sub("", fold(value)).replace("٫", ".")
        if not text or len(text) > 64:
            return None
        try:
            return int(text)
        except ValueError:
            pass
        try:
            number = float(text)
        except ValueError:
            return None
        return number if math.isfinite(number) else None
    return None


def json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (list, tuple)):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return (isinstance(value, int) and not isinstance(value, bool)) or (
            isinstance(value, float) and value.is_integer()
        )
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "array":
        return isinstance(value, (list, tuple))
    if expected == "object":
        return isinstance(value, dict)
    return False


def _canon(value: Any) -> str:
    """Comparison key for ``enum``/``not_in``: folded text; ``"10"`` and ``10`` compare equal."""
    if isinstance(value, str):
        text = fold(value)
        try:
            number: float = float(text) if text[:1].isdigit() or text[:1] in "-+." else math.nan
        except ValueError:
            number = math.nan
        return as_text(number) if math.isfinite(number) else text
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return as_text(value)


def _preview(value: Any) -> Any:
    if isinstance(value, str) and len(value) > _EVIDENCE_LIMIT:
        return value[:_EVIDENCE_LIMIT] + f"… ({len(value)} characters)"
    if isinstance(value, (list, dict)):
        text = as_text(value)
        return text if len(text) <= _EVIDENCE_LIMIT else text[:_EVIDENCE_LIMIT] + "…"
    return value


# --------------------------------------------------------------------------- compiled constraint


@dataclass(frozen=True)
class CompiledConstraint:
    """A :class:`Constraint` with regexes compiled and value sets folded, ready for hot-path use."""

    param: str
    spec: Constraint
    action: Action
    pattern: re.Pattern[str] | None
    not_pattern: re.Pattern[str] | None
    allowed: frozenset[str] | None
    forbidden: frozenset[str] | None
    operator_name: str  # "enum" or "in", as written by the policy author

    @classmethod
    def build(cls, param: str, spec: Constraint) -> CompiledConstraint:
        allowed = spec.allowed_values
        return cls(
            param=param,
            spec=spec,
            action=Action(spec.on_violation),
            pattern=re.compile(spec.pattern) if spec.pattern is not None else None,
            not_pattern=re.compile(spec.not_pattern) if spec.not_pattern is not None else None,
            allowed=frozenset(_canon(v) for v in allowed) if allowed is not None else None,
            forbidden=frozenset(_canon(v) for v in spec.not_in) if spec.not_in is not None else None,
            operator_name="enum" if spec.enum is not None else "in",
        )

    # -- public ------------------------------------------------------------

    def check(self, arguments: dict[str, Any]) -> list[Reason]:
        """All violations of this constraint for the call's arguments (empty when it holds)."""
        present = self.param in arguments and arguments[self.param] is not None
        if not present:
            if self.spec.required:
                return [self._reason("required", True, None, "required")]
            return []
        value = arguments[self.param]
        reasons: list[Reason] = []
        for check in (self._type, self._numbers, self._lengths, self._items, self._enum,
                      self._not_in, self._patterns, self._domains):
            reasons.extend(check(value))
        return reasons

    # -- operators ---------------------------------------------------------

    def _type(self, value: Any) -> list[Reason]:
        expected = self.spec.type
        if expected is None or _type_ok(value, expected):
            return []
        return [self._reason("type", expected, json_type(value), "type")]

    def _numbers(self, value: Any) -> list[Reason]:
        spec = self.spec
        if spec.max is None and spec.min is None:
            return []
        reasons: list[Reason] = []
        for leaf in leaves(value):
            number = as_number(leaf)
            for op, limit in (("max", spec.max), ("min", spec.min)):
                if limit is None:
                    continue
                if number is None:
                    reasons.append(self._reason(op, limit, _preview(leaf), "not_number"))
                elif (op == "max" and number > limit) or (op == "min" and number < limit):
                    reasons.append(self._reason(op, limit, number, op))
        return reasons

    def _lengths(self, value: Any) -> list[Reason]:
        spec = self.spec
        if spec.max_length is None and spec.min_length is None:
            return []
        reasons: list[Reason] = []
        for leaf in leaves(value):
            length = len(as_text(leaf))
            if spec.max_length is not None and length > spec.max_length:
                reasons.append(self._reason("max_length", spec.max_length, length, "max_length"))
            if spec.min_length is not None and length < spec.min_length:
                reasons.append(self._reason("min_length", spec.min_length, length, "min_length"))
        return reasons

    def _items(self, value: Any) -> list[Reason]:
        limit = self.spec.max_items
        if limit is None:
            return []
        if isinstance(value, (list, tuple, set)):
            count = len(value)
        elif isinstance(value, str):
            count = len(list(iter_pieces(value)))
        else:
            count = 1
        if count > limit:
            return [self._reason("max_items", limit, count, "max_items")]
        return []

    def _enum(self, value: Any) -> list[Reason]:
        if self.allowed is None:
            return []
        bad: list[Any] = []
        for leaf in leaves(value):
            if _canon(leaf) in self.allowed:
                continue
            pieces = list(iter_pieces(leaf)) if isinstance(leaf, str) else []
            if len(pieces) > 1:
                bad.extend(p for p in pieces if _canon(p) not in self.allowed)
            else:
                bad.append(leaf)
        if not bad:
            return []
        expected = list(self.spec.allowed_values or [])
        return [self._reason(self.operator_name, expected, _preview(_one_or_list(bad)), "enum")]

    def _not_in(self, value: Any) -> list[Reason]:
        if self.forbidden is None:
            return []
        hits: list[Any] = []
        for leaf in leaves(value):
            if _canon(leaf) in self.forbidden:
                hits.append(leaf)
            elif isinstance(leaf, str):
                hits.extend(p for p in iter_pieces(leaf) if _canon(p) in self.forbidden)
        if not hits:
            return []
        return [self._reason("not_in", list(self.spec.not_in or []), _preview(_one_or_list(hits)), "not_in")]

    def _patterns(self, value: Any) -> list[Reason]:
        if self.pattern is None and self.not_pattern is None:
            return []
        reasons: list[Reason] = []
        for leaf in leaves(value):
            text = as_text(leaf)
            for op, rx in (("pattern", self.pattern), ("not_pattern", self.not_pattern)):
                if rx is None:
                    continue
                outcome = bounded_search(rx, text)
                if outcome.truncated:
                    reasons.append(self._reason(op, rx.pattern, f"<{len(text)} characters>", "regex_too_long"))
                elif op == "pattern" and not outcome.matched_all:
                    reasons.append(self._reason(op, rx.pattern, _preview(text), "pattern"))
                elif op == "not_pattern" and outcome.matched_any:
                    reasons.append(self._reason(op, rx.pattern, _preview(text), "not_pattern"))
        return reasons

    def _domains(self, value: Any) -> list[Reason]:
        spec = self.spec
        if spec.domain_in is None and spec.domain_not_in is None:
            return []
        outside: list[str] = []
        blocked: list[str] = []
        for piece in iter_pieces(value):
            domains = piece_domains(piece)
            if spec.domain_in is not None:
                if not domains:
                    outside.append(f"{_preview(piece)} (no domain)")
                outside.extend(d for d in domains if not domain_matches(d, spec.domain_in))
            if spec.domain_not_in is not None:
                blocked.extend(d for d in domains if domain_matches(d, spec.domain_not_in))
        reasons: list[Reason] = []
        if outside:
            reasons.append(self._reason("domain_in", list(spec.domain_in or []),
                                        _one_or_list(_dedupe(outside)), "domain_in"))
        if blocked:
            reasons.append(self._reason("domain_not_in", list(spec.domain_not_in or []),
                                        _one_or_list(_dedupe(blocked)), "domain_not_in"))
        return reasons

    # -- reason ------------------------------------------------------------

    def _reason(self, operator: str, expected: Any, actual: Any, template: str) -> Reason:
        message, message_ar = render(
            template,
            param=self.param,
            operator=operator,
            expected=fmt_value(expected),
            actual=fmt_value(actual),
            limit=REGEX_INPUT_LIMIT,
        )
        return Reason(
            layer="policy",
            code="CONSTRAINT_VIOLATION",
            message=message,
            message_ar=message_ar,
            action=self.action,
            rule_id=f"constraint:{self.param}.{operator}",
            risk_score=OBJECTION_RISK_SCORE,
            evidence={"param": self.param, "operator": operator, "expected": expected, "actual": actual},
        )


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _one_or_list(items: list[Any]) -> Any:
    return items[0] if len(items) == 1 else items


def compile_constraints(constraints: dict[str, Constraint]) -> list[CompiledConstraint]:
    return [CompiledConstraint.build(param, spec) for param, spec in constraints.items()]


def check_constraints(arguments: dict[str, Any], constraints: list[CompiledConstraint]) -> list[Reason]:
    """Run every compiled constraint against the call arguments."""
    reasons: list[Reason] = []
    for constraint in constraints:
        reasons.extend(constraint.check(arguments))
    return reasons
