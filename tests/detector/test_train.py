"""Training pipeline end to end on a neutral synthetic dataset (proves the pipeline, not detection quality)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from mirsad.detector import InjectionDetector
from mirsad.detector.dataset import read_records, write_jsonl
from mirsad.detector.model import COEF_FILE, INTERCEPT_FILE, META_FILE, EnsembleConfig, LinearTextModel
from mirsad.detector.train import TrainConfig, TrainingError, main, train

from .neutral_data import SMALL_FEATURES, make_dataset, make_records

PACKAGED_MODEL_DIR = Path(__file__).resolve().parents[2] / "src" / "mirsad" / "detector" / "model"


def _packaged_state() -> dict[str, int]:
    if not PACKAGED_MODEL_DIR.is_dir():
        return {}
    return {p.name: p.stat().st_mtime_ns for p in PACKAGED_MODEL_DIR.iterdir()}


def test_model_files_are_written(trained):
    out = trained["model_dir"]
    assert sorted(p.name for p in out.iterdir()) == sorted([COEF_FILE, INTERCEPT_FILE, META_FILE])
    model = LinearTextModel.load(out)
    meta = model.meta
    assert meta.features == SMALL_FEATURES
    assert meta.training["C"] in trained["config"].c_grid
    assert meta.training["class_weight"] == "balanced"
    assert meta.training["n_train"] > meta.training["n_val"] > 0
    assert set(meta.training["test_splits"]) >= {"test_en", "test_ar", "test_mixed"}
    assert meta.training["dataset_stats_sha256"]
    assert set(meta.metrics) >= {"val", "test_en", "test_ar", "test_mixed"}


def test_metrics_report_structure(trained):
    path = trained["reports_dir"] / "detector_metrics.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    assert set(report["splits"]) >= {"train", "val", "test_en", "test_ar", "test_mixed"}
    val = report["splits"]["val"]
    for system in ("ensemble", "model_only", "rules_only", "ensemble_at_block_threshold"):
        m = val[system]
        assert {"precision", "recall", "f1", "fpr", "roc_auc", "pr_auc", "confusion_matrix"} <= set(m)
        assert sum(map(sum, m["confusion_matrix"])) == m["n"]
    assert {"by_language", "by_variety", "by_carrier", "by_difficulty", "recall_by_attack_type"} <= set(val)
    assert len(val["threshold_sweep"]) == 19
    assert set(report["latency_ms"]) == {"ensemble", "rules_only"}
    assert set(report["latency_ms"]["ensemble"]) == {"0.5KB", "2KB", "10KB"}
    assert set(report["targets"]) == {"f1_test_en_ge_0.85", "f1_test_ar_ge_0.85", "p50_2kb_lt_10ms"}
    EnsembleConfig.model_validate(report["ensemble_config"])
    assert report["selection"]["criterion"].startswith("max F1 on val")


def test_figures_are_written(trained):
    pytest.importorskip("matplotlib")
    figures = trained["report"].get("figures", [])
    names = {Path(p).name for p in figures}
    assert names == {"confusion_matrices.png", "roc_curves.png", "pr_curves.png", "threshold_sweep.png",
                     "per_language_f1.png", "ablation_f1.png"}
    for p in figures:
        assert Path(p).stat().st_size > 1000


def test_model_separates_the_placeholder_task(trained):
    # sanity check of the plumbing only: label == presence of a placeholder token
    splits = trained["report"]["splits"]
    aucs = [splits[n]["model_only"]["roc_auc"] for n in ("val", "test_en", "test_ar", "test_mixed")]
    assert all(a is not None and a >= 0.75 for a in aucs), aucs


def test_trained_detector_loads_in_ensemble_mode(trained, model_detector):
    assert model_detector.mode == "ensemble"
    assert model_detector.ensemble.model_dump() == trained["report"]["ensemble_config"]


def test_tuning_never_looks_at_test_splits(tmp_path, built_data):
    """Changing the test splits must not change the learned weights or any tuned threshold."""
    cfg = TrainConfig(latency_repeats=2, c_grid=(4.0,), figures=False, features=SMALL_FEATURES)
    copy = tmp_path / "data"
    shutil.copytree(built_data / "splits", copy / "splits")
    first = train(copy, tmp_path / "m1", None, config=cfg)
    for path in (copy / "splits").glob("test_*.jsonl"):
        recs = read_records(path)
        write_jsonl(path, [r | {"label": 1 - r["label"]} for r in recs[: len(recs) // 2]])
    second = train(copy, tmp_path / "m2", None, config=cfg)
    assert first["ensemble_config"] == second["ensemble_config"]
    np.testing.assert_array_equal(np.load(tmp_path / "m1" / COEF_FILE), np.load(tmp_path / "m2" / COEF_FILE))
    assert first["splits"]["test_en"]["ensemble"] != second["splits"]["test_en"]["ensemble"]


def test_training_errors(tmp_path):
    with pytest.raises(TrainingError, match="build_dataset"):
        train(tmp_path, tmp_path / "out")
    splits = tmp_path / "splits"
    one_class = [r for r in make_records("oc", 20, lang="en", seed=1) if r["label"] == 0]
    write_jsonl(splits / "train.jsonl", one_class)
    write_jsonl(splits / "val.jsonl", one_class)
    with pytest.raises(TrainingError, match="both benign"):
        train(tmp_path, tmp_path / "out")
    write_jsonl(splits / "train.jsonl", make_records("tr", 20, lang="en", seed=2))
    with pytest.raises(TrainingError, match="val split needs both classes"):
        train(tmp_path, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_cli_main_builds_and_trains(tmp_path, capsys):
    data = make_dataset(tmp_path / "data", seed=5, train_per_lang=30, test_per_lang=8)
    args = ["--data", str(data), "--out", str(tmp_path / "model"), "--reports", str(tmp_path / "reports"),
            "--build", "--no-figures", "--latency-repeats", "2", "--c-grid", "2"]
    assert main(args) == 0
    out = capsys.readouterr().out
    assert "latency p50 ms" in out and "test_ar" in out
    assert InjectionDetector(tmp_path / "model").mode == "ensemble"
    assert (tmp_path / "reports" / "detector_metrics.json").is_file()


def test_cli_main_reports_training_failure(tmp_path, capsys):
    assert main(["--data", str(tmp_path), "--out", str(tmp_path / "model"), "--reports", str(tmp_path / "r"),
                 "--no-figures"]) == 2
    assert "training failed" in capsys.readouterr().err


@pytest.mark.slow
def test_python_dash_m_entry_points(tmp_path):
    """``python -m mirsad.detector.build_dataset`` and ``... .train`` run end to end in a scratch dir."""
    data = make_dataset(tmp_path / "data", seed=9, train_per_lang=30, test_per_lang=8)
    before = _packaged_state()
    env_cmd = [sys.executable, "-m"]
    build = subprocess.run([*env_cmd, "mirsad.detector.build_dataset", "--data", str(data)],
                           cwd=tmp_path, capture_output=True, text=True, timeout=300)
    assert build.returncode == 0, build.stderr
    assert "leakage check: OK" in build.stdout
    result = subprocess.run(
        [*env_cmd, "mirsad.detector.train", "--data", str(data), "--out", str(tmp_path / "model"),
         "--reports", str(tmp_path / "reports"), "--no-figures", "--latency-repeats", "2", "--c-grid", "2"],
        cwd=tmp_path, capture_output=True, text=True, timeout=600,
    )
    assert result.returncode == 0, result.stderr
    assert "latency p50 ms" in result.stdout
    assert LinearTextModel.files_present(tmp_path / "model")
    assert _packaged_state() == before, "tests must never write the shipped model directory"
