# Formring: paid macOS app, store runbook

Store side built 2026-11-02 on the `formring-store` branch (worktree `/Volumes/Extreme SSD/_worktrees/Purplelink LLC/formring-store`),
copied from Legroom (the closest app on the shared license scheme) and Lenscrib (the hidden-page pattern). The app is built in its
own repo, `/Volumes/Extreme SSD/Formring`; its `README.md`, `docs/designs/formring-1.0.md` and `docs/screenshots/` are the source of
every claim on the page. Name: Formring, slug `formring`, page `/formring/`, success page `/formring/success/`.

Formring is a macOS 14+ app (universal binary, Apple silicon and Intel) that converts files from a ring of actions at the pointer:
hold Option while dragging files, drop them on a slice, and the result is saved next to the original. The same actions are in the
menu-bar item, the Dock icon and Finder's Services menu. 50 actions: images, PDFs, video, audio, transcription, documents, Markdown,
fonts, archives. History with Undo (moves results to the Trash). Everything runs on the Mac with Apple frameworks; the only network
use is the Sparkle update check. Sold at **$14.99 once**, USD, one DMG that runs free for 7 days from first launch and then needs a
license key (the ring still opens after the trial; running an action asks for a key; History and Undo keep working). One key works
on two Macs. 14-day refund like the other apps.

**Copy rule:** the page says only what the app's README and design doc say, carries no percentage (the test fails on any), names
nothing that is not built (no PowerPoint or Excel conversion, no watch folders, no App Store edition, no optional engines), and says
plainly what the app does not do (PDF to Word loses layout, background removal can be poor, some actions depend on the Mac).
`netlify/tests/formring-site.test.mjs` enforces these.

## Licensing: the shared scheme, and the Suite gate

Formring uses **PurplelinkLicenseV1** (prefix `FR1`, slug `formring`), the same scheme as Outbound Veil and Legroom, not a separate
one like Lenscrib. The entry is in `LICENSED_PRODUCTS` in `netlify/lib/license.mjs`:

    formring: { prefix: "FR1", label: "Formring", appPath: "/formring/", inSuite: false }

No new signing key and no new env var for keys: it signs with the existing `PURPLELINK_LICENSE_PRIVATE_KEY` and the app embeds the
existing public key `d8gyRHTJVAivaL2wx4m1dQTLxrfE2htFhxzNDF8dFs4=`. Keys are derived from the Stripe session id, so the success
page (`license-keys.js` via `purchase-license.mjs`), the receipt email and `/recover/` always show the same key.

**Suite gate (a launch decision for Ben).** `licensedSlugsFor("app-suite")` used to return every key of `LICENSED_PRODUCTS`, so adding
Formring would have handed every past Mac Suite buyer an `FR1` key (on their success page, receipt link and recovery email) for an
app that is still hidden. `inSuite: false` closes that: `suiteIncludes(slug)` in `license.mjs` is false for it, `licensedSlugsFor`
leaves it out of the Suite, and `formring-download.mjs` refuses an `app-suite` session (`not_entitled`) and
`formring-reminder.mjs` does not count a Suite order as a Formring purchase. Custom bundles never include it (it is not in
`BUNDLE_PARTS`). Outbound Veil and Legroom are unchanged; `formring-license.test.mjs` pins their keys byte for byte against the code
as it was before.

At launch Ben decides whether past and future Suite buyers get Formring:

- **Yes:** set `inSuite: true` (or delete the field) in `LICENSED_PRODUCTS`, then do the rest of the Suite work, which is separate
  and not done here: add a part to `netlify/lib/bundles.mjs` only if it should be in pick-2 and pick-3 (that changes bundle
  pricing), the Suite page and success page, the Suite emails (`stripe-webhook.mjs`), the recovery email, the refund text for
  `app-suite` in `checkout.mjs`, Terms, and the tests that pin them. The design doc says "added to the Suite"; that was a plan, not a
  decision. The gate tests (`formring-license.test.mjs`, `formring-purchase.test.mjs`, `formring-download.test.mjs`) include a "gate flipped" case that shows what
  changes.
- **No:** leave it. Formring is then sold on its own, like Lenscrib.

## What is in the branch

| Piece | Files |
|---|---|
| License keys | `netlify/lib/license.mjs` (`formring` entry, `inSuite`, `suiteIncludes`), `netlify/tests/formring-license.test.mjs` |
| Delivery | `netlify/functions/formring-download.mjs` (a copy of `legroom-download.mjs`), `netlify/tests/formring-download.test.mjs` |
| Trial emails | `formring-reminder.mjs`, `formring-reminder-send.mjs` (daily 14:50 UTC schedule), engine `netlify/lib/trial-reminder.mjs` |
| Checkout, receipt, recovery | `checkout.mjs` (`formring`, `amount: 1499`, refund line), `stripe-webhook.mjs` (`BLOB_DELIVERED_PRODUCTS`, receipt note; the key comes from `licenseKeysForSession`), `purchase-license.mjs` (`KEYED_PRODUCTS`), `sales.mjs`, `followup.mjs`, `managed-payments.mjs`; `purchases-recover.mjs` needed no change (it is generic over `licenseKeysForSession`) |
| Stats and dashboard | `stats.mjs` (`fr_trial_download` counted as `frTrialDownloads`, `formring` in `PRODUCT_PAGES`), `traffic_dashboard.py` |
| Pages | `site/formring/` (`index.html`, `launch.js`, `formring.css`, `success.js`, `success/`, `img/`), Terms and Privacy sections, `scripts/apply_layout.py` (section marker only) |
| Media | `site/assets/formring-icon.webp`, `site/assets/video/formring-demo.mp4` and `formring-poster.webp` |
| Demo video source | `video/src/formring/FormringDemo.jsx`, composition `FormringDemo` in `video/src/Root.jsx`, `video/build-formring.mjs`, stills in `video/assets/formring/` |
| Tests | `formring-license`, `formring-download`, `formring-purchase`, `formring-site` (all `netlify/tests/formring-*.test.mjs`); `tapefolio-site.test.mjs` and `lenscrib-site.test.mjs` strings updated for the new Terms and Privacy wording |

Safe to merge now: nothing is linked and the page is switched off. There is no nav, footer, home, products, pricing, suite, sitemap,
search index or llms link to `/formring/` (a test asserts it), and the page is `noindex, follow`. The trial link has no `href`, the Buy
button is `disabled`, and the hero says "Not released yet".

The checkout itself is not gated: `POST /.netlify/functions/checkout {"product":"formring"}` returns a real Stripe session as soon as
this deploys. Nothing on the site calls it while the buttons are dead.

## Release gate

`site/formring/launch.js` holds the only page switch: `window.FORMRING_LAUNCH = { live, version, sizeMb, released }`. Until `live` is
`true` and `version` (x.y.z), `sizeMb` (whole number) and `released` (YYYY-MM-DD) are all valid, the trial link has no `href` and is
`aria-disabled`, the Buy button is `disabled`, the hero says "Not released yet", and the sticky bar is removed. The PRE-LAUNCH GUARD
test in `formring-site.test.mjs` pins the shipped state; delete it at launch, as Tapefolio did.

The trial door `formring-download?trial=1` is public but stays closed while nothing is released: with no DMG in `formring-files` it
answers 404 `no_trial`. There is no separate trial build; the trial door serves the same newest `Formring-x.y.z.dmg` buyers get, and
the key is the paywall.

## Stripe

Nothing to create. `formring` is priced inline in `checkout.mjs` (`amount: 1499`, name "Formring for macOS", success path
`/formring/success/`), the way Keyfeel, Tapefolio and Lenscrib are, so there is no Stripe Price and no `STRIPE_PRICE_FORMRING`
variable (Legroom and Outbound Veil use a Price; the newer apps do not). Session metadata carries `product` = `formring`. Tax code
`txcd_10202000` is in `managed-payments.mjs` like the other apps. No Stripe change was made.

## Env vars and Blobs (NOT set yet; set at launch)

| Item | Value |
|---|---|
| `FORMRING_UPDATE_TOKEN` | Netlify production env var, secret, write-only. The same value is built into the app and sent as header `X-Formring-Channel` on every Sparkle request. Local copy `~/.config/purplelink/formring-update-token` (mode 600). Never print it. Takes effect after the next site deploy |
| `PURPLELINK_LICENSE_PRIVATE_KEY` | Already set (shared with Outbound Veil and Legroom). Nothing to add for Formring |
| Blobs store `formring-files` | Private. Holds `Formring-<ver>.dmg` and `appcast.xml`. Not created yet |
| Blobs store `formring-stats` | Created on the first update download; per-file counts |
| Blobs stores `fr-trial-reminders`, `fr-trial-reminder-tokens` | Created on the first reminder sign-up |

## Delivery

`netlify/functions/formring-download.mjs`, a copy of `legroom-download.mjs` with one DMG name pattern (`Formring-x.y.z.dmg`):

- Buyers: `?session_id=cs_...` lists the newest DMG; `&file=Formring-x.y.z.dmg` streams any released version. The session must be paid,
  not refunded or disputed, and carry `metadata.product` of `formring` (or `app-suite` only after the Suite gate is flipped). The
  license key is not in this response; the success page gets it from `purchase-license` through `license-keys.js`, like Legroom.
- Public trial: `?trial=1`, newest DMG, 20 per IP per day (429 after).
- Updates (Sparkle): `?feed=1`, `?update=<dmg>`, `?stats=1` need the `X-Formring-Channel` header, compared in constant time; 403
  otherwise and 403 when the variable is unset. The feed's enclosure URLs are rewritten to the `?update=` door.
- Feed URL in the app: `https://purplelink.llc/.netlify/functions/formring-download?feed=1`.

Keep the DMG well under what a Netlify function can stream in its 30 second limit (the Tapefolio notes record a 182 MB DMG truncating
at 129 MB).

## Demo video

`site/assets/video/formring-demo.mp4` (1920x1080, 24 s, silent, H.264, about 1 MB) and `formring-poster.webp`. Made with Remotion from
the app's own screenshots: `cd video && node build-formring.mjs` renders the `FormringDemo` composition to `video/out/formring/`
(gitignored), re-encodes it as limited-range yuv420p with the index first, and writes the poster frame. Copy the mp4 into
`site/assets/video/` and convert the poster with `cwebp`. Scenes: title card, the ring over a photo with a file chip dropped on the
JPEG slice, the PDF ring, the video ring, the menu-bar window with History and Undo, a closing line. Every caption is burned in; the
page also describes the video in text. The page loads it with `<video controls preload="none" poster=...>`, so nothing downloads
until played. Re-render it when the app's screenshots change.

## Releasing a version

Same shape as Legroom: a Developer-ID-signed, notarized DMG named `Formring-x.y.z.dmg` with Sparkle built in, `SUFeedURL` as above,
the update token compiled in, the shared `PurplelinkLicenseV1` public key built in. The app repo's `scripts/build-release.sh` stages
the DMG; its README says publishing is not scripted yet. A publish script must upload the DMG and `appcast.xml` to `formring-files`
and read both back byte for byte (the Legroom and Tapefolio publish scripts are the model). No separate trial build.

## Test checkout recipe (one real purchase with a 100%-off code)

Only after the DMG and appcast are in `formring-files`, `FORMRING_UPDATE_TOKEN` is set and deployed, and a deploy that carries this PR is
live. No money moves.

1. In the Stripe dashboard (live mode) create a 100% off, once, coupon and a promotion code with a maximum of 1 redemption.
2. `curl -s -X POST https://purplelink.llc/.netlify/functions/checkout -H 'content-type: application/json' -d '{"product":"formring"}'`
   and open the `url`.
3. Enter the code and an address you can read; complete it.
4. Expected: redirect to `/formring/success/?session_id=cs_live_...` with a download button and an `FR1-...` key; a receipt email
   ("Your Formring for macOS download") with the same key, "Paste a key into the matching app (Formring: "Enter license key")", and
   the macOS 14 and Option-drag note; the function log shows `delivered_by_blobs`.
5. Download the DMG and compare its SHA-256 with the upload. Open it, enter the key, confirm it unlocks, confirm a wrong key is refused.
6. `curl -s -H "X-Formring-Channel: $(cat ~/.config/purplelink/formring-update-token)" "https://purplelink.llc/.netlify/functions/formring-download?feed=1"`
   returns the appcast with the enclosure at `?update=Formring-x.y.z.dmg`; without the header it returns 403.
7. `/recover/` with the test address lists the purchase and the key.
8. Refund the test session in Stripe (housekeeping only).

## Launch checklist (owner)

1. Set `FORMRING_UPDATE_TOKEN` on Netlify (production) from `~/.config/purplelink/formring-update-token`. Do not print it. No Stripe
   price and no key variable to create (see above).
2. Build the app with the same token and header and the shared public key; stage `Formring-<ver>.dmg` and `appcast.xml` in `formring-files`.
3. Run the test checkout recipe.
4. **Decide the Suite gate** (above) and flip `inSuite` in `netlify/lib/license.mjs` as part of the launch change, or leave it.
5. Launch commit (separate from this PR): fill in `site/formring/launch.js`; delete the PRE-LAUNCH GUARD test; write the live wording into
   the static fallbacks in `index.html` (the strings the script replaces: hero status, the two gated buttons, the `data-fr-facts`
   sentence); replace the placeholder app icon (the Formring repo's `assets/brand/PLACEHOLDER` says "replace before release", and
   `site/assets/formring-icon.webp`, the video's icon and the page icon all use it); add a share card and `og:image` (the card
   generator `scripts/gen_og_cards.py` does not cover product pages; product cards are `site/assets/og/<slug>.png`); re-render the
   demo video if the icon or screenshots changed; flip `<meta name="robots">` to `index, follow`.
6. Launch-day links, none of which exist yet: nav and footer (`scripts/apply_layout.py` `FOOTER_COLUMNS`), home dock tile, products
   card and chooser, pricing row, sitemap, search index, `llms.txt` block, `gen_llms_full.py` page list, changelog entry, `/li/formring`
   style redirects in `netlify.toml`, and the support-box topic (`support-message.mjs` `TOPICS` plus `apply_support_box.py`).
7. Add the click counter in `site/analytics.js` (a `formring-download?trial=1` branch firing `fr_trial_download`, and `fr_trial_download`
   in the `FUNNEL` regex). The server side (`stats.mjs`, dashboard) is already in. It is held back only because changing `analytics.js`
   restamps every page.
8. Run `python3 scripts/apply_layout.py --check`, `python3 scripts/fingerprint_assets.py`, `python3 scripts/check_content.py --strict`.
9. Confirm the Terms and Privacy wording against the shipped app: that the only network use is the update check (app name, version,
   macOS version, update token); that nothing dropped on the app is sent; that there is no analytics; that the trial clock and key
   check send nothing.

## Open items

- Intel: the page says Apple silicon and Intel, from the design doc (universal binary). The design doc says Intel behaviour is
  unverified until manual test R11 passes on an Intel Mac or Rosetta; confirm before launch or change the page, FAQ and JSON-LD.
- The app's `docs/screenshots/history.png` renders as an empty dark rectangle (one flat colour); it is not used. The menu-bar window
  screenshot shows the history list instead. Re-render it with `FormringApp --render-screenshots` if a History window shot is wanted.
- The app icon is a placeholder (see launch step 5).
- Settings: the design mentions a per-app exclusion list; the page does not, because the vendored ring settings only expose the key
  and the on/off switch. Add it to the FAQ if the app ships one.
- Update policy: the page, FAQ, Terms and reminder email say every update is included, as for Tapefolio and Lenscrib. Ben has not stated
  a policy for Formring; change those places together if it should differ.
- Tax: `txcd_10202000` copied from the other apps; confirm with the accountant like the rest.
