#!/bin/bash
# Background UI test driver: agent-desktop 1.2.0, headless only.
# Usage: scripts/ui-test/ad.sh <agent-desktop args...>   (see docs/mac-app-ui-testing.md)
set -u
AD_ROOT="${AD_ROOT:-$HOME/.purplelink/agent-desktop}"
BIN="$AD_ROOT/pkg/bin/agent-desktop-darwin-arm64"
export AGENT_DESKTOP_HOME="$AD_ROOT/home"
[ -x "$BIN" ] || { echo "ad.sh: agent-desktop not installed at $BIN (see docs/mac-app-ui-testing.md)" >&2; exit 2; }
mkdir -p "$AGENT_DESKTOP_HOME"; chmod 700 "$AGENT_DESKTOP_HOME"
for a in "$@"; do
  case "$a" in
    --headed|--headed=*) echo "ad.sh: --headed uses the real mouse and keyboard; refused" >&2; exit 3 ;;
  esac
done
# Commands that take focus, move the real cursor or windows, send global keys, quit apps,
# or touch Ben's clipboard and notifications. batch is refused because it can wrap any of them.
case "${1:-}" in
  launch|focus-window|press|key-down|key-up|hover|drag|mouse-*|double-click|triple-click|\
  move-window|resize-window|minimize|maximize|restore|close-app|open-system-surface|\
  clipboard-set|clipboard-clear|*notification*|batch|cursor-overlay)
    echo "ad.sh: '$1' is not allowed in background tests (docs/mac-app-ui-testing.md)" >&2; exit 3 ;;
esac
exec "$BIN" "$@"
