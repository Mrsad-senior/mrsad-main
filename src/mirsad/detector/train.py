"""Train, tune and evaluate the detector model.

    python -m mirsad.detector.train --data data/detector --out src/mirsad/detector/model --reports reports

1. fit a class-balanced logistic regression on ``train`` (hashed char 2-5 + word 1-2 n-grams of the
   normalised text), choosing C by validation PR-AUC;
2. on ``val`` only, tune the noisy-OR exponents (alpha, beta) and the decision threshold to maximise F1
   subject to FPR <= 5 %; the same criterion picks the model-only and rules-only thresholds used in
   the ablation (test splits are never used for any choice);
3. evaluate every split (per language, variety and attack type), sweep thresholds, measure scan latency
   for 0.5 / 2 / 10 KB texts, and write ``coef.npy`` / ``intercept.npy`` / ``meta.json`` (no pickle),
   ``reports/detector_metrics.json`` and figures under ``reports/figures/``.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import logging
import sys
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import sklearn
from sklearn.linear_model import LogisticRegression

from mirsad.detector.dataset import read_records
from mirsad.detector.detector import InjectionDetector
from mirsad.detector.metrics import classification_metrics, percentile_ms, select_threshold, threshold_sweep
from mirsad.detector.model import (
    EnsembleConfig,
    FeatureConfig,
    LinearTextModel,
    ModelMeta,
    TextFeaturizer,
    calibrate_array,
)
from mirsad.detector.normalize import normalize
from mirsad.detector.rules import RuleSet, rule_score

log = logging.getLogger("mirsad.detector")

SYSTEMS = ("ensemble", "model_only", "rules_only")
LATENCY_SIZES = {"0.5KB": 512, "2KB": 2048, "10KB": 10240}


class TrainingError(RuntimeError):
    """The data cannot support training (missing splits, a single class, ...)."""


@dataclass
class TrainConfig:
    seed: int = 1337
    c_grid: tuple[float, ...] = (0.5, 2.0, 8.0)
    exponent_grid: tuple[float, ...] = (0.5, 0.75, 1.0, 1.5, 2.0)
    max_fpr: float = 0.05
    window_chars: int = 600
    stride_chars: int = 300
    figures: bool = True
    latency_repeats: int = 50
    features: FeatureConfig = field(default_factory=FeatureConfig)


@dataclass
class _Split:
    name: str
    records: list[dict[str, Any]]
    norm: list[str]
    rules: np.ndarray
    model: np.ndarray | None = None

    @property
    def y(self) -> np.ndarray:
        return np.asarray([int(r["label"]) for r in self.records], dtype=int)


def _prepare(name: str, records: list[dict[str, Any]], rules: RuleSet) -> _Split:
    norms: list[str] = []
    scores: list[float] = []
    for rec in records:
        n = normalize(rec["text"])
        norms.append(n.text)
        scores.append(rule_score(rules.match(n), n.signals))
    return _Split(name, records, norms, np.asarray(scores, dtype=float))


def _raw_ensemble(m: np.ndarray, r: np.ndarray, alpha: float, beta: float) -> np.ndarray:
    return 1.0 - np.power(1.0 - np.clip(m, 0, 1), alpha) * np.power(1.0 - np.clip(r, 0, 1), beta)


def _fit(X: Any, y: np.ndarray, C: float, seed: int) -> tuple[np.ndarray, float]:
    clf = LogisticRegression(C=C, class_weight="balanced", solver="liblinear", max_iter=5000, random_state=seed)
    clf.fit(X, y)
    return clf.coef_.ravel().astype(np.float32), float(clf.intercept_[0])


def _scores(split: _Split, ens: EnsembleConfig) -> dict[str, np.ndarray]:
    assert split.model is not None
    raw = _raw_ensemble(split.model, split.rules, ens.alpha, ens.beta)
    return {"ensemble": calibrate_array(raw, ens.pivot), "model_only": split.model, "rules_only": split.rules}


def _evaluate(split: _Split, ens: EnsembleConfig) -> dict[str, Any]:
    y = split.y
    scores = _scores(split, ens)
    thresholds = {"ensemble": ens.flag_threshold, "model_only": ens.model_threshold, "rules_only": ens.rules_threshold}
    out: dict[str, Any] = {name: classification_metrics(y, scores[name], thresholds[name]) for name in SYSTEMS}
    out["ensemble_at_block_threshold"] = classification_metrics(y, scores["ensemble"], ens.block_threshold)
    out["rules_only_fallback"] = classification_metrics(y, split.rules, 0.5)  # what rules-only mode does in production
    out["threshold_sweep"] = threshold_sweep(y, scores["ensemble"])
    for key, field_name in (("by_language", "lang"), ("by_variety", "variety"), ("by_carrier", "carrier"),
                            ("by_difficulty", "difficulty")):
        groups: dict[str, list[int]] = defaultdict(list)
        for i, rec in enumerate(split.records):
            groups[str(rec.get(field_name, "?"))].append(i)
        out[key] = {
            g: {name: classification_metrics(y[idx], scores[name][idx], thresholds[name]) for name in SYSTEMS}
            for g, idx in sorted(groups.items())
        }
    by_attack: dict[str, list[int]] = defaultdict(list)
    for i, rec in enumerate(split.records):
        if int(rec["label"]) == 1:
            by_attack[str(rec.get("attack_type", "?"))].append(i)
    out["recall_by_attack_type"] = {
        a: {name: float(np.mean(scores[name][idx] >= thresholds[name])) for name in SYSTEMS} | {"n": len(idx)}
        for a, idx in sorted(by_attack.items())
    }
    return out


def _tune_ensemble(val: _Split, cfg: TrainConfig) -> tuple[EnsembleConfig, dict[str, Any]]:
    assert val.model is not None
    y = val.y
    candidates = []
    for alpha, beta in itertools.product(cfg.exponent_grid, cfg.exponent_grid):
        raw = _raw_ensemble(val.model, val.rules, alpha, beta)
        sel = select_threshold(y, raw, max_fpr=cfg.max_fpr)
        dist = abs(np.log(alpha)) + abs(np.log(beta))
        candidates.append(((sel["constraint_met"], round(sel["f1"], 6), -dist, sel["threshold"]), alpha, beta, sel))
    candidates.sort(key=lambda c: c[0], reverse=True)
    _, alpha, beta, sel = candidates[0]
    model_sel = select_threshold(y, val.model, max_fpr=cfg.max_fpr)
    rules_sel = select_threshold(y, val.rules, max_fpr=cfg.max_fpr)
    ens = EnsembleConfig(alpha=alpha, beta=beta, pivot=float(np.clip(sel["threshold"], 0.01, 0.99)),
                         model_threshold=float(np.clip(model_sel["threshold"], 0.01, 0.99)),
                         rules_threshold=float(np.clip(rules_sel["threshold"], 0.01, 0.99)))
    info = {
        "criterion": f"max F1 on val subject to FPR <= {cfg.max_fpr}",
        "ensemble": {"alpha": alpha, "beta": beta, **sel},
        "ensemble_top5": [{"alpha": a, "beta": b, **s} for _, a, b, s in candidates[:5]],
        "model_only": model_sel,
        "rules_only": rules_sel,
    }
    return ens, info


def _latency_texts(splits: list[_Split]) -> dict[str, str]:
    benign = [r["text"] for s in splits for r in s.records if int(r["label"]) == 0]
    corpus = "\n\n".join(benign) if benign else ""
    if len(corpus) < 10240:
        filler = ("Dear team, please find attached the quarterly report for Najd Trading Co. The shipment of "
                  "dates arrives on Sunday. فريق المبيعات يرحب بكم ويشكركم على التعاون المستمر. ")
        corpus = (corpus + "\n\n" + filler * (10240 // len(filler) + 2)).strip()
    return {label: corpus[:size] for label, size in LATENCY_SIZES.items()}


def measure_latency(detector: InjectionDetector, texts: dict[str, str], repeats: int) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for label, text in texts.items():
        n = repeats if len(text) <= 2048 else max(10, repeats // 3)
        for _ in range(3):
            detector.scan(text)
        samples = []
        for _ in range(n):
            t0 = time.perf_counter()
            detector.scan(text)
            samples.append((time.perf_counter() - t0) * 1000.0)
        out[label] = {"chars": len(text), "n": n, "p50": percentile_ms(samples, 50), "p95": percentile_ms(samples, 95),
                      "mean": float(np.mean(samples))}
    return out


def _sha256_file(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def train(data_dir: str | Path, out_dir: str | Path, reports_dir: str | Path | None = None, *,
          config: TrainConfig | None = None) -> dict[str, Any]:
    """Run the full training / tuning / evaluation pipeline and return the metrics report."""
    cfg = config or TrainConfig()
    data_dir, out_dir = Path(data_dir), Path(out_dir)
    splits_dir = data_dir / "splits"
    if not (splits_dir / "train.jsonl").exists():
        raise TrainingError(f"{splits_dir}/train.jsonl not found - run python -m mirsad.detector.build_dataset first")
    rules = RuleSet.default()
    started = time.time()

    train_split = _prepare("train", read_records(splits_dir / "train.jsonl"), rules)
    y_train = train_split.y
    if len(set(y_train.tolist())) < 2:
        raise TrainingError("train split needs both benign (0) and injection (1) examples")
    val_split = _prepare("val", read_records(splits_dir / "val.jsonl"), rules)
    if len(set(val_split.y.tolist())) < 2:
        raise TrainingError("val split needs both classes to tune thresholds - add data or lower --val-fraction")
    test_splits = [
        _prepare(p.stem, recs, rules)
        for p in sorted(splits_dir.glob("test_*.jsonl"))
        if (recs := read_records(p))
    ]
    log.info("train=%d val=%d tests=%s", len(train_split.records), len(val_split.records),
             {s.name: len(s.records) for s in test_splits})

    featurizer = TextFeaturizer(cfg.features)
    X_train = featurizer.transform(train_split.norm)
    c_search = []
    best: tuple[float, float, np.ndarray, float] | None = None
    for C in cfg.c_grid:
        coef, intercept = _fit(X_train, y_train, C, cfg.seed)
        model = LinearTextModel(coef, intercept, ModelMeta(features=cfg.features))
        m_val, _ = model.score_windows(val_split.norm, window_chars=cfg.window_chars, stride_chars=cfg.stride_chars)
        ap = classification_metrics(val_split.y, m_val, 0.5)["pr_auc"] or 0.0
        c_search.append({"C": C, "val_pr_auc": ap})
        if best is None or ap > best[0] + 1e-9:
            best = (ap, C, coef, intercept)
    assert best is not None
    _, best_c, coef, intercept = best

    model = LinearTextModel(coef, intercept, ModelMeta(features=cfg.features))
    for split in (train_split, val_split, *test_splits):
        split.model, _ = model.score_windows(split.norm, window_chars=cfg.window_chars, stride_chars=cfg.stride_chars)
    ensemble, selection = _tune_ensemble(val_split, cfg)
    selection["C"] = best_c
    selection["c_search"] = c_search

    evaluations = {s.name: _evaluate(s, ensemble) for s in (val_split, *test_splits)}
    evaluations["train"] = {name: m for name, m in _evaluate(train_split, ensemble).items() if name in SYSTEMS}

    stats_path = splits_dir / "stats.json"
    meta = ModelMeta(
        features=cfg.features,
        ensemble=ensemble,
        training={
            "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "data_dir": str(data_dir),
            "seed": cfg.seed,
            "C": best_c,
            "solver": "liblinear",
            "class_weight": "balanced",
            "window_chars": cfg.window_chars,
            "stride_chars": cfg.stride_chars,
            "n_train": len(train_split.records),
            "n_val": len(val_split.records),
            "train_labels": {str(k): int(v) for k, v in zip(*np.unique(y_train, return_counts=True), strict=True)},
            "test_splits": {s.name: len(s.records) for s in test_splits},
            "rules": len(rules),
            "dataset_stats_sha256": _sha256_file(stats_path),
            "sklearn_version": sklearn.__version__,
            "numpy_version": np.__version__,
        },
        metrics={
            name: {
                "f1": ev["ensemble"]["f1"], "precision": ev["ensemble"]["precision"],
                "recall": ev["ensemble"]["recall"], "fpr": ev["ensemble"]["fpr"], "roc_auc": ev["ensemble"]["roc_auc"],
                "f1_model_only": ev["model_only"]["f1"], "f1_rules_only": ev["rules_only"]["f1"], "n": ev["ensemble"]["n"],
            }
            for name, ev in evaluations.items() if name != "train"
        },
    )
    final = LinearTextModel(coef, intercept, meta)
    final.save(out_dir)
    log.info("model saved to %s", out_dir)

    detector = InjectionDetector(out_dir, window_chars=cfg.window_chars, stride_chars=cfg.stride_chars)
    texts = _latency_texts([val_split, *test_splits, train_split])
    latency = {"ensemble": measure_latency(detector, texts, cfg.latency_repeats),
               "rules_only": measure_latency(InjectionDetector(None), texts, cfg.latency_repeats)}

    def f1_for(lang_split: str) -> float | None:
        ev = evaluations.get(lang_split)
        return ev["ensemble"]["f1"] if ev else None

    report: dict[str, Any] = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duration_s": round(time.time() - started, 2),
        "data_dir": str(data_dir),
        "model_dir": str(out_dir),
        "config": {k: v for k, v in asdict(cfg).items() if k != "features"} | {"features": cfg.features.model_dump()},
        "dataset": {"splits": {s.name: len(s.records) for s in (train_split, val_split, *test_splits)},
                    "stats_file": str(stats_path) if stats_path.exists() else None},
        "selection": selection,
        "ensemble_config": ensemble.model_dump(),
        "splits": evaluations,
        "latency_ms": latency,
        "targets": {
            "f1_test_en_ge_0.85": None if f1_for("test_en") is None else f1_for("test_en") >= 0.85,
            "f1_test_ar_ge_0.85": None if f1_for("test_ar") is None else f1_for("test_ar") >= 0.85,
            "p50_2kb_lt_10ms": latency["ensemble"]["2KB"]["p50"] < 10.0,
        },
        "notes": [
            "All thresholds and the ensemble combination were chosen on the validation split only.",
            "Scores are calibrated so the tuned operating point maps to 0.5 (flag) and 0.8 is the block threshold.",
        ],
    }
    if reports_dir is not None:
        reports_dir = Path(reports_dir)
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "detector_metrics.json").write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                                           encoding="utf-8")
        if cfg.figures:
            try:
                from mirsad.detector.figures import write_figures
            except ImportError as exc:  # matplotlib is a dev dependency
                log.warning("figures skipped (%s)", exc)
            else:
                curves_input = {s.name: (s.y, _scores(s, ensemble)) for s in (val_split, *test_splits)}
                report["figures"] = write_figures(reports_dir / "figures", report, curves_input)
                (reports_dir / "detector_metrics.json").write_text(
                    json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m mirsad.detector.train", description=__doc__.split("\n")[0])
    parser.add_argument("--data", default="data/detector")
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent / "model"))
    parser.add_argument("--reports", default="reports")
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--c-grid", default="0.5,2,8", help="comma-separated inverse regularisation strengths")
    parser.add_argument("--max-fpr", type=float, default=0.05)
    parser.add_argument("--no-figures", action="store_true")
    parser.add_argument("--latency-repeats", type=int, default=50)
    parser.add_argument("--build", action="store_true", help="run build_dataset first")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if args.build:
        from mirsad.detector.build_dataset import build_dataset

        build_dataset(args.data)
    cfg = TrainConfig(seed=args.seed, c_grid=tuple(float(c) for c in args.c_grid.split(",") if c.strip()),
                      max_fpr=args.max_fpr, figures=not args.no_figures, latency_repeats=args.latency_repeats)
    try:
        report = train(args.data, args.out, args.reports, config=cfg)
    except TrainingError as exc:
        print(f"training failed: {exc}", file=sys.stderr)
        return 2
    sel = report["selection"]
    print(f"C={sel['C']}  alpha={sel['ensemble']['alpha']}  beta={sel['ensemble']['beta']}  "
          f"pivot={report['ensemble_config']['pivot']:.3f}")
    for name, ev in report["splits"].items():
        e = ev["ensemble"]
        auc = f"{e['roc_auc']:.3f}" if e.get("roc_auc") is not None else "n/a"
        print(f"  {name:<22} n={e['n']:<6} F1={e['f1']:.3f}  P={e['precision']:.3f}  R={e['recall']:.3f}  "
              f"FPR={e['fpr']:.3f}  AUC={auc}  | rules F1={ev['rules_only']['f1']:.3f}  model F1={ev['model_only']['f1']:.3f}")
    lat = report["latency_ms"]["ensemble"]
    print("latency p50 ms: " + "  ".join(f"{k}={v['p50']:.2f}" for k, v in lat.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
