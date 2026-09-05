#!/usr/bin/env python3
"""Create every Getty batch needed and fill them.

509 country-tagged images / 100 per batch = 6 batches, and ESP has no bulk batch
creation. This walks the whole job: create a batch, fill it to the cap, create
the next, repeat -- for commercial ("iStock creative image") first, then
editorial ("iStock editorial image").

Everything is journalled to getty-upload-state.json against the batch's OWN file
count, never the loop counter, because ESP stops accepting at 100 files silently
and an optimistic journal once recorded 265 successes for 100 real uploads.

USAGE
  scripts/getty-run-all.py              # do the whole job
  scripts/getty-run-all.py --plan       # show what it would do
"""
import argparse, csv, json, re, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WS = ROOT / "photo-licensing-workspace"
SRC = Path("/Volumes/Extreme SSD/Nikon Photos")
SET = WS / "getty-ready-set.csv"
STATE = WS / "getty-upload-state.json"
PLAN = WS / "getty-batch-plan.json"
CDP = "http://127.0.0.1:9225"
CAP = 100
PY = sys.executable


def state():
    return json.loads(STATE.read_text()) if STATE.exists() else {"uploaded": {}}


def groups():
    rows = list(csv.DictReader(open(SET)))
    out = {}
    for use in ("commercial", "editorial"):
        files = [r["filename"] for r in rows if r["use"] == use]
        out[use] = [files[i:i + CAP] for i in range(0, len(files), CAP)]
    return out


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    for line in (p.stdout or "").splitlines():
        if "Deprecation" not in line and "trace-deprecation" not in line and line.strip():
            print("   ", line)
    return p.returncode == 0, (p.stdout or "") + (p.stderr or "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true")
    a = ap.parse_args()

    g = groups()
    plan = json.loads(PLAN.read_text()) if PLAN.exists() else {}

    print("PLAN")
    for use, chunks in g.items():
        for i, c in enumerate(chunks, 1):
            key = f"{use}-{i}"
            print(f"  {key:<14} {len(c):>3} files   batch={plan.get(key, '(to create)')}")
    if a.plan:
        return

    for use, chunks in g.items():
        kind = "creative" if use == "commercial" else "editorial"
        for i, chunk in enumerate(chunks, 1):
            key = f"{use}-{i}"
            bid = plan.get(key)

            if not bid:
                print(f"\n=== {key}: creating batch ({kind}) ===")
                ok, out = run([PY, str(ROOT / "scripts" / "getty-batch.py"),
                               "--create", f"purplelink {use} {i}", "--type", kind])
                m = re.search(r"created batch (\d+)", out)
                if not m:
                    # One transient failure (a dead ESP tab) shouldn't abandon
                    # the remaining batches -- retry once before giving up.
                    print(f"    batch creation failed for {key}; retrying once")
                    time.sleep(20)
                    ok, out = run([PY, str(ROOT / "scripts" / "getty-batch.py"),
                                   "--create", f"purplelink {use} {i}", "--type", kind])
                    m = re.search(r"created batch (\d+)", out)
                if not m:
                    print(f"    could not create batch for {key}; stopping")
                    return
                bid = m.group(1)
                plan[key] = bid
                PLAN.write_text(json.dumps(plan, indent=2))

            st = state()
            already = len(st["uploaded"].get(bid, []))
            if already >= len(chunk):
                print(f"\n=== {key}: batch {bid} already holds {already}/{len(chunk)} — skipping ===")
                continue

            print(f"\n=== {key}: filling batch {bid} ({len(chunk)} files) ===")
            run([PY, "-u", str(ROOT / "scripts" / "getty-upload.py"),
                 "--batch", bid, "--use", use])

    print("\nALL BATCHES PROCESSED")
    for use, chunks in g.items():
        for i, c in enumerate(chunks, 1):
            key = f"{use}-{i}"
            bid = plan.get(key, "?")
            got = len(state()["uploaded"].get(bid, []))
            print(f"  {key:<14} batch {bid:<10} {got}/{len(c)} uploaded")


if __name__ == "__main__":
    main()
