# Scope D — Academic Review Engine as a B2B / White-Label API

**Status:** Scoping document — no code changes implied. Written 2026-07-16.
**Product idea:** Expose the existing multi-layer paper-review engine (Modal backend) as a
licensed API for other platforms — journal submission systems, university writing centers,
citation-tool builders, and researcher-tool startups — as a semi-passive licensing revenue
stream alongside (not replacing) the consumer one-time-purchase products.

---

## 1. Current state — what exists today (code-grounded)

### 1.1 The engine

The core asset is a four-layer adversarial review pipeline in
`backend/latextools/papercheck.py`, orchestrated end-to-end by
`papercheck.run_review_pipeline` (papercheck.py:2198):

| Layer | Function | What it does |
|---|---|---|
| L0 — Extraction | `papercheck.extract_paper` (papercheck.py:503) | pdfplumber-based structured extraction (title, abstract, body, references, figures) with two-column/gutter heuristics (`_extract_page_text`), reference splitting/parsing, hard caps (400 pages, 80k body chars, 60 refs) |
| L1 — Vision | `papercheck.run_layer_1_vision` (papercheck.py:1344) | Renders up to 30 PDF pages (≤2200px, 60s render timeout) and runs Claude vision over them for figure manipulation, text-figure contradictions, table inconsistencies, presentation/accessibility issues. Findings scrubbed for image-borne prompt injection by `_scrub_l1_findings` |
| L2 — Citations | `papercheck.run_layer_2_citations` (papercheck.py:1576) | Verifies every parsed reference against CrossRef; DOI resolution walks the doi.org redirect chain hop-by-hop with an SSRF guard (`_resolve_doi_redirects_safely`, `_is_ssrf_safe_url`) — detects dead/hallucinated references |
| L2.5 — Deep citation audit | `citation_audit.run_citation_audit` (citation_audit.py:417) | Extracts sentence↔citation pairs, ranks by salience, fetches source abstracts (OpenAlex → Semantic Scholar → CrossRef), and issues an LLM verdict per claim (Supported / Partially / Not supported / Contradicted / Unavailable; 40-pair cap). Runs concurrently with L1/L2 |
| L3 — Persona panel | `papercheck.run_layer_3_personas` (papercheck.py:1757) | Seven personas in parallel (`PERSONA_PROMPTS`: methodology_critic, statistical_skeptic, data_integrity_officer, editor_in_chief, equation_analyst, literature_auditor, numerical_realist), merged by `_consensus_filter` (token-Jaccard ≥ 0.35 marks cross-persona consensus) |
| L3.5 — Deep pass | `papercheck.run_layer_3_deep_pass` (papercheck.py:1855) | Deep tier only: each persona re-reviews with sight of the others' first-pass findings |
| Deterministic checks | `manuscript_checks.all_findings` | No-LLM ground truth: statcheck p-value recomputation, GRIM, arithmetic consistency, open-science statements, reference integrity. Ported from ModernTex Swift; fully reproducible |
| Add-ons | `paperreview_extras.run_anonymity_check`, `journals.check_compliance` | Double-blind leak scan; rule-based journal compliance |
| L4 — Synthesis | `papercheck.run_layer_4_rectify` (papercheck.py:2042) | Produces the final Markdown report (Blind Spots, Data-to-Claim Contradictions, Equation Audit, Rectification Checklist, Novelty Estimate, Citation Support Audit, Panel Transcript) |
| Post | `pdf_annotate.annotate_pdf` | Annotated copy of the customer's PDF (no LLM calls) |

Domain packs exist for ML, biomedicine, psychology/social, chemistry/materials, general
(`DOMAIN_MODULES`, papercheck.py:893), plus an AI-SCoRe checklist mode (`domain == "nca"`
delegates to `aiscore.run_aiscore` inside `run_review_pipeline`).

Adjacent sellable checks, all reusing the same Anthropic helper and safety stack:

- **Citation audit / hallucination detection** — `citation_audit.py` (also usable standalone)
- **BibTeX validation & correction** — `bibcheck.py` (pure logic; network checks in `app.py`'s `/validate-bib`)
- **Deterministic stats checks** — `manuscript_checks.py` (statcheck/GRIM — zero LLM cost)
- **Anonymity check, citation gap, cover letter, revision review** — `paperreview_extras.py`
- **Response-to-reviewers review** — `response_review.py` (3-persona panel)
- **Resume review** — `resume_review.py` (3-persona; first non-academic product)

Model economics are already instrumented: `DEFAULT_MODEL = claude-fable-5` with
`claude-opus-4-8` fallback (papercheck.py:49–56), a pricing table
(`MODEL_PRICING_PER_MTOK`), and per-call cost capture via `_record_usage` / `_cost_usd`
flowing into a `UsageTracker` contextvar (papercheck.py:75–156). Every finished job writes a
**permanent per-job cost record** — product, status, price charged, input/output tokens,
cost USD, models used — via `app.py:_write_usage_ledger` into the Modal Dict
`paper-review-usage-ledger` (app.py:92–102, 205–227). This is the seed of metered billing.

### 1.2 The real API surface today

Everything is served from one Modal ASGI app, `app.py:web()` (app.py:926), at
`https://ben-ampel--purplelink-latextools-web.modal.run`. Relevant paid endpoints:

- `POST /paper-review/register-token` — internal, HMAC header-authenticated (`x-webhook-secret`), called only by the Stripe webhook (app.py:2008)
- `POST /paper-review/redeem-session` — session_id → token exchange for the browser
- `POST /paper-review/submit` — token + PDF upload → `.spawn()`s `paper_review_pipeline`; tier/bundles inferred from the token's product config (app.py:2437)
- `GET /paper-review/status?token=…` — polling; result deleted ~30 min after first delivery (`PAPER_RESULT_GRACE_SECONDS`), 24h TTL backstop (app.py:2620)
- `POST /score/submit` + per-tool submits for cover-letter, anonymity-check, citation-gap, revision-review, response-review, resume-review
- A dozen free LaTeX-tool endpoints (compile, diff, validate-bib, word-stats, pdf-structure, …)

CORS is locked to `https://purplelink.llc` / `www` (`ALLOWED_ORIGINS`, app.py:195) — the
whole surface assumes a browser flow from our own site. Server-to-server callers aren't
CORS-blocked, but nothing authenticates them either, except single-use tokens.

### 1.3 How access is gated now (the key gap)

The entire access model is **one-time Stripe Checkout → single-use redemption token**:

1. `netlify/functions/checkout.mjs` maps a product key (`PRODUCT_CATALOG`: 11 SKUs, $2–$150) to a Stripe price and creates a one-time-payment Checkout Session (idempotency-keyed, 25/day/IP rate cap).
2. `netlify/functions/stripe-webhook.mjs` verifies the Stripe signature and forwards `checkout.session.completed` to Modal's `/paper-review/register-token` with a shared secret header.
3. `paper_review_register_token` (app.py:2009) cross-checks `amount_paid` against `PAID_PRODUCTS` and mints `qty` tokens (`secrets.token_urlsafe(32)`), 7-day TTL, stored in Modal Dicts (`paper-review-tokens` + a reverse index).
4. `/paper-review/submit` enforces single use via an atomic compare-and-set claim (`_claim_token`, app.py:2399 — `paper_token_claims_dict.put(..., skip_if_exists=True)`), spawn-before-consume, and auto-reissue on mid-pipeline failure (`_reissue_token_on_failure`, app.py:230).

Rate limiting is per-IP, per-endpoint-bucket, 25/day (`core.DAILY_LIMIT`,
`core.check_and_increment`, core.py:409–480). There are **no accounts, no API keys, no
subscriptions, no per-customer quotas, and no machine-readable output contract** — the
deliverable is a Markdown report (plus annotated PDF) designed for a human buyer, with a
Purplelink referral footer appended (`_referral_footer_md`, app.py:292) and
Purplelink-branded delivery emails (`delivery.py:FROM_ADDRESS`, templates at
delivery.py:215–397).

Two important operational facts:

- **Capacity ceiling:** `paper_review_pipeline` runs at `max_containers=4`, 900s timeout (app.py:391–397); the web app at `max_containers=6`, 4 concurrent inputs. Realistic throughput is roughly 15–40 full reviews/hour. Fine for pilots; a platform integration needs these raised (a config change, but with cost and Anthropic rate-limit implications).
- **Checkout is currently disabled** ("Coming soon" buttons; placeholder Modal secrets — see `docs/paper-review-runbook.md`). The engine has never had paying traffic, so `usage_ledger_dict` holds no real COGS data yet; consumer prices were set from estimates (comment at app.py:162–172).

The security posture is genuinely strong for a B2B pitch: single-place input sanitization
(`safety.py` — length caps, zero-width/control stripping, delimiter neutralization,
injection-pattern flagging), prompt fencing, image-channel injection scrubbing, SSRF guards
on DOI resolution, upload caps + magic bytes, and an unusually good data-retention story
(manuscripts held in memory / short-TTL dicts only; results purged ~30 min after delivery).
`docs/security-paper-review.md` is effectively a ready-made vendor-security-questionnaire
answer.

---

## 2. The productization gap

What has to exist before another platform can integrate. Effort: S = days,
M = 1–2 weeks, L = multi-week.

| # | Capability | What exists today | Net-new work | Effort |
|---|---|---|---|---|
| 1 | **API-key issuance & tenant registry** | Single-use tokens per Stripe session; HMAC shared secret for the webhook | Long-lived per-tenant keys (hashed at rest in a Modal Dict or small DB), key create/rotate/revoke, per-key product scopes, a minimal admin CLI. No self-serve signup needed for outbound sales — keys can be minted manually at first | **M** (S for a manual-issuance v0) |
| 2 | **Metered / subscription billing** | `UsageTracker` + `_write_usage_ledger` already record per-job tokens, model, and USD cost, permanently, keyed per job | Aggregate ledger records by tenant (add `tenant_id` to the ledger key/record), push Stripe Billing meter events or generate monthly invoices, overage handling. Stripe subscription objects replace one-time Checkout for these customers | **M** (ledger aggregation is S; Stripe metered wiring is the M) |
| 3 | **Per-key rate limiting & quotas** | Per-IP daily counters (`core.check_and_increment`) — same primitive works | Key-scoped quotas (monthly + burst), concurrency caps per tenant, 429 + Retry-After semantics, plan-tier lookup | **S/M** |
| 4 | **Per-tenant isolation** | Jobs keyed by single-use token; results auto-purged (30-min grace + 24h TTL — already a good API default) | Namespace `paper_jobs_dict` entries by tenant, tenant-scoped status lookups (a tenant must never read another's job), per-tenant retention overrides, audit log of submissions | **M** |
| 5 | **White-label output** | The L4 Markdown report is already brand-neutral; branding enters only via the referral footer (`_referral_footer_md`, appended only when `deliver_email` is set — app.py:445–453) and `delivery.py` email templates | A `branding=none` (or per-tenant branding config) flag: suppress referral footer, skip/re-skin delivery emails (or return results API-only and let the partner deliver), optional partner name in the report header. Smallest item on this list | **S** |
| 6 | **Machine-readable output + OpenAPI spec** | Layer outputs are already dicts (merged_findings, L2 issues, audit findings, deterministic findings all structured JSON before L4 flattens to Markdown — see `run_review_pipeline`'s return, papercheck.py:2369–2385) | A `format=json` response mode exposing the structured layers alongside (or instead of) the Markdown; versioned response schema; an OpenAPI 3.1 spec + hosted reference docs distinct from the consumer upload flow; sandbox/test keys with a stub pipeline | **M** |
| 7 | **Completion webhooks** | Polling only (`/paper-review/status`) | Per-tenant callback URL with HMAC signing (mirror the existing `stripe-webhook.mjs` pattern in reverse), retry/backoff. Polling can remain the v0 contract | **S/M** |
| 8 | **Usage dashboard** | Ledger is queryable via `modal dict items paper-review-usage-ledger` (runbook, "Cost & margin tracking") | v0: monthly usage statement email + CSV export per tenant (S). v1: a simple authenticated stats page (the site already has a first-party `/stats/` pattern to copy) | **S → M** |
| 9 | **SLA & capacity** | Modal autoscaling with deliberately low caps (`max_containers=4` pipeline); no status page; alerting exists only for webhook failures (`alertOperator`, stripe-webhook.mjs:107) | Raise container caps per contracted volume, queue-depth/latency monitoring, a status page, an SLA credit policy, Anthropic rate-limit headroom check. Mostly operational, not code | **S code / M operational** |
| 10 | **B2B trust package** | `docs/security-paper-review.md` threat model; strong retention story | DPA template, data-flow diagram, subprocessor list (Modal, Anthropic, Stripe, Resend, Netlify), retention policy doc. SOC 2 is **L** and should be explicitly deferred — pilot partners at this size accept a security doc + DPA | **S docs / L if SOC 2 demanded** |

**Zero-engineering pilot hack worth noting:** the volume-pack machinery already mints N
tokens per purchase and emails them with `?direct_token=` deep links
(`html_volume_pack_tokens`, delivery.py:226). A writing center or editing firm could be
sold a 20-pack ($150) today, with tokens distributed internally, before any API work
exists. That is a legitimate discovery instrument: if nobody will buy token packs, nobody
will buy an API.

---

## 3. Target customers

Ranked roughly by fit. "Wedge" = the single check to lead with, chosen for low COGS,
easy integration, and obvious pain.

| # | Archetype | Why they'd pay | Easiest wedge |
|---|---|---|---|
| 1 | **Academic editing / proofreading firms** (thesis and manuscript services) | They sell "submission readiness" but do it manually; a white-labeled pre-submission report is a new upsell SKU with zero staff time | Full standard review, white-labeled (`run_review_pipeline`, standard tier) |
| 2 | **Citation-manager / reference-tool builders** (Zotero plugin ecosystem, reference SaaS) | AI-hallucinated citations are a top-of-mind 2026 problem; "verify my library" is a feature they can ship in a week against one endpoint | Citation verification (`run_layer_2_citations` + `bibcheck`) |
| 3 | **University writing centers & graduate schools** | Fixed budgets, recurring cohorts, want an institutional tool that isn't "students pasting theses into a chatbot"; strong data-retention story matters here and we already have it | Volume-pack full reviews first; API later. Anonymity check (`run_anonymity_check`) for submission prep workshops |
| 4 | **AI academic-writing assistants** (Paperpal-class startups) | They compete on checks they haven't built; deterministic statcheck/GRIM (`manuscript_checks.py`) is reproducible, defensible, and near-zero marginal cost — a differentiator they can label "verified, not AI-guessed" | Deterministic checks + citation audit |
| 5 | **Smaller OA journal platforms / library publishing programs** | Desk-check automation: dead-DOI and hallucinated-reference screening before editors spend time | Citation verification as a desk-check batch endpoint |
| 6 | **Preprint servers / institutional repositories** | Integrity screening at ingest (figure manipulation flags, reference verification) without hiring integrity staff | L1 vision scan + L2 citations (hedged-language findings already built into the prompts) |
| 7 | **Conference / workshop management tooling** (OpenReview-adjacent, smaller CMTs) | Desk-reject triage at deadline spikes; per-paper pricing maps cleanly to their submission fees | Standard review or citations-only, batch submitted |
| 8 | **Research-integrity consultancies** | They bill hourly for exactly what L1 + deterministic checks automate; API output becomes their working notes | L1 vision + statcheck/GRIM |
| 9 | **Grant-support / research-development offices** | Pre-submission review of proposals (methods + numbers + citations); weaker fit — pipeline is tuned to manuscripts | Citation audit + deterministic checks only |
| 10 | **Methods-course tooling / LMS plugins** | Teaching statistical reporting: statcheck/GRIM on student papers is cheap (no LLM) and pedagogically legible | Deterministic checks (`manuscript_checks.all_findings`) |

Note the pattern: **citation verification is the wedge for half the list.** It is also the
cheapest layer to serve (CrossRef/OpenAlex/S2 are free; only the claim-support audit spends
LLM tokens) and the easiest to price per call. The full review is the premium follow-on,
not the door-opener.

---

## 4. Pricing models

All numbers are hypotheses to test in discovery, not commitments. Two hard constraints from
the code: (a) consumer prices were sized for only ~15–30% margin on Fable 5
(app.py:162–172), so wholesale discounts off retail are tight until real COGS data exists;
(b) `usage_ledger_dict` is empty until consumer checkout goes live — **price nothing
long-term until the ledger has real per-SKU COGS.**

### Option A — Per-call / credit packs

| Product | Est. COGS (per run) | B2B per-call range | Retail anchor |
|---|---|---|---|
| Citation verification only | ~$0.10–0.50 (APIs free; small LLM audit spend) | $0.50–$1.50 | $3 (citation-gap) |
| Deterministic checks only | ~$0.00 (no LLM) | $0.10–$0.25 | — (currently bundled) |
| Anonymity check | ~$0.20–0.60 | $0.75–$1.50 | $2 |
| Standard full review | est. $3–6 on Fable 5 (unverified) | $6–$9 | $9 |
| Deep full review | est. $6–11 (unverified) | $10–$14 | $15 |

Pros: matches the existing token mental model; the claim/consume plumbing already enforces
exactly-once per credit. Cons: revenue is lumpy; no floor.

### Option B — Subscription tiers (recommended primary model)

- **Starter — $99/mo:** 150 citation verifications OR 12 standard reviews (credit-equivalent pool), API key, email support.
- **Growth — $349/mo:** ~600 verifications / 50 reviews, webhook delivery, white-label flag, 99% monthly uptime target.
- **Platform — $999–$1,999/mo:** negotiated volume, per-tenant retention terms, DPA, named support, capacity reservation (raised `max_containers`).

The public benchmark (a niche API at ~500 subs × $29/mo ≈ $14.5k/mo) is the wrong shape for
this product — that's a self-serve long tail, and this is an outbound short head. A more
honest target: **3–8 accounts at $99–$1,000/mo ≈ $1k–$5k/mo within a year** if discovery
validates. Treat the $14.5k figure as illustrative of the category, not a forecast.

### Option C — Flat white-label license

$500–$2,500/mo (or $8k–$25k/yr) per platform for unlimited-within-fair-use usage under
their brand. Only rational once real COGS data proves the fair-use cap can't be
margin-negative — a single partner batch-running deep reviews at $6–11 COGS each could
invert the economics. Do not lead with this; offer it as the graduation tier for a proven
Growth-plan customer.

**Recommendation:** lead with B (subscription with included credits + overage at per-call
rates from A), because it matches the metered-ledger infrastructure that half-exists and
produces predictable revenue. Every number above requires customer discovery first.

---

## 5. Go-to-market

This is an **outbound, founder-sales motion** — no marketplace listing will sell a
manuscript-review API on its own. Listings (RapidAPI, Datarade; an MoR like Paddle/Lemon
Squeezy for tax if selling internationally) are distribution hygiene for later, not the
strategy.

**First three outreach targets (concrete, warm-ish):**

1. **A Zotero-ecosystem tool builder.** The repo already contains `zotero-plugin/` work — the ecosystem is known territory. Pitch: "add a 'verify references' button backed by our citation-verification endpoint; you brand it, we meter it." Wedge: L2 + bibcheck. This is also the fastest technical integration on the list (one endpoint, JSON in/out).
2. **One academic editing/proofreading firm** (mid-size, sells thesis/journal-submission packages). Pitch: white-labeled "pre-submission integrity report" as a new line item on every engagement. Start with a 20-pack of tokens **today** (zero engineering), convert to API + white-label if they reorder.
3. **One library publishing program or small OA journal platform** (university-press-adjacent, 5–50 journals). Pitch: automated desk-check — dead DOIs, hallucinated references, statcheck — on every submission, at a per-manuscript price far below one hour of editorial time. These buyers move slowly but renew forever.

**Pilot offer (same shape for all three):** 90 days, 100 free calls or 10 free full
reviews, co-designed output branding, a named feedback channel, published price honored for
12 months if they convert within the pilot. Ask in return: a reference/logo and a
15-minute integration debrief.

**Sales collateral needed (all S-effort):** a two-page API overview PDF, the security
one-pager distilled from `docs/security-paper-review.md`, and a sample white-label report
(run the pipeline on a public preprint).

---

## 6. Sequencing recommendation

### The honest caveat first

**This is the least passive of the current product ideas.** Consumer one-time checkout is
fire-and-forget; this is contracts, security questionnaires, integration support, capacity
commitments, and quarterly check-in calls. Every SLA signed converts "semi-passive
licensing" into an on-call obligation for a solo operator. The engine is genuinely
license-worthy — the seven-persona panel, deterministic checks, and injection-hardened
pipeline are a real moat — but the revenue is earned with sales time, not compounding
quietly. Budget accordingly: expect ~2–4 hours/week per active account, indefinitely.

### What must be true before investing engineering time

1. **Consumer checkout is live and the usage ledger has ≥ 50 real jobs** — otherwise B2B pricing is guesswork on top of guesswork (the runbook itself flags current prices as provisional).
2. **At least two discovery conversations per archetype in §3's top 3, and at least one party willing to sign a paid pilot or buy a token pack.** Token packs are the discovery instrument: if a firm won't spend $150 on 20 reviews, they won't spend $349/mo on an API.
3. **Anthropic rate limits and Modal cost ceilings are confirmed** for 5–10× current `max_containers` before any SLA language is offered.

### Phases

**Phase 0 — Validate (0 engineering, 2–4 weeks of conversations).**
Sell token packs manually to 2–3 prospects (the `direct_token` email flow already supports
out-of-band distribution). Run discovery on pricing model A vs B. Kill criterion: no paid
pilot interest after ~10 conversations → shelve this scope and keep the engine consumer-only.

**Phase 1 — MVP API (roughly 3–5 weeks of part-time engineering).**
Items 1, 3, 5, 6 from §2: manually-issued API keys, per-key quotas, `branding=none`,
`format=json` structured output, OpenAPI spec + minimal docs page. Reuse the existing
submit/status endpoints under an `/v1/` prefix rather than building parallel routes. Billing
stays semi-manual (monthly invoice generated from the ledger — item 2's S-half only).

**Phase 2 — White-label & scale (only after 2+ paying tenants).**
Items 2 (full Stripe metering), 4 (tenant isolation hardening), 7 (webhooks), 8 (dashboard),
9 (capacity + status page). Consider marketplace listings and an MoR here, not before.

**Phase 3 — Optional platform play.**
Flat licenses (Option C), per-tenant domain modules, batch endpoints for journal-platform
desk-check queues. Only if Phase 2 tenants are pulling for it.

### Bottom line

The engineering gap is smaller than it looks — the engine, cost accounting, safety stack,
and even a proto-credit system already exist; the genuinely new pieces are API keys, a JSON
output contract, and billing aggregation. The market gap is bigger than it looks — every
dollar here is sold outbound. Validate with token packs before writing a line of API-key
code.
