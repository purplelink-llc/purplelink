# Photo arm automation map (built 2026-09-30)

What runs on its own, what it writes, and the few things that still need Ben.
The plan it implements is `docs/growth-briefs/2026-09-30-photo-arm-persona-panel.md`.

## The spine: destination hub pages

- `scripts/gen_photo_hubs.py` builds `/photography/<country>/` and
  `/photography/<country>/<place>/` from `photo-licensing-workspace/batch-001-metadata.csv`
  and the taxonomy in `scripts/data/photo-places.json` (hand-written intros and
  one verifiable fact per place; edit that file to change the words).
- Writes watermarked `site/assets/photography/hub/<stem>-1200.webp` and `-480.webp`,
  `site/photography/hub-data.json` (what is on which page; every other script
  reads it), `site/sitemap-images.xml`, and the "Browse by place" section on
  `/photography/` between the `hubs:start`/`hubs:end` markers.
- Each photograph carries `ImageObject` JSON-LD with `license` and
  `acquireLicensePage`, and a License link into `/photography/license/`.
- Weekly: the `photo-weekly-maintenance` scheduled task reruns it and pushes
  when something changed (new photos in the CSV, edited intros).

## Direct sales on the domain

- `/photography/license/` (page + `shop.js`): three tiers, $29 web / $79
  commercial / $199 extended, a picker over `hub-data.json`, `?photo=DSC_xxxx`
  deep links from the hub pages. Photographs with people are editorial-only
  and never offered.
- `netlify/functions/checkout.mjs`: `photo-license-*` and `photo-calendar-*`
  products with inline prices; `photo` is validated and copied into the
  session metadata.
- `netlify/functions/photo-download.mjs`: streams the clean original (or the
  calendar PDFs) from the private `photo-files` Blobs store once the session
  is paid, plus a generated license text naming buyer, file, tier and terms.
- `scripts/photo-blobs-upload.sh`: uploads every licensable original named in
  `hub-data.json` and every `calendar-2027-*.pdf` to that store (idempotent,
  manifest in `photo-licensing-workspace/analytics/photo-blobs.json`). Uses
  the Netlify CLI login; nothing stored in the repo.
- `/photography/calendars/` (page + `scripts/photo-calendars.py`): 2027
  printable calendars, $7 each or $19 for all seven, Letter and A4.

## Pitches and credits (approval queue, never unattended sends)

- `scripts/photo-pitch.py queue` turns rows of
  `docs/photo-licensing/direct-pitch-targets.csv` whose notes carry
  `VERIFIED <date>` into approval-queue items (`~/.purplelink/queue/pending/`).
  `followup` queues the Hotel d'Angleterre follow-up. `send` mails approved
  items with watermarked previews attached and logs them in
  `Outreach/OUTREACH-LOG.md` ("Photo licensing pitches", "Photo-for-credit offers").
- The `photo-pitch-weekly` scheduled task (Mondays) finds new hotel and
  tour-operator targets, opens the files to verify them, adds the VERIFIED
  marker, queues, and sends what Ben approved the week before. The
  `photo-credit-weekly` task does the same for travel bloggers (free image for
  a credit link to the matching hub page).

## Audience layers

- Short video: `/Volumes/Extreme SSD/TikTokPipeline/PhotoPipeline/` renders a
  daily "Where is this?" guess-and-reveal clip from `hub-data.json` and posts it
  to the Purplelink YouTube channel through `scripts/yt-upload.py` (launchd
  `com.purplelink.photo-shorts`). `touch PhotoPipeline/PAUSE` stops it.
- Pinterest: `scripts/pinterest-pins.py` writes 2:3 pins into
  `site/assets/photography/pins/` and a bulk-create CSV in
  `photo-licensing-workspace/pinterest/`. Needs a Pinterest Business account
  (see `pinterest.md`).

## Measurement

- `scripts/stats-collect.py` (daily sweep) and `scripts/sales-ledgers.py`
  (per-sale rows for Adobe, Shutterstock, Getty).
- `scripts/photo-weekly-memo.py`: the Monday five-line memo. Line 1 is the
  rule that matters: trailing-4-week royalties plus direct sales divided by
  owner hours from `photo-licensing-workspace/analytics/owner-hours.csv`
  (Ben appends a row when he spends time; nothing else measures it). Above
  $5/hour grow, below it hold.
- Alamy caption rewrite: tracked account-level (views, zooms, CTR) from the
  date in `analytics/alamy-rewrite.json`; day 28 is the readout.

## Still needs Ben

- Alamy: $5.32 owed and "Need Payment Details" on the balance page; enter
  payment details at alamy.com/stock-photography-payment-details.aspx.
- Approve queue items (pitches, credits) in the queue digest.
- Pinterest Business account and board creation.
- Purplelink TikTok and Instagram accounts if the shorts should go beyond YouTube.
- Log owner hours in `owner-hours.csv` so the $/hour rule can fire.
- Etsy: the refreshed hero-listing copy and mockups in
  `photo-licensing-workspace/etsy/<slug>/v2/` are applied to the live listings
  by `scripts/etsy-hero-refresh.py` once reviewed.
