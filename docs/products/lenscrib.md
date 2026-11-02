# Lenscrib: paid macOS app, store runbook

Store side built 2026-11-01 on the `lenscrib-store` branch (worktree `/Volumes/Extreme SSD/_worktrees/Purplelink LLC/lenscrib-store`),
copied from `tapefolio.md`. The app is built in a separate repo by another worker; its README is the source of every claim on
the page. Name: Lenscrib (no final e), slug `lenscrib`, bundle id `llc.purplelink.lenscrib`.

Lenscrib is a macOS 14+, Apple silicon app for stock photo contributors. A vision model that runs on the Mac (downloaded once
from Hugging Face, about 3 GB, photos never uploaded) drafts a title, a description and keywords for each photo. The photo's GPS
and date name the place and the date (offline place list, no network). It cleans keywords (lowercase, duplicates, generic words),
fits them to Adobe Stock, Shutterstock, Alamy, Vecteezy and Dreamstime rules, builds the editorial caption line, writes the
metadata into the image files (IPTC and XMP) and exports each agency's CSV. It does not upload to agencies. Sold at
**$19.99 once**, USD, one DMG that runs free for 7 days from first launch and then needs a license key. One key works on two
Macs. 14-day refund like the other apps.

**Not in the Mac Suite, and not one of the pick-2 and pick-3 bundle parts** (Ben has not decided). `bundles.mjs`, the Suite
pages and the Suite emails were not touched, so a Suite or bundle session is refused by `lenscrib-download` (`not_entitled`)
and gets no Lenscrib key. If Ben decides to add it, that is a separate change (see "Open items").

**Copy rule:** the page says only what the app brief says, carries no percentage (the test fails on any), says plainly that the
model can be wrong (it guesses species and places) and that the user reviews every field, and never says the app uploads to an
agency. `netlify/tests/lenscrib-site.test.mjs` enforces these.

## What is in the branch

| Piece | Files |
|---|---|
| License keys | `netlify/lib/lenscrib-license.mjs`, `netlify/tests/lenscrib-license.test.mjs`, `netlify/tests/fixtures/lenscrib-license-vectors.json` |
| Delivery | `netlify/functions/lenscrib-download.mjs`, `netlify/tests/lenscrib-download.test.mjs` |
| Trial emails | `lenscrib-reminder.mjs`, `lenscrib-reminder-send.mjs` (daily 14:30 UTC schedule), engine `netlify/lib/trial-reminder.mjs` |
| Checkout, receipt, recovery | `checkout.mjs` (`lenscrib`, `amount: 1999`, refund line), `stripe-webhook.mjs` (receipt text plus key), `purchase-license.mjs` (`KEYED_PRODUCTS`), `purchases-recover.mjs`, `sales.mjs`, `followup.mjs`, `managed-payments.mjs` |
| Stats and dashboard | `stats.mjs` (`lcb_trial_download` counted as `lcbTrialDownloads`, `lenscrib` in `PRODUCT_PAGES`), `traffic_dashboard.py` |
| Pages | `site/lenscrib/` (index, `launch.js`, `lenscrib.css`, `success.js`, `success/`), Terms and Privacy sections |
| Tests | the three `lenscrib-*.test.mjs` files; `tapefolio-site.test.mjs` strings updated for the new Terms and Privacy wording |

Safe to merge now: nothing is linked and the page is switched off. There is no nav, footer, home, products, pricing, sitemap,
search index or llms link to `/lenscrib/` (a test asserts it), and the page is `noindex, follow`. The trial link has no `href`,
the Buy button is `disabled`, and the hero says "Not released yet".

The checkout itself is not gated: `POST /.netlify/functions/checkout {"product":"lenscrib"}` returns a real Stripe session as
soon as this deploys. Nothing on the site calls it while the buttons are dead.

## Release gate

`site/lenscrib/launch.js` holds the only switch: `window.LENSCRIB_LAUNCH = { live, version, sizeMb, released }`. Until `live` is
`true` and `version` (x.y.z), `sizeMb` (whole number) and `released` (YYYY-MM-DD) are all valid, the trial link has no `href` and
is `aria-disabled`, the Buy button is `disabled`, the hero says "Not released yet", and the sticky bar is removed. The
PRE-LAUNCH GUARD test in `lenscrib-site.test.mjs` pins the shipped state; delete it at launch, as Tapefolio did.

## Stripe

Nothing to create. `lenscrib` is priced inline in `checkout.mjs` (`amount: 1999`, name "Lenscrib for macOS", success path
`/lenscrib/success/`), so there is no Stripe Price and no `STRIPE_PRICE_*` variable. Session metadata carries
`product` = `lenscrib`. Tax code `txcd_10202000` is in `managed-payments.mjs` like the other apps. No Stripe change was made.

## Env vars and Blobs (NOT set yet; set at launch)

| Item | Value |
|---|---|
| `LENSCRIB_UPDATE_TOKEN` | Netlify production env var, secret, write-only. The same value is built into the app and sent as header `X-Lenscrib-Channel` on every Sparkle request. Local copy `~/.config/purplelink/lenscrib-update-token` (mode 600). Takes effect after the next site deploy |
| `LENSCRIB_LICENSE_PRIVATE_KEY` | Netlify production env var, secret, write-only. The raw 32-byte Ed25519 seed, base64. Local copy `~/.config/purplelink/lenscrib-license-private-key` (mode 600; back it up with the Sparkle keys). Its public half is `LENSCRIB_LICENSE_PUBLIC_KEY_B64` in `netlify/lib/lenscrib-license.mjs` and must be the one built into the app |
| Blobs store `lenscrib-files` | Private. Holds `Lenscrib-<ver>.dmg` and `appcast.xml`. Not created yet |
| Blobs store `lenscrib-stats` | Created on the first update download; per-file counts |
| Blobs stores `lcb-trial-reminders`, `lcb-trial-reminder-tokens` | Created on first use by the optional trial emails |
| Blobs store `rate-limits` | Existing; the public download door writes `rl:trial:<day>:<hash>` |

Check that the key on disk matches the public key in the module without printing the seed (prints `match` or `MISMATCH`):

```
node -e '
const { createPrivateKey, createPublicKey } = require("node:crypto");
const seed = require("fs").readFileSync(process.env.HOME + "/.config/purplelink/lenscrib-license-private-key", "utf8").trim();
const pkcs8 = Buffer.concat([Buffer.from("302e020100300506032b657004220420", "hex"), Buffer.from(seed, "base64")]);
const pub = createPublicKey(createPrivateKey({ key: pkcs8, format: "der", type: "pkcs8" })).export({ format: "der", type: "spki" }).subarray(-32).toString("base64");
console.log(pub === "EmMW+2pz1QfCDC8IRk0pyTfINugd3oY/Xz9wD02jcGk=" ? "match" : "MISMATCH");
'
```

Without `LENSCRIB_LICENSE_PRIVATE_KEY` everything still delivers, but `license` is `null` and the emails and success page leave the
key out. Without `LENSCRIB_UPDATE_TOKEN` the update channel stays closed (403).

## What the app must match

| Item | Value |
|---|---|
| Key format | `LCB1-` + Crockford Base32 of a 4-byte nonce and a 64-byte Ed25519 signature, 109 characters in groups of five |
| Signed message | UTF-8 `LenscribLicenseV1` followed by the 4 nonce bytes |
| Nonce | first 4 bytes of `sha256("lenscrib-license:" + lower-cased, trimmed email)` |
| Public key (base64) | `EmMW+2pz1QfCDC8IRk0pyTfINugd3oY/Xz9wD02jcGk=` |
| Update header | `X-Lenscrib-Channel: <LENSCRIB_UPDATE_TOKEN>` |
| Feed URL | `https://purplelink.llc/.netlify/functions/lenscrib-download?feed=1` |
| DMG name | exactly `Lenscrib-x.y.z.dmg` (capital L) |
| Bundle id | `llc.purplelink.lenscrib` |
| Menu wording | "Enter License Key" (emails, FAQ and the success page say so) |

Test vectors for the app's own tests: `netlify/tests/fixtures/lenscrib-license-vectors.json` (throwaway test public key, valid and
invalid keys, spelling variants). The scheme is separate from `KFL1`, `TFL1`, `PNL1`, `SML1`, `PurplelinkLicenseV1` and `MTX1`.

## Delivery

`netlify/functions/lenscrib-download.mjs`, a copy of `tapefolio-download.mjs` without the Suite and bundle entitlement:

- Buyers: `?session_id=cs_...` lists files and returns `license`; `&file=Lenscrib-x.y.z.dmg` streams one. The session must be paid
  and carry `metadata.product` of exactly `lenscrib`.
- Public download (the trial): `?download=1` (`?trial=1` also works), newest DMG, 20 per IP per day (429 after).
- Updates (Sparkle): `?feed=1`, `?update=<dmg>`, `?stats=1` need the `X-Lenscrib-Channel` header, compared in constant time; 403
  otherwise and 403 when the variable is unset.

Keep the DMG well under what a Netlify function can stream in its 30 second limit (the Tapefolio notes record a 182 MB DMG
truncating at 129 MB). The 3 GB vision model is a separate download from Hugging Face and is not in the DMG.

## Releasing a version

Same shape as Tapefolio: a Developer-ID-signed, notarized DMG named `Lenscrib-x.y.z.dmg` with Sparkle built in, `SUFeedURL` as
above, the update token compiled in, the `LCB1` public key built in. A publish script uploads the DMG and `appcast.xml` to
`lenscrib-files` and reads both back byte for byte. No separate trial build.

## Test checkout recipe (one real purchase with a 100%-off code)

Only after the DMG and appcast are in `lenscrib-files`, both env vars are set and deployed, and a deploy that carries this PR is
live. No money moves.

1. In the Stripe dashboard (live mode) create a 100% off, once, coupon and a promotion code with a maximum of 1 redemption.
2. `curl -s -X POST https://purplelink.llc/.netlify/functions/checkout -H 'content-type: application/json' -d '{"product":"lenscrib"}'`
   and open the `url`.
3. Enter the code and an address you can read; complete it.
4. Expected: redirect to `/lenscrib/success/?session_id=cs_live_...` with a download button and an `LCB1-...` key; a receipt email
   ("Your Lenscrib for macOS download") with the same key, "up to two of your Macs", the macOS 14 and 3 GB model notes; the
   function log shows `delivered_by_blobs`.
5. Download the DMG and compare its SHA-256 with the upload. Open it, enter the key, confirm it unlocks, confirm a wrong key is refused.
6. `curl -s -H "X-Lenscrib-Channel: $(cat ~/.config/purplelink/lenscrib-update-token)" "https://purplelink.llc/.netlify/functions/lenscrib-download?feed=1"`
   returns the appcast with the enclosure at `?update=Lenscrib-x.y.z.dmg`; without the header it returns 403.
7. `/recover/` with the test address lists the purchase and the key.
8. Refund the test session in Stripe (housekeeping only).

## Launch checklist (owner)

1. Set `LENSCRIB_UPDATE_TOKEN` and `LENSCRIB_LICENSE_PRIVATE_KEY` on Netlify (production); run the key check above. Do not print them.
2. Build the app with the same public key, token and header; stage `Lenscrib-<ver>.dmg` and `appcast.xml` in `lenscrib-files`.
3. Run the test checkout recipe.
4. Launch commit (separate from this PR): fill in `site/lenscrib/launch.js`; delete the PRE-LAUNCH GUARD test; write the live wording
   into the static fallbacks in `index.html` (the four strings the script replaces: hero status, the two gated buttons, the
   `data-lcb-facts` sentence); add the app icon (`site/assets/lenscrib-icon.webp`), a share card and `og:image`, screenshots of the
   real app and a promo video if there is one; flip `<meta name="robots">` to `index, follow`.
5. Launch-day links, none of which exist yet: nav and footer (`scripts/apply_layout.py`), home dock tile, products card and
   chooser, pricing row, sitemap, search index, `llms.txt` block, `gen_llms_full.py` page list, changelog entry, `/li/lenscrib`
   style redirects in `netlify.toml`, and the support-box topic (`support-message.mjs` `TOPICS` plus `apply_support_box.py`,
   which the topic test requires to stay in step).
6. Add the click counter in `site/analytics.js` (a `lenscrib-download?(download|trial)=1` branch firing `lcb_trial_download`, and
   `lcb_trial_download` in the `FUNNEL` regex). The server side (`stats.mjs`, dashboard) is already in. It is held back only
   because changing `analytics.js` restamps every page.
7. Run `python3 scripts/apply_layout.py --check`, `python3 scripts/fingerprint_assets.py`, `python3 scripts/check_content.py --strict`.
8. Confirm the Terms and Privacy wording against the shipped app: that the network use is exactly the one-time model download from
   Hugging Face and the update check (app name, version, macOS version, update token); that no photo, metadata or location is sent;
   that there is no analytics; that the trial clock and key check send nothing.

## Open items

- The app itself is built elsewhere. The server and pages assume the menu wording "Enter License Key", the feed URL and header
  above, and the claims on the page (the 3 GB size, the five agencies, IPTC/XMP writing, CSV export, offline place list, macOS 14,
  Apple silicon only, no upload to agencies).
- Update policy: the page, FAQ, Terms and reminder email say every update is included, as for Tapefolio and Keyfeel. Ben has
  not stated a policy for Lenscrib; change those four places together if it should differ.
- Suite and bundles: Ben has not decided. Adding Lenscrib means `bundles.mjs` (`BUNDLE_PARTS`, which changes bundle prices and
  every Suite page and email), `lenscrib-download.mjs` entitlement, the Suite emails and the Suite success page, and the tests that
  pin them.
- Tax: `txcd_10202000` copied from the other apps; confirm with the accountant like the rest.
- The page has no icon, share card, screenshots or video yet.
