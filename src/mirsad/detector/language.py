"""Coarse language identification for detector reporting (en / ar / mixed / other)."""

from __future__ import annotations

import re
from typing import Literal

from mirsad import textutil

Language = Literal["en", "ar", "mixed", "other"]

#: share of Arabic letters (among Arabic + Latin) at or above which a text counts as Arabic
AR_THRESHOLD = 0.7
#: share at or below which a Latin-script text counts as English
EN_THRESHOLD = 0.3
_SAMPLE_CHARS = 20_000

# Arabizi (Arabic chat alphabet): digits standing for Arabic letters inside Latin words, e.g. "ta3limat", "7awel".
_ARABIZI_TOKEN_RE = re.compile(r"\b(?:[a-z]+[2356789][a-z]+[a-z0-9]*|[2356789][a-z]{2,}[a-z0-9]*)\b", re.IGNORECASE)
_LATIN_WORD_RE = re.compile(r"\b[a-z][a-z0-9']*\b", re.IGNORECASE)


def _strip_addresses(text: str) -> str:
    # e-mail addresses and URLs are Latin even inside Arabic text; they must not tip the balance
    return textutil.EMAIL_RE.sub(" ", textutil.URL_RE.sub(" ", text))


def _other_letters(text: str) -> int:
    count = 0
    for c in text:
        if c.isalpha():
            cp = ord(c)
            if cp < 0x250 or 0x0600 <= cp <= 0x06FF or 0x0750 <= cp <= 0x077F or 0x08A0 <= cp <= 0x08FF \
                    or 0xFB50 <= cp <= 0xFEFF:
                continue
            count += 1
    return count


def _arabizi_share(text: str) -> tuple[int, int]:
    tokens = _ARABIZI_TOKEN_RE.findall(text)
    # tokens with fewer than three letters ("b2b", "e2e", "4g") are not Arabizi
    arabizi = sum(1 for t in tokens if sum(ch.isalpha() for ch in t) >= 3)
    words = len(_LATIN_WORD_RE.findall(text))
    return arabizi, words


def detect_language(text: str) -> Language:
    """Classify ``text`` by script balance (``textutil.arabic_ratio``) with an Arabizi heuristic."""
    if not text or not text.strip():
        return "other"
    sample = text if len(text) <= _SAMPLE_CHARS else text[: _SAMPLE_CHARS // 2] + text[-_SAMPLE_CHARS // 2:]
    sample = _strip_addresses(sample)
    arabic = len(textutil.ARABIC_CHAR_RE.findall(sample))
    latin = len(textutil.LATIN_CHAR_RE.findall(sample))
    other = _other_letters(sample)
    if arabic + latin == 0 or other > arabic + latin:
        return "other"
    ratio = textutil.arabic_ratio(sample)
    if ratio >= AR_THRESHOLD:
        return "ar"
    if ratio > EN_THRESHOLD:
        return "mixed"
    arabizi, words = _arabizi_share(sample)
    if arabizi >= 2 and words:
        share = arabizi / words
        if share >= 0.3:
            return "ar"
        if share >= 0.08:
            return "mixed"
    if ratio >= 0.1 and arabic >= 8:
        return "mixed"
    return "en"
