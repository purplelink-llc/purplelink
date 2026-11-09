#!/bin/bash
# Dashboard publish watchdog. launchd job com.purplelink.dashboard-live-gate runs this at 05:40, 11:40, 15:40 and 19:40,
# forty minutes after each slot of the desktop task dashboard-live-publish, which does the Artifact publish (headless
# claude -p has no Artifact tool, so this job no longer publishes; 2026-11-07). It only reads state and notifies:
# a staged build that missed its slot, or no successful publish for 30 hours, posts one notification per problem a day.
GATE_NAME=dashboard-live-gate
. "$HOME/.purplelink/bin/gate-lib.sh" || exit 1
set -u

T="$HOME/.purplelink/traffic"
[ -d "$T" ] || { log "traffic folder missing, skipping"; exit 0; }
msg="$("$PYTHON" -I "$HOME/.purplelink/bin/dashboard_stage.py" watchdog 2>&1)"
rc=$?
log "$msg"
[ $rc -eq 0 ] && exit 0
# One notification per distinct problem per day, so a desktop app left closed overnight does not ping four times.
key="$(date +%Y-%m-%d) $(printf '%s' "$msg" | sed 's/[0-9][0-9]-[0-9][0-9] [0-9:]*//g' | shasum | cut -c1-12)"
seen="$T/.watchdog-notified"
if [ "$(cat "$seen" 2>/dev/null)" != "$key" ]; then
  notify_fail "dashboard not published: $msg. Open the Claude app; the desktop task dashboard-live-publish publishes it."
  printf '%s' "$key" > "$seen"
fi
exit 1
