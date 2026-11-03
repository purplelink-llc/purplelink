# Suite placement audit

2026-11-03. Ben's approved item from the Adam Robinson research (rec 5): check where the free tools and trials give
away enough to remove the reason to pay, check where the $59.99 Mac Suite appears and where it should, and change
placement only. No price changes (price hold until 2027-01-12, studio rules) and no pop-ups.

## What the free side gives away

**Converters (22 pages under /tools/).** Free, unlimited, no watermark, no account, files never leave the browser.
They overlap one paid app directly: Née ($14.99, in the Suite) does the same image conversions, ICNS and favicons,
images to PDF and PDF text on the Mac. Née's own page already sends Windows and Linux visitors to these pages ("On
another computer, these free pages do the same image conversions").

Not changed: no daily cap and no watermark. Every converter FAQ says "no limit beyond the sizes above", the pages
exist to be found in search and to show how we treat files, and a cap would make that copy false. What Née sells
is different: it works in Finder on a folder at a time, saves next to the original, and handles video, audio,
documents, fonts and archives, which the web pages do not. The fix is to say so where it applies (below), not to
make the free page worse.

**Trials (7 days, full app).** A trial is the complete app with no account; after day 7 the app needs a key. That is
the right amount to give: the trial ends on its own and the price is stated on the app page. Nothing to change.

**Paper Review.** The reference check is free and the paid review is separate. Out of scope here.

## Where the Suite appears

| Place | Before | After this change |
|---|---|---|
| Nav and footer, every page | "Mac Suite" link | unchanged |
| Home | "the Mac Suite, $59.99 once" | unchanged |
| /pricing/, /suite/ | full price table | unchanged |
| App pages (ModernTex, Outbound Veil, Legroom, Keyfeel, Tapefolio, Panely, Summonly, Née) | one line by the buy button: "Or get the Mac Suite" / "Also in the Mac Suite: ..., $59.99 once" | same text, link tagged `utm_content=<app>-buy` (ModernTex's second mention under the download: `moderntex-mention-2`) |
| Vitae page | "Included for life in the Mac Suite." with no price | adds "$59.99 once with eight more Mac apps", tagged `vitae-buy` (FAQ mention: `vitae-mention-2`) |
| Converter pages | nav link only | one line shown after the first file converts: "Our nine Mac apps are also sold together in the Mac Suite, $59.99 once. Each has a free trial or a free version." Tagged `converter-done-<slug>` |
| Trial download block (after a trial click) | setup and reminder email offer | unchanged; see below |
| Trial reminder emails (Keyfeel, Legroom, Née, Outbound Veil) | single-app price only | unchanged; email, not the site |
| In-app trial-ending screens | in each app's repo | out of scope |

None of the Suite links on app pages carried a tag before, so a Suite sale could not be traced to the page line that
led to it.

## Where an app fits a converter

Added to the one-sentence app links from #554 and #557 (same `converter-crosslink` campaign, `utm_content` is the
page slug):

- Née on HEIC to JPG, WebP to PNG, AVIF to JPG, PNG to JPG and TIFF to JPG ("To convert images in Finder
  instead, Née ... saves each copy next to the original").
- Née on PNG to ICNS and PNG to ICO ("To make icons in Finder instead, Née ... builds an .icns file, an Xcode icon
  set and web favicons from one image").

The #554 skip of the image pages was wrong: Née is a direct fit there.

## Placement rules used

- Text only, below the converter or beside the existing buy line. No box, no pop-up, no banner, no countdown.
- The Suite line on converters waits for a successful conversion, so it never stands between a visitor and the
  tool, and it never appears after an error.
- One tag per placement: `utm_source=purplelink`, `utm_medium=tool` or `product-page`, `utm_campaign=suite-placement`
  (Suite) or `converter-crosslink` (single app), and a `utm_content` no other link uses.
- Clicks count as `offer_click` with meta `nee` or `suite` (added to `OFFER_APPS` in `netlify/lib/tool-counts.mjs`).

## Measuring it

- Per converter page: `offerClicks` for `suite` and `nee` in the tool counts.
- Per sale: analytics.js stores a tagged on-site arrival as the `last` touch, and checkout.mjs attaches first and
  last touch to the Stripe order. The Suite versus single-app mix by `last.t` (utm_content) is the measure the
  research named.
- Caveat: a visitor whose first touch was a direct-visit placeholder gets that placeholder replaced by the first
  tagged on-site link they click, so first-touch reports will show some `purplelink / tool` arrivals. That is the
  existing behavior for the tool offer links too (analytics.js, "A later tagged arrival still replaces it").
- Look again on 2026-12-01 (four weeks of clicks), then at the price-hold end, 2027-01-12.

## Open, for Ben

- **Trial reminder emails.** The day-6 reminder for Keyfeel, Legroom, Née and Outbound Veil names only the single
  price. One added line ("It is also in the Mac Suite, nine apps for $59.99 once") would put the Suite in the
  trial-ending path. That changes an outbound email, so it waits for a yes.
- **In-app Buy screens.** The trial-ending screen in each app links to its own buy page. A Suite mention there is an
  app release per app.
- **Trial download block.** Left without a Suite line on purpose: the visitor has just chosen one app, and asking for
  more money at that moment reads as a push.
