#!/usr/bin/env python3
"""Submit Getty ESP batches for review.

The ESP submit flow is three steps, not one:
  1. Select all -> click SUBMIT
  2. If any file fails validation, an alert appears ("Some files can't be
     submitted... some files will be excluded") -- dismiss with GOT IT.
     This does NOT submit; it only acknowledges.
  3. Click SUBMIT again -> confirm with "YES, SUBMIT".

Files that fail validation stay behind in the batch, which is how you find out
which ones need work: whatever is still selectable afterwards is the problem set.

USAGE
  scripts/getty-submit.py --batch 66154962
  scripts/getty-submit.py --all           # every batch in getty-batch-plan.json
"""
import argparse, json, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WS = ROOT / "photo-licensing-workspace"
PLAN = WS / "getty-batch-plan.json"
CDP = "http://127.0.0.1:9225"


def submit_batch(b, bid):
    pg = b.contexts[0].new_page()
    try:
        pg.goto(f"https://esp.gettyimages.com/contribute/batches/{bid}",
                wait_until="domcontentloaded", timeout=60_000)
        pg.wait_for_timeout(16_000)
        if "sign-in" in pg.url:
            return {"batch": bid, "error": "not signed in to ESP"}

        total = re.search(r"(\d[\d,]*)\s+files?", pg.inner_text("body"))
        total = int(total.group(1).replace(",", "")) if total else -1

        pg.get_by_text("Select all", exact=True).first.click()
        pg.wait_for_timeout(7_000)
        ready = re.search(r"SUBMIT\s*\n?\s*(\d+)", pg.inner_text("body"))
        ready = int(ready.group(1)) if ready else -1
        if ready == 0:
            return {"batch": bid, "total": total, "submitted": 0,
                    "note": "nothing passed validation"}

        pg.get_by_text("SUBMIT", exact=True).first.click()
        pg.wait_for_timeout(6_000)

        # step 2: the "some files will be excluded" acknowledgement
        dlg = pg.locator("[data-cy=alert-dialog]")
        if dlg.count() and "GOT IT" in dlg.first.inner_text().upper():
            dlg.locator("button").first.click()
            pg.wait_for_timeout(5_000)
            pg.get_by_text("SUBMIT", exact=True).first.click()
            pg.wait_for_timeout(6_000)

        # step 3: the real confirmation
        yes = pg.get_by_text("YES, SUBMIT", exact=True)
        if not yes.count():
            return {"batch": bid, "total": total, "ready": ready,
                    "error": "confirmation dialog never appeared"}
        yes.first.click()
        pg.wait_for_timeout(30_000)

        left = re.search(r"SUBMIT\s*\n?\s*(\d+)", pg.inner_text("body"))
        return {"batch": bid, "total": total, "submitted": ready,
                "excluded": max(total - ready, 0),
                "still_pending": int(left.group(1)) if left else None}
    finally:
        try:
            pg.close()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()

    plan = json.loads(PLAN.read_text()) if PLAN.exists() else {}
    ids = [a.batch] if a.batch else (sorted(set(plan.values())) if a.all else [])
    if not ids:
        sys.exit("pass --batch <id> or --all")

    from playwright.sync_api import sync_playwright
    results = []
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        for bid in ids:
            name = next((k for k, v in plan.items() if v == bid), bid)
            print(f"\n=== {name} ({bid}) ===")
            r = submit_batch(b, bid)
            results.append(r)
            print("   ", r)
            time.sleep(4)

    (WS / "getty-submit-results.json").write_text(json.dumps(results, indent=2))
    done = sum(r.get("submitted", 0) or 0 for r in results)
    print(f"\nTOTAL SUBMITTED: {done}")
    print("wrote getty-submit-results.json")


if __name__ == "__main__":
    main()
