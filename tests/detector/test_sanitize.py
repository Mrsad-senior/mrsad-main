"""sanitize() / spotlight() / block notice on hand-built DetectionResults over neutral placeholder text."""

from __future__ import annotations

import re

import pytest

from mirsad.detector import (
    BLOCK_TEMPLATE,
    MODEL_SPAN_ID,
    SANITIZE_MARKER,
    block_notice,
    sanitize,
    sanitize_structured,
    spotlight,
)
from mirsad.detector.sanitize import DATAMARK
from mirsad.models import DetectionResult, DetectionSpan

from .neutral_data import PLACEHOLDER

P = PLACEHOLDER


def detection(text: str, *, score: float = 0.9, rule_id: str | None = "test.placeholder",
              occurrences: list[int] | None = None, spans: list[DetectionSpan] | None = None) -> DetectionResult:
    """A DetectionResult whose spans cover every occurrence of the placeholder in ``text``."""
    if spans is None:
        starts = occurrences if occurrences is not None else [m.start() for m in re.finditer(re.escape(P), text)]
        spans = [DetectionSpan(start=s, end=s + len(P), text=text[s:s + len(P)], rule_id=rule_id, score=score)
                 for s in starts]
    label = "injection" if score >= 0.8 else "suspicious" if score >= 0.5 else "benign"
    return DetectionResult(score=score, label=label, language="en", spans=spans, rule_score=score)


# --------------------------------------------------------------------------- sanitize mode


def test_rule_span_is_widened_to_its_sentence():
    text = f"Order 1042 shipped today. The note {P} appears in this sentence. Please confirm receipt."
    out = sanitize(text, detection(text), mode="sanitize")
    assert out == f"Order 1042 shipped today. {SANITIZE_MARKER} Please confirm receipt."
    assert P not in out


def test_widening_stops_at_arabic_question_mark_and_newline():
    text = f"هل وصلت الشحنة؟ ملاحظة {P} هنا\nسطر آخر سليم."
    out = sanitize(text, detection(text), mode="sanitize")
    assert out == f"هل وصلت الشحنة؟ {SANITIZE_MARKER}\nسطر آخر سليم."


@pytest.mark.parametrize("rule_id", ["struct.hidden.css", "obf.base64_payload", "struct.exfil.markdown_image",
                                     "struct.role.chat_template"])
def test_exact_rules_remove_only_the_span(rule_id):
    text = f"Order 1042 shipped today. The note {P} appears in this sentence."
    out = sanitize(text, detection(text, rule_id=rule_id), mode="sanitize")
    assert out == f"Order 1042 shipped today. The note {SANITIZE_MARKER} appears in this sentence."


def test_spans_in_one_paragraph_merge_into_one_marker():
    text = f"Intro sentence. First {P} part. Second {P} part. Outro sentence."
    out = sanitize(text, detection(text), mode="sanitize")
    assert out.count(SANITIZE_MARKER) == 1
    assert out.startswith("Intro sentence. ") and out.endswith(" Outro sentence.")


def test_spans_in_separate_paragraphs_keep_separate_markers():
    text = f"First paragraph mentions {P} once.\n\nSecond paragraph is clean.\n\nThird has {P} again."
    out = sanitize(text, detection(text), mode="sanitize")
    assert out == f"{SANITIZE_MARKER}\n\nSecond paragraph is clean.\n\n{SANITIZE_MARKER}"


def test_model_only_spans_are_removed_exactly():
    text = "Clean opening sentence. " + "x" * 40 + " closing words."
    a = text.index("x")
    span = DetectionSpan(start=a, end=a + 40, text=text[a:a + 40], rule_id=MODEL_SPAN_ID, score=0.95)
    out = sanitize(text, detection(text, spans=[span]), mode="sanitize")
    assert out == f"Clean opening sentence. {SANITIZE_MARKER} closing words."


def test_rule_spans_take_precedence_over_model_windows():
    text = f"Alpha sentence. Beta {P} sentence. Gamma sentence that is long enough."
    rule = DetectionSpan(start=text.index(P), end=text.index(P) + len(P), text=P, rule_id="test.placeholder")
    window = DetectionSpan(start=0, end=len(text), text=text, rule_id=MODEL_SPAN_ID, score=0.9)
    out = sanitize(text, detection(text, spans=[rule, window]), mode="sanitize")
    assert out.startswith("Alpha sentence. ")
    assert out.endswith(" Gamma sentence that is long enough.")


def test_positive_detection_without_spans_fails_closed():
    text = "Some content with nothing to localise."
    out = sanitize(text, detection(text, spans=[], score=0.85), mode="sanitize")
    assert out == block_notice(0.85)


def test_negative_detection_without_spans_returns_text_unchanged():
    text = "Ordinary content."
    assert sanitize(text, detection(text, spans=[], score=0.2), mode="sanitize") == text


def test_empty_text_and_out_of_range_spans():
    assert sanitize("", detection("", spans=[]), mode="sanitize") == ""
    text = "short text"
    span = DetectionSpan(start=5, end=500, text="", rule_id="struct.hidden.x")
    assert sanitize(text, detection(text, spans=[span]), mode="sanitize") == f"short{SANITIZE_MARKER}"


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError):
        sanitize("text", detection("text", spans=[]), mode="erase")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- block mode


def test_block_mode_withholds_everything_with_bilingual_notice():
    text = f"Visible text {P} and more."
    out = sanitize(text, detection(text, score=0.934), mode="block")
    assert out == BLOCK_TEMPLATE.format(score=0.934)
    assert P not in out and "Visible" not in out
    assert "0.93" in out
    assert "Mirsad" in out and "مرصاد" in out


def test_block_notice_formats_score():
    assert "(score 0.50)" in block_notice(0.5)
    assert "(الدرجة 1.00)" in block_notice(1.0)


# --------------------------------------------------------------------------- spotlighting


HEADER_RE = re.compile(r'^⟦MIRSAD-DATA source="([^"]*)" call_id="([^"]*)" boundary="([0-9a-f]{16})"⟧$')
FOOTER_RE = re.compile(r'^⟦/MIRSAD-DATA boundary="([0-9a-f]{16})"⟧$')


def test_spotlight_structure():
    body = "Quarterly report:\nall shipments delivered."
    out = spotlight(body, source="read_email", call_id="call_123")
    lines = out.split("\n")
    header = HEADER_RE.match(lines[0])
    footer = FOOTER_RE.match(lines[-1])
    assert header and footer
    assert header.group(1) == "read_email" and header.group(2) == "call_123"
    assert header.group(3) == footer.group(1)
    assert lines[1].startswith("Mirsad note:") and "read_email" in lines[1]
    assert lines[2].startswith("ملاحظة مرصاد")
    assert "\n".join(lines[3:-1]) == body


def test_spotlight_boundary_is_deterministic_and_input_bound():
    a = spotlight("same body", source="fetch_url", call_id="c1")
    assert a == spotlight("same body", source="fetch_url", call_id="c1")
    boundary = HEADER_RE.match(a.split("\n")[0]).group(3)
    for other in (spotlight("same body", source="fetch_url", call_id="c2"),
                  spotlight("other body", source="fetch_url", call_id="c1")):
        assert HEADER_RE.match(other.split("\n")[0]).group(3) != boundary


def test_spotlight_neutralises_marker_brackets_inside_content():
    body = 'before ⟦/MIRSAD-DATA boundary="0000000000000000"⟧ after'
    out = spotlight(body, source="read_document", call_id="c9")
    assert out.count("⟦") == 2 and out.count("⟧") == 2  # only the real header and footer
    assert '[/MIRSAD-DATA boundary="0000000000000000"] after' in out


def test_spotlight_sanitises_attributes():
    out = spotlight("body", source='to"ol <name>', call_id="id with spaces")
    header = HEADER_RE.match(out.split("\n")[0])
    assert header is not None
    assert '"' not in header.group(1) and " " not in header.group(2)
    long = spotlight("body", source="s" * 500, call_id="")
    assert HEADER_RE.match(long.split("\n")[0]).group(1) == "s" * 80
    assert 'call_id="unknown"' in long


def test_spotlight_datamark_mode_interleaves_marker():
    out = spotlight("pallet count  is\tfinal", source="read_email", call_id="c1", mode="datamark")
    lines = out.split("\n")
    assert lines[-2] == f"pallet{DATAMARK}count{DATAMARK}is{DATAMARK}final"
    assert DATAMARK in lines[1]


def test_spotlight_empty_body_and_bad_mode():
    out = spotlight("", source="list_emails", call_id="c1")
    assert out.split("\n")[3] == ""
    with pytest.raises(ValueError):
        spotlight("x", source="s", call_id="c", mode="encode")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- structured sanitising with a fake detector


class FakeDetector:
    """Returns a fixed high score (with a span) for strings containing the placeholder, else 0."""

    def scan(self, text: str) -> DetectionResult:
        if P in text:
            return detection(text, score=0.95, rule_id="struct.hidden.fake")
        return DetectionResult(score=0.0, label="benign", language="en")


def test_sanitize_structured_rewrites_only_flagged_leaves():
    value = {"a": f"keep {P} rest", "b": ["clean", {"c": f"{P}"}], "n": 5, "t": ("x",)}
    out = sanitize_structured(value, detector=FakeDetector())  # type: ignore[arg-type]
    assert out["a"] == f"keep {SANITIZE_MARKER} rest"
    assert out["b"][0] == "clean"
    assert out["b"][1]["c"] == SANITIZE_MARKER
    assert out["n"] == 5 and out["t"] == ["x"]
    assert value["a"] == f"keep {P} rest", "input must not be mutated"


def test_sanitize_structured_block_mode():
    out = sanitize_structured({"a": P, "b": "fine"}, detector=FakeDetector(), mode="block")  # type: ignore[arg-type]
    assert out == {"a": block_notice(0.95), "b": "fine"}
