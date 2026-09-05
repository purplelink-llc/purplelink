#!/usr/bin/env python3
"""Rebuild Getty upload state from Getty itself.

The journal cannot be trusted as a source of truth. Under a flaky network,
chunks timed out, were recorded as failures, and then landed anyway -- so the
journal under-counted, the next batch recalculated from that undercount, and
re-sent 25 files that were already uploaded. Scraping the page doesn't fix it
either: ESP renders the file grid virtually, so scrolling surfaced only 53 of
59 files in one batch.

ESP's own API returns a batch's complete contents in one call:
    GET /api/submission/v1/submission_batches/<id>/contributions

This reads that for every batch, writes the authoritative state, and reports
duplicates and the true remainder.

USAGE
  scripts/getty-state.py                 # report
  scripts/getty-state.py --write         # also rewrite getty-upload-state.json
"""
import argparse, collections, csv, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WS = ROOT / "photo-licensing-workspace"
SET = WS / "getty-ready-set.csv"
STATE = WS / "getty-upload-state.json"
PLAN = WS / "getty-batch-plan.json"
CDP = "http://127.0.0.1:9225"
API = "https://esp.gettyimages.com/api/submission/v1/submission_batches/{}/contributions"


def batch_contents(pg, bid):
    """Complete filename list for a batch, straight from ESP's API."""
    js = """async (url) => {
        const r = await fetch(url, {credentials:'include',
                                    headers:{'Accept':'application/json'}});
        return await r.text();
    }"""
    body = pg.evaluate(js, API.format(bid))
    names = re.findall(r'"(?:file_?name|original_?file_?name)"\s*:\s*"([^"]+\.jpe?g)"',
                       body, re.I)
    if not names:                      # fall back to any filename-looking token
        names = re.findall(r"((?:DSC|IMG)_[\w\-() ]*\.jpe?g)", body)
    return sorted(set(names))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    plan = json.loads(PLAN.read_text()) if PLAN.exists() else {}
    ids = sorted(set(plan.values()))
    if not ids:
        sys.exit("no batches in getty-batch-plan.json")

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        pg = b.contexts[0].new_page()
        pg.goto("https://esp.gettyimages.com/contribute/batches",
                wait_until="domcontentloaded", timeout=60_000)
        pg.wait_for_timeout(10_000)
        contents = {bid: batch_contents(pg, bid) for bid in ids}
        pg.close()

    rows = list(csv.DictReader(open(SET)))
    want = {use: {r["filename"] for r in rows if r["use"] == use}
            for use in ("commercial", "editorial")}

    print("BATCH CONTENTS (from ESP API)")
    for bid, files in contents.items():
        name = next((k for k, v in plan.items() if v == bid), "?")
        print(f"  {bid}  {len(files):>4} files   {name}")

    everything = [f for files in contents.values() for f in files]
    dupes = {f: [b for b, fl in contents.items() if f in fl]
             for f, n in collections.Counter(everything).items() if n > 1}
    print(f"\nduplicated across batches: {len(dupes)}")
    for f, where in list(dupes.items())[:10]:
        print(f"   {f:<28} {where}")

    uniq = set(everything)
    for use in ("commercial", "editorial"):
        have = uniq & want[use]
        print(f"\n{use}: {len(have)}/{len(want[use])} in Getty, "
              f"{len(want[use]) - len(have)} remaining")
        rem = sorted(want[use] - uniq)
        (WS / f"getty-remaining-{use}.txt").write_text("\n".join(rem))
        print(f"   -> getty-remaining-{use}.txt")

    if a.write:
        STATE.write_text(json.dumps({"uploaded": contents,
                                     "source": "rebuilt from ESP API"}, indent=1))
        print(f"\nrewrote {STATE.name} from Getty's own contents")


if __name__ == "__main__":
    main()
