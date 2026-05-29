"""Single source of truth for the pages that carry the ModernTex CTA.

Both insert_moderntex_cta.py and verify_moderntex_cta.py import from here so the
page list and source-tag convention cannot drift between insertion and
verification. To add a page to the funnel, edit only this file.
"""

TOOL_SLUGS = [
    "bib-builder", "bib-validator", "citation-generator", "equation-renderer",
    "file-to-markdown", "latex-diff", "latex-table-generator", "latex-to-pdf",
    "latex-to-word", "markdown-to-pdf", "pdf-tools", "reference-converter",
    "word-counter", "word-to-latex",
]
GUIDE_SLUGS = [
    "citation-styles-explained", "doi-to-bibtex", "fix-bibtex-errors",
    "latex-to-word", "latex-track-changes", "latex-word-count",
]

MARKER = "<!-- moderntex-cta -->"


def targets():
    """Yield (html_path, source_tag) for every page in the funnel."""
    for s in TOOL_SLUGS:
        yield f"site/tools/{s}/index.html", f"tool:{s}"
    for s in GUIDE_SLUGS:
        yield f"site/guides/{s}/index.html", f"guide:{s}"
