"""Build the Mirsad IS499 poster: portrait 85 cm x 142 cm PowerPoint, one slide.

The layout follows the department's example poster: title band (title, subtitle, authors, advisor,
university logo), then Introduction, Objectives | Methodology, figures, Results, Conclusion | Future
Directions. Every measured number on the Results tiles and in the conclusion is read from
``reports/results_summary.json`` when the poster is built; a value that has not been measured is shown
as "pending" (the detector F1 and the attack-success reduction show "pending team data" until the
team's attack-labelled data has been evaluated).

Text boxes are sized with the Calibri metrics shipped with Microsoft Office (when installed), so
cards grow with their content and the free vertical space is shared between the section gaps; the
figures keep their aspect ratio.

Usage::

    python scripts/build_poster.py                      # writes deliverables/Mirsad_Poster.pptx
    python scripts/build_poster.py --preview            # macOS + PowerPoint: also renders
                                                        # deliverables/Mirsad_Poster_preview.png
    python scripts/build_poster.py --preview --renderer quicklook

``--preview`` exports a PDF with Microsoft PowerPoint (inside PowerPoint's sandbox container) and
renders it to PNG with PyMuPDF (``pip install pymupdf``). If PowerPoint automation is blocked (for
example by a dialog waiting for the user), ``--renderer quicklook`` renders the slide with macOS Quick
Look (``qlmanage``) instead; because the poster uses Arial, which macOS also ships, that preview uses the
same font metrics as PowerPoint.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageFont
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Cm, Pt

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "deliverables" / "Mirsad_Poster.pptx"
DEFAULT_PREVIEW = ROOT / "deliverables" / "Mirsad_Poster_preview.png"
RESULTS = ROOT / "reports" / "results_summary.json"
FIG = ROOT / "docs" / "figures"
PSU_LOGO = ROOT / "docs" / "report" / "assets" / "psu_logo.png"
APP_ICON = ROOT / "web" / "public" / "assets" / "icons" / "icon-512.png"
FIGURES = {
    "architecture": FIG / "architecture.png",
    "dashboard": FIG / "screens" / "dash-overview.png",
    "pwa_detail": FIG / "screens" / "pwa-detail-en.png",
    "pwa_pending": FIG / "screens" / "pwa-pending-ar.png",
}
OFFICE_FONTS = Path("/Applications/Microsoft PowerPoint.app/Contents/Resources/DFonts")
SYSTEM_FONTS = Path("/System/Library/Fonts/Supplemental")
OSASCRIPT = "/usr/bin/osascript"
QLMANAGE = "/usr/bin/qlmanage"
PPT_CONTAINER = Path.home() / "Library/Containers/com.microsoft.Powerpoint/Data/Documents"

# ----------------------------------------------------------------------------- brand

NAVY = RGBColor(0x0B, 0x1F, 0x3A)
TEAL = RGBColor(0x0F, 0x76, 0x6E)
BG = RGBColor(0xEE, 0xF6, 0xFB)
AMBER = RGBColor(0xF5, 0x9E, 0x0B)
# tints and text shades derived from the four brand colours
TEAL_ON_NAVY = RGBColor(0x5E, 0xEA, 0xD4)
NAVY_SOFT = RGBColor(0xD6, 0xE4, 0xF0)   # light text on navy
AMBER_DARK = RGBColor(0x92, 0x40, 0x0E)
AMBER_TINT = RGBColor(0xFE, 0xF3, 0xC7)
TEAL_TINT = RGBColor(0xE3, 0xF1, 0xEF)
INK = RGBColor(0x1F, 0x29, 0x37)
MUTED = RGBColor(0x47, 0x55, 0x69)
LINE = RGBColor(0xC5, 0xD5, 0xE4)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

# Arial ships with macOS, Windows and Microsoft Office, so PowerPoint, Quick Look/Keynote previews and print
# shops all render the same metrics (Calibri exists only inside Office on macOS). It also covers Arabic.
FONT = "Arial"
ARABIC_FONT = "Arial"

TEAM = [
    "Mohammed Yasser Alanssari",
    "Bader Alshuraie",
    "Bader Abdullah Abbod Alyamini",
    "Abdulmalik bin Saedan",
    "Abdullah Naif Abdullah Al-Orabi",
]
SUPERVISOR = "Dr. Omaia Al-Omari"
PENDING = "pending"
PENDING_TEAM = "pending team data"
NB = " "  # keeps "≤ 200 ms" and similar on one line

# ----------------------------------------------------------------------------- geometry (cm, points)

SLIDE_W, SLIDE_H = 85.0, 142.0
MARGIN = 4.0
CONTENT_W = SLIDE_W - 2 * MARGIN
COL_GAP = 2.0
COL_W = (CONTENT_W - COL_GAP) / 2

TITLE_PT = 132
SUBTITLE_PT = 50
AUTHOR_PT = 34
HEAD_PT = 60
BODY_PT = 30
SUB_PT = 34
CAPTION_PT = 26
VALUE_PT = 58
LABEL_PT = 26
FOOTER_PT = 26

PILL_H = 3.6
CARD_PAD_X = 1.8
CARD_PAD_TOP = PILL_H / 2 + 1.2
CARD_PAD_BOTTOM = 1.7
CARD_RADIUS = 1.1
CARD_GAP_MIN = PILL_H / 2 + 1.5      # above a card whose heading pill straddles its top edge
PLAIN_GAP_MIN = 1.8
FOOTER_H = 3.2

CM_PER_PT = 2.54 / 72
LINE_FACTOR = 1.2                    # single line spacing as a multiple of the font size (Arial: 1.15)
FIT_SLACK = 1.03                     # safety factor on measured text heights


# ----------------------------------------------------------------------------- results


class Results:
    """Dotted-path access to reports/results_summary.json; missing or null values are ``None``."""

    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if not self.data:
            print(f"  WARNING {path} not found: every result shows as pending")

    def get(self, dotted: str) -> Any:
        node: Any = self.data
        for part in dotted.split("."):
            node = node.get(part) if isinstance(node, dict) else None
        return node

    def fmt(self, dotted: str, spec: str = "", suffix: str = "") -> str:
        value = self.get(dotted)
        if value is None:
            return PENDING
        try:
            return format(value, spec) + suffix
        except (TypeError, ValueError):
            return f"{value}{suffix}"

    def asr_reduction(self) -> float | None:
        """ASR reduction of the full defence in the first benchmark run that executed attack episodes."""
        for run in (self.get("bench") or {}).values():
            value = (((run or {}).get("configs") or {}).get("full") or {}).get("asr_reduction")
            if value is not None:
                return float(value)
        return None

    def generated(self) -> str:
        raw = self.get("generated_at")
        try:
            dt = datetime.fromisoformat(str(raw))
            return f"{dt.day} {dt:%b %Y}"
        except (TypeError, ValueError):
            return "an unknown date"


@dataclass
class Tile:
    value: str
    label: str
    detail: str
    pending: bool = False


def result_tiles(r: Results) -> list[Tile]:
    """The eleven measured/pending tiles of the Results section, in reading order."""
    bench = "bench.scripted_benign_oracle"
    lat = "latency.separate_process"
    sec = "security"

    def ratio(passed: str, total: str) -> tuple[str, str]:
        p, t = r.get(passed), r.get(total)
        return (PENDING if p is None else f"{p:,}"), (f"of {t:,}" if t is not None else "total pending")

    py_v, py_d = ratio("python_tests.passed", "python_tests.total")
    web_v, web_d = ratio("web_tests.passed", "web_tests.total")
    if r.get("web_tests.files") is not None and r.get("web_tests.total") is not None:
        web_d += f" · {r.get('web_tests.files')} suites"
    if r.get("python_tests.by_area"):
        py_d += f" · {len(r.get('python_tests.by_area'))} areas"

    calls = r.get(f"{bench}.configs.full.calls")
    replay_m, replay_c = r.get(f"{bench}.replay_matched"), r.get(f"{bench}.replay_checked")
    bandit = r.get(f"{sec}.bandit_issues")
    vuln_parts = [r.get(f"{sec}.pip_audit_vulnerable"), r.get(f"{sec}.npm_audit_vulnerabilities")]
    vulns = None if any(v is None for v in vuln_parts) else sum(vuln_parts)
    sessions = r.get(f"{lat}.sessions")

    ar, en = r.get("detector.splits.test_ar.f1"), r.get("detector.splits.test_en.f1")
    if ar is None and en is None:
        f1 = Tile(PENDING_TEAM, "Detector F1 (AR/EN)", f"target ≥{NB}0.85", pending=True)
    else:
        f1 = Tile(f"{'–' if ar is None else format(ar, '.2f')} / {'–' if en is None else format(en, '.2f')}",
                  "Detector F1 (AR/EN)", f"target ≥{NB}0.85")
    asr = r.asr_reduction()
    asr_tile = (Tile(PENDING_TEAM, "Attack success reduction", f"target ≥{NB}80%", pending=True) if asr is None
                else Tile(f"{asr:.0%}", "Attack success reduction", f"target ≥{NB}80%"))

    return [
        Tile(py_v, "Python tests passed", py_d),
        Tile(web_v, "Web tests passed", web_d),
        Tile(r.fmt("coverage.percent", ".1f", "%"), "Statement coverage",
             f"{r.get('coverage.statements'):,} statements" if r.get("coverage.statements") else "core package"),
        Tile(r.fmt(f"{bench}.configs.full.fpr", ".1%"), "Benign false-positive rate",
             f"{calls} calls · target ≤{NB}5%" if calls else f"target ≤{NB}5%"),
        Tile(r.fmt(f"{bench}.configs.full.friction", ".1%"), "Approval friction (full defence)",
             "sent to a human"),
        Tile(r.fmt(f"{lat}.sequential_added_p50", ".1f", f"{NB}ms"), "Median added latency, sequential",
             f"target ≤{NB}200{NB}ms"),
        Tile(r.fmt(f"{lat}.concurrent_added_p50", ".0f", f"{NB}ms"),
             f"Median added latency, {sessions if sessions else 'concurrent'} concurrent sessions",
             "separate process"),
        Tile(PENDING if replay_m is None else f"{replay_m}/{replay_c}", "Audit replays matched",
             "hash chain verified" if r.get(f"{bench}.audit_all_ok") else "same action on replay"),
        Tile(f"{PENDING if bandit is None else bandit} / {PENDING if vulns is None else vulns}",
             "Bandit issues / vulnerable packages",
             f"{r.get(f'{sec}.bandit_loc'):,} lines scanned" if r.get(f"{sec}.bandit_loc") else "pip-audit, npm audit"),
        f1,
        asr_tile,
    ]


# ----------------------------------------------------------------------------- text measurement


@dataclass(frozen=True)
class St:
    """Run style."""

    size: float = BODY_PT
    bold: bool = False
    color: RGBColor = INK
    font: str = FONT
    italic: bool = False


Run = tuple[str, St]
Para = list[Run]

ARABIC_RE = re.compile(r"[؀-ۿ]")


class Metrics:
    """Text widths from the Office font files (falls back to an average-width estimate)."""

    FILES = {("Calibri", False): ["Calibri.ttf"], ("Calibri", True): ["Calibrib.ttf"],
             ("Arial", False): ["arial.ttf", "Arial.ttf"], ("Arial", True): ["arialbd.ttf", "Arial Bold.ttf"]}

    def __init__(self) -> None:
        self._fonts: dict[tuple[str, bool], Any] = {}
        self.exact = self._font(FONT, False) is not None and self._font(FONT, True) is not None
        if not self.exact:
            print(f"  NOTE {FONT} font files not found: text heights are estimated, check the preview")

    def _font(self, family: str, bold: bool):
        key = (family, bold)
        if key not in self._fonts:
            self._fonts[key] = None
            for name in self.FILES.get(key, []):
                for folder in (OFFICE_FONTS, SYSTEM_FONTS):
                    if (folder / name).exists():
                        self._fonts[key] = ImageFont.truetype(str(folder / name), 200)
                        break
                if self._fonts[key] is not None:
                    break
        return self._fonts[key]

    def width(self, text: str, st: St) -> float:
        """Width of ``text`` in cm."""
        family = ARABIC_FONT if ARABIC_RE.search(text) else st.font
        font = self._font(family, st.bold)
        if font is None:
            return len(text) * st.size * (0.55 if st.bold else 0.52) * CM_PER_PT
        return font.getlength(text) * st.size / 200 * CM_PER_PT

    @staticmethod
    def _words(para: Para) -> list[list[Run]]:
        words: list[list[Run]] = []
        cur: list[Run] = []
        for text, st in para:
            for k, part in enumerate(text.split(" ")):
                if k > 0 and cur:
                    words.append(cur)
                    cur = []
                if part:
                    cur.append((part, st))
        if cur:
            words.append(cur)
        return words

    def lines(self, para: Para, width_cm: float) -> int:
        count, x = 1, 0.0
        for word in self._words(para):
            ww = sum(self.width(t, st) for t, st in word)
            if ww > width_cm:
                print(f"  FIT word wider than its box ({width_cm:.1f} cm): {''.join(t for t, _ in word)!r}")
            sp = self.width(" ", word[0][1])
            if x == 0:
                x = ww
            elif x + sp + ww <= width_cm:
                x += sp + ww
            else:
                count += 1
                x = ww
        return count

    def para_width(self, para: Para) -> float:
        return sum(self.width(t, st) for t, st in para)

    def height(self, paras: list[Para], width_cm: float, space_after_pt: float = 0.0) -> float:
        total = 0.0
        for i, para in enumerate(paras):
            size = max(st.size for _, st in para)
            total += self.lines(para, width_cm) * size * LINE_FACTOR * CM_PER_PT
            if i < len(paras) - 1:
                total += space_after_pt * CM_PER_PT
        return total * FIT_SLACK


# ----------------------------------------------------------------------------- content


def words_in(paras: list[Para]) -> int:
    return len(" ".join(t for para in paras for t, _ in para).replace(NB, " ").split())


def body(text: str, **kw: Any) -> Run:
    return (text, St(**{"size": BODY_PT, **kw}))


INTRO: list[Para] = [[
    body("AI agents now read e-mail, web pages and documents and act through tools that send messages, export "
         "records or move money. Instructions hidden in that content can hijack an agent (indirect prompt "
         "injection, OWASP LLM01), and firewalls or DLP only see an authorised agent making a normal call. "),
    body("Mirsad", bold=True, color=NAVY),
    body(" (Arabic for “watchtower”) is a drop-in gateway between any agent and its tools. It checks every "
         "tool call before it runs and every result before the model sees it, in Arabic and English."),
]]

OBJECTIVES = [  # the three SMART objectives of ch1 section 1.3, shortened
    ("Enforce security at the tool boundary",
     "Intercept every tool call and result of MCP and OpenAI-style agents, enforce a YAML policy and taint "
     f"tracking, and add at most 200{NB}ms median latency per call.", "M5, Mar 2027"),
    ("Detect injections in Arabic and English",
     "Build a detector and a labelled dataset for MSA, Gulf dialect, Arabizi, mixed and English text that "
     f"reaches F1 ≥{NB}0.85 on held-out test sets.", "M4, Feb 2027"),
    ("Keep humans in control and prove the effect",
     "Provide a mobile approval app, a dashboard and a replayable, tamper-evident audit log; cut attack "
     f"success by ≥{NB}80% while blocking ≤{NB}5% of benign actions.", "M6, Apr 2027"),
]

METHOD: list[Para] = [
    [body("Scrum.", bold=True, color=NAVY),
     body(" Two-week sprints (17 over two semesters), one owner per workstream, all coding against a "
          "written interface contract.")],
    [body("DevSecOps.", bold=True, color=NAVY),
     body(" STRIDE threat model, a second reviewer on every pull request and CI security gates: tests, "
          "coverage, Bandit, pip-audit and npm audit.")],
]

LAYERS = [
    ("Policy engine", "YAML allow-lists, per-parameter limits and rate limits; unlisted tools are denied."),
    ("Taint tracking", "labels results by trust and sensitivity; escalates or blocks untrusted or "
                       "confidential data sent outside."),
    ("Injection detector", "Arabic/English normalisation and weighted rules; risky results are sanitised "
                           "or marked as data."),
    ("Human approval", "high-risk calls wait for a phone decision with a bilingual summary; no answer "
                       "means deny."),
    ("Audit log", "every decision enters an HMAC-SHA-256 hash chain that can be verified and replayed."),
]
LAYERS_NOTE = "Layers combine by deny-overrides: any deny wins."

CAPTIONS = {
    "architecture": "Architecture: call path before a tool runs, result path before the model reads.",
    "dashboard": "Admin dashboard: live decisions and audit-chain status.",
    "pwa_detail": "Approver app, request (EN).",
    "pwa_pending": "Approver app, queue (AR).",
}

FUTURE = [
    "Measure detector F1 and attack-success reduction with team data.",
    "Fine-tune an Arabic or multilingual encoder (MARBERT, XLM-R).",
    "Multi-worker deployment on PostgreSQL with shared rate limits.",
    "Saudi pilot with NCA ECC evidence: retention, SIEM, anchoring.",
]


def conclusion(r: Results) -> list[Para]:
    """Conclusion text; the numbers come from the results file."""
    tasks = r.get("bench.scripted_benign_oracle.tasks")
    fpr = r.get("bench.scripted_benign_oracle.configs.full.fpr")
    p50 = r.get("latency.separate_process.sequential_added_p50")
    task_part = f"On {tasks} benign English and Arabic tasks" if tasks else "On the benign benchmark tasks"
    if fpr is None:
        fpr_part = "its false-positive rate is pending"
    elif fpr == 0:
        fpr_part = "it denied no benign call automatically"
    else:
        fpr_part = f"it denied {fpr:.1%} of benign calls automatically"
    lat_part = (f" and added a median of {p50:.1f}{NB}ms per call" if p50 is not None
                else "; its added latency is pending")
    return [[
        body("Mirsad shows that the tool-calling boundary is a workable control point for AI agents. One "
             "drop-in gateway applies an organisation’s rules to every action, explains each decision in "
             "Arabic and English, asks a human when the stakes are high and keeps a verifiable, replayable "
             f"record. {task_part}, {fpr_part}{lat_part}. Its effect on real attacks awaits the team’s "
             "attack data."),
    ]]


# ----------------------------------------------------------------------------- drawing helpers


def cm(v: float) -> int:
    return Cm(v)


@dataclass
class Poster:
    results: Results
    m: Metrics = field(default_factory=Metrics)

    def __post_init__(self) -> None:
        self.prs = Presentation()
        self.prs.slide_width = cm(SLIDE_W)
        self.prs.slide_height = cm(SLIDE_H)
        self.slide = self.prs.slides.add_slide(self.prs.slide_layouts[6])  # blank
        bg = self.slide.background.fill
        bg.solid()
        bg.fore_color.rgb = BG
        self.warnings: list[str] = []

    # ------------------------------------------------------------- primitives

    @staticmethod
    def _style(run, st: St) -> None:
        run.font.size = Pt(st.size)
        run.font.bold = st.bold
        run.font.italic = st.italic
        run.font.name = st.font
        run.font.color.rgb = st.color
        if ARABIC_RE.search(run.text or ""):
            r_pr = run._r.get_or_add_rPr()
            r_pr.set("lang", "ar-SA")
            cs = r_pr.find(qn("a:cs"))
            if cs is None:
                cs = r_pr.makeelement(qn("a:cs"), {})
                r_pr.append(cs)
            cs.set("typeface", ARABIC_FONT)

    def text(self, x: float, y: float, w: float, h: float, paras: list[Para], *, align=PP_ALIGN.LEFT,
             anchor=MSO_ANCHOR.TOP, space_after: float = 0.0, name: str = "text"):
        box = self.slide.shapes.add_textbox(cm(x), cm(y), cm(w), cm(h))
        box.name = name
        tf = box.text_frame
        tf.word_wrap = True
        tf.auto_size = MSO_AUTO_SIZE.NONE
        tf.vertical_anchor = anchor
        for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
            setattr(tf, side, 0)
        for i, para in enumerate(paras):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            if space_after and i < len(paras) - 1:
                p.space_after = Pt(space_after)
            for txt, st in para:
                run = p.add_run()
                run.text = txt
                self._style(run, st)
        need = self.m.height(paras, w, space_after)
        if need > h + 0.05:
            self.warnings.append(f"text box '{name}' needs {need:.2f} cm, has {h:.2f} cm")
        return box

    def rect(self, x: float, y: float, w: float, h: float, *, fill: RGBColor | None = WHITE,
             line: RGBColor | None = None, line_pt: float = 1.5, radius: float | None = None,
             kind=MSO_SHAPE.RECTANGLE, name: str = "shape"):
        shape_kind = MSO_SHAPE.ROUNDED_RECTANGLE if radius else kind
        shp = self.slide.shapes.add_shape(shape_kind, cm(x), cm(y), cm(w), cm(h))
        shp.name = name
        if radius:
            shp.adjustments[0] = min(0.5, radius / min(w, h))
        if fill is None:
            shp.fill.background()
        else:
            shp.fill.solid()
            shp.fill.fore_color.rgb = fill
        if line is None:
            shp.line.fill.background()
        else:
            shp.line.color.rgb = line
            shp.line.width = Pt(line_pt)
        shp.shadow.inherit = False
        return shp

    def label_shape(self, shp, text: str, st: St) -> None:
        tf = shp.text_frame
        for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
            setattr(tf, side, 0)
        tf.word_wrap = False
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run()
        run.text = text
        self._style(run, st)

    def badge(self, x: float, y: float, d: float, label: str, *, fill: RGBColor, color: RGBColor,
              size: float, name: str = "badge"):
        shp = self.rect(x, y, d, d, fill=fill, kind=MSO_SHAPE.OVAL, name=name)
        self.label_shape(shp, label, St(size=size, bold=True, color=color))
        return shp

    def card(self, x: float, y: float, w: float, h: float, heading: str | None, name: str):
        self.rect(x, y, w, h, fill=WHITE, line=LINE, line_pt=1.75, radius=CARD_RADIUS, name=f"{name} card")
        if heading:
            st = St(size=HEAD_PT, bold=True, color=WHITE)
            pw = self.m.width(heading, st) + 4.4
            pill = self.rect(x + (w - pw) / 2, y - PILL_H / 2, pw, PILL_H, fill=TEAL, radius=PILL_H / 2,
                             name=f"{name} heading")
            self.label_shape(pill, heading, st)

    def picture(self, path: Path, x: float, y: float, w: float, h: float, alt: str, *, border: bool = True):
        pic = self.slide.shapes.add_picture(str(path), cm(x), cm(y), cm(w), cm(h))
        pic._element.nvPicPr.cNvPr.set("descr", alt)
        if border:
            pic.line.color.rgb = LINE
            pic.line.width = Pt(1.5)
        return pic

    @staticmethod
    def aspect(path: Path) -> float:
        with Image.open(path) as img:
            return img.width / img.height

    def caption_paras(self, number: int, key: str) -> list[Para]:
        return [[(f"Figure {number}. ", St(size=CAPTION_PT, bold=True, color=NAVY)),
                 (CAPTIONS[key], St(size=CAPTION_PT, color=MUTED))]]

    # ------------------------------------------------------------- header

    def header_height(self) -> float:
        return self._header(draw=False)

    def _header(self, *, draw: bool) -> float:
        logo_h = 4.6
        logo_w = logo_h * self.aspect(PSU_LOGO)
        logo_pad = 0.9
        card_w, card_h = logo_w + 2 * logo_pad, logo_h + 2 * logo_pad
        title_st = St(size=TITLE_PT, bold=True, color=WHITE)
        bar_st = St(size=TITLE_PT, bold=False, color=TEAL_ON_NAVY)
        title_runs: Para = [("Mirsad", title_st), ("  |  ", bar_st), ("مرصاد", title_st)]
        title_w = self.m.para_width(title_runs) + 1.0
        title_h = self.m.height([title_runs], title_w)
        icon_d = title_h * 0.86
        right_st = St(size=28, bold=True, color=WHITE)
        right_st2 = St(size=28, color=NAVY_SOFT)
        right_paras: list[Para] = [[("College of Computer &", right_st)], [("Information Sciences", right_st)],
                                   [("IS499 Senior Project", right_st2)]]
        right_w = max(self.m.para_width(p) for p in right_paras) + 1.2
        right_h = self.m.height(right_paras, right_w)
        row_h = max(card_h, title_h, right_h)

        top = 2.2
        y_sub = top + row_h + 0.7
        sub_st = St(size=SUBTITLE_PT, color=TEAL_ON_NAVY)
        sub_paras: list[Para] = [[("A Runtime Security Firewall for AI Agents Against Prompt-Injection Attacks",
                                   sub_st)]]
        sub_h = self.m.height(sub_paras, CONTENT_W)
        y_rule = y_sub + sub_h + 0.9
        y_auth = y_rule + 0.25 + 1.0
        a_lab = St(size=AUTHOR_PT, bold=True, color=TEAL_ON_NAVY)
        a_txt = St(size=AUTHOR_PT, color=WHITE)
        names = [n.replace(" ", NB) for n in TEAM]
        auth_paras: list[Para] = [[("Authors: ", a_lab), ("  ·  ".join(names[:3]), a_txt)],
                                  [("  ·  ".join(names[3:]), a_txt)]]
        auth_w = CONTENT_W - 2.0
        auth_h = self.m.height(auth_paras, auth_w)
        y_adv = y_auth + auth_h + 0.35
        adv_paras: list[Para] = [[("Advisor: ", a_lab), (SUPERVISOR, a_txt)]]
        adv_h = self.m.height(adv_paras, auth_w)
        total = y_adv + adv_h + 2.0
        if not draw:
            return total

        self.rect(0, 0, SLIDE_W, total, fill=NAVY, name="title band")
        self.rect(0, total - 0.45, SLIDE_W, 0.45, fill=AMBER, name="title band rule")
        cy = top + row_h / 2
        # university logo on a white card (the logo artwork is dark on transparent)
        self.rect(MARGIN, cy - card_h / 2, card_w, card_h, fill=WHITE, radius=0.8, name="logo card")
        self.picture(PSU_LOGO, MARGIN + logo_pad, cy - logo_h / 2, logo_w, logo_h,
                     "Prince Sultan University logo", border=False)
        # icon + title, centred as a group on the page
        gap = 1.0
        group_w = icon_d + gap + title_w
        gx = (SLIDE_W - group_w) / 2
        if gx < MARGIN + card_w + 0.8 or gx + group_w > SLIDE_W - MARGIN - right_w - 0.8:
            self.warnings.append("title row is crowded: logo, title and course text may touch")
        self.picture(APP_ICON, gx, cy - icon_d / 2, icon_d, icon_d, "Mirsad logo", border=False)
        self.text(gx + icon_d + gap, cy - title_h / 2, title_w, title_h, [title_runs], name="title",
                  anchor=MSO_ANCHOR.MIDDLE)
        self.text(SLIDE_W - MARGIN - right_w, cy - right_h / 2, right_w, right_h, right_paras,
                  align=PP_ALIGN.RIGHT, name="course")
        self.text(MARGIN, y_sub, CONTENT_W, sub_h, sub_paras, align=PP_ALIGN.CENTER, name="subtitle")
        self.rect((SLIDE_W - 16) / 2, y_rule, 16, 0.25, fill=AMBER, name="subtitle rule")
        self.text(MARGIN + 1.0, y_auth, auth_w, auth_h, auth_paras, align=PP_ALIGN.CENTER, name="authors")
        self.text(MARGIN + 1.0, y_adv, auth_w, adv_h, adv_paras, align=PP_ALIGN.CENTER, name="advisor")
        return total

    # ------------------------------------------------------------- introduction

    def intro_height(self) -> float:
        inner = CONTENT_W - 2 * CARD_PAD_X
        return CARD_PAD_TOP + self.m.height(INTRO, inner) + CARD_PAD_BOTTOM

    def draw_intro(self, y: float) -> float:
        h = self.intro_height()
        self.card(MARGIN, y, CONTENT_W, h, "Introduction", "introduction")
        inner = CONTENT_W - 2 * CARD_PAD_X
        th = self.m.height(INTRO, inner)
        self.text(MARGIN + CARD_PAD_X, y + CARD_PAD_TOP, inner, th, INTRO, name="introduction text")
        return h

    # ------------------------------------------------------------- objectives | methodology

    OBJ_PAD = 1.0
    OBJ_BADGE = 2.9
    OBJ_GAP = 0.9

    def _objective_paras(self, i: int) -> list[Para]:
        title, desc, due = OBJECTIVES[i]
        return [[(title, St(size=BODY_PT + 2, bold=True, color=NAVY))],
                [body(desc), body(f" ({due.replace(' ', NB)})", color=MUTED)]]

    def _objective_heights(self) -> list[float]:
        inner = COL_W - 2 * CARD_PAD_X
        tw = inner - 2 * self.OBJ_PAD - self.OBJ_BADGE - 1.0
        return [max(self.OBJ_BADGE, self.m.height(self._objective_paras(i), tw, 6)) + 2 * self.OBJ_PAD
                for i in range(len(OBJECTIVES))]

    LAYER_BADGE = 2.2

    def _method_parts(self) -> tuple[float, float, list[float], float, float]:
        inner = COL_W - 2 * CARD_PAD_X
        intro_h = self.m.height(METHOD, inner, 10)
        sub_h = self.m.height([[("How Mirsad works: five layers", St(size=SUB_PT, bold=True, color=TEAL))]], inner)
        tw = inner - self.LAYER_BADGE - 0.9
        rows = [max(self.LAYER_BADGE, self.m.height([self._layer_para(i)], tw)) for i in range(len(LAYERS))]
        note_h = self.m.height([[body(LAYERS_NOTE, bold=True, color=TEAL)]], inner)
        return intro_h, sub_h, rows, note_h, tw

    def _layer_para(self, i: int) -> Para:
        name, desc = LAYERS[i]
        return [body(name, bold=True, color=NAVY), body(f" – {desc}")]

    def objmeth_height(self) -> float:
        obj = sum(self._objective_heights()) + self.OBJ_GAP * (len(OBJECTIVES) - 1)
        intro_h, sub_h, rows, note_h, _ = self._method_parts()
        meth = intro_h + 1.1 + sub_h + 0.6 + sum(rows) + 0.55 * (len(rows) - 1) + 0.9 + note_h
        self._obj_natural, self._meth_natural = obj, meth
        return CARD_PAD_TOP + max(obj, meth) + CARD_PAD_BOTTOM

    def draw_objmeth(self, y: float) -> float:
        h = self.objmeth_height()
        content_h = h - CARD_PAD_TOP - CARD_PAD_BOTTOM
        inner = COL_W - 2 * CARD_PAD_X
        # objectives
        x = MARGIN
        self.card(x, y, COL_W, h, "Objectives", "objectives")
        heights = self._objective_heights()
        extra = content_h - self._obj_natural
        gap = self.OBJ_GAP + extra / (len(heights) - 1) if extra > 0 and len(heights) > 1 else self.OBJ_GAP
        cy = y + CARD_PAD_TOP
        tw = inner - 2 * self.OBJ_PAD - self.OBJ_BADGE - 1.0
        for i, oh in enumerate(heights):
            sx = x + CARD_PAD_X
            self.rect(sx, cy, inner, oh, fill=BG, radius=0.7, name=f"objective {i + 1}")
            self.rect(sx, cy, 0.45, oh, fill=AMBER, name=f"objective {i + 1} accent")
            self.badge(sx + self.OBJ_PAD, cy + self.OBJ_PAD, self.OBJ_BADGE, str(i + 1), fill=AMBER,
                       color=NAVY, size=48, name=f"objective {i + 1} number")
            paras = self._objective_paras(i)
            th = self.m.height(paras, tw, 6)
            self.text(sx + self.OBJ_PAD + self.OBJ_BADGE + 1.0, cy + (oh - th) / 2, tw, th, paras,
                      space_after=6, name=f"objective {i + 1} text")
            cy += oh + gap
        # methodology
        x = MARGIN + COL_W + COL_GAP
        self.card(x, y, COL_W, h, "Methodology", "methodology")
        intro_h, sub_h, rows, note_h, tw = self._method_parts()
        extra = max(0.0, content_h - self._meth_natural)
        row_gap = 0.55 + extra / (len(rows) + 1)
        cx = x + CARD_PAD_X
        cy = y + CARD_PAD_TOP
        self.text(cx, cy, inner, intro_h, METHOD, space_after=10, name="methodology text")
        cy += intro_h + 1.1
        self.text(cx, cy, inner, sub_h, [[("How Mirsad works: five layers", St(size=SUB_PT, bold=True, color=TEAL))]],
                  name="layers heading")
        cy += sub_h + 0.6
        for i, rh in enumerate(rows):
            self.badge(cx, cy + (rh - self.LAYER_BADGE) / 2, self.LAYER_BADGE, str(i + 1), fill=TEAL, color=WHITE,
                       size=34, name=f"layer {i + 1} number")
            th = self.m.height([self._layer_para(i)], tw)
            self.text(cx + self.LAYER_BADGE + 0.9, cy + (rh - th) / 2, tw, th, [self._layer_para(i)],
                      name=f"layer {i + 1} text")
            cy += rh + row_gap
        cy += 0.9 - 0.55
        self.rect(cx, cy - 0.45, inner, 0.12, fill=LINE, name="layers rule")
        self.text(cx, cy, inner, note_h, [[body(LAYERS_NOTE, bold=True, color=TEAL)]], name="layers note")
        return h

    # ------------------------------------------------------------- figures (one row of four)

    FIG_ORDER = ("architecture", "dashboard", "pwa_detail", "pwa_pending")
    FIG_GAP = 1.6
    CAP_GAP = 0.6

    def _fig_widths(self, hf: float) -> list[float]:
        return [hf * self.aspect(FIGURES[key]) for key in self.FIG_ORDER]

    def fig_max_height(self) -> float:
        total_aspect = sum(self.aspect(FIGURES[key]) for key in self.FIG_ORDER)
        return (CONTENT_W - self.FIG_GAP * (len(self.FIG_ORDER) - 1)) / total_aspect

    def _caption_h(self, hf: float) -> float:
        return max(self.m.height(self.caption_paras(i + 1, key), w)
                   for i, (key, w) in enumerate(zip(self.FIG_ORDER, self._fig_widths(hf), strict=True)))

    def fig_band_height(self, hf: float) -> float:
        return hf + self.CAP_GAP + self._caption_h(hf)

    def draw_figures(self, y: float, hf: float) -> float:
        widths = self._fig_widths(hf)
        gap = self.FIG_GAP
        x = MARGIN + (CONTENT_W - sum(widths) - gap * (len(widths) - 1)) / 2
        cap_h = self._caption_h(hf)
        for i, (key, w) in enumerate(zip(self.FIG_ORDER, widths, strict=True)):
            number = i + 1
            self.picture(FIGURES[key], x, y, w, hf, f"Figure {number}: {CAPTIONS[key]}")
            self.text(x, y + hf + self.CAP_GAP, w, cap_h, self.caption_paras(number, key), align=PP_ALIGN.CENTER,
                      name=f"figure {number} caption")
            x += w + gap
        return self.fig_band_height(hf)

    # ------------------------------------------------------------- results

    TILE_GAP = 0.9
    TILE_PAD = 0.7
    TILE_COLS = 6
    ACCENT_H = 0.45

    def _tile_parts(self, t: Tile, width: float) -> tuple[list[Para], list[Para], list[Para], float, float, float]:
        inner = width - 2 * self.TILE_PAD
        if t.pending:  # "pending" / "team data" on two deliberate lines
            first, _, rest = t.value.partition(" ")
            value: list[Para] = [[(first, St(size=34, bold=True, color=AMBER_DARK))]]
            if rest:
                value.append([(rest, St(size=34, bold=True, color=AMBER_DARK))])
        else:
            value = [[(t.value, St(size=VALUE_PT, bold=True, color=NAVY))]]
        value_h = max(VALUE_PT * LINE_FACTOR * CM_PER_PT * FIT_SLACK, self.m.height(value, inner))
        label: list[Para] = [[(t.label, St(size=LABEL_PT, bold=True, color=INK))]]
        detail: list[Para] = [[(t.detail, St(size=LABEL_PT, color=MUTED))]]
        return value, label, detail, value_h, self.m.height(label, inner), self.m.height(detail, inner)

    def _tile_height(self, t: Tile, width: float) -> float:
        _, _, _, vh, lh, dh = self._tile_parts(t, width)
        return self.ACCENT_H + self.TILE_PAD + vh + 0.2 + lh + 0.1 + dh + self.TILE_PAD

    def _note_paras(self) -> list[Para]:
        r = self.results
        mode = str(r.get("latency.separate_process.detector_mode") or "unknown").replace("_", "-")
        return [[("Read at build time from ", St(size=LABEL_PT, color=WHITE)),
                 ("results_summary.json", St(size=LABEL_PT, bold=True, color=WHITE)),
                 (f" ({r.generated()}). Benign tasks only; detector in {mode} mode.", St(size=LABEL_PT, color=WHITE))]]

    def _results_layout(self) -> dict[str, Any]:
        inner = CONTENT_W - 2 * CARD_PAD_X
        tiles = result_tiles(self.results)
        tile_w = (inner - (self.TILE_COLS - 1) * self.TILE_GAP) / self.TILE_COLS
        slots: list[Tile | None] = [*tiles, None]  # the last slot holds the data note
        rows = [slots[i:i + self.TILE_COLS] for i in range(0, len(slots), self.TILE_COLS)]
        note_h = self.m.height(self._note_paras(), tile_w - 2 * self.TILE_PAD) + 2 * self.TILE_PAD
        row_h = [max(self._tile_height(t, tile_w) if t else note_h for t in row) for row in rows]
        grid_h = sum(row_h) + self.TILE_GAP * (len(rows) - 1)
        return dict(rows=rows, row_h=row_h, grid_h=grid_h, tile_w=tile_w)

    def results_height(self) -> float:
        return CARD_PAD_TOP + self._results_layout()["grid_h"] + CARD_PAD_BOTTOM

    def draw_results(self, y: float) -> float:
        h = self.results_height()
        lay = self._results_layout()
        self.card(MARGIN, y, CONTENT_W, h, "Results", "results")
        x0 = MARGIN + CARD_PAD_X
        cy = y + CARD_PAD_TOP
        tw = lay["tile_w"]
        for r_i, row in enumerate(lay["rows"]):
            rh = lay["row_h"][r_i]
            for c_i, t in enumerate(row):
                tx = x0 + c_i * (tw + self.TILE_GAP)
                if t is None:
                    self.rect(tx, cy, tw, rh, fill=NAVY, radius=0.6, name="results note tile")
                    paras = self._note_paras()
                    nh = self.m.height(paras, tw - 2 * self.TILE_PAD)
                    self.text(tx + self.TILE_PAD, cy + (rh - nh) / 2, tw - 2 * self.TILE_PAD, nh, paras,
                              name="results note")
                else:
                    self._draw_tile(t, tx, cy, tw, rh)
            cy += rh + self.TILE_GAP
        return h

    def _draw_tile(self, t: Tile, x: float, y: float, w: float, h: float) -> None:
        accent = AMBER if t.pending else TEAL
        self.rect(x, y, w, h, fill=AMBER_TINT if t.pending else BG, radius=0.6, name=f"tile {t.label}")
        self.rect(x + 0.6, y, w - 1.2, self.ACCENT_H, fill=accent, name=f"tile {t.label} accent")
        value, label, detail, vh, lh, dh = self._tile_parts(t, w)
        inner = w - 2 * self.TILE_PAD
        ty = y + self.ACCENT_H + self.TILE_PAD
        self.text(x + self.TILE_PAD, ty, inner, vh, value, anchor=MSO_ANCHOR.MIDDLE, name=f"tile {t.label} value")
        ty += vh + 0.2
        self.text(x + self.TILE_PAD, ty, inner, lh, label, name=f"tile {t.label} label")
        ty += lh + 0.1
        self.text(x + self.TILE_PAD, ty, inner, dh, detail, name=f"tile {t.label} detail")

    # ------------------------------------------------------------- conclusion | future directions

    BULLET_D = 0.75
    BULLET_GAP = 0.65

    def _future_rows(self) -> tuple[list[float], float]:
        inner = COL_W - 2 * CARD_PAD_X
        tw = inner - self.BULLET_D - 0.8
        return [self.m.height([[body(f)]], tw) for f in FUTURE], tw

    def closing_height(self) -> float:
        inner = COL_W - 2 * CARD_PAD_X
        concl = self.m.height(conclusion(self.results), inner)
        rows, _ = self._future_rows()
        fut = sum(rows) + self.BULLET_GAP * (len(rows) - 1)
        self._concl_natural, self._fut_natural = concl, fut
        return CARD_PAD_TOP + max(concl, fut) + CARD_PAD_BOTTOM

    def draw_closing(self, y: float) -> float:
        h = self.closing_height()
        inner = COL_W - 2 * CARD_PAD_X
        content_h = h - CARD_PAD_TOP - CARD_PAD_BOTTOM
        x = MARGIN
        self.card(x, y, COL_W, h, "Conclusion", "conclusion")
        paras = conclusion(self.results)
        ch = self.m.height(paras, inner)
        self.text(x + CARD_PAD_X, y + CARD_PAD_TOP + (content_h - ch) / 2, inner, ch, paras, name="conclusion text")
        x = MARGIN + COL_W + COL_GAP
        self.card(x, y, COL_W, h, "Future Directions", "future")
        rows, tw = self._future_rows()
        extra = max(0.0, content_h - self._fut_natural)
        gap = self.BULLET_GAP + extra / (len(rows) - 1) if len(rows) > 1 else 0
        cy = y + CARD_PAD_TOP
        line_h = BODY_PT * LINE_FACTOR * CM_PER_PT
        for i, rh in enumerate(rows):
            self.badge(x + CARD_PAD_X, cy + (line_h - self.BULLET_D) / 2, self.BULLET_D, "", fill=AMBER,
                       color=NAVY, size=10, name=f"future {i + 1} bullet")
            self.text(x + CARD_PAD_X + self.BULLET_D + 0.8, cy, tw, rh, [[body(FUTURE[i])]], name=f"future {i + 1}")
            cy += rh + gap
        return h

    # ------------------------------------------------------------- footer

    def draw_footer(self) -> None:
        y = SLIDE_H - FOOTER_H
        self.rect(0, y, SLIDE_W, FOOTER_H, fill=NAVY, name="footer band")
        self.rect(0, y, SLIDE_W, 0.3, fill=TEAL, name="footer rule")
        st = St(size=FOOTER_PT, color=NAVY_SOFT)
        paras: list[Para] = [[("Prince Sultan University  ·  College of Computer & Information Sciences  ·  "
                               "IS499 Senior Project 2026–2027  ·  Open source under Apache-2.0", st)]]
        th = self.m.height(paras, CONTENT_W)
        self.text(MARGIN, y + 0.15 + (FOOTER_H - th) / 2, CONTENT_W, th, paras, align=PP_ALIGN.CENTER, name="footer")

    # ------------------------------------------------------------- assembly

    def build(self) -> dict[str, float]:
        header_h = self.header_height()
        intro_h = self.intro_height()
        objmeth_h = self.objmeth_height()
        results_h = self.results_height()
        closing_h = self.closing_height()
        # gaps: header->intro, intro->objmeth, objmeth->figures, figures->results, results->closing, closing->footer
        min_gaps = [CARD_GAP_MIN, CARD_GAP_MIN, PLAIN_GAP_MIN, CARD_GAP_MIN, CARD_GAP_MIN, PLAIN_GAP_MIN]
        fixed = header_h + intro_h + objmeth_h + results_h + closing_h + FOOTER_H + sum(min_gaps)
        avail = SLIDE_H - fixed
        hf = self.fig_max_height()
        while hf > 8 and self.fig_band_height(hf) > avail:
            hf -= 0.1
        band_h = self.fig_band_height(hf)
        slack = avail - band_h
        if slack < -0.01:
            self.warnings.append(f"content is {-slack:.1f} cm taller than the poster")
        if hf < self.fig_max_height() - 0.05:
            print(f"  NOTE figures scaled to {hf:.1f} cm height to fit (max {self.fig_max_height():.1f} cm)")
        gaps = [g + max(0.0, slack) / len(min_gaps) for g in min_gaps]

        self._header(draw=True)
        y = header_h + gaps[0]
        y += self.draw_intro(y) + gaps[1]
        y += self.draw_objmeth(y) + gaps[2]
        y += self.draw_figures(y, hf) + gaps[3]
        y += self.draw_results(y) + gaps[4]
        y += self.draw_closing(y) + gaps[5]
        self.draw_footer()
        return {"header": header_h, "intro": intro_h, "objmeth": objmeth_h, "figures": band_h, "fig_h": hf,
                "results": results_h, "closing": closing_h, "slack_per_gap": max(0.0, slack) / len(min_gaps),
                "bottom": y}

    def save(self, out: Path) -> None:
        props = self.prs.core_properties
        props.title = "Mirsad | مرصاد – IS499 poster"
        props.author = "Mirsad team, Prince Sultan University"
        props.subject = "A Runtime Security Firewall for AI Agents Against Prompt-Injection Attacks"
        props.keywords = "Mirsad; prompt injection; AI agents; IS499"
        out.parent.mkdir(parents=True, exist_ok=True)
        self.prs.save(str(out))


def check_content(r: Results) -> list[str]:
    """Word-count limits from the poster brief."""
    problems = []
    n = words_in(INTRO)
    if not 70 <= n <= 90:
        problems.append(f"introduction has {n} words (70-90 required)")
    n = words_in(conclusion(r))
    if not 60 <= n <= 80:
        problems.append(f"conclusion has {n} words (60-80 required)")
    if len(FUTURE) != 4:
        problems.append("future directions must have 4 bullets")
    return problems


# ----------------------------------------------------------------------------- preview (macOS + PowerPoint)

APPLESCRIPT = """
on run argv
    set pptxPath to item 1 of argv
    set pdfPath to item 2 of argv
    set pptxName to item 3 of argv
    with timeout of 600 seconds
        tell application "Microsoft PowerPoint"
            open (POSIX file pptxPath)
            set opened to false
            set waited to 0
            repeat while (not opened) and waited < 120
                try
                    get name of presentation pptxName
                    set opened to true
                on error
                    delay 1
                    set waited to waited + 1
                end try
            end repeat
            if not opened then error "presentation did not open"
            -- referenced by name, so other open presentations are never touched
            save presentation pptxName in ((POSIX file pdfPath) as text) as save as PDF
            close presentation pptxName saving no
        end tell
    end timeout
end run
"""

CLOSE_SCRIPT = """
on run argv
    with timeout of 30 seconds
        tell application "Microsoft PowerPoint"
            try
                close presentation (item 1 of argv) saving no
            end try
        end tell
    end timeout
end run
"""


def export_pdf(pptx: Path, pdf: Path, *, timeout_s: int = 300) -> None:
    """Export ``pptx`` to ``pdf`` with PowerPoint. PowerPoint is sandboxed, so the work happens in its
    container; if PowerPoint hangs it is quit and the export retried once."""
    work = PPT_CONTAINER / "mirsad_poster"
    work.mkdir(parents=True, exist_ok=True)
    name = f"mirsad_poster_{os.getpid()}.pptx"
    work_pptx, work_pdf = work / name, work / name.replace(".pptx", ".pdf")
    shutil.copyfile(pptx, work_pptx)
    script = work.parent / "mirsad_poster_export.applescript"
    script.write_text(APPLESCRIPT, encoding="utf-8")
    try:
        for attempt in (1, 2):
            work_pdf.unlink(missing_ok=True)
            try:
                # fixed argument list, no shell; the paths are our own working copies
                proc = subprocess.run([OSASCRIPT, str(script), str(work_pptx), str(work_pdf), name],  # noqa: S603
                                      capture_output=True, text=True, timeout=timeout_s)
                ok = proc.returncode == 0 and work_pdf.exists()
                if not ok:
                    print(f"  PowerPoint export failed (attempt {attempt}): {proc.stderr.strip()[:300]}")
                    subprocess.run([OSASCRIPT, "-e", CLOSE_SCRIPT, name], capture_output=True, timeout=60)  # noqa: S603
            except subprocess.TimeoutExpired:
                ok = False
                print(f"  PowerPoint did not answer within {timeout_s} s (attempt {attempt}); quitting it")
                subprocess.run([OSASCRIPT, "-e", 'tell application "Microsoft PowerPoint" to quit saving no'],  # noqa: S603
                               capture_output=True, timeout=60)
                time.sleep(5)
            if ok:
                for _ in range(20):  # PowerPoint may still be flushing the file
                    size = work_pdf.stat().st_size
                    time.sleep(0.5)
                    if size and size == work_pdf.stat().st_size:
                        break
                pdf.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(work_pdf), pdf)
                return
        raise RuntimeError("PowerPoint could not export the poster to PDF")
    finally:
        work_pptx.unlink(missing_ok=True)
        script.unlink(missing_ok=True)


def render_quicklook(pptx: Path, png: Path, *, height_px: int = 4000) -> None:
    """Render the slide with macOS Quick Look (no PowerPoint automation involved)."""
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "poster.pptx"
        shutil.copyfile(pptx, src)
        subprocess.run([QLMANAGE, "-t", "-s", str(height_px), "-o", tmp, str(src)],  # noqa: S603
                       capture_output=True, timeout=300, check=False)
        out = Path(tmp) / "poster.pptx.png"
        if not out.exists():
            raise RuntimeError("Quick Look could not render the poster")
        png.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(out) as img:
            img.convert("RGB").save(png, optimize=True)


def render_png(pdf: Path, png: Path, *, width_px: int = 2400) -> None:
    import fitz  # PyMuPDF

    with fitz.open(str(pdf)) as doc:
        page = doc[0]
        zoom = width_px / page.rect.width
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        png.parent.mkdir(parents=True, exist_ok=True)
        pix.save(str(png))


# ----------------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--results", type=Path, default=RESULTS)
    ap.add_argument("--preview", action="store_true", help="export a PDF with PowerPoint and render a PNG preview")
    ap.add_argument("--preview-out", type=Path, default=DEFAULT_PREVIEW)
    ap.add_argument("--keep-pdf", type=Path, default=None, help="also keep the exported PDF at this path")
    ap.add_argument("--renderer", choices=("powerpoint", "quicklook"), default="powerpoint",
                    help="how --preview renders the slide (default: PowerPoint PDF export + PyMuPDF)")
    args = ap.parse_args(argv)

    for path in [PSU_LOGO, APP_ICON, *FIGURES.values()]:
        if not path.exists():
            print(f"error: missing asset {path.relative_to(ROOT)}", file=sys.stderr)
            return 1
    results = Results(args.results)
    problems = check_content(results)
    poster = Poster(results)
    layout = poster.build()
    poster.save(args.out)
    print(f"wrote {args.out.relative_to(ROOT) if args.out.is_relative_to(ROOT) else args.out}")
    print("  layout (cm): " + ", ".join(f"{k}={v:.1f}" for k, v in layout.items()))
    for msg in [*problems, *poster.warnings]:
        print(f"  WARNING {msg}")

    if args.preview and args.renderer == "quicklook":
        render_quicklook(args.out, args.preview_out)
        print(f"wrote {args.preview_out} (Quick Look)")
    elif args.preview:
        with tempfile.TemporaryDirectory() as tmp:
            pdf = args.keep_pdf or Path(tmp) / "poster.pdf"
            export_pdf(args.out, pdf)
            render_png(pdf, args.preview_out)
        print(f"wrote {args.preview_out} (PowerPoint)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
