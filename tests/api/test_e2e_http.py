"""End-to-end over real HTTP with every real module (no fakes).

Mirrors what an operator does: ``mirsad init --demo`` on an empty data directory, then
``mirsad serve`` with ``MIRSAD_ENABLE_DEMO=true`` (the app built by the real ``serve`` command is
run by an in-process uvicorn server on a free port), then plain HTTP calls: admin login, stats,
agent creation, the demo workspace tools checked against ``configs/policies/default.yaml``, a
human approval sent from a *second process* while the agent's invoke call is waiting, audit
verification, deterministic replay, CSV export and the OpenAPI document.

Only benign tool calls are made; no detector test content is needed here.
"""

from __future__ import annotations

import csv
import importlib
import io
import os
import re
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from click.testing import CliRunner


def _available(*modules: str) -> bool:
    try:
        for m in modules:
            importlib.import_module(m)
        return hasattr(importlib.import_module("mirsad.detector"), "InjectionDetector")
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _available("mirsad.policy", "mirsad.taint", "mirsad.detector", "mirsad.adapters.upstreams",
                   "demo.workspace_server", "uvicorn"),
    reason="real modules of other areas not available")

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = ROOT / "configs" / "policies" / "default.yaml"
ADMIN_PASSWORD = "e2e-admin-password-4821"  # test-only value for a throwaway data dir
POLICY_AGENT = "email-crm-assistant"
DEMO_TOOLS = {"list_emails", "read_email", "send_email", "search_customers", "get_customer", "export_customers",
              "update_customer_note", "delete_customer", "fetch_url", "list_documents", "read_document",
              "transfer_funds"}
# Spec section 8 endpoints that must appear in /openapi.json (the MCP mount and static routes are not in it).
SPEC_PATHS = {
    "/healthz": {"get"}, "/api/auth/login": {"post"}, "/api/auth/me": {"get"},
    "/v1/guard/tool-call": {"post"}, "/v1/guard/tool-result": {"post"}, "/v1/tools/{tool}/invoke": {"post"},
    "/v1/tools": {"get"}, "/v1/chat/completions": {"post"}, "/api/detector/scan": {"post"},
    "/api/approvals": {"get"}, "/api/approvals/{approval_id}": {"get"},
    "/api/approvals/{approval_id}/decision": {"post"}, "/api/stream": {"get"}, "/api/push/subscribe": {"post"},
    "/api/push/vapid": {"get"}, "/api/audit/events": {"get"}, "/api/audit/events/{seq}": {"get"},
    "/api/audit/verify": {"post"}, "/api/audit/events/{seq}/replay": {"post"}, "/api/audit/export": {"get"},
    "/api/stats/overview": {"get"}, "/api/stats/timeseries": {"get"}, "/api/policies": {"get", "put"},
    "/api/policies/{version}": {"get"}, "/api/policies/validate": {"post"}, "/api/agents": {"get", "post"},
    "/api/agents/{agent_id}/rotate-key": {"post"}, "/api/agents/{agent_id}": {"patch", "delete"},
    "/api/users": {"get", "post"}, "/api/users/{username}": {"patch", "delete"}, "/api/tools": {"get"},
    "/api/demo/chat": {"post"}, "/api/demo/reset": {"post"}, "/api/demo/state": {"get"},
    "/api/demo/scenarios": {"get"},
}
# Runs in a separate interpreter: the approver is a different process from the waiting agent.
APPROVER_SCRIPT = """
import os, sys, httpx
base, approval_id = sys.argv[1], sys.argv[2]
r = httpx.post(f"{base}/api/approvals/{approval_id}/decision", timeout=30,
               headers={"Authorization": "Bearer " + os.environ["E2E_APPROVER_TOKEN"]},
               json={"approve": True, "note": "expected supplier order"})
print(r.status_code, r.json().get("status"), r.json().get("decided_by"))
"""


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="module")
def e2e(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, Any]]:
    import uvicorn
    from demo.workspace_server import WORLD

    from mirsad import cli

    work = tmp_path_factory.mktemp("e2e")
    port = _free_port()
    env = {"MIRSAD_DATA_DIR": str(work / "data"), "MIRSAD_ENABLE_DEMO": "true",
           "MIRSAD_POLICY_PATH": str(DEFAULT_POLICY),
           # absent on purpose: in demo mode the in-process demo workspace is the upstream
           "MIRSAD_UPSTREAMS_PATH": str(work / "absent-upstreams.yaml"),
           "MIRSAD_LOG_LEVEL": "WARNING"}
    with pytest.MonkeyPatch.context() as mp:
        for key in [k for k in os.environ if k.startswith("MIRSAD_")]:
            mp.delenv(key)
        for key, value in env.items():
            mp.setenv(key, value)
        mp.chdir(work)  # Settings also reads ./.env; keep the developer's one out of the test
        WORLD.reset()
        runner = CliRunner()

        init = runner.invoke(cli.main, ["init", "--demo", "--admin-password", ADMIN_PASSWORD],
                             catch_exceptions=False)
        assert init.exit_code == 0, init.output
        assert ADMIN_PASSWORD not in init.output and "mk_" not in init.output  # secrets only in the file

        captured: dict[str, Any] = {}
        mp.setattr(uvicorn, "run", lambda app, **kw: captured.update(app=app, **kw))
        serve = runner.invoke(cli.main, ["serve", "--port", str(port)], catch_exceptions=False)
        assert serve.exit_code == 0, serve.output
        app = captured["app"]
        assert captured["port"] == port and app.state.settings.enable_demo is True

        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
        thread = threading.Thread(target=server.run, name="mirsad-e2e-server", daemon=True)
        thread.start()
        deadline = time.time() + 30
        while not server.started and thread.is_alive() and time.time() < deadline:
            time.sleep(0.05)
        assert server.started, "uvicorn did not start"
        base = f"http://127.0.0.1:{port}"
        client = httpx.Client(base_url=base, timeout=60)
        try:
            yield {"base": base, "client": client, "app": app, "world": WORLD, "data_dir": work / "data",
                   "init_output": init.output}
        finally:
            client.close()
            server.should_exit = True
            thread.join(timeout=30)
            WORLD.reset()


def _login(e2e: dict[str, Any]) -> dict[str, str]:
    r = e2e["client"].post("/api/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _new_agent(e2e: dict[str, Any], admin: dict[str, str], agent_id: str) -> dict[str, str]:
    r = e2e["client"].post("/api/agents", headers=admin,
                           json={"id": agent_id, "name": f"E2E {agent_id}", "policy_agent_id": POLICY_AGENT})
    assert r.status_code == 201, r.text
    assert r.json()["warnings"] == [] and r.json()["api_key"].startswith("mk_")
    return {"Authorization": f"Bearer {r.json()['api_key']}"}


def _invoke(e2e: dict[str, Any], agent: dict[str, str], tool: str, args: dict[str, Any], session: str,
            client: httpx.Client | None = None, call_id: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"session_id": session, "arguments": args}
    if call_id:
        body["call_id"] = call_id
    r = (client or e2e["client"]).post(f"/v1/tools/{tool}/invoke", headers=agent, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _codes(decision: dict[str, Any]) -> list[str]:
    return [r["code"] for r in decision["reasons"]]


def test_init_demo_then_login_and_overview(e2e):
    c = e2e["client"]
    assert c.get("/healthz").json()["status"] == "ok"
    creds = e2e["data_dir"] / "credentials.txt"
    assert str(creds) in e2e["init_output"] and (creds.stat().st_mode & 0o777) == 0o600

    admin = _login(e2e)
    me = c.get("/api/auth/me", headers=admin).json()
    assert me == {"username": "admin", "role": "admin", "display_name": "Administrator", "lang": "en"}
    overview = c.get("/api/stats/overview", headers=admin)
    assert overview.status_code == 200
    body = overview.json()
    assert body["audit_ok"] is True and body["approvals_pending"] == 0
    assert {"total_calls", "allowed", "denied", "approvals_required", "injections_detected", "results_sanitized",
            "median_latency_ms", "p95_latency_ms", "by_tool", "by_layer"} <= body.keys()

    # the demo agent created by `init --demo` authenticates with the key from credentials.txt
    match = re.search(r"id=demo-agent\s+policy_agent=email-crm-assistant\s+api_key=(mk_\S+)", creds.read_text())
    assert match, "demo agent key missing from credentials.txt"
    tools = c.get("/v1/tools", headers={"X-Mirsad-Key": match.group(1)})
    assert tools.status_code == 200 and {t["name"] for t in tools.json()} == DEMO_TOOLS
    # the policy that `init` stored is the active one the server enforces
    policies = c.get("/api/policies", headers=admin).json()
    assert policies["active"]["yaml_text"] == DEFAULT_POLICY.read_text(encoding="utf-8")


def test_agent_tool_calls_follow_the_default_policy(e2e):
    c, world = e2e["client"], e2e["world"]
    admin = _login(e2e)
    agent = _new_agent(e2e, admin, "e2e-policy-agent")

    tools = {t["name"]: t for t in c.get("/v1/tools", headers=agent).json()}
    assert set(tools) == DEMO_TOOLS
    assert tools["send_email"]["profile"]["sink"] == "dynamic" and tools["read_email"]["profile"]["trust"] == "untrusted"
    assert tools["send_email"]["input_schema"]["properties"].keys() >= {"to", "subject", "body"}

    listing = _invoke(e2e, agent, "list_emails", {"limit": 3}, "e2e-read")
    assert listing["decision"]["action"] == "allow" and listing["error"] is None
    result = listing["result"]
    assert result["trust"] == "untrusted" and result["action"] in ("pass", "flag")
    assert isinstance(result["structured"], list) and 1 <= len(result["structured"]) <= 3
    email_id = result["structured"][0]["id"]

    read = _invoke(e2e, agent, "read_email", {"email_id": email_id}, "e2e-read")
    assert read["decision"]["action"] == "allow" and read["result"]["structured"]["id"] == email_id

    search = _invoke(e2e, agent, "search_customers", {"query": "", "limit": 3}, "e2e-crm")
    assert search["decision"]["action"] == "allow"
    assert search["result"]["sensitivity"] == "confidential" and len(search["result"]["structured"]) <= 3

    too_many = _invoke(e2e, agent, "search_customers", {"query": "", "limit": 51}, "e2e-crm")
    assert too_many["decision"]["action"] == "deny" and too_many["result"] is None
    assert "CONSTRAINT_VIOLATION" in _codes(too_many["decision"])

    internal = _invoke(e2e, agent, "send_email", {"to": "sales@najd-trading.example", "subject": "Weekly summary",
                                                  "body": "The weekly summary is attached."}, "e2e-internal")
    assert internal["decision"]["action"] == "allow", internal["decision"]
    assert internal["decision"]["sink"] == "internal"
    assert any(m["to"] == "sales@najd-trading.example" for m in world.outbox)

    exports_before = len(world.exports)
    export = _invoke(e2e, agent, "export_customers", {"count": 200}, "e2e-export")
    decision = export["decision"]
    assert decision["action"] == "deny" and export["result"] is None and export["error"]
    violation = next(r for r in decision["reasons"] if r["code"] == "CONSTRAINT_VIOLATION")
    assert violation["layer"] == "policy" and violation["evidence"]["param"] == "count"
    assert violation["message_ar"]  # bilingual explanation for approvers/admins
    assert len(world.exports) == exports_before  # the tool never ran

    # decisions only (wait=false): approval-always and amount limits from the same policy
    delete = c.post("/v1/guard/tool-call", headers=agent, json={
        "session_id": "e2e-guard", "tool": "delete_customer", "arguments": {"customer_id": "C001"}, "wait": False})
    assert delete.json()["action"] == "require_approval" and "APPROVAL_ALWAYS" in _codes(delete.json())
    transfer = c.post("/v1/guard/tool-call", headers=agent, json={
        "session_id": "e2e-guard", "tool": "transfer_funds", "wait": False,
        "arguments": {"to_iban": "SA4420000001234567891234", "amount_sar": 20000}})
    assert transfer.json()["action"] == "deny"
    unknown = c.post("/v1/guard/tool-call", headers=agent, json={
        "session_id": "e2e-guard", "tool": "shell_exec", "arguments": {}, "wait": False})
    assert unknown.json()["action"] == "deny"


def test_external_email_waits_for_an_approval_sent_from_a_second_process(e2e):
    c, world = e2e["client"], e2e["world"]
    admin = _login(e2e)
    agent = _new_agent(e2e, admin, "e2e-approval-agent")
    args = {"to": "orders@gulf-supplies.example", "subject": "Purchase order", "body": "Please confirm the order."}
    outcome: dict[str, Any] = {}

    def agent_call() -> None:
        with httpx.Client(base_url=e2e["base"], timeout=90) as own:
            try:
                outcome["response"] = _invoke(e2e, agent, "send_email", args, "e2e-approval", client=own,
                                              call_id="call_e2e_external")
            except BaseException as exc:  # surfaced by the main thread
                outcome["error"] = exc

    waiting = threading.Thread(target=agent_call, name="e2e-waiting-agent")
    waiting.start()
    record = None
    deadline = time.time() + 30
    while record is None and time.time() < deadline and waiting.is_alive():
        pending = c.get("/api/approvals", headers=admin, params={"status": "pending"}).json()
        record = next((p for p in pending if p["call_id"] == "call_e2e_external"), None)
        if record is None:
            time.sleep(0.1)
    assert record is not None, outcome
    assert waiting.is_alive(), "the invoke call must still be waiting for the human"
    assert record["tool"] == "send_email" and record["arguments"]["to"] == args["to"]
    assert record["summary_en"] and record["summary_ar"]
    assert "CONSTRAINT_VIOLATION" in _codes(record["decision"])
    assert not any(m["to"] == args["to"] for m in world.outbox)  # nothing sent before the decision

    token = _login(e2e)["Authorization"].removeprefix("Bearer ")
    approver = subprocess.run([sys.executable, "-I", "-c", APPROVER_SCRIPT, e2e["base"], record["id"]],
                              env={**os.environ, "E2E_APPROVER_TOKEN": token}, capture_output=True, text=True,
                              timeout=120)
    assert approver.returncode == 0, approver.stderr
    assert approver.stdout.split() == ["200", "approved", "admin"]

    waiting.join(timeout=60)
    assert not waiting.is_alive() and "error" not in outcome, outcome
    response = outcome["response"]
    decision = response["decision"]
    assert decision["action"] == "allow" and decision["approval_status"] == "approved"
    assert decision["approval_id"] == record["id"]
    assert {"CONSTRAINT_VIOLATION", "APPROVED_BY_HUMAN"} <= set(_codes(decision))
    assert decision["latency_ms"] < 5_000  # excludes the human wait
    assert response["result"] is not None and response["error"] is None
    assert any(m["to"] == args["to"] for m in world.outbox)

    stored = c.get(f"/api/approvals/{record['id']}", headers=admin).json()
    assert stored["status"] == "approved" and stored["decided_by"] == "admin"
    assert stored["note"] == "expected supplier order"
    # audited exactly once, by the gateway that was waiting
    events = c.get("/api/audit/events", headers=admin,
                   params={"event_type": "approval.decided", "call_id": "call_e2e_external"}).json()
    assert events["total"] == 1 and events["items"][0]["payload"]["source"] == "gateway"
    assert c.get("/api/approvals", headers=admin, params={"status": ""}).status_code == 200


def test_audit_verify_replay_and_csv_export(e2e):
    c = e2e["client"]
    admin = _login(e2e)
    agent = _new_agent(e2e, admin, "e2e-audit-agent")
    denied = _invoke(e2e, agent, "export_customers", {"count": 200}, "e2e-audit")
    allowed = _invoke(e2e, agent, "get_customer", {"customer_id": "C001"}, "e2e-audit")

    verify = c.post("/api/audit/verify", headers=admin).json()
    assert verify["ok"] is True and verify["checked"] >= 10 and verify["first_bad_seq"] is None

    replay = c.post(f"/api/audit/events/{denied['decision']['audit_seq']}/replay", headers=admin).json()
    assert replay["event_type"] == "tool_call.decision"
    assert replay["original_action"] == replay["replayed_action"] == "deny" and replay["match"] is True
    assert replay["details"]["reasons_match"] is True

    inspection = c.post(f"/api/audit/events/{allowed['result']['audit_seq']}/replay", headers=admin).json()
    assert inspection["event_type"] == "tool_result.inspection" and inspection["match"] is True

    # every decision recorded so far in this run replays to the same action
    decisions = c.get("/api/audit/events", headers=admin,
                      params={"event_type": "tool_call.decision", "limit": 1000}).json()
    assert decisions["total"] >= 2
    mismatches = [e["seq"] for e in decisions["items"]
                  if not c.post(f"/api/audit/events/{e['seq']}/replay", headers=admin).json()["match"]]
    assert mismatches == []

    export = c.get("/api/audit/export", headers=admin, params={"format": "csv"})
    assert export.status_code == 200 and export.headers["content-type"].startswith("text/csv")
    assert re.match(r'attachment; filename="mirsad-audit-\d{8}T\d{6}Z\.csv"', export.headers["content-disposition"])
    rows = list(csv.DictReader(io.StringIO(export.text)))
    assert {"seq", "event_type", "tool", "action", "prev_hash", "hash"} <= set(rows[0])
    seqs = [int(r["seq"]) for r in rows]
    assert seqs == list(range(1, len(rows) + 1))  # complete chain, oldest first
    assert any(r["event_type"] == "tool_call.decision" and r["tool"] == "export_customers" and r["action"] == "deny"
               for r in rows)
    assert any(r["event_type"] == "audit.verified" for r in rows)

    filtered = c.get("/api/audit/export", headers=admin, params={"format": "csv", "action": "deny"})
    assert all(r["action"] == "deny" for r in csv.DictReader(io.StringIO(filtered.text)))

    overview = c.get("/api/stats/overview", headers=admin).json()
    assert overview["total_calls"] == decisions["total"] and overview["denied"] >= 1 and overview["audit_ok"] is True


def test_openapi_document_covers_the_spec_routes(e2e):
    spec = e2e["client"].get("/openapi.json")
    assert spec.status_code == 200
    paths = spec.json()["paths"]
    missing = {p: sorted(m - set(paths.get(p, {}))) for p, m in SPEC_PATHS.items() if m - set(paths.get(p, {}))}
    assert missing == {}
    operations = sum(1 for item in paths.values() for m in item if m in ("get", "post", "put", "patch", "delete"))
    assert operations >= sum(len(m) for m in SPEC_PATHS.values())
    assert e2e["client"].get("/docs").status_code == 200
