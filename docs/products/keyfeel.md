# Keyfeel: paid macOS app, launch runbook

Launched 2026-10-07. The app lives in
`/Volumes/Extreme SSD/Keyfeel` (brand assets in `assets/brand/`). "Keyfeel" is a working name that Ben has decided
to use; no name clearance has been done (see Open items).

Keyfeel is a macOS menu-bar utility, sold on purplelink.llc/keyfeel as a one-time **$9.99** purchase with a free
7-day trial inside the same app (one DMG for everyone; a license key unlocks it, like ModernTex), and it is in the Mac Suite ($54.99, five apps,
see `app-suite.md`). It plays recorded keyboard-switch sounds on every key press, plus mouse-click sounds, speed-aware
scroll ticks, optional trackpad haptics, a click ripple, per-app silence and automatic silence while the microphone is
in use. It works offline, reads key codes and never the characters, and needs the macOS Input Monitoring permission.
Requires macOS 13 or later, Apple silicon or Intel. 14-day refund like the other apps.

**Copy rule:** the pages list only the shipped features named in the brief (recorded profiles Tactile, Cherry MX Brown
and Dome plus synthesized extras; a different recording each press; per-key pitch and left-to-right stereo; press and
release sounds; space bar and Return sounds; mouse click press and release sounds; speed-aware scroll ticks; trackpad
haptics on scroll and click, only while a finger is on the trackpad; click ripple; per-app silence; silence while the
microphone is in use; import your own sound; menu-bar control). Do not add a feature to a page until it ships.

## Release gate (nothing can sell by accident)

`site/keyfeel/launch.js` holds the only switch: `window.KEYFEEL_LAUNCH = { live, version, sizeMb, released }`.
As shipped, `live` is `false`. Until it is `true` **and** `version` (x.y.z), `sizeMb` (whole number) and `released`
(YYYY-MM-DD) are all valid:

- the page's trial link has no `href` and is `aria-disabled`; the Buy button has the `disabled` attribute;
- the hero says "Not released yet"; no version, size or date is shown;
- the sticky "Get Keyfeel" bar is removed.

`netlify/tests/keyfeel-site.test.mjs` runs `launch.js` in a fake DOM for each state, and has one test named
"PRE-LAUNCH GUARD" that asserts the shipped values; delete that test when you flip the switch.

The gate covers the Keyfeel page only. It does **not** gate: the `keyfeel` and `app-suite` entries in `checkout.mjs`
(the Suite is $54.99 and names Keyfeel the moment this branch deploys), the Suite page, the listings (products, pricing,
home, llms files, sitemap, footer), Terms and Privacy. So merge and deploy this branch on launch day, not before.

## Stripe

Nothing to create. `keyfeel` is priced inline in `netlify/functions/checkout.mjs` (`amount: 999`, name "Keyfeel for
macOS", success path `/keyfeel/success/`), like ModernTex, so there is no Stripe Price and no `STRIPE_PRICE_*` env var.
The Suite is `amount: 5400`. Session metadata carries `product` = `keyfeel` or `app-suite`.

## Env vars and Blobs

| Item | Value |
|---|---|
| `KEYFEEL_UPDATE_TOKEN` | Netlify production env var, secret, write-only. Random string; the same value is compiled into the app and sent as header `X-Keyfeel-Channel` on every Sparkle request. Takes effect after the next site deploy. Suggested local copy `~/.config/purplelink/keyfeel-update-token` |
| Blobs store `keyfeel-files` | Private. Holds `Keyfeel-<ver>.dmg` and `appcast.xml` |
| Blobs store `keyfeel-stats` | Created on first update download; per-file download counts |
| Blobs store `rate-limits` | Existing; the public download door writes `rl:trial:<day>:<hash>` |

## Delivery

`netlify/functions/keyfeel-download.mjs`, a copy of `legroom-download.mjs`:

- Buyers: `?session_id=cs_...` lists files; `&file=Keyfeel-x.y.z.dmg` streams one. The session must be paid and carry
  `metadata.product` of `keyfeel` **or `app-suite`**, so every Suite buyer, including those who paid $39 or $49, gets
  Keyfeel.
- Public download (the trial): `?download=1` (`?trial=1` kept for old links) streams the newest `Keyfeel-x.y.z.dmg`,
  20 downloads per IP per day (429 after). It is the same app buyers and Sparkle get.
- Updates (Sparkle, paid build only): `?feed=1`, `?update=<dmg>` and `?stats=1` require the header
  `X-Keyfeel-Channel: <KEYFEEL_UPDATE_TOKEN>`, compared in constant time; 403 otherwise, and 403 when the env var is
  unset. The token is never logged or echoed. The feed rewrites every enclosure URL to the update door.
- File names are exact: `Keyfeel-1.0.0.dmg` (capital K, lower-case "eel"). Anything else
  is ignored by the buyer list and refused at the update door.
- There is no licence key. The buyer email (webhook `BLOB_DELIVERED_PRODUCTS`) carries the success-page link and a short
  note on the Input Monitoring permission. The Suite email now says the page has five things and carries the same note.
  `/recover/` (purchases-recover.mjs) re-sends the link, with Keyfeel named in the Suite recovery email.

Analytics: the trial link click fires `kf_trial_download` (site/analytics.js), counted as `kfTrialDownloads` in
`stats.mjs` and shown in the traffic dashboard next to the other trial columns. `keyfeel` is its own "Keyfeel" line in
the dashboard (`sales.mjs` maps it to the purplelink site; `/keyfeel/` is in the checkout-rate denominator).

Tests: `node --experimental-test-module-mocks --test netlify/tests/*.test.mjs` (keyfeel-download, keyfeel-site,
checkout, suite-entitlement, suite-webhook, purchases-recover, legroom-site cover this product), and
`python3 -m pytest scripts/traffic-dashboard`.

## Releasing a version

In the Keyfeel repo (`/Volumes/Extreme SSD/Keyfeel`): `KF_VERSION=x.y.z scripts/build-release.sh` (paid) and
builds a universal, Developer-ID-signed, notarized DMG into
`releases/staging/<ver>/`; the notary profile is `moderntex`. Notarization sometimes fails to staple on a CloudKit
timeout (Error 68); rerun. `PURPLELINK_SITE=<site checkout>/site scripts/publish-release.sh x.y.z --yes` uploads to the
`keyfeel-files` store and rebuilds the appcast, reading every upload back byte for byte. Sparkle uses the shared default
EdDSA key (public `6yp5/7HTj/lA+mxplvbKsfksGLsSvpgXUUtsVhMfW8U=`). The channel token lives in
`~/.config/purplelink/keyfeel-update-token`. There is no separate trial build.

Released: 1.0.0 (build 15), 2026-10-07.

## Launch checklist (owner)

1. Set `KEYFEEL_UPDATE_TOKEN` on Netlify (production), and build it into the app.
2. Stage `Keyfeel-<ver>.dmg` and `appcast.xml` in `keyfeel-files`.
3. Fill in `site/keyfeel/launch.js` (`live: true`, version, size in MB, release date), delete the PRE-LAUNCH GUARD
   test, commit, merge to main and deploy. The same deploy raises the Suite to $54.
4. One real purchase and refund of each of `keyfeel` and `app-suite`: the success pages list the download, the email
   arrives, the DMG opens, Sparkle sees the feed.
5. Confirm the privacy and Terms wording against the shipped app (what the update request carries; that the trial has
   no update check; that nothing is logged).
6. Add Keyfeel to the site-wide promo list in `site/site.js` (`APPS`); it is deliberately absent until the trial works.
7. Static fallback text in `site/keyfeel/index.html` ("Not released yet", "Free trial opens at release", "Buying opens
   at release", the "Version, size and release date..." sentence) is what crawlers and `llms-full.txt` read, because the
   gate swaps text in the browser. After launch, edit those four strings to their live wording and drop the `hidden`
   and `data-kf-*` attributes if you want the static HTML to match.
8. Add a Keyfeel entry to `site/changelog/index.html` and, if wanted, a share-card entry in `site/assets/og/_gen.html`.

## Open items

- Name: no trademark search has been done for KEYFEEL.
- The page shows no screenshots of the app; the hero and the four pictures are illustrations from
  `Keyfeel/assets/brand/` and are labelled as such. Replace them with captures when there are any. There is no video.
- Behaviour claims on the page that only the app can confirm: that the paid app's only network use is the update check
  and the trial has none; that Keyfeel only listens (does not alter or block keys); what the haptics do on a Mac without a
  haptic trackpad is not stated on the page and should be checked.
- Optional trial emails (2026-10-08): `keyfeel-reminder.mjs` + `keyfeel-reminder-send.mjs` (daily 14:20 UTC), shared engine
  `netlify/lib/trial-reminder.mjs`, form wired by `site/trial-reminder.js`. Blobs `kf-trial-reminders`, `kf-trial-reminder-tokens`.
  The setup email links `/keyfeel/` because there is no `/keyfeel/start/` first-run page (the Input Monitoring steps are in the
  page, the success page and the buyer email too).

## License keys (from 1.1.0)

One app, one DMG. Until a valid key is entered the app runs for 7 days from first launch (first-launch time kept in the
Keychain and a file, earlier wins, clock set-back ignored), then stays silent. Keys are `KFL1-` + Crockford Base32 of a
4-byte nonce and a 64-byte Ed25519 signature over `KeyfeelLicenseV1` + nonce, checked offline in the app
(`KeyfeelCore/LicenseKey.swift`, public key `YX6tWGJbj3EL9u3BBIRWrWBlRV0ppO149FkUZbPK/XY=`). Issued by
`netlify/lib/keyfeel-license.mjs` from `KEYFEEL_LICENSE_PRIVATE_KEY` (Netlify production secret; local copy
`~/.config/purplelink/keyfeel-license-private-key`, mode 600; back it up with the Sparkle keys). The nonce is derived
from the buyer's email address, so the receipt email, the success pages (the `license` field of `keyfeel-download`'s
purchase door) and `/recover/` all show the same key. Keys are not tied to a machine and cannot be revoked remotely; the
Terms ask a refunded buyer to stop using it. Suite buyers get a Keyfeel key too. To re-issue a key by hand:
`issueKeyfeelLicense(email)`.

The app also accepts `keyfeel://license/<key>`.
