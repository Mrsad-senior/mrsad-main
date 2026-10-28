"""Detector dataset schema (BUILD_SPEC section 12) and JSONL helpers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

from mirsad.detector.normalize import normalize

Lang = Literal["en", "ar", "mixed"]
Variety = Literal["en", "msa", "gulf", "egyptian", "levantine", "arabizi", "mixed"]
Carrier = Literal["email", "web", "document", "crm_note", "chat", "tool_output", "review", "ticket",
                  "code_comment", "plain"]
AttackType = Literal["none", "goal_hijack", "data_exfiltration", "tool_misuse", "role_impersonation",
                     "context_ignoring", "obfuscated", "payload_splitting", "social_engineering",
                     "markdown_exfil", "system_prompt_leak"]
Difficulty = Literal["easy", "medium", "hard"]

MAX_TEXT_CHARS = 50_000
CORE_SPLITS = ("train", "val", "test_en", "test_ar", "test_mixed")


class DatasetRecord(BaseModel):
    """One labelled example. ``label`` 1 = prompt injection aimed at an AI agent, 0 = benign."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=False)

    id: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    label: StrictInt
    lang: Lang
    variety: Variety
    carrier: Carrier
    attack_type: AttackType
    difficulty: Difficulty
    source: str = ""
    notes: str = ""

    @field_validator("id")
    @classmethod
    def _id_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("id is blank")
        return v.strip()

    @field_validator("text")
    @classmethod
    def _text_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text is blank")
        return v

    @field_validator("label")
    @classmethod
    def _label_binary(cls, v: int) -> int:
        if v not in (0, 1):
            raise ValueError("label must be 0 or 1")
        return v

    def warnings(self) -> list[str]:
        """Soft consistency problems (reported, record kept)."""
        out: list[str] = []
        if self.label == 1 and self.attack_type == "none":
            out.append("injection_without_attack_type")
        if self.label == 0 and self.attack_type != "none":
            out.append("benign_with_attack_type")
        if self.lang == "en" and self.variety not in ("en", "mixed"):
            out.append("lang_variety_mismatch")
        if self.lang == "ar" and self.variety in ("en",):
            out.append("lang_variety_mismatch")
        extra = set(self.model_extra or {})
        if extra:
            out.append("unknown_fields")
        return out


def text_hash(text: str) -> str:
    """Deduplication key: SHA-256 of the detector's normalised view of the text."""
    return hashlib.sha256(normalize(text).text.encode("utf-8")).hexdigest()


def iter_jsonl(path: Path) -> Iterator[tuple[int, str]]:
    with path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            if line.strip():
                yield lineno, line


def read_records(path: str | Path) -> list[dict[str, Any]]:
    """Read an already-validated split file (plain dicts)."""
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for _, line in iter_jsonl(path)]


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=False) + "\n")
            n += 1
    return n
