"""Safe handling of administrator-written regular expressions.

Policy regexes run against tool arguments that a (possibly hijacked) model
generated, so a badly written pattern is a denial-of-service vector. Two
defences live here:

* :func:`compile_user_regex` rejects patterns with *nested ambiguous
  quantifiers* (``(a+)+``, ``(.*@.*){51,}``), the textbook cause of
  exponential backtracking, at policy-validation time.
* :func:`bounded_search` never hands more than :data:`REGEX_INPUT_LIMIT`
  characters to a user regex and reports whether the input was truncated, so
  callers can fail closed instead of silently skipping the tail.

The nested-quantifier check is a heuristic: it catches the exponential class
but not every polynomial (quadratic) pattern. The input bound caps those.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from mirsad.textutil import strip_invisible

try:  # private CPython modules (3.11+); the safety check degrades gracefully without them
    from re import _constants as _c
    from re import _parser as _sre_parse
except ImportError:  # pragma: no cover - alternative interpreters
    _c = None  # type: ignore[assignment]
    _sre_parse = None  # type: ignore[assignment]

logger = logging.getLogger("mirsad.policy")

REGEX_INPUT_LIMIT = 50_000
"""Maximum number of characters passed to any policy regex (ReDoS bound)."""

MAX_PATTERN_LENGTH = 2_000

# Representative alphabet for the character-set overlap test. Literal characters and
# range endpoints from the pattern are added per pattern, so overlaps on those are exact.
_BASE_ALPHABET = frozenset(
    [chr(c) for c in range(32, 127)]
    + ["\t", "\n", "\r", " ", "é", "ا", "ب", "م", "٣", "\u200b", "＠", "_"]
)


@dataclass(frozen=True)
class RegexOutcome:
    """Result of :func:`bounded_search` on the raw and the normalised form of a value."""

    matched_raw: bool
    matched_normalized: bool
    truncated: bool

    @property
    def matched_any(self) -> bool:
        return self.matched_raw or self.matched_normalized

    @property
    def matched_all(self) -> bool:
        return self.matched_raw and self.matched_normalized


def normalize_for_match(text: str) -> str:
    """NFKC + invisible-character removal, so ``ｌｏｃａｌｈｏｓｔ`` or ``local\u200bhost`` cannot dodge a pattern."""
    text = unicodedata.normalize("NFKC", text)
    text, _ = strip_invisible(text)
    return text


def bounded_search(rx: re.Pattern[str], text: str) -> RegexOutcome:
    """``rx.search`` on at most :data:`REGEX_INPUT_LIMIT` characters, raw and normalised."""
    truncated = len(text) > REGEX_INPUT_LIMIT
    head = text[:REGEX_INPUT_LIMIT]
    raw = rx.search(head) is not None
    norm_text = normalize_for_match(head)[:REGEX_INPUT_LIMIT]
    norm = raw if norm_text == head else rx.search(norm_text) is not None
    return RegexOutcome(matched_raw=raw, matched_normalized=norm, truncated=truncated)


def compile_user_regex(pattern: str) -> re.Pattern[str]:
    """Compile an administrator regex, raising ``ValueError`` with a readable message when unsafe or invalid."""
    if not isinstance(pattern, str):
        raise ValueError(f"regular expression must be a string, got {type(pattern).__name__}")
    if len(pattern) > MAX_PATTERN_LENGTH:
        raise ValueError(f"regular expression is longer than {MAX_PATTERN_LENGTH} characters")
    try:
        rx = re.compile(pattern)
    except re.error as exc:
        where = f" at position {exc.pos}" if exc.pos is not None else ""
        raise ValueError(f"invalid regular expression {pattern!r}: {exc.msg}{where}") from None
    problem = nested_quantifier_problem(pattern)
    if problem:
        raise ValueError(
            f"regular expression {pattern!r} can cause catastrophic backtracking (ReDoS): {problem}. "
            "Make the repeated parts unambiguous, e.g. write '(?:[^@]*@){51}' instead of '(.*@.*){51,}'"
        )
    return rx


# --------------------------------------------------------------------------- nested-quantifier analysis


def nested_quantifier_problem(pattern: str) -> str | None:
    """Describe the first nested ambiguous quantifier in ``pattern``, or ``None`` when none is found.

    A repeat nested inside another repeat is reported when the characters its
    body can start with overlap the characters that may follow it inside the
    enclosing loop. Then the engine can split the input between iterations in
    exponentially many ways before failing.
    """
    if _sre_parse is None or _c is None:
        return None
    try:
        parsed = _sre_parse.parse(pattern)
    except Exception:  # noqa: BLE001 - compile() already succeeded; never fail validation here
        return None
    analyzer = _Analyzer(parsed)
    try:
        analyzer.check(list(parsed), frozenset(), parsed.state.flags, in_loop=False)
    except RecursionError:  # pragma: no cover - absurdly deep patterns
        return "pattern nesting is too deep to analyse"
    return analyzer.problem


class _Analyzer:
    def __init__(self, parsed: Any) -> None:
        extra: set[str] = set()
        self._collect(list(parsed), extra)
        self.sigma = _BASE_ALPHABET | frozenset(extra)
        self.problem: str | None = None

    # -- alphabet ---------------------------------------------------------

    def _collect(self, items: list[Any], out: set[str]) -> None:
        for op, av in items:
            if op in (_c.LITERAL, _c.NOT_LITERAL):
                out.update(_case_variants(chr(av)))
            elif op == _c.IN:
                for iop, iav in av:
                    if iop == _c.LITERAL:
                        out.update(_case_variants(chr(iav)))
                    elif iop == _c.RANGE:
                        out.update(_case_variants(chr(iav[0])) | _case_variants(chr(iav[1])))
            for sub in _children(op, av):
                self._collect(list(sub), out)

    # -- FIRST sets -------------------------------------------------------

    def first(self, items: list[Any], flags: int) -> tuple[frozenset[str], bool]:
        acc: set[str] = set()
        for item in items:
            chars, nullable = self.first_item(item, flags)
            acc |= chars
            if not nullable:
                return frozenset(acc), False
        return frozenset(acc), True

    def first_item(self, item: tuple[Any, Any], flags: int) -> tuple[frozenset[str], bool]:
        op, av = item
        ignore = bool(flags & _c.SRE_FLAG_IGNORECASE)
        if op == _c.LITERAL:
            ch = chr(av)
            return (_case_variants(ch) if ignore else frozenset(ch)), False
        if op == _c.NOT_LITERAL:
            excluded = _case_variants(chr(av)) if ignore else {chr(av)}
            return self.sigma - excluded, False
        if op == _c.ANY:
            return (self.sigma if flags & _c.SRE_FLAG_DOTALL else self.sigma - {"\n"}), False
        if op == _c.IN:
            return frozenset(ch for ch in self.sigma if _in_class(av, ch, ignore)), False
        if op == _c.BRANCH:
            acc: set[str] = set()
            nullable = False
            for alt in av[1]:
                chars, n = self.first(list(alt), flags)
                acc |= chars
                nullable = nullable or n
            return frozenset(acc), nullable
        if op == _c.SUBPATTERN:
            _group, add, delete, sub = av
            return self.first(list(sub), (flags | add) & ~delete)
        if op == getattr(_c, "ATOMIC_GROUP", None):
            return self.first(list(av), flags)
        if op in _repeat_ops():
            low, _high, sub = av
            chars, nullable = self.first(list(sub), flags)
            return chars, nullable or low == 0
        if op in (_c.AT, _c.ASSERT, _c.ASSERT_NOT):
            return frozenset(), True
        if op == _c.GROUPREF_EXISTS:
            _group, yes, no = av
            chars, n1 = self.first(list(yes), flags)
            if no is None:
                return chars, True
            chars2, n2 = self.first(list(no), flags)
            return chars | chars2, n1 or n2
        # GROUPREF and anything unknown: assume it can be any character or nothing.
        return self.sigma, True

    # -- ambiguity walk ---------------------------------------------------

    def check(self, items: list[Any], follow: frozenset[str], flags: int, *, in_loop: bool) -> None:
        for i, item in enumerate(items):
            if self.problem:
                return
            rest_first, rest_nullable = self.first(items[i + 1 :], flags)
            item_follow = rest_first | (follow if rest_nullable else frozenset())
            self.check_item(item, item_follow, flags, in_loop=in_loop)

    def check_item(self, item: tuple[Any, Any], follow: frozenset[str], flags: int, *, in_loop: bool) -> None:
        op, av = item
        if op in (_c.MAX_REPEAT, _c.MIN_REPEAT):
            _low, high, sub = av
            body = list(sub)
            body_first, _ = self.first(body, flags)
            unbounded = high == _c.MAXREPEAT
            if in_loop and unbounded and body_first & follow:
                self.problem = "an unbounded repeat inside another repeat can match the same characters as what follows it"
                return
            loops = unbounded or high > 1
            inner_follow = (body_first | follow) if loops else follow
            self.check(body, inner_follow, flags, in_loop=in_loop or loops)
        elif op == _c.SUBPATTERN:
            _group, add, delete, sub = av
            self.check(list(sub), follow, (flags | add) & ~delete, in_loop=in_loop)
        elif op == _c.BRANCH:
            for alt in av[1]:
                self.check(list(alt), follow, flags, in_loop=in_loop)
        elif op in (_c.ASSERT, _c.ASSERT_NOT):
            self.check(list(av[1]), frozenset(), flags, in_loop=False)
        elif op == _c.GROUPREF_EXISTS:
            _group, yes, no = av
            self.check(list(yes), follow, flags, in_loop=in_loop)
            if no is not None:
                self.check(list(no), follow, flags, in_loop=in_loop)
        # Possessive repeats and atomic groups never backtrack into themselves: safe by construction.


def _repeat_ops() -> tuple[Any, ...]:
    ops = [_c.MAX_REPEAT, _c.MIN_REPEAT]
    possessive = getattr(_c, "POSSESSIVE_REPEAT", None)
    if possessive is not None:
        ops.append(possessive)
    return tuple(ops)


def _children(op: Any, av: Any) -> list[Any]:
    if op == _c.SUBPATTERN:
        return [av[3]]
    if op in _repeat_ops():
        return [av[2]]
    if op == _c.BRANCH:
        return list(av[1])
    if op in (_c.ASSERT, _c.ASSERT_NOT):
        return [av[1]]
    if op == getattr(_c, "ATOMIC_GROUP", None):
        return [av]
    if op == _c.GROUPREF_EXISTS:
        return [x for x in av[1:] if x is not None]
    return []


def _case_variants(ch: str) -> frozenset[str]:
    return frozenset({ch, ch.lower(), ch.upper()})


_CATEGORY_RE: dict[Any, re.Pattern[str]] = {}


def _category_rx(cat: Any) -> re.Pattern[str] | None:
    if not _CATEGORY_RE and _c is not None:
        _CATEGORY_RE.update({
            _c.CATEGORY_DIGIT: re.compile(r"\d"),
            _c.CATEGORY_NOT_DIGIT: re.compile(r"\D"),
            _c.CATEGORY_SPACE: re.compile(r"\s"),
            _c.CATEGORY_NOT_SPACE: re.compile(r"\S"),
            _c.CATEGORY_WORD: re.compile(r"\w"),
            _c.CATEGORY_NOT_WORD: re.compile(r"\W"),
        })
    return _CATEGORY_RE.get(cat)


def _in_class(items: list[Any], ch: str, ignore: bool) -> bool:
    negate = False
    hit = False
    variants = _case_variants(ch) if ignore else frozenset(ch)
    for op, av in items:
        if op == _c.NEGATE:
            negate = True
        elif op == _c.LITERAL:
            hit = hit or chr(av) in variants
        elif op == _c.RANGE:
            lo, hi = av
            hit = hit or any(lo <= ord(v) <= hi for v in variants)
        elif op == _c.CATEGORY:
            rx = _category_rx(av)
            hit = hit or rx is None or rx.match(ch) is not None
        else:  # unknown member kind: be conservative
            hit = True
    return hit != negate
