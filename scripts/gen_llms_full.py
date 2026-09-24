#!/usr/bin/env python3
"""Write site/llms-full.txt: the readable text of the key pages, in one file.

llms.txt is the short index for language models; llms-full.txt carries the
pages themselves (products, paid tools, apps, the main guides) so an assistant
can answer "what does Paper Review check" or "what does ModernTex cost" from
the site's own words. It is generated from the HTML at deploy time, so it can't
drift from the pages the way the hand-written llms.txt once did.

  python3 scripts/gen_llms_full.py
"""
from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
OUT = SITE / "llms-full.txt"
BASE = "https://purplelink.llc"

PAGES = [
    "products/",
    "moderntex/",
    "vitae/",
    "vitae/plus/",
    "tools/paper-review/",
    "tools/paper-review/sample/",
    "tools/paper-review/packs/",
    "tools/paper-review/revision/",
    "tools/response-review/",
    "tools/citation-gap/",
    "tools/anonymity-check/",
    "tools/cover-letter/",
    "tools/resume-review/",
    "scholar-utility-belt/",
    "tools/",
    "tools/latex-to-pdf/",
    "tools/bib-validator/",
    "tools/citation-generator/",
    "globepin/",
    "haea/",
    "about/",
    "guides/methodology-problems-peer-reviewers-flag/",
    "guides/get-feedback-on-a-paper-before-submitting/",
    "guides/ai-policy-checking-your-own-manuscript/",
    "guides/overleaf-alternative-mac/",
    "guides/best-mac-latex-editors/",
]

SKIP_TAGS = {"script", "style", "noscript", "svg", "header", "footer", "nav", "form", "button", "template"}
BLOCK_TAGS = {"p", "li", "h1", "h2", "h3", "h4", "dt", "dd", "tr", "pre", "summary", "figcaption", "blockquote", "br", "div", "section"}


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0
        self.in_main = 0
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True
        if tag == "main":
            self.in_main += 1
        if tag in SKIP_TAGS:
            self.skip += 1
        if tag in BLOCK_TAGS:
            self.out.append("\n")
        if tag in ("h1", "h2", "h3") and not self.skip and self.in_main:
            self.out.append({"h1": "# ", "h2": "## ", "h3": "### "}[tag])
        if tag == "li" and not self.skip and self.in_main:
            self.out.append("- ")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "main":
            self.in_main -= 1
        if tag in SKIP_TAGS and self.skip:
            self.skip -= 1
        if tag in BLOCK_TAGS:
            self.out.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self.skip or not self.in_main:
            return
        self.out.append(data)


def page_text(rel: str) -> tuple[str, str]:
    raw = (SITE / rel / "index.html").read_text(encoding="utf-8")
    p = _Text()
    p.feed(raw)
    text = "".join(p.out)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return html.unescape(p.title.strip()), text


def main() -> None:
    parts = [
        "# Purplelink LLC: full text of the main pages\n",
        "> The readable text of Purplelink's product, tool, app and guide pages, "
        "generated from the site. The short index is at https://purplelink.llc/llms.txt.\n",
    ]
    for rel in PAGES:
        if not (SITE / rel / "index.html").exists():
            continue
        title, text = page_text(rel)
        parts.append(f"\n\n---\n\nSource: {BASE}/{rel}\nTitle: {title}\n\n{text}\n")
    OUT.write_text("".join(parts), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB, {len(PAGES)} pages)")


if __name__ == "__main__":
    main()
