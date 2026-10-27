#!/usr/bin/env python3
"""Add the ModernTex call-to-action band to the LaTeX error pages (the hub and every error page).

The band is the one the tool and guide pages already carry (same words, same classes, so the same CSS), with
its links tagged ?from=latex-errors so the funnel can tell a ModernTex visit that started on an error page
from any other. Search visitors and the YouTube "how to fix it" videos land on these pages; until this band
the only ModernTex mention was a line inside the "What each editor shows" list.

Inserted immediately before <nav class="tool-related"; idempotent (a page that already has the marker is
skipped). Run from the repo root:  python3 scripts/insert_latex_errors_cta.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKER = "<!-- moderntex-cta -->"
ANCHOR = '      <nav class="tool-related"'
TAG = "?from=latex-errors"
BLOCK = f"""      {MARKER}
      <section class="waitlist-section mt-cta">
        <p class="eyebrow">From the maker of these tools</p>
        <h2>Writing LaTeX on a Mac?</h2>
        <p>ModernTex is a native macOS LaTeX studio. It has multi-file manuscript navigation, a PDF preview that stays in sync, BibTeX completion that searches by author or title, and compile errors in plain language. $19.99 once, all updates included, forever.</p>
        <div class="waitlist-actions">
          <a class="btn btn-primary" href="/moderntex/{TAG}">Get ModernTex &mdash; $19.99</a>
          <a class="btn btn-ghost" href="/moderntex/{TAG}">See what it does</a>
        </div>
        <p class="waitlist-fine-print">Requires macOS 14 or later. Free 7-day trial, no account.</p>
      </section>

"""


def pages(root: Path = ROOT) -> list[Path]:
    base = root / "site" / "latex-errors"
    return [base / "index.html"] + sorted(base.glob("*/index.html"))


def insert(html: str) -> tuple[str, str]:
    """(new_html, status) where status is "changed", "skipped" or an error string."""
    if MARKER in html:
        return html, "skipped"
    i = html.find(ANCHOR)
    if i == -1:
        return html, "anchor not found"
    if html.find(ANCHOR, i + 1) != -1:
        return html, "anchor found more than once"
    return html[:i] + BLOCK + html[i:], "changed"


def main() -> int:
    changed = skipped = 0
    bad = []
    for p in pages():
        new, status = insert(p.read_text(encoding="utf-8"))
        if status == "changed":
            p.write_text(new, encoding="utf-8")
            changed += 1
        elif status == "skipped":
            skipped += 1
        else:
            bad.append((p, status))
    print(f"changed {changed}, skipped {skipped}")
    for p, why in bad:
        print("FAIL", p, why)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
