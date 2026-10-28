"""``mirsad`` command line: run the server, bootstrap users, manage policies, audit and detector.

Secrets (generated passwords, agent keys) are never logged. ``mirsad init`` writes them to a
``credentials.txt`` file with mode 0600 and prints only its path; ``agent create`` prints the
key exactly once (or writes it to ``--key-file``).
"""

from __future__ import annotations

import asyncio
import getpass
import json
import logging
import os
import re
import runpy
import sys
import time
from pathlib import Path
from typing import Any

import click

from mirsad import __version__
from mirsad.config import Settings

log = logging.getLogger("mirsad.cli")

DEMO_AGENT_ID = "demo-agent"
DEMO_POLICY_AGENT = "email-crm-assistant"
INIT_USERS = (("admin", "admin", "Administrator"), ("approver", "approver", "Approver"),
              ("auditor", "auditor", "Auditor"))


# --------------------------------------------------------------------------- helpers


def _settings(ctx: click.Context) -> Settings:
    return ctx.obj["settings"]


def _overrides(ctx: click.Context) -> dict[str, Any]:
    return ctx.obj.get("overrides") or {}


def _core(ctx: click.Context) -> tuple[Any, Any, Any]:
    """(db, audit, auth) without loading the policy engine, detector or upstreams."""
    import importlib

    o = _overrides(ctx)
    settings = _settings(ctx)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    auth = o.get("auth") or importlib.import_module("mirsad.auth")
    if "db" in o:
        db = o["db"]
    else:
        from mirsad.storage import Database

        db = Database(settings.resolved_database_url())
        db.create_all()
    if "audit" in o:
        audit = o["audit"]
    else:
        from mirsad.audit import AuditLog, audit_key_from_secret

        audit = AuditLog(db, audit_key_from_secret(settings.resolved_secret_key()),
                         payload_max_chars=settings.audit_payload_max_chars)
    return db, audit, auth


def _components(ctx: click.Context) -> Any:
    from mirsad.api.components import build_components

    return build_components(_settings(ctx), _overrides(ctx))


def _policy_module(ctx: click.Context) -> Any:
    import importlib

    return _overrides(ctx).get("policy_module") or importlib.import_module("mirsad.policy")


def _actor() -> str:
    try:
        return f"cli:{getpass.getuser()}"
    except Exception:
        return "cli"


def _echo_json(value: Any) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    click.echo(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def _write_secret_file(path: Path, text: str) -> None:
    """Append ``text`` to ``path`` with owner-only permissions (created 0600, tightened if it existed)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, text.encode("utf-8"))
    finally:
        os.close(fd)
    path.chmod(0o600)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return (slug or "agent")[:64]


# --------------------------------------------------------------------------- root


@click.group()
@click.version_option(__version__, prog_name="mirsad")
@click.option("--data-dir", type=click.Path(path_type=Path), default=None,
              help="Data directory (database, secret key). Default: $MIRSAD_DATA_DIR or .mirsad")
@click.option("--log-level", default=None, help="Logging level (default: $MIRSAD_LOG_LEVEL or INFO)")
@click.pass_context
def main(ctx: click.Context, data_dir: Path | None, log_level: str | None) -> None:
    """Mirsad (مرصاد): runtime security firewall for AI agents."""
    ctx.ensure_object(dict)
    if "settings" not in ctx.obj:
        ctx.obj["settings"] = Settings(**({"data_dir": data_dir} if data_dir else {}))
    elif data_dir:
        ctx.obj["settings"] = ctx.obj["settings"].model_copy(update={"data_dir": data_dir})
    level = (log_level or ctx.obj["settings"].log_level or "INFO").upper()
    # stderr only: stdout carries command output (and MCP messages for mcp-proxy).
    logging.basicConfig(level=getattr(logging, level, logging.INFO), stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")


# --------------------------------------------------------------------------- serve / init


@main.command()
@click.option("--host", default=None, help="Bind address (default: $MIRSAD_HOST or 127.0.0.1)")
@click.option("--port", type=int, default=None, help="Port (default: $MIRSAD_PORT or 8700)")
@click.option("--demo/--no-demo", default=None, help="Enable the Demo Console endpoints")
@click.pass_context
def serve(ctx: click.Context, host: str | None, port: int | None, demo: bool | None) -> None:
    """Run the gateway, API, dashboard and approver PWA."""
    import uvicorn

    from mirsad.api import create_app

    updates = {k: v for k, v in {"host": host, "port": port, "enable_demo": demo}.items() if v is not None}
    settings = _settings(ctx).model_copy(update=updates)
    app = create_app(settings, gateway_overrides=_overrides(ctx) or None)
    click.echo(f"Mirsad {__version__} listening on http://{settings.host}:{settings.port}  (docs: /docs)", err=True)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level.lower(),
                proxy_headers=False, server_header=False)


@main.command()
@click.option("--demo", is_flag=True, help=f"Also create the demo agent '{DEMO_AGENT_ID}' ({DEMO_POLICY_AGENT})")
@click.option("--admin-password", envvar="MIRSAD_ADMIN_PASSWORD", default=None,
              help="Admin password (default: $MIRSAD_ADMIN_PASSWORD, else generated)")
@click.pass_context
def init(ctx: click.Context, demo: bool, admin_password: str | None) -> None:
    """Create the database, the initial policy version, admin/approver/auditor users (and the demo agent).

    Generated credentials go to <data_dir>/credentials.txt (mode 600); only that path is printed.
    """
    from mirsad.api.components import generate_password, load_initial_policy
    from mirsad.api.store import PolicyStore, Tables

    settings = _settings(ctx)
    db, audit, auth = _core(ctx)
    try:
        store = PolicyStore(Tables(db))
        engine = load_initial_policy(settings, _policy_module(ctx), store)
        click.echo(f"Active policy version: {engine.version[:12]}")
    except ImportError:
        click.echo("Policy engine not available; skipped storing the initial policy.", err=True)

    lines: list[str] = []
    existing = {u.username for u in auth.list_users(db)}
    for username, role, display in INIT_USERS:
        if username in existing:
            click.echo(f"User '{username}' already exists; left unchanged.")
            continue
        provided = role == "admin" and admin_password
        password = admin_password if provided else generate_password()
        auth.create_user(db, username, password, role, display_name=display)
        audit.append("user.created", payload={"username": username, "role": role, "created_by": _actor()})
        lines.append(f"{role:<9} username={username}  password="
                     f"{'(provided via --admin-password / MIRSAD_ADMIN_PASSWORD)' if provided else password}")
    if demo:
        if auth.get_agent(db, DEMO_AGENT_ID) is not None:
            click.echo(f"Agent '{DEMO_AGENT_ID}' already exists; use `mirsad agent create` or rotate its key "
                       "in the dashboard.")
        else:
            _info, key = auth.create_agent(db, DEMO_AGENT_ID, "Demo Email & CRM Assistant", DEMO_POLICY_AGENT,
                                           description="Created by `mirsad init --demo`")
            audit.append("agent.created", agent_id=DEMO_POLICY_AGENT,
                         payload={"id": DEMO_AGENT_ID, "policy_agent_id": DEMO_POLICY_AGENT, "created_by": _actor()})
            lines.append(f"agent     id={DEMO_AGENT_ID}  policy_agent={DEMO_POLICY_AGENT}  api_key={key}")
    if not lines:
        click.echo("Nothing new to create.")
        return
    path = settings.data_dir.resolve() / "credentials.txt"
    stamp = time.strftime("%Y-%m-%d %H:%M:%S %Z")
    _write_secret_file(path, f"# Mirsad credentials generated by `mirsad init` on {stamp}.\n"
                             "# Store them in a password manager, then delete this file.\n"
                             + "\n".join(lines) + "\n\n")
    click.echo(f"Credentials written to {path} (mode 600).")
    if demo:
        click.echo("Start the server with: mirsad serve --demo")


# --------------------------------------------------------------------------- policy


@main.group()
def policy() -> None:
    """Validate and activate policy files."""


@policy.command("validate")
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_context
def policy_validate(ctx: click.Context, file: Path) -> None:
    """Check a policy YAML file; exit code 1 when it is invalid."""
    from mirsad.api.routers.policies import validate_text

    errors = validate_text(_policy_module(ctx), file.read_text(encoding="utf-8"))
    if errors:
        for err in errors:
            click.echo(f"error: {err}", err=True)
        raise SystemExit(1)
    click.echo(f"{file}: valid")


@policy.command("activate")
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--comment", default=None, help="Change note stored with the version")
@click.pass_context
def policy_activate(ctx: click.Context, file: Path, comment: str | None) -> None:
    """Store FILE as a new policy version and make it active (a running server picks it up within seconds)."""
    from mirsad.api.routers.policies import validate_text
    from mirsad.api.store import PolicyStore, Tables

    text = file.read_text(encoding="utf-8")
    module = _policy_module(ctx)
    errors = validate_text(module, text)
    if errors:
        for err in errors:
            click.echo(f"error: {err}", err=True)
        raise SystemExit(1)
    engine = module.PolicyEngine.from_yaml(text)
    db, audit, _auth = _core(ctx)
    store = PolicyStore(Tables(db))
    previous = store.active_version()
    store.save(engine.version, text, created_by=_actor(), comment=comment or f"activated from {file.name}")
    store.activate(engine.version)
    audit.append("policy.activated", policy_version=engine.version,
                 payload={"version": engine.version, "previous_version": previous, "activated_by": _actor(),
                          "comment": comment, "source": "cli"})
    click.echo(f"Activated policy {engine.version[:12]} (previous: {(previous or '-')[:12]}).")


# --------------------------------------------------------------------------- audit


@main.group("audit")
def audit_group() -> None:
    """Verify, export and replay the tamper-evident audit log."""


@audit_group.command("verify")
@click.pass_context
def audit_verify(ctx: click.Context) -> None:
    """Recompute the HMAC hash chain; exit code 1 if it is broken."""
    _db, audit, _auth = _core(ctx)
    report = audit.verify()
    _echo_json(report)
    if not getattr(report, "ok", False):
        raise SystemExit(1)


@audit_group.command("export")
@click.option("--format", "fmt", type=click.Choice(["json", "csv"]), default="json", show_default=True)
@click.option("--out", type=click.Path(dir_okay=False, path_type=Path), default=None, help="File (default stdout)")
@click.option("--agent-id", default=None)
@click.option("--tool", default=None)
@click.option("--action", default=None)
@click.option("--event-type", default=None)
@click.option("--since", type=float, default=None, help="epoch seconds")
@click.option("--until", type=float, default=None, help="epoch seconds")
@click.pass_context
def audit_export(ctx: click.Context, fmt: str, out: Path | None, **filters: Any) -> None:
    """Export audit events (JSON keeps the chain fields for offline verification)."""
    _db, audit, _auth = _core(ctx)
    body = audit.export(fmt, **{k: v for k, v in filters.items() if v is not None})
    if out is None:
        click.echo(body)
    else:
        out.write_text(body, encoding="utf-8")
        click.echo(f"Wrote {out}", err=True)


@audit_group.command("replay")
@click.argument("seq", type=int)
@click.pass_context
def audit_replay(ctx: click.Context, seq: int) -> None:
    """Re-evaluate a stored decision/inspection event with the policy version it recorded."""
    from mirsad.gateway import ReplayError

    comps = _components(ctx)
    try:
        report = comps.gateway.replay(seq)
    except KeyError:
        click.echo(f"error: audit event {seq} not found", err=True)
        raise SystemExit(1) from None
    except ReplayError as exc:
        click.echo(f"error: {exc}", err=True)
        raise SystemExit(1) from None
    _echo_json(report)


# --------------------------------------------------------------------------- detector / scan


@main.command()
@click.argument("text", required=False)
@click.option("--file", "file", type=click.Path(exists=True, dir_okay=False, path_type=Path), default=None)
@click.pass_context
def scan(ctx: click.Context, text: str | None, file: Path | None) -> None:
    """Scan TEXT (or --file) for prompt injection and print the DetectionResult."""
    if (text is None) == (file is None):
        raise click.UsageError("give exactly one of TEXT or --file")
    content = text if text is not None else file.read_text(encoding="utf-8")  # type: ignore[union-attr]
    detector = _overrides(ctx).get("detector")
    if detector is None:
        from mirsad.detector import InjectionDetector

        detector = InjectionDetector.default()
    _echo_json(detector.scan(content))


@main.group("detector")
def detector_group() -> None:
    """Injection detector model tools."""


@detector_group.command("train", context_settings={"ignore_unknown_options": True, "allow_extra_args": True})
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def detector_train(args: tuple[str, ...]) -> None:
    """Train the detector (delegates to ``python -m mirsad.detector.train``; extra args are passed through)."""
    saved = sys.argv
    sys.argv = ["mirsad.detector.train", *args]
    try:
        runpy.run_module("mirsad.detector.train", run_name="__main__", alter_sys=True)
    finally:
        sys.argv = saved


# --------------------------------------------------------------------------- agents / users


@main.group()
def agent() -> None:
    """Manage agent identities."""


@agent.command("create")
@click.argument("name")
@click.option("--policy-agent", "policy_agent", required=True, help="Agent id in the policy YAML")
@click.option("--id", "agent_id", default=None, help="Slug (default: derived from NAME)")
@click.option("--description", default="")
@click.option("--key-file", type=click.Path(dir_okay=False, path_type=Path), default=None,
              help="Write the API key to this file (mode 600) instead of printing it")
@click.pass_context
def agent_create(ctx: click.Context, name: str, policy_agent: str, agent_id: str | None, description: str,
                 key_file: Path | None) -> None:
    """Register an agent and show its API key once."""
    db, audit, auth = _core(ctx)
    slug = agent_id or _slugify(name)
    try:
        _info, key = auth.create_agent(db, slug, name, policy_agent, description=description)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    audit.append("agent.created", agent_id=policy_agent,
                 payload={"id": slug, "name": name, "policy_agent_id": policy_agent, "created_by": _actor()})
    if key_file is not None:
        _write_secret_file(key_file, key + "\n")
        click.echo(f"Agent '{slug}' created; API key written to {key_file} (mode 600).")
    else:
        click.echo(f"Agent '{slug}' created. API key (shown once, store it securely):")
        click.echo(key)


@main.group()
def user() -> None:
    """Manage human users."""


@user.command("create")
@click.argument("username")
@click.option("--role", type=click.Choice(["admin", "approver", "auditor"]), required=True)
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True,
              envvar="MIRSAD_NEW_USER_PASSWORD", help="Prompted (hidden) when omitted")
@click.option("--display-name", default="")
@click.option("--lang", type=click.Choice(["en", "ar"]), default="en", show_default=True)
@click.pass_context
def user_create(ctx: click.Context, username: str, role: str, password: str, display_name: str, lang: str) -> None:
    """Create a dashboard / approver user."""
    db, audit, auth = _core(ctx)
    try:
        auth.create_user(db, username, password, role, display_name=display_name, lang=lang)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    audit.append("user.created", payload={"username": username, "role": role, "created_by": _actor()})
    click.echo(f"User '{username}' created with role {role}.")


# --------------------------------------------------------------------------- MCP stdio proxy


@main.command("mcp-proxy")
@click.option("--agent-key", envvar="MIRSAD_AGENT_KEY", required=True, help="Agent API key (or $MIRSAD_AGENT_KEY)")
@click.option("--url", default="http://127.0.0.1:8700", show_default=True, help="Base URL of the Mirsad server")
@click.option("--session-id", default=None, help="Session id for taint tracking (default: one per process)")
def mcp_proxy(agent_key: str, url: str, session_id: str | None) -> None:
    """Serve MCP over stdio, forwarding every tool call to a running Mirsad gateway."""
    from mirsad.adapters.mcp_proxy import run_stdio_proxy

    asyncio.run(run_stdio_proxy(url, agent_key, session_id=session_id))


if __name__ == "__main__":  # pragma: no cover
    main()
