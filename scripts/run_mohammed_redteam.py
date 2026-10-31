"""Run the 60 fixed attack/twin pairs without mixing unrelated templates and tasks."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from bench.loader import Suite, load_suite
from bench.metrics import summarize
from bench.run import build_parser, run_benchmark

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "mohammed-redteam"


async def main() -> None:
    suite = load_suite()
    pairs = json.loads((ROOT / "bench/scenarios/mohammed_pairs.json").read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    tasks = {t.id: t for t in suite.user_tasks}
    templates = {t.id: t for t in suite.attack_templates}
    injections = {t.id: t for t in suite.injection_tasks}
    records = []
    for approver in ("oracle", "approve"):
        for pair in pairs:
            selected = Suite(user_tasks=[tasks[pair["task"]]],
                             attack_templates=[templates[pair["template"]]],
                             injection_tasks=[injections[pair["injection"]]],
                             files=suite.files)
            out = OUT / approver / pair["id"]
            argv = ["--agent", "scripted", "--episodes", "all", "--defense", "all",
                    "--approver", approver, "--positions", "end", "--seed", "7",
                    "--replay-check", "--no-figures", "--out", str(out)]
            args = build_parser().parse_args(argv)
            args.argv = argv
            await run_benchmark(args, selected)
            records.extend(json.loads(line) for line in (out / "episodes.jsonl").read_text().splitlines())
    summary = summarize(records)
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    (OUT / "episodes.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
    compact = []
    for config in summary["configs"]:
        compact.append({k: config[k] for k in ("agent", "defense", "approver", "overall", "asr", "asr_reduction")})
    print("MOHAMMED_REDTEAM_RESULTS=" + json.dumps(compact, ensure_ascii=False))
    # Bypasses stay reproducible as the exact pair + side-effect record, even when an expected
    # security assertion fails. A failed threshold must never erase the evidence.
    bypasses = [r for r in records if r.get("kind") == "attack"
                and r.get("defense") == "full" and r.get("attack_success")]
    (OUT / "bypasses.json").write_text(json.dumps(bypasses, ensure_ascii=False, indent=2))
    checks = [json.loads(line) for path in OUT.glob("*/*/audit_checks.jsonl")
              for line in path.read_text().splitlines()]
    (OUT / "audit_checks.json").write_text(json.dumps(checks, indent=2))
    print("MOHAMMED_REDTEAM_BYPASSES=" + str(len(bypasses)))
    print("MOHAMMED_REDTEAM_AUDIT=" + json.dumps(checks))
    assert len(pairs) == 60
    assert all(c["audit"]["ok"] for c in checks), "audit verification failed"


if __name__ == "__main__":
    asyncio.run(main())
