"""Render the design diagrams in docs/diagrams/ to PNG figures in docs/figures/.

* ``*.mmd`` files are Mermaid sources, rendered with mermaid.js inside headless Chrome.
* ``*.html`` files are hand-built diagrams; the element with id ``diagram`` is captured.

Requires Playwright (``pip install playwright``) and a Chrome install (``channel="chrome"``),
plus a local copy of mermaid.min.js (``npm install mermaid@11``) passed via ``MERMAID_JS``.

    MERMAID_JS=node_modules/mermaid/dist/mermaid.min.js python scripts/render_diagrams.py [name ...]
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "diagrams"
OUT = ROOT / "docs" / "figures"

MERMAID_CONFIG = {
    "startOnLoad": False,
    "theme": "base",
    "fontFamily": "Arial, Helvetica, sans-serif",
    "themeVariables": {
        "primaryColor": "#e6f4f4",
        "primaryBorderColor": "#0f766e",
        "primaryTextColor": "#0b1f3a",
        "lineColor": "#334155",
        "secondaryColor": "#eef2ff",
        "tertiaryColor": "#f8fafc",
        "fontSize": "15px",
        "actorBkg": "#0b1f3a",
        "actorTextColor": "#ffffff",
        "actorBorder": "#0b1f3a",
        "signalColor": "#1e293b",
        "signalTextColor": "#0b1f3a",
        "noteBkgColor": "#fff7ed",
        "noteBorderColor": "#f59e0b",
        "labelBoxBkgColor": "#e6f4f4",
        "activationBkgColor": "#ccfbf1",
        "labelTextColor": "#0b1f3a",
        "loopTextColor": "#0b1f3a",
    },
    "flowchart": {"htmlLabels": True, "curve": "basis", "padding": 12, "useMaxWidth": False},
    "sequence": {"mirrorActors": False, "showSequenceNumbers": True, "actorMargin": 40, "useMaxWidth": False,
                 "messageFontSize": 15, "actorFontSize": 15, "noteFontSize": 14},
    "er": {"layoutDirection": "LR", "useMaxWidth": False},
    "state": {"useMaxWidth": False},
    "class": {"useMaxWidth": False},
    "gantt": {"useMaxWidth": False},
}

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<style>body{{margin:0;background:#fff}} #diagram{{display:inline-block;padding:24px;background:#fff}}</style>
<script src="file://{mermaid}"></script></head>
<body><div id="diagram"><pre class="mermaid">{source}</pre></div>
<script>
mermaid.initialize({config});
mermaid.run({{querySelector: '.mermaid'}}).then(() => document.body.dataset.ready = '1')
  .catch(e => {{ document.body.dataset.error = String(e); document.body.dataset.ready = '1'; }});
</script></body></html>"""


def render_all(names: list[str]) -> None:
    mermaid_js = os.environ.get("MERMAID_JS", "")
    OUT.mkdir(parents=True, exist_ok=True)
    sources = sorted(p for p in SRC.iterdir() if p.suffix in {".mmd", ".html"})
    if names:
        sources = [p for p in sources if p.stem in names]
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(device_scale_factor=2.5, viewport={"width": 1600, "height": 1200})
        for src in sources:
            if src.suffix == ".mmd":
                if not mermaid_js:
                    sys.exit("MERMAID_JS must point to mermaid.min.js")
                text = src.read_text(encoding="utf-8").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                html = PAGE.format(mermaid=Path(mermaid_js).resolve(), source=text, config=json.dumps(MERMAID_CONFIG))
                tmp = OUT / f".{src.stem}.html"
                tmp.write_text(html, encoding="utf-8")
                page.goto(tmp.as_uri())
                page.wait_for_function("document.body.dataset.ready === '1'", timeout=30_000)
                error = page.evaluate("document.body.dataset.error || ''")
                tmp.unlink()
                if error:
                    print(f"FAILED {src.name}: {error}")
                    continue
            else:
                page.goto(src.as_uri())
                page.wait_for_load_state("networkidle")
            page.locator("#diagram").screenshot(path=str(OUT / f"{src.stem}.png"))
            print(f"rendered {src.stem}.png")
        browser.close()


if __name__ == "__main__":
    render_all(sys.argv[1:])
