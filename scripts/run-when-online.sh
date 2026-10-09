#!/bin/bash
# usage: run-when-online.sh <command> [args...]
#
# Waits (up to 5 minutes) until DNS and a TCP connection work, then runs the command.
# launchd fires morning jobs the moment the Mac wakes, often before Wi-Fi and DNS are back.
# stream analytics died on that twice (NameResolutionError, 2026-10-07 and 2026-10-09).
# Installed as a local copy at ~/.purplelink/run-when-online.sh so it exists when the SSD does not.
for _ in $(seq 1 60); do
  /usr/bin/nc -z -G 3 www.apple.com 443 >/dev/null 2>&1 && break
  sleep 5
done
exec "$@"
