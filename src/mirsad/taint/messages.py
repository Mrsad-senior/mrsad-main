"""Bilingual (English / Arabic) explanations for taint reasons.

Messages are written for a non-technical approver: they say what the agent is about to do,
which earlier tool result the data or destination came from, and why that matters. Technical
identifiers (call ids, hashes) stay in the reason's ``evidence``.
"""

from __future__ import annotations

import re

_INDEX_RE = re.compile(r"\[(\d+)\]")

# First-strong isolates keep Latin addresses readable inside Arabic text (and vice versa).
_FSI = "\u2068"
_PDI = "\u2069"

KIND_LABELS: dict[str, tuple[str, str]] = {
    "email": ("e-mail address", "عنوان البريد الإلكتروني"),
    "url": ("link", "الرابط"),
    "domain": ("website domain", "نطاق الموقع"),
    "iban": ("bank account number (IBAN)", "رقم الحساب البنكي (IBAN)"),
    "phone": ("phone number", "رقم الهاتف"),
    "number": ("number", "الرقم"),
    "id": ("record ID", "معرّف السجل"),
    "ngram": ("passage of text", "المقطع النصي"),
}


def isolate(text: str) -> str:
    return f"{_FSI}{text}{_PDI}"


def truncate(text: str, limit: int = 80) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def mask(value: str, kind: str) -> str:
    """Partially hide a confidential value so messages (and push notifications) do not spread it."""
    if kind == "ngram":
        return f'"{truncate(value, 60)}"'
    if kind == "email":
        local, _, domain = value.partition("@")
        return f"{local[:2]}•••@{domain}"
    if kind in ("phone", "iban", "number"):
        keep_head = 5 if kind == "phone" else 4 if kind == "iban" else 1
        if len(value) <= keep_head + 2:
            return "•" * len(value)
        return f"{value[:keep_head]}•••{value[-2:]}"
    return truncate(value, 40)


def humanize_field(field: str | None) -> tuple[str | None, int | None]:
    """``"emails[2].body"`` -> (``"body"``, 3): the field name and 1-based item number."""
    if not field:
        return None, None
    index = _INDEX_RE.search(field)
    leaf = _INDEX_RE.sub("", field).split(".")[-1] or None
    return leaf, (int(index.group(1)) + 1 if index else None)


def _source_en(tool: str, field: str | None) -> str:
    leaf, item = humanize_field(field)
    where = f"item {item} of " if item else ""
    if leaf:
        return f'the "{isolate(leaf)}" field of {where}a {isolate(tool)} result'
    return f"{where}a {isolate(tool)} result"


def _source_ar(tool: str, field: str | None) -> str:
    leaf, item = humanize_field(field)
    where = f"العنصر {item} من " if item else ""
    if leaf:
        return f'الحقل "{isolate(leaf)}" في {where}نتيجة الأداة {isolate(tool)}'
    return f"{where}نتيجة الأداة {isolate(tool)}"


def _more_en(extra: int, noun: str) -> str:
    return f" ({extra} more {noun} also matched.)" if extra > 0 else ""


def _more_ar(extra: int) -> str:
    return f" (وتطابقت {extra} عناصر أخرى أيضًا.)" if extra > 0 else ""


def untrusted_to_external(tool: str, source_tools: list[str]) -> tuple[str, str]:
    names = ", ".join(isolate(t) for t in source_tools) or "?"
    en = (
        f"{isolate(tool)} would send data outside the organisation, and earlier in this conversation "
        f"the assistant read content from an untrusted source ({names}). Instructions hidden in that "
        "content could be steering the assistant."
    )
    ar = (
        f"الأداة {isolate(tool)} سترسل بيانات إلى خارج المنظمة، وقد قرأ المساعد في وقت سابق من هذه "
        f"المحادثة محتوى من مصدر غير موثوق ({names}). قد يحتوي ذلك المحتوى على تعليمات مخفية توجّه المساعد."
    )
    return en, ar


def confidential_to_external(
    tool: str, kind: str, value: str, source_tool: str, field: str | None, extra: int
) -> tuple[str, str]:
    label_en, label_ar = KIND_LABELS.get(kind, (kind, kind))
    shown = isolate(mask(value, kind))
    en = (
        f"{isolate(tool)} would send confidential data outside the organisation: the {label_en} {shown} "
        f"comes from {_source_en(source_tool, field)}.{_more_en(extra, 'confidential items')}"
    )
    ar = (
        f"الأداة {isolate(tool)} سترسل بيانات سرية إلى خارج المنظمة: {label_ar} {shown} "
        f"مصدره {_source_ar(source_tool, field)}.{_more_ar(extra)}"
    )
    return en, ar


def untrusted_destination(
    tool: str,
    destination: str,
    match: str,
    domain: str | None,
    source_tool: str,
    field: str | None,
    extra: int,
) -> tuple[str, str]:
    dest = isolate(truncate(destination, 80))
    if match == "domain" and domain:
        what_en = f"The destination {dest} belongs to the domain {isolate(domain)}, which"
        what_ar = (
            f"الوجهة {dest} تتبع النطاق {isolate(domain)} الذي لم يحدده المستخدم ولا نظام موثوق، بل يظهر"
        )
    else:
        what_en = f"The destination {dest}"
        what_ar = f"الوجهة {dest} لم يحددها المستخدم ولا نظام موثوق، بل تظهر"
    en = (
        f"{what_en} was not given by the user or by a trusted system: it only appears inside untrusted "
        f"content ({_source_en(source_tool, field)}). An attacker may be redirecting {isolate(tool)} to "
        f"an address they control.{_more_en(extra, 'destinations')}"
    )
    ar = (
        f"{what_ar} فقط داخل محتوى غير موثوق ({_source_ar(source_tool, field)}). قد يحاول مهاجم "
        f"توجيه الأداة {isolate(tool)} إلى عنوان يتحكم فيه.{_more_ar(extra)}"
    )
    return en, ar


def after_injection(tool: str, risk: str) -> tuple[str, str]:
    risk_ar = {"high": "عالي الخطورة", "critical": "بالغ الخطورة"}.get(risk, risk)
    en = (
        "A prompt-injection attempt was detected earlier in this conversation, and "
        f"{isolate(tool)} is a {risk}-risk action. Make sure the user really asked for it."
    )
    ar = (
        "تم رصد محاولة حقن تعليمات (Prompt Injection) في وقت سابق من هذه المحادثة، والأداة "
        f"{isolate(tool)} إجراء {risk_ar}. تأكد من أن المستخدم طلبه فعلًا."
    )
    return en, ar
