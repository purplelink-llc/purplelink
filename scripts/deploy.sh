#!/usr/bin/env bash
# Production deploy wrapper for purplelink.llc.
#
# Default behavior:
#   1. Deploys site/ to Netlify --prod with the latest commit subject as the message.
#   2. Pings IndexNow about any URLs whose sitemap lastmod is today.
#
# Usage:
#   bash scripts/deploy.sh                  # frontend + IndexNow
#   bash scripts/deploy.sh --backend         # also deploy backend/ to Modal
#   bash scripts/deploy.sh --message "..."   # custom Netlify deploy message
#   bash scripts/deploy.sh --skip-ping       # frontend only, no IndexNow
#   bash scripts/deploy.sh --ping-all        # ping every URL in the sitemap
#   bash scripts/deploy.sh --dry-run         # print the planned actions, don't execute
#
# Exits non-zero on first failure. IndexNow is best-effort — its failure is
# reported but does not fail the deploy (your site is already live).
set -euo pipefail

MESSAGE=""
DO_BACKEND=0
SKIP_PING=0
PING_ALL=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backend)    DO_BACKEND=1; shift ;;
    --skip-ping)  SKIP_PING=1; shift ;;
    --ping-all)   PING_ALL=1; shift ;;
    --message)    MESSAGE="$2"; shift 2 ;;
    --dry-run)    DRY_RUN=1; shift ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *)
      echo "unknown arg: $1" >&2
      exit 1 ;;
  esac
done

# Run from repo root regardless of invocation path
cd "$(dirname "$0")/.."

# Default message: latest commit subject
if [[ -z "$MESSAGE" ]]; then
  MESSAGE="$(git log -1 --pretty=%s)"
fi

# Warn (don't block) on uncommitted changes — the user might be deploying
# intentionally-dirty state for preview, but they should at least see it.
if [[ -n "$(git status --porcelain 2>/dev/null || true)" ]]; then
  echo "warning: uncommitted changes detected"
  git status --short | head -5
  echo
fi

step() { printf "\n=== %s ===\n" "$*"; }

if [[ $DRY_RUN -eq 1 ]]; then
  step "DRY RUN — planned actions"
  [[ $DO_BACKEND -eq 1 ]] && echo "  · modal deploy backend/app.py"
  echo "  · netlify deploy --prod --dir site --message \"$MESSAGE\""
  if [[ $SKIP_PING -eq 0 ]]; then
    if [[ $PING_ALL -eq 1 ]]; then
      echo "  · python3 scripts/indexnow_ping.py --all"
    else
      echo "  · python3 scripts/indexnow_ping.py    (today's lastmod URLs)"
    fi
  fi
  exit 0
fi

# 1. Backend (optional)
if [[ $DO_BACKEND -eq 1 ]]; then
  step "modal deploy backend/app.py"
  (cd backend && modal deploy app.py)
fi

# 2. Frontend
step "netlify deploy --prod"
netlify deploy --prod --dir site --message "$MESSAGE"

# 3. IndexNow (best-effort)
if [[ $SKIP_PING -eq 0 ]]; then
  step "IndexNow ping"
  if [[ $PING_ALL -eq 1 ]]; then
    python3 scripts/indexnow_ping.py --all || echo "(IndexNow ping failed — non-fatal)"
  else
    python3 scripts/indexnow_ping.py || echo "(IndexNow ping failed — non-fatal)"
  fi
fi

step "done"
echo "https://purplelink.llc"
