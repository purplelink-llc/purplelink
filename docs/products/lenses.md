# Lenses: paid macOS app, store runbook

Store side built 2026-11-05 on the `lenses-launch` branch. The app lives in its own private repo
(`purplelink-llc/Lenses`, local `/Volumes/Extreme SSD/Lenses`); the launch facts file written that day is the source of every
claim on the page. Name: Lenses (always capitalised), slug and checkout key `lenses`, bundle id `llc.purplelink.Lenses`.

Lenses is a menu bar app for display glasses (macOS 14 or later, Apple silicon). When the glasses are plugged in it applies a
profile (sharp HiDPI mode, 120 Hz where offered, layout, edge margin, night tint, Dark Mode and a bigger pointer for one
profile); on unplug or quit it puts the Mac back. Tested on RayNeo Air; it also recognises XREAL and VITURE by display name
(untested on them) and any other glasses through "Use this display as my glasses". Notarized direct download, not the Mac
App Store (it uses private macOS display calls).

**$4.99 once, USD. A paid download only.** No license key, no free trial, no public download, no Sparkle updater, no trial
reminder emails. 14-day refund like the other apps. Sold on its own: not in the Mac Suite and not a bundle part
(`netlify/lib/bundles.mjs` is untouched), so a Suite or bundle session gets `not_entitled` from the download function.

Privacy claim: Lenses collects nothing and makes no network requests.

## Delivery chain

1. `checkout.mjs`: `"lenses": { envKey: "STRIPE_PRICE_LENSES", amount: 499, ... }`. The env Price wins when set: product
   `prod_VZncC6arvZzEdp`, price `price_1UYe0sJkzNxf3fKqgthDxYXu` ($4.99 one-time, live, created 2026-11-05 with Ben's approval);
   the inline 499 is the fallback. Session metadata `product` = `lenses`. Refund line in `REFUND_TEXT`; it must
   match the Refunds sentence in the Lenses section of `site/terms/index.html` word for word (`lenses-purchase.test.mjs` and
   `trial-buy-path.test.mjs` compare them).
2. `stripe-webhook.mjs`: `lenses` is in `BLOB_DELIVERED_PRODUCTS`; the receipt email carries the link to
   `/lenses/success/?session_id=...` and one plain note (macOS 14, Apple silicon, Open at Login option). No key block.
3. `/lenses/success/` calls `lenses-download.mjs?session_id=cs_...` for `{product, files:[{key,label,url}]}` and links the
   `&file=Lenses-x.y.z.dmg` stream. The function checks the session is paid, not refunded or disputed (`revocationFor`), and
   that `metadata.product === "lenses"` exactly. It serves the newest version by semantic sort and any older named DMG. It
   streams from the private Blobs store `lenses-files`.
4. `purchases-recover.mjs` needs no Lenses code: it lists the purchase as a download page with no key line, because it reads
   `BLOB_DELIVERED_PRODUCTS`. `purchase-license.mjs` is deliberately NOT changed: `KEYED_PRODUCTS` there is the list of products
   that have a key, and Lenses has none.
5. Also registered: `sales.mjs` (site map), `stats.mjs` (`PRODUCT_PAGES`, chat-page pattern), `followup.mjs` (the day-14 "what
   do you use it for" email), `managed-payments.mjs` (tax code `txcd_10202000`, same as the other Mac apps),
   `support-message.mjs` (topic), `scripts/traffic-dashboard/traffic_dashboard.py` (name maps, group and colour).

## Blobs store and publishing a release

Only one store: `lenses-files` (private), holding `Lenses-<x.y.z>.dmg`. Nothing else: no appcast, no stats store, no env var.
Create it by uploading the first DMG from a checkout of this repo (the CLI must be logged in to the Purplelink site):

```
netlify blobs:set lenses-files Lenses-1.0.0.dmg --input /path/to/Lenses-1.0.0.dmg --force
netlify blobs:list lenses-files
```

This is the same command the other apps' `scripts/publish-release.sh` use (for example Keyfeel's). The file name must match
`Lenses-<digits>.<digits>.<digits>.dmg` exactly or the function ignores it. Verify the upload against the local file's size or
sha256 afterwards. Uploading takes effect at once: no site build is needed, because the function reads Blobs on each request.
To withdraw a version, `netlify blobs:delete lenses-files Lenses-x.y.z.dmg --force`.

Because there is no updater, a later version is a new DMG in the store; buyers get it from the same link in their receipt
email ("always hands you the newest version"). Version text on the product page waits for the next scheduled build.

## Tests

- `netlify/tests/lenses-download.test.mjs`: session checks, newest-DMG listing with no `license` field, streaming, bad file
  names, no release, no public or update door.
- `netlify/tests/lenses-purchase.test.mjs`: catalog entry ($4.99 inline), refund text against Terms, receipt email with the
  link and no key, Suite email without Lenses, recovery email.
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
