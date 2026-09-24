#!/usr/bin/env python3
"""
Build site/search-index.json for the /search/ page.

One entry per indexable page: its path, title (without the " | Purplelink"
suffix), meta description, the section it belongs to, and the page's h2
headings, which is where most of a guide's vocabulary lives. The same pages
as the sitemap: noindex pages and the cron-owned blog/digest/ are left out.

Usage:
    python3 scripts/gen_search_index.py
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
OUT = SITE / "search-index.json"

EXCLUDE_PREFIXES = ("blog/digest", "assets", "search")
NOINDEX_RE = re.compile(r'<meta[^>]+name=["\']robots["\'][^>]*noindex', re.I)
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
DESC_RE = re.compile(r'<meta\s+name="description"\s+content="([^"]*)"', re.S)
H2_RE = re.compile(r"<h2[^>]*>(.*?)</h2>", re.S)
TAG_RE = re.compile(r"<[^>]+>")

SECTIONS = {
    "tools": "Tool",
    "guides": "Guide",
    "blog": "Blog",
    "templates": "Template",
    "format": "Reference format",
}
PRODUCT_PAGES = {"moderntex", "vitae", "globepin", "haea", "scholar-utility-belt", "kits", "products", "pricing", "labs", "desk"}


def clean(text: str) -> str:
    return " ".join(html.unescape(TAG_RE.sub(" ", text)).split())


def section_for(rel: str) -> str:
    first = rel.split("/", 1)[0]
    if rel.startswith("tools/paper-review"):
        return "Paper Review"
    if first in SECTIONS:
        return SECTIONS[first]
    if first in PRODUCT_PAGES:
        return "Product"
    return "Page"


def main() -> int:
    entries = []
    for page in sorted(SITE.rglob("index.html")):
        rel = page.parent.relative_to(SITE).as_posix()
        rel = "" if rel == "." else rel
        if any(rel.startswith(p) for p in EXCLUDE_PREFIXES):
            continue
        text = page.read_text(encoding="utf-8", errors="replace")
        if NOINDEX_RE.search(text):
            continue
        title_m = TITLE_RE.search(text)
        if not title_m:
            continue
        title = clean(title_m.group(1))
        title = re.sub(r"\s*[|·-]\s*Purplelink( LLC)?$", "", title)
        desc_m = DESC_RE.search(text)
        heads = [clean(h) for h in H2_RE.findall(text)]
        heads = [h for h in heads if h and len(h) < 90][:12]
        entries.append({
            "u": "/" + (rel + "/" if rel else ""),
            "t": title,
            "d": clean(desc_m.group(1)) if desc_m else "",
            "s": section_for(rel),
            "h": heads,
        })
    OUT.write_text(json.dumps(entries, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"search index: {len(entries)} pages, {OUT.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
