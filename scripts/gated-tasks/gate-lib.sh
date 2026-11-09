#!/bin/bash
# Shared helpers for the gated scheduled tasks (token-efficiency brief, recommendation 8, 2026-11-04).
# Sourced by p1-coding-gate.sh, dashboard-live-gate.sh, dashboard-refresh.sh and cost-console-refresh.sh; never run alone.
# Each wrapper does its cheap checks in plain shell and starts `claude -p` only for the step that needs a model,
# so a run with nothing to do costs no tokens. Installed copies live in ~/.purplelink/bin/.
#
# Callers set GATE_NAME before sourcing. Logs: ~/Library/Logs/purplelink-<GATE_NAME>.log. Notifications only on failure.
# GATE_DRYRUN=1 logs the claude command instead of running it (used to test the gate without spending tokens).
set -u

export HOME="${HOME:-/Users/benampel}"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/Library/Frameworks/Python.framework/Versions/3.12/bin:/usr/bin:/bin:$PATH"
PYTHON="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
LOG="$HOME/Library/Logs/purplelink-${GATE_NAME:?GATE_NAME not set}.log"
GATE_BASE="$HOME/.purplelink/gate"
mkdir -p "$GATE_BASE/work" "$HOME/Library/Logs"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ${GATE_NAME}: $*" >> "$LOG"; }

# One failure notification per run, no sound and no focus change (osascript display notification only posts a banner).
notify_fail() {
  log "FAILED: $*"
  /usr/bin/osascript -e "display notification \"$(printf '%s' "$*" | tr '"\\' "''" | cut -c1-180)\" with title \"Scheduled job failed: ${GATE_NAME}\"" >/dev/null 2>&1 || true
}

# `timeout` is GNU coreutils and absent on this Mac; perl's alarm does the same job.
run_timeout() { local s="$1"; shift; perl -e 'alarm shift; exec @ARGV or exit 127' "$s" "$@"; }

# Fresh working folder for one claude run: it is the run's cwd and its scratchpad (the Artifact tool only publishes from
# the working directory or the scratchpad). Folders older than 3 days are pruned with find -delete under the fixed base.
new_workdir() {
  local d="$GATE_BASE/work/${GATE_NAME}-$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$d" && echo "$d"
  [ -d "$GATE_BASE/work" ] && find "$GATE_BASE/work" -mindepth 1 -depth -mtime +3 -delete 2>/dev/null
  return 0
}

# Body of a desktop scheduled task prompt: SKILL.md without its frontmatter (so the model gets the same instructions
# the desktop task had; re-enabling the task restores the old behaviour with no other change).
skill_body() { awk 'BEGIN{n=0} n>=2{print; next} /^---[[:space:]]*$/{n++}' "$HOME/.claude/scheduled-tasks/$1/SKILL.md"; }

# run_claude <model> <max-turns> <max-usd> <workdir> <allowedTools...>   (prompt on stdin)
# Sonnet or Haiku only. Prints claude's final text to the log. Returns claude's exit code (124 on timeout).
run_claude() {
  local model="$1" turns="$2" usd="$3" wd="$4"; shift 4
  case "$model" in sonnet|haiku) ;; *) notify_fail "refusing model '$model' (Sonnet or Haiku only)"; return 2;; esac
  local prompt; prompt="$(cat)"
  # launchd gives stdin /dev/null: a call without a redirect used to run claude with no prompt (2b drafts, until 11-07)
  if [ -z "${prompt//[[:space:]]/}" ]; then notify_fail "run_claude called with an empty prompt (missing < prompt file?)"; return 2; fi
  if [ "${GATE_DRYRUN:-0}" = "1" ]; then
    log "DRYRUN claude -p --model $model --max-turns $turns --max-budget-usd $usd cwd=$wd tools=$* prompt_bytes=${#prompt}"
    return 0
  fi
  local out rc
  out="$(cd "$wd" && printf '%s' "$prompt" | run_timeout 1800 claude -p --model "$model" --max-turns "$turns" \
        --max-budget-usd "$usd" --permission-mode dontAsk --allowedTools "$@" 2>&1)"
  rc=$?
  # A rare empty-input failure was seen once (2026-11-04); one retry is cheap because nothing ran.
  if [ $rc -ne 0 ] && printf '%s' "$out" | grep -q "Input must be provided"; then
    log "claude ($model) reported empty input, retrying once"
    out="$(cd "$wd" && printf '%s' "$prompt" | run_timeout 1800 claude -p --model "$model" --max-turns "$turns" \
          --max-budget-usd "$usd" --permission-mode dontAsk --allowedTools "$@" 2>&1)"
    rc=$?
  fi
  log "claude ($model) exit $rc: $(printf '%s' "$out" | tail -c 1500 | tr '\n' ' ')"
  LAST_CLAUDE_OUT="$out"
  return $rc
}
