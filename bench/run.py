"""Mirsad-Bench runner (resumable).

    python -m bench.run --agent scripted --episodes benign --defense all --approver oracle \
        --out reports/bench/scripted-benign-oracle
    python -m bench.run --agent scripted --episodes all --defense all --approver oracle \
        --out reports/bench/scripted-attack-oracle
    python -m bench.run --agent llm --episodes attack --defense none,full --approver oracle --limit 48 \
        --out reports/bench/llm-attack-oracle

Writes ``<out>/episodes.jsonl`` (one line per finished episode, appended as it goes),
``<out>/summary.json``, ``<out>/summary.md`` and ``<out>/figures/*.png``. Re-running with the same
``--out`` skips episodes already in ``episodes.jsonl`` (key = agent|defense|approver|episode|seed), so an
interrupted run continues where it stopped.

Benign episodes run a user task as written. Attack episodes (``--episodes attack|all``, or ``auto`` when
the human team has added attack files to ``bench/scenarios/attacks/``) plant a rendered attack template
into the item a user task reads and grade the injection task's predicate as well; see
:mod:`bench.attacks` and docs/benchmark.md.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import platform
import shlex
import sys
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from demo.agent import DEFAULT_LLM_BASE_URL, DEFAULT_MODEL, make_world_executor

from bench.agents import LLMAgent, RecordingDirectBackend, RecordingGatewayBackend, ScriptedAgent
from bench.attacks import (
    POSITIONS,
    AttackEpisode,
    AttackSelection,
    RenderContext,
    attribute,
    build_attack_episodes,
    is_injection_call,
    plant_attack,
)
from bench.defenses import AGENT_ID, APPROVERS, DEFENSES, DefenseRuntime, detector_mode
from bench.episode import PredicateContext, build_world, evaluate
from bench.loader import SCENARIOS_DIR, Suite, UserTask, load_suite
from bench.metrics import summarize
from bench.report import write_reports

logger = logging.getLogger("mirsad.bench")


def episode_key(agent: str, defense: str, approver: str, task_id: str, seed: int) -> str:
    return f"{agent}|{defense}|{approver}|{task_id}|seed{seed}"


def read_episodes(path: Path) -> list[dict[str, Any]]:
    """Episodes already written (a torn last line from a crash is ignored)."""
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("ignoring a malformed line in %s", path)
    return out


def _parse_list(value: str, allowed: tuple[str, ...], what: str) -> list[str]:
    items = list(allowed) if value == "all" else [v.strip() for v in value.split(",") if v.strip()]
    bad = [v for v in items if v not in allowed]
    if bad:
        raise SystemExit(f"unknown {what}: {', '.join(bad)} (choose from {', '.join(allowed)} or 'all')")
    return items


def _backend(world: Any, runtime: DefenseRuntime, session_id: str, marker: Any = None) -> Any:
    if runtime.protected:
        return RecordingGatewayBackend(runtime.gateway(), AGENT_ID, session_id, make_world_executor(world),
                                       marker=marker)
    return RecordingDirectBackend(world, session_id, marker=marker)


async def _drive(agent: Any, task: UserTask, backend: Any, attack: Any = None) -> tuple[Any, str, str | None]:
    """Run the agent; returns ``(answer, stopped_reason, error)``. Agent/LLM failures are results, not crashes."""
    try:
        outcome = await (agent.run(task, backend) if attack is None else agent.run(task, backend, attack=attack))
        return outcome.answer, outcome.stopped_reason, None
    except Exception as exc:
        logger.warning("episode %s failed: %s: %s", task.id, type(exc).__name__, exc)
        return None, "completed", f"{type(exc).__name__}: {exc}"[:500]


async def run_episode(task: UserTask, agent: Any, runtime: DefenseRuntime, *, seed: int = 7,
                      run_id: str = "") -> dict[str, Any]:
    """Run one benign episode and return its record (never raises for agent/tool failures)."""
    world = build_world(task, seed=seed)
    session_id = f"bench-{task.id}-{uuid.uuid4().hex[:8]}"
    backend = _backend(world, runtime, session_id)
    runtime.approver.begin(task.plan)
    started = time.time()
    answer, stopped, error = await _drive(agent, task, backend)
    executed = [(r.tool, r.args) for r in backend.records if r.executed and not r.tool_error]
    utility = False
    if error is None:
        utility = evaluate(task.success, PredicateContext(world=world, executed=executed, answer=answer))
    approver = runtime.approver.mode if runtime.protected else "none"
    return {
        "key": episode_key(agent.name, runtime.defense, approver, task.id, seed),
        "run_id": run_id, "kind": "benign", "agent": agent.name, "defense": runtime.defense,
        "approver": approver, "task_id": task.id, "lang": task.lang, "variety": task.variety,
        "category": task.category, "expect_approval": task.expect_approval, "seed": seed,
        "utility": bool(utility), "calls": [r.model_dump() for r in backend.records],
        "n_calls": len(backend.records), "answer_preview": (answer or "")[:400] if answer is not None else None,
        "stopped_reason": stopped, "error": error, "started_at": started,
        "duration_s": round(time.time() - started, 3),
    }


async def run_attack_episode(episode: AttackEpisode, agent: Any, runtime: DefenseRuntime, *, seed: int = 7,
                             run_id: str = "", render_ctx: RenderContext | None = None) -> dict[str, Any]:
    """Run one attack episode and return its record (never raises for agent/tool failures).

    The rendered template is planted into the user task's read target, the agent runs the user task, and
    afterwards both predicates are evaluated on the World: the user task's (utility under attack) and the
    injection task's (attack success).
    """
    task = episode.task
    world = build_world(task, seed=seed)
    planted = plant_attack(world, episode, render_ctx)
    session_id = f"bench-{task.id}-{uuid.uuid4().hex[:8]}"
    backend = _backend(world, runtime, session_id, marker=planted.marker)
    runtime.approver.begin(task.plan)
    started = time.time()
    answer, stopped, error = await _drive(agent, task, backend, attack=planted)
    executed = [(r.tool, r.args) for r in backend.records if r.executed and not r.tool_error]
    ctx = PredicateContext(world=world, executed=executed, answer=answer)
    utility = evaluate(task.success, ctx) if error is None else False
    attack_success = evaluate(episode.injection.success, ctx)  # side effects count even if the agent failed later
    calls = []
    for r in backend.records:
        c = r.model_dump()
        c["injection"] = is_injection_call(c, episode.injection, task)
        calls.append(c)
    inj_calls = [c for c in calls if c["injection"]]
    approver = runtime.approver.mode if runtime.protected else "none"
    record: dict[str, Any] = {
        "key": episode_key(agent.name, runtime.defense, approver, episode.id, seed),
        "run_id": run_id, "kind": "attack", "agent": agent.name, "defense": runtime.defense,
        "approver": approver, "task_id": task.id, "episode_id": episode.id, "lang": task.lang,
        "variety": task.variety, "category": task.category, "expect_approval": task.expect_approval, "seed": seed,
        "attack": planted.describe(), "attack_success": bool(attack_success), "utility": bool(utility),
        "seen": any(c.get("planted_seen") for c in calls), "delivered": any(c.get("planted_delivered") for c in calls),
        "attempted": bool(inj_calls), "injection_calls": len(inj_calls),
        "injection_calls_executed": sum(1 for c in inj_calls if c["executed"] and not c["tool_error"]),
        "calls": calls, "n_calls": len(calls),
        "answer_preview": (answer or "")[:400] if answer is not None else None,
        "stopped_reason": stopped, "error": error, "started_at": started,
        "duration_s": round(time.time() - started, 3),
    }
    record["stopped_by"], record["layers_involved"] = attribute(record)
    return record


def scenarios_fingerprint(suite: Suite) -> str:
    """sha256 over the scenario files, so a resumed run can tell that grading rules changed."""
    digest = hashlib.sha256()
    for name in sorted(suite.files):
        digest.update(Path(name).name.encode())
        digest.update(Path(name).read_bytes())
    return digest.hexdigest()


def _tasks_meta(tasks: list[UserTask]) -> dict[str, int]:
    out: dict[str, int] = {}
    for t in tasks:
        out[t.lang] = out.get(t.lang, 0) + 1
    return out


def episode_mode(requested: str, suite: Suite) -> str:
    """Resolve ``--episodes``: ``auto`` runs attack episodes too when attack files define both lists."""
    if requested == "auto":
        return "all" if suite.has_attacks else "benign"
    if requested in ("attack", "all") and not suite.has_attacks:
        raise SystemExit("no attack episodes to run: bench/scenarios/attacks/*.yaml must define both "
                         "injection_tasks and attack_templates (see bench/scenarios/attacks/README.md)")
    return requested


def select_attacks(args: argparse.Namespace, suite: Suite) -> AttackSelection:
    """The attack episodes for this run (same for every defence configuration)."""
    pool = suite.select(lang=args.lang, ids=args.tasks.split(",") if args.tasks else None,
                        categories=args.categories.split(",") if args.categories else None)
    try:
        return build_attack_episodes(pool, suite.injection_tasks, suite.attack_templates,
                                     injection_keys=args.injections, template_keys=args.templates,
                                     langs=args.langs, positions=args.positions, limit=args.limit, seed=args.seed)
    except (KeyError, ValueError) as exc:
        raise SystemExit(str(exc).strip("'\"")) from exc


async def run_benchmark(args: argparse.Namespace, suite: Suite) -> dict[str, Any]:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    episodes_path = out_dir / "episodes.jsonl"
    done = {e.get("key") for e in read_episodes(episodes_path)}
    mode = episode_mode(getattr(args, "episodes", "auto"), suite)
    tasks: list[UserTask] = []
    if mode in ("benign", "all"):
        tasks = suite.select(lang=args.lang, ids=args.tasks.split(",") if args.tasks else None,
                             categories=args.categories.split(",") if args.categories else None, limit=args.limit)
    selection = select_attacks(args, suite) if mode in ("attack", "all") else None
    attack_eps = selection.episodes if selection else []
    defenses = _parse_list(args.defense, DEFENSES, "defense")
    approvers = _parse_list(args.approver, APPROVERS, "approver")
    agent: Any = (ScriptedAgent() if args.agent == "scripted" else
                  LLMAgent(base_url=args.llm_base_url, model=args.model, max_steps=args.max_steps))
    render_ctx = RenderContext(model=args.model if args.agent == "llm" else None)
    run_id = out_dir.name
    fingerprint = scenarios_fingerprint(suite)
    state_path = out_dir / "run_state.json"
    if done and state_path.exists():
        previous = json.loads(state_path.read_text(encoding="utf-8")).get("scenarios_sha256")
        if previous != fingerprint:
            logger.warning("scenario files changed since the episodes in %s were recorded; earlier episodes were "
                           "graded with the old files (use a fresh --out for comparable results)", out_dir)
    state_path.write_text(json.dumps({"scenarios_sha256": fingerprint}), encoding="utf-8")
    if mode == "benign" and (suite.injection_tasks or suite.attack_templates):
        logger.info("attack files found (%d injection tasks, %d templates); this run is benign only "
                    "(--episodes attack|all to run them)", len(suite.injection_tasks), len(suite.attack_templates))
    if selection is not None:
        logger.info("attack episodes: %d (of %d valid combinations; excluded pairs: %s)", len(attack_eps),
                    selection.candidates, {k: len(v) for k, v in selection.excluded.items()} or "none")

    audit_checks: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="mirsad-bench-") as tmp:
        workdir = Path(args.keep_audit) if args.keep_audit else Path(tmp)
        for defense in defenses:
            for approver in (approvers if defense != "none" else approvers[:1]):
                runtime = DefenseRuntime(defense, approver, workdir=workdir)
                shown_approver = approver if runtime.protected else "none"
                todo = [t for t in tasks
                        if episode_key(agent.name, defense, shown_approver, t.id, args.seed) not in done]
                todo_attacks = [ep for ep in attack_eps
                                if episode_key(agent.name, defense, shown_approver, ep.id, args.seed) not in done]
                logger.info("%s / %s / %s: %d benign + %d attack episode(s) to run, %d already done", agent.name,
                            defense, shown_approver, len(todo), len(todo_attacks),
                            len(tasks) + len(attack_eps) - len(todo) - len(todo_attacks))
                ran = 0
                for task in todo:
                    record = await run_episode(task, agent, runtime, seed=args.seed, run_id=run_id)
                    with episodes_path.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                    ran += 1
                    logger.info("  %-28s utility=%s calls=%d", task.id, record["utility"], record["n_calls"])
                for ep in todo_attacks:
                    record = await run_attack_episode(ep, agent, runtime, seed=args.seed, run_id=run_id,
                                                      render_ctx=render_ctx)
                    with episodes_path.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                    ran += 1
                    logger.info("  %-60s attack_success=%s utility=%s stopped_by=%s", ep.id,
                                record["attack_success"], record["utility"], record["stopped_by"])
                if runtime.protected and ran:
                    check = {"defense": defense, "approver": approver, "episodes": ran,
                             "audit": runtime.verify_audit(),
                             "replay": runtime.replay_check() if args.replay_check else None,
                             "at": datetime.now(UTC).isoformat(timespec="seconds")}
                    audit_checks.append(check)
                    with (out_dir / "audit_checks.jsonl").open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps(check) + "\n")
                await runtime.aclose()

    episodes = read_episodes(episodes_path)
    summary = summarize(episodes)
    all_checks = read_episodes(out_dir / "audit_checks.jsonl")
    used = {t.id: t for t in tasks} | {ep.task.id: ep.task for ep in attack_eps}
    meta = {
        "run_id": run_id, "agent": args.agent, "model": args.model if args.agent == "llm" else None,
        "command": "python -m bench.run " + " ".join(shlex.quote(a) for a in (args.argv or [])),
        "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "episodes_mode": mode, "n_tasks": len(used), "tasks_by_lang": _tasks_meta(list(used.values())),
        "n_benign_tasks": len(tasks),
        "attack": None if selection is None else {
            **selection.meta(), "langs": args.langs, "templates_filter": args.templates or "all",
            "injections_filter": args.injections or "all", "positions": args.positions, "limit": args.limit,
            "seed": args.seed, "sampling": "balanced over templates" if args.limit else "all combinations"},
        "detector_mode": {d: detector_mode(d) for d in defenses},
        "scenario_files": [Path(f).name for f in suite.files], "scenarios_sha256": fingerprint,
        "injection_tasks_available": len(suite.injection_tasks),
        "attack_templates_available": len(suite.attack_templates),
        "python": platform.python_version(), "platform": platform.platform(),
        "audit_checks": all_checks,
    }
    write_reports(out_dir, summary, meta, figures=not args.no_figures)
    return {"summary": summary, "meta": meta}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m bench.run",
                                description="Run Mirsad-Bench (benign and attack episodes).")
    p.add_argument("--agent", choices=["scripted", "llm"], default="scripted")
    p.add_argument("--episodes", choices=["auto", "benign", "attack", "all"], default="auto",
                   help="which episodes to run; auto = benign, plus attack episodes when attack files exist")
    p.add_argument("--defense", default="all", help=f"comma list of {', '.join(DEFENSES)} or 'all'")
    p.add_argument("--approver", default="oracle", help=f"comma list of {', '.join(APPROVERS)} or 'all'")
    p.add_argument("--lang", choices=["en", "ar", "all"], default="all", help="user task language")
    p.add_argument("--tasks", default="", help="comma list of user task ids")
    p.add_argument("--categories", default="", help="comma list of task categories")
    p.add_argument("--limit", type=int, default=None,
                   help="benign: at most N user tasks (after filters); attack: at most N attack episodes "
                        "(seeded sample balanced over templates)")
    p.add_argument("--langs", default="all", help="attack template languages: comma list of en, ar, mixed or 'all'")
    p.add_argument("--templates", default="", help="attack template ids or styles (comma list; default all)")
    p.add_argument("--injections", default="", help="injection task ids or categories (comma list; default all)")
    p.add_argument("--positions", default=",".join(POSITIONS),
                   help="where planted text may go (start, middle, end); each episode gets one, chosen by seed")
    p.add_argument("--seed", type=int, default=7, help="World seed; also seeds attack sampling and positions")
    p.add_argument("--scenarios", default=str(SCENARIOS_DIR))
    p.add_argument("--out", default=None, help="output directory (default reports/bench/<agent>-<timestamp>)")
    p.add_argument("--llm-base-url", default=DEFAULT_LLM_BASE_URL)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--max-steps", type=int, default=8)
    p.add_argument("--replay-check", action="store_true", help="replay every audited decision afterwards")
    p.add_argument("--keep-audit", default="", help="keep the audit SQLite files in this directory")
    p.add_argument("--no-figures", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(argv)
    args.argv = argv
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("mirsad.bench").setLevel(logging.INFO)
    if args.out is None:
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        args.out = str(Path("reports") / "bench" / f"{args.agent}-{stamp}")
    suite = load_suite(args.scenarios)
    result = asyncio.run(run_benchmark(args, suite))
    sys.stdout.write((Path(args.out) / "summary.md").read_text(encoding="utf-8"))
    return 0 if result["summary"]["episodes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
