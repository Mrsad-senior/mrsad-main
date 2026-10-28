"""Keep docs/policy-language.md honest: its complete YAML examples must behave as documented."""

from __future__ import annotations

import re

from policy_helpers import ROOT

from mirsad.policy import validate_policy

DOC = ROOT / "docs" / "policy-language.md"


def yaml_blocks() -> list[str]:
    text = DOC.read_text(encoding="utf-8")
    return [b for b in re.findall(r"```yaml\n(.*?)```", text, flags=re.S) if b.startswith("version: 1\n")]


def test_documentation_exists_and_covers_every_operator():
    text = DOC.read_text(encoding="utf-8")
    for operator in ("max", "min", "max_length", "min_length", "enum", "in", "not_in", "pattern", "not_pattern",
                     "domain_in", "domain_not_in", "max_items", "required", "type", "on_violation"):
        assert f"`{operator}`" in text, operator
    for heading in ("Monitor mode", "deny-overrides", "Worked scenarios", "XACML", "Limitations"):
        assert heading in text


def test_complete_examples_in_the_documentation():
    blocks = yaml_blocks()
    valid = [b for b in blocks if "# line" not in b]
    broken = [b for b in blocks if "# line" in b]
    assert valid and len(broken) == 1
    for block in valid:
        assert validate_policy(block) == [], block
    errors = validate_policy(broken[0])
    assert [int(e.split(",")[0].removeprefix("line ")) for e in errors] == [9, 11, 13, 16]
