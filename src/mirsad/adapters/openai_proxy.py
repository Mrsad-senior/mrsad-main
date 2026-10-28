"""OpenAI-compatible chat-completions proxy (BUILD_SPEC section 7.3).

Any agent that speaks the OpenAI Chat Completions API can be protected by
changing its ``base_url`` to Mirsad. For each ``POST /v1/chat/completions``:

1. every ``role: tool`` (and legacy ``role: function``) message is inspected with
   ``gateway.inspect_result`` and its content replaced by the inspected content
   (sanitised / spotlighted / blocked), the tool name being resolved from the
   preceding assistant ``tool_calls``;
2. tool definitions the agent's policy does not allow are removed from ``tools``
   (least privilege: the model is not offered what it may not use);
3. the request is forwarded to ``settings.llm_base_url`` (the agent key is never
   forwarded; upstream auth comes from ``X-Upstream-Authorization`` or
   ``settings.llm_api_key``);
4. every returned ``tool_calls[i]`` is checked with ``gateway.check_call``; denied
   calls are removed and a bilingual explanation is appended to the assistant text;
   if no call is left, ``finish_reason`` becomes ``"stop"``.

The response keeps the OpenAI shape and adds an informational ``mirsad`` object
(session id + per-call decisions), which OpenAI client libraries ignore.
"""

# No ``from __future__ import annotations`` here: FastAPI must evaluate the endpoint's
# ``Annotated[..., Depends(dependency)]`` annotation, which refers to a closure variable.

import hashlib
import inspect
import json
import logging
from collections import OrderedDict
from collections.abc import Callable
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from mirsad.adapters.messages import block_message, extract_agent_key
from mirsad.adapters.serialization import parse_json_text
from mirsad.models import Action, Decision, Reason, Risk, ToolCall, ToolResult, new_id

logger = logging.getLogger("mirsad.adapters")

__all__ = ["build_openai_router", "session_id_for"]

SESSION_HEADER = "X-Mirsad-Session"
UPSTREAM_AUTH_HEADER = "X-Upstream-Authorization"
_WITHHELD = "[Mirsad] This tool result could not be inspected and was withheld.\n\n[مرصاد] تعذّر فحص نتيجة الأداة فحُجبت."


# --------------------------------------------------------------------------- helpers


def _content_text(content: Any) -> str:
    """Text of an OpenAI message ``content`` (string or list of content parts)."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                parts.append(str(part.get("text", "")))
            elif isinstance(part, str):
                parts.append(part)
        return "\n".join(parts)
    return json.dumps(content, ensure_ascii=False)


def session_id_for(messages: list[Any], agent_id: str, header_value: str | None) -> str:
    """``X-Mirsad-Session`` if given, else a stable hash of the agent id and first user message."""
    if header_value and header_value.strip():
        return header_value.strip()[:128]
    first_user = next((m for m in messages if isinstance(m, dict) and m.get("role") == "user"), None)
    seed = _content_text(first_user.get("content")) if first_user else ""
    digest = hashlib.sha256(f"{agent_id}\x00{seed}".encode()).hexdigest()[:24]
    return f"oa-{digest}"


class _LRU:
    """Small LRU of inspected tool-message content.

    Chat clients resend the whole conversation every turn; without this each tool
    message would be re-inspected (and re-audited) on every request.
    """

    def __init__(self, maxsize: int = 4096) -> None:
        self.maxsize = maxsize
        self._data: OrderedDict[tuple[str, ...], tuple[str, str]] = OrderedDict()

    def get(self, key: tuple[str, ...]) -> tuple[str, str] | None:
        value = self._data.get(key)
        if value is not None:
            self._data.move_to_end(key)
        return value

    def put(self, key: tuple[str, ...], value: tuple[str, str]) -> None:
        self._data[key] = value
        self._data.move_to_end(key)
        while len(self._data) > self.maxsize:
            self._data.popitem(last=False)


def _local_denial(call_id: str, code: str, message: str, message_ar: str) -> Decision:
    """A DENY decided by the proxy itself (malformed call, gateway failure): fail closed."""
    return Decision(
        call_id=call_id,
        action=Action.DENY,
        risk=Risk.HIGH,
        risk_score=0.6,
        reasons=[
            Reason(
                layer="system",
                code=code,
                message=message,
                message_ar=message_ar,
                action=Action.DENY,
                risk_score=0.6,
            )
        ],
    )


def _default_agent_dependency() -> Callable[..., Any]:
    """``mirsad.api.deps.require_agent`` when available, else a local equivalent."""
    try:
        from mirsad.api.deps import require_agent
    except ImportError:
        logger.warning("mirsad.api.deps not available; OpenAI proxy uses its own agent-key check")
        return _fallback_require_agent
    try:
        # Tolerate both styles: a dependency function, or a zero-argument factory returning one.
        if not inspect.signature(require_agent).parameters:
            return require_agent()
    except (TypeError, ValueError):
        pass
    return require_agent


async def _fallback_require_agent(request: Request) -> Any:
    key = extract_agent_key(request.headers)
    if not key:
        raise HTTPException(
            status_code=401, detail="Missing agent key", headers={"WWW-Authenticate": "Bearer"}
        )
    from mirsad.auth import authenticate_agent_key

    agent = await run_in_threadpool(authenticate_agent_key, request.app.state.db, key)
    if agent is None:
        raise HTTPException(
            status_code=401, detail="Invalid agent key", headers={"WWW-Authenticate": "Bearer"}
        )
    return agent


def _settings(request: Request) -> Any:
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        from mirsad.config import get_settings

        settings = get_settings()
    return settings


def _upstream_headers(request: Request, settings: Any) -> dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    override = request.headers.get(UPSTREAM_AUTH_HEADER)
    if override and override.strip():
        value = override.strip()
        headers["Authorization"] = value if " " in value else f"Bearer {value}"
    elif getattr(settings, "llm_api_key", ""):
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"
    return headers


# --------------------------------------------------------------------------- router


def build_openai_router(
    *,
    agent_dependency: Callable[..., Any] | None = None,
    http_client: httpx.AsyncClient | None = None,
    filter_tools: bool = True,
    upstream_timeout_s: float = 300.0,
    cache_size: int = 4096,
) -> APIRouter:
    """Router with ``POST /v1/chat/completions``.

    Uses ``request.app.state.gateway`` and ``request.app.state.settings``. Keyword
    arguments exist for tests and embedding: ``agent_dependency`` replaces the agent-key
    dependency, ``http_client`` replaces the per-request client used for the upstream LLM.
    """
    dependency = agent_dependency or _default_agent_dependency()
    cache = _LRU(cache_size)
    router = APIRouter(tags=["openai-proxy"])

    async def inspect_messages(
        gateway: Any, messages: list[Any], session_id: str, agent_id: str, report: list[dict[str, Any]]
    ) -> list[Any]:
        tool_names: dict[str, str] = {}
        last_function: str | None = None
        out: list[Any] = []
        for msg in messages:
            if not isinstance(msg, dict):
                raise HTTPException(status_code=400, detail="each message must be an object")
            role = msg.get("role")
            if role == "assistant":
                for tc in msg.get("tool_calls") or []:
                    if isinstance(tc, dict):
                        fn = tc.get("function") or {}
                        if tc.get("id") and isinstance(fn, dict) and fn.get("name"):
                            tool_names[str(tc["id"])] = str(fn["name"])
                fc = msg.get("function_call")
                if isinstance(fc, dict) and fc.get("name"):
                    last_function = str(fc["name"])
                out.append(msg)
                continue
            if role not in ("tool", "function"):
                out.append(msg)
                continue
            if role == "tool":
                call_id = str(msg.get("tool_call_id") or new_id("call_"))
                tool = tool_names.get(call_id) or str(msg.get("name") or "unknown_tool")
            else:
                call_id = new_id("call_")
                tool = str(msg.get("name") or last_function or "unknown_tool")
            text = _content_text(msg.get("content"))
            key = (agent_id, session_id, call_id, tool, hashlib.sha256(text.encode()).hexdigest())
            cached = cache.get(key)
            if cached is not None:
                content, action = cached
            else:
                try:
                    outcome = await gateway.inspect_result(
                        ToolResult(
                            call_id=call_id,
                            session_id=session_id,
                            agent_id=agent_id,
                            tool=tool,
                            content=text,
                            structured=parse_json_text(text),
                        )
                    )
                    content, action = outcome.content, outcome.action
                    cache.put(key, (content, action))
                except Exception:
                    logger.exception("inspect_result failed for %s; withholding the tool message", tool)
                    content, action = _WITHHELD, "block"
            report.append({"tool_call_id": call_id, "tool": tool, "action": action})
            new_msg = dict(msg)
            new_msg["content"] = content
            out.append(new_msg)
        return out

    def filter_tool_definitions(gateway: Any, body: dict[str, Any], agent_id: str) -> None:
        tools = body.get("tools")
        if not filter_tools or not isinstance(tools, list) or not tools:
            return
        names = [
            str(t["function"]["name"])
            for t in tools
            if isinstance(t, dict) and isinstance(t.get("function"), dict) and t["function"].get("name")
        ]
        try:
            visible = set(gateway.policy.visible_tools(agent_id, names))
        except Exception:
            logger.exception("visible_tools failed; forwarding tool definitions unfiltered")
            return
        kept = [
            t
            for t in tools
            if isinstance(t, dict)
            and isinstance(t.get("function"), dict)
            and t["function"].get("name") in visible
        ]
        if len(kept) == len(tools):
            return
        logger.info(
            "agent %s: hid %d tool definition(s) not allowed by policy", agent_id, len(tools) - len(kept)
        )
        choice = body.get("tool_choice")
        if isinstance(choice, dict):
            forced = (choice.get("function") or {}).get("name")
            if forced and forced not in visible:
                body.pop("tool_choice", None)
        if kept:
            body["tools"] = kept
        else:
            for k in ("tools", "tool_choice", "parallel_tool_calls"):
                body.pop(k, None)

    async def check_tool_call(
        gateway: Any, tc: dict[str, Any], session_id: str, agent_id: str
    ) -> tuple[str, Decision]:
        fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
        name = str(fn.get("name") or "unknown_tool")
        call_id = str(tc.get("id") or new_id("call_"))
        tc["id"] = call_id
        raw = fn.get("arguments")
        if raw is None or raw == "":
            arguments: Any = {}
        elif isinstance(raw, dict):
            arguments = raw
        else:
            arguments = parse_json_text(str(raw))
        if not isinstance(arguments, dict):
            # Constraints and taint checks cannot see inside unparsable arguments: fail closed.
            return name, _local_denial(
                call_id,
                "MALFORMED_ARGUMENTS",
                f"The arguments for {name} are not a valid JSON object, so they cannot be checked.",
                f"معطيات الأداة {name} ليست كائن JSON صالحًا، لذا لا يمكن فحصها.",
            )
        call = ToolCall(
            call_id=call_id, session_id=session_id, agent_id=agent_id, tool=name, arguments=arguments
        )
        try:
            return name, await gateway.check_call(call)
        except Exception:
            logger.exception("check_call failed for %s; denying", name)
            return name, _local_denial(
                call_id,
                "GATEWAY_ERROR",
                "Mirsad could not evaluate this call.",
                "تعذّر على مرصاد تقييم هذا الاستدعاء.",
            )

    async def check_response(
        gateway: Any, data: dict[str, Any], session_id: str, agent_id: str, report: list[dict[str, Any]]
    ) -> None:
        for choice in data.get("choices") or []:
            if not isinstance(choice, dict) or not isinstance(choice.get("message"), dict):
                continue
            msg = choice["message"]
            blocked: list[str] = []
            tool_calls = msg.get("tool_calls")
            if isinstance(tool_calls, list) and tool_calls:
                kept = []
                for tc in tool_calls:
                    if not isinstance(tc, dict):
                        continue
                    name, decision = await check_tool_call(gateway, tc, session_id, agent_id)
                    report.append(
                        {
                            "id": tc.get("id"),
                            "tool": name,
                            "action": decision.action.value,
                            "risk": decision.risk.value,
                            "reasons": [r.code for r in decision.reasons if r.action != Action.ALLOW],
                            "approval_id": decision.approval_id,
                            "audit_seq": decision.audit_seq,
                        }
                    )
                    if decision.allowed:
                        kept.append(tc)
                    else:
                        blocked.append(block_message(decision, name))
                if kept:
                    msg["tool_calls"] = kept
                else:
                    msg.pop("tool_calls", None)
            fc = msg.get("function_call")
            if isinstance(fc, dict):
                legacy = {"id": new_id("call_"), "type": "function", "function": fc}
                name, decision = await check_tool_call(gateway, legacy, session_id, agent_id)
                report.append({"id": legacy["id"], "tool": name, "action": decision.action.value})
                if not decision.allowed:
                    msg.pop("function_call", None)
                    blocked.append(block_message(decision, name))
            if not blocked:
                continue
            explanation = "\n\n".join(blocked)
            existing = _content_text(msg.get("content"))
            msg["content"] = f"{existing}\n\n{explanation}" if existing.strip() else explanation
            if not msg.get("tool_calls") and not msg.get("function_call"):
                choice["finish_reason"] = "stop"

    @router.post("/v1/chat/completions")
    async def chat_completions(request: Request, agent: Annotated[Any, Depends(dependency)]) -> JSONResponse:
        gateway = getattr(request.app.state, "gateway", None)
        if gateway is None:
            raise HTTPException(status_code=503, detail="Mirsad gateway is not ready")
        settings = _settings(request)
        try:
            body = await request.json()
        except ValueError:
            raise HTTPException(status_code=400, detail="request body must be JSON") from None
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="request body must be a JSON object")
        if body.get("stream"):
            raise HTTPException(
                status_code=400, detail="Streaming is not supported by the Mirsad proxy; send stream=false."
            )
        messages = body.get("messages")
        if not isinstance(messages, list) or not messages:
            raise HTTPException(status_code=400, detail="'messages' must be a non-empty list")
        agent_id = str(getattr(agent, "policy_agent_id", "") or getattr(agent, "id", ""))
        if not agent_id:
            raise HTTPException(status_code=500, detail="agent identity is missing")
        session_id = session_id_for(messages, agent_id, request.headers.get(SESSION_HEADER))

        result_report: list[dict[str, Any]] = []
        call_report: list[dict[str, Any]] = []
        body["messages"] = await inspect_messages(gateway, messages, session_id, agent_id, result_report)
        filter_tool_definitions(gateway, body, agent_id)
        body.setdefault("model", getattr(settings, "llm_model", None))
        body.pop("stream_options", None)

        url = str(settings.llm_base_url).rstrip("/") + "/chat/completions"
        headers = _upstream_headers(request, settings)
        try:
            if http_client is not None:
                upstream = await http_client.post(url, json=body, headers=headers, timeout=upstream_timeout_s)
            else:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(upstream_timeout_s, connect=10.0)
                ) as client:
                    upstream = await client.post(url, json=body, headers=headers)
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Upstream LLM timed out") from None
        except httpx.HTTPError as exc:
            logger.warning("upstream LLM unreachable at %s: %r", url, exc)
            raise HTTPException(status_code=502, detail="Upstream LLM is unreachable") from None

        response_headers = {SESSION_HEADER: session_id}
        if upstream.status_code >= 400:
            try:
                err_body: Any = upstream.json()
            except ValueError:
                err_body = {"error": {"message": upstream.text[:2000], "type": "upstream_error"}}
            return JSONResponse(err_body, status_code=upstream.status_code, headers=response_headers)
        try:
            data = upstream.json()
        except ValueError:
            raise HTTPException(status_code=502, detail="Upstream LLM returned invalid JSON") from None
        if not isinstance(data, dict):
            raise HTTPException(status_code=502, detail="Upstream LLM returned an unexpected payload")

        await check_response(gateway, data, session_id, agent_id, call_report)
        data["mirsad"] = {"session_id": session_id, "tool_calls": call_report, "tool_results": result_report}
        return JSONResponse(data, headers=response_headers)

    return router
