"""Deep citation audit for Paper Review (Layer 2 deepening).

Pure logic + injected-IO helpers so the bulk of the module is unit-testable
without network or Anthropic access. The async fetch/assess wrappers and the
run_citation_audit orchestrator are the only parts that touch I/O.

Flow:
  1. extract_claim_citations  — sentence <-> citation pairs from the body.
  2. rank_claims              — order by how load-bearing the claim is.
  3. fetch_source_abstract    — OpenAlex -> Semantic Scholar -> CrossRef.
  4. assess_claims            — batched LLM verdict per claim/abstract pair.
  5. run_citation_audit       — wire it together, return an audit dict.
"""
from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field
from typing import Optional

import json as _json

from .papercheck import _anthropic_message, _parse_json_findings

MAX_AUDIT_PAIRS = 40
ASSESS_BATCH_SIZE = 8
VERDICTS = (
    "Supported",
    "Partially supported",
    "Not supported by abstract",
    "Contradicted",
    "Source unavailable",
)

# Sentence splitter: break after . ! ? when followed by a capital / paren / bracket.
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\[])")
# Numeric citation markers: [12], [3, 4], [5-7], [5–7].
_NUM_CITE = re.compile(r"\[(\d{1,3}(?:\s*[,\-–]\s*\d{1,3})*)\]")
# An author token: optional lowercase nobiliary particles ("van der", "de")
# followed by a capitalized surname.
_AUTHOR = r"(?:[a-z]+\s+){0,2}[A-Z][A-Za-z\-]+"
# Author-year markers: (Smith et al., 2021), (van der Berg et al., 2021),
# (de Bruijn and Smith, 2018), (Smith, 2019a).
_AY_CITE = re.compile(
    r"\((" + _AUTHOR + r"(?:\s+et al\.?)?"
    r"(?:\s+(?:&|and)\s+" + _AUTHOR + r")?,?\s+\d{4}[a-z]?)\)"
)


@dataclass
class ClaimCitation:
    """One sentence and the citation marker(s) attached to it."""
    claim_sentence: str
    ref_keys: list[str]
    location: str = ""
    salience: float = 0.0

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def _expand_numeric(inner: str) -> list[str]:
    """Expand '3, 4' -> ['3','4'] and '5-7' -> ['5','6','7']."""
    keys: list[str] = []
    for part in re.split(r"\s*,\s*", inner.strip()):
        m = re.match(r"(\d{1,3})\s*[\-–]\s*(\d{1,3})$", part)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            if lo <= hi and hi - lo < 50:
                keys.extend(str(n) for n in range(lo, hi + 1))
        elif part.isdigit():
            keys.append(part)
    return keys


def _split_sentences(text: Optional[str]) -> list[str]:
    parts = _SENT_SPLIT.split(text or "")
    return [p.strip() for p in parts if p.strip()]


def extract_claim_citations(structure) -> list[ClaimCitation]:
    """Find every sentence in the body that carries a citation marker.

    Supports numeric ([12], [3,4], [5-7]) and author-year ((Smith, 2021))
    styles — the two dominant academic conventions. Un-parseable markers are
    simply not matched (never raises).
    """
    claims: list[ClaimCitation] = []
    for sent in _split_sentences(getattr(structure, "body", "") or ""):
        keys: list[str] = []
        for m in _NUM_CITE.finditer(sent):
            keys.extend(_expand_numeric(m.group(1)))
        for m in _AY_CITE.finditer(sent):
            keys.append(m.group(1).strip())
        if keys:
            # De-dup while preserving order.
            seen = set()
            uniq = [k for k in keys if not (k in seen or seen.add(k))]
            claims.append(ClaimCitation(claim_sentence=sent, ref_keys=uniq))
    return claims


_CAUSAL = re.compile(
    r"\b(show|shows|showed|demonstrate|demonstrates|demonstrated|prove|proves|"
    r"cause|causes|caused|improve|improves|improved|outperform|outperforms|"
    r"outperformed|increase|increases|increased|reduce|reduces|reduced|"
    r"significant|significantly|correlate|correlates|correlated|lead|leads)\b",
    re.IGNORECASE,
)
_SUPERLATIVE = re.compile(
    r"\b(first|best|state[- ]of[- ]the[- ]art|novel|unprecedented|only|"
    r"highest|lowest|largest|strongest)\b",
    re.IGNORECASE,
)
_HAS_NUMBER = re.compile(r"\d")


def _salience(sentence: str) -> float:
    """Higher = more load-bearing (the kind of claim a reviewer challenges)."""
    s = 0.0
    if _CAUSAL.search(sentence):
        s += 2.0
    if _HAS_NUMBER.search(sentence):
        s += 1.0
    if _SUPERLATIVE.search(sentence):
        s += 1.0
    return s


def rank_claims(claims: list[ClaimCitation]) -> list[ClaimCitation]:
    """Return claims ordered by salience (desc), stable for ties.

    Mutates each claim's `salience` field as a side effect so the report can
    show why a claim was prioritised.
    """
    for c in claims:
        c.salience = _salience(c.claim_sentence)
    return sorted(claims, key=lambda c: c.salience, reverse=True)


@dataclass
class SourceAbstract:
    """An abstract fetched (or not) for one cited reference."""
    ref_key: str
    text: Optional[str]
    status: str               # "ok" | "unavailable"
    source: str = ""          # "openalex" | "semantic_scholar" | "crossref"
    title: str = ""

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def reconstruct_abstract(inverted_index: Optional[dict]) -> Optional[str]:
    """Rebuild plain text from an OpenAlex abstract_inverted_index."""
    if not inverted_index:
        return None
    positions: list[tuple[int, str]] = []
    for word, idxs in inverted_index.items():
        for i in idxs:
            positions.append((i, word))
    if not positions:
        return None
    positions.sort(key=lambda p: p[0])
    return " ".join(word for _, word in positions)


_MAILTO = "ben@purplelink.llc"
_UA = "purplelink-paper-review/1.0 (mailto:ben@purplelink.llc)"


async def _openalex(client, ref) -> Optional[SourceAbstract]:
    try:
        if getattr(ref, "doi", ""):
            resp = await client.get(
                f"https://api.openalex.org/works/https://doi.org/{ref.doi}",
                params={"mailto": _MAILTO}, timeout=10.0,
            )
        elif getattr(ref, "title", ""):
            resp = await client.get(
                "https://api.openalex.org/works",
                params={"search": ref.title[:200], "per-page": "1", "mailto": _MAILTO},
                timeout=10.0,
            )
        else:
            return None
        if resp.status_code != 200:
            return None
        data = resp.json()
        work = data
        if "results" in data:
            results = data.get("results") or []
            if not results:
                return None
            work = results[0]
        text = reconstruct_abstract(work.get("abstract_inverted_index"))
        if not text:
            return None
        return SourceAbstract(
            ref_key="", text=text, status="ok", source="openalex",
            title=work.get("title") or "",
        )
    except Exception:
        return None


async def _semantic_scholar(client, ref) -> Optional[SourceAbstract]:
    try:
        if getattr(ref, "doi", ""):
            ident = f"DOI:{ref.doi}"
        elif getattr(ref, "arxiv_id", ""):
            ident = f"arXiv:{ref.arxiv_id}"
        else:
            return None
        resp = await client.get(
            f"https://api.semanticscholar.org/graph/v1/paper/{ident}",
            params={"fields": "title,abstract,tldr"}, timeout=10.0,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        text = data.get("abstract")
        tldr = (data.get("tldr") or {}).get("text") if data.get("tldr") else None
        body = text or tldr
        if not body:
            return None
        return SourceAbstract(
            ref_key="", text=body, status="ok", source="semantic_scholar",
            title=data.get("title") or "",
        )
    except Exception:
        return None


async def _crossref_abstract(client, ref) -> Optional[SourceAbstract]:
    try:
        if not getattr(ref, "doi", ""):
            return None
        resp = await client.get(
            f"https://api.crossref.org/works/{ref.doi}",
            params={"mailto": _MAILTO}, headers={"User-Agent": _UA}, timeout=10.0,
        )
        if resp.status_code != 200:
            return None
        msg = (resp.json() or {}).get("message") or {}
        raw = msg.get("abstract")
        if not raw:
            return None
        text = re.sub(r"<[^>]+>", " ", raw)        # strip JATS-XML tags
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return None
        return SourceAbstract(
            ref_key="", text=text, status="ok", source="crossref",
            title=(msg.get("title") or [""])[0],
        )
    except Exception:
        return None


async def fetch_source_abstract(client, ref_key: str, ref) -> SourceAbstract:
    """Try OpenAlex -> Semantic Scholar -> CrossRef. Never raises.

    Returns a SourceAbstract with status 'unavailable' if no source yields an
    abstract — that is a first-class, honest outcome, never guessed.
    """
    for fetcher in (_openalex, _semantic_scholar, _crossref_abstract):
        got = await fetcher(client, ref)
        if got is not None:
            got.ref_key = ref_key
            return got
    return SourceAbstract(ref_key=ref_key, text=None, status="unavailable")


def _resolve_ref(ref_key: str, references: list) -> Optional["PaperReference"]:
    """Map a citation marker to a PaperReference.

    Numeric keys index 1-based into the reference list. Author-year keys match
    the first author surname + year against each reference's raw text.
    Returns None when no confident match exists.
    """
    key = ref_key.strip()
    if key.isdigit():
        i = int(key) - 1
        if 0 <= i < len(references):
            return references[i]
        return None
    # Author-year: pull surname + 4-digit year, look for both in raw. Skip
    # lowercase nobiliary particles ("van der", "de") so the captured surname
    # matches the keys extract_claim_citations produces (e.g. "van der Berg").
    surname = re.match(r"(?:[a-z]+\s+){0,2}([A-Z][A-Za-z\-]+)", key)
    year = re.search(r"\d{4}", key)
    if not surname or not year:
        return None
    sn, yr = surname.group(1).lower(), year.group(0)
    for ref in references:
        raw = (getattr(ref, "raw", "") or "").lower()
        if sn in raw and yr in raw:
            return ref
    return None


@dataclass
class AuditFinding:
    claim_sentence: str
    ref_key: str
    verdict: str
    source_quote: Optional[str] = None
    rationale: str = ""
    location: str = ""

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


_ASSESS_SYSTEM = (
    "You audit academic citations. For each numbered item you are given a "
    "CLAIM from a manuscript and the ABSTRACT of the source it cites. Decide "
    "whether the abstract supports the claim. Reply ONLY with a JSON array; "
    "one object per item with keys: index (int), verdict (one of "
    "\"Supported\", \"Partially supported\", \"Not supported by abstract\", "
    "\"Contradicted\"), source_quote (the abstract sentence that most bears "
    "on the claim, or null), rationale (one short sentence). Judge ONLY "
    "against the abstract text provided; if the abstract is silent, that is "
    "\"Not supported by abstract\", not a failure of the paper. Use hedged, "
    "non-accusatory language in the rationale."
)


def _clamp_verdict(v: str) -> str:
    v = (v or "").strip()
    for canonical in VERDICTS:
        if v.lower() == canonical.lower():
            return canonical
    return "Not supported by abstract"


def _build_assess_prompt(batch: list) -> str:
    lines = []
    for i, (claim, src) in enumerate(batch):
        lines.append(
            f"[{i}] CLAIM: {claim.claim_sentence}\n"
            f"    ABSTRACT: {(src.text or '')[:2000]}"
        )
    return "\n\n".join(lines)


async def assess_claims(client, pairs: list) -> list:
    """Assess (ClaimCitation, SourceAbstract) pairs into AuditFindings.

    Unavailable sources short-circuit to 'Source unavailable' with no LLM
    call. Available pairs are batched (ASSESS_BATCH_SIZE per call) to bound
    cost. Never raises; on an LLM/parse error the affected pairs fall back to
    'Source unavailable' so the run always completes.
    """
    findings: list[AuditFinding] = []
    assessable: list = []
    for claim, src in pairs:
        if src.status != "ok" or not src.text:
            findings.append(AuditFinding(
                claim_sentence=claim.claim_sentence,
                ref_key=src.ref_key or (claim.ref_keys[0] if claim.ref_keys else ""),
                verdict="Source unavailable",
                source_quote=None,
                rationale="No abstract could be retrieved for this source.",
                location=claim.location,
            ))
        else:
            assessable.append((claim, src))

    for start in range(0, len(assessable), ASSESS_BATCH_SIZE):
        batch = assessable[start:start + ASSESS_BATCH_SIZE]
        try:
            raw = await _anthropic_message(
                client,
                system=_ASSESS_SYSTEM,
                user_content=[{"type": "text", "text": _build_assess_prompt(batch)}],
                max_tokens=1500,
            )
            parsed = _parse_json_findings(raw)
            by_index = {int(o.get("index", -1)): o for o in parsed if isinstance(o, dict)}
        except Exception:
            by_index = {}
        for i, (claim, src) in enumerate(batch):
            o = by_index.get(i)
            if o is None:
                findings.append(AuditFinding(
                    claim_sentence=claim.claim_sentence, ref_key=src.ref_key,
                    verdict="Source unavailable",
                    rationale="Assessment could not be completed for this item.",
                    location=claim.location,
                ))
                continue
            findings.append(AuditFinding(
                claim_sentence=claim.claim_sentence,
                ref_key=src.ref_key,
                verdict=_clamp_verdict(o.get("verdict")),
                source_quote=o.get("source_quote") or None,
                rationale=(o.get("rationale") or "").strip(),
                location=claim.location,
            ))
    return findings
