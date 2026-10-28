"""Build the Mirsad final presentation (16:9 PowerPoint) from the project's own data.

Every measured number is read from ``reports/results_summary.json`` (and, for the benchmark language
split, ``reports/bench/*/summary.json``) when the deck is built; values that have not been measured
yet are shown as "pending". Requirement and sprint counts, the policy excerpt, taint actions, the
approval timeout and the Gantt chart come from the repository sources, and the speaker notes of
every slide are copied from ``docs/presentation_script.md`` (sections ``### Slide N – Title``).

Usage::

    python scripts/build_slides.py [--out deliverables/Mirsad_Final_Presentation.pptx] [--no-fit-check]

The fit check estimates, with the Calibri/Consolas metrics shipped with Microsoft Office when they
are installed, whether any text box overflows; it only prints warnings.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "deliverables" / "Mirsad_Final_Presentation.pptx"
RESULTS = ROOT / "reports" / "results_summary.json"
SCRIPT_MD = ROOT / "docs" / "presentation_script.md"
POLICY = ROOT / "configs" / "policies" / "default.yaml"
PLAN = ROOT / "docs" / "pm" / "plan.yaml"
REQUIREMENTS = ROOT / "docs" / "report" / "content" / "parts" / "requirements_fr_nfr.md"
SPRINTS = ROOT / "docs" / "report" / "content" / "ch3_4.md"
RULES_DIR = ROOT / "src" / "mirsad" / "detector" / "rules"
FIG = ROOT / "docs" / "figures"
PSU_LOGO = ROOT / "docs" / "report" / "assets" / "psu_logo.png"
APP_ICON = ROOT / "web" / "public" / "assets" / "icons" / "icon-512.png"
OFFICE_FONTS = Path("/Applications/Microsoft PowerPoint.app/Contents/Resources/DFonts")

# ----------------------------------------------------------------------------- brand

NAVY = RGBColor(0x0B, 0x1F, 0x3A)
TEAL = RGBColor(0x0F, 0x76, 0x6E)
TEAL_LIGHT = RGBColor(0x2D, 0xD4, 0xBF)
AMBER = RGBColor(0xF5, 0x9E, 0x0B)
AMBER_DARK = RGBColor(0x92, 0x40, 0x0E)
RED = RGBColor(0xB9, 0x1C, 0x1C)
INK = RGBColor(0x1F, 0x29, 0x37)
MUTED = RGBColor(0x5B, 0x64, 0x72)
LINE = RGBColor(0xD5, 0xDB, 0xE3)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
TINT = RGBColor(0xF3, 0xF6, 0xFA)       # neutral card
TEAL_TINT = RGBColor(0xE6, 0xF2, 0xF1)
AMBER_TINT = RGBColor(0xFE, 0xF3, 0xC7)
RED_TINT = RGBColor(0xFD, 0xEC, 0xEC)
GREY_TINT = RGBColor(0xEE, 0xF1, 0xF5)
SLATE = RGBColor(0x94, 0xA3, 0xB8)

FONT = "Arial"  # ships with macOS, Windows and Office, so previews and every laptop render identically
MONO = "Courier New"  # available on macOS and Windows, unlike Consolas
ARABIC_FONT = "Arial"
SLIDE_W, SLIDE_H = 13.333, 7.5
MARGIN = 0.6
CONTENT_W = SLIDE_W - 2 * MARGIN
PENDING = "pending"

TEAM = [  # name, student ID (SPAP form)
    ("Mohammed Yasser Alanssari", "221110935"),
    ("Bader Alshuraie", "221110016"),
    ("Bader Abdullah Abbod Alyamini", "221110197"),
    ("Abdulmalik bin Saedan", "221110958"),
    ("Abdullah Naif Abdullah Al-Orabi", "222110432"),
]
SUPERVISOR = "Dr. Omaia Al-Omari"


# ----------------------------------------------------------------------------- data access


class Results:
    """Dotted-path access to reports/results_summary.json; missing or null values are ``None``."""

    def __init__(self, path: Path):
        self.data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if not self.data:
            print(f"  WARNING {path} not found: every result will show as pending")

    def get(self, dotted: str) -> Any:
        node: Any = self.data
        for part in dotted.split("."):
            if isinstance(node, dict):
                node = node.get(part)
            elif isinstance(node, list):
                try:
                    node = node[int(part)]
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return node

    def fmt(self, dotted: str, spec: str = "", suffix: str = "") -> str:
        value = self.get(dotted)
        if value is None:
            return PENDING
        try:
            return format(value, spec) + suffix
        except (TypeError, ValueError):
            return str(value) + suffix

    def attack_reduction(self) -> float | None:
        """ASR reduction of the full configuration in any benchmark run that executed attack episodes."""
        for run in (self.get("bench") or {}).values():
            value = ((run or {}).get("configs") or {}).get("full", {}).get("asr_reduction")
            if value is not None:
                return value
        return None


VALUE_RE = re.compile(r"\{\{(?P<file>[^#{}]+)#(?P<path>[^|{}]+)(?:\|(?P<fmt>[^{}]+))?\}\}")


def resolve_placeholders(text: str) -> str:
    """Same semantics as scripts/build_docs.py: ``{{reports/x.json#a.b|fmt}}`` -> value or [pending]."""
    cache: dict[Path, Any] = {}

    def sub(m: re.Match) -> str:
        file = ROOT / m.group("file").strip()
        if file not in cache:
            cache[file] = json.loads(file.read_text(encoding="utf-8")) if file.exists() else None
        node = cache[file]
        for part in m.group("path").strip().split("."):
            node = node.get(part) if isinstance(node, dict) else None
        if node is None:
            return "[pending]"
        fmt = m.group("fmt")
        try:
            return format(node, fmt) if fmt else str(node)
        except (TypeError, ValueError):
            return str(node)

    return VALUE_RE.sub(sub, text)


def load_notes(path: Path) -> dict[int, str]:
    """Speaker notes per slide number from the '### Slide N – Title' sections of the script."""
    text = path.read_text(encoding="utf-8")
    heads = list(re.finditer(r"^### Slide (\d+) – .+$", text, re.M))
    notes: dict[int, str] = {}
    for m in heads:
        nxt = re.search(r"^#{2,3} ", text[m.end():], re.M)
        body = text[m.end(): m.end() + nxt.start()] if nxt else text[m.end():]
        body = resolve_placeholders(body)
        body = re.sub(r"\s*\[@[^\]]+\]", "", body)            # citations are for the written report
        body = re.sub(r"\*\*([^*]+)\*\*", r"\1", body)
        body = re.sub(r"(?<!\w)\*([^*\s][^*]*)\*", r"\1", body)
        body = body.replace("`", "")
        paras = [" ".join(p.split()) for p in re.split(r"\n\s*\n", body) if p.strip()]
        notes[int(m.group(1))] = "\n\n".join(paras)
    return notes


def requirement_counts() -> tuple[dict[str, int], int]:
    groups: dict[str, int] = {}
    nfr = 0
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\|\s*(FR\d+)\.\d+\s*\|", line)
        if m:
            groups[m.group(1)] = groups.get(m.group(1), 0) + 1
        elif re.match(r"^\|\s*NFR\d+\s*\|", line):
            nfr += 1
    return groups, nfr


def sprint_count() -> int:
    return len(re.findall(r"^\|\s*S\d+\s*\|", SPRINTS.read_text(encoding="utf-8"), re.M))


def detector_rule_count() -> int:
    total = 0
    for f in sorted(RULES_DIR.glob("*.yaml")):
        doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        if isinstance(doc, dict) and isinstance(doc.get("rules"), list):
            total += len(doc["rules"])
    return total


def bench_meta(run: str) -> dict[str, Any]:
    path = ROOT / "reports" / "bench" / run / "summary.json"
    return json.loads(path.read_text(encoding="utf-8")).get("meta", {}) if path.exists() else {}


POLICY_EXCERPT = """\
send_email:
  allow: true
  sink: dynamic
  sink_params: [to, cc, bcc]
  risk: medium
  constraints:
    to: {domain_in: [najd-trading.example],
         on_violation: require_approval}
delete_customer:
  {risk: critical, approval: always}
"*": {allow: false}"""


def check_excerpt(policy: dict[str, Any]) -> None:
    """Warn if the policy excerpt shown on the slide is no longer a subset of the shipped policy."""
    tools = policy["agents"][0]["tools"]

    def subset(a: Any, b: Any) -> bool:
        if isinstance(a, dict):
            return isinstance(b, dict) and all(k in b and subset(v, b[k]) for k, v in a.items())
        return a == b

    if not subset(yaml.safe_load(POLICY_EXCERPT), tools):
        print("  WARNING the policy excerpt on slide 9 no longer matches configs/policies/default.yaml")


# ----------------------------------------------------------------------------- text-fit estimate


@dataclass
class FitItem:
    slide: int
    name: str
    paragraphs: list[tuple[str, float, bool, str]]   # text, size pt, bold, font
    width: float
    height: float


@dataclass
class FitChecker:
    items: list[FitItem] = field(default_factory=list)
    fonts: dict[tuple[str, bool], Any] = field(default_factory=dict)
    broken_words: list[str] = field(default_factory=list)

    def _font(self, family: str, bold: bool):
        key = (family, bold)
        if key not in self.fonts:
            name = {("Calibri", False): "Calibri.ttf", ("Calibri", True): "Calibrib.ttf",
                    ("Consolas", False): "Consola.ttf", ("Consolas", True): "Consolab.ttf"}.get(key)
            path = OFFICE_FONTS / name if name else None
            system = {("Arial", False): "Arial.ttf", ("Arial", True): "Arial Bold.ttf",
                      ("Courier New", False): "Courier New.ttf", ("Courier New", True): "Courier New Bold.ttf"}.get(key)
            if system:
                path = Path("/System/Library/Fonts/Supplemental") / system
            self.fonts[key] = ImageFont.truetype(str(path), 100) if path and path.exists() else None
        return self.fonts[key]

    def lines(self, text: str, size: float, bold: bool, family: str, width_in: float) -> int | None:
        font = self._font(family, bold)
        if font is None or re.search(r"[؀-ۿ]", text):
            return None
        scale = size / 100.0
        limit = width_in * 72.0
        count = 0
        for raw in text.split("\n"):
            words = raw.split(" ")
            line = ""
            count += 1
            for word in words:
                if font.getlength(word) * scale > limit:
                    self.broken_words.append(word)       # PowerPoint would break this word mid-way
                trial = f"{line} {word}".strip()
                if font.getlength(trial) * scale <= limit or not line:
                    line = trial
                else:
                    count += 1
                    line = word
        return count

    def report(self) -> int:
        problems = 0
        for it in self.items:
            total = 0.0
            self.broken_words = []
            for text, size, bold, family in it.paragraphs:
                n = self.lines(text, size, bold, family, it.width)
                if n is None:
                    total = -1
                    break
                total += n * size * 1.2 / 72.0
            if total > it.height + 0.02:
                problems += 1
                print(f"  FIT slide {it.slide}: '{it.name}' needs ~{total:.2f} in, box is {it.height:.2f} in")
            if self.broken_words:
                problems += 1
                print(f"  FIT slide {it.slide}: '{it.name}' is too narrow for {self.broken_words}")
        return problems


# ----------------------------------------------------------------------------- deck builder


class Deck:
    def __init__(self, results: Results, notes: dict[int, str], tmp: Path, fit: FitChecker):
        self.r = results
        self.notes = notes
        self.tmp = tmp
        self.fit = fit
        self.prs = Presentation()
        self.prs.slide_width = Inches(SLIDE_W)
        self.prs.slide_height = Inches(SLIDE_H)
        self.slide_no = 0
        self.total = 0
        self.policy = yaml.safe_load(POLICY.read_text(encoding="utf-8"))
        check_excerpt(self.policy)

    # ------------------------------------------------------------- primitives

    def new_slide(self, title: str, kicker: str | None = None, *, dark: bool = False):
        self.slide_no += 1
        slide = self.prs.slides.add_slide(self.prs.slide_layouts[5])   # "Title Only": real title placeholder
        if dark:
            bg = slide.background.fill
            bg.solid()
            bg.fore_color.rgb = NAVY
        t = slide.shapes.title
        t.left, t.top, t.width, t.height = Inches(MARGIN), Inches(0.62), Inches(CONTENT_W), Inches(0.8)
        tf = t.text_frame
        tf.word_wrap = True
        tf.auto_size = MSO_AUTO_SIZE.NONE
        tf.vertical_anchor = MSO_ANCHOR.TOP
        for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
            setattr(tf, side, 0)
        tf.text = title
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        for run in p.runs:
            self._style_run(run, 30, NAVY if not dark else WHITE, True, FONT)
        self.fit.items.append(FitItem(self.slide_no, "title", [(title, 30, True, FONT)], CONTENT_W, 0.8))
        if kicker:
            self.text(slide, MARGIN, 0.3, 8.0, 0.3, kicker.upper(), size=12, color=TEAL, bold=True,
                      spacing=150, name="kicker")
        return slide

    @staticmethod
    def _style_run(run, size: float, color: RGBColor, bold: bool, font: str, *, spacing: int | None = None,
                   italic: bool = False) -> None:
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.italic = italic
        run.font.name = font
        run.font.color.rgb = color
        r_pr = run._r.get_or_add_rPr()
        if spacing:
            r_pr.set("spc", str(spacing))
        if re.search(r"[؀-ۿ]", run.text or ""):
            r_pr.set("lang", "ar-SA")
            cs = r_pr.find(qn("a:cs"))
            if cs is None:
                cs = r_pr.makeelement(qn("a:cs"), {})
                r_pr.append(cs)
            cs.set("typeface", ARABIC_FONT)

    def text(self, slide, x: float, y: float, w: float, h: float, content, *, size: float = 18,
             color: RGBColor = INK, bold: bool = False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
             font: str = FONT, spacing: int | None = None, space_after: float = 0, line_spacing: float | None = None,
             rtl: bool = False, name: str = "text", italic: bool = False):
        """Add a text box. ``content`` is a string (paragraphs split on '\\n') or a list of paragraphs,
        each a string or a list of (text, {size,color,bold,font,italic}) runs."""
        box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        box.name = name
        tf = box.text_frame
        tf.word_wrap = True
        tf.auto_size = MSO_AUTO_SIZE.NONE
        tf.vertical_anchor = anchor
        for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
            setattr(tf, side, 0)
        paras = content.split("\n") if isinstance(content, str) else content
        fit_paras = []
        for i, para in enumerate(paras):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            if space_after:
                p.space_after = Pt(space_after)
            if line_spacing:
                p.line_spacing = line_spacing
            if rtl:
                p._p.get_or_add_pPr().set("rtl", "1")
            runs = [(para, {})] if isinstance(para, str) else para
            joined = ""
            max_size = size
            any_bold = bold
            fam = font
            for txt, opts in runs:
                run = p.add_run()
                run.text = txt
                rs = opts.get("size", size)
                self._style_run(run, rs, opts.get("color", color), opts.get("bold", bold), opts.get("font", font),
                                spacing=opts.get("spacing", spacing), italic=opts.get("italic", italic))
                joined += txt
                max_size = max(max_size, rs)
                any_bold = any_bold or opts.get("bold", False)
                fam = opts.get("font", font)
            fit_paras.append((joined, max_size, any_bold, fam))
        self.fit.items.append(FitItem(self.slide_no, name, fit_paras, w, h))
        return box

    def shape(self, slide, x: float, y: float, w: float, h: float, *, fill: RGBColor | None = None,
              line: RGBColor | None = None, line_w: float = 1.0, radius: float | None = None,
              kind=MSO_SHAPE.RECTANGLE, name: str = "shape"):
        auto = MSO_SHAPE.ROUNDED_RECTANGLE if radius else kind
        shp = slide.shapes.add_shape(auto, Inches(x), Inches(y), Inches(w), Inches(h))
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
            shp.line.width = Pt(line_w)
        shp.shadow.inherit = False
        shp.text_frame.text = ""
        return shp

    def circle_label(self, slide, x: float, y: float, d: float, label: str, *, fill: RGBColor = TEAL,
                     color: RGBColor = WHITE, size: float = 18, name: str = "badge"):
        c = self.shape(slide, x, y, d, d, fill=fill, kind=MSO_SHAPE.OVAL, name=name)
        tf = c.text_frame
        for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
            setattr(tf, side, 0)
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.word_wrap = False
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run()
        run.text = label
        self._style_run(run, size, color, True, FONT)
        return c

    def chip(self, slide, x: float, y: float, w: float, h: float, label: str, kind: str, *, size: float = 14):
        fill, color = {"yes": (TEAL, WHITE), "met": (TEAL, WHITE), "partial": (AMBER_TINT, AMBER_DARK),
                       "approval": (AMBER_TINT, AMBER_DARK), "pending": (AMBER_TINT, AMBER_DARK),
                       "no": (GREY_TINT, MUTED), "na": (GREY_TINT, MUTED), "deny": (RED_TINT, RED),
                       "notmet": (RED_TINT, RED)}[kind]
        s = self.shape(slide, x, y, w, h, fill=fill, radius=h / 2, name=f"chip {label}")
        tf = s.text_frame
        for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
            setattr(tf, side, 0)
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run()
        run.text = label
        self._style_run(run, size, color, True, FONT)
        return s

    def arrow(self, slide, x: float, y: float, w: float = 0.32, h: float = 0.32, color: RGBColor = SLATE):
        return self.shape(slide, x, y, w, h, fill=color, kind=MSO_SHAPE.RIGHT_ARROW, name="arrow")

    def picture(self, slide, path: Path, x: float, y: float, *, w: float | None = None, h: float | None = None,
                alt: str = ""):
        pic = slide.shapes.add_picture(str(path), Inches(x), Inches(y),
                                       Inches(w) if w else None, Inches(h) if h else None)
        pic._element.nvPicPr.cNvPr.set("descr", alt)
        return pic

    def framed(self, src: Path, *, max_w: int, radius: int, border: int, border_color: tuple[int, int, int],
               crop: tuple[int, int, int, int] | None = None) -> Path:
        """Screenshot with rounded corners and a border, downscaled for file size (cached in tmp)."""
        img = Image.open(src).convert("RGB")
        if crop:
            img = img.crop(crop)
        if img.width > max_w:
            img = img.resize((max_w, round(img.height * max_w / img.width)), Image.LANCZOS)
        w, h = img.size
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=255)
        out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        out.paste(img, (0, 0), mask)
        if border:
            ImageDraw.Draw(out).rounded_rectangle((border // 2, border // 2, w - 1 - border // 2, h - 1 - border // 2),
                                                  radius=radius, outline=border_color + (255,), width=border)
        dst = self.tmp / f"{src.stem}-{max_w}-{border}.png"
        out.save(dst, optimize=True)
        return dst

    def footer(self, slide) -> None:
        if APP_ICON.exists():
            self.picture(slide, APP_ICON, MARGIN, 7.02, w=0.24, alt="Mirsad logo")
        self.text(slide, MARGIN + 0.34, 7.04, 7.0, 0.24,
                  [[("Mirsad ", {}), ("مرصاد", {}), ("  ·  IS499 Senior Project  ·  Prince Sultan University", {})]],
                  size=10, color=MUTED, name="footer")
        self.text(slide, SLIDE_W - MARGIN - 1.2, 7.02, 1.2, 0.26, f"{self.slide_no} / {self.total}", size=11,
                  color=MUTED, align=PP_ALIGN.RIGHT, name="slide number")

    # ------------------------------------------------------------- slides

    def s01_title(self):
        s = self.new_slide("Mirsad")
        t = s.shapes.title
        t.left, t.top, t.width, t.height = Inches(MARGIN), Inches(2.05), Inches(7.6), Inches(1.0)
        for run in t.text_frame.paragraphs[0].runs:
            run.font.size = Pt(60)
        self.fit.items[-1] = FitItem(1, "title", [("Mirsad", 60, True, FONT)], 7.6, 1.0)
        self.picture(s, PSU_LOGO, MARGIN, 0.45, w=2.5, alt="Prince Sultan University logo")
        self.text(s, MARGIN, 1.72, 7.6, 0.3, "IS499 SENIOR PROJECT  ·  FINAL PRESENTATION", size=14, color=TEAL,
                  bold=True, spacing=120, name="kicker")
        self.text(s, MARGIN, 3.1, 7.6, 0.85,
                  "A runtime security firewall for AI agents\nagainst prompt-injection attacks",
                  size=22, color=INK, name="subtitle")
        self.text(s, MARGIN, 4.08, 7.6, 0.3, "TEAM", size=12, color=MUTED, bold=True, spacing=150, name="team label")
        for i, (name, sid) in enumerate(TEAM):
            y = 4.38 + i * 0.37
            self.text(s, MARGIN, y, 5.4, 0.36, name, size=18, color=NAVY, name=f"member {i}")
            self.text(s, MARGIN + 5.5, y, 1.6, 0.36, sid, size=18, color=MUTED, name=f"id {i}")
        self.text(s, MARGIN, 6.3, 7.6, 0.36, [[("Supervisor  ", {"color": MUTED}), (SUPERVISOR, {"bold": True})]],
                  size=18, color=NAVY, name="supervisor")
        self.text(s, MARGIN, 6.8, 7.8, 0.42,
                  "College of Computer & Information Sciences  ·  Information Systems Department  ·  "
                  "Academic Year 2026–2027", size=10.5, color=MUTED, name="college")
        # right brand panel
        px = 8.85
        self.shape(s, px, 0, SLIDE_W - px, SLIDE_H, fill=NAVY, name="brand panel")
        pw = SLIDE_W - px
        if APP_ICON.exists():
            self.picture(s, APP_ICON, px + (pw - 2.0) / 2, 1.55, w=2.0, alt="Mirsad logo: an eye under a roof")
        self.text(s, px, 3.75, pw, 0.85, "مرصاد", size=48, color=TEAL_LIGHT, bold=True, align=PP_ALIGN.CENTER,
                  rtl=True, name="arabic name")
        self.text(s, px, 4.65, pw, 0.4, "“watchtower”", size=18, color=LINE, italic=True,
                  align=PP_ALIGN.CENTER, name="meaning")
        self.text(s, px + 0.5, 5.45, pw - 1.0, 0.9,
                  "Inspects every tool call and every tool result of an AI agent",
                  size=18, color=WHITE, align=PP_ALIGN.CENTER, name="tagline")

    def s02_problem(self):
        s = self.new_slide("Agents obey instructions hidden in the data they read", "Introduction · the problem")
        steps = [
            ("Attacker plants text", "with hidden instructions in an e-mail, web page, CV or CRM note",
             TEAL, TINT),
            ("Agent reads it", "while doing a normal task for its user", TEAL, TINT),
            ("Agent acts on it", "exports data, sends money or deletes records with its own permissions",
             RED, RED_TINT),
        ]
        cw, gap, y, h = 3.55, 0.73, 1.85, 2.85
        for i, (head, body, badge, tint) in enumerate(steps):
            x = MARGIN + i * (cw + gap)
            self.shape(s, x, y, cw, h, fill=tint, radius=0.18, name=f"step card {i + 1}")
            self.circle_label(s, x + 0.35, y + 0.35, 0.62, str(i + 1), fill=badge, size=20)
            self.text(s, x + 0.35, y + 1.17, cw - 0.7, 0.45, head, size=22, color=NAVY, bold=True,
                      name=f"step head {i + 1}")
            self.text(s, x + 0.35, y + 1.7, cw - 0.7, 1.0, body, size=18, color=INK, name=f"step body {i + 1}")
            if i < 2:
                self.arrow(s, x + cw + (gap - 0.4) / 2, y + h / 2 - 0.2, 0.4, 0.4)
        self.shape(s, MARGIN, 5.15, CONTENT_W, 1.35, fill=NAVY, radius=0.18, name="callout")
        self.text(s, MARGIN + 0.45, 5.15, CONTENT_W - 0.9, 1.35,
                  [[("Firewalls, IAM and DLP ", {"bold": True, "color": TEAL_LIGHT}),
                    ("see an authorised agent making a normal API call. ", {}),
                    ("The control has to sit at the tool call.", {"bold": True})]],
                  size=20, color=WHITE, anchor=MSO_ANCHOR.MIDDLE, name="callout text")

    def s03_why(self):
        s = self.new_slide("Why this matters for Saudi organisations", "Introduction · motivation")
        cards = [
            ("#1", "LLM01", "Prompt injection is the top risk for LLM applications",
             "OWASP Top 10 for LLM Applications 2025"),
            ("§", "PDPL & ECC", "A leaking agent discloses personal data; logging and monitoring are required",
             "PDPL (2021, amended 2023); NCA ECC-2:2024"),
            ("ع", "Arabic gap", "None of the detectors we reviewed publishes Arabic accuracy results",
             "Team review of 11 products and prototypes, Oct 2026"),
        ]
        cw, gap, y, h = 3.78, 0.395, 1.8, 4.75
        for i, (glyph, head, body, src) in enumerate(cards):
            x = MARGIN + i * (cw + gap)
            self.shape(s, x, y, cw, h, fill=TINT, radius=0.18, name=f"card {i + 1}")
            self.circle_label(s, x + 0.4, y + 0.4, 0.8, glyph, fill=NAVY if i < 2 else TEAL, size=24,
                              name=f"icon {i + 1}")
            self.text(s, x + 0.4, y + 1.45, cw - 0.8, 0.6, head, size=24, color=NAVY, bold=True,
                      name=f"card head {i + 1}")
            self.text(s, x + 0.4, y + 2.15, cw - 0.8, 1.55, body, size=19, color=INK, name=f"card body {i + 1}")
            self.text(s, x + 0.4, y + h - 0.75, cw - 0.8, 0.5, src, size=12, color=MUTED, name=f"source {i + 1}")

    def s04_objectives(self):
        s = self.new_slide("Three SMART objectives, fixed before implementation", "Introduction · objectives")
        rows = [
            ("Enforce policy at the tool boundary", "MCP and OpenAI-style agents, no agent changes",
             "Median added latency ≤ 200 ms", "M5 · Mar 2027"),
            ("Detect Arabic and English injections", "MSA, Gulf dialect, Arabizi, mixed and English",
             "F1 ≥ 0.85 on held-out AR and EN tests", "M4 · Feb 2027"),
            ("Keep humans in control, prove the effect", "Approval app, replayable audit, Mirsad-Bench",
             "≥ 80% less attack success; ≤ 5% benign blocked", "M6 · Apr 2027"),
        ]
        y0, h, gap = 1.8, 1.42, 0.25
        for i, (head, sub, target, ms) in enumerate(rows):
            y = y0 + i * (h + gap)
            self.shape(s, MARGIN, y, CONTENT_W, h, fill=TINT, radius=0.16, name=f"objective {i + 1}")
            self.circle_label(s, MARGIN + 0.35, y + (h - 0.7) / 2, 0.7, str(i + 1), size=22)
            self.text(s, MARGIN + 1.3, y + 0.24, 5.6, 0.5, head, size=19, color=NAVY, bold=True,
                      name=f"objective head {i + 1}")
            self.text(s, MARGIN + 1.3, y + 0.8, 5.6, 0.4, sub, size=18, color=MUTED, name=f"objective sub {i + 1}")
            self.shape(s, MARGIN + 7.05, y + 0.28, 3.65, h - 0.56, fill=AMBER_TINT, radius=0.14,
                       name=f"target box {i + 1}")
            self.text(s, MARGIN + 7.25, y + 0.28, 3.3, h - 0.56, target, size=18, color=AMBER_DARK, bold=True,
                      anchor=MSO_ANCHOR.MIDDLE, name=f"target {i + 1}")
            self.text(s, MARGIN + 10.85, y, 1.2, h, ms.replace(" · ", "\n"), size=15, color=MUTED,
                      anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.RIGHT, name=f"milestone {i + 1}")

    def s05_related(self):
        s = self.new_slide("Existing tools cover parts of the problem", "Background · related work")
        cols = ["Lakera Guard", "AWS AgentCore", "agentgateway", "Invariant", "CaMeL", "Mirsad"]
        rows = [
            ("Per-tool and per-parameter policy", ["partial", "yes", "yes", "yes", "yes", "yes"]),
            ("Taint / data-flow tracking", ["no", "partial", "no", "partial", "yes", "yes"]),
            ("Arabic injection detection", ["yes", "partial", "no", "no", "na", "yes*"]),
            ("Human approval channel", ["no", "partial", "no", "no", "partial", "yes"]),
            ("Tamper-evident decision audit", ["no", "partial", "no", "no", "no", "yes"]),
        ]
        label_w, col_w, y0, head_h, row_h = 3.45, (CONTENT_W - 3.45) / 6, 1.62, 0.52, 0.58
        mx = MARGIN + label_w + 5 * col_w
        self.shape(s, mx + 0.05, y0 - 0.05, col_w - 0.1, head_h + 5 * row_h + 0.12, fill=TEAL_TINT, radius=0.12,
                   name="Mirsad column")
        for j, c in enumerate(cols):
            self.text(s, MARGIN + label_w + j * col_w, y0, col_w, head_h, c, size=15, color=NAVY, bold=True,
                      align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, name=f"col {c}")
        labels = {"yes": "Yes", "partial": "Partial", "no": "No", "na": "n/a", "yes*": "Yes*"}
        for i, (cap, vals) in enumerate(rows):
            y = y0 + head_h + i * row_h
            self.shape(s, MARGIN, y, CONTENT_W, 0.012, fill=LINE, name="row rule")
            self.text(s, MARGIN, y, label_w - 0.1, row_h, cap, size=17, color=INK, anchor=MSO_ANCHOR.MIDDLE,
                      name=f"row {i + 1}")
            for j, v in enumerate(vals):
                cx = MARGIN + label_w + j * col_w + (col_w - 1.05) / 2
                self.chip(s, cx, y + (row_h - 0.36) / 2, 1.05, 0.36, labels[v], v.rstrip("*"), size=13)
        y = y0 + head_h + 5 * row_h + 0.14
        self.text(s, MARGIN, y, CONTENT_W, 0.32,
                  "Yes = documented · Partial = limited, preview or tied to one platform · No = not documented · "
                  "* built; accuracy pending team data", size=13, color=MUTED, name="legend")
        self.text(s, MARGIN, y + 0.34, CONTENT_W, 0.3,
                  "Source: team review of product documentation and papers, October 2026 "
                  "(docs/research/competitive-analysis.md)", size=12, color=MUTED, name="source")
        self.shape(s, MARGIN, 6.12, CONTENT_W, 0.68, fill=NAVY, radius=0.14, name="gap box")
        self.text(s, MARGIN + 0.35, 6.12, CONTENT_W - 0.7, 0.68,
                  [[("Gap: ", {"bold": True, "color": TEAL_LIGHT}),
                    ("no reviewed system documents all five in one vendor-neutral, self-hostable component.", {})]],
                  size=19, color=WHITE, anchor=MSO_ANCHOR.MIDDLE, name="gap text")

    def s06_requirements(self):
        groups, nfr = requirement_counts()
        n_fr = sum(groups.values())
        s = self.new_slide(f"{n_fr} functional and {nfr} non-functional requirements", "Analysis · requirements")
        names = {"FR1": "Agent interception", "FR2": "Policy engine", "FR3": "Taint tracking",
                 "FR4": "Injection detection", "FR5": "Human approval", "FR6": "Audit and replay",
                 "FR7": "Admin console", "FR8": "Demo and benchmark"}
        tw, th, gx, gy = 2.02, 1.6, 0.2, 0.25
        for k, (fr, label) in enumerate(names.items()):
            r, c = divmod(k, 4)
            x, y = MARGIN + c * (tw + gx), 1.8 + r * (th + gy)
            self.shape(s, x, y, tw, th, fill=TINT, radius=0.14, name=f"tile {fr}")
            self.text(s, x + 0.2, y + 0.18, tw - 0.4, 0.3, fr, size=14, color=TEAL, bold=True, name=f"{fr} id")
            self.text(s, x + 0.2, y + 0.5, tw - 0.4, 0.68, label, size=18, color=NAVY, bold=True,
                      name=f"{fr} name")
            n = groups.get(fr, 0)
            self.text(s, x + 0.2, y + th - 0.42, tw - 0.4, 0.3, f"{n} requirement{'s' if n != 1 else ''}",
                      size=13, color=MUTED, name=f"{fr} count")
        rx = MARGIN + 4 * tw + 3 * gx + 0.4
        rw = SLIDE_W - MARGIN - rx
        self.text(s, rx, 1.8, rw, 0.4, "Key quality targets", size=18, color=NAVY, bold=True, name="nfr head")
        targets = [("≤ 200 ms", "median added latency"), ("≥ 80%", "statement coverage"),
                   ("AR + EN", "full right-to-left interface"), ("< 30 s", "for an approver's decision")]
        for i, (big, small) in enumerate(targets):
            y = 2.32 + i * 0.78
            self.text(s, rx, y, 1.4, 0.6, big, size=22, color=TEAL, bold=True, anchor=MSO_ANCHOR.MIDDLE,
                      name=f"nfr value {i}")
            self.text(s, rx + 1.45, y, rw - 1.45, 0.66, small, size=14, color=INK, anchor=MSO_ANCHOR.MIDDLE,
                      name=f"nfr label {i}")
        self.text(s, MARGIN, 5.7, CONTENT_W, 0.9,
                  [[("Elicited from ", {"bold": True, "color": NAVY}),
                    ("OWASP, NCA ECC, PDPL and NIST AI RMF · attack literature · competitor review · "
                     "STRIDE threat model · three personas. Every requirement has an acceptance test.", {})]],
                  size=16, color=MUTED, name="sources")

    def s07_architecture(self):
        s = self.new_slide("One gateway between any agent and its tools", "Design · architecture")
        w = 9.35
        self.picture(s, FIG / "architecture.png", MARGIN, 1.55, w=w,
                     alt="Mirsad architecture: agents connect through adapters to the gateway call path and result "
                         "path, with audit log, admin API and approval service, in front of upstream tools")
        rx = MARGIN + w + 0.3
        rw = SLIDE_W - MARGIN - rx
        points = [("Drop-in", "agents only change the endpoint"),
                  ("Two checkpoints", "before a call runs and before the model reads a result"),
                  ("Audited", "every decision goes to a hash-chained log")]
        for i, (head, body) in enumerate(points):
            y = 1.75 + i * 1.6
            self.circle_label(s, rx, y, 0.5, str(i + 1), size=16)
            self.text(s, rx, y + 0.6, rw, 0.95, [[(head + ": ", {"bold": True, "color": NAVY}), (body, {})]],
                      size=15, color=INK, name=f"point {i + 1}")

    def _flow_box(self, s, x, y, w, h, head, sub, *, fill=TINT, head_color=NAVY, line=None, name="box"):
        self.shape(s, x, y, w, h, fill=fill, line=line, line_w=1.5, radius=0.14, name=name)
        self.text(s, x + 0.12, y + 0.14, w - 0.24, 0.4, head, size=18, color=head_color, bold=True,
                  align=PP_ALIGN.CENTER, name=f"{name} head")
        if sub:
            self.text(s, x + 0.12, y + 0.56, w - 0.24, h - 0.62, sub, size=14, color=MUTED,
                      align=PP_ALIGN.CENTER, name=f"{name} sub")

    def s08_flow(self):
        s = self.new_slide("Every tool call is checked twice", "Design · how a tool call is checked")
        bw, gap, bh = 2.06, 0.455, 1.22
        lanes = [
            ("BEFORE THE TOOL RUNS", 1.9, [("Tool call", "from the agent"), ("Policy", "allow-list · limits · rules"),
                                           ("Taint", "where did each value come from?"), ("Decide", "any deny wins")]),
            ("BEFORE THE MODEL READS THE RESULT", 3.85, [("Tool result", "raw content"),
                                                        ("Detector", "Arabic + English scan"),
                                                        ("Sanitise", "remove or mark as data"),
                                                        ("Label", "trust · sensitivity · values"),
                                                        ("To the agent", "inspected result")]),
        ]
        for title, y, boxes in lanes:
            self.text(s, MARGIN, y - 0.36, 8, 0.3, title, size=12, color=TEAL, bold=True, spacing=120,
                      name=f"lane {title}")
            for i, (head, sub) in enumerate(boxes):
                x = MARGIN + i * (bw + gap)
                outline = NAVY if i == 0 else None
                self._flow_box(s, x, y, bw, bh, head, sub, fill=WHITE if i == 0 else TINT, line=outline,
                               name=f"{head} box")
                if i < len(boxes) - 1 or title.startswith("BEFORE THE TOOL"):
                    self.arrow(s, x + bw + (gap - 0.3) / 2, y + bh / 2 - 0.15, 0.3, 0.3)
        # outcomes of the call path
        ox = MARGIN + 4 * (bw + gap)
        for k, (label, kind) in enumerate([("Allow", "yes"), ("Ask a human", "approval"), ("Deny", "deny")]):
            self.chip(s, ox, 1.9 + k * 0.42, bw, 0.36, label, kind, size=15)
        self.shape(s, MARGIN, 5.4, CONTENT_W, 0.5, fill=TEAL_TINT, radius=0.12, name="audit strip")
        self.text(s, MARGIN, 5.4, CONTENT_W, 0.5, "Every decision and inspection  →  HMAC-chained audit log",
                  size=17, color=TEAL, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE,
                  name="audit text")
        self.text(s, MARGIN, 6.1, CONTENT_W, 0.7,
                  [[("Example: ", {"bold": True, "color": NAVY}),
                    ("send_email to an address seen only inside an untrusted e-mail  →  ", {}),
                    ("TAINT_UNTRUSTED_DESTINATION", {"font": MONO, "size": 16, "color": RED}),
                    ("  →  deny", {"bold": True, "color": RED})]],
                  size=17, color=INK, name="example")

    def s09_policy_taint(self):
        s = self.new_slide("Policy decides actions; taint tracks where data came from", "Design · policy and taint")
        pw = 5.75
        self.text(s, MARGIN, 1.62, pw, 0.3, "configs/policies/default.yaml (excerpt)", size=13, color=MUTED,
                  font=MONO, name="policy caption")
        self.shape(s, MARGIN, 1.98, pw, 3.45, fill=NAVY, radius=0.14, name="code panel")
        code_lines = POLICY_EXCERPT.split("\n")
        paras = []
        for line in code_lines:
            m = re.match(r"^(\s*)([^:]+:)(.*)$", line)
            if m and not line.strip().startswith("{") and not line.strip().startswith("on_violation"):
                paras.append([(m.group(1) + m.group(2), {"color": TEAL_LIGHT}), (m.group(3), {"color": WHITE})])
            else:
                paras.append([(line, {"color": WHITE})])
        self.text(s, MARGIN + 0.3, 2.2, pw - 0.5, 3.1, paras, size=13, font=MONO, color=WHITE, name="policy code")
        self.text(s, MARGIN, 5.6, pw, 0.7, "Unlisted tools are denied; policies are validated, versioned and "
                  "activated without a restart.", size=15, color=MUTED, name="policy note")
        taint = self.policy.get("taint", {})
        rules = [("TAINT_UNTRUSTED_TO_EXTERNAL", "Untrusted content read, then a call to an external destination",
                  taint.get("untrusted_to_external_sink")),
                 ("TAINT_CONFIDENTIAL_TO_EXTERNAL", "Confidential values sent to an external destination",
                  taint.get("confidential_to_external_sink")),
                 ("TAINT_UNTRUSTED_DESTINATION", "Destination chosen by untrusted content",
                  taint.get("untrusted_controls_destination")),
                 ("TAINT_AFTER_INJECTION", "High-risk tool after an injection was detected",
                  taint.get("after_injection_high_risk"))]
        rx = MARGIN + pw + 0.45
        rw = SLIDE_W - MARGIN - rx
        self.text(s, rx, 1.62, rw, 0.35, "Taint rules in the default policy", size=18, color=NAVY, bold=True,
                  name="taint head")
        for i, (code, desc, action) in enumerate(rules):
            y = 2.1 + i * 1.0
            self.shape(s, rx, y + 0.95, rw, 0.012, fill=LINE, name="rule line")
            self.text(s, rx, y + 0.05, rw - 1.55, 0.3, code, size=12, color=TEAL, font=MONO, name=f"rule code {i}")
            self.text(s, rx, y + 0.35, rw - 1.55, 0.6, desc, size=17, color=INK, name=f"rule desc {i}")
            label, kind = {"deny": ("Deny", "deny"), "require_approval": ("Approval", "approval"),
                           "allow": ("Allow", "yes")}.get(str(action), (str(action), "na"))
            self.chip(s, rx + rw - 1.4, y + 0.3, 1.4, 0.4, label, kind, size=15)
        self.text(s, rx, 6.1, rw, 0.7, "Evidence names the source tool, call and field.", size=15,
                  color=MUTED, name="taint note")

    def s10_components(self):
        s = self.new_slide("Detection, human approval and a verifiable record", "Design · detector, approval, audit")
        timeout = (self.policy.get("defaults") or {}).get("approval_timeout_s", 120)
        n_rules = detector_rule_count()
        cards = [
            ("ع", "Injection detector", ["Undoes hidden-character and Arabic spelling tricks",
                                         "Scores text with rules and an n-gram model"],
             f"{n_rules} rules · EN · AR · Arabizi", "A signal, not the boundary"),
            ("✓", "Human approval", ["Arabic/English summary: what, why, data source",
                                     "Pushed to the approver's phone"],
             f"No answer in {timeout} s → deny", "Fail-safe by design"),
            ("#", "Audit log", ["Hash chain (HMAC-SHA-256); IDs masked",
                                "Verify the chain, replay any decision"],
             "Edit, delete, reorder → detected", "Evidence for auditors"),
        ]
        cw, gap, y, h = 3.78, 0.395, 1.75, 4.95
        for i, (glyph, head, lines, fact, note) in enumerate(cards):
            x = MARGIN + i * (cw + gap)
            self.shape(s, x, y, cw, h, fill=TINT, radius=0.18, name=f"card {head}")
            self.circle_label(s, x + 0.4, y + 0.4, 0.78, glyph, fill=NAVY, size=24, name=f"icon {head}")
            self.text(s, x + 0.4, y + 1.35, cw - 0.8, 0.5, head, size=24, color=NAVY, bold=True,
                      name=f"head {head}")
            for k, line in enumerate(lines):
                ly = y + 1.98 + k * 0.98
                self.shape(s, x + 0.42, ly + 0.13, 0.12, 0.12, fill=TEAL, kind=MSO_SHAPE.OVAL, name="dot")
                self.text(s, x + 0.68, ly, cw - 1.08, 0.9, line, size=18, color=INK, name=f"{head} line {k}")
            self.shape(s, x + 0.35, y + h - 1.1, cw - 0.7, 0.5, fill=WHITE, line=LINE, radius=0.12,
                       name=f"fact {head}")
            self.text(s, x + 0.35, y + h - 1.1, cw - 0.7, 0.5, fact, size=15, color=TEAL, bold=True,
                      align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, name=f"fact text {head}")
            self.text(s, x + 0.4, y + h - 0.5, cw - 0.8, 0.35, note, size=13, color=MUTED, italic=True,
                      align=PP_ALIGN.CENTER, name=f"note {head}")

    def s11_ui(self):
        s = self.new_slide("Bilingual dashboard and installable approver app", "Implementation · user interfaces")
        screens = FIG / "screens"
        dw = 4.05
        dh = dw * 1800 / 2880
        en = self.framed(screens / "dash-overview.png", max_w=1600, radius=22, border=4, border_color=(0xD5, 0xDB, 0xE3))
        ar = self.framed(screens / "dash-activity-ar.png", max_w=1600, radius=22, border=4,
                         border_color=(0xD5, 0xDB, 0xE3))
        self.picture(s, en, MARGIN, 1.62, w=dw, alt="Admin dashboard overview in English")
        self.picture(s, ar, MARGIN, 1.62 + dh + 0.18, w=dw, alt="Activity and audit log page in Arabic, right-to-left")
        ph = 4.72
        pw = ph * 1170 / 2532
        p_en = self.framed(screens / "pwa-detail-en.png", max_w=800, radius=70, border=22, border_color=(0x0B, 0x1F, 0x3A))
        p_ar = self.framed(screens / "pwa-pending-ar.png", max_w=800, radius=70, border=22,
                           border_color=(0x0B, 0x1F, 0x3A))
        x1 = MARGIN + dw + 0.4
        self.picture(s, p_en, x1, 1.62, h=ph, alt="Approver app: request detail with summary and Approve/Deny")
        self.picture(s, p_ar, x1 + pw + 0.25, 1.62, h=ph, alt="Approver app: pending requests in Arabic")
        self.text(s, x1, 1.62 + ph + 0.08, pw * 2 + 0.25, 0.3, "Approver app: request detail (EN) · queue (AR)",
                  size=12, color=MUTED, align=PP_ALIGN.CENTER, name="phone caption")
        rx = x1 + 2 * pw + 0.25 + 0.4
        rw = SLIDE_W - MARGIN - rx
        blocks = [("Admin dashboard", "Live statistics, audit log, policies, agents, detector playground"),
                  ("English and Arabic", "Full right-to-left layout with one toggle"),
                  ("Approver app (PWA)", "Installs on Android and iOS; push alerts; one-tap decision")]
        for i, (head, body) in enumerate(blocks):
            y = 1.7 + i * 1.62
            self.text(s, rx, y, rw, 0.4, head, size=18, color=NAVY, bold=True, name=f"ui head {i}")
            self.text(s, rx, y + 0.42, rw, 1.1, body, size=16, color=INK, name=f"ui body {i}")

    def s12_method(self):
        n_sprints = sprint_count()
        s = self.new_slide("Scrum, DevSecOps and an engineering contract", "Process · methodology and management")
        items = [("S", "Scrum", f"{n_sprints} two-week sprints over two semesters"),
                 ("C", "Engineering contract", "Interfaces fixed first; five parallel workstreams"),
                 ("CI", "DevSecOps", "Every pull request: review, lint, tests, Bandit, pip-audit")]
        lw = 3.75
        for i, (glyph, head, body) in enumerate(items):
            y = 1.75 + i * 1.6
            self.circle_label(s, MARGIN, y, 0.62, glyph, fill=NAVY, size=16 if len(glyph) > 1 else 20)
            self.text(s, MARGIN + 0.8, y - 0.02, lw - 0.8, 0.4, head, size=19, color=NAVY, bold=True,
                      name=f"practice {i}")
            self.text(s, MARGIN + 0.8, y + 0.4, lw - 0.8, 0.95, body, size=16, color=INK, name=f"practice body {i}")
        self._gantt(s, MARGIN + lw + 0.35, 1.62, SLIDE_W - MARGIN - (MARGIN + lw + 0.35), 5.15)

    def _gantt(self, s, x0: float, y0: float, w: float, h: float) -> None:
        plan = yaml.safe_load(PLAN.read_text(encoding="utf-8"))
        start, end = date(2026, 9, 1), date(2027, 6, 1)
        label_w = 2.45
        gx, gw = x0 + label_w, w - label_w
        span = (end - start).days

        def X(d: date) -> float:
            return gx + gw * (d - start).days / span

        phases = []
        for ph in plan["phases"]:
            starts = [t["start"] for t in ph["tasks"]]
            ends = [t["end"] for t in ph["tasks"]]
            phases.append((ph["name"], min(starts), max(ends)))
        top = y0 + 0.95
        row_h = (h - 1.35) / len(phases)
        # month grid and labels
        months = [date(2026 + (8 + k) // 12, (8 + k) % 12 + 1, 1) for k in range(10)]
        for m in months:
            self.shape(s, X(m), top - 0.05, 0.008, row_h * len(phases) + 0.05, fill=LINE, name="month line")
            if m < end:
                self.text(s, X(m) + 0.03, y0 + h - 0.36, 0.6, 0.3, m.strftime("%b"), size=12, color=MUTED,
                          name="month")
        self.text(s, X(date(2026, 9, 1)), y0 + 0.5, X(date(2027, 1, 1)) - X(date(2026, 9, 1)), 0.28,
                  "Senior Project I · Fall 2026", size=12, color=MUTED, align=PP_ALIGN.CENTER, name="sem1")
        self.text(s, X(date(2027, 1, 1)), y0 + 0.5, X(end) - X(date(2027, 1, 1)), 0.28,
                  "Senior Project II · Spring 2027", size=12, color=MUTED, align=PP_ALIGN.CENTER, name="sem2")
        for i, (name, a, b) in enumerate(phases):
            y = top + i * row_h
            self.text(s, x0, y, label_w - 0.12, row_h, name.replace("&", "and"), size=14, color=INK,
                      anchor=MSO_ANCHOR.MIDDLE, name=f"phase {i}")
            bar_h = row_h * 0.52
            self.shape(s, X(a), y + (row_h - bar_h) / 2, max(0.1, X(b) - X(a)), bar_h,
                       fill=NAVY, radius=0.06, name=f"bar {i}")
        for ms in plan["milestones"]:
            d = ms["date"]
            self.shape(s, X(d) - 0.11, y0 + 0.05, 0.22, 0.22, fill=AMBER, kind=MSO_SHAPE.DIAMOND,
                       name=f"milestone {ms['id']}")
            self.text(s, X(d) - 0.3, y0 + 0.24, 0.6, 0.26, ms["id"], size=11, color=AMBER_DARK, bold=True,
                      align=PP_ALIGN.CENTER, name=f"ms label {ms['id']}")

    def s13_testing(self):
        r = self.r
        s = self.new_slide("Testing and quality evidence", "Testing · verification")
        tiles = [
            (r.fmt("python_tests.passed", ","), f"of {r.fmt('python_tests.total', ',')} Python tests passed"),
            (r.fmt("web_tests.passed"), f"of {r.fmt('web_tests.total')} web tests passed"),
            (r.fmt("coverage.percent", ".1f", "%"), "statement coverage (target ≥ 80%)"),
            (r.fmt("security.bandit_issues"), f"Bandit issues in {r.fmt('security.bandit_loc', ',')} lines"),
            (self._vuln_total(), "vulnerable dependencies (pip-audit, npm audit)"),
        ]
        tw, gap = (CONTENT_W - 4 * 0.22) / 5, 0.22
        for i, (big, small) in enumerate(tiles):
            x = MARGIN + i * (tw + gap)
            self.shape(s, x, 1.7, tw, 1.6, fill=TEAL_TINT if i < 3 else TINT, radius=0.14, name=f"tile {i}")
            self.text(s, x + 0.2, 1.84, tw - 0.4, 0.62, big, size=30, color=NAVY, bold=True, name=f"tile value {i}")
            self.text(s, x + 0.2, 2.5, tw - 0.4, 0.72, small, size=14, color=MUTED, name=f"tile label {i}")
        by_area = r.get("python_tests.by_area") or {}
        if by_area:
            items = sorted(by_area.items(), key=lambda kv: kv[1])
            data = CategoryChartData()
            data.categories = [k for k, _ in items]
            data.add_series("Python tests", [v for _, v in items])
            self.text(s, MARGIN, 3.58, 7.6, 0.35, "Python tests by area", size=16, color=NAVY, bold=True,
                      name="chart title")
            gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(MARGIN), Inches(3.92), Inches(7.6),
                                    Inches(2.95), data)
            self._style_bar_chart(gf.chart, "0", [NAVY] * len(items), max_value=max(by_area.values()) * 1.18,
                                  font_size=12)
        rx = MARGIN + 8.0
        rw = SLIDE_W - MARGIN - rx
        self.text(s, rx, 3.62, rw, 0.4, "Security tests attack the gateway", size=18, color=NAVY, bold=True,
                  name="sec head")
        self.text(s, rx, 4.05, rw, 1.6,
                  f"{r.fmt('python_tests.by_area.security')} cases: forged tokens, role tampering, audit tampering, "
                  "regex denial of service, SSRF, oversized bodies, brute-force logins", size=16, color=INK,
                  name="sec body")
        self.text(s, rx, 5.75, rw, 1.0,
                  f"Code base: {r.fmt('code_size.python_src', ',')} lines of Python, "
                  f"{r.fmt('code_size.web_ts', ',')} of TypeScript, {r.fmt('code_size.python_tests', ',')} of tests",
                  size=14, color=MUTED, name="code size")

    def _vuln_total(self) -> str:
        a, b = self.r.get("security.pip_audit_vulnerable"), self.r.get("security.npm_audit_vulnerabilities")
        return PENDING if a is None or b is None else str(a + b)

    def _style_bar_chart(self, chart, number_format: str, colors: list[RGBColor], *, max_value: float,
                         font_size: int = 13) -> None:
        chart.has_legend = False
        chart.has_title = False
        chart.font.name = FONT
        chart.font.size = Pt(font_size)
        chart.font.color.rgb = INK
        plot = chart.plots[0]
        plot.gap_width = 55
        plot.vary_by_categories = False
        plot.has_data_labels = True
        dl = plot.data_labels
        dl.number_format = number_format
        dl.number_format_is_linked = False
        dl.position = XL_LABEL_POSITION.OUTSIDE_END
        dl.font.size = Pt(font_size)
        dl.font.color.rgb = INK
        dl.font.bold = True
        series = plot.series[0]
        for idx, color in enumerate(colors):
            pt = series.points[idx]
            pt.format.fill.solid()
            pt.format.fill.fore_color.rgb = color
        va = chart.value_axis
        va.minimum_scale = 0
        va.maximum_scale = max_value
        va.has_major_gridlines = False
        va.visible = False
        ca = chart.category_axis
        ca.tick_labels.font.size = Pt(font_size)
        ca.tick_labels.font.color.rgb = INK
        ca.format.line.color.rgb = LINE
        ca.has_major_gridlines = False

    def s14_results(self):
        r = self.r
        base = "bench.scripted_benign_oracle"
        s = self.new_slide("What protection costs legitimate work", "Evaluation · measured results")
        tiles = [
            (r.fmt(f"{base}.configs.full.fpr", ".1%"), "benign calls denied automatically (limit ≤ 5%)", TEAL_TINT),
            (r.fmt(f"{base}.configs.full.friction", ".1%"), "benign calls sent to a human, by policy design", TINT),
            (f"{r.fmt(f'{base}.configs.full.utility', '.0%')} / "
             f"{r.fmt('bench.scripted_benign_deny.configs.full.utility', '.0%')}",
             "tasks completed: informed / always-deny approver", TINT),
            (r.fmt("latency.separate_process.sequential_added_p50", ".1f", " ms"),
             f"median added per call; {r.fmt('latency.separate_process.concurrent_added_p50', '.0f', ' ms')} "
             f"at {r.fmt('latency.separate_process.sessions')} concurrent sessions", TEAL_TINT),
        ]
        tw, th = 2.95, 2.0
        for i, (big, small, fill) in enumerate(tiles):
            rr, cc = divmod(i, 2)
            x, y = MARGIN + cc * (tw + 0.22), 1.72 + rr * (th + 0.22)
            self.shape(s, x, y, tw, th, fill=fill, radius=0.14, name=f"result tile {i}")
            self.text(s, x + 0.25, y + 0.2, tw - 0.5, 0.7, big, size=32, color=NAVY, bold=True,
                      name=f"result value {i}")
            self.text(s, x + 0.25, y + 0.95, tw - 0.5, 0.95, small, size=15, color=INK, name=f"result label {i}")
        cfgs = [("none", "No protection"), ("detector_only", "Detector only"), ("taint_only", "Taint only"),
                ("policy_only", "Policy only"), ("full", "Full Mirsad")]
        vals = [r.get(f"{base}.configs.{k}.friction") for k, _ in cfgs]
        cx = MARGIN + 2 * tw + 0.22 + 0.5
        cw = SLIDE_W - MARGIN - cx
        self.text(s, cx, 1.72, cw, 0.35, "Benign calls sent to a human, by configuration", size=16, color=NAVY,
                  bold=True, name="chart title")
        self.text(s, cx, 2.07, cw, 0.3, "Automatic denials: 0 in every configuration" if all(
            (r.get(f"{base}.configs.{k}.fpr") or 0) == 0 for k, _ in cfgs) else "See report for automatic denials",
            size=13, color=MUTED, name="chart subtitle")
        if all(v is not None for v in vals):
            data = CategoryChartData()
            data.categories = [lbl for _, lbl in reversed(cfgs)]
            data.add_series("Friction", list(reversed(vals)))
            gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(cx), Inches(2.4), Inches(cw), Inches(3.55),
                                    data)
            colors = [TEAL if k == "full" else SLATE for k, _ in reversed(cfgs)]
            self._style_bar_chart(gf.chart, "0.0%", colors, max_value=max(max(vals), 0.01) * 1.3, font_size=14)
        meta = bench_meta("scripted-benign-oracle")
        langs = meta.get("tasks_by_lang") or {}
        lang_txt = f" ({langs.get('en', '?')} English, {langs.get('ar', '?')} Arabic)" if langs else ""
        mode = (meta.get("detector_mode") or {}).get("full", "unknown")
        self.text(s, MARGIN, 6.2, CONTENT_W, 0.62,
                  f"Mirsad-Bench: {r.fmt(base + '.tasks')} benign tasks{lang_txt}, "
                  f"{r.fmt(base + '.configs.full.calls')} tool calls, scripted agent; detector mode: "
                  f"{mode.replace('_', '-')}. Latency: {r.fmt('latency.separate_process.calls', ',')} calls, "
                  "server in a separate process.", size=13, color=MUTED, name="method note")

    def s15_scorecard(self):
        r = self.r
        s = self.new_slide("Objectives: what is met and what is pending", "Evaluation · scorecard")
        replay_c = sum((run or {}).get("replay_checked") or 0 for run in (r.get("bench") or {}).values())
        replay_m = sum((run or {}).get("replay_matched") or 0 for run in (r.get("bench") or {}).values())
        conc = r.get("latency.separate_process.concurrent_added_p50")
        fpr = r.get("bench.scripted_benign_oracle.configs.full.fpr")
        calls = r.get("bench.scripted_benign_oracle.configs.full.calls")
        cov = r.get("coverage.percent")
        f1_ar, f1_en = r.get("detector.splits.test_ar.f1"), r.get("detector.splits.test_en.f1")
        asr_red = r.attack_reduction()

        def status(value, ok) -> str:
            return "pending" if value is None else ("met" if ok else "notmet")

        def f1_text(v):
            return PENDING if v is None else f"{v:.2f}"

        rows = [
            ("Median added latency ≤ 200 ms",
             f"{r.fmt('latency.separate_process.sequential_added_p50', '.1f', ' ms')} per call · "
             f"{r.fmt('latency.separate_process.concurrent_added_p50', '.0f', ' ms')} at "
             f"{r.fmt('latency.separate_process.sessions')} sessions", status(conc, conc is not None and conc <= 200)),
            ("Benign actions blocked ≤ 5%",
             f"{r.fmt('bench.scripted_benign_oracle.configs.full.fpr', '.1%')} of {calls} benign calls"
             if calls is not None else PENDING, status(fpr, fpr is not None and fpr <= 0.05)),
            ("Every decision replayable", f"{replay_m} / {replay_c} replayed identically" if replay_c else PENDING,
             status(replay_c or None, replay_c and replay_m == replay_c)),
            ("Statement coverage ≥ 80%", r.fmt("coverage.percent", ".1f", "%"), status(cov, cov is not None and cov >= 80)),
            ("Detector F1 ≥ 0.85 (Arabic, English)", f"AR {f1_text(f1_ar)} · EN {f1_text(f1_en)}",
             status(None if f1_ar is None or f1_en is None else 1, (f1_ar or 0) >= 0.85 and (f1_en or 0) >= 0.85)),
            ("Attack success reduced ≥ 80%", PENDING if asr_red is None else f"{asr_red:.0%}",
             status(asr_red, asr_red is not None and asr_red >= 0.8)),
        ]
        c1, c2, c3 = 4.6, 5.3, CONTENT_W - 4.6 - 5.3
        y0, rh = 1.7, 0.6
        for j, (head, cw, xo) in enumerate([("Target (proposal)", c1, 0), ("Result", c2, c1), ("Status", c3, c1 + c2)]):
            self.text(s, MARGIN + xo, y0, cw, 0.4, head.upper(), size=12, color=MUTED, bold=True, spacing=100,
                      align=PP_ALIGN.CENTER if j == 2 else PP_ALIGN.LEFT, name=f"col {j}")
        for i, (target, result, st) in enumerate(rows):
            y = y0 + 0.42 + i * rh
            self.shape(s, MARGIN, y, CONTENT_W, 0.012, fill=LINE, name="row rule")
            self.text(s, MARGIN, y, c1 - 0.1, rh, target, size=18, color=NAVY, bold=True, anchor=MSO_ANCHOR.MIDDLE,
                      name=f"target {i}")
            self.text(s, MARGIN + c1, y, c2 - 0.1, rh, result, size=18, color=INK, anchor=MSO_ANCHOR.MIDDLE,
                      name=f"result {i}")
            label = {"met": "Met", "pending": "Pending", "notmet": "Not met"}[st]
            self.chip(s, MARGIN + c1 + c2 + (c3 - 1.5) / 2, y + (rh - 0.38) / 2, 1.5, 0.38, label, st, size=15)
        y = y0 + 0.42 + len(rows) * rh + 0.25
        self.shape(s, MARGIN, y, CONTENT_W, 0.95, fill=AMBER_TINT, radius=0.14, name="pending note box")
        self.text(s, MARGIN + 0.35, y, CONTENT_W - 0.7, 0.95,
                  [[("Why pending: ", {"bold": True}),
                    ("F1 and attack success need attack-labelled data written by the team. ", {}),
                    ("make detector", {"font": MONO, "size": 15}),
                    (" and the benchmark's attack episodes produce them; this slide updates from the result files.",
                     {})]],
                  size=16, color=AMBER_DARK, anchor=MSO_ANCHOR.MIDDLE, name="pending note")

    def s16_demo(self):
        s = self.new_slide("Live demo: one request, with and without Mirsad", "Demonstration · plan")
        steps = [("Unprotected", "CV with hidden instructions; the agent may delete a customer", "Abdulmalik"),
                 ("Protected", "Same request: the deletion waits; Deny on the phone", "Abdulmalik, Mohammed"),
                 ("Audit", "Verify the hash chain; replay the decision", "Bader Alyamini"),
                 ("Invoice e-mail", "Untrusted content inspected and marked as data", "Abdulmalik"),
                 ("Arabic", "RTL interface and an Arabic scenario", "Abdullah")]
        n = len(steps)
        sw = (CONTENT_W - (n - 1) * 0.25) / n
        line_y = 2.15
        self.shape(s, MARGIN + sw / 2, line_y - 0.02, CONTENT_W - sw, 0.04, fill=LINE, name="timeline")
        for i, (head, body, who) in enumerate(steps):
            x = MARGIN + i * (sw + 0.25)
            self.circle_label(s, x + sw / 2 - 0.34, line_y - 0.34, 0.68, str(i + 1),
                              fill=RED if i == 0 else TEAL, size=20)
            self.shape(s, x, 2.75, sw, 2.55, fill=TINT, radius=0.16, name=f"demo card {i + 1}")
            self.text(s, x + 0.22, 2.92, sw - 0.44, 0.45, head, size=19, color=NAVY, bold=True,
                      name=f"demo head {i + 1}")
            self.text(s, x + 0.22, 3.42, sw - 0.44, 1.35, body, size=16, color=INK, name=f"demo body {i + 1}")
            self.text(s, x + 0.22, 4.82, sw - 0.44, 0.42, who, size=11, color=MUTED, name=f"demo who {i + 1}")
        self.text(s, MARGIN, 5.6, CONTENT_W, 0.4,
                  "Everything runs locally: fictional Najd Trading Co. data, Qwen2.5 7B through Ollama, "
                  "no external services.", size=16, color=INK, name="demo setup")
        self.shape(s, MARGIN, 6.12, CONTENT_W, 0.62, fill=GREY_TINT, radius=0.12, name="fallback box")
        self.text(s, MARGIN + 0.3, 6.12, CONTENT_W - 0.6, 0.62,
                  [[("Fallback: ", {"bold": True, "color": NAVY}),
                    ("the same scenario from the command line, and the screenshots in Appendix C.", {})]],
                  size=16, color=INK, anchor=MSO_ANCHOR.MIDDLE, name="fallback")

    def s17_conclusion(self):
        r = self.r
        s = self.new_slide("Conclusion and future work", "Conclusion")
        fpr = r.fmt("bench.scripted_benign_oracle.configs.full.fpr", ".0%")
        lat = r.fmt("latency.separate_process.sequential_added_p50", ".0f", " ms")
        delivered = ["Drop-in gateway for MCP, OpenAI-style and SDK agents",
                     "Policy, taint, AR/EN detector, approval and audit in one component",
                     f"{fpr} benign calls auto-denied; about {lat} added per call"]
        nxt = ["Team attack data → detector F1 and attack success rate",
               "Load test with several workers and PostgreSQL",
               "Fine-tune a multilingual encoder; pilot with a Saudi organisation"]
        colw = (CONTENT_W - 0.4) / 2
        for k, (head, items, badge, fill) in enumerate([("Delivered", delivered, TEAL, TEAL_TINT),
                                                         ("Next", nxt, AMBER_DARK, AMBER_TINT)]):
            x = MARGIN + k * (colw + 0.4)
            self.shape(s, x, 1.75, colw, 3.95, fill=fill, radius=0.18, name=f"{head} card")
            self.text(s, x + 0.4, 1.95, colw - 0.8, 0.5, head, size=24, color=NAVY, bold=True, name=f"{head} head")
            for i, item in enumerate(items):
                y = 2.65 + i * 0.98
                self.circle_label(s, x + 0.4, y + 0.04, 0.36, "✓" if k == 0 else "→", fill=badge, size=14)
                self.text(s, x + 0.95, y, colw - 1.35, 0.9, item, size=18, color=INK, name=f"{head} item {i}")
        self.text(s, MARGIN, 5.95, CONTENT_W, 0.8,
                  [[("Limits: ", {"bold": True, "color": NAVY}),
                    ("proxy-level taint is coarser than CaMeL; concurrency measured on one worker with SQLite; "
                     "detection accuracy and attack reduction not yet measured.", {})]],
                  size=16, color=MUTED, name="limits")

    def s18_thanks(self):
        s = self.new_slide("Thank you", dark=True)
        t = s.shapes.title
        t.left, t.top, t.width, t.height = Inches(MARGIN), Inches(2.95), Inches(CONTENT_W), Inches(1.0)
        p = t.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        for run in p.runs:
            run.font.size = Pt(54)
        self.fit.items[-1] = FitItem(self.slide_no, "title", [("Thank you", 54, True, FONT)], CONTENT_W, 1.0)
        if APP_ICON.exists():
            self.picture(s, APP_ICON, (SLIDE_W - 1.5) / 2, 1.15, w=1.5, alt="Mirsad logo")
        self.text(s, MARGIN, 4.0, CONTENT_W, 0.8, "شكرًا لكم", size=36, color=TEAL_LIGHT, bold=True,
                  align=PP_ALIGN.CENTER, rtl=True, name="arabic thanks")
        self.text(s, MARGIN, 4.95, CONTENT_W, 0.5, "Questions are welcome", size=24, color=WHITE,
                  align=PP_ALIGN.CENTER, name="questions")
        self.text(s, MARGIN, 6.2, CONTENT_W, 0.35, "  ·  ".join(n for n, _ in TEAM), size=12, color=LINE,
                  align=PP_ALIGN.CENTER, name="team line")
        self.text(s, MARGIN, 6.62, CONTENT_W, 0.35, f"Supervisor: {SUPERVISOR}  ·  Prince Sultan University",
                  size=14, color=LINE, align=PP_ALIGN.CENTER, name="supervisor line")

    # ------------------------------------------------------------- build

    def build(self, out: Path) -> None:
        slides = [self.s01_title, self.s02_problem, self.s03_why, self.s04_objectives, self.s05_related,
                  self.s06_requirements, self.s07_architecture, self.s08_flow, self.s09_policy_taint,
                  self.s10_components, self.s11_ui, self.s12_method, self.s13_testing, self.s14_results,
                  self.s15_scorecard, self.s16_demo, self.s17_conclusion, self.s18_thanks]
        self.total = len(slides)
        missing = [n for n in range(1, self.total + 1) if not self.notes.get(n)]
        if missing:
            raise SystemExit(f"speaker notes missing in {SCRIPT_MD.name} for slides {missing}")
        for make in slides:
            make()
            slide = self.prs.slides[self.slide_no - 1]
            if 1 < self.slide_no < self.total:
                self.footer(slide)
            slide.notes_slide.notes_text_frame.text = self.notes[self.slide_no]
        props = self.prs.core_properties
        props.title = "Mirsad (مرصاد) – IS499 Final Presentation"
        props.author = "Mirsad team – Prince Sultan University"
        props.subject = "A runtime security firewall for AI agents against prompt-injection attacks"
        props.keywords = "prompt injection; AI agents; MCP; security gateway; Arabic"
        out.parent.mkdir(parents=True, exist_ok=True)
        self.prs.save(str(out))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--no-fit-check", action="store_true", help="skip the text-overflow estimate")
    args = ap.parse_args(argv)
    results = Results(RESULTS)
    notes = load_notes(SCRIPT_MD)
    fit = FitChecker()
    with tempfile.TemporaryDirectory() as tmp:
        deck = Deck(results, notes, Path(tmp), fit)
        deck.build(args.out)
    print(f"wrote {args.out}  ({deck.total} slides)")
    if not args.no_fit_check:
        if not (OFFICE_FONTS / "Calibri.ttf").exists():
            print("  fit check skipped: Calibri metrics not found")
        elif fit.report() == 0:
            print("  fit check: no text box is estimated to overflow")
    return 0


if __name__ == "__main__":
    sys.exit(main())
