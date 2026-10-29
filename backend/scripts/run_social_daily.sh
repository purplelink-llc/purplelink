#!/bin/bash
# Daily ranked social pipeline: pick, vet and queue today's post (the existing scheduler posts it).
# launchd job com.purplelink.social-daily calls this every 15 minutes. `social.py daily run` does nothing before the
# configured pick time, nothing once today is done, and records a missed day after the last pick time, so a Mac that
# was asleep or an SSD that was unmounted at 09:30 simply picks late the same day at the next fire. Nothing here posts.
# The installed copy lives at ~/.purplelink/bin/social-daily.sh. Log: ~/Library/Logs/purplelink-social.log
set -u

REPO="/Volumes/Extreme SSD/Purplelink LLC"
SCRIPT="$REPO/backend/scripts/social.py"
PYTHON="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
LOG="$HOME/Library/Logs/purplelink-social.log"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] daily-wrapper: $*" >> "$LOG"; }

[ -d "$REPO/.git" ] || { log "repo not mounted; will retry at the next fire"; exit 0; }
[ -f "$SCRIPT" ] || { log "social.py not in the checkout yet; will retry"; exit 0; }
[ -x "$PYTHON" ] || { log "python not found at $PYTHON"; exit 1; }

# Code runs from the read-only jobs-ro worktree, which repo-ro.sh keeps at origin/main (as the other scheduled jobs
# have since 2026-10-23): the shared checkout's main can sit behind for days (2026-10-28: 79 commits, so merged social
# code never ran). Data paths are absolute and still point at the shared checkout. Without jobs-ro, the shared
# checkout's code runs as before.
RO="$HOME/.purplelink/bin/repo-ro.sh"
if [ -x "$RO" ]; then
  WT=$("$RO" update 2>>"$LOG") && [ -f "$WT/backend/scripts/social.py" ] && SCRIPT="$WT/backend/scripts/social.py"
fi
[ -f "$REPO/backend/socialpost/daily/pipeline.py" ] || { log "daily pipeline not in the checkout yet (main not synced); will retry"; exit 0; }

# `timeout` is GNU coreutils, absent on the Mac mini (2026-10-20): without this the fetch below failed silently.
if ! command -v timeout >/dev/null 2>&1; then
  if command -v gtimeout >/dev/null 2>&1; then timeout() { gtimeout "$@"; }
  else timeout() { local s="$1"; shift; perl -e 'alarm shift; exec @ARGV or exit 127' "$s" "$@"; }; fi
fi

# origin/main gives each page's publish date; a failed fetch is fine (the last fetch is used)
timeout 60 git -C "$REPO" fetch -q origin main 2>/dev/null || true

"$PYTHON" "$SCRIPT" daily run
rc=$?

# Instagram (Ben, 2026-10-23): a Reel for each Purplelink YouTube video in the inbox and an image post for each
# LinkedIn company post that went out. Queues only; the scheduler posts. Does nothing until Instagram is enabled.
"$PYTHON" "$SCRIPT" instagram run || log "instagram run exited $?"
exit $rc
