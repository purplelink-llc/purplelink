#!/bin/bash
# Daily LinkedIn poster for Purplelink digest.
# Run by launchd every 30 min (StartInterval). Guards on active hours so it only
# fires 9am–noon. Idempotent: checks whether today's digest is already posted
# before doing anything. Retries on next wake/interval if the SSD is unmounted.

PROJECT="/Volumes/Extreme SSD/Purplelink LLC"
PYTHON="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
GIT="/usr/bin/git"
LOG="$HOME/Library/Logs/purplelink-linkedin.log"
ACTIVE_START=9
ACTIVE_END=12
DONE_MARKER="$HOME/.purplelink/linkedin-posted-$(date +%Y-%m-%d)"

notify() {
    /usr/bin/osascript -e "display notification \"$1\" with title \"Purplelink\"" 2>/dev/null
}

# Guard: SSD mounted?
[ -d "$PROJECT" ] || exit 0

# Guard: active hours only (9am–noon)
HOUR=$((10#$(date +%H)))
[ "$HOUR" -lt "$ACTIVE_START" ] || [ "$HOUR" -ge "$ACTIVE_END" ] && exit 0

# Guard: already posted today?
[ -f "$DONE_MARKER" ] && exit 0

echo "" >> "$LOG"
echo "════════════════════════════════════════════════════════════" >> "$LOG"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] LinkedIn post starting" >> "$LOG"

# Fetch only the digest directory from origin — avoids conflicts with local changes
cd "$PROJECT" || exit 0
"$GIT" fetch origin --quiet >> "$LOG" 2>&1 && \
"$GIT" checkout origin/main -- site/blog/digest/ >> "$LOG" 2>&1
if [ $? -ne 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] git fetch failed — will retry" >> "$LOG"
    exit 0
fi

# Check that today's digest file actually exists
TODAY=$(date +%Y-%m-%d)
DIGEST="$PROJECT/site/blog/digest/$TODAY.html"
if [ ! -f "$DIGEST" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] No digest file for $TODAY yet — will retry" >> "$LOG"
    exit 0
fi

# Post to LinkedIn
"$PYTHON" "$PROJECT/backend/scripts/linkedin_post.py" >> "$LOG" 2>&1
RC=$?

case $RC in
  0)
    touch "$DONE_MARKER"
    notify "Purplelink digest posted to LinkedIn"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Posted OK" >> "$LOG"
    ;;
  2)
    notify "LinkedIn session expired — run: python3 backend/scripts/linkedin_login.py"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] SESSION EXPIRED" >> "$LOG"
    ;;
  *)
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Post failed (exit $RC) — will retry" >> "$LOG"
    ;;
esac

exit 0
