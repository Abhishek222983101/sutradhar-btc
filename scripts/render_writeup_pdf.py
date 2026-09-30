"""Render docs/TECHNICAL_WRITEUP.md to a styled PDF at docs/TECHNICAL_WRITEUP.pdf.
Run: uvx --with markdown2 --with weasyprint python scripts/render_writeup_pdf.py
"""

from __future__ import annotations

from pathlib import Path

import markdown2
from weasyprint import CSS, HTML

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "TECHNICAL_WRITEUP.md"
OUT = ROOT / "docs" / "TECHNICAL_WRITEUP.pdf"

CSS_TEXT = """
@page { size: A4; margin: 22mm 18mm 20mm 18mm;
  @bottom-right { content: "Sutradhar — SIH26146 · page " counter(page) " of " counter(pages); font-size: 8pt; color: #666; font-family: "IBM Plex Mono", monospace; }
}
* { box-sizing: border-box; }
body { font-family: "Archivo", "Helvetica Neue", Arial, sans-serif; font-size: 10.5pt; line-height: 1.55; color: #0a0a0a; }
h1 { font-size: 22pt; font-weight: 800; margin: 0 0 4mm; border-bottom: 3px solid #000; padding-bottom: 3mm; }
h2 { font-size: 15pt; font-weight: 800; margin: 8mm 0 3mm; color: #1d2b8f; page-break-after: avoid; }
h3 { font-size: 12pt; font-weight: 700; margin: 5mm 0 2mm; page-break-after: avoid; }
p { margin: 0 0 3mm; }
table { width: 100%; border-collapse: collapse; margin: 3mm 0 5mm; font-size: 9pt; }
th, td { border: 1px solid #999; padding: 1.6mm 2.2mm; text-align: left; vertical-align: top; }
th { background: #1d2b8f; color: #fff; font-weight: 700; }
tr:nth-child(even) td { background: #f3f4f8; }
code { font-family: "IBM Plex Mono", monospace; background: #eef0f6; padding: 0.5mm 1mm; font-size: 9pt; border-radius: 2px; }
pre { background: #16181d; color: #e8eaf0; padding: 4mm; border-radius: 3px; font-size: 8.3pt; overflow-x: auto; page-break-inside: avoid; }
pre code { background: none; color: inherit; padding: 0; }
ul, ol { margin: 0 0 3mm; padding-left: 6mm; }
li { margin-bottom: 1mm; }
strong { color: #000; }
hr { border: none; border-top: 1px solid #ccc; margin: 6mm 0; }
blockquote { border-left: 3px solid #ff9933; margin: 3mm 0; padding: 1mm 4mm; color: #333; font-style: italic; background: #fff8ee; }
.titlepage { text-align: center; page-break-after: always; padding-top: 60mm; }
.titlepage h1 { font-size: 30pt; border: none; }
.titlepage .sub { font-size: 13pt; color: #444; margin-top: 4mm; }
.titlepage .meta { margin-top: 20mm; font-family: "IBM Plex Mono", monospace; font-size: 9.5pt; color: #555; }
.badge { display: inline-block; background: #ff9933; border: 2px solid #000; padding: 1mm 3mm; font-weight: 800; font-size: 9pt; margin-top: 8mm; }
"""

TITLE = """
<div class="titlepage">
  <div class="badge">SIH 2026 · PS 26146 · NTRO</div>
  <h1>Sutradhar</h1>
  <div class="sub">Offline AI for Bitcoin Transaction Traffic — Technical Write-up</div>
  <div class="meta">
    Team Paradigm<br>
    github.com/Abhishek222983101/sutradhar-btc<br>
    Live demo: sutradhar-one-red.vercel.app
  </div>
</div>
"""


def main() -> None:
    md = SRC.read_text(encoding="utf-8")
    body = markdown2.markdown(
        md, extras=["tables", "fenced-code-blocks", "header-ids", "strike", "code-friendly"]
    )
    html = f"<html><head><meta charset='utf-8'></head><body>{TITLE}{body}</body></html>"
    HTML(string=html, base_url=str(ROOT)).write_pdf(str(OUT), stylesheets=[CSS(string=CSS_TEXT)])
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
