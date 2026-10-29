"""Construction of the runtime object graph (shared by the FastAPI app and the CLI).

Each component can be replaced through ``overrides`` (tests, benchmarks, embedding). Other
areas' modules are imported lazily so that importing the API never drags in heavy optional
dependencies, and a missing optional piece (e.g. upstreams) degrades instead of crashing.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mirsad.api.store import PolicyStore, Tables
from mirsad.config import PACKAGE_DIR, Settings
from mirsad.gateway import Gateway

log = logging.getLogger("mirsad.api")

#: Keys accepted in ``overrides`` / ``create_app(gateway_overrides=...)``.
OVERRIDE_KEYS = frozenset({
    "db", "audit", "notifier", "approvals", "policy", "policy_store", "taint", "detector", "upstreams",
    "gateway", "auth", "policy_module", "sanitizer", "spotlighter",
})

# Used when neither the database nor settings.policy_path provides a policy: deny everything.
DENY_ALL_POLICY = """\
version: 1
organization:
  name: Unconfigured
  internal_domains: []
defaults:
  decision: deny
agents: []
"""

# Used in demo mode when ``settings.upstreams_path`` does not exist (same entry as spec section 7.1).
DEMO_WORKSPACE_TARGET = "demo.workspace_server:server"
DEMO_UPSTREAMS: dict[str, Any] = {"upstreams": [{
    "name": "workspace", "transport": "inprocess", "target": DEMO_WORKSPACE_TARGET,
    "description": "Najd Trading Co. simulated workspace (fictional demo data)"}]}


@dataclass
class Components:
    settings: Settings
    db: Any
    tables: Tables
    audit: Any
    notifier: Any
    approvals: Any
    policy_store: Any
    policy: Any
    taint: Any
    detector: Any
    upstreams: Any
    gateway: Gateway
    auth: Any
    policy_module: Any
    secret: str = ""

    def as_state(self) -> dict[str, Any]:
        """The ``app.state`` attributes promised by the build spec (section 14)."""
        return {name: getattr(self, name) for name in (
            "settings", "db", "audit", "notifier", "approvals", "policy_store", "taint", "detector",
            "upstreams", "gateway")}


def load_initial_policy(settings: Settings, policy_module: Any, store: PolicyStore) -> Any:
    """Active DB version, else ``settings.policy_path`` (persisted as the first version), else deny-all."""
    engine_cls = policy_module.PolicyEngine
    active = store.active()
    if active:
        try:
            return engine_cls.from_yaml(active["yaml_text"])
        except Exception:
            log.exception("active policy %s failed to load; falling back to %s", active["version"][:12],
                          settings.policy_path)
    path = Path(settings.policy_path)
    if path.is_file():
        text = path.read_text(encoding="utf-8")
        source = f"initial policy from {path.name}"
    else:
        log.warning("no policy in the database and %s does not exist; using a deny-all policy", path)
        text, source = DENY_ALL_POLICY, "built-in deny-all fallback"
    engine = engine_cls.from_yaml(text)
    store.save(engine.version, text, created_by="system", comment=source)
    store.activate(engine.version)
    return engine


def _demo_workspace_available() -> bool:
    try:
        return importlib.util.find_spec(DEMO_WORKSPACE_TARGET.split(":", 1)[0]) is not None
    except (ImportError, ValueError):
        return False


def load_upstreams(settings: Settings) -> Any:
    """Upstreams from ``settings.upstreams_path``. Without that file: in demo mode the in-process demo
    workspace (shared with ``/api/demo/*``, spec section 14), otherwise no upstream tools."""
    from mirsad.adapters.upstreams import UpstreamManager

    path = Path(settings.upstreams_path)
    if path.is_file():
        return UpstreamManager.from_file(path)
    if settings.enable_demo and _demo_workspace_available():
        log.info("upstreams file %s not found; demo mode: serving the in-process demo workspace (%s)", path,
                 DEMO_WORKSPACE_TARGET)
        return UpstreamManager.from_dict(DEMO_UPSTREAMS)
    log.info("upstreams file %s not found; starting with no upstream tools", path)
    return UpstreamManager()


def build_engine(policy_module: Any, yaml_text: str, previous: Any = None) -> Any:
    """New engine from YAML that keeps the previous engine's rate-limit counters across a hot reload."""
    limiter = getattr(previous, "rate_limiter", None)
    if limiter is not None:
        try:
            return policy_module.PolicyEngine.from_yaml(yaml_text, rate_limiter=limiter)
        except TypeError:  # engine without rate_limiter support
            pass
    return policy_module.PolicyEngine.from_yaml(yaml_text)


def policy_agent_names(policy: Any) -> dict[str, str]:
    if callable(getattr(policy, "agent_names", None)):
        return dict(policy.agent_names())
    names: dict[str, str] = {}
    for agent in getattr(getattr(policy, "document", None), "agents", None) or []:
        agent_id = getattr(agent, "id", None) or (agent.get("id") if isinstance(agent, dict) else None)
        name = getattr(agent, "name", None) or (agent.get("name") if isinstance(agent, dict) else None)
        if agent_id:
            names[agent_id] = name or agent_id
    return names


def build_components(settings: Settings, overrides: dict[str, Any] | None = None) -> Components:
    o = dict(overrides or {})
    unknown = set(o) - OVERRIDE_KEYS
    if unknown:
        raise ValueError(f"unknown override keys: {sorted(unknown)}")
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    secret = settings.resolved_secret_key()

    auth = o.get("auth") or importlib.import_module("mirsad.auth")
    if "db" in o:
        db = o["db"]
    else:
        from mirsad.storage import Database

        db = Database(settings.resolved_database_url())
        db.create_all()
    tables = Tables(db)

    if "audit" in o:
        audit = o["audit"]
    else:
        from mirsad.audit import AuditLog, audit_key_from_secret

        audit = AuditLog(db, audit_key_from_secret(secret), payload_max_chars=settings.audit_payload_max_chars)

    if "notifier" in o:
        notifier = o["notifier"]
    else:
        from mirsad.approvals import Notifier

        notifier = Notifier.from_settings(settings)

    if "approvals" in o:
        approvals = o["approvals"]
    else:
        from mirsad.approvals import ApprovalService

        approvals = ApprovalService(db, notifier, timeout_s=settings.approval_timeout_s)

    policy_module = o.get("policy_module") or importlib.import_module("mirsad.policy")
    policy_store = o.get("policy_store") or PolicyStore(tables)
    if "policy" in o:
        policy = o["policy"]
        yaml_text = getattr(policy, "yaml_text", None)
        if yaml_text and isinstance(policy_store, PolicyStore) and policy_store.active_version() != policy.version:
            policy_store.save(policy.version, yaml_text, created_by="system", comment="provided at startup")
            policy_store.activate(policy.version)
    else:
        policy = load_initial_policy(settings, policy_module, policy_store)

    gateway_ref: list = []
    if "taint" in o:
        taint = o["taint"]
    else:
        from mirsad.taint import TaintTracker

        # Follow policy hot-swaps: internal domains always come from the gateway's active policy.
        def internal_domains() -> list[str]:
            current = gateway_ref[0].policy if gateway_ref else policy
            try:
                return list(current.internal_domains())
            except Exception:
                return []

        taint = TaintTracker(internal_domains=internal_domains)

    if "detector" in o:
        detector = o["detector"]
    else:
        from mirsad.detector import InjectionDetector

        model_dir = Path(settings.detector_model_dir)
        if model_dir.resolve() != (PACKAGE_DIR / "detector" / "model").resolve() and model_dir.is_dir():
            detector = InjectionDetector(model_dir)
        else:
            detector = InjectionDetector.default()

    if "upstreams" in o:
        upstreams = o["upstreams"]
    else:
        try:
            upstreams = load_upstreams(settings)
        except ImportError:
            log.warning("mirsad.adapters.upstreams unavailable; tool invocation disabled")
            upstreams = None

    if "gateway" in o:
        gateway = o["gateway"]
    else:
        import os

        from mirsad.security.intent import OllamaIntentJudge
        from mirsad.security.monitor import SecurityMonitor
        judge = OllamaIntentJudge(model=os.getenv('MIRSAD_JUDGE_MODEL', 'qwen2.5:3b')) if os.getenv('MIRSAD_INTENT_JUDGE_ENABLED') == '1' else None
        gateway = Gateway(
            policy=policy, taint=taint, detector=detector, audit=audit, approvals=approvals,
            security_monitor=SecurityMonitor(intent_judge=judge),
            agent_names=policy_agent_names(policy), policy_store=getattr(policy_store, "get_yaml", None),
            max_result_chars=settings.max_result_chars, sanitizer=o.get("sanitizer"),
            spotlighter=o.get("spotlighter"))

    gateway_ref.append(gateway)
    comps = Components(settings=settings, db=db, tables=tables, audit=audit, notifier=notifier, approvals=approvals,
                       policy_store=policy_store, policy=policy, taint=taint, detector=detector,
                       upstreams=upstreams, gateway=gateway, auth=auth, policy_module=policy_module, secret=secret)
    try:
        for agent in auth.list_agents(db):
            gateway.agent_names.setdefault(agent.policy_agent_id, agent.name)
    except Exception:
        log.debug("could not preload agent names", exc_info=True)
    return comps


def bootstrap_admin(comps: Components) -> bool:
    """Create the first admin from ``MIRSAD_ADMIN_PASSWORD`` when no user exists yet."""
    password = os.environ.get("MIRSAD_ADMIN_PASSWORD")
    if not password or comps.auth.list_users(comps.db):
        return False
    username = os.environ.get("MIRSAD_ADMIN_USERNAME", "admin")
    comps.auth.create_user(comps.db, username, password, "admin", display_name="Administrator", lang="en")
    comps.audit.append("user.created", payload={"username": username, "role": "admin", "created_by": "bootstrap"})
    log.info("bootstrap admin user '%s' created from MIRSAD_ADMIN_PASSWORD", username)
    return True


def generate_password(nbytes: int = 18) -> str:
    return secrets.token_urlsafe(nbytes)
