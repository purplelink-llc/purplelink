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
  (`git worktree add ../work-x -b my-change origin/main`) and push from there.
- `.githooks/main-guard.sh` blocks a commit on `main` while it is behind `origin/main`
  (override: `ALLOW_STALE_MAIN=1`).
- `scripts/sync-main.sh`, run by the launchd job `com.benampel.main-sync` every 15 minutes, fast-forwards
  `main` only when that provably touches nothing (no local-only commits, no uncommitted or
  recently modified incoming files). Otherwise it logs to `~/Library/Logs/purplelink-main-sync.log`
  and sends one notification. It never merges, rebases, stashes or resets.

## Deploy

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
