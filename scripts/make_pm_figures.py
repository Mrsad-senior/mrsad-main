"""Draw the Gantt chart (docs/figures/gantt.png) from docs/pm/plan.yaml."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import yaml  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PALETTE = ["#0b1f3a", "#0f766e", "#2563eb", "#7c3aed", "#be123c", "#b45309", "#475569"]


def main() -> None:
    plan = yaml.safe_load((ROOT / "docs/pm/plan.yaml").read_text(encoding="utf-8"))
    rows: list[tuple[str, date, date, str, str]] = []
    for i, phase in enumerate(plan["phases"]):
        for t in phase["tasks"]:
            rows.append((f'{t["id"]}  {t["name"]}', t["start"], t["end"], PALETTE[i % len(PALETTE)], t["owner"]))
    fig, ax = plt.subplots(figsize=(13, 0.36 * len(rows) + 2.2), dpi=170)
    for y, (_label, start, end, color, owner) in enumerate(rows):
        ax.barh(y, (end - start).days, left=mdates.date2num(start), height=0.62, color=color, alpha=0.92)
        ax.text(mdates.date2num(end) + 2, y, owner, va="center", fontsize=7.5, color="#334155")
    ax.set_yticks(range(len(rows)), [r[0] for r in rows], fontsize=8.2)
    ax.invert_yaxis()
    for m in plan["milestones"]:
        x = mdates.date2num(m["date"])
        ax.axvline(x, color="#dc2626", lw=0.8, ls="--", alpha=0.6)
        ax.plot(x, -0.9, marker="D", color="#dc2626", ms=6, clip_on=False)
        ax.text(x, -1.5, m["id"], ha="center", fontsize=8, color="#dc2626", fontweight="bold")
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    ax.set_xlim(mdates.date2num(date(2026, 8, 25)), mdates.date2num(date(2027, 6, 5)))
    ax.axvspan(mdates.date2num(date(2026, 12, 25)), mdates.date2num(date(2027, 1, 9)), color="#e2e8f0", alpha=0.7)
    ax.text(mdates.date2num(date(2027, 1, 1)), len(rows) - 0.3, "break", ha="center", fontsize=7, color="#64748b")
    ax.grid(axis="x", color="#e2e8f0")
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=PALETTE[i % len(PALETTE)]) for i in range(len(plan["phases"]))]
    ax.legend(handles, [p["name"] for p in plan["phases"]], loc="lower left", fontsize=7.5, ncol=4, frameon=False,
              bbox_to_anchor=(0, -0.09))
    ax.set_title("Mirsad project schedule (Senior Project I: Fall 2026 · Senior Project II: Spring 2027)",
                 fontsize=11, fontweight="bold", color="#0b1f3a", pad=26)
    fig.tight_layout()
    out = ROOT / "docs/figures/gantt.png"
    fig.savefig(out, bbox_inches="tight")
    print("wrote", out, "tasks:", len(rows), "days:", (date(2027, 5, 20) - date(2026, 9, 1)) // timedelta(days=1))


if __name__ == "__main__":
    main()
