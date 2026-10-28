"""Prompt-injection detector (Arabic + English): normalisation, rules, ML model, ensemble, actions.

Public interface (BUILD_SPEC section 4)::

    normalize(text) -> NormalizedText
    detect_language(text) -> "en" | "ar" | "mixed" | "other"
    RuleSet().match(normalized) -> list[RuleHit]
    InjectionDetector(model_dir=None, *, window_chars=600, stride_chars=300)
        .default() / .scan(text) / .scan_structured(value)
    sanitize(text, detection, *, mode="sanitize" | "block") -> str
    spotlight(text, *, source, call_id) -> str
"""

from mirsad.detector.detector import DEFAULT_MODEL_DIR, MODEL_SPAN_ID, InjectionDetector, load_model
from mirsad.detector.language import detect_language
from mirsad.detector.normalize import EVASION_SIGNALS, NormalizedText, normalize
from mirsad.detector.rules import Rule, RuleHit, RuleSet, rule_score
from mirsad.detector.sanitize import (
    BLOCK_TEMPLATE,
    SANITIZE_MARKER,
    block_notice,
    sanitize,
    sanitize_structured,
    spotlight,
)

__all__ = [
    "BLOCK_TEMPLATE",
    "DEFAULT_MODEL_DIR",
    "EVASION_SIGNALS",
    "MODEL_SPAN_ID",
    "SANITIZE_MARKER",
    "InjectionDetector",
    "NormalizedText",
    "Rule",
    "RuleHit",
    "RuleSet",
    "block_notice",
    "detect_language",
    "load_model",
    "normalize",
    "rule_score",
    "sanitize",
    "sanitize_structured",
    "spotlight",
]
