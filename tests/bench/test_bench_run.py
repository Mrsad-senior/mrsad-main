"""Runner (resumable outputs), comparison report and a small latency run."""

from __future__ import annotations

import json

import httpx
import pytest
from bench.run import main as run_main
from bench.run import read_episodes

from bench import compare, latency


def test_runner_writes_outputs_and_resumes(tmp_path):
    out = tmp_path / "run1"
    args = ["--agent", "scripted", "--defense", "none,policy_only", "--approver", "oracle",
            "--tasks", "en-doc-read-01,ar-export-01", "--out", str(out), "--no-figures", "--replay-check"]
    assert run_main(args) == 0
    eps = read_episodes(out / "episodes.jsonl")
    assert len(eps) == 4
    assert {e["defense"] for e in eps} == {"none", "policy_only"}
    summary = json.loads((out / "summary.json").read_text())
    assert summary["episodes"] == 4 and summary["attack_episodes"] == 0
    assert summary["meta"]["audit_checks"][0]["replay"]["matched"] == 2
    assert "Benign results per configuration" in (out / "summary.md").read_text()

    assert run_main(args) == 0  # resume: nothing new to run
    assert len(read_episodes(out / "episodes.jsonl")) == 4


def test_runner_tolerates_a_torn_last_line(tmp_path):
    path = tmp_path / "episodes.jsonl"
    path.write_text('{"key": "a"}\n{"key": ', encoding="utf-8")
    assert read_episodes(path) == [{"key": "a"}]


def test_runner_figures(tmp_path):
    out = tmp_path / "run2"
    assert run_main(["--defense", "none,taint_only", "--approver", "deny", "--lang", "ar", "--limit", "2",
                     "--out", str(out)]) == 0
    assert (out / "figures" / "benign_by_defense.png").stat().st_size > 1000


def test_compare_renders_rows(tmp_path):
    out = tmp_path / "run3"
    run_main(["--defense", "none,full", "--approver", "deny", "--tasks", "en-web-read-01", "--out", str(out),
              "--no-figures"])
    rows = compare.comparison_rows([compare.load_summary(out)])
    assert [r["defense"] for r in rows] == ["none", "full"]
    text = compare.render(rows)
    assert "| run3 | scripted | full | deny |" in text and "ASR is not reported" in text
    assert compare.main([str(out), "--out", str(tmp_path / "cmp.md")]) == 0
    with pytest.raises(FileNotFoundError):
        compare.load_summary(tmp_path / "missing")


@pytest.mark.slow
def test_latency_benchmark_small(tmp_path):
    result = latency.run_latency(calls=20, sessions=4, warmup=2)
    assert result["sequential"]["http_errors"] == 0 and result["concurrent"]["http_errors"] == 0
    assert result["sequential"]["non_allow"] == 0  # benign read-only traffic is never blocked
    assert result["sequential"]["added_ms"]["n"] == 20 and result["concurrent"]["http_ms"]["n"] == 20
    assert result["audit_chain_ok"] is True
    latency.write_figure(result, tmp_path / "lat.png")
    assert (tmp_path / "lat.png").exists()


def test_latency_server_rejects_missing_agent_key(tmp_path):
    with latency.GatewayServer(tmp_path) as srv:
        resp = httpx.post(f"{srv.base_url}/v1/tools/list_emails/invoke", json={"session_id": "s", "arguments": {}})
        assert resp.status_code == 401
