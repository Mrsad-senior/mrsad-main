"""Scripted plan execution and benign episode utility through the real gateway."""

from __future__ import annotations

import pytest
from bench.agents import ScriptedAgent
from bench.defenses import DefenseRuntime
from bench.run import run_episode


@pytest.fixture
def agent():
    return ScriptedAgent()


async def test_undefended_baseline_completes_every_benign_task(suite, agent, tmp_path):
    runtime = DefenseRuntime("none", "deny", workdir=tmp_path)
    for task in suite.user_tasks:
        rec = await run_episode(task, agent, runtime)
        assert rec["utility"], task.id
        assert rec["n_calls"] == len(task.plan)
        assert all(c["executed"] and not c["tool_error"] for c in rec["calls"]), task.id
        assert rec["approver"] == "none" and rec["defense"] == "none"


async def test_internal_reply_passes_full_defense_without_friction(suite, agent, tmp_path):
    runtime = DefenseRuntime("full", "deny", workdir=tmp_path)
    rec = await run_episode(suite.task("en-internal-reply-01"), agent, runtime)
    assert rec["utility"]
    assert [c["final_action"] for c in rec["calls"]] == ["allow", "allow"]
    assert not any(c["escalated"] for c in rec["calls"])
    read = rec["calls"][0]
    assert read["inspection_action"] in ("pass", "flag") and read["gateway_ms"] > 0
    assert runtime.verify_audit()["ok"] is True


async def test_external_vendor_reply_needs_a_human(suite, agent, tmp_path):
    task = suite.task("en-external-reply-01")
    oracle = await run_episode(task, agent, DefenseRuntime("full", "oracle", workdir=tmp_path))
    denied = await run_episode(task, agent, DefenseRuntime("full", "deny", workdir=tmp_path))
    send_ok, send_denied = oracle["calls"][1], denied["calls"][1]
    assert send_ok["escalated"] and send_ok["approval_status"] == "approved" and send_ok["executed"]
    assert oracle["utility"] is True
    assert send_denied["escalated"] and send_denied["final_action"] == "deny" and not send_denied["executed"]
    assert denied["utility"] is False


async def test_legitimate_approval_tasks_are_escalated_and_oracle_approves(suite, agent, tmp_path):
    runtime = DefenseRuntime("full", "oracle", workdir=tmp_path)
    for task_id in ("en-approval-transfer-01", "ar-approval-delete-01"):
        rec = await run_episode(suite.task(task_id), agent, runtime)
        assert rec["expect_approval"] and rec["utility"], task_id
        assert any(c["escalated"] for c in rec["calls"]), task_id
    assert runtime.approver.approved >= 2 and runtime.approver.denied == 0
    replay = runtime.replay_check()
    assert replay["checked"] >= 3 and replay["matched"] == replay["checked"]


async def test_scripted_agent_continues_after_a_blocked_step(suite, agent, tmp_path):
    rec = await run_episode(suite.task("ar-approval-delete-01"), agent,
                            DefenseRuntime("full", "deny", workdir=tmp_path))
    assert rec["n_calls"] == 2 and rec["utility"] is False
    assert rec["calls"][0]["executed"] and not rec["calls"][1]["executed"]
