#!/bin/bash
# Dashboard live publish, gated. launchd job com.purplelink.dashboard-live-gate runs this at 11:00, 15:00 and 19:00.
# Steps 1 to 3 of the desktop task dashboard-live-publish (nothing staged / build still being written / export lock)
# are plain shell here. Only a staged, consistent build starts `claude -p --model haiku` for the Artifact publish
# (steps 4 and 5, the task's own prompt).
GATE_NAME=dashboard-live-gate
. "$HOME/.purplelink/bin/gate-lib.sh" || exit 1
set -u

T="$HOME/.purplelink/traffic"
[ -f "$T/publish-pending.json" ] || { log "nothing staged"; exit 0; }
[ -d "$T/live-build" ] || { log "live-build folder missing"; exit 0; }
want="$("$PYTHON" -I -c 'import json,sys;print(json.load(open(sys.argv[1]))["sha256"])' "$T/publish-pending.json" 2>/dev/null)"
have="$(shasum -a 256 "$T/live-build/index.html" 2>/dev/null | cut -d' ' -f1)"
if [ -z "$want" ] || [ "$want" != "$have" ]; then log "build in progress; skipped"; exit 0; fi
if [ -e "$T/.export.lock" ]; then log "export running; skipped"; exit 0; fi

WD="$(new_workdir)"
{
  echo "Setup note from the launcher: the staged-flag, build-hash and export-lock checks (steps 1 to 3) already passed, so go straight to step 4."
  echo "Use this folder as <this session's scratchpad>: $WD"
  echo
  skill_body dashboard-live-publish
} | run_claude haiku 40 2 "$WD" Bash Read Write Edit Glob Artifact
rc=$?
if [ $rc -ne 0 ]; then notify_fail "claude run exited $rc (staged build left in place for the next slot)"; exit 1; fi
log "done"
