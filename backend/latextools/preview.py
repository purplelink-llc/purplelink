"""Free pre-payment preview for Paper Review.

Deterministic only: no LLM, no Anthropic call. Extracts the manuscript text
and reference list with the same code the paid review uses, checks each
reference against CrossRef, scans for anonymity leftovers with regular
expressions, and returns counts plus up to three findings that quote the
manuscript.

Nothing is stored. The PDF is parsed from memory, the result is returned to
the caller, and no manuscript text is written to a Modal Dict or a log line
(log calls here carry counts and timings only).

Network: only two fixed hosts are contacted, api.crossref.org and doi.org,
and redirects are never followed, so a DOI in an uploaded PDF cannot steer a
request anywhere else.
"""
from __future__ import annotations

import asyncio
import io
import logging
import re
import time
from typing import Optional
from urllib.parse import quote

from . import papercheck
from .papercheck import PaperReference

logger = logging.getLogger(__name__)

MAX_FINDINGS = 3
QUOTE_MAX_CHARS = 240
LOOKUP_CONCURRENCY = 6
LOOKUP_BUDGET_SECONDS = 35.0
REQUEST_TIMEOUT_SECONDS = 10.0
MAX_ANONYMITY_PAGES = 60
MIN_REFERENCE_CHARS = 25

_UA = {"User-Agent": "purplelink-paper-review-preview/1.0 (mailto:ben@purplelink.llc)"}

# Finding types, strongest first. The score orders the three that are shown.
_SCORES = {
    "doi_mismatch": 100,
    "reference_not_found": 80,
    "dead_doi": 70,
    "anonymity": 60,       # adjusted per kind below
    "weak_match": 40,
}
_ANON_SCORES = {
    "metadata_author": 76, "self_citation": 74, "acknowledgments": 66,
    "funding": 64, "email": 62, "repository": 58, "institution": 55,
}


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f​-‏‪-‮⁠﻿]")


def _quote(text: str, limit: int = QUOTE_MAX_CHARS) -> str:
    """One-line, control-character-free excerpt of manuscript text."""
    cleaned = re.sub(r"\s+", " ", _CONTROL_RE.sub("", text or "")).strip()
    if len(cleaned) > limit:
        cleaned = cleaned[: limit - 1].rstrip() + "…"
    return cleaned


def _tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{2,}", (s or "").lower()))


def _squash(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def title_in_reference(title: str, raw: str) -> float:
    """How much of a CrossRef *title* appears in the manuscript's *raw*
    reference entry, from 0 to 1.

    Compares against the whole entry rather than a parsed title, because the
    title parse is a heuristic and PDF text often arrives with words run
    together or hyphenated across lines. The squashed comparison (letters
    and digits only) survives both.
    """
    if not title or not raw:
        return 0.0
    sq_title = _squash(title)
    if len(sq_title) >= 12 and sq_title in _squash(raw):
        return 1.0
    t = _tokens(title)
    if not t:
        return 0.0
    return len(t & _tokens(raw)) / len(t)


# ---------------------------------------------------------------------------
# Extraction (CPU-bound; run in a worker thread)
# ---------------------------------------------------------------------------

_GENERIC_AUTHORS = {
    "", "anonymous", "anonymous author", "anonymous authors", "anonymous submission",
    "author", "authors", "user", "admin", "administrator", "owner", "unknown",
    "microsoft office user", "latex", "pdftex", "tex",
}


def _metadata_author(pdf_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader
        meta = PdfReader(io.BytesIO(pdf_bytes), strict=False).metadata
        author = str((meta.author if meta else "") or "").strip()
    except Exception:
        return ""
    if author.lower() in _GENERIC_AUTHORS or len(author) > 300:
        return ""
    return author


def extract(pdf_bytes: bytes):
    """Returns (structure, pages, metadata_author).

    Raises papercheck.PaperExtractionError for scanned or unreadable PDFs.
    """
    pages: list = []
    structure = papercheck.extract_paper(pdf_bytes, page_texts=pages)
    return structure, pages, _metadata_author(pdf_bytes)


# ---------------------------------------------------------------------------
# References against CrossRef
# ---------------------------------------------------------------------------

def _looks_unindexed(raw: str, ref: PaperReference) -> bool:
    """Preprints and web pages are mostly absent from CrossRef, so a miss on
    one says nothing about whether the citation is real."""
    low = raw.lower()
    return bool(ref.arxiv_id) or "arxiv" in low or "http://" in low or "https://" in low or "www." in low


async def _check_doi(client, ref: PaperReference) -> dict:
    """A reference that carries a DOI: does it resolve, and to this title?"""
    doi = ref.doi
    try:
        resp = await client.get(
            "https://api.crossref.org/works/" + quote(doi, safe="/"),
            params={"mailto": "ben@purplelink.llc"},
            headers=_UA, timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=False,
        )
    except Exception:
        return {"status": "unchecked"}
    if resp.status_code == 200:
        try:
            titles = (resp.json().get("message") or {}).get("title") or []
        except Exception:
            titles = []
        found = titles[0] if titles else ""
        if not found:
            return {"status": "verified"}
        score = title_in_reference(found, ref.raw)
        if score >= 0.6:
            return {"status": "verified"}
        if score < 0.35 and len(_tokens(found)) >= 3:
            return {"status": "doi_mismatch", "found_title": found, "doi": doi}
        return {"status": "weak_match", "found_title": found, "doi": doi}
    if resp.status_code != 404:
        return {"status": "unchecked"}

    # Not a CrossRef DOI. DataCite and other agencies still resolve at
    # doi.org: a redirect means the DOI exists. The redirect is not followed.
    try:
        head = await client.head(
            "https://doi.org/" + quote(doi, safe="/"),
            headers=_UA, timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=False,
        )
    except Exception:
        return {"status": "unchecked"}
    if head.status_code in (301, 302, 303, 307, 308):
        return {"status": "verified"}
    if head.status_code != 404:
        return {"status": "unchecked"}
    # The DOI does not exist as printed. PDF text often splits a DOI across
    # lines, so give the reference a second chance by title before flagging.
    by_title = await _check_title(client, PaperReference(raw=ref.raw, title=ref.title))
    if by_title["status"] == "verified":
        return by_title
    return {"status": "dead_doi", "doi": doi}


async def _check_title(client, ref: PaperReference) -> dict:
    """A reference without a DOI: bibliographic search, via the same
    papercheck._crossref_lookup the paid review uses."""
    raw = ref.raw
    query_ref = PaperReference(raw=raw, title=(ref.title or _quote(raw, 200)))
    res = await papercheck._crossref_lookup(client, query_ref)
    status = res.get("status")
    if status == "matched":
        return {"status": "verified"}
    if status == "not_found":
        return {"status": "unchecked" if _looks_unindexed(raw, ref) else "reference_not_found"}
    if status != "weak_match":
        return {"status": "unchecked"}
    found = res.get("found_title") or ""
    score = max(title_in_reference(found, raw), float(res.get("confidence") or 0.0))
    if score >= 0.8:
        return {"status": "verified"}
    if _looks_unindexed(raw, ref):
        return {"status": "unchecked"}
    if score < 0.35:
        return {"status": "reference_not_found", "found_title": found}
    return {"status": "weak_match", "found_title": found}


async def check_references(client, references: list[PaperReference]) -> list[dict]:
    """One result dict per reference, in order. Never raises. References not
    reached inside the time budget come back as "unchecked"."""
    sem = asyncio.Semaphore(LOOKUP_CONCURRENCY)

    async def _one(ref: PaperReference) -> dict:
        if len(ref.raw.strip()) < MIN_REFERENCE_CHARS:
            return {"status": "unchecked"}
        async with sem:
            try:
                if ref.doi:
                    return await _check_doi(client, ref)
                return await _check_title(client, ref)
            except Exception:
                return {"status": "unchecked"}

    tasks = [asyncio.ensure_future(_one(r)) for r in references]
    if not tasks:
        return []
    done, pending = await asyncio.wait(tasks, timeout=LOOKUP_BUDGET_SECONDS)
    for t in pending:
        t.cancel()
    out = []
    for t, ref in zip(tasks, references):
        res = {"status": "unchecked"}
        if t in done and not t.cancelled() and t.exception() is None:
            res = t.result()
        out.append({**res, "raw": ref.raw})
    return out


# ---------------------------------------------------------------------------
# Deterministic anonymity scan
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9][A-Za-z0-9._%+-]{0,63}@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+\b")
_REPO_RE = re.compile(r"\b(?:https?://)?(?:www\.)?(?:github|gitlab|bitbucket)\.(?:com|org)/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?", re.I)
_SELF_CITE_RE = re.compile(
    r"[^.\n]{0,80}\b(?:"
    r"(?:in|from|of|on|extends?|extending|following)?\s*(?:our|my)\s+(?:own\s+)?"
    r"(?:previous|prior|earlier|recent|past|preliminary)\s+"
    r"(?:work|works|study|studies|paper|papers|research|results?|findings|publications?|articles?)"
    r"|we\s+(?:have\s+)?(?:previously|recently|earlier)\s+"
    r"(?:showed|shown|demonstrated|proposed|reported|introduced|developed|presented|published|found)"
    r")\b[^.\n]{0,120}",
    re.I,
)
_CITATION_MARK_RE = re.compile(r"\[\s*\d+(?:\s*[,;–-]\s*\d+)*\s*\]|\(\s*[A-Z][^()]{0,60}\b(?:19|20)\d{2}[a-z]?\s*\)")
_ACK_HEADING_RE = re.compile(r"^\s*(?:\d+\.?\s+)?acknowledge?ments?\s*[:.]?\s*$", re.I)
_FUNDING_HEADING_RE = re.compile(r"^\s*(?:\d+\.?\s+)?(?:funding(?:\s+(?:statement|information|sources?))?|financial\s+support)\s*[:.]?\s*$", re.I)
_FUNDING_PHRASE_RE = re.compile(
    r"[^.\n]{0,100}\b(?:(?:was|were|is|are)\s+(?:partially\s+|partly\s+|jointly\s+)?(?:supported|funded)\s+(?:in\s+part\s+)?by"
    r"|grant\s+(?:no\.?|number|#|agreement)\s*[A-Za-z0-9]"
    r"|under\s+(?:grant|award|contract)\s+[A-Za-z0-9#]"
    r")[^.\n]{0,120}",
    re.I,
)
_INSTITUTION_RE = re.compile(
    r"\b(?:universit(?:y|ies|é|à|ät|at|eit|et|a)|universidad|universidade|institute|institut|"
    r"college|polytechnic|laborator(?:y|ies)|hospital|academy|"
    r"department\s+of|dept\.?\s+of|school\s+of|faculty\s+of|cent(?:er|re)\s+for)\b",
    re.I,
)
_ABSTRACT_LINE_RE = re.compile(r"^\s*abstract\b", re.I)
_HEADER_MAX_LINES = 25


def _anon(kind: str, label: str, quote_text: str, page: Optional[int], detail: str) -> dict:
    return {
        "type": "anonymity", "kind": kind, "label": label,
        "quote": _quote(quote_text), "page": page, "detail": detail,
        "_score": _ANON_SCORES.get(kind, _SCORES["anonymity"]),
    }


def anonymity_scan(pages: list, metadata_author: str = "") -> list[dict]:
    """Regular-expression scan for leftovers that break double-blind review.

    *pages* is [(page_number, text), ...] for the manuscript body (the
    reference list is not included). One finding per distinct quote.
    """
    findings: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def _add(kind, label, quote_text, page, detail):
        key = (kind, _quote(quote_text).lower())
        if not key[1] or key in seen:
            return
        seen.add(key)
        findings.append(_anon(kind, label, quote_text, page, detail))

    if metadata_author:
        _add("metadata_author", "Author name in the PDF properties",
             f"Author: {metadata_author}", None,
             "The PDF's document properties name an author. Reviewers can see this field in any PDF reader. Clear it before a blind submission.")

    for page_no, text in pages[:MAX_ANONYMITY_PAGES]:
        if not text:
            continue
        lines = text.split("\n")

        if page_no == 1:
            for line in lines[:_HEADER_MAX_LINES]:
                if _ABSTRACT_LINE_RE.match(line):
                    break
                if _INSTITUTION_RE.search(line) and len(line.strip()) <= 200:
                    _add("institution", "Institution named above the abstract", line, 1,
                         "An affiliation appears in the first-page header. Remove the author block for blind review.")

        for m in _EMAIL_RE.finditer(text):
            _add("email", "Email address", m.group(0), page_no,
                 "An email address identifies an author or their institution.")

        for m in _REPO_RE.finditer(text):
            _add("repository", "Link to a code repository", m.group(0), page_no,
                 "A repository URL usually carries a username or lab name. Use an anonymised mirror for review.")

        for m in _SELF_CITE_RE.finditer(text):
            if _CITATION_MARK_RE.search(m.group(0)):
                _add("self_citation", "Self-citation phrasing", m.group(0), page_no,
                     "This wording tells the reviewer that the cited work is yours. Cite it in the third person.")

        for i, line in enumerate(lines):
            if _ACK_HEADING_RE.match(line):
                following = " ".join(lines[i + 1:i + 4])
                _add("acknowledgments", "Acknowledgments section", f"{line.strip()}: {following}", page_no,
                     "Acknowledgments name colleagues, funders and institutions. Leave the section out of a blind submission.")
            elif _FUNDING_HEADING_RE.match(line):
                following = " ".join(lines[i + 1:i + 4])
                _add("funding", "Funding section", f"{line.strip()}: {following}", page_no,
                     "Funder names and grant numbers trace back to the authors. Withhold them until acceptance.")

        for m in _FUNDING_PHRASE_RE.finditer(text):
            _add("funding", "Funding statement", m.group(0), page_no,
                 "Funder names and grant numbers trace back to the authors. Withhold them until acceptance.")

    return findings


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

_REF_COPY = {
    "doi_mismatch": (
        "DOI points to a different title",
        "CrossRef lists this DOI under the title “{found}”, which does not appear in your reference.",
    ),
    "reference_not_found": (
        "No CrossRef match for this reference",
        "CrossRef has no close match. Books, reports and some conference papers are not indexed there, so check this one by hand.",
    ),
    "dead_doi": (
        "DOI does not resolve",
        "doi.org has no record of {doi}. Check it for a typo; a DOI split across two lines in the PDF can also cause this.",
    ),
    "weak_match": (
        "Only a partial CrossRef match",
        "The closest CrossRef record is “{found}”. Check the title, authors and year.",
    ),
}


def _reference_findings(results: list[dict]) -> list[dict]:
    out = []
    for r in results:
        status = r.get("status")
        if status not in _REF_COPY:
            continue
        label, detail = _REF_COPY[status]
        out.append({
            "type": status, "label": label, "quote": _quote(r.get("raw", "")), "page": None,
            "detail": detail.format(found=_quote(r.get("found_title", ""), 160), doi=_quote(r.get("doi", ""), 120)),
            "_score": _SCORES[status],
        })
    return out


def _pick(findings: list[dict]) -> list[dict]:
    """Strongest first, but never three of the same kind when another kind
    has something to show: at most two anonymity items alongside reference
    problems, and the other way round."""
    ranked = sorted(findings, key=lambda f: -f["_score"])
    shown: list[dict] = []
    per_group: dict[str, int] = {}
    groups = {("anonymity" if f["type"] == "anonymity" else "reference") for f in ranked}
    # Every non-blind manuscript trips the anonymity scan (author names and an
    # acknowledgments section are normal there), so when reference problems
    # exist they lead and anonymity gets one slot at most.
    caps = {"reference": 2 if len(groups) > 1 else MAX_FINDINGS,
            "anonymity": 1 if len(groups) > 1 else MAX_FINDINGS}
    ranked.sort(key=lambda f: (0 if f["type"] != "anonymity" else 1, -f["_score"]))
    for f in ranked:
        group = "anonymity" if f["type"] == "anonymity" else "reference"
        if per_group.get(group, 0) >= caps[group]:
            continue
        shown.append(f)
        per_group[group] = per_group.get(group, 0) + 1
        if len(shown) == MAX_FINDINGS:
            break
    return shown


def build_response(structure, ref_results: list[dict], anonymity: list[dict]) -> dict:
    statuses = [r.get("status") for r in ref_results]
    n_found = max(structure.n_references_total, len(ref_results))
    counts = {
        "references_found": n_found,
        "checked": sum(1 for s in statuses if s != "unchecked"),
        "verified": statuses.count("verified"),
        "weak_matches": statuses.count("weak_match"),
        "not_found": statuses.count("reference_not_found") + statuses.count("dead_doi"),
        "doi_mismatches": statuses.count("doi_mismatch"),
    }
    counts["unchecked"] = n_found - counts["checked"]
    counts["anonymity_leftovers"] = len(anonymity)

    all_findings = _reference_findings(ref_results) + anonymity
    shown = _pick(all_findings)
    shown_ids = {id(f) for f in shown}
    more = {"reference_not_found": 0, "doi_mismatch": 0, "dead_doi": 0, "weak_match": 0, "anonymity": 0}
    for f in all_findings:
        if id(f) not in shown_ids:
            more[f["type"]] += 1

    notes = []
    if n_found == 0:
        notes.append("No reference list was found. A heading such as References or Bibliography is needed to locate it.")
    elif n_found > len(ref_results):
        notes.append(f"The first {len(ref_results)} of {n_found} references were checked.")
    if anonymity:
        notes.append("Anonymity leftovers matter only if the venue reviews double-blind.")

    return {
        "status": "ok",
        "pages": structure.page_count,
        "counts": counts,
        "findings": [{k: v for k, v in f.items() if not k.startswith("_")} for f in shown],
        "more": more,
        "notes": notes,
    }


def make_client():
    import httpx
    # httpx logs every request URL at INFO, and the CrossRef query string is
    # reference text from the manuscript. Keep it out of the logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    return httpx.AsyncClient(
        timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS),
        limits=httpx.Limits(max_connections=LOOKUP_CONCURRENCY * 2),
        follow_redirects=False,
    )


async def run_preview(pdf_bytes: bytes) -> dict:
    """Full preview for one PDF. Raises papercheck.PaperExtractionError when
    the PDF has no usable text layer."""
    started = time.time()
    structure, pages, author = await asyncio.to_thread(extract, pdf_bytes)
    # extract_paper stops collecting body text at the reference heading, so
    # the pages before it are the ones to scan. Pages after the heading hold
    # the reference list, where emails and "supported by" would be noise.
    body_pages = _body_pages(pages)
    anonymity = anonymity_scan(body_pages, author)
    async with make_client() as client:
        ref_results = await check_references(client, structure.references)
    out = build_response(structure, ref_results, anonymity)
    logger.info(
        "paper preview: pages=%d refs=%d checked=%d anonymity=%d seconds=%.1f",
        structure.page_count, out["counts"]["references_found"],
        out["counts"]["checked"], len(anonymity), time.time() - started,
    )
    return out


def _body_pages(pages: list) -> list:
    """Pages up to and including the one where the reference list starts,
    with that page cut at the heading."""
    out = []
    for page_no, text in pages:
        cut = None
        offset = 0
        for line in text.split("\n"):
            if papercheck._bibliography_heading_split(line) is not None:
                cut = offset
                break
            offset += len(line) + 1
        if cut is not None:
            out.append((page_no, text[:cut]))
            break
        out.append((page_no, text))
    return out
