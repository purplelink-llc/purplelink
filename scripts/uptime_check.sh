#!/usr/bin/env bash
# Probe the URLs in scripts/uptime-checks.txt. Used by .github/workflows/uptime.yml, safe to run by hand.
#
#   scripts/uptime_check.sh [checks-file]
#
# Every failing check is retried once after RETRY_DELAY seconds (default 60), so a blip does not alert.
# The names of checks that still fail are written one per line to $UPTIME_FAILED_FILE (default
# uptime-failed.txt) and the script exits 1; with nothing failing the file is empty and the exit is 0.
set -u

checks="${1:-$(dirname "$0")/uptime-checks.txt}"
failed_file="${UPTIME_FAILED_FILE:-uptime-failed.txt}"
delay="${RETRY_DELAY:-60}"
timeout="${CHECK_TIMEOUT:-90}"

[ -f "$checks" ] || { echo "no checks file: $checks" >&2; exit 2; }

run_pass() { # prints names of failing checks
  local name method url codes status
  while IFS='|' read -r name method url codes; do
    case "$name" in ''|'#'*) continue ;; esac
    status="$(curl -s -o /dev/null -m "$timeout" -X "$method" -w '%{http_code}' "$url" || true)"
    case ",$codes," in
      *",$status,"*) echo "ok    $name ($status)" >&2 ;;
      *) echo "FAIL  $name (got ${status:-none}, want $codes)" >&2; echo "$name" ;;
    esac
  done < "$checks"
}

first="$(run_pass)"
if [ -n "$first" ]; then
  echo "retrying in ${delay}s: $(echo "$first" | tr '\n' ' ')" >&2
  sleep "$delay"
  second="$(run_pass)"
else
  second=""
fi

printf '%s' "$second" | sed '/^$/d' > "$failed_file"
[ -s "$failed_file" ] && exit 1
exit 0
