#!/bin/bash
# usage: run-when-online.sh <command> [args...]
#
# Waits (up to 5 minutes) until DNS and a TCP connection work, then runs the command,
# retrying it when it fails.
#
# launchd fires morning jobs the moment the Mac wakes, often before Wi-Fi and DNS are back.
# stream analytics died on that twice (NameResolutionError, 2026-10-07 and 2026-10-09).
# The wait alone was not enough: on 2026-10-13 the Mac rebooted at 08:29, the job fired at
# 08:30 with the network nominally up, and the run died on "Connection reset by peer".
# So a failed run is now retried: RETRIES more attempts (default 3), RETRY_DELAY seconds
# apart (default 120), each after the same online check. The last attempt's exit code is
# returned, so launchd still sees a real failure when every attempt fails.
#
# Installed as a local copy at ~/.purplelink/run-when-online.sh so it exists when the SSD
# does not; the repo copy in scripts/ is the source. Re-copy after editing.
RETRIES="${RETRIES:-3}"
RETRY_DELAY="${RETRY_DELAY:-120}"

wait_online() {
  for _ in $(seq 1 60); do
    /usr/bin/nc -z -G 3 www.apple.com 443 >/dev/null 2>&1 && return 0
    sleep 5
  done
  return 1
}

attempt=0
while :; do
  wait_online
  "$@"
  rc=$?
  [ "$rc" -eq 0 ] && exit 0
  attempt=$((attempt + 1))
  if [ "$attempt" -gt "$RETRIES" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] run-when-online: giving up after $((RETRIES + 1)) attempts (exit $rc): $*" >&2
    exit "$rc"
  fi
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] run-when-online: attempt $attempt failed (exit $rc), retrying in ${RETRY_DELAY}s: $*" >&2
  sleep "$RETRY_DELAY"
done
