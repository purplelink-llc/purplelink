#!/usr/bin/env python3
"""Stamp the "Send to my Mac" block onto the Mac-app product pages (docs/designs/send-to-mac.md).

One definition of the markup, so the copies cannot drift. Each page in PAGES gets the block between the
send-to-mac markers, in the hero after the buttons and the lines that belong to them (after the .buy-suite sentence
when the page has one, else after the .app-hero-actions div), plus one plain script tag for
/send-to-mac.js in <head>, right after theme.js and before the stylesheets. That script must not be deferred: it
decides the platform before the first paint, so the block appears without moving anything. fingerprint_assets.py adds
the ?v= hash. Idempotent: run it after editing the markup or adding a page.

The block starts hidden. With scripting off, or on a Mac, it stays hidden and the page is exactly as before.

Adding an app: one entry in PAGES here, and one email template in PRODUCTS in netlify/functions/send-to-mac.mjs
(site-tests/test_send_to_mac.py checks that the two lists match).

  python3 scripts/apply_send_to_mac.py           # rewrite in place
  python3 scripts/apply_send_to_mac.py --check   # exit 1 if any page is out of date
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
START = "<!-- send-to-mac:start -->"
END = "<!-- send-to-mac:end -->"
SCRIPT = '<script src="/send-to-mac.js"></script>'

# page -> (product slug, app name, trial download link on that page)
PAGES = {
    "moderntex/index.html": ("moderntex", "ModernTex", "/.netlify/functions/moderntex-download?trial=1"),
    "legroom/index.html": ("legroom", "Legroom", "/.netlify/functions/legroom-download?trial=1"),
    "outbound-veil/index.html": ("outbound-veil", "Outbound Veil", "/.netlify/functions/outbound-veil-download?trial=1"),
    "nee/index.html": ("nee", "Née", "/.netlify/functions/nee-download?trial=1"),
}


def markup(slug: str, name: str, download: str) -> str:
    name = html.escape(name)
    return f"""{START}
        <form class="send-to-mac" data-send-to-mac data-product="{slug}" hidden novalidate aria-labelledby="s2m-head">
          <p class="send-to-mac-head" id="s2m-head">On Windows or a phone? {name} runs on a Mac, so I can email you the download link to open there.</p>
          <label class="send-to-mac-label" for="s2m-email">Your email</label>
          <div class="trial-remind-row">
            <input type="email" id="s2m-email" name="email" autocomplete="email" inputmode="email" spellcheck="false" maxlength="254" required aria-describedby="s2m-note s2m-status">
            <button type="submit" class="btn btn-secondary">Email me the link</button>
          </div>
          <div class="send-to-mac-hp" aria-hidden="true"><input type="text" name="website" tabindex="-1" autocomplete="off"></div>
          <label class="send-to-mac-news"><input type="checkbox" name="news"> <span>Also send me news about new Purplelink apps, a few emails a year at most.</span></label>
          <p class="trial-remind-note" id="s2m-note">One email with the link and the trial terms. Your address is not kept. The news box sends a confirm link first, and only a confirmed address is kept.</p>
          <p class="trial-remind-note send-to-mac-status" id="s2m-status" data-s2m-status role="status" aria-live="polite"></p>
          <p class="trial-remind-note"><a href="{download}" data-s2m-anyway>Download the disk image here anyway</a> · <a href="/privacy/#send-to-mac">Privacy</a></p>
        </form>
        {END}"""


BLOCK = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
SCRIPT_TAG = re.compile(r'[ \t]*<script src="/send-to-mac\.js[^"]*"></script>\n')
THEME_JS = re.compile(r'([ \t]*)(<script src="/theme\.js[^"]*"></script>\n)')
ACTIONS = re.compile(r'<div class="app-hero-actions"[^>]*>.*?</div>\n', re.S)
SUITE = re.compile(r'<p class="buy-suite">.*?</p>\n', re.S)


def render(text: str, slug: str, name: str, download: str, rel: str) -> str:
    block = markup(slug, name, download)
    if START in text:
        text = BLOCK.sub(lambda _m: block, text, count=1)
    else:
        actions = ACTIONS.search(text)
        if not actions:
            raise SystemExit(f"{rel}: no app-hero-actions div")
        suite = SUITE.search(text, actions.end())
        m = suite if suite and suite.start() - actions.end() < 1500 else actions
        text = text[: m.end()] + "        " + block + "\n" + text[m.end():]
    if not SCRIPT_TAG.search(text):  # keep an existing tag, fingerprint_assets.py has stamped its hash
        m = THEME_JS.search(text)
        if not m:
            raise SystemExit(f"{rel}: no theme.js script tag")
        text = text[: m.end()] + f"{m.group(1)}{SCRIPT}\n" + text[m.end():]
    return text


def main() -> int:
    check = "--check" in sys.argv
    stale = 0
    for rel, (slug, name, download) in PAGES.items():
        path = SITE / rel
        old = path.read_text(encoding="utf-8")
        new = render(old, slug, name, download, rel)
        if new != old:
            stale += 1
            if not check:
                path.write_text(new, encoding="utf-8")
    print(f"send to my Mac: {stale} page(s) {'stale' if check else 'updated'}")
    return 1 if check and stale else 0


if __name__ == "__main__":
    sys.exit(main())
