"""Compare several Mirsad-Bench runs side by side.

    python -m bench.compare reports/bench/scripted-oracle reports/bench/scripted-deny \
        --out reports/bench/comparison.md

Each argument is a run directory (containing ``summary.json``) or a ``summary.json`` path. The
output is a markdown table with one row per (run, agent, defense, approver) and, when attack episodes
exist, the number of attack episodes, ASR, ASR reduction against the undefended baseline of the same
run, and utility under attack.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from bench.report import DEFENSE_ORDER


def load_summary(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if p.is_dir():
        p = p / "summary.json"
    if not p.is_file():
        raise FileNotFoundError(f"no summary.json at {path}")
    data = json.loads(p.read_text(encoding="utf-8"))
    data.setdefault("meta", {}).setdefault("run_id", p.parent.name)
    return data


def _pct(v: float | None) -> str:
    return "–" if v is None else f"{100 * v:.1f}%"


def comparison_rows(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for s in summaries:
        run = s["meta"].get("run_id", "?")
        for c in s.get("configs", []):
            o = c["overall"]
            attack = c.get("attack") or {}
            rows.append({
                "run": run, "agent": c["agent"], "defense": c["defense"], "approver": c["approver"],
                "episodes": o["episodes"], "utility": o["utility"], "fpr": o["fpr"], "friction": o["friction"],
                "final_block_rate": o["final_block_rate"], "result_fp_rate": o["result_fp_rate"],
                "gateway_p50": o["latency_ms"]["gateway_p50"], "gateway_p95": o["latency_ms"]["gateway_p95"],
                "asr": c.get("asr"), "asr_reduction": c.get("asr_reduction"),
                "attack_episodes": attack.get("episodes", 0),
                "utility_under_attack": attack.get("utility_under_attack"),
            })
    rows.sort(key=lambda r: (r["run"], r["agent"],
                             DEFENSE_ORDER.index(r["defense"]) if r["defense"] in DEFENSE_ORDER else 99,
                             r["approver"]))
    return rows


def render(rows: list[dict[str, Any]]) -> str:
    any_asr = any(r["asr"] is not None for r in rows)
    head = ("| run | agent | defense | approver | episodes | utility | FPR | friction | final block | result FP | "
            "p50 ms | p95 ms |" + (" attack episodes | ASR | ASR reduction | utility under attack |" if any_asr else ""))
    sep = "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|" + ("---:|---:|---:|---:|" if any_asr else "")
    lines = ["# Mirsad-Bench comparison", "", head, sep]
    for r in rows:
        p50 = "–" if r["gateway_p50"] is None else f"{r['gateway_p50']:.2f}"
        p95 = "–" if r["gateway_p95"] is None else f"{r['gateway_p95']:.2f}"
        line = (f"| {r['run']} | {r['agent']} | {r['defense']} | {r['approver']} | {r['episodes']} | "
                f"{_pct(r['utility'])} | {_pct(r['fpr'])} | {_pct(r['friction'])} | {_pct(r['final_block_rate'])} | "
                f"{_pct(r['result_fp_rate'])} | {p50} | {p95} |")
        if any_asr:
            line += (f" {r.get('attack_episodes', 0)} | {_pct(r['asr'])} | {_pct(r['asr_reduction'])} | "
                     f"{_pct(r.get('utility_under_attack'))} |")
        lines.append(line)
    if any_asr:
        lines += ["", "Episodes, utility, FPR, friction, final block, result FP and latency are over benign episodes; "
                  "ASR, ASR reduction (vs. defense none of the same run and agent) and utility under attack are over "
                  "attack episodes."]
    else:
        lines += ["", "No attack episodes in these runs, so ASR is not reported."]
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m bench.compare", description="Compare Mirsad-Bench runs.")
    parser.add_argument("runs", nargs="+", help="run directories or summary.json files")
    parser.add_argument("--out", default="", help="write markdown here (default: stdout)")
    parser.add_argument("--json", default="", help="also write the rows as JSON here")
    args = parser.parse_args(argv)
    rows = comparison_rows([load_summary(r) for r in args.runs])
    text = render(rows)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    if args.json:
        Path(args.json).write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
