#!/bin/bash
# Hourly release watcher: when an iPhone app is live on the App Store, publish its prepared YouTube videos.
# launchd job com.purplelink.app-release-watch calls this at minute 20 of every hour. Code comes from the jobs-ro
# worktree (origin/main) through repo-ro.sh; release.json files and the thumbnails are git-ignored and are read from the
# shared checkout by the script itself. The installed copy lives at ~/.purplelink/bin/app-release-watch.sh.
# Pause: touch ~/.purplelink/app-release-watch/PAUSE (delete it to resume). Log: ~/Library/Logs/purplelink-app-release-watch.log
# Arguments (--check, --dry-run, --app NAME) pass through to scripts/app-release-watch.py.
set -u

REPO="/Volumes/Extreme SSD/Purplelink LLC"
PYTHON="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
RO="$HOME/.purplelink/bin/repo-ro.sh"
LOG="$HOME/Library/Logs/purplelink-app-release-watch.log"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"
export PYTHONUNBUFFERED=1

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] wrapper: $*" >> "$LOG"; }

# The SSD may be unmounted or asleep; the next hour tries again.
[ -d "$REPO/.git" ] || { log "repo not mounted; will retry at the next run"; exit 0; }
[ -x "$PYTHON" ] || { log "python not found at $PYTHON"; exit 1; }
[ -x "$RO" ] || { log "repo-ro.sh not found at $RO"; exit 1; }

cd "$HOME" || exit 1
"$RO" exec "$PYTHON" scripts/app-release-watch.py "$@" >> "$LOG" 2>&1
rc=$?
[ "$rc" -eq 0 ] || log "app-release-watch.py exited $rc"
exit "$rc"
