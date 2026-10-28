"""Binary-classification metrics and operating-point selection for the detector."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score, roc_curve


def confusion(y_true: np.ndarray, y_pred: np.ndarray) -> tuple[int, int, int, int]:
    """(tn, fp, fn, tp)."""
    y_true = np.asarray(y_true, dtype=int)
    y_pred = np.asarray(y_pred, dtype=int)
    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    tn = int(np.sum((y_true == 0) & (y_pred == 0)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))
    return tn, fp, fn, tp


def _safe_div(a: float, b: float) -> float:
    return float(a / b) if b else 0.0


def classification_metrics(y_true: Sequence[int], scores: Sequence[float], threshold: float) -> dict[str, Any]:
    """Precision, recall, F1, accuracy, FPR, ROC-AUC, PR-AUC and the confusion matrix at ``threshold``.

    AUCs are ``None`` when the split has a single class (undefined).
    """
    y = np.asarray(y_true, dtype=int)
    s = np.asarray(scores, dtype=float)
    pred = (s >= threshold).astype(int)
    tn, fp, fn, tp = confusion(y, pred)
    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1 = _safe_div(2 * precision * recall, precision + recall)
    both = len(np.unique(y)) == 2
    return {
        "n": int(len(y)),
        "positives": int(np.sum(y == 1)),
        "negatives": int(np.sum(y == 0)),
        "threshold": float(threshold),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": _safe_div(tp + tn, len(y)),
        "fpr": _safe_div(fp, fp + tn),
        "fnr": _safe_div(fn, fn + tp),
        "roc_auc": float(roc_auc_score(y, s)) if both else None,
        "pr_auc": float(average_precision_score(y, s)) if both else None,
        "confusion_matrix": [[tn, fp], [fn, tp]],
    }


def select_threshold(y_true: Sequence[int], scores: Sequence[float], *, max_fpr: float = 0.05) -> dict[str, Any]:
    """Threshold maximising F1 subject to FPR <= ``max_fpr`` (exact search over all cut points).

    Falls back to the lowest-FPR threshold when the constraint cannot be met; ties prefer the
    higher threshold (fewer false alarms).
    """
    y = np.asarray(y_true, dtype=int)
    s = np.asarray(scores, dtype=float)
    n_pos = int(np.sum(y == 1))
    n_neg = int(np.sum(y == 0))
    if len(y) == 0 or n_pos == 0:
        return {"threshold": 0.5, "f1": 0.0, "fpr": 0.0, "recall": 0.0, "precision": 0.0,
                "constraint_met": n_pos == 0, "note": "no positives in tuning split"}
    order = np.argsort(-s, kind="mergesort")
    s_sorted = s[order]
    y_sorted = y[order]
    tp = np.cumsum(y_sorted == 1)
    fp = np.cumsum(y_sorted == 0)
    # candidate cut after each distinct score value (predict positive for score >= s_sorted[i])
    last_of_value = np.r_[s_sorted[1:] != s_sorted[:-1], True]
    idx = np.nonzero(last_of_value)[0]
    tp_c, fp_c = tp[idx].astype(float), fp[idx].astype(float)
    thresholds = s_sorted[idx]
    precision = np.divide(tp_c, tp_c + fp_c, out=np.zeros_like(tp_c), where=(tp_c + fp_c) > 0)
    recall = tp_c / n_pos
    f1 = np.divide(2 * precision * recall, precision + recall, out=np.zeros_like(tp_c), where=(precision + recall) > 0)
    fpr = fp_c / n_neg if n_neg else np.zeros_like(fp_c)
    ok = fpr <= max_fpr + 1e-12
    if np.any(ok):
        cand = np.nonzero(ok)[0]
        best_f1 = f1[cand].max()
        best = cand[np.nonzero(np.isclose(f1[cand], best_f1))[0]]
        i = int(best[np.argmax(thresholds[best])])
        met = True
    else:
        i = int(np.argmin(fpr))
        met = False
    # place the cut halfway to the next lower score so tiny score jitter does not flip decisions
    t = float(thresholds[i])
    lower = s_sorted[s_sorted < t]
    if lower.size:
        t = float((t + lower.max()) / 2.0)
    return {"threshold": t, "f1": float(f1[i]), "fpr": float(fpr[i]), "recall": float(recall[i]),
            "precision": float(precision[i]), "constraint_met": met}


def threshold_sweep(y_true: Sequence[int], scores: Sequence[float],
                    thresholds: Sequence[float] | None = None) -> list[dict[str, float]]:
    thresholds = thresholds if thresholds is not None else [round(x, 2) for x in np.arange(0.05, 1.0, 0.05)]
    out = []
    for t in thresholds:
        m = classification_metrics(y_true, scores, float(t))
        out.append({"threshold": float(t), "precision": m["precision"], "recall": m["recall"], "f1": m["f1"],
                    "fpr": m["fpr"], "accuracy": m["accuracy"]})
    return out


def curves(y_true: Sequence[int], scores: Sequence[float]) -> dict[str, Any] | None:
    """ROC and PR curve points (for figures); ``None`` for single-class splits."""
    y = np.asarray(y_true, dtype=int)
    if len(np.unique(y)) < 2:
        return None
    fpr, tpr, _ = roc_curve(y, scores)
    prec, rec, _ = precision_recall_curve(y, scores)
    return {"fpr": fpr.tolist(), "tpr": tpr.tolist(), "precision": prec.tolist(), "recall": rec.tolist()}


def percentile_ms(samples: Sequence[float], q: float) -> float:
    return float(np.percentile(np.asarray(samples, dtype=float), q)) if len(samples) else 0.0
