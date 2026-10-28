"""Tool-name globs: matching, precedence and overlap detection.

Precedence when resolving a tool name for an agent: an exact key wins, then the
longest matching glob, then the catch-all ``"*"``. Two globs of the same length
that can match the same name would make precedence ambiguous, so the schema
rejects them using :func:`globs_overlap`.
"""

from __future__ import annotations

import fnmatch
import re
from functools import cache, lru_cache

CATCH_ALL = "*"
_STAR = ("star",)
_ALPHABET = frozenset(
    [chr(c) for c in range(32, 127)] + ["ا", "ب", "é"]
)


def is_glob(key: str) -> bool:
    return any(ch in key for ch in "*?[")


@lru_cache(maxsize=1024)
def compile_glob(pattern: str) -> re.Pattern[str]:
    """Case-sensitive fnmatch-style glob as a compiled regex (tool names are case-sensitive)."""
    return re.compile(fnmatch.translate(pattern))


def glob_matches(pattern: str, name: str) -> bool:
    if not is_glob(pattern):
        return pattern == name
    return compile_glob(pattern).match(name) is not None


def specificity(pattern: str) -> int:
    """Longer globs are more specific ("longer glob beats shorter")."""
    return len(pattern)


def _tokens(pattern: str) -> tuple[tuple[str, ...], ...]:
    out: list[tuple[str, ...]] = []
    i, n = 0, len(pattern)
    while i < n:
        ch = pattern[i]
        i += 1
        if ch == "*":
            if not out or out[-1] != _STAR:
                out.append(_STAR)
        elif ch == "?":
            out.append(("any",))
        elif ch == "[":
            j = i
            if j < n and pattern[j] == "!":
                j += 1
            if j < n and pattern[j] == "]":
                j += 1
            while j < n and pattern[j] != "]":
                j += 1
            if j >= n:
                out.append(("lit", "["))
            else:
                out.append(("class", pattern[i - 1 : j + 1]))
                i = j + 1
        else:
            out.append(("lit", ch))
    return tuple(out)


def _chars_overlap(a: tuple[str, ...], b: tuple[str, ...]) -> bool:
    if a[0] == "any" or b[0] == "any":
        return True
    if a[0] == "lit" and b[0] == "lit":
        return a[1] == b[1]
    if a[0] == "lit":
        return fnmatch.fnmatchcase(a[1], b[1])
    if b[0] == "lit":
        return fnmatch.fnmatchcase(b[1], a[1])
    candidates = _ALPHABET | set(a[1]) | set(b[1])
    return any(fnmatch.fnmatchcase(ch, a[1]) and fnmatch.fnmatchcase(ch, b[1]) for ch in candidates)


def globs_overlap(a: str, b: str) -> bool:
    """True when some tool name matches both globs (dynamic programming over the two token lists)."""
    ta, tb = _tokens(a), _tokens(b)

    @cache
    def go(i: int, j: int) -> bool:
        if i == len(ta) and j == len(tb):
            return True
        if i < len(ta) and ta[i] == _STAR:
            return go(i + 1, j) or (j < len(tb) and go(i, j + 1))
        if j < len(tb) and tb[j] == _STAR:
            return go(i, j + 1) or (i < len(ta) and go(i + 1, j))
        if i == len(ta) or j == len(tb):
            return False
        return _chars_overlap(ta[i], tb[j]) and go(i + 1, j + 1)

    return go(0, 0)
