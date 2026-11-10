from __future__ import annotations

import json

import httpx

from mirsad.detector.layered import OllamaJudge
from mirsad.llm_config import DEFAULT_JUDGE_BASE_URL, DEFAULT_JUDGE_MODEL, resolve_judge_connection
from mirsad.security.intent import OllamaIntentJudge


def test_judge_connection_defaults_to_local_ollama_without_key():
    connection = resolve_judge_connection({})

    assert connection.base_url == DEFAULT_JUDGE_BASE_URL
    assert connection.api_key is None
    assert connection.model == DEFAULT_JUDGE_MODEL


def test_judge_connection_falls_back_to_shared_llm_settings_when_specific_values_are_empty():
    connection = resolve_judge_connection({
        "MIRSAD_JUDGE_BASE_URL": "  ",
        "MIRSAD_JUDGE_API_KEY": "",
        "MIRSAD_LLM_BASE_URL": " https://api.groq.com/openai/v1/ ",
        "MIRSAD_LLM_API_KEY": " shared-secret ",
        "MIRSAD_JUDGE_MODEL": " hosted-model ",
    })

    assert connection.base_url == "https://api.groq.com/openai/v1/"
    assert connection.api_key == "shared-secret"
    assert connection.model == "hosted-model"


def test_judge_specific_connection_takes_precedence_over_shared_llm_settings():
    connection = resolve_judge_connection({
        "MIRSAD_JUDGE_BASE_URL": "https://judge.example/v1",
        "MIRSAD_JUDGE_API_KEY": "judge-secret",
        "MIRSAD_LLM_BASE_URL": "https://shared.example/v1",
        "MIRSAD_LLM_API_KEY": "shared-secret",
    })

    assert connection.base_url == "https://judge.example/v1"
    assert connection.api_key == "judge-secret"


def test_content_judge_sends_bearer_key_to_openai_compatible_endpoint():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://judge.example/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer judge-secret"
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({
            "instruction_to_agent": True,
            "score": 0.9,
            "reason": "The document directs an unrelated action.",
        })}}]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = OllamaJudge(base_url="https://judge.example/v1", api_key="judge-secret",
                             client=client).score("untrusted content")

    assert result.score == 0.9


def test_intent_judge_omits_authorization_header_without_key():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == f"{DEFAULT_JUDGE_BASE_URL}/chat/completions"
        assert "Authorization" not in request.headers
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({
            "authorized": True,
            "confidence": 0.95,
            "risk_level": "low",
            "reason": "The proposed lookup matches the original request.",
        })}}]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = OllamaIntentJudge(client=client).assess(
            "Look up account ACC-001", "get_account_balance", {"account_id": "ACC-001"})

    assert result.authorized is True


def test_intent_judge_sends_bearer_key_when_configured():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer intent-secret"
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({
            "authorized": False,
            "confidence": 0.91,
            "risk_level": "high",
            "reason": "The original request does not authorize this transfer.",
        })}}]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = OllamaIntentJudge(api_key="intent-secret", client=client).assess(
            "Summarize the invoice", "transfer_funds", {"amount_sar": 500})

    assert result.authorized is False
