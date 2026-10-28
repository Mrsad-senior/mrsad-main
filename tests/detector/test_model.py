"""Linear text model: pickle-free persistence, windowed scoring and score combination.

The model here is trained in ``tmp_path`` on neutral synthetic data where the label is simply the
presence of the token ``AAA``.
"""

from __future__ import annotations

import json
import random

import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

from mirsad.detector import MODEL_SPAN_ID, InjectionDetector, load_model, normalize
from mirsad.detector.model import (
    COEF_FILE,
    FORMAT_VERSION,
    INTERCEPT_FILE,
    META_FILE,
    EnsembleConfig,
    FeatureConfig,
    LinearTextModel,
    ModelMeta,
    TextFeaturizer,
    calibrate,
    calibrate_array,
    chunk_bounds,
    combine_scores,
)

from .neutral_data import MARKER, neutral_text

TINY = FeatureConfig(char_features=2**12, word_features=2**10)


def synthetic(n: int, seed: int) -> tuple[list[str], np.ndarray]:
    rng = random.Random(seed)
    texts, labels = [], []
    for i in range(n):
        label = i % 2
        lang = ("en", "ar", "mixed")[i % 3]
        texts.append(normalize(neutral_text(rng, lang, positive=bool(label), serial=i)).text)
        labels.append(label)
    return texts, np.asarray(labels)


@pytest.fixture(scope="module")
def tiny_model() -> LinearTextModel:
    texts, y = synthetic(240, seed=11)
    X = TextFeaturizer(TINY).transform(texts)
    clf = LogisticRegression(C=50.0, class_weight="balanced", solver="liblinear", random_state=0).fit(X, y)
    meta = ModelMeta(features=TINY, ensemble=EnsembleConfig(pivot=0.4, model_threshold=0.5),
                     training={"note": "neutral synthetic token task", "n_train": len(texts)},
                     metrics={"val": {"f1": 1.0}})
    return LinearTextModel(clf.coef_.ravel(), float(clf.intercept_[0]), meta)


# --------------------------------------------------------------------------- learning sanity


def test_tiny_model_learns_the_marker_token(tiny_model):
    texts, y = synthetic(90, seed=99)  # held-out neutral texts
    p = tiny_model.score_texts(texts)
    assert np.all(p[y == 1] > 0.5)
    assert np.all(p[y == 0] < 0.5)


# --------------------------------------------------------------------------- persistence without pickle


def test_save_writes_only_numpy_and_json(tiny_model, tmp_path):
    out = tiny_model.save(tmp_path / "model")
    assert sorted(p.name for p in out.iterdir()) == sorted([COEF_FILE, INTERCEPT_FILE, META_FILE])
    assert LinearTextModel.files_present(out)
    meta = json.loads((out / META_FILE).read_text(encoding="utf-8"))
    assert meta["format_version"] == FORMAT_VERSION
    assert meta["features"]["char_features"] == 2**12
    assert meta["training"]["note"] == "neutral synthetic token task"
    coef = np.load(out / COEF_FILE, allow_pickle=False)
    assert coef.dtype == np.float32 and coef.shape == (TINY.n_features,)
    # the .npy header declares a plain numeric dtype: nothing executable is stored
    with (out / COEF_FILE).open("rb") as fh:
        header = fh.read(128)
    assert b"'descr': '<f4'" in header and b"|O" not in header


def test_round_trip_preserves_scores_and_meta(tiny_model, tmp_path, monkeypatch):
    out = tiny_model.save(tmp_path / "model")
    calls: list[dict] = []
    real_load = np.load

    def spy(*args, **kwargs):
        calls.append(kwargs)
        return real_load(*args, **kwargs)

    monkeypatch.setattr(np, "load", spy)
    loaded = LinearTextModel.load(out)
    assert len(calls) == 2
    assert all(kw.get("allow_pickle") is False for kw in calls)

    texts, _ = synthetic(30, seed=5)
    np.testing.assert_allclose(loaded.score_texts(texts), tiny_model.score_texts(texts), rtol=1e-6)
    np.testing.assert_array_equal(loaded.coef, tiny_model.coef)
    assert loaded.intercept == pytest.approx(tiny_model.intercept)
    assert loaded.meta.model_dump() == tiny_model.meta.model_dump()


def test_object_arrays_are_refused(tiny_model, tmp_path):
    out = tiny_model.save(tmp_path / "model")
    np.save(out / COEF_FILE, np.array([{"not": "numbers"}], dtype=object), allow_pickle=True)
    with pytest.raises(ValueError):
        LinearTextModel.load(out)
    assert load_model(out) is None


@pytest.mark.parametrize("problem", ["format", "length", "nan_coef", "two_intercepts", "int_coef"])
def test_load_validates_files(tiny_model, tmp_path, problem):
    out = tiny_model.save(tmp_path / "model")
    if problem == "format":
        meta = json.loads((out / META_FILE).read_text(encoding="utf-8"))
        meta["format_version"] = 99
        (out / META_FILE).write_text(json.dumps(meta), encoding="utf-8")
    elif problem == "length":
        np.save(out / COEF_FILE, np.zeros(7, dtype=np.float32))
    elif problem == "nan_coef":
        coef = tiny_model.coef.copy()
        coef[0] = np.nan
        np.save(out / COEF_FILE, coef)
    elif problem == "two_intercepts":
        np.save(out / INTERCEPT_FILE, np.zeros(2))
    else:
        np.save(out / COEF_FILE, np.zeros(TINY.n_features, dtype=np.int32))
    with pytest.raises(ValueError):
        LinearTextModel.load(out)


def test_constructor_checks_feature_count():
    with pytest.raises(ValueError):
        LinearTextModel(np.zeros(5), 0.0, ModelMeta(features=TINY))


def test_load_model_caches_by_directory_and_mtime(tiny_model, tmp_path):
    out = tiny_model.save(tmp_path / "model")
    assert load_model(out) is load_model(out)


# --------------------------------------------------------------------------- detector in ensemble mode


def test_detector_uses_saved_model(tiny_model, tmp_path):
    out = tiny_model.save(tmp_path / "model")
    det = InjectionDetector(out)
    assert det.mode == "ensemble"
    assert "+model-" in det.version
    assert det.info()["training"]["note"] == "neutral synthetic token task"
    rng = random.Random(3)
    pos = neutral_text(rng, "en", positive=True, serial=1)
    neg = neutral_text(rng, "en", positive=False, serial=2)
    r_pos, r_neg = det.scan(pos), det.scan(neg)
    assert r_pos.model_score > 0.5 > r_neg.model_score
    assert r_pos.score > r_neg.score
    assert r_pos.rule_score == 0.0  # neutral text: only the model contributes
    model_spans = [s for s in r_pos.spans if s.rule_id == MODEL_SPAN_ID]
    assert model_spans and all(pos[s.start:s.end] == s.text for s in model_spans)


def test_long_text_is_scored_by_windows(tiny_model):
    rng = random.Random(4)
    filler = " ".join(neutral_text(rng, "en", positive=False, serial=i) for i in range(40))
    text = normalize(filler + f" {MARKER} " + filler[:200]).text
    best, windows = tiny_model.score_windows([text], window_chars=600, stride_chars=300)
    assert len(windows) > 3
    assert all(0 <= w.start < w.end <= len(text) and w.owner == 0 for w in windows)
    top = max(windows, key=lambda w: w.score)
    assert top.score == pytest.approx(best[0])
    assert top.start <= text.index("aaa") < top.end
    # windows cover the whole text
    assert windows[0].start == 0 and windows[-1].end == len(text)


def test_score_windows_edge_cases(tiny_model):
    best, windows = tiny_model.score_windows([])
    assert best.shape == (0,) and windows == []
    best, windows = tiny_model.score_windows(["", "short text"])
    assert best.shape == (2,) and {w.owner for w in windows} == {0, 1}
    assert tiny_model.score_texts([]).shape == (0,)


def test_chunk_bounds_are_contiguous_and_prefer_whitespace():
    text = " ".join(f"word{i}" for i in range(400))
    bounds = chunk_bounds(text, 300)
    assert bounds[0][0] == 0 and bounds[-1][1] == len(text)
    assert all(a < b for a, b in bounds)
    assert all(bounds[i][1] == bounds[i + 1][0] for i in range(len(bounds) - 1))
    assert all(text[b] == " " for _, b in bounds[:-1])
    assert chunk_bounds("tiny", 300) == [(0, 4)]
    no_space = "x" * 1000
    assert chunk_bounds(no_space, 300)[-1][1] == 1000


# --------------------------------------------------------------------------- ensemble arithmetic


def test_noisy_or_and_calibration():
    ens = EnsembleConfig()
    assert combine_scores(0.0, 0.0, ens) == 0.0
    assert combine_scores(0.5, 0.5, ens) == pytest.approx(0.75)
    assert combine_scores(0.3, 0.0, ens) == pytest.approx(0.3)
    assert combine_scores(1.5, -1.0, ens) == pytest.approx(1.0)  # inputs are clipped
    assert calibrate(0.5, 0.5) == pytest.approx(0.5)
    assert calibrate(0.2, 0.2) == pytest.approx(0.5)  # the tuned pivot maps to the flag threshold
    assert calibrate(0.1, 0.2) == pytest.approx(0.25)
    assert calibrate(1.0, 0.2) == pytest.approx(1.0)
    grid = np.linspace(0, 1, 101)
    cal = calibrate_array(grid, 0.3)
    assert np.all(np.diff(cal) >= 0)
    np.testing.assert_allclose(cal, [calibrate(x, 0.3) for x in grid])
    shaped = EnsembleConfig(alpha=2.0, beta=0.5, pivot=0.5)
    assert combine_scores(0.5, 0.5, shaped) == pytest.approx(1 - 0.25 * 0.5 ** 0.5)
