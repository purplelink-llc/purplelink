#!/usr/bin/env python3
"""Write site/blog/feed.xml, an Atom feed of the blog posts.

Each post under site/blog/<slug>/ (the digest has its own feed) contributes
its headline, datePublished, dateModified and description from the page's
JSON-LD and meta tags, so the feed can't drift from the posts.

  python3 scripts/gen_blog_feed.py
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "site" / "blog"
OUT = BLOG / "feed.xml"
BASE = "https://purplelink.llc"
AUTHOR = "Benjamin Ampel"


def post_meta(page: Path) -> dict | None:
    raw = page.read_text(encoding="utf-8")
    info: dict = {}
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', raw, re.S):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        for item in data.get("@graph", [data]):
            if isinstance(item, dict) and item.get("datePublished"):
                info.setdefault("title", item.get("headline", ""))
                info.setdefault("published", item["datePublished"])
                info.setdefault("updated", item.get("dateModified") or item["datePublished"])
                info.setdefault("summary", item.get("description", ""))
    if "published" not in info:
        return None
    if not info.get("title"):
        m = re.search(r"<title>(.*?)</title>", raw, re.S)
        info["title"] = re.sub(r"\s*\|.*$", "", html.unescape(m.group(1)).strip()) if m else page.parent.name
    if not info.get("summary"):
        m = re.search(r'<meta name="description" content="([^"]*)"', raw)
        info["summary"] = html.unescape(m.group(1)) if m else ""
    info["url"] = f"{BASE}/blog/{page.parent.name}/"
    return info


def stamp(day: str) -> str:
    return day if "T" in day else f"{day}T12:00:00Z"


def main() -> None:
    posts = []
    for page in sorted(BLOG.glob("*/index.html")):
        if page.parent.name == "digest":
            continue
        meta = post_meta(page)
        if meta:
            posts.append(meta)
    posts.sort(key=lambda p: (p["published"], p["url"]), reverse=True)
    updated = max((stamp(p["updated"]) for p in posts), default="2026-01-01T12:00:00Z")
    entries = "".join(
        f"""
  <entry>
    <title>{escape(p['title'])}</title>
    <link href="{p['url']}"/>
    <id>{p['url']}</id>
    <published>{stamp(p['published'])}</published>
    <updated>{stamp(p['updated'])}</updated>
    <summary>{escape(p['summary'])}</summary>
  </entry>"""
        for p in posts
    )
    OUT.write_text(
        f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Purplelink blog</title>
  <subtitle>Notes from a one-person studio making tools for academic researchers.</subtitle>
  <link href="{BASE}/blog/feed.xml" rel="self"/>
  <link href="{BASE}/blog/"/>
  <id>{BASE}/blog/</id>
  <updated>{updated}</updated>
  <author><name>{AUTHOR}</name></author>{entries}
</feed>
""",
        encoding="utf-8",
    )
    print(f"wrote {OUT.relative_to(ROOT)} ({len(posts)} posts)")


if __name__ == "__main__":
    main()
