"""Python SDK against a minimal FastAPI app implementing the guard endpoints."""

from __future__ import annotations

import datetime as dt

import httpx
import pytest
from adapters_testkit import INJECTION, SANITIZED_MARK, FakeGateway, FakeUpstreams, ToolInfo, make_mini_api
from fastapi.testclient import TestClient

from mirsad.models import Action, ToolResult
from mirsad.sdk import AsyncMirsadClient, MirsadAuthError, MirsadBlocked, MirsadClient, MirsadError
from mirsad.sdk.client import _bind_arguments

BASE = "http://testserver"
KEY = "mk_test"


def make_env(**gateway_kwargs):
    gateway = FakeGateway(**gateway_kwargs)
    ups = FakeUpstreams(
        [
            ToolInfo(
                "read_email",
                "Read one e-mail",
                {"type": "object", "properties": {"email_id": {"type": "string"}}},
            ),
            ToolInfo("send_email", "Send an e-mail"),
        ],
        results={
            "read_email": ToolResult(
                call_id="x", session_id="x", agent_id="a", tool="read_email", content=f"Body. {INJECTION}"
            )
        },
    )
    app = make_mini_api(gateway, ups, key=KEY)
    return gateway, ups, app


def sync_client(app, key: str = KEY, **kwargs) -> MirsadClient:
    return MirsadClient(BASE, key, http_client=TestClient(app, base_url=BASE), **kwargs)


def async_client(app, key: str = KEY, **kwargs) -> AsyncMirsadClient:
    http = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE)
    return AsyncMirsadClient(BASE, key, http_client=http, **kwargs)


# --------------------------------------------------------------------------- explicit API (sync)


def test_check_call_sends_key_session_and_returns_decision() -> None:
    gateway, _, app = make_env(deny={"send_email"})
    client = sync_client(app, session_id="conv-1")
    allowed = client.check_call("read_email", {"email_id": "E1"}, call_id="call_42")
    denied = client.check_call("send_email", {"to": "attacker@evil.example"})
    assert allowed.action == Action.ALLOW and allowed.call_id == "call_42"
    assert denied.action == Action.DENY and denied.reasons[0].code == "TAINT_UNTRUSTED_DESTINATION"
    seen = app.state.seen[0]
    assert seen["headers"]["authorization"] == f"Bearer {KEY}"
    assert seen["headers"]["x-mirsad-session"] == "conv-1"
    assert seen["body"] == {
        "session_id": "conv-1",
        "tool": "read_email",
        "arguments": {"email_id": "E1"},
        "wait": True,
        "call_id": "call_42",
    }
    assert gateway.checked[0].agent_id == "email-crm-assistant"


def test_inspect_result_serialises_values() -> None:
    gateway, _, app = make_env()
    client = sync_client(app)
    outcome = client.inspect_result("get_customer", "call_1", {"id": "C017", "notes": INJECTION})
    assert outcome.action == "sanitize" and SANITIZED_MARK in outcome.content
    body = app.state.seen[0]["body"]
    assert body["structured"] == {"id": "C017", "notes": INJECTION}
    assert body["content"].startswith('{"id": "C017"')
    text = client.inspect_result("fetch_url", "call_2", '{"title": "ok"}')
    assert text.action == "pass" and gateway.inspected[-1].structured == {"title": "ok"}


def test_invoke_and_tools() -> None:
    _, ups, app = make_env(visible={"read_email"})
    client = sync_client(app, session_id="s-9")
    response = client.invoke("read_email", {"email_id": "E2"})
    assert response.decision.allowed and SANITIZED_MARK in response.result.content
    assert ups.executed[0].session_id == "s-9"
    assert client.tools() == [
        {
            "type": "function",
            "function": {
                "name": "read_email",
                "description": "Read one e-mail",
                "parameters": {"type": "object", "properties": {"email_id": {"type": "string"}}},
            },
        }
    ]


def test_errors_are_raised_as_mirsad_errors() -> None:
    _, _, app = make_env()
    with pytest.raises(MirsadAuthError) as info:
        sync_client(app, key="mk_wrong").check_call("read_email", {})
    assert info.value.status_code == 401 and info.value.detail == "Invalid agent key"

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    offline = MirsadClient(BASE, KEY, http_client=httpx.Client(transport=httpx.MockTransport(down)))
    with pytest.raises(MirsadError, match="unreachable"):
        offline.tools()
    with pytest.raises(ValueError):
        MirsadClient(BASE, "")


# --------------------------------------------------------------------------- guard decorator (sync client)


def test_guard_runs_tool_and_returns_inspected_text() -> None:
    gateway, _, app = make_env()
    client = sync_client(app)
    ran: list[tuple] = []

    @client.guard
    def read_document(doc_id: str, lang: str = "ar") -> dict:
        ran.append((doc_id, lang))
        return {"doc_id": doc_id, "body": f"تقرير المبيعات. {INJECTION}"}

    out = read_document("D3")
    assert ran == [("D3", "ar")]
    assert isinstance(out, str) and SANITIZED_MARK in out and "IGNORE PREVIOUS" not in out
    assert "تقرير المبيعات" in out
    assert gateway.checked[0].arguments == {"doc_id": "D3", "lang": "ar"}  # defaults are checked too
    assert gateway.inspected[0].call_id == gateway.checked[0].call_id
    assert read_document.__name__ == "read_document"


def test_guard_denied_call_does_not_run() -> None:
    _, _, app = make_env(deny={"send_email"})
    client = sync_client(app)
    ran: list[str] = []

    @client.guard
    def send_email(to: str, body: str) -> str:
        ran.append(to)
        return "sent"

    with pytest.raises(MirsadBlocked) as info:
        send_email("attacker@evil.example", body="all customers")
    assert ran == []
    exc = info.value
    assert exc.stage == "call" and exc.decision.action == Action.DENY
    assert "Tool call blocked: send_email" in str(exc) and "مرصاد" in str(exc)


def test_guard_blocked_result_raises() -> None:
    _, _, app = make_env(block_results={"fetch_url"})
    client = sync_client(app)

    @client.guard
    def fetch_url(url: str) -> str:
        return f"<html>{INJECTION}</html>"

    with pytest.raises(MirsadBlocked) as info:
        fetch_url("https://free-prizes.example/win")
    assert info.value.stage == "result" and info.value.outcome.action == "block"


def test_guard_on_method_with_name_override() -> None:
    gateway, _, app = make_env()
    client = sync_client(app)

    class CRM:
        @client.guard(name="get_customer")
        def lookup(self, customer_id: str, *, fields: tuple = ("name",)) -> str:
            return f"customer {customer_id}"

    assert CRM().lookup("C017") == "customer C017"
    call = gateway.checked[0]
    assert call.tool == "get_customer" and call.arguments == {"customer_id": "C017", "fields": ["name"]}


async def test_sync_client_guard_on_async_function() -> None:
    _, _, app = make_env(deny={"send_email"})
    client = sync_client(app)

    @client.guard
    async def summarise(text: str) -> str:
        return text.upper()

    @client.guard
    async def send_email(to: str) -> str:
        raise AssertionError("must not run")

    assert await summarise("hello") == "HELLO"
    with pytest.raises(MirsadBlocked):
        await send_email("attacker@evil.example")


def test_guard_fails_closed_when_gateway_unreachable() -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = MirsadClient(BASE, KEY, http_client=httpx.Client(transport=httpx.MockTransport(down)))
    ran: list[int] = []

    @client.guard
    def delete_customer(customer_id: str) -> str:
        ran.append(1)
        return "deleted"

    with pytest.raises(MirsadError):
        delete_customer("C001")
    assert ran == []


def test_bind_arguments_normalises_values() -> None:
    def tool(a, *rest, when: dt.date, **extra):
        return None

    args = _bind_arguments(tool, (1, 2, 3), {"when": dt.date(2026, 10, 11), "tags": {"x"}})
    assert args == {"a": 1, "rest": [2, 3], "when": "2026-10-11", "tags": ["x"]}
    with pytest.raises(TypeError):
        _bind_arguments(tool, (), {})


def test_session_management() -> None:
    client = MirsadClient(BASE, KEY)
    first = client.session_id
    assert first.startswith("sdk-")
    assert client.new_session("conv-2") == "conv-2" == client.session_id
    assert client.new_session() not in (first, "conv-2")
    client.close()


def test_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIRSAD_URL", "http://gw.najd-trading.example:8700/")
    monkeypatch.setenv("MIRSAD_AGENT_KEY", "mk_env")
    with MirsadClient.from_env() as client:
        assert client.base_url == "http://gw.najd-trading.example:8700"


# --------------------------------------------------------------------------- async client


async def test_async_client_explicit_api() -> None:
    gateway, ups, app = make_env(deny={"send_email"}, visible={"read_email", "send_email"})
    async with async_client(app, session_id="a-1") as client:
        decision = await client.check_call("send_email", {"to": "attacker@evil.example"})
        outcome = await client.inspect_result("read_email", "call_7", f"Hi {INJECTION}")
        response = await client.invoke("read_email", {"email_id": "E2"})
        tools = await client.tools()
    assert decision.action == Action.DENY
    assert outcome.action == "sanitize"
    assert response.result is not None and SANITIZED_MARK in response.result.content
    assert {t["function"]["name"] for t in tools} == {"read_email", "send_email"}
    assert all(c.session_id == "a-1" for c in gateway.checked)


async def test_async_guard_sync_and_async_functions() -> None:
    _, _, app = make_env(deny={"transfer_funds"})
    client = async_client(app)

    @client.guard
    def read_email(email_id: str) -> dict:
        return {"id": email_id, "body": INJECTION}

    @client.guard(name="transfer_funds")
    async def pay(to_iban: str, amount_sar: float) -> str:
        raise AssertionError("must not run")

    out = await read_email("E2")
    assert SANITIZED_MARK in out
    with pytest.raises(MirsadBlocked) as info:
        await pay("SA0380000000608010167519", 50000)
    assert info.value.tool == "transfer_funds"
    await client.aclose()


async def test_async_client_auth_error() -> None:
    _, _, app = make_env()
    client = async_client(app, key="mk_wrong")
    with pytest.raises(MirsadAuthError):
        await client.tools()
