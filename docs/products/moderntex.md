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
- **Free trial (public, since 1.0.2):** `?trial=1` streams the newest
  `ModernTex-Trial-x.y.z.dmg`, no session, 20 downloads per IP per day. The trial
  edition is the same source built with `MODERNTEX_EDITION=trial`: seven days from
  first launch (Keychain + Application Support, earliest wins), then `TrialExpiredView`
  replaces the window. It ships with NO Sparkle feed, so it cannot update into the
  paid app, and its filename matches neither the buyer list nor the appcast.
  Cut it with `MODERNTEX_VERSION=x.y.z MODERNTEX_EDITION=trial scripts/build-release.sh`
  after the paid release of the same version. The site fires `trial_download`
  on the link click; `stats.mjs` counts it.
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
`orders@purplelink.llc` via Resend (`RESEND_API_KEY`, the sending-only "purplelink-netlify" key in the Resend dashboard), reply-to ben@purplelink.llc, because
Stripe's receipt carries no download link. A send failure alerts the operator
(`ALERT_EMAIL_TO` = ben@purplelink.llc) with the link to forward by
hand; it never changes the webhook's 200 to Stripe.

## Follow-up emails

After delivery, `stripe-webhook.mjs` posts `{session_id, email, product: "moderntex"}`
to the backend's `/lifecycle/register` (same `x-webhook-secret` as register-token).
That seeds `customer_lifecycle_dict` with `product: "moderntex"`, and the daily
`lifecycle_email_sweep` sends two emails from `backend/latextools/delivery.py`:
`html_lifecycle_mtx_tips` on day 3 and `html_lifecycle_mtx_before_submit` on day 21
(links carry `utm_campaign=mtx-d3` / `mtx-d21`). There is no win-back. The shared
lifecycle unsubscribe applies, and the privacy page describes the sequence.
A failed register is logged in the function log, not alerted: the buyer
already has the key. Needs both deploys (`deploy.sh` and `deploy.sh --backend`).

Trial sign-ups: after a trial-download click, `/moderntex/` reveals an optional
email form (`[data-trial-signup]` in `site.js`) that posts to the public
`/lifecycle/trial` (rate-limited per IP, honeypot `website`). It stores
`customer_lifecycle_dict["trial:<email>"]` with `product: "moderntex-trial"`,
sends `html_lifecycle_trial_setup` at once, and the sweep sends
`trial_features` (day 4) and `trial_ending` (day 6). A ModernTex purchase from
the same address marks the trial entry finished (`converted_at`), which also
gives a trial-to-paid count. Campaign tags: `mtx-trial-1`, `-4`, `-6`.

## Releasing a version

From the ModernTex repo, on a clean commit:

```
MODERNTEX_VERSION=1.0.2 scripts/build-release.sh          # stages, does not publish
MODERNTEX_VERSION=1.0.2 MODERNTEX_EDITION=trial scripts/build-release.sh   # then the trial
scripts/publish-release.sh 1.0.2                            # then, after testing the staged DMG
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

## Lost keys

`/recover/` posts an email address to `netlify/functions/purchases-recover.mjs`,
which lists paid Checkout Sessions for that address in Stripe
(`customer_details[email]`, as typed and lower-cased), keeps ModernTex and kit
purchases, and emails that address a newly minted key
(`issueModernTexLicense`, exported from `stripe-webhook.mjs`) plus the latest
ModernTex download page and each kit's download page. Same answer for every
address; 3 requests per address and 20 per IP per UTC day (Blobs
`rate-limits`). Tests: `node --experimental-test-module-mocks --test netlify/tests/*.test.mjs`
(run `npm install` first).
