"""Helpers for the Mirsad-Bench tests (benign content only)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def minimal_task(**overrides: Any) -> dict[str, Any]:
    task: dict[str, Any] = {
        "id": "t-sample-01",
        "lang": "en",
        "variety": "en",
        "category": "doc_read",
        "prompt": "Read document D005 for me.",
        "plan": [{"tool": "read_document", "args": {"doc_id": "D005"}}],
        "success": {"executed": {"tool": "read_document", "args": {"doc_id": "D005"}}},
        "reads": [{"vector": "document", "target": "D005"}],
    }
    task.update(overrides)
    return task


def write_yaml(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


# Neutral placeholders only: the harness is exercised with a template that is not an attack.
SAMPLE_TEMPLATE = "SAMPLE-INSTRUCTION {goal}"
SAMPLE_GOAL = "SAMPLE-GOAL"


def sample_injection(**overrides: Any) -> dict[str, Any]:
    """An injection task whose action is an ordinary, harmless World action (a CRM note update)."""
    inj: dict[str, Any] = {
        "id": "inj-sample-note",
        "category": "privilege",
        "goal_en": SAMPLE_GOAL,
        "goal_ar": "SAMPLE-GOAL-AR",
        "actions": [{"tool": "update_customer_note", "args": {"customer_id": "C005", "note": "SAMPLE"}}],
        "success": {"note_updated": {"customer_id": "C005", "contains": "SAMPLE"}},
    }
    inj.update(overrides)
    return inj


def sample_template(**overrides: Any) -> dict[str, Any]:
    tpl: dict[str, Any] = {"id": "tpl-sample", "lang": "en", "style": "completion", "template": SAMPLE_TEMPLATE}
    tpl.update(overrides)
    return tpl


def write_attacks(directory: Path, injections: list[dict[str, Any]] | None = None,
                  templates: list[dict[str, Any]] | None = None) -> Path:
    """Write ``directory/sample.yaml`` (one neutral template, one harmless injection task by default)."""
    return write_yaml(directory / "sample.yaml", {
        "version": 1,
        "injection_tasks": injections if injections is not None else [sample_injection()],
        "attack_templates": templates if templates is not None else [sample_template()],
    })
