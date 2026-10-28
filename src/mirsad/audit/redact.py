"""Deep redaction of secrets and regulated personal identifiers.

Applied to every audit payload (and stored approval arguments) before it is
persisted, so credentials that an agent handled never land in the long-lived,
exportable audit trail. Two mechanisms are combined:

* **field names**: values under keys such as ``password``, ``api_key``, ``token``
  or ``authorization`` are replaced wholesale;
* **value shapes**: free text is scanned for well-known secret formats (provider
  API keys, JWTs, bearer tokens, PEM private keys, ``password=...`` assignments)
  and for personal identifiers regulated under the Saudi PDPL (Luhn-valid card
  numbers, Saudi national/iqama IDs, IBANs), which are masked to the last four
  characters so records remain correlatable without exposing the full number.

Redaction is deliberately fail-safe: ambiguous 10-digit numbers starting with 1 or
2 are treated as national IDs. Ordinary prose, e-mail addresses, URLs and
domain names are left untouched because the audit trail needs them.
"""

from __future__ import annotations

import base64
import math
import re
from collections.abc import Mapping
from datetime import date, datetime
from enum import Enum
from pathlib import PurePath
from typing import Any

from pydantic import BaseModel

from mirsad.textutil import IBAN_RE

REDACTED = "[REDACTED]"

# ---------------------------------------------------------------------------------------- keys

_SECRET_KEY_RE = re.compile(
    r"(?:^|_)(?:password|passwd|pwd|passphrase|secret|client_secret|secret_key|api_key|apikey|"
    r"access_key|private_key|token|access_token|refresh_token|id_token|auth_token|session_token|"
    r"bearer|authorization|auth|cookie|set_cookie|credential|credentials|otp|cvv|cvc|pin|"
    r"signing_key|hmac_key|webhook_secret)(?:$|_)"
)
# Metadata about a secret is not itself secret and is useful in the audit trail.
_SAFE_KEY_SUFFIX_RE = re.compile(r"_(?:type|types|count|len|length|ttl|expires|expires_in|at|prefix|hint|id|ids)$")
_NATIONAL_ID_KEY_RE = re.compile(
    r"(?:^|_)(?:national_id|nationalid|national_number|iqama|iqama_number|iqama_id|id_number|nin|civil_id)(?:$|_)"
)


def _normalise_key(key: str) -> str:
    key = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key)
    return re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")


def is_secret_key(key: str) -> bool:
    """True when a mapping key names a credential whose value must never be stored."""
    norm = _normalise_key(key)
    return bool(_SECRET_KEY_RE.search(norm)) and not _SAFE_KEY_SUFFIX_RE.search(norm)


# -------------------------------------------------------------------------------------- values

_DIGIT = r"[0-9٠-٩۰-۹]"
_TO_ASCII = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

_PEM_RE = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----.*?(?:-----END [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----|\Z)",
    re.DOTALL,
)
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}")
# Header form: everything after the scheme is a credential.
_AUTH_HEADER_RE = re.compile(
    r"(?i)\b((?:proxy-)?authorization\"?\s*[:=]\s*\"?)((?:bearer|basic|digest|token|negotiate)\s+)?[^\s,;\"']{6,}"
)
# Free-text form: require a long token with a digit or punctuation so prose ("bearer of news") survives.
_BEARER_RE = re.compile(r"(?i)\b(bearer)(\s+)(?=[A-Za-z0-9._~+/=-]*[0-9._~+/=-])[A-Za-z0-9._~+/=-]{16,}")
_MIRSAD_KEY_RE = re.compile(r"\bmk_([A-Za-z0-9]{8})_[A-Za-z0-9_-]{16,}")
_PROVIDER_KEY_RES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bsk-(?:proj-|ant-(?:api\d+-)?|admin-)?[A-Za-z0-9_-]{16,}"), "API_KEY"),
    (re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}"), "API_KEY"),
    (re.compile(r"\b(?:AKIA|ASIA|AGPA|AIDA|AROA|ANPA|ANVA|AIPA)[A-Z0-9]{16}\b"), "AWS_KEY"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"), "GITHUB_TOKEN"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}"), "GITHUB_TOKEN"),
    (re.compile(r"\bxox[abprse]-[A-Za-z0-9-]{10,}"), "SLACK_TOKEN"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{35}"), "GOOGLE_KEY"),
    (re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}"), "GITLAB_TOKEN"),
]
_ASSIGNMENT_RE = re.compile(
    r"(?i)\b((?:password|passwd|pwd|passphrase|secret|client[_-]?secret|api[_-]?key|access[_-]?key|"
    r"secret[_-]?key|token|access[_-]?token|auth[_-]?token|refresh[_-]?token|private[_-]?key))"
    # quoted value (anything up to the closing quote) or bare value (stops at URL/CSV separators)
    r"(\"?\s*[:=]\s*)(?:(\"[^\"\n]{1,512}\"|'[^'\n]{1,512}')|([^\s\"',;&]{3,}))"
)


def _redact_assignment(m: re.Match[str]) -> str:
    quoted = m.group(3)
    value = f"{quoted[0]}{REDACTED}{quoted[0]}" if quoted else REDACTED
    return f"{m.group(1)}{m.group(2)}{value}"
_ARABIC_PASSWORD_RE = re.compile(r"(كلمة\s+(?:المرور|السر|مرور|سر)|الرقم\s+السري)(\s*[:：=]\s*)(\S+)")

# Contiguous 13-19 digits, 4-4-4-x groups or the Amex 4-6-5 layout, with one consistent separator.
# Free-form digit runs ("2024-01-15 2024-02-16") are intentionally not candidates.
_CARD_CANDIDATE_RE = re.compile(
    rf"(?<![\d+.\w])(?:{_DIGIT}{{13,19}}"
    rf"|{_DIGIT}{{4}}([ -]){_DIGIT}{{4}}\1{_DIGIT}{{4}}\1{_DIGIT}{{1,7}}"
    rf"|{_DIGIT}{{4}}([ -]){_DIGIT}{{6}}\2{_DIGIT}{{5}})(?![\d\w])"
)
_NATIONAL_ID_RE = re.compile(r"(?<![\d.\w])[12١٢][0-9٠-٩]{9}(?![\d\w]|\.\d)")


def luhn_valid(digits: str) -> bool:
    """Luhn (mod 10) check, as used by payment cards (and Saudi national IDs)."""
    digits = digits.translate(_TO_ASCII)
    if not digits.isdigit():
        return False
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _mask_keep_last(text: str, keep_last: int, keep_first: int = 0) -> str:
    """Replace alphanumerics with ``*`` except the first/last N, preserving separators."""
    positions = [i for i, ch in enumerate(text) if ch.isalnum()]
    keep = set(positions[:keep_first]) | set(positions[-keep_last:] if keep_last else [])
    return "".join(ch if (i in keep or not ch.isalnum()) else "*" for i, ch in enumerate(text))


def _mask_card(match: re.Match[str]) -> str:
    raw = match.group(0)
    digits = re.sub(r"\D", "", raw.translate(_TO_ASCII))
    # Payment cards start with 2-6 (ISO/IEC 7812 major industry identifier); this skips
    # millisecond timestamps (1...) and international phone numbers (9...).
    if 13 <= len(digits) <= 19 and digits[0] in "23456" and luhn_valid(digits):
        return _mask_keep_last(raw, 4)
    return raw


def _mask_iban(match: re.Match[str]) -> str:
    return _mask_keep_last(match.group(0), keep_last=4, keep_first=2)


def _mask_national_id(match: re.Match[str]) -> str:
    return _mask_keep_last(match.group(0), 4)


def redact_text(text: str) -> str:
    """Redact secret and identifier shapes inside free text."""
    if not text:
        return text
    text = _PEM_RE.sub("[REDACTED:PRIVATE_KEY]", text)
    text = _JWT_RE.sub("[REDACTED:JWT]", text)
    text = _AUTH_HEADER_RE.sub(lambda m: f"{m.group(1)}{m.group(2) or ''}{REDACTED}", text)
    text = _BEARER_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", text)
    text = _MIRSAD_KEY_RE.sub(lambda m: f"mk_{m.group(1)}_{REDACTED}", text)
    for pattern, label in _PROVIDER_KEY_RES:
        text = pattern.sub(f"[REDACTED:{label}]", text)
    text = _ASSIGNMENT_RE.sub(_redact_assignment, text)
    text = _ARABIC_PASSWORD_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", text)
    text = IBAN_RE.sub(_mask_iban, text)
    text = _CARD_CANDIDATE_RE.sub(_mask_card, text)
    text = _NATIONAL_ID_RE.sub(_mask_national_id, text)
    return text


def to_jsonable(value: Any) -> Any:
    """Convert pydantic models, enums, tuples, sets, dates and bytes into plain JSON types."""
    if isinstance(value, BaseModel):
        return to_jsonable(value.model_dump(mode="json"))
    if isinstance(value, Enum):
        return to_jsonable(value.value)
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)  # NaN/inf are not valid JSON (browsers reject them)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        items = sorted(value, key=repr) if isinstance(value, (set, frozenset)) else value
        return [to_jsonable(v) for v in items]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        return "base64:" + base64.b64encode(bytes(value)).decode()
    if isinstance(value, PurePath):
        return str(value)
    return str(value)


def _redact_national_id_value(value: Any) -> Any:
    if isinstance(value, (int, str)) and not isinstance(value, bool):
        text = str(value)
        return _mask_keep_last(text, 4) if len(text) > 4 else "*" * len(text)
    return _redact(value)


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if is_secret_key(key) and item not in (None, "", [], {}):
                out[key] = REDACTED
            elif _NATIONAL_ID_KEY_RE.search(_normalise_key(key)):
                out[key] = _redact_national_id_value(item)
            else:
                out[key] = _redact(item)
        return out
    if isinstance(value, list):
        return [_redact(v) for v in value]
    if isinstance(value, int) and not isinstance(value, bool):
        # Card numbers occasionally arrive as integers; national IDs are only masked by key
        # because bare 10-digit integers are usually UNIX timestamps.
        masked = redact_text(str(value)) if len(str(abs(value))) >= 13 else str(value)
        return value if masked == str(value) else masked
    return value


def redact(value: Any) -> Any:
    """Return a deep copy of ``value`` with secrets and regulated identifiers masked.

    The input is not modified. Pydantic models, enums, tuples and other non-JSON
    types are converted to JSON-compatible equivalents first.
    """
    return _redact(to_jsonable(value))
