"""The ``mirsad`` command line (click CliRunner on a temporary data dir)."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner
from tests.api.conftest import default_overrides, make_settings
from tests.api.fakes import policy_text

from mirsad.cli import main


@pytest.fixture
def cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("MIRSAD_ADMIN_PASSWORD", raising=False)
    settings = make_settings(tmp_path)
    runner = CliRunner()

    def run(*args: str, input: str | None = None) -> Any:
        return runner.invoke(main, list(args), obj={"settings": settings, "overrides": default_overrides()},
                             input=input, catch_exceptions=False)

    run.settings = settings  # type: ignore[attr-defined]
    return run


def _db(settings):
    from mirsad.storage import Database

    return Database(settings.resolved_database_url())


def test_init_writes_private_credentials_file_and_prints_only_its_path(cli):
    r = cli("init")
    assert r.exit_code == 0, r.output
    path = cli.settings.data_dir.resolve() / "credentials.txt"
    assert f"Credentials written to {path}" in r.output
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    content = path.read_text()
    from mirsad import auth

    db = _db(cli.settings)
    for role in ("admin", "approver", "auditor"):
        line = next(x for x in content.splitlines() if x.startswith(role))
        password = line.split("password=")[1].strip()
        assert password not in r.output
        assert auth.authenticate_user(db, role, password) is not None
    again = cli("init")
    assert "already exists" in again.output and "Nothing new to create" in again.output


def test_init_demo_creates_agent_and_honours_admin_password(cli):
    r = cli("init", "--demo", "--admin-password", "my-admin-password-1")
    assert r.exit_code == 0, r.output
    content = (cli.settings.data_dir / "credentials.txt").read_text()
    key = content.split("api_key=")[1].split()[0]
    assert key.startswith("mk_") and key not in r.output and "my-admin-password-1" not in content
    from mirsad import auth

    db = _db(cli.settings)
    agent = auth.authenticate_agent_key(db, key)
    assert agent.policy_agent_id == "email-crm-assistant"
    assert auth.authenticate_user(db, "admin", "my-admin-password-1") is not None


def test_policy_validate(cli, tmp_path):
    good = tmp_path / "good.yaml"
    good.write_text(policy_text())
    assert cli("policy", "validate", str(good)).exit_code == 0
    bad = tmp_path / "bad.yaml"
    bad.write_text("version: 1\nagents: notalist\n")
    r = cli("policy", "validate", str(bad))
    assert r.exit_code == 1 and "error:" in r.output


def test_policy_activate_persists_and_audits(cli, tmp_path):
    cli("init")
    new = tmp_path / "new.yaml"
    new.write_text(policy_text(extra_tools="      rm_rf: {allow: true}\n"))
    r = cli("policy", "activate", str(new), "--comment", "allow rm")
    assert r.exit_code == 0 and "Activated policy" in r.output
    from mirsad.api.store import PolicyStore, Tables

    store = PolicyStore(Tables(_db(cli.settings)))
    active = store.active()
    assert "rm_rf" in active["yaml_text"] and active["comment"] == "allow rm" and len(store.list()) == 2
    verify = cli("audit", "verify")
    assert verify.exit_code == 0 and json.loads(verify.output)["ok"] is True


def test_user_and_agent_create(cli, tmp_path):
    r = cli("user", "create", "noura", "--role", "approver", "--password", "noura-password-1", "--lang", "ar")
    assert r.exit_code == 0 and "noura-password-1" not in r.output
    dup = CliRunner().invoke(main, ["user", "create", "noura", "--role", "auditor", "--password", "x" * 12],
                             obj={"settings": cli.settings, "overrides": default_overrides()})
    assert dup.exit_code != 0 and "exists" in dup.output
    shown = cli("agent", "create", "CRM Bot", "--policy-agent", "test-agent")
    assert shown.exit_code == 0 and "crm-bot" in shown.output
    key = shown.output.strip().splitlines()[-1]
    assert key.startswith("mk_")
    key_file = tmp_path / "bot.key"
    hidden = cli("agent", "create", "Other", "--policy-agent", "test-agent", "--id", "other-bot",
                 "--key-file", str(key_file))
    assert "mk_" not in hidden.output and key_file.read_text().startswith("mk_")
    if os.name != "nt":
        assert stat.S_IMODE(key_file.stat().st_mode) == 0o600


def test_audit_verify_detects_tampering_and_export(cli, tmp_path):
    cli("init")
    out = tmp_path / "audit.json"
    r = cli("audit", "export", "--format", "json", "--out", str(out))
    assert r.exit_code == 0 and json.loads(out.read_text())["count"] >= 3
    from sqlalchemy import text

    with _db(cli.settings).engine.begin() as conn:
        conn.execute(text("UPDATE audit_events SET event_type = 'forged' WHERE seq = 1"))
    bad = cli("audit", "verify")
    assert bad.exit_code == 1 and json.loads(bad.output)["ok"] is False


def test_audit_replay_and_scan(cli):
    from mirsad.api.components import build_components
    from mirsad.models import ToolCall

    comps = build_components(cli.settings, default_overrides())
    import asyncio

    d = asyncio.run(comps.gateway.check_call(ToolCall(session_id="s", agent_id="test-agent", tool="rm_rf")))
    r = cli("audit", "replay", str(d.audit_seq))
    assert r.exit_code == 0 and json.loads(r.output)["match"] is True
    assert cli("audit", "replay", "99999").exit_code == 1
    s = cli("scan", "Please SAMPLE-FLAGGED-TEXT now")
    assert json.loads(s.output)["label"] == "injection"
    import click

    with pytest.raises(click.UsageError):
        CliRunner().invoke(main, ["scan"], obj={"settings": cli.settings, "overrides": default_overrides()},
                           catch_exceptions=False, standalone_mode=False)


def test_detector_train_delegates_to_training_module(cli, monkeypatch):
    import runpy
    import sys

    seen: dict[str, Any] = {}

    def fake_run_module(name: str, **kwargs: Any) -> None:
        seen["name"], seen["argv"] = name, list(sys.argv)

    monkeypatch.setattr(runpy, "run_module", fake_run_module)
    r = cli("detector", "train", "--data", "data/detector", "--out", "model")
    assert r.exit_code == 0
    assert seen == {"name": "mirsad.detector.train", "argv": ["mirsad.detector.train", "--data", "data/detector",
                                                              "--out", "model"]}


def test_mcp_proxy_requires_agent_key(cli, monkeypatch):
    monkeypatch.delenv("MIRSAD_AGENT_KEY", raising=False)
    r = CliRunner().invoke(main, ["mcp-proxy"], obj={"settings": cli.settings})
    assert r.exit_code == 2 and "agent-key" in r.output
