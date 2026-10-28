"""Latency added by the Mirsad gateway over HTTP.

    python -m bench.latency                         # 1,000 calls + 50 concurrent sessions
    python -m bench.latency --calls 200 --sessions 10

Starts the real FastAPI app (``mirsad.api.create_app``) with uvicorn in a background thread of this
process, on a free localhost port, with a temporary data directory and the default policy. The demo
workspace tools are registered as Python upstream tools over their own World. For the same list of
benign, read-only calls it measures

* ``direct``      calling the demo tool function in-process (``demo.world.call_tool``),
* ``sequential``  ``POST /v1/tools/{tool}/invoke`` one call at a time (keep-alive client),
* ``concurrent``  the same calls spread over N concurrent sessions,

and reports p50/p95/p99 of the HTTP round trip, of the gateway-reported time (decision + result
inspection) and of the *added* latency (HTTP round trip minus the direct call, paired per call).
Writes ``reports/bench/latency.json`` and ``reports/bench/figures/latency.png``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import platform
import secrets
import shlex
import socket
import statistics
import sys
import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from demo.world import TOOLS, World, call_tool

from bench.defenses import AGENT_ID, DEFAULT_POLICY_PATH
from bench.metrics import percentile
from bench.report import AXIS, GRID, INK, INK_2, SERIES, SURFACE

logger = logging.getLogger("mirsad.bench")

# Read-only calls that the default policy allows without escalation (benign traffic).
_CALL_CYCLE: list[tuple[str, dict[str, Any]]] = [
    ("list_emails", {"folder": "inbox", "limit": 5}),
    ("read_email", {"email_id": "E006"}),
    ("search_customers", {"query": "Riyadh", "limit": 5}),
    ("get_customer", {"customer_id": "C012"}),
    ("read_document", {"doc_id": "D005"}),
    ("read_email", {"email_id": "E017"}),
    ("list_documents", {}),
    ("get_customer", {"customer_id": "C045"}),
    ("read_document", {"doc_id": "D011"}),
    ("read_email", {"email_id": "E010"}),
]
CALLS_PER_SESSION_SEQ = 10


def benign_calls(n: int) -> list[tuple[str, dict[str, Any]]]:
    return [_CALL_CYCLE[i % len(_CALL_CYCLE)] for i in range(n)]


def stats(values: list[float]) -> dict[str, float | int | None]:
    return {
        "n": len(values),
        "p50": _r(percentile(values, 50)), "p95": _r(percentile(values, 95)), "p99": _r(percentile(values, 99)),
        "mean": _r(statistics.fmean(values)) if values else None,
        "max": _r(max(values)) if values else None,
    }


def _r(v: float | None) -> float | None:
    return None if v is None else round(v, 3)


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def build_bench_app(data_dir: Path, policy_path: Path) -> tuple[Any, str]:
    """The real Mirsad app with the demo workspace tools in-process and one registered agent."""
    from mirsad.adapters.upstreams import UpstreamManager
    from mirsad.api import create_app
    from mirsad.auth import create_agent
    from mirsad.config import Settings

    world = World()
    upstreams = UpstreamManager()
    for name, spec in TOOLS.items():
        upstreams.register_python(name, _bind(world, name), spec.description, spec.input_schema)
    settings = Settings(data_dir=data_dir, policy_path=policy_path,
                        upstreams_path=data_dir / "no-upstreams.yaml", secret_key=secrets.token_urlsafe(32),
                        enable_demo=False, approval_timeout_s=5.0, log_level="WARNING")
    app = create_app(settings, gateway_overrides={"upstreams": upstreams})
    _agent, api_key = create_agent(app.state.db, "bench-latency", "Bench latency agent", AGENT_ID)
    return app, api_key


class GatewayProcess:
    """The same app served by ``python -m bench.latency_server`` in a separate OS process.

    Keeps the load generator from competing with the gateway for the interpreter lock, which is closer
    to a real deployment where agents and the gateway run in different processes or machines.
    """

    def __init__(self, data_dir: Path, *, policy_path: Path = DEFAULT_POLICY_PATH) -> None:
        self.data_dir = data_dir
        self.policy_path = policy_path
        self.port = 0
        self.api_key = ""
        self._proc: Any = None
        self.report: dict[str, Any] = {}

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self, timeout_s: float = 60.0) -> None:
        import subprocess

        self.port = free_port()
        self._proc = subprocess.Popen(  # noqa: S603 - fixed module path, no shell
            [sys.executable, "-m", "bench.latency_server", "--data-dir", str(self.data_dir),
             "--policy", str(self.policy_path), "--port", str(self.port)],
            stdout=subprocess.PIPE, text=True)
        line = self._proc.stdout.readline()
        if not line:
            raise RuntimeError("latency server did not start")
        self.api_key = json.loads(line)["api_key"]
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                if httpx.get(f"{self.base_url}/healthz", timeout=1).status_code == 200:
                    return
            except httpx.HTTPError:
                time.sleep(0.1)
        raise RuntimeError("latency server not healthy")

    def stop(self) -> None:
        import signal

        if self._proc is not None:
            self._proc.send_signal(signal.SIGINT)
            self._proc.wait(timeout=30)
            report = self.data_dir / "latency-server-report.json"
            if report.exists():
                self.report = json.loads(report.read_text(encoding="utf-8"))

    def __enter__(self) -> GatewayProcess:
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()


class GatewayServer:
    """The real Mirsad app served by uvicorn in a background thread (temp data dir, demo tools)."""

    def __init__(self, data_dir: Path, *, policy_path: Path = DEFAULT_POLICY_PATH) -> None:
        self.data_dir = data_dir
        self.policy_path = policy_path
        self.port = 0
        self.api_key = ""
        self.app: Any = None
        self._server: Any = None
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self, timeout_s: float = 30.0) -> None:
        import uvicorn

        self.app, self.api_key = build_bench_app(self.data_dir, self.policy_path)
        self.port = free_port()
        config = uvicorn.Config(self.app, host="127.0.0.1", port=self.port, log_level="warning",
                                access_log=False, lifespan="on")
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, name="mirsad-latency-server", daemon=True)
        self._thread.start()
        deadline = time.monotonic() + timeout_s
        while not self._server.started:
            if time.monotonic() > deadline or not self._thread.is_alive():
                raise RuntimeError("uvicorn did not start")
            time.sleep(0.05)
        logger.info("gateway listening on %s", self.base_url)

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=15)

    def __enter__(self) -> GatewayServer:
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()


def _bind(world: World, name: str) -> Any:
    def tool(**kwargs: Any) -> Any:
        return call_tool(world, name, kwargs)

    return tool


def measure_direct(calls: list[tuple[str, dict[str, Any]]]) -> list[float]:
    world = World()
    out = []
    for tool, args in calls:
        t0 = time.perf_counter()
        call_tool(world, tool, dict(args))
        out.append((time.perf_counter() - t0) * 1000)
    return out


def _gateway_ms(body: dict[str, Any]) -> float:
    dec = body.get("decision") or {}
    res = body.get("result") or {}
    return float(dec.get("latency_ms") or 0.0) + float(res.get("latency_ms") or 0.0)


def measure_sequential(server: GatewayServer, calls: list[tuple[str, dict[str, Any]]], *,
                       tag: str) -> dict[str, Any]:
    http_ms: list[float] = []
    gw_ms: list[float] = []
    non_allow = errors = 0
    headers = {"Authorization": f"Bearer {server.api_key}"}
    t_start = time.perf_counter()
    with httpx.Client(base_url=server.base_url, headers=headers, timeout=60.0) as client:
        for i, (tool, args) in enumerate(calls):
            payload = {"session_id": f"{tag}-{i // CALLS_PER_SESSION_SEQ}", "arguments": args}
            t0 = time.perf_counter()
            resp = client.post(f"/v1/tools/{tool}/invoke", json=payload)
            http_ms.append((time.perf_counter() - t0) * 1000)
            if resp.status_code != 200:
                errors += 1
                continue
            body = resp.json()
            gw_ms.append(_gateway_ms(body))
            if (body.get("decision") or {}).get("action") != "allow":
                non_allow += 1
    wall = time.perf_counter() - t_start
    return {"http": http_ms, "gateway": gw_ms, "non_allow": non_allow, "errors": errors, "wall_s": wall}


async def _concurrent(server: GatewayServer, calls: list[tuple[str, dict[str, Any]]], sessions: int) -> dict[str, Any]:
    http_ms: list[float | None] = [None] * len(calls)
    gw_ms: list[float] = []
    counters = {"non_allow": 0, "errors": 0}
    headers = {"Authorization": f"Bearer {server.api_key}"}
    limits = httpx.Limits(max_connections=sessions + 5, max_keepalive_connections=sessions + 5)
    async with httpx.AsyncClient(base_url=server.base_url, headers=headers, timeout=120.0, limits=limits) as client:

        async def session(s: int) -> None:
            for i in range(s, len(calls), sessions):
                tool, args = calls[i]
                t0 = time.perf_counter()
                resp = await client.post(f"/v1/tools/{tool}/invoke", json={"session_id": f"conc-{s}", "arguments": args})
                http_ms[i] = (time.perf_counter() - t0) * 1000
                if resp.status_code != 200:
                    counters["errors"] += 1
                    continue
                body = resp.json()
                gw_ms.append(_gateway_ms(body))
                if (body.get("decision") or {}).get("action") != "allow":
                    counters["non_allow"] += 1

        t_start = time.perf_counter()
        await asyncio.gather(*(session(s) for s in range(sessions)))
        wall = time.perf_counter() - t_start
    return {"http": [v for v in http_ms if v is not None], "http_by_index": http_ms, "gateway": gw_ms,
            "wall_s": wall, **counters}


def _paired_added(http: list[float | None], direct: list[float]) -> list[float]:
    return [h - d for h, d in zip(http, direct, strict=False) if h is not None]


def run_latency(*, calls: int = 1000, sessions: int = 50, warmup: int = 50,
                policy_path: Path = DEFAULT_POLICY_PATH, server_process: bool = False) -> dict[str, Any]:
    plan = benign_calls(calls)
    direct = measure_direct(plan)
    with tempfile.TemporaryDirectory(prefix="mirsad-latency-") as tmp:
        server_cls = GatewayProcess if server_process else GatewayServer
        srv = server_cls(Path(tmp), policy_path=policy_path)
        with srv:
            measure_sequential(srv, benign_calls(warmup), tag="warmup")
            seq = measure_sequential(srv, plan, tag="seq")
            conc = asyncio.run(_concurrent(srv, plan, sessions))
            if not server_process:
                det_mode = getattr(srv.app.state.detector, "mode", "unknown")
                audit_ok = bool(srv.app.state.audit.verify().ok)
        if server_process:
            det_mode = srv.report.get("detector_mode", "unknown")
            audit_ok = bool(srv.report.get("audit_ok"))
    return {
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "calls": calls, "warmup_calls": warmup, "concurrent_sessions": sessions,
        "policy": str(Path(policy_path).name), "detector_mode": det_mode,
        "python": platform.python_version(), "platform": platform.platform(), "machine": platform.machine(),
        "call_mix": sorted({t for t, _ in _CALL_CYCLE}),
        "direct_ms": stats(direct),
        "sequential": {
            "http_ms": stats(seq["http"]), "gateway_ms": stats(seq["gateway"]),
            "added_ms": stats(_paired_added(seq["http"], direct)),
            "non_allow": seq["non_allow"], "http_errors": seq["errors"],
            "throughput_rps": round(len(seq["http"]) / seq["wall_s"], 1) if seq["wall_s"] else None,
        },
        "concurrent": {
            "http_ms": stats(conc["http"]), "gateway_ms": stats(conc["gateway"]),
            "added_ms": stats(_paired_added(conc["http_by_index"], direct)),
            "non_allow": conc["non_allow"], "http_errors": conc["errors"],
            "wall_s": round(conc["wall_s"], 3),
            "throughput_rps": round(len(conc["http"]) / conc["wall_s"], 1) if conc["wall_s"] else None,
        },
        "audit_chain_ok": audit_ok,
        "server": "separate process" if server_process else "in-process thread",
        "_raw": {"seq_added": _paired_added(seq["http"], direct),
                 "conc_added": _paired_added(conc["http_by_index"], direct)},
    }


def write_figure(result: dict[str, Any], path: Path) -> None:
    """ECDF of added latency per call: sequential vs concurrent sessions."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4.2), facecolor=SURFACE)
    series = [("Sequential (1 client)", result["_raw"]["seq_added"]),
              (f"{result['concurrent_sessions']} concurrent sessions", result["_raw"]["conc_added"])]
    for i, (label, vals) in enumerate(series):
        data = sorted(max(v, 1e-3) for v in vals)
        if not data:
            continue
        ys = [(k + 1) / len(data) for k in range(len(data))]
        ax.plot(data, ys, color=SERIES[i], linewidth=2, label=label)
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(lambda x, _p: f"{x:g}")
    ax.xaxis.set_minor_formatter(lambda x, _p: f"{x:g}" if f"{x:g}"[0] in "25" else "")
    ax.tick_params(axis="x", which="minor", colors=INK_2, labelsize=8)
    ax.set_xlabel("added latency per call, ms (HTTP invoke minus direct tool call, log scale)",
                  color=INK_2, fontsize=9)
    ax.set_ylabel("share of calls", color=INK_2, fontsize=9)
    ax.yaxis.set_major_formatter(lambda y, _p: f"{100 * y:.0f}%")
    ax.set_title(f"Mirsad gateway added latency ({result['calls']} benign calls)", color=INK, fontsize=10,
                 loc="left")
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
    ax.tick_params(colors=INK_2, labelsize=9)
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK_2, loc="lower right")
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    p = argparse.ArgumentParser(prog="python -m bench.latency", description="Measure Mirsad's added latency.")
    p.add_argument("--calls", type=int, default=1000)
    p.add_argument("--sessions", type=int, default=50)
    p.add_argument("--warmup", type=int, default=50)
    p.add_argument("--policy", default=str(DEFAULT_POLICY_PATH))
    p.add_argument("--out", default="reports/bench/latency.json")
    p.add_argument("--figure", default="reports/bench/figures/latency.png")
    p.add_argument("--no-figure", action="store_true")
    p.add_argument("--server-process", action="store_true",
                   help="run the gateway in its own process instead of a thread of the load generator")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.WARNING)
    result = run_latency(calls=args.calls, sessions=args.sessions, warmup=args.warmup, policy_path=Path(args.policy),
                         server_process=args.server_process)
    result["command"] = "python -m bench.latency " + " ".join(shlex.quote(a) for a in argv)
    if not args.no_figure:
        write_figure(result, Path(args.figure))
        result["figure"] = args.figure
    raw = result.pop("_raw")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    seq, conc = result["sequential"], result["concurrent"]
    sys.stdout.write(
        f"direct p50 {result['direct_ms']['p50']} ms | sequential HTTP p50/p95/p99 "
        f"{seq['http_ms']['p50']}/{seq['http_ms']['p95']}/{seq['http_ms']['p99']} ms, added p50/p95/p99 "
        f"{seq['added_ms']['p50']}/{seq['added_ms']['p95']}/{seq['added_ms']['p99']} ms | "
        f"{result['concurrent_sessions']} sessions added p50/p95/p99 {conc['added_ms']['p50']}/"
        f"{conc['added_ms']['p95']}/{conc['added_ms']['p99']} ms, {conc['throughput_rps']} req/s, "
        f"errors {conc['http_errors']} | samples {len(raw['seq_added'])}+{len(raw['conc_added'])}\n")
    return 0 if not (seq["http_errors"] or conc["http_errors"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
