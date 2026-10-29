"""Defense configurations for Mirsad-Bench.

``none``           no gateway: tools run directly against the World (baseline).
``full``           real Gateway with the default policy, TaintTracker, InjectionDetector.default(),
                   hash-chained AuditLog on a temporary SQLite file and ApprovalService(auto_decider).
``policy_only``    policy layer only (allow-list, constraints, rate limits, rules, approval policy);
                   taint disabled, detector replaced by :class:`NullDetector`, no spotlighting.
``taint_only``     tool profiles kept (trust / sensitivity / sink / risk) so taint rules can fire, but no
                   constraints, rate limits, global rules or approval policy; null detector.
``detector_only``  real detector (with sanitise + spotlight from the policy), taint disabled, no
                   constraints, rate limits, global rules or approval policy.

Ablations are produced by transforming the default policy YAML, so every configuration runs the
same production code paths. Each episode gets a fresh PolicyEngine (fresh rate limiter) and a fresh
TaintTracker; the audit database and approval service are shared per runtime.

Approver modes (the ``auto_decider`` of the ApprovalService): ``deny`` rejects every escalation,
``approve`` accepts every escalation, ``oracle`` accepts exactly the calls that match the user
task's plan (same tool and identifying arguments) and rejects everything else, i.e. a human who
knows what the user asked for.
"""

from __future__ import annotations

import copy
import logging
import secrets
import time
from pathlib import Path
from typing import Any

import yaml

from bench.episode import plan_step_matches
from mirsad.config import PROJECT_DIR
from mirsad.models import DetectionResult

logger = logging.getLogger("mirsad.bench")

DEFENSES: tuple[str, ...] = ("none", "full", "policy_only", "taint_only", "detector_only")
APPROVERS: tuple[str, ...] = ("deny", "approve", "oracle")
DEFAULT_POLICY_PATH = PROJECT_DIR / "configs" / "policies" / "default.yaml"
AGENT_ID = "email-crm-assistant"
AGENT_NAME = "Email & CRM Assistant"

_shared_detector: Any = None


class NullDetector:
    """Stand-in detector for ablations without the detector layer: every text scores 0 (benign)."""

    version = "null-detector"
    mode = "disabled"

    def scan(self, text: str) -> DetectionResult:
        return DetectionResult(score=0.0, label="benign", language="other")

    def scan_structured(self, value: Any) -> DetectionResult:
        return DetectionResult(score=0.0, label="benign", language="other")


def shared_detector() -> Any:
    """The real detector, loaded once per process (it is stateless and slow to load)."""
    global _shared_detector
    if _shared_detector is None:
        from mirsad.detector import InjectionDetector

        _shared_detector = InjectionDetector.default()
        logger.info("detector loaded (mode=%s)", getattr(_shared_detector, "mode", "?"))
    return _shared_detector


def detector_mode(defense: str) -> str:
    if defense in ("full", "detector_only"):
        return str(getattr(shared_detector(), "mode", "unknown"))
    return "disabled"


# --------------------------------------------------------------------------- policy ablations


def policy_yaml_for(defense: str, base_yaml: str) -> str:
    """Return the policy YAML used by ``defense`` (raises ValueError for ``none`` / unknown names)."""
    if defense not in DEFENSES or defense == "none":
        raise ValueError(f"no policy for defense {defense!r}")
    if defense == "full":
        return base_yaml
    doc = copy.deepcopy(yaml.safe_load(base_yaml))
    detector = doc.setdefault("detector", {})
    taint = doc.setdefault("taint", {})
    if defense in ("policy_only", "taint_only"):
        detector["spotlight"] = False
    if defense in ("policy_only", "detector_only"):
        taint["enabled"] = False
    if defense in ("taint_only", "detector_only"):
        doc["rules"] = []
        for agent in doc.get("agents", []):
            for tool in (agent.get("tools") or {}).values():
                if not isinstance(tool, dict):
                    continue
                tool.pop("constraints", None)
                tool.pop("rate_limit", None)
                if tool.get("allow"):
                    tool["approval"] = "never"
    if defense in ("policy_only", "taint_only"):
        for agent in doc.get("agents", []):
            if isinstance(agent.get("detector"), dict):
                agent["detector"]["spotlight"] = False
            for tool in (agent.get("tools") or {}).values():
                if isinstance(tool, dict) and isinstance(tool.get("detector"), dict):
                    tool["detector"]["spotlight"] = False
    if defense == "detector_only":
        for agent in doc.get("agents", []):
            if isinstance(agent.get("taint"), dict):
                agent["taint"]["enabled"] = False
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)


# --------------------------------------------------------------------------- approver


class Approver:
    """Automatic stand-in for the human approver (used as ApprovalService.auto_decider)."""

    def __init__(self, mode: str) -> None:
        if mode not in APPROVERS:
            raise ValueError(f"unknown approver mode {mode!r}; expected one of {APPROVERS}")
        self.mode = mode
        self.plan: list[Any] = []
        self.requested = 0
        self.approved = 0
        self.denied = 0

    def begin(self, plan: list[Any]) -> None:
        """Set the user plan the oracle compares escalated calls against."""
        self.plan = list(plan)

    def verdict(self, tool: str, arguments: dict[str, Any]) -> bool:
        if self.mode == "approve":
            return True
        if self.mode == "deny":
            return False
        return plan_step_matches(tool, arguments, self.plan)

    def decide(self, record: Any) -> bool:
        self.requested += 1
        ok = self.verdict(record.tool, dict(record.arguments or {}))
        if ok:
            self.approved += 1
        else:
            self.denied += 1
        return ok


# --------------------------------------------------------------------------- runtime


class DefenseRuntime:
    """Owns the shared pieces of one (defense, approver) configuration and builds per-episode gateways."""

    def __init__(self, defense: str, approver: str, *, workdir: str | Path,
                 policy_path: str | Path = DEFAULT_POLICY_PATH, approval_timeout_s: float = 5.0,
                 detector: Any = None) -> None:
        if defense not in DEFENSES:
            raise ValueError(f"unknown defense {defense!r}; expected one of {DEFENSES}")
        self.defense = defense
        self.approver = Approver(approver)
        self.policy_yaml: str | None = None
        self.db: Any = None
        self.audit: Any = None
        self.approvals: Any = None
        self.detector: Any = None
        self._last_gateway: Any = None
        if defense == "none":
            return

        from mirsad.approvals import ApprovalService, Notifier
        from mirsad.audit import AuditLog
        from mirsad.policy import PolicyEngine
        from mirsad.storage import Database

        base = Path(policy_path).read_text(encoding="utf-8")
        self.policy_yaml = policy_yaml_for(defense, base)
        PolicyEngine.from_yaml(self.policy_yaml)  # fail fast on an invalid ablation
        workdir = Path(workdir)
        workdir.mkdir(parents=True, exist_ok=True)
        db_path = workdir / f"audit-{defense}-{approver}-{int(time.time() * 1000)}.db"
        self.db = Database(f"sqlite:///{db_path}")
        self.db.create_all()
        self.db_path = db_path
        self.audit = AuditLog(self.db, secrets.token_bytes(32))
        self.approvals = ApprovalService(self.db, Notifier(), timeout_s=approval_timeout_s,
                                         auto_decider=self.approver.decide, redact_arguments=False)
        if detector is not None:
            self.detector = detector
        elif defense in ("full", "detector_only"):
            self.detector = shared_detector()
        else:
            self.detector = NullDetector()

    @property
    def protected(self) -> bool:
        return self.defense != "none"

    def gateway(self) -> Any:
        """A fresh Gateway for one episode (new policy engine + rate limiter, new taint tracker)."""
        if not self.protected:
            raise RuntimeError("defense 'none' has no gateway")
        from mirsad.gateway import Gateway
        from mirsad.policy import PolicyEngine
        from mirsad.taint import TaintTracker

        engine = PolicyEngine.from_yaml(self.policy_yaml or "")
        taint = TaintTracker(internal_domains=engine.internal_domains())
        gw = Gateway(policy=engine, taint=taint, detector=self.detector, audit=self.audit,
                     approvals=self.approvals, agent_names={AGENT_ID: AGENT_NAME})
        self._last_gateway = gw
        return gw

    def verify_audit(self) -> dict[str, Any]:
        """Verify the hash chain of this runtime's audit log."""
        if self.audit is None:
            return {"ok": None, "checked": 0}
        report = self.audit.verify()
        return {"ok": bool(report.ok), "checked": int(getattr(report, "checked", 0)),
                "message": str(getattr(report, "message", ""))}

    def replay_check(self, *, max_events: int = 5000) -> dict[str, Any]:
        """Replay stored ``tool_call.decision`` events and count how many reproduce the same action."""
        if self.audit is None:
            return {"checked": 0, "matched": 0}
        gw = self._last_gateway or self.gateway()
        checked = matched = 0
        mismatches: list[int] = []
        offset = 0
        while checked < max_events:
            events, _total = self.audit.query(event_type="tool_call.decision", order="asc", limit=500,
                                              offset=offset)
            if not events:
                break
            offset += len(events)
            for ev in events:
                if checked >= max_events:
                    break
                checked += 1
                try:
                    report = gw.replay(ev.seq)
                except Exception:
                    logger.exception("replay of seq %s failed", ev.seq)
                    mismatches.append(ev.seq)
                    continue
                if report.match:
                    matched += 1
                else:
                    mismatches.append(ev.seq)
        return {"checked": checked, "matched": matched, "mismatched_seqs": mismatches[:20]}

    async def aclose(self) -> None:
        """Release background work and pooled SQLite handles before temp cleanup."""
        if self.approvals is not None and hasattr(self.approvals, "aclose"):
            await self.approvals.aclose()
        if self.db is not None and hasattr(self.db, "dispose"):
            self.db.dispose()
