"""Helpers shared by the policy tests (a uniquely named module, so it never clashes with other areas)."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from mirsad.models import ToolCall

ROOT = Path(__file__).resolve().parents[2]
POLICY_DIR = ROOT / "configs" / "policies"
DEFAULT_POLICY = POLICY_DIR / "default.yaml"
AGENT = "email-crm-assistant"


def make_call(tool: str, agent: str = AGENT, session: str = "s1", **arguments: Any) -> ToolCall:
    return ToolCall(session_id=session, agent_id=agent, tool=tool, arguments=arguments)


def policy_text(agents_yaml: str, *, rules_yaml: str = "", extra: str = "") -> str:
    """A small policy around an ``agents:`` body (indentation-insensitive)."""
    head = textwrap.dedent(
        """\
        version: 1
        organization:
          name: Test Org
          internal_domains: [najd-trading.example]
        """
    )
    body = "agents:\n" + textwrap.indent(textwrap.dedent(agents_yaml), "  ")
    rules = ("rules:\n" + textwrap.indent(textwrap.dedent(rules_yaml), "  ")) if rules_yaml else ""
    return head + textwrap.dedent(extra) + body + rules


def codes(reasons: list[Any]) -> list[str]:
    return [r.code for r in reasons]
