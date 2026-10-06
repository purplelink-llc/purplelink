#!/bin/bash
# Blocks a commit on branch main while main is behind origin/main.
#
# Why: the daily digest cron and other sessions push to origin/main all day. A commit made on a
# stale local main makes the two histories diverge, and a diverged main has already broken
# deploys (2026-07-24, 2026-10-05). Commit on a branch or a worktree off origin/main instead,
# or bring main up to date first.
#
# Escape hatch (rare, deliberate):  ALLOW_STALE_MAIN=1 git commit ...
[ -n "${ALLOW_STALE_MAIN:-}" ] && exit 0
branch="$(git symbolic-ref --short -q HEAD)" || exit 0
[ "$branch" = "main" ] || exit 0
gitdir="$(git rev-parse --git-dir)"
# Reconciling already: a merge, rebase or cherry-pick is in progress.
if [ -f "$gitdir/MERGE_HEAD" ] || [ -f "$gitdir/CHERRY_PICK_HEAD" ] || [ -d "$gitdir/rebase-merge" ] || [ -d "$gitdir/rebase-apply" ]; then exit 0; fi
# Refresh origin/main, but never hang a commit on the network: give up after 8 seconds.
( git fetch -q origin main >/dev/null 2>&1 ) & fetch_pid=$!
( sleep 8; kill "$fetch_pid" 2>/dev/null ) >/dev/null 2>&1 & timer_pid=$!
wait "$fetch_pid" 2>/dev/null
kill "$timer_pid" 2>/dev/null; wait "$timer_pid" 2>/dev/null
git rev-parse -q --verify origin/main >/dev/null || exit 0   # no remote ref: nothing to compare
behind="$(git rev-list --count HEAD..origin/main 2>/dev/null || echo 0)"
[ "${behind:-0}" -gt 0 ] || exit 0
ahead="$(git rev-list --count origin/main..HEAD 2>/dev/null || echo 0)"
{
  echo ""
  echo "BLOCKED: local main is $behind commit(s) behind origin/main (and $ahead ahead)."
  echo ""
  echo "The daily digest cron and other sessions push to origin/main, so a commit made here now"
  echo "makes main diverge. That has already broken deploys twice (2026-07-24 and 2026-10-05)."
  echo ""
  echo "Do one of these:"
  echo "  1) Best: commit in a worktree off origin/main, then push (nothing shared is touched):"
  echo "       git worktree add \"../work-\$(date +%H%M)\" -b my-change origin/main"
  echo "  2) Bring main up to date first (stash your uncommitted work if git asks):"
  echo "       git stash && git rebase origin/main && git stash pop"
  echo "  3) Deliberate override, rare:  ALLOW_STALE_MAIN=1 git commit ..."
  echo ""
} >&2
exit 1
