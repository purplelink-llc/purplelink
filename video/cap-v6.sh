#!/usr/bin/env bash
# Capture one RubbleFront v6 clip: cap-v6.sh <outname> <clip> [runner args...]  -> $FL/build/trailer/v6/clips/<outname>.mp4 + .wav
# Launched with `open -g -n` so the Godot window never takes focus (it stays always-on-top so macOS keeps drawing it).
set -euo pipefail
FL="${RF_RUBBLEFRONT:-/Volumes/Extreme SSD/RubbleFront}"
WT="${RF_WORKTREE:-/Volumes/Extreme SSD/_worktrees/RubbleFront/trailer-v6}"
out="${1:?outname}"; clip="${2:?clip}"; shift 2
O="$FL/build/trailer/v6"; mkdir -p "$O/raw" "$O/clips"
[ -d "$WT/game/tools" ] || { echo "no worktree game dir: $WT"; exit 2; }
rm -f "$O/raw/$out.avi" "$O/raw/$out.log"
TL="$(mktemp -t rfcap6)"   # open --stdout fails (LaunchServices -10810) on a path with a space, so log to a temp file first
open -g -n -W --env RUBBLEFRONT_TEST_ID=trailer6 --stdout "$TL" --stderr "$TL" \
  -a /Applications/Godot.app --args --path "$WT/game" --write-movie "$O/raw/$out.avi" --fixed-fps 30 \
  --resolution "${RES:-1920x1080}" res://tools/trailer_runner.tscn -- --clip="$clip" "$@" &
OP=$!
t=0; while kill -0 "$OP" 2>/dev/null && [ "$t" -lt "${WDOG:-420}" ]; do sleep 2; t=$((t+2)); done
if kill -0 "$OP" 2>/dev/null; then pkill -f "write-movie $O/raw/$out.avi" || true; echo "WATCHDOG $out"; fi
wait "$OP" 2>/dev/null || true
cp "$TL" "$O/raw/$out.log"; rm -f "${TL:?}"
grep -E "MARK|MEDIC|SCRIPT" "$O/raw/$out.log" | sed 's/MARK //' | tr '\n' ' ' | cut -c1-400; echo
[ -s "$O/raw/$out.avi" ] || { echo "NO AVI $out"; exit 3; }
ffmpeg -y -loglevel error -i "$O/raw/$out.avi" -c:v libx264 -crf 14 -preset fast -pix_fmt yuv420p -an "$O/clips/$out.mp4"
ffmpeg -y -loglevel error -i "$O/raw/$out.avi" -vn -ac 2 -ar 48000 "$O/clips/$out.wav"
rm -f "$O/raw/$out.avi"
ffprobe -v error -show_entries format=duration -of csv=p=0 "$O/clips/$out.mp4"
