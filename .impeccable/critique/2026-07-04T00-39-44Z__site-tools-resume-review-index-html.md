---
score: 25
total: 40
p0: 0
p1: 2
p2: 2
p3: 1
timestamp: 2026-07-04T00-39-44Z
slug: site-tools-resume-review-index-html
---
Method: dual-agent (A: a102a77dcbd180439 · B: a0040c8955ab2cbca)

## Design Health Score

| Heuristic | Score | Note |
|---|---|---|
| Visibility of system status | 2/4 | Checkout click gives no visible "opening secure checkout…" state |
| Match between system and real world | 3/4 | ATS Screener / Hiring Manager / Recruiter personas map to real actors |
| User control and freedom | 2/4 | No preview/edit step before one-shot upload |
| Consistency and standards | 3/4 | Shares `pr-*` classes and section order with the other two tool pages |
| Error prevention | 2/4 | File-type/size limits only stated in a collapsed FAQ, not near the upload control |
| Recognition rather than recall | 3/4 | Persona/layer breakdowns fully spelled out on-page |
| Flexibility and efficiency of use | 2/4 | No returning-buyer shortcut |
| Aesthetic and minimalist design | 3/4 | Restrained, consistent with brand |
| Help recognize/diagnose/recover from errors | 2/4 | Refund policy buried in FAQ instead of near CTA |
| Help and documentation | 3/4 | FAQ copy specific and non-generic |
| **Total** | **25/40** | Shared score basis; page-specific deltas below |

## Anti-Patterns Verdict

Deterministic scan (CLI, `detect.mjs --json`) + browser overlay evidence, combined with the LLM design pass:

- **Eyebrow pattern (P1, confirmed by both assessments):** `<p class="eyebrow">Paid tool · $5</p>` above the H1 is the literal tracked-uppercase-kicker pattern PRODUCT.md's anti-reference list bans. Present on all three pages including this one and its upload step (`Step 2 of 2 · Upload`).
- **`overused-font` (browser overlay, Assessment B):** 91-94% of visible text renders in Plus Jakarta Sans — Fraunces is underused as a hierarchy tool, not itself a violation but a missed lever.
- **`line-length` (browser overlay, Assessment B):** body copy runs ~94-114 characters/line, well past the 65-75ch cap in the skill's own typography rule.
- **`hero-eyebrow-chip` (browser overlay, Assessment B):** consistent with the eyebrow finding above — same root cause, two detectors.
- No gradient text, no glassmorphism, no hero-metric template, no identical-card-grid found — the page does **not** read as generic AI slop at the structural level. This is a real strength, not a false negative.

## Overall Impression

Above-average small-business execution, not broken, but leaving real conversion on the table by backloading its own best asset: trust copy. The privacy/refund language ("nothing is retained after delivery," "we'll refund the price") is genuinely strong, specific, non-hedgy writing — exactly the calm-confident voice the brand asks for — but it sits in FAQ items 4 and 7, several scrolls from the CTA, at the exact moment (uploading a personal resume to a stranger's AI) when the buyer is most anxious and needs it most.

## What's Working

1. FAQ copy is specific and plain, not AI-tool boilerplate.
2. Persona framing (ATS Screener / Hiring Manager Skeptic / Recruiter Red Flags) is a legible, concrete differentiator versus vague "AI-powered analysis."
3. No structural AI-slop tells (no gradient text, no hero-metric dashboard, no cliché card grid).

## Priority Issues

- **P1 — Trust content is backloaded, not front-loaded.** Move a compressed one-line version of the privacy/refund reassurance to sit directly beside the CTA button, next to "Secure checkout via Stripe." → `/impeccable clarify site/tools/resume-review/`
- **P1 — Eyebrow pattern violates the project's own anti-reference list.** Drop `class="eyebrow"` lines on both the landing and upload page; fold the price into the H1 subhead or button copy (already partly done on the button). → `/impeccable typeset site/tools/resume-review/`
- **P2 — No proof-of-output before payment.** Unlike Paper Review, Resume Review has no sample-report preview; a first-time $5 buyer has to trust FAQ prose alone. → `/impeccable craft` a sample-report drawer ported from Paper Review's pattern.
- **P2 — Body copy line length (~94-114ch) exceeds the 65-75ch cap.** → `/impeccable layout site/tools/resume-review/`
- **P3 — Hero/CTA alignment seam:** centered `.tools-hero` sits directly above a left-aligned `.pr-checkout-row`, producing an unintentional-looking hard edge. → `/impeccable layout`

## Persona Red Flags

- **Skeptical first-time buyer:** biggest fear is "is this generic AI feedback or does it actually catch real problems" — no sample report to answer that fear pre-payment.
- **Sam (accessibility):** verify contrast of any `:has(input:checked)` selected-state tint against its own tinted background (shared component with Paper Review's tier picker; not resume-review-specific but worth a pass here too if the pattern is reused).

## Minor Observations

- Cloudflare Analytics beacon present, unrelated to design.
- Related-tools cross-link at footer is a quiet, appropriate upsell; no complaint.

## Questions to Consider

1. If the privacy/refund copy is this strong, why is it the last thing read instead of the first thing seen?
2. Would porting Paper Review's sample-report drawer to this cheaper, more impulse-buy product convert better than it does on the higher-priced product it's currently exclusive to?
