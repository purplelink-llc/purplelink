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

# Server code: what a checkout, delivery or security fix changes. Page text and version strings are not urgent.
CODE=(netlify netlify.toml package.json package-lock.json)
code_changed() {
  ! git diff --quiet "${CACHED_COMMIT_REF:-}" "${COMMIT_REF:-HEAD}" -- "${CODE[@]}" 2>/dev/null
}

case "$msg" in
  # The Daily Digest was retired on 2026-10-17 and no longer commits; this exception is harmless and kept.
  "chore(digest): Daily Digest"*)
    if inputs_changed; then
      echo "netlify_ignore: building now (digest)"
      exit 1
    fi
    echo "netlify_ignore: no build inputs changed"
    exit 0
    ;;
  *"[deploy now]"*)
    # Honoured only for server-code changes (2026-10-17: 10 of 12 [deploy now] builds in two days were page text,
    # mostly app version strings, which can wait for the slot). Urgent page text: netlify-batch-build.sh manual.
    if code_changed; then
      echo "netlify_ignore: building now ([deploy now] with server-code changes)"
      exit 1
    fi
    echo "netlify_ignore: [deploy now] on a page-text change waits for the next scheduled build"
    exit 0
    ;;
esac

echo "netlify_ignore: batched; the next scheduled build (06:00 or 17:00 US Eastern, Mac awake) will publish this"
exit 0
