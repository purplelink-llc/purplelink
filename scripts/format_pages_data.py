"""Dataset for the /format/references-for-<slug>/ venue pages.

Single source of truth for generate_format_pages.py. Every fact here was
verified against the venue's own author guidelines/templates or, where the
venue's own page could not be loaded directly, against the venue's official
EndNote/BibTeX style files published on endnote.com or the ACM/INFORMS
authoring-tools pages (see `source_url`). Where a fact is corroborated only
via a secondary source, `source_note` says so explicitly — don't strengthen
that hedge when editing.

Only venues with a genuinely different required manuscript format, citation
style, or reference-manager support are listed. Do not add a venue whose
answer to all three of those is identical to an existing entry — that would
just be the same page with a different name on it.
"""

VENUES = [
    {
        "slug": "ieee-sp",
        "name": "IEEE Symposium on Security and Privacy",
        "abbr": "IEEE S&P (“Oakland”)",
        "field": "Computer security",
        "manuscript_formats": "LaTeX only",
        "template": "IEEEtran (“compsoc” conference option) — \\documentclass[conference,compsoc]{IEEEtran}",
        "default_to": "bibtex",
        "citation_style": "Numbered, bracketed citations (e.g. [1], [2]) — IEEEtran's standard bibliography style.",
        "format_note": "The IEEEtran class is built to manage references through BibTeX; a call for papers that requires IEEEtran in practice means preparing your bibliography as a .bib file.",
        "source_url": "https://sp2026.ieee-security.org/cfpapers.html",
        "source_note": "Template requirement confirmed directly from the venue's call for papers. BibTeX is IEEEtran's conventional workflow, not a line explicitly stated in the CFP.",
    },
    {
        "slug": "usenix-security",
        "name": "USENIX Security Symposium",
        "abbr": "USENIX Security",
        "field": "Computer security",
        "manuscript_formats": "LaTeX or Word",
        "template": "Official USENIX LaTeX and Word templates (final version must use the official style files)",
        "default_to": "bibtex",
        "citation_style": "Numbered citations, consistent with the official template's IEEE-adjacent formatting.",
        "format_note": "USENIX's official LaTeX template ships with a .bib file and a pdflatex + bibtex build process, so BibTeX is the format its own template expects.",
        "source_url": "https://www.usenix.org/conferences/author-resources/paper-templates",
        "source_note": "The template repository itself confirms the BibTeX build; USENIX's live guidelines page returned an access error when this page was generated, so this is based on the template files rather than the guidelines text.",
    },
    {
        "slug": "acm-ccs",
        "name": "ACM Conference on Computer and Communications Security",
        "abbr": "ACM CCS",
        "field": "Computer security",
        "manuscript_formats": "LaTeX only",
        "template": "acmart, sigconf proceedings template — \\documentclass[manuscript]{acmart}",
        "default_to": "bibtex",
        "citation_style": "Numbered citations by default (ACM-Reference-Format bibliography style).",
        "format_note": "ACM's authoring documentation states plainly: use BibTeX to prepare your references for acmart submissions. Manually typed \\bibitem entries aren't accepted.",
        "source_url": "https://homes.cs.washington.edu/~spencer/taps/article-latex.html",
        "source_note": "BibTeX requirement and default numbered style are ACM-wide policy for the acmart/sigconf template that CCS uses, per ACM's TAPS authoring guide.",
    },
    {
        "slug": "ndss",
        "name": "Network and Distributed System Security Symposium",
        "abbr": "NDSS",
        "field": "Computer and network security",
        "manuscript_formats": "LaTeX only",
        "template": "IEEEtran (NDSS-hosted template), two-column, 10pt Times",
        "default_to": "bibtex",
        "citation_style": "Numbered citations — conventional for the IEEEtran template NDSS uses.",
        "format_note": "As with other IEEEtran-based venues, BibTeX is the standard way to manage the bibliography for this template.",
        "source_url": "https://www.ndss-symposium.org/ndss2026/submissions/templates/",
        "source_note": "Template requirement confirmed directly from the venue's templates page. BibTeX and numbered-style are inferred from the IEEEtran template's conventions, not stated explicitly on that page.",
    },
    {
        "slug": "misq",
        "name": "MIS Quarterly",
        "abbr": "MISQ",
        "field": "Information systems",
        "manuscript_formats": "Word",
        "template": "No LaTeX template — Microsoft Word manuscript",
        "default_to": "endnote",
        "citation_style": "Author-year, APA-derived with MISQ-specific conventions (e.g. “(Angelou 1969)” — no comma before the year; volume:issue written as “(23:3)”).",
        "format_note": "MISQ has an official EndNote output style, which is the practical route for Word-based authors who manage references in EndNote, Zotero, or Mendeley.",
        "source_url": "https://endnote.com/downloads/styles/mis-quarterly/",
        "source_note": "EndNote style and author-year format are corroborated via EndNote's own published style listing; MISQ's own submission-guidelines page returned an access error when this page was generated, so this is not a direct confirmation from the journal's own text.",
    },
    {
        "slug": "isr",
        "name": "Information Systems Research",
        "abbr": "ISR",
        "field": "Information systems",
        "manuscript_formats": "LaTeX or Word",
        "template": "INFORMS journal LaTeX style files (includes a BibTeX .bst matching INFORMS reference format)",
        "default_to": "bibtex",
        "citation_style": "Author-year (e.g. “(Norman 1977)”), references listed alphabetically — per the INFORMS house style guide.",
        "format_note": "ISR is one of the few venues here that officially supports both paths: INFORMS publishes a BibTeX style file for LaTeX authors and a separate EndNote style (“Inf Syst Res.ens”) for Word/reference-manager authors.",
        "source_url": "https://pubsonline.informs.org/authorportal/latex-style-files",
        "source_note": "LaTeX/BibTeX style files confirmed directly from INFORMS's author portal. EndNote style confirmed via endnote.com's published style listing.",
    },
    {
        "slug": "acm-csur",
        "name": "ACM Computing Surveys",
        "abbr": "ACM CSUR",
        "field": "Computer science (survey articles)",
        "manuscript_formats": "LaTeX or Word",
        "template": "acmart, manuscript option — \\documentclass[manuscript]{acmart}",
        "default_to": "bibtex",
        "citation_style": "Numbered citations by default (ACM-Reference-Format bibliography style) — the same ACM-wide convention CCS uses.",
        "format_note": "Like other acmart-based ACM venues, CSUR's authoring guidelines call for BibTeX to prepare references.",
        "source_url": "https://dl.acm.org/journal/csur/author-guidelines",
        "source_note": "Confirmed directly from ACM's author-guidelines page for the journal plus ACM's shared TAPS authoring documentation for the BibTeX/citation-style rule.",
    },
    {
        "slug": "ieee-tdsc",
        "name": "IEEE Transactions on Dependable and Secure Computing",
        "abbr": "IEEE TDSC",
        "field": "Computer security and dependable computing",
        "manuscript_formats": "Word, plain text, or LaTeX",
        "template": "IEEE Computer Society journal template (via the IEEE Template Selector); LaTeX submissions must pass the IEEE LaTeX Analyzer",
        "default_to": "bibtex",
        "citation_style": "Numbered citations in order of appearance (square brackets), per the IEEE Reference Guide.",
        "format_note": "TDSC is more flexible on manuscript format than the security conferences above — Word and plain text are both accepted alongside LaTeX. For LaTeX authors, BibTeX remains the standard way to produce IEEE's numbered reference list.",
        "source_url": "https://www.computer.org/publications/author-resources",
        "source_note": "Numbered citation order and IEEE Reference Guide confirmed via IEEE Computer Society's general author-resources page; this journal's own dedicated page returned no substantive content when this page was generated, so treat the BibTeX detail as the template's convention rather than an explicit TDSC-specific statement.",
    },
]
