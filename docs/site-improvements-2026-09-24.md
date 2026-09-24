# Site improvements, September 2026: what changed and what needs Ben

Branch: `claude/gifted-knuth-mof4vk`. Nothing here is deployed. The audit that
started this is `docs/site-audit-2026-09-24.md`; the strategy behind the
retention work is `docs/growth-proposals-2026-09.md`.

## Before or at deploy: your actions

1. **Deploy both halves.** `bash scripts/deploy.sh` for the site and functions,
   then `bash scripts/deploy.sh --backend` for Modal. Several features need
   both:
   - volume-pack token expiry fix and the win-back rule (backend)
   - ModernTex buyer follow-up emails (webhook + backend)
   - ModernTex trial emails (page + backend)
   - Paper Review decision-date reminder (upload page + backend)
   - product-aware "ready" emails (backend)
2. **Stripe: pack buyers purged earlier.** Before the expiry fix, the weekly
   sweep deleted volume-pack entries after 7 days. Check Stripe for 5-pack and
   20-pack sessions older than a week and reissue unused tokens by hand
   (`docs/paper-review-runbook.md`).
3. **Amazon Associates tag.** `site/desk/desk.js` has `AMAZON_TAG = ""`. The
   research desk links work without it but earn nothing.
4. **ModernTex screenshot.** `01-editor-clean*.webp` still shows the
   "1 error" label and a Kalshi.tex tab. Re-shoot at 2880 px wide and replace
   both files.
5. **ModernTex size.** Pages say 15 MB; an older note said 14 MB. Check the
   current DMG and fix whichever is wrong.
6. **Verify three facts before they matter:**
   - the DOIs in the Citation Gap sample report
   - the template details in `site/templates/*` (class options, page limits)
   - the policy summaries in `site/guides/ai-policy-checking-your-own-manuscript/`.
     They were researched from search results because the publishers' sites
     were blocked from the build environment. Cells marked "check the page"
     were not pinned down.
7. **Old digest pages** keep the old nav until the Modal cron regenerates them.
   The generator (`backend/digest/publisher.py`) already has the new nav.
8. **Bundles need Stripe prices.** A submission bundle (Paper Review +
   Citation Gap + Cover Letter) was proposed but not built: it needs new price
   IDs in Stripe and in Netlify env first.

## What changed

### Look and navigation
- One shared nav (Products, Tools, Guides, Blog, About) and a four-column
  footer on every page, applied by `scripts/apply_layout.py` (run in deploy).
- New pages: `/products/` (everything with prices), `/scholar-utility-belt/`,
  `/desk/` (books), `/templates/` (five venue templates),
  `/tools/submission-checklist/`, and four guides:
  - Overleaf alternatives
  - getting feedback before submitting
  - methodology problems reviewers flag
  - using AI on your own manuscript (publisher policies)
- Homepage leads with the products, has a "Before you submit" section, a
  guides row and a plain contact line.
- Kits: three-up grid, cropped covers, a cleaner bundle band.
- Tool pages:
  - related links are now a labelled grid
  - `/tools/` and `/guides/` have a filter box ("/" focuses it)
  - comparison tables stack into cards on phones
- Contrast, dark mode, mobile overflow, back-link gutters, button word
  spacing and footer contrast were fixed across the site. The final sweep
  found 0 mobile overflow on 246 pages and 0 JS errors.

### Selling
- AdSense is off the money pages.
- Paid tools show refund lines and sample outputs.
- Paper Review:
  - sample report open by default
  - a FAQ on journal AI policies
  - consistent delivery times
- Every paid-tool result page ends with "What comes next" (the tool that
  naturally follows), tagged `?from=after-<product>`.
- "Ready" emails name the right product. Cover Letter buyers were told
  "Your Paper Review is ready". Each email offers one next step.
- ModernTex: specs table, closing call to action, clean screenshot crop.

### Retention (all opt-out-able through the existing lifecycle unsubscribe)
- **ModernTex buyers:** tips on day 3, a pre-submission note on day 21.
- **ModernTex trial:** after a trial download, an optional form sends:
  - a setup guide at once
  - tips on day 4
  - a trial-ending note on day 6

  Buying ends the sequence.
- **Paper Review:** an optional "when do you expect a decision?" (4, 8 or 12
  weeks) sends one email then, about Response Review and Revision Review.
- **Remembered choices** (this browser only): LaTeX engine, Word style,
  equation, table, PDF and Markdown options, Paper Review tier, field and
  journal, plus recently used tools. The privacy page has a button that
  clears them.
- The privacy page describes each of these.

### Search and AI visibility
- Missing share images were generated, and deploy fails if one is missing
  (`scripts/check_og_images.py`).
- `llms.txt` has corrected prices and pages. `llms-full.txt` is generated
  from 25 pages at deploy (`scripts/gen_llms_full.py`).
- The sitemap ignores commits that only change `?v=` stamps.
- 29 pages gained `<main>` landmarks. Structured data parses on every page.

### Copy
- Dash-joined clauses were rewritten across about 370 spots on tool, product
  and guide pages, keeping matching FAQ structured data in sync. Blog posts,
  the changelog and legal pages were left as written.

### Backend fixes
- Volume-pack tokens no longer expire after 7 days (the packs are sold as
  "never expire"). Spent packs are kept 30 days.
- Buyers who purchased again no longer get the win-back email, as the privacy
  policy promises.
- Anonymity Check reports use readable category headings.

## Numbers to watch after deploy

- **Trial to paid:** trial entries with `converted_at` divided by all
  `trial:*` entries in `customer_lifecycle_dict`.
- **Email click-throughs:** the `utm_campaign` values
  - `mtx-d3`, `mtx-d21` (buyer emails)
  - `mtx-trial-1`, `mtx-trial-4`, `mtx-trial-6` (trial emails)
  - `decision` (decision reminder)
  - `ready` (ready emails)

  These show up as sources in `stats.mjs`.
- **Result-page next steps:** `from:after-*` sources in `stats.mjs`.
