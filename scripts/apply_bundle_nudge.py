#!/usr/bin/env python3
"""Stamp one honest "pick two" bundle line under the buy buttons of each Mac-app product page
(buyer revenue program, piece 7, docs/designs/buyer-revenue-program.md).

The numbers come from site/suite/bundle.js (BUNDLE_PRICING and PART_PRICE), which a test already keeps equal to the
server's netlify/lib/bundles.mjs. The line names only the pairings that really cost less than buying the two apps
separately; a page where no pairing saves gets no line. No deadline, no countdown, no "limited" wording.

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

# page slug -> part key in PART_PRICE
PAGES = {
    "moderntex": "moderntex",
    "outbound-veil": "outbound-veil",
    "legroom": "legroom",
    "keyfeel": "keyfeel",
    "tapefolio": "tapefolio",
    "panely": "panely",
    "summonly": "summonly",
    "nee": "nee",
}

NAMES = {
    "moderntex": "ModernTex", "outbound-veil": "Outbound Veil", "legroom": "Legroom", "keyfeel": "Keyfeel",
    "tapefolio": "Tapefolio", "panely": "Panely", "summonly": "Summonly", "nee": "Née", "lenses": "Lenses", "vitae-plus": "Vitae Plus",
}


def _js_object(src: str, name: str) -> dict:
    m = re.search(name + r"\s*=\s*(\{[^}]*\})", src)
    if not m:
        raise SystemExit(f"{BUNDLE_JS.name}: no {name}")
    return json.loads(re.sub(r"([{,]\s*)([A-Za-z0-9_-]+)\s*:", r'\1"\2":', m.group(1).replace("'", '"')))


def prices() -> tuple[dict, dict]:
    src = BUNDLE_JS.read_text(encoding="utf-8")
    return _js_object(src, "BUNDLE_PRICING"), _js_object(src, "PART_PRICE")


def dollars(cents: int) -> str:
    return f"${cents / 100:.2f}"


def link(slug: str) -> str:
    return ("/suite/?utm_source=purplelink&amp;utm_medium=product-page&amp;utm_campaign=bundle-nudge"
            f"&amp;utm_content={slug}#bundle")


def _join(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " or " + names[-1]


def sentence(part: str, bundles: dict, parts: dict) -> str | None:
    """The plain text of the line for one page, or None when no pairing saves money."""
    own = parts[part]
    two, three = bundles["2"], bundles["3"]
    others = {k: v for k, v in parts.items() if k != part}
    savers = sorted((k for k, v in others.items() if own + v > two), key=lambda k: (-others[k], NAMES[k]))
    if not savers:
        return None
    extra = two - own
    if len(savers) == len(others):
        # Every pairing saves. Pick 3 is named only when every set of three containing this app costs more
        # separately than the pick-3 price.
        cheapest_two = sum(sorted(others.values())[:2])
        line = (f"Add a second Mac app for {dollars(extra)} more: any two apps from the Mac Suite are "
                f"{dollars(two)}")
        if own + cheapest_two > three:
            line += f", or any three are {dollars(three)}"
        return line + "."
    # Only catalog prices on these pages (site-tests/test_intl_advertise.py): no computed difference.
    return (f"Pair it with {_join([NAMES[k] for k in savers])} in the Mac Suite's pick-two bundle and the two "
            f"apps are {dollars(two)} together, less than buying them separately. "
            "Other pairings cost less on their own.")


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
    bundles, parts = prices()
    stale = []
    for slug, part in PAGES.items():
        path = SITE / slug / "index.html"
        rel = str(path.relative_to(ROOT))
        old = path.read_text(encoding="utf-8")
        new = render(old, slug, sentence(part, bundles, parts), rel)
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
