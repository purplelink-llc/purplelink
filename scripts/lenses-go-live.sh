#!/bin/bash
# Makes the two Lenses launch videos public and starts the thumbnail test. Run by hand, only after Ben says go AND
# https://purplelink.llc/lenses/ returns 200 (first scheduled Netlify build after the site PR merges).
#   bash scripts/lenses-go-live.sh [--dry-run]
set -eu
cd "$(dirname "$0")/.."
LONG="Lt6G-s0_UlQ"; SHORT="86CL2_aWajw"
OUT="video/out/howto/lenses-ar-glasses-mac"
code=$(curl -s -o /dev/null -w '%{http_code}' -L https://purplelink.llc/lenses/)
[ "$code" = "200" ] || { echo "lenses page answers $code, not 200: stop"; exit 1; }
code=$(curl -s -o /dev/null -w '%{http_code}' -L https://purplelink.llc/guides/ar-glasses-mac-setup/)
[ "$code" = "200" ] || { echo "guide answers $code, not 200: stop"; exit 1; }
[ "${1:-}" = "--dry-run" ] && { echo "pages 200; would make $LONG and $SHORT public, add captions, start the A/B test"; exit 0; }
PY=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3
"$PY" scripts/yt-visibility.py public "$LONG" "$SHORT"
"$PY" scripts/yt-captions.py --channel purplelink -- "$LONG" "$OUT/lenses-ar-glasses-mac-16x9.srt"
"$PY" scripts/yt-captions.py --channel purplelink -- "$SHORT" "$OUT/lenses-ar-glasses-mac-9x16.srt"
"$PY" scripts/yt-abtest.py start "$LONG" "$OUT/lenses-ar-glasses-mac-thumb-A.jpg" "$OUT/lenses-ar-glasses-mac-thumb-B.jpg" "$OUT/lenses-ar-glasses-mac-thumb-C.jpg"
echo "done. Next: ~/.purplelink/social/staging/lenses-enqueue.sh <NOT_BEFORE> $LONG $SHORT, then approve each item on Ben's word."
