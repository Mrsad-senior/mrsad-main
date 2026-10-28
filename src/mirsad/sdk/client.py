"""Python SDK for agents and frameworks that call tools themselves.

Two ways to use it:

* explicit: ``client.check_call(...)`` before running a tool and
  ``client.inspect_result(...)`` after it, or ``client.invoke(...)`` to let the
  gateway run an upstream tool end to end;
* the :meth:`MirsadClient.guard` decorator, which wraps an existing tool function:
  check -> run -> inspect. The wrapped function returns the **inspected text**
  (sanitised / spotlighted), not the raw return value. The agent must feed that
  returned value to the model; feeding the raw value would bypass Mirsad.

Both clients fail closed: if the gateway cannot be reached the guard raises
:class:`MirsadError` and the tool function is not executed.

``timeout`` (default 150 s) must exceed the gateway's approval timeout because a call
that needs human approval blocks until someone decides. It configures the HTTP client
the SDK creates; a caller-supplied ``http_client`` keeps its own timeout settings.
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import os
import uuid
from collections.abc import Callable
from typing import Any, Literal, TypeVar
from urllib.parse import quote

import httpx

from mirsad.adapters.messages import block_message, result_block_message
from mirsad.adapters.serialization import jsonable, parse_json_text, to_json_text
from mirsad.models import Decision, GatewayResponse, InspectionOutcome, new_id

__all__ = ["AsyncMirsadClient", "MirsadAuthError", "MirsadBlocked", "MirsadClient", "MirsadError"]

F = TypeVar("F", bound=Callable[..., Any])


class MirsadError(Exception):
    """The gateway could not be reached or answered with an error."""

    def __init__(self, message: str, *, status_code: int | None = None, detail: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class MirsadAuthError(MirsadError):
    """The agent key was missing, invalid or disabled (HTTP 401/403)."""


class MirsadBlocked(MirsadError):
    """Mirsad blocked a tool call (``stage="call"``) or withheld its result (``stage="result"``).

    ``str(exc)`` is a bilingual explanation that can be shown to the model or the user.
    """

    def __init__(
        self,
        decision: Decision,
        *,
        tool: str | None = None,
        outcome: InspectionOutcome | None = None,
    ) -> None:
        self.decision = decision
        self.outcome = outcome
        self.tool = tool or "tool"
        self.stage: Literal["call", "result"] = "result" if outcome is not None else "call"
        if outcome is not None:
            message = outcome.content.strip() or result_block_message(outcome, self.tool)
        else:
            message = block_message(decision, self.tool)
        super().__init__(message)


# --------------------------------------------------------------------------- shared logic


def _bind_arguments(fn: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
    """Map a call of ``fn`` to a JSON-safe ``{param: value}`` dict (defaults applied, self/cls skipped)."""
    sig = inspect.signature(fn)
    bound = sig.bind(*args, **kwargs)
    bound.apply_defaults()
    params = list(sig.parameters.values())
    out: dict[str, Any] = {}
    for name, value in bound.arguments.items():
        param = sig.parameters[name]
        if params and param is params[0] and name in ("self", "cls"):
            continue
        if param.kind is inspect.Parameter.VAR_KEYWORD:
            out.update(value)
        elif param.kind is inspect.Parameter.VAR_POSITIONAL:
            out[name] = list(value)
        else:
            out[name] = value
    return jsonable(out)


def _raise_for_status(resp: httpx.Response) -> Any:
    if resp.status_code < 400:
        try:
            return resp.json()
        except ValueError as exc:
            raise MirsadError("Mirsad returned a non-JSON response", status_code=resp.status_code) from exc
    try:
        body = resp.json()
        detail = body.get("detail", body) if isinstance(body, dict) else body
    except ValueError:
        detail = resp.text[:500]
    cls = MirsadAuthError if resp.status_code in (401, 403) else MirsadError
    raise cls(f"Mirsad API error {resp.status_code}: {detail}", status_code=resp.status_code, detail=detail)


def _openai_tools(items: Any) -> list[dict[str, Any]]:
    tools = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        schema = dict(item.get("input_schema") or {})
        schema.setdefault("type", "object")
        schema.setdefault("properties", {})
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": item["name"],
                    "description": item.get("description") or "",
                    "parameters": schema,
                },
            }
        )
    return tools


class _Base:
    def __init__(self, base_url: str, api_key: str, session_id: str | None, timeout: float) -> None:
        if not base_url:
            raise ValueError("base_url is required")
        if not api_key:
            raise ValueError("api_key is required")
        self.base_url = base_url.rstrip("/")
        self.session_id = session_id or f"sdk-{uuid.uuid4().hex[:16]}"
        self.timeout = timeout
        self._api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}", "X-Mirsad-Session": self.session_id}

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def new_session(self, session_id: str | None = None) -> str:
        """Start a new taint session (e.g. a new conversation) and return its id."""
        self.session_id = session_id or f"sdk-{uuid.uuid4().hex[:16]}"
        return self.session_id

    def _check_payload(
        self, tool: str, arguments: dict[str, Any], call_id: str | None, wait: bool
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "session_id": self.session_id,
            "tool": tool,
            "arguments": jsonable(arguments or {}),
            "wait": wait,
        }
        if call_id:
            payload["call_id"] = call_id
        return payload

    def _result_payload(self, tool: str, call_id: str, content: Any) -> dict[str, Any]:
        if isinstance(content, str):
            text, structured = content, parse_json_text(content)
        else:
            text, structured = to_json_text(content)
        return {
            "session_id": self.session_id,
            "call_id": call_id,
            "tool": tool,
            "content": text,
            "structured": structured,
        }


# --------------------------------------------------------------------------- sync client


class MirsadClient(_Base):
    """Synchronous client for the Mirsad agent API (``/v1/guard/*``, ``/v1/tools``)."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        session_id: str | None = None,
        timeout: float = 150,
        http_client: httpx.Client | None = None,
    ) -> None:
        super().__init__(base_url, api_key, session_id, timeout)
        self._owns_http = http_client is None
        self._http = http_client or httpx.Client(timeout=httpx.Timeout(timeout, connect=10.0))

    @classmethod
    def from_env(cls, **kwargs: Any) -> MirsadClient:
        """Build from ``MIRSAD_URL`` (default http://127.0.0.1:8700) and ``MIRSAD_AGENT_KEY``."""
        return cls(
            os.environ.get("MIRSAD_URL", "http://127.0.0.1:8700"),
            os.environ.get("MIRSAD_AGENT_KEY", ""),
            **kwargs,
        )

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> MirsadClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _request(self, method: str, path: str, json_body: Any = None) -> Any:
        try:
            resp = self._http.request(method, self._url(path), json=json_body, headers=self._headers())
        except httpx.HTTPError as exc:
            raise MirsadError(f"Mirsad gateway unreachable at {self.base_url}: {exc}") from exc
        return _raise_for_status(resp)

    def check_call(
        self, tool: str, arguments: dict[str, Any], *, call_id: str | None = None, wait: bool = True
    ) -> Decision:
        """Ask whether ``tool(**arguments)`` may run. Blocks while a human approval is pending (``wait``)."""
        data = self._request(
            "POST", "/v1/guard/tool-call", self._check_payload(tool, arguments, call_id, wait)
        )
        return Decision.model_validate(data)

    def inspect_result(self, tool: str, call_id: str, content: str | Any) -> InspectionOutcome:
        """Inspect a tool result; non-string values are serialised to JSON text first."""
        data = self._request("POST", "/v1/guard/tool-result", self._result_payload(tool, call_id, content))
        return InspectionOutcome.model_validate(data)

    def invoke(self, tool: str, arguments: dict[str, Any]) -> GatewayResponse:
        """Run an upstream tool through the gateway (check -> execute -> inspect)."""
        body = {"session_id": self.session_id, "arguments": jsonable(arguments or {})}
        data = self._request("POST", f"/v1/tools/{quote(tool, safe='')}/invoke", body)
        return GatewayResponse.model_validate(data)

    def tools(self) -> list[dict[str, Any]]:
        """OpenAI function-calling schemas of the tools visible to this agent."""
        return _openai_tools(self._request("GET", "/v1/tools"))

    def guard(self, fn: F | None = None, *, name: str | None = None) -> Any:
        """Decorator: check the call, run the function, inspect and return the inspected text.

        Works on sync and async functions (async ones stay async). Raises :class:`MirsadBlocked`
        when the call is denied or the result is blocked, and :class:`MirsadError` when the
        gateway is unreachable; in both pre-execution cases the function is not run.
        """

        def decorate(func: F) -> F:
            tool = name or func.__name__

            if inspect.iscoroutinefunction(func):

                @functools.wraps(func)
                async def async_wrapper(*args: Any, **kwargs: Any) -> str:
                    arguments = _bind_arguments(func, args, kwargs)
                    call_id = new_id("call_")
                    decision = await asyncio.to_thread(self.check_call, tool, arguments, call_id=call_id)
                    if not decision.allowed:
                        raise MirsadBlocked(decision, tool=tool)
                    value = await func(*args, **kwargs)
                    outcome = await asyncio.to_thread(self.inspect_result, tool, call_id, value)
                    if outcome.action == "block":
                        raise MirsadBlocked(decision, tool=tool, outcome=outcome)
                    return outcome.content

                return async_wrapper  # type: ignore[return-value]

            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> str:
                arguments = _bind_arguments(func, args, kwargs)
                call_id = new_id("call_")
                decision = self.check_call(tool, arguments, call_id=call_id)
                if not decision.allowed:
                    raise MirsadBlocked(decision, tool=tool)
                value = func(*args, **kwargs)
                outcome = self.inspect_result(tool, call_id, value)
                if outcome.action == "block":
                    raise MirsadBlocked(decision, tool=tool, outcome=outcome)
                return outcome.content

            return wrapper  # type: ignore[return-value]

        return decorate(fn) if fn is not None else decorate


# --------------------------------------------------------------------------- async client


class AsyncMirsadClient(_Base):
    """Asynchronous client with the same API as :class:`MirsadClient`."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        session_id: str | None = None,
        timeout: float = 150,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(base_url, api_key, session_id, timeout)
        self._owns_http = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=10.0))

    @classmethod
    def from_env(cls, **kwargs: Any) -> AsyncMirsadClient:
        return cls(
            os.environ.get("MIRSAD_URL", "http://127.0.0.1:8700"),
            os.environ.get("MIRSAD_AGENT_KEY", ""),
            **kwargs,
        )

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> AsyncMirsadClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def _request(self, method: str, path: str, json_body: Any = None) -> Any:
        try:
            resp = await self._http.request(method, self._url(path), json=json_body, headers=self._headers())
        except httpx.HTTPError as exc:
            raise MirsadError(f"Mirsad gateway unreachable at {self.base_url}: {exc}") from exc
        return _raise_for_status(resp)

    async def check_call(
        self, tool: str, arguments: dict[str, Any], *, call_id: str | None = None, wait: bool = True
    ) -> Decision:
        data = await self._request(
            "POST", "/v1/guard/tool-call", self._check_payload(tool, arguments, call_id, wait)
        )
        return Decision.model_validate(data)

    async def inspect_result(self, tool: str, call_id: str, content: str | Any) -> InspectionOutcome:
        data = await self._request(
            "POST", "/v1/guard/tool-result", self._result_payload(tool, call_id, content)
        )
        return InspectionOutcome.model_validate(data)

    async def invoke(self, tool: str, arguments: dict[str, Any]) -> GatewayResponse:
        body = {"session_id": self.session_id, "arguments": jsonable(arguments or {})}
        data = await self._request("POST", f"/v1/tools/{quote(tool, safe='')}/invoke", body)
        return GatewayResponse.model_validate(data)

    async def tools(self) -> list[dict[str, Any]]:
        return _openai_tools(await self._request("GET", "/v1/tools"))

    def guard(self, fn: F | None = None, *, name: str | None = None) -> Any:
        """Like :meth:`MirsadClient.guard`, but the wrapper is always a coroutine function.

        Sync functions are called directly inside the coroutine (wrap blocking I/O yourself).
        """

        def decorate(func: F) -> F:
            tool = name or func.__name__
            is_async = inspect.iscoroutinefunction(func)

            @functools.wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> str:
                arguments = _bind_arguments(func, args, kwargs)
                call_id = new_id("call_")
                decision = await self.check_call(tool, arguments, call_id=call_id)
                if not decision.allowed:
                    raise MirsadBlocked(decision, tool=tool)
                value = await func(*args, **kwargs) if is_async else func(*args, **kwargs)
                outcome = await self.inspect_result(tool, call_id, value)
                if outcome.action == "block":
                    raise MirsadBlocked(decision, tool=tool, outcome=outcome)
                return outcome.content

            return wrapper  # type: ignore[return-value]

        return decorate(fn) if fn is not None else decorate
