"""Shared connection settings for the optional LLM security judges."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_JUDGE_BASE_URL = "http://127.0.0.1:11434/v1"
DEFAULT_JUDGE_MODEL = "qwen2.5:3b"


@dataclass(frozen=True)
class JudgeConnection:
    """Resolved OpenAI-compatible endpoint used by both security judges."""

    base_url: str
    api_key: str | None
    model: str


def _value(environment: Mapping[str, str], name: str) -> str | None:
    value = environment.get(name, "").strip()
    return value or None


def resolve_judge_connection(environment: Mapping[str, str] | None = None) -> JudgeConnection:
    """Resolve judge-specific settings, then shared LLM settings, then local Ollama.

    Empty values deliberately count as unset. This lets deployments add the
    judge variables to an example file while still sharing the main LLM endpoint.
    """

    env = os.environ if environment is None else environment
    return JudgeConnection(
        base_url=(
            _value(env, "MIRSAD_JUDGE_BASE_URL")
            or _value(env, "MIRSAD_LLM_BASE_URL")
            or DEFAULT_JUDGE_BASE_URL
        ),
        api_key=_value(env, "MIRSAD_JUDGE_API_KEY") or _value(env, "MIRSAD_LLM_API_KEY"),
        model=_value(env, "MIRSAD_JUDGE_MODEL") or DEFAULT_JUDGE_MODEL,
    )
