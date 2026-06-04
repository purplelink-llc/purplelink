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
