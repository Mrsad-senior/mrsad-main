"""Shared fixtures for the detector tests.

Every dataset and model used here is built in a temporary directory from neutral synthetic records
(see ``neutral_data.py``): the "positive" class is defined by a placeholder token, so the pipeline is
exercised end to end without any adversarial text. Rule matching on real content is covered by the
rule files' own ``examples`` / ``negatives`` maintained by the human team.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mirsad.detector import InjectionDetector, Rule, RuleSet
from mirsad.detector.build_dataset import BuildConfig, build_dataset
from mirsad.detector.train import TrainConfig, train

from .neutral_data import PLACEHOLDER, SMALL_FEATURES, make_dataset


@pytest.fixture(scope="session")
def rules() -> RuleSet:
    return RuleSet.default()


@pytest.fixture(scope="session")
def rules_detector() -> InjectionDetector:
    """Detector with no model directory: rules-only fallback mode with the packaged rule base."""
    return InjectionDetector(None)


@pytest.fixture(scope="session")
def placeholder_rules() -> RuleSet:
    """A stub rule base with one neutral rule that matches the placeholder token only."""
    rule = Rule(id="test.placeholder", category="goal_hijack", weight=0.9, lang="any",
                description="test stub: matches the neutral placeholder token",
                pattern=PLACEHOLDER.lower(), examples=(PLACEHOLDER,))
    return RuleSet([rule])


@pytest.fixture(scope="session")
def placeholder_detector(placeholder_rules: RuleSet) -> InjectionDetector:
    return InjectionDetector(None, rules=placeholder_rules)


@pytest.fixture(scope="session")
def built_data(tmp_path_factory: pytest.TempPathFactory) -> Path:
    data = make_dataset(tmp_path_factory.mktemp("data"), seed=3, train_per_lang=60, test_per_lang=12)
    build_dataset(data, config=BuildConfig(seed=7))
    return data


@pytest.fixture(scope="session")
def trained(tmp_path_factory: pytest.TempPathFactory, built_data: Path) -> dict:
    out = tmp_path_factory.mktemp("model")
    reports = tmp_path_factory.mktemp("reports")
    cfg = TrainConfig(latency_repeats=5, c_grid=(4.0, 16.0), features=SMALL_FEATURES)
    report = train(built_data, out, reports, config=cfg)
    return {"model_dir": out, "reports_dir": reports, "report": report, "config": cfg}


@pytest.fixture(scope="session")
def model_detector(trained: dict) -> InjectionDetector:
    return InjectionDetector(trained["model_dir"])
