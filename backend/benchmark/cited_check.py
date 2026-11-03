# backend/benchmark/cited_check.py
"""Is a suggested "missing" citation already in the paper?

CrossRef confirming that a suggested title exists says nothing about
whether the manuscript already cites it. This module answers the second
question by matching the suggested work against the paper's own text:

  1. its DOI (or the arXiv ID inside an arXiv DOI) anywhere in the paper;
  2. its title anywhere in the paper, compared with all spacing and
     punctuation removed, so pdfplumber's merged words and line-break
     hyphens do not hide a match;
  3. its main title (the part before a colon), the same way;
  4. token coverage against each extracted reference: at least 80% of the
     title's content words appear in one reference entry;
  5. the same coverage within any window of WINDOW_LINES consecutive lines
     of the paper text. Two-column PDFs come out of pdfplumber with the two
     columns' lines interleaved, so a reference title can be split across
     lines that are not adjacent (a 2026-11-02 spot check found a cited
     paper this way that checks 1-4 missed).

The paper text is every page pdfplumber read, not only the references
papercheck.extract_paper keeps (it caps them at MAX_REFERENCES_TO_REVIEW),
so a work cited as reference 75 still counts as cited. A title that shows
up in the body but not the bibliography also counts as cited. Both choices
lean toward "already cited", which keeps the headline conservative.

Pure functions, no network: unit-testable and safe to re-run on saved text.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Short or generic titles ("GoT", "Deep Learning") would match by accident.
MIN_SQUASHED_TITLE_CHARS = 20
MIN_SQUASHED_MAIN_TITLE_CHARS = 15
MIN_CONTENT_TOKENS = 4
TOKEN_COVERAGE_THRESHOLD = 0.8
WINDOW_LINES = 8
# CrossRef's top hit must be the paper the model named, not a neighbour.
# Production accepts 0.6 word overlap, which let "Conformalized Composite
# Quantile Regression" stand in for "Conformalized Quantile Regression".
STRICT_TITLE_JACCARD = 0.8

_STOPWORDS = frozenset(
    "a an and are as at be by for from how in into is it its of on or the to "
    "via vs we what when where which with without".split()
)
_ARXIV_DOI_RE = re.compile(r"10\.48550/arxiv\.(\d{4}\.\d{4,5})", re.IGNORECASE)
# CrossRef often returns a supplementary-material DOI ("...s001"); the parent
# DOI is what a bibliography would carry.
_SUPPLEMENT_SUFFIX_RE = re.compile(r"\.s\d{3}$", re.IGNORECASE)


def _fold(text: str) -> str:
    """Lowercase, strip accents, and rejoin words split by a line-break hyphen."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"-\s*\n\s*", "", text)
    return text.lower()


def squash(text: str) -> str:
    """Only letters and digits: 'Attention Is All\\nYou-Need' -> 'attentionisallyouneed'."""
    return re.sub(r"[^a-z0-9]", "", _fold(text))


def content_tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", _fold(text)) if len(t) > 2 and t not in _STOPWORDS}


def _doi_forms(doi: str) -> list[str]:
    doi = (doi or "").strip().lower()
    if not doi:
        return []
    forms = {doi, _SUPPLEMENT_SUFFIX_RE.sub("", doi)}
    return [f for f in forms if f]


@dataclass
class PaperText:
    """What the check matches against: the full text and the parsed references."""
    squashed: str
    references: list[dict]   # PaperReference.to_dict() rows
    lines: list[str] | None = None
    _ref_tokens: list[set[str]] | None = None
    _window_tokens: list[set[str]] | None = None

    @classmethod
    def build(cls, full_text: str, references: list[dict]) -> "PaperText":
        return cls(squashed=squash(full_text), references=list(references or []),
                   lines=(full_text or "").splitlines())

    def window_tokens(self) -> list[set[str]]:
        if self._window_tokens is None:
            lines = self.lines or []
            self._window_tokens = [
                content_tokens("\n".join(lines[i:i + WINDOW_LINES]))
                for i in range(max(1, len(lines) - WINDOW_LINES + 1))
            ]
        return self._window_tokens

    def ref_tokens(self) -> list[set[str]]:
        if self._ref_tokens is None:
            self._ref_tokens = [content_tokens(r.get("raw", "")) for r in self.references]
        return self._ref_tokens


def find_citation(paper: PaperText, *, title: str = "", doi: str = "") -> str | None:
    """Return how the work was found in the paper ("doi", "arxiv_id", "title",
    "main_title", "reference_tokens", "text_window"), or None if it was not found."""
    for form in _doi_forms(doi):
        if squash(form) in paper.squashed:
            return "doi"
        if m := _ARXIV_DOI_RE.search(form):
            if squash(m.group(1)) in paper.squashed:
                return "arxiv_id"
        if any((r.get("doi") or "").lower().rstrip(".") == form for r in paper.references):
            return "doi"

    title = (title or "").strip()
    if not title:
        return None
    sq = squash(title)
    if len(sq) >= MIN_SQUASHED_TITLE_CHARS and sq in paper.squashed:
        return "title"
    if ":" in title:
        main = squash(title.split(":", 1)[0])
        if len(main) >= MIN_SQUASHED_MAIN_TITLE_CHARS and main in paper.squashed:
            return "main_title"

    tokens = content_tokens(title)
    if len(tokens) >= MIN_CONTENT_TOKENS:
        for ref_toks in paper.ref_tokens():
            if len(tokens & ref_toks) / len(tokens) >= TOKEN_COVERAGE_THRESHOLD:
                return "reference_tokens"
        for win_toks in paper.window_tokens():
            if len(tokens & win_toks) / len(tokens) >= TOKEN_COVERAGE_THRESHOLD:
                return "text_window"
    return None


def _strip_venue(title: str) -> str:
    """'Some Title (CMAME, 2022)' -> 'Some Title'."""
    return re.sub(r"\s*\([^)]*\b(19|20)\d{2}\b[^)]*\)\s*$", "", title or "").strip()


def titles_match(named: str, found: str) -> bool:
    """Is `found` (CrossRef's title) the same work as `named` (the model's)?"""
    a, b = squash(_strip_venue(named)), squash(found)
    if a and a == b:
        return True
    ta, tb = content_tokens(_strip_venue(named)), content_tokens(found)
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= STRICT_TITLE_JACCARD


def strictly_exists(gap: dict) -> bool:
    """CrossRef matched (production's "confirmed_exists") AND its record's
    title is the work the model named, by the stricter test above."""
    v = gap.get("verification") or {}
    if v.get("status") != "confirmed_exists":
        return False
    return any(titles_match(t, v.get("found_title", "")) for t in split_title_hint(gap.get("candidate_title_hint", "")))


def split_title_hint(hint: str) -> list[str]:
    """The model sometimes packs several titles into one hint, separated by ';'."""
    hint = (hint or "").strip()
    if not hint or hint.lower() in {"unknown", "n/a", "none"}:
        return []
    return [p.strip() for p in hint.split(";") if p.strip()]


def check_gap(paper: PaperText, gap: dict) -> dict:
    """Decide whether one gap's suggested work already appears in the paper.

    Checks the CrossRef-matched title and DOI and every title in the model's
    hint. If any of them is found, the gap is "already cited": when the model
    names three works and the paper cites one, we do not count the gap.
    """
    v = gap.get("verification") or {}
    probes: list[tuple[str, str]] = []
    if v.get("found_title") or v.get("found_doi"):
        probes.append((v.get("found_title", ""), v.get("found_doi", "")))
    probes.extend((t, "") for t in split_title_hint(gap.get("candidate_title_hint", "")))

    for title, doi in probes:
        how = find_citation(paper, title=title, doi=doi)
        if how:
            return {"cited": True, "how": how, "matched": title or doi}
    return {"cited": False, "how": None, "matched": None}


def is_counted_gap(gap: dict) -> bool:
    """The headline definition: CrossRef found the work the model named AND
    the paper does not cite it."""
    cited = (gap.get("already_cited") or {}).get("cited")
    return strictly_exists(gap) and cited is False


def apply_cited_check(gaps: list[dict], full_text: str, references: list[dict]) -> list[dict]:
    """Return new gap dicts, each with an "already_cited" verdict attached."""
    paper = PaperText.build(full_text, references)
    return [{**g, "already_cited": check_gap(paper, g)} for g in gaps]
