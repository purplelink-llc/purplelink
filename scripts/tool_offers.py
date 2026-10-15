#!/usr/bin/env python3
"""Tool-page offer cards: the single source for which tool page offers which app, and the copy.

Every sentence below restates something the target product's own page says (checked against
site/<app>/index.html on origin/main, 2026-10-14). The evidence column for each claim is in the
PR description. A tool that is not in OFFERS shows no offer card.

Run from the repo root:  python3 scripts/tool_offers.py
Idempotent: it removes the old generic ModernTex block and any earlier offer card, then writes the
card for the tools listed here. It touches nothing else on a page.

Rules (docs/growth-briefs/delphi-2026-10/FINAL-REPORT.md, section 6): no discounts, bundles or
education pricing, no social proof, no compliance claims. Only ModernTex, Tapefolio, Outbound Veil
and Vitae are ever offered from a tool page.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "site" / "tools"

OPEN = "<!-- tool-offer -->"
CLOSE = "<!-- /tool-offer -->"

APPS = {
    "moderntex": {
        "name": "ModernTex",
        "href": "/moderntex/",
        "meta": "$19.99 once, after a free 7-day trial. Needs a Mac with macOS 14 or later.",
    },
    "tapefolio": {
        "name": "Tapefolio",
        "href": "/tapefolio/",
        "meta": "Free for 7 days, then $29.99 once. Needs macOS 26 or later on a Mac with Apple silicon.",
    },
    "outbound-veil": {
        "name": "Outbound Veil",
        "href": "/outbound-veil/",
        "meta": "Free for 7 days, then $29.99 once. Needs macOS 14 or later.",
    },
    "vitae": {
        "name": "Vitae",
        "href": "/vitae/",
        "meta": "The app is free, with no limits on your record. Needs macOS 15 or later.",
    },
}

# slug -> (app, hook, what the app does that the tool cannot)
OFFERS = {
    "latex-to-pdf": (
        "moderntex",
        "A compile on this page is cut off after about a minute.",
        "ModernTex compiles on your Mac, so there is no server compile timeout, and its Live mode keeps the PDF in sync as you type.",
    ),
    "latex-diff": (
        "moderntex",
        "This compares two files you upload, and an edited table shows only in its final form.",
        "ModernTex takes a snapshot at any point, such as before a major revision, and compares any two snapshots in a diff.",
    ),
    "bib-validator": (
        "moderntex",
        "This checks a .bib file after you have written it.",
        "ModernTex points a bibliography build error at the line in your .bib file, and completes citations from your .bib files as you type.",
    ),
    "bib-builder": (
        "moderntex",
        "This builds a .bib file from the DOIs and arXiv IDs you paste in.",
        "ModernTex suggests citations from your .bib files as you type, searching by author, title or key.",
    ),
    "citation-generator": (
        "moderntex",
        "This gives you one formatted citation to copy and does not keep your reference list.",
        "ModernTex suggests citations from your .bib files as you type, searching by author, title or key.",
    ),
    "reference-converter": (
        "moderntex",
        "This converts references between BibTeX, RIS and EndNote, and stops there.",
        "ModernTex suggests citations from your .bib files as you type, searching by author, title or key.",
    ),
    "word-to-latex": (
        "moderntex",
        "This gives you a .tex starting point, not a finished manuscript.",
        "ModernTex opens a LaTeX project with a sidebar of its sections and a PDF preview that stays in sync, and it explains compile errors in plain language.",
    ),
    "latex-table-generator": (
        "moderntex",
        "This turns CSV or TSV that you paste in into a booktabs table.",
        "ModernTex has a Table Editor: paste a range from Excel or Google Sheets, resize columns by dragging, and it writes booktabs-style LaTeX underneath.",
    ),
    "equation-renderer": (
        "moderntex",
        "This renders one equation to an image.",
        "ModernTex builds your whole document on your Mac and keeps the PDF in sync as you type, with each compile error explained in plain language.",
    ),
    "thesis-format-checker": (
        "moderntex",
        "This reads a finished PDF and cannot change the source it came from.",
        "ModernTex is an editor for a thesis written in LaTeX across several files, with a sidebar to jump between chapters, sections and bibliography files.",
    ),
    "camera-ready-checker": (
        "moderntex",
        "This checks the final PDF after it has been built.",
        "ModernTex checks anonymization, page limits, required sections and submission packaging before you send a manuscript.",
    ),
    "submission-checklist": (
        "moderntex",
        "This checklist is yours to tick through by hand.",
        "ModernTex checks anonymization, page limits, required sections and submission packaging automatically before you send a manuscript.",
    ),
    "transcript-cleaner": (
        "tapefolio",
        "This cleans a transcript you already have. It does not make one from audio.",
        "Tapefolio transcribes interview and meeting recordings on your Mac, labels the speakers and helps you replace names and other identifiers. Your files are not uploaded. It will mishear some words, so you check the draft against the recording.",
    ),
    "metadata-cleaner": (
        "outbound-veil",
        "This cleans files and pasted text that you hand to it. It does not watch what you type.",
        "Outbound Veil checks what you type for personal information, such as names, phone numbers and card numbers, before you send it or paste it into ChatGPT or claude.ai in Chrome. The check runs on your Mac. It will miss some things, and it is not a compliance product.",
    ),
    "anonymity-check": (
        "outbound-veil",
        "This reads a finished manuscript PDF for leaks in a blind submission.",
        "Outbound Veil is a different check. It marks names, contact details and ID numbers in the text you are typing, before you send it. It is not a manuscript leak scan, it will miss some things, and it is not a compliance product.",
    ),
    "resume-review": (
        "vitae",
        "This reviews one resume and does not keep a record of your work.",
        "Vitae imports a CV from Word, PDF, RTF, ODT or a web page. It then fills your CV from the papers, grants and positions you track, and exports to PDF, Word, rich text, HTML or Markdown.",
    ),
}

# Pages that carried the generic ModernTex block and now carry nothing, for the report and the tests.
# word-counter: the ModernTex page does not say it counts words. markdown-to-pdf, file-to-markdown,
# pdf-tools, pdf-structure, latex-to-word: no ModernTex feature on its page covers them.

OLD_BLOCK = re.compile(r"      <!-- moderntex-cta -->\n      <section\b.*?</section>\n\n?", re.S)
NEW_BLOCK = re.compile(re.escape("      " + OPEN) + r".*?" + re.escape(CLOSE) + r"\n\n?", re.S)
ANCHOR_NAV = '      <nav class="tool-related"'
ANCHOR_MAIN = "    </main>"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def card(slug, app_key, hook, what):
    app = APPS[app_key]
    href = f'{app["href"]}?utm_source=tool-{slug}&amp;utm_medium=tool&amp;utm_campaign={app_key}'
    return (
        f"      {OPEN}\n"
        f'      <aside class="tool-offer" aria-label="About {app["name"]}" data-offer="{app_key}">\n'
        f'        <p class="tool-offer-hook">{esc(hook)}</p>\n'
        f"        <p>{esc(what)}</p>\n"
        f'        <p class="tool-offer-meta">{esc(app["meta"])}</p>\n'
        f'        <a class="tool-offer-link" href="{href}" data-track="offer_click" data-track-meta="{app_key}">See {app["name"]}</a>\n'
        f"      </aside>\n"
        f"      {CLOSE}\n\n"
    )


def rewrite(slug, html):
    html = OLD_BLOCK.sub("", html)
    html = NEW_BLOCK.sub("", html)
    if slug not in OFFERS:
        return html
    block = card(slug, *OFFERS[slug])
    if html.count(ANCHOR_NAV) == 1:
        return html.replace(ANCHOR_NAV, block + ANCHOR_NAV)
    if html.count(ANCHOR_MAIN) == 1:
        return html.replace(ANCHOR_MAIN, block.rstrip("\n") + "\n" + ANCHOR_MAIN)
    raise SystemExit(f"{slug}: no anchor for the offer card")


def main():
    changed = 0
    for d in sorted(TOOLS.iterdir()):
        page = d / "index.html"
        if not page.is_file():
            continue
        old = page.read_text(encoding="utf-8")
        new = rewrite(d.name, old)
        if new != old:
            page.write_text(new, encoding="utf-8")
            changed += 1
            print("changed", d.name)
    print(f"{changed} page(s) changed")
    unknown = [s for s in OFFERS if not (TOOLS / s / "index.html").is_file()]
    if unknown:
        print("unknown slugs:", unknown)
        sys.exit(1)


if __name__ == "__main__":
    main()
