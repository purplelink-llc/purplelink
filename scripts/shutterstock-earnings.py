#!/usr/bin/env python3
"""Parse Shutterstock's "Export (CSV)" earnings file into the daily ledger.

WHY THIS EXISTS
Shutterstock discontinued its contributor API endpoints (/v2/contributor/images
and /v2/contributor/earnings/summary) in favour of the buyer-side content APIs,
and it sends no sales email. The CSV export from the Earnings page is the only
sanctioned, non-scraped route to this data -- and unlike a browser session, a
file on disk does not expire.

Get it from https://submit.shutterstock.com/earnings -> "Export (CSV)" and drop
it in photo-licensing-workspace/exports/. One file per month, named e.g.
2026_8_earnings_by_month.csv.

FILE SHAPE (verified against a real export, 2026-08-18)
    <BOM>,,,Images,Images,Images,Images,Videos,...      <- category grouping row
    Date,Total downloads,Total earnings,Subscriptions,On demand,Enhanced,...
    08/10/2026,1,0.1,,,,0.1,,,,,,
    ...
    Monthly totals,2,0.2,,,,0.2,,,,,,

Three things that bite:
  - a UTF-8 BOM sits before the first field name
  - there are TWO header rows; the first is a merged category banner, not data
  - the final row is "Monthly totals", not a date, and would parse as a day
    with a nonsense date if fed to strptime
Empty cells mean "no downloads that day", not zero-dollar sales, so blank rows
are skipped rather than written as $0.00 readings.
"""
import argparse, csv, datetime, glob, io, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WS = ROOT / "photo-licensing-workspace"
EXPORTS = WS / "exports"
LEDGER = WS / "analytics" / "shutterstock-earnings.csv"
SNAPSHOTS = WS / "analytics" / "snapshots.csv"
FIELDS = ["date", "downloads", "earnings", "subscriptions", "on_demand",
          "enhanced", "single_and_other"]


def parse_file(path):
    text = Path(path).read_text(encoding="utf-8-sig")     # strips the BOM
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) < 3:
        return [], None
    header = [h.strip().lower() for h in rows[1]]         # row 0 is the banner
    def col(name):
        try:
            return header.index(name)
        except ValueError:
            return None
    ix = {k: col(v) for k, v in (
        ("downloads", "total downloads"), ("earnings", "total earnings"),
        ("subscriptions", "subscriptions"), ("on_demand", "on demand"),
        ("enhanced", "enhanced"), ("single_and_other", "single & other"))}

    def val(row, key):
        i = ix.get(key)
        if i is None or i >= len(row):
            return None
        v = (row[i] or "").strip()
        return float(v) if v else None

    out, total = [], None
    for row in rows[2:]:
        if not row or not row[0].strip():
            continue
        label = row[0].strip()
        if label.lower().startswith("monthly total"):
            total = {"downloads": val(row, "downloads"), "earnings": val(row, "earnings")}
            continue
        try:
            d = datetime.datetime.strptime(label, "%m/%d/%Y").date()
        except ValueError:
            continue
        # A blank row is a day with no downloads, not a $0 sale. Skipping keeps
        # the ledger to real events instead of one row per calendar day.
        if val(row, "downloads") is None and val(row, "earnings") is None:
            continue
        rec = {"date": d.isoformat()}
        for k in FIELDS[1:]:
            rec[k] = val(row, k)
        out.append(rec)
    return out, total


def write_snapshot(total):
    if not total or total.get("earnings") is None:
        return
    today = datetime.date.today().isoformat()
    rows = []
    if SNAPSHOTS.exists():
        rows = [r for r in csv.DictReader(open(SNAPSHOTS))
                if not (r["snapshot_date"] == today and r["platform"] == "shutterstock"
                        and r["metric"] in ("balance", "downloads"))]
    for metric, v in (("balance", total["earnings"]), ("downloads", total["downloads"])):
        if v is not None:
            rows.append({"snapshot_date": today, "platform": "shutterstock",
                         "metric": metric, "value": v, "note": "from CSV export"})
    rows.sort(key=lambda r: (r["snapshot_date"], r["platform"], r["metric"]))
    with open(SNAPSHOTS, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["snapshot_date", "platform", "metric", "value", "note"])
        w.writeheader(); w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(EXPORTS))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    files = sorted(glob.glob(str(Path(a.dir) / "*earnings*.csv")))
    if not files:
        sys.exit(f"no export found in {a.dir}\n"
                 "Get one: submit.shutterstock.com/earnings -> Export (CSV)")

    all_rows, latest_total = [], None
    for f in files:
        rows, total = parse_file(f)
        tot = ""
        if total and total.get("earnings") is not None:
            tot = "  monthly total ${:.2f}".format(total["earnings"])
        print(f"  {Path(f).name}: {len(rows)} day(s) with activity{tot}")
        all_rows.extend(rows)
        if total:
            latest_total = total
    all_rows.sort(key=lambda r: r["date"])

    print(f"\n{len(all_rows)} earning day(s):")
    for r in all_rows:
        kinds = [k for k in FIELDS[3:] if r.get(k)]
        print(f"  {r['date']}  {int(r['downloads'] or 0)} download(s)  "
              f"${r['earnings'] or 0:.2f}  [{', '.join(kinds) or 'unspecified'}]")

    if a.dry_run:
        print("\n--dry-run: nothing written")
        return
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader(); w.writerows(all_rows)
    write_snapshot(latest_total)
    print(f"\nwrote {LEDGER.name} and updated {SNAPSHOTS.name}")


if __name__ == "__main__":
    main()
