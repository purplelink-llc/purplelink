#!/bin/bash
# Daily social metrics (clicks, engagement, followers) and, once a week, the report and learning step.
# launchd job com.purplelink.social-metrics calls this hourly; it runs once per US Eastern day, after 12:00 Eastern.
# A missing repo is logged and retried at the next fire, so the day is not lost. Reads and writes private files only
# (~/.purplelink/social/metrics.json); the weekly report goes to docs/growth-briefs (git-ignored). Nothing here posts.
# The installed copy lives at ~/.purplelink/bin/social-metrics.sh. Log: ~/Library/Logs/purplelink-social.log
set -u

REPO="/Volumes/Extreme SSD/Purplelink LLC"
SCRIPT="$REPO/backend/scripts/social.py"
PYTHON="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
LOG="$HOME/Library/Logs/purplelink-social.log"
MARK="$HOME/.purplelink/social/metrics-last-day"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] metrics-wrapper: $*" >> "$LOG"; }

NYDAY=$(TZ=America/New_York date +%F)
NYH=$(TZ=America/New_York date +%H)
[ "$NYH" -ge 12 ] || exit 0
[ "$(cat "$MARK" 2>/dev/null)" = "$NYDAY" ] && exit 0
[ -d "$REPO/.git" ] || { log "repo not mounted; will retry at the next fire"; exit 0; }
[ -f "$REPO/backend/socialpost/daily/metrics.py" ] || { log "metrics code not in the checkout yet; will retry"; exit 0; }
[ -x "$PYTHON" ] || { log "python not found at $PYTHON"; exit 1; }

# Code runs from the read-only jobs-ro worktree at origin/main (repo-ro.sh), like run_social.sh and
# run_social_daily.sh; data paths are absolute and stay in the shared checkout. Without jobs-ro, the shared checkout's
# code runs as before.
RO="$HOME/.purplelink/bin/repo-ro.sh"
if [ -x "$RO" ]; then
  WT=$("$RO" update 2>>"$LOG") && [ -f "$WT/backend/scripts/social.py" ] && SCRIPT="$WT/backend/scripts/social.py"
fi

if "$PYTHON" "$SCRIPT" daily metrics >> "$LOG" 2>&1; then
  mkdir -p "$(dirname "$MARK")" && echo "$NYDAY" > "$MARK"
else
  log "metrics failed; will retry at the next fire"
fi
exit 0
