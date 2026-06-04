# Deep Citation Audit — Paper Review Layer 2 Deepening

**Date:** 2026-06-04
**Status:** Approved (brainstorming) — pending spec review
**Owner:** Ben Ampel / Purplelink LLC

## Summary

Upgrade Paper Review's **Layer 2** from a citation *existence* check into a
citation *claim-support* audit. Today Layer 2 answers "does this reference
exist and does its title match?" After this change it also answers the
question a reviewer actually cares about: **"does the source you cite
actually support the claim you attached it to?"**

The flow mirrors the four-step model the user referenced (a legal
citation-verification UI), translated to academic sources:

1. **Identify** — extract sentence ↔ citation pairs (the claim each in-text
   citation supports), from body text *and* footnotes.
2. **Fetch** — retrieve each cited source's **abstract** (+ TLDR when
   available) from OpenAlex / Semantic Scholar / CrossRef.
3. **Cross-reference & assess** — an LLM places the user's claim next to the
   source's own words and returns a verdict.
4. **Track** — verdicts become a new **Citation Support Audit** section in the
   Markdown report and annotated PDF, and feed richer evidence into the
   Layer-3 Literature persona.

No new page, no new checkout. This deepens the existing pipeline behind the
already-disabled ("Coming soon") Paper Review checkout.

## Decisions (locked in brainstorming)

| Decision | Choice |
|---|---|
| Citation universe | **Academic** — OpenAlex, Semantic Scholar, CrossRef, arXiv/DOI/direct URL |
| Packaging | **Deepen Layer 2 in place** — no new tool page |
| Tier gating | **All tiers**, with a bounded per-run cap |
| Assessment altitude | **Abstract-level** ("supported *by the abstract*"), not full-text |
| No retrievable source | Verdict **"Source unavailable"** — audited, never judged from title alone |
| Over-cap strategy | **Prioritize load-bearing claims**; log the skipped count (no silent truncation) |

## Verdict taxonomy

Each audited claim-citation pair resolves to exactly one verdict:

- **Supported** — the abstract directly substantiates the claim.
- **Partially supported** — the abstract supports part of the claim, or
  supports a weaker version of it.
- **Not supported by abstract** — the abstract does not contain evidence for
  the claim (may still be in the full text — flagged, not condemned).
- **Contradicted** — the abstract states something at odds with the claim.
- **Source unavailable** — no abstract could be retrieved; not assessable.

Voice constraint (from `DESIGN.md` / site norms): hedged, specific, never
accusatory. "Not supported by abstract" must read as "verify against the full
text," not "you lied."

## Architecture

All new logic lives in `backend/latextools/` as pure, unit-testable helpers
plus thin async I/O wrappers, following the existing `papercheck.py` pattern.
Network calls stay inside async helpers so `app.py` can run them concurrently.

### New module: `backend/latextools/citation_audit.py`

Pure logic + injected-IO helpers (no Anthropic/Modal imports in the pure
parts), mirroring how `pdf_structure.py` was structured.

**1. Identify — `extract_claim_citations(structure) -> list[ClaimCitation]`**
- Input: the existing `PaperStructure` (already parsed from the PDF in
  `extract_paper`), which holds body text and references.
- Walk body + footnote text; for each in-text citation marker (numeric
  `[12]`, `[3,4]`, author-year `(Smith et al., 2021)`, superscript), capture:
  - `claim_sentence` — the sentence the citation is attached to.
  - `ref_keys` — the reference(s) it points to (resolved to `PaperReference`
    entries where possible).
  - `location` — section / page / footnote marker for the report.
- Returns a list of `ClaimCitation` dataclasses. Pure function, deterministic,
  fully unit-tested against fixture text (numeric + author-year styles).

**2. Prioritize — `rank_claims(claims) -> list[ClaimCitation]`**
- Heuristic salience score favoring load-bearing claims: presence of
  causal/empirical verbs ("shows", "demonstrates", "causes", "improves",
  "outperforms"), numbers/effect sizes, superlatives, and claims in
  Results/Discussion over Related Work. Pure + unit-tested.
- The pipeline audits the top `MAX_AUDIT_PAIRS` (default **40**) and records
  `skipped = max(0, len(claims) - MAX_AUDIT_PAIRS)` for honest reporting.

**3. Fetch — `async fetch_source_abstract(client, ref) -> SourceAbstract`**
- Resolution order: OpenAlex (reconstruct from `abstract_inverted_index`) →
  Semantic Scholar (`abstract` + `tldr`) → CrossRef (`abstract` field, often
  JATS-XML — stripped to text). Keyed by DOI when present, else title search.
- Never raises; returns `SourceAbstract(text=None, status="unavailable", ...)`
  on miss. 10s timeout per call, consistent with existing L2.
- Reuses the httpx client and mailto/User-Agent conventions already in
  `papercheck.py` / `bibcheck.py`.

**4. Assess — `async assess_claims(anthropic, batch) -> list[Verdict]`**
- Batches multiple claim/abstract pairs into one Anthropic call (JSON output)
  to bound cost; reuses `_anthropic_message` + `_parse_json_findings` patterns
  already in `papercheck.py`.
- Each verdict carries: `verdict` (taxonomy above), `source_quote` (the
  abstract sentence that most bears on the claim, or null), and a one-line
  `rationale`. Pairs with `status="unavailable"` skip the LLM and resolve
  directly to **Source unavailable**.

### Integration into the pipeline (`papercheck.py` + `app.py`)

- `run_layer_2_citations` keeps its existing existence-check contract and
  gains an augmented result: `{checked, verified, issues, audit: {...}}` where
  `audit` = `{audited, skipped, by_verdict: {...}, findings: [...]}`.
- The orchestration (in `app.py`) runs Identify → rank → Fetch (concurrent,
  bounded) → Assess (batched) after the existence check, within the existing
  L2 async stage so total wall-clock stays inside the sub-10-minute budget.
- **Layer 3**: the Literature persona's evidence block (today fed the
  existence cross-check) additionally receives the audit findings, so the
  persona reasons over *how the literature is used*, not just whether it
  resolves.
- **Layer 4 / report**: new **"Citation Support Audit"** section — a compact
  table of the most important findings (claim · cited ref · verdict · source
  quote), a verdict tally, and an explicit "N citations not audited (cap)" /
  "M sources unavailable" footnote. Each non-Supported finding quotes both the
  claim and the source passage so the author can verify.
- **Annotated PDF** (`pdf_annotate.py`): non-Supported / Contradicted findings
  become margin annotations at the claim location, reusing the existing
  annotation path.

### Frontend (`site/tools/paper-review/`)

Content-only; no behavior change, no new checkout. Honors strict CSP
(`style-src 'self'` — all styling stays in `paper-review.css`), no emojis,
hedged voice.

- **`index.html`**: rewrite the Layer 2 bullet in "How the review works" to
  describe the claim-support audit; add a FAQ entry ("How deep is the
  citation check?") that states the abstract-level limitation plainly; update
  the JSON-LD `featureList` and the `FAQPage` to match.
- The existing sample-report `<pre>` gains a short **Citation Support Audit**
  excerpt so buyers see the new output shape.
- No new CSS required beyond reuse; if the sample table needs styling it uses
  existing report classes.

## Cost & runtime guardrails

- Hard cap `MAX_AUDIT_PAIRS = 40` claim-citation pairs per run.
- Abstract fetches run concurrently with a bounded gather; per-call 10s
  timeout; failures degrade to "Source unavailable", never block the run.
- LLM assessment batched (target ~8–10 pairs per call) → a handful of calls,
  not 40. Net added cost is a few cents of tokens, well within the existing
  paid-tool envelope.
- Everything ephemeral: claim text, abstracts, and verdicts live only for the
  duration of the run and are deleted with the rest of the result on
  retrieval. No new persistence. (Privacy parity with current pipeline;
  abstracts are public data, claims are the user's manuscript text already
  being sent to Anthropic.)

## Testing

- `backend/tests/test_citation_audit.py`:
  - `extract_claim_citations` against numeric and author-year fixtures
    (including footnote citations and multi-ref markers).
  - `rank_claims` ordering (load-bearing claim ranks above a Related-Work
    mention).
  - Abstract reconstruction from a sample OpenAlex `abstract_inverted_index`.
  - Verdict assembly with injected fake fetch/assess (no network): cap
    enforcement, skipped count, "Source unavailable" path.
- Existing `papercheck` / `bibcheck` tests must stay green (augmented L2
  result is additive — existing keys unchanged).

## Out of scope (YAGNI)

- Legal citations / CourtListener / Bluebook parsing.
- Full-text (paywalled) retrieval.
- A standalone citation-audit tool page or separate checkout.
- Persisting audit history across runs.

## Risks

- **In-text citation extraction is messy** across styles. Mitigation: support
  the two dominant styles (numeric, author-year) well; degrade gracefully
  (un-parseable markers are skipped and counted, never crash).
- **Abstract availability varies by field.** Mitigation: "Source unavailable"
  is a first-class, honest outcome, surfaced explicitly, never guessed.
- **Over-claiming risk** if verdicts read as accusations. Mitigation: hedged
  taxonomy wording + always quote the source passage so the human decides.
