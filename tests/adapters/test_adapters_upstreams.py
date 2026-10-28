"""UpstreamManager: configuration, in-process / stdio / HTTP MCP upstreams, Python tools."""

from __future__ import annotations

import sys
from pathlib import Path

import mcp_types as types
import pytest
from adapters_testkit import make_workspace_server, serve_asgi
from mcp.server import Server

from mirsad.adapters import upstreams as upstreams_mod
from mirsad.adapters.upstreams import (
    UpstreamConfig,
    UpstreamError,
    UpstreamManager,
    call_result_to_tool_result,
    load_object,
    value_to_tool_result,
)
from mirsad.models import ToolCall, ToolResult

HERE = Path(__file__).parent
INPROC = {
    "upstreams": [
        {"name": "ws", "transport": "inprocess", "target": "adapters_testkit:make_workspace_server"}
    ]
}


def tc(tool: str, **arguments: object) -> ToolCall:
    return ToolCall(session_id="s1", agent_id="email-crm-assistant", tool=tool, arguments=arguments)


# --------------------------------------------------------------------------- configuration


@pytest.mark.parametrize(
    "entry",
    [
        {"name": "a", "transport": "inprocess"},
        {"name": "a", "transport": "inprocess", "target": "no_colon_here"},
        {"name": "a", "transport": "stdio", "command": []},
        {"name": "a", "transport": "http", "url": "ftp://x"},
        {"name": "a b", "transport": "http", "url": "http://x/mcp"},
        {"name": "a", "transport": "carrier-pigeon"},
        {"name": "a", "transport": "http", "url": "http://x/mcp", "unknown_key": 1},
        {"name": "a", "transport": "http", "url": "http://x/mcp", "tool_prefix": "bad prefix"},
    ],
)
def test_invalid_upstream_entries_are_rejected(entry: dict) -> None:
    with pytest.raises(UpstreamError):
        UpstreamManager.from_dict({"upstreams": [entry]})


def test_duplicate_and_reserved_names_are_rejected() -> None:
    dup = {"name": "x", "transport": "http", "url": "http://h/mcp"}
    with pytest.raises(UpstreamError, match="duplicate"):
        UpstreamManager.from_dict({"upstreams": [dup, dup]})
    with pytest.raises(UpstreamError):
        UpstreamManager.from_dict({"upstreams": [{**dup, "name": "python"}]})


def test_yaml_parsing_and_env_expansion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CRM_TOKEN", "s3cr3t")
    mgr = UpstreamManager.from_yaml(
        """
upstreams:
  - name: crm
    transport: http
    url: http://127.0.0.1:9000/mcp
    headers: {Authorization: "Bearer ${CRM_TOKEN}"}
  - name: files
    transport: stdio
    command: [python, -m, demo.workspace_server]
    enabled: false
"""
    )
    assert [s["name"] for s in mgr.status()] == ["crm"]  # disabled entries are skipped
    assert mgr._configs[0].headers["Authorization"] == "Bearer s3cr3t"
    with pytest.raises(UpstreamError):
        UpstreamManager.from_yaml("- just\n- a list\n")
    with pytest.raises(UpstreamError):
        UpstreamManager.from_yaml("upstreams: [\n")


async def test_missing_file_gives_empty_manager(tmp_path: Path) -> None:
    mgr = UpstreamManager.from_file(tmp_path / "nope.yaml")
    assert await mgr.list_tools() == []
    result = await mgr.call(tc("anything"))
    assert result.is_error and "Unknown tool" in result.content


def test_from_file_reads_yaml(tmp_path: Path) -> None:
    path = tmp_path / "upstreams.yaml"
    path.write_text(
        "upstreams:\n  - {name: ws, transport: inprocess, target: 'pkg.mod:server'}\n", encoding="utf-8"
    )
    mgr = UpstreamManager.from_file(path)
    assert mgr.status()[0]["transport"] == "inprocess"


def test_python_command_maps_to_running_interpreter() -> None:
    assert upstreams_mod._python_command(["python", "-m", "x"]) == [sys.executable, "-m", "x"]
    assert upstreams_mod._python_command(["node", "srv.js"]) == ["node", "srv.js"]


# --------------------------------------------------------------------------- in-process MCP upstream


async def test_inprocess_lists_tools_with_schemas() -> None:
    async with UpstreamManager.from_dict(INPROC) as mgr:
        tools = {t.name: t for t in await mgr.list_tools()}
        assert {"read_email", "send_email", "add", "broken", "slow"} <= set(tools)
        add = tools["add"]
        assert add.upstream == "ws"
        assert add.description == "Add two numbers."
        assert set(add.input_schema["properties"]) == {"a", "b"}
        assert add.input_schema["required"] == ["a", "b"]
        assert mgr.status()[0]["connected"] is True


async def test_inprocess_call_returns_text_and_structured() -> None:
    async with UpstreamManager.from_dict(INPROC) as mgr:
        result = await mgr.call(tc("add", a=2, b=3))
        assert result == ToolResult(
            call_id=result.call_id,
            session_id="s1",
            agent_id="email-crm-assistant",
            tool="add",
            content="5",
            structured={"result": 5},
        )
        email = await mgr.call(tc("read_email", email_id="E1"))
        assert not email.is_error
        # dict return without output schema: structured comes from the JSON text
        assert email.structured == {
            "id": "E1",
            "from": "ops@najd-trading.example",
            "body": "Quarterly figures attached.",
        }


async def test_inprocess_tool_errors_become_error_results() -> None:
    async with UpstreamManager.from_dict(INPROC) as mgr:
        broken = await mgr.call(tc("broken"))
        assert broken.is_error and "broken" in broken.content
        bad_args = await mgr.call(tc("add", a="x"))
        assert bad_args.is_error
        unknown = await mgr.call(tc("does_not_exist"))
        assert unknown.is_error and unknown.content == "Unknown tool: does_not_exist"


async def test_call_timeout_returns_error_and_reconnects() -> None:
    cfg = {"upstreams": [{**INPROC["upstreams"][0], "call_timeout_s": 0.2}]}
    async with UpstreamManager.from_dict(cfg) as mgr:
        result = await mgr.call(tc("slow", seconds=5))
        assert result.is_error and "timed out" in result.content
        again = await mgr.call(tc("add", a=1, b=1))
        assert again.content == "2"
        assert mgr.status()[0]["connect_count"] == 2


async def test_tool_list_is_cached_until_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"list": 0}

    async def on_list(ctx, params):
        calls["list"] += 1
        return types.ListToolsResult(
            tools=[types.Tool(name="ping", input_schema={"type": "object", "properties": {}})]
        )

    async def on_call(ctx, params):
        return types.CallToolResult(content=[types.TextContent(type="text", text="pong")])

    server = Server("counting", on_list_tools=on_list, on_call_tool=on_call)
    monkeypatch.setattr(upstreams_mod, "load_object", lambda target: server)
    mgr = UpstreamManager([UpstreamConfig(name="c", transport="inprocess", target="x:y")], tools_ttl_s=3600)
    try:
        await mgr.list_tools()
        await mgr.list_tools()
        assert (await mgr.call(tc("ping"))).content == "pong"
        assert calls["list"] == 1
        await mgr.list_tools(refresh=True)
        assert calls["list"] == 2
        mgr._fetched_at -= 7200  # TTL expired
        await mgr.list_tools()
        assert calls["list"] == 3
    finally:
        await mgr.stop()


async def test_one_broken_upstream_does_not_hide_others() -> None:
    cfg = {
        "upstreams": [
            {"name": "bad", "transport": "inprocess", "target": "no_such_module_xyz:server"},
            INPROC["upstreams"][0],
        ]
    }
    async with UpstreamManager.from_dict(cfg) as mgr:
        names = {t.name for t in await mgr.list_tools()}
        assert "add" in names
        status = {s["name"]: s for s in mgr.status()}
        assert status["bad"]["connected"] is False
        assert "no_such_module_xyz" in status["bad"]["last_error"]
        assert status["ws"]["connected"] is True


def test_load_object_validation() -> None:
    with pytest.raises(UpstreamError, match="cannot import"):
        load_object("no_such_module_xyz:server")
    with pytest.raises(UpstreamError, match="no attribute"):
        load_object("adapters_testkit:missing_attr")
    with pytest.raises(UpstreamError, match="not an MCP server"):
        load_object("adapters_testkit:INJECTION")
    assert load_object("adapters_testkit:make_workspace_server").name == "test-workspace"


# --------------------------------------------------------------------------- python function tools


async def test_python_tools_sync_async_and_errors() -> None:
    mgr = UpstreamManager()

    def lookup(customer_id: str) -> dict:
        return {"id": customer_id, "name": "شركة نجد", "tier": "gold"}

    async def greet(name: str) -> str:
        return f"hello {name}"

    def explode() -> None:
        raise RuntimeError("boom")

    schema = {"type": "object", "properties": {"customer_id": {"type": "string"}}}
    mgr.register_python("lookup", lookup, "Look up a customer", schema)
    mgr.register_python("greet", greet, "Greet", {"properties": {"name": {"type": "string"}}})
    mgr.register_python("explode", explode, "Fails", {}, in_thread=True)

    tools = {t.name: t for t in await mgr.list_tools()}
    assert tools["greet"].input_schema["type"] == "object"
    assert tools["lookup"].upstream == "python"

    res = await mgr.call(tc("lookup", customer_id="C017"))
    assert res.structured == {"id": "C017", "name": "شركة نجد", "tier": "gold"}
    assert "شركة نجد" in res.content  # ensure_ascii=False keeps Arabic readable for the detector
    assert (await mgr.call(tc("greet", name="Sara"))).content == "hello Sara"
    err = await mgr.call(tc("explode"))
    # Unexpected failures must not leak their message (it may hold paths or hosts); details go to the log.
    assert err.is_error and "internal error" in err.content and "boom" not in err.content
    bad = await mgr.call(tc("greet", nme="typo"))
    # Argument errors stay visible so the agent can correct its call.
    assert bad.is_error and "rejected the arguments" in bad.content and "nme" in bad.content

    with pytest.raises(ValueError):
        mgr.register_python("bad name!", greet, "", {})


async def test_python_tool_shadows_mcp_tool_and_prefix_routing() -> None:
    cfg = {"upstreams": [{**INPROC["upstreams"][0], "tool_prefix": "ws."}]}
    async with UpstreamManager.from_dict(cfg) as mgr:
        mgr.register_python("ws.add", lambda a, b: "python wins", "shadow", {})
        names = [t.name for t in await mgr.list_tools()]
        assert names.count("ws.add") == 1
        assert "ws.read_email" in names and "read_email" not in names
        assert (await mgr.call(tc("ws.add", a=1, b=2))).content == "python wins"
        email = await mgr.call(tc("ws.read_email", email_id="E1"))
        assert email.structured["id"] == "E1" and email.tool == "ws.read_email"


# --------------------------------------------------------------------------- result conversion


def test_call_result_conversion_handles_all_block_types() -> None:
    result = types.CallToolResult(
        content=[
            types.TextContent(type="text", text="first"),
            types.ImageContent(type="image", data="aGk=", mime_type="image/png"),
            types.EmbeddedResource(
                type="resource",
                resource=types.TextResourceContents(
                    uri="file:///notes.txt", text="embedded note", mime_type="text/plain"
                ),
            ),
            types.ResourceLink(type="resource_link", name="report", uri="file:///report.pdf"),
        ],
        is_error=True,
    )
    out = call_result_to_tool_result(tc("x"), result)
    assert out.is_error
    lines = out.content.split("\n")
    assert lines[0] == "first"
    assert "image (image/png) omitted by Mirsad" in lines[1]
    assert lines[2] == "embedded note"  # embedded text is inspected like any other text
    assert "report" in lines[3]
    assert out.structured is None


def test_structured_only_result_gets_text_form() -> None:
    result = types.CallToolResult(content=[], structured_content={"rows": [1, 2]})
    out = call_result_to_tool_result(tc("x"), result)
    assert out.structured == {"rows": [1, 2]}
    assert out.content == '{"rows": [1, 2]}'


def test_value_to_tool_result_variants() -> None:
    assert value_to_tool_result(tc("x"), None).content == ""
    assert value_to_tool_result(tc("x"), "[1, 2]").structured == [1, 2]
    assert value_to_tool_result(tc("x"), "plain").structured is None
    assert value_to_tool_result(tc("x"), b"bytes").content == "bytes"
    out = value_to_tool_result(tc("x"), {"when": {1, 2}})
    assert out.structured == {"when": [1, 2]}


# --------------------------------------------------------------------------- stdio and HTTP transports


async def test_stdio_upstream_lists_calls_and_reconnects_after_crash() -> None:
    cfg = {
        "upstreams": [
            {
                "name": "echo",
                "transport": "stdio",
                "command": ["python", str(HERE / "stdio_echo_server.py")],
                "env": {"ECHO_MARKER": "najd"},
                "connect_timeout_s": 30,
            }
        ]
    }
    async with UpstreamManager.from_dict(cfg) as mgr:
        assert {t.name for t in await mgr.list_tools()} == {"echo", "whoami", "crash"}
        assert (await mgr.call(tc("echo", text="مرحبا"))).content == "echo: مرحبا"
        first = (await mgr.call(tc("whoami"))).structured
        assert first["marker"] == "najd"
        crashed = await mgr.call(tc("crash"))
        assert crashed.is_error
        second = (await mgr.call(tc("whoami"))).structured
        assert second["pid"] != first["pid"]  # a fresh server process was spawned


async def test_http_upstream_with_headers() -> None:
    server = make_workspace_server()
    app = server.streamable_http_app(host="127.0.0.1")
    async with serve_asgi(app) as base:
        cfg = {
            "upstreams": [
                {"name": "remote", "transport": "http", "url": f"{base}/mcp", "headers": {"X-Test": "1"}}
            ]
        }
        async with UpstreamManager.from_dict(cfg) as mgr:
            assert "send_email" in {t.name for t in await mgr.list_tools()}
            result = await mgr.call(tc("add", a=20, b=22))
            assert result.content == "42" and result.structured == {"result": 42}


async def test_unreachable_http_upstream_returns_error_result() -> None:
    cfg = {
        "upstreams": [
            {"name": "gone", "transport": "http", "url": "http://127.0.0.1:9/mcp", "connect_timeout_s": 5}
        ]
    }
    mgr = UpstreamManager.from_dict(cfg)
    await mgr.start()  # must not raise
    try:
        mgr._routes["x"] = ("gone", "x")
        mgr._dirty = False
        mgr._fetched_at = 10**12
        result = await mgr.call(tc("x"))
        assert result.is_error and "unavailable" in result.content
    finally:
        await mgr.stop()


# --------------------------------------------------------------------------- resilience


async def test_failed_connect_backs_off_instead_of_retrying_every_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = {"n": 0}

    def failing_load(target: str):
        attempts["n"] += 1
        raise UpstreamError("server is down")

    monkeypatch.setattr(upstreams_mod, "load_object", failing_load)
    mgr = UpstreamManager([UpstreamConfig(name="down", transport="inprocess", target="x:y")])
    await mgr.start()
    mgr._routes["t"], mgr._dirty, mgr._fetched_at = ("down", "t"), False, 10**12
    first = await mgr.call(tc("t"))
    second = await mgr.call(tc("t"))
    assert first.is_error and second.is_error and "unavailable" in second.content
    assert "server is down" not in second.content  # internal error text stays in the log
    assert attempts["n"] == 1  # start() tried once; calls during the backoff window fail fast
    assert mgr.status()[0]["next_retry_s"] > 0
    await mgr.stop()


def test_manager_survives_event_loop_change() -> None:
    """Hosts such as FastAPI's TestClient may run successive requests on different loops."""
    import asyncio

    mgr = UpstreamManager.from_dict(INPROC)
    assert asyncio.run(mgr.call(tc("add", a=1, b=2))).content == "3"
    assert asyncio.run(mgr.call(tc("add", a=2, b=2))).content == "4"
    assert mgr.status()[0]["connect_count"] == 2
