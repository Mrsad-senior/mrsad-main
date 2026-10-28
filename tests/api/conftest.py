"""Fixtures for the api area: an app on a temporary data dir with real storage/auth/audit/approvals/taint
(and the real policy engine when importable), plus a fake detector so results are deterministic."""

from __future__ import annotations

import importlib
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from tests.api.fakes import FAKE_POLICY_MODULE, TEST_POLICY, FakeDetector, fake_sanitize, fake_spotlight

from mirsad.api import create_app
from mirsad.config import Settings


def _real_policy_available() -> bool:
    try:
        return hasattr(importlib.import_module("mirsad.policy"), "PolicyEngine")
    except Exception:
        return False


REAL_POLICY = _real_policy_available()
SECRET = "test-secret-key-0123456789abcdef0123456789"
PASSWORD = "correct-horse-battery"


def make_settings(tmp_path: Path, *, policy: str = TEST_POLICY, **kw: Any) -> Settings:
    policy_file = tmp_path / "policy.yaml"
    policy_file.write_text(policy, encoding="utf-8")
    base: dict[str, Any] = {
        "data_dir": tmp_path / "data", "secret_key": SECRET, "policy_path": policy_file,
        "upstreams_path": tmp_path / "no-upstreams.yaml", "approval_timeout_s": 5.0,
        "cors_origins": ["http://localhost:5173"], "enable_demo": False,
    }
    base.update(kw)
    return Settings(**base)


def default_overrides() -> dict[str, Any]:
    o: dict[str, Any] = {"detector": FakeDetector(), "sanitizer": fake_sanitize, "spotlighter": fake_spotlight}
    if not REAL_POLICY:
        o["policy_module"] = FAKE_POLICY_MODULE
    return o


class Api:
    """Test helper around one app instance and an ASGI client."""

    def __init__(self, app: Any, client: httpx.AsyncClient) -> None:
        self.app = app
        self.client = client

    @property
    def comps(self) -> Any:
        return self.app.state.components

    def user(self, username: str, role: str, password: str = PASSWORD) -> str:
        """Create a user and return a bearer token for it."""
        auth = self.comps.auth
        if auth.get_user(self.comps.db, username) is None:
            auth.create_user(self.comps.db, username, password, role)
        return auth.create_token(username, role, self.comps.secret, 1)

    def h(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def admin(self) -> dict[str, str]:
        return self.h(self.user("admin1", "admin"))

    def approver(self) -> dict[str, str]:
        return self.h(self.user("approver1", "approver"))

    def auditor(self) -> dict[str, str]:
        return self.h(self.user("auditor1", "auditor"))

    def agent(self, agent_id: str = "agent-one", policy_agent: str = "test-agent") -> dict[str, str]:
        _info, key = self.comps.auth.create_agent(self.comps.db, agent_id, agent_id.title(), policy_agent)
        return {"Authorization": f"Bearer {key}"}

    def register_tool(self, name: str, fn: Callable[..., Any], schema: dict[str, Any] | None = None) -> None:
        self.comps.upstreams.register_python(name, fn, f"{name} tool", schema or {"type": "object", "properties": {}})


@pytest.fixture
def make_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[..., Any]:
    monkeypatch.delenv("MIRSAD_ADMIN_PASSWORD", raising=False)

    def factory(*, policy: str = TEST_POLICY, overrides: dict[str, Any] | None = None,
                static_dir: Path | None = None, **settings_kw: Any) -> Any:
        settings = make_settings(tmp_path, policy=policy, **settings_kw)
        o = default_overrides()
        o.update(overrides or {})
        return create_app(settings, gateway_overrides=o, static_dir=static_dir or tmp_path / "no-static")

    return factory


@pytest.fixture
async def api(make_app: Callable[..., Any]) -> AsyncIterator[Api]:
    app = make_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        yield Api(app, client)


@pytest.fixture
def api_factory(make_app: Callable[..., Any]) -> Callable[..., Any]:
    """Build an Api for a custom app configuration (use as ``async with api_factory(...) as api``)."""
    import contextlib

    @contextlib.asynccontextmanager
    async def factory(**kw: Any) -> AsyncIterator[Api]:
        app = make_app(**kw)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as c:
            yield Api(app, c)

    return factory
