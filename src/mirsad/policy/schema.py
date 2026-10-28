"""Policy document schema (YAML version 1), loader and validator.

The schema is strict: unknown keys, unknown constraint operators, bad enum
values, invalid or ReDoS-prone regexes, duplicate YAML keys, duplicate agent or
rule ids and ambiguous tool globs are all errors. Errors are reported with the
YAML line/column they refer to, e.g.::

    line 14, column 11: agents[0].tools.send_email.constraints.to: unknown constraint operator
    'domian_in' (did you mean 'domain_in'?)
"""

from __future__ import annotations

import difflib
import json
import logging
import math
import re
import types
from typing import Annotated, Any, Literal, Union, get_args, get_origin

import yaml
from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)

from mirsad.models import Action, Risk, Sensitivity, Trust
from mirsad.policy import globs
from mirsad.policy.messages import fmt_value
from mirsad.policy.regex_guard import compile_user_regex

logger = logging.getLogger("mirsad.policy")

MAX_POLICY_CHARS = 1_000_000
MAX_YAML_NODES = 100_000
_DEFER_SEMANTIC = "mirsad_defer_semantic_checks"


class PolicyError(Exception):
    """Raised for invalid policy documents; ``errors`` holds one readable message per problem."""

    def __init__(self, errors: list[str] | str) -> None:
        self.errors: list[str] = [errors] if isinstance(errors, str) else list(errors)
        detail = "\n".join(f"  - {e}" for e in self.errors)
        super().__init__(f"invalid policy ({len(self.errors)} error(s)):\n{detail}")


# --------------------------------------------------------------------------- field types


def _check_regex(value: str) -> str:
    compile_user_regex(value)
    return value


def _normalize_domain(value: str) -> str:
    domain = value.strip().lower().rstrip(".")
    if domain.startswith("*."):
        domain = domain[2:]
    if not domain:
        raise ValueError("domain must not be empty")
    if any(ch in domain for ch in "@/:") or any(ch.isspace() for ch in domain):
        raise ValueError(
            f"{value!r} is not a bare domain; write it like 'najd-trading.example' (no '@', scheme, path or port)"
        )
    if domain.startswith(".") or ".." in domain:
        raise ValueError(f"{value!r} is not a valid domain")
    return domain


def _scalar_to_list(value: Any) -> Any:
    return [value] if isinstance(value, str) else value


def _no_bool(value: Any) -> Any:
    if isinstance(value, bool):
        raise ValueError("expected a number, got a boolean")
    return value


def _scalars_only(values: list[Any]) -> list[Any]:
    for item in values:
        if not isinstance(item, (str, int, float, bool)):
            raise ValueError(f"list values must be strings, numbers or booleans, got {_type_name(item)}")
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError("list values must be finite numbers")
    return values


def _tool_key(value: str) -> str:
    if not value or value != value.strip() or any(ch.isspace() for ch in value):
        raise ValueError(f"tool key {value!r} must be a non-empty name or glob without spaces")
    return value


RegexStr = Annotated[str, AfterValidator(_check_regex)]
DomainStr = Annotated[str, AfterValidator(_normalize_domain)]
NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Identifier = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:\-]{0,127}$")]
ToolKey = Annotated[str, AfterValidator(_tool_key)]
Number = Annotated[float, BeforeValidator(_no_bool)]
Count = Annotated[int, BeforeValidator(_no_bool), Field(ge=0)]
Scalar = str | int | float | bool
ScalarList = Annotated[list[Any], AfterValidator(_scalars_only)]
JsonType = Literal["string", "number", "integer", "boolean", "array", "object"]
SinkLiteral = Literal["none", "internal", "external", "dynamic"]
StaticSink = Literal["none", "internal", "external"]
StrList = Annotated[list[NonEmptyStr], BeforeValidator(_scalar_to_list)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


# --------------------------------------------------------------------------- settings sections


class DetectorSettings(_Strict):
    """Injection-detector thresholds and actions (global, overridable per agent and per tool)."""

    flag_threshold: float = Field(0.5, ge=0.0, le=1.0)
    block_threshold: float = Field(0.8, ge=0.0, le=1.0)
    on_detect: Literal["sanitize", "block", "flag"] = "sanitize"
    spotlight: bool = True


class DetectorOverride(_Strict):
    """Partial :class:`DetectorSettings`; only the keys that are set replace the inherited values."""

    flag_threshold: float | None = Field(None, ge=0.0, le=1.0)
    block_threshold: float | None = Field(None, ge=0.0, le=1.0)
    on_detect: Literal["sanitize", "block", "flag"] | None = None
    spotlight: bool | None = None

    def apply(self, base: DetectorSettings) -> DetectorSettings:
        return base.model_copy(update=self.model_dump(exclude_none=True))


def _default_destination_params() -> list[str]:
    return ["to", "cc", "bcc", "recipient", "url", "to_iban", "webhook"]


def _default_trusted_fields() -> list[str]:
    return ["from", "sender", "id", "email_id", "date", "received_at", "customer_id", "doc_id"]


class TaintSettings(_Strict):
    """Taint-tracking switches and the action each taint rule produces."""

    enabled: bool = True
    destination_params: list[NonEmptyStr] = Field(default_factory=_default_destination_params)
    trusted_fields: list[NonEmptyStr] = Field(default_factory=_default_trusted_fields)
    untrusted_to_external_sink: Action = Action.REQUIRE_APPROVAL
    confidential_to_external_sink: Action = Action.REQUIRE_APPROVAL
    untrusted_controls_destination: Action = Action.DENY
    after_injection_high_risk: Action = Action.REQUIRE_APPROVAL


class TaintOverride(_Strict):
    """Partial :class:`TaintSettings` for one agent (Mirsad extension to the spec schema)."""

    enabled: bool | None = None
    destination_params: list[NonEmptyStr] | None = None
    trusted_fields: list[NonEmptyStr] | None = None
    untrusted_to_external_sink: Action | None = None
    confidential_to_external_sink: Action | None = None
    untrusted_controls_destination: Action | None = None
    after_injection_high_risk: Action | None = None

    def apply(self, base: TaintSettings) -> TaintSettings:
        return base.model_copy(update=self.model_dump(exclude_none=True))


class Organization(_Strict):
    name: str = ""
    internal_domains: list[DomainStr] = Field(default_factory=list)


class Defaults(_Strict):
    decision: Action = Action.DENY
    approval_timeout_s: float = Field(120.0, gt=0, le=86_400)


# --------------------------------------------------------------------------- tools & constraints

CONSTRAINT_OPERATORS = (
    "required", "type", "min", "max", "min_length", "max_length", "max_items",
    "enum", "in", "not_in", "pattern", "not_pattern", "domain_in", "domain_not_in",
)


class Constraint(_Strict):
    """Per-argument constraint. All operators that are set must hold (logical AND)."""

    max: Number | None = None
    min: Number | None = None
    max_length: Count | None = None
    min_length: Count | None = None
    enum: ScalarList | None = None
    in_: ScalarList | None = Field(None, alias="in")
    not_in: ScalarList | None = None
    pattern: RegexStr | None = None
    not_pattern: RegexStr | None = None
    domain_in: list[DomainStr] | None = None
    domain_not_in: list[DomainStr] | None = None
    max_items: Count | None = None
    required: bool = False
    type: JsonType | None = None
    on_violation: Literal["deny", "require_approval"] = "deny"

    @property
    def allowed_values(self) -> list[Scalar] | None:
        """``enum`` and ``in`` are synonyms."""
        return self.enum if self.enum is not None else self.in_

    @model_validator(mode="after")
    def _check(self) -> Constraint:
        has_operator = self.required or any(
            getattr(self, name) is not None
            for name in ("max", "min", "max_length", "min_length", "enum", "in_", "not_in", "pattern",
                         "not_pattern", "domain_in", "domain_not_in", "max_items", "type")
        )
        if not has_operator:
            raise ValueError("constraint has no operators; use at least one of: " + ", ".join(CONSTRAINT_OPERATORS))
        if self.enum is not None and self.in_ is not None:
            raise ValueError("'enum' and 'in' are synonyms; use only one of them")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError(f"min ({fmt_value(self.min)}) is greater than max ({fmt_value(self.max)})")
        if self.min_length is not None and self.max_length is not None and self.min_length > self.max_length:
            raise ValueError(f"min_length ({self.min_length}) is greater than max_length ({self.max_length})")
        for name, label in (("enum", "enum"), ("in_", "in"), ("not_in", "not_in"),
                            ("domain_in", "domain_in"), ("domain_not_in", "domain_not_in")):
            value = getattr(self, name)
            if value is not None and not value:
                raise ValueError(f"'{label}' must not be an empty list")
        return self


class RateLimit(_Strict):
    max_calls: Annotated[int, BeforeValidator(_no_bool), Field(ge=1, le=1_000_000)]
    per_seconds: Annotated[float, BeforeValidator(_no_bool), Field(gt=0, le=31 * 86_400)]
    scope: Literal["agent", "session"] = "agent"


class ToolPolicy(_Strict):
    """Security profile of one tool (or glob of tools) for one agent."""

    allow: bool = False
    description: str = ""
    trust: Trust = Trust.TRUSTED
    sensitivity: Sensitivity = Sensitivity.INTERNAL
    sink: SinkLiteral = "none"
    sink_params: list[NonEmptyStr] = Field(default_factory=list)
    risk: Risk = Risk.LOW
    approval: Literal["never", "on_risk", "always"] = "on_risk"
    scan: bool | None = None
    constraints: dict[NonEmptyStr, Constraint] = Field(default_factory=dict)
    rate_limit: RateLimit | None = None
    detector: DetectorOverride | None = None

    @property
    def effective_scan(self) -> bool:
        """``scan`` defaults to true for tools whose results are untrusted."""
        return self.scan if self.scan is not None else self.trust == Trust.UNTRUSTED

    @model_validator(mode="after")
    def _check_sink(self) -> ToolPolicy:
        if self.sink == "dynamic" and not self.sink_params:
            raise ValueError("sink: dynamic needs sink_params (the arguments that hold destinations, e.g. [to, cc])")
        if self.sink_params and self.sink != "dynamic":
            raise ValueError(f"sink_params is only used with sink: dynamic (this tool has sink: {self.sink})")
        return self


class AgentPolicy(_Strict):
    id: Identifier
    name: str = ""
    description: str = ""
    tools: dict[ToolKey, ToolPolicy] = Field(default_factory=dict)
    detector: DetectorOverride | None = None
    taint: TaintOverride | None = None


# --------------------------------------------------------------------------- global rules


class RuleWhen(_Strict):
    """Conditions of a global rule; every condition that is set must hold."""

    tool: StrList | None = None
    agent: StrList | None = None
    arg_matches: dict[NonEmptyStr, RegexStr] = Field(default_factory=dict)
    sink: Annotated[list[StaticSink], BeforeValidator(_scalar_to_list)] | None = None
    session_tainted: bool | None = None
    min_risk: Risk | None = None


class Rule(_Strict):
    id: Identifier
    description: str = ""
    when: RuleWhen
    action: Action
    message: str | None = None
    message_ar: str | None = None
    risk_score: float | None = Field(None, ge=0.0, le=1.0)


# --------------------------------------------------------------------------- document


class PolicyDocument(_Strict):
    """A parsed and validated policy (YAML schema version 1)."""

    version: Literal[1]
    mode: Literal["enforce", "monitor"] = "enforce"
    organization: Organization = Field(default_factory=Organization)
    defaults: Defaults = Field(default_factory=Defaults)
    detector: DetectorSettings = Field(default_factory=DetectorSettings)
    taint: TaintSettings = Field(default_factory=TaintSettings)
    agents: list[AgentPolicy]
    rules: list[Rule] = Field(default_factory=list)

    @field_validator("agents", mode="before")
    @classmethod
    def _agents_list(cls, value: Any) -> Any:
        return [] if value is None else value

    @model_validator(mode="after")
    def _semantic(self, info: ValidationInfo) -> PolicyDocument:
        if info.context and info.context.get(_DEFER_SEMANTIC):
            return self  # load_policy runs these checks itself to attach line numbers
        issues = semantic_issues(self)
        if issues:
            raise ValueError("; ".join(f"{format_path(loc)}: {msg}" for loc, msg in issues))
        return self


Loc = tuple[str | int, ...]


def semantic_issues(doc: PolicyDocument) -> list[tuple[Loc, str]]:
    """Cross-field checks that pydantic field validation cannot express."""
    issues: list[tuple[Loc, str]] = []
    if doc.detector.flag_threshold > doc.detector.block_threshold:
        issues.append((("detector",), _threshold_msg(doc.detector)))

    seen_agents: dict[str, int] = {}
    for i, agent in enumerate(doc.agents):
        if agent.id in seen_agents:
            issues.append((("agents", i, "id"),
                           f"duplicate agent id '{agent.id}' (already defined at agents[{seen_agents[agent.id]}])"))
        else:
            seen_agents[agent.id] = i

        agent_detector = agent.detector.apply(doc.detector) if agent.detector else doc.detector
        if agent.detector and agent_detector.flag_threshold > agent_detector.block_threshold:
            issues.append((("agents", i, "detector"), _threshold_msg(agent_detector)))
        for key, tool in agent.tools.items():
            if tool.detector:
                merged = tool.detector.apply(agent_detector)
                if merged.flag_threshold > merged.block_threshold:
                    issues.append((("agents", i, "tools", key, "detector"), _threshold_msg(merged)))

        patterns = [k for k in agent.tools if globs.is_glob(k) and k != globs.CATCH_ALL]
        for a_idx, a in enumerate(patterns):
            for b in patterns[a_idx + 1 :]:
                if globs.specificity(a) == globs.specificity(b) and globs.globs_overlap(a, b):
                    issues.append((
                        ("agents", i, "tools", b),
                        f"glob '{b}' conflicts with glob '{a}': both have the same length and can match the "
                        "same tool name, so precedence is ambiguous; add an exact entry or make one glob longer",
                    ))

    seen_rules: dict[str, int] = {}
    for j, rule in enumerate(doc.rules):
        if rule.id in seen_rules:
            issues.append((("rules", j, "id"),
                           f"duplicate rule id '{rule.id}' (already defined at rules[{seen_rules[rule.id]}])"))
        else:
            seen_rules[rule.id] = j
        for agent_ref in rule.when.agent or []:
            if not globs.is_glob(agent_ref) and agent_ref not in seen_agents:
                known = ", ".join(sorted(seen_agents)) or "none"
                issues.append((("rules", j, "when", "agent"),
                               f"rule refers to unknown agent '{agent_ref}' (known agents: {known})"))
    return issues


def _threshold_msg(settings: DetectorSettings) -> str:
    return (f"flag_threshold ({settings.flag_threshold}) must not be greater than "
            f"block_threshold ({settings.block_threshold})")


# --------------------------------------------------------------------------- YAML loading


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader that records duplicate mapping keys instead of silently keeping the last one."""

    def __init__(self, stream: str) -> None:
        super().__init__(stream)
        self.duplicate_keys: list[tuple[yaml.Mark, str]] = []

    def construct_mapping(self, node: yaml.Node, deep: bool = False) -> dict[Any, Any]:
        if isinstance(node, yaml.MappingNode):
            seen: dict[str, yaml.Mark] = {}
            for key_node, _ in node.value:
                if key_node.tag == "tag:yaml.org,2002:merge" or not isinstance(key_node, yaml.ScalarNode):
                    continue
                first = seen.get(key_node.value)
                if first is not None:
                    self.duplicate_keys.append((
                        key_node.start_mark,
                        f"duplicate key '{key_node.value}' (first defined at line {first.line + 1}); "
                        "YAML would silently keep only the last value",
                    ))
                else:
                    seen[key_node.value] = key_node.start_mark
        return super().construct_mapping(node, deep=deep)


_Issue = tuple[int | None, int | None, str]


def _count_nodes(root: yaml.Node) -> int:
    count = 0
    stack: list[yaml.Node] = [root]
    while stack:
        node = stack.pop()
        count += 1
        if count > MAX_YAML_NODES:
            break
        if isinstance(node, yaml.MappingNode):
            for key, value in node.value:
                stack.append(key)
                stack.append(value)
        elif isinstance(node, yaml.SequenceNode):
            stack.extend(node.value)
    return count


def _parse(text: str) -> tuple[PolicyDocument | None, list[str]]:
    if not isinstance(text, str):
        return None, [f"policy must be YAML text, got {type(text).__name__}"]
    if len(text) > MAX_POLICY_CHARS:
        return None, [f"policy is larger than {MAX_POLICY_CHARS} characters"]

    loader = _StrictLoader(text)
    try:
        root = loader.get_single_node()
        if root is None:
            return None, ["policy is empty"]
        if _count_nodes(root) > MAX_YAML_NODES:
            return None, [f"policy expands to more than {MAX_YAML_NODES} YAML nodes (excessive or recursive aliases)"]
        data = loader.construct_document(root)
    except yaml.MarkedYAMLError as exc:
        return None, [_format_issue(_yaml_error_issue(exc))]
    except yaml.YAMLError as exc:
        return None, [f"YAML syntax error: {exc}"]
    except RecursionError:
        return None, ["policy is nested too deeply"]
    finally:
        loader.dispose()

    issues: list[_Issue] = [(m.line + 1, m.column + 1, msg) for m, msg in loader.duplicate_keys]
    if not isinstance(data, dict):
        issues.append((root.start_mark.line + 1, root.start_mark.column + 1,
                       f"the policy must be a YAML mapping with keys like 'version' and 'agents', "
                       f"got {_type_name(data)}"))
        return None, _finish(issues)

    try:
        doc = PolicyDocument.model_validate(data, context={_DEFER_SEMANTIC: True})
    except ValidationError as exc:
        for err in exc.errors(include_url=False):
            raw_loc = tuple(err["loc"])
            key_error = bool(raw_loc) and raw_loc[-1] == "[key]"
            if key_error:
                # pydantic reports a bad key as e.g. 1 for True; the input holds the key as YAML produced it
                raw_loc = (*raw_loc[:-2], err.get("input"))
            loc = tuple(p for p in raw_loc if p != "[key]")
            line, col = _locate(root, loc, use_key=key_error or err["type"] == "extra_forbidden")
            issues.append((line, col, f"{format_path(loc)}: {_describe(err, loc)}"))
        return None, _finish(issues)

    for loc, msg in semantic_issues(doc):
        line, col = _locate(root, loc, use_key=True)
        issues.append((line, col, f"{format_path(loc)}: {msg}"))
    if issues:
        return None, _finish(issues)
    return doc, []


def _finish(issues: list[_Issue]) -> list[str]:
    ordered = sorted(enumerate(issues), key=lambda item: (item[1][0] is None, item[1][0] or 0, item[0]))
    return [_format_issue(issue) for _, issue in ordered]


def _format_issue(issue: _Issue) -> str:
    line, col, msg = issue
    if line is None:
        return msg
    return f"line {line}, column {col}: {msg}"


def _yaml_error_issue(exc: yaml.MarkedYAMLError) -> _Issue:
    mark = exc.problem_mark or exc.context_mark
    parts = [p for p in (exc.context, exc.problem) if p]
    msg = "YAML syntax error: " + "; ".join(parts) if parts else f"YAML syntax error: {exc}"
    if mark is None:
        return None, None, msg
    return mark.line + 1, mark.column + 1, msg


def _locate(root: yaml.Node, loc: Loc, *, use_key: bool) -> tuple[int, int]:
    """Line/column (1-based) of the deepest YAML node that ``loc`` resolves to."""
    node: yaml.Node = root
    key_node: yaml.Node | None = None
    resolved_all = True
    for part in loc:
        if isinstance(node, yaml.MappingNode):
            match = None
            for k, v in node.value:
                if isinstance(k, yaml.ScalarNode) and _key_matches(k.value, part):
                    match = (k, v)  # last one wins, as in the constructed data
            if match is None:
                resolved_all = False
                break
            key_node, node = match
        elif (isinstance(node, yaml.SequenceNode) and isinstance(part, int) and not isinstance(part, bool)
              and 0 <= part < len(node.value)):
            key_node, node = None, node.value[part]
        else:
            resolved_all = False
            break
    target = key_node if (use_key and resolved_all and key_node is not None) else node
    if not resolved_all and key_node is not None and isinstance(node, (yaml.MappingNode, yaml.SequenceNode)):
        target = key_node  # point at the key that owns the incomplete block
    mark = target.start_mark
    return mark.line + 1, mark.column + 1


_YAML_TRUE = frozenset({"y", "yes", "true", "on"})
_YAML_FALSE = frozenset({"n", "no", "false", "off"})


def _key_matches(scalar: str, part: str | int) -> bool:
    if isinstance(part, bool):  # an unquoted yes/no/on/off key became a boolean
        return scalar.lower() in (_YAML_TRUE if part else _YAML_FALSE)
    return scalar == str(part)


def format_path(loc: Loc) -> str:
    out = ""
    for part in loc:
        if isinstance(part, bool):
            out += f"[{str(part).lower()}]"
        elif isinstance(part, int):
            out += f"[{part}]"
        elif re.fullmatch(r"[A-Za-z_][A-Za-z0-9_\-]*", str(part)):
            out += ("." if out else "") + str(part)
        else:
            out += f"[{json.dumps(str(part), ensure_ascii=False)}]"
    return out or "<root>"


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "a boolean"
    if isinstance(value, (int, float)):
        return "a number"
    if isinstance(value, str):
        return "a string"
    if isinstance(value, list):
        return "a list"
    if isinstance(value, dict):
        return "a mapping"
    return type(value).__name__


def _short(value: Any, limit: int = 60) -> str:
    text = repr(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _suggest(word: str, options: list[str]) -> str:
    close = difflib.get_close_matches(str(word), options, n=1, cutoff=0.6)
    return f" (did you mean '{close[0]}'?)" if close else ""


def _describe(err: Any, loc: Loc) -> str:
    kind = err["type"]
    msg: str = err["msg"]
    value = err.get("input")
    if kind == "extra_forbidden":
        key = str(loc[-1]) if loc else "?"
        parent = _model_at(loc[:-1])
        allowed = _allowed_keys(parent) if parent else []
        what = "unknown constraint operator" if parent is Constraint else "unknown key"
        listing = f"; allowed: {', '.join(allowed)}" if allowed else ""
        return f"{what} '{key}'{_suggest(key, allowed)}{listing}"
    if kind == "missing":
        return f"missing required key '{loc[-1]}'" if loc else "missing value"
    if kind in ("literal_error", "enum"):
        expected = re.findall(r"'([^']*)'", str((err.get("ctx") or {}).get("expected", "")))
        hint = _suggest(str(value), expected) if isinstance(value, str) else ""
        return f"invalid value {_short(value)}: {msg}{hint}"
    if kind == "value_error":
        return msg.removeprefix("Value error, ")
    if kind == "string_pattern_mismatch":  # only identifiers use a pattern
        return (f"{_short(value)} is not a valid id: use 1-128 letters, digits, '_', '-', '.' or ':', "
                "starting with a letter or digit")
    if kind in ("model_type", "dict_type", "model_attributes_type"):
        return f"expected a mapping (for example {{allow: true}}), got {_type_name(value)}"
    if kind == "list_type":
        return f"expected a list (for example [a, b]), got {_type_name(value)}"
    if kind == "string_type" and isinstance(value, bool):
        return (f"{msg}; YAML reads unquoted yes/no/on/off/true/false as booleans, "
                "so put the value in quotes")
    return f"{msg} (got {_short(value)})"


def _unwrap(annotation: Any) -> Any:
    origin = get_origin(annotation)
    if origin is Annotated:
        return _unwrap(get_args(annotation)[0])
    if origin in (Union, types.UnionType):
        for arg in get_args(annotation):
            if arg is not type(None):
                return _unwrap(arg)
    return annotation


def _model_at(loc: Loc) -> type[BaseModel] | None:
    """The pydantic model class that validates the value at ``loc`` (for key suggestions)."""
    current: Any = PolicyDocument
    for part in loc:
        current = _unwrap(current)
        if isinstance(current, type) and issubclass(current, BaseModel):
            field = next((f for name, f in current.model_fields.items() if (f.alias or name) == part), None)
            if field is None:
                return None
            current = field.annotation
            continue
        origin = get_origin(current)
        if origin is list:
            current = get_args(current)[0]
        elif origin is dict:
            current = get_args(current)[1]
        else:
            return None
    current = _unwrap(current)
    return current if isinstance(current, type) and issubclass(current, BaseModel) else None


def _allowed_keys(model: type[BaseModel]) -> list[str]:
    return [f.alias or name for name, f in model.model_fields.items()]


# --------------------------------------------------------------------------- public API


def load_policy(text: str) -> PolicyDocument:
    """Parse and validate policy YAML; raise :class:`PolicyError` listing every problem found."""
    doc, errors = _parse(text)
    if errors or doc is None:
        raise PolicyError(errors or ["invalid policy"])
    logger.debug("policy loaded: %d agent(s), %d rule(s), mode=%s", len(doc.agents), len(doc.rules), doc.mode)
    return doc


def validate_policy(text: str) -> list[str]:
    """Return human-readable errors (with ``line N, column M`` prefixes where known); ``[]`` when valid."""
    _, errors = _parse(text)
    return errors
