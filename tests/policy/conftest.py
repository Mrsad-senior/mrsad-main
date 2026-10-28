from __future__ import annotations

from collections.abc import Callable

import pytest
from policy_helpers import DEFAULT_POLICY, policy_text

from mirsad.policy import PolicyEngine, RateLimiter


@pytest.fixture
def default_text() -> str:
    return DEFAULT_POLICY.read_text(encoding="utf-8")


@pytest.fixture
def engine(default_text: str) -> PolicyEngine:
    """Default policy with a private rate limiter so tests never share counters."""
    return PolicyEngine.from_yaml(default_text, rate_limiter=RateLimiter())


@pytest.fixture
def build() -> Callable[..., PolicyEngine]:
    """Build an engine from a small agents/rules snippet (see ``policy_helpers.policy_text``)."""

    def _build(agents_yaml: str, *, rules_yaml: str = "", extra: str = "") -> PolicyEngine:
        return PolicyEngine.from_yaml(policy_text(agents_yaml, rules_yaml=rules_yaml, extra=extra),
                                      rate_limiter=RateLimiter())

    return _build
