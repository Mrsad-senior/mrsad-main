"""Load and validate Mirsad-Bench scenario files.

Validation runs in two passes: the JSON Schema in ``bench/scenarios/schema.json`` checks the
shape of each file, then :func:`semantic_errors` checks what a schema cannot express (tool
arguments against the demo tool schemas, fixture ids that would collide with the seeded
World, read targets that the plan never reads, duplicate ids, unknown fixture sets).

User tasks live in ``bench/scenarios/*.yaml``. Injection tasks and attack templates are
supplied by the human team in ``bench/scenarios/attacks/*.yaml``; this module only loads and
validates them (:mod:`bench.attacks` turns them into attack episodes).
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from demo.world import TOOLS, World
from jsonschema import Draft202012Validator
from pydantic import BaseModel, Field

logger = logging.getLogger("mirsad.bench")

SCENARIOS_DIR = Path(__file__).resolve().parent / "scenarios"
ATTACKS_DIR = SCENARIOS_DIR / "attacks"
SCHEMA_PATH = SCENARIOS_DIR / "schema.json"

Lang = Literal["en", "ar"]
Vector = Literal["email", "web", "document", "crm_note"]

#: Placeholders an attack template may use; any other ``{lowercase_word}`` is a loader error.
TEMPLATE_PLACEHOLDERS = ("goal", "actions_text", "user", "model")
PLACEHOLDER_RE = re.compile(r"\{([a-z_]+)\}")

# Which plan step "reads" a target of each vector (tool, argument holding the target id).
_READ_TOOLS: dict[str, tuple[tuple[str, str | None], ...]] = {
    "email": (("read_email", "email_id"),),
    "web": (("fetch_url", "url"),),
    "document": (("read_document", "doc_id"),),
    "crm_note": (("get_customer", "customer_id"), ("search_customers", None), ("export_customers", None)),
}


class ScenarioError(ValueError):
    """Raised when scenario files are invalid; ``errors`` lists every problem found."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("invalid scenario files:\n  - " + "\n  - ".join(errors))
        self.errors = errors


# --------------------------------------------------------------------------- models


class ToolStep(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)


class ReadTarget(BaseModel):
    vector: Vector
    target: str


class Fixtures(BaseModel):
    emails: list[dict[str, Any]] = Field(default_factory=list)
    customers: list[dict[str, Any]] = Field(default_factory=list)
    web_pages: list[dict[str, Any]] = Field(default_factory=list)
    documents: list[dict[str, Any]] = Field(default_factory=list)

    def merged(self, other: Fixtures) -> Fixtures:
        return Fixtures(
            emails=[*self.emails, *other.emails],
            customers=[*self.customers, *other.customers],
            web_pages=[*self.web_pages, *other.web_pages],
            documents=[*self.documents, *other.documents],
        )

    def is_empty(self) -> bool:
        return not (self.emails or self.customers or self.web_pages or self.documents)


class UserTask(BaseModel):
    """A benign user request with the plan a compliant agent would follow."""

    id: str
    lang: Lang
    variety: Literal["en", "msa", "gulf"]
    category: str
    prompt: str
    fixtures: Fixtures = Field(default_factory=Fixtures)
    plan: list[ToolStep]
    success: dict[str, Any]
    reads: list[ReadTarget] = Field(default_factory=list)
    expect_approval: bool = False
    notes: str = ""
    source_file: str = ""


class InjectionTask(BaseModel):
    """Attacker goal (supplied by the human team): actions plus a success predicate."""

    id: str
    category: str
    goal: str = ""          # language-neutral fallback
    goal_en: str = ""
    goal_ar: str = ""
    actions: list[ToolStep]
    success: dict[str, Any]
    vectors: list[Vector] = Field(default_factory=list)  # empty: every vector
    notes: str = ""
    source_file: str = ""

    def goal_for(self, lang: str) -> tuple[str, bool]:
        """``(goal text, fallback_used)`` for a template whose goal language is ``lang``."""
        primary = self.goal_ar if lang == "ar" else self.goal_en
        if primary:
            return primary, False
        for alt in (self.goal, self.goal_en, self.goal_ar):
            if alt:
                return alt, True
        return "", True


class AttackTemplate(BaseModel):
    """Attack text template (supplied by the human team); never authored in this repository."""

    id: str
    lang: Literal["en", "ar", "mixed"]
    variety: str | None = None
    style: str
    template: str
    goal_lang: Lang | None = None
    vectors: list[Vector] = Field(default_factory=list)  # empty: every vector
    source: str = ""
    notes: str = ""
    source_file: str = ""

    @property
    def text_lang(self) -> Lang:
        """Language of the goal text and of the {user}/{model} names (``mixed`` defaults to English)."""
        if self.goal_lang:
            return self.goal_lang
        return "ar" if self.lang == "ar" else "en"


class Suite(BaseModel):
    user_tasks: list[UserTask] = Field(default_factory=list)
    injection_tasks: list[InjectionTask] = Field(default_factory=list)
    attack_templates: list[AttackTemplate] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)

    @property
    def has_attacks(self) -> bool:
        return bool(self.injection_tasks and self.attack_templates)

    def task(self, task_id: str) -> UserTask:
        for t in self.user_tasks:
            if t.id == task_id:
                return t
        raise KeyError(f"unknown user task {task_id!r}")

    def select(self, *, lang: str = "all", ids: Iterable[str] | None = None,
               categories: Iterable[str] | None = None, limit: int | None = None) -> list[UserTask]:
        """User tasks filtered by language/ids/categories, in file order, at most ``limit``."""
        wanted = set(ids or [])
        cats = set(categories or [])
        out = [t for t in self.user_tasks
               if (lang == "all" or t.lang == lang)
               and (not wanted or t.id in wanted)
               and (not cats or t.category in cats)]
        if wanted:
            missing = wanted - {t.id for t in out}
            if missing:
                raise KeyError(f"unknown user task id(s): {', '.join(sorted(missing))}")
        return out[:limit] if limit else out


# --------------------------------------------------------------------------- schema


@lru_cache(maxsize=1)
def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    schema = load_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


@lru_cache(maxsize=1)
def seed_ids() -> dict[str, frozenset[str]]:
    """Ids present in a freshly seeded World (fixtures must not collide with them)."""
    w = World()
    return {
        "email": frozenset(e["id"] for e in w.emails),
        "customer": frozenset(c["id"] for c in w.customers),
        "web": frozenset(w.web_pages),
        "document": frozenset(w.documents),
    }


def _loc(path: Iterable[Any]) -> str:
    parts = [str(p) for p in path]
    return "/".join(parts) if parts else "<root>"


def schema_errors(data: Any) -> list[str]:
    """JSON Schema violations of one parsed scenario file (empty when valid)."""
    errors = sorted(_validator().iter_errors(data), key=lambda e: list(e.absolute_path))
    return [f"{_loc(e.absolute_path)}: {e.message}" for e in errors]


# --------------------------------------------------------------------------- semantic checks


def tool_arg_errors(step: dict[str, Any] | ToolStep) -> list[str]:
    """Problems with one ``{tool, args}`` step, checked against the demo tool's input schema."""
    if isinstance(step, ToolStep):
        tool, args = step.tool, step.args
    else:
        tool, args = step.get("tool"), step.get("args") or {}
    spec = TOOLS.get(str(tool))
    if spec is None:
        return [f"unknown tool {tool!r}"]
    validator = Draft202012Validator(spec.input_schema)
    return [f"{tool}: {e.message}" for e in validator.iter_errors(args)]


def _fixture_ids(fx: dict[str, Any]) -> dict[str, list[str]]:
    return {
        "email": [e["id"] for e in fx.get("emails", [])],
        "customer": [c["id"] for c in fx.get("customers", [])],
        "web": [p["url"] for p in fx.get("web_pages", [])],
        "document": [d["id"] for d in fx.get("documents", [])],
    }


def _plan_reads(plan: list[dict[str, Any]], vector: str, target: str) -> bool:
    for tool, arg in _READ_TOOLS[vector]:
        for step in plan:
            if step.get("tool") != tool:
                continue
            if arg is None or str((step.get("args") or {}).get(arg, "")) == target:
                return True
    return False


def _predicate_tools(pred: Any) -> list[str]:
    if not isinstance(pred, dict):
        return []
    out: list[str] = []
    for op, val in pred.items():
        if op in ("all", "any"):
            for p in val:
                out.extend(_predicate_tools(p))
        elif op == "not":
            out.extend(_predicate_tools(val))
        elif op == "executed" and isinstance(val, dict):
            out.append(str(val.get("tool")))
    return out


def _predicate_ops(pred: Any) -> list[str]:
    if not isinstance(pred, dict):
        return []
    out: list[str] = []
    for op, val in pred.items():
        out.append(op)
        if op in ("all", "any"):
            for p in val:
                out.extend(_predicate_ops(p))
        elif op == "not":
            out.extend(_predicate_ops(val))
    return out


def template_placeholder_errors(text: str) -> list[str]:
    """Unknown ``{lowercase_word}`` placeholders in an attack template (typo guard)."""
    unknown = sorted({m.group(1) for m in PLACEHOLDER_RE.finditer(text)} - set(TEMPLATE_PLACEHOLDERS))
    return [f"unknown placeholder {{{name}}} (allowed: {', '.join('{' + p + '}' for p in TEMPLATE_PLACEHOLDERS)})"
            for name in unknown]


def semantic_errors(data: dict[str, Any], *, kind: Literal["tasks", "attacks"]) -> list[str]:
    """Checks beyond the JSON Schema for one schema-valid file."""
    errors: list[str] = []
    seeds = seed_ids()
    if kind == "tasks":
        for key in ("injection_tasks", "attack_templates"):
            if data.get(key):
                errors.append(f"{key}: only allowed in bench/scenarios/attacks/*.yaml")
    else:
        for key in ("user_tasks", "fixture_sets"):
            if data.get(key):
                errors.append(f"{key}: not allowed in attack files (put user tasks in bench/scenarios/*.yaml)")

    sets: dict[str, dict[str, Any]] = data.get("fixture_sets") or {}
    for name, fx in sets.items():
        errors.extend(_fixture_errors(fx, f"fixture_sets/{name}", seeds))

    for i, task in enumerate(data.get("user_tasks") or []):
        where = f"user_tasks/{i} ({task.get('id')})"
        if (task["lang"] == "en") != (task["variety"] == "en"):
            errors.append(f"{where}: variety {task['variety']!r} does not match lang {task['lang']!r}")
        merged: dict[str, list[Any]] = {"emails": [], "customers": [], "web_pages": [], "documents": []}
        for name in task.get("use_fixtures") or []:
            if name not in sets:
                errors.append(f"{where}: unknown fixture set {name!r}")
                continue
            for k in merged:
                merged[k].extend(sets[name].get(k, []))
        for k in merged:
            merged[k].extend((task.get("fixtures") or {}).get(k, []))
        errors.extend(_fixture_errors(merged, where, seeds))
        for j, step in enumerate(task["plan"]):
            errors.extend(f"{where}/plan/{j}: {e}" for e in tool_arg_errors(step))
        known = _fixture_ids(merged)
        for read in task.get("reads") or []:
            vector, target = read["vector"], read["target"]
            pool = {"email": "email", "web": "web", "document": "document", "crm_note": "customer"}[vector]
            if target not in seeds[pool] and target not in known[pool]:
                errors.append(f"{where}: read target {vector}:{target} does not exist in the seed World or fixtures")
            elif not _plan_reads(task["plan"], vector, target):
                errors.append(f"{where}: read target {vector}:{target} is never read by the plan")
        for tool in _predicate_tools(task["success"]):
            if tool not in {s["tool"] for s in task["plan"]}:
                errors.append(f"{where}: success predicate expects {tool!r}, which the plan never calls")

    for i, inj in enumerate(data.get("injection_tasks") or []):
        where = f"injection_tasks/{i} ({inj.get('id')})"
        for j, step in enumerate(inj["actions"]):
            errors.extend(f"{where}/actions/{j}: {e}" for e in tool_arg_errors(step))
        if "answer_contains_any" in _predicate_ops(inj["success"]):
            errors.append(f"{where}: success must be judged on World side effects; answer_contains_any is not "
                          "allowed in injection tasks")
        for tool in _predicate_tools(inj["success"]):
            if tool not in {s["tool"] for s in inj["actions"]}:
                errors.append(f"{where}: success predicate expects {tool!r}, which the actions never call")
    for i, tpl in enumerate(data.get("attack_templates") or []):
        where = f"attack_templates/{i} ({tpl.get('id')})"
        errors.extend(f"{where}: {e}" for e in template_placeholder_errors(tpl["template"]))
    return errors


def _fixture_errors(fx: dict[str, Any], where: str, seeds: dict[str, frozenset[str]]) -> list[str]:
    errors: list[str] = []
    for pool, ids in _fixture_ids(fx).items():
        seen: set[str] = set()
        for fid in ids:
            if fid in seeds[pool]:
                errors.append(f"{where}: fixture {pool} id {fid!r} collides with the seeded World")
            if fid in seen:
                errors.append(f"{where}: duplicate fixture {pool} id {fid!r}")
            seen.add(fid)
    return errors


# --------------------------------------------------------------------------- loading


def read_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ScenarioError([f"{path.name}: YAML error: {exc}"]) from exc


def validate_file(path: Path, *, kind: Literal["tasks", "attacks"]) -> tuple[dict[str, Any], list[str]]:
    """Parse and validate one file. Returns ``(data, errors)``; errors are prefixed with the file name."""
    data = read_yaml(path)
    if data is None:
        return {}, [f"{path.name}: file is empty"]
    errs = schema_errors(data)
    if not errs:
        errs = semantic_errors(data, kind=kind)
    return data, [f"{path.name}: {e}" for e in errs]


def _expand_task(task: dict[str, Any], sets: dict[str, Any], source: str) -> UserTask:
    fixtures = Fixtures()
    for name in task.get("use_fixtures") or []:
        fixtures = fixtures.merged(Fixtures.model_validate(sets[name]))
    fixtures = fixtures.merged(Fixtures.model_validate(task.get("fixtures") or {}))
    body = {k: v for k, v in task.items() if k not in ("use_fixtures", "fixtures")}
    return UserTask.model_validate({**body, "fixtures": fixtures, "source_file": source})


def load_suite(directory: str | Path = SCENARIOS_DIR, *, include_attacks: bool = True,
               attacks_dir: str | Path | None = None) -> Suite:
    """Load every ``*.yaml`` user-task file in ``directory`` and (optionally) every attack file.

    Raises :class:`ScenarioError` listing all problems when anything is invalid.
    """
    directory = Path(directory)
    adir = Path(attacks_dir) if attacks_dir is not None else directory / "attacks"
    errors: list[str] = []
    suite = Suite()
    for path in sorted(directory.glob("*.yaml")):
        data, errs = validate_file(path, kind="tasks")
        errors.extend(errs)
        suite.files.append(str(path))
        if errs:
            continue
        sets = data.get("fixture_sets") or {}
        suite.user_tasks.extend(_expand_task(t, sets, path.name) for t in data.get("user_tasks") or [])
    if include_attacks and adir.is_dir():
        for path in sorted([*adir.glob("*.yaml"), *adir.glob("*.yml")]):
            data, errs = validate_file(path, kind="attacks")
            errors.extend(errs)
            suite.files.append(str(path))
            if errs:
                continue
            suite.injection_tasks.extend(InjectionTask.model_validate({**t, "source_file": path.name})
                                         for t in data.get("injection_tasks") or [])
            suite.attack_templates.extend(AttackTemplate.model_validate({**t, "source_file": path.name})
                                          for t in data.get("attack_templates") or [])
    for label, items in (("user task", suite.user_tasks), ("injection task", suite.injection_tasks),
                         ("attack template", suite.attack_templates)):
        seen: set[str] = set()
        for item in items:
            if item.id in seen:
                errors.append(f"duplicate {label} id {item.id!r}")
            seen.add(item.id)
    if errors:
        raise ScenarioError(errors)
    logger.info("loaded %d user tasks, %d injection tasks, %d attack templates from %d files",
                len(suite.user_tasks), len(suite.injection_tasks), len(suite.attack_templates), len(suite.files))
    return suite


def main(argv: list[str] | None = None) -> int:
    """``python -m bench.loader [DIR]``: validate scenario files and print a short inventory."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Validate Mirsad-Bench scenario files.")
    parser.add_argument("directory", nargs="?", default=str(SCENARIOS_DIR))
    parser.add_argument("--has-attacks", action="store_true",
                        help="exit 0 when valid attack files define injection tasks and templates, 3 when they do "
                             "not (1 when any file is invalid)")
    args = parser.parse_args(argv)
    try:
        suite = load_suite(args.directory)
    except ScenarioError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    if args.has_attacks and not suite.has_attacks:
        sys.stdout.write(f"no attack episodes: {len(suite.injection_tasks)} injection tasks, "
                         f"{len(suite.attack_templates)} attack templates\n")
        return 3
    by_lang: dict[str, int] = {}
    for t in suite.user_tasks:
        by_lang[t.lang] = by_lang.get(t.lang, 0) + 1
    sys.stdout.write(
        f"OK: {len(suite.user_tasks)} user tasks {by_lang}, {len(suite.injection_tasks)} injection tasks, "
        f"{len(suite.attack_templates)} attack templates\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
