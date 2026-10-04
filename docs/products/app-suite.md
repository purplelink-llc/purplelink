# Purplelink Mac Suite

$39 once: ModernTex + Outbound Veil + Vitae Plus for life. Added 2026-10-04.

## Why $39
At launch ModernTex was $10, so $10 + Outbound Veil $29 = $39 and the pitch was "the two paid apps, Vitae Plus for life included". ModernTex went to $19.99 on 2026-10-04: the parts now come to $48.99 plus Vitae Plus ($24 a year), $73 in the first year, so the Suite at $39 is a stronger deal than at launch. Raise it if it converts too easily.
Vitae Plus alone is $24 a year ($3 a month). At launch Vitae Plus had 0 subscribers, so including it costs no
existing revenue. Net per sale after Stripe fees: $37.57 (Outbound Veil alone nets $27.86, ModernTex $9.41).
No fake "regular price" and no countdown on the page: the separate prices shown are the real ones. Raising to
$49 later is fine if it converts; change `amount` in checkout.mjs, `#price` and the button text in
site/suite/index.html, the offer in its JSON-LD, the Terms section, llms.txt and this file.

## How it works
- Checkout: `app-suite` in `netlify/functions/checkout.mjs`, priced inline (`amount: 3900`), so there is no Stripe
  Price to create and no env var. Success path `/suite/success/`. Promotion codes are allowed like every product.
- Delivery: the session id is the bearer token, as for every Blobs-delivered product.
  - `moderntex-download.mjs` and `outbound-veil-download.mjs` accept `metadata.product` of their own key or `app-suite`.
  - `vitae-license.mjs ?session_id=` signs a Vitae Plus key for an `app-suite` session: the same v2 format, plan
    `lifetime`, exp 100 years out, id = sha256(session id)[0:16]. The shipped Vitae app verifies any plan string and
    refreshes only inside the last 10 days of a key, so it never calls refresh for these. No app change was needed.
    `manage` and `refresh` return 404 for these keys (no subscription behind them).
- Email: `stripe-webhook.mjs` lists `app-suite` in BLOB_DELIVERED_PRODUCTS, so the buyer gets the suite page link and
  a fresh ModernTex license key (MTX1-...). Duplicate Stripe deliveries are deduped as for the other products.
- Recovery: `/recover/` (purchases-recover.mjs) re-sends the suite page link and a new ModernTex key;
  `/vitae/plus/recover/` (vitae-license.mjs recover) also includes lifetime keys found by the email on the session.
- Dashboard: origin/main already maps `app-suite` to its own "Mac Suite" line (sales.mjs, traffic_dashboard.py); nothing to add here.
- Pages: `/suite/` (product), `/suite/success/` (noindex; three downloads/keys fetched independently), Terms section,
  cross-links from ModernTex, Outbound Veil, Vitae Plus and /products/.

## Known gap
Vitae's Settings tab labels any non-annual plan "$3 a month" (PlusSettingsTab.swift line 27), so a Suite key shows a
price next to the plan until Vitae ships a small update that handles `plan == "lifetime"`. The success page says to
ignore it. The key works regardless.

## Tests
`node --experimental-test-module-mocks --test netlify/tests/{checkout,vitae-license,purchases-recover,suite-entitlement,suite-webhook}.test.mjs`.
One test in purchases-recover.test.mjs ("answers the same whether or not anything matched") fails on Node 26 before and
after this change: the test signs ModernTex keys with a random private key paired to the real public key, and Node 26
rejects that JWK. It passes on Node 22.

## Go-live checklist (owner)
1. Push to main (a push deploys). No env var or Stripe object is needed.
2. One real purchase on the live site, then a refund: check the success page shows both downloads and the key, the
   email arrives with a working ModernTex key, and the Vitae key activates in Vitae.
3. Optional: a Vitae update labeling the lifetime plan.
