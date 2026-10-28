"""Hashed n-gram features + logistic regression, persisted without pickle.

Features: character n-grams (2-5, ``char_wb``) and word n-grams (1-2), each hashed with
:class:`~sklearn.feature_extraction.text.HashingVectorizer` and L2-normalised, then concatenated.
The trained model is just a weight vector and a bias, saved as ``coef.npy`` / ``intercept.npy``
(loaded with ``allow_pickle=False``) plus ``meta.json`` — no executable artefacts.

Long texts are scored over sliding windows. To avoid featurising every character twice, the text is
cut (at whitespace) into ``stride``-sized chunks that are featurised once; a window is the sum of
``window/stride`` consecutive chunk vectors, re-normalised.
"""

from __future__ import annotations

import json
import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import scipy.sparse as sp
from pydantic import BaseModel, Field
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.preprocessing import normalize as l2_normalize

log = logging.getLogger("mirsad.detector")

FORMAT_VERSION = 1
COEF_FILE = "coef.npy"
INTERCEPT_FILE = "intercept.npy"
META_FILE = "meta.json"


class FeatureConfig(BaseModel):
    """Vectoriser parameters (stored in meta.json so inference rebuilds identical features)."""

    char_ngram: tuple[int, int] = (2, 5)
    word_ngram: tuple[int, int] = (1, 2)
    char_features: int = 2**20
    word_features: int = 2**18
    word_token_pattern: str = r"(?u)\b\w+\b"  # noqa: S105 - a regex, not a credential

    @property
    def n_features(self) -> int:
        return self.char_features + self.word_features


class EnsembleConfig(BaseModel):
    """How model and rule scores combine, tuned on the validation split.

    ``raw = 1 - (1-m)^alpha * (1-r)^beta``; the tuned decision threshold ``pivot`` on ``raw`` is then
    mapped to 0.5 with a monotone piecewise-linear calibration so the policy thresholds (.5 flag /
    .8 block) keep their meaning whatever the operating point is.
    """

    alpha: float = 1.0
    beta: float = 1.0
    pivot: float = 0.5
    flag_threshold: float = 0.5
    block_threshold: float = 0.8
    #: model-only probability above which a window is reported as a span (and removed by sanitize)
    model_threshold: float = 0.5
    #: rules-only operating point found on validation (reported for the ablation)
    rules_threshold: float = 0.5


class ModelMeta(BaseModel):
    format_version: int = FORMAT_VERSION
    model_type: str = "logistic_regression"
    features: FeatureConfig = Field(default_factory=FeatureConfig)
    ensemble: EnsembleConfig = Field(default_factory=EnsembleConfig)
    training: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)


class TextFeaturizer:
    """Stateless hashed char + word n-gram features over already-normalised text."""

    def __init__(self, config: FeatureConfig | None = None) -> None:
        self.config = config or FeatureConfig()
        c = self.config
        self._char = HashingVectorizer(
            analyzer="char_wb", ngram_range=tuple(c.char_ngram), n_features=c.char_features,
            alternate_sign=False, norm=None, lowercase=False, dtype=np.float32,
        )
        self._word = HashingVectorizer(
            analyzer="word", ngram_range=tuple(c.word_ngram), n_features=c.word_features,
            token_pattern=c.word_token_pattern, alternate_sign=False, norm=None, lowercase=False,
            dtype=np.float32,
        )

    def raw_counts(self, texts: Sequence[str]) -> tuple[sp.csr_matrix, sp.csr_matrix]:
        return self._char.transform(texts), self._word.transform(texts)

    @staticmethod
    def finish(char_counts: sp.spmatrix, word_counts: sp.spmatrix) -> sp.csr_matrix:
        """L2-normalise each block separately and concatenate."""
        return sp.hstack(
            [l2_normalize(char_counts, norm="l2", copy=False), l2_normalize(word_counts, norm="l2", copy=False)],
            format="csr",
        )

    def transform(self, texts: Sequence[str]) -> sp.csr_matrix:
        """One feature row per text (used for training)."""
        return self.finish(*self.raw_counts(list(texts)))


@dataclass(frozen=True, slots=True)
class Window:
    """One scored window: owning text index, normalised char range and model probability."""

    owner: int
    start: int
    end: int
    score: float


def chunk_bounds(text: str, stride: int) -> list[tuple[int, int]]:
    """Cut ``text`` into consecutive chunks of ~``stride`` chars, preferring whitespace boundaries."""
    n = len(text)
    if n <= stride:
        return [(0, n)]
    bounds: list[tuple[int, int]] = []
    pos = 0
    slack = max(10, stride // 6)
    while pos < n:
        target = pos + stride
        if target >= n:
            bounds.append((pos, n))
            break
        cut = -1
        for j in range(target, min(n, target + slack)):
            if text[j] in " \n":
                cut = j
                break
        if cut < 0:
            back = text.rfind(" ", pos + stride // 2, target)
            cut = back if back > pos else target
        bounds.append((pos, cut))
        pos = cut
    return bounds


class LinearTextModel:
    """Logistic-regression weights over :class:`TextFeaturizer` features."""

    def __init__(self, coef: np.ndarray, intercept: float, meta: ModelMeta | None = None) -> None:
        self.meta = meta or ModelMeta()
        coef = np.asarray(coef, dtype=np.float32).ravel()
        if coef.shape[0] != self.meta.features.n_features:
            raise ValueError(f"coef has {coef.shape[0]} weights, features expect {self.meta.features.n_features}")
        self.coef = coef
        self.intercept = float(intercept)
        self.featurizer = TextFeaturizer(self.meta.features)

    # ------------------------------------------------------------------ scoring

    def decision(self, X: sp.spmatrix) -> np.ndarray:
        return np.asarray(X @ self.coef, dtype=np.float64).ravel() + self.intercept

    def predict_proba(self, X: sp.spmatrix) -> np.ndarray:
        z = np.clip(self.decision(X), -40.0, 40.0)
        return 1.0 / (1.0 + np.exp(-z))

    def score_texts(self, texts: Sequence[str]) -> np.ndarray:
        """Whole-text probability (no windowing)."""
        if not texts:
            return np.zeros(0)
        return self.predict_proba(self.featurizer.transform(list(texts)))

    def score_windows(self, texts: Sequence[str], *, window_chars: int = 600,
                      stride_chars: int = 300) -> tuple[np.ndarray, list[Window]]:
        """Max window probability per text, plus every window (owner, normalised range, score)."""
        n_texts = len(texts)
        if n_texts == 0:
            return np.zeros(0), []
        stride = max(50, stride_chars)
        per_window = max(1, round(window_chars / stride))
        chunk_texts: list[str] = []
        chunk_owner: list[int] = []
        chunk_ranges: list[tuple[int, int]] = []
        first_chunk: list[int] = []
        for i, text in enumerate(texts):
            first_chunk.append(len(chunk_texts))
            for a, b in chunk_bounds(text, stride) if text else [(0, 0)]:
                chunk_texts.append(text[a:b])
                chunk_owner.append(i)
                chunk_ranges.append((a, b))
        char_c, word_c = self.featurizer.raw_counts(chunk_texts)

        rows: list[int] = []
        cols: list[int] = []
        windows_meta: list[tuple[int, int, int]] = []
        n_chunks = len(chunk_texts)
        for i in range(n_texts):
            lo = first_chunk[i]
            hi = first_chunk[i + 1] if i + 1 < n_texts else n_chunks
            starts = range(lo, max(lo + 1, hi - per_window + 1))
            for w, s in enumerate(starts, start=len(windows_meta)):
                e = min(hi, s + per_window)
                rows.extend([w] * (e - s))
                cols.extend(range(s, e))
                windows_meta.append((i, chunk_ranges[s][0], chunk_ranges[e - 1][1]))
        assign = sp.csr_matrix(
            (np.ones(len(rows), dtype=np.float32), (rows, cols)), shape=(len(windows_meta), n_chunks)
        )
        X = self.featurizer.finish(assign @ char_c, assign @ word_c)
        probs = self.predict_proba(X)
        best = np.zeros(n_texts)
        windows: list[Window] = []
        for (owner, a, b), p in zip(windows_meta, probs, strict=True):
            windows.append(Window(owner, a, b, float(p)))
            if p > best[owner]:
                best[owner] = p
        return best, windows

    # ------------------------------------------------------------------ persistence (no pickle)

    def save(self, model_dir: str | Path) -> Path:
        model_dir = Path(model_dir)
        model_dir.mkdir(parents=True, exist_ok=True)
        np.save(model_dir / COEF_FILE, self.coef.astype(np.float32), allow_pickle=False)
        np.save(model_dir / INTERCEPT_FILE, np.asarray([self.intercept], dtype=np.float64), allow_pickle=False)
        (model_dir / META_FILE).write_text(
            json.dumps(self.meta.model_dump(mode="json"), indent=2, ensure_ascii=False, default=_json_default),
            encoding="utf-8",
        )
        return model_dir

    @classmethod
    def load(cls, model_dir: str | Path) -> LinearTextModel:
        """Load ``coef.npy``/``intercept.npy`` with ``allow_pickle=False`` and ``meta.json``."""
        model_dir = Path(model_dir)
        meta = ModelMeta.model_validate_json((model_dir / META_FILE).read_text(encoding="utf-8"))
        if meta.format_version != FORMAT_VERSION:
            raise ValueError(f"unsupported model format {meta.format_version}")
        coef = np.load(model_dir / COEF_FILE, allow_pickle=False)
        intercept = np.load(model_dir / INTERCEPT_FILE, allow_pickle=False)
        if coef.ndim != 1 or not np.issubdtype(coef.dtype, np.floating) or not np.all(np.isfinite(coef)):
            raise ValueError("coef.npy must be a finite 1-D float array")
        if intercept.size != 1 or not math.isfinite(float(intercept.ravel()[0])):
            raise ValueError("intercept.npy must hold one finite value")
        return cls(coef, float(intercept.ravel()[0]), meta)

    @staticmethod
    def files_present(model_dir: str | Path) -> bool:
        model_dir = Path(model_dir)
        return all((model_dir / f).is_file() for f in (COEF_FILE, INTERCEPT_FILE, META_FILE))


def _json_default(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"not JSON serialisable: {type(value).__name__}")


def combine_scores(model_score: float, rule_score: float, ensemble: EnsembleConfig) -> float:
    """Noisy-OR of model and rule scores (with tuned exponents) followed by threshold calibration."""
    m = min(max(model_score, 0.0), 1.0)
    r = min(max(rule_score, 0.0), 1.0)
    raw = 1.0 - (1.0 - m) ** ensemble.alpha * (1.0 - r) ** ensemble.beta
    return calibrate(raw, ensemble.pivot)


def calibrate(raw: float, pivot: float) -> float:
    """Monotone piecewise-linear map sending ``pivot`` to 0.5 (identity when pivot == 0.5)."""
    pivot = min(max(pivot, 1e-6), 1.0 - 1e-6)
    raw = min(max(raw, 0.0), 1.0)
    if raw < pivot:
        return 0.5 * raw / pivot
    return 0.5 + 0.5 * (raw - pivot) / (1.0 - pivot)


def calibrate_array(raw: np.ndarray, pivot: float) -> np.ndarray:
    pivot = min(max(pivot, 1e-6), 1.0 - 1e-6)
    raw = np.clip(raw, 0.0, 1.0)
    return np.where(raw < pivot, 0.5 * raw / pivot, 0.5 + 0.5 * (raw - pivot) / (1.0 - pivot))
