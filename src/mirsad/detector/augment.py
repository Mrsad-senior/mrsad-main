"""Training-set augmentation: carrier embedding and obfuscation variants (train split only)."""

from __future__ import annotations

import random
import re

ZERO_WIDTH_CHARS = ("\u200b", "\u200c", "\u200d", "\u2060")
LATIN_TO_CYRILLIC = {"a": "а", "e": "е", "o": "о", "p": "р", "c": "с", "x": "х", "i": "і", "y": "у",
                     "A": "А", "E": "Е", "O": "О", "P": "Р", "C": "С", "X": "Х", "I": "І"}
ARABIC_LOOKALIKES = {"ي": "ی", "ك": "ک", "ه": "ھ"}
HARAKAT = ("َ", "ُ", "ِ", "ْ", "ّ", "ً")
TATWEEL = "ـ"
# Arabic letters that never join to the following letter: no tatweel after them
_NON_JOINING = set("اأإآدذرزوؤءة")
_ARABIC_LETTER_RE = re.compile("[ء-ي]")
_WORD_RE = re.compile(r"\S{5,}")
_SENTENCE_END_RE = re.compile(r"(?<=[.!?؟])\s+|\n+")

OBFUSCATIONS_BY_LANG = {
    "en": ("zero_width", "homoglyphs", "spacing_noise"),
    "ar": ("zero_width", "homoglyphs", "tashkeel", "spacing_noise", "elongation"),
    "mixed": ("zero_width", "homoglyphs", "tashkeel", "spacing_noise", "elongation"),
}


def embed_in_carrier(payload: str, carrier: str, position: str, rng: random.Random) -> str:
    """Insert ``payload`` at the start, middle (sentence boundary) or end of a benign ``carrier``."""
    payload = payload.strip()
    carrier = carrier.strip()
    if position == "start":
        return f"{payload}\n\n{carrier}"
    if position == "end":
        return f"{carrier}\n\n{payload}"
    if position != "middle":
        raise ValueError(f"unknown position {position!r}")
    cuts = [m.end() for m in _SENTENCE_END_RE.finditer(carrier)]
    cuts = [c for c in cuts if 0 < c < len(carrier)]
    if cuts:
        mid = len(carrier) / 2
        cut = min(cuts, key=lambda c: abs(c - mid))
    else:
        space = carrier.find(" ", len(carrier) // 2)
        cut = space if space > 0 else len(carrier) // 2
    return f"{carrier[:cut].rstrip()} {payload} {carrier[cut:].lstrip()}"


def zero_width(text: str, rng: random.Random, rate: float = 0.25) -> str:
    out: list[str] = []
    for i, ch in enumerate(text):
        out.append(ch)
        if ch.isalpha() and i + 1 < len(text) and text[i + 1].isalpha() and rng.random() < rate:
            out.append(rng.choice(ZERO_WIDTH_CHARS))
    return "".join(out)


def homoglyphs(text: str, rng: random.Random, rate: float = 0.35) -> str:
    out: list[str] = []
    for ch in text:
        repl = LATIN_TO_CYRILLIC.get(ch) or ARABIC_LOOKALIKES.get(ch)
        out.append(repl if repl and rng.random() < rate else ch)
    return "".join(out)


def tashkeel(text: str, rng: random.Random, rate: float = 0.6) -> str:
    out: list[str] = []
    for ch in text:
        out.append(ch)
        if _ARABIC_LETTER_RE.match(ch) and rng.random() < rate:
            out.append(rng.choice(HARAKAT))
            if rng.random() < 0.15:  # stacked marks, a typical obfuscation pattern
                out.append(rng.choice(HARAKAT))
    return "".join(out)


def elongation(text: str, rng: random.Random, rate: float = 0.3) -> str:
    out: list[str] = []
    for i, ch in enumerate(text):
        out.append(ch)
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if (_ARABIC_LETTER_RE.match(ch) and ch not in _NON_JOINING and nxt and _ARABIC_LETTER_RE.match(nxt)
                and rng.random() < rate):
            out.append(TATWEEL * rng.randint(1, 4))
    return "".join(out)


def spacing_noise(text: str, rng: random.Random, max_words: int = 3) -> str:
    """Letter-space some long words ("i g n o r e") or split them once ("instru ctions")."""
    words = list(_WORD_RE.finditer(text))
    if not words:
        return text
    chosen = sorted(rng.sample(words, k=min(max_words, len(words))), key=lambda m: m.start())
    out: list[str] = []
    pos = 0
    for m in chosen:
        out.append(text[pos:m.start()])
        word = m.group(0)
        if rng.random() < 0.5:
            out.append(" ".join(word))
        else:
            cut = rng.randint(2, len(word) - 2)
            out.append(word[:cut] + " " + word[cut:])
        pos = m.end()
    out.append(text[pos:])
    return "".join(out)


OBFUSCATORS = {
    "zero_width": zero_width,
    "homoglyphs": homoglyphs,
    "tashkeel": tashkeel,
    "spacing_noise": spacing_noise,
    "elongation": elongation,
}


def obfuscate(text: str, kind: str, rng: random.Random) -> str:
    try:
        fn = OBFUSCATORS[kind]
    except KeyError as exc:
        raise ValueError(f"unknown obfuscation {kind!r}") from exc
    return fn(text, rng)
