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
