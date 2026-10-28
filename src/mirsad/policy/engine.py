"""Policy engine: resolves tool profiles and evaluates tool calls against a policy document.

Evaluation order for one call (all objections are collected, then combined by
the gateway with deny-overrides, see ``mirsad.models.combine_reasons``):

1. unknown agent              -> DENY ``UNKNOWN_AGENT`` (stop)
2. tool not allowed           -> DENY ``TOOL_NOT_ALLOWED`` (stop)
3. informational tool risk    -> ALLOW ``TOOL_RISK`` with the tool's risk score
4. argument constraints       -> ``CONSTRAINT_VIOLATION`` (deny / require_approval)
5. rate limit                 -> DENY ``RATE_LIMIT`` (layer ``ratelimit``)
6. global rules               -> ``RULE_MATCH`` with the rule's action
7. ``approval: always``       -> REQUIRE_APPROVAL ``APPROVAL_ALWAYS``
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote

import yaml
from pydantic import BaseModel, Field

from mirsad.models import (
    Action,
    Reason,
    Risk,
    Sensitivity,
    SinkKind,
    ToolCall,
    ToolProfile,
    Trust,
    combine_reasons,
)
from mirsad.policy import globs
from mirsad.policy.constraints import (
    OBJECTION_RISK_SCORE,
    CompiledConstraint,
    as_text,
    check_constraints,
    compile_constraints,
    iter_pieces,
    leaves,
    piece_domains,
)
from mirsad.policy.messages import RISK_AR, fmt_score, render
from mirsad.policy.ratelimit import RateLimiter
from mirsad.policy.regex_guard import bounded_search
from mirsad.policy.schema import (
    AgentPolicy,
    DetectorSettings,
    PolicyDocument,
    PolicyError,
    RateLimit,
    Rule,
    TaintSettings,
    ToolPolicy,
    load_policy,
)
from mirsad.textutil import domain_matches

logger = logging.getLogger("mirsad.policy")

RISK_SCORES: dict[Risk, float] = {Risk.LOW: 0.1, Risk.MEDIUM: 0.3, Risk.HIGH: 0.6, Risk.CRITICAL: 0.9}
APPROVAL_RISK_THRESHOLD = 0.6
DEFAULTS_ENTRY = "defaults.decision"


class PolicyEvaluation(BaseModel):
    """Policy and rate-limit verdict for one call, before taint analysis and approval."""

    reasons: list[Reason] = Field(default_factory=list)
    profile: ToolProfile
    sink: SinkKind
    rate_counts: dict[str, int] = Field(default_factory=dict)

    @property
    def action(self) -> Action:
        return combine_reasons(self.reasons)[0]

    @property
    def risk_score(self) -> float:
        return combine_reasons(self.reasons)[1]


@dataclass(frozen=True)
class _ToolEntry:
    key: str
    policy: ToolPolicy
    constraints: list[CompiledConstraint]
    detector: DetectorSettings

    def profile_for(self, tool: str) -> ToolProfile:
        p = self.policy
        return ToolProfile(
            tool=tool,
            allowed=p.allow,
            trust=p.trust,
            sensitivity=p.sensitivity,
            sink=p.sink,
            sink_params=tuple(p.sink_params),
            risk=p.risk,
            approval=p.approval,
            scan=p.effective_scan,
            matched_rule=self.key,
        )


@dataclass(frozen=True)
class _Agent:
    policy: AgentPolicy
    exact: dict[str, _ToolEntry]
    globs: list[tuple[re.Pattern[str], _ToolEntry]]
    catch_all: _ToolEntry | None
    detector: DetectorSettings
    taint: TaintSettings


@dataclass(frozen=True)
class _CompiledRule:
    rule: Rule
    arg_patterns: tuple[tuple[str, re.Pattern[str]], ...]


def canonical_json(document: PolicyDocument) -> str:
    """Canonical JSON of a parsed policy: sorted keys, no whitespace, UTF-8 text."""
    data = document.model_dump(mode="json", by_alias=True)
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class PolicyEngine:
    """Evaluates tool calls against an immutable :class:`PolicyDocument`.

    The engine is safe to share between threads: everything except the rate
    limiter is read-only after construction, and the limiter has its own lock.
    """

    def __init__(
        self,
        document: PolicyDocument,
        *,
        rate_limiter: RateLimiter | None = None,
        yaml_text: str | None = None,
    ) -> None:
        self.document = document
        self.rate_limiter = rate_limiter if rate_limiter is not None else RateLimiter()
        self.version = hashlib.sha256(canonical_json(document).encode("utf-8")).hexdigest()
        self.yaml_text = yaml_text if yaml_text is not None else yaml.safe_dump(
            document.model_dump(mode="json", by_alias=True), sort_keys=False, allow_unicode=True
        )
        self._agents: dict[str, _Agent] = {}
        for agent in document.agents:
            self._agents.setdefault(agent.id, self._compile_agent(agent))
        self._rules = [
            _CompiledRule(rule, tuple((arg, re.compile(rx)) for arg, rx in rule.when.arg_matches.items()))
            for rule in document.rules
        ]
        logger.info("policy engine ready: version=%s mode=%s agents=%d rules=%d",
                    self.version[:12], self.mode, len(self._agents), len(self._rules))

    # ------------------------------------------------------------------ construction

    @classmethod
    def from_yaml(cls, text: str, *, rate_limiter: RateLimiter | None = None) -> PolicyEngine:
        return cls(load_policy(text), rate_limiter=rate_limiter, yaml_text=text)

    @classmethod
    def from_file(cls, path: str | Path, *, rate_limiter: RateLimiter | None = None) -> PolicyEngine:
        try:
            text = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise PolicyError(f"cannot read policy file {path}: {exc}") from exc
        return cls.from_yaml(text, rate_limiter=rate_limiter)

    def _compile_agent(self, agent: AgentPolicy) -> _Agent:
        doc = self.document
        detector = agent.detector.apply(doc.detector) if agent.detector else doc.detector
        taint = agent.taint.apply(doc.taint) if agent.taint else doc.taint
        entries = {
            key: _ToolEntry(
                key=key,
                policy=tool,
                constraints=compile_constraints(tool.constraints),
                detector=tool.detector.apply(detector) if tool.detector else detector,
            )
            for key, tool in agent.tools.items()
        }
        exact = {k: e for k, e in entries.items() if not globs.is_glob(k)}
        patterns = sorted(
            (k for k in entries if globs.is_glob(k) and k != globs.CATCH_ALL),
            key=lambda k: (-globs.specificity(k), k),
        )
        return _Agent(
            policy=agent,
            exact=exact,
            globs=[(globs.compile_glob(k), entries[k]) for k in patterns],
            catch_all=entries.get(globs.CATCH_ALL),
            detector=detector,
            taint=taint,
        )

    # ------------------------------------------------------------------ simple accessors

    @property
    def mode(self) -> Literal["enforce", "monitor"]:
        """``monitor``: the gateway audits would-be decisions but always allows (shadow deployment)."""
        return self.document.mode

    @property
    def approval_timeout_s(self) -> float:
        return self.document.defaults.approval_timeout_s

    def agent_ids(self) -> list[str]:
        return list(self._agents)

    def agent_names(self) -> dict[str, str]:
        return {a.policy.id: a.policy.name or a.policy.id for a in self._agents.values()}

    def internal_domains(self) -> list[str]:
        return list(self.document.organization.internal_domains)

    def taint_settings(self, agent_id: str) -> TaintSettings:
        agent = self._agents.get(agent_id)
        return agent.taint if agent else self.document.taint

    def detector_settings(self, agent_id: str, tool: str) -> DetectorSettings:
        """Global settings, overridden by the agent's ``detector:`` and then by the matched tool entry's."""
        agent = self._agents.get(agent_id)
        if agent is None:
            return self.document.detector
        entry = self._resolve(agent, tool)
        return entry.detector if entry else agent.detector

    # ------------------------------------------------------------------ tool resolution

    def _resolve(self, agent: _Agent, tool: str) -> _ToolEntry | None:
        entry = agent.exact.get(tool)
        if entry is not None:
            return entry
        for rx, candidate in agent.globs:
            if rx.match(tool):
                return candidate
        return agent.catch_all

    def tool_profile(self, agent_id: str, tool: str) -> ToolProfile:
        agent = self._agents.get(agent_id)
        if agent is None:
            return ToolProfile(tool=tool, allowed=False)
        entry = self._resolve(agent, tool)
        if entry is None:
            return self._default_profile(tool)
        return entry.profile_for(tool)

    def _default_profile(self, tool: str) -> ToolProfile:
        decision = self.document.defaults.decision
        if decision == Action.DENY:
            return ToolProfile(tool=tool, allowed=False, matched_rule=DEFAULTS_ENTRY)
        # A tool nobody described: assume the worst about its results and destination.
        return ToolProfile(
            tool=tool,
            allowed=True,
            trust=Trust.UNTRUSTED,
            sensitivity=Sensitivity.INTERNAL,
            sink="external",
            risk=Risk.MEDIUM,
            approval="always" if decision == Action.REQUIRE_APPROVAL else "on_risk",
            scan=True,
            matched_rule=DEFAULTS_ENTRY,
        )

    def visible_tools(self, agent_id: str, tools: list[str]) -> list[str]:
        """The subset of ``tools`` the agent may call (order preserved)."""
        return [t for t in tools if self.tool_profile(agent_id, t).allowed]

    # ------------------------------------------------------------------ sinks

    def resolve_sink(self, call: ToolCall, profile: ToolProfile) -> SinkKind:
        """Static sinks as declared; ``dynamic`` by the domains of the destination arguments.

        A non-empty destination value with no recognisable e-mail/URL/host domain is
        treated as EXTERNAL: an unknown destination must not count as internal.
        """
        if profile.sink != "dynamic":
            return SinkKind(profile.sink)
        pieces = [piece for param in profile.sink_params for piece in iter_pieces(call.arguments.get(param))]
        if not pieces:
            return SinkKind.NONE
        internal = self.internal_domains()
        for piece in pieces:
            domains = piece_domains(piece)
            if not domains or any(not domain_matches(d, internal) for d in domains):
                return SinkKind.EXTERNAL
        return SinkKind.INTERNAL

    # ------------------------------------------------------------------ evaluation

    def evaluate_call(
        self,
        call: ToolCall,
        *,
        now: float | None = None,
        rate_counts: dict[str, int] | None = None,
        session_tainted: bool = False,
    ) -> PolicyEvaluation:
        """Evaluate one call. With ``rate_counts`` (replay mode) the limiter is neither read nor updated."""
        agent = self._agents.get(call.agent_id)
        profile = self.tool_profile(call.agent_id, call.tool)
        sink = self.resolve_sink(call, profile)

        if agent is None:
            reason = self._reason("UNKNOWN_AGENT", Action.DENY, OBJECTION_RISK_SCORE,
                                  {"agent_id": call.agent_id}, agent=call.agent_id)
            return PolicyEvaluation(reasons=[reason], profile=profile, sink=sink)

        if not profile.allowed:
            entry_name = profile.matched_rule or DEFAULTS_ENTRY
            reason = self._reason(
                "TOOL_NOT_ALLOWED", Action.DENY, OBJECTION_RISK_SCORE,
                {"tool": call.tool, "agent_id": call.agent_id, "matched_entry": entry_name},
                rule_id=entry_name, tool=call.tool, agent=call.agent_id, entry=entry_name,
            )
            return PolicyEvaluation(reasons=[reason], profile=profile, sink=sink)

        risk_score = RISK_SCORES[profile.risk]
        reasons = [self._reason(
            "TOOL_RISK", Action.ALLOW, risk_score,
            {"tool": call.tool, "risk": profile.risk.value, "risk_score": risk_score},
            tool=call.tool, risk=profile.risk.value, risk_ar=RISK_AR[profile.risk], score=fmt_score(risk_score),
        )]

        entry = self._resolve(agent, call.tool)
        counts: dict[str, int] = {}
        if entry is not None:
            reasons.extend(check_constraints(call.arguments, entry.constraints))
            if entry.policy.rate_limit is not None:
                reasons.extend(self._rate_limit(call, entry.policy.rate_limit, now, rate_counts, counts))

        reasons.extend(self._rule_reasons(call, profile, sink, session_tainted))

        if profile.approval == "always":
            reasons.append(self._reason("APPROVAL_ALWAYS", Action.REQUIRE_APPROVAL, risk_score,
                                        {"tool": call.tool}, tool=call.tool))

        evaluation = PolicyEvaluation(reasons=reasons, profile=profile, sink=sink, rate_counts=counts)
        logger.debug("policy %s/%s -> %s (%d reasons, sink=%s)", call.agent_id, call.tool,
                     evaluation.action.value, len(reasons), sink.value)
        return evaluation

    def approval_required(self, profile: ToolProfile, risk_score: float, taint_fired: bool) -> bool:
        """Approval semantics of spec 2.1 for a call whose combined action is otherwise ALLOW."""
        if profile.approval == "never":
            return False
        if profile.approval == "always":
            return True
        return risk_score >= APPROVAL_RISK_THRESHOLD or (profile.risk.rank >= Risk.HIGH.rank and taint_fired)

    # ------------------------------------------------------------------ rate limit

    @staticmethod
    def rate_key(call: ToolCall, limit: RateLimit) -> str:
        """Counter key; components are URL-quoted so different agent/session/tool triples never collide."""
        parts = [f"agent={quote(call.agent_id, safe='')}"]
        if limit.scope == "session":
            parts.append(f"session={quote(call.session_id, safe='')}")
        parts.append(f"tool={quote(call.tool, safe='')}")
        return "rl:" + ";".join(parts)

    def _rate_limit(
        self,
        call: ToolCall,
        limit: RateLimit,
        now: float | None,
        replay_counts: dict[str, int] | None,
        used: dict[str, int],
    ) -> list[Reason]:
        key = self.rate_key(call, limit)
        if replay_counts is not None:
            count = int(replay_counts.get(key, 1))
        else:
            count = self.rate_limiter.hit(key, limit.per_seconds, time.time() if now is None else now)
        used[key] = count
        if count <= limit.max_calls:
            return []
        window = int(limit.per_seconds) if float(limit.per_seconds).is_integer() else limit.per_seconds
        return [self._reason(
            "RATE_LIMIT", Action.DENY, OBJECTION_RISK_SCORE,
            {"key": key, "count": count, "max_calls": limit.max_calls, "per_seconds": limit.per_seconds,
             "scope": limit.scope},
            layer="ratelimit", rule_id=f"rate_limit:{call.tool}",
            tool=call.tool, count=count, window=window, limit=limit.max_calls,
        )]

    # ------------------------------------------------------------------ global rules

    def _rule_reasons(self, call: ToolCall, profile: ToolProfile, sink: SinkKind,
                      session_tainted: bool) -> list[Reason]:
        reasons: list[Reason] = []
        for compiled in self._rules:
            matched = self._rule_matches(compiled, call, profile, sink, session_tainted)
            if matched is None:
                continue
            rule = compiled.rule
            default_score = 0.0 if rule.action == Action.ALLOW else OBJECTION_RISK_SCORE
            desc = f": {rule.description.rstrip('.')}" if rule.description else ""
            message, message_ar = render("RULE_MATCH", rule=rule.id, desc=desc)
            reasons.append(Reason(
                layer="policy",
                code="RULE_MATCH",
                message=rule.message or message,
                message_ar=rule.message_ar or message_ar,
                action=rule.action,
                rule_id=rule.id,
                risk_score=rule.risk_score if rule.risk_score is not None else default_score,
                evidence={"rule": rule.id, "description": rule.description, "matched": matched},
            ))
        return reasons

    def _rule_matches(self, compiled: _CompiledRule, call: ToolCall, profile: ToolProfile,
                      sink: SinkKind, session_tainted: bool) -> dict[str, Any] | None:
        """The conditions that matched, or ``None`` when the rule does not apply."""
        when = compiled.rule.when
        matched: dict[str, Any] = {}
        if when.tool is not None:
            if not any(globs.glob_matches(p, call.tool) for p in when.tool):
                return None
            matched["tool"] = call.tool
        if when.agent is not None:
            if not any(globs.glob_matches(p, call.agent_id) for p in when.agent):
                return None
            matched["agent"] = call.agent_id
        if when.sink is not None:
            if sink.value not in when.sink:
                return None
            matched["sink"] = sink.value
        if when.session_tainted is not None:
            if when.session_tainted != session_tainted:
                return None
            matched["session_tainted"] = session_tainted
        if when.min_risk is not None:
            if profile.risk.rank < when.min_risk.rank:
                return None
            matched["risk"] = profile.risk.value
        for arg, rx in compiled.arg_patterns:
            value = call.arguments.get(arg)
            if value is None or not _value_matches(rx, value):
                return None
            matched.setdefault("arg_matches", {})[arg] = rx.pattern
        return matched

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _reason(code: str, action: Action, risk_score: float, evidence: dict[str, Any], *,
                layer: Literal["policy", "ratelimit"] = "policy", rule_id: str | None = None,
                **template_values: Any) -> Reason:
        message, message_ar = render(code, **template_values)
        return Reason(layer=layer, code=code, message=message, message_ar=message_ar, action=action,
                      rule_id=rule_id, risk_score=risk_score, evidence=evidence)


def _value_matches(rx: re.Pattern[str], value: Any) -> bool:
    """Rule ``arg_matches``: any list element (or the value) matches; over-long input counts as a match."""
    for leaf in leaves(value):
        outcome = bounded_search(rx, as_text(leaf))
        if outcome.truncated or outcome.matched_any:
            return True
    return False
