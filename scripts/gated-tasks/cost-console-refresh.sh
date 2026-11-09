#!/bin/bash
# Nightly cost console build (04:42). Shell rebuilds the data and page; the desktop task cost-console-refresh (04:55)
# publishes it, because headless claude -p has no Artifact tool (the old Haiku publish step here reported
# "Not published" on 2026-11-07). Failure notification only.
set -u
GATE_NAME="cost-console-refresh"
. "$HOME/.purplelink/bin/gate-lib.sh"

RO="/Volumes/Extreme SSD/_worktrees/Purplelink LLC/jobs-ro"
OUT="$HOME/.purplelink/cost-console"
log "start"
[ -f "$RO/scripts/cost_console/run.sh" ] || { log "jobs-ro worktree missing, skipping"; exit 0; }
if ! bash "$RO/scripts/cost_console/run.sh" >> "$LOG" 2>&1; then notify_fail "cost_console/run.sh failed"; exit 1; fi
[ -s "$OUT/index.html" ] || { notify_fail "no $OUT/index.html after run.sh"; exit 1; }
# A publish older than 30 hours means the desktop task has not run (app closed, task disabled).
last="$(cat "$OUT/published-at" 2>/dev/null || true)"
case "$last" in *[!0-9]*) last="";; esac
if [ -n "$last" ] && [ $(( $(date +%s) - last )) -gt 108000 ]; then
  notify_fail "cost console last published $(date -r "$last" '+%m-%d %H:%M'); check the desktop task cost-console-refresh"
fi
log "built; the desktop task publishes it"
