#!/usr/bin/env bash
# Upload the FAA retry queue in small batches.
#
# FAA expires its session fast -- one dropped between a 3-image test and the
# full run minutes later. A single long run therefore risks losing the whole
# queue to one logout. Batches of 40 mean a logout costs one batch, and every
# image that lands is verified against the account before being journalled.
#
# Between batches this re-checks the session and STOPS if it's gone, rather
# than firing the remaining batches into a logged-out page.
set -u
cd "$(dirname "$0")/.."

QUEUE="photo-licensing-workspace/faa-retry-queue.csv"
DIR="/Volumes/Extreme SSD/Nikon Photos"
LOG="photo-licensing-workspace/faa-retry.log"
BATCH="${1:-40}"
MAX_BATCHES="${2:-6}"

signed_in() {
  python3 - <<'PY' 2>/dev/null
from playwright.sync_api import sync_playwright
try:
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        pg = b.contexts[0].new_page()
        pg.goto("https://fineartamerica.com/profiles/benjamin-ampel.html",
                wait_until="domcontentloaded", timeout=40000)
        pg.wait_for_timeout(8000)
        ok = pg.locator('a:has-text("Upload Image")').count() > 0
        pg.close()
        raise SystemExit(0 if ok else 1)
except SystemExit:
    raise
except Exception:
    raise SystemExit(1)
PY
}

: > "$LOG"
for i in $(seq 1 "$MAX_BATCHES"); do
  if ! signed_in; then
    echo "=== BATCH $i: FAA session is gone — stopping. Sign in and re-run. ===" | tee -a "$LOG"
    break
  fi
  echo "=== BATCH $i (limit $BATCH) ===" | tee -a "$LOG"
  python3 -u scripts/faa-upload.py --queue "$QUEUE" --dir "$DIR" --limit "$BATCH" 2>&1 \
    | grep -vE "Deprecation|trace-dep" | tee -a "$LOG" | grep -E "OK |FAIL |STOPPING|done:"
  remaining=$(python3 -c "import json;d=json.load(open('photo-licensing-workspace/faa-upload-state.json'));print(len(d['failed']))")
  echo "    remaining after batch $i: $remaining" | tee -a "$LOG"
  [ "$remaining" -eq 0 ] && break
  sleep 20
done
echo "=== BATCHED RUN FINISHED ===" | tee -a "$LOG"
