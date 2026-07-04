---
score: 25
total: 40
p0: 0
p1: 2
p2: 3
p3: 2
timestamp: 2026-07-04T00-39-44Z
slug: site-tools-paper-review-index-html
---
Method: dual-agent (A: a102a77dcbd180439 · B: a0040c8955ab2cbca)

## Design Health Score

| Heuristic | Score | Note |
|---|---|---|
| Visibility of system status | 2/4 | No visible "opening secure checkout…" state on click |
| Match between system and real world | 3/4 | Persona framing maps to real review-process actors |
| User control and freedom | 2/4 | Sample-report drawer helps, but no edit/preview step post-upload |
| Consistency and standards | 3/4 | Shares `pr-*` classes and structure with the other two pages |
| Error prevention | 2/4 | File constraints only in collapsed FAQ, not near upload control |
| Recognition rather than recall | 3/4 | Four-layer breakdown fully spelled out |
| Flexibility and efficiency of use | 2/4 | No returning-buyer shortcut; volume-pack pricing asks for mental math pre-conversion |
| Aesthetic and minimalist design | 3/4 | Restrained, but "How the review works" list runs unconstrained line length |
| Help recognize/diagnose/recover from errors | 2/4 | Refund policy buried in FAQ, not near CTA |
| Help and documentation | 3/4 | FAQ genuinely specific, not filler |
| **Total** | **25/40** | Lowest cognitive-load score of the three pages, concentrated in the tier picker |

## Anti-Patterns Verdict

- **CLI detector — `numbered-section-markers` (1 finding): confirmed FALSE POSITIVE.** Assessment B read the actual source lines: the flagged "numbers" were "under 10 minutes," a "$11" price label, and bracketed citation markers (`[11]`, `[12]`) inside a sample-output block — not real 01/02/03 section-numbering UI. No action needed.
- **CLI detector — em-dash count anomaly (unresolved):** detector reported 18 em-dashes; a raw whole-file grep found only 14. The discrepancy couldn't be explained from file content alone and is flagged as-is rather than guessed at. Worth a manual `grep -o '—' site/tools/paper-review/index.html | wc -l` pass before trusting either count for a hard "zero em-dash" claim.
- **Eyebrow pattern (P1, confirmed):** same `<p class="eyebrow">Paid tool · $9-15</p>` tracked-uppercase kicker as the other two pages — the project's own banned pattern.
- **Browser overlay — `hero-eyebrow-chip`, `line-length` (~94-114ch), `overused-font` (91-94% Plus Jakarta Sans):** present here too, confirming this is a shared-template systemic pattern across all three tool pages, not a one-off.
- No gradient text, no glassmorphism, no hero-metric template found.

## Overall Impression

The most feature-rich of the three pages (three tiers, sample-report drawer, volume-pack upsell) and also the one where that richness works against it: the tier picker, sample-report toggle, and volume-pack link all compete in the first viewport-and-a-half before a first-time visitor has any proof the product is good. The sample-report drawer itself is a genuinely strong, non-gamified conversion device — the single most brand-consistent way to "not be boring" — but it sits below the tier decision instead of above it, so a first-timer is asked to pick a price tier before seeing what they're picking.

## What's Working

1. Sample-report drawer shows real output before payment — proof over decoration, exactly right for a skeptical-academic buyer.
2. FAQ copy is specific and plain.
3. "Anonymity Check bundled free" living in the hero paragraph (not repeated per-tier) is the right instinct where it appears — flagged below for where it's over-repeated instead.

## Priority Issues

- **P1 — Trust content backloaded.** Same fix as resume-review: privacy/refund/"advisory only" reassurance compressed to one line beside the CTA. → `/impeccable clarify site/tools/paper-review/`
- **P1 — Eyebrow pattern violates the project's own anti-reference list.** → `/impeccable typeset site/tools/paper-review/`
- **P2 — Sample-report drawer sits in the wrong decision order.** Move it above or directly beside the tier picker so a first-time buyer sees proof before being asked to choose a price. → `/impeccable layout site/tools/paper-review/`
- **P2 — Tier copy repeats "Anonymity Check bundled free" and similar qualifiers across all three tier descriptions.** State it once above the tier list instead of re-earning the claim three times. → `/impeccable clarify`
- **P2 — Volume-pack pricing ("5 for $38, 16% off" / "20 for $150, 17% off") asks a not-yet-converted first-time buyer to do discount math for a bulk use case that doesn't fit their mental model yet.** Consider moving this entirely off the primary conversion path (e.g., a post-purchase upsell) rather than presenting it pre-conversion.
- **P3 — "How the review works" numbered list runs unconstrained line length (~90+ characters) on wide viewports** with no narrower max-width for this specific block. → `/impeccable layout`
- **P3 — Em-dash count anomaly (detector: 18, raw grep: 14) unresolved** — verify manually before treating either count as ground truth.

## Persona Red Flags

- **Jordan (first-timer):** tier picker (a $9 vs $11 vs $15 decision) is asked before the sample report is seen — wrong order for a first-time decision sequence.
- **Sam (accessibility):** `.pr-tier-option:has(input:checked)` selected-state relies on `:has()` support plus an outline+tint change on an already-tinted background — verify computed contrast ratio meets WCAG AA; plausible low-contrast spot, not yet measured.

## Minor Observations

- Cloudflare Analytics beacon present, unrelated to design.
- Related-tools cross-links at footer are a good quiet upsell mechanism.

## Questions to Consider

1. Is the three-tier picker actually reducing friction, or importing a SaaS-pricing-page pattern onto a product where most buyers take the default middle tier anyway? Would a single price with optional add-ons get the same revenue with a lighter decision?
2. Why does the most expensive product get a pre-payment proof (sample report) while the two cheaper, more impulse-friendly products ask for blind trust?
