"""Report-quality matplotlib figures for detector evaluation (150 dpi PNG, no seaborn).

Colour roles: categorical slots 1-3 (validated colour-blind-safe as a set) identify the three
systems; a single-hue blue ramp encodes counts in confusion matrices; text stays in ink colours.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, to_rgb  # noqa: E402
from sklearn.metrics import auc, average_precision_score, precision_recall_curve, roc_curve  # noqa: E402

DPI = 150
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SYSTEM_COLORS = {"ensemble": "#2a78d6", "model_only": "#eb6834", "rules_only": "#1baf7a"}
SYSTEM_LABELS = {"ensemble": "Ensemble (rules + model)", "model_only": "Model only", "rules_only": "Rules only"}
SWEEP_COLORS = {"precision": "#2a78d6", "recall": "#eb6834", "f1": "#1baf7a", "fpr": "#eda100"}
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
SYSTEMS = ("ensemble", "model_only", "rules_only")


def _style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "font.family": "sans-serif", "font.size": 9, "axes.titlesize": 10, "axes.titleweight": "bold",
        "axes.labelcolor": INK_2, "axes.edgecolor": AXIS, "axes.linewidth": 0.8, "text.color": INK,
        "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": INK_2, "ytick.labelcolor": INK_2,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "grid.linestyle": "-",
        "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 2.0,
        "lines.solid_capstyle": "round", "legend.frameon": False, "legend.fontsize": 8,
    })


def _grid_shape(n: int) -> tuple[int, int]:
    cols = min(3, max(1, n))
    return (n + cols - 1) // cols, cols


def _save(fig: plt.Figure, path: Path) -> str:
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return str(path)


def confusion_matrices(out: Path, report: Mapping[str, Any]) -> str:
    names = [n for n in report["splits"] if n != "train"]
    rows, cols = _grid_shape(len(names))
    fig, axes = plt.subplots(rows, cols, figsize=(3.4 * cols, 3.2 * rows), squeeze=False)
    cmap = LinearSegmentedColormap.from_list("mirsad_blue", BLUE_RAMP)
    for ax, name in zip(axes.flat, names, strict=False):
        m = report["splits"][name]["ensemble"]
        cm = np.asarray(m["confusion_matrix"], dtype=float)
        norm = cm / np.maximum(cm.sum(axis=1, keepdims=True), 1)
        ax.imshow(norm, cmap=cmap, vmin=0, vmax=1)
        ax.grid(False)
        for (i, j), v in np.ndenumerate(cm):
            r, g, b = to_rgb(cmap(norm[i, j]))
            ink = "#ffffff" if (0.2126 * r + 0.7152 * g + 0.0722 * b) < 0.5 else INK
            ax.text(j, i, f"{int(v)}\n{norm[i, j]:.0%}", ha="center", va="center", color=ink, fontsize=9)
        ax.set_xticks([0, 1], ["benign", "injection"])
        ax.set_yticks([0, 1], ["benign", "injection"])
        ax.set_xlabel("Predicted")
        ax.set_ylabel("Actual")
        ax.set_title(f"{name}  (F1 {m['f1']:.2f})")
    for ax in list(axes.flat)[len(names):]:
        ax.set_visible(False)
    fig.suptitle("Confusion matrices — ensemble at the calibrated 0.5 threshold", fontsize=11, color=INK)
    fig.tight_layout()
    return _save(fig, out / "confusion_matrices.png")


def _curve_figure(out: Path, curves_input: Mapping[str, tuple[np.ndarray, dict[str, np.ndarray]]],
                  kind: str) -> str | None:
    names = [n for n, (y, _) in curves_input.items() if len(np.unique(y)) == 2]
    if not names:
        return None
    rows, cols = _grid_shape(len(names))
    fig, axes = plt.subplots(rows, cols, figsize=(3.6 * cols, 3.3 * rows), squeeze=False)
    for ax, name in zip(axes.flat, names, strict=False):
        y, scores = curves_input[name]
        for system in SYSTEMS:
            s = scores[system]
            if kind == "roc":
                fpr, tpr, _ = roc_curve(y, s)
                area = float(auc(fpr, tpr))
                ax.plot(fpr, tpr, color=SYSTEM_COLORS[system], label=f"{SYSTEM_LABELS[system]} (AUC {area:.2f})")
            else:
                prec, rec, _ = precision_recall_curve(y, s)
                ap = float(average_precision_score(y, s))
                ax.plot(rec, prec, color=SYSTEM_COLORS[system], label=f"{SYSTEM_LABELS[system]} (AP {ap:.2f})")
        if kind == "roc":
            ax.plot([0, 1], [0, 1], color=AXIS, linewidth=1.0)
            ax.set_xlabel("False positive rate")
            ax.set_ylabel("True positive rate")
        else:
            base = float(np.mean(y))
            ax.axhline(base, color=AXIS, linewidth=1.0)
            ax.set_xlabel("Recall")
            ax.set_ylabel("Precision")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1.02)
        ax.set_title(name)
        ax.legend(loc="lower right" if kind == "roc" else "lower left")
    for ax in list(axes.flat)[len(names):]:
        ax.set_visible(False)
    title = "ROC curves by split" if kind == "roc" else "Precision–recall curves by split"
    fig.suptitle(title, fontsize=11, color=INK)
    fig.tight_layout()
    return _save(fig, out / ("roc_curves.png" if kind == "roc" else "pr_curves.png"))


def threshold_sweep_figure(out: Path, report: Mapping[str, Any]) -> str:
    sweep = report["splits"]["val"]["threshold_sweep"]
    t = [p["threshold"] for p in sweep]
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    for key, label in (("precision", "Precision"), ("recall", "Recall"), ("f1", "F1"), ("fpr", "False positive rate")):
        ax.plot(t, [p[key] for p in sweep], color=SWEEP_COLORS[key], label=label)
    cfg = report["ensemble_config"]
    for x, text in ((cfg["flag_threshold"], "flag (tuned point)"), (cfg["block_threshold"], "block")):
        ax.axvline(x, color=MUTED, linewidth=1.0)
        ax.text(x + 0.01, 0.03, text, color=INK_2, fontsize=8, rotation=90, va="bottom")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("Calibrated score threshold")
    ax.set_ylabel("Metric value")
    ax.set_title("Threshold sweep on the validation split (ensemble)")
    ax.legend(loc="center left", bbox_to_anchor=(1.0, 0.5))
    fig.tight_layout()
    return _save(fig, out / "threshold_sweep.png")


def _grouped_bars(ax: plt.Axes, groups: list[str], values: dict[str, list[float | None]]) -> None:
    x = np.arange(len(groups))
    width = 0.22
    for k, system in enumerate(SYSTEMS):
        vals = [np.nan if v is None else v for v in values[system]]
        pos = x + (k - 1) * (width + 0.03)
        ax.bar(pos, vals, width=width, color=SYSTEM_COLORS[system], label=SYSTEM_LABELS[system], zorder=2)
        if system == "ensemble":
            for xi, v in zip(pos, vals, strict=True):
                if not np.isnan(v):
                    ax.text(xi, v + 0.015, f"{v:.2f}", ha="center", va="bottom", fontsize=7.5, color=INK_2)
    ax.set_xticks(x, groups)
    ax.set_ylim(0, 1.08)
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=3)


def per_language_figure(out: Path, report: Mapping[str, Any]) -> str | None:
    """F1 per language, pooled over all test splits (validation when there is no test data)."""
    test_names = [n for n in report["splits"] if n.startswith("test_")] or ["val"]
    pooled: dict[str, dict[str, list[int]]] = {}
    for name in test_names:
        for lang, systems in report["splits"][name]["by_language"].items():
            for system in SYSTEMS:
                cm = np.asarray(systems[system]["confusion_matrix"])
                acc = pooled.setdefault(lang, {}).setdefault(system, [0, 0, 0, 0])
                tn, fp, fn, tp = int(cm[0, 0]), int(cm[0, 1]), int(cm[1, 0]), int(cm[1, 1])
                for i, v in enumerate((tn, fp, fn, tp)):
                    acc[i] += v
    if not pooled:
        return None
    langs = [lang for lang in ("en", "ar", "mixed") if lang in pooled] + sorted(set(pooled) - {"en", "ar", "mixed"})
    values: dict[str, list[float | None]] = {s: [] for s in SYSTEMS}
    for lang in langs:
        for system in SYSTEMS:
            tn, fp, fn, tp = pooled[lang][system]
            values[system].append(2 * tp / (2 * tp + fp + fn) if (tp + fp + fn) else None)
    fig, ax = plt.subplots(figsize=(6.0, 3.8))
    _grouped_bars(ax, langs, values)
    ax.set_xlabel("Language")
    ax.set_ylabel("F1 score")
    scope = "test splits" if test_names != ["val"] else "validation split"
    ax.set_title(f"F1 by language ({scope}, pooled)")
    fig.tight_layout()
    return _save(fig, out / "per_language_f1.png")


def ablation_figure(out: Path, report: Mapping[str, Any]) -> str:
    names = [n for n in report["splits"] if n != "train"]
    values = {s: [report["splits"][n][s]["f1"] for n in names] for s in SYSTEMS}
    fig, ax = plt.subplots(figsize=(max(6.0, 1.6 * len(names) + 2), 3.8))
    _grouped_bars(ax, names, values)
    ax.set_xlabel("Split")
    ax.set_ylabel("F1 score")
    ax.set_title("Ablation: ensemble vs model-only vs rules-only (val-tuned thresholds)")
    fig.tight_layout()
    return _save(fig, out / "ablation_f1.png")


def write_figures(out_dir: str | Path, report: Mapping[str, Any],
                  curves_input: Mapping[str, tuple[np.ndarray, dict[str, np.ndarray]]]) -> list[str]:
    """Write every figure; returns the file paths."""
    _style()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = [
        confusion_matrices(out, report),
        _curve_figure(out, curves_input, "roc"),
        _curve_figure(out, curves_input, "pr"),
        threshold_sweep_figure(out, report),
        per_language_figure(out, report),
        ablation_figure(out, report),
    ]
    return [p for p in paths if p]
