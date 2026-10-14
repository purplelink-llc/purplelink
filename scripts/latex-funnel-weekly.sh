#!/bin/bash
# Weekly LaTeX video funnel read and stop-rule check (launchd llc.purplelink.latexfunnel, Mondays 09:10).
# Records one row in ~/.purplelink/latex-funnel/history.csv, appends the report to the log, and raises a macOS
# notification when the stop rule says something other than WAIT (CONTINUE, STOP or WARN).
# Rule text and thresholds: the docstring of scripts/latex_funnel_report.py.
# Runs the local copies in ~/.purplelink/latex-funnel/ (install: cp scripts/latex_funnel_report.py
# scripts/latex-funnel-weekly.sh there), so it works when the repo checkout is behind or the SSD is not mounted.
PYTHON="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
HERE="$HOME/.purplelink/latex-funnel"
LOG="$HOME/.purplelink-logs/latex-funnel.log"
mkdir -p "$(dirname "$LOG")"
[ -f "$HERE/latex_funnel_report.py" ] || { echo "[$(date '+%F %T')] $HERE/latex_funnel_report.py missing, skipping" >> "$LOG"; exit 0; }
OUT=$("$PYTHON" "$HERE/latex_funnel_report.py" --record 2>&1); rc=$?
{ echo "[$(date '+%F %T')] exit $rc"; echo "$OUT"; } >> "$LOG"
[ $rc -eq 0 ] || exit $rc
STATUS=$(echo "$OUT" | sed -n 's/.*stop rule: \([A-Z]*\) - .*/\1/p')
if [ -n "$STATUS" ] && [ "$STATUS" != "WAIT" ]; then
  MSG=$(echo "$OUT" | sed -n 's/.*stop rule: //p' | cut -c1-180)
  /usr/bin/osascript -e "display notification \"$MSG\" with title \"LaTeX video funnel\"" 2>/dev/null
fi
exit 0
