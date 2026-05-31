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
import unicodedata
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
    year: str = ""
    doi: str = ""
    missing_fields: list[str] = field(default_factory=list)
    parse_error: str = ""

    # Network results — None means "not checked"
    doi_ok: bool | None = None
    doi_status: int | None = None

    crossref_confidence: float | None = None
    crossref_title: str | None = None
    crossref_doi: str | None = None
    crossref_authors: list[str] | None = None
    crossref_year: int | None = None
    crossref_journal: str | None = None     # CrossRef's container-title
    crossref_volume: str | None = None
    crossref_issue: str | None = None
    crossref_pages: str | None = None
    crossref_publisher: str | None = None

    s2_confidence: float | None = None
    s2_title: str | None = None
    s2_year: int | None = None
    s2_authors: list[str] | None = None

    # Best author-similarity score (0..1) computed from whichever of
    # CrossRef / S2 returned an author list. None if no author check ran.
    author_match: float | None = None

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
        # Title matches well but authors do not — likely a hallucination
        # that latched onto a real paper. Warn rather than ok.
        title_matched = (cr is not None and cr >= THRESHOLD_OK) or (s2 is not None and s2 >= THRESHOLD_OK)
        if title_matched and self.author_match is not None and self.author_match < 0.5:
            return "warning"
        if year_mismatch(self):
            return "warning"
        return "ok"

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "type": self.entry_type,
            "year": self.year,
            "parse_error": self.parse_error,
            "missing_fields": self.missing_fields,
            "doi": self.doi,
            "doi_ok": self.doi_ok,
            "doi_status": self.doi_status,
            "crossref_confidence": self.crossref_confidence,
            "crossref_title": self.crossref_title,
            "crossref_doi": self.crossref_doi,
            "crossref_authors": self.crossref_authors,
            "crossref_year": self.crossref_year,
            "crossref_journal": self.crossref_journal,
            "crossref_volume": self.crossref_volume,
            "crossref_issue": self.crossref_issue,
            "crossref_pages": self.crossref_pages,
            "crossref_publisher": self.crossref_publisher,
            "s2_confidence": self.s2_confidence,
            "s2_title": self.s2_title,
            "s2_year": self.s2_year,
            "s2_authors": self.s2_authors,
            "author_match": self.author_match,
            "year_mismatch": year_mismatch(self),
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
            year=entry.get("year", ""),
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


def normalize_author_name(name: str) -> str:
    """Reduce an author name to a canonical, comparable last-name token.

    Handles the messy real-world space of name formats:
      "Smith, John"      → "smith"
      "John Smith"       → "smith"
      "J. A. Smith"      → "smith"
      "Smith-Jones, John" → "smith-jones"
      "Müller, Otto"     → "muller"          (diacritics folded)
      "{van der Berg}, J." → "van der berg"  (BibTeX braces stripped)

    Returns an empty string if the input is blank.
    """
    s = name.strip()
    if not s:
        return ""
    # "Last, First" form: split on first comma
    if "," in s:
        last = s.split(",", 1)[0]
    else:
        toks = s.split()
        last = toks[-1] if toks else ""
    # Strip BibTeX grouping braces commonly used for multi-word surnames
    last = last.replace("{", "").replace("}", "").strip()
    # Fold diacritics (Müller → Muller)
    last = unicodedata.normalize("NFD", last)
    last = "".join(c for c in last if unicodedata.category(c) != "Mn")
    return last.lower()


def split_authors(field: str) -> list[str]:
    """Split a BibTeX `author` field on the literal `\\s+and\\s+` separator."""
    s = (field or "").strip()
    if not s:
        return []
    parts = re.split(r"\s+and\s+", s)
    return [p.strip() for p in parts if p.strip()]


def author_similarity(bib_authors: str, ref_authors: list[str] | None) -> float:
    """Jaccard similarity over normalized last-name sets.

    bib_authors: raw BibTeX author field (e.g. "Smith, John and Doe, Jane").
    ref_authors: list of names from an external service (e.g. CrossRef).

    Returns 1.0 if both sides reduce to identical last-name sets, 0.0 if no
    overlap, partial credit otherwise. Returns 0.0 if either side is empty.
    """
    bib_lasts = {normalize_author_name(a) for a in split_authors(bib_authors)}
    ref_lasts = {normalize_author_name(a) for a in (ref_authors or [])}
    bib_lasts.discard("")
    ref_lasts.discard("")
    if not bib_lasts or not ref_lasts:
        return 0.0
    inter = bib_lasts & ref_lasts
    union = bib_lasts | ref_lasts
    return len(inter) / len(union)


def _parse_year(s: str) -> int | None:
    """Pull a four-digit year out of a BibTeX year field. Tolerant of `{2020}`,
    `2020a`, `in press, 2020`, etc."""
    if not s:
        return None
    m = re.search(r"\d{4}", s)
    return int(m.group()) if m else None


def year_mismatch(r: "EntryResult") -> bool:
    """True iff the bib year and the best authoritative year differ by >= 2.

    A drift of 0–1 years is tolerated because online-first / print years
    legitimately differ. Either side missing → no mismatch (insufficient info).
    """
    bib_y = _parse_year(r.year)
    if bib_y is None:
        return False
    for ref_y in (r.crossref_year, r.s2_year):
        if ref_y is not None and abs(bib_y - ref_y) >= 2:
            return True
    return False


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


# ---------------------------------------------------------------------------
# Corrected-bib generation
# ---------------------------------------------------------------------------

# Container-title (CrossRef) maps to different BibTeX field names depending on
# the entry type. Proceedings-shaped entries use `booktitle`; everything else
# uses `journal`.
_BOOKTITLE_TYPES = {
    "inproceedings", "conference", "incollection",
    "inbook", "proceedings",
}


def _format_authors_for_bib(authors: list[str] | None) -> str:
    """Render CrossRef-style names ("Jane Doe") into BibTeX "Last, First" joined
    by " and ". Pass-through if a name already contains a comma."""
    out: list[str] = []
    for a in (authors or []):
        a = a.strip()
        if not a:
            continue
        if "," in a:
            out.append(a)
            continue
        parts = a.rsplit(" ", 1)
        if len(parts) == 2 and parts[1]:
            out.append(f"{parts[1]}, {parts[0]}")
        else:
            out.append(a)
    return " and ".join(out)


def _find_entry_end(lines: list[str], start_idx: int) -> int:
    """Return the line index containing the closing `}` of the entry that
    begins on lines[start_idx]. Walks brace depth, tolerant of nested braces
    inside values."""
    depth = 0
    seen_open = False
    in_string = False  # inside "..." string in BibTeX
    for i in range(start_idx, len(lines)):
        for ch in lines[i]:
            if ch == '"' and not (seen_open and depth == 0):
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
                seen_open = True
            elif ch == "}":
                depth -= 1
                if seen_open and depth == 0:
                    return i
    return len(lines) - 1


def _build_corrected_entry(r: EntryResult, entry_type: str, key: str) -> str:
    """Build a fully-corrected BibTeX entry string from CrossRef metadata.

    Preserves the original entry's key and type; replaces all other fields
    with authoritative values where CrossRef provided them. Fields the source
    did not return are simply omitted (rather than blanked).
    """
    fields: list[tuple[str, str]] = []

    authors = _format_authors_for_bib(r.crossref_authors)
    if authors:
        fields.append(("author", authors))
    if r.crossref_title:
        fields.append(("title", r.crossref_title))
    if r.crossref_year is not None:
        fields.append(("year", str(r.crossref_year)))

    if r.crossref_journal:
        type_lc = entry_type.lower()
        field_name = "booktitle" if type_lc in _BOOKTITLE_TYPES else "journal"
        fields.append((field_name, r.crossref_journal))
    if r.crossref_volume:
        fields.append(("volume", r.crossref_volume))
    if r.crossref_issue:
        fields.append(("number", r.crossref_issue))
    if r.crossref_pages:
        fields.append(("pages", r.crossref_pages))
    if r.crossref_publisher:
        fields.append(("publisher", r.crossref_publisher))
    if r.crossref_doi:
        fields.append(("doi", r.crossref_doi))

    lines = [f"@{entry_type}{{{key},"]
    for k, v in fields:
        # 2-space indent, key left-padded to 9 chars for readable column alignment
        lines.append(f"  {k:<9}= {{{v}}},")
    lines.append("}")
    return "\n".join(lines)


def correct_bib(bib_text: str, results: list[EntryResult]) -> str:
    """Produce a corrected .bib where entries with high-confidence CrossRef
    matches (>= THRESHOLD_OK) are replaced wholesale with authoritative
    metadata. Low- or no-confidence entries pass through unchanged.

    Each replaced entry is preceded by a comment marker so users can audit
    which entries the tool rewrote.
    """
    by_key = {r.key: r for r in results}
    lines = bib_text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^@(\w+)\s*\{\s*([^,\s{]+)", line.strip(), re.IGNORECASE)
        if m:
            entry_type, key = m.group(1), m.group(2)
            r = by_key.get(key)
            if (
                r is not None
                and r.crossref_confidence is not None
                and r.crossref_confidence >= THRESHOLD_OK
            ):
                end = _find_entry_end(lines, i)
                out.append("% [bib-validator] CORRECTED from CrossRef")
                out.append(_build_corrected_entry(r, entry_type, key))
                i = end + 1
                continue
        out.append(line)
        i += 1
    return "\n".join(out)


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

    if r.author_match is not None:
        pct = int(r.author_match * 100)
        tag = "OK" if r.author_match >= 0.85 else (
            "PARTIAL" if r.author_match >= 0.5 else "MISMATCH")
        parts.append(f"Authors: {pct}% {tag}")

    if year_mismatch(r):
        ref_y = r.crossref_year if r.crossref_year is not None else r.s2_year
        parts.append(f"Year: bib={r.year} vs ref={ref_y} MISMATCH")

    status = r.overall().upper()
    return "% [bib-validator] " + status + " | " + " | ".join(parts)
