"""Canonical text view for injection detection (Arabic + English).

Attackers hide instructions behind zero-width characters, bidi controls,
homoglyphs, diacritics, compatibility forms, HTML entities and letter spacing.
:func:`normalize` removes those disguises and keeps an offset map from every
normalised character back to the original text, so rule hits can be
highlighted and removed exactly where they appear in the content that the
user and the model see.
"""

from __future__ import annotations

import html.entities
import re
import unicodedata
from dataclasses import dataclass, field

from mirsad import textutil

# --------------------------------------------------------------------------- signal names

SIG_ZERO_WIDTH = "zero_width_chars"
SIG_BIDI = "bidi_controls"
SIG_HOMOGLYPHS = "homoglyphs"
SIG_TASHKEEL = "tashkeel_obfuscation"
SIG_MIXED_SCRIPTS = "mixed_scripts"
SIG_BASE64 = "base64_blob"
SIG_HTML_HIDDEN = "html_hidden_text"
SIG_MD_IMAGE = "markdown_image_url"
# extra evasion signals (beyond the eight required by the spec)
SIG_ELONGATION = "arabic_elongation"
SIG_COMBINING = "combining_marks"
SIG_COMPAT = "compat_chars"
SIG_LETTER_SPACING = "letter_spacing"
SIG_HTML_ENTITIES = "html_entities"

#: signals that indicate deliberate evasion (used as a score amplifier by the rule engine)
EVASION_SIGNALS: frozenset[str] = frozenset({
    SIG_ZERO_WIDTH, SIG_BIDI, SIG_HOMOGLYPHS, SIG_MIXED_SCRIPTS, SIG_TASHKEEL, SIG_ELONGATION,
    SIG_COMBINING, SIG_COMPAT, SIG_LETTER_SPACING, SIG_HTML_ENTITIES,
})

# --------------------------------------------------------------------------- character tables

_BIDI_CONTROLS = frozenset("\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")
_BIDI_MARKS = frozenset("\u200e\u200f\u061c")  # LRM / RLM / ALM: routine in Arabic text, stripped silently
_ZWNJ, _ZWJ, _BOM = "\u200c", "\u200d", "\ufeff"
_NEWLINES = frozenset("\n\r  \x0b\x0c\x85")

# Arabic-script letters folded on top of textutil.normalize_arabic (Persian/Urdu look-alikes, dotless forms).
_ARABIC_EXTRA_FOLD = {
    "ٱ": "ا", "ڪ": "ك", "ک": "ك", "ی": "ي", "ې": "ي", "ۍ": "ي", "ێ": "ي",
    "ھ": "ه", "ہ": "ه", "ۃ": "ه", "ە": "ه", "ۀ": "ه", "ٮ": "ب", "ں": "ن", "ڡ": "ف", "ٯ": "ق",
}

# Latin-script look-alikes that are never needed for reading English/Arabic.
_LATIN_HOMOGLYPHS = {
    "ı": "i", "ȷ": "j", "ɑ": "a", "ɡ": "g", "ǀ": "l", "ɩ": "i", "ꞁ": "l", "ꜱ": "s", "ᴠ": "v",
    "ʀ": "r", "ɴ": "n", "ᴍ": "m", "ᴏ": "o", "ᴄ": "c", "ᴇ": "e", "ᴛ": "t", "ᴜ": "u", "ᴡ": "w", "ʜ": "h",
}

# Cyrillic / Greek / Armenian characters that render like Latin letters (case-aware, keyed on the original char).
_CONFUSABLES = {
    # Cyrillic upper / lower
    "А": "a", "В": "b", "С": "c", "Е": "e", "Н": "h", "І": "i", "Ј": "j", "К": "k", "М": "m", "О": "o",
    "Р": "p", "Ѕ": "s", "Т": "t", "Х": "x", "У": "y", "Ү": "y", "Ԛ": "q", "Ԝ": "w", "Ӏ": "l",
    "а": "a", "с": "c", "е": "e", "ё": "e", "һ": "h", "і": "i", "ї": "i", "ј": "j", "о": "o", "р": "p",
    "ѕ": "s", "х": "x", "у": "y", "ү": "y", "ԁ": "d", "ԛ": "q", "ԝ": "w", "ӏ": "l", "к": "k", "м": "m",
    "т": "t", "в": "b", "н": "h", "п": "n", "г": "r",
    # Greek upper / lower
    "Α": "a", "Β": "b", "Ε": "e", "Ζ": "z", "Η": "h", "Ι": "i", "Κ": "k", "Μ": "m", "Ν": "n", "Ο": "o",
    "Ρ": "p", "Τ": "t", "Υ": "y", "Χ": "x",
    "α": "a", "ι": "i", "κ": "k", "ν": "v", "ο": "o", "ρ": "p", "τ": "t", "υ": "u", "χ": "x", "γ": "y",
    "ω": "w", "ε": "e",
    # Armenian
    "օ": "o", "ս": "u", "հ": "h", "ո": "n", "ց": "g", "զ": "q",
}
# lower-cased key view: normalisation lower-cases before the word-level pass looks at confusables
_CONFUSABLES_LOWER = {k.lower(): v for k, v in _CONFUSABLES.items() if k.islower()}
for _k, _v in _CONFUSABLES.items():
    _CONFUSABLES_LOWER.setdefault(_k.lower(), _v)

_ENTITY_RE = re.compile(r"&(#[0-9]{1,7}|#[xX][0-9a-fA-F]{1,6}|[a-zA-Z][a-zA-Z0-9]{1,30});")
BASE64_RE = re.compile(r"(?<![A-Za-z0-9+/=_-])[A-Za-z0-9+/]{40,}={0,2}(?![A-Za-z0-9+/=_-])")
_HTML_HIDDEN_RE = re.compile(
    r"(?:display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0(?:\.0+)?(?:px|pt|em|rem|%)?\s*[;\"'}]"
    r"|opacity\s*:\s*0(?:\.0+)?\s*[;\"'}]|(?<![-\w])color\s*:\s*(?:#fff(?:fff)?\b|white\b|rgba?\(\s*255\s*,\s*255\s*,\s*255)"
    r"|\bhidden\s*=|aria-hidden\s*=\s*[\"']?true|<!--)"
)
_MD_IMAGE_RE = re.compile(r"!\[[^\]\n]{0,200}\]\(\s*<?https?://")
_LETTER_SPACING_RE = re.compile(
    r"(?<![^\W_])[^\W\d_](?P<sep>[ .\-_*|·•/]{1,3})(?:[^\W\d_](?P=sep)){1,}[^\W\d_](?![^\W_])"
)
_WORD_RE = re.compile(r"[^\W\d_]+")
_CYR_GREEK_RE = re.compile("[Ͱ-ϿЀ-ԯ԰-֏]")

# flag bits returned by the per-character table
_F_ZW = 1
_F_BIDI = 2
_F_BIDI_MARK = 4
_F_TASHKEEL = 8
_F_TATWEEL = 16
_F_COMBINING = 32
_F_COMPAT = 64
_F_CONFUSABLE = 128
_F_HOMOGLYPH = 256

_CHAR_CACHE: dict[str, tuple[str, int]] = {}
_CHAR_CACHE_MAX = 65_536


@dataclass(slots=True)
class NormalizedText:
    """Normalised text plus ``offsets[i]`` = index in ``original`` of normalised char ``i``."""

    text: str
    signals: list[str]
    offsets: list[int]
    original: str = field(default="", repr=False)

    def to_original(self, start: int, end: int) -> tuple[int, int]:
        """Map a normalised span ``[start, end)`` to ``[o_start, o_end)`` in the original text."""
        n = len(self.offsets)
        if n == 0:
            return 0, 0
        start = max(0, min(start, n - 1))
        end = max(start + 1, min(end, n))
        o_start = self.offsets[start]
        o_end = _unit_end(self.original, self.offsets[end - 1])
        orig = self.original
        # include marks / invisibles the normaliser dropped right after the last character
        while o_end < len(orig) and _is_droppable(orig[o_end]):
            o_end += 1
        return o_start, o_end

    def from_original(self, o_start: int, o_end: int) -> tuple[int, int]:
        """Map an original span to the smallest normalised span covering it."""
        import bisect

        start = bisect.bisect_left(self.offsets, o_start)
        end = bisect.bisect_left(self.offsets, o_end)
        return start, max(start, end)


def _unit_end(original: str, index: int) -> int:
    """End of the source unit at ``index`` (an HTML entity spans several characters)."""
    if 0 <= index < len(original) and original[index] == "&":
        m = _ENTITY_RE.match(original, index)
        if m:
            return m.end()
    return index + 1


def _is_droppable(ch: str) -> bool:
    _, flags = _char_info(ch)
    return bool(flags & (_F_TASHKEEL | _F_TATWEEL | _F_COMBINING | _F_ZW | _F_BIDI | _F_BIDI_MARK))


def _is_compat_letter(cp: int) -> bool:
    return (
        0xFF01 <= cp <= 0xFF5E  # fullwidth ASCII
        or 0x1D400 <= cp <= 0x1D7FF  # mathematical alphanumerics
        or 0x2460 <= cp <= 0x24FF  # enclosed alphanumerics
        or 0x1F130 <= cp <= 0x1F189  # squared / negative squared letters
        or 0x2100 <= cp <= 0x214F  # letterlike symbols
        or 0x1D00 <= cp <= 0x1DBF  # phonetic extensions (small caps etc.)
    )


def _char_info(ch: str) -> tuple[str, int]:
    """Normalised form and flags for one character (memoised)."""
    cached = _CHAR_CACHE.get(ch)
    if cached is not None:
        return cached
    result = _compute_char(ch)
    if len(_CHAR_CACHE) >= _CHAR_CACHE_MAX:
        _CHAR_CACHE.clear()
    _CHAR_CACHE[ch] = result
    return result


def _compute_char(ch: str) -> tuple[str, int]:
    if ch in _BIDI_CONTROLS:
        return "", _F_BIDI
    if ch in _BIDI_MARKS:
        return "", _F_BIDI_MARK
    if textutil.INVISIBLE_RE.match(ch):
        return "", _F_ZW
    if ch == textutil.TATWEEL:
        return "", _F_TATWEEL
    if textutil.TASHKEEL_RE.match(ch):
        return "", _F_TASHKEEL
    if ch in _LATIN_HOMOGLYPHS:
        return _LATIN_HOMOGLYPHS[ch], _F_HOMOGLYPH
    flags = 0
    s = unicodedata.normalize("NFKC", ch)
    if s != ch and _is_compat_letter(ord(ch)):
        flags |= _F_COMPAT
    s = s.lower()
    decomposed = unicodedata.normalize("NFD", s)
    if any(unicodedata.combining(c) for c in decomposed):
        stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
        if not stripped:
            return "", _F_COMBINING
        s = unicodedata.normalize("NFC", stripped)
    out: list[str] = []
    for c in s:
        if c.isspace():
            out.append("\n" if c in _NEWLINES else " ")
            continue
        if not c.isascii():
            digit = unicodedata.decimal(c, None)
            if digit is not None:
                out.append(str(digit))
                continue
            c = textutil.normalize_arabic(c) or ""
            c = _ARABIC_EXTRA_FOLD.get(c, c)
        out.append(c)
    if ch in _CONFUSABLES:
        flags |= _F_CONFUSABLE
    return "".join(out), flags


def fold_arabic_chars(pattern: str) -> str:
    """Apply the per-character Arabic folding to a regex pattern / keyword, leaving ASCII untouched."""
    out: list[str] = []
    for ch in pattern:
        cp = ord(ch)
        if 0x0600 <= cp <= 0x06FF or 0x0750 <= cp <= 0x077F or 0x08A0 <= cp <= 0x08FF or 0xFB50 <= cp <= 0xFEFC:
            out.append(_char_info(ch)[0])
        else:
            out.append(ch)
    return "".join(out)


def _decode_units(text: str) -> tuple[list[tuple[int, str]] | None, int]:
    """Decode HTML entities into (orig_index, char) units; returns (None, 0) when there is nothing to decode."""
    if "&" not in text or ";" not in text:
        return None, 0
    units: list[tuple[int, str]] = []
    pos = 0
    letters = 0
    for m in _ENTITY_RE.finditer(text):
        name = m.group(1)
        if name[0] == "#":
            try:
                cp = int(name[2:], 16) if name[1] in "xX" else int(name[1:])
                decoded = chr(cp) if 0 < cp <= 0x10FFFF else None
            except ValueError:
                decoded = None
            if decoded and decoded.isalpha():
                letters += 1
        else:
            cp_named = html.entities.name2codepoint.get(name)
            decoded = chr(cp_named) if cp_named is not None else None
        if decoded is None:
            continue
        units.extend((i, text[i]) for i in range(pos, m.start()))
        units.append((m.start(), decoded))
        pos = m.end()
    if pos == 0:
        return None, 0
    units.extend((i, text[i]) for i in range(pos, len(text)))
    return units, letters


def normalize(text: str) -> NormalizedText:
    """NFKC, strip zero-width/bidi controls, fold Arabic & homoglyphs, ASCII digits, lower case.

    Whitespace runs collapse to one space (or one newline if the run contained one), so line-anchored
    rules keep working. ``offsets`` maps each normalised character to its index in ``text``.
    """
    if not text:
        return NormalizedText("", [], [], text or "")
    units, entity_letters = _decode_units(text)
    iterable = units if units is not None else enumerate(text)

    out: list[str] = []
    offs: list[int] = []
    zw = bidi = tatweel = combining = compat = confusable = homoglyph = 0
    tashkeel_odd = 0
    mark_run = 0
    last_mark = ""
    prev_base_arabic = False
    n = len(text)
    for idx, ch in iterable:
        s, flags = _char_info(ch)
        if flags:
            if flags & _F_TASHKEEL:
                mark_run += 1
                if mark_run >= 3 or ch == last_mark or not prev_base_arabic:
                    tashkeel_odd += 1
                last_mark = ch
                continue
            if flags & _F_ZW:
                if ch == _BOM and idx == 0:
                    pass
                elif ch == _ZWNJ and (_arabic_neighbour(text, idx)):
                    pass  # Persian/Urdu orthography uses ZWNJ legitimately
                elif ch == _ZWJ and _emoji_neighbour(text, idx, n):
                    pass
                else:
                    zw += 1
                continue
            if flags & _F_BIDI:
                bidi += 1
                continue
            if flags & (_F_BIDI_MARK | _F_TATWEEL | _F_COMBINING):
                if flags & _F_TATWEEL:
                    tatweel += 1
                elif flags & _F_COMBINING:
                    combining += 1
                continue
            if flags & _F_COMPAT:
                compat += 1
            if flags & _F_CONFUSABLE:
                confusable += 1
            if flags & _F_HOMOGLYPH:
                homoglyph += 1
        if not s:
            continue
        mark_run = 0
        last_mark = ""
        prev_base_arabic = "؀" <= s[-1] <= "ۿ"
        if len(s) == 1:
            out.append(s)
            offs.append(idx)
        else:
            out.extend(s)
            offs.extend([idx] * len(s))

    signals: set[str] = set()
    if zw:
        signals.add(SIG_ZERO_WIDTH)
    if bidi:
        signals.add(SIG_BIDI)
    if tashkeel_odd:
        signals.add(SIG_TASHKEEL)
    if tatweel >= 3:
        signals.add(SIG_ELONGATION)
    if combining >= 3:
        signals.add(SIG_COMBINING)
    if compat >= 3:
        signals.add(SIG_COMPAT)
    if homoglyph:
        signals.add(SIG_HOMOGLYPHS)
    if entity_letters >= 3:
        signals.add(SIG_HTML_ENTITIES)
    if confusable:
        _fold_confusables(out, offs, text, signals)

    joined = "".join(out)
    if " " in joined or "." in joined or "-" in joined or "_" in joined or "*" in joined:
        joined, offs = _collapse_letter_spacing(joined, offs, signals)
    joined, offs = _collapse_whitespace(joined, offs)

    if len(text) >= 40 and BASE64_RE.search(text) and _looks_base64(text):
        signals.add(SIG_BASE64)
    if ("<" in joined or "style" in joined or "hidden" in joined) and _HTML_HIDDEN_RE.search(joined):
        signals.add(SIG_HTML_HIDDEN)
    if "![" in joined and _MD_IMAGE_RE.search(joined):
        signals.add(SIG_MD_IMAGE)
    return NormalizedText(joined, sorted(signals), offs, text)


def _arabic_neighbour(text: str, idx: int) -> bool:
    before = text[idx - 1] if idx > 0 else ""
    after = text[idx + 1] if idx + 1 < len(text) else ""
    return any("؀" <= c <= "ۿ" for c in (before, after) if c)


def _emoji_neighbour(text: str, idx: int, n: int) -> bool:
    for j in (idx - 1, idx + 1):
        if 0 <= j < n:
            c = text[j]
            if ord(c) >= 0x2600 and unicodedata.category(c) in ("So", "Sk", "Mn", "Cf") or "︀" <= c <= "️":
                return True
    return False


def _looks_base64(text: str) -> bool:
    for m in BASE64_RE.finditer(text):
        blob = m.group(0)
        if any(c.isupper() for c in blob) and any(c.islower() for c in blob) and any(c.isdigit() for c in blob):
            return True
    return False


def _fold_confusables(out: list[str], offs: list[int], original: str, signals: set[str]) -> None:
    """Fold Cyrillic/Greek/Armenian look-alikes inside Latin words (1:1, offsets unchanged)."""
    joined = "".join(out)
    latin_letters = sum(1 for c in joined if "a" <= c <= "z")
    foreign_letters = len(_CYR_GREEK_RE.findall(joined))
    latin_dominant = latin_letters > foreign_letters
    folded_any = mixed_any = False
    for m in _WORD_RE.finditer(joined):
        word = m.group(0)
        has_latin = any("a" <= c <= "z" for c in word)
        conf_positions = [i for i, c in enumerate(word) if c in _CONFUSABLES_LOWER]
        if not conf_positions:
            continue
        all_confusable = len(conf_positions) == len(word)
        if not (has_latin or (all_confusable and latin_dominant)):
            continue
        for i in conf_positions:
            k = m.start() + i
            orig_char = original[offs[k]] if offs[k] < len(original) else out[k]
            out[k] = _CONFUSABLES.get(orig_char) or _CONFUSABLES_LOWER[out[k]]
        folded_any = True
        mixed_any = mixed_any or has_latin
    if folded_any:
        signals.add(SIG_HOMOGLYPHS)
    if mixed_any:
        signals.add(SIG_MIXED_SCRIPTS)


def _collapse_letter_spacing(joined: str, offs: list[int], signals: set[str]) -> tuple[str, list[int]]:
    """Join letter-spaced words ("i g n o r e", "ت ج ا ه ل") so word rules can see them."""
    if not _LETTER_SPACING_RE.search(joined):
        return joined, offs
    keep = [True] * len(joined)
    long_run = False
    for m in _LETTER_SPACING_RE.finditer(joined):
        run = m.group(0)
        letters = sum(1 for c in run if c.isalpha())
        if letters >= 5:
            long_run = True
        for i in range(m.start(), m.end()):
            if not joined[i].isalpha():
                keep[i] = False
    if long_run:
        signals.add(SIG_LETTER_SPACING)
    chars = [c for c, k in zip(joined, keep, strict=True) if k]
    new_offs = [o for o, k in zip(offs, keep, strict=True) if k]
    return "".join(chars), new_offs


def _collapse_whitespace(joined: str, offs: list[int]) -> tuple[str, list[int]]:
    """Collapse whitespace runs (newline wins) and trim both ends."""
    out: list[str] = []
    new_offs: list[int] = []
    pending: str | None = None
    pending_off = 0
    for c, o in zip(joined, offs, strict=True):
        if c == " " or c == "\n":
            if pending is None:
                pending, pending_off = c, o
            elif c == "\n":
                pending = "\n"
            continue
        if pending is not None:
            if out:
                out.append(pending)
                new_offs.append(pending_off)
            pending = None
        out.append(c)
        new_offs.append(o)
    return "".join(out), new_offs
