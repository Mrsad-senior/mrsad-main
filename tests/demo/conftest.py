"""Shared fakes for the demo agent tests: a scripted LLM and a fake gateway."""

from __future__ import annotations

import json
from typing import Any

import httpx

from mirsad.models import (
    Action,
    Decision,
    GatewayResponse,
    InspectionOutcome,
    Reason,
    Sensitivity,
    ToolCall,
    Trust,
)


def make_llm(script: list[dict[str, Any]]) -> httpx.AsyncClient:
    """An httpx client whose transport replays ``script`` assistant messages in order.

    Each entry is either ``{"tool": name, "arguments": {...}}`` for a tool call or
    ``{"text": "..."}`` for a final reply. The last entry repeats if the loop asks
    for more.
    """
    state = {"i": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        idx = min(state["i"], len(script) - 1)
        step = script[idx]
        state["i"] += 1
        if "tool" in step:
            msg = {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": f"c{idx}",
                        "type": "function",
                        "function": {
                            "name": step["tool"],
                            "arguments": json.dumps(step.get("arguments", {})),
                        },
                    }
                ],
            }
            finish = "tool_calls"
        else:
            msg = {"role": "assistant", "content": step.get("text", "done")}
            finish = "stop"
        return httpx.Response(200, json={"choices": [{"message": msg, "finish_reason": finish}]})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


class FakeGateway:
    """Allows everything except tools in ``deny_tools``; runs allowed calls via the executor."""

    def __init__(self, deny_tools: set[str] | None = None):
        self.deny_tools = deny_tools or set()
        self.calls: list[ToolCall] = []

    async def execute(self, call: ToolCall, executor: Any) -> GatewayResponse:
        self.calls.append(call)
        if call.tool in self.deny_tools:
            decision = Decision(
                call_id=call.call_id,
                action=Action.DENY,
                reasons=[Reason(
                    layer="taint", code="TAINT_UNTRUSTED_TO_EXTERNAL",
                    message="untrusted content reaching an external sink",
                    message_ar="محتوى غير موثوق يصل إلى وجهة خارجية",
                    action=Action.DENY, risk_score=0.6,
                )],
            )
            return GatewayResponse(decision=decision, result=None)
        result = await executor(call)
        decision = Decision(call_id=call.call_id, action=Action.ALLOW)
        inspection = InspectionOutcome(
            call_id=call.call_id, action="pass", content=result.content,
            structured=result.structured, trust=Trust.UNTRUSTED, sensitivity=Sensitivity.INTERNAL,
        )
        return GatewayResponse(decision=decision, result=inspection)
