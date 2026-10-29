"""Conservative synthetic sector-sensitive data indicators (not production-grade DLP)."""
from __future__ import annotations

import re
from typing import Any

_RE = {
    'iban': re.compile(r'\bSA\d{22}\b', re.I),
    'card': re.compile(r'(?<!\d)(?:\d[ -]?){13,19}(?!\d)'),
    'account': re.compile(r'\b(?:account(?:_number)?|حساب)\s*(?:#|:|رقم)?\s*[A-Z0-9-]{6,20}\b', re.I),
    'amount': re.compile(r'\b(?:SAR|ر\.س|ريال)\s*\d[\d,]*(?:\.\d{1,2})?\b', re.I),
    'patient_id': re.compile(r'\bPAT[-_]\d{3,12}\b', re.I),
    'diagnosis': re.compile(r'\b(?:diagnosis|diagnosed with|تشخيص|التشخيص)\b', re.I),
    'prescription': re.compile(r'\b(?:prescription|dosage|medication|وصفة|الجرعة|دواء)\b', re.I),
    'lab_result': re.compile(r'\b(?:lab result|blood test|hemoglobin|نتائج التحاليل|نتيجة التحليل)\b', re.I),
}
_SECTORS = {'finance': ('iban', 'card', 'account', 'amount'),
            'healthcare': ('patient_id', 'diagnosis', 'prescription', 'lab_result')}


def _luhn(digits: str) -> bool:
    total = 0
    for idx, value in enumerate(map(int, reversed(digits))):
        if idx % 2:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def find_sensitive(data: Any, sector: str) -> list[str]:
    """Return *categories*, never matching private values (audit-safe by design)."""
    text = str(data)
    found: list[str] = []
    for kind in _SECTORS.get(sector, ()):
        matches = _RE[kind].findall(text)
        if kind == 'card':
            matches = [m for m in matches if _luhn(re.sub(r'\D', '', m))]
        if matches:
            found.append(kind)
    return found
