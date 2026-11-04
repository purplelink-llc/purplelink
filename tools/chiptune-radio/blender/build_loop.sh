#!/bin/bash
# Render the racer's skyway loop in Blender and pack it for the racer theme (docs/designs/blender-loop-backgrounds.md).
#   bash blender/build_loop.sh [render|pack|preview|all]      (default all; every stage resumes where it stopped)
# Frames go to $AMBIENT_LOOPS/racer-highway-v1/_frames (about 1 MB each, removed after a good pack with KEEP_FRAMES unset).
set -u
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
TOOL="$(cd "$HERE/.." && pwd)"
LOOPS="${AMBIENT_LOOPS:-/Volumes/Extreme SSD/PurplelinkVideos/ambient/_loops}"
NAME="racer-highway-v1"
DEST="$LOOPS/$NAME"
FRAMES="$DEST/_frames"
RAW="$DEST/_raw"
ASSETS="$LOOPS/_assets"
BLENDER="${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}"
STAGE="${1:-all}"
PY="${PYTHON:-python3.12}"

mkdir -p "$FRAMES" "$RAW"

if [ "$STAGE" = render ] || [ "$STAGE" = all ]; then
  if pgrep -f 'Blender.app/Contents/MacOS/Blender' >/dev/null; then
    echo "Blender is already running; not starting a second render" >&2
    exit 1
  fi
  AMBIENT_LOOPS="$LOOPS" python3 -I "$HERE/fetch_assets.py"
  # one Blender run per 100 frames, each under a 25-minute watchdog (no GNU timeout on this Mac)
  for lo in 0 100 200 300 400 500 600 700 800 900; do
    hi=$((lo + 99)); [ "$hi" -gt 900 ] && hi=900
    perl -e 'alarm shift; exec @ARGV' 1500 "$BLENDER" -b --factory-startup --python "$HERE/racer_highway.py" -- \
      --assets "$ASSETS" --out "$FRAMES" --raw "$RAW" --frames "$lo-$hi" | grep -E '^(BUILD|FRAME [0-9]*0 |DONE|Error|Traceback)' || true
  done
  n=$(ls "$FRAMES" | grep -c '^f[0-9]*\.npz$' || true)
  [ "$n" -eq 901 ] || { echo "only $n of 901 frames rendered" >&2; exit 1; }
fi

if [ "$STAGE" = pack ] || [ "$STAGE" = all ]; then
  (cd "$TOOL" && "$PY" bgloop.py build --frames "$FRAMES" --name "$NAME")
fi

if [ "$STAGE" = preview ] || [ "$STAGE" = all ]; then
  (cd "$TOOL" && "$PY" longform.py --theme racer --seconds 20 --no-music --out "$DEST/preview.mp4")
fi

if [ "$STAGE" = all ] && [ -z "${KEEP_FRAMES:-}" ] && [ -f "$DEST/loop.npz" ]; then
  rm -rf "${RAW:?}"
fi
echo "done: $DEST"
