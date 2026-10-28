"""Collect every measured result into reports/results_summary.json (the single source for the documents).

Reads the outputs written by scripts/run_evidence.sh: JUnit XML of the Python suite, the Vitest JSON report,
coverage.json, Bandit / pip-audit / npm-audit reports, the latency benchmarks, the Mirsad-Bench runs and the
detector metrics. Anything that has not been produced yet is stored as null, and the documents show
"[pending]" for it instead of a number.
"""

from __future__ import annotations

import json
import re
import subprocess
import xml.etree.ElementTree as ET  # noqa: S405 - parses our own JUnit output
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def python_tests() -> dict[str, Any] | None:
    junit = REPORTS / "tests" / "junit.xml"
    if not junit.exists():
        return None
    root = ET.parse(junit).getroot()  # noqa: S314 - trusted local file
    suites = [root] if root.tag == "testsuite" else list(root)
    total = sum(int(s.get("tests", 0)) for s in suites)
    failures = sum(int(s.get("failures", 0)) + int(s.get("errors", 0)) for s in suites)
    skipped = sum(int(s.get("skipped", 0)) for s in suites)
    by_area: dict[str, int] = {}
    for case in root.iter("testcase"):
        m = re.match(r"tests\.(\w+)", case.get("classname", ""))
        area = m.group(1) if m else "other"
        by_area[area] = by_area.get(area, 0) + 1
    return {"total": total, "passed": total - failures - skipped, "failed": failures, "skipped": skipped,
            "by_area": dict(sorted(by_area.items()))}


def web_tests() -> dict[str, Any] | None:
    data = load(REPORTS / "tests" / "vitest.json")
    if not data:
        return None
    return {"total": data.get("numTotalTests"), "passed": data.get("numPassedTests"),
            "failed": data.get("numFailedTests"), "files": data.get("numTotalTestSuites")}


def coverage() -> dict[str, Any] | None:
    data = load(REPORTS / "coverage.json")
    if not data:
        return None
    per: dict[str, list[int]] = {}
    for name, info in data["files"].items():
        parts = name.split("mirsad/")[-1].split("/")
        key = parts[0].removesuffix(".py")
        acc = per.setdefault(key, [0, 0])
        acc[0] += info["summary"]["covered_lines"]
        acc[1] += info["summary"]["num_statements"]
    return {"percent": round(data["totals"]["percent_covered"], 1),
            "statements": data["totals"]["num_statements"],
            "by_package": {k: round(100 * a / b, 1) for k, (a, b) in sorted(per.items()) if b}}


def security() -> dict[str, Any]:
    out: dict[str, Any] = {}
    bandit = load(REPORTS / "security" / "bandit.json")
    if bandit:
        out["bandit_issues"] = len(bandit["results"])
        out["bandit_loc"] = bandit["metrics"]["_totals"]["loc"]
    pip = load(REPORTS / "security" / "pip-audit.json")
    if pip:
        deps = pip.get("dependencies", [])
        out["pip_audit_packages"] = len(deps)
        out["pip_audit_vulnerable"] = sum(1 for d in deps if d.get("vulns"))
    npm = load(REPORTS / "security" / "npm-audit.json")
    if npm:
        out["npm_audit_vulnerabilities"] = npm["metadata"]["vulnerabilities"]["total"]
    return out


def latency() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, file in (("in_process", "latency.json"), ("separate_process", "latency-process.json")):
        data = load(REPORTS / "bench" / file)
        if not data:
            continue
        out[name] = {
            "calls": data["calls"], "sessions": data["concurrent_sessions"], "detector_mode": data["detector_mode"],
            "sequential_added_p50": data["sequential"]["added_ms"]["p50"],
            "sequential_added_p95": data["sequential"]["added_ms"]["p95"],
            "sequential_added_p99": data["sequential"]["added_ms"]["p99"],
            "sequential_rps": data["sequential"]["throughput_rps"],
            "concurrent_added_p50": data["concurrent"]["added_ms"]["p50"],
            "concurrent_added_p95": data["concurrent"]["added_ms"]["p95"],
            "concurrent_added_p99": data["concurrent"]["added_ms"]["p99"],
            "concurrent_rps": data["concurrent"]["throughput_rps"],
            "concurrent_errors": data["concurrent"]["http_errors"],
            "gateway_p50": data["sequential"]["gateway_ms"]["p50"],
            "audit_ok": data["audit_chain_ok"], "date": data["date"],
        }
    return out


def bench_runs() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for summary in sorted((REPORTS / "bench").glob("*/summary.json")):
        data = load(summary)
        run = summary.parent.name.replace("-", "_")
        configs: dict[str, Any] = {}
        for cfg in data.get("configs", []):
            o = cfg.get("overall", {})
            lat = o.get("latency_ms") or {}
            configs[cfg["defense"]] = {k: o.get(k) for k in (
                "episodes", "calls", "utility", "fpr", "friction", "final_block_rate", "result_fp_rate")} | {
                "asr": cfg.get("asr"), "asr_reduction": cfg.get("asr_reduction"),
                "gateway_p50_ms": lat.get("gateway_p50"), "gateway_p95_ms": lat.get("gateway_p95")}
        checks = data.get("meta", {}).get("audit_checks", [])
        out[run] = {
            "agent": data.get("meta", {}).get("agent"), "tasks": data.get("meta", {}).get("n_tasks"),
            "attack_episodes": (data.get("attack_episodes") if isinstance(data.get("attack_episodes"), int)
                                else len(data.get("attack_episodes") or [])),
            "replay_checked": sum(c["replay"]["checked"] for c in checks if c.get("replay")),
            "replay_matched": sum(c["replay"]["matched"] for c in checks if c.get("replay")),
            "audit_all_ok": all(c["audit"]["ok"] for c in checks) if checks else None,
            "configs": configs,
        }
    return out


def detector() -> dict[str, Any] | None:
    data = load(REPORTS / "detector_metrics.json")
    if not data:
        return None
    splits = {name: {k: ev["ensemble"].get(k) for k in ("f1", "precision", "recall", "fpr", "roc_auc", "n")}
              | {"f1_rules_only": ev.get("rules_only", {}).get("f1"), "f1_model_only": ev.get("model_only", {}).get("f1")}
              for name, ev in data.get("splits", {}).items()}
    lat = data.get("latency_ms", {}).get("ensemble", {})
    return {"splits": splits, "latency_ms": lat, "generated_at": data.get("generated_at")}


def code_size() -> dict[str, int]:
    def count(globs: list[str]) -> int:
        return sum(len(p.read_text(encoding="utf-8", errors="ignore").splitlines())
                   for g in globs for p in ROOT.glob(g) if p.is_file() and "node_modules" not in p.parts)
    return {"python_src": count(["src/mirsad/**/*.py"]), "python_demo_bench": count(["demo/**/*.py", "bench/**/*.py"]),
            "python_tests": count(["tests/**/*.py"]), "web_ts": count(["web/src/**/*.ts", "web/src/**/*.tsx"])}


def main() -> None:
    commit = None
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,  # noqa: S603,S607
                                text=True, check=True).stdout.strip() or None
    except Exception:  # noqa: BLE001 - not a git checkout
        commit = None
    summary = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"), "commit": commit,
        "python_tests": python_tests(), "web_tests": web_tests(), "coverage": coverage(), "security": security(),
        "latency": latency(), "bench": bench_runs(), "detector": detector(), "code_size": code_size(),
    }
    out = REPORTS / "results_summary.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
