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
#   * The first sweep of the day may open a sign-in window (see LOGIN_FLAG below).
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

# One sweep at a time: the sweep now waits in the heavy queue, possibly for an hour or more, and a manual
# --force run must not start a second one beside the hourly launchd run. lockf -t 0 gives up at once if held.
if [ "${PHOTOSTATS_HELD:-}" != "1" ]; then
  /usr/bin/lockf -t 0 "$STATE/run.lock" /usr/bin/env PHOTOSTATS_HELD=1 /bin/bash "$0" "$@"
  rc=$?
  # lockf exits 75 (EX_TEMPFAIL) when another instance holds the lock
  [ "$rc" -eq 75 ] && { echo "--- $(date '+%F %T') another sweep is already running or waiting; not starting a second" >> "$LOG"; exit 0; }
  exit "$rc"
fi

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

# Interpreter preflight (2026-10-19): an SSD stall left the run on a Python without websocket and all 11
# platforms failed on an import. If the interpreter cannot import what the collector needs, leave quietly
# and keep today's attempt for the next hour.
if ! "$PY" -c 'import websocket' >/dev/null 2>&1; then
  echo "--- $(date '+%F %T') python preflight failed ($PY); will try again next hour" >> "$LOG"
  exit 0
fi

echo $((n + 1)) > "$ATTEMPTS_FILE"
echo "--- $(date '+%F %T') attempt $((n + 1)) of 3 ---" >> "$LOG"
cd "$VOL" || exit 1
# First attempt of the day: if a site is signed out, bring its login page to the front (the
# collector waits up to 5 minutes per site and carries on the moment it is signed in). FAA ends
# its session server-side within hours, so a sign-in each day is expected. Later attempts
# never open a window, so Chrome does not keep popping up.
if [ "$n" -eq 0 ]; then LOGIN_FLAG=""; else LOGIN_FLAG="--no-auto-login"; fi
# With a Keychain entry (scripts/faa-autologin.py), sign in to Fine Art America first. A no-op when already
# signed in or when there is no entry, and it never blocks the sweep.
#
# The sweep drives a Chrome with 11 sites in parallel. Run beside a video render or a model run (load ~280 on
# 2026-10-20), every page timed out and 10 of 11 platforms were not read, so the FAA sale of 10-19 was missed.
# Like every other heavy job it goes through the shared queue (render lane): it waits for the lock and the memory
# gate, runs at reduced priority, and pauses while a daily pipeline is busy.
HEAVY="$HOME/.purplelink/nightq/heavy"
SWEEP='"$1" -u "$2/scripts/faa-autologin.py" --if-needed || true; exec "$1" -u "$2/scripts/stats-collect.py" --headed $3'
if [ -x "$HEAVY" ]; then
  NIGHTQ_LANE=render "$HEAVY" photostats -- /bin/bash -c "$SWEEP" sweep "$PY" "$VOL" "$LOGIN_FLAG" >> "$LOG" 2>&1
else
  /bin/bash -c "$SWEEP" sweep "$PY" "$VOL" "$LOGIN_FLAG" >> "$LOG" 2>&1
fi
rc=$?
echo "--- $(date '+%F %T') finished, exit $rc ---" >> "$LOG"

[ "$rc" -eq 0 ] && echo "$TODAY" > "$MARKER"

# The Monday memo (scripts/photo-weekly-memo.py) used to run only as the last step of the photo-pitch-weekly
# task; when Ben paused that task on 2026-10-19 the memo stopped too (10-26 was never written). It now runs
# here, after the first good sweep of each Monday-to-Sunday week that has no memo yet, so a Monday the Mac
# sleeps through is caught up later that week. It never changes the sweep's exit code.
if [ "$rc" -eq 0 ]; then
  WEEK_START="$(date -v-"$(( ($(date +%u) + 6) % 7 ))"d +%Y-%m-%d)"
  HAVE_MEMO=""
  for f in "$VOL"/docs/growth-briefs/photo-memo-*.md; do
    [ -e "$f" ] || continue
    d="$(basename "$f" .md)"; d="${d#photo-memo-}"
    [[ "$d" > "$WEEK_START" || "$d" == "$WEEK_START" ]] && HAVE_MEMO=1
  done
  if [ -z "$HAVE_MEMO" ]; then
    echo "--- $(date '+%F %T') writing this week's photo memo ---" >> "$LOG"
    "$PY" "$VOL/scripts/photo-weekly-memo.py" >> "$LOG" 2>&1 || echo "--- photo memo failed (sweep unaffected)" >> "$LOG"
  fi
fi

if [ -f "$HOME/.purplelink/collector-health.py" ]; then
  "$PY" "$HOME/.purplelink/collector-health.py" --notify >> "$LOG" 2>&1
fi
exit "$rc"
