#!/bin/bash
# Weekly outreach runner (Outreach/WEEKLY-PLAN.md), fired by launchd
# llc.purplelink.outreach Tue/Wed/Thu 08:30. One successful pass per ISO week;
# a failed pass (usually a LinkedIn browser hiccup) retries the next morning.
# Each channel is idempotent through OUTREACH-LOG.md, so a retry never resends
# an email or double-posts. 08:30 is deliberately before run_linkedin.sh's
# 09:00-12:00 window: both use the same Playwright profile and it cannot be
# opened twice.

PROJECT="/Volumes/Extreme SSD/Purplelink LLC"
PYTHON="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
LOG="$HOME/Library/Logs/purplelink-outreach.log"
MARKER="$HOME/.purplelink/outreach-week-$(date +%G-%V)"

[ -d "$PROJECT" ] || exit 0
[ -f "$MARKER" ] && exit 0
mkdir -p "$HOME/.purplelink"

{
  echo
  echo "════════════════════════════════════════════════════════════"
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] weekly outreach starting"
  cd "$PROJECT" && "$PYTHON" scripts/outreach.py weekly
  RC=$?
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] exit $RC"
  [ "$RC" -eq 0 ] && touch "$MARKER"
} >> "$LOG" 2>&1
exit 0
