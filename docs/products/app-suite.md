# Purplelink Mac Suite

$54.99 once: ModernTex + Outbound Veil + Legroom + Keyfeel + Tapefolio + Vitae Plus for life. Added 2026-10-04 at $39
(three apps); Legroom joined and the price went to $49 on the Legroom launch branch (2026-10-05); Keyfeel joined and the
price went to $54 on the `keyfeel-store` branch (2026-10-07, see `keyfeel.md`); on 2026-10-07 the owner decided every app
price ends in .99, so the Suite became $54.99 (Outbound Veil $29.99, Legroom $9.99); Tapefolio joined on 2026-10-09 with
the price left at $54.99 by the owner's decision (see "Tapefolio joined" below and `tapefolio.md`).

## Panely and Summonly joined (2026-10-12, prepared, not live), price unchanged
Panely ($9.99, `panely.md`) and Summonly ($9.99, `summonly.md`) are the sixth and seventh apps, so the Suite is seven apps and Vitae Plus, eight
parts in custom bundles, and stays $54.99 by Ben's decision (2026-10-11). The parts come to $143.92 the first year (the page rounds to $144; the
test `legroom-site.test.mjs` checks the rows against the shown total). Prepared on branch `new-apps/launch-day`, which must not merge before both
releases are published: it changes the Suite's entitlement, checkout line name, emails, success page and every page footer. Per-app terms sections
for Panely and Summonly are drafts for Ben to read. To do by hand: re-render `site/assets/og/mac-suite.png` from `_gen.html` (`?t=mac-suite`;
the kicker now says Eight Mac apps) and decide how the home dock shows ten products.

## Tapefolio joined (2026-10-09), price unchanged
Tapefolio ($29.99 once, `tapefolio.md`) is the sixth part and the Suite stays $54.99; `amount: 5499` in `checkout.mjs`
was not touched. The first-year parts now come to $123.95 (ModernTex $19.99, Outbound Veil $29.99, Legroom $9.99,
Keyfeel $9.99, Tapefolio $29.99, Vitae Plus counted at a round $24, as every earlier version of this note did). At the
$23.99 the Suite page lists beside Vitae Plus the exact sum is $123.94; both round to $124, which is what the page shows
(`netlify/tests/legroom-site.test.mjs` checks the rows against the shown total). The earlier $93.96 / $94 figures in the
history below were the five-app totals. Nobody who already bought the Suite at $39, $49, $54 or $54.99 pays more:
their `app-suite` session unlocks `tapefolio-download` and gets a Tapefolio key (the key comes from the buyer's address,
so a Suite buyer and a Tapefolio-only buyer with the same address get the same key). The Terms say so without naming a
price, and a refund is still "the full amount you paid". Everything that names the contents changed in the same branch:
`checkout.mjs` (line name), `stripe-webhook.mjs` and `purchases-recover.mjs` (the page "has six things", plus the
Tapefolio key and first-run note), `site/suite/*` (rows, card, FAQ, JSON-LD, success page and script), Terms, `llms.txt`,
the "Also in the Mac Suite" lines on the five app pages, the Vitae Plus page, the home and products Suite sentences
(now $124), `site/site.js` (promo text) and `site/assets/og/_gen.html`. Tapefolio is the only app that needs macOS 26 and
Apple silicon, so the Suite FAQ says so. **To do by hand:** re-render `site/assets/og/mac-suite.png` from `_gen.html`
(`?t=mac-suite`, 1200x630); it still says five apps. The Suite page also shows no Tapefolio icon (none exists yet).

## Why $54.99
(Written before Tapefolio joined: the parts then came to $93.96.) The 2026-10-07 .99 pricing decision moved Outbound Veil from $29 to $29.99, Legroom from $9 to $9.99 and the Suite from
$54 to $54.99. The parts now come to $93.96 for the first year (ModernTex $19.99, Outbound Veil $29.99, Legroom $9.99,
Keyfeel $9.99, Vitae Plus $24; the page rounds to $94). The contents did not change, so $54 buyers keep everything and
the Terms say only that the price changed. The history below is why it was $54, $49 and $39.

### Why $54 (history)
Keyfeel ($9.99 once) joined the Suite and the price rose by $5, so the parts came to $91.98 for the first year
(ModernTex $19.99, Outbound Veil $29, Legroom $9, Keyfeel $9.99, Vitae Plus $24; the page rounded to $92). Existing $39
and $49 buyers keep everything and get Keyfeel too: their `app-suite` sessions unlock `keyfeel-download`, and a refund
is "the full amount you paid", so the pages do not name a price there. Why it was $49 with four apps:

### Why $49 (history)
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
- Checkout: `app-suite` in `netlify/functions/checkout.mjs`, priced inline (`amount: 5499`), so there is no Stripe
  Price to create and no env var. Success path `/suite/success/`. Promotion codes are allowed like every product.
- Delivery: the session id is the bearer token, as for every Blobs-delivered product.
  - `moderntex-download.mjs`, `outbound-veil-download.mjs`, `legroom-download.mjs`, `keyfeel-download.mjs` and `tapefolio-download.mjs` accept `metadata.product` of their own key or `app-suite`.
  - `vitae-license.mjs ?session_id=` signs a Vitae Plus key for an `app-suite` session: the same v2 format, plan
    `lifetime`, exp 100 years out, id = sha256(session id)[0:16]. The shipped Vitae app verifies any plan string and
    refreshes only inside the last 10 days of a key, so it never calls refresh for these. No app change was needed.
    `manage` and `refresh` return 404 for these keys (no subscription behind them).
- Email: `stripe-webhook.mjs` lists `app-suite` in BLOB_DELIVERED_PRODUCTS, so the buyer gets the suite page link and
  a fresh ModernTex license key (MTX1-...); the email says the page has six things (five downloads and the Vitae key), carries the Keyfeel and Tapefolio keys and the Keyfeel Input Monitoring note and the Tapefolio first-run note. Duplicate Stripe deliveries are deduped as for the other products.
- Recovery: `/recover/` (purchases-recover.mjs) re-sends the suite page link and a new ModernTex key;
  `/vitae/plus/recover/` (vitae-license.mjs recover) also includes lifetime keys found by the email on the session.
- Dashboard: origin/main already maps `app-suite` to its own "Mac Suite" line (sales.mjs, traffic_dashboard.py); nothing to add here.
- Pages: `/suite/` (product), `/suite/success/` (noindex; the ModernTex, Outbound Veil, Legroom, Keyfeel and Tapefolio downloads and the Vitae
  key, fetched independently so one failure never hides the others), Terms section, cross-links from Outbound Veil,
  Vitae Plus, Legroom and /products/. Legroom's Terms say "updates to the version you bought" (no major-version promise),
  and the Suite page repeats that for Legroom while keeping "forever" for ModernTex and Outbound Veil and "all updates" for Keyfeel and Tapefolio.

## Known gap
Vitae's Settings tab labels any non-annual plan "$3 a month" (changing to $2.99 with the next Vitae release) (PlusSettingsTab.swift line 27), so a Suite key shows a
price next to the plan until Vitae ships a small update that handles `plan == "lifetime"`. The success page says to
ignore it. The key works regardless.

## Tests
`node --experimental-test-module-mocks --test netlify/tests/{checkout,vitae-license,purchases-recover,suite-entitlement,suite-webhook,legroom-download,legroom-site,keyfeel-download,keyfeel-site,tapefolio-download,tapefolio-license,tapefolio-site}.test.mjs`.
One test in purchases-recover.test.mjs ("answers the same whether or not anything matched") fails on Node 26 before and
after this change: the test signs ModernTex keys with a random private key paired to the real public key, and Node 26
rejects that JWK. It passes on Node 22.

## Go-live checklist (owner)
1. Push to main (a push deploys). The Suite itself needs no env var or Stripe object; Legroom's are in `legroom.md` and
   Keyfeel's in `keyfeel.md`, Tapefolio's in `tapefolio.md`. Do not deploy the Tapefolio branch before Tapefolio is ready
   to release: it changes the Suite copy and its success page at once.
2. One real purchase on the live site, then a refund: check the success page shows the five downloads and the keys, the
   email arrives with a working ModernTex key, and the Vitae key activates in Vitae.
3. Optional: a Vitae update labeling the lifetime plan.


## Custom bundles (added 2026-10-11)

Pick any 2 of the six parts for $34.99, or any 3 for $44.99, the same price whichever parts. The six parts are the five apps and
a lifetime Vitae Plus key; all six stays the Suite at $54.99, and there is no pick 4 or 5 (it would sit within $5 of the Suite). The
picker on `/suite/` sends four or more parts to the Suite, and refuses a pair or triple that costs less bought separately.

- **Price analysis:** `docs/growth-briefs/custom-bundle-pricing-2026-10-11.md` (git-ignored; model in `custom-bundle-model-2026-10-11.py`).
  Rules: every bundle costs more than the dearest single app ($29.99); price against the dearest combination, not the average; the Suite
  stays the best value; cheap pairs stay cheaper apart. Read after 60 days, change a price only on 30 or more bundle checkout clicks.
- **Code:** `netlify/lib/bundles.mjs` (table, parsing, `entitledParts`), products `bundle-2` and `bundle-3` in `checkout.mjs` (client sends only
  `apps`; Stripe metadata `product` and `apps`), the five `*-download.mjs` doors and `vitae-license.mjs` accept a bundle that names their part,
  `licenseKeysForSession(product, sid, { apps })` issues only the chosen apps' keys (the same keys the Suite gets for that session),
  `purchase-license.mjs` returns `parts` so `/suite/success/` (`success.js`) hides the rest, and the purchase and recovery emails name the parts.
- **Page:** `site/suite/bundle.js` and `bundle.css`; its price table is checked against the server's in `netlify/tests/custom-bundles.test.mjs`.
- **Reading the ModernTex price checkpoint (2026-11-08):** a bundle that includes ModernTex is not a ModernTex order in `product_funnel.json`;
  count it as one when reading the checkpoint.
- **Vitae Plus lifetime** is a standing commitment with no later revenue; the Suite already carries it.
