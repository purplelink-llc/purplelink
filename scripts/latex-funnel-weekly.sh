#!/bin/bash
# Weekly LaTeX video funnel read and stop-rule check (launchd llc.purplelink.latexfunnel, Mondays 09:10).
# Records one row in ~/.purplelink/latex-funnel/history.csv, appends the report to the log, and raises a macOS
# notification when the stop rule says something other than WAIT (CONTINUE, STOP or WARN).
# Rule text and thresholds: the docstring of scripts/latex_funnel_report.py.
PYTHON="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
REPO="/Volumes/Extreme SSD/Purplelink LLC"
LOG="$HOME/.purplelink-logs/latex-funnel.log"
mkdir -p "$(dirname "$LOG")"
[ -f "$REPO/scripts/latex_funnel_report.py" ] || { echo "[$(date '+%F %T')] repo not mounted, skipping" >> "$LOG"; exit 0; }
OUT=$("$PYTHON" "$REPO/scripts/latex_funnel_report.py" --record 2>&1); rc=$?
{ echo "[$(date '+%F %T')] exit $rc"; echo "$OUT"; } >> "$LOG"
[ $rc -eq 0 ] || exit $rc
STATUS=$(echo "$OUT" | sed -n 's/.*stop rule: \([A-Z]*\) - .*/\1/p')
if [ -n "$STATUS" ] && [ "$STATUS" != "WAIT" ]; then
  MSG=$(echo "$OUT" | sed -n 's/.*stop rule: //p' | cut -c1-180)
  /usr/bin/osascript -e "display notification \"$MSG\" with title \"LaTeX video funnel\"" 2>/dev/null
fi
exit 0
