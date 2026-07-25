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

# Commit + push only if the log actually changed.
#
# `git commit --only <path>` is deliberate: this runs unattended against the
# same working copy a human uses, so a bare `git commit` would sweep up whatever
# happened to be staged at the time and push it. --only commits that one file
# and nothing else, regardless of the index state.
if ! "$GIT" diff --quiet -- analytics/subscriber-growth.csv 2>/dev/null; then
    if ! "$GIT" commit --only analytics/subscriber-growth.csv \
            -m "chore(analytics): record weekly subscriber count" --quiet; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] commit failed — leaving for manual review" >> "$LOG"
        exit 0
    fi

    # Only push a fast-forward. If main has diverged (a local digest run, an
    # unpushed commit), stop and let a human sort it out rather than forcing.
    "$GIT" fetch origin main --quiet 2>> "$LOG"
    BEHIND="$("$GIT" rev-list --count HEAD..origin/main 2>/dev/null || echo 0)"
    if [ "$BEHIND" != "0" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] main is $BEHIND behind origin — committed locally, not pushing" >> "$LOG"
        notify "Subscriber count committed; push skipped (main behind origin)"
        exit 0
    fi

    if "$GIT" push --quiet 2>> "$LOG"; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Committed + pushed growth log" >> "$LOG"
        notify "Subscriber count recorded for this week"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] push failed — commit is local only" >> "$LOG"
    fi
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] No change to commit" >> "$LOG"
fi

exit 0
