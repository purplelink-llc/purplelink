"""Reference checking for the ChatGPT / Claude citation app (MCP server).

Pure parsing and matching plus async lookups against Crossref and Semantic
Scholar. No Modal import, no MCP import, no storage. The lookup functions take
an httpx.AsyncClient so tests can mock the transport; nothing here logs the
reference text.

The matching mirrors the site's BibTeX validator (bibcheck.py and the
/validate-bib endpoint in app.py): Crossref first, Semantic Scholar as the
fallback, title similarity thresholds of 0.85 (confident) and 0.50 (low), and
last-name Jaccard for authors. Retraction detection is a port of the
Retraction Checker's retractionOf() in site/tools/retraction-check/.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from urllib.parse import quote

from latextools.bibcheck import (
    THRESHOLD_OK,
    THRESHOLD_WARN,
    normalize_author_name,
    normalize_title,
    split_authors,
    title_similarity,
)

MAX_ENTRIES = 100
MAX_INPUT_BYTES = 200_000
MAX_DOIS = 100
MAX_BIBTEX_DOIS = 50
MAX_TITLE_LOOKUPS_RETRACTION = 25

MAILTO = "ben@purplelink.llc"
USER_AGENT = f"purplelink-citation-app/1.0 (mailto:{MAILTO})"
CROSSREF = "https://api.crossref.org/works"
S2_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"

CROSSREF_CONCURRENCY = 3   # Crossref's polite pool allows about 3 at once
S2_CONCURRENCY = 1
DEADLINE_SECONDS = 24.0    # whole-call budget; unfinished entries come back as lookup_incomplete

RETRACTED_TYPES = {"retraction", "withdrawal", "removal"}
CONCERN_TYPES = {"expression_of_concern", "partial_retraction"}
CORRECTION_TYPES = {"correction", "corrigendum", "erratum", "addendum", "clarification"}
_TITLE_FLAG = re.compile(r"^\s*(?:retracted|withdrawn)\s*[:\-–—]", re.I)
_TITLE_PREFIX = re.compile(r"^\s*(?:retracted|retraction|withdrawn)\s*[:\-–—]\s*", re.I)

# Includes < and > because early Wiley DOIs contain them.
DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()<>/:A-Za-z0-9]+")
_BIB_ENTRY_RE = re.compile(r"@\w+\s*\{")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


class InputError(ValueError):
    """The caller's input is unusable. The message is safe to show the model."""


# ---------------------------------------------------------------- parsing


@dataclass
class Reference:
    index: int
    raw: str
    title: str = ""
    authors: str = ""     # BibTeX-style author string, or the text before the year
    year: str = ""
    venue: str = ""
    doi: str = ""
    key: str = ""
    from_bibtex: bool = False


def trim_doi(raw: str) -> str:
    d = re.sub(r"""[.,;:\]}"'’”]+$""", "", raw)
    while d.endswith(">") and d.count(">") > d.count("<"):
        d = re.sub(r"[.,;:]+$", "", d[:-1])
    while d.endswith(")") and d.count(")") > d.count("("):
        d = re.sub(r"[.,;:]+$", "", d[:-1])
    return d


def normalize_doi(value: str) -> str:
    """'https://doi.org/10.1/x', 'doi:10.1/x' or '10.1/x' to '10.1/x'. '' if none."""
    v = (value or "").strip()
    v = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", v, flags=re.I)
    m = DOI_RE.search(v)
    return trim_doi(m.group(0)) if m else ""


def extract_dois(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in DOI_RE.finditer(text or ""):
        d = trim_doi(m.group(0))
        if len(d) < 8 or d.lower() in seen:
            continue
        seen.add(d.lower())
        out.append(d)
    return out


def _check_size(text: str) -> None:
    if len(text.encode("utf-8", errors="replace")) > MAX_INPUT_BYTES:
        raise InputError(
            f"Input is larger than {MAX_INPUT_BYTES // 1000} KB. Send the reference list only, "
            f"in batches of up to {MAX_ENTRIES} entries."
        )


def _clean_bib_value(v: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[{}]", "", v or "")).strip()


def _parse_bibtex(text: str) -> list[Reference]:
    import bibtexparser
    from bibtexparser.bparser import BibTexParser

    parser = BibTexParser(common_strings=True)
    parser.ignore_nonstandard_types = False
    db = bibtexparser.loads(text, parser=parser)
    refs: list[Reference] = []
    for e in db.entries:
        venue = e.get("journal") or e.get("booktitle") or e.get("journaltitle") or ""
        doi = normalize_doi(e.get("doi", "")) or normalize_doi(e.get("url", ""))
        refs.append(Reference(
            index=0,
            raw=_clean_bib_value(e.get("title", "")) or e.get("ID", "?"),
            title=_clean_bib_value(e.get("title", "")),
            authors=_clean_bib_value(e.get("author", "")).replace("{", "").replace("}", ""),
            year=_clean_bib_value(e.get("year", "") or str(e.get("date", ""))[:4]),
            venue=_clean_bib_value(venue),
            doi=doi,
            key=e.get("ID", ""),
            from_bibtex=True,
        ))
    return refs


def guess_title(line: str) -> str:
    """Segment after the year up to the next sentence. Brittle by design, like the site tool's."""
    m = re.search(r"\b(?:19|20)\d{2}[a-z]?\b", line)
    rest = line[m.end():] if m else line
    rest = re.sub(r"^[\s.,;:)\]]+", "", rest)
    t = re.match(r"^([^.]{12,}?)\.\s+[A-Z]", rest + ". X")
    return (t.group(1) if t else rest)[:200].strip()


def _parse_plain(text: str) -> list[Reference]:
    blocks = re.split(r"\n\s*\n", text) if re.search(r"\n\s*\n", text) else text.split("\n")
    refs: list[Reference] = []
    for blk in blocks:
        line = re.sub(r"\s+", " ", blk).strip()
        line = re.sub(r"^\s*(?:\[\d{1,3}\]|\d{1,3}[.)])\s*", "", line)
        doi = normalize_doi(line) if DOI_RE.search(line) else ""
        has_year = re.search(r"\b(19|20)\d{2}\b", line)
        if not doi and (len(line) < 40 or not has_year):
            continue
        if doi and len(line) < 10:
            continue
        ym = re.search(r"\b((?:19|20)\d{2})[a-z]?\b", line)
        refs.append(Reference(
            index=0,
            raw=line[:600],
            title=guess_title(line) if not (doi and len(line) <= len(doi) + 2) else "",
            authors=line[:ym.start()].strip(" .,;:([") if ym else "",
            year=ym.group(1) if ym else "",
            doi=doi,
        ))
    return refs


def parse_references(text: str) -> tuple[list[Reference], list[str]]:
    """BibTeX or plain-text list to references. Returns (refs, notes)."""
    if not isinstance(text, str) or not text.strip():
        raise InputError("No references were provided.")
    _check_size(text)
    refs = _parse_bibtex(text) if _BIB_ENTRY_RE.search(text) else _parse_plain(text)
    if not refs:
        raise InputError(
            "No references found. Send BibTeX entries, or a list with one reference per line "
            "or per blank-line-separated paragraph, each with a year."
        )
    notes: list[str] = []
    if len(refs) > MAX_ENTRIES:
        notes.append(f"Only the first {MAX_ENTRIES} of {len(refs)} references were checked. Send the rest in another call.")
        refs = refs[:MAX_ENTRIES]
    for i, r in enumerate(refs, 1):
        r.index = i
    return refs, notes


# ----------------------------------------------------- retraction logic


def _update_date(u: dict) -> str:
    try:
        parts = ((u.get("updated") or {}).get("date-parts") or [[]])[0]
        nums = [int(x) for x in parts[:3]]
    except Exception:
        return ""
    if not nums or not (1000 <= nums[0] <= 9999):
        return ""
    return "-".join([f"{nums[0]:04d}"] + [f"{n:02d}" for n in nums[1:]])


def _notice(type_: str, doi: str, date: str) -> dict:
    doi = doi[:120]
    url = "https://doi.org/" + quote(doi, safe="/()-._~:;") if doi else ""
    return {"type": type_, "doi": doi, "date": date, "url": url}


def retraction_status(message: dict) -> dict:
    """Retraction / concern / correction status of one Crossref work record.

    Returns {"status": "retracted" | "expression_of_concern" | "corrected" | "none",
    "notices": [{type, doi, date, url}]}. Port of retractionOf() in the site's
    Retraction Checker, extended with corrections. Pure: no network.
    """
    none = {"status": "none", "notices": []}
    if not isinstance(message, dict):
        return none
    found: list[dict] = []
    updates = message.get("updated-by")
    for u in updates if isinstance(updates, list) else []:
        if not isinstance(u, dict):
            continue
        t = str(u.get("type") or "").strip().lower()
        if t in RETRACTED_TYPES | CONCERN_TYPES | CORRECTION_TYPES:
            found.append(_notice(t, str(u.get("DOI") or ""), _update_date(u)))
    hard = [f for f in found if f["type"] in RETRACTED_TYPES]
    concern = [f for f in found if f["type"] in CONCERN_TYPES]
    corr = [f for f in found if f["type"] in CORRECTION_TYPES]
    if hard:
        return {"status": "retracted", "notices": (hard + concern + corr)[:5]}
    if concern:
        return {"status": "expression_of_concern", "notices": (concern + corr)[:5]}
    # The record is itself a retraction notice: citing it is citing a retraction.
    targets = message.get("update-to")
    for t in targets if isinstance(targets, list) else []:
        if isinstance(t, dict) and str(t.get("type") or "").strip().lower() in RETRACTED_TYPES:
            return {"status": "retracted", "notices": [_notice("retraction_notice_itself", str(message.get("DOI") or ""), _update_date(t))]}
    titles = message.get("title")
    title = titles[0] if isinstance(titles, list) and titles else ""
    if isinstance(title, str) and _TITLE_FLAG.match(title):
        return {"status": "retracted", "notices": [_notice("title_flag", "", "")]}
    if corr:
        return {"status": "corrected", "notices": corr[:5]}
    return none


# ------------------------------------------------------------- matching


def _safe(s: object, limit: int = 300) -> str:
    """Crossref and S2 text is untrusted: drop control characters, bound the length."""
    return _CONTROL_RE.sub(" ", str(s or "")).strip()[:limit]


def _tokens(s: str) -> set[str]:
    return set(normalize_title(s).split())


def title_score(ref: Reference, found_title: str) -> float:
    """0..1 match between the cited and the found title.

    BibTeX titles are exact fields, so plain sequence similarity is used (as in
    the site validator). A pasted reference has no reliable title field, so the
    score is the better of that and how much of the found title's words appear
    in the whole reference.
    """
    found = _TITLE_PREFIX.sub("", found_title or "")
    if not found.strip():
        return 0.0
    score = title_similarity(ref.title, found) if ref.title else 0.0
    if not ref.from_bibtex:
        nf, nr = normalize_title(found), normalize_title(ref.raw)
        if len(nf) >= 8 and f" {nf} " in f" {nr} ":
            score = 1.0   # the whole found title appears verbatim in the reference
        else:
            ft = _tokens(found)
            if len(ft) >= 3:
                score = max(score, len(ft & _tokens(ref.raw)) / len(ft))
    return round(score, 3)


@dataclass
class Candidate:
    source: str            # "crossref" | "semantic_scholar"
    title: str
    doi: str = ""
    year: int | None = None
    authors: list[str] = field(default_factory=list)
    venue: str = ""
    retraction: dict | None = None
    score: float = 0.0


def _crossref_author(a: dict) -> str:
    fam, giv, name = (a.get("family") or "").strip(), (a.get("given") or "").strip(), (a.get("name") or "").strip()
    return f"{fam}, {giv}" if fam and giv else fam or name


def candidate_from_crossref(item: dict) -> Candidate:
    issued = ((item.get("issued") or {}).get("date-parts") or [[]])[0]
    year = issued[0] if issued and isinstance(issued[0], int) else None
    ct = item.get("container-title") or []
    return Candidate(
        source="crossref",
        title=_safe((item.get("title") or [""])[0]),
        doi=_safe(item.get("DOI"), 120),
        year=year,
        authors=[_safe(_crossref_author(a), 80) for a in (item.get("author") or []) if isinstance(a, dict)][:30],
        venue=_safe(ct[0] if ct else "", 200),
        retraction=retraction_status(item),
    )


def candidate_from_s2(p: dict) -> Candidate:
    ext = p.get("externalIds") or {}
    return Candidate(
        source="semantic_scholar",
        title=_safe(p.get("title")),
        doi=_safe(ext.get("DOI"), 120),
        year=p.get("year") if isinstance(p.get("year"), int) else None,
        authors=[_safe(a.get("name"), 80) for a in (p.get("authors") or []) if isinstance(a, dict) and a.get("name")][:30],
        venue=_safe(p.get("venue"), 200),
    )


def author_overlap(cited: str, found: list[str]) -> float:
    """Share of the cited last names that appear among the found authors.

    The site validator uses Jaccard, which penalises a cited list shorter than
    the real one. Citing the first few authors, or "and others", is normal, so
    here only cited names that are missing from the real author list count.
    """
    cited_lasts = {normalize_author_name(a) for a in split_authors(cited) if a.strip().lower() not in ("others", "et al.", "et al")}
    found_lasts = {normalize_author_name(a) for a in found}
    cited_lasts.discard("")
    found_lasts.discard("")
    if not cited_lasts or not found_lasts:
        return 1.0   # nothing to compare
    return len(cited_lasts & found_lasts) / len(cited_lasts)


def find_mismatches(ref: Reference, c: Candidate) -> list[dict]:
    out: list[dict] = []
    try:
        cy = int(re.search(r"\d{4}", ref.year).group(0)) if ref.year else None
    except Exception:
        cy = None
    if cy and c.year and cy != c.year:
        note = " (off by one: online-first and print years often differ)" if abs(cy - c.year) == 1 else ""
        out.append({"field": "year", "cited": str(cy), "found": str(c.year) + note})
    if c.authors:
        if ref.from_bibtex and ref.authors:
            if author_overlap(ref.authors, c.authors) < 0.5:
                out.append({"field": "authors", "cited": ref.authors[:200], "found": "; ".join(c.authors[:6])})
        elif not ref.from_bibtex:
            first = normalize_author_name(c.authors[0])
            if first and first not in normalize_title(ref.raw).replace(" ", "") and first not in normalize_title(ref.raw):
                out.append({"field": "authors", "cited": ref.authors[:200] or "(not found in reference)", "found": "; ".join(c.authors[:6])})
    if ref.from_bibtex and ref.venue and c.venue:
        a, b = _tokens(ref.venue), _tokens(c.venue)
        if a and b and len(a & b) / len(a | b) < 0.3 and not (a <= b or b <= a):
            out.append({"field": "venue", "cited": ref.venue[:150], "found": c.venue[:150]})
    return out


def classify(score: float, have_candidate: bool) -> str:
    if not have_candidate:
        return "not_found"
    if score >= THRESHOLD_OK:
        return "found"
    if score >= THRESHOLD_WARN:
        return "needs_review"
    return "likely_hallucinated"


# --------------------------------------------------------------- lookups


async def _get_json(client, url: str, params: dict | None, headers: dict | None = None, retries: int = 1):
    """GET with one short retry on 429/503. Returns (status, json_or_None). Never raises."""
    for attempt in range(retries + 1):
        try:
            r = await client.get(url, params=params, headers=headers, follow_redirects=False)
        except Exception:
            return 0, None
        if r.status_code in (429, 503) and attempt < retries:
            try:
                wait = min(float(r.headers.get("retry-after", "1")), 2.0)
            except ValueError:
                wait = 1.0
            await asyncio.sleep(wait)
            continue
        if r.status_code != 200:
            return r.status_code, None
        try:
            return 200, r.json()
        except Exception:
            return 0, None
    return 0, None


def _unavailable(status: int) -> bool:
    """No answer, throttled, or a server error: the service, not the reference, is the problem."""
    return status == 0 or status == 429 or status >= 500


class Lookups:
    """Crossref + Semantic Scholar with bounded concurrency. One per tool call."""

    SELECT = "title,DOI,author,issued,container-title,updated-by,update-to"

    def __init__(self, client) -> None:
        self.client = client
        self.cr = asyncio.Semaphore(CROSSREF_CONCURRENCY)
        self.s2 = asyncio.Semaphore(S2_CONCURRENCY)
        self.crossref_down = False
        self.s2_down = False

    async def crossref_work(self, doi: str) -> tuple[str, Candidate | None]:
        """('ok'|'missing'|'error', candidate)"""
        async with self.cr:
            status, data = await _get_json(
                self.client, f"{CROSSREF}/{quote(doi, safe='/')}",
                {"mailto": MAILTO}, {"User-Agent": USER_AGENT})
        if status == 200 and data and data.get("message"):
            return "ok", candidate_from_crossref(data["message"])
        if status == 404:
            return "missing", None
        self.crossref_down = self.crossref_down or status in (0, 429) or status >= 500
        return "error", None

    async def crossref_search(self, ref: Reference) -> list[Candidate] | None:
        """Candidates, [] when Crossref has none, None when the lookup failed."""
        query = ref.raw if not ref.from_bibtex else f"{ref.title} {ref.authors}"
        params = {"query.bibliographic": query[:300], "rows": "3", "select": self.SELECT, "mailto": MAILTO}
        async with self.cr:
            status, data = await _get_json(self.client, CROSSREF, params, {"User-Agent": USER_AGENT})
        if status != 200 or not data:
            self.crossref_down = self.crossref_down or status in (0, 429) or status >= 500
            return []
        return [candidate_from_crossref(i) for i in (data.get("message") or {}).get("items", [])]

    async def s2_search(self, ref: Reference) -> list[Candidate] | None:
        q = ref.title or guess_title(ref.raw) or ref.raw
        params = {"query": q[:200], "fields": "title,authors,year,venue,externalIds", "limit": "3"}
        async with self.s2:
            status, data = await _get_json(self.client, S2_SEARCH, params, {"User-Agent": USER_AGENT}, retries=0)
        if status != 200 or data is None:
            self.s2_down = self.s2_down or status in (0, 429) or status >= 500
            return []
        return [candidate_from_s2(p) for p in (data.get("data") or []) if isinstance(p, dict)]


def _cited_year(ref: Reference) -> int | None:
    m = re.search(r"\d{4}", ref.year or "")
    return int(m.group(0)) if m else None


def _year_ok(ref: Reference, c: Candidate) -> bool:
    cy = _cited_year(ref)
    return cy is None or c.year is None or abs(cy - c.year) <= 1


def _is_notice(c: Candidate) -> bool:
    return any(n["type"] == "retraction_notice_itself" for n in (c.retraction or {}).get("notices", []))


def _rank(ref: Reference, c: Candidate) -> tuple:
    """Title match first; among near-equal titles, the cited year, then the work over its own retraction
    notice (which shares the title), then a record that carries a retraction or concern flag."""
    flagged = (c.retraction or {}).get("status") in ("retracted", "expression_of_concern")
    return (round(c.score, 1), _year_ok(ref, c), not _is_notice(c), flagged, c.score)


def _best(ref: Reference, cands: list[Candidate]) -> Candidate | None:
    for c in cands:
        c.score = title_score(ref, c.title)
    return max(cands, key=lambda c: _rank(ref, c)) if cands else None


def _settled(ref: Reference, c: Candidate | None) -> bool:
    """A confident title match in the cited year (give or take one) needs no further source."""
    return c is not None and c.score >= THRESHOLD_OK and _year_ok(ref, c)


async def check_reference(lk: Lookups, ref: Reference) -> dict:
    """Look up one reference. Always returns a result dict; never raises."""
    notes: list[str] = []
    best: Candidate | None = None
    doi_missing = False
    doi_cand: Candidate | None = None   # the record the cited DOI resolves to

    if ref.doi:
        state, cand = await lk.crossref_work(ref.doi)
        if state == "ok" and cand:
            cand.score = title_score(ref, cand.title) if (ref.title or not ref.from_bibtex) else 1.0
            if not ref.title and ref.from_bibtex:
                notes.append("The entry has a DOI but no title, so only the DOI was checked.")
            best = doi_cand = cand
            if cand.score < THRESHOLD_OK and ref.title:
                notes.append("The DOI resolves to a paper with a different title than the one cited.")
        elif state == "missing":
            doi_missing = True
            notes.append("The DOI is not registered with Crossref (it may belong to another agency such as DataCite, or be invalid).")

    searched_ok = False   # at least one index answered the title search
    if not _settled(ref, best):
        cands = await lk.crossref_search(ref) if not lk.crossref_down else None
        searched_ok = cands is not None
        b = _best(ref, cands or [])
        if b and (best is None or _rank(ref, b) > _rank(ref, best)):
            best = b
        if not _settled(ref, best):
            s2c = await lk.s2_search(ref) if not lk.s2_down else None
            searched_ok = searched_ok or s2c is not None
            b2 = _best(ref, s2c or [])
            if b2 and (best is None or _rank(ref, b2) > _rank(ref, best)):
                best = b2
                if b2.doi:
                    st, cc = await lk.crossref_work(b2.doi)
                    if st == "ok" and cc:
                        b2.retraction = cc.retraction
    else:
        searched_ok = True

    if best is None and not searched_ok and not doi_missing:
        return _result(ref, "lookup_failed", None, [], notes + ["Crossref and Semantic Scholar could not be reached for this entry. Try again."])
    status = classify(best.score if best else 0.0, best is not None)
    if status == "not_found" and doi_missing:
        status = "likely_hallucinated"
        notes.append("No DOI match and no title match anywhere: a fabricated DOI is a common sign of an invented reference.")
    mism = find_mismatches(ref, best) if best and status in ("found", "needs_review") else []
    if status == "needs_review" and best and best.score < 0.75 and any(m["field"] == "authors" for m in mism):
        status = "likely_hallucinated"   # a loosely similar title with none of the cited authors
    if status == "found" and best and best is not doi_cand and not _year_ok(ref, best):
        # Found by title search only, years apart: often a reprint, a copy or another edition. When the cited DOI
        # itself resolves to this title, the DOI settles identity and the year is just a mismatch.
        status = "needs_review"
        notes.append("The only close title match is from a different year. It may be a reprint or a copy rather than the cited work.")
    elif status == "needs_review":
        notes.append("The closest published title is similar but not the same. Compare it with your source.")
    if status == "likely_hallucinated" and best:
        notes.append("The closest published title is a poor match. Check that the reference exists before citing it.")
    return _result(ref, status, best, mism, notes)


def _result(ref: Reference, status: str, c: Candidate | None, mism: list[dict], notes: list[str]) -> dict:
    ret = (c.retraction if c else None) or {"status": "none", "notices": []}
    flagged = c is not None and status in ("found", "needs_review")
    return {
        "index": ref.index,
        "key": ref.key or None,
        "reference": ref.raw[:200],
        "status": status,
        "match_score": c.score if c else None,
        "matched_doi": (c.doi or None) if c and status in ("found", "needs_review") else None,
        "matched_title": c.title if c and status in ("found", "needs_review", "likely_hallucinated") else None,
        "matched_source": c.source if c else None,
        "mismatches": mism,
        "retraction_status": ret["status"] if flagged else "unknown",
        "retraction_notices": ret["notices"] if flagged else [],
        "notes": notes,
    }


async def check_references(client, refs: list[Reference], deadline: float = DEADLINE_SECONDS) -> list[dict]:
    """Check all references concurrently inside a wall-clock budget; unfinished ones are marked, not dropped."""
    lk = Lookups(client)
    tasks = {asyncio.ensure_future(check_reference(lk, r)): r for r in refs}
    done, pending = await asyncio.wait(tasks.keys(), timeout=deadline)
    for t in pending:
        t.cancel()
    out: dict[int, dict] = {}
    for t in done:
        r = tasks[t]
        try:
            out[r.index] = t.result()
        except Exception:
            out[r.index] = _result(r, "lookup_failed", None, [], ["Lookup failed."])
    for t in pending:
        r = tasks[t]
        out[r.index] = _result(r, "lookup_incomplete", None, [], ["Ran out of time. Send this entry again in a smaller batch."])
    return [out[r.index] for r in refs]


def summarize_references(results: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return {
        "total": len(results),
        "found": counts.get("found", 0),
        "needs_review": counts.get("needs_review", 0),
        "likely_hallucinated": counts.get("likely_hallucinated", 0),
        "not_found": counts.get("not_found", 0),
        "lookup_failed": counts.get("lookup_failed", 0) + counts.get("lookup_incomplete", 0),
        "retracted": sum(1 for r in results if r["retraction_status"] == "retracted"),
        "expression_of_concern": sum(1 for r in results if r["retraction_status"] == "expression_of_concern"),
        "corrected": sum(1 for r in results if r["retraction_status"] == "corrected"),
    }


# ------------------------------------------------------ check_retractions


async def retractions_for_dois(client, dois: list[str], deadline: float = DEADLINE_SECONDS) -> list[dict]:
    """Retraction status per DOI. Batches of 20 through the Crossref filter, as the site tool does."""
    lk = Lookups(client)
    by_doi: dict[str, dict] = {}
    plain = [d for d in dois if "," not in d]
    odd = [d for d in dois if "," in d]
    chunks = [plain[i:i + 20] for i in range(0, len(plain), 20)]

    async def chunk_job(chunk: list[str]) -> None:
        params = {
            "filter": ",".join("doi:" + d for d in chunk),
            "select": "DOI,title,updated-by,update-to", "rows": str(len(chunk)), "mailto": MAILTO,
        }
        async with lk.cr:
            status, data = await _get_json(client, CROSSREF, params, {"User-Agent": USER_AGENT})
        if status != 200 or not data:
            for d in chunk:
                by_doi[d.lower()] = {"state": "error"}
            return
        for it in (data.get("message") or {}).get("items", []):
            by_doi[str(it.get("DOI", "")).lower()] = {"state": "ok", "title": _safe((it.get("title") or [""])[0]), "ret": retraction_status(it)}
        for d in chunk:  # a DOI the filter did not return is not registered with Crossref
            by_doi.setdefault(d.lower(), {"state": "missing"})

    async def single_job(d: str) -> None:
        st, c = await lk.crossref_work(d)
        by_doi[d.lower()] = {"state": "ok", "title": c.title, "ret": c.retraction} if st == "ok" and c else {"state": st}

    jobs = [asyncio.ensure_future(chunk_job(c)) for c in chunks] + [asyncio.ensure_future(single_job(d)) for d in odd]
    if jobs:
        _, pending = await asyncio.wait(jobs, timeout=deadline)
        for p in pending:
            p.cancel()
    out = []
    for d in dois:
        r = by_doi.get(d.lower())
        if r is None:
            out.append({"doi": d, "status": "lookup_failed", "title": None, "notices": [], "note": "Lookup did not finish. Try again with fewer DOIs."})
        elif r["state"] == "ok":
            out.append({"doi": d, "status": r["ret"]["status"], "title": r["title"] or None, "notices": r["ret"]["notices"], "note": ""})
        elif r["state"] == "missing":
            out.append({"doi": d, "status": "not_in_crossref", "title": None, "notices": [],
                        "note": "Not registered with Crossref. It may belong to another agency such as DataCite, or be mistyped."})
        else:
            out.append({"doi": d, "status": "lookup_failed", "title": None, "notices": [], "note": "Crossref could not be reached for this DOI."})
    return out


# -------------------------------------------------------- doi_to_bibtex


async def bibtex_for_dois(client, dois: list[str], deadline: float = DEADLINE_SECONDS) -> list[dict]:
    """BibTeX through Crossref content negotiation, as the site's bib builder does."""
    sem = asyncio.Semaphore(CROSSREF_CONCURRENCY)

    async def one(d: str) -> dict:
        async with sem:
            try:
                r = await client.get(
                    f"{CROSSREF}/{quote(d, safe='')}/transform/application/x-bibtex",
                    headers={"User-Agent": USER_AGENT, "Accept": "application/x-bibtex"},
                    follow_redirects=False,
                )
            except Exception:
                return {"doi": d, "status": "error", "bibtex": None}
        if r.status_code == 404:
            return {"doi": d, "status": "not_found", "bibtex": None}
        if r.status_code != 200:
            return {"doi": d, "status": "error", "bibtex": None}
        return {"doi": d, "status": "ok", "bibtex": _CONTROL_RE.sub(" ", r.text).strip()[:4000]}

    tasks = [asyncio.ensure_future(one(d)) for d in dois]
    done, pending = await asyncio.wait(tasks, timeout=deadline)
    for p in pending:
        p.cancel()
    return [
        t.result() if t in done and not t.cancelled() and t.exception() is None
        else {"doi": d, "status": "error", "bibtex": None}
        for d, t in zip(dois, tasks)
    ]


def clean_doi_list(raw: list[str] | None, limit: int) -> tuple[list[str], list[str]]:
    """Normalise, dedupe and cap a DOI list. Returns (dois, notes). Raises InputError if none usable."""
    notes: list[str] = []
    seen: set[str] = set()
    out: list[str] = []
    bad = 0
    for v in raw or []:
        d = normalize_doi(str(v))
        if not d:
            bad += 1
        elif d.lower() not in seen:
            seen.add(d.lower())
            out.append(d)
    if bad:
        notes.append(f"{bad} item(s) did not look like a DOI and were skipped.")
    if not out:
        raise InputError("No valid DOIs found. A DOI looks like 10.1038/nature14539.")
    if len(out) > limit:
        notes.append(f"Only the first {limit} of {len(out)} DOIs were processed.")
        out = out[:limit]
    return out, notes
