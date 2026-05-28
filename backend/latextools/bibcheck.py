"""Pure logic for BibTeX validation — no HTTP calls, no Modal imports.

Layers handled here:
  1. Parsing (bibtexparser v1)
  2. Required-field completeness per entry type
  3. Title normalization and similarity scoring
  4. Annotated .bib generation

Network checks (DOI resolution, CrossRef, Semantic Scholar) live in app.py
because they require httpx and are IO-bound async operations.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

MAX_SYNTAX_ENTRIES = 500   # parse + completeness cap
MAX_NETWORK_ENTRIES = 100  # DOI / CrossRef / S2 cap

# Confidence thresholds for title-similarity matching.
THRESHOLD_OK = 0.85    # >= this → confident match
THRESHOLD_WARN = 0.50  # >= this but < THRESHOLD_OK → possible mismatch

REQUIRED_FIELDS: dict[str, list[str]] = {
    "article":       ["author", "title", "journal", "year"],
    "book":          ["author", "title", "publisher", "year"],
    "booklet":       ["title"],
    "conference":    ["author", "title", "booktitle", "year"],
    "inbook":        ["author", "title", "publisher", "year"],
    "incollection":  ["author", "title", "booktitle", "publisher", "year"],
    "inproceedings": ["author", "title", "booktitle", "year"],
    "manual":        ["title"],
    "mastersthesis": ["author", "title", "school", "year"],
    "misc":          [],
    "phdthesis":     ["author", "title", "school", "year"],
    "proceedings":   ["title", "year"],
    "techreport":    ["author", "title", "institution", "year"],
    "thesis":        ["author", "title", "school", "year"],
    "unpublished":   ["author", "title", "note"],
}


@dataclass
class EntryResult:
    key: str
    entry_type: str
    title: str = ""
    author: str = ""
    doi: str = ""
    missing_fields: list[str] = field(default_factory=list)
    parse_error: str = ""

    # Network results — None means "not checked"
    doi_ok: bool | None = None
    doi_status: int | None = None

    crossref_confidence: float | None = None
    crossref_title: str | None = None
    crossref_doi: str | None = None

    s2_confidence: float | None = None
    s2_title: str | None = None
    s2_year: int | None = None

    def overall(self) -> str:
        if self.parse_error:
            return "error"
        if self.missing_fields:
            return "error"
        if self.doi_ok is False:
            return "error"
        cr = self.crossref_confidence
        s2 = self.s2_confidence
        if (cr is not None and cr < THRESHOLD_WARN) or (s2 is not None and s2 < THRESHOLD_WARN):
            return "error"
        if (cr is not None and cr < THRESHOLD_OK) or (s2 is not None and s2 < THRESHOLD_OK):
            return "warning"
        return "ok"

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "type": self.entry_type,
            "parse_error": self.parse_error,
            "missing_fields": self.missing_fields,
            "doi": self.doi,
            "doi_ok": self.doi_ok,
            "doi_status": self.doi_status,
            "crossref_confidence": self.crossref_confidence,
            "crossref_title": self.crossref_title,
            "crossref_doi": self.crossref_doi,
            "s2_confidence": self.s2_confidence,
            "s2_title": self.s2_title,
            "s2_year": self.s2_year,
            "overall": self.overall(),
        }


def parse_bib(bib_text: str) -> list[EntryResult]:
    """Parse a .bib string with bibtexparser v1.

    Returns one EntryResult per parseable entry, capped at MAX_SYNTAX_ENTRIES.
    Entries that bibtexparser couldn't parse are omitted (bibtexparser v1
    silently skips unparseable blocks; callers can detect this by comparing
    len(results) to the raw @-count in the source).
    """
    import bibtexparser
    from bibtexparser.bparser import BibTexParser

    parser = BibTexParser(common_strings=True)
    parser.ignore_nonstandard_types = False
    db = bibtexparser.loads(bib_text, parser=parser)

    results: list[EntryResult] = []
    for entry in db.entries[: MAX_SYNTAX_ENTRIES]:
        r = EntryResult(
            key=entry.get("ID", "?"),
            entry_type=entry.get("ENTRYTYPE", "misc").lower(),
            title=entry.get("title", ""),
            author=entry.get("author", ""),
            doi=_clean_doi(entry.get("doi", "")),
        )
        r.missing_fields = _check_completeness(r.entry_type, entry)
        results.append(r)
    return results


def _clean_doi(doi: str) -> str:
    doi = doi.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.lower().startswith(prefix):
            doi = doi[len(prefix):]
    return doi


def _check_completeness(entry_type: str, entry: dict) -> list[str]:
    required = REQUIRED_FIELDS.get(entry_type, [])
    return [f for f in required if not entry.get(f, "").strip()]


def normalize_title(title: str) -> str:
    """Lowercase, strip LaTeX markup, collapse whitespace."""
    title = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", title)
    title = re.sub(r"[{}\\]", " ", title)
    title = title.lower()
    title = re.sub(r"[^\w\s]", " ", title)
    return re.sub(r"\s+", " ", title).strip()


def title_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(
        None, normalize_title(a), normalize_title(b)
    ).ratio()


def summarize(results: list[EntryResult]) -> dict:
    counts: dict[str, int] = {"ok": 0, "warning": 0, "error": 0, "total": len(results)}
    for r in results:
        counts[r.overall()] += 1
    return counts


def annotate_bib(bib_text: str, results: list[EntryResult]) -> str:
    """Prepend a validator comment line above each @-entry in bib_text."""
    by_key = {r.key: r for r in results}
    out_lines: list[str] = []
    for line in bib_text.split("\n"):
        m = re.match(r"^@\w+\s*\{\s*([^,\s{]+)", line.strip(), re.IGNORECASE)
        if m:
            key = m.group(1)
            r = by_key.get(key)
            if r:
                out_lines.append(_entry_comment(r))
        out_lines.append(line)
    return "\n".join(out_lines)


def _entry_comment(r: EntryResult) -> str:
    parts: list[str] = []

    if r.parse_error:
        parts.append(f"PARSE ERROR: {r.parse_error}")
    elif r.missing_fields:
        parts.append(f"MISSING: {', '.join(r.missing_fields)}")
    else:
        parts.append("fields OK")

    if r.doi:
        if r.doi_ok is True:
            parts.append("DOI: resolves")
        elif r.doi_ok is False:
            parts.append(f"DOI: DEAD (HTTP {r.doi_status})")

    if r.crossref_confidence is not None:
        pct = int(r.crossref_confidence * 100)
        tag = "OK" if r.crossref_confidence >= THRESHOLD_OK else (
            "WARN" if r.crossref_confidence >= THRESHOLD_WARN else "MISMATCH")
        parts.append(f"CrossRef: {pct}% {tag}")
        if r.crossref_title and r.crossref_confidence < THRESHOLD_OK:
            short = r.crossref_title[:60]
            parts.append(f'  found: "{short}"')

    if r.s2_confidence is not None:
        pct = int(r.s2_confidence * 100)
        tag = "OK" if r.s2_confidence >= THRESHOLD_OK else (
            "WARN" if r.s2_confidence >= THRESHOLD_WARN else "MISMATCH")
        parts.append(f"S2: {pct}% {tag}")
        if r.s2_title and r.s2_confidence < THRESHOLD_OK:
            parts.append(f'  found: "{r.s2_title[:60]}"')

    status = r.overall().upper()
    return "% [bib-validator] " + status + " | " + " | ".join(parts)
