#!/usr/bin/env python3
"""Stamp the "Write to Ben" support box onto /support/ and the app pages.

One definition of the markup, so the eight copies cannot drift. Each page gets
the block between the support-box markers plus one script tag for
/support-box.js (fingerprint_assets.py adds the ?v= hash). Idempotent: run it
after editing the markup or adding a page to PAGES.

The form starts hidden. support-box.js shows it, so with JavaScript off the
visitor sees the mailto link and nothing broken. Topics must match TOPICS in
netlify/functions/support-message.mjs (site-tests and the function's own
allowlist both reject anything else).

  python3 scripts/apply_support_box.py           # rewrite in place
  python3 scripts/apply_support_box.py --check   # exit 1 if any page is out of date
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
MAIL = "ben@purplelink.llc"
START = "<!-- support-box:start -->"
END = "<!-- support-box:end -->"
SCRIPT = '<script src="/support-box.js" defer></script>'

TOPICS = {
    "general": "General",
    "moderntex": "ModernTex",
    "outbound-veil": "Outbound Veil",
    "legroom": "Legroom",
    "keyfeel": "Keyfeel",
    "tapefolio": "Tapefolio",
    "panely": "Panely",
    "summonly": "Summonly",
    "vitae": "Vitae",
    "batterymeter": "BatteryMeter",
    "haea": "haea",
    "paper-review": "Paper Review",
    "refund": "Refund",
    "bug": "Bug report",
}

# page -> (topic, variant). The product pages place the box after the FAQ section.
PAGES = {
    "support/index.html": ("general", "page"),
    "moderntex/index.html": ("moderntex", "compact"),
    "outbound-veil/index.html": ("outbound-veil", "compact"),
    "legroom/index.html": ("legroom", "compact"),
    "keyfeel/index.html": ("keyfeel", "compact"),
    "tapefolio/index.html": ("tapefolio", "compact"),
    "panely/index.html": ("panely", "compact"),
    "summonly/index.html": ("summonly", "compact"),
    "vitae/index.html": ("vitae", "compact"),
    "batterymeter/index.html": ("batterymeter", "compact"),
    "haea/index.html": ("haea", "compact"),
}


def markup(topic: str, variant: str) -> str:
    name = TOPICS[topic]
    subject = f"Support: {name}".replace(" ", "%20").replace(":", "%3A")
    if variant == "page":
        lede = "Write a message and it goes to Ben's inbox. Add your email so he can reply."
        picker = (
            '      <div class="support-box-field">\n'
            '        <label for="sb-topic">About</label>\n'
            '        <select id="sb-topic" name="topic">\n'
            + "".join(f'          <option value="{k}">{html.escape(v)}</option>\n' for k, v in TOPICS.items())
            + "        </select>\n"
            "      </div>\n"
        )
    else:
        lede = f"A question about {html.escape(name)} that this page does not answer? Write to Ben here."
        picker = ""
    return f"""{START}
    <section class="support-box support-box--{variant}" data-support-box data-support-topic="{topic}" aria-labelledby="sb-heading">
      <h2 class="support-box-head" id="sb-heading">Write to Ben</h2>
      <p class="support-box-lede">{lede}</p>
      <form class="support-box-form" novalidate hidden>
{picker}      <div class="support-box-field">
        <label for="sb-email">Your email</label>
        <input type="email" id="sb-email" name="email" autocomplete="email" inputmode="email" spellcheck="false" maxlength="254" required aria-describedby="sb-email-hint sb-email-error">
        <p class="support-box-hint" id="sb-email-hint">Used only to reply to this message.</p>
        <p class="support-box-error" id="sb-email-error" hidden></p>
      </div>
      <div class="support-box-field">
        <label for="sb-message">Message</label>
        <textarea id="sb-message" name="message" rows="6" maxlength="5000" required aria-describedby="sb-message-hint sb-message-error"></textarea>
        <p class="support-box-hint" id="sb-message-hint">What you did, what you expected and what you saw. For a purchase, include the email you paid with.</p>
        <p class="support-box-error" id="sb-message-error" hidden></p>
      </div>
      <input type="text" name="website" class="visually-hidden" tabindex="-1" autocomplete="off" aria-hidden="true">
      <button type="submit" class="btn btn-primary">Send message</button>
      </form>
      <p class="support-box-status" data-sb-status role="status" aria-live="polite"></p>
      <p class="support-box-fine">Prefer your own mail app? Write to <a href="mailto:{MAIL}?subject={subject}">{MAIL}</a>. The form delivers your message by email through Resend and does not store it on this site. <a href="/privacy/#support-form">Privacy</a>.</p>
    </section>
    {END}"""


BLOCK = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
SCRIPT_TAG = re.compile(r'[ \t]*<script src="/support-box\.js[^"]*" defer></script>\n')
SITE_JS = re.compile(r'([ \t]*)(<script src="/site\.js[^"]*" defer></script>\n)')


def render(text: str, topic: str, variant: str, rel: str) -> str:
    block = markup(topic, variant)
    if START in text:
        text = BLOCK.sub(lambda _m: block, text, count=1)
    elif variant == "page":
        anchor = "<h2>How to reach Ben</h2>"
        if anchor not in text:
            raise SystemExit(f"{rel}: anchor not found")
        text = text.replace(anchor, block + "\n\n      " + anchor, 1)
    else:
        m = re.search(r'(<section class="faq-section".*?</section>\n)', text, re.S)
        if not m:
            raise SystemExit(f"{rel}: no faq-section")
        text = text[: m.end()] + "\n    " + block + "\n" + text[m.end():]
    if not SCRIPT_TAG.search(text):  # keep an existing tag, fingerprint_assets.py has stamped its hash
        m = SITE_JS.search(text)
        if not m:
            raise SystemExit(f"{rel}: no site.js script tag")
        text = text[: m.end()] + f"{m.group(1)}{SCRIPT}\n" + text[m.end():]
    return text


def main() -> int:
    check = "--check" in sys.argv
    stale = 0
    for rel, (topic, variant) in PAGES.items():
        path = SITE / rel
        old = path.read_text(encoding="utf-8")
        new = render(old, topic, variant, rel)
        if new != old:
            stale += 1
            if not check:
                path.write_text(new, encoding="utf-8")
    print(f"support box: {stale} page(s) {'stale' if check else 'updated'}")
    return 1 if check and stale else 0


if __name__ == "__main__":
    sys.exit(main())
