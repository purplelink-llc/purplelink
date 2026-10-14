#!/usr/bin/env bash
# Capture one RubbleFront v2 trailer clip: cap-v2.sh <clip> [--seed=N]  -> $FL/build/trailer/v3/clips/<clip>.mp4 + .wav (+ raw avi)
set -euo pipefail
FL="${RF_FRONTLINK:-/Volumes/Extreme SSD/Frontlink}"
WT="${RF_WORKTREE:-/Volumes/Extreme SSD/_worktrees/Frontlink/Frontlink-work-trailer}"
GODOT="${GODOT:-/Applications/Godot.app/Contents/MacOS/Godot}"
clip="$1"; shift || true
O="$FL/build/trailer/v3"; mkdir -p "$O/raw" "$O/clips"
FRONTLINK_TEST_ID=trailer RUBBLEFRONT_TEST_ID=trailer "$GODOT" --path "$WT/game" --write-movie "$O/raw/$clip.avi" --fixed-fps 30 --resolution 1920x1080 res://tools/trailer_runner.tscn -- --clip="$clip" "$@" > "$O/raw/$clip.log" 2>&1 || true
grep -E "MARK|MEDIC|ERROR|SCRIPT" "$O/raw/$clip.log" | head -40
ffmpeg -y -loglevel error -i "$O/raw/$clip.avi" -c:v libx264 -crf 14 -preset fast -pix_fmt yuv420p -an "$O/clips/$clip.mp4"
ffmpeg -y -loglevel error -i "$O/raw/$clip.avi" -vn -ac 2 -ar 48000 "$O/clips/$clip.wav"
ffprobe -v error -show_entries format=duration -of csv=p=0 "$O/clips/$clip.mp4"
