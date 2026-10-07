# Legroom: paid macOS app, launch runbook

Built on branch `legroom` (worktree `../Purplelink-legroom`), not yet live. Release 1.0.0 (build 1) is staged in the
Legroom repo (`/Volumes/Extreme SSD/Legroom`, branch `release`, `releases/staging/1.0.0/`: paid DMG 6.3 MB, trial DMG
5.3 MB, both notarized). This page is the runbook; the go-live steps are at the bottom.

Legroom is sold on purplelink.llc/legroom as a one-time $9.99 purchase with a 7-day trial edition, and is also in the
Mac Suite ($54.99, see `app-suite.md`). It is a menu-bar app that shows free disk space, warns before the disk fills, and
cleans folders and developer caches through rules the user previews and approves (Trash or permanent delete), with
What Grew (daily measurements, 1/7/30-day growth), Suggestions, Space Map and Find Files. After the trial the menu-bar
readout and low-space alerts stay free; rules, What Grew, Suggestions, Space Map and Find Files lock.

**Copy rule, decided 2026-10-05:** the pages say only "one-time $9.99, 7-day free trial" (it was $9 until the 2026-10-07 .99 pricing decision). They do not promise future major
versions, and they do not mention the Uninstaller, widget or command-line tool (planned, unreleased). Terms say
"updates to the version you bought are included" and that no decision has been made about a later major version.

## Stripe (live mode)

| Item | Value |
|---|---|
| Product | `prod_VMVa0tBaTReZTY` (account `acct_1TnewbJkzNxf3fKq`); still named after the working name Freeboard, **rename to "Legroom" before the first sale** (receipts and the dashboard read it; the dashboard maps both `legroom` and `freeboard`) |
| Price | $9.99 USD one-time (.99 pricing decision 2026-10-07). `price_1ULmZ6JkzNxf3fKqAs4vIdMw` was created at $9 and a Stripe Price amount cannot be edited: create a $9.99 Price on the product, set `STRIPE_PRICE_LEGROOM` to it and redeploy, before or with the site deploy that shows $9.99 |
| Env vars | `STRIPE_PRICE_LEGROOM` (the price id above) and `LEGROOM_UPDATE_TOKEN` (secret, write-only; local copy `~/.config/purplelink/legroom-update-token`, which `build-release.sh` compiles into the app as `LGUpdateChannelToken`). Both are Netlify production context and take effect only after the next site deploy |
| Product key | `legroom` in `netlify/functions/checkout.mjs` (`envKey: "STRIPE_PRICE_LEGROOM"`) |
| Success page | `/legroom/success/?session_id=cs_...` |

The Mac Suite is priced inline in `checkout.mjs` (`amount: 5499`, see `app-suite.md`); it needs no Stripe object.

## Delivery

`netlify/functions/legroom-download.mjs`, a copy of `outbound-veil-download.mjs`, streams from the private
`legroom-files` Blobs store (files: `Legroom-<ver>.dmg`, `Legroom-Trial-<ver>.dmg`, `appcast.xml`):

- Buyers: `?session_id=cs_...` lists files; `&file=Legroom-x.y.z.dmg` streams one. The session must be paid and carry
  `metadata.product` of `legroom` **or `app-suite`**, so every Suite buyer, including those who paid $39, gets Legroom.
- Trial (public): `?trial=1` streams the newest `Legroom-Trial-x.y.z.dmg`, 20 downloads per IP per day. The trial
  edition is the same source built with `LG_EDITION=trial`: 7 days from first launch (Keychain plus a file, earliest
  wins). It does not link Sparkle and has no feed, so it cannot update into the paid app.
- Updates (Sparkle, paid build only): `?feed=1` and `?update=<dmg>` (and `?stats=1` for download counts) require the
  header `X-Legroom-Channel: <LEGROOM_UPDATE_TOKEN>`, compared in constant time; 403 otherwise. The app checks once a
  day (`SUScheduledCheckInterval` 86400) and asks before installing (`SUAutomaticallyUpdate` false). The Sparkle key is
  Legroom's own (`--account legroom` in the login keychain), not ModernTex's.
- There is no licence key. The buyer email (webhook `BLOB_DELIVERED_PRODUCTS`) carries the success-page link and the
  one-sentence review ask. `purchases-recover.mjs` (`/recover/`) re-sends it; a Suite recovery now names Legroom.
- The app's Buy button opens `https://purplelink.llc/legroom/` (`LicenseText.buyURL`).

Tests: `node --experimental-test-module-mocks --test netlify/tests/{legroom-download,legroom-site,suite-entitlement,suite-webhook,checkout,purchases-recover}.test.mjs`
(the one `purchases-recover` failure on Node 26 is the known JWK issue in `app-suite.md`).

## What the privacy page says the app sends

No account, no analytics; measurements, rules, the log and the trial clock stay on the Mac. The only network use is the
Buy link (opens a browser) and, in the paid build, the daily Sparkle request to the feed URL, which carries the app name
and version (Sparkle's User-Agent) and the update token header, plus the IP address any request has. The site counts
downloads per version, not people. Before launch it is worth confirming this with a packet capture (Sparkle's
User-Agent contents and that no system profile is sent: `SUEnableSystemProfiling` is not set).

## Releasing a version

From the Legroom repo, on a clean commit (the build reads the token from `~/.config/purplelink/legroom-update-token`):

```
LG_VERSION=1.0.0 scripts/build-release.sh                      # stages the paid DMG, notarized
LG_VERSION=1.0.0 LG_EDITION=trial scripts/build-release.sh     # then the trial
scripts/publish-release.sh 1.0.0 --dry-run                     # shows what would go live
scripts/publish-release.sh 1.0.0                               # asks you to type "publish"
scripts/publish-release.sh 1.0.0 --rollback                    # pulls it back
```

`publish-release.sh` refuses unless `$SITE_REPO/netlify/functions/legroom-download.mjs` and `$SITE/legroom/` exist, and
runs `netlify blobs:set` with the site repo as the working directory, so run it from a checkout that has the
`legroom` branch merged and the Netlify link (`.netlify/state.json`, site `b264591f-...`); by default that is
`/Volumes/Extreme SSD/Purplelink LLC`. Publish the Blobs **after** the site deploy so the function exists, but before
announcing. Then update the version text on `/legroom/` ("Version 1.0.0 · 6 MB disk image") and deploy again.

## Dashboard

`sales.mjs` and `traffic_dashboard.py` already mapped `legroom` (and the old `freeboard` Stripe name) to their own
"Legroom" line before this branch. This branch adds `/legroom/` to the checkout-rate denominator (`product_paths`), a
`lg_trial_download` beacon event (site/analytics.js, counted as `lgTrialDownloads` in `stats.mjs`) and a dashboard
column for it. There is no Legroom block like Outbound Veil's `outbound_veil_report` yet.

## Open items

- Trademark: attorney search for LEGROOM (classes 9 and 42). The working name Freeboard was cleared out for a conflict;
  see the Legroom repo and `docs/growth-briefs/freeboard-name-clearance-2026-10-03.md`. Do not call the name cleared.
- Rename the Stripe product (above).
- The app icon on the page (`site/assets/legroom-icon.webp`) comes from the Legroom repo's unmerged `icon` branch
  ("draft 4c"); the staged 1.0.0 DMG was built from `release`, which does not contain that icon. Merge the icon branch
  and rebuild, or change the page to match what the DMG ships.
- The screenshots keep the QA harness window titles ("QA Dropdown" and so on) and are captioned "Sample data".
- `/guides/best-disk-space-analyzer-for-mac/` still says Legroom is unreleased, has no page and costs a planned $9;
  update it on launch day (it was out of scope for this branch).
- Not built: trial reminder emails, a "first ten minutes" page, a Legroom block in the daily dashboard, a video.
