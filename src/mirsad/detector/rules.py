"""Weighted regex rules over normalised text (English, Arabic MSA + Gulf, Arabizi, structural).

Rules live in YAML files under ``detector/rules/`` so they can be reviewed and extended without
touching code. Each rule carries positive ``examples`` (and optional ``negatives``) that the test
suite checks, which keeps the rule base honest as it grows.

Rule score = ``1 - prod(1 - w_i)`` over *distinct* rules that fired (a rule matching twice counts
once), capped at :data:`SCORE_CAP`.
"""

from __future__ import annotations

import base64
import binascii
import logging
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from mirsad.detector.normalize import (
    BASE64_RE,
    EVASION_SIGNALS,
    SIG_BASE64,
    NormalizedText,
    fold_arabic_chars,
    normalize,
)

log = logging.getLogger("mirsad.detector")

RULES_DIR = Path(__file__).resolve().parent / "rules"
RULE_FILES = ("en.yaml", "ar.yaml", "arabizi.yaml", "structural.yaml")
MACROS_FILE = "macros.yaml"

SCORE_CAP = 0.99
MAX_HITS_PER_RULE = 25
#: weight of each distinct evasion signal (zero-width, homoglyphs, ...) when at least one rule fired
EVASION_WEIGHT = 0.1
EVASION_MAX_TERMS = 3
#: weight multiplier for hits quoted inside text that discusses attacks (security articles, training)
QUOTE_DAMPING = 0.5
BASE64_RULE_ID = "obf.base64_payload"

Category = Literal[
    "context_ignoring", "role_impersonation", "addressing_ai", "action_directive", "exfiltration",
    "secrecy", "urgency_authority", "tool_knowledge", "prompt_leak", "jailbreak", "hidden_content",
    "payload_splitting", "obfuscation", "goal_hijack",
]

_MACRO_RE = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")
_QUOTE_OPEN = "\"“«„`"
_QUOTE_CLOSE = "\"”»`"
_DISCUSSION_RE = re.compile(fold_arabic_chars(
    r"\b(?:prompt[- ]injections?|injection\s+attacks?|jailbreak\w*|attackers?|adversar\w+|examples?|e\.g\.|"
    r"such\s+as|for\s+instance|phrases?\s+like|researchers?|security\s+(?:awareness|training|researchers?|team)|"
    r"red[- ]team\w*|malicious\s+(?:prompts?|instructions?|inputs?)|known\s+as|payloads?|phishing)\b"
    r"|حقن|هجوم|هجمات|مثال|امثلة|أمثلة|الباحثين|المهاجم|المهاجمين|عبارات\s+مثل|التصيد|الاحتيال"
))


class Rule(BaseModel):
    """One weighted detection rule (as written in the YAML files)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
    category: Category
    weight: float = Field(gt=0.0, lt=1.0)
    lang: Literal["en", "ar", "arabizi", "any"] = "any"
    description: str = Field(min_length=3)
    pattern: str = Field(min_length=1)
    #: normalised substrings; the regex only runs when one of them occurs (cheap pre-filter)
    triggers: tuple[str, ...] = ()
    #: optional regex the matched text must also contain (e.g. a digit for leetspeak rules)
    guard: str | None = None
    #: optional signal name added to the detection when this rule fires
    signal: str | None = None
    examples: tuple[str, ...] = Field(min_length=1)
    negatives: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RuleHit:
    """One rule match: normalised span, original span and the original text it covers."""

    rule_id: str
    category: str
    weight: float
    start: int
    end: int
    orig_start: int
    orig_end: int
    text: str
    dampened: bool = False


@dataclass(frozen=True, slots=True)
class _Compiled:
    rule: Rule
    regex: re.Pattern[str]
    guard: re.Pattern[str] | None
    triggers: tuple[str, ...]


def expand_macros(pattern: str, macros: dict[str, str], *, rule_id: str = "?") -> str:
    """Replace ``{{NAME}}`` placeholders (macros may reference other macros)."""
    for _ in range(8):
        if "{{" not in pattern:
            return pattern

        def repl(m: re.Match[str]) -> str:
            name = m.group(1)
            if name not in macros:
                raise ValueError(f"rule {rule_id}: unknown macro {{{{{name}}}}}")
            return macros[name]

        pattern = _MACRO_RE.sub(repl, pattern)
    if _MACRO_RE.search(pattern):
        raise ValueError(f"rule {rule_id}: macro expansion too deep (cycle?)")
    return pattern


def rule_score(hits: Iterable[RuleHit], signals: Sequence[str] = ()) -> float:
    """Noisy-OR over distinct rules: ``1 - prod(1 - w)``; evasion signals amplify only real hits."""
    best: dict[str, float] = {}
    for h in hits:
        if h.weight > best.get(h.rule_id, 0.0):
            best[h.rule_id] = h.weight
    if not best:
        return 0.0
    remaining = 1.0
    for w in best.values():
        remaining *= 1.0 - w
    evasion = sorted(s for s in set(signals) if s in EVASION_SIGNALS)[:EVASION_MAX_TERMS]
    for _ in evasion:
        remaining *= 1.0 - EVASION_WEIGHT
    return min(SCORE_CAP, 1.0 - remaining)


class RuleSet:
    """Compiled rule base. ``match`` returns every hit with spans in normalised and original text."""

    def __init__(self, rules: Iterable[Rule], *, macros: dict[str, str] | None = None) -> None:
        macros = dict(macros or {})
        self.rules: list[Rule] = []
        self._compiled: list[_Compiled] = []
        seen: set[str] = set()
        for rule in rules:
            if rule.id in seen:
                raise ValueError(f"duplicate rule id {rule.id}")
            seen.add(rule.id)
            self.rules.append(rule)
            self._compiled.append(self._compile(rule, macros))
        self._all_triggers = sorted({t for c in self._compiled for t in c.triggers})
        self._by_id = {r.id: r for r in self.rules}

    @staticmethod
    def _compile(rule: Rule, macros: dict[str, str]) -> _Compiled:
        pattern = fold_arabic_chars(expand_macros(rule.pattern.strip(), macros, rule_id=rule.id))
        try:
            regex = re.compile(pattern, re.MULTILINE)
            guard = re.compile(fold_arabic_chars(expand_macros(rule.guard, macros, rule_id=rule.id))) \
                if rule.guard else None
        except re.error as exc:
            raise ValueError(f"rule {rule.id}: invalid regex: {exc}") from exc
        triggers = tuple(sorted({normalize(t).text for t in rule.triggers if normalize(t).text}))
        return _Compiled(rule, regex, guard, triggers)

    # ------------------------------------------------------------------ loading

    @classmethod
    def from_yaml(cls, texts: Iterable[str], *, macros_text: str | None = None) -> RuleSet:
        macros: dict[str, str] = {}
        if macros_text:
            data = yaml.safe_load(macros_text) or {}
            macros = {str(k): str(v) for k, v in (data.get("macros") or {}).items()}
        rules: list[Rule] = []
        for text in texts:
            data = yaml.safe_load(text) or {}
            for raw in data.get("rules") or []:
                rules.append(Rule.model_validate(raw))
        return cls(rules, macros=macros)

    @classmethod
    def from_dir(cls, directory: str | Path = RULES_DIR) -> RuleSet:
        directory = Path(directory)
        macros_path = directory / MACROS_FILE
        files = [directory / name for name in RULE_FILES if (directory / name).exists()]
        extra = sorted(p for p in directory.glob("*.yaml") if p.name not in RULE_FILES and p.name != MACROS_FILE)
        texts = [p.read_text(encoding="utf-8") for p in [*files, *extra]]
        macros_text = macros_path.read_text(encoding="utf-8") if macros_path.exists() else None
        return cls.from_yaml(texts, macros_text=macros_text)

    @classmethod
    def default(cls) -> RuleSet:
        """The packaged rule base (cached)."""
        return _default_ruleset()

    # ------------------------------------------------------------------ introspection

    def __len__(self) -> int:
        return len(self.rules)

    def get(self, rule_id: str) -> Rule | None:
        return self._by_id.get(rule_id)

    def describe(self) -> list[dict[str, object]]:
        """Rule metadata for documentation and the dashboard."""
        return [
            {"id": r.id, "category": r.category, "weight": r.weight, "lang": r.lang, "description": r.description}
            for r in self.rules
        ]

    # ------------------------------------------------------------------ matching

    def match(self, normalized: NormalizedText) -> list[RuleHit]:
        """All hits on ``normalized.text`` with spans mapped back to the original text."""
        hits = self._match_plain(normalized)
        if SIG_BASE64 in normalized.signals and normalized.original:
            hits.extend(self._base64_hits(normalized))
        if hits:
            hits = self._dampen_quoted(normalized, hits)
            hits.sort(key=lambda h: (h.orig_start, h.orig_end, h.rule_id))
        return hits

    def score(self, hits: Iterable[RuleHit], signals: Sequence[str] = ()) -> float:
        return rule_score(hits, signals)

    def signals_for(self, hits: Iterable[RuleHit]) -> list[str]:
        """Signals declared by the rules that fired."""
        out = {self._by_id[h.rule_id].signal for h in hits if h.rule_id in self._by_id}
        return sorted(s for s in out if s)

    def _match_plain(self, normalized: NormalizedText) -> list[RuleHit]:
        text = normalized.text
        if not text:
            return []
        present = {t for t in self._all_triggers if t in text}
        original = normalized.original
        hits: list[RuleHit] = []
        for comp in self._compiled:
            if comp.triggers and not any(t in present for t in comp.triggers):
                continue
            count = 0
            for m in comp.regex.finditer(text):
                if m.end() <= m.start():
                    continue
                if comp.guard is not None and not comp.guard.search(m.group(0)):
                    continue
                o_start, o_end = normalized.to_original(m.start(), m.end())
                hits.append(RuleHit(
                    rule_id=comp.rule.id, category=comp.rule.category, weight=comp.rule.weight,
                    start=m.start(), end=m.end(), orig_start=o_start, orig_end=o_end,
                    text=original[o_start:o_end],
                ))
                count += 1
                if count >= MAX_HITS_PER_RULE:
                    break
        return hits

    def _base64_hits(self, normalized: NormalizedText) -> list[RuleHit]:
        """Decode base64 blobs and run the rules on the decoded text (one level deep)."""
        out: list[RuleHit] = []
        original = normalized.original
        for m in BASE64_RE.finditer(original):
            decoded = _decode_base64_text(m.group(0))
            if not decoded:
                continue
            inner = normalize(decoded)
            inner_hits = self._match_plain(inner)
            if not inner_hits:
                continue
            weight = min(0.95, max(0.6, rule_score(inner_hits)))
            start, end = normalized.from_original(m.start(), m.end())
            out.append(RuleHit(
                rule_id=BASE64_RULE_ID, category="obfuscation", weight=weight, start=start, end=end,
                orig_start=m.start(), orig_end=m.end(), text=m.group(0),
            ))
        return out

    @staticmethod
    def _dampen_quoted(normalized: NormalizedText, hits: list[RuleHit]) -> list[RuleHit]:
        """Halve hits that sit inside quotes in text that discusses attacks (articles, training)."""
        text = normalized.text
        if not any(q in text for q in _QUOTE_OPEN) or not _DISCUSSION_RE.search(text):
            return hits
        out: list[RuleHit] = []
        for h in hits:
            if h.rule_id != BASE64_RULE_ID and _is_quoted(text, h.start, h.end):
                out.append(RuleHit(
                    rule_id=h.rule_id, category=h.category, weight=h.weight * QUOTE_DAMPING, start=h.start,
                    end=h.end, orig_start=h.orig_start, orig_end=h.orig_end, text=h.text, dampened=True,
                ))
            else:
                out.append(h)
        return out


def _is_quoted(text: str, start: int, end: int) -> bool:
    line_start = text.rfind("\n", 0, start) + 1
    left = text[max(line_start, start - 120):start]
    line_end = text.find("\n", end)
    right = text[end:min(len(text) if line_end < 0 else line_end, end + 240)]
    straight_open = left.count('"') % 2 == 1 or left.count("`") % 2 == 1
    curly_open = max(left.rfind("“"), left.rfind("«"), left.rfind("„")) > max(left.rfind("”"), left.rfind("»"))
    if not (straight_open or curly_open):
        return False
    return any(q in right for q in _QUOTE_CLOSE)


def _decode_base64_text(blob: str) -> str | None:
    if not (any(c.isupper() for c in blob) and any(c.islower() for c in blob)):
        return None
    padded = blob + "=" * (-len(blob) % 4)
    try:
        raw = base64.b64decode(padded, validate=True)
        decoded = raw.decode("utf-8")
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return None
    if not decoded:
        return None
    printable = sum(1 for c in decoded if c.isprintable() or c in "\n\r\t")
    letters = sum(1 for c in decoded if c.isalpha())
    if printable / len(decoded) < 0.9 or letters / len(decoded) < 0.5:
        return None
    return decoded


@lru_cache(maxsize=1)
def _default_ruleset() -> RuleSet:
    rules = RuleSet.from_dir(RULES_DIR)
    log.debug("loaded %d detector rules from %s", len(rules), RULES_DIR)
    return rules
