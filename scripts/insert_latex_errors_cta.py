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
# The primary button is the free trial through the guide door, counted as guide_mtx_trial; mtx-trial-door.js
# sends visitors who are not on a Mac to /moderntex/ instead. The ghost button keeps the tagged product-page link.
TRIAL = "/.netlify/functions/moderntex-download?src=guide&amp;trial=1"
BLOCK = f"""      {MARKER}
      <section class="waitlist-section mt-cta">
        <p class="eyebrow">From the maker of these tools</p>
        <h2>Writing LaTeX on a Mac?</h2>
        <p>ModernTex is a native macOS LaTeX studio. It has multi-file manuscript navigation, a PDF preview that stays in sync, BibTeX completion that searches by author or title, and compile errors in plain language. $19.99 once, all updates included, forever.</p>
        <div class="waitlist-actions">
          <a class="btn btn-primary" href="{TRIAL}" data-track="guide_mtx_trial" data-track-meta="{{meta}}:end">Try ModernTex free for 7 days</a>
          <a class="btn btn-ghost" href="/moderntex/{TAG}" data-track="guide_mtx_click" data-track-meta="{{meta}}:end-page">See what it does</a>
        </div>
        <p class="waitlist-fine-print">Requires macOS 14 or later. No account, and the trial is the full app.</p>
        <script src="/mtx-trial-door.js" defer></script>
      </section>

"""


def pages(root: Path = ROOT) -> list[Path]:
    base = root / "site" / "latex-errors"
    return [base / "index.html"] + sorted(base.glob("*/index.html"))


def meta_for(p: Path, root: Path = ROOT) -> str:
    """"latex-errors" for the hub, "latex-errors:<slug>" for an error page."""
    return p.parent.relative_to(root / "site").as_posix().replace("/", ":")


def insert(html: str, meta: str = "latex-errors") -> tuple[str, str]:
    """(new_html, status) where status is "changed", "skipped" or an error string."""
    if MARKER in html:
        return html, "skipped"
    i = html.find(ANCHOR)
    if i == -1:
        return html, "anchor not found"
    if html.find(ANCHOR, i + 1) != -1:
        return html, "anchor found more than once"
    return html[:i] + BLOCK.replace("{meta}", meta) + html[i:], "changed"


def main() -> int:
    changed = skipped = 0
    bad = []
    for p in pages():
        new, status = insert(p.read_text(encoding="utf-8"), meta_for(p))
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
