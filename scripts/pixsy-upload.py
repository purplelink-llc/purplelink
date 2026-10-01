#!/usr/bin/env python3
"""Upload the licensed library to Pixsy for image-theft monitoring.

WHY THIS EXISTS
The library is public on seven stock/print sites, so copies get lifted. Pixsy
reverse-searches each uploaded image and, on a submitted case, recovers a fee
for a share of it. Matching only needs a recognisable copy, so it gets the
2048px versions in photo-licensing-workspace/pixsy-upload/ (EXIF kept), not
the originals.

HOW
Pixsy's "Import Images from Computer" page is an Uppy dashboard that takes up
to 1000 files. Playwright over CDP refuses more than ~50MB per
set_input_files, so files go in batches of BATCH (about 35MB each), then the
Uppy "Upload N files" button is clicked and the "Successfully uploaded" toast
is awaited. State is recorded per batch in pixsy-upload-state.json so a rerun
skips what already went up.

  python3 scripts/pixsy-upload.py [--limit N]
"""
import argparse, json, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "photo-licensing-workspace" / "pixsy-upload"
STATE = ROOT / "photo-licensing-workspace" / "pixsy-upload-state.json"
URL = "https://my.pixsy.com/images/import/upload"
CDP = "http://127.0.0.1:9340"
BATCH = 60


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    state = json.loads(STATE.read_text()) if STATE.exists() else {"uploaded": []}
    done = set(state["uploaded"])
    todo = [p for p in sorted(DIR.glob("*.jpg")) if p.name not in done]
    if a.limit:
        todo = todo[:a.limit]
    print(f"{len(done)} already uploaded, {len(todo)} to go")
    with sync_playwright() as p:
        ctx = p.chromium.connect_over_cdp(CDP).contexts[0]
        pg = ctx.new_page(); pg.bring_to_front()
        for i in range(0, len(todo), BATCH):
            chunk = todo[i:i + BATCH]
            pg.goto(URL, wait_until="domcontentloaded"); pg.wait_for_timeout(5000)
            if "not verified" in pg.inner_text("body") and i == 0:
                print("  note: Pixsy email not verified yet -- uploads work, scanning waits")
            pg.locator("input[type=file]").first.set_input_files([str(c) for c in chunk], timeout=180_000)
            pg.wait_for_timeout(3000)
            pg.locator(".uppy-StatusBar-actionBtn--upload").first.click(force=True, timeout=60_000)
            ok = False
            for _ in range(200):          # up to 10 minutes per batch
                pg.wait_for_timeout(3000)
                t = re.sub(r"\s+", " ", pg.inner_text("body"))
                m = re.search(r"Successfully uploaded (\d+) files?", t)
                if m:
                    ok = int(m.group(1)) == len(chunk); break
                if re.search(r"failed|error", t, re.I) and "Upload" not in t[-400:]:
                    break
            if not ok:
                sys.exit(f"  batch at {i} did not confirm; stopping (state saved)")
            state["uploaded"] += [c.name for c in chunk]
            STATE.write_text(json.dumps(state, indent=1))
            print(f"  OK  {len(state['uploaded'])} uploaded")
        pg.close()


if __name__ == "__main__":
    main()
