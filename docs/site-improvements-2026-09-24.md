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
5. **Vitae screenshots.** `/vitae/` has no picture of the app at all (the
   only one, `dashboard.png`, was a screenshot of a Claude session and was
   removed). Two or three real screenshots (submissions list, CV export,
   grant tracker) at 2880 px wide would do more for that page than any copy
   change. The launch cards in `Outreach/03-launches/assets/` are text, not
   screenshots.
6. **ModernTex size.** Pages say 15 MB; an older note said 14 MB. Check the
   current DMG and fix whichever is wrong.
7. **Verify three facts before they matter:**
   - the DOIs in the Citation Gap sample report
   - the template details in `site/templates/*` (class options, page limits)
   - the policy summaries in `site/guides/ai-policy-checking-your-own-manuscript/`.
     They were researched from search results because the publishers' sites
     were blocked from the build environment. Cells marked "check the page"
     were not pinned down.
8. **Read what carries your name.** The new guides are bylined "Benjamin
   Ampel" like the existing ones:
   - overleaf-alternative-mac
   - get-feedback-on-a-paper-before-submitting
   - methodology-problems-peer-reviewers-flag
   - ai-policy-checking-your-own-manuscript

   The same goes for the templates pages and the new customer emails in
   `backend/latextools/delivery.py` (ModernTex tips, trial, decision
   reminder). Read them in your voice before deploying.
9. **Old digest pages** keep the old nav until the Modal cron regenerates them.
   The generator (`backend/digest/publisher.py`) already has the new nav.
10. **Does an unlocked trial copy update itself?** `docs/products/moderntex.md`
    says the trial build ships with no Sparkle feed. The site and the
    trial-ending email now tell buyers to install the paid download once to
    get updates. If a license key does switch the trial copy onto the update
    feed, remove that sentence from `/moderntex/`, the success page and
    `html_lifecycle_trial_ending`. If it doesn't, consider making it do so.
11. **Bundles need Stripe prices.** A submission bundle (Paper Review +
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

### Find a purchase
- `/recover/` (linked in every footer, the ModernTex FAQ and both success
  pages) emails a fresh ModernTex license key and the download pages for any
  ModernTex or kit purchase made with an address. Before this, a buyer who
  lost the receipt email lost the key. Needs the frontend deploy only.

### For labs and departments
- `/labs/` puts volume packs, invoices, purchase orders, ModernTex for
  groups, data handling and vendor details (legal name, address, NAICS) on
  one page for purchasing and research offices. It says a W-9 is available
  on request and invites purchase-order and group-key requests by email:
  those are manual for now, so reply when they come in.

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

### Later additions
- `/tools/paper-review/sample/`: the example report, section by section,
  linked from the product page (under the buy button and after the sample),
  the homepage report card, and llms.txt.
- Template pages offer a starter zip (main.tex, references.bib, README).
  Four compile with latexmk here; NeurIPS needs that year's style file.
- The Paper Review status page shows "While it runs" links during the
  wait, and a "What comes next" panel after any paid result.
- ModernTex shows its release history (six releases since 4 September).
- GlobePin: four distinct screenshots (two were duplicates) and one App
  Store button.
- Blog Atom feed at `/blog/feed.xml`, rebuilt at deploy.
- The traffic dashboard's sales panel shows follow-up email counts, and
  Vitae Plus and digest sales are no longer "unattributed".
- No inline `style` attributes remain outside the cron-owned digest.
- A free response-to-reviewers template tool at
  `/tools/response-letter-template/`, which leads to Response Review.
- On phones, ModernTex and Paper Review show a slim sticky call to action
  once the hero buttons scroll away.
- New first-party events:
  - `template_download`
  - `sticky_cta`
  - `recover_request`
  - `response_template_download`
- Two full axe sweeps (WCAG 2 A/AA, light and dark) now come back clean on
  every page.
- A review of the customer-facing copy against the code found real bugs,
  now fixed (unsubscribe, pack anonymity, sender and reply-to, deletion
  timing, small-tool buyers getting Paper Review follow-ups).

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
