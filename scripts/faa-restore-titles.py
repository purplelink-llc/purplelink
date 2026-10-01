#!/usr/bin/env python3
"""Restore full, searchable titles on live Fine Art America listings.

WHY: faa-upload.py let FAA pull each title from the image's embedded IPTC
ObjectName, a field capped at 64 bytes that also drops non-ASCII letters.
So 60-odd listings went live cut mid-phrase ("...with Danish flag and
industrial") or garbled ("Skgafoss", "Jkulsrln"), and editorial datelines
led with a date nobody searches ("Tokyo, Japan - June 2025 - ..."). FAA
itself accepts 100 characters (the edit form's maxlength), so the fix is
the full title from metadata-master.csv: dateline moved to a trailing place
name, accents folded to plain letters (how buyers type them), no colons
(FAA rejects them). Found 2026-09-23.

Reads photo-licensing-workspace/faa-title-plan.json ({"plan": [{id, live,
new}]}); every save is re-read from the edit form before it counts. Each
rename is appended to faa-title-renames.json (old -> new), because
faa-update-metadata.py matches listings to faa-metadata-v2.csv by title.

  scripts/faa-restore-titles.py --limit 3
  scripts/faa-restore-titles.py
"""
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WS = ROOT / "photo-licensing-workspace"
PLAN = WS / "faa-title-plan.json"
RENAMES = WS / "faa-title-renames.json"
CDP = "http://127.0.0.1:9340"
EDIT = "https://fineartamerica.com/controlpanel/updateartwork.html?artworkid={}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    plan = json.loads(PLAN.read_text())["plan"]
    done = json.loads(RENAMES.read_text()) if RENAMES.exists() else {}
    todo = [r for r in plan if r["id"] not in done]
    if a.limit:
        todo = todo[: a.limit]
    print(f"{len(todo)} title(s) to restore\n", flush=True)

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        pg = p.chromium.connect_over_cdp(CDP).contexts[0].new_page()
        pg.bring_to_front()
        ok = fails = 0
        for i, r in enumerate(todo, 1):
            pg.goto(EDIT.format(r["id"]), wait_until="networkidle", timeout=60_000)
            pg.wait_for_timeout(1500)
            if "login" in pg.url.lower():
                sys.exit("FAA session signed out -- sign in, then re-run (finished renames are kept)")
            field = pg.locator('input[name="artworkname"]').first
            if not field.count():
                print(f"  FAIL [{i}] {r['id']} -- no edit form"); fails += 1
                continue
            field.fill(r["new"])
            pg.get_by_role("link", name="Submit").first.click()
            pg.wait_for_timeout(4000)
            pg.goto(EDIT.format(r["id"]), wait_until="networkidle", timeout=60_000)
            pg.wait_for_timeout(1500)
            got = pg.locator('input[name="artworkname"]').first.input_value()
            if got.strip() == r["new"]:
                done[r["id"]] = {"old": r["live"], "new": r["new"]}
                RENAMES.write_text(json.dumps(done, indent=1))
                ok += 1
                print(f"  OK   [{i}/{len(todo)}] {r['new']}", flush=True)
            else:
                fails += 1
                print(f"  FAIL [{i}/{len(todo)}] {r['id']} saved as {got!r}", flush=True)
                if fails >= 5 and ok == 0:
                    sys.exit("5 failures with no success -- check the browser")
        print(f"\ndone: {ok} restored, {fails} failed")
        pg.close()


if __name__ == "__main__":
    main()
