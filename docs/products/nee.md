# Née: paid macOS app, store runbook

> **Renamed from AKA to Née on 2026-11-02** (Ben), before any sale, because of a name conflict. "Née" in UI and copy;
> ASCII `nee` in every id, path, URL, key prefix (`NEE1`), store (`nee-files`), env var (`NEE_UPDATE_TOKEN`) and file name.
> `/aka/` redirects to `/nee/` (netlify.toml).

Store side built 2026-11-02 on the `nee-store` branch (worktree `/Volumes/Extreme SSD/_worktrees/Purplelink LLC/nee-store`),
copied from Legroom (the closest app on the shared license scheme) and Lenscrib (the hidden-page pattern). The app is built in its
own repo, `/Volumes/Extreme SSD/Née`; its `README.md`, `docs/designs/nee-1.0.md` and `docs/screenshots/` are the source of
every claim on the page. Name: Née, slug `nee`, page `/nee/`, success page `/nee/success/`.

Née is a macOS 14+ app (universal binary, Apple silicon and Intel) that converts files from a ring of actions at the pointer:
hold Option while dragging files, drop them on a slice, and the result is saved next to the original. The same actions are in the
menu-bar item, the Dock icon and Finder's Services menu. 51 actions: images, PDFs, video, audio, transcription, documents, Markdown,
fonts, archives. History with Undo (moves results to the Trash). Everything runs on the Mac with Apple frameworks; the only network
use is the Sparkle update check. Sold at **$14.99 once**, USD, one DMG that runs free for 7 days from first launch and then needs a
license key (the ring still opens after the trial; running an action asks for a key; History and Undo keep working). One key works
on two Macs. 14-day refund like the other apps.

**Copy rule:** the page says only what the app's README and design doc say, carries no percentage (the test fails on any), names
nothing that is not built (no PowerPoint or Excel conversion, no watch folders, no App Store edition, no optional engines), and says
plainly what the app does not do (PDF to Word loses layout, background removal can be poor, some actions depend on the Mac).
`netlify/tests/nee-site.test.mjs` enforces these.

## Licensing: the shared scheme, and the Suite gate

Née uses **PurplelinkLicenseV1** (prefix `NEE1`, slug `nee`), the same scheme as Outbound Veil and Legroom, not a separate
one like Lenscrib. The entry is in `LICENSED_PRODUCTS` in `netlify/lib/license.mjs`:

    nee: { prefix: "NEE1", label: "Née", appPath: "/nee/" }

No new signing key and no new env var for keys: it signs with the existing `PURPLELINK_LICENSE_PRIVATE_KEY` and the app embeds the
existing public key `d8gyRHTJVAivaL2wx4m1dQTLxrfE2htFhxzNDF8dFs4=`. Keys are derived from the Stripe session id, so the success
page (`license-keys.js` via `purchase-license.mjs`), the receipt email and `/recover/` always show the same key.

**Suite gate (Ben decided yes on 2026-11-02; it opens at launch).** `licensedSlugsFor("app-suite")` used to return every key of `LICENSED_PRODUCTS`, so adding
Née would have handed every past Mac Suite buyer an `NEE1` key (on their success page, receipt link and recovery email) for an
app that is still hidden. `inSuite: false` closes that: `suiteIncludes(slug)` in `license.mjs` is false for it, `licensedSlugsFor`
leaves it out of the Suite, and `nee-download.mjs` refuses an `app-suite` session (`not_entitled`) and
`nee-reminder.mjs` does not count a Suite order as a Née purchase. Custom bundles never include it (it is not in
`BUNDLE_PARTS`). Outbound Veil and Legroom are unchanged; `nee-license.test.mjs` pins their keys byte for byte against the code
as it was before.

**Suite decision (Ben, 2026-11-02): YES, Née joins the Mac Suite. Done in the launch PR.** It stayed `inSuite: false` while the page was hidden, so no past
Suite buyer was handed a key for an unreleased app. The launch commit removes the field AND does all of
the following in the same commit, so the Suite never advertises or entitles something that is not live. Line numbers are as of the
rename PR; search for `Panely and Summonly` / `Panely, Summonly` to re-find them.

Price stays $59.99; the pick-2 ($34.99) and pick-3 ($44.99) prices stay too, but the "eight" count becomes "nine" everywhere it
appears (the nine parts are eight Mac apps and a lifetime Vitae Plus key). Decide the "bought separately" total on
`site/products/index.html:206` (currently $144 the first year) and add Née's $14.99.

1. **Entitlement (code)**
   - `netlify/lib/license.mjs:27-30`: set `inSuite` true or delete it; update the comment.
   - `netlify/lib/bundles.mjs:13-21`: add `{ slug: "nee", label: "Née" }` to `BUNDLE_PARTS` (after `summonly`, before `vitae-plus`);
     fix the "eight parts / seven Mac apps" wording at lines 2, 6, 60. This is what makes `entitledParts("app-suite")` and the
     pick-2/pick-3 bundles include Née, and `nee-download.mjs` already accepts both once that is true.
   - `site/suite/bundle.js:7` (the part table copy that a test keeps equal to `bundles.mjs`) and line 33 ("has all eight").
   - `netlify/functions/checkout.mjs`: `app-suite` product name at 223 and the comments at 217-225 (list and "all eight");
     refund text for `app-suite` at 136 if it names parts.
   - `netlify/functions/nee-download.mjs:3,89` and `netlify/functions/nee-reminder.mjs:31`: comments only (the gate they mention
     is now open); the code reads `suiteIncludes`.
2. **Suite page** `site/suite/index.html`: title 7; meta/OG/Twitter 8, 10, 11, 18, 19; JSON-LD 43 and the FAQ answers 140, 148, 156,
   164 (updates, trial, refund wording, macOS requirement); icon strip 250-257 (add `nee-icon.webp`); tagline 261; bundle heading
   and copy 292-293, "All eight" 299; pick-your-own checkboxes 304-311 (add `value="nee"`); app cards 329-378 (add an Née card);
   "One page, eight things" and its paragraphs 393-402; FAQ 411, 412, 414.
3. **Suite success page** `site/suite/success/index.html:37` (lead sentence), the per-app rows near 96-101 and 139 (add an Née
   download and key row), and `site/suite/success.js:2, 159-179` (the row list and "shows all eight").
4. **Suite emails and recovery**
   - `netlify/functions/stripe-webhook.mjs`: comments 101-108; the Suite email paragraphs at 394-400 ("That page has eight things",
     the download list); the Née-specific note at 494-500 should also be sent to Suite and bundle buyers (`isNee` is true only for
     `productKey === "nee"` today; widen it to any session whose entitled parts include `nee`); the key block near 478-483 if it
     lists licensed slugs by name.
   - `netlify/functions/purchases-recover.mjs:170-171` (recovery email list), and the per-app lines at 24, 102, 148, 237, 240 if
     Née needs a row there.
   - `netlify/lib/followup.mjs:38-41` (the Suite and bundle labels).
5. **Copy that counts or lists the Suite apps** (add Née, "eight" becomes "nine"): `site/index.html:288`; `site/products/index.html:206`;
   `site/pricing/index.html:274` and `site/pricing.md:16, 21`; `site/llms.txt:3, 150, 152, 237`; `site/site.js:998`; the "Also in the Mac
   Suite" lines at `site/moderntex/index.html:249, 294`, `site/moderntex/buy/index.html:40`, `site/moderntex/success/index.html:50`,
   `site/pt-br/moderntex/index.html:310`, `site/keyfeel/index.html:199`, `site/legroom/index.html:227`,
   `site/outbound-veil/index.html:187`, `site/tapefolio/index.html:235`; `site/recover/index.html:87, 98`;
   `site/terms/index.html:64, 193-197` (the Suite terms list and the updates clause); `site/privacy/index.html:115, 125`;
   `docs/products/app-suite.md:9, 10, 14, 15, 27, 70`. Guides that list the Suite apps in prose (`site/guides/best-*`,
   `site/guides/mac/index.html:234`) are editorial: update them only if they claim a count.
6. **Product page** `site/nee/index.html`: add the "Also in the Mac Suite" line like the other apps, and drop any "sold on its own"
   wording (`nee-site.test.mjs` and the Née terms section in `site/terms/index.html:159-166` say it is sold on its own today).
7. **Tests that pin the above** (change them in the same commit): `netlify/tests/nee-license.test.mjs` (the LAUNCH GATE test at 50 is
   the one to invert; "flipping the gate" at 60 shows the new behaviour), `nee-purchase.test.mjs`, `nee-download.test.mjs`,
   `custom-bundles.test.mjs:68, 104`, `suite-webhook.test.mjs:63-64`, `new-apps-purchase.test.mjs:1, 62, 75, 79`,
   `checkout.test.mjs:160`, `purchases-recover.test.mjs:116-117`, `legroom-site.test.mjs:136, 175, 238, 350`,
   `tapefolio-site.test.mjs:17, 302, 480, 577-578`, `lenscrib-site.test.mjs:261, 269`, `nee-site.test.mjs:265, 273`, and any Suite
   page test under `site-tests/`.

## Audio output: MP3 (Ben, 2026-11-02)

The app writes MP3 as well as M4A, WAV, FLAC and AIFF (LAME). The page lists MP3 in the Audio row and the JSON-LD description. If
the app's LAME build needs a notice or license line, add it to the app's NOTICES and to the Terms third-party text at launch.

Working name: the app was called Formring until 2026-11-02.

## What is in the branch

| Piece | Files |
|---|---|
| License keys | `netlify/lib/license.mjs` (`nee` entry, `inSuite`, `suiteIncludes`), `netlify/tests/nee-license.test.mjs` |
| Delivery | `netlify/functions/nee-download.mjs` (a copy of `legroom-download.mjs`), `netlify/tests/nee-download.test.mjs` |
| Trial emails | `nee-reminder.mjs`, `nee-reminder-send.mjs` (daily 14:50 UTC schedule), engine `netlify/lib/trial-reminder.mjs` |
| Checkout, receipt, recovery | `checkout.mjs` (`nee`, `amount: 1499`, refund line), `stripe-webhook.mjs` (`BLOB_DELIVERED_PRODUCTS`, receipt note; the key comes from `licenseKeysForSession`), `purchase-license.mjs` (`KEYED_PRODUCTS`), `sales.mjs`, `followup.mjs`, `managed-payments.mjs`; `purchases-recover.mjs` needed no change (it is generic over `licenseKeysForSession`) |
| Stats and dashboard | `stats.mjs` (`nee_trial_download` counted as `neeTrialDownloads`, `nee` in `PRODUCT_PAGES`), `traffic_dashboard.py` |
| Pages | `site/nee/` (`index.html`, `launch.js`, `nee.css`, `success.js`, `success/`, `img/`), Terms and Privacy sections, `scripts/apply_layout.py` (section marker only) |
| Media | `site/assets/nee-icon.webp`, `site/assets/video/nee-demo.mp4` and `nee-poster.webp` |
| Demo video source | `video/src/nee/NeeDemo.jsx`, composition `NeeDemo` in `video/src/Root.jsx`, `video/build-nee.mjs`, stills in `video/assets/nee/` |
| Tests | `nee-license`, `nee-download`, `nee-purchase`, `nee-site` (all `netlify/tests/nee-*.test.mjs`); `tapefolio-site.test.mjs` and `lenscrib-site.test.mjs` strings updated for the new Terms and Privacy wording |

Before the launch PR the page was hidden: no link anywhere, `noindex, follow`, dead buttons and "Not released yet". The launch PR
(`nee-launch`, draft) switches all of that on at once, so it must not merge before the manual steps in the checklist below.

The checkout itself is not gated: `POST /.netlify/functions/checkout {"product":"nee"}` returns a real Stripe session as soon as
this deploys. Nothing on the site calls it while the buttons are dead.

## Release gate

`site/nee/launch.js` holds the only page switch: `window.NEE_LAUNCH = { live, version, sizeMb, released }`. Until `live` is
`true` and `version` (x.y.z), `sizeMb` (whole number) and `released` (YYYY-MM-DD) are all valid, the trial link has no `href` and is
`aria-disabled`, the Buy button is `disabled`, the hero says "Not released yet", and the sticky bar is removed. The launch PR sets `live`
to `true` with version 1.0.0, 5 MB and the release date, and `go-live-app.py nee` (re-runnable) writes the same wording into the static
HTML. The LAUNCHED test in `nee-site.test.mjs` replaced the PRE-LAUNCH GUARD and checks that `launch.js` and the static page agree.

The trial door `nee-download?trial=1` is public but stays closed while nothing is released: with no DMG in `nee-files` it
answers 404 `no_trial`. There is no separate trial build; the trial door serves the same newest `Nee-x.y.z.dmg` buyers get, and
the key is the paywall.

## Stripe

Nothing to create. `nee` is priced inline in `checkout.mjs` (`amount: 1499`, name "Née for macOS", success path
`/nee/success/`), the way Keyfeel, Tapefolio and Lenscrib are, so there is no Stripe Price and no `STRIPE_PRICE_Née`
variable (Legroom and Outbound Veil use a Price; the newer apps do not). Session metadata carries `product` = `nee`. Tax code
`txcd_10202000` is in `managed-payments.mjs` like the other apps. No Stripe change was made.

## Env vars and Blobs (NOT set yet; set at launch)

| Item | Value |
|---|---|
| `NEE_UPDATE_TOKEN` | Netlify production env var, secret, write-only. The same value is built into the app and sent as header `X-Nee-Channel` on every Sparkle request. Local copy `~/.config/purplelink/nee-update-token` (mode 600). Never print it. Takes effect after the next site deploy |
| `PURPLELINK_LICENSE_PRIVATE_KEY` | Already set (shared with Outbound Veil and Legroom). Nothing to add for Née |
| Blobs store `nee-files` | Private. Holds `Nee-<ver>.dmg` and `appcast.xml`. Not created yet |
| Blobs store `nee-stats` | Created on the first update download; per-file counts |
| Blobs stores `nee-trial-reminders`, `nee-trial-reminder-tokens` | Created on the first reminder sign-up |

## Delivery

`netlify/functions/nee-download.mjs`, a copy of `legroom-download.mjs` with one DMG name pattern (`Nee-x.y.z.dmg`):

- Buyers: `?session_id=cs_...` lists the newest DMG; `&file=Nee-x.y.z.dmg` streams any released version. The session must be paid,
  not refunded or disputed, and carry `metadata.product` of `nee`, `app-suite`, or a custom bundle whose `apps` include `nee`. The
  license key is not in this response; the success page gets it from `purchase-license` through `license-keys.js`, like Legroom.
- Public trial: `?trial=1`, newest DMG, 20 per IP per day (429 after).
- Updates (Sparkle): `?feed=1`, `?update=<dmg>`, `?stats=1` need the `X-Nee-Channel` header, compared in constant time; 403
  otherwise and 403 when the variable is unset. The feed's enclosure URLs are rewritten to the `?update=` door.
- Feed URL in the app: `https://purplelink.llc/.netlify/functions/nee-download?feed=1`.
- The feed is signed (Sparkle `sign_update`; the app sets `SURequireSignedFeed`). Upload `appcast.xml` exactly as the app
  repo's `scripts/build-release.sh` staged it and never edit it by hand: the function serves a signed feed byte for byte,
  and any change stops every installed copy from updating. Re-sign with `sign_update appcast.xml` after any change.

Keep the DMG well under what a Netlify function can stream in its 30 second limit (the Tapefolio notes record a 182 MB DMG truncating
at 129 MB).

## Demo video

`site/assets/video/nee-demo.mp4` (1920x1080, 24 s, silent, H.264, about 1 MB) and `nee-poster.webp`. Made with Remotion from
the app's own screenshots: `cd video && node build-nee.mjs` renders the `NeeDemo` composition to `video/out/nee/`
(gitignored), re-encodes it as limited-range yuv420p with the index first, and writes the poster frame. Copy the mp4 into
`site/assets/video/` and convert the poster with `cwebp`. Scenes: title card, the ring over a photo with a file chip dropped on the
JPEG slice, the PDF ring, the video ring, the menu-bar window with History and Undo, a closing line. Every caption is burned in; the
page also describes the video in text. The page loads it with `<video controls preload="none" poster=...>`, so nothing downloads
until played. Re-render it when the app's screenshots change.

### Spot (26 s, with music)

A fast cut for ads and social, approved by Ben 2026-11-02: the problem (an app downloaded for each conversion), the apps
folding into Née, then the ring on eight file types, a batch cut, and the end card. Source `video/src/nee/NeeSpot.jsx`
(timing in `spot-stills.mjs`, 120 BPM), ring frames in `video/assets/nee/spot/` drawn by the app itself
(`Née --render-spot DIR`, backgrounds cut out), music from `video/nee-spot-bed.py` (generated, no licence needed).
`cd video && python3 nee-spot-bed.py out/nee/nee-spot-bed.wav && node build-nee-spot.mjs` writes `out/nee/nee-spot.mp4`
(silent), `nee-spot-music.mp4` and one still per picker in `out/nee/stills/`. It says "All at once", not "automate":
Née has no watch folders or Shortcuts actions.

## Releasing a version

Same shape as Legroom: a Developer-ID-signed, notarized DMG named `Nee-x.y.z.dmg` with Sparkle built in, `SUFeedURL` as above,
the update token compiled in, the shared `PurplelinkLicenseV1` public key built in. The app repo's `scripts/build-release.sh` stages
the DMG; its README says publishing is not scripted yet. A publish script must upload the DMG and `appcast.xml` to `nee-files`
and read both back byte for byte (the Legroom and Tapefolio publish scripts are the model). No separate trial build.

## Test checkout recipe (one real purchase with a 100%-off code)

Only after the DMG and appcast are in `nee-files`, `NEE_UPDATE_TOKEN` is set and deployed, and a deploy that carries this PR is
live. No money moves.

1. In the Stripe dashboard (live mode) create a 100% off, once, coupon and a promotion code with a maximum of 1 redemption.
2. `curl -s -X POST https://purplelink.llc/.netlify/functions/checkout -H 'content-type: application/json' -d '{"product":"nee"}'`
   and open the `url`.
3. Enter the code and an address you can read; complete it.
4. Expected: redirect to `/nee/success/?session_id=cs_live_...` with a download button and an `NEE1-...` key; a receipt email
   ("Your Née for macOS download") with the same key, "Paste a key into the matching app (Née: "Enter license key")", and
   the macOS 14 and Option-drag note; the function log shows `delivered_by_blobs`.
5. Download the DMG and compare its SHA-256 with the upload. Open it, enter the key, confirm it unlocks, confirm a wrong key is refused.
6. `curl -s -H "X-Nee-Channel: $(cat ~/.config/purplelink/nee-update-token)" "https://purplelink.llc/.netlify/functions/nee-download?feed=1"`
   returns the appcast with the enclosure at `?update=Nee-x.y.z.dmg`; without the header it returns 403.
7. `/recover/` with the test address lists the purchase and the key.
8. Refund the test session in Stripe (housekeeping only).

## Launch checklist (owner)

Status as of the launch PR (draft, `nee-launch` branch, do not merge until Ben says go). "In the PR" means the files are
changed there; "manual" means a person does it, in this order, on launch day.

| # | Step | Status |
|---|---|---|
| 1 | `NEE_UPDATE_TOKEN` on Netlify production, from `~/.config/purplelink/nee-update-token`, never printed | **Manual**, before merge. Takes effect on the next deploy |
| 2 | Upload `Nee-1.0.0.dmg` and the signed `appcast.xml` (never edited) to the `nee-files` Blobs store and read both back; SHA-256 `01ce39d5...0e8acb` and `674f663c...b332665` | **Manual**, before merge |
| 3 | Test checkout recipe (100%-off code), above | **Manual**, after a deploy that carries the PR |
| 4 | Suite: `inSuite` removed, bundle part, Suite page, success page, emails, copy, tests | **In the PR** |
| 5 | Launch commit: `launch.js` live (1.0.0, 5 MB), static wording, robots `index, follow`, share card `site/assets/og/nee.png` (and a refreshed `mac-suite.png`), PRE-LAUNCH GUARD test replaced by LAUNCHED | **In the PR**. The release date in `launch.js`, the sitemap, the changelog entry and the static facts is the day the PR was prepared: if launch is on another day, run `python3 scripts/go-live-app.py nee 1.0.0 5 YYYY-MM-DD` (idempotent) and change the changelog date |
| 6 | Launch-day links: footer, home dock tile and price ladder, products card and chooser, pricing row and `pricing.md`, sitemap, `llms.txt` block and the `gen_llms_full.py` page list, changelog entry, support-box topic, house promo card in `site.js` | **In the PR**. Not done on purpose: the `/li/nee`-style social short links (the social engine's `PRODUCTS` list and its tests change with them, and posting is an outward action) |
| 7 | Click counter in `site/analytics.js` (`nee-download?trial=1` fires `nee_trial_download`, also in `FUNNEL`) | **In the PR** |
| 8 | `apply_layout.py --check`, `check_content.py --strict`, both test suites (the build adds the `?v=` stamps; committed pages stay bare) | Run, green |
| 9 | Terms and Privacy wording confirmed against the shipped app | **Manual**: Ben reads the Née sections once more against the app's behavior |
| 10 | Guide "Free offline file converters for Mac" listed and linked to `/nee/` | **In the PR** |

Merge, then the scheduled 06:00 or 17:00 Eastern build publishes the site. The DMG and appcast are live as soon as they are in
Blobs; the page, the Suite change and the `NEE_UPDATE_TOKEN` take effect with that build. Do not put `[deploy now]` in the PR:
nothing here is a customer-harm fix.

## Open items

- Intel: the page says Apple silicon and Intel, from the design doc (universal binary). The design doc says Intel behaviour is
  unverified until manual test R11 passes on an Intel Mac or Rosetta; confirm before launch or change the page, FAQ and JSON-LD.
- Done in the follow-up PR: the designed app icon replaced the placeholder (page, video, icon asset), and the History window
  screenshot now renders (`Née --render-screenshots`); the page still uses the menu-bar shot for the history list.
- Settings: the design mentions a per-app exclusion list; the page does not, because the vendored ring settings only expose the key
  and the on/off switch. Add it to the FAQ if the app ships one.
- Update policy: the page, FAQ, Terms and reminder email say every update is included, as for Tapefolio and Lenscrib. Ben has not stated
  a policy for Née; change those places together if it should differ.
- Tax: `txcd_10202000` copied from the other apps; confirm with the accountant like the rest.
