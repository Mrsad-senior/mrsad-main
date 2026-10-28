"""Scenario schema + loader validation."""

from __future__ import annotations

import pytest
from bench.loader import (
    ATTACKS_DIR,
    ScenarioError,
    load_suite,
    schema_errors,
    semantic_errors,
    tool_arg_errors,
)
from bench_helpers import minimal_task, write_yaml


def test_suite_has_enough_benign_tasks_in_both_languages(suite):
    en = [t for t in suite.user_tasks if t.lang == "en"]
    ar = [t for t in suite.user_tasks if t.lang == "ar"]
    assert len(en) >= 20 and len(ar) >= 20
    assert {t.variety for t in ar} == {"msa", "gulf"}
    for lang_tasks in (en, ar):
        assert sum(t.expect_approval for t in lang_tasks) >= 2


def test_every_category_is_covered(suite):
    cats = {t.category for t in suite.user_tasks}
    assert cats == {"email_read", "crm_lookup", "internal_reply", "external_reply", "web_read", "doc_read",
                    "crm_update", "export", "approval_required"}


def test_all_plans_are_valid_tool_calls(suite):
    for task in suite.user_tasks:
        for step in task.plan:
            assert tool_arg_errors(step) == [], (task.id, step)


def test_fixture_sets_are_expanded(suite):
    task = suite.task("en-external-reply-02")
    assert [e["id"] for e in task.fixtures.emails] == ["E101", "E104"]


def test_schema_rejects_missing_and_unknown_fields():
    bad = minimal_task()
    del bad["plan"]
    bad["colour"] = "blue"
    errors = schema_errors({"version": 1, "user_tasks": [bad]})
    assert any("plan" in e for e in errors)
    assert any("colour" in e for e in errors)


def test_schema_rejects_bad_predicate_operator():
    task = minimal_task(success={"sent_somewhere": "x"})
    assert schema_errors({"version": 1, "user_tasks": [task]})
    two_ops = minimal_task(success={"deleted": "C001", "fetched": "https://a.example/x"})
    assert schema_errors({"version": 1, "user_tasks": [two_ops]})


def test_bad_tool_arguments_are_reported():
    assert tool_arg_errors({"tool": "read_email", "args": {}})  # missing email_id
    assert tool_arg_errors({"tool": "list_emails", "args": {"limit": 500}})  # above maximum
    assert tool_arg_errors({"tool": "read_email", "args": {"email_id": "E001", "extra": 1}})
    assert tool_arg_errors({"tool": "no_such_tool", "args": {}}) == ["unknown tool 'no_such_tool'"]


def test_read_target_must_exist_and_be_read_by_plan():
    unread = minimal_task(reads=[{"vector": "email", "target": "E006"}])
    errs = semantic_errors({"version": 1, "user_tasks": [unread]}, kind="tasks")
    assert any("never read by the plan" in e for e in errs)
    missing = minimal_task(reads=[{"vector": "document", "target": "D999"}])
    errs = semantic_errors({"version": 1, "user_tasks": [missing]}, kind="tasks")
    assert any("does not exist" in e for e in errs)


def test_fixture_ids_must_not_collide_with_seed_world():
    task = minimal_task(fixtures={"emails": [{"id": "E001", "from": "a@b.example", "to": "c@najd-trading.example",
                                              "subject": "Hello", "body": "Ordinary text."}]})
    errs = semantic_errors({"version": 1, "user_tasks": [task]}, kind="tasks")
    assert any("collides" in e for e in errs)


def test_variety_must_match_language():
    errs = semantic_errors({"version": 1, "user_tasks": [minimal_task(variety="gulf")]}, kind="tasks")
    assert any("variety" in e for e in errs)


def test_loader_reports_all_errors_and_duplicate_ids(tmp_path):
    write_yaml(tmp_path / "a.yaml", {"version": 1, "user_tasks": [minimal_task()]})
    write_yaml(tmp_path / "b.yaml", {"version": 1, "user_tasks": [minimal_task()]})
    with pytest.raises(ScenarioError) as exc:
        load_suite(tmp_path)
    assert any("duplicate user task id" in e for e in exc.value.errors)


def test_attack_lists_rejected_in_task_files(tmp_path):
    write_yaml(tmp_path / "a.yaml", {"version": 1, "user_tasks": [minimal_task()],
                                     "attack_templates": [{"id": "tpl-1", "lang": "en", "style": "completion",
                                                           "template": "SAMPLE-FLAGGED-TEXT {goal}"}]})
    with pytest.raises(ScenarioError) as exc:
        load_suite(tmp_path)
    assert any("only allowed in bench/scenarios/attacks" in e for e in exc.value.errors)


def test_repository_attacks_folder_holds_no_attack_files(suite):
    assert ATTACKS_DIR.is_dir()
    assert list(ATTACKS_DIR.glob("*.yaml")) == [] and list(ATTACKS_DIR.glob("*.yml")) == []
    assert not suite.has_attacks and suite.injection_tasks == [] and suite.attack_templates == []


def test_attack_files_are_validated_with_neutral_placeholders(tmp_path):
    write_yaml(tmp_path / "tasks.yaml", {"version": 1, "user_tasks": [minimal_task()]})
    stub = {
        "version": 1,
        "injection_tasks": [{
            "id": "inj-stub-01", "category": "privilege", "goal": "SAMPLE-GOAL",
            "actions": [{"tool": "update_customer_note", "args": {"customer_id": "C005", "note": "SAMPLE-MARKER"}}],
            "success": {"note_updated": {"customer_id": "C005", "contains": "SAMPLE-MARKER"}},
        }],
        "attack_templates": [{"id": "tpl-stub-01", "lang": "en", "style": "completion",
                              "template": "SAMPLE-FLAGGED-TEXT {goal}"}],
    }
    write_yaml(tmp_path / "attacks" / "stub.yaml", stub)
    loaded = load_suite(tmp_path)
    assert loaded.has_attacks and len(loaded.injection_tasks) == 1

    stub["attack_templates"][0]["template"] = "SAMPLE-FLAGGED-TEXT without a placeholder"
    write_yaml(tmp_path / "attacks" / "stub.yaml", stub)
    with pytest.raises(ScenarioError):
        load_suite(tmp_path)


def test_user_tasks_rejected_in_attack_files(tmp_path):
    write_yaml(tmp_path / "attacks" / "x.yaml", {"version": 1, "user_tasks": [minimal_task()]})
    with pytest.raises(ScenarioError) as exc:
        load_suite(tmp_path)
    assert any("not allowed in attack files" in e for e in exc.value.errors)


def test_select_filters(suite):
    assert all(t.lang == "ar" for t in suite.select(lang="ar"))
    assert len(suite.select(limit=3)) == 3
    assert [t.id for t in suite.select(ids=["ar-export-01"])] == ["ar-export-01"]
    with pytest.raises(KeyError):
        suite.select(ids=["missing-task"])
