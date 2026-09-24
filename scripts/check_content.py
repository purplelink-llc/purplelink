#!/usr/bin/env python3
"""Content checks for pages published to site/, run before every deploy.

The weekly cloud routines publish guides and blog posts straight to main. Two
of their failure modes reached the live site: bracketed [SCREENSHOT: ...]
notes left in the HTML, and guides that were never added to /guides/, so
nothing on the site linked to them. This catches both, plus inline styles
(the CSP forbids them) and Amazon links without the Associates tag or the
required disclosure.

Usage:
    python3 scripts/check_content.py            # report, always exit 0
    python3 scripts/check_content.py --strict   # exit 1 on any problem

Netlify's build runs the report form so one bad page never blocks the daily
digest deploy; the routines and deploy.sh run --strict before committing.
The cron-owned daily digest (site/blog/digest/) is skipped.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "site"
TAG = "purplelinkpl-20"
DISCLOSURE = "As an Amazon Associate I earn from qualifying purchases"

PLACEHOLDER = re.compile(r"\[(?:SCREENSHOT|INSERT|TODO|TK)\b[^\]]*\]|\bTODO:", re.I)
INLINE_STYLE = re.compile(r"<[a-zA-Z][^>]*\sstyle\s*=", re.S)
# Product and search pages only; links to Amazon's own help or policy pages
# are citations, not affiliate links.
AMAZON_LINK = re.compile(
    r'<a\b[^>]*href="https://(?:www\.)?amazon\.com/(?:dp/|s\?|gp/product/|[^"/]+/dp/)[^"]*"[^>]*>', re.S
)


def skip(page: Path) -> bool:
    rel = page.relative_to(SITE).as_posix()
    return rel.startswith("blog/digest/")


def visible(html: str) -> str:
    """Drop scripts, styles and comments so JSON-LD and CSS never trip a check."""
    html = re.sub(r"<script\b.*?</script>", "", html, flags=re.S | re.I)
    html = re.sub(r"<style\b.*?</style>", "", html, flags=re.S | re.I)
    return re.sub(r"<!--.*?-->", "", html, flags=re.S)


def main() -> int:
    strict = "--strict" in sys.argv
    problems: list[str] = []

    for page in sorted(SITE.rglob("*.html")):
        if skip(page):
            continue
        rel = page.relative_to(SITE).as_posix()
        raw = page.read_text(encoding="utf-8", errors="replace")
        body = visible(raw)
        for m in PLACEHOLDER.finditer(body):
            problems.append(f"{rel}: placeholder left in page: {m.group(0)[:60]}")
        if INLINE_STYLE.search(body):
            problems.append(f"{rel}: inline style attribute (CSP forbids it)")
        amazon = AMAZON_LINK.findall(raw)
        for tag_html in amazon:
            href = re.search(r'href="([^"]*)"', tag_html).group(1)
            if f"tag={TAG}" not in href:
                problems.append(f"{rel}: Amazon link without tag={TAG}: {href[:70]}")
            if 'rel="sponsored' not in tag_html:
                problems.append(f"{rel}: Amazon link without rel=\"sponsored ...\": {href[:70]}")
        if amazon and DISCLOSURE not in body:
            problems.append(f"{rel}: has Amazon links but no Associates disclosure sentence")

    # Every guide and blog post must be reachable from its index.
    for section, index_rel in (("guides", "guides/index.html"), ("blog", "blog/index.html")):
        index = (SITE / index_rel).read_text(encoding="utf-8", errors="replace")
        for d in sorted((SITE / section).iterdir()):
            if not d.is_dir() or not (d / "index.html").exists():
                continue
            if section == "blog" and d.name in {"digest", "topics"}:
                continue
            if f'href="/{section}/{d.name}/"' not in index:
                problems.append(f"{section}/{d.name}/: not linked from /{index_rel.rsplit('/', 1)[0]}/")

    if problems:
        print(f"content check: {len(problems)} problem(s)")
        for p in problems:
            print(f"  - {p}")
        return 1 if strict else 0
    print("content check: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
