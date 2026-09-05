#!/usr/bin/env bash
# Production deploy wrapper for purplelink.llc.
#
# Default behavior:
#   1. Regenerates site/sitemap.xml from the pages actually on disk.
#   2. Deploys site/ to Netlify --prod with the latest commit subject as the message.
#   3. Pings IndexNow about any URLs whose sitemap lastmod is today.
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

# --- Sync guard: never publish a working copy that is BEHIND origin ----------
# The content cron (Modal) commits digests to GitHub; this script publishes the
# LOCAL site/ tree. If local is behind origin, deploying would revert the live
# site to stale content (this exact bug shipped once). Fetch and refuse to
# deploy when origin has commits we don't hold. Override with FORCE_DEPLOY=1
# only when you deliberately mean to publish local-only state.
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)"
if git fetch -q origin "$BRANCH" 2>/dev/null; then
  BEHIND="$(git rev-list --count "HEAD..origin/$BRANCH" 2>/dev/null || echo 0)"
  AHEAD="$(git rev-list --count "origin/$BRANCH..HEAD" 2>/dev/null || echo 0)"
  if [[ "${BEHIND:-0}" -gt 0 && "${FORCE_DEPLOY:-0}" != "1" ]]; then
    echo "REFUSING TO DEPLOY: local is $BEHIND commit(s) behind origin/$BRANCH." >&2
    echo "Deploying now would publish stale content and revert the live site." >&2
    echo "Fix: git pull --rebase origin $BRANCH   (then re-run), or FORCE_DEPLOY=1 to override." >&2
    exit 2
  fi
  [[ "${AHEAD:-0}" -gt 0 ]] && echo "note: local is $AHEAD commit(s) ahead of origin/$BRANCH (unpushed)."
else
  echo "warning: could not fetch origin/$BRANCH — deploying without a sync check."
fi

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
  echo "  · python3 scripts/gen_sitemap.py"
  python3 scripts/gen_sitemap.py --check 2>&1 | sed 's/^/      /' || true
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

# 2. Sitemap
# Regenerated from disk on every deploy. It used to be hand-maintained and had
# drifted to 84 URLs against 105 indexable pages; Search Console showed the
# effect for /guides/word-to-latex/ as "No referring sitemaps detected" and no
# crawl ever. Generating it here means a new page cannot ship undiscoverable.
# Existing <priority>/<changefreq> tuning is preserved, and lastmod comes from
# each file's last commit, so the IndexNow step below still pings only what
# genuinely changed.
step "regenerate sitemap"
python3 scripts/gen_sitemap.py

# 2b. Asset fingerprints
# Every local CSS/JS reference carries ?v=<hash of the file>, so a changed asset
# is a new URL and the assets themselves can be cached hard (see netlify.toml).
# This MUST run before every deploy: the immutable headers mean an asset that
# ships without a fresh stamp stays cached for a year. Runs first so the deploy
# and a git-triggered Netlify build publish identical HTML.
step "fingerprint assets"
python3 scripts/fingerprint_assets.py

# 3. Frontend
step "netlify deploy --prod"
netlify deploy --prod --dir site --message "$MESSAGE"

# 4. IndexNow (best-effort)
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
