"""Normalisation: invisible/bidi characters, Arabic folding, homoglyphs, digits, and the offset map."""

from __future__ import annotations

import base64

import pytest

from mirsad.detector import normalize
from mirsad.detector.normalize import (
    SIG_BASE64,
    SIG_BIDI,
    SIG_COMPAT,
    SIG_ELONGATION,
    SIG_HOMOGLYPHS,
    SIG_HTML_HIDDEN,
    SIG_LETTER_SPACING,
    SIG_MD_IMAGE,
    SIG_MIXED_SCRIPTS,
    SIG_TASHKEEL,
    SIG_ZERO_WIDTH,
    fold_arabic_chars,
)

ZWSP, ZWNJ, ZWJ, WJ, BOM = "\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"
LRM, RLM, ALM = "\u200e", "\u200f", "\u061c"
RLO, PDF, LRI, PDI = "\u202e", "\u202c", "\u2066", "\u2069"


def assert_offsets_valid(original: str, norm) -> None:
    assert len(norm.offsets) == len(norm.text)
    assert all(0 <= o < len(original) for o in norm.offsets)
    assert norm.offsets == sorted(norm.offsets), "offsets must be non-decreasing"


# --------------------------------------------------------------------------- basics


def test_empty_and_plain_ascii():
    empty = normalize("")
    assert (empty.text, empty.signals, empty.offsets) == ("", [], [])
    n = normalize("Quarterly Report")
    assert n.text == "quarterly report"
    assert n.offsets == list(range(len("Quarterly Report")))
    assert n.signals == []
    assert n.original == "Quarterly Report"


def test_whitespace_runs_collapse_and_newline_wins():
    n = normalize("  Invoice \t total\n\n  due   Monday  ")
    assert n.text == "invoice total\ndue monday"
    assert_offsets_valid("  Invoice \t total\n\n  due   Monday  ", n)


def test_nfkc_ligature_expands_with_repeated_offset():
    n = normalize("e\ufb01le")  # "e\ufb01le": the fi ligature becomes two characters
    assert n.text == "efile"
    assert n.offsets == [0, 1, 1, 2, 3]


# --------------------------------------------------------------------------- invisible & bidi characters


@pytest.mark.parametrize("ch", [ZWSP, ZWJ, WJ])
def test_zero_width_characters_are_removed_and_signalled(ch):
    original = f"ship{ch}ment re{ch}port"
    n = normalize(original)
    assert n.text == "shipment report"
    assert SIG_ZERO_WIDTH in n.signals
    assert_offsets_valid(original, n)
    # every kept character maps back to the identical (lower-cased) character in the original
    assert all(original[o].lower() == c for c, o in zip(n.text, n.offsets, strict=True))


def test_leading_bom_and_arabic_zwnj_are_not_evasion():
    assert normalize(f"{BOM}Monthly summary").signals == []
    persian = f"م\u06cc{ZWNJ}خواهم"  # Persian orthography uses ZWNJ between letters
    n = normalize(persian)
    assert ZWNJ not in n.text
    assert SIG_ZERO_WIDTH not in n.signals


def test_bidi_controls_are_removed_and_signalled():
    original = f"order {RLO}2024{PDF} and {LRI}notes{PDI}"
    n = normalize(original)
    assert n.text == "order 2024 and notes"
    assert SIG_BIDI in n.signals
    assert_offsets_valid(original, n)


@pytest.mark.parametrize("mark", [LRM, RLM, ALM])
def test_directional_marks_are_stripped_silently(mark):
    n = normalize(f"فاتورة{mark} رقم 5")
    assert mark not in n.text
    assert SIG_BIDI not in n.signals


# --------------------------------------------------------------------------- Arabic


def test_tashkeel_removed_without_signal_for_ordinary_vocalisation():
    original = "مَرْحَبًا بِكُمْ"
    n = normalize(original)
    assert n.text == "مرحبا بكم"
    assert SIG_TASHKEEL not in n.signals
    assert_offsets_valid(original, n)
    assert n.offsets == [0, 2, 4, 6, 8, 9, 10, 12, 14]


def test_stacked_diacritics_raise_tashkeel_signal():
    n = normalize("تَََقرير")  # three identical marks on one letter
    assert n.text == "تقرير"
    assert SIG_TASHKEEL in n.signals


def test_tatweel_removed_and_long_runs_signalled():
    short = normalize("شـركة")
    assert short.text == "شركه"
    assert SIG_ELONGATION not in short.signals
    long = normalize("شـــركة")
    assert long.text == "شركه"
    assert SIG_ELONGATION in long.signals
    assert long.offsets == [0, 4, 5, 6]


@pytest.mark.parametrize(
    ("original", "expected"),
    [
        ("إدارة", "اداره"),  # hamza-below alef, ta marbuta
        ("أحمد", "احمد"),  # hamza-above alef
        ("آمال", "امال"),  # madda alef
        ("ٱلكتاب", "الكتاب"),  # wasla alef
        ("مستشفى", "مستشفي"),  # alef maqsura -> ya
        ("مسؤول", "مسوول"),  # waw with hamza
        ("رئيس", "رييس"),  # ya with hamza
        ("\u06a9", "ك"),  # Persian keheh -> kaf
        ("\u06cc", "ي"),  # Farsi yeh -> ya
    ],
)
def test_arabic_letter_variants_fold(original, expected):
    n = normalize(original)
    assert n.text == expected
    assert len(n.offsets) == len(n.text)


def test_fold_arabic_chars_leaves_ascii_and_regex_syntax_untouched():
    assert fold_arabic_chars(r"(?:إدارة|\d+)\s+abc") == r"(?:اداره|\d+)\s+abc"


# --------------------------------------------------------------------------- homoglyphs & compatibility forms


def test_cyrillic_lookalikes_inside_latin_word_are_folded():
    original = "inv\u043eice t\u043et\u0430l"  # Cyrillic o and a inside Latin words
    n = normalize(original)
    assert n.text == "invoice total"
    assert SIG_HOMOGLYPHS in n.signals
    assert SIG_MIXED_SCRIPTS in n.signals
    assert n.offsets == list(range(len(original)))


def test_uppercase_cyrillic_lookalike_is_folded():
    n = normalize("\u0405tatus report")  # Cyrillic DZE looks like S
    assert n.text == "status report"
    assert SIG_HOMOGLYPHS in n.signals


def test_genuine_cyrillic_text_is_not_folded():
    # Russian "hello world": no Latin letters around, so nothing is folded
    n = normalize("\u041f\u0440\u0438\u0432\u0435\u0442 \u043c\u0438\u0440")
    assert n.text == "\u043f\u0440\u0438\u0432\u0435\u0442 \u043c\u0438\u0440"
    assert SIG_HOMOGLYPHS not in n.signals
    assert SIG_MIXED_SCRIPTS not in n.signals


def test_latin_homoglyph_dotless_i():
    n = normalize("pr\u0131ce l\u0131st")
    assert n.text == "price list"
    assert SIG_HOMOGLYPHS in n.signals


def test_fullwidth_letters_fold_with_compat_signal():
    n = normalize("\uff32\uff25\uff30\uff2f\uff32\uff34")  # fullwidth REPORT
    assert n.text == "report"
    assert SIG_COMPAT in n.signals


def test_latin_accents_are_stripped():
    assert normalize("Café résumé naïve").text == "cafe resume naive"
    assert normalize("cafe\u0301").text == "cafe"  # decomposed combining acute


# --------------------------------------------------------------------------- digits


@pytest.mark.parametrize(
    ("original", "expected"),
    [
        ("٠١٢٣٤٥٦٧٨٩", "0123456789"),  # Arabic-Indic
        ("۰۱۲۳۴۵۶۷۸۹", "0123456789"),  # Extended Arabic-Indic (Persian/Urdu)
        ("\uff11\uff12\uff13", "123"),  # fullwidth
        ("رقم الطلب ١٠٤٢", "رقم الطلب 1042"),
    ],
)
def test_digits_fold_to_ascii(original, expected):
    n = normalize(original)
    assert n.text == expected
    assert len(n.offsets) == len(n.text)


# --------------------------------------------------------------------------- structural signals (neutral content)


def test_html_entities_decode_and_map_to_whole_entity():
    original = "Report &amp; invoice"
    n = normalize(original)
    assert n.text == "report & invoice"
    i = n.text.index("&")
    assert n.to_original(i, i + 1) == (7, 12)
    assert original[7:12] == "&amp;"


def test_letter_spacing_is_collapsed_and_signalled():
    n = normalize("the r e p o r t is ready")
    assert "report" in n.text
    assert SIG_LETTER_SPACING in n.signals


def test_base64_blob_signal():
    blob = base64.b64encode(b"Quarterly shipment summary for the main warehouse, all pallets counted.").decode()
    n = normalize(f"Attachment: {blob}")
    assert SIG_BASE64 in n.signals


def test_hidden_html_and_markdown_image_signals():
    assert SIG_HTML_HIDDEN in normalize('<span style="display:none">note</span>').signals
    assert SIG_MD_IMAGE in normalize("![logo](https://najd-trading.example/logo.png)").signals


def test_signals_are_sorted_and_unique():
    n = normalize(f"inv\u043eice{ZWSP} {RLO}x{PDF}")
    assert n.signals == sorted(set(n.signals))


# --------------------------------------------------------------------------- offset map round trips


@pytest.mark.parametrize(
    "original",
    [
        "Please review the CONTRACT before Monday.",
        f"Please re{ZWSP}view the con{ZWJ}tract before Monday.",
        "يرجى مُراجَعة العَقد قبل يوم الاثنين",
        "يرجى مراجعـــة العقد قبل يوم الاثنين",
        f"Ple\u0430se {RLO}review{PDF} the contract",
        "Total: ١٢٣ SAR &amp; VAT",
    ],
)
def test_to_original_round_trip(original):
    n = normalize(original)
    assert_offsets_valid(original, n)
    for word in n.text.split(" "):
        start = n.text.index(word)
        a, b = n.to_original(start, start + len(word))
        assert 0 <= a < b <= len(original)
        # the original slice normalises back to exactly the normalised word
        assert normalize(original[a:b]).text == word


def test_to_original_includes_trailing_marks():
    original = "كتبَ الطالبُ"
    n = normalize(original)
    first = n.text.split(" ")[0]
    a, b = n.to_original(0, len(first))
    assert original[a:b] == "كتبَ"


def test_from_original_maps_back_to_normalised_span():
    original = f"Order {ZWSP}1042 shipped"
    n = normalize(original)
    o_start = original.index("1042")
    start, end = n.from_original(o_start, o_start + 4)
    assert n.text[start:end] == "1042"


def test_to_original_clamps_out_of_range():
    n = normalize("abc")
    assert n.to_original(-5, 99) == (0, 3)
    assert normalize("").to_original(0, 1) == (0, 0)
