#!/bin/bash
# launchd entry point for the daily photo-stats sweep (scripts/stats-collect.py).
#
# Installed as a local copy at ~/.purplelink/photostats-run.sh so launchd can start it
# when the external SSD is not mounted yet (the same reason the traffic job has run.sh).
#
# Why a wrapper, not the script directly:
#   * A calendar job that fires while the Mac sleeps is not reliable (the sweep missed
#     2026-10-06 and 2026-10-08), so launchd calls this at login, hourly and at 07:00,
#     and this keeps it to one good sweep a day.
#   * It waits for the SSD instead of failing when the Mac has just woken.
#   * A sweep that only failed for connection reasons is retried, at most 3 attempts a day,
#     so Chrome does not keep opening.
#   * It reports what is stale afterwards (collector-health.py).
#
# stats-collect.py exits 0 = done, 3 = some platforms failed on the connection (retry),
# 4 = nothing collected (retry), 2 = crashed (retry). Signed-out sites are not retried: a
# retry cannot fix those, and collector-health.py says which ones need a sign-in.
set -uo pipefail

VOL="/Volumes/Extreme SSD/Purplelink LLC"
PY="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
[ -x "$PY" ] || PY="$(command -v python3)"
STATE="$HOME/.purplelink/photostats"
LOG="$HOME/.purplelink-logs/photostats.log"
mkdir -p "$STATE" "$HOME/.purplelink-logs"

TODAY="$(date +%Y-%m-%d)"
MARKER="$STATE/last-success-date"
ATTEMPTS_FILE="$STATE/attempts-$TODAY"
n="$(cat "$ATTEMPTS_FILE" 2>/dev/null || echo 0)"

if [ "${1:-}" != "--force" ]; then
  [ "$(date +%H)" -lt 7 ] && exit 0
  [ "$(cat "$MARKER" 2>/dev/null)" = "$TODAY" ] && exit 0
  [ "$n" -ge 3 ] && exit 0
fi

# Wait up to two minutes for the SSD. Not mounted: leave quietly, try again next hour,
# and do not spend one of today's attempts on it.
for _ in $(seq 1 24); do
  [ -f "$VOL/scripts/stats-collect.py" ] && break
  sleep 5
done
if [ ! -f "$VOL/scripts/stats-collect.py" ]; then
  echo "--- $(date '+%F %T') SSD not mounted; will try again next hour" >> "$LOG"
  [ -f "$HOME/.purplelink/collector-health.py" ] && "$PY" "$HOME/.purplelink/collector-health.py" --notify >> "$LOG" 2>&1
  exit 0
fi

echo $((n + 1)) > "$ATTEMPTS_FILE"
echo "--- $(date '+%F %T') attempt $((n + 1)) of 3 ---" >> "$LOG"
cd "$VOL" || exit 1
"$PY" -u "$VOL/scripts/stats-collect.py" --headed --no-auto-login >> "$LOG" 2>&1
rc=$?
echo "--- $(date '+%F %T') finished, exit $rc ---" >> "$LOG"

[ "$rc" -eq 0 ] && echo "$TODAY" > "$MARKER"

if [ -f "$HOME/.purplelink/collector-health.py" ]; then
  "$PY" "$HOME/.purplelink/collector-health.py" --notify >> "$LOG" 2>&1
fi
exit "$rc"
