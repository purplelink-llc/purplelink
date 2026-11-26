# ModernPaper (hidden launch)

PDF reader and editor for academics. $79 one-time, 7-day trial, then reading, searching and read-aloud stay free; saving
annotations, forms, page tools, redaction and the Claude panel (the buyer's own API key) need a key. Mac only, no account.

## State on 2026-11-26

- Page `/modernpaper/` and `/modernpaper/success/` exist but are **unlisted**: `noindex`, not in the sitemap, search index,
  `llms.txt`, nav, footer or apps index, and no page links to them. `scripts/gen_sitemap.py`, `gen_search_index.py` and
  `gen_llms_full.py` skip a page carrying `<meta name="robots" ... noindex>`; `site-tests/test_modernpaper_unlisted.py` pins it.
- Checkout key `modernpaper`, Stripe Price in env var `STRIPE_PRICE_MODERNPAPER` (Ben creates it; nothing is created from code).
  There is deliberately no inline amount: with the env var unset, checkout answers 500 `misconfigured` and charges nothing.
- Licence: PurplelinkLicenseV1, slug `modernpaper`, prefix `MP1` (`netlify/lib/license.mjs`). Same signing secret as the other apps.
- No DMG and no Blobs store: Developer ID signing is unresolved. The success page and the buyer email show the key and say the
  download link will be emailed when the first signed release is out. There is no `modernpaper-download` function.
- `inSuite: false` keeps an MP1 key off every existing Suite buyer's success page, email and `/recover/`. It is not in
  `BUNDLE_PARTS`, so the custom bundles cannot include it.
- The macOS minimum is not stated anywhere (the app's `Package.swift` and `make-app.sh` say 14.0, the sell brief said 26).
  The page and email say "a recent version of macOS". Fill in the real minimum with the first release.

## Flips at public launch (Ben, 2026-11-26: it joins the Suite and bundles then)

Do all of them in one commit, as docs/products/nee.md "Suite gate" lists for Née.

1. `netlify/lib/license.mjs`: delete `, inSuite: false` from the `modernpaper` entry (one line).
2. `netlify/lib/bundles.mjs`: add `{ slug: "modernpaper", label: "ModernPaper" }` to `BUNDLE_PARTS` and `"modernpaper": 7900` to
   `PART_CENTS`; mirror both in `site/suite/bundle.js` (a test keeps them equal). Fix the part counts in the comments and copy.
3. `site/modernpaper/index.html`: `robots` to `index, follow`, add `og:` tags and an OG card
   (`python3 scripts/gen_og_cards.py --only modernpaper`), JSON-LD, and the "Also in the Mac Suite" line. Add the page to
   `scripts/apply_layout.py` footer and nav lists, the apps index, `site/llms.txt` and the sitemap (automatic once indexable).
4. Copy that counts Suite apps (see nee.md item 5), `app-suite` refund text in `checkout.mjs`, the Suite page, Suite success page
   and recovery list, and widen the ModernPaper email note to Suite and bundle buyers.
5. Add the download function and Blobs store, then drop the "no download yet" copy from the page, success page and receipt email.
6. Pricing check: the Suite is $59.99, so ModernPaper at $79 alone costs more than the Suite that will contain it.

## Tests

`netlify/tests/modernpaper.test.mjs` (key round trip, Suite gate, checkout with the env var set and unset),
`site-tests/test_modernpaper_unlisted.py`.
