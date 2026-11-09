# Purplelink LLC — Project Instructions

The rules are below. The full background (dates, IDs, file paths, why each rule exists) is in
`docs/agent-context.md`. Read its matching section before deploy, release, checkout, product-status or marketing work.

## Design

- Before frontend or design work, read `PRODUCT.md` and `DESIGN.md`, and use the impeccable skill
  (`/impeccable critique|audit|polish <path>`).
- Dark is the default theme: no `@media (prefers-color-scheme)` rules; gate dark overrides as
  `:where(:root:not([data-theme="light"]))`. Light is opt-in via `site/theme.js`.
- No inline styles; all styling in external stylesheets. New external origins go into `netlify.toml`'s CSP first.
- No emojis in UI copy. No AI-tell prose, marketing buzzwords or em-dash tics: calm, plain, specific.
- WCAG 2.1 AA contrast, keyboard nav, `prefers-reduced-motion` on all motion. Self-host fonts and scripts.
- Two owner-approved CSP exceptions must not be reverted: AdSense (`'unsafe-inline'` plus the Google ad origins,
  2026-07-03) and the Reddit pixel (`site/reddit-pixel.js`, ad-click visitors only, 2026-10-29). If an audit flags
  either, surface it; don't revert. Details: `docs/agent-context.md`, "Design Context".

## Git

- Never commit on `main` in the shared checkout. Work in a worktree off `origin/main` under
  `/Volumes/Extreme SSD/_worktrees/Purplelink LLC/<name>` and push from there. `.githooks/main-guard.sh` blocks
  stale-main commits; `com.benampel.main-sync` fast-forwards `main` safely every 15 minutes.
- Scheduled and cloud sessions never push `main`: branch, `gh pr create`, wait for every check, squash-merge only when
  green. Before a PR with a new page: `python3 scripts/gen_og_cards.py --only <section>/<slug>`, then
  `python3 -m pytest -q site-tests` and `node --experimental-test-module-mocks --test netlify/tests/*.test.mjs`.
  (The Modal digest cron is the one job that commits to `main` by design.)
- Build output is not committed: never `git add` `site/search-index.json` or `site/llms-full.txt`; pages carry no
  `?v=` stamps (strip with `python3 scripts/fingerprint_assets.py --strip`); `backend/latextools/buddy_facts.py` is
  generated from `site/llms.txt`.
- The repo is public. Add files by path, never `git add -A`. Never add `Outreach/`, `docs/growth-briefs/`,
  `docs/organic-traffic/`, `docs/photo-licensing/` or other private internals (backed up to
  `purplelink-llc/purplelink-private`). Don't make the repo private (it breaks Netlify).

## Deploy

- Builds are batched: the site publishes at 06:00 and 17:00 US Eastern. A push to `main` does not build.
- Never use `[deploy now]` or `netlify-batch-build.sh manual` unless customers are harmed or blocked until it ships
  (broken checkout, download or license delivery, security fix, wrong price or claim). Never write the marker in a
  commit message just to mention it. Don't call `netlify api createSiteBuild`.
- App releases (Sparkle feeds, DMGs) go live through Blobs at once and never need a build.
- Frontend `bash scripts/deploy.sh`; backend (Modal) `bash scripts/deploy.sh --backend`. Live site: https://purplelink.llc.
- Never print the build-hook URLs. Details: `docs/agent-context.md`, "Deploy".

## Products

- Stripe checkout is live and selling (all 13 `PRODUCT_CATALOG` keys). Any old note saying checkout is disabled is
  stale; ignore it.
- Paper Review delivery depends on the Stripe webhook. A `stripe-webhook.mjs` operator alert email means a
  paid-but-undelivered customer: treat it as an incident. See `docs/paper-review-runbook.md`.
- Outbound Veil is live ($29.99, 7-day trial then license key). Its name is cleared by Ben; don't re-raise trademark
  concerns unless a refusal or a letter arrives. Runbook: `docs/products/outbound-veil.md`.
- ModernTex and app release steps: `docs/products/moderntex.md` and `docs/agent-context.md`, "Deploy".

## Marketing and posting

- Nothing outward (posts, emails, spend, sign-ups) happens without an approved queue item or Ben's explicit yes.
- Read `.agents/product-marketing.md` before marketing work.
- Every purplelink.llc link in an outward draft needs a unique `utm_content`: make it with
  `python3 scripts/hub/hub.py utm URL --asset A --channel C`. Record sends with
  `approval_queue.py done ID --url <live url>`.
- Standing approvals cover only: the daily company post (LinkedIn company page, Bluesky, Threads, Mastodon in Ben's
  voice, Facebook Page) and Instagram mirrors of Purplelink YouTube videos and company-page posts. Nothing else: no X,
  no Reddit, no replies, likes, follows or DMs, never Ben's own LinkedIn, never RubbleFront's Instagram.
- `social.py approve <id>` only when Ben says so in chat for that item; never edit an approved item; never remove
  `~/.purplelink/social/PAUSE` unless Ben says so; never add the queue, config or tokens to the repo.
- Details: `docs/agent-context.md`, "Marketing arm", and `docs/social-posting.md`.
