#!/usr/bin/env bash
# Netlify's build.ignore step (netlify.toml). Exit 0 skips the build, exit 1 builds.
#
# Builds are batched to save build minutes (Netlify Starter: 300 a month). A push to main does NOT build, except:
#   - the digest cron's final daily commit ("chore(digest): Daily Digest #N ..."), so the emailed digest link is live;
#   - any commit whose message contains "[deploy now]", for fixes that cannot wait (checkout, delivery, security).
# Everything else waits for the scheduled build: a launchd job on Ben's Mac calls the "scheduled" build hook at 06:00
# and 17:00 US Eastern when main has unpublished site changes (~/.purplelink/bin/netlify-batch-build.sh). Builds started by a
# build hook are never cancelled by this step (Netlify docs, "Ignore builds"), so they always run.
#
# Even the two exceptions build only when the push changed a build input; adding a script to `command` in
# netlify.toml means adding it to INPUTS here too.
set -u

INPUTS=(site netlify netlify.toml package.json package-lock.json scripts/netlify_ignore.sh
  scripts/apply_layout.py scripts/fingerprint_assets.py scripts/gen_search_index.py scripts/gen_blog_feed.py
  scripts/gen_llms_full.py scripts/check_og_images.py scripts/check_content.py scripts/check_games.py scripts/games-data)

inputs_changed() {
  # An unreadable ref (fresh clone, no cache) counts as changed.
  ! git diff --quiet "${CACHED_COMMIT_REF:-}" "${COMMIT_REF:-HEAD}" -- "${INPUTS[@]}" 2>/dev/null
}

msg=$(git log -1 --format=%B "${COMMIT_REF:-HEAD}" 2>/dev/null || true)

case "$msg" in
  *"[deploy now]"*|"chore(digest): Daily Digest"*)
    if inputs_changed; then
      echo "netlify_ignore: building now (digest or [deploy now])"
      exit 1
    fi
    echo "netlify_ignore: no build inputs changed"
    exit 0
    ;;
esac

echo "netlify_ignore: batched; the next scheduled build (06:00 or 17:00 US Eastern, Mac awake) will publish this"
exit 0
