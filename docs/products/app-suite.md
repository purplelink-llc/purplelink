# Purplelink Mac Suite

$49 once: ModernTex + Outbound Veil + Legroom + Vitae Plus for life. Added 2026-10-04 at $39 (three apps); Legroom joined
and the price went to $49 on the Legroom launch branch (2026-10-05).

## Why $49
Legroom ($9 once) joined the Suite and the price rose by $10, so the parts now come to $81.99 for the first year
(ModernTex $19.99, Outbound Veil $29, Legroom $9, Vitae Plus $24; the page rounds to $82). Existing $39 buyers keep
everything and get Legroom too: their `app-suite` sessions unlock `legroom-download`, and a refund is "the full amount
you paid", so the pages do not name a price there. The history below is why it was $39.

### Why $39 (history)
At launch ModernTex was $10, so $10 + Outbound Veil $29 = $39 and the pitch was "the two paid apps, Vitae Plus for life included". ModernTex went to $19.99 on 2026-10-04: the parts now come to $48.99 plus Vitae Plus ($24 a year), $73 in the first year, so the Suite at $39 is a stronger deal than at launch. Raise it if it converts too easily.
Vitae Plus alone is $24 a year ($3 a month). At launch Vitae Plus had 0 subscribers, so including it costs no
existing revenue. Net per sale after Stripe fees: $37.57 (Outbound Veil alone nets $27.86, ModernTex $9.41).
No fake "regular price" and no countdown on the page: the separate prices shown are the real ones. The next price change touches: `amount` in checkout.mjs and its test, `#price`, the button texts, the deal and sum rows and
the JSON-LD offer in site/suite/index.html, the Terms section, llms.txt, site/products/index.html, the guide
/guides/best-academic-record-tracking-software/, site/assets/og/mac-suite.png (render from _gen.html), and this file.

## How it works
- Checkout: `app-suite` in `netlify/functions/checkout.mjs`, priced inline (`amount: 4900`), so there is no Stripe
  Price to create and no env var. Success path `/suite/success/`. Promotion codes are allowed like every product.
- Delivery: the session id is the bearer token, as for every Blobs-delivered product.
  - `moderntex-download.mjs`, `outbound-veil-download.mjs` and `legroom-download.mjs` accept `metadata.product` of their own key or `app-suite`.
  - `vitae-license.mjs ?session_id=` signs a Vitae Plus key for an `app-suite` session: the same v2 format, plan
    `lifetime`, exp 100 years out, id = sha256(session id)[0:16]. The shipped Vitae app verifies any plan string and
    refreshes only inside the last 10 days of a key, so it never calls refresh for these. No app change was needed.
    `manage` and `refresh` return 404 for these keys (no subscription behind them).
- Email: `stripe-webhook.mjs` lists `app-suite` in BLOB_DELIVERED_PRODUCTS, so the buyer gets the suite page link and
  a fresh ModernTex license key (MTX1-...); the email says the page has four things (three downloads and the Vitae key). Duplicate Stripe deliveries are deduped as for the other products.
- Recovery: `/recover/` (purchases-recover.mjs) re-sends the suite page link and a new ModernTex key;
  `/vitae/plus/recover/` (vitae-license.mjs recover) also includes lifetime keys found by the email on the session.
- Dashboard: origin/main already maps `app-suite` to its own "Mac Suite" line (sales.mjs, traffic_dashboard.py); nothing to add here.
- Pages: `/suite/` (product), `/suite/success/` (noindex; the ModernTex, Outbound Veil and Legroom downloads and the Vitae
  key, fetched independently so one failure never hides the others), Terms section, cross-links from Outbound Veil,
  Vitae Plus, Legroom and /products/. Legroom's Terms say "updates to the version you bought" (no major-version promise),
  and the Suite page repeats that for Legroom while keeping "forever" for ModernTex and Outbound Veil.

## Known gap
Vitae's Settings tab labels any non-annual plan "$3 a month" (PlusSettingsTab.swift line 27), so a Suite key shows a
price next to the plan until Vitae ships a small update that handles `plan == "lifetime"`. The success page says to
ignore it. The key works regardless.

## Tests
`node --experimental-test-module-mocks --test netlify/tests/{checkout,vitae-license,purchases-recover,suite-entitlement,suite-webhook,legroom-download,legroom-site}.test.mjs`.
One test in purchases-recover.test.mjs ("answers the same whether or not anything matched") fails on Node 26 before and
after this change: the test signs ModernTex keys with a random private key paired to the real public key, and Node 26
rejects that JWK. It passes on Node 22.

## Go-live checklist (owner)
1. Push to main (a push deploys). The Suite itself needs no env var or Stripe object; Legroom's are in `legroom.md`.
2. One real purchase on the live site, then a refund: check the success page shows the three downloads and the key, the
   email arrives with a working ModernTex key, and the Vitae key activates in Vitae.
3. Optional: a Vitae update labeling the lifetime plan.
