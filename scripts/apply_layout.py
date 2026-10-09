#!/usr/bin/env python3
"""Stamp the shared header nav and footer onto every page in site/.

The site had nine header variants and six footers, because each page carried
its own copy. Two nav items ("Software", "Products") pointed at homepage ids
that no longer existed, on 226 pages, and 228 pages had no footer link to the
tools. This script is now the one place the nav and footer are defined.

It replaces the contents of <nav aria-label="Primary navigation"> and the
whole <footer class="footer"> element, and marks the current section with
aria-current. It is idempotent: run it after adding or editing a page.

Skipped:
  - site/blog/digest/  (generated and committed by the Modal cron; see
    .githooks/pre-commit. backend/digest/publisher.py emits the same markup)
  - checkout success, manage and recover pages, whose short nav is deliberate
  - /stats/ and build-only files under assets/

  python3 scripts/apply_layout.py           # rewrite in place
  python3 scripts/apply_layout.py --check   # exit 1 if any page is out of date
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"

SKIP_PREFIXES = ("blog/digest/", "assets/", "stats/")
SKIP_PATHS = {
    "moderntex/success/index.html",
    "kits/success/index.html",
    "sheets/success/index.html",
    "sheets/live/setup/index.html",
    "vitae/plus/success/index.html",
    "vitae/plus/manage/index.html",
    "vitae/plus/recover/index.html",
    "tools/paper-review/packs/success/index.html",
}

# (label, href, sections that mark it current)
NAV = [
    ("Products", "/products/", ("products/", "moderntex/", "legroom/", "keyfeel/", "tapefolio/", "vitae/", "globepin/",
                                "haea/", "binnacle/", "kits/", "sheets/", "scholar-utility-belt/", "labs/", "recover/")),
    ("Tools", "/tools/", ("tools/", "format/")),
    ("Guides", "/guides/", ("guides/", "templates/", "latex-errors/")),
    ("Games", "/games/", ("games/",)),
    ("Blog", "/blog/", ("blog/", "changelog/")),
    ("About", "/about/", ("about/", "press/")),
]

FOOTER_COLUMNS = [
    ("Products", [
        ("ModernTex", "/moderntex/"),
        ("Vitae", "/vitae/"),
        ("Legroom", "/legroom/"),
        ("Keyfeel", "/keyfeel/"),
        ("Paper Review", "/tools/paper-review/"),
        ("Scholar Utility Belt", "/scholar-utility-belt/"),
        ("All products", "/products/"),
    ]),
    ("Free tools", [
        ("LaTeX to PDF", "/tools/latex-to-pdf/"),
        ("BibTeX Validator", "/tools/bib-validator/"),
        ("Citation Generator", "/tools/citation-generator/"),
        ("LaTeX Diff", "/tools/latex-diff/"),
        ("Word Counter", "/tools/word-counter/"),
        ("Daily games", "/games/"),
        ("Sports games", "/games/sports/"),
        ("All tools", "/tools/"),
    ]),
    ("Learn", [
        ("Guides", "/guides/"),
        ("Research methods", "/guides/methodology-problems-peer-reviewers-flag/"),
        ("LaTeX templates", "/templates/"),
        ("LaTeX errors", "/latex-errors/"),
        ("Reference formats", "/format/"),
        ("Blog", "/blog/"),
        ("Changelog", "/changelog/"),
        ("Search", "/search/"),
    ]),
    ("Company", [
        ("About", "/about/"),
        ("Pricing", "/pricing/"),
        ("Press", "/press/"),
        ("Support", "/support/"),
        ("Contact", "mailto:ben@purplelink.llc"),
        ("Privacy", "/privacy/"),
        ("Terms", "/terms/"),
        ("Find a purchase", "/recover/"),
        ("For labs", "/labs/"),
    ]),
]

NAV_RE = re.compile(r'(<nav aria-label="Primary navigation">)(.*?)(</nav>)', re.S)
FOOTER_RE = re.compile(r'([ \t]*)<footer class="footer">.*?</footer>', re.S)


def section_of(rel: str) -> str:
    return "" if rel in ("index.html", "404.html") else rel


def nav_html(rel: str, inline: bool, indent: str) -> str:
    items = []
    for label, href, sections in NAV:
        current = any(rel.startswith(s) for s in sections)
        attr = ' aria-current="page"' if current else ""
        items.append(f'<a href="{href}"{attr}>{label}</a>')
    if inline:
        return "".join(items)
    return "\n" + "".join(f"{indent}  {i}\n" for i in items) + indent


def footer_html(indent: str) -> str:
    i = indent
    cols = []
    for head, links in FOOTER_COLUMNS:
        lis = "\n".join(f'{i}        <li><a href="{h}">{t}</a></li>' for t, h in links)
        cols.append(
            f'{i}    <nav class="footer-col" aria-label="{head}">\n'
            f'{i}      <p class="footer-head">{head}</p>\n'
            f'{i}      <ul>\n{lis}\n{i}      </ul>\n'
            f'{i}    </nav>'
        )
    return (
        f'{i}<footer class="footer">\n'
        f'{i}  <div class="footer-grid">\n'
        f'{i}    <div class="footer-about">\n'
        f'{i}      <a class="footer-brand" href="/">\n'
        f'{i}        <img src="/assets/purplelink-mark.svg" alt="" width="26" height="26">\n'
        f'{i}        <span>Purplelink LLC</span>\n'
        f'{i}      </a>\n'
        f'{i}      <p class="footer-blurb">Apps and tools made by a one-person studio '
        f'in Atlanta, Georgia.</p>\n'
        f'{i}      <a class="footer-mail" href="mailto:ben@purplelink.llc">ben@purplelink.llc</a>\n'
        f'{i}    </div>\n'
        + "\n".join(cols) + "\n"
        f'{i}  </div>\n'
        f'{i}  <div class="footer-bottom">\n'
        f'{i}    <span>&copy; 2026 Purplelink LLC</span>\n'
        f'{i}    <span class="footer-loc">Atlanta, Georgia · Est. 2026</span>\n'
        f'{i}    <button type="button" class="theme-toggle" data-theme-toggle hidden>Use light theme</button>\n'
        f'{i}  </div>\n'
        f'{i}</footer>'
    )


MOTION_CSS = '    <link rel="stylesheet" href="/motion.css">\n'
MOTION_JS = '    <script src="/motion.js" defer></script>\n'


THEME_JS = '    <script src="/theme.js"></script>\n'


def with_theme(html: str) -> str:
    """theme.js must run before first paint, so it goes in <head> ahead of the
    stylesheet and without defer. Pages that already carry it are left alone."""
    if "theme.js" in html or "</head>" not in html:
        return html
    m = re.search(r'[ \t]*<link rel="stylesheet" href="/?styles\.css', html)
    if m:
        return html[:m.start()] + THEME_JS + html[m.start():]
    return html.replace("</head>", THEME_JS + "</head>", 1)


def with_motion(html: str) -> str:
    """Every page loads the shared motion module (fingerprint_assets stamps
    the ?v hash). Pages that already carry it are left alone."""
    if "motion.js" in html or "</head>" not in html:
        return html
    if "/site.js" not in html:
        return html.replace("</head>", MOTION_CSS + MOTION_JS + "</head>", 1)
    out = re.sub(r'(<link rel="stylesheet" href="/?styles\.css[^"]*">\n)',
                 lambda m: m.group(1) + MOTION_CSS, html, count=1)
    if "motion.css" not in out:
        out = out.replace("</head>", MOTION_CSS + "</head>", 1)
    return re.sub(r'(<script src="/?site\.js[^"]*" defer></script>\n)',
                  lambda m: m.group(1) + MOTION_JS, out, count=1) if "motion.js" not in out else out


def render(rel: str, html: str) -> str:
    def nav_sub(m: re.Match) -> str:
        inline = "\n" not in m.group(2)
        line_start = html.rfind("\n", 0, m.start()) + 1
        indent = re.match(r"[ \t]*", html[line_start:]).group(0)
        return m.group(1) + nav_html(section_of(rel), inline, indent) + m.group(3)

    out = NAV_RE.sub(nav_sub, html, count=1)
    out = FOOTER_RE.sub(lambda m: footer_html(m.group(1)), out, count=1)
    return with_theme(with_motion(out))


def pages():
    for f in sorted(SITE.rglob("*.html")):
        rel = f.relative_to(SITE).as_posix()
        if rel.startswith(SKIP_PREFIXES) or rel in SKIP_PATHS or rel.startswith("google"):
            continue
        yield rel, f


def main() -> int:
    check = "--check" in sys.argv
    stale = 0
    for rel, f in pages():
        html = f.read_text(encoding="utf-8")
        new = render(rel, html)
        if new != html:
            stale += 1
            if not check:
                f.write_text(new, encoding="utf-8")
    verb = "stale" if check else "updated"
    print(f"layout: {stale} page(s) {verb}")
    return 1 if (check and stale) else 0


if __name__ == "__main__":
    sys.exit(main())
