"""Bilingual (English / Arabic) message templates for policy-layer reasons.

These strings reach approvers and administrators, so they are written as
plain sentences rather than error codes.
"""

from __future__ import annotations

import json
from typing import Any

from mirsad.models import Risk

RISK_AR = {
    Risk.LOW: "منخفضة",
    Risk.MEDIUM: "متوسطة",
    Risk.HIGH: "مرتفعة",
    Risk.CRITICAL: "حرجة",
}

_TEMPLATES: dict[str, tuple[str, str]] = {
    "UNKNOWN_AGENT": (
        "Agent '{agent}' is not defined in the active policy, so all of its tool calls are denied.",
        "الوكيل '{agent}' غير مُعرَّف في السياسة النشطة، لذلك تُرفض جميع استدعاءاته للأدوات.",
    ),
    "TOOL_NOT_ALLOWED": (
        "Tool '{tool}' is not allowed for agent '{agent}' (policy entry: {entry}).",
        "الأداة '{tool}' غير مسموح بها للوكيل '{agent}' (مدخل السياسة: {entry}).",
    ),
    "TOOL_RISK": (
        "Tool '{tool}' is classified as {risk} risk (score {score}).",
        "الأداة '{tool}' مصنّفة بدرجة خطورة {risk_ar} (الدرجة {score}).",
    ),
    "APPROVAL_ALWAYS": (
        "The policy requires human approval for every call to '{tool}'.",
        "تشترط السياسة موافقة بشرية على كل استدعاء للأداة '{tool}'.",
    ),
    "RATE_LIMIT": (
        "Rate limit exceeded for '{tool}': {count} calls in the last {window} seconds (limit {limit}).",
        "تم تجاوز حدّ معدّل الاستخدام للأداة '{tool}': {count} استدعاءً خلال آخر {window} ثانية (الحد {limit}).",
    ),
    "RULE_MATCH": (
        "Policy rule '{rule}' matched{desc}.",
        "انطبقت قاعدة السياسة '{rule}'{desc}.",
    ),
    # constraint operators -------------------------------------------------
    "max": (
        "Argument '{param}' is {actual}, above the maximum of {expected}.",
        "قيمة الحقل '{param}' هي {actual}، وهي تتجاوز الحد الأقصى المسموح به ({expected}).",
    ),
    "min": (
        "Argument '{param}' is {actual}, below the minimum of {expected}.",
        "قيمة الحقل '{param}' هي {actual}، وهي أقل من الحد الأدنى المسموح به ({expected}).",
    ),
    "not_number": (
        "Argument '{param}' must be a number to check '{operator}: {expected}', but it is {actual}.",
        "يجب أن تكون قيمة الحقل '{param}' رقمًا للتحقق من الشرط '{operator}: {expected}'، لكن قيمته {actual}.",
    ),
    "max_length": (
        "Argument '{param}' is {actual} characters long; the maximum is {expected}.",
        "طول الحقل '{param}' هو {actual} حرفًا، والحد الأقصى المسموح به {expected}.",
    ),
    "min_length": (
        "Argument '{param}' is {actual} characters long; the minimum is {expected}.",
        "طول الحقل '{param}' هو {actual} حرفًا، والحد الأدنى المطلوب {expected}.",
    ),
    "enum": (
        "Argument '{param}' has the value {actual}, which is not one of the allowed values {expected}.",
        "القيمة {actual} في الحقل '{param}' ليست من القيم المسموح بها {expected}.",
    ),
    "not_in": (
        "Argument '{param}' contains the forbidden value {actual}.",
        "يحتوي الحقل '{param}' على قيمة محظورة: {actual}.",
    ),
    "pattern": (
        "Argument '{param}' does not match the required pattern {expected}.",
        "قيمة الحقل '{param}' لا تطابق النمط المطلوب {expected}.",
    ),
    "not_pattern": (
        "Argument '{param}' matches the forbidden pattern {expected}.",
        "قيمة الحقل '{param}' تطابق نمطًا محظورًا {expected}.",
    ),
    "regex_too_long": (
        "Argument '{param}' is longer than {limit} characters and cannot be checked safely against '{operator}'.",
        "يتجاوز طول الحقل '{param}' حدّ {limit} حرف، ولا يمكن فحصه بأمان وفق الشرط '{operator}'.",
    ),
    "domain_in": (
        "Argument '{param}' sends data to {actual}, outside the allowed domains {expected}.",
        "الحقل '{param}' يرسل البيانات إلى {actual}، وهو خارج النطاقات المسموح بها {expected}.",
    ),
    "domain_not_in": (
        "Argument '{param}' targets the blocked domain {actual}.",
        "الحقل '{param}' يستهدف نطاقًا محظورًا: {actual}.",
    ),
    "max_items": (
        "Argument '{param}' has {actual} items; at most {expected} are allowed.",
        "يحتوي الحقل '{param}' على {actual} عنصرًا، والحد الأقصى المسموح به {expected}.",
    ),
    "required": (
        "Required argument '{param}' is missing.",
        "الحقل الإلزامي '{param}' مفقود.",
    ),
    "type": (
        "Argument '{param}' must be of type {expected}, but it is {actual}.",
        "يجب أن يكون الحقل '{param}' من النوع {expected}، لكنه من النوع {actual}.",
    ),
}


def render(key: str, **values: Any) -> tuple[str, str]:
    """Return ``(message, message_ar)`` for a template key."""
    en, ar = _TEMPLATES[key]
    return en.format(**values), ar.format(**values)


def fmt_value(value: Any, *, limit: int = 80) -> str:
    """Short human-readable rendering of an argument value or limit for messages."""
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, float) and value.is_integer():
        text = str(int(value))
    elif isinstance(value, (int, float)):
        text = str(value)
    elif isinstance(value, str):
        text = f"'{value}'"
    elif isinstance(value, (list, tuple, set)):
        text = "[" + ", ".join(fmt_value(v, limit=limit) for v in value) + "]"
    elif value is None:
        text = "null"
    else:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text


def fmt_score(score: float) -> str:
    return f"{score:.1f}"
