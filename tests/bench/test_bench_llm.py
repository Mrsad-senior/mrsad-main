"""LLM agent smoke test against the local Ollama model (deselect with -m 'not llm')."""

from __future__ import annotations

import httpx
import pytest
from bench.agents import LLMAgent
from bench.defenses import DefenseRuntime
from bench.run import run_episode

pytestmark = pytest.mark.llm


def _ollama_up() -> bool:
    try:
        return httpx.get("http://127.0.0.1:11434/api/tags", timeout=3).status_code == 200
    except httpx.HTTPError:
        return False


@pytest.mark.skipif(not _ollama_up(), reason="Ollama is not running on 127.0.0.1:11434")
async def test_llm_agent_reads_a_document_through_the_gateway(suite, tmp_path):
    rec = await run_episode(suite.task("en-doc-read-01"), LLMAgent(), DefenseRuntime("full", "oracle",
                                                                                      workdir=tmp_path))
    assert rec["error"] is None
    assert any(c["tool"] == "read_document" for c in rec["calls"])
    assert rec["answer_preview"]
