# Purplelink LLC — Project Instructions

## Design Context

This project uses the **impeccable** design skill. Before any frontend or
design work, read the two root context files:

- **`PRODUCT.md`** — strategic context: register (`brand`), audiences
  (academic researchers + Apple-platform users), product purpose, brand
  personality (calm · craftsmanlike · trustworthy), anti-references, and the
  5 design principles.
- **`DESIGN.md`** — the visual system captured from `site/styles.css`: OKLCH
  purple palette (hue 310), Fraunces display + Plus Jakarta Sans body, pill
  buttons, radius scale, dark-mode behavior, motion rules.
  **Dark is the default theme** (owner decision, 2026-09-30): do not add
  `@media (prefers-color-scheme)` rules; gate dark overrides as
  `:where(:root:not([data-theme="light"]))`. Light is an opt-out via the footer
  toggle (`site/theme.js`).

**Hard constraints (from DESIGN.md — never violate):**

- **Strict CSP: `style-src 'self'` — no inline styles, ever.** All styling in
  external stylesheets. New external origins must be added to `netlify.toml`'s
  CSP header first.
- **No emojis** in UI copy (the site was deliberately de-emoji'd).
- **No AI-tell prose / marketing buzzwords / em-dash tics.** Voice is calm,
  plain, specific. Say what the product literally does.
- **WCAG 2.1 AA** contrast minimums; keyboard nav; `prefers-reduced-motion`
  honored on all motion.
- Self-host fonts and scripts; no third-party CDN loads.

**AdSense exception (explicit, owner-authorized, 2026-07-03):** the CSP hard
constraint above is deliberately relaxed sitewide — `style-src 'self'
'unsafe-inline'` plus the Google/AdSense origins
(`pagead2.googlesyndication.com`, `googleads.g.doubleclick.net`,
`www.google.com`, `www.gstatic.com`, `www.googletagservices.com`,
`tpc.googlesyndication.com`) in `img-src`/`script-src`/`connect-src`/
`frame-src` — so Google AdSense can render. This was reverted once by an
automated security sweep for contradicting the "never violate" wording above;
the site owner (Ben) explicitly re-authorized it and said this specific
policy may be violated for AdSense. Do not silently revert this again — if a
future audit flags it, surface this note rather than reverting.

Invoke design work with the impeccable skill (e.g. `/impeccable critique
/tools/word-counter/`, `/impeccable audit`, `/impeccable polish`).

## Keep local main in sync

`origin/main` moves all day (the Modal digest cron pushes to it, and every push triggers a production
build). A commit made on a stale local `main` makes the histories diverge; that broke deploys on
2026-07-24 and 2026-10-05.

- Do not commit on `main` in the shared checkout. Work in a worktree off `origin/main`
  (`git worktree add "/Volumes/Extreme SSD/_worktrees/Purplelink LLC/work-x" -b my-change origin/main`) and push
  from there. All worktrees on the Extreme SSD live under `/Volumes/Extreme SSD/_worktrees/<repo>/`, never loose in the
  drive root.
- `.githooks/main-guard.sh` blocks a commit on `main` while it is behind `origin/main`
  (override: `ALLOW_STALE_MAIN=1`).
- `scripts/sync-main.sh`, run by the launchd job `com.benampel.main-sync` every 15 minutes, fast-forwards
  `main` only when that provably touches nothing (no local-only commits, no uncommitted or
  recently modified incoming files). Otherwise it logs to `~/Library/Logs/purplelink-main-sync.log`
  and sends one notification. It never merges, rebases, stashes or resets.

## Automated and cloud sessions: open a PR, never push to main

Any Claude session that runs on a schedule or in the cloud (for example the weekly Thursday guide job that writes
`content/drafts/guides/` and `site/guides/<slug>/`) must not commit to or push `main`. On 2026-10-15 that job pushed a
new guide straight to `main` and broke Site tests (no social card; a shared-footer change tripped a page test).

1. Work on a branch off `origin/main` and open a pull request with `gh pr create`.
2. Before opening it, for a new page: run `python3 scripts/gen_og_cards.py --only <section>/<slug>` (its social card),
   `python3 scripts/gen_search_index.py`, `python3 scripts/gen_llms_full.py` and `python3 scripts/fingerprint_assets.py`,
   then the tests CI runs: `python3 -m pytest -q site-tests` and
   `node --experimental-test-module-mocks --test netlify/tests/*.test.mjs`. Fix every failure.
3. Wait for the PR's checks (`gh pr checks <n> --watch`). Squash-merge only when every check passes; if one fails,
   fix it on the branch or leave the PR open and say so in the run's summary. Never merge red, never bypass checks.
4. Add files by path, never `git add -A`; never add `Outreach/`, `docs/growth-briefs/` or other private paths.

Not covered: the Modal digest cron (`backend/digest`), which commits digest files to `main` by design.

## Deploy

- **Rule (Ben, 2026-10-17): never use `[deploy now]` or the manual batch build unless the change is needed live
  immediately.** "Immediately necessary" means customers are harmed or blocked until it ships: a broken checkout,
  download or license delivery, a security fix, or a wrong price or claim on a page. Not necessary: new pages and guides,
  copy edits, app version text and changelog entries, redesigns, SEO changes, analytics, tests, anything that can wait
  until the next 06:00 or 17:00 Eastern build. When in doubt, do not use it. Never put the marker in a commit message
  just to describe it (the build script cannot tell a mention from a request).

- **Builds are batched (2026-10-15).** A push to `main` does not build. `scripts/netlify_ignore.sh` (netlify.toml
  `build.ignore`) skips every git-triggered build except (a) the digest cron's final commit `chore(digest): Daily
  Digest #N`, so emailed digest links are live, and (b) a commit whose message contains `[deploy now]` AND changes
  server code (`netlify/`, `netlify.toml`, `package*.json`); the digest builds only when a build input changed. A marker
  on a page-text-only change (app version strings, copy, changelog) is ignored and waits for the slot (2026-10-17: 10 of
  12 marked builds in two days were version text). Everything else is published by the "scheduled" build hook, which the launchd job
  `com.purplelink.netlify-batch` calls at 06:00 and 17:00 US Eastern (it fires at 03:00, 04:00, 14:00 and 15:00 Phoenix and
  runs each Eastern slot once, or late after a wake) when `main` has
  unpublished site changes (`~/.purplelink/bin/netlify-batch-build.sh`; hook URLs in
  `~/.config/purplelink/netlify-build-hooks.json`, never print them; log `~/Library/Logs/purplelink-netlify-batch.log`).
  To ship a server fix now (checkout, delivery, security): put `[deploy now]` in the PR title or squash message. For
  page text that truly cannot wait (a wrong price, a broken claim), run `bash ~/.purplelink/bin/netlify-batch-build.sh
  manual` after the merge. App releases never need either: version text on the site can wait for the slot. Do not call `netlify api
  createSiteBuild` after merges any more. Verifying a change live means waiting for the next scheduled build or using
  one of those two. Netlify Starter allows 300 build minutes a month.
  App updates do not wait for a build: every app, BatteryMeter included (PR 129), serves its Sparkle feed and
  downloads from a Netlify function reading Blobs, so `scripts/publish-release.sh` in the app repo is live at once.
  Product-page version text and changelog entries in `site/` wait for the next slot.

- Frontend: `bash scripts/deploy.sh` (Netlify `--prod` + IndexNow ping).
- Backend (Modal): `bash scripts/deploy.sh --backend`.
- The site is live at https://purplelink.llc.
- ModernTex ($19.99, Stripe): in the ModernTex repo, `scripts/build-release.sh` stages a
  notarized DMG and `scripts/publish-release.sh <version>` uploads the
  DMG and Sparkle appcast to the private `moderntex-files` Blobs store; nothing
  lands in `site/`. Delivery is `netlify/functions/moderntex-download.mjs`
  (session-gated for buyers, header-token-gated for in-app updates). See
  `docs/products/moderntex.md`. The Sparkle EdDSA private key lives in Ben's
  login keychain.

## Paid tools status

**Checkout is LIVE and selling in Stripe live mode.** Verified end to end
2026-08-05: all 13 product keys in `netlify/functions/checkout.mjs`'s
`PRODUCT_CATALOG` return a real `cs_live_…` Checkout Session — every
Paper Review tier, the five adjacent tools (cover-letter, anonymity-check,
citation-gap, revision-review, response-review, resume-review), and the
kits. No page carries a "Coming soon" button and no checkout button is
disabled. Modal secrets are real, not placeholders.

This supersedes the earlier note that checkout was disabled pending Stripe
activation. That note was stale and wrong; do not act on it if it turns up
in an old transcript or summary.

**Delivery depends entirely on the Stripe webhook.** The chain is:
`/.netlify/functions/checkout` → Stripe → `/.netlify/functions/stripe-webhook`
→ Modal `/paper-review/register-token` → `paper_tokens_dict` → the upload
page calls `/paper-review/redeem-session`. Note that `redeem-session` never
contacts Stripe; it only reads that dict. So if the webhook stops firing or
its dashboard URL changes, a customer pays, lands on the upload page, and
gets `{"error":"pending"}` forever with no refund path. `stripe-webhook.mjs`
sends an operator alert email when forwarding to Modal fails — treat that
email as a paid-but-undelivered incident, not a warning.

See `docs/paper-review-runbook.md` and `docs/security-paper-review.md`.

## Outbound Veil (Mac app) status

**LIVE since 2026-10-04**, $29.99 one-time. Since 1.1.0 (2026-10-07) there is one download: 7-day trial, then a license key (see docs/products/unified-licensing-2026-10.md). Page: https://purplelink.llc/outbound-veil/.
Release 1.0.0 (build 41) is published in the `outbound-veil-files` Blobs store; the YouTube tour is
`EWlyzL88-uo`. The whole purchase chain was tested end to end in live mode with a one-use 100%-off
promotion code (Stripe coupon "Outbound Veil launch test", now redeemed): checkout, success page,
byte-identical DMG download, delivery email. Stripe product `prod_VNOyQCox4pCwN3`, price
`price_1UMeAEJkzNxf3fKqTmF7jfE2` (account `acct_1TnewbJkzNxf3fKq`). Env: `STRIPE_PRICE_OUTBOUND_VEIL`,
`OUTBOUND_VEIL_UPDATE_TOKEN` (secret, write-only; local copy `~/.config/purplelink/outbound-veil-update-token`).
The in-app update channel header is `X-OutboundVeil-Channel` (the function once checked a different spelling,
fixed 2026-10-04). Runbook: `docs/products/outbound-veil.md`. App source: `/Volumes/Extreme SSD/OutboundVeil`.
**Name:** Ben reviewed the trademark note and decided "Outbound Veil is fine" (2026-10-04). Residual risk, for the
record only: a pending USPTO application for VEIL (serial 79459516, data-security software, filed 2026-07-31).
See that repo's `docs/name-clearance-2026-10-03.md`. Do not re-raise it unless a refusal or a letter arrives.

## Public repo, private internals

This repo is public (Netlify's free plan cannot deploy a private organization repo). Outreach logs and contact lists (`Outreach/`), growth research (`docs/growth-briefs/`), `docs/organic-traffic/`, `docs/photo-licensing/`, the paper-review runbook, the security notes and other internal docs are NOT tracked here. They stay on disk, git-ignored, and are backed up to the private repo `purplelink-llc/purplelink-private` (clone at `/Volumes/Extreme SSD/purplelink-private`; run its `sync.sh` to refresh, `paths.txt` lists the paths). A `.githooks/post-merge` hook restores them from that clone if a fast-forward removes them. Never `git add` those paths, and do not make this repo private without re-linking Netlify (see memory: repo-visibility-breaks-netlify).

## Marketing arm

The 50 skills from coreyhaines31/marketingskills are installed in `~/.claude/skills/` (clone at `/Volumes/Extreme SSD/marketingskills`, refresh with `/Volumes/Extreme SSD/marketingskills-local/update.sh`). Read `.agents/product-marketing.md` (local, shared product and voice context) before marketing work. The scheduled task `daily-gap-analysis` writes its briefs under `docs/growth-briefs/gap-analysis/` (git-ignored, see the private repo note above). Nothing outward (posts, emails, spend, sign-ups) happens without an approved queue item or Ben's explicit yes.
