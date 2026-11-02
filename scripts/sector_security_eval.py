"""Repeatable bilingual security evaluation with and without Mirsad.

This is an authorization-stage evaluation: every case contains a trusted original
user task and the tool call the agent proposes next.  The unprotected baseline
allows the proposed call; the protected run sends it through the real Gateway.

The final holdout file is deliberately separate from unit/regression tests.  Freeze
it before the final run and do not tune rules or thresholds from its results.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import tempfile
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from mirsad.approvals import ApprovalService, Notifier  # noqa: E402
from mirsad.audit import AuditLog  # noqa: E402
from mirsad.detector import InjectionDetector  # noqa: E402
from mirsad.gateway import Gateway  # noqa: E402
from mirsad.models import ToolCall  # noqa: E402
from mirsad.policy import PolicyEngine  # noqa: E402
from mirsad.security import OllamaIntentJudge, SecurityMonitor  # noqa: E402
from mirsad.storage import Database  # noqa: E402
from mirsad.taint import TaintTracker  # noqa: E402

DEFAULT_CASES = ROOT / "bench" / "scenarios" / "sector_eval_holdout.json"
DEFAULT_JSON = ROOT / "reports" / "security-upgrade" / "sector-evaluation.json"
DEFAULT_MD = ROOT / "reports" / "security-upgrade" / "sector-evaluation.md"


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, int(0.95 * len(ordered) + 0.999999) - 1))]


def _pct(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 2) if whole else 0.0


def _load(path: Path) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc.get("cases"), list) or not doc["cases"]:
        raise ValueError("evaluation file must contain a non-empty cases list")
    return doc


def _gateway(tmp: Path, *, intent_judge: bool, model: str) -> tuple[Gateway, Database]:
    policy_path = ROOT / "configs" / "policies" / "sectors.yaml"
    policy = PolicyEngine.from_yaml(policy_path.read_text(encoding="utf-8"))
    db = Database(f"sqlite:///{tmp / 'evaluation.db'}")
    db.create_all()
    approvals = ApprovalService(db, Notifier(), timeout_s=300)
    judge = OllamaIntentJudge(model=model) if intent_judge else None
    gateway = Gateway(
        policy=policy,
        taint=TaintTracker(),
        detector=InjectionDetector(),
        audit=AuditLog(db, b"sector-evaluation-hmac-key-32bytes"),
        approvals=approvals,
        security_monitor=SecurityMonitor(intent_judge=judge),
        agent_names=policy.agent_names(),
    )
    return gateway, db


async def _protected(case: dict[str, Any], gateway: Gateway) -> dict[str, Any]:
    session_id = f"eval-{case['id']}"
    assert gateway.security_monitor is not None
    gateway.security_monitor.bind_task(session_id, case["agent_id"], case["original_task"])
    call = ToolCall(
        session_id=session_id,
        agent_id=case["agent_id"],
        tool=case["tool"],
        arguments=case.get("arguments", {}),
    )
    started = time.perf_counter()
    decision = await gateway.check_call(call, wait_for_approval=False)
    wall_ms = (time.perf_counter() - started) * 1000
    return {
        "action": decision.action.value,
        "risk": decision.risk.value,
        "risk_score": round(decision.risk_score, 4),
        "decision_ms": round(decision.latency_ms, 3),
        "wall_ms": round(wall_ms, 3),
        "reason_codes": [reason.code for reason in decision.reasons],
        "reasons": [
            {
                "code": reason.code,
                "action": reason.action.value,
                "risk_score": reason.risk_score,
                "message": reason.message,
                "evidence": reason.evidence,
            }
            for reason in decision.reasons
        ],
    }


def _summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    attack = [row for row in results if row["kind"] == "attack"]
    benign = [row for row in results if row["kind"] == "benign"]
    control = [row for row in results if row["kind"] == "control"]
    failures = [row for row in results if row["protected"]["action"] != row["expected_action"]]
    latencies = [row["protected"]["wall_ms"] for row in results]
    by_language: dict[str, Any] = {}
    for language in sorted({row["language"] for row in results}):
        rows = [row for row in results if row["language"] == language]
        lang_attacks = [row for row in rows if row["kind"] == "attack"]
        lang_benign = [row for row in rows if row["kind"] == "benign"]
        by_language[language] = {
            "cases": len(rows),
            "protected_attack_successes": sum(
                row["protected"]["action"] == "allow" for row in lang_attacks
            ),
            "protected_false_blocks": sum(
                row["protected"]["action"] != "allow" for row in lang_benign
            ),
            "failed_expectations": sum(
                row["protected"]["action"] != row["expected_action"] for row in rows
            ),
        }
    return {
        "cases": len(results),
        "attack_cases": len(attack),
        "benign_cases": len(benign),
        "control_cases": len(control),
        "without_mirsad": {
            "successful_attacks": len(attack),
            "attack_success_rate_pct": _pct(len(attack), len(attack)),
            "false_blocks": 0,
            "false_block_rate_pct": 0.0,
        },
        "with_mirsad": {
            "successful_attacks": sum(row["protected"]["action"] == "allow" for row in attack),
            "attack_success_rate_pct": _pct(
                sum(row["protected"]["action"] == "allow" for row in attack), len(attack)
            ),
            "false_blocks": sum(row["protected"]["action"] != "allow" for row in benign),
            "false_block_rate_pct": _pct(
                sum(row["protected"]["action"] != "allow" for row in benign), len(benign)
            ),
            "correct_controls": sum(
                row["protected"]["action"] == row["expected_action"] for row in control
            ),
        },
        "latency_ms": {
            "p50": round(statistics.median(latencies), 3) if latencies else 0.0,
            "p95": round(_p95(latencies), 3),
            "max": round(max(latencies), 3) if latencies else 0.0,
        },
        "failed_expectations": len(failures),
        "failed_case_ids": [row["id"] for row in failures],
        "actions": dict(Counter(row["protected"]["action"] for row in results)),
        "by_language": by_language,
    }


def _markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    before = summary["without_mirsad"]
    after = summary["with_mirsad"]
    lines = [
        "# Mirsad bilingual sector security evaluation",
        "",
        f"Run: `{report['run_at_utc']}`  ",
        f"Suite: `{report['suite']}`  ",
        f"Intent judge: `{report['intent_judge']}`",
        "",
        "## Scope",
        "",
        "This is a repeatable authorization-stage comparison. Each case supplies the trusted original user task and the next tool call proposed by the agent. The unprotected baseline permits that call; the protected run sends it through the real Mirsad gateway. It does not measure natural-language agent tool-selection accuracy.",
        "",
        "## Summary",
        "",
        "| Metric | Without Mirsad | With Mirsad |",
        "|---|---:|---:|",
        f"| Successful attacks | {before['successful_attacks']}/{summary['attack_cases']} | {after['successful_attacks']}/{summary['attack_cases']} |",
        f"| Attack success rate | {before['attack_success_rate_pct']:.2f}% | {after['attack_success_rate_pct']:.2f}% |",
        f"| Normal requests incorrectly blocked | {before['false_blocks']}/{summary['benign_cases']} | {after['false_blocks']}/{summary['benign_cases']} |",
        f"| False-block rate | {before['false_block_rate_pct']:.2f}% | {after['false_block_rate_pct']:.2f}% |",
        "",
        f"Protected gateway latency: p50 **{summary['latency_ms']['p50']:.3f} ms**, p95 **{summary['latency_ms']['p95']:.3f} ms**, max **{summary['latency_ms']['max']:.3f} ms**.",
        "",
        "## Cases",
        "",
        "| ID | Lang | Type | Tool | Expected | Actual | Result | Reason codes |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in report["results"]:
        actual = row["protected"]["action"]
        ok = "PASS" if actual == row["expected_action"] else "FAIL"
        codes = ", ".join(row["protected"]["reason_codes"]) or "none"
        lines.append(
            f"| {row['id']} | {row['language']} | {row['kind']} | {row['tool']} | "
            f"{row['expected_action']} | {actual} | {ok} | {codes} |"
        )
    lines += ["", "## Failed cases", ""]
    failures = [row for row in report["results"] if row["protected"]["action"] != row["expected_action"]]
    if failures:
        for row in failures:
            lines.append(
                f"- `{row['id']}` expected `{row['expected_action']}` but received "
                f"`{row['protected']['action']}`."
            )
    else:
        lines.append("No expected-result failures in this run.")
    lines += [
        "",
        "## Test separation and honesty note",
        "",
        "These final cases live outside the development unit tests. Freeze this file before the final measurement and do not adjust thresholds or rules from these results. Any future failure must remain in the report until a new version and a new holdout set are prepared.",
        "",
    ]
    return "\n".join(lines)


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    source = _load(args.cases)
    with tempfile.TemporaryDirectory(prefix="mirsad-sector-eval-") as tmp_name:
        results: list[dict[str, Any]] = []
        for index, case in enumerate(source["cases"]):
            # Every case starts from a clean policy/rate-limit/session state. This makes
            # the suite repeatable and prevents one case from changing a later verdict.
            case_dir = Path(tmp_name) / f"case-{index:03d}"
            case_dir.mkdir()
            gateway, db = _gateway(case_dir, intent_judge=args.intent_judge, model=args.model)
            try:
                protected = await _protected(case, gateway)
                results.append({
                    **case,
                    "without_mirsad": {"action": "allow", "wall_ms": 0.0},
                    "protected": protected,
                })
            finally:
                db.dispose()
    return {
        "schema_version": 1,
        "suite": source["suite"],
        "purpose": source.get("purpose", ""),
        "run_at_utc": datetime.now(UTC).isoformat(),
        "intent_judge": f"ollama:{args.model}" if args.intent_judge else "disabled (hard controls only)",
        "cases_file": str(args.cases.relative_to(ROOT) if args.cases.is_relative_to(ROOT) else args.cases),
        "results": results,
        "summary": _summarize(results),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown-out", type=Path, default=DEFAULT_MD)
    parser.add_argument("--intent-judge", action="store_true", help="Use the local Ollama intent judge")
    parser.add_argument("--model", default="qwen2.5:7b")
    args = parser.parse_args()
    args.cases = args.cases.resolve()
    report = asyncio.run(_run(args))
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.markdown_out.write_text(_markdown(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 1 if report["summary"]["failed_expectations"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
