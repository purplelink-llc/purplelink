#!/bin/zsh
# Renders Panely's real Settings view offscreen into PNGs (2x, transparent where the window has no fill).
# Safe by construction: a fake HOME, no window is shown, no real folders, no keys or mouse events, the app is never launched.
# usage: render.sh <outdir>
set -e
export DEVELOPER_DIR="/Volumes/Extreme SSD/Xcode.app/Contents/Developer"
SRC="${PANELY_SRC:-/Volumes/Extreme SSD/Panely/Sources}"
HERE="${0:A:h}"
OUT="${1:?outdir}"
W="$(mktemp -d /tmp/panely-build.XXXXXX)"
FAKE="$(mktemp -d /tmp/panely-fakehome.XXXXXX)"
mkdir -p "$OUT"
# one module: PanelyCore + the three app files the Settings view needs, with the module import removed
cat "$SRC"/PanelyCore/*.swift "$SRC/PanelyApp/SettingsView.swift" "$SRC/PanelyApp/SettingsStore.swift" "$SRC/PanelyApp/LoginItem.swift" | grep -v '^import PanelyCore' > "$W/App.swift"
# patch the COPY only: height of the form is a variable; a recorder row and a problem row can be shown on request
python3 - "$W/App.swift" <<'P'
import sys
p=sys.argv[1]; s=open(p).read()
s=s.replace(".frame(width: 540, height: 640)\n    }", "\n    }")
s=s.replace("            .onDisappear { stop() }\n", "            .onDisappear { stop() }\n            .onAppear { if ProcessInfo.processInfo.environment[\"PANELY_REC\"] == label { recording = true }; if let r = ProcessInfo.processInfo.environment[\"PANELY_PROBLEM_LABEL\"], r == label { problem = ProcessInfo.processInfo.environment[\"PANELY_PROBLEM\"] } }\n",1)
open(p,"w").write(s)
P
grep -q PANELY_REC "$W/App.swift" || { echo "patch failed"; exit 1; }
cp "$HERE/Harness.swift" "$W/main.swift"
# the harness is main.swift; the app sources are other files in the same module
mv "$W/App.swift" "$W/Panely.swift"
swiftc -O -module-name PanelyShots -swift-version 5 "$W/main.swift" "$W/Panely.swift" -o "$W/shots" 2>&1 | grep -v warning | head -30
run() { CFFIXED_USER_HOME="$FAKE" HOME="$FAKE" PANELY_OUT="$OUT" "$@"; }
for k in $(seq 1 1); do :; done
run env PANELY_MODE=full "$W/shots"
run env PANELY_MODE=recording PANELY_REC="Shortcut for Left third" "$W/shots"
run env PANELY_MODE=problem PANELY_PROBLEM_LABEL="Shortcut for Top half" PANELY_PROBLEM="macOS uses this for Mission Control (Control-Up)." "$W/shots"
rm -rf "$W" "$FAKE"
