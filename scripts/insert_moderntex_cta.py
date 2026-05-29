#!/usr/bin/env python3
"""Insert the ModernTex waitlist CTA block into all 19 tool/guide pages.

Idempotent: a page that already contains the CTA marker is skipped, so the
script is safe to re-run. The block is inserted immediately before the
'<nav class="tool-related"' line, at 6-space indentation, matching the
surrounding <main> content.
"""
import sys

from cta_pages import MARKER, targets

ANCHOR = '      <nav class="tool-related"'


def block(source):
    return (
        f"      {MARKER}\n"
        '      <section class="waitlist-section">\n'
        '        <p class="eyebrow">From the team behind these tools</p>\n'
        "        <h2>Writing LaTeX on a Mac?</h2>\n"
        "        <p>We're building ModernTex — a native macOS LaTeX studio. "
        "Join the waitlist for one email at launch.</p>\n"
        '        <form class="waitlist-form" name="waitlist-moderntex" '
        'method="POST" data-netlify="true" data-netlify-honeypot="bot-field">\n'
        '          <input type="hidden" name="form-name" value="waitlist-moderntex">\n'
        f'          <input type="hidden" name="source" value="{source}">\n'
        '          <p hidden><input name="bot-field"></p>\n'
        '          <input type="email" name="email" placeholder="your@email.com" '
        'required autocomplete="email" aria-label="Email address">\n'
        '          <button type="submit">Notify me at launch</button>\n'
        "        </form>\n"
        '        <p class="waitlist-fine-print">We\'ll only use your email to '
        'notify you at launch. <a href="/privacy/">Privacy Policy</a> · '
        '<a href="/moderntex/">Learn more about ModernTex →</a></p>\n'
        "      </section>\n\n"
    )


def main():
    changed, skipped, failed = [], [], []
    for path, source in targets():
        with open(path, encoding="utf-8") as fh:
            html = fh.read()
        if MARKER in html:
            skipped.append((path, "already has CTA"))
            continue
        idx = html.find(ANCHOR)
        if idx == -1:
            failed.append((path, "anchor not found"))
            continue
        if html.find(ANCHOR, idx + 1) != -1:
            failed.append((path, "anchor found more than once"))
            continue
        new_html = html[:idx] + block(source) + html[idx:]
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(new_html)
        changed.append(path)

    print(f"changed: {len(changed)}")
    print(f"skipped: {len(skipped)}")
    for p, r in skipped:
        print("  SKIP", p, "-", r)
    if failed:
        for p, r in failed:
            print("  FAIL", p, "-", r)
        sys.exit(1)


if __name__ == "__main__":
    main()
