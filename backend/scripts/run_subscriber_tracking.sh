#!/bin/bash
# Weekly digest subscriber tracker. Run by launchd every Monday morning.
# Records the current subscriber count to analytics/subscriber-growth.csv
# and commits it, so growth is visible in git history over time.

PROJECT="/Volumes/Extreme SSD/Purplelink LLC"
PYTHON="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
GIT="/usr/bin/git"
LOG="$HOME/Library/Logs/purplelink-subscriber-tracking.log"

notify() {
    /usr/bin/osascript -e "display notification \"$1\" with title \"Purplelink\"" 2>/dev/null
}

# Guard: SSD mounted?
[ -d "$PROJECT" ] || exit 0

# Guard: only run on Mondays (1)
DOW=$(date +%u)
[ "$DOW" != "1" ] && exit 0

echo "" >> "$LOG"
echo "════════════════════════════════════════════════════════════" >> "$LOG"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Subscriber tracking starting" >> "$LOG"

cd "$PROJECT" || exit 0

"$PYTHON" "$PROJECT/backend/scripts/track_subscribers.py" >> "$LOG" 2>&1
RC=$?

if [ $RC -ne 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] track_subscribers.py failed (exit $RC)" >> "$LOG"
    exit 0
fi

# Commit + push only if the log actually changed
if ! "$GIT" diff --quiet -- analytics/subscriber-growth.csv 2>/dev/null; then
    "$GIT" add analytics/subscriber-growth.csv
    "$GIT" commit -m "chore(analytics): record weekly subscriber count" --quiet
    "$GIT" push --quiet 2>> "$LOG"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Committed + pushed growth log" >> "$LOG"
    notify "Subscriber count recorded for this week"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] No change to commit" >> "$LOG"
fi

exit 0
