#!/usr/bin/env python3
"""Record one month of photo royalties for a platform that is not read daily, entered by hand from its statement.

Two platforms are entered this way instead of by the daily sweep, because their sign-ins expire within days and they
only pay once a month:

  getty     left the sweep 2026-10-18. Getty posts the monthly royalty statement around the 20th, for the month
            before. Read the total at https://accountmanagement.gettyimages.com/Reports/Statement.
  vecteezy  left the sweep 2026-10-20. Vecteezy confirms a month's earnings after month end and pays about the
            15th. Read the confirmed amount for the month under Payments at https://contributors.vecteezy.com/earnings.

    python3 scripts/record-photo-month.py getty 2026-10 3.45            # October's total, in dollars
    python3 scripts/record-photo-month.py vecteezy 2026-10 0 --dry-run  # show the rows, write nothing

The platform's money lives in snapshots.csv as one cumulative "balance" (lifetime royalties), the figure the photo
dashboard, the platform totals and monthly revenue already read. This adds the month's total to the last balance and
appends two rows dated today: the new balance, and a statement_month_total row naming the month, which is how a month
that was already entered is refused. A month with no sales is entered as 0, so the record shows it was checked.

Vecteezy's balance rows before 2026-10-20 were the sweep's "Total Unpaid Earnings" reading, which was $0.00 on every
day it read, so the lifetime balance starts from 0 without a gap.
Record one month of photo royalties for a platform that is not read daily, entered by hand from its statement.

Two platforms are entered this way instead of by the daily sweep, because their sign-ins expire within days and they
only pay once a month:

  getty     left the sweep 2026-10-18. Getty posts the monthly royalty statement around the 20th, for the month
            before. Read the total at https://accountmanagement.gettyimages.com/Reports/Statement.
  vecteezy  left the sweep 2026-10-20. Vecteezy confirms a month's earnings after month end and pays about the
            15th. Read the confirmed amount for the month under Payments at https://contributors.vecteezy.com/earnings.

    python3 scripts/record-photo-month.py getty 2026-10 3.45            # October's total, in dollars
    python3 scripts/record-photo-month.py vecteezy 2026-10 0 --dry-run  # show the rows, write nothing

The platform's money lives in snapshots.csv as one cumulative "balance" (lifetime royalties), the figure the photo
dashboard, the platform totals and monthly revenue already read. This adds the month's total to the last balance and
appends two rows dated today: the new balance, and a statement_month_total row naming the month, which is how a month
that was already entered is refused. A month with no sales is entered as 0, so the record shows it was checked.

Vecteezy's balance rows before 2026-10-20 were the sweep's "Total Unpaid Earnings" reading, which was $0.00 on every
day it read, so the lifetime balance starts from 0 without a gap.
"""
import argparse, csv, datetime, re, sys
from pathlib import Path

PLATFORMS = ("getty", "vecteezy")
SNAPSHOTS = Path(__file__).resolve().parent.parent / "photo-licensing-workspace" / "analytics" / "snapshots.csv"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("platform", choices=PLATFORMS, help="platform the statement is for")
    ap.add_argument("month", help="statement month, YYYY-MM")
    ap.add_argument("amount", help="total royalties for that month in US dollars, e.g. 3.45")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--snapshots", type=Path, default=SNAPSHOTS)
    a = ap.parse_args(argv)

    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", a.month):
        print(f"month must be YYYY-MM, got {a.month!r}", file=sys.stderr)
        return 2
    try:
        amount = round(float(a.amount.replace("$", "").replace(",", "")), 2)
    except ValueError:
        print(f"amount must be a number of dollars, got {a.amount!r}", file=sys.stderr)
        return 2
    if amount < 0:
        print("amount cannot be negative", file=sys.stderr)
        return 2
    if not a.snapshots.exists():
        print(f"no snapshots file at {a.snapshots}", file=sys.stderr)
        return 1

    rows = list(csv.DictReader(open(a.snapshots, newline="", encoding="utf-8")))
    plat = [r for r in rows if r["platform"] == a.platform]
    if any(r["metric"] == "statement_month_total" and r["note"] == a.month for r in plat):
        print(f"{a.platform} {a.month} is already recorded; nothing written. Fix a wrong entry by editing {a.snapshots.name}.",
              file=sys.stderr)
        return 1
    balances = [r for r in plat if r["metric"] == "balance"]
    last = float(balances[-1]["value"]) if balances else 0.0
    new = round(last + amount, 2)

    today = datetime.date.today().isoformat()
    add = [{"snapshot_date": today, "platform": a.platform, "metric": "balance", "value": f"{new:.2f}",
            "note": f"{a.month} statement +{amount:.2f}, entered by hand"},
           {"snapshot_date": today, "platform": a.platform, "metric": "statement_month_total", "value": f"{amount:.2f}",
            "note": a.month}]
    for r in add:
        print(",".join(r.values()))
    if a.dry_run:
        print("dry run: nothing written")
        return 0
    with open(a.snapshots, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=["snapshot_date", "platform", "metric", "value", "note"]).writerows(add)
    print(f"{a.platform} {a.month}: ${amount:.2f} recorded. Lifetime {a.platform} royalties now ${new:.2f} (was ${last:.2f}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
