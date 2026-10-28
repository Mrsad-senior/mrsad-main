"""JSON helpers shared by the adapters and the SDK.

Every tool result that Mirsad inspects needs a *text* form (what the model reads,
what the detector scans) and, when possible, a *structured* form (so the taint
tracker can see field names such as ``from`` or ``customer_id``).
"""

from __future__ import annotations

import base64
import dataclasses
import datetime as _dt
import enum
import json
import uuid
from decimal import Decimal
from pathlib import PurePath
from typing import Any

from pydantic import BaseModel

__all__ = ["jsonable", "parse_json_text", "to_json_text"]


def _default(value: Any) -> Any:
    """``json.dumps`` fallback for common non-JSON types."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    if isinstance(value, (set, frozenset)):
        return sorted(value, key=repr)
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        return value.isoformat()
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, (bytes, bytearray)):
        try:
            return bytes(value).decode("utf-8")
        except UnicodeDecodeError:
            return base64.b64encode(bytes(value)).decode("ascii")
    if isinstance(value, (Decimal, uuid.UUID, PurePath)):
        return str(value)
    return repr(value)


def jsonable(value: Any) -> Any:
    """Return a deep copy of ``value`` made only of JSON types (dict/list/str/number/bool/None)."""
    return json.loads(json.dumps(value, ensure_ascii=False, default=_default))


def parse_json_text(text: str | None) -> Any | None:
    """Parse ``text`` as JSON; ``None`` when it is empty or not valid JSON."""
    if not text:
        return None
    stripped = text.strip()
    if not stripped:
        return None
    try:
        return json.loads(stripped)
    except (ValueError, RecursionError):
        return None


def to_json_text(value: Any) -> tuple[str, Any | None]:
    """Text and structured forms of an arbitrary tool return value.

    * ``str`` is kept verbatim; its structured form is the parsed JSON when the text is JSON.
    * ``None`` becomes ``""``.
    * ``bytes`` are decoded as UTF-8 (invalid bytes replaced).
    * Everything else is serialised to JSON (pydantic models, dataclasses, sets and dates
      included); the structured form is the JSON value itself.
    """
    if value is None:
        return "", None
    if isinstance(value, str):
        return value, parse_json_text(value)
    if isinstance(value, (bytes, bytearray)):
        text = bytes(value).decode("utf-8", errors="replace")
        return text, parse_json_text(text)
    structured = jsonable(value)
    return json.dumps(structured, ensure_ascii=False), structured
