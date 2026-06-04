# Deep Citation Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deepen Paper Review's Layer 2 from a citation existence-check into a claim-support audit that fetches each cited source's abstract and assesses whether it actually supports the claim it's attached to.

**Architecture:** A new pure-logic-plus-async module `backend/latextools/citation_audit.py` (mirroring `pdf_structure.py`'s pure/injected-IO style) extracts sentence↔citation pairs, ranks them by how load-bearing they are, fetches abstracts (OpenAlex → Semantic Scholar → CrossRef), and batches an LLM assessment. The orchestrator `run_review_pipeline` runs the audit concurrently with L1/L2 and attaches it additively as `l2["audit"]`, so Layer-3 personas, the Layer-4 report, and the annotated PDF all consume it without contract changes.

**Tech Stack:** Python 3.11, `httpx` (async), Anthropic Messages API (reused via `papercheck._anthropic_message`), `pytest`. Frontend is static HTML/CSS (strict CSP, no inline styles).

---

## File Structure

- **Create** `backend/latextools/citation_audit.py` — all new audit logic: dataclasses, claim extraction, ranking, abstract fetch, assessment, orchestrator.
- **Create** `backend/tests/test_citation_audit.py` — unit tests for every pure function + injected-IO async paths.
- **Modify** `backend/latextools/papercheck.py` — (a) run the audit concurrently and attach `l2["audit"]`; (b) add `## Citation Support Audit` to the L4 report spec; (c) feed audit into the Literature persona content + prompt line.
- **Modify** `backend/latextools/pdf_annotate.py` — annotate non-Supported / Contradicted audit findings at the claim's page.
- **Modify** `site/tools/paper-review/index.html` — Layer 2 copy, a new FAQ entry, JSON-LD `featureList` + `FAQPage`, sample-report excerpt.

Constants (defined once in `citation_audit.py`):
- `MAX_AUDIT_PAIRS = 40`
- `ASSESS_BATCH_SIZE = 8`
- `VERDICTS = ("Supported", "Partially supported", "Not supported by abstract", "Contradicted", "Source unavailable")`

---

### Task 1: Module skeleton + data model + claim extraction

**Files:**
- Create: `backend/latextools/citation_audit.py`
- Test: `backend/tests/test_citation_audit.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_citation_audit.py
import sys
from pathlib import Path
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from latextools import citation_audit as ca
from latextools.papercheck import PaperStructure, PaperReference


def test_extract_numeric_claim_citations():
    body = (
        "Transformers improve translation quality [12]. "
        "The sky is blue. "
        "Our method outperforms all baselines [3, 4]."
    )
    struct = PaperStructure(body=body)
    claims = ca.extract_claim_citations(struct)
    # Two sentences carry citations; the middle one has none.
    assert len(claims) == 2
    first = claims[0]
    assert "Transformers improve" in first.claim_sentence
    assert first.ref_keys == ["12"]
    second = claims[1]
    assert second.ref_keys == ["3", "4"]


def test_extract_author_year_and_numeric_range():
    body = (
        "Prior work established this effect (Smith et al., 2021). "
        "Replications confirmed it [5-7]."
    )
    struct = PaperStructure(body=body)
    claims = ca.extract_claim_citations(struct)
    assert claims[0].ref_keys == ["Smith et al., 2021"]
    assert claims[1].ref_keys == ["5", "6", "7"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest backend/tests/test_citation_audit.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'latextools.citation_audit'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/latextools/citation_audit.py
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
# Author-year markers: (Smith et al., 2021), (Smith and Jones, 2020), (Smith, 2019a).
_AY_CITE = re.compile(
    r"\(([A-Z][A-Za-z\-]+(?:\s+et al\.?)?"
    r"(?:\s+(?:&|and)\s+[A-Z][A-Za-z\-]+)?,?\s+\d{4}[a-z]?)\)"
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


def _split_sentences(text: str) -> list[str]:
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest backend/tests/test_citation_audit.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/latextools/citation_audit.py backend/tests/test_citation_audit.py
git commit -m "feat(citation-audit): module skeleton + claim-citation extraction"
```

---

### Task 2: Rank claims by salience

**Files:**
- Modify: `backend/latextools/citation_audit.py`
- Test: `backend/tests/test_citation_audit.py`

- [ ] **Step 1: Write the failing test**

```python
def test_rank_claims_prioritizes_load_bearing():
    weak = ca.ClaimCitation("Related work also touches this area [1].", ["1"])
    strong = ca.ClaimCitation(
        "Our method significantly outperforms all baselines by 12% [2].", ["2"]
    )
    ranked = ca.rank_claims([weak, strong])
    assert ranked[0] is strong          # causal verb + number rank first
    assert ranked[1] is weak
    assert ranked[0].salience > ranked[1].salience


def test_rank_claims_is_stable_for_ties():
    a = ca.ClaimCitation("A plain mention [1].", ["1"])
    b = ca.ClaimCitation("Another plain mention [2].", ["2"])
    ranked = ca.rank_claims([a, b])
    assert ranked == [a, b]             # equal salience keeps input order
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest backend/tests/test_citation_audit.py::test_rank_claims_prioritizes_load_bearing -q`
Expected: FAIL with `AttributeError: module 'latextools.citation_audit' has no attribute 'rank_claims'`

- [ ] **Step 3: Write minimal implementation**

Append to `citation_audit.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest backend/tests/test_citation_audit.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/latextools/citation_audit.py backend/tests/test_citation_audit.py
git commit -m "feat(citation-audit): salience ranking for load-bearing claims"
```

---

### Task 3: Abstract data model + OpenAlex inverted-index reconstruction + ref resolution

**Files:**
- Modify: `backend/latextools/citation_audit.py`
- Test: `backend/tests/test_citation_audit.py`

- [ ] **Step 1: Write the failing test**

```python
from latextools.papercheck import PaperReference


def test_reconstruct_abstract_from_inverted_index():
    inv = {"The": [0], "cat": [1], "sat": [2]}
    assert ca.reconstruct_abstract(inv) == "The cat sat"
    assert ca.reconstruct_abstract(None) is None
    assert ca.reconstruct_abstract({}) is None


def test_resolve_ref_numeric_and_author_year():
    refs = [
        PaperReference(raw="[1] Smith J. 2021. Deep nets. doi:10.1/x", title="Deep nets",
                       doi="10.1/x", year="2021", authors="Smith J."),
        PaperReference(raw="[2] Jones A. 2019. Shallow nets.", title="Shallow nets",
                       year="2019", authors="Jones A."),
    ]
    # Numeric key indexes 1-based into the reference list.
    assert ca._resolve_ref("2", refs) is refs[1]
    # Author-year key matches on surname + year in the raw text.
    assert ca._resolve_ref("Smith, 2021", refs) is refs[0]
    # Unknown key -> None.
    assert ca._resolve_ref("Nobody, 1900", refs) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest backend/tests/test_citation_audit.py::test_reconstruct_abstract_from_inverted_index -q`
Expected: FAIL with `AttributeError: ... has no attribute 'reconstruct_abstract'`

- [ ] **Step 3: Write minimal implementation**

Append to `citation_audit.py`:

```python
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


def _resolve_ref(ref_key: str, references: list) -> Optional["object"]:
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
    # Author-year: pull surname + 4-digit year, look for both in raw.
    surname = re.match(r"([A-Z][A-Za-z\-]+)", key)
    year = re.search(r"\d{4}", key)
    if not surname or not year:
        return None
    sn, yr = surname.group(1).lower(), year.group(0)
    for ref in references:
        raw = (getattr(ref, "raw", "") or "").lower()
        if sn in raw and yr in raw:
            return ref
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest backend/tests/test_citation_audit.py -q`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/latextools/citation_audit.py backend/tests/test_citation_audit.py
git commit -m "feat(citation-audit): SourceAbstract, OpenAlex reconstruction, ref resolution"
```

---

### Task 4: Async abstract fetch (OpenAlex → Semantic Scholar → CrossRef)

**Files:**
- Modify: `backend/latextools/citation_audit.py`
- Test: `backend/tests/test_citation_audit.py`

- [ ] **Step 1: Write the failing test**

```python
import asyncio


class _FakeResp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class _FakeClient:
    """Returns queued responses keyed by URL substring."""
    def __init__(self, routes):
        self.routes = routes          # list of (url_substr, _FakeResp)

    async def get(self, url, **kwargs):
        for sub, resp in self.routes:
            if sub in url:
                return resp
        return _FakeResp(404, {})


def test_fetch_source_abstract_openalex_hit():
    ref = PaperReference(raw="x", title="Deep nets", doi="10.1/x")
    client = _FakeClient([
        ("openalex.org", _FakeResp(200, {
            "abstract_inverted_index": {"Deep": [0], "nets": [1]},
            "title": "Deep nets",
        })),
    ])
    out = asyncio.get_event_loop().run_until_complete(
        ca.fetch_source_abstract(client, "1", ref)
    )
    assert out.status == "ok"
    assert out.source == "openalex"
    assert out.text == "Deep nets"


def test_fetch_source_abstract_all_miss_is_unavailable():
    ref = PaperReference(raw="x", title="Ghost paper")
    client = _FakeClient([])        # every route 404 / empty
    out = asyncio.get_event_loop().run_until_complete(
        ca.fetch_source_abstract(client, "1", ref)
    )
    assert out.status == "unavailable"
    assert out.text is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest backend/tests/test_citation_audit.py::test_fetch_source_abstract_openalex_hit -q`
Expected: FAIL with `AttributeError: ... has no attribute 'fetch_source_abstract'`

- [ ] **Step 3: Write minimal implementation**

Append to `citation_audit.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest backend/tests/test_citation_audit.py -q`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/latextools/citation_audit.py backend/tests/test_citation_audit.py
git commit -m "feat(citation-audit): async abstract fetch with 3-source fallback"
```

---

### Task 5: Batched LLM assessment + verdict assembly

**Files:**
- Modify: `backend/latextools/citation_audit.py`
- Test: `backend/tests/test_citation_audit.py`

- [ ] **Step 1: Write the failing test**

```python
def test_assess_claims_short_circuits_unavailable(monkeypatch):
    # When the abstract is unavailable, no LLM call happens and the verdict
    # is "Source unavailable".
    async def _boom(*a, **k):
        raise AssertionError("LLM must not be called for unavailable sources")
    monkeypatch.setattr(ca, "_anthropic_message", _boom)

    claim = ca.ClaimCitation("A claim [1].", ["1"])
    src = ca.SourceAbstract(ref_key="1", text=None, status="unavailable")
    findings = asyncio.get_event_loop().run_until_complete(
        ca.assess_claims(object(), [(claim, src)])
    )
    assert len(findings) == 1
    assert findings[0].verdict == "Source unavailable"
    assert findings[0].source_quote is None


def test_assess_claims_parses_llm_verdicts(monkeypatch):
    async def _fake_llm(client, system, user_content, max_tokens, **k):
        return (
            '[{"index": 0, "verdict": "Supported", '
            '"source_quote": "We show X improves Y.", '
            '"rationale": "Abstract states the same result."}]'
        )
    monkeypatch.setattr(ca, "_anthropic_message", _fake_llm)

    claim = ca.ClaimCitation("X improves Y [1].", ["1"])
    src = ca.SourceAbstract(ref_key="1", text="We show X improves Y.", status="ok")
    findings = asyncio.get_event_loop().run_until_complete(
        ca.assess_claims(object(), [(claim, src)])
    )
    assert findings[0].verdict == "Supported"
    assert findings[0].source_quote == "We show X improves Y."


def test_assess_claims_clamps_unknown_verdict(monkeypatch):
    async def _fake_llm(client, system, user_content, max_tokens, **k):
        return '[{"index": 0, "verdict": "Totally Made Up", "rationale": "x"}]'
    monkeypatch.setattr(ca, "_anthropic_message", _fake_llm)
    claim = ca.ClaimCitation("X [1].", ["1"])
    src = ca.SourceAbstract(ref_key="1", text="abstract", status="ok")
    findings = asyncio.get_event_loop().run_until_complete(
        ca.assess_claims(object(), [(claim, src)])
    )
    # Unknown verdicts clamp to the conservative "Not supported by abstract".
    assert findings[0].verdict == "Not supported by abstract"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest backend/tests/test_citation_audit.py::test_assess_claims_short_circuits_unavailable -q`
Expected: FAIL with `AttributeError: ... has no attribute 'assess_claims'` (and `_anthropic_message` import error inside the module is fixed in Step 3)

- [ ] **Step 3: Write minimal implementation**

Add this import near the top of `citation_audit.py` (below the existing imports):

```python
import json as _json

from .papercheck import _anthropic_message, _parse_json_findings
```

Append to `citation_audit.py`:

```python
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
```

Note: `_parse_json_findings` already tolerates fenced/`json`-prefixed output and returns a `list[dict]`; reusing it keeps parsing behaviour consistent with the rest of `papercheck`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest backend/tests/test_citation_audit.py -q`
Expected: PASS (11 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/latextools/citation_audit.py backend/tests/test_citation_audit.py
git commit -m "feat(citation-audit): batched LLM assessment + verdict assembly"
```

---

### Task 6: Orchestrator `run_citation_audit`

**Files:**
- Modify: `backend/latextools/citation_audit.py`
- Test: `backend/tests/test_citation_audit.py`

- [ ] **Step 1: Write the failing test**

```python
def test_run_citation_audit_end_to_end(monkeypatch):
    refs = [
        PaperReference(raw="[1] Smith 2021 Deep nets", title="Deep nets", doi="10.1/x"),
        PaperReference(raw="[2] Jones 2019 Shallow nets", title="Shallow nets"),
    ]
    body = (
        "Our method significantly outperforms baselines [1]. "
        "Related work mentions this [2]."
    )
    struct = PaperStructure(body=body, references=refs)

    async def _fake_fetch(client, ref_key, ref):
        if ref_key == "1":
            return ca.SourceAbstract(ref_key="1", text="We show big gains.", status="ok")
        return ca.SourceAbstract(ref_key="2", text=None, status="unavailable")
    monkeypatch.setattr(ca, "fetch_source_abstract", _fake_fetch)

    async def _fake_assess(client, pairs):
        out = []
        for claim, src in pairs:
            if src.status == "ok":
                out.append(ca.AuditFinding(claim.claim_sentence, src.ref_key,
                                           "Supported", "We show big gains.", "ok"))
            else:
                out.append(ca.AuditFinding(claim.claim_sentence, src.ref_key,
                                           "Source unavailable"))
        return out
    monkeypatch.setattr(ca, "assess_claims", _fake_assess)

    audit = asyncio.get_event_loop().run_until_complete(
        ca.run_citation_audit(object(), struct)
    )
    assert audit["audited"] == 2
    assert audit["skipped"] == 0
    assert audit["by_verdict"]["Supported"] == 1
    assert audit["by_verdict"]["Source unavailable"] == 1
    # The load-bearing claim is audited first.
    assert "outperforms" in audit["findings"][0]["claim_sentence"]


def test_run_citation_audit_caps_and_reports_skipped(monkeypatch):
    refs = [PaperReference(raw=f"[{i}] ref", title=f"t{i}") for i in range(1, 60)]
    body = " ".join(f"Claim number {i} shows an effect [{i}]." for i in range(1, 60))
    struct = PaperStructure(body=body, references=refs)

    async def _fake_fetch(client, ref_key, ref):
        return ca.SourceAbstract(ref_key=ref_key, text="abstract", status="ok")
    async def _fake_assess(client, pairs):
        return [ca.AuditFinding(c.claim_sentence, s.ref_key, "Supported") for c, s in pairs]
    monkeypatch.setattr(ca, "fetch_source_abstract", _fake_fetch)
    monkeypatch.setattr(ca, "assess_claims", _fake_assess)

    audit = asyncio.get_event_loop().run_until_complete(
        ca.run_citation_audit(object(), struct)
    )
    assert audit["audited"] == ca.MAX_AUDIT_PAIRS
    assert audit["skipped"] == 59 - ca.MAX_AUDIT_PAIRS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest backend/tests/test_citation_audit.py::test_run_citation_audit_end_to_end -q`
Expected: FAIL with `AttributeError: ... has no attribute 'run_citation_audit'`

- [ ] **Step 3: Write minimal implementation**

Add near the top imports of `citation_audit.py`:

```python
import asyncio
import logging

logger = logging.getLogger(__name__)
```

Append to `citation_audit.py`:

```python
def _empty_audit() -> dict:
    return {"audited": 0, "skipped": 0,
            "by_verdict": {v: 0 for v in VERDICTS}, "findings": []}


async def run_citation_audit(client, structure) -> dict:
    """End-to-end deep citation audit. Returns a dict shaped for l2['audit'].

    {audited, skipped, by_verdict: {verdict: count}, findings: [AuditFinding]}.
    Never raises — on any failure returns an empty audit so the surrounding
    review pipeline is unaffected.
    """
    try:
        claims = extract_claim_citations(structure)
        if not claims:
            return _empty_audit()
        ranked = rank_claims(claims)
        selected = ranked[:MAX_AUDIT_PAIRS]
        skipped = max(0, len(ranked) - len(selected))

        references = getattr(structure, "references", []) or []
        pairs: list = []
        for claim in selected:
            key = claim.ref_keys[0] if claim.ref_keys else ""
            ref = _resolve_ref(key, references) if key else None
            if ref is None:
                pairs.append((claim, SourceAbstract(ref_key=key, text=None,
                                                     status="unavailable")))
            else:
                pairs.append((claim, ref))

        # Fetch abstracts concurrently for the resolved refs.
        async def _maybe_fetch(claim, ref_or_src):
            if isinstance(ref_or_src, SourceAbstract):
                return (claim, ref_or_src)
            key = claim.ref_keys[0] if claim.ref_keys else ""
            src = await fetch_source_abstract(client, key, ref_or_src)
            return (claim, src)

        fetched = await asyncio.gather(*[_maybe_fetch(c, r) for c, r in pairs])

        findings = await assess_claims(client, list(fetched))

        by_verdict = {v: 0 for v in VERDICTS}
        for f in findings:
            by_verdict[f.verdict] = by_verdict.get(f.verdict, 0) + 1
        return {
            "audited": len(findings),
            "skipped": skipped,
            "by_verdict": by_verdict,
            "findings": [f.to_dict() for f in findings],
        }
    except Exception:
        logger.exception("run_citation_audit failed")
        return _empty_audit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest backend/tests/test_citation_audit.py -q`
Expected: PASS (13 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/latextools/citation_audit.py backend/tests/test_citation_audit.py
git commit -m "feat(citation-audit): run_citation_audit orchestrator with cap + tally"
```

---

### Task 7: Wire the audit into `run_review_pipeline`

**Files:**
- Modify: `backend/latextools/papercheck.py:1581-1586` (the L1/L2 concurrent block)
- Test: `backend/tests/test_citation_audit.py`

- [ ] **Step 1: Write the failing test**

```python
def test_layer2_audit_key_is_attached(monkeypatch):
    # Prove the orchestrator attaches audit onto the l2 dict additively.
    from latextools import papercheck

    base_l2 = {"checked": 2, "verified": 2, "issues": []}
    audit = {"audited": 1, "skipped": 0,
             "by_verdict": {v: 0 for v in ca.VERDICTS}, "findings": []}
    merged = papercheck.attach_audit(dict(base_l2), audit)
    assert merged["checked"] == 2          # existing keys preserved
    assert merged["audit"]["audited"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest backend/tests/test_citation_audit.py::test_layer2_audit_key_is_attached -q`
Expected: FAIL with `AttributeError: module 'latextools.papercheck' has no attribute 'attach_audit'`

- [ ] **Step 3: Write minimal implementation**

Add this small helper to `papercheck.py` just after `run_layer_2_citations` (around line 986):

```python
def attach_audit(l2: dict, audit: dict) -> dict:
    """Additively attach the deep-citation-audit result onto the L2 dict.

    Kept as a named helper so the wiring is unit-testable without running the
    full network pipeline.
    """
    l2 = dict(l2)
    l2["audit"] = audit
    return l2
```

Then modify the concurrent block in `run_review_pipeline` (currently lines 1582-1586). Replace:

```python
        l1_task = asyncio.create_task(run_layer_1_vision(client, pdf_bytes, domain))
        l2_task = asyncio.create_task(run_layer_2_citations(client, structure.references))
        l1, l2 = await asyncio.gather(l1_task, l2_task)
        progress.layer_status["l1"] = l1.get("status", "ok")
        progress.layer_status["l2"] = "ok"
```

with:

```python
        from latextools import citation_audit
        l1_task = asyncio.create_task(run_layer_1_vision(client, pdf_bytes, domain))
        l2_task = asyncio.create_task(run_layer_2_citations(client, structure.references))
        audit_task = asyncio.create_task(
            citation_audit.run_citation_audit(client, structure)
        )
        l1, l2, audit = await asyncio.gather(l1_task, l2_task, audit_task)
        l2 = attach_audit(l2, audit)
        progress.layer_status["l1"] = l1.get("status", "ok")
        progress.layer_status["l2"] = "ok"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest backend/tests/test_citation_audit.py -q`
Expected: PASS (14 passed)

- [ ] **Step 5: Run the full backend suite to confirm no regressions**

Run: `python3 -m pytest backend -q`
Expected: PASS (all prior tests still green; L2 contract is additive)

- [ ] **Step 6: Commit**

```bash
git add backend/latextools/papercheck.py backend/tests/test_citation_audit.py
git commit -m "feat(citation-audit): run audit concurrently and attach to l2"
```

---

### Task 8: Add the Citation Support Audit section to the L4 report

**Files:**
- Modify: `backend/latextools/papercheck.py` (the `_L4_SYSTEM_CORE` string, after the `## Reference Verification Summary` section, around line 1343)
- Test: `backend/tests/test_citation_audit.py`

- [ ] **Step 1: Write the failing test**

```python
def test_l4_prompt_includes_citation_support_audit_section():
    from latextools import papercheck
    assert "## Citation Support Audit" in papercheck._L4_SYSTEM_CORE
    # The instruction names the cap/unavailable footnote behaviour.
    assert "not audited" in papercheck._L4_SYSTEM_CORE.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest backend/tests/test_citation_audit.py::test_l4_prompt_includes_citation_support_audit_section -q`
Expected: FAIL with `AssertionError`

- [ ] **Step 3: Write minimal implementation**

In `papercheck.py`, insert the following section into `_L4_SYSTEM_CORE` immediately after the `## Reference Verification Summary` block and before `## Panel Transcript`:

```python
## Citation Support Audit
Render the deep citation audit supplied in layer_2_citations.audit. This audit
fetched the abstract of each cited source and judged whether it supports the
claim it was attached to. Produce:
- A one-line tally: counts per verdict (Supported, Partially supported, Not
  supported by abstract, Contradicted, Source unavailable).
- A Markdown table of the most important non-Supported findings (skip
  "Supported" rows to keep it focused), columns: Claim (quoted, trimmed) |
  Cited ref | Verdict | What the source's abstract says (source_quote).
- If audit.skipped > 0, add a final italic line: "_N citations with weaker
  claims were not audited (per-run cap)._" using the real number.
- If audit.audited == 0, write exactly: "No in-text citations were available
  to audit at the abstract level."
Keep wording hedged: "Not supported by abstract" means verify against the full
text, not that the citation is wrong.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest backend/tests/test_citation_audit.py::test_l4_prompt_includes_citation_support_audit_section -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/latextools/papercheck.py backend/tests/test_citation_audit.py
git commit -m "feat(citation-audit): surface Citation Support Audit in L4 report"
```

---

### Task 9: Feed the audit into the Literature persona

**Files:**
- Modify: `backend/latextools/papercheck.py` (`_build_persona_user_content`, around lines 992-1040)
- Test: `backend/tests/test_citation_audit.py`

- [ ] **Step 1: Write the failing test**

```python
def test_persona_content_includes_audit_block():
    from latextools import papercheck
    from latextools.papercheck import PaperStructure
    struct = PaperStructure(body="Body text here.")
    l2 = {"issues": [], "audit": {"audited": 1, "skipped": 0,
          "by_verdict": {}, "findings": [
              {"claim_sentence": "X improves Y.", "ref_key": "1",
               "verdict": "Contradicted", "source_quote": "We found no effect.",
               "rationale": "Abstract reports the opposite."}]}}
    content = papercheck._build_persona_user_content(
        "PERSONA", struct, {"findings": []}, l2, "general")
    blob = _json_dump_blob(content)
    assert "citation_support_audit" in blob
    assert "Contradicted" in blob


def _json_dump_blob(content) -> str:
    # content is a list of content blocks; concatenate their text.
    import json
    return json.dumps(content)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest backend/tests/test_citation_audit.py::test_persona_content_includes_audit_block -q`
Expected: FAIL with `AssertionError` (the `citation_support_audit` block is not yet added)

- [ ] **Step 3: Write minimal implementation**

In `_build_persona_user_content` (`papercheck.py`), find the block that wraps the L2 issues:

```python
        + _safety.wrap_user_content(
            _json.dumps(l2.get("issues", [])[:30], indent=2),
            "citation_issues_from_l2",
        )
```

Immediately after it (before the `manuscript_body` block), insert:

```python
        + _safety.wrap_user_content(
            _json.dumps((l2.get("audit") or {}).get("findings", [])[:40], indent=2),
            "citation_support_audit",
        )
```

Then edit the `_LITERATURE_AUDITOR` string constant in `papercheck.py` (around line 619, the persona that "scrutinize[s] how the manuscript USES the literature"). Insert this sentence into its `Check:` preamble, right after the line "You are given a citation cross-check (Layer 2) listing which references verified; use it.":

```
You are also given a citation_support_audit: per-claim verdicts on whether each cited source's abstract supports the claim. Use Contradicted and Not-supported-by-abstract findings as evidence, but keep language hedged and quote the source.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest backend/tests/test_citation_audit.py::test_persona_content_includes_audit_block -q`
Expected: PASS

- [ ] **Step 5: Run the full backend suite**

Run: `python3 -m pytest backend -q`
Expected: PASS (all green)

- [ ] **Step 6: Commit**

```bash
git add backend/latextools/papercheck.py backend/tests/test_citation_audit.py
git commit -m "feat(citation-audit): feed audit findings to the Literature persona"
```

---

### Task 10: Annotate non-Supported audit findings in the PDF

**Files:**
- Modify: `backend/latextools/pdf_annotate.py` (the `annotate_pdf` body, after the L3 loop around line 175)
- Test: `backend/tests/test_citation_audit.py`

- [ ] **Step 1: Write the failing test**

```python
def test_audit_annotation_text_renders_verdict():
    from latextools import pdf_annotate
    finding = {
        "claim_sentence": "X improves Y.", "ref_key": "12",
        "verdict": "Contradicted", "source_quote": "We found no effect.",
        "rationale": "Abstract reports the opposite.",
    }
    body = pdf_annotate._make_audit_annotation_text(finding)
    assert "Contradicted" in body
    assert "[12]" in body or "12" in body
    assert "We found no effect." in body


def test_audit_findings_selected_for_annotation():
    from latextools import pdf_annotate
    findings = [
        {"claim_sentence": "a", "ref_key": "1", "verdict": "Supported"},
        {"claim_sentence": "b", "ref_key": "2", "verdict": "Contradicted"},
        {"claim_sentence": "c", "ref_key": "3", "verdict": "Not supported by abstract"},
        {"claim_sentence": "d", "ref_key": "4", "verdict": "Source unavailable"},
    ]
    selected = pdf_annotate._audit_findings_to_annotate(findings)
    verdicts = {f["verdict"] for f in selected}
    # Only Contradicted + Not-supported are worth a margin note.
    assert verdicts == {"Contradicted", "Not supported by abstract"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest backend/tests/test_citation_audit.py::test_audit_annotation_text_renders_verdict -q`
Expected: FAIL with `AttributeError: module 'latextools.pdf_annotate' has no attribute '_make_audit_annotation_text'`

- [ ] **Step 3: Write minimal implementation**

Add these two helpers to `pdf_annotate.py` (near `_make_annotation_text`, around line 101):

```python
def _make_audit_annotation_text(finding: dict) -> str:
    """Render one audit finding into a sticky-note body."""
    verdict = finding.get("verdict") or "(no verdict)"
    ref = finding.get("ref_key") or ""
    quote = finding.get("source_quote") or ""
    rationale = finding.get("rationale") or ""
    head = f"CITATION AUDIT — {verdict}"
    if ref:
        head += f" [{ref}]"
    lines = [head]
    if quote:
        lines.append(_wrap_text(f"Source abstract: {quote}"))
    if rationale:
        lines.append(_wrap_text(rationale))
    return "\n".join(lines)


def _audit_findings_to_annotate(findings: list) -> list:
    """Only Contradicted / Not-supported findings earn a margin annotation."""
    keep = {"Contradicted", "Not supported by abstract"}
    return [f for f in (findings or []) if f.get("verdict") in keep]
```

Then in `annotate_pdf`, after the existing L3 loop (`for f in (l3.get("merged_findings") or [])[:40]:` block), add a loop that places audit annotations using the claim sentence to locate the page:

```python
    # Audit — place a note on the page where the claim sentence lives.
    audit = (l2.get("audit") or {})
    for f in _audit_findings_to_annotate(audit.get("findings", []))[:20]:
        page = _find_page_for_quote(f.get("claim_sentence", ""), page_texts) or 1
        _add(page, "audit", {
            "issue": _make_audit_annotation_text(f),
            "severity": "major" if f.get("verdict") == "Contradicted" else "minor",
        })
```

Note: `_add`, `page_texts`, and `_find_page_for_quote` already exist in `annotate_pdf`'s scope. `_make_annotation_text` reads `finding["issue"]`, so passing the rendered text under the `issue` key reuses the existing rendering path.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest backend/tests/test_citation_audit.py -q`
Expected: PASS

- [ ] **Step 5: Run the full backend suite**

Run: `python3 -m pytest backend -q`
Expected: PASS (all green)

- [ ] **Step 6: Commit**

```bash
git add backend/latextools/pdf_annotate.py backend/tests/test_citation_audit.py
git commit -m "feat(citation-audit): annotate contradicted/unsupported claims in the PDF"
```

---

### Task 11: Frontend copy — Layer 2 description, FAQ, JSON-LD, sample excerpt

**Files:**
- Modify: `site/tools/paper-review/index.html`

No automated test (static content). Verification is by `grep` after each edit.

- [ ] **Step 1: Update the Layer 2 bullet in "How the review works"**

Replace the `<li>` for "Layer 2 — Live citation cross-check" (lines ~170-175) with:

```html
          <li>
            <strong>Layer 2 — Citation support audit.</strong>
            Every reference is verified against CrossRef, then we go deeper:
            for the most load-bearing claims, we fetch the cited source's
            abstract and check whether it actually supports the claim you
            attached it to. Each finding shows your claim next to the source's
            own words, with a verdict — supported, partially supported, not
            supported by the abstract, contradicted, or source unavailable.
            Hedged language; verify each against the full text.
          </li>
```

- [ ] **Step 2: Add a FAQ entry**

After the "What domains does it cover?" `<details>` in the `tool-faq` section (around line 266), add:

```html
        <details><summary>How deep is the citation check?</summary><div class="faq-body">Two levels. First, every reference is checked for existence against CrossRef (dead DOIs, hallucinated or weakly-matched titles). Second, for the most load-bearing claims we fetch the cited source's abstract from OpenAlex, Semantic Scholar, or CrossRef and assess whether it supports your claim. This is an abstract-level check: a claim supported only in the full text is marked "not supported by abstract," not wrong — verify it against the source. When no abstract can be retrieved, the citation is marked "source unavailable" rather than guessed. On citation-heavy papers we audit the most important claims first and tell you how many were not audited.</div></details>
```

- [ ] **Step 3: Update the JSON-LD `featureList`**

In the `WebApplication` `featureList` array (around line 36-46), replace `"Live citation cross-check against CrossRef"` with two entries:

```json
            "Live citation existence cross-check against CrossRef",
            "Deep citation support audit: fetches cited abstracts and verifies claim support",
```

- [ ] **Step 4: Update the JSON-LD FAQ answer**

In the `FAQPage` → "What does the review include?" answer (around line 55), change the Layer 2 clause from `"(2) a live CrossRef cross-check of every reference,"` to:

```
(2) a citation support audit — existence cross-check against CrossRef plus an abstract-level check of whether the most load-bearing cited sources actually support the claims,
```

- [ ] **Step 5: Add a sample excerpt to the report `<pre>`**

In the `pr-sample` `<pre>` block, after the `## Reference Verification Summary` paragraph (around line 246), append:

```
## Citation Support Audit

Verdicts: 18 supported, 4 partially supported, 2 not supported by
abstract, 1 contradicted, 3 source unavailable.

| Claim | Cited ref | Verdict | What the source's abstract says |
|---|---|---|---|
| "Method X reduces error by 40%." | [14] | Contradicted | Abstract reports a 4% reduction, not 40%. Verify the figure. |
| "Prior work proved this is optimal." | [9] | Not supported by abstract | Abstract describes a heuristic; optimality may be in the full text. |

_5 citations with weaker claims were not audited (per-run cap)._
```

- [ ] **Step 6: Verify all edits landed**

Run: `grep -c "Citation support audit\|citation support audit\|Citation Support Audit" "site/tools/paper-review/index.html"`
Expected: `4` (Layer 2 heading, FAQ, sample heading, and one prose mention) or greater.

- [ ] **Step 7: Commit**

```bash
git add site/tools/paper-review/index.html
git commit -m "feat(citation-audit): update Paper Review copy, FAQ, JSON-LD, sample"
```

---

### Task 12: Full verification + branch wrap-up

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend suite**

Run: `python3 -m pytest backend -q`
Expected: PASS — all prior tests plus the new `test_citation_audit.py` green.

- [ ] **Step 2: Lint-import the new module in isolation**

Run: `cd backend && python3 -c "from latextools import citation_audit; print('ok', citation_audit.MAX_AUDIT_PAIRS)"`
Expected: `ok 40`

- [ ] **Step 3: Confirm no syntax errors in modified backend files**

Run: `cd backend && python3 -c "import ast,sys; [ast.parse(open(f).read()) for f in ['latextools/papercheck.py','latextools/pdf_annotate.py','latextools/citation_audit.py']]; print('parse ok')"`
Expected: `parse ok`

- [ ] **Step 4: Stop here for code review**

Do NOT deploy. The Paper Review checkout is disabled ("Coming soon") and Modal secrets are placeholders, so this ships as a pipeline capability behind the existing gate. Hand back to the requesting session for `requesting-code-review` and a deploy decision.

---

## Self-Review

**Spec coverage:**
- Identify → Task 1 (`extract_claim_citations`). ✓
- Fetch → Task 4 (`fetch_source_abstract`, 3-source fallback). ✓
- Assess → Task 5 (`assess_claims`, batched, clamps unknown verdicts). ✓
- Track (report) → Task 8 (L4 section). ✓
- Track (annotated PDF) → Task 10. ✓
- Verdict taxonomy (5 values) → `VERDICTS` constant (Task 1), used in Tasks 5/6/8/10. ✓
- Academic sources only → OpenAlex/S2/CrossRef in Task 4; no legal code. ✓
- All tiers, bounded cap → cap applied in `run_citation_audit` (Task 6); no tier gating branch, runs for every tier in `run_review_pipeline` (Task 7). ✓
- Abstract-level honesty → "Not supported by abstract" wording in Tasks 5/8/11. ✓
- Source unavailable, never guessed → Task 5 short-circuit + Task 4 fallback. ✓
- Prioritize load-bearing claims + log skipped → Task 2 ranking + Task 6 `skipped` + Task 8 footnote. ✓
- Layer-3 Literature persona consumes audit → Task 9. ✓
- Frontend copy/FAQ/JSON-LD → Task 11. ✓
- Cost guardrails (cap 40, batch 8, concurrent fetch, ephemeral) → Tasks 5/6/7. ✓
- Tests → Task 1-10 each ship tests; Task 12 runs the suite. ✓
- Strict CSP / no emojis / hedged voice → Task 11 uses external CSS only, no emojis, hedged wording. ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code. ✓

**Type consistency:** `ClaimCitation`, `SourceAbstract`, `AuditFinding` defined once (Tasks 1/3/5) and reused with matching fields. `fetch_source_abstract(client, ref_key, ref)` signature consistent across Tasks 4/6. `run_citation_audit(client, structure)` consistent Tasks 6/7. `attach_audit(l2, audit)` consistent Tasks 7. `_make_audit_annotation_text` / `_audit_findings_to_annotate` consistent Task 10. ✓
