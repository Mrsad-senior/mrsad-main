"""Coarse language identification on neutral sentences."""

from __future__ import annotations

import pytest

from mirsad.detector import detect_language


@pytest.mark.parametrize(
    "text",
    [
        "Please find attached the quarterly sales report for Najd Trading Co.",
        "The warehouse will be closed on Sunday for the annual inventory count.",
        "Thanks, see you at the 10am meeting.",
        "Invoice INV-2026-0042 is due on 30 October.",
    ],
)
def test_english(text):
    assert detect_language(text) == "en"


@pytest.mark.parametrize(
    "text",
    [
        "نرفق لكم تقرير المبيعات الربعي لشركة نجد التجارية.",
        "سيُغلق المستودع يوم الأحد لإجراء الجرد السنوي.",
        "الله يعطيك العافية، ممكن ترسل لي جدول الشحنات حق الأسبوع الجاي؟",  # Gulf dialect
        "فاتورة رقم ١٠٤٢ مستحقة الدفع في ٣٠ أكتوبر.",
    ],
)
def test_arabic(text):
    assert detect_language(text) == "ar"


def test_arabic_with_email_and_url_stays_arabic():
    text = "يرجى التواصل مع sales@najd-trading.example أو زيارة https://najd-trading.example/catalogue للمزيد."
    assert detect_language(text) == "ar"


@pytest.mark.parametrize(
    "text",
    [
        "تم تحديث الـ dashboard وإضافة تقرير الـ KPIs الجديد للـ sales team.",
        "Please review the عرض السعر attached and confirm the delivery date مع المورد.",
        "الاجتماع بكرة الساعة 10 في meeting room B، لا تنسى تجيب الـ laptop.",
    ],
)
def test_mixed_code_switching(text):
    assert detect_language(text) == "mixed"


def test_arabizi_chat_is_arabic():
    # Arabic written in Latin letters with digits for Arabic sounds ("I want to book an appointment tomorrow")
    assert detect_language("ana 3ayez a7jez maw3ed bokra 3ashan el sha7na") == "ar"


def test_short_technical_tokens_are_not_arabizi():
    assert detect_language("Our b2b portal supports e2e encryption over 4g networks.") == "en"


@pytest.mark.parametrize(
    "text",
    ["", "   \n\t", "12345 67890", "!!! ??? ...", "\u041f\u0440\u0438\u0432\u0435\u0442 \u043c\u0438\u0440, \u043a\u0430\u043a \u0434\u0435\u043b\u0430", "你好\uff0c世界"],
)
def test_other(text):
    assert detect_language(text) == "other"


def test_long_text_is_sampled_without_error():
    text = ("Quarterly shipment summary. " * 2000) + ("ملخص الشحنات الربعي. " * 10)
    assert detect_language(text) == "en"
