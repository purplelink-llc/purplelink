# ModernPaper

PDF reader and editor for academics. $49 one-time, 7-day trial, then reading, searching and read-aloud stay free; saving
annotations, forms, page tools, redaction and the Claude panel (the buyer's own API key) need a key. Mac only, no account.

## State on 2026-11-27 (public)

- Public since 2026-11-27, $49 one-time (inline `amount: 4900` in `netlify/functions/checkout.mjs`; the `STRIPE_PRICE_MODERNPAPER`
  `envKey` is kept). Page `/modernpaper/` and `/modernpaper/success/` (noindex, like the other success pages). The product page is
  indexable, in the sitemap, `llms.txt`, the products page (with Buy and Add to bundle), nav and footer (`scripts/apply_layout.py`).
  OG card `site/assets/og/modernpaper.png` comes from `site/assets/og/_gen.html?t=modernpaper`.
- Licence: PurplelinkLicenseV1, slug `modernpaper`, prefix `MP1` (`netlify/lib/license.mjs`). Same signing secret as the other apps.
- Part of the Mac Suite ($99.99, eleven parts) and the custom bundles (`BUNDLE_PARTS`, `PART_CENTS` 4900, mirrored in
  `site/suite/bundle.js` and `site/products/shop.js`). Suite and bundle buyers get an MP1 key and download button on the Suite
  success page, in the Suite receipt email and in `/recover/`, the same as Née.
- macOS minimum is 14.0 (page, email, JSON-LD).
- No `modernpaper-icon*` asset exists, so the home page dock/hero strip has no ModernPaper icon; the Suite page cards use
  `purplelink-mark.svg` as a placeholder. Add the icon when it exists.
- A DMG must be staged in the `modernpaper-files` Blobs store before the Download button and buyer links work (see "Delivery");
  until then the download door answers 404 `no_release`.

## Delivery

`netlify/functions/modernpaper-download.mjs`, a copy of `tapefolio-download.mjs` (same doors, same refund revocation and trial cap):

- Buyers: `?session_id=cs_...` lists files and returns `license`; `&file=ModernPaper-x.y.z.dmg` streams one. The session must be
  paid, not refunded or disputed (`netlify/lib/refunds.mjs`), and carry `metadata.product` of `modernpaper`, a custom bundle or
  add-on that names it, or `app-suite` (ModernPaper is in the Suite since 2026-11-27).
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
- The page's Download button points at `?download=1`.

Analytics: no `analytics.js` event yet; add `modernpaper_trial_download` with the launch if wanted.

## Tests

`netlify/tests/modernpaper.test.mjs` (key round trip, Suite and bundle gates, checkout with the env var set and unset),
`netlify/tests/modernpaper-download.test.mjs` (buyer, trial and update doors, refunds, Suite gate, key equals the email's key),
`site-tests/test_modernpaper_listed.py` (indexable, in the sitemap, llms.txt and the products page).
