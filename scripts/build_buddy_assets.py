#!/usr/bin/env python3
"""Build the two files Buddy, the site chat, reads (docs/designs/buddy-chat.md, section 4):

- backend/latextools/buddy_facts.py: the facts block, copied from site/llms.txt. Build output, not in git: backend/app.py
  writes it on every deploy and test run (latextools/buddy_build.py); this script writes it too, for convenience.
- site/buddy-chat/links.json: the page paths in site/sitemap.xml, the only links the chat panel will draw.

Run after changing llms.txt or adding pages:  python3 scripts/build_buddy_assets.py
Check mode (used by the tests):                python3 scripts/build_buddy_assets.py --check
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITEMAP = ROOT / "site" / "sitemap.xml"
LINKS_JSON = ROOT / "site" / "buddy-chat" / "links.json"


def write_facts() -> None:
    """The facts are build output (not in git); latextools/buddy_build.py makes them, as app.py does at deploy."""
    sys.path.insert(0, str(ROOT / "backend"))
    from latextools import buddy_build
    print("wrote", buddy_build.write_facts().relative_to(ROOT))


def links_source() -> str:
    xml = SITEMAP.read_text(encoding="utf-8")
    paths = {re.sub(r"^https://purplelink\.llc", "", u) or "/"
             for u in re.findall(r"<loc>\s*(https://purplelink\.llc[^<\s]*)\s*</loc>", xml)}
    paths = {p if p.endswith("/") else p + "/" for p in paths if "?" not in p and not p.endswith((".pdf", ".xml"))}
    return json.dumps(sorted(paths), indent=0) + "\n"


def main() -> int:
    # Only links.json is committed; --check (the tests) covers it. The facts are made at deploy and test time.
    outputs = {LINKS_JSON: links_source()}
    if "--check" in sys.argv:
        stale = [str(p.relative_to(ROOT)) for p, src in outputs.items()
                 if not p.exists() or p.read_text(encoding="utf-8") != src]
        if stale:
            print("stale, run python3 scripts/build_buddy_assets.py:", ", ".join(stale))
            return 1
        return 0
    for path, src in outputs.items():
        path.write_text(src, encoding="utf-8")
        print("wrote", path.relative_to(ROOT))
    write_facts()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
