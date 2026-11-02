"""The injection detector: normalisation -> rules -> ML model -> noisy-OR ensemble."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from mirsad.detector.language import detect_language
from mirsad.detector.layered import ContentLayer, EmbeddingSimilarity, OllamaJudge
from mirsad.detector.model import EnsembleConfig, LinearTextModel, Window, combine_scores
from mirsad.detector.normalize import NormalizedText, normalize
from mirsad.detector.rules import RuleHit, RuleSet, rule_score
from mirsad.models import DetectionResult, DetectionSpan

log = logging.getLogger("mirsad.detector")

DEFAULT_MODEL_DIR = Path(__file__).resolve().parent / "model"
MODEL_SPAN_ID = "model:window"
MAX_MODEL_SPANS = 3
#: leaves of a structured value shorter than this (ids, dates, flags) skip the model
MIN_MODEL_CHARS = 12

Mode = Literal["ensemble", "rules_only"]

_MODEL_CACHE: dict[tuple[str, float], LinearTextModel] = {}
_MODEL_LOCK = threading.Lock()


def load_model(model_dir: str | Path) -> LinearTextModel | None:
    """Load (and cache) a model directory; ``None`` when files are missing or invalid."""
    path = Path(model_dir).resolve()
    if not LinearTextModel.files_present(path):
        log.info("detector model not found in %s; using rules-only mode", path)
        return None
    try:
        key = (str(path), (path / "meta.json").stat().st_mtime)
    except OSError:
        return None
    with _MODEL_LOCK:
        cached = _MODEL_CACHE.get(key)
        if cached is not None:
            return cached
        try:
            model = LinearTextModel.load(path)
        except Exception as exc:  # corrupt/foreign files must never take the gateway down
            log.warning("detector model in %s is invalid (%s); using rules-only mode", path, exc)
            return None
        _MODEL_CACHE.clear()
        _MODEL_CACHE[key] = model
        return model


@dataclass(slots=True)
class _Analysis:
    normalized: NormalizedText
    hits: list[RuleHit]
    rule_score: float
    model_score: float = 0.0
    windows: list[Window] = field(default_factory=list)


class InjectionDetector:
    """Scores text for prompt injection; works rules-only when no trained model is available."""

    def __init__(self, model_dir: str | Path | None = None, *, window_chars: int = 600,
                 stride_chars: int = 300, rules: RuleSet | None = None,
                 model: LinearTextModel | None = None,
                 semantic: ContentLayer | None = None,
                 judge: ContentLayer | None = None) -> None:
        if window_chars < 50 or stride_chars < 50 or stride_chars > window_chars:
            raise ValueError("need 50 <= stride_chars <= window_chars")
        self.window_chars = window_chars
        self.stride_chars = stride_chars
        self.rules = rules or RuleSet.default()
        self.model_dir = Path(model_dir) if model_dir is not None else None
        self.model = model if model is not None else (load_model(model_dir) if model_dir is not None else None)
        self.ensemble = self.model.meta.ensemble if self.model is not None else EnsembleConfig()
        self.semantic = semantic
        self.judge = judge
        self._version = _fingerprint(self.rules, self.model)

    @classmethod
    def default(cls) -> InjectionDetector:
        """Detector with the packaged model (``mirsad/detector/model/``), rules-only if it is absent."""
        # Optional providers require explicit enablement. Missing enabled providers
        # raise rather than silently downgrade security to keyword-only scanning.
        semantic = EmbeddingSimilarity.local() if os.getenv('MIRSAD_SEMANTIC_ENABLED') == '1' else None
        judge = OllamaJudge(model=os.getenv('MIRSAD_JUDGE_MODEL', 'qwen2.5:3b'),
                            extraction=os.getenv('MIRSAD_JUDGE_EXTRACTION', 'flag')) if os.getenv('MIRSAD_JUDGE_ENABLED') == '1' else None
        return cls(DEFAULT_MODEL_DIR, semantic=semantic, judge=judge)

    @property
    def mode(self) -> Mode:
        return "ensemble" if self.model is not None else "rules_only"

    @property
    def version(self) -> str:
        """Fingerprint of the rule base and model weights; replays report it to explain score drift."""
        return self._version

    def info(self) -> dict[str, Any]:
        """Configuration summary for the dashboard / audit."""
        return {
            "mode": self.mode,
            "content_layers": ["rules", *( ["linear_ml"] if self.model else []),
                               *( ["semantic"] if self.semantic else []), *( ["llm_judge"] if self.judge else [])],
            "version": self.version,
            "rules": len(self.rules),
            "window_chars": self.window_chars,
            "stride_chars": self.stride_chars,
            "ensemble": self.ensemble.model_dump(),
            "model_dir": str(self.model_dir) if self.model_dir else None,
            "training": self.model.meta.training if self.model is not None else {},
        }

    # ------------------------------------------------------------------ public API

    def scan(self, text: str) -> DetectionResult:
        """Score ``text`` in [0, 1]; label by the (calibrated) .5 / .8 thresholds."""
        start = time.perf_counter()
        text = _as_text(text)
        analysis = self._analyze([text])[0]
        result = self._enrich(text, self._result(text, analysis))
        result.latency_ms = (time.perf_counter() - start) * 1000.0
        return result

    def scan_many(self, texts: Sequence[str]) -> list[DetectionResult]:
        """Batch scan (one vectoriser call for all texts); latency is the per-text average."""
        start = time.perf_counter()
        items = [_as_text(t) for t in texts]
        analyses = self._analyze(items)
        results = [self._enrich(t, self._result(t, a)) for t, a in zip(items, analyses, strict=True)]
        per = (time.perf_counter() - start) * 1000.0 / max(1, len(results))
        for r in results:
            r.latency_ms = per
        return results

    def scan_structured(self, value: Any) -> DetectionResult:
        """Scan every string (keys and values) inside a JSON-like value and merge the results.

        Spans refer to ``json.dumps(value, ensure_ascii=False)`` (default separators); a plain string is
        scanned as-is.
        """
        if isinstance(value, str):
            return self.scan(value)
        start = time.perf_counter()
        dump, leaves = dump_with_positions(value)
        texts = [leaf.text for leaf in leaves]
        analyses = self._analyze(texts, min_model_chars=MIN_MODEL_CHARS)
        best_score = best_model = best_rule = 0.0
        spans: list[DetectionSpan] = []
        signals: set[str] = set()
        layer_scores: dict[str, float] = {}
        layer_reasons: dict[str, str] = {}
        for leaf, analysis in zip(leaves, analyses, strict=True):
            leaf_result = self._result(leaf.text, analysis, detect_lang=False)
            best_score = max(best_score, leaf_result.score)
            best_model = max(best_model, leaf_result.model_score)
            best_rule = max(best_rule, leaf_result.rule_score)
            signals.update(leaf_result.signals)
            for name, value in leaf_result.layer_scores.items():
                if value >= layer_scores.get(name, -1):
                    layer_scores[name] = value
                    layer_reasons[name] = leaf_result.layer_reasons.get(name, '')
            for s in leaf_result.spans:
                a, b = leaf.positions[s.start], leaf.positions[s.end]
                spans.append(DetectionSpan(start=a, end=b, text=dump[a:b], rule_id=s.rule_id, score=s.score))
        spans.sort(key=lambda s: (s.start, s.end))
        language = detect_language("\n".join(texts)) if texts else "other"
        result = DetectionResult(
            score=round(best_score, 6), label=self._label(best_score), language=language, spans=spans,
            signals=sorted(signals), model_score=round(best_model, 6), rule_score=round(best_rule, 6),
            layer_scores=layer_scores, layer_reasons=layer_reasons,
        )
        # Judge the whole structured document ONCE, not once per JSON leaf.
        result = self._enrich(dump, result)
        result.latency_ms = (time.perf_counter() - start) * 1000.0
        return result

    def _enrich(self, text: str, result: DetectionResult) -> DetectionResult:
        """Merge independent layer evidence with existing score without weakening it.

        Max aggregation is deliberately conservative. It is a heuristic risk
        ranking, not a calibrated attack probability; formal calibration remains
        part of the benchmark deliverable.
        """
        scores = {'keywords': result.rule_score}
        reasons = {'keywords': 'Rules/patterns matched' if result.rule_score else 'No rule matched'}
        if self.model is not None:
            scores['linear_ml'] = result.model_score
            reasons['linear_ml'] = 'Trained linear text classifier score'
        for name, layer in (('semantic', self.semantic), ('llm_judge', self.judge)):
            if layer is not None and text.strip():
                signal = layer.score(text)  # failure propagates; gateway blocks the untrusted result
                if not 0 <= signal.score <= 1:
                    raise ValueError(f'{name} returned invalid risk score')
                scores[name] = round(signal.score, 6)
                reasons[name] = signal.reason[:250]
        value = max((result.score, *scores.values()))
        result.score = round(value, 6)
        result.label = self._label(value)
        result.layer_scores = scores
        result.layer_reasons = reasons
        return result

    # ------------------------------------------------------------------ internals

    def _label(self, score: float) -> Literal["benign", "suspicious", "injection"]:
        if score >= self.ensemble.block_threshold:
            return "injection"
        if score >= self.ensemble.flag_threshold:
            return "suspicious"
        return "benign"

    def _analyze(self, texts: Sequence[str], *, min_model_chars: int = 1) -> list[_Analysis]:
        analyses: list[_Analysis] = []
        for text in texts:
            norm = normalize(text)
            hits = self.rules.match(norm)
            analyses.append(_Analysis(norm, hits, rule_score(hits, norm.signals)))
        if self.model is not None:
            idx = [i for i, a in enumerate(analyses) if len(a.normalized.text) >= min_model_chars]
            if idx:
                best, windows = self.model.score_windows(
                    [analyses[i].normalized.text for i in idx],
                    window_chars=self.window_chars, stride_chars=self.stride_chars,
                )
                for local, i in enumerate(idx):
                    analyses[i].model_score = float(best[local])
                for w in windows:
                    target = analyses[idx[w.owner]]
                    target.windows.append(w)
        return analyses

    def combined_score(self, model_score: float, rule_score_value: float) -> float:
        if self.model is None:
            return min(max(rule_score_value, 0.0), 1.0)
        return combine_scores(model_score, rule_score_value, self.ensemble)

    def _result(self, text: str, analysis: _Analysis, *, detect_lang: bool = True) -> DetectionResult:
        score = self.combined_score(analysis.model_score, analysis.rule_score)
        spans: list[DetectionSpan] = []
        seen: set[tuple[int, int, str]] = set()
        for h in analysis.hits:
            key = (h.orig_start, h.orig_end, h.rule_id)
            if key in seen or h.orig_end <= h.orig_start:
                continue
            seen.add(key)
            spans.append(DetectionSpan(start=h.orig_start, end=h.orig_end, text=h.text, rule_id=h.rule_id,
                                       score=round(h.weight, 4)))
        norm = analysis.normalized
        flagged = [w for w in analysis.windows if w.score >= self.ensemble.model_threshold]
        flagged.sort(key=lambda w: w.score, reverse=True)
        for w in flagged[:MAX_MODEL_SPANS]:
            if w.end <= w.start:
                continue
            a, b = norm.to_original(w.start, w.end)
            spans.append(DetectionSpan(start=a, end=b, text=text[a:b], rule_id=MODEL_SPAN_ID,
                                       score=round(w.score, 4)))
        spans.sort(key=lambda s: (s.start, s.end))
        signals = sorted(set(norm.signals) | set(self.rules.signals_for(analysis.hits)))
        return DetectionResult(
            score=round(score, 6),
            label=self._label(score),
            language=detect_language(text) if detect_lang else "other",
            spans=spans,
            signals=signals,
            model_score=round(analysis.model_score, 6),
            rule_score=round(analysis.rule_score, 6),
        )


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return value if isinstance(value, str) else str(value)


def _fingerprint(rules: RuleSet, model: LinearTextModel | None) -> str:
    """``rules-<12 hex>`` or ``rules-<12 hex>+model-<12 hex>``."""
    rule_view = [(r.id, r.weight, r.pattern, r.guard, r.lang) for r in rules.rules]
    digest = hashlib.sha256(json.dumps(rule_view, ensure_ascii=False).encode("utf-8")).hexdigest()[:12]
    version = f"rules-{digest}"
    if model is not None:
        h = hashlib.sha256(model.coef.tobytes())
        h.update(repr(model.intercept).encode("ascii"))
        h.update(model.meta.ensemble.model_dump_json().encode("utf-8"))
        version += f"+model-{h.hexdigest()[:12]}"
    return version


# --------------------------------------------------------------------------- structured values


@dataclass(slots=True)
class Leaf:
    """A string inside a structured value and where each of its characters sits in the JSON dump."""

    text: str
    positions: list[int]  # positions[i] = dump index of char i; positions[len(text)] = end of the string body


_ESCAPE_CACHE: dict[str, str] = {}


def _escape(ch: str) -> str:
    esc = _ESCAPE_CACHE.get(ch)
    if esc is None:
        esc = json.dumps(ch, ensure_ascii=False)[1:-1]
        if len(_ESCAPE_CACHE) < 4096:
            _ESCAPE_CACHE[ch] = esc
    return esc


def dump_with_positions(value: Any) -> tuple[str, list[Leaf]]:
    """``json.dumps(value, ensure_ascii=False)`` plus a character map for every string leaf."""
    parts: list[str] = []
    leaves: list[Leaf] = []
    length = 0

    def emit(s: str) -> None:
        nonlocal length
        parts.append(s)
        length += len(s)

    def emit_string(s: str) -> None:
        nonlocal length
        emit('"')
        positions: list[int] = []
        for ch in s:
            positions.append(length)
            emit(_escape(ch))
        positions.append(length)
        emit('"')
        if any(c.isalpha() for c in s):
            leaves.append(Leaf(s, positions))

    def walk(v: Any, depth: int) -> None:
        if depth > 64:
            emit_string(str(v))
            return
        if isinstance(v, str):
            emit_string(v)
        elif v is None or isinstance(v, (bool, int, float)):
            emit(json.dumps(v))
        elif isinstance(v, dict):
            emit("{")
            for i, (k, item) in enumerate(v.items()):
                if i:
                    emit(", ")
                emit_string(k if isinstance(k, str) else _json_key(k))
                emit(": ")
                walk(item, depth + 1)
            emit("}")
        elif isinstance(v, (list, tuple)):
            emit("[")
            for i, item in enumerate(v):
                if i:
                    emit(", ")
                walk(item, depth + 1)
            emit("]")
        elif hasattr(v, "model_dump"):
            walk(v.model_dump(mode="json"), depth + 1)
        else:
            emit_string(str(v))

    walk(value, 0)
    return "".join(parts), leaves


def _json_key(key: Any) -> str:
    if key is None:
        return "null"
    if isinstance(key, bool):
        return "true" if key else "false"
    if isinstance(key, (int, float)):
        return json.dumps(key)
    return str(key)
