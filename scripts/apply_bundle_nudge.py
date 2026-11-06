#!/usr/bin/env python3
"""Stamp one honest bundle line under the buy buttons of each Mac-app product page
(buyer revenue program, piece 7, docs/designs/buyer-revenue-program.md).

Since 2026-11-06 every pair and every triple is a percent off the parts' own prices (any 2: 25% off, any 3: 40%
off), so every app page gets the same line and no page needs a computed saving. The percents come from
site/suite/bundle.js (BUNDLE_PERCENT), which a test keeps equal to the server's netlify/lib/bundles.mjs. The line
states percents only, never a dollar figure (site-tests/test_intl_advertise.py allows catalog prices alone on these
pages). No deadline, no countdown, no "limited" wording.

The line sits between the bundle-nudge markers, after the last line that belongs to the buy buttons (the
send-to-mac block, else the .buy-suite sentence, else the .buy-assurance line, else the app-hero-actions div).

  python3 scripts/apply_bundle_nudge.py           # rewrite in place
  python3 scripts/apply_bundle_nudge.py --check   # exit 1 if any page is out of date
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
BUNDLE_JS = SITE / "suite" / "bundle.js"
START = "<!-- bundle-nudge:start -->"
END = "<!-- bundle-nudge:end -->"

# page slug -> part key (every app page in the Suite)
PAGES = {
    "moderntex": "moderntex",
    "outbound-veil": "outbound-veil",
    "legroom": "legroom",
    "keyfeel": "keyfeel",
    "tapefolio": "tapefolio",
    "panely": "panely",
    "summonly": "summonly",
    "nee": "nee",
    "lenses": "lenses",
}

def _js_object(src: str, name: str) -> dict:
    m = re.search(name + r"\s*=\s*(\{[^}]*\})", src)
    if not m:
        raise SystemExit(f"{BUNDLE_JS.name}: no {name}")
    return json.loads(re.sub(r"([{,]\s*)([A-Za-z0-9_-]+)\s*:", r'\1"\2":', m.group(1).replace("'", '"')))


def percents() -> dict:
    """{"2": 25, "3": 40}, read from BUNDLE_PERCENT in bundle.js."""
    return _js_object(BUNDLE_JS.read_text(encoding="utf-8"), "BUNDLE_PERCENT")


def link(slug: str) -> str:
    return ("/suite/?utm_source=purplelink&amp;utm_medium=product-page&amp;utm_campaign=bundle-nudge"
            f"&amp;utm_content={slug}#bundle")


def sentence(tiers: dict) -> str:
    """The plain text of the line, the same for every page."""
    return (f"Add any second Mac Suite app and save {tiers['2']}% on both, or any third for {tiers['3']}% off all "
            "three.")


def markup(slug: str, text: str) -> str:
    return (f'{START}<p class="buy-bundle">{html.escape(text, quote=False)} '
            f'<a href="{link(slug)}">Choose the apps</a>.</p>{END}')


BLOCK = re.compile(r"[ \t]*" + re.escape(START) + r".*?" + re.escape(END) + r"\n", re.S)
ACTIONS = re.compile(r'<div class="app-hero-actions"[^>]*>.*?</div>\n', re.S)
AFTER = [
    re.compile(r"<!-- send-to-mac:end -->\n"),
    re.compile(r'<p class="buy-suite">.*?</p>\n', re.S),
    re.compile(r'<p class="buy-assurance">.*?</p>\n', re.S),
]


def render(text: str, slug: str, line: str | None, rel: str) -> str:
    text = BLOCK.sub("", text, count=1)
    if line is None:
        return text
    actions = ACTIONS.search(text)
    if not actions:
        raise SystemExit(f"{rel}: no app-hero-actions div")
    anchor = actions
    for pat in AFTER:
        m = pat.search(text, actions.end())
        if m and m.start() - actions.end() < 3000:
            anchor = m
            break
    return text[: anchor.end()] + "        " + markup(slug, line) + "\n" + text[anchor.end():]


def main(argv: list[str]) -> int:
    check = "--check" in argv
    line = sentence(percents())
    stale = []
    for slug in PAGES:
        path = SITE / slug / "index.html"
        rel = str(path.relative_to(ROOT))
        old = path.read_text(encoding="utf-8")
        new = render(old, slug, line, rel)
        if new != old:
            stale.append(rel)
            if not check:
                path.write_text(new, encoding="utf-8")
    if check and stale:
        print("bundle nudge out of date (run python3 scripts/apply_bundle_nudge.py):\n  " + "\n  ".join(stale))
        return 1
    if not check:
        print(f"updated {len(stale)} page(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
