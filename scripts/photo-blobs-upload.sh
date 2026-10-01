#!/bin/bash
# Upload the clean originals and calendar PDFs that photo-download.mjs serves
# into the private `photo-files` Netlify Blobs store of the purplelink site.
#
# The site only ever publishes watermarked copies; the files here are the
# deliverables a paid Checkout Session unlocks. The upload itself is
# scripts/photo-blobs-upload.mjs (the @netlify/blobs client, with the token
# the Netlify CLI login already holds), because `netlify blobs:set` fails
# intermittently with "not linked to a project" when called hundreds of times.
#
#   bash scripts/photo-blobs-upload.sh            # every licensable photo in hub-data.json + calendars
#   bash scripts/photo-blobs-upload.sh DSC_1326   # just these stems
#
# Idempotent: photo-licensing-workspace/analytics/photo-blobs.json records
# what was uploaded with the source file's size + mtime; unchanged files are
# skipped. Run it after gen_photo_hubs.py adds photographs or
# photo-calendars.py rebuilds the PDFs.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WS="${PL_WORKSPACE:-$ROOT/photo-licensing-workspace}"
[ -d "$WS" ] || WS="/Volumes/Extreme SSD/Purplelink LLC/photo-licensing-workspace"
SRC="${PL_PHOTOS:-/Volumes/Extreme SSD/Nikon Photos}"
MANIFEST="$WS/analytics/photo-blobs.json"
HUB="$ROOT/site/photography/hub-data.json"
# node_modules (with @netlify/blobs) lives in the main checkout.
NODE_DIR="$ROOT"; [ -d "$ROOT/node_modules/@netlify/blobs" ] || NODE_DIR="/Volumes/Extreme SSD/Purplelink LLC"
mkdir -p "$(dirname "$MANIFEST")"
UPLOADER="$ROOT/scripts/photo-blobs-upload.mjs"

python3 - "$HUB" "$SRC" "$WS" "$@" <<'EOF' | (cd "$NODE_DIR" && PL_NODE_DIR="$NODE_DIR" node "$UPLOADER" "$MANIFEST")
import json, sys
from pathlib import Path
hub, src, ws = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
only = set(sys.argv[4:])
seen = set()
if hub.exists():
    d = json.loads(hub.read_text())
    for c in d["countries"]:
        for p in c["places"] + [{"images": c["extra"]}]:
            for i in p["images"]:
                if i["people"] or (only and i["stem"] not in only) or i["stem"] in seen:
                    continue
                f = src / f"{i['stem']}.jpeg"
                if f.exists():
                    seen.add(i["stem"]); print(f"{i['stem']}.jpeg\t{f}")
if not only:
    for f in sorted((ws / "calendars").glob("calendar-2027-*.pdf")):
        print(f"{f.name}\t{f}")
