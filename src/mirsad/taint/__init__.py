"""Taint tracking: follow untrusted and confidential data from tool results into tool calls.

Public interface (BUILD_SPEC section 3)::

    TaintTracker(max_values_per_session=2000, session_ttl_s=6 * 3600)
    extract_values(text_or_structured, *, trusted_fields) -> list[(value, kind, field_path, from_trusted_field)]
"""

from mirsad.taint.extract import ExtractedValue, extract_values
from mirsad.taint.rules import (
    CODE_AFTER_INJECTION,
    CODE_CONFIDENTIAL_TO_EXTERNAL,
    CODE_UNTRUSTED_DESTINATION,
    CODE_UNTRUSTED_TO_EXTERNAL,
    TAINT_CODES,
    ResolvedTaintSettings,
    TaintView,
    evaluate_rules,
)
from mirsad.taint.tracker import TaintTracker

__all__ = [
    "CODE_AFTER_INJECTION",
    "CODE_CONFIDENTIAL_TO_EXTERNAL",
    "CODE_UNTRUSTED_DESTINATION",
    "CODE_UNTRUSTED_TO_EXTERNAL",
    "TAINT_CODES",
    "ExtractedValue",
    "ResolvedTaintSettings",
    "TaintTracker",
    "TaintView",
    "evaluate_rules",
    "extract_values",
]
