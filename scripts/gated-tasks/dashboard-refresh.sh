#!/bin/bash
# Daily dashboard refresh (04:33), replacing the desktop task refresh-purplelink-dashboard.
# Same steps as ~/.purplelink/traffic/artifact-export/REFRESH.md; only the steps that need a model use claude -p:
#   1/1b Gmail counts (Haiku, read-only search) -> 2 export_all.sh (shell) -> 2b drafts (Sonnet)
#   -> 3 freshness check + 4 build and stage (dashboard_stage.py stage, shell).
# The publish itself is the desktop task dashboard-live-publish (05:00, 11:00, 15:00, 19:00): headless claude -p has no
# Artifact tool, so a launchd publish never worked (stale dashboard 2026-11-06/07). Failure notification only.
set -u
GATE_NAME="dashboard-refresh"
. "$HOME/.purplelink/bin/gate-lib.sh"

T="$HOME/.purplelink/traffic"
X="$T/artifact-export"
ART="https://claude.ai/artifact/9ipzFZUBAci9n2Y4hRpWGx"
TODAY="$(date +%Y-%m-%d)"
log "start"
[ -d "$X" ] || { log "artifact-export folder missing (drive not mounted?), skipping"; exit 0; }
WD="$(new_workdir)" || { notify_fail "cannot make work folder"; exit 1; }

# Steps 1 and 1b: read-only Gmail counts. Failure here is not fatal (REFRESH.md: delete the files, dashboard says "not checked").
GMAIL_TOOL="mcp__claude_ai_Gmail__search_threads"
S="$(date -v-7d +%Y/%m/%d)"
cat > "$WD/gmail-prompt.md" <<PROMPT
Do exactly these two read-only Gmail checks and write two JSON files. Only use the search_threads tool; never open, quote, reply to, send, draft or delete any message.
1. Search threads: from:alerts@purplelink.llc newer_than:14d . Write $T/artifact-data/gmail_alerts.json as {"count": <number of threads>, "days": 14, "checked": "<ISO time now>"}.
2. With S = $S, count threads for (a) after:$S from:mail@depositphotos.com subject:"Sold Files" and (b) after:$S from:donotreply@fineartamerica.com subject:"New Order". Write $T/artifact-data/photo_sale_emails.json as {"checked": "<ISO time now>", "since": "$(date -v-7d +%Y-%m-%d)", "platforms": {"Depositphotos": <n>, "Fine Art America": <n>}}.
If Gmail is unavailable, delete the file(s) you could not write instead of writing a count. Finish with one short line.
PROMPT
rm -f "$T/artifact-data/gmail_alerts.json.new" 2>/dev/null
run_claude haiku 12 0.5 "$WD" "$GMAIL_TOOL" Write Bash Read < "$WD/gmail-prompt.md" || log "gmail step failed (non-fatal)"

# Step 2: deterministic export. Must exit 0.
if ! bash "$X/export_all.sh" >> "$LOG" 2>&1; then notify_fail "export_all.sh failed"; exit 1; fi

# Step 2b: generative drafts (local files only), Sonnet.
cat > "$WD/drafts-prompt.md" <<PROMPT
Read $X/REFRESH.md and do ONLY step 2b (the generative steps a to d), exactly as written there. export_all.sh has already run. Do not do any other step: no Gmail, no build, no publish, no Artifact calls. Use only the local input files the prompts name; do not open any image, browser or website; do not send, post, draft or delete any email; never write these files into the repo. If a prompt says to stop (stale input), skip that step and say so. If a step fails, say which and carry on. Finish with one short line.
PROMPT
run_claude sonnet 40 3 "$WD" Bash Read Write Edit Glob < "$WD/drafts-prompt.md" || log "2b drafts step failed (non-fatal, carried on)"

# Step 3: the daily traffic run must have finished today.
LSD="$(cat "$T/last-success-date" 2>/dev/null || true)"
if [ "$LSD" != "$TODAY" ]; then notify_fail "last-success-date is '$LSD', not $TODAY: traffic run not finished, nothing published"; exit 1; fi

# Step 4: build into a side folder, check it, swap it in as live-build and mark it pending for the desktop publish task.
if ! BID="$("$PYTHON" -I "$HOME/.purplelink/bin/dashboard_stage.py" stage --source nightly 2>>"$LOG")"; then
  notify_fail "build or staging failed (see log); nothing new staged"; exit 1
fi
log "staged $BID for the 05:00 desktop publish"
log "done"
