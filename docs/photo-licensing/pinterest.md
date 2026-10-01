# Pinterest runbook for the photography pages

Pinterest is a search engine for pictures. A pin that points at
`/photography/<country>/<place>/` keeps sending visitors for months, which is
what the hub pages need. This file covers the one-time setup, the first bulk
upload, the weekly refresh, and the point at which to stop.

Everything here is produced by `scripts/pinterest-pins.py`. It reads
`site/photography/hub-data.json` (written by `scripts/gen_photo_hubs.py`),
renders a 1000x1500 JPEG per photograph into
`site/assets/photography/pins/`, and writes the upload CSV to
`photo-licensing-workspace/pinterest/pins.csv`. The pin images are committed
and served from purplelink.llc; the CSV stays in the gitignored workspace.

## One-time setup (Ben)

1. Create a Pinterest Business account at business.pinterest.com. Use the
   ben@purplelink.llc address. Business name: Purplelink. Website:
   https://purplelink.llc.

2. Claim the website. In Settings > Claimed accounts > Websites, choose
   "Add HTML tag". Pinterest shows a line of the form
   `<meta name="p:domain_verify" content="..."/>`. Copy the `content`
   value, then add this line to the `<head>` of `site/index.html`
   (directly after the `<meta name="viewport" ...>` line), with the real
   value in place of `PASTE-TAG-HERE`:

       <meta name="p:domain_verify" content="PASTE-TAG-HERE">

   Deploy (`bash scripts/deploy.sh`), then click "Verify" in Pinterest. The
   tag only needs to be on the home page. Leave it in place afterwards;
   Pinterest re-checks it.

3. Create the boards. Board names must match the `Pinterest board` column of
   the CSV exactly, or the bulk upload rejects the row. Run
   `python3 scripts/pinterest-pins.py --check` to print the list; at the time
   of writing it is: Canada, Denmark, Germany, Iceland, Japan, Netherlands,
   Panama, Switzerland, United Kingdom, United States. One board per country,
   public, with a one-line description such as "Travel photographs of
   Iceland by Benjamin Ampel. Prints and licenses at purplelink.llc".

## First upload

1. From the repo root, build the pins and the CSV:

       python3 scripts/gen_photo_hubs.py
       python3 scripts/pinterest-pins.py --mark-exported

   Commit and deploy `site/assets/photography/pins/` first; Pinterest
   fetches each `Media URL` when it processes the CSV, so the images must be
   live before the upload.

2. In Pinterest: Create > Bulk create pins > upload
   `photo-licensing-workspace/pinterest/pins.csv`. The limit is 200 pins per
   file; the first run is about 120, so one file. Pinterest reports a row
   count and any rejected rows; the usual rejection is a board name that
   does not match.

3. Publish dates in the CSV are spread five per day, between 09:00 and 20:00
   local time, starting the day after the script ran. Pinterest schedules
   them; nothing else to do. If the upload happens more than a day after the
   script ran, re-run the script so the dates start tomorrow again.

`--mark-exported` records each pin's slug in
`photo-licensing-workspace/pinterest/exported.json`, so later runs can skip
them.

## Weekly refresh

After new photographs are added to the hub pages (new places in
`scripts/data/photo-places.json`, or new rows in the metadata CSV):

    python3 scripts/gen_photo_hubs.py
    python3 scripts/pinterest-pins.py --new-only --mark-exported

The CSV then holds only pins not yet exported. Upload it the same way. If
nothing is new the CSV has a header and no rows, and there is nothing to
upload. Do not re-upload an old CSV: Pinterest does not de-duplicate, and a
second copy of the same pin counts against the account.

Other flags: `--check` prints counts and writes nothing; `--limit N` builds
only the first N pins (useful for a test upload of five).

Every run also lists photographs it refused to pin because their own title
or keywords name a different country from the page they sit on (for
example an Arizona night sky filed under Kyoto). Those are matcher slips in
`scripts/data/photo-places.json`; fix the match terms there and re-run
`gen_photo_hubs.py`, and the pins appear on the next refresh.

## What to watch, and when to stop

Pinterest Analytics > Overview shows monthly viewers and outbound clicks.
Record both in the monthly report.

Kill criterion: if the account has under 1,000 monthly viewers at day 90
after the first pins go live, stop. Leave the existing pins up (they cost
nothing), but do not run the weekly refresh or spend time on the account.
If it is above that line, keep the weekly refresh and look at which boards
get the outbound clicks before adding more places.

## Notes

- Pin images carry the same diagonal watermark as the hub pages and a purple
  band with the place name. They are deliberately small (about 180 KB,
  JPEG quality 72) so the folder stays under 25 MB.
- Photographs with a recognisable person are never pinned.
- Pinterest can also run its own "claimed website" pins from the ImageObject
  JSON-LD on the hub pages once the site is verified; that is a bonus, not
  something to set up.
