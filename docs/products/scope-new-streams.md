# Scope: Three New Semi-Passive Revenue Streams — MuscleOnGLP / Purplelink LLC

Status: scoping only. No code changed, no deploy run. Date: 2026-07-16.

Purpose: evaluate three revenue streams that reuse assets already built and
shipped, keep the strictly research-focused / educational-science brand intact,
and reach first dollar with the least net-new work and lowest brand risk.

## Non-negotiable brand frame (applies to all three)

Content stays neutral, evidence-based, educational. Never diets, body-shaming,
before/after or "transformation" framing, weight-loss hype, or supplement hype.
Affiliate strategy stays equipment/tools, never supplements. Every monetized
artifact carries the standing disclaimer already drafted in
`muscleonglp-site/DISCLAIMER-draft.md` ("general educational content only… not
medical advice… no doctor–patient relationship… AI-assisted content"). The
research pipeline's own disclaimer string lives in
`backend/research_digest/renderer.py` (`DISCLAIMER`) and must ride along with
any licensed feed verbatim.

---

## What already exists (grounded inventory)

### The research pipeline — `backend/research_digest/`

| Asset | File / symbol | What it produces |
|---|---|---|
| Harvester | `harvester.py` → `Paper` dataclass, `harvest_all()` | Weekly pull from PubMed E-utilities + Europe PMC, deduped by DOI/PMID/title. Each `Paper`: `title, authors, source, is_preprint, venue, pub_date (YYYY-MM-DD), url (canonical DOI/PubMed), abstract, doi, pmid`. Query is drug-term AND muscle-term (`sources.py` `core_query()`), incl. next-gen multi-agonists. |
| Curator | `curator.py` → `curate()` | Single LLM pass. Per paper: `relevance` 0–3 (kept only if ≥2), `summary` (2–4 sentences, abstract-only, IRON-RULE constrained), `why_it_matters` (1 sentence, reader-tail trimmed), `action` (closed 4-lever vocabulary — protein / training / monitor / clinician — with `_ACTION_BAN` regex that DROPS anything prescriptive). Plus a weekly `intro`. 2–8 items/week. |
| Data model | `models.py` → `DigestItem`, `WeeklyDigest` | `DigestItem = {paper, relevance, summary, why_it_matters, action}`. `WeeklyDigest = {date, week_label, slug, intro, items[]}`. This is the exact structured record a buyer would license. |
| Renderer | `renderer.py` → `render_post_html`, `render_hub_html`, `_json()` | Currently serializes the digest to HTML + JSON-LD only. A JSON serializer helper (`_json`) already exists. |
| Publisher | `publisher.py` → `write_into()` | Maintains `research/index.json` — but only a THIN manifest per week: `{slug, week_label, date, count, blurb}`. The rich per-item fields are rendered into HTML and then effectively discarded. |
| Cron | `app.py` | Modal cron, Mondays 13:00 UTC. `DRY_RUN` path already returns rendered artifacts in-memory without deploying — a ready-made hook for producing an export. |
| Mailer | `mailer.py` → `notify_review()` | Resend email, but only to Ben as a review copy (`ben@purplelink.llc`), from `guides@purplelink.llc`. Not to subscribers. |

Key finding: the pipeline **already generates** a per-paper structured record
(summary + why + non-prescriptive action + full citation metadata) every week
for free, then throws away everything except a 180-char blurb. Stream 1 is
mostly a serialization + exposure problem, not a content problem.

### The site commerce + email infra — `muscleonglp-site/`

| Asset | File | What it does |
|---|---|---|
| Email capture | `netlify/functions/subscribe.mjs` + `subscribe.js` | POSTs to Buttondown, tags `cheat-sheet` + source, rate-limited, idempotent on already-subscribed. Free cheat-sheet magnet (`/assets/glp1-muscle-cheatsheet.pdf`). |
| Checkout | `netlify/functions/checkout.mjs` | Stripe Checkout session creator, origin allowlist, per-IP daily limit, idempotency key, records TOS acceptance in Netlify Blobs BEFORE returning the pay URL. |
| Product map | `netlify/functions/lib/products.mjs` → `PRODUCTS` | Single source of truth: 6 products (`muscleonglp-guide` $5, `complete-pack` $9, plus four $1 mini-guides), each `{envKey (Stripe Price), successPath, title, file}`. |
| Gated delivery | `netlify/functions/download.mjs` | Only path to a paid PDF. Verifies Stripe session paid + TOS record exists, streams the file from `guide-files` Netlify Blobs store (files never on public URL). |
| Written content | `learn/` (10 articles) + `guides/` (4 mini-guides) | ~24,000 words of published, cited educational content (article word counts 796–2,929; mini-guides 7–8 pp each). Repackage-ready raw material. |

Current product ladder (live): $1 mini-guides → $5 core handbook (30pp) →
$9 Complete Pack (60pp, "best value"). Slots for a $12–39 tier are open above
the current ceiling.

---

## Stream 1 — License the curated research feed as a data product

### Reusable vs. net-new

| Reusable (built) | Net-new |
|---|---|
| Full harvest + curate + structured-record generation (`harvester.py`, `curator.py`, `models.py`) runs weekly at ~zero marginal cost. | A JSON serializer for `WeeklyDigest`/`DigestItem` (trivial — `_json` pattern already in `renderer.py`). |
| `DRY_RUN` in `app.py` already returns in-memory artifacts — a natural export hook. | A stable public schema + versioning, an archive store (accumulate weeks, not just latest), and access control (API key or gated URL). |
| Disclaimer string (`renderer.py DISCLAIMER`) travels with the data. | A licensing agreement + "research summary, not medical advice, no redistribution" terms. Buyer onboarding (manual at first). |
| Netlify Functions + Blobs pattern (`download.mjs`) is a working template for a gated, key-checked endpoint. | Billing (Stripe recurring, or invoice for institutional buyers). |

### Buyers and why they pay

| Buyer | Job-to-be-done | Why they pay vs. DIY |
|---|---|---|
| Registered dietitians / GLP-1-focused RDs | Stay current for client work without reading PubMed weekly | Time. A vetted, plain-language, cited weekly feed replaces hours of scanning. |
| Telehealth GLP-1 clinics | Clinician-facing "what's new" internal brief; patient-education content | Turnkey, neutral, already disclaimered; cheaper than a medical writer. |
| Supplement / nutrition companies (R&D + market monitoring, NOT for us to hype) | Competitive/scientific intelligence on the muscle-preservation category | Structured, filtered signal in their exact niche; hard to buy elsewhere. |
| Health-tech / GLP-1 app platforms | Embed a "latest research" module | Licensed structured JSON drops straight into a content module. |
| Pharma competitive-intelligence teams | Track muscle/lean-mass literature around incretin drugs incl. next-gen agonists | The `sources.py` query already covers survodutide/retatrutide/CagriSema etc. — narrow, relevant, deduped. |

### Delivery + pricing

Offer three delivery formats off the same JSON:

| Format | Fit | Effort |
|---|---|---|
| **JSON API / gated URL** (key-checked Netlify Function returning current + archived weeks) | Health-tech, pharma CI, app platforms | The technical core. Mirror `download.mjs` auth pattern. |
| **Emailed weekly brief** (richer than the public post; full items, earlier) | RDs, clinics | Reuse `mailer.py` send path; swap recipient + template. |
| **Notion / Airtable mirror** (push the JSON into a shared base) | Non-technical RDs, small clinics | Thin sync script; lowest buyer friction. |

Pricing (recurring, invoice or Stripe):

| Tier | Price | For |
|---|---|---|
| Practitioner | $29–49 / mo | Solo RD / small clinic — emailed brief + read-only Notion/Airtable |
| Team | $149–299 / mo | Clinic / app team — JSON API, up to N seats, full archive |
| Enterprise / CI | $500–1,500 / mo (annual) | Supplement R&D, pharma CI — API + archive + custom query terms, licensed for internal use |

Reasoning: institutional CI feeds in a defined niche support 3–4 figures/mo;
practitioner tier is priced as a professional tool (below a journal
subscription, above a newsletter). Recurring beats one-time for passive income.
Start with 1–2 hand-sold enterprise/practitioner deals (concierge, invoice) to
validate before building self-serve billing.

### Effort: **M** (serialization + archive + a gated endpoint is small; licensing terms, buyer onboarding, and sales are the real cost).

### Compliance / brand guardrails
- License as **research summary, not medical advice**; disclaimer travels with every payload.
- Contract must bar the buyer from **representing the feed as our clinical endorsement** or re-selling raw records.
- Explicitly **do not** let a supplement buyer's use pull the public brand toward supplement hype — the feed is the same neutral records we publish; we never tailor "action" lines to a customer's product.
- The `action` field's `_ACTION_BAN` guard (`curator.py`) is a selling point: prove the feed cannot emit dosing/drug-switch language.
- Keep source attribution intact — every record already links DOI/PubMed; never strip provenance.

---

## Stream 2 — Paid premium email tier

### Reusable vs. net-new

| Reusable (built) | Net-new |
|---|---|
| Buttondown list + capture (`subscribe.mjs`), free cheat-sheet magnet, tagging by source. | A paid tier. Buttondown supports paid subscriptions natively (Stripe-backed) — enable it, or gate a `premium` segment. |
| The full weekly `WeeklyDigest` (more items + `intro` + per-item `why`/`action`) already generated in `app.py`. | An automated subscriber send of the digest (today `mailer.py` emails only Ben). Wire the digest to a Buttondown broadcast / paid segment. |
| Resend send path (`mailer.py`) as a template if not using Buttondown's sender. | Free-vs-paid content split + archive access for paying members. |

### Free vs. paid split (keep free a strong funnel)

| Free (funnel) | Paid ($5–8 / mo or $40–60 / yr) |
|---|---|
| Monthly-ish roundup email, top 2–3 papers, summary + why | Every-week send, all 2–8 curated papers with `why` + `action` |
| Link to the public `/research/` post | Full searchable archive of past weeks |
| Cheat-sheet magnet | Earlier access (send before the public post goes live) |
| — | Occasional deeper synthesis (theme write-ups across several weeks) + subscriber-only Q&A digest |

The free tier stays genuinely useful (it must keep feeding the list and SEO),
but the paid tier trades on **completeness, cadence, archive, and timing** —
all near-zero marginal cost because the digest is already produced weekly.

### Pricing
$5/mo or $45/yr (annual discount nudges to recurring). Price it as "less than a
coffee to keep up with your meds' research." Near-zero marginal cost per
subscriber: the content exists the moment `curate()` runs; a paid send is one
more broadcast.

### Effort: **S–M** (S if using Buttondown's built-in paid subscriptions; M if building segmented sends + archive gating).

### Compliance / brand guardrails
- Same disclaimer in every send; never imply the paid tier is personalized medical advice.
- Paid content is **more of the same neutral summaries**, never "insider protocols" or hype — the value is cadence/archive, not a different (riskier) editorial voice.
- Honor unsubscribe + clean refund path; keep the free tier honestly valuable so paid never feels like a paywall on safety information.

---

## Stream 3 — Digital product ladder off the existing guides

### Reusable vs. net-new

| Reusable (built) | Net-new |
|---|---|
| Stripe checkout + gated PDF delivery + TOS gate (`checkout.mjs`, `download.mjs`, `products.mjs`) — adding a PDF product = one entry in `PRODUCTS` + a Stripe Price + upload to `guide-files` Blobs. | The product artifacts themselves (trackers, logs, workbooks). |
| ~24,000 words of published `learn/` + `guides/` content to repackage (protein targets, exercise progressions, monitoring signs, off-ramp). | Notion/Airtable interactive templates (don't fit the single-PDF Blobs path). |
| Existing covers/asset pipeline (`assets/cover-*.png`) and success-page pattern (`success/`). | A second storefront for non-PDF templates (Gumroad or Lemon Squeezy). |

### Which products (all reuse written content)

| Product | Built from | Format | Price |
|---|---|---|---|
| Protein & training log (printable) | `learn/protein-on-glp1`, `best-exercises-…` | PDF — fits existing Stripe/Blobs path exactly | $12 |
| Muscle-preservation workbook (12-week) | `no-gym-plan` + `best-exercises` progressions | PDF | $19 |
| GLP-1 muscle tracker (Notion template) | `signs-of-muscle-loss`, monitoring cues | Notion duplicate link | $19–29 |
| Off-ramp planner (workbook + checklist) | `muscle-after-stopping-ozempic`, `off-ramp` guide | PDF | $19 |
| "Everything" bundle | all of the above + Complete Pack | mixed | $39 |

### Platform

- **PDF printables/workbooks → reuse existing Stripe infra.** Add to `PRODUCTS`, create a Stripe Price, upload the file to `guide-files`. Zero new platform, same TOS gate, same download flow. This is the cheapest path and keeps everything under Purplelink LLC's existing Stripe account.
- **Notion/Airtable interactive templates → Gumroad** (built-in discovery/SEO, simplest) **or Lemon Squeezy** (Merchant-of-Record, auto-handles global VAT). Use Lemon Squeezy if selling into the EU/global at volume; Gumroad to start for the discovery surface. The existing Blobs path can't serve a Notion "duplicate" link, so a light second storefront is justified here.

### Cross-sell into the handbook
Every product's success page (pattern already in `success/`) and its own footer
links up-ladder: printable/tracker ($12–19) → Complete Pack ($9 as an add-on
sounds odd, so instead) → position the $39 bundle as the anchor and the $5–9
handbook/pack as the entry rung. Each `learn/` article that sources a product
gets a contextual "companion tracker" CTA, turning existing SEO traffic into
product views.

### Effort: **S** for PDF printables/workbooks (content exists, infra exists); **M** for Notion templates + a new storefront.

### Compliance / brand guardrails
- Trackers/logs are **neutral self-monitoring tools**, never "shred" / transformation / calorie-restriction framing. A protein log tracks protein; it does not prescribe a deficit.
- Same medical disclaimer front-matter (`DISCLAIMER-draft.md`) in every file.
- No before/after fields, no goal-weight shaming prompts — track strength, lean-mass proxies, protein, training adherence (the four neutral levers), not body-shame metrics.
- Keep pricing honest ($12–39 is the validated range; don't inflate a repackaged PDF).

---

## Sequencing across the three

| Stream | Effort | Time-to-first-dollar | Marginal cost | Brand risk | Recurring? |
|---|---|---|---|---|---|
| 1 — Feed licensing | M | Medium (needs a buyer conversation) | ~0 | Low–Med (contract controls misuse) | Yes (best) |
| 2 — Paid email | S–M | Medium (needs list size to convert) | ~0 | Low | Yes |
| 3 — Digital products | S (PDF) | **Fast** (list + SEO traffic already arriving) | ~0 after authoring | Low | No (one-time) |

Recommended order:

1. **Stream 3 (PDF printables/workbooks) first** — fastest to a live SKU, reuses both the content and the exact commerce infra, first dollar in days.
2. **Stream 2 (paid email)** next — flip on Buttondown paid + wire the already-generated weekly digest to subscribers; converts the same audience Stream 3 is warming, adds recurring revenue at zero marginal cost.
3. **Stream 1 (feed licensing)** as the higher-ceiling play — start concierge (1–2 hand-sold practitioner/CI deals on invoice) in parallel once the JSON export exists; build self-serve billing only after validation.

---

## Recommendation: do Stream 3 (digital-product ladder) first

Fastest path to first dollar at lowest brand risk:

- **Infra is already live and proven.** A new PDF product is literally one entry in `PRODUCTS` (`lib/products.mjs`), one Stripe Price, and one file uploaded to the `guide-files` Blobs store — the `checkout.mjs` → TOS gate → `download.mjs` flow already works for the $1–9 catalog.
- **The content already exists.** ~24,000 words across `learn/` and `guides/` cover exactly the protein/training/monitoring/off-ramp material a tracker or workbook repackages. Authoring is reformatting, not research.
- **Traffic is already arriving.** The SEO articles and the email list are live funnels; a $12–19 companion tracker monetizes visitors who are already on the page.
- **Lowest brand risk.** A neutral self-monitoring log/workbook sits squarely inside the evidence-based frame with the existing disclaimer — no new editorial voice, no redistribution contract, no medical-advice exposure beyond what's already shipped.
- **It de-risks the others.** Shipping products validates willingness-to-pay and grows the list, which is exactly the precondition Stream 2 (paid email) and Stream 1 (needs a warm audience + a serialized archive) both depend on.

Start with the **printable protein & training log at $12** and the **12-week
workbook at $19**, cross-sold from the `learn/` articles they're built from and
bundled with the Complete Pack at a $39 anchor. Then turn on the paid email
tier, and pursue feed-licensing deals concierge-style once the JSON export is
in place.
