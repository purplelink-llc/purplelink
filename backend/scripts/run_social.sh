#!/bin/bash
# Scheduler wrapper for the unified social poster: runs `social.py run-due`.
# launchd job com.purplelink.social-scheduler calls this every 10 minutes. The installed copy lives at
# ~/.purplelink/bin/social-run-due.sh so the job still starts cleanly when the repo checkout is behind or the SSD is
# unmounted. run-due itself does nothing unless an item is approved, due, in its posting window and not stale, and
# nothing at all while ~/.purplelink/social/PAUSE exists. Log: ~/Library/Logs/purplelink-social.log
set -u

REPO="/Volumes/Extreme SSD/Purplelink LLC"
SCRIPT="$REPO/backend/scripts/social.py"
PYTHON="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
LOG="$HOME/Library/Logs/purplelink-social.log"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] wrapper: $*" >> "$LOG"; }

[ -d "$REPO/.git" ] || { log "repo not mounted; skipped"; exit 0; }
[ -f "$SCRIPT" ] || { log "social.py not in the checkout yet (main not synced); skipped"; exit 0; }
[ -x "$PYTHON" ] || { log "python not found at $PYTHON"; exit 1; }

# Code runs from the read-only jobs-ro worktree, which repo-ro.sh keeps at origin/main (as the other scheduled jobs
# have since 2026-10-23): the shared checkout's main can sit behind for days (2026-10-28: 79 commits, so merged social
# code never ran). Data paths are absolute and still point at the shared checkout. Without jobs-ro, the shared
# checkout's code runs as before.
RO="$HOME/.purplelink/bin/repo-ro.sh"
if [ -x "$RO" ]; then
  WT=$("$RO" update 2>>"$LOG") && [ -f "$WT/backend/scripts/social.py" ] && SCRIPT="$WT/backend/scripts/social.py"
fi

"$PYTHON" "$SCRIPT" run-due
exit $?
