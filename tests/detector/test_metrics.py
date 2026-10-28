"""Metric definitions and operating-point selection."""

from __future__ import annotations

import numpy as np
import pytest

from mirsad.detector.metrics import (
    classification_metrics,
    confusion,
    curves,
    percentile_ms,
    select_threshold,
    threshold_sweep,
)


def test_confusion_order_is_tn_fp_fn_tp():
    assert confusion(np.array([0, 0, 1, 1, 1]), np.array([0, 1, 0, 1, 1])) == (1, 1, 1, 2)


def test_classification_metrics_known_values():
    y = [0, 0, 0, 0, 1, 1, 1, 1]
    s = [0.1, 0.2, 0.6, 0.3, 0.9, 0.8, 0.4, 0.7]
    m = classification_metrics(y, s, 0.5)
    assert m["confusion_matrix"] == [[3, 1], [1, 3]]
    assert m["precision"] == pytest.approx(0.75)
    assert m["recall"] == pytest.approx(0.75)
    assert m["f1"] == pytest.approx(0.75)
    assert m["fpr"] == pytest.approx(0.25)
    assert m["fnr"] == pytest.approx(0.25)
    assert m["accuracy"] == pytest.approx(0.75)
    assert m["roc_auc"] == pytest.approx(15 / 16)  # 15 of 16 (positive, negative) pairs ordered correctly
    assert 0.0 < m["pr_auc"] <= 1.0
    assert (m["n"], m["positives"], m["negatives"]) == (8, 4, 4)


def test_single_class_split_has_no_auc_and_no_division_errors():
    m = classification_metrics([0, 0, 0], [0.1, 0.7, 0.2], 0.5)
    assert m["roc_auc"] is None and m["pr_auc"] is None
    assert m["precision"] == 0.0 and m["recall"] == 0.0 and m["f1"] == 0.0
    assert m["fpr"] == pytest.approx(1 / 3)
    empty = classification_metrics([], [], 0.5)
    assert empty["n"] == 0 and empty["accuracy"] == 0.0


def test_select_threshold_perfect_separation():
    y = [0, 0, 0, 1, 1, 1]
    s = [0.1, 0.2, 0.3, 0.7, 0.8, 0.9]
    sel = select_threshold(y, s)
    assert sel["f1"] == 1.0 and sel["fpr"] == 0.0 and sel["constraint_met"]
    assert 0.3 < sel["threshold"] <= 0.7
    assert sel["threshold"] == pytest.approx(0.5)  # halfway between the classes


def test_select_threshold_respects_fpr_limit():
    rng = np.random.default_rng(0)
    y = np.r_[np.zeros(200, dtype=int), np.ones(50, dtype=int)]
    s = np.r_[rng.uniform(0, 0.7, 200), rng.uniform(0.3, 1.0, 50)]
    sel = select_threshold(y, s, max_fpr=0.05)
    assert sel["constraint_met"]
    assert classification_metrics(y, s, sel["threshold"])["fpr"] <= 0.05 + 1e-9
    loose = select_threshold(y, s, max_fpr=1.0)
    assert loose["f1"] >= sel["f1"]


def test_select_threshold_degenerate_inputs():
    assert select_threshold([0, 0], [0.2, 0.4])["note"] == "no positives in tuning split"
    assert select_threshold([], [])["threshold"] == 0.5
    inverted = select_threshold([1, 1, 0, 0], [0.1, 0.2, 0.8, 0.9], max_fpr=0.0)
    assert inverted["f1"] == 0.0 or not inverted["constraint_met"]


def test_threshold_sweep_and_curves():
    y = [0, 1, 0, 1]
    s = [0.2, 0.8, 0.4, 0.6]
    sweep = threshold_sweep(y, s)
    assert [p["threshold"] for p in sweep] == [round(x, 2) for x in np.arange(0.05, 1.0, 0.05)]
    assert {"precision", "recall", "f1", "fpr", "accuracy"} <= set(sweep[0])
    custom = threshold_sweep(y, s, thresholds=[0.5])
    assert custom == [{"threshold": 0.5, "precision": 1.0, "recall": 1.0, "f1": 1.0, "fpr": 0.0, "accuracy": 1.0}]
    c = curves(y, s)
    assert c is not None and {"fpr", "tpr", "precision", "recall"} == set(c)
    assert curves([1, 1], [0.2, 0.3]) is None


def test_percentile_ms():
    assert percentile_ms([1.0, 2.0, 3.0], 50) == 2.0
    assert percentile_ms([], 95) == 0.0
