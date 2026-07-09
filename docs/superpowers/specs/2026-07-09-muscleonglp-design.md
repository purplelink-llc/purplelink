# MuscleOnGLP — Design

## Context

Follows a market-research pass (session history, not a separate artifact) into MicroSaaS
and consumer-content opportunities. The original idea ("SEO/GEO-optimized site selling
cheap PDF workout routines for all kinds of people") was narrowed after research showed:

- Generic workout-PDF categories (C25K, glute programs, general strength) are saturated
  and dominated by free, authoritative content (Jeff Nippard, Bret Contreras, Muscle &
  Strength, the original C25K.com) — ruled out as separate niches.
- Etsy's digital-workout-plan categories already carry 5,000+ listings each — confirms
  the saturation signal found independently in r/passive_income research ("PDFs are
  dead" sentiment).
- The GLP-1 (Ozempic/Wegovy/Mounjaro/Zepbound) muscle-preservation angle is a real,
  timely, currently-underserved wedge: 11% of US adults are on a GLP-1 as of mid-2026
  (tripled from 3% in 2024, per Gallup), and lean-mass loss during GLP-1 use is a
  documented clinical problem, not a manufactured one. Existing coverage is fragmented
  across personal-training-studio blogs and major health publishers rather than a
  dedicated, well-productized content storefront.
- Gray-market/compounded GLP-1 sourcing or dosing guidance was explicitly considered and
  rejected: FDA removed semaglutide and tirzepatide from the drug shortage list in 2025,
  narrowing compounding pharmacies' legal basis; FDA/FTC have issued active warnings
  about counterfeit product; steering readers toward suppliers would create real
  liability and likely violate Stripe/AdSense terms. This product stays strictly in the
  exercise/protein-guidance lane.

## Product

**MuscleOnGLP** — a standalone consumer brand (own domain, `muscleonglp.com` or similar,
availability to be confirmed at registration time) selling a single flagship PDF guide:
a resistance-training and protein-intake protocol for preserving lean mass while on a
GLP-1 medication. Priced at $5 or less. Sold simultaneously through three channels:
direct Stripe checkout on the domain, a Gumroad listing, and an Etsy listing — all three
selling the identical PDF file.

Four SEO/GEO landing pages front the same guide, one per drug (Ozempic, Wegovy,
Mounjaro, Zepbound). Each page carries genuinely distinct content and angle (matched to
that drug's specific body-composition data where it differs — e.g. tirzepatide's
different lean-mass-loss fraction versus semaglutide's) rather than a templated
find-and-replace across four near-identical pages, to avoid both a poor reader
experience and Google's programmatic-SEO/thin-content risk.

## Decisions

- **Entity**: ships under Purplelink LLC — same legal entity, same Stripe account. No
  new business formation. No visible branding link between MuscleOnGLP and Purplelink on
  the public-facing site.
- **Distribution channels**: all three simultaneously from day one — own domain (direct
  Stripe checkout, keeps full margin), Gumroad, and Etsy (marketplace distribution,
  despite known category saturation — accepted tradeoff for reach versus relying solely
  on unproven SEO).
- **Catalog scope (v1)**: a single flagship guide, not a full drug-times-goal matrix.
  Chosen over a larger initial catalog because (a) the product's actual demand is
  unvalidated, and (b) publishing many thin/near-duplicate pages before any one is
  proven risks a Google Helpful Content-style penalty. Expand the catalog only once
  real conversion data exists.
- **Content voice**: written in an academic, citation-forward register (full
  application of the `benampel` writing-style skill, not a lighter tone-neutral pass),
  deliberately trading the breezy tone of most competing consumer fitness content for a
  register that reads as rigorous and credible. Every substantive claim in the guide
  must trace to a specific cited source.
- **Content sourcing**: peer-reviewed sources preferred; a preprint (e.g. a medRxiv or
  Research Square article) may be cited only if explicitly labeled as a preprint in the
  guide's own text, never presented as peer-reviewed. No citation ships without a real,
  verifiable DOI or PMID.
- **Content generation**: fully LLM-generated (no human-authored draft), subject to four
  sequential red-team review passes before anything is finalized (see Content Pipeline).
- **Legal/scope boundary**: no content on sourcing, obtaining, or dosing compounded or
  gray-market GLP-1 product, under any circumstance. Guide content addresses exercise
  and nutrition only, for readers already using a GLP-1, with a standard "not medical
  advice, consult your prescriber" disclaimer.

## Content Grounding (research gathered during brainstorming)

Real, cited findings to ground the flagship guide, gathered via live web research (not
fabricated):

- **STEP 1 trial** (semaglutide, DEXA-measured): lean mass fell approximately 13.2% from
  baseline, accounting for 45.2% of total weight lost. ([Neeland et al., Diabetes,
  Obesity and Metabolism, 2024](https://dom-pubs.onlinelibrary.wiley.com/doi/10.1111/dom.15728))
- **SURMOUNT-1 trial** (tirzepatide): lean mass fell approximately 10.9% from baseline,
  accounting for 25.7% of total weight lost — a meaningfully lower fraction than
  semaglutide's, a nuance most consumer content flattens away and this guide should
  preserve.
- A routine-care digital-phenotyping analysis found tirzepatide associated with greater
  relative lean-body-mass loss than semaglutide at 3/6/9/12 months. **This is a
  preprint** (medRxiv, 2026) and must be labeled as such if cited.
- Lean-mass-retention research consistently supports a higher-protein target of
  1.6–2.4 g/kg bodyweight per day during weight loss.
- ACSM resistance-training guidance: 2-3 sessions per week, 8-12 exercises per session,
  2-3 sets of 8-15 reps at 60-80% of one-rep max.
- An actively enrolling registered trial addresses this exact question: [NCT06885736 —
  "LEAN Mass Preservation With Resistance Exercise and Protein During
  Semaglutide/Tirzepatide Therapy"](https://clinicaltrials.gov/study/NCT06885736) — worth
  citing as evidence this is a live, active area of clinical research rather than
  settled or niche.

## Architecture

- **PDF generation**: a one-time content-production pipeline, not a recurring cron —
  the guide is authored once, red-teamed, and then shipped as a static asset. Likely
  Python + WeasyPrint or a LaTeX pipeline, reusing patterns already present in
  Purplelink's manuscript tooling, to produce a properly typeset PDF rather than a plain
  document export.
- **Site**: a static Netlify site matching Purplelink's existing deploy pattern — a home
  page plus four drug-specific landing pages, Stripe Checkout wired for direct purchase,
  and outbound links to the Gumroad and Etsy listings.
- **Fulfillment**: Stripe webhook → Modal function → emails the PDF via Resend (already
  wired into Purplelink's backend) along with a direct download link. No login or
  customer dashboard for a single static product.
- **Gumroad/Etsy listings**: created and maintained manually, not API-synced. No
  automation is justified for two listings of one static product.
- **Red-team pipeline**: four sequential LLM review passes run once against the drafted
  guide before anything is finalized:
  1. **Medical/safety accuracy** — every claim checked against its cited source; no
     unsupported health claims; correct "not medical advice" framing.
  2. **FTC/legal compliance** — no deceptive or implied-endorsement health claims;
     disclaimers appropriate for a health-adjacent consumer product.
  3. **Voice pass** (`benampel` skill) — confirms the academic, citation-forward register
     and catches generic AI phrasing, buzzwords, and aphoristic cadence.
  4. **Originality/non-derivative check** — compares against existing published guides
     (Cleveland Clinic, personal-training-studio content already in market) to confirm
     the guide isn't derivative.
  Each pass either approves the draft or returns specific required edits; the draft
  loops through a pass again after edits until all four pass cleanly.

## Error Handling

- **Stripe webhook succeeds, delivery email fails**: the webhook handler logs the
  failure and retries; given expected low volume, a manual fallback (checking the
  Stripe dashboard for a payment with no corresponding delivery record) is an acceptable
  backstop rather than building a full delivery-retry queue.
- **Red-team pass conflict** (e.g. the safety pass wants more specific language that the
  originality pass flags as too close to a source): the safety pass wins outright; the
  content gets rewritten to satisfy both, never the reverse.
- **Citation drift**: because this is static, one-time content rather than a live feed,
  a periodic manual check (not per-sale) that cited figures still match their source is
  sufficient.

## Testing

- No traditional unit-test suite — this is content, not application logic. "Testing"
  here means the four-pass red-team loop itself, which functions as the correctness
  check on the guide's claims and voice.
- One manual end-to-end purchase test (a real Stripe test-mode payment confirming the
  email and PDF actually arrive) before going live across all three channels.

## Explicitly Out of Scope (for this design pass)

- Expanding beyond the single flagship guide to a fuller drug-times-goal catalog.
- A dashboard or customer login system.
- API-syncing the Etsy and Gumroad listings with the primary site.
- Subscription or recurring pricing.
- Any content addressing sourcing, obtaining, or dosing of compounded or gray-market
  GLP-1 medication — ruled out for legal/liability reasons independent of this design.
