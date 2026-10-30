"""Plain-language approval summaries for non-technical approvers (English and Arabic).

A summary has at most three sentences, built only from the call and the
decision's reasons (no LLM involved, so it cannot itself be prompt-injected):

1. what the agent wants to do (tool, key arguments, destination);
2. why Mirsad paused or blocked it, naming where the risky data came from;
3. the overall risk level.

Attacker-controlled values (addresses, URLs, ids) are shown verbatim but
length-limited and stripped of line breaks so they cannot fake extra sentences.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any, Literal

from mirsad.models import Action, Decision, Reason, Risk, SinkKind, ToolCall

Lang = Literal["en", "ar"]

_MAX_VALUE_CHARS = 80
_MAX_DESTINATIONS = 3
_DEST_PARAMS = ("to", "cc", "bcc", "recipient", "recipients", "url", "webhook", "endpoint", "to_iban", "iban")

# Higher first: the reasons an approver most needs to understand. Only two fit in a summary, so the
# security monitor's fraud signals (unrequested action, new payee, patient data leaving) rank near the top.
_REASON_PRIORITY = {
    "TAINT_UNTRUSTED_DESTINATION": 0,
    "HEALTH_DATA_EXTERNAL": 0.2,
    "TASK_INTENT_MISMATCH": 0.4,
    "SEMANTIC_TASK_MISMATCH": 0.4,
    "UNBOUND_TASK": 0.4,
    "NEW_BENEFICIARY": 0.6,
    "TAINT_AFTER_INJECTION": 1,
    "TAINT_CONFIDENTIAL_TO_EXTERNAL": 2,
    "SENSITIVE_OUTBOUND": 2.5,
    "TAINT_UNTRUSTED_TO_EXTERNAL": 3,
    "UNUSUAL_READ_THEN_SEND": 3.5,
    "REPEATED_EXPORT": 3.5,
    "RULE_MATCH": 4,
    "UNSEEN_TOOL_SEQUENCE": 4.5,
    "CONSTRAINT_VIOLATION": 5,
    "TOOL_NOT_ALLOWED": 6,
    "UNKNOWN_AGENT": 6,
    "RATE_LIMIT": 7,
    "APPROVAL_ALWAYS": 8,
    "APPROVAL_POLICY": 9,
}

_MONEY_TOOLS = ("transfer_funds", "approve_payment")

# Security-monitor reasons carry English messages only; these are the approver-facing phrases.
# Arabic phrases follow «لأن», so each starts with a noun.
_MONITOR_PHRASE = {
    "NEW_BENEFICIARY": (
        "this account has never been paid before and is not on the registered beneficiary list",
        "الحساب المستفيد غير مسجَّل في قائمة المستفيدين ولم يُحوَّل إليه من قبل"),
    "TASK_INTENT_MISMATCH": (
        "the user's original request did not ask for this kind of action",
        "طلب المستخدم الأصلي لم يتضمن هذا النوع من الإجراءات"),
    "SEMANTIC_TASK_MISMATCH": (
        "an intent check found that the user's original request did not ask for this action",
        "فحص النية وجد أن طلب المستخدم الأصلي لم يتضمن هذا الإجراء"),
    "UNBOUND_TASK": (
        "no verified user request is attached to this action",
        "غياب طلب مستخدم موثَّق مرتبط بهذا الإجراء"),
    "HEALTH_DATA_EXTERNAL": (
        "patient information would leave the hospital",
        "معلومات المريض ستخرج من المستشفى"),
    "SENSITIVE_OUTBOUND": (
        "the outgoing data contains sensitive personal or financial details",
        "البيانات الصادرة تحتوي تفاصيل شخصية أو مالية حساسة"),
    "UNUSUAL_READ_THEN_SEND": (
        "the agent read many records just before this outgoing action",
        "قراءة الوكيل عدداً كبيراً من السجلات قبل هذا الإجراء الصادر مباشرة"),
    "REPEATED_EXPORT": (
        "this is a repeated bulk export in the same session",
        "تكرار التصدير الجماعي في الجلسة نفسها"),
    "UNSEEN_TOOL_SEQUENCE": (
        "this sequence of actions has not been seen in reviewed normal use",
        "تسلسل الإجراءات هذا غير مألوف في الاستخدام الطبيعي المراجَع"),
}

_RISK_WORD = {
    "en": {"low": "low", "medium": "medium", "high": "high", "critical": "critical"},
    "ar": {"low": "منخفض", "medium": "متوسط", "high": "مرتفع", "critical": "حرج"},
}


# ----------------------------------------------------------------------------- small helpers


def _clean(value: Any, limit: int = _MAX_VALUE_CHARS) -> str:
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _num(value: Any, limit: int = 20) -> str:
    """``9500`` -> ``9,500`` and ``10000.0`` -> ``10,000``; anything non-numeric is shown as is."""
    if isinstance(value, bool):
        return _clean(value, limit)
    try:
        number = float(str(value).replace(",", ""))
    except ValueError:
        return _clean(value, limit)
    if number != number or number in (float("inf"), float("-inf")):
        return _clean(value, limit)
    return f"{number:,.0f}" if number == int(number) else f"{number:,.2f}"


def _flatten(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple, set)):
        out: list[str] = []
        for item in value:
            out.extend(_flatten(item))
        return out
    if isinstance(value, str):
        return [p.strip() for p in re.split(r"[;,]", value) if p.strip()]
    return [str(value)]


def _destinations(call: ToolCall) -> list[str]:
    seen: list[str] = []
    for param in _DEST_PARAMS:
        for item in _flatten(call.arguments.get(param)):
            item = _clean(item)
            if item and item not in seen:
                seen.append(item)
    return seen


def _join(items: list[str], lang: Lang) -> str:
    shown = items[:_MAX_DESTINATIONS]
    extra = len(items) - len(shown)
    if lang == "ar":
        text = "، ".join(shown)
        return text + (f" و{extra} غيرها" if extra else "")
    if extra:
        return ", ".join(shown) + f" and {extra} more"
    return shown[0] if len(shown) == 1 else ", ".join(shown[:-1]) + " and " + shown[-1]


def _first(ev: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if ev.get(key) not in (None, "", [], {}):
            return ev[key]
    return None


def _walk_dicts(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for v in value.values():
            yield from _walk_dicts(v)
    elif isinstance(value, list):
        for v in value:
            yield from _walk_dicts(v)


def _sources(evidence: dict[str, Any]) -> list[dict[str, str]]:
    """Find ``{tool, ref, field}`` provenance entries anywhere in a reason's evidence."""
    out: list[dict[str, str]] = []
    for d in _walk_dicts(evidence):
        tool = _first(d, "source_tool", "from_tool")
        if tool is None and d is not evidence:
            tool = _first(d, "tool")
        if tool is None:
            continue
        ref = _first(d, "source_ref", "source_id", "email_id", "doc_id", "source_call_id", "call_id")
        field = _first(d, "field", "source_field", "field_path")
        entry = {"tool": _clean(tool, 40), "ref": _clean(ref, 40) if ref else "", "field": _clean(field, 40) if field else ""}
        if entry not in out:
            out.append(entry)
    for item in _flatten(evidence.get("untrusted_sources")) if not out else []:
        tool, _, ref = item.partition(":")
        out.append({"tool": _clean(tool, 40), "ref": _clean(ref, 40), "field": ""})
    return out


def _source_kind(tool: str) -> str:
    t = tool.lower()
    if "invoice" in t:
        return "invoice"
    if "patient" in t:
        return "patient"
    if "mail" in t:
        return "email"
    if any(k in t for k in ("url", "web", "fetch", "browse", "http", "search_web")):
        return "web"
    if any(k in t for k in ("doc", "file", "pdf", "drive")):
        return "document"
    if any(k in t for k in ("customer", "crm", "contact")):
        return "crm"
    return "other"


_SOURCE_PHRASE = {
    ("en", True): {"email": "an untrusted email", "web": "an untrusted web page", "document": "an untrusted document",
                   "crm": "an untrusted CRM record", "invoice": "an untrusted supplier invoice",
                   "patient": "a patient record containing outside notes", "other": "untrusted tool output"},
    ("en", False): {"email": "an email", "web": "a web page", "document": "a document",
                    "crm": "a confidential customer record", "invoice": "an invoice",
                    "patient": "a confidential patient record", "other": "tool output"},
    ("ar", True): {"email": "بريد إلكتروني غير موثوق", "web": "صفحة ويب غير موثوقة", "document": "مستند غير موثوق",
                   "crm": "سجل عميل غير موثوق", "invoice": "فاتورة مورّد غير موثوقة",
                   "patient": "سجل مريض يحتوي ملاحظات خارجية", "other": "مخرجات أداة غير موثوقة"},
    ("ar", False): {"email": "بريد إلكتروني", "web": "صفحة ويب", "document": "مستند",
                    "crm": "سجل عميل سري", "invoice": "فاتورة", "patient": "سجل مريض سري", "other": "مخرجات أداة"},
}


def _describe_source(src: dict[str, str], lang: Lang, *, untrusted: bool) -> str:
    phrase = _SOURCE_PHRASE[(lang, untrusted)][_source_kind(src["tool"])]
    ref = f" {src['ref']}" if src["ref"] else ""
    return f"{phrase} ({src['tool']}{ref})"


def _describe_sources(sources: list[dict[str, str]], lang: Lang, *, untrusted: bool) -> str:
    return _join([_describe_source(s, lang, untrusted=untrusted) for s in sources], lang)


def _param_phrase(param: str | None, lang: Lang) -> str:
    p = (param or "").lower()
    if p in ("to", "cc", "bcc", "recipient", "recipients"):
        return "عنوان المستلم" if lang == "ar" else "the recipient address"
    if p in ("url", "webhook", "endpoint"):
        return "عنوان الويب" if lang == "ar" else "the web address"
    if p in ("to_iban", "iban"):
        return "رقم الحساب البنكي (IBAN) المستفيد" if lang == "ar" else "the destination bank account (IBAN)"
    if p in ("amount_sar", "amount"):
        return "المبلغ" if lang == "ar" else "the amount"
    if not p:
        return "إحدى القيم" if lang == "ar" else "a value"
    return f"قيمة «{param}»" if lang == "ar" else f"the value of “{param}”"


# ----------------------------------------------------------------------------- sentence 1: intent


def _payee(decision: Decision, lang: Lang) -> str:
    """Payee status for money tools, put in the first sentence (the part a lock screen shows)."""
    codes = {r.code for r in decision.reasons}
    if "NEW_BENEFICIARY" in codes:
        return "مستفيد جديد غير مسجَّل " if lang == "ar" else "a NEW, unregistered beneficiary "
    if "KNOWN_BENEFICIARY" in codes:
        return "المستفيد المسجَّل " if lang == "ar" else "the registered beneficiary "
    return ""


def _intent(call: ToolCall, decision: Decision, agent_name: str, lang: Lang,
            org_name: str | None, org_name_ar: str | None) -> str:
    args = call.arguments
    tool = _clean(call.tool, 60)
    dests = _destinations(call)
    dest_text = _join(dests, lang) if dests else ""
    outside = decision.sink == SinkKind.EXTERNAL
    agent = _clean(agent_name or call.agent_id, 60)
    payee = _payee(decision, lang) if call.tool in _MONEY_TOOLS else ""
    patient = _clean(args.get("patient_id", "?"), 40)

    if lang == "ar":
        org = org_name_ar or "المؤسسة"
        where = f" إلى {payee}{dest_text}" if dest_text else ""
        if outside and dest_text:
            where += f" (خارج {org})"
        verbs = {
            "send_email": f"إرسال بريد إلكتروني{where}",
            "fetch_url": f"فتح الرابط {dest_text}" + (f" (خارج {org})" if outside and dest_text else ""),
            "transfer_funds": f"تحويل {_num(args.get('amount_sar', '?'))} ريال سعودي{where}",
            "approve_payment": f"اعتماد الدفعة {_clean(args.get('transfer_id', '?'), 40)}",
            "send_lab_results": f"إرسال نتائج تحاليل المريض {patient}{where}",
            "update_prescription": f"تغيير وصفة المريض {patient} إلى «{_clean(args.get('prescription', '?'), 60)}»",
            "book_appointment": f"حجز موعد للمريض {patient} في {_clean(args.get('slot', '?'), 30)}",
            "read_invoice": f"قراءة الفاتورة {_clean(args.get('invoice_id', '?'), 40)}",
            "get_patient_record": f"فتح سجل المريض {patient}",
            "export_customers": f"تصدير {_clean(args.get('count', '?'), 12)} من سجلات العملاء",
            "delete_customer": f"حذف سجل العميل {_clean(args.get('customer_id', '?'), 40)}",
            "update_customer_note": f"تعديل الملاحظة على سجل العميل {_clean(args.get('customer_id', '?'), 40)}",
            "get_customer": f"الاطلاع على بيانات العميل {_clean(args.get('customer_id', '?'), 40)}",
            "search_customers": "البحث في سجلات العملاء",
            "read_email": f"قراءة البريد {_clean(args.get('email_id', '?'), 40)}",
            "read_document": f"قراءة المستند {_clean(args.get('doc_id', '?'), 40)}",
        }
        if call.tool in verbs:
            return f"يريد الوكيل «{agent}» {verbs[call.tool]} عبر الأداة {tool}."
        target = ""
        if dest_text:
            target = f" (الوجهة: {dest_text}" + (f"، خارج {org})" if outside else ")")
        return f"يريد الوكيل «{agent}» تشغيل الأداة {tool}{target}."

    org = org_name or "the organisation"
    where = f" to {payee}{dest_text}" if dest_text else ""
    if outside and dest_text:
        where += f" (outside {org})"
    verbs = {
        "send_email": f"send an email{where}",
        "fetch_url": f"open the web address {dest_text}" + (f" (outside {org})" if outside and dest_text else ""),
        "transfer_funds": f"transfer {_num(args.get('amount_sar', '?'))} SAR{where}",
        "approve_payment": f"approve payment {_clean(args.get('transfer_id', '?'), 40)}",
        "send_lab_results": f"send the lab results of patient {patient}{where}",
        "update_prescription": f"change the prescription of patient {patient} to “{_clean(args.get('prescription', '?'), 60)}”",
        "book_appointment": f"book an appointment for patient {patient} at {_clean(args.get('slot', '?'), 30)}",
        "read_invoice": f"read invoice {_clean(args.get('invoice_id', '?'), 40)}",
        "get_patient_record": f"open the record of patient {patient}",
        "export_customers": f"export {_clean(args.get('count', '?'), 12)} customer records",
        "delete_customer": f"delete customer record {_clean(args.get('customer_id', '?'), 40)}",
        "update_customer_note": f"change the note on customer {_clean(args.get('customer_id', '?'), 40)}",
        "get_customer": f"look up customer {_clean(args.get('customer_id', '?'), 40)}",
        "search_customers": "search the customer records",
        "read_email": f"read email {_clean(args.get('email_id', '?'), 40)}",
        "read_document": f"read document {_clean(args.get('doc_id', '?'), 40)}",
    }
    if call.tool in verbs:
        return f"The {agent} wants to {verbs[call.tool]} using the {tool} tool."
    target = ""
    if dest_text:
        target = f" (destination: {dest_text}" + (f", outside {org})" if outside else ")")
    return f"The {agent} wants to run the {tool} tool{target}."


# ----------------------------------------------------------------------------- sentence 2: why


def _constraint_phrase(ev: dict[str, Any], lang: Lang) -> str:
    param = ev.get("param") or ev.get("parameter") or ev.get("arg")
    op = str(ev.get("operator") or ev.get("op") or "")
    expected = ev.get("expected")
    actual = ev.get("actual")
    fmt = _num if op in ("max", "min") else _clean
    exp_text = _join([fmt(x, 40) for x in _flatten(expected)], lang) if expected is not None else ""
    act_text = fmt(actual, 60) if actual is not None else ""
    subject = _param_phrase(param, lang)
    if lang == "ar":
        # Gender-invariant predicates: the subject may be masculine or feminine.
        if op in ("domain_in",):
            return f"{subject} خارج النطاقات المسموح بها ({exp_text})"
        if op in ("domain_not_in",):
            return f"{subject} ضمن نطاق محظور ({exp_text})"
        if op == "max":
            return f"{subject} ({act_text}) أعلى من الحد الأقصى المسموح ({exp_text})"
        if op == "min":
            return f"{subject} ({act_text}) أقل من الحد الأدنى المسموح ({exp_text})"
        if op in ("max_length", "max_items"):
            return f"{subject} أطول من المسموح ({exp_text})"
        if op in ("pattern", "not_pattern", "type"):
            return f"{subject} بصيغة لا تسمح بها السياسة"
        if op in ("enum", "in", "not_in"):
            return f"{subject} خارج القيم المسموح بها"
        return f"في {subject} مخالفةً لأحد قيود السياسة"
    if op == "domain_in":
        return f"{subject} is outside the allowed domains ({exp_text})"
    if op == "domain_not_in":
        return f"{subject} is in a blocked domain ({exp_text})"
    if op == "max":
        return f"{subject} ({act_text}) is above the allowed maximum of {exp_text}"
    if op == "min":
        return f"{subject} ({act_text}) is below the allowed minimum of {exp_text}"
    if op in ("max_length", "max_items"):
        return f"{subject} is longer than allowed ({exp_text})"
    if op in ("pattern", "not_pattern", "type"):
        return f"{subject} does not match the format the policy allows"
    if op in ("enum", "in", "not_in"):
        return f"{subject} is not one of the allowed values"
    return f"{subject} breaks a policy constraint"


def _reason_phrase(reason: Reason, decision: Decision, lang: Lang, injection: bool, tool: str = "") -> str:
    ev = reason.evidence or {}
    code = reason.code
    ar = lang == "ar"
    sources = _sources(ev)
    money = tool in _MONEY_TOOLS

    if code in _MONITOR_PHRASE:
        return _MONITOR_PHRASE[code][1 if ar else 0]

    # Arabic phrases follow «لأن», so each one starts with a noun and avoids gendered predicates.
    if code == "TAINT_UNTRUSTED_DESTINATION":
        subject = _param_phrase(_first(ev, "param", "parameter", "arg"), lang)
        src = _describe_sources(sources, lang, untrusted=True) if sources else (
            "محتوى غير موثوق" if ar else "untrusted content")
        if ar:
            return f"مصدر {subject} {src}" + ("، وهو محتوى رُصدت فيه تعليمات مشبوهة" if injection else "")
        return f"{subject} came from {src}" + (" that contained suspected instructions" if injection else "")
    if code == "TAINT_UNTRUSTED_TO_EXTERNAL":
        if ar:
            src = _describe_sources(sources, lang, untrusted=True) if sources else "محتوى غير موثوق"
            what = "يحوّل أموالاً" if money else "يرسل بيانات"
            return f"الوكيل اطّلع في هذه الجلسة على {src}، وهذا الإجراء {what} إلى خارج المؤسسة"
        src = _describe_sources(sources, lang, untrusted=True) if sources else "untrusted content"
        what = "this payment sends money" if money else "this action sends data"
        return f"the agent read {src} earlier in this session, and {what} outside the organisation"
    if code == "TAINT_CONFIDENTIAL_TO_EXTERNAL":
        src = _describe_sources(sources, lang, untrusted=False) if sources else ""
        if ar:
            return "الطلب سيُرسل بيانات سرية" + (f" مصدرها {src}" if src else "") + " إلى خارج المؤسسة"
        return "it would send confidential data" + (f" from {src}" if src else "") + " outside the organisation"
    if code == "TAINT_AFTER_INJECTION":
        risk = _RISK_WORD[lang].get(str(ev.get("tool_risk") or ev.get("risk") or "high"), _RISK_WORD[lang]["high"])
        if ar:
            return f"محاولة حقن تعليمات مشبوهة رُصدت في وقت سابق من هذه الجلسة، ومستوى خطورة هذا الإجراء {risk}"
        return f"a suspected prompt injection was detected earlier in this session and this is a {risk}-risk action"
    if code == "CONSTRAINT_VIOLATION":
        return _constraint_phrase(ev, lang)
    if code == "APPROVAL_ALWAYS":
        return "السياسة تشترط موافقة بشرية على كل استخدام لهذه الأداة" if ar else \
            "the policy requires a human to approve every use of this tool"
    if code == "APPROVAL_POLICY":
        risk = _RISK_WORD[lang][decision.risk.value]
        return f"مستوى الخطورة الإجمالي ({risk}) يستلزم موافقة بشرية وفق السياسة" if ar else \
            f"its overall risk ({risk}) needs human approval under the policy"
    if code == "RULE_MATCH":
        rule = _clean(reason.rule_id or ev.get("rule_id") or "?", 60)
        return f"الطلب يطابق قاعدة السياسة «{rule}»" if ar else f"it matches the policy rule “{rule}”"
    if code == "RATE_LIMIT":
        return "الوكيل تجاوز الحد المسموح لعدد مرات استخدام هذه الأداة" if ar else \
            "the agent has exceeded how often it may use this tool"
    if code == "TOOL_NOT_ALLOWED":
        return "هذا الوكيل غير مسموح له باستخدام هذه الأداة" if ar else "this agent is not allowed to use this tool"
    if code == "UNKNOWN_AGENT":
        return "هذا الوكيل غير مسجل في السياسة" if ar else "this agent is not registered in the policy"
    # Unknown code (e.g. added by another layer later): fall back to the layer's own message.
    if ar:
        # Never put an English-only message inside an Arabic card.
        text = _clean(reason.message_ar, 200).rstrip(".") if reason.message_ar else ""
        return f"الفحص أشار إلى ما يلي: {text}" if text else "فحصاً أمنياً إضافياً اعترض على هذا الإجراء"
    text = _clean(reason.message, 200).rstrip(".")
    if len(text) > 1 and text[0].isupper() and text[1].islower():
        text = text[0].lower() + text[1:]
    return text or code


def _why(decision: Decision, lang: Lang, tool: str = "") -> str:
    objecting = [r for r in decision.reasons if r.action != Action.ALLOW]
    objecting.sort(key=lambda r: (_REASON_PRIORITY.get(r.code, 50), -r.risk_score))
    injection = any(
        r.code == "TAINT_AFTER_INJECTION" or r.layer == "detector" or (r.evidence or {}).get("injection_detected")
        for r in decision.reasons
    )
    phrases: list[str] = []
    codes = {r.code for r in objecting}
    for reason in objecting:
        # The destination phrase already says the source "contained suspected instructions".
        if reason.code == "TAINT_AFTER_INJECTION" and "TAINT_UNTRUSTED_DESTINATION" in codes:
            continue
        phrase = _reason_phrase(reason, decision, lang, injection, tool)
        if phrase and phrase not in phrases:
            phrases.append(phrase)
        if len(phrases) == 2:
            break

    if lang == "ar":
        verb = "منع مرصاد الطلب" if decision.action == Action.DENY else "أوقف مرصاد الطلب مؤقتًا"
        if not phrases:
            return f"{verb} بانتظار مراجعتك."
        return f"{verb} لأن " + "، ولأن ".join(phrases) + "."
    verb = "Mirsad blocked it" if decision.action == Action.DENY else "Mirsad paused it"
    if not phrases:
        return f"{verb} for your review."
    return f"{verb} because " + ", and ".join(phrases) + "."


def summarize(call: ToolCall, decision: Decision, *, agent_name: str, lang: Literal["en", "ar"],
              org_name: str | None = None, org_name_ar: str | None = None) -> str:
    """Plain-language 1-3 sentences: what the agent wants, why Mirsad paused it, the risk."""
    if lang not in ("en", "ar"):
        raise ValueError("lang must be 'en' or 'ar'")
    parts = [_intent(call, decision, agent_name, lang, org_name, org_name_ar)]
    if decision.action != Action.ALLOW:
        parts.append(_why(decision, lang, call.tool))
    risk: Risk = decision.risk
    if lang == "ar":
        parts.append(f"مستوى الخطورة: {_RISK_WORD['ar'][risk.value]}.")
    else:
        parts.append(f"Risk level: {_RISK_WORD['en'][risk.value]}.")
    return " ".join(parts)
