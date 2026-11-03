#!/usr/bin/env bash
# Capture one RubbleFront v4 clip: cap-v4.sh <outname> <clip> [runner args...]  -> $FL/build/trailer/v4/clips/<outname>.mp4 + .wav
set -euo pipefail
FL="${RF_RUBBLEFRONT:-${RF_FRONTLINK:-/Volumes/Extreme SSD/RubbleFront}}"
WT="${RF_WORKTREE:-/Volumes/Extreme SSD/_worktrees/RubbleFront/Frontlink-work-trailer}"
GODOT="${GODOT:-/Applications/Godot.app/Contents/MacOS/Godot}"
out="$1"; clip="$2"; shift 2 || true
O="$FL/build/trailer/v4"; mkdir -p "$O/raw" "$O/clips"
( sleep ${WDOG:-150}; pkill -f "trailer_runner.tscn -- --clip=$clip" ) >/dev/null 2>&1 &
WD=$!
FRONTLINK_TEST_ID=trailer RUBBLEFRONT_TEST_ID=trailer "$GODOT" --path "$WT/game" --write-movie "$O/raw/$out.avi" --fixed-fps 30 --resolution 1920x1080 res://tools/trailer_runner.tscn -- --clip="$clip" "$@" > "$O/raw/$out.log" 2>&1 || true
kill $WD 2>/dev/null || true
grep -E "MARK|MEDIC|SCRIPT" "$O/raw/$out.log" | sed 's/MARK //' | tr '\n' ' '; echo
ffmpeg -y -loglevel error -i "$O/raw/$out.avi" -c:v libx264 -crf 14 -preset fast -pix_fmt yuv420p -an "$O/clips/$out.mp4"
ffmpeg -y -loglevel error -i "$O/raw/$out.avi" -vn -ac 2 -ar 48000 "$O/clips/$out.wav"
ffprobe -v error -show_entries format=duration -of csv=p=0 "$O/clips/$out.mp4"
