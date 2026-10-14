#!/bin/bash
# Weekly Test & Compare check (launchd llc.purplelink.ytabtest, Sundays 03:30, through run-when-online.sh).
# Runs local copies in ~/.purplelink/yt-abtest (the shared main checkout can lag) and keeps its own log there;
# notifies once when a test reaches a result. Install: copy yt-abtest.py, yt-thumbnail.py, yt-upload.py, cdp_tab.py
# and this file into ~/.purplelink/yt-abtest, seed ab-tests.json from video/thumbs/ab-tests.json, load the plist.
set -u
D="$HOME/.purplelink/yt-abtest"
export YT_ABTEST_LOG="$D/ab-tests.json"
PY=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3
[ -x "$PY" ] || PY=python3
cd "$D" || exit 1
out=$("$PY" yt-abtest.py status 2>&1); rc=$?
printf '%s %s\n%s\n' "$(date '+%F %T')" "rc=$rc" "$out" >> "$D/weekly.log"
if [ $rc -ne 0 ]; then
  osascript -e 'display notification "Weekly thumbnail test check failed; see ~/.purplelink/yt-abtest/weekly.log" with title "YouTube A/B"' >/dev/null 2>&1
  exit $rc
fi
res=$(printf '%s\n' "$out" | grep '^RESULT' | head -3)
if [ -n "$res" ]; then
  msg=$(printf '%s' "$res" | tr '\n' ' ' | cut -c1-180 | sed 's/"/'"'"'/g')
  osascript -e "display notification \"$msg\" with title \"YouTube thumbnail test result\"" >/dev/null 2>&1
fi
exit 0
