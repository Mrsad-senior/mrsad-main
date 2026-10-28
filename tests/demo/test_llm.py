"""Live LLM smoke test against a running Ollama (qwen2.5:7b).

Marked ``llm`` so it is skipped by default: ``pytest -m llm`` to run it. It only
checks that the tool-calling loop completes against the real model; it does not
assert anything about whether an attack succeeds (model behaviour is not
deterministic enough for that).
"""

from __future__ import annotations

import httpx
import pytest
from demo.agent import DEFAULT_LLM_BASE_URL, DEFAULT_MODEL, DemoAgent, DirectBackend
from demo.scenarios import apply_scenario
from demo.world import World

pytestmark = pytest.mark.llm


def _ollama_up() -> bool:
    try:
        httpx.get(f"{DEFAULT_LLM_BASE_URL}/models", timeout=3.0).raise_for_status()
        return True
    except Exception:
        return False


async def test_live_scenario_loop_completes():
    if not _ollama_up():
        pytest.skip("Ollama is not reachable")
    world = World()
    scenario = apply_scenario(world, "invoice-exfil")
    agent = DemoAgent(
        backend=DirectBackend(world),
        model=DEFAULT_MODEL,
        session_id="llm-test",
    )
    transcript = await agent.run(scenario.user_prompt_en)
    # The loop terminated cleanly and the agent used at least one tool.
    assert transcript.stopped_reason in {"completed", "max_steps", "max_rounds"}
    assert len(transcript.steps) >= 1
    assert all(step.tool for step in transcript.steps)
