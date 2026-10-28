"""InjectionDetector: rules-only fallback, benign texts, structured scanning, labels and latency.

No adversarial text is used: positive detections come from a stub rule that matches the neutral
placeholder token (see ``conftest.placeholder_rules``).
"""

from __future__ import annotations

import json
import logging
import statistics
import time
from pathlib import Path

import numpy as np
import pytest
from pydantic import BaseModel

import mirsad.detector.detector as detector_module
from mirsad.detector import InjectionDetector, Rule, RuleSet, load_model
from mirsad.detector.detector import dump_with_positions
from mirsad.detector.model import COEF_FILE, INTERCEPT_FILE, META_FILE
from mirsad.models import DetectionResult

from .neutral_data import PLACEHOLDER

BENIGN_EN = [
    "Dear team, please find attached the quarterly sales report for Najd Trading Co. Revenue grew 12% "
    "compared with last quarter.",
    "Please forward the signed contract to the legal department before Thursday so we can finalise the "
    "supplier agreement.",
    "Reminder: the warehouse in Dammam will be closed on Sunday for inventory. Shipments resume on Monday.",
    "Hi Sara, could you update the customer note for account C017 with the new delivery address and call "
    "them to confirm?",
    "Invoice INV-2026-0042 for 15,400 SAR is due on 30 October. Payment can be made by bank transfer to the "
    "account on file.",
    "Meeting notes: we agreed to review the pricing model, send the revised quote to the client and schedule "
    "a follow-up next week.",
    "Thank you for your order. Your package of Ajwa dates has been dispatched and should arrive within three "
    "business days.",
    "To reset the office printer, hold the power button for ten seconds, then select the default tray in the "
    "settings menu.",
    "The board approved the new travel policy. Employees must submit expense claims within 30 days with "
    "original receipts.",
    "Customer feedback: the delivery was late but the support agent was very helpful and resolved the issue.",
]
BENIGN_AR = [
    "السادة فريق المبيعات، نرفق لكم تقرير المبيعات الربعي لشركة نجد التجارية. ارتفعت الإيرادات بنسبة ١٢٪.",
    "يرجى إرسال العقد الموقّع إلى الإدارة القانونية قبل يوم الخميس لإتمام اتفاقية المورّد.",
    "تذكير: سيُغلق المستودع في الدمام يوم الأحد لإجراء الجرد، وتُستأنف الشحنات صباح الاثنين.",
    "مرحباً سارة، هل يمكنك تحديث ملاحظة العميل للحساب C017 بعنوان التسليم الجديد والاتصال به للتأكيد؟",
    "فاتورة رقم INV-2026-0042 بمبلغ ١٥٤٠٠ ريال مستحقة في ٣٠ أكتوبر، ويمكن السداد بالتحويل البنكي.",
    "محضر الاجتماع: اتفقنا على مراجعة نموذج التسعير وإرسال العرض المعدّل للعميل وتحديد موعد للمتابعة.",
    "شكراً لطلبك. تم شحن طلبك من تمور العجوة ومن المتوقع وصوله خلال ثلاثة أيام عمل.",
    "وافق مجلس الإدارة على سياسة السفر الجديدة، ويجب تقديم مطالبات المصروفات خلال ٣٠ يوماً مع الإيصالات.",
    "ملاحظات العميل: تأخر التوصيل لكن موظف الدعم كان متعاوناً جداً وحل المشكلة بسرعة.",
    "الله يعطيك العافية، ممكن ترسل لي جدول الشحنات حق الأسبوع الجاي؟ نبي نرتب مع المورد.",
]
BENIGN_MIXED = [
    "تم تحديث الـ dashboard وإضافة تقرير الـ KPIs الجديد للـ sales team.",
    "Please review the عرض السعر attached and confirm the delivery date مع المورد.",
]


# --------------------------------------------------------------------------- construction & fallback


def test_default_falls_back_to_rules_only_when_model_dir_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(detector_module, "DEFAULT_MODEL_DIR", tmp_path)
    det = InjectionDetector.default()
    assert det.mode == "rules_only"
    assert det.model is None
    assert len(det.rules) > 0
    info = det.info()
    assert info["mode"] == "rules_only"
    assert info["training"] == {}
    result = det.scan("Quarterly report attached.")
    assert isinstance(result, DetectionResult)
    assert result.model_score == 0.0


def test_default_with_packaged_directory_works_either_way():
    det = InjectionDetector.default()
    assert det.mode in ("rules_only", "ensemble")
    assert det.model_dir == detector_module.DEFAULT_MODEL_DIR
    assert det.scan(BENIGN_EN[0]).label == "benign"


def test_missing_model_dir_means_rules_only(tmp_path):
    det = InjectionDetector(tmp_path / "does-not-exist")
    assert det.mode == "rules_only"
    assert load_model(tmp_path / "does-not-exist") is None


@pytest.mark.parametrize("broken", ["bad_json", "wrong_shape", "pickled_object", "non_finite"])
def test_invalid_model_files_fall_back_to_rules_only(tmp_path, broken, caplog):
    (tmp_path / META_FILE).write_text("{}", encoding="utf-8")
    coef = np.zeros(2**20 + 2**18, dtype=np.float32)
    np.save(tmp_path / INTERCEPT_FILE, np.asarray([0.0]))
    if broken == "bad_json":
        (tmp_path / META_FILE).write_text("{not json", encoding="utf-8")
        np.save(tmp_path / COEF_FILE, coef)
    elif broken == "wrong_shape":
        np.save(tmp_path / COEF_FILE, np.zeros(10, dtype=np.float32))
    elif broken == "pickled_object":
        np.save(tmp_path / COEF_FILE, np.array([{"a": 1}], dtype=object), allow_pickle=True)
    else:
        coef[3] = np.inf
        np.save(tmp_path / COEF_FILE, coef)
    with caplog.at_level(logging.WARNING, logger="mirsad.detector"):
        det = InjectionDetector(tmp_path)
    assert det.mode == "rules_only"
    assert any("invalid" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize(("window", "stride"), [(40, 40), (600, 20), (300, 600)])
def test_invalid_window_parameters(window, stride):
    with pytest.raises(ValueError):
        InjectionDetector(None, window_chars=window, stride_chars=stride)


def test_version_fingerprint(placeholder_rules):
    a = InjectionDetector(None)
    b = InjectionDetector(None)
    stub = InjectionDetector(None, rules=placeholder_rules)
    assert a.version == b.version
    assert a.version.startswith("rules-") and "+model-" not in a.version
    assert stub.version != a.version
    assert a.info()["version"] == a.version


# --------------------------------------------------------------------------- benign content


@pytest.mark.parametrize("text", BENIGN_EN)
def test_benign_english_business_text_is_below_flag_threshold(rules_detector, text):
    r = rules_detector.scan(text)
    assert r.score < 0.5
    assert r.label == "benign"
    assert r.language == "en"


@pytest.mark.parametrize("text", BENIGN_AR)
def test_benign_arabic_business_text_is_below_flag_threshold(rules_detector, text):
    r = rules_detector.scan(text)
    assert r.score < 0.5
    assert r.label == "benign"
    assert r.language == "ar"


@pytest.mark.parametrize("text", BENIGN_MIXED)
def test_benign_mixed_text_is_below_flag_threshold(rules_detector, text):
    r = rules_detector.scan(text)
    assert r.score < 0.5
    assert r.language == "mixed"


def test_benign_texts_also_pass_with_a_trained_model(model_detector):
    assert model_detector.mode == "ensemble"
    for text in BENIGN_EN + BENIGN_AR:
        assert model_detector.scan(text).score < 0.5, text


def test_empty_and_non_string_input(rules_detector):
    for value in ("", None):
        r = rules_detector.scan(value)  # type: ignore[arg-type]
        assert r.score == 0.0 and r.label == "benign" and r.language == "other" and r.spans == []
    assert rules_detector.scan(12345).language == "other"  # type: ignore[arg-type]


def test_result_fields_and_latency(rules_detector):
    r = rules_detector.scan(BENIGN_EN[0])
    assert 0.0 <= r.score <= 1.0
    assert r.latency_ms > 0.0
    assert r.rule_score == 0.0
    DetectionResult.model_validate(r.model_dump())


# --------------------------------------------------------------------------- labels via stub rules


@pytest.mark.parametrize(("weight", "label"), [(0.3, "benign"), (0.6, "suspicious"), (0.9, "injection")])
def test_labels_follow_thresholds(weight, label):
    rule = Rule(id="test.weighted", category="goal_hijack", weight=weight, description="test stub",
                pattern="sample-flagged-text", examples=(PLACEHOLDER,))
    det = InjectionDetector(None, rules=RuleSet([rule]))
    r = det.scan(f"Status line: {PLACEHOLDER} end.")
    assert r.score == pytest.approx(weight)
    assert r.label == label


def test_spans_point_into_the_original_text(placeholder_detector):
    text = f"Order 1042 shipped. Note: {PLACEHOLDER} here.\nSecond line {PLACEHOLDER.lower()}."
    r = placeholder_detector.scan(text)
    assert r.label == "injection"
    assert len(r.spans) == 2
    for span in r.spans:
        assert text[span.start:span.end] == span.text
        assert span.text.lower() == PLACEHOLDER.lower()
        assert span.rule_id == "test.placeholder"


def test_spans_survive_invisible_characters(placeholder_detector):
    hidden = "SAMPLE-\u200bFLAGGED-\u202eTEXT"
    text = f"Header. {hidden} footer."
    r = placeholder_detector.scan(text)
    assert r.label == "injection"
    span = r.spans[0]
    assert text[span.start:span.end] == hidden
    assert "zero_width_chars" in r.signals and "bidi_controls" in r.signals
    # evasion signals amplify a real hit
    assert r.rule_score > 0.9


def test_scan_many_matches_scan(placeholder_detector):
    texts = [BENIGN_EN[0], f"x {PLACEHOLDER} y", BENIGN_AR[0]]
    batch = placeholder_detector.scan_many(texts)
    single = [placeholder_detector.scan(t) for t in texts]
    assert [b.score for b in batch] == [s.score for s in single]
    assert [b.language for b in batch] == [s.language for s in single]
    assert placeholder_detector.scan_many([]) == []


# --------------------------------------------------------------------------- structured values


def test_scan_structured_nested_json_spans_refer_to_dump(placeholder_detector):
    value = {
        "emails": [
            {"id": "E1", "subject": "Quarterly report", "body": "Line one\nwith \"quotes\" and "
             f"{PLACEHOLDER} inside.", "flags": [True, None, 3.5]},
            {"id": "E2", "subject": "تقرير المبيعات", "body": "لا شيء هنا"},
        ],
        "count": 2,
        PLACEHOLDER: "keys are scanned too",
    }
    r = placeholder_detector.scan_structured(value)
    dump = json.dumps(value, ensure_ascii=False)
    assert r.label == "injection"
    assert len(r.spans) == 2
    assert [dump[s.start:s.end] for s in r.spans] == [PLACEHOLDER, PLACEHOLDER]
    assert r.spans == sorted(r.spans, key=lambda s: (s.start, s.end))
    assert r.language in ("en", "mixed")


def test_scan_structured_maps_through_json_escapes(placeholder_detector):
    value = {"note": "tab\there \\ backslash \u2028 sep é " + PLACEHOLDER}
    r = placeholder_detector.scan_structured(value)
    dump = json.dumps(value, ensure_ascii=False)
    assert dump[r.spans[0].start:r.spans[0].end] == PLACEHOLDER


def test_scan_structured_benign_and_degenerate_values(rules_detector, placeholder_detector):
    benign = {"customers": [{"name": "Najd Trading", "city": "Riyadh", "notes": BENIGN_EN[1]},
                            {"name": "شركة نجد", "city": "الرياض", "notes": BENIGN_AR[1]}]}
    r = rules_detector.scan_structured(benign)
    assert r.score < 0.5 and r.label == "benign"
    empty = placeholder_detector.scan_structured({})
    assert empty.score == 0.0 and empty.language == "other" and empty.spans == []
    numbers = placeholder_detector.scan_structured([1, 2.5, True, None])
    assert numbers.score == 0.0
    # a plain string is scanned as text
    assert placeholder_detector.scan_structured(f"a {PLACEHOLDER}").label == "injection"


def test_scan_structured_handles_models_tuples_and_deep_nesting(placeholder_detector):
    class Item(BaseModel):
        title: str
        body: str

    value = {"items": (Item(title="Report", body=f"x {PLACEHOLDER}"),)}
    assert placeholder_detector.scan_structured(value).label == "injection"
    deep: object = "leaf"
    for _ in range(80):
        deep = [deep]
    assert placeholder_detector.scan_structured(deep).score == 0.0


@pytest.mark.parametrize("value", [
    {7: "seven", None: "none", False: "no", 2.5: "half", "k": [1, "x", {"n": None}]},
    ["tab\there", "quote \" and backslash \\", "سطر عربي", float("inf"), -0.0],
    {"nested": {"deeper": {"deepest": "value"}}, "empty": {}, "list": []},
])
def test_dump_with_positions_matches_json_dumps(value):
    dump, leaves = dump_with_positions(value)
    assert dump == json.dumps(value, ensure_ascii=False)
    for leaf in leaves:
        assert len(leaf.positions) == len(leaf.text) + 1
        assert all(a < b for a, b in zip(leaf.positions, leaf.positions[1:], strict=False))


# --------------------------------------------------------------------------- latency


def _benign_2kb() -> str:
    block = " ".join(BENIGN_EN[:5] + BENIGN_AR[:5]) + " "
    return (block * (2048 // len(block) + 1))[:2048]


def _p50_ms(det: InjectionDetector, text: str, n: int = 30) -> float:
    for _ in range(3):
        det.scan(text)
    samples = []
    for _ in range(n):
        t0 = time.perf_counter()
        det.scan(text)
        samples.append((time.perf_counter() - t0) * 1000.0)
    return statistics.median(samples)


# Generous bounds: the spec target is p50 < 10 ms on a laptop; CI runners can be several times slower.
LATENCY_BOUND_MS = 50.0


def test_rules_only_scan_latency_p50_for_2kb(rules_detector):
    text = _benign_2kb()
    assert len(text) == 2048
    assert rules_detector.scan(text).score < 0.5
    assert _p50_ms(rules_detector, text) < LATENCY_BOUND_MS


def test_ensemble_scan_latency_p50_for_2kb(model_detector):
    assert _p50_ms(model_detector, _benign_2kb()) < LATENCY_BOUND_MS


def test_packaged_model_dir_constant_points_inside_package():
    assert detector_module.DEFAULT_MODEL_DIR == Path(detector_module.__file__).resolve().parent / "model"
