"""
Convert report/report.md and report/ai_use_appendix.md to PDF via
styled HTML + Chrome headless. Mermaid blocks are replaced with a
hand-crafted SVG diagram so no JS renderer is required.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from markdown_it import MarkdownIt

REPORT_DIR = Path(__file__).resolve().parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# ---------------------------------------------------------------------------
# Workflow SVG (replaces the mermaid code block)
# ---------------------------------------------------------------------------

def _workflow_svg() -> str:
    W, H = 580, 748

    C_TERM   = "#0f172a"
    C_DATA   = "#1e3a5f"
    C_STRAT  = "#1d4ed8"
    C_GRAY   = "#1f2937"
    C_GREEN  = "#065f46"
    C_PURPLE = "#5b21b6"
    EDGE     = "#6b7280"

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" '
        f'font-family="Inter,-apple-system,BlinkMacSystemFont,sans-serif" '
        f'style="display:block;background:#fff;">'
    )

    # ── Arrow-head marker ──────────────────────────────────────────────────
    parts.append(
        '<defs>'
        '<marker id="ah" markerWidth="9" markerHeight="6.5" '
        'refX="8.5" refY="3.25" orient="auto">'
        '<polygon points="0 0,9 3.25,0 6.5" fill="#6b7280"/>'
        '</marker>'
        '</defs>'
    )

    # ── Helper: straight arrow ─────────────────────────────────────────────
    def arr(x1, y1, x2, y2, dash: bool = False) -> str:
        da = ' stroke-dasharray="5 3"' if dash else ''
        return (
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{EDGE}" stroke-width="1.5" fill="none"{da} '
            f'marker-end="url(#ah)"/>'
        )

    # ── Helper: path arrow ─────────────────────────────────────────────────
    def parr(d: str, dash: bool = False) -> str:
        da = ' stroke-dasharray="5 3"' if dash else ''
        return (
            f'<path d="{d}" stroke="{EDGE}" stroke-width="1.5" '
            f'fill="none"{da} marker-end="url(#ah)"/>'
        )

    # ── Helper: rounded-rect node ──────────────────────────────────────────
    def node(cx, cy, w, h, fill, label, sub: str = "", fs: float = 9.5) -> str:
        x, y = cx - w // 2, cy - h // 2
        s = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5" fill="{fill}"/>'
        if sub:
            s += (
                f'<text x="{cx}" y="{cy - 7}" text-anchor="middle" '
                f'dominant-baseline="middle" fill="#fff" font-size="{fs}" '
                f'font-weight="500">{label}</text>'
                f'<text x="{cx}" y="{cy + 8}" text-anchor="middle" '
                f'dominant-baseline="middle" fill="rgba(255,255,255,.65)" '
                f'font-size="7.5">{sub}</text>'
            )
        else:
            s += (
                f'<text x="{cx}" y="{cy}" text-anchor="middle" '
                f'dominant-baseline="middle" fill="#fff" font-size="{fs}" '
                f'font-weight="500">{label}</text>'
            )
        return s

    # ── Helper: terminal oval ──────────────────────────────────────────────
    def term(cx, cy, rx, ry, label, fs: float = 10) -> str:
        return (
            f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{C_TERM}"/>'
            f'<text x="{cx}" y="{cy}" text-anchor="middle" '
            f'dominant-baseline="middle" fill="#fff" font-size="{fs}" '
            f'font-weight="600">{label}</text>'
        )

    # ── Helper: small edge label ───────────────────────────────────────────
    def elabel(x, y, text, anchor: str = "middle") -> str:
        return (
            f'<text x="{x}" y="{y}" text-anchor="{anchor}" '
            f'fill="#9ca3af" font-size="7.5" font-style="italic">{text}</text>'
        )

    # ══════════════════════════════════════════════════════════════════════
    # Node positions (cx, cy)
    # ══════════════════════════════════════════════════════════════════════
    # START / END
    SX, SY   = 290, 36
    EX, EY   = 290, 714

    # Main spine
    MDX, MDY = 290, 100    # Market Data
    AGX, AGY = 290, 247    # Agreement Profile
    SAX, SAY = 290, 628    # Save JSON Output

    # Parallel strategy row (y=174)
    AX, AY = 118, 174
    BX, BY = 290, 174
    CX, CY = 462, 174

    # Evaluator row (y=328)
    CEX, CEY = 152, 328    # Consensus Evaluator
    DEX, DEY = 444, 328    # Disagreement Evaluator

    # Debate branch (right side)
    DDX, DDY = 444, 424    # Debate Dispatch
    DTX, DTY = 444, 504    # Debate A | B | C
    DSX, DSY = 444, 580    # Debate Summary

    # ── EDGES (drawn before nodes) ────────────────────────────────────────

    # START → Market Data
    parts.append(arr(SX, SY + 18, MDX, MDY - 17))

    # Market Data → 3 strategies
    parts.append(arr(MDX, MDY + 17, AX, AY - 16))
    parts.append(arr(MDX, MDY + 17, BX, BY - 16))
    parts.append(arr(MDX, MDY + 17, CX, CY - 16))

    # 3 strategies → Agreement Profile (fan-in via elbows)
    parts.append(parr(f"M {AX} {AY+16} L {AX} {AGY-22} L {AGX-12} {AGY-16}"))
    parts.append(arr(BX, BY + 16, AGX, AGY - 16))
    parts.append(parr(f"M {CX} {CY+16} L {CX} {AGY-22} L {AGX+12} {AGY-16}"))

    # Agreement Profile → Consensus Evaluator (left, "Unanimous")
    parts.append(parr(f"M {AGX-18} {AGY+16} L {CEX+10} {CEY-16}"))
    parts.append(elabel(202, 296, "Unanimous", "end"))

    # Agreement Profile → Disagreement Evaluator (right, "Split")
    parts.append(parr(f"M {AGX+18} {AGY+16} L {DEX-10} {DEY-16}"))
    parts.append(elabel(382, 296, "Split", "start"))

    # Consensus Evaluator → Save JSON Output (left-spine elbow)
    parts.append(parr(f"M {CEX} {CEY+16} L {CEX} {SAY-4} L {SAX-14} {SAY-16}"))

    # Disagreement Evaluator → Save JSON (dashed, --skip-debate path)
    parts.append(parr(
        f"M {DEX-14} {DEY+16} L {DEX-14} {SAY-38} L {SAX+14} {SAY-16}",
        dash=True,
    ))
    parts.append(elabel(310, 530, "–– agree / –skip-debate"))

    # Disagreement Evaluator → Debate Dispatch (solid, debate path)
    parts.append(arr(DEX, DEY + 16, DDX, DDY - 16))
    parts.append(elabel(DDX + 90, 378, "debate enabled", "start"))

    # Debate Dispatch → Debate A|B|C
    parts.append(arr(DDX, DDY + 16, DTX, DTY - 16))

    # Debate A|B|C → Debate Summary
    parts.append(arr(DTX, DTY + 16, DSX, DSY - 16))

    # Debate Summary → Save JSON Output
    parts.append(parr(f"M {DSX} {DSY+16} L {DSX} {SAY-10} L {SAX+14} {SAY-16}"))

    # Save JSON Output → END
    parts.append(arr(SAX, SAY + 16, EX, EY - 18))

    # ── NODES (drawn over edges) ──────────────────────────────────────────
    parts.append(term(SX,  SY,  52, 18, "START"))
    parts.append(node(MDX, MDY, 215, 34, C_DATA,   "Market Data Component", "no LLM calls"))
    parts.append(node(AX,  AY,  152, 32, C_STRAT,  "Strategy A"))
    parts.append(node(BX,  BY,  152, 32, C_STRAT,  "Strategy B"))
    parts.append(node(CX,  CY,  152, 32, C_STRAT,  "Strategy C"))
    parts.append(node(AGX, AGY, 215, 32, C_GRAY,   "Agreement Profile"))
    parts.append(node(CEX, CEY, 195, 32, C_GRAY,   "Consensus Evaluator"))
    parts.append(node(DEX, DEY, 200, 32, C_GRAY,   "Disagreement Evaluator"))
    parts.append(node(DDX, DDY, 165, 32, C_PURPLE, "Debate Dispatch"))
    parts.append(node(DTX, DTY, 165, 32, C_PURPLE, "Debate A | B | C", "parallel"))
    parts.append(node(DSX, DSY, 165, 32, C_PURPLE, "Debate Summary"))
    parts.append(node(SAX, SAY, 205, 32, C_GREEN,  "Save JSON Output"))
    parts.append(term(EX,  EY,  52, 18, "END"))

    parts.append("</svg>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

@page {
    size: letter;
    margin: 1.05in 1.05in 1.0in 1.05in;
}

body {
    font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 10.5pt;
    line-height: 1.65;
    color: #1a1a1a;
}

h1 {
    font-size: 19pt; font-weight: 700; color: #111;
    margin: 0 0 26px 0; padding-bottom: 10px;
    border-bottom: 2px solid #111;
}
h2 {
    font-size: 13.5pt; font-weight: 700; color: #111;
    margin: 30px 0 11px 0; padding-bottom: 5px;
    border-bottom: 1px solid #d1d5db;
}
h3 { font-size: 11pt; font-weight: 600; color: #1f2937; margin: 20px 0 7px 0; }
h4 { font-size: 10.5pt; font-weight: 600; color: #374151; margin: 14px 0 5px 0; }

p { margin: 0 0 11px 0; }

ul, ol { margin: 0 0 11px 1.35em; }
li { margin-bottom: 3px; }
li > ul, li > ol { margin-top: 3px; margin-bottom: 0; }

a { color: #1a56db; text-decoration: none; }

code {
    font-family: 'JetBrains Mono', 'SF Mono', 'Fira Code', Consolas, monospace;
    font-size: 8.8pt;
    background: #f3f4f6;
    border: 1px solid #e5e7eb;
    border-radius: 3px;
    padding: 1px 5px;
    color: #be123c;
}

pre {
    background: #f8f9fa;
    border: 1px solid #e5e7eb;
    border-radius: 5px;
    padding: 12px 14px;
    margin: 0 0 14px 0;
    page-break-inside: avoid;
}
pre code {
    background: none; border: none; padding: 0;
    color: #1a1a1a; font-size: 8.2pt; line-height: 1.5;
}

blockquote {
    border-left: 3px solid #374151;
    background: #f9fafb;
    margin: 0 0 14px 0;
    padding: 10px 14px;
    color: #374151;
    font-style: italic;
    page-break-inside: avoid;
}
blockquote p { margin-bottom: 5px; }
blockquote p:last-child { margin-bottom: 0; }

table {
    width: 100%;
    border-collapse: collapse;
    font-size: 9.2pt;
    margin: 0 0 16px 0;
    page-break-inside: avoid;
}
thead tr { background: #1f2937; color: #fff; }
thead th { padding: 7px 9px; text-align: left; font-weight: 600; }
tbody tr:nth-child(even) { background: #f9fafb; }
tbody tr:nth-child(odd)  { background: #fff; }
tbody td { padding: 6px 9px; border-bottom: 1px solid #e5e7eb; vertical-align: top; }

.diagram-wrap {
    margin: 0 0 16px 0;
    page-break-inside: avoid;
    text-align: center;
}
.diagram-caption {
    font-size: 8pt; color: #6b7280; margin-top: 6px; font-style: italic;
}

hr { border: none; border-top: 1px solid #e5e7eb; margin: 22px 0; }
strong { font-weight: 600; }
em { font-style: italic; }
"""

# ---------------------------------------------------------------------------
# Markdown → HTML
# ---------------------------------------------------------------------------

_MERMAID_FENCE = re.compile(
    r"^(`{3}|~{3})mermaid\s*\n(.*?)^\1\s*$",
    re.MULTILINE | re.DOTALL,
)


def md_to_html(source: str, title: str) -> str:
    md = MarkdownIt("commonmark", {"html": True}).enable("table")

    def _replace_mermaid(m: re.Match) -> str:
        svg = _workflow_svg()
        return (
            f'\n\n<div class="diagram-wrap">\n{svg}\n'
            '<p class="diagram-caption">Figure 1 — StockTrader LangGraph workflow</p>\n'
            "</div>\n\n"
        )

    processed = _MERMAID_FENCE.sub(_replace_mermaid, source)
    body = md.render(processed)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>{CSS}</style>
</head>
<body>
{body}
</body>
</html>"""


# ---------------------------------------------------------------------------
# HTML → PDF via Chrome headless
# ---------------------------------------------------------------------------

def html_to_pdf(html_path: Path, pdf_path: Path) -> None:
    cmd = [
        CHROME,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--run-all-compositor-stages-before-draw",
        "--disable-extensions",
        "--print-to-pdf-no-header",
        f"--print-to-pdf={pdf_path}",
        html_path.as_uri(),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(
            f"Chrome exited {result.returncode}.\n{result.stderr[:600]}"
        )


def convert(md_path: Path, pdf_path: Path, title: str) -> None:
    source = md_path.read_text(encoding="utf-8")
    html = md_to_html(source, title)
    with tempfile.NamedTemporaryFile(
        suffix=".html", delete=False, mode="w", encoding="utf-8"
    ) as fh:
        fh.write(html)
        tmp = Path(fh.name)
    try:
        html_to_pdf(tmp, pdf_path)
    finally:
        tmp.unlink(missing_ok=True)
    size = pdf_path.stat().st_size // 1024
    print(f"  ✓  {pdf_path.name}  ({size} KB)")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Building PDFs …")
    convert(
        REPORT_DIR / "report.md",
        REPORT_DIR / "report.pdf",
        "Comparative Analysis Report",
    )
    convert(
        REPORT_DIR / "ai_use_appendix.md",
        REPORT_DIR / "ai_use_appendix.pdf",
        "AI Use Appendix",
    )
    print("Done.")
