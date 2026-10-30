"""Text helpers shared by the policy, taint and detector layers.

Keeping Arabic normalisation and value extraction in one place guarantees that
every layer sees the same canonical form of a string.
"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit

# Zero-width, bidi-control and other invisible code points used to hide or split instructions.
INVISIBLE_RE = re.compile("[\u00ad\u034f\u061c\u115f\u1160\u17b4\u17b5\u180e\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u206f\u3164\ufeff\uffa0]")
TASHKEEL_RE = re.compile("[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")
TATWEEL = "\u0640"
_ARABIC_FOLD = str.maketrans({
    "آ": "ا", "أ": "ا", "إ": "ا", "ٱ": "ا",  # alef variants -> ا
    "ى": "ي",  # alef maqsura -> ya
    "ة": "ه",  # ta marbuta -> ha
    "ؤ": "و",  # waw hamza -> waw
    "ئ": "ي",  # ya hamza -> ya
    "ک": "ك",  # keheh -> kaf
    "ی": "ي",  # farsi yeh -> ya
})
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

ARABIC_CHAR_RE = re.compile("[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\ufb50-\ufdff\ufe70-\ufeff]")
LATIN_CHAR_RE = re.compile("[A-Za-z]")

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
URL_RE = re.compile(r"\bhttps?://[^\s<>\"'()\]]+", re.IGNORECASE)
# Groups may be separated by a space, dash or dot ("SA03-8000-..." is common on invoices).
IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[-.]?\s?[A-Z0-9]{4}){3,7}(?:\s?[-.]?\s?[A-Z0-9]{1,4})?\b")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?966|00966|0)?5\d(?:[\s-]?\d){7}(?!\d)|(?<!\d)\+\d{1,3}(?:[\s-]?\d){7,12}(?!\d)")


def strip_invisible(text: str) -> tuple[str, int]:
    """Remove invisible/bidi characters; return the cleaned text and how many were removed."""
    cleaned, count = INVISIBLE_RE.subn("", text)
    return cleaned, count


def normalize_arabic(text: str) -> str:
    text = TASHKEEL_RE.sub("", text).replace(TATWEEL, "")
    return text.translate(_ARABIC_FOLD)


def fold(text: str) -> str:
    """Canonical comparison form: NFKC, no invisibles, folded Arabic, ASCII digits, lower case, single spaces."""
    text = unicodedata.normalize("NFKC", text)
    text, _ = strip_invisible(text)
    text = normalize_arabic(text).translate(_DIGITS).lower()
    return re.sub(r"\s+", " ", text).strip()


def arabic_ratio(text: str) -> float:
    ar = len(ARABIC_CHAR_RE.findall(text))
    lat = len(LATIN_CHAR_RE.findall(text))
    return ar / (ar + lat) if (ar + lat) else 0.0


def extract_domain(value: str) -> str | None:
    """Domain of an e-mail address or URL (lower case), else None."""
    value = value.strip().strip("<>\"'").lower()
    if not value:
        return None
    if "://" in value:
        host = urlsplit(value).hostname
        return host.rstrip(".") if host else None
    if "@" in value:
        domain = value.rsplit("@", 1)[1].strip().rstrip(".>")
        return domain or None
    return None


def domain_matches(domain: str, allowed: list[str]) -> bool:
    """True when ``domain`` equals or is a subdomain of an entry in ``allowed``."""
    domain = domain.lower().rstrip(".")
    for entry in allowed:
        entry = entry.lower().lstrip("*.").rstrip(".")
        if domain == entry or domain.endswith("." + entry):
            return True
    return False


def split_addresses(value: object) -> list[str]:
    """Flatten a destination argument (string, comma/semicolon list, or list) into individual values."""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        out: list[str] = []
        for item in value:
            out.extend(split_addresses(item))
        return out
    return [part.strip() for part in re.split(r"[;,\s]+", str(value)) if part.strip()]
