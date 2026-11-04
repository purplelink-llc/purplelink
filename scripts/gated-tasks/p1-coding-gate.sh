#!/bin/bash
# TELLTALE P1 blind coding, gated. launchd job com.purplelink.p1-coding-gate runs this every 4 h (at :17, as the desktop
# task p1-blind-coding did). The prep script prints NOTHING TO CODE on most runs; only a ready (or interrupted) batch starts
# Claude, with the task's own prompt (~/.claude/scheduled-tasks/p1-blind-coding/SKILL.md) on Sonnet. Nothing else changes:
# same prep and merge scripts, same two parallel Sonnet coders, same hash chain.
GATE_NAME=p1-coding-gate
. "$HOME/.purplelink/bin/gate-lib.sh" || exit 1
set -u

CODE="/Volumes/Extreme SSD/Prediction Markets/docs/fraud-detection/delphi-2026-10-19/code"
[ -d "$CODE" ] || { log "SSD not mounted; nothing to do"; exit 0; }

prep="$(cd "$CODE" && "$PYTHON" -I p1_coding_prep.py 2>&1)"; rc=$?
if [ $rc -ne 0 ]; then notify_fail "p1_coding_prep.py exited $rc: $(printf '%s' "$prep" | tail -c 200)"; exit 1; fi
case "$prep" in
  *"NOTHING TO CODE"*) log "nothing to code"; exit 0;;
  *"BATCH READY"*|*"already pending"*) log "batch ready or pending; starting coders";;
  *) notify_fail "unexpected prep output: $(printf '%s' "$prep" | tail -c 200)"; exit 1;;
esac

# The prep above already created the batch, so the prompt's own Step 1 will see "A batch is already pending", which its
# text handles (it clears only codes_A/codes_B, which cannot exist yet) and then carries on to Step 2.
WD="$(new_workdir)"
skill_body p1-blind-coding | run_claude sonnet 40 4 "$WD" Bash Read Write Agent
rc=$?
if [ $rc -ne 0 ]; then notify_fail "claude run exited $rc (batch left pending; the next run resumes it)"; exit 1; fi
log "done"
