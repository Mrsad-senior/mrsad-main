"""Gateway process for ``python -m bench.latency --server-process``.

Builds the same app as the in-process benchmark, prints ``{"api_key": ...}`` on stdout, serves until
interrupted, then writes ``latency-server-report.json`` (detector mode, audit verification) in the data dir.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import uvicorn

from bench.latency import build_bench_app


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", required=True)
    p.add_argument("--policy", required=True)
    p.add_argument("--port", type=int, required=True)
    args = p.parse_args()
    data_dir = Path(args.data_dir)
    app, api_key = build_bench_app(data_dir, Path(args.policy))
    sys.stdout.write(json.dumps({"api_key": api_key}) + "\n")
    sys.stdout.flush()
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning", access_log=False)
    report = {"detector_mode": getattr(app.state.detector, "mode", "unknown"),
              "audit_ok": bool(app.state.audit.verify().ok)}
    (data_dir / "latency-server-report.json").write_text(json.dumps(report), encoding="utf-8")


if __name__ == "__main__":
    main()
