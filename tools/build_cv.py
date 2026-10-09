#!/usr/bin/env python3
"""Render a CV markdown file (cv/*.md) to a styled A4 PDF via headless Chromium.

Usage: python3 tools/build_cv.py cv/track1-realestate-hospitality-he.md [out.pdf]
Hebrew files (containing Hebrew letters in the title) render RTL automatically.
"""
import html
import re
import subprocess
import sys
import tempfile
from pathlib import Path

CHROME_CANDIDATES = [
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    "chromium",
    "google-chrome",
]

CSS = """
@page { size: A4; margin: 12mm 15mm; }
* { box-sizing: border-box; }
body { font-family: "Liberation Sans", "DejaVu Sans", Arial, sans-serif; font-size: 9.4pt;
       line-height: 1.4; color: #1f2430; margin: 0; }
h1 { font-size: 22pt; letter-spacing: .5px; margin: 0 0 2px; color: #14213d; }
.contact { color: #555; margin: 0 0 4px; }
.headline { font-weight: bold; color: #b5651d; margin: 0 0 10px; font-size: 10.5pt; }
h2 { break-after: avoid;  font-size: 10.5pt; text-transform: uppercase; letter-spacing: 1px; color: #14213d;
     border-bottom: 1.5px solid #b5651d; padding-bottom: 2px; margin: 10px 0 5px; }
h3 { font-size: 10.5pt; margin: 7px 0 0; color: #14213d; }
p { margin: 0 0 4px; }
p.org { color: #444; margin: 0 0 3px; }
ul { margin: 0 0 4px; padding-inline-start: 16px; }
li { margin: 0 0 2px; }
strong { color: #14213d; }
.ltr { direction: ltr; unicode-bidi: isolate; }
"""


def inline(text: str) -> str:
    t = html.escape(text)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    # keep phone numbers / emails / Latin runs stable inside RTL text
    t = re.sub(r"(\+?\d[\d\- ]{6,}\d)", r'<span class="ltr">\1</span>', t)
    return t


def md_to_html(md: str) -> tuple[str, bool]:
    lines = md.splitlines()
    rtl = bool(re.search(r"[֐-׿]", lines[0]))
    out, in_list, header_done = [], False, False
    for i, raw in enumerate(lines):
        line = raw.rstrip()
        if not line.startswith("- ") and in_list:
            out.append("</ul>")
            in_list = False
        if not line:
            continue
        if line.startswith("# "):
            out.append(f"<h1>{inline(line[2:])}</h1>")
        elif line.startswith("## "):
            header_done = True
            out.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("### "):
            out.append(f"<h3>{inline(line[4:])}</h3>")
        elif line.startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{inline(line[2:])}</li>")
        elif not header_done:
            cls = "headline" if line.startswith("**") else "contact"
            out.append(f'<p class="{cls}">{inline(line)}</p>')
        elif line.startswith("**") and i > 0 and lines[i - 1].startswith("### "):
            out.append(f'<p class="org">{inline(line)}</p>')
        else:
            out.append(f"<p>{inline(line)}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out), rtl


def find_chrome() -> str:
    for c in CHROME_CANDIDATES:
        try:
            subprocess.run([c, "--version"], capture_output=True, check=True)
            return c
        except (OSError, subprocess.CalledProcessError):
            continue
    sys.exit("Chrome/Chromium not found")


def main() -> None:
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".pdf")
    body, rtl = md_to_html(src.read_text(encoding="utf-8"))
    lang, direction = ("he", "rtl") if rtl else ("en", "ltr")
    doc = (f'<!DOCTYPE html><html lang="{lang}" dir="{direction}"><head><meta charset="utf-8">'
           f"<style>{CSS}</style></head><body>{body}</body></html>")
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(doc)
        tmp = f.name
    subprocess.run([find_chrome(), "--headless", "--no-sandbox", "--disable-gpu",
                    "--no-pdf-header-footer", f"--print-to-pdf={dst.resolve()}",
                    f"file://{tmp}"], check=True, capture_output=True)
    print(dst)


if __name__ == "__main__":
    main()
