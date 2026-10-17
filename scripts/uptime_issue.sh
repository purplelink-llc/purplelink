#!/usr/bin/env bash
# Open, update or close the single "uptime" GitHub issue from the result of scripts/uptime_check.sh.
# Needs GH_TOKEN (the workflow's GITHUB_TOKEN with issues: write) and GITHUB_REPOSITORY.
#
#   scripts/uptime_issue.sh <failed-file>
#
# Failing checks: open one issue labelled "uptime" (GitHub emails the repo owner), or, when one is
# already open, update its body and comment only if the set of failing checks changed (so a long outage
# is one email per change, not one per 15 minutes). Nothing failing: comment and close the open issue.
set -u

failed_file="${1:-uptime-failed.txt}"
label="uptime"
run_url="${GITHUB_SERVER_URL:-https://github.com}/${GITHUB_REPOSITORY:-}/actions/runs/${GITHUB_RUN_ID:-}"

gh label create "$label" --color B60205 --description "Site or backend is down" >/dev/null 2>&1 || true
open_issue="$(gh issue list --label "$label" --state open --limit 1 --json number --jq '.[0].number // empty')"

if [ -s "$failed_file" ]; then
  failing="$(sort "$failed_file" | paste -sd, -)"
  list="$(sort "$failed_file" | sed 's/^/- /')"
  body="$(printf 'These checks failed twice in a row, 60 seconds apart:\n\n%s\n\nLatest run: %s\n\nThe checks are listed in scripts/uptime-checks.txt. This issue closes itself when they pass again.\n\n<!-- failing: %s -->' "$list" "$run_url" "$failing")"
  if [ -z "$open_issue" ]; then
    gh issue create --label "$label" --title "Uptime alert: $failing" --body "$body"
  else
    previous="$(gh issue view "$open_issue" --json body --jq .body | sed -n 's/.*<!-- failing: \(.*\) -->.*/\1/p' | head -1)"
    if [ "$previous" != "$failing" ]; then
      gh issue edit "$open_issue" --title "Uptime alert: $failing" --body "$body"
      gh issue comment "$open_issue" --body "Now failing: $failing. Latest run: $run_url"
    else
      echo "issue #$open_issue already lists the same failures"
    fi
  fi
elif [ -n "$open_issue" ]; then
  gh issue comment "$open_issue" --body "All checks pass again. Closing. Run: $run_url"
  gh issue close "$open_issue"
else
  echo "all checks pass, no open uptime issue"
fi
