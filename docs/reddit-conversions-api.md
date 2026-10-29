# Reddit Conversions API (server-side Purchase for ModernTex)

A ModernTex sale that came from a Reddit ad is reported to Reddit twice: by the browser pixel
(`site/reddit-pixel.js`) and by the Stripe webhook (`netlify/lib/reddit-capi.mjs`). Both use the Stripe Checkout
Session id as the conversion id, so Reddit counts the sale once.

## How the signal travels

1. `site/analytics.js` keeps `?rdt_cid=` for 90 days (`pl_rdt`, first click wins). Nothing is kept under Do Not Track.
2. A ModernTex checkout request carries `rdt` (the click id, or an empty marker when the first touch was
   `paid:reddit` with no click id).
3. `netlify/functions/checkout.mjs` copies it to session metadata `reddit_ad=1` and `reddit_click_id` (validated).
   Only `moderntex` and `moderntex-seats`.
4. `stripe-webhook.mjs`, after delivery, posts the event. It is not awaited and never throws, so delivery and the
   2xx to Stripe are unaffected. Free ($0) orders are not reported.

## Setup (once)

1. Reddit Ads, Events Manager, your pixel, Conversions API: generate a **conversion access token**.
2. Netlify, Site configuration, Environment variables (secret, all deploy contexts):
   - `REDDIT_CAPI_TOKEN`: the token. Without it nothing is sent.
   - `REDDIT_AD_ACCOUNT_ID` (optional): the id for the request URL if Events Manager shows one other than the pixel id.
     Default is the pixel id `a2_jx9tsee4sm5h`.
   - `REDDIT_CAPI_TEST_MODE=1` (optional): sends with `test_mode: true`; Reddit then does not record the events.
     Remove it to go live.
3. Env changes need the next build to apply. Check Events Manager, Test Events, after a real Reddit-ad purchase.

Never commit the token. Logs carry only status codes.
