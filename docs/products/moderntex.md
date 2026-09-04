# ModernTex — paid macOS app, live status

ModernTex 1.x is sold on purplelink.llc/moderntex for **$10 one-time**, updates included.

## Stripe (live mode)

| Item | Value |
|---|---|
| Product | `prod_VCVCqJD98UKu3t` (ModernTex) |
| Price | `price_1UC6BrJkzNxf3fKqjQwyoJqe` ($10.00 USD, one-time) |
| Env var | `STRIPE_PRICE_MODERNTEX` (production context) |
| Product key | `moderntex` in `netlify/functions/checkout.mjs` |
| Success page | `/moderntex/success/?session_id=cs_…` (`site/moderntex/success.js`) |

## Delivery

`netlify/functions/moderntex-download.mjs` streams from the private `moderntex-files`
Netlify Blobs store. Two doors:

- **Buyers:** `?session_id=cs_…` (list) and `&file=ModernTex-x.y.z.dmg`. The function
  checks the session on our Stripe account is paid and carries `metadata.product=moderntex`.
  The list always offers the newest DMG in the store.
- **In-app updates (Sparkle):** `?feed=1` and `?update=ModernTex-x.y.z.dmg`, requiring
  the header `X-ModernTex-Channel: <MODERNTEX_UPDATE_TOKEN>` (Netlify env, production).
  ModernTex's `build.sh` compiles that token into the app (`MTUpdateChannelToken` in
  Info.plist) and `UpdaterService` sends it on every Sparkle request. It keeps the update
  channel off the open web; it is not a licence check.

Nothing under `site/moderntex/` is a binary. `/moderntex/download/*` and
`/moderntex/appcast.xml` 301 to the product page (they were public for a few hours on
2026-09-04 before the paywall).

## Buyer email

`stripe-webhook.mjs` emails every ModernTex (and kit) buyer the success-page link from
`orders@purplelink.llc` via Resend (`RESEND_API_KEY`), reply-to ben@purplelink.llc, because
Stripe's receipt carries no download link. A send failure alerts the operator
(`ALERT_EMAIL_TO`, which must be set for alerts to go anywhere) with the link to forward by
hand; it never changes the webhook's 200 to Stripe.

## Releasing a version

From the ModernTex repo, on a clean commit:

```
MODERNTEX_VERSION=1.0.1 scripts/release.sh
```

It builds universal, signs (notarizes when the `moderntex` notarytool profile exists),
signs the appcast with the keychain EdDSA key, and uploads the DMG plus `appcast.xml`
to the Blobs store via `netlify blobs:set`. Update the version text on
`site/moderntex/index.html` and the changelog, then `bash scripts/deploy.sh`.

## Rotating the update token

```
netlify env:set MODERNTEX_UPDATE_TOKEN <new> --context production --force
```

then redeploy the site AND cut a new app release (older installs keep the old token and
stop seeing updates, so rotate only when you must).
