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
- No DMG is staged yet: Developer ID signing is unresolved. `netlify/functions/modernpaper-download.mjs` exists (see "Delivery"
  below) but answers 404 `no_release` / 500 `file_unavailable` until a DMG is uploaded to the `modernpaper-files` Blobs store. The
  success page and the buyer email still show the key and say the download link will be emailed when the first signed release is out.
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
5. Stage the first signed DMG and appcast in `modernpaper-files` (see "Delivery"), point the page's Download button at
   `/.netlify/functions/modernpaper-download?download=1`, then drop the "no download yet" copy from the page, success page and receipt email.
6. Pricing check: the Suite is $59.99, so ModernPaper at $79 alone costs more than the Suite that will contain it.

## Delivery

`netlify/functions/modernpaper-download.mjs`, a copy of `tapefolio-download.mjs` (same doors, same refund revocation and trial cap):

- Buyers: `?session_id=cs_...` lists files and returns `license`; `&file=ModernPaper-x.y.z.dmg` streams one. The session must be
  paid, not refunded or disputed (`netlify/lib/refunds.mjs`), and carry `metadata.product` of `modernpaper`, a custom bundle or
  add-on that names it, or `app-suite` **only once ModernPaper is in the Suite** (the function asks `suiteIncludes("modernpaper")`,
  so deleting `inSuite: false` from `netlify/lib/license.mjs` at launch opens it to Suite buyers with no change here).
- `license` is the MP1 key from `issueLicense("modernpaper", { sessionId })` with `PURPLELINK_LICENSE_PRIVATE_KEY`: the same key the
  receipt email and `purchase-license` show, derived from the session id. It is `null` when the secret is unset; delivery of the DMG
  is never blocked by it.
- Public download (the trial): `?download=1` (`?trial=1` also works) streams the newest `ModernPaper-x.y.z.dmg`, 20 downloads per
  IP per day (429 after), counted in the existing `rate-limits` store. Same file buyers and Sparkle get. Beta-channel versions are
  skipped (`netlify/lib/release-pick.mjs`).
- Updates (Sparkle): `?feed=1`, `?update=<dmg>` and `?stats=1` require the header `X-ModernPaper-Channel: <MODERNPAPER_UPDATE_TOKEN>`,
  compared in constant time; 403 otherwise and 403 when the variable is unset. The feed rewrites every enclosure URL to the update
  door. Set `SUFeedURL` to `https://purplelink.llc/.netlify/functions/modernpaper-download?feed=1` in the app.
- Blobs stores `modernpaper-files` (DMGs and `appcast.xml`) and `modernpaper-stats` (`downloads:<dmg>` counters, created on the first
  update download). File names are exact: `ModernPaper-1.0.0.dmg`; anything else is refused. No `netlify.toml` route or CSP change is
  needed (Tapefolio has none for delivery, and there is no new origin).
- Not yet done (Ben, outside the code): create `MODERNPAPER_UPDATE_TOKEN` in Netlify and in the app build, and upload the first DMG
  and appcast with the release script. Nothing was created by this change.
- The page has no Download button yet. The hidden page stays unlisted; add the trial link only when a DMG is staged.

Analytics: no `analytics.js` event yet; add `modernpaper_trial_download` with the launch if wanted.

## Tests

`netlify/tests/modernpaper.test.mjs` (key round trip, Suite gate, checkout with the env var set and unset),
`netlify/tests/modernpaper-download.test.mjs` (buyer, trial and update doors, refunds, Suite gate, key equals the email's key),
`site-tests/test_modernpaper_unlisted.py`.
