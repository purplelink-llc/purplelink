# Tapefolio: paid macOS app, store runbook

Store side built 2026-10-09 on the `tapefolio-store` branch (worktree `/Volumes/Extreme SSD/work-tapefolio`), modelled on
`keyfeel.md`. The app lives in `/Volumes/Extreme SSD/Tapefolio` (its README is the source of every claim on the page).
Name decided and cleared by Ben 2026-10-09.

Tapefolio is a macOS 26+, Apple silicon app for private, on-device transcription and OCR for researchers. It transcribes
audio with word timing, labels speakers, has an opt-in speaker memory, finds identifiers and replaces them with codes
case by case (the key file kept apart), has a review screen with an audio player and word highlighting, exports to Word,
HTML, Markdown, text, SRT, VTT, JSON and a MAXQDA-friendly timestamped Word file, records from the microphone, and runs
Batch OCR on photos, scans and PDFs. No speech model is bundled (decision 2026-10-09: a 182 MB DMG truncated at 129 MB through
a Netlify function, so the app is about 40 MB and ships only the standard speaker-separation models). Until the user downloads a
speech model, Tapefolio uses Apple's on-device speech recognition, and macOS may fetch Apple's own model once. NVIDIA Parakeet
(English, about 470 MB), Whisper base (English, about 150 MB), Whisper large-v3 turbo (many languages, about 650 MB) and NVIDIA
Nemotron 3 speaker separation (about 190 MB) are optional, deletable downloads in Settings, from Hugging Face, each once.
Nemotron 3 is the recommended speaker model and is used automatically once installed; standard speaker separation comes with the app. Sold at **$29.99 once**, USD, one DMG that runs free
for 7 days from first launch and then needs a license key. One key works on two Macs. 14-day refund like the other apps.
It is the sixth part of the Mac Suite, whose price did not change (see `app-suite.md`).

**Copy rule:** the page says only what the app README says. No accuracy figure appears beyond the ones the README states
(the test `netlify/tests/tapefolio-site.test.mjs` fails on any other percentage), it never says the app anonymizes or makes
anything compliant, and it says plainly that the app mishears words, mislabels speakers and misses identifiers. Do not add a
feature to the page until it ships (the same test lists some it must not mention).

## What is in the branch, and what is held back

| Commit | What | Safe to merge early? |
|---|---|---|
| `Tapefolio: license keys, delivery, ...` | key module, delivery function, trial emails, checkout entry, webhook and recovery emails, stats, dashboard | yes, nothing public changes |
| `Tapefolio: product page, success page, release gate, Terms and Privacy` | `/tapefolio/` (noindex, buttons dead), `/tapefolio/success/`, Terms and Privacy sections | yes, the page is unlisted and switched off |
| `Tapefolio: app icon assets ...` and `Tapefolio share card ...` | the two icon files, the hero icon, `tapefolio.png`, the page's `og:image` | yes, same page, same state |
| `Mac Suite: Tapefolio joins ...` | Suite page, its success page, Terms contents, "Also in the Mac Suite" lines, llms.txt, home and products Suite sentences, promo text, `app-suite.md`, then `Mac Suite and site promo: Tapefolio icon` (icon row, card, the `site.js` promo entry) and `Mac Suite share card: six apps` | no: it changes the Suite page and the Suite email at once, and buyers would be sent to a download that is not staged. Merge on launch day |
| `Link Tapefolio from home and products (do not merge until launch)` | footer (all pages, `apply_layout.py`, the digest publisher), home dock tile (eight tiles, `home.css`) and cost row, products card and chooser, pricing row, sitemap, search index, `llms.txt` block, `gen_llms_full.py` page list, changelog entry, and the flip of `/tapefolio/` to `index, follow` | no, launch day only |

The Suite commit is not gated by `launch.js` (same as Keyfeel): the moment it deploys, `app-suite` buyers are told they get
Tapefolio and the success page calls `tapefolio-download`, which answers 500 `file_unavailable` until a DMG is staged.

## Release gate (nothing can sell by accident)

`site/tapefolio/launch.js` holds the only switch: `window.TAPEFOLIO_LAUNCH = { live, version, sizeMb, released }`. Until
`live` is `true` **and** `version` (x.y.z), `sizeMb` (whole number) and `released` (YYYY-MM-DD) are all valid, the trial link has
no `href` and is `aria-disabled`, the Buy button is `disabled`, the hero says "Not released yet", and the sticky bar is
removed. `tapefolio-site.test.mjs` runs `launch.js` in a fake DOM for each state.

**Launched 2026-10-09** (the `Tapefolio 1.0.0 is live` commit, last on the branch): `live: true`, version `1.0.0`, `sizeMb`
`43` (the DMG is 43,259,154 bytes, notarized, build 22), released `2026-10-09`. The static HTML already says the live wording
(real `href`s, "Try it free for 7 days", "Buy Tapefolio", "Version 1.0.0, released October 9, 2026. 43 MB disk image.", the
"Not released yet" label removed), so crawlers and `llms-full.txt` match what the script produces. The PRE-LAUNCH GUARD test
is gone, replaced by a "LAUNCHED" test that checks the values and that wording. To change the version or size on a later
release, edit `launch.js` and the `data-tf-facts` sentence together (the test checks they agree).

Before launch, two more things held the page back, both undone by the link commit:

- `<meta name="robots" content="noindex, follow">` on `/tapefolio/`. The deploy script regenerates the sitemap and the
  search index from the pages on disk and leaves out noindex pages, so the page is not listed anywhere until it flips to
  `index, follow`. The link commit does this (and adds the sitemap and search entries by hand, so they are in the branch
  too). A test asserts `index, follow`.
- No nav, footer, home, products or pricing link points at `/tapefolio/`. The Suite page does (the card and the "See
  Tapefolio" link), which is why that commit waits for launch.

The checkout itself is not gated: `POST /.netlify/functions/checkout {"product":"tapefolio"}` returns a real Stripe session
as soon as the first commit deploys. Nothing on the site calls it while the buttons are dead.

## Stripe

Nothing to create. `tapefolio` is priced inline in `netlify/functions/checkout.mjs` (`amount: 2999`, name "Tapefolio for
macOS", success path `/tapefolio/success/`), like Keyfeel, so there is no Stripe Price and no `STRIPE_PRICE_*` variable.
`app-suite` stays `amount: 5499`. Session metadata carries `product` = `tapefolio` or `app-suite`. Promotion codes are
allowed (`allow_promotion_codes`), which is what the test recipe below uses. The existing Stripe webhook endpoint already
handles `checkout.session.completed` for every product; no change there.

## Env vars and Blobs

| Item | Value |
|---|---|
| `TAPEFOLIO_UPDATE_TOKEN` | Netlify production env var, secret, write-only. Random string; the same value is built into the app and sent as header `X-Tapefolio-Channel` on every Sparkle request. Takes effect after the next site deploy. Suggested local copy `~/.config/purplelink/tapefolio-update-token` |
| `TAPEFOLIO_LICENSE_PRIVATE_KEY` | Netlify production env var, secret, write-only. The raw 32-byte Ed25519 seed, base64 (the same format as `KEYFEEL_LICENSE_PRIVATE_KEY`). The local copy is `~/.config/purplelink/tapefolio-license-private-key` (mode 600; back it up with the Sparkle keys). Its public half is compiled into `netlify/lib/tapefolio-license.mjs` and must be the one built into the app: `5qmJMOr4uux0LZrWGs/V6nc6VKXsogioMgiJ3pBlSvI=` |
| Blobs store `tapefolio-files` | Private. Holds `Tapefolio-<ver>.dmg` and `appcast.xml` |
| Blobs store `tapefolio-stats` | Created on the first update download; per-file download counts |
| Blobs stores `tf-trial-reminders`, `tf-trial-reminder-tokens` | Created on first use by the optional trial emails (see below) |
| Blobs store `rate-limits` | Existing; the public download door writes `rl:trial:<day>:<hash>` |

To check that the key on disk matches the public key in the module without printing the seed, run this once (it prints
only `match` or `MISMATCH`):

```
node -e '
const { createPrivateKey, createPublicKey } = require("node:crypto");
const seed = require("fs").readFileSync(process.env.HOME + "/.config/purplelink/tapefolio-license-private-key", "utf8").trim();
const pkcs8 = Buffer.concat([Buffer.from("302e020100300506032b657004220420", "hex"), Buffer.from(seed, "base64")]);
const pub = createPublicKey(createPrivateKey({ key: pkcs8, format: "der", type: "pkcs8" })).export({ format: "der", type: "spki" }).subarray(-32).toString("base64");
console.log(pub === "5qmJMOr4uux0LZrWGs/V6nc6VKXsogioMgiJ3pBlSvI=" ? "match" : "MISMATCH");
'
```

Without `TAPEFOLIO_LICENSE_PRIVATE_KEY` everything still delivers, but `license` is `null` and the emails and success pages
leave the key out (they never invent one). Without `TAPEFOLIO_UPDATE_TOKEN` the update channel stays closed (403).

## Delivery

`netlify/functions/tapefolio-download.mjs`, a copy of `keyfeel-download.mjs`:

- Buyers: `?session_id=cs_...` lists files and returns `license`; `&file=Tapefolio-x.y.z.dmg` streams one. The session must
  be paid and carry `metadata.product` of `tapefolio` **or `app-suite`**, so every Suite buyer, whatever they paid, gets
  Tapefolio.
- Public download (the trial): `?download=1` (`?trial=1` also works) streams the newest `Tapefolio-x.y.z.dmg`, 20 downloads
  per IP per day (429 after). It is the same app buyers and Sparkle get. With no bundled speech model the DMG is about 40 MB,
  still larger than Keyfeel's. A function response has a 30 second limit, and a 182 MB DMG truncated at 129 MB, so keep the
  DMG well under that: stream it from Blobs as the code does, and time a full download of the real file from a slow connection
  before launch.
- Updates (Sparkle): `?feed=1`, `?update=<dmg>` and `?stats=1` require the header `X-Tapefolio-Channel:
  <TAPEFOLIO_UPDATE_TOKEN>`, compared in constant time; 403 otherwise and 403 when the variable is unset. The feed rewrites
  every enclosure URL to the update door.
- File names are exact: `Tapefolio-1.0.0.dmg` (capital T). Anything else is ignored by the buyer list and refused at the
  update door.

Emails: the receipt email (`stripe-webhook.mjs`) carries the success-page link, the `TFL1` key, "up to two of your Macs", the
macOS 26 and Apple silicon requirement, the first-run wait and the mishearing note. The Suite email says the page has six
things and carries the Tapefolio key too. `/recover/` (`purchases-recover.mjs`) re-sends the link and the key.

Analytics: the trial-link click fires `tf_trial_download` (`site/analytics.js`, which matches both `?download=1` and
`?trial=1`), counted as `tfTrialDownloads` in `stats.mjs` and shown in the traffic dashboard. `tapefolio` is its own
"Tapefolio" line in the dashboard (`sales.mjs` maps it to the purplelink site; `/tapefolio/` is in the checkout-rate
denominator). Note the Keyfeel page links `?download=1` while `analytics.js` only counts `keyfeel-download?trial=1`, so
`kfTrialDownloads` is probably undercounting; not changed here.

Optional trial emails: `tapefolio-reminder.mjs` + `tapefolio-reminder-send.mjs` (daily 14:30 UTC), the shared engine
`netlify/lib/trial-reminder.mjs`, form wired by `site/trial-reminder.js`. A setup email at download and one reminder five
days later, nothing else, each record deleted when the reminder is sent. The setup email links `/tapefolio/` because there
is no `/tapefolio/start/` page.

Tests: `node --experimental-test-module-mocks --test netlify/tests/*.test.mjs` (tapefolio-license, tapefolio-download,
tapefolio-site, trial-reminder-apps, checkout, suite-entitlement, suite-webhook, purchases-recover, legroom-site cover this
product) and `python3 -m pytest scripts/traffic-dashboard`. Tests that sign a key through the handlers use a seed Node
accepts beside the production public key (Node 24 does) and skip themselves on a Node that checks the pair; the signing
itself is tested with a throwaway key pair.

## License keys

One app, one DMG. Until a valid key is entered the app runs for 7 days from first launch, then locks (the app owns the
exact behaviour). Keys are `TFL1-` + Crockford Base32 of a 4-byte nonce and a 64-byte Ed25519 signature over
`TapefolioLicenseV1` + nonce, 109 characters in groups of five, checked offline in the app against the public key above.
Issued by `netlify/lib/tapefolio-license.mjs` from `TAPEFOLIO_LICENSE_PRIVATE_KEY`. The nonce is the first 4 bytes of
`sha256("tapefolio-license:" + lower-cased, trimmed email)`, so the receipt email, the success page (the `license` field
of the purchase door) and `/recover/` all show the same key, and a Suite buyer gets the same key as a Tapefolio-only buyer
with that address. Keys are not tied to a machine and cannot be revoked remotely; the Terms ask a refunded buyer to stop
using the key. To re-issue a key by hand: `issueTapefolioLicense(email)`.

For the app's own tests there is a vector file, `netlify/tests/fixtures/tapefolio-license-vectors.json`: a throwaway test
public key (not production), valid keys for three addresses, invalid keys (one character changed, wrong domain string,
wrong signer, wrong prefix, too short, empty) and spelling variants (case, no dashes, spaces). The app should verify
all of them. The scheme is separate from `KFL1`, `PurplelinkLicenseV1` and `MTX1`; those were not touched.

## Releasing a version

The Tapefolio repo has no release script yet (its README lists "Trial edition, notarised release, product page" as open).
What the store needs from it, in the same shape as Keyfeel:

1. A universal-or-arm64, Developer-ID-signed, notarized DMG named exactly `Tapefolio-x.y.z.dmg`, with Sparkle built in,
   `SUFeedURL` set to `https://purplelink.llc/.netlify/functions/tapefolio-download?feed=1`, the `TAPEFOLIO_UPDATE_TOKEN`
   value compiled in and sent as `X-Tapefolio-Channel` on every Sparkle request, and the `TFL1` public key above built in.
   Bundle id `llc.purplelink.tapefolio`. The key text is also accepted by a `tapefolio://license/<key>` link if the app
   wants one (Keyfeel has the same).
2. A publish script that uploads `Tapefolio-<ver>.dmg` and `appcast.xml` to the `tapefolio-files` Blobs store, rebuilds the
   appcast with the right EdDSA signature and reads every upload back byte for byte (copy Keyfeel's
   `scripts/publish-release.sh`). The appcast must be signed with the Sparkle EdDSA key whose public half the app's
   `SUPublicEDKey` holds; check which key that is before the first publish.
3. No separate trial build. The public download door serves the same newest DMG.

## Test checkout recipe (one real purchase with a 100%-off code)

Do this only after the DMG and appcast are in `tapefolio-files` and both env vars are set and deployed. No money moves.

1. In the Stripe dashboard (live mode), create a coupon: percent off 100, duration once. Create a promotion code on it
   with a maximum of 1 redemption (for example `TFTEST`). Do the same again for the Suite test in step 7 if you want both.
2. Start the session from the page (after flipping `launch.js`) or by hand:
   `curl -s -X POST https://purplelink.llc/.netlify/functions/checkout -H 'content-type: application/json' -d '{"product":"tapefolio"}'`
   and open the `url` it returns.
3. In Stripe Checkout enter the promotion code and an address you can read. Complete it.
4. Expected: redirect to `/tapefolio/success/?session_id=cs_live_...` with a download button and a `TFL1-...` key; a receipt
   email ("Your Tapefolio for macOS download") with the same key, "up to two of your Macs", the macOS 26 note and the
   first-run note; the Netlify function log shows `delivered_by_blobs` for the webhook.
5. Download the DMG from the success page and compare its SHA-256 with the file you uploaded. Open it on a Mac, enter the key,
   confirm it unlocks, confirm a wrong key is refused.
6. Check Sparkle: `curl -s -H "X-Tapefolio-Channel: $(cat ~/.config/purplelink/tapefolio-update-token)" "https://purplelink.llc/.netlify/functions/tapefolio-download?feed=1"`
   returns the appcast with the enclosure pointed at `?update=Tapefolio-x.y.z.dmg`; without the header it returns 403.
7. Repeat steps 2 to 5 with `{"product":"app-suite"}` and a second code: `/suite/success/` shows five downloads, the keys
   and the Vitae Plus key, and the Tapefolio key equals the one a Tapefolio purchase with the same address shows.
8. Open `/recover/` with the test address: the email lists both purchases and the keys.
9. Refund both test sessions in the Stripe dashboard (they are already $0, so this is only housekeeping) and leave the
   promotion codes used up.

## Launch checklist (owner)

1. Set `TAPEFOLIO_UPDATE_TOKEN` and `TAPEFOLIO_LICENSE_PRIVATE_KEY` on Netlify (production); run the key check above.
2. Stage `Tapefolio-<ver>.dmg` and `appcast.xml` in `tapefolio-files`.
3. Run the test checkout recipe against a deploy that has the first two commits (it works before the Suite and link commits).
4. (Done in the launch commit.) Fill in `site/tapefolio/launch.js`, delete the PRE-LAUNCH GUARD test, and update the four static
   fallback strings in `site/tapefolio/index.html` to their live wording, as `keyfeel.md` item 7 describes.
5. Merge the Suite commit and the link commit together, deploy, and rerun `python3 scripts/apply_layout.py --check`,
   `python3 scripts/fingerprint_assets.py` and `python3 scripts/check_content.py --strict`.
6. (Done.) The changelog entry and the sitemap `lastmod` already carry the real release date, 2026-10-09 (it is what the stand-in
   guessed), and the `Status:` line of the Tapefolio block in `site/llms.txt` now says "Shipping, version 1.0.0".
7. Confirm the Terms and Privacy wording against the shipped app: that the network use is only the optional model downloads, the
   update check and macOS fetching Apple's own speech model once; that the update request carries nothing from the user's files; that there is no analytics; that
   the trial clock and key check send nothing; that speaker memory stays on the Mac. The update request is described as: app name, app version, macOS version and the update token.
8. (Done.) The share cards are rendered (see Assets).

## Assets

Done (2026-10-09, from the real icon `Tapefolio/assets/brand/icon-1024.png`):

- `site/assets/tapefolio-icon.webp` (240x240) and `tapefolio-icon-128.webp`, made with Pillow (Lanczos, quality 92, alpha kept;
  the 1024 PNG is a squircle with transparent corners and a baked shadow). Used for the hero (`.app-hero-icon`, 120x120), the
  Suite icon row (72px) and Suite card (56px), and the site promo entry. The home dock tile is not done (below).
- `site/assets/og/tapefolio.png` and a re-rendered `site/assets/og/mac-suite.png` (six apps), 1200x630. There is no script for
  these: `_gen.html?t=<key>` is a page that draws a card, and the cards are screenshots of it. I rendered both with headless
  Chromium through Playwright (`viewport 1200x630`, device scale 1, wait for the fonts, `clip` to the viewport, save, then
  Pillow `optimize`), and the same renderer reproduced the old `mac-suite.png` pixel for pixel before the text changed. To
  redo one: serve `site/`, open `/assets/og/_gen.html?t=tapefolio` and screenshot it at 1200x630. The page's `og:image`,
  `twitter:image` and JSON-LD `image` point at `tapefolio.png`.

Screenshots and video (added after launch; sources in the `tapefolio-video` branch, storyboard `video/storyboards/tapefolio-promo.md`):

- `site/assets/tapefolio-screens/`: six real captures of the running app, 1600 px wide webp (the settings capture is 1200 wide):
  `review-main`, `review-decisions`, `review-preview`, `export-sheet`, `ocr-results`, `settings-models`. `review-main` is also the
  hero picture (`.tf-hero-window`, loads eagerly; the rest are lazy). The captions say what each capture shows and nothing more.
  They are not cropped: the draft reads "Brightwater Clinic Indecator" and the first pass did not mark "Decatur" or "Brightwater
  Clinic" as identifiers, and the captions and the page say so. The recording is an invented interview read by two computer
  voices, and the OCR letters are generated test files; the page says that in the hero caption, the video section and the
  "What it looks like" intro. To add a capture: webp under 250 KB, real width and height attributes, specific alt text, a caption
  that does not claim more than the picture shows, and a line in the test's `SHOTS` list.
- The promo video is public on YouTube, ID `b5iFfo1E_lY`, 45 seconds, https://youtu.be/b5iFfo1E_lY. The page uses the same
  facade as `/keyfeel/` (`<div class="yt-embed" data-motion="youtube">` with `site/assets/video/tapefolio-poster.webp`, 1920x1080;
  `motion.js` builds the `youtube-nocookie` iframe on click, and the CSP already allows that frame source, so `netlify.toml` did
  not change) plus a `VideoObject` in the JSON-LD like Outbound Veil's. `uploadDate` there is 2026-10-09, the day it was added;
  correct it if the upload date differs.
- `tapefolio-hero.mp4`, `tapefolio-hero.webm` (8 second silent loop, 1280x720) and `tapefolio-hero-poster.webp` are committed but
  not used: `/keyfeel/` does not use its hero loop either. To use them, copy Outbound Veil's `hero-media` markup
  (`data-motion="video"` with `<source data-src>` for webm then mp4) into the hero figure in place of the static picture.
- `llms.txt` has no video line for Keyfeel or Outbound Veil, so none was added for Tapefolio.

Still not done: a hero loop on the page (see above).

## Speaker-label measurements (corrected 2026-10-09)

The earlier page claim "between 87% and 94% of words were given to the right speaker" counted only words that had a speaker
label. The old default setting (20 s window) labelled only 51% and 54% of the words on the two AMI meetings, so it was
overstated. With the fixed default (10 s window) 88% and 96% of words are labelled and Nemotron 3 labels 90% and 95%. Counting
every word, about 83% to 84% of words on the two AMI meetings (four people each, headset mix) get the right speaker, with the
standard setting and with Nemotron 3 alike, and some words get no label. That is what the page says now. The setting was tuned
on the AMI meetings, so those numbers may flatter it.

On five real two-person recordings (71 minutes, VoxConverse, CC BY 4.0, YouTube audio, human-checked labels; no transcripts, so
this is scored on speech time, not words) standard speaker separation missed 8.5% of the speech, added 1.7% and mixed up
speakers for 1.1% (total 11.3%); Nemotron 3 missed 1.4%, added 0.5% and mixed up 0.0% (total 1.9%). The old default scored
50.5% on the same files, which the page does not mention. The VoxConverse files were not used for tuning. Caveats the page
states: five files, English, YouTube-quality audio, two speakers, and word accuracy on them is not measured. Source: the
Tapefolio repo README, section "Real two-person recordings: VoxConverse" (its scripts). `tapefolio-site.test.mjs` fails on any
percentage on the page that is not in its allowed list, so a new figure needs a test change.

## Open items

- The app itself: the license check, the 7-day trial clock, "Enter License Key", the Sparkle updater with the channel
  header, and the notarized release are all still to build in the Tapefolio repo. The server and pages assume the menu
  wording "Enter License Key" (as Keyfeel); change the emails, the FAQ and the success page if the app says something else.
- Claims on the pages that only the app can confirm: that the network use is exactly three things: the model
  downloads from Hugging Face (each once), the update check, which sends the app's name, its version, the macOS version and the update
  token to purplelink.llc, and macOS itself fetching Apple's own speech model once if Apple's recognition is used (Ben's description,
  2026-10-09); that nothing from the user's files is sent; that there is no analytics and no account; the download sizes (about 470 MB
  Parakeet, 150 MB Whisper base, 650 MB Whisper large-v3 turbo, 190 MB Nemotron 3, as given by the coordinator 2026-10-09; the README
  also names a 95 MB Nemotron variant); that the app is about 40 MB; that Apple's recognition is the default until a model is
  downloaded; that a microphone prompt appears on first recording; that the first-run wait applies to each model the first time it
  runs and is "a few minutes". The measured error rates on the page are Apple 28.5% and 23.0%, Parakeet 26.3% and 21.4%, Whisper
  large 27.0% and 21.4% (shown as 21% to 29%), Whisper base 39.4% and 29.1% (shown as 29% to 39%), on the two AMI meetings.
- Update policy (decided by Ben 2026-10-09): every future update is included for anyone who bought, with no version or time
  limit. The page, FAQ, JSON-LD, Terms, Suite FAQ, `llms.txt` and the reminder email all say so in Keyfeel's words ("The purchase
  includes all updates to Tapefolio"). Legroom is the only app that still limits updates to the version bought.
- Name: Ben cleared TAPEFOLIO on 2026-10-09. The README still carries its own "run a USPTO search, register the domains"
  note from 2026-10-08.
- The home page dock now has eight tiles (Tapefolio sits after Keyfeel, so the four paid Mac apps stay together). It is eight across
  from 1600 px up, two rows of four from 561 to 1599 px, and two columns on a phone; the seven existing tiles are unchanged
  (`site/home.css`, `.dock`). Eight across at 1440 px was too narrow ("Outbound Veil" and "Scholar Utility Belt" wrapped and the
  descriptions ran to five lines), while four by two keeps every label on one or two lines. The change is in the link commit.
- `site/llms-full.txt` is not regenerated here (the checked-in copy already lags the pages); the deploy script regenerates it, and
  `scripts/gen_llms_full.py` now includes `tapefolio/`.
- Only English meeting audio and generated OCR files have been measured; the page says so. Real handwriting, phone photos,
  other languages and different microphones for speaker memory are untested.
