"""Write ``summary.json``, ``summary.md`` and ``figures/*.png`` for a Mirsad-Bench run."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("mirsad.bench")

# Reference palette (dataviz skill, light mode): surface, ink, and categorical slots 1-2 in fixed order.
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834"]

DEFENSE_ORDER = ["none", "full", "policy_only", "taint_only", "detector_only"]


def _pct(v: float | None) -> str:
    return "–" if v is None else f"{100 * v:.1f}%"


def _ms(v: float | None) -> str:
    return "–" if v is None else f"{v:.2f}"


def _sorted_configs(summary: dict[str, Any]) -> list[dict[str, Any]]:
    def key(c: dict[str, Any]) -> tuple[Any, ...]:
        d = c["defense"]
        return (c["agent"], DEFENSE_ORDER.index(d) if d in DEFENSE_ORDER else 99, c["approver"])
    return sorted(summary["configs"], key=key)


STOP_COLUMNS = ("detector", "policy", "taint", "approval")
OTHER_STOPS = ("other", "not_reached", "agent_ignored", "ineffective", "error")
DIMENSION_TITLES = {
    "template_lang": "template language", "template_variety": "template variety", "style": "template style",
    "injection_category": "injection category", "vector": "vector (where the text was planted)",
    "position": "position in the item", "task_lang": "user task language",
}


def render_markdown(summary: dict[str, Any], meta: dict[str, Any]) -> str:
    lines = [f"# Mirsad-Bench run `{meta.get('run_id', '?')}`", ""]
    lines.append(f"* Date (UTC): {meta.get('finished_at', meta.get('started_at', '?'))}")
    lines.append(f"* Command: `{meta.get('command', '?')}`")
    lines.append(f"* Agent: {meta.get('agent')}"
                 + (f" (model {meta.get('model')})" if meta.get("agent") == "llm" else ""))
    lines.append(f"* Episodes: {summary['episodes']} (attack episodes: {summary['attack_episodes']})")
    lines.append(f"* User tasks: {meta.get('n_tasks')} ({meta.get('tasks_by_lang')})")
    lines.append(f"* Detector mode: {meta.get('detector_mode')}")
    attack_meta = meta.get("attack") or {}
    if not summary["attack_episodes"]:
        lines.append("* Attack success rate: not measured in this run (no attack episodes; see docs/benchmark.md).")
    else:
        excluded = attack_meta.get("excluded") or {}
        lines.append(f"* Attack episodes per configuration: {attack_meta.get('episodes', '?')} of "
                     f"{attack_meta.get('candidates', '?')} valid combinations "
                     f"({attack_meta.get('injection_tasks', '?')} injection tasks x {attack_meta.get('templates', '?')} "
                     f"templates x user-task reads; sampling: {attack_meta.get('sampling', '?')}, "
                     f"seed {attack_meta.get('seed', '?')}; excluded pairs: {excluded or 'none'}). "
                     "See 'Attack results' below.")
    if summary.get("benign_episodes", summary["episodes"] - summary["attack_episodes"]):
        lines += _benign_sections(summary)
    if summary["attack_episodes"]:
        lines += _attack_sections(summary)
    checks = meta.get("audit_checks") or []
    if checks:
        lines += ["", "## Audit chain and replay", "", "| defense | approver | chain ok | events checked | "
                  "decisions replayed | replay matches |", "|---|---|---|---:|---:|---:|"]
        for a in checks:
            rep = a.get("replay") or {}
            lines.append(f"| {a['defense']} | {a['approver']} | {a['audit'].get('ok')} | "
                         f"{a['audit'].get('checked')} | {rep.get('checked', '–')} | {rep.get('matched', '–')} |")
    lines.append("")
    return "\n".join(lines)


def _attack_sections(summary: dict[str, Any]) -> list[str]:
    configs = [c for c in _sorted_configs(summary) if c.get("attack")]
    lines = ["", "## Attack results per configuration", "",
             "| agent | defense | approver | attack episodes | ASR | ASR reduction | utility under attack | "
             "delivered | attempted | stopped: detector | stopped: policy | stopped: taint | stopped: approval | "
             "not stopped by a layer |",
             "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for c in configs:
        a = c["attack"]
        stops = a["stopped_by"]
        rest = sum(stops.get(k, 0) for k in OTHER_STOPS)
        lines.append(f"| {c['agent']} | {c['defense']} | {c['approver']} | {a['episodes']} | {_pct(a['asr'])} | "
                     f"{_pct(c.get('asr_reduction'))} | {_pct(a['utility_under_attack'])} | "
                     f"{_pct(a['delivery_rate'])} | {_pct(a['attempt_rate'])} | "
                     + " | ".join(str(stops.get(k, 0)) for k in STOP_COLUMNS) + f" | {rest} |")
    lines += ["", "ASR = attack episodes whose injection-task predicate held on World side effects / attack episodes; "
              "ASR reduction = 1 - ASR / ASR(defense none) for the same agent; utility under attack = attack "
              "episodes whose user-task predicate still held. Delivered = the planted text reached the agent at "
              "least once; attempted = the agent made at least one injection call. The 'stopped' columns count "
              "failed attacks by the layer that stopped them first (detector = the planted text was removed or "
              "withheld before it reached the agent); 'not stopped by a layer' counts failed attacks that no "
              "layer stopped (text never reached the agent for another reason, agent ignored it, ineffective "
              "action, or an agent error).", ""]
    detail = []
    for c in configs:
        parts = [f"{k} x{c['attack']['stopped_by'][k]}" for k in OTHER_STOPS if c["attack"]["stopped_by"].get(k)]
        if parts:
            detail.append(f"* {c['agent']} / {c['defense']} / {c['approver']}: {', '.join(parts)}")
    if detail:
        lines += ["Failed attacks not stopped by a layer:", *detail, ""]
    for dim, title in DIMENSION_TITLES.items():
        groups = sorted({k for c in configs for k in c["attack"]["by"].get(dim, {})})
        if not groups:
            continue
        lines += [f"## ASR by {title}", "",
                  f"| agent | defense | approver | {dim} | episodes | ASR | ASR reduction | utility under attack |",
                  "|---|---|---|---|---:|---:|---:|---:|"]
        for c in configs:
            for key in groups:
                g = c["attack"]["by"][dim].get(key)
                if not g:
                    continue
                lines.append(f"| {c['agent']} | {c['defense']} | {c['approver']} | {key} | {g['episodes']} | "
                             f"{_pct(g['asr'])} | {_pct(g.get('asr_reduction'))} | {_pct(g['utility_under_attack'])} |")
        lines.append("")
    return lines


def _benign_sections(summary: dict[str, Any]) -> list[str]:
    lines = ["", "## Benign results per configuration", "",
              "| agent | defense | approver | episodes | utility | FPR (auto-deny) | friction (escalated) | "
              "unexpected friction | final block | result FP (sanitise/block) | approval recall | "
              "gateway p50 ms | gateway p95 ms |",
              "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for c in _sorted_configs(summary):
        o = c["overall"]
        if not o["episodes"]:
            continue
        lat = o["latency_ms"]
        lines.append(
            f"| {c['agent']} | {c['defense']} | {c['approver']} | {o['episodes']} | {_pct(o['utility'])} | "
            f"{_pct(o['fpr'])} | {_pct(o['friction'])} | {_pct(o['unexpected_friction'])} | "
            f"{_pct(o['final_block_rate'])} | {_pct(o['result_fp_rate'])} | {_pct(o['approval_recall'])} | "
            f"{_ms(lat['gateway_p50'])} | {_ms(lat['gateway_p95'])} |")
    lines += ["", "Rates are over benign tool calls (FPR, friction, final block) or inspected tool results "
              "(result FP); utility is over episodes. Gateway latency = decision + result inspection, "
              "excluding human wait.", "", "## By language", "",
              "| agent | defense | approver | lang | episodes | utility | FPR | friction | result FP | "
              "gateway p50 ms |", "|---|---|---|---|---:|---:|---:|---:|---:|---:|"]
    for c in _sorted_configs(summary):
        for lang, o in c["by_lang"].items():
            lines.append(f"| {c['agent']} | {c['defense']} | {c['approver']} | {lang} | {o['episodes']} | "
                         f"{_pct(o['utility'])} | {_pct(o['fpr'])} | {_pct(o['friction'])} | "
                         f"{_pct(o['result_fp_rate'])} | {_ms(o['latency_ms']['gateway_p50'])} |")
    lines += ["", "## By Arabic variety", "", "| agent | defense | approver | variety | episodes | utility | FPR | "
              "friction | result FP |", "|---|---|---|---|---:|---:|---:|---:|---:|"]
    for c in _sorted_configs(summary):
        for var, o in c["by_variety"].items():
            if var == "en":
                continue
            lines.append(f"| {c['agent']} | {c['defense']} | {c['approver']} | {var} | {o['episodes']} | "
                         f"{_pct(o['utility'])} | {_pct(o['fpr'])} | {_pct(o['friction'])} | "
                         f"{_pct(o['result_fp_rate'])} |")
    lines += ["", "## Why benign calls were stopped or escalated (reason codes)", ""]
    for c in _sorted_configs(summary):
        reasons = c["overall"]["blocking_reasons"]
        if reasons:
            joined = ", ".join(f"`{k}` x{v}" for k, v in reasons.items())
            lines.append(f"* {c['agent']} / {c['defense']} / {c['approver']}: {joined}")
    lines += ["", "## By task category (utility / friction)", "",
              "| agent | defense | approver | category | episodes | utility | FPR | friction |",
              "|---|---|---|---|---:|---:|---:|---:|"]
    for c in _sorted_configs(summary):
        for cat, o in c["by_category"].items():
            lines.append(f"| {c['agent']} | {c['defense']} | {c['approver']} | {cat} | {o['episodes']} | "
                         f"{_pct(o['utility'])} | {_pct(o['fpr'])} | {_pct(o['friction'])} |")
    return lines


# --------------------------------------------------------------------------- figures


def _style(ax: Any) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
    ax.tick_params(colors=INK_2, labelsize=9)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _barh(ax: Any, labels: list[str], values: list[float], title: str, *, pct: bool) -> None:
    import numpy as np

    y = np.arange(len(labels))
    ax.barh(y, values, height=0.6, color=SERIES[0], edgecolor=SURFACE, linewidth=2)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_title(title, color=INK, fontsize=10, loc="left")
    top = max(values + [0.0])
    ax.set_xlim(0, (1.0 if pct else top * 1.25) or 1.0)
    for yi, v in zip(y, values, strict=True):
        ax.text(v + (0.01 if pct else top * 0.02 + 1e-9), yi, f"{100 * v:.0f}%" if pct else f"{v:.1f}",
                va="center", fontsize=8, color=INK_2)
    _style(ax)
    if pct:
        ax.xaxis.set_major_formatter(lambda x, _p: f"{100 * x:.0f}%")


def write_figures(summary: dict[str, Any], fig_dir: Path) -> list[str]:
    """ASR per defense (attack runs), benign metrics per defense, friction by language and gateway latency.

    Returns the written paths.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    fig_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    all_configs = _sorted_configs(summary)
    if not all_configs:
        return written
    multi = len({x["approver"] for x in all_configs}) > 1

    def label(c: dict[str, Any]) -> str:
        return f"{c['defense']}\n({c['approver']})" if multi else c["defense"]

    attacked = [c for c in all_configs if c.get("attack")]
    if attacked:
        fig, axes = plt.subplots(1, 2, figsize=(9, 0.55 * len(attacked) + 1.8), facecolor=SURFACE, sharey=True)
        for ax, (key, title) in zip(axes, [("asr", "Attack success rate"),
                                           ("utility_under_attack", "Utility under attack")], strict=True):
            _barh(ax, [label(c) for c in attacked], [c["attack"][key] or 0.0 for c in attacked], title, pct=True)
        fig.tight_layout()
        path = fig_dir / "asr_by_defense.png"
        fig.savefig(path, dpi=150, facecolor=SURFACE)
        plt.close(fig)
        written.append(str(path))

    configs = [c for c in all_configs if c["overall"]["episodes"]]
    if not configs:
        return written
    labels = [label(c) for c in configs]

    fig, axes = plt.subplots(1, 3, figsize=(12, 0.55 * len(configs) + 1.8), facecolor=SURFACE, sharey=True)
    for ax, (key, title) in zip(axes, [("fpr", "Benign false-positive rate (auto-deny)"),
                                       ("friction", "Approval friction (escalated)"),
                                       ("utility", "Benign utility")], strict=True):
        _barh(ax, labels, [c["overall"][key] or 0.0 for c in configs], title, pct=True)
    fig.tight_layout()
    path = fig_dir / "benign_by_defense.png"
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    written.append(str(path))

    langs = sorted({lang for c in configs for lang in c["by_lang"]})
    if len(langs) > 1:
        fig, ax = plt.subplots(figsize=(8, 0.6 * len(configs) + 1.6), facecolor=SURFACE)
        y = np.arange(len(configs))
        h = 0.36
        for i, lang in enumerate(langs[:2]):
            vals = [(c["by_lang"].get(lang) or {}).get("friction") or 0.0 for c in configs]
            ax.barh(y + (i - 0.5) * h, vals, height=h, color=SERIES[i], edgecolor=SURFACE, linewidth=2,
                    label={"en": "English", "ar": "Arabic"}.get(lang, lang))
        ax.set_yticks(y, labels)
        ax.invert_yaxis()
        ax.set_xlim(0, 1)
        ax.xaxis.set_major_formatter(lambda x, _p: f"{100 * x:.0f}%")
        ax.set_title("Approval friction on benign calls, by language", color=INK, fontsize=10, loc="left")
        ax.legend(frameon=False, fontsize=9, labelcolor=INK_2, loc="lower right")
        _style(ax)
        fig.tight_layout()
        path = fig_dir / "friction_by_language.png"
        fig.savefig(path, dpi=150, facecolor=SURFACE)
        plt.close(fig)
        written.append(str(path))

    gated = [c for c in configs if c["overall"]["latency_ms"]["samples"]]
    if gated:
        fig, ax = plt.subplots(figsize=(8, 0.6 * len(gated) + 1.6), facecolor=SURFACE)
        y = np.arange(len(gated))
        h = 0.36
        glabels = [labels[configs.index(c)] for c in gated]
        for i, (k, name) in enumerate([("gateway_p50", "p50"), ("gateway_p95", "p95")]):
            vals = [c["overall"]["latency_ms"][k] or 0.0 for c in gated]
            ax.barh(y + (i - 0.5) * h, vals, height=h, color=SERIES[i], edgecolor=SURFACE, linewidth=2, label=name)
        ax.set_yticks(y, glabels)
        ax.invert_yaxis()
        ax.set_xlabel("ms per call (decision + result inspection, excl. human wait)", color=INK_2, fontsize=9)
        ax.set_title("Gateway latency per benign call", color=INK, fontsize=10, loc="left")
        ax.legend(frameon=False, fontsize=9, labelcolor=INK_2, loc="lower right")
        _style(ax)
        fig.tight_layout()
        path = fig_dir / "gateway_latency.png"
        fig.savefig(path, dpi=150, facecolor=SURFACE)
        plt.close(fig)
        written.append(str(path))
    return written


def write_reports(out_dir: Path, summary: dict[str, Any], meta: dict[str, Any], *, figures: bool = True) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    if figures:
        try:
            meta["figures"] = [str(Path(p).relative_to(out_dir)) for p in write_figures(summary, out_dir / "figures")]
        except ImportError:
            logger.warning("matplotlib not installed; skipping figures")
    payload = {"meta": meta, **summary}
    (out_dir / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "summary.md").write_text(render_markdown(summary, meta), encoding="utf-8")
