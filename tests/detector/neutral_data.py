"""Neutral synthetic dataset records for detector pipeline tests.

Nothing here resembles an attack. A record is "positive" (label 1) only because it contains the
placeholder token :data:`MARKER`; the tests use it as a stand-in for "contains an injection" so the
dataset builder, trainer and model persistence can be exercised end to end without adversarial text.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from mirsad.detector.model import FeatureConfig

MARKER = "AAA"
PLACEHOLDER = "SAMPLE-FLAGGED-TEXT"
#: small hashing spaces keep test models tiny and fast; the shipped model uses the defaults
SMALL_FEATURES = FeatureConfig(char_features=2**14, word_features=2**12)

EN_WORDS = (
    "invoice", "pallet", "harbor", "ledger", "orchid", "copper", "timber", "canvas", "meadow", "violet",
    "shipment", "quarter", "budget", "warehouse", "supplier", "catalogue", "receipt", "schedule", "office",
    "printer", "calendar", "parcel", "contract", "pricing", "delivery", "inventory", "garden", "river",
    "coffee", "morning",
)
AR_WORDS = (
    "تقرير", "شحنة", "فاتورة", "مستودع", "طلبية", "عميل", "موعد", "ميزانية", "منتج", "مورد",
    "اجتماع", "جدول", "مكتب", "حساب", "عقد", "تسليم", "مخزون", "سعر", "صباح", "حديقة",
    "قهوة", "نهر", "دفتر", "طابعة", "تقويم", "طرد", "فرع", "موظف", "خدمة", "تمور",
)
_VARIETY = {"en": "en", "ar": "msa", "mixed": "mixed"}


def neutral_text(rng: random.Random, lang: str, *, positive: bool, serial: int) -> str:
    """A bag of neutral business words; positives get :data:`MARKER` at a random position."""
    n = rng.randint(10, 18)
    if lang == "en":
        words = [rng.choice(EN_WORDS) for _ in range(n)]
        words.append(f"ref {serial}")
    elif lang == "ar":
        words = [rng.choice(AR_WORDS) for _ in range(n)]
        words.append(f"رقم {serial}")
    else:
        words = [rng.choice(EN_WORDS if i % 2 else AR_WORDS) for i in range(n)]
        words.append(f"ref {serial}")
    if positive:
        words.insert(rng.randrange(len(words) + 1), MARKER)
    return " ".join(words)


def record(rec_id: str, text: str, label: int, lang: str, **extra: Any) -> dict[str, Any]:
    """A schema-valid dataset record (BUILD_SPEC section 12)."""
    rec: dict[str, Any] = {
        "id": rec_id,
        "text": text,
        "label": label,
        "lang": lang,
        "variety": _VARIETY[lang],
        "carrier": "email",
        "attack_type": "goal_hijack" if label == 1 else "none",
        "difficulty": "easy",
        "source": "",
        "notes": "neutral synthetic test record",
    }
    rec.update(extra)
    return rec


def make_records(prefix: str, n: int, *, lang: str, seed: int, positive_share: float = 0.5,
                 serial_start: int = 0) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    n_pos = int(round(n * positive_share))
    out = []
    for i in range(n):
        label = 1 if i < n_pos else 0
        text = neutral_text(rng, lang, positive=bool(label), serial=serial_start + i)
        out.append(record(f"{prefix}-{i:04d}", text, label, lang))
    return out


def write_batch(path: Path, records: list[dict[str, Any]], *, extra_lines: list[str] | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(r, ensure_ascii=False) for r in records] + list(extra_lines or [])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def make_dataset(root: Path, *, seed: int = 0, train_per_lang: int = 40, test_per_lang: int = 12) -> Path:
    """Write a small neutral dataset under ``root/raw`` and ``root/external``; returns ``root``."""
    serial = 0
    for k, lang in enumerate(("en", "ar", "mixed")):
        recs = make_records(f"tr-{lang}", train_per_lang, lang=lang, seed=seed + k, serial_start=serial)
        serial += train_per_lang
        write_batch(root / "raw" / f"neutral-{lang}.jsonl", recs)
        tests = make_records(f"te-{lang}", test_per_lang, lang=lang, seed=seed + 100 + k, serial_start=serial)
        serial += test_per_lang
        write_batch(root / "raw" / f"test-neutral-{lang}.jsonl", tests)
    ext = make_records("ext", 8, lang="en", seed=seed + 200, serial_start=serial)
    write_batch(root / "external" / "test-placeholder.jsonl", ext)
    return root
