#!/bin/bash
# Keeps local main level with origin/main, but only when that provably touches nothing.
# Runs from launchd every 15 minutes. It never merges, rebases, stashes, resets or deletes.
#
#   fast-forwards main only if ALL of these hold:
#     - main is checked out in the repo root and no git operation is in progress
#     - main is a pure ancestor of origin/main (no local-only commits)
#     - none of the incoming files has an uncommitted edit, none collides with an untracked
#       file, and none was modified on disk in the last 10 minutes (a session may be working on it)
#   otherwise it logs why and tells you once per state change.
REPO="${PURPLELINK_REPO:-/Volumes/Extreme SSD/Purplelink LLC}"
LOG="${PURPLELINK_SYNC_LOG:-$HOME/Library/Logs/purplelink-main-sync.log}"
STATE="${PURPLELINK_SYNC_STATE:-$HOME/.purplelink/main-sync.state}"
NOTIFY="${PURPLELINK_SYNC_NOTIFY:-1}"
mkdir -p "$(dirname "$STATE")" "$(dirname "$LOG")"
log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }
say() {   # say STATE MESSAGE : log always, notify only when the state changes
  log "$2"
  if [ "$(cat "$STATE" 2>/dev/null)" != "$1" ]; then
    echo "$1" > "$STATE"
    case "$1" in ok*) ;; *) [ "$NOTIFY" = 1 ] && osascript -e "display notification \"$2\" with title \"Purplelink main sync\"" >/dev/null 2>&1;; esac
  fi
}
[ -d "$REPO/.git" ] || { log "repo not available (drive unmounted?)"; exit 0; }
cd "$REPO" || exit 0
( git fetch -q origin main ) >/dev/null 2>&1 & fp=$!; ( sleep 30; kill $fp 2>/dev/null ) >/dev/null 2>&1 & tp=$!; wait $fp; fr=$?; kill $tp 2>/dev/null; wait $tp 2>/dev/null
[ "$fr" = 0 ] || { log "fetch failed or timed out (offline?)"; exit 0; }
branch="$(git symbolic-ref --short -q HEAD)"
[ "$branch" = "main" ] || { say "skip-branch" "main is not checked out here (on ${branch:-detached}); nothing to sync"; exit 0; }
gd="$(git rev-parse --git-dir)"
for f in index.lock MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD rebase-merge rebase-apply; do [ -e "$gd/$f" ] && { log "git operation in progress ($f); will retry"; exit 0; }; done
behind="$(git rev-list --count main..origin/main)"; ahead="$(git rev-list --count origin/main..main)"
if [ "$behind" = 0 ]; then
  [ "$ahead" = 0 ] && say "ok" "in sync with origin/main" || say "ok-ahead" "in sync; $ahead local commit(s) not pushed yet"
  exit 0
fi
if [ "$ahead" != 0 ]; then
  say "diverged" "main DIVERGED: $ahead local-only and $behind behind. Needs a person: push or rebase the local commits (nothing was changed)."
  exit 0
fi
# pure fast-forward candidate: prove it touches nothing
git diff --name-only main origin/main | sort > "$STATE.incoming"
git status --porcelain=v1 -uno | cut -c4- | sed 's/.* -> //' | sort > "$STATE.dirty"
overlap="$(comm -12 "$STATE.incoming" "$STATE.dirty")"
if [ -n "$overlap" ]; then say "blocked-dirty" "main is $behind behind but $(echo "$overlap" | wc -l | tr -d ' ') incoming file(s) have uncommitted edits (e.g. $(echo "$overlap" | head -1)); not touching them"; exit 0; fi
git diff --name-only --diff-filter=A main origin/main | sort > "$STATE.added"
collide="$(git ls-files --others --exclude-standard | sort | comm -12 - "$STATE.added")"
if [ -n "$collide" ]; then say "blocked-untracked" "main is $behind behind but an untracked file collides with an incoming one (e.g. $(echo "$collide" | head -1)); not touching it"; exit 0; fi
recent=0; while IFS= read -r p; do [ -e "$p" ] && [ -n "$(find "$p" -mmin -10 2>/dev/null)" ] && recent=1 && break; done < "$STATE.incoming"
if [ "$recent" = 1 ]; then log "an incoming file was modified in the last 10 minutes; a session may be using it, will retry"; exit 0; fi
if git merge --ff-only -q origin/main >/dev/null 2>&1; then say "ok" "fast-forwarded main by $behind commit(s) to $(git rev-parse --short main)"; else say "ff-failed" "fast-forward refused by git; nothing changed"; fi
rm -f "$STATE.incoming" "$STATE.dirty" "$STATE.added"
