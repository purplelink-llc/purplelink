# Paper Review: Coherence Check (spec, 2026-10-23)

Status: prototype behind two feature flags, not visible to buyers. Pricing and launch are Ben's decision.
Code: `backend/latextools/coherence.py`, tests `backend/tests/test_coherence.py`, CLI
`backend/scripts/coherence_check.py`, internal endpoint `POST /paper-review/coherence/internal`.

## What it does

The paid review asks "is this paper good?" The coherence check asks a narrower question that a reviewer
answers in the first hour and an author rarely sees in their own draft: **does the paper agree with
itself?** It reads each section into a *Paper Bible* (what the paper says its research questions,
hypotheses, constructs, theories, sample, numbers, contributions and limitations are) and compares the
sections against each other.

The idea comes from fiction tools that keep a "story bible" of every scene and flag continuity errors. A
manuscript has the same failure: the introduction promises three contributions, the discussion delivers two;
H3 is stated in the theory section and never reported; "trust" is a belief on page 4 and a behaviour on
page 19; the abstract still says 87.4% after the results changed to 84.7%.

## The checks

| Type | Example | How it is found |
|---|---|---|
| `hypothesis_untested` | H3 stated in Theory, never named in Results, Discussion or Conclusion | Rule (labels by section role), model for unlabelled hypotheses |
| `hypothesis_undeclared` | H4 appears with its result but was never stated | Rule |
| `research_question_unanswered` | RQ2 posed, never answered | Rule (labels and "the second research question"), model |
| `label_gap` | H1, H2, H4: H3 missing | Rule |
| `acronym_conflict` | SEM = structural equation modeling, later search engine marketing | Rule (Schwartz-Hearst expansion) |
| `abstract_results_mismatch` | Abstract 12.4%, results 12.7% | Rule (numbers, rounding and 92% = 0.92 allowed), model for worded results |
| `construct_definition_conflict` | A construct defined or measured two incompatible ways | Model |
| `term_drift` | One concept under three names, or one name drifting in meaning | Model |
| `theory_unused` | A theory introduced as the lens and never used to derive or interpret | Model |
| `contribution_undelivered` | A contribution claimed in the introduction, absent from the discussion | Model |
| `limitation_contradicts_claim` | "Generalises across industries" vs "single-firm sample" | Model |
| `sample_inconsistency` | N = 412 in the method, 410 in a table note | Model |
| `citation_role_conflict` | One source cited for opposite claims | Model |

Out of scope on purpose: style, grammar, statistics reporting (statcheck and GRIM already run in the main
review), figure and reference integrity (also in the main review), and the quality of the research. Whether a
citation actually supports its claim needs the cited abstract; that is the existing `citation_audit` module's
job and is the natural phase 2 here (the Bible already records each central `citation_use`).

## Pipeline

1. **Read.** `.tex` through a tolerant LaTeX stripper (pandoc rejects many real preambles: it failed on the
   first real draft tried, on a `\newcolumntype`), keeping `\cite` keys as `[cite: keys]` and table cells.
   `.docx` through pandoc to Markdown (same `--sandbox` and zip checks as the existing Word path). `.pdf`
   through pypdf, which keeps two-column pages in reading order better than the main review's extractor
   (that extractor interleaved the columns of the open-access test paper), with running heads removed.
   Sections are split on headings and each gets a role (introduction, literature, theory, method, results,
   discussion, limitations, conclusion); a subsection inherits its parent's role.
2. **Rules** (no model, no cost): labels, acronyms, abstract numbers. This is also the free sample.
3. **Extract** (cheaper model, one call per ~14,000 characters of whole sections, four in parallel): Paper
   Bible items, each `{section, kind, label, text, quote}`. Code checks every quote verbatim against the
   section text and drops the item if it is not there.
4. **Cross-check** (main model, one call, Bible only): findings must cite Bible item ids. The report's
   quotes are taken from those items, never from the model's free text, so a quote in the report is always
   a real span of the manuscript.
5. **Verify** (main model, one call, full text plus the candidate list): drops findings the text resolves
   (the hypothesis is in a table, the definitions are compatible) and resets confidence. If the verifier's
   reply is unreadable, findings are kept and marked "not verified" rather than silently dropped.

### Paper Bible schema

```json
{"id": "B12", "section": "S7", "kind": "construct_definition", "label": "Job embeddedness",
 "text": "Defined as the forces that keep an employee in a job, modelled formatively.",
 "quote": "We model job embeddedness as a formative construct because"}
```

Kinds: `research_question`, `rq_answer`, `hypothesis`, `hypothesis_result`, `construct_definition`,
`theory`, `theory_use`, `sample`, `key_number`, `contribution_claimed`, `contribution_delivered`,
`limitation`, `claim`, `citation_use`. Sections: `{id, title, level, role, chars}`.

### Report format

Each finding: `type`, `title` (one sentence), `sections` involved, `quotes` (verbatim, at most 25 words
each, with their section), `why` (why a reviewer cares), `fix` (a specific edit), `confidence`
(high, medium, low), `source` (rule or model), `verifier_note`. The rendered report lists findings surest
first, then a short Paper Bible appendix (research questions, hypotheses, construct definitions, theories,
sample, claimed contributions, limitations) so the author can confirm the paper says what they meant. The
JSON also keeps the verifier's dropped findings for internal tuning; they are never shown to a buyer.

## Inputs and limits

- `.pdf`, `.docx`, `.tex` (single file; `\input` children are not followed, so a multi-file project
  should be uploaded as its PDF until a zip path exists). 20 MB upload cap, as for Paper Review.
- Up to 120 PDF pages read; up to 160,000 characters of section text sent (about 45,000 tokens).
  References are never sent; appendices are cut first when a paper is longer.
- Scanned PDFs (no text layer) are refused with a plain message.

## Privacy

Same rules as Paper Review today, stated on the product page:

- The manuscript is processed in memory. Nothing is written to a Modal Dict or a log line except counts
  (sections, items, findings). Exceptions are logged by type only, since messages can carry text.
- It goes to Anthropic's API only, which keeps inputs up to 30 days for abuse monitoring and does not
  train on them. No other service sees it.
- The report is held and deleted on the existing Paper Review schedule (30 minutes after first view, 24
  hours at most) and emailed as the report only, never the manuscript.
- Unpublished work: the report quotes the manuscript, so it is treated as the manuscript for retention.

## How it fits the product

Current prices (live, `PAID_PRODUCTS` in `backend/app.py`): Standard $9, Journal $11, Deep $15, 5-pack $38,
20-pack $150; add-ons Anonymity $2, Cover letter $3, Citation gap $5, Revision review $2. Paper Review has
never sold (near-zero traffic), so the question is less margin than a clearer reason to buy.

Options considered:

1. **Standalone tier.** A cheaper, narrower product with an obvious promise.
2. **Included in existing tiers.** Raises the value of $9 but adds nothing a new visitor can understand
   faster.
3. **Free sample, paid full report.** The rule checks are free to run; the model stages are not.

**Recommendation: a standalone "Coherence Check" at $5, with the rule checks free on the upload page as
its sample, and the full check folded into all three existing tiers at no price change.**

- $5 sits under the $9 Standard and next to the $5 Citation Gap, so it reads as an entry point, not a
  discount. Measured model cost per paper is in "Prototype runs" below; Stripe takes about $0.45 of $5.
- The free sample works like the existing free preview: run the rules, show the count and the first
  finding, and say how many sections the full check reads. A draft with labelled hypotheses or a stale
  abstract number shows something real before payment.
- Adding it to existing tiers gives the $9 review a concrete new line ("checks that your paper agrees with
  itself") without touching its price.

Constraint to weigh before launch: studio rule 1 holds every price, trial and discount until 2027-01-12. A
new product at a new price is not a change to an existing price, but it is a new price; Ben should decide
whether it waits. Including it in the existing tiers needs no price decision.

Stripe implications (nothing has been created): one new Price on the existing Paper Review product account
(`STRIPE_PRICE_COHERENCE_CHECK`), a `coherence-check` key in `checkout.mjs`'s `PRODUCT_CATALOG` and in
`PAID_PRODUCTS` (category `coherence-check`, amount 500), a dispatch branch in `adjacent_tool_pipeline`, an
upload page under `site/tools/paper-review/`, and a new CSP-safe script. Stripe Tax already applies. The
planned December move to a new Stripe account means the price is created twice; launching after the move
avoids that.

### Flags

- `COHERENCE_CHECK_ENABLED=1` (web function's secret): enables the internal endpoint. Callers also need
  `x-webhook-secret: $BACKEND_WEBHOOK_SECRET`. `mode=rules` runs inline; `mode=full` runs in the
  `coherence_check_job` Modal function, which is the only one that mounts the Anthropic key.
- `COHERENCE_IN_REVIEW=1` (pipeline function's secret): appends the coherence section to paid Paper Review
  reports. It runs inside the order's usage tracker, so it counts against the order's cost ceiling, and a
  failure returns an empty section rather than failing the paid review.
- `COHERENCE_EXTRACT_MODEL` (default `claude-sonnet-5-5`), `COHERENCE_CHECK_MODEL` (default the review's
  `DEFAULT_MODEL`), `COHERENCE_EFFORT`.

## Name and positioning

Options, in Purplelink's plain voice:

1. **Coherence Check**: "Does your paper agree with itself?" Plain, says what it does. Recommended.
2. **Consistency Check**: clearer to some, but reads like spelling and formatting.
3. **Paper Bible**: memorable, but borrowed from fiction and odd on an academic page. Better as the name of
   the appendix inside the report.

Page copy draft: "Reviewers notice when the introduction promises three contributions and the discussion
delivers two, when H3 is never reported, or when the abstract's numbers no longer match the tables. The
Coherence Check reads every section, records what each one claims, and lists the places where they
disagree, with the exact sentences quoted. $5."

## Prototype runs

Pending: the two live runs need a non-production Anthropic key (`BENCH_ANTHROPIC_KEY`).

Rule checks alone (no model), 2026-10-23:

- An open-access PDF (an ICSE 2026 survey with 15 hypotheses, CC BY-NC-SA): after two fixes found on this
  paper (labels glued to words by PDF extraction, "supportingH10"; an ISBN read as an abstract number), no
  rule findings, which is correct: every hypothesis is reported. The paper's real coherence point, two
  hypotheses stated and later "not tested" for reliability reasons, needs the model stage.
- One of the owner's own LaTeX drafts (21 sections): no rule findings; its three research questions are
  each answered in Results. Also correct.
