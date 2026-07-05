# Multi-State Labor-Law Compliance Tracker — Design

## Context

A 9-way MicroSaaS market research pass (documented in session history, not a separate
artifact) evaluated candidate ideas across watches, class-action matching, domain
arbitrage, grant matching, M&A due-diligence, salary benchmarking, podcast clipping, SEO
auto-fix, and legal-deadline calculation. Eight of nine were saturated, already dominated
by well-funded incumbents, or structurally not viable for a solo operator (either a
crowded market with an entrenched leader, or — in the legal-deadline case — not actually
a software business at all, since it requires a standing legal-research operation and
carries malpractice-level liability).

The ninth — a compliance-change alert tool for small businesses — was the standout: cheap
public data access, a proven price point from real market comparables (TaxJar $19/mo,
NexusMonitor $19-69/mo), and a specific, named, currently-underserved wedge: multi-state
labor law for very small employers (5-50 employees), which today is only sold bundled
inside expensive full HR platforms (Mineral, Zenefits) rather than as a standalone
product.

## Product

A subscription tool that monitors labor-law changes (minimum wage, paid sick leave, pay
transparency, final-paycheck timing, and similar categories) across all 50 states plus
federal, and alerts a specific small business only when a change actually applies to
their profile (which states they have employees in, headcount, industry) — not a generic
firehose of every regulatory change everywhere.

## Decisions

- **Entity**: ships under Purplelink LLC (same legal entity, same Stripe account), not a
  new separate company.
- **Domain/branding**: lives at a subdomain of purplelink.llc (e.g.
  `compliance.purplelink.llc`), with its own distinct visual tone suited to a
  small-business audience, separate from Purplelink's academic-tools identity — but
  sharing hosting/deploy tooling.
- **Jurisdiction scope**: all 50 states + federal from day one (not a narrower
  high-activity-states-only launch). This is a deliberately larger scope than the
  minimal-MVP alternative and should be understood as raising both data-ingestion
  surface area (50 state sources to scrape/normalize, not 5) and cost (LegiScan's
  full-national tier, roughly $1,000/yr per the market research, versus ~$25/yr for a
  single state) relative to a narrower launch.
- **Delivery**: both an email digest and a web dashboard (not email-only). The dashboard
  requires its own lightweight authenticated frontend, which is real, additional build
  scope beyond a pure email-cron product.
- **Classification validation**: fully automated from day one, with no human
  review gating individual sends. This raises the stakes on the error-handling design
  (see below) since there is no manual backstop before a customer sees an alert (or
  fails to see one).

## Architecture

Four independent stages, each with one job:

```
[Ingestion: cron jobs]          [Classification: two-stage]        [Delivery]
Federal Register API   ─┐
LegiScan API (50 states)─┼──▶ raw items ──▶ Stage 1: tag with     ──▶ Stage 2: match
State DOL page scrapers ─┘      structured metadata (state,           against each
                                 topic, headcount threshold,           customer's stored
                                 effective date) — run ONCE            profile via
                                 per item, customer-agnostic           structured filter
                                                                        │
                                                                        ▼
                                                              confirmed matches ──▶
                                                              LLM writes plain-English,
                                                              business-specific alert,
                                                              grounded in source text
                                                                        │
                                                                        ▼
                                                          Email digest + dashboard entry
```

1. **Ingestion** — scheduled Modal cron jobs pull raw regulatory items daily from three
   source types (Federal Register API, LegiScan API, scraped state DOL announcement
   pages) into a shared raw-items store, deduplicated by `(source, source_ref)`.
2. **Stage 1 — tagging** — runs once per raw item, independent of any customer.
   Produces structured metadata: jurisdiction, topic category, any numeric threshold
   (e.g. headcount), effective date, and the tagger's own confidence score. This is the
   per-item-expensive, aggregate-cheap step — cost scales with regulatory volume, not
   with customer count.
3. **Stage 2 — matching + alert generation** — runs per customer profile against the
   tagged item backlog. Whether an item is relevant to a given customer is decided by
   pure structured filtering (state overlap, headcount threshold) with **no LLM call**.
   Only on a confirmed match does an LLM write the customer-facing explanation, grounded
   in the item's raw source text so the alert can cite exactly what changed.
4. **Delivery** — matched, written alerts are emailed as a digest (not real-time) and
   persisted to an authenticated dashboard the customer can browse/search.

This shape means adding customers does not multiply LLM cost against the full
regulatory-item backlog — the expensive classification work happens once per item,
and per-customer cost is a cheap filter query plus, only on a real match, one
alert-writing LLM call.

## Data Model

**`RegulatoryItem`** — one row per raw ingested item.
- `id`, `source` (`federal_register` / `legiscan` / `state_dol_scrape`), `source_ref`,
  `raw_text`, `published_date`, `ingested_at`.
- Deduplicated on `(source, source_ref)`.

**`ItemTag`** — Stage 1 output, one-to-many with `RegulatoryItem` (a single item can
produce zero, one, or multiple tags if it bundles several topics).
- `item_id`, `jurisdiction` (state code, or city+state for local ordinances), `topic`
  (enum: `minimum_wage` / `paid_sick_leave` / `pay_transparency` / `final_paycheck` /
  `other`), `headcount_threshold` (nullable int), `effective_date`, `confidence`
  (float; low-confidence tags are logged for periodic manual spot-checking rather than
  silently trusted or silently dropped, per the error-handling section below).

**`CustomerProfile`**
- `customer_id`, `states[]`, `headcount`, `industry` (a small set of broad categories,
  mainly relevant for industry-specific rules), `created_at`, `active`.

**`Alert`** — Stage 2 output, one per confirmed customer↔item match.
- `customer_id`, `item_id`, `matched_on` (which tag triggered it), `written_summary`
  (LLM-generated plain-English explanation + action item, grounded in `raw_text`),
  `sent_at`, `digest_id`, `feedback` (nullable thumbs-up/down from the customer, used to
  build an ongoing accuracy signal).

The key property: `ItemTag` is customer-agnostic and computed exactly once per item;
`Alert` is the only customer-specific object, and computing whether one should exist at
all is a cheap database filter, not an LLM call.

## Tech Stack & Hosting

Reuses Purplelink's existing, already-proven infrastructure rather than introducing new
platforms:

- **Backend & scheduled jobs**: Python on Modal, matching the existing digest/sweep cron
  job pattern already live in Purplelink's backend.
- **Database**: the one genuinely new piece of infrastructure this project needs.
  Purplelink's existing paid tools use ephemeral Modal Dicts because they only need
  short-lived tokens; this product needs real relational queries (customers by state,
  items by jurisdiction+topic, join history for the dashboard), so it needs an actual
  Postgres database. Recommendation: a hosted Postgres provider with a free tier
  sufficient for early-stage volume (e.g. Neon), not Modal Dicts.
- **Email delivery**: reuse Resend, already wired into Purplelink's backend.
- **Billing**: reuse the existing Stripe account; new Products/Prices for this offering;
  same Netlify checkout-function pattern already live on purplelink.llc.
- **Dashboard auth**: magic-link email login (no passwords) — matches the low-friction
  expectation of a busy small-business owner and avoids building/maintaining a password
  reset flow for a solo-operator project.
- **Frontend**: static marketing site + a lightweight authenticated dashboard, hosted on
  Netlify, at a subdomain of purplelink.llc with its own visual tone for a small-business
  audience.

## Error Handling

- **Silent scraper breakage** — a state DOL page changes structure and a scraper starts
  returning zero new items. Because classification is fully automated with no per-send
  human review, a broken scraper causes *silence*, not an obviously-wrong alert — which
  is worse, since nobody notices on their own. Each ingestion job tracks its own
  historical item-count baseline and alerts the operator (not the customer) if a source
  goes quiet longer than its normal cadence.
- **False negatives (missed relevant changes)** — the most damaging failure mode, since a
  customer has no way to know they weren't told about something real. Low-confidence
  Stage 1 tags are logged for periodic manual spot-checking rather than silently dropped
  or silently trusted, giving an ongoing accuracy signal without gating every individual
  send.
- **False positives (irrelevant alerts)** — recoverable but erodes trust over time. Every
  alert cites the raw source text it was grounded in so a customer can sanity-check it
  quickly, and each alert carries a thumbs-up/down that feeds a running accuracy log.
- **Source API outages** — ingestion jobs skip and retry a failed source independently
  rather than failing the whole day's run; a partial ingestion is preferred over none.
- **Mid-cycle profile changes** — a customer adding a state or changing headcount applies
  to the next matching run immediately, not at a billing-cycle boundary.

## Testing

- Deterministic unit tests for the Stage 2 filter logic (state overlap, headcount
  threshold, topic matching) — no LLM involved here, so it should be tested exhaustively
  like any other business logic.
- A small "golden set" of real historical law changes with known-correct
  classifications, used to evaluate the Stage 1 tagger's accuracy before trusting a
  prompt change in production, re-run whenever that prompt changes.
- A recurring manual audit (weekly, in the early period) sampling a slice of what
  actually got sent, specifically hunting for the false-negative failure mode above,
  since it is invisible otherwise.

## Explicitly Out of Scope (for this design pass)

- Non-labor-law compliance categories (sales tax nexus, licensing/permits) — the market
  research found labor law specifically to be the underserved wedge; other categories are
  a possible future expansion, not part of this design.
- Slack/Teams delivery — email + dashboard only for now.
- Per-send human review gate — deliberately not part of this design per the automated-
  from-day-one decision; the error-handling section's spot-checking is a lighter-weight
  substitute, not a gate.
- Detailed onboarding UX/copy, pricing-page design, and the specific LLM prompts for
  Stage 1/Stage 2 — these are implementation-plan-level detail, not architecture.
