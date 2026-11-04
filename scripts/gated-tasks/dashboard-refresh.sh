#!/bin/bash
# Daily dashboard refresh (04:33), replacing the desktop task refresh-purplelink-dashboard.
# Same steps as ~/.purplelink/traffic/artifact-export/REFRESH.md; only the steps that need a model use claude -p:
#   1/1b Gmail counts (Haiku, read-only search) -> 2 export_all.sh (shell) -> 2b drafts (Sonnet)
#   -> 3 freshness check + 4 build (shell) -> 5/6 artifact read, check_live, one publish (Haiku).
# Never forces a publish. Failure notification only.
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
run_claude sonnet 40 3 "$WD" Bash Read Write Edit Glob || log "2b drafts step failed (non-fatal, carried on)"

# Step 3: the daily traffic run must have finished today.
LSD="$(cat "$T/last-success-date" 2>/dev/null || true)"
if [ "$LSD" != "$TODAY" ]; then notify_fail "last-success-date is '$LSD', not $TODAY: traffic run not finished, nothing published"; exit 1; fi

# Step 4: build.
if ! bash "$X/page/build_page.sh" "$WD/dash" >> "$LOG" 2>&1; then notify_fail "build_page.sh failed"; exit 1; fi

# Steps 5 and 6: read, check, one publish, then record. Haiku, never force.
cat > "$WD/publish-prompt.md" <<PROMPT
Publish the Purplelink dashboard. The build is already done in $WD/dash (index.html plus data/*.json); $WD is this session's working folder and scratchpad. Do ONLY REFRESH.md steps 5 and 6 from $X/REFRESH.md, exactly as written there: Artifact read of $ART, Artifact list scope files, check_live.py against the saved live page with --merge $WD/dash-merged/index.html (exit 2 or 1: stop and report, do not publish), then one publish (url=$ART, file_path=$WD/dash/index.html, root=$WD/dash, files for every file in $WD/dash/data; no icon, title or capabilities). If refused for live-page lines the build lacks, follow the merged-copy procedure in step 5 once. Never use force; never resend a refused file unchanged. After a successful publish only: rewrite $X/published.json as {id: sha256} for each data file and copy $WD/dash/index.html to $X/last-published.html. Do not run export_all.sh or build_page.sh and do not edit anything under $X/page/. Finish with one short line: which datasets changed, the generated time in the export_info.json, and whether the publish succeeded.
PROMPT
run_claude haiku 40 2 "$WD" Bash Read Write Edit Glob Artifact < "$WD/publish-prompt.md"
rc=$?
if [ "$rc" -ne 0 ]; then notify_fail "publish step exited $rc"; exit 1; fi
if [ "${GATE_DRYRUN:-0}" != "1" ] && ! printf '%s' "${LAST_CLAUDE_OUT:-}" | grep -qi "publish.*succe\|published"; then
  notify_fail "publish step did not report success"; exit 1
fi
log "done"
