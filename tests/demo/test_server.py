"""Tests for the MCP workspace server, driven in-process via mcp.Client."""

from __future__ import annotations

import json
import logging

import pytest
from mcp import Client

from demo import workspace_server


@pytest.fixture(autouse=True)
def _reset_world():
    workspace_server.WORLD.reset()
    yield
    workspace_server.WORLD.reset()


@pytest.fixture(autouse=True)
def _quiet_logs():
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)


async def test_list_tools():
    async with Client(workspace_server.server) as client:
        result = await client.list_tools()
        names = {t.name for t in result.tools}
    assert names == set(workspace_server._WRAPPERS)
    assert len(names) == 12


async def test_tool_has_schema():
    async with Client(workspace_server.server) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
    schema = tools["send_email"].input_schema
    assert schema["type"] == "object"
    assert set(schema["required"]) == {"to", "subject", "body"}


async def test_call_read_email_returns_json_text():
    async with Client(workspace_server.server) as client:
        res = await client.call_tool("read_email", {"email_id": "E001"})
    assert res.is_error is False
    data = json.loads(res.content[0].text)
    assert data["id"] == "E001"


async def test_call_list_emails():
    async with Client(workspace_server.server) as client:
        res = await client.call_tool("list_emails", {"folder": "inbox", "limit": 3})
    data = json.loads(res.content[0].text)
    assert len(data) == 3


async def test_call_tool_shares_world():
    async with Client(workspace_server.server) as client:
        await client.call_tool("send_email", {"to": "x@evil.example", "subject": "s", "body": "b"})
    assert len(workspace_server.WORLD.outbox) == 1


async def test_invalid_args_surface_clear_error():
    async with Client(workspace_server.server) as client:
        res = await client.call_tool("read_email", {"email_id": "E999"})
    assert res.is_error is True
    assert "unknown email_id" in res.content[0].text


async def test_missing_required_arg_is_error():
    async with Client(workspace_server.server) as client:
        res = await client.call_tool("get_customer", {})
    assert res.is_error is True
