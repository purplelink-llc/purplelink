# Lenses: paid macOS app, store runbook

Store side built 2026-11-05 on the `lenses-launch` branch. The app lives in its own private repo
(`purplelink-llc/Lenses`, local `/Volumes/Extreme SSD/Lenses`); the launch facts file written that day is the source of every
claim on the page. Name: Lenses (always capitalised), slug and checkout key `lenses`, bundle id `llc.purplelink.Lenses`.

Lenses is a menu bar app for display glasses (macOS 14 or later, Apple silicon). When the glasses are plugged in it applies a
profile (sharp HiDPI mode, 120 Hz where offered, layout, edge margin, night tint, Dark Mode and a bigger pointer for one
profile); on unplug or quit it puts the Mac back. Tested on RayNeo Air; it also recognises XREAL and VITURE by display name
(untested on them) and any other glasses through "Use this display as my glasses". Notarized direct download, not the Mac
App Store (it uses private macOS display calls).

**$4.99 once, USD. One download: 7-day trial from first launch, then a license key** (licensing added 2026-11-06, Ben in chat;
1.1.0 is the first version with it). PurplelinkLicenseV1, prefix `LN1`, slug `lenses`, same signing seed and public key as the
other keyed apps (`PURPLELINK_LICENSE_PRIVATE_KEY`). Sparkle updates come from the token-gated feed below. No trial
reminder emails. 14-day refund like the other apps. Sold on its own for $4.99 and, since 2026-11-06 (Ben, in chat), also
in the Mac Suite at the same $59.99 and as a custom-bundle pick (`lenses` in `netlify/lib/bundles.mjs`). `lenses-download.mjs`
accepts a paid `lenses` session, a paid `app-suite` session and a bundle session whose apps include `lenses` (`bundleHasPart`);
anything else gets `not_entitled`. Past Suite buyers get Lenses at no charge, and a Suite or pick-bundle that includes Lenses
issues a Lenses key too (`licensedSlugsFor`). The Suite email, success page (`site/suite/success.js`), `/recover/` and the
REFUND_TEXT for `app-suite` all name the Lenses key.

Existing 1.0.0 buyers have no key but are not locked out: 1.1.0 treats an install with prior Lenses preferences as paid (see
the app repo's `docs` and `Licensing.swift`). The key nonce derives from the Stripe session id, so the success page and
`purchases-recover.mjs` give every old buyer their key; they can enter it any time. Nobody is emailed.

Privacy claim: Lenses collects nothing about your displays or settings. The only network request is the Sparkle update check.

## Delivery chain

1. `checkout.mjs`: `"lenses": { envKey: "STRIPE_PRICE_LENSES", amount: 499, ... }`. The env Price wins when set: product
   `prod_VZncC6arvZzEdp`, price `price_1UYe0sJkzNxf3fKqgthDxYXu` ($4.99 one-time, live, created 2026-11-05 with Ben's approval);
   the inline 499 is the fallback. Session metadata `product` = `lenses`. Refund line in `REFUND_TEXT`; it must
   match the Refunds sentence in the Lenses section of `site/terms/index.html` word for word (`lenses-purchase.test.mjs` and
   `trial-buy-path.test.mjs` compare them).
2. `stripe-webhook.mjs`: `lenses` is in `BLOB_DELIVERED_PRODUCTS`; the receipt email carries the link to
   `/lenses/success/?session_id=...`, the generic license-key block (`licenseKeysForSession`) and one plain note (macOS 14,
   Apple silicon, Open at Login option).
3. `/lenses/success/` calls `lenses-download.mjs?session_id=cs_...` for `{product, files:[{key,label,url}]}` and links the
   `&file=Lenses-x.y.z.dmg` stream. The function checks the session is paid, not refunded or disputed (`revocationFor`), and
   that `metadata.product === "lenses"` exactly. It serves the newest version by semantic sort and any older named DMG. It
   streams from the private Blobs store `lenses-files`.
4. `purchases-recover.mjs` needs no Lenses code: it lists the purchase as a download page and adds the key line from
   `licenseKeysForSession`. `purchase-license.mjs` `KEYED_PRODUCTS` includes `lenses`, which is what the success page's
   `/license-keys.js` box reads.
5. Also registered: `sales.mjs` (site map), `stats.mjs` (`PRODUCT_PAGES`, chat-page pattern), `followup.mjs` (the day-14 "what
   do you use it for" email), `managed-payments.mjs` (tax code `txcd_10202000`, same as the other Mac apps),
   `support-message.mjs` (topic), `scripts/traffic-dashboard/traffic_dashboard.py` (name maps, group and colour).

## Three doors on `lenses-download.mjs`

1. Purchase door: `?session_id=cs_...` (above).
2. Trial door: `?trial=1`, public, no Stripe call, 20 per IP per day, serves the newest DMG. It answers 404 `no_trial` until a
   version >= 1.1.0 is staged, so the free trial can never hand out 1.0.0 (which has no license check).
3. Update door (Sparkle): `?feed=1` (appcast), `?update=Lenses-x.y.z.dmg`, `?stats=1`. Needs the header `X-Lenses-Channel`
   equal to env `LENSES_UPDATE_TOKEN` (constant-time compare; no env value means closed). The feed's enclosure URLs are rewritten
   to the update door unless the appcast is signed. The app bakes the token into Info.plist (`LensesUpdateChannelToken`).

## Blobs store and publishing a release

Store `lenses-files` (private) holds `Lenses-<x.y.z>.dmg` and `appcast.xml`; `lenses-stats` holds download counters. The app
repo's `scripts/publish-release.sh` uploads a release (DMG first, then the appcast) and verifies it; the Sparkle key is the
keychain account `lenses`, backed up under `~/.config/purplelink/sparkle-keys/`. Manual form:

```
netlify blobs:set lenses-files Lenses-1.1.0.dmg --input /path/to/Lenses-1.1.0.dmg --force
netlify blobs:set lenses-files appcast.xml --input /path/to/appcast.xml --force
netlify blobs:list lenses-files
```

The file name must match `Lenses-<digits>.<digits>.<digits>.dmg` exactly or the function ignores it. Verify the upload against
the local file's size or sha256 afterwards. Uploading takes effect at once: no site build is needed. To withdraw a version,
`netlify blobs:delete lenses-files Lenses-x.y.z.dmg --force`. Product-page version text waits for the next scheduled build.

Go-live order: set `LENSES_UPDATE_TOKEN` in Netlify (local copy `~/.config/purplelink/lenses-update-token`), confirm
`PURPLELINK_LICENSE_PRIVATE_KEY` is set, upload the 1.1.0 DMG and appcast, then let the site PR deploy at the next slot.

## Tests

- `netlify/tests/lenses-download.test.mjs`: session checks (Suite session, bundle with and without Lenses), newest-DMG listing, streaming, bad file
  names, no release, the trial door (1.0.0 guard, rate limit), the token-gated feed and update door.
- `netlify/tests/lenses-license.test.mjs`: LN1 key shape, isolation from other products, determinism, no seed gives no key, Suite.
- `netlify/tests/lenses-purchase.test.mjs`: catalog entry ($4.99 inline), refund text against Terms, receipt email with the
  link and an LN1 key, Suite email naming the Lenses download and key, Lenses as a bundle part, recovery email.
- Product page tests live in `netlify/tests/lenses-site.test.mjs` (page owner, not this file).

## Not verified

- No live purchase has been made. Run one with a one-use 100%-off promotion code once the first DMG is in `lenses-files`, and
  check the receipt email, the success page, the download and the refund path.
- The receipt note says Lenses has an Open at Login option in its menu. That comes from the facts file; the app repo was not
  on disk when this was written, so it is not checked against the app. The email makes no claim about first launch.
- Nothing here has been deployed. A push to `main` does not build (batched builds); see `CLAUDE.md`, "Deploy". The new function
  and the checkout entry are server code, but this launch is not a reason for `[deploy now]`; wait for the 06:00 or 17:00
  Eastern slot unless Ben decides otherwise.
- The Lenses Stripe session metadata (`product=lenses`) is only exercised by tests, not by a real Checkout Session.

## Video on the product page
`site/lenses/index.html` embeds the v2 video, `Lkc1RzLbGCs` (2026-11-06: before/after for each setting, 60 vs 120 Hz
slowed 4x), with the click-to-load `yt-embed` block (youtube-nocookie, styles in `motion.css`); the poster is its thumbnail A.
The Short is `2PWYkaGT-6I`. The v1 launch videos (`Lt6G-s0_UlQ`, Short `86CL2_aWajw`) are replaced. Add a `VideoObject`
to the JSON-LD once v2 is public. The before/after stills in `site/assets/lenses/` come from
`video/build-lenses-stills.mjs`; they are simulated views, and the page says so.
