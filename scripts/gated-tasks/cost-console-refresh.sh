#!/bin/bash
# Nightly cost console refresh (04:42), replacing the desktop task cost-console-refresh (whose runs ended after ~4 s
# without doing the work, brief finding F1). Shell rebuilds the data and page; Haiku only does the Artifact publish.
# Never forces; never changes the artifact's sharing, title or icon. Failure notification only.
set -u
GATE_NAME="cost-console-refresh"
. "$HOME/.purplelink/bin/gate-lib.sh"

RO="/Volumes/Extreme SSD/_worktrees/Purplelink LLC/jobs-ro"
OUT="$HOME/.purplelink/cost-console"
ART="https://claude.ai/artifact/3nwSTQPAqZbb53WoQuFZKu"
log "start"
[ -x "$RO/scripts/cost_console/run.sh" ] || [ -f "$RO/scripts/cost_console/run.sh" ] || { log "jobs-ro worktree missing, skipping"; exit 0; }
if ! bash "$RO/scripts/cost_console/run.sh" >> "$LOG" 2>&1; then notify_fail "cost_console/run.sh failed"; exit 1; fi
[ -s "$OUT/index.html" ] || { notify_fail "no $OUT/index.html after run.sh"; exit 1; }

WD="$(new_workdir)" || { notify_fail "cannot make work folder"; exit 1; }
cp "$OUT/index.html" "$WD/index.html"
cat > "$WD/prompt.md" <<PROMPT
Publish the private cost console page. $WD is this session's working folder and scratchpad; $WD/index.html is the freshly built page (a copy of $OUT/index.html). Steps: 1) Artifact action read of $ART (so this session has read it). 2) One Artifact publish: url=$ART, file_path=$WD/index.html. Do not pass icon, title, capabilities or description, and never change the artifact's sharing. Never use force; if the publish is refused, merge onto the live version it hands back only if the only difference is the page's own data lines, otherwise stop and report. Finish with one short line: published or not, the 14-day total, today's figure and the ratio if the page shows them.
PROMPT
run_claude haiku 15 1 "$WD" Read Bash Glob Artifact < "$WD/prompt.md"
rc=$?
if [ "$rc" -ne 0 ]; then notify_fail "publish step exited $rc"; exit 1; fi
if [ "${GATE_DRYRUN:-0}" != "1" ] && ! printf '%s' "${LAST_CLAUDE_OUT:-}" | grep -qi "published"; then
  notify_fail "publish step did not report success"; exit 1
fi
log "done"
