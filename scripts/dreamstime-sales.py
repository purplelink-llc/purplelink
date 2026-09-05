#!/usr/bin/env python3
"""Parse Dreamstime's per-sale earnings list into a ledger.

WHY THIS EXISTS
Everything else reports a running total. `sales 2` and `balance 0.70` tell you
money moved but not WHICH photograph earned it, and that is the only question
whose answer changes what you shoot next. This keeps one row per sale, joined
back to the original Nikon filename.

WHY NOT THE API
There isn't one for contributors. Dreamstime's API products (Partner/Search,
Business, Enterprise, Reseller, Affiliate) are all buyer-side -- they let you
embed Dreamstime's collection in YOUR product. Nothing exposes your own sales.

WHY NOT EMAIL
Dreamstime does not email for subscription-tier sales. Its newsletter settings
have seven toggles and none concerns sales; the page states sales notices are
transactional. There is no wording to write a mail parser against.

SOURCE FORMAT (verified against the live page 2026-08-16, not guessed)
    div.account-list
      div.account-list__date                 "August 14, 2026"
      div.account-list__item
        div.account-list__text
          a.account-list__title  href=".../...-image469681257"
          p  <strong>$0.35</strong> · 25% royalty · subscription · maximum
Dates are siblings that PRECEDE the items they label, so parsing walks the
document in order and carries the last date seen.

TWO WAYS IN
  --html FILE   parse a saved page. Use this when the press-and-hold check is
                up, which it intermittently is for the automation profile.
  (default)     attach to the CDP Chrome and read the page live.

NO SILENT TRUNCATION
The page prints "Showing 1 - N of M". If N < M there are sales this run cannot
see, and that is reported as a warning rather than written out as a complete
ledger -- a short ledger that looks whole is worse than a loud gap.
"""
import argparse, csv, datetime, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WS = ROOT / "photo-licensing-workspace"
AN = WS / "analytics"
LEDGER = AN / "dreamstime-sales.csv"
SNAPSHOTS = AN / "snapshots.csv"
TITLES = WS / "alamy-metadata.csv"   # Filename,Caption,...,Title
URL = "https://www.dreamstime.com/account/earnings-images"
CDP = "http://127.0.0.1:9225"

FIELDS = ["sale_date", "filename", "image_id", "title", "amount",
          "royalty_pct", "license", "tier", "url"]

# One pass over the document. Branch 1 is a date header, branch 2 a sale row.
TOKEN = re.compile(
    r'<div class="account-list__date">\s*([^<]+?)\s*</div>'
    r'|<a\s+href="([^"]*?image(\d+))"[^>]*class="account-list__title"\s*>\s*'
    r'(.*?)\s*</a>\s*<p>\s*<strong>\s*\$?([\d.,]+)\s*</strong>(.*?)</p>',
    re.S | re.I)

SHOWING = re.compile(r"Showing\s+\d+\s*-\s*(\d+)\s+of\s+(\d+)", re.I)


def detag(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


def title_map():
    """Dreamstime's listing title is the Title we uploaded, so it joins exactly.
    Returns {title: filename}; empty if the metadata CSV is missing."""
    if not TITLES.exists():
        return {}
    out = {}
    for r in csv.DictReader(open(TITLES)):
        t = (r.get("Title") or "").strip()
        if t:
            out[t.casefold()] = r["Filename"]
    return out


def parse(html):
    """[] of sale dicts, in page order."""
    names = title_map()
    sales, cur = [], None
    for m in TOKEN.finditer(html):
        if m.group(1):
            raw = m.group(1).strip()
            try:
                cur = datetime.datetime.strptime(raw, "%B %d, %Y").date().isoformat()
            except ValueError:
                cur = raw            # keep it visible rather than dropping the row
            continue
        url, image_id, title, amount, tail = (m.group(2), m.group(3),
                                              detag(m.group(4)), m.group(5),
                                              m.group(6))
        # tail is "· 25% royalty · subscription · maximum" separated by spans
        parts = [p.strip() for p in re.sub(r"<[^>]+>", "|", tail).split("|") if p.strip()]
        roy = next((p for p in parts if "%" in p), "")
        rest = [p for p in parts if "%" not in p]
        sales.append({
            "sale_date": cur or "",
            "filename": names.get(title.casefold(), ""),
            "image_id": image_id,
            "title": title,
            "amount": float(amount.replace(",", "")),
            "royalty_pct": (re.search(r"([\d.]+)\s*%", roy).group(1) if roy else ""),
            "license": rest[0] if rest else "",
            "tier": rest[1] if len(rest) > 1 else "",
            "url": url,
        })
    return sales


def live_html():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        pg = b.contexts[0].new_page()
        try:
            pg.goto(URL, wait_until="domcontentloaded", timeout=60000)
            pg.wait_for_timeout(7000)
            body = pg.inner_text("body")
            if re.search(r"Press & Hold|confirm you are a human", body, re.I):
                raise SystemExit(
                    "Dreamstime is serving its press-and-hold check to this profile.\n"
                    "Open the page in your normal browser, save it, and re-run with\n"
                    f"  scripts/dreamstime-sales.py --html <saved.html>")
            if re.search(r"\bSign in\b", body[:500], re.I):
                raise SystemExit("not signed in — run stats-collect.py --login")
            return pg.content()
        finally:
            pg.close()


def write_snapshot(sales):
    """Roll the ledger up into the same tidy CSV everything else writes."""
    today = datetime.date.today().isoformat()
    rows = []
    if SNAPSHOTS.exists():
        rows = [r for r in csv.DictReader(open(SNAPSHOTS))
                if not (r["snapshot_date"] == today and r["platform"] == "dreamstime"
                        and r["metric"] in ("sales", "balance"))]
    rows.append({"snapshot_date": today, "platform": "dreamstime", "metric": "sales",
                 "value": len(sales), "note": "from earnings ledger"})
    rows.append({"snapshot_date": today, "platform": "dreamstime", "metric": "balance",
                 "value": round(sum(s["amount"] for s in sales), 2),
                 "note": "from earnings ledger"})
    rows.sort(key=lambda r: (r["snapshot_date"], r["platform"], r["metric"]))
    with open(SNAPSHOTS, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["snapshot_date", "platform", "metric", "value", "note"])
        w.writeheader(); w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", help="saved earnings page instead of the live site")
    ap.add_argument("--dry-run", action="store_true", help="print, write nothing")
    a = ap.parse_args()

    html = Path(a.html).read_text(errors="ignore") if a.html else live_html()
    sales = parse(html)
    if not sales:
        sys.exit("no sales rows found — the page layout may have changed")

    m = SHOWING.search(detag(html))
    if m and int(m.group(1)) < int(m.group(2)):
        print(f"WARNING: page shows {m.group(1)} of {m.group(2)} sales. "
              f"This ledger is INCOMPLETE — paginate before trusting totals.")

    total = sum(s["amount"] for s in sales)
    print(f"{len(sales)} sale(s), ${total:.2f}\n")
    for s in sales:
        who = s["filename"] or "?unmatched?"
        print(f"  {s['sale_date']}  {who:16s} ${s['amount']:.2f}  "
              f"{s['royalty_pct']}%  {s['license']}/{s['tier']}")
        print(f"                    {s['title'][:70]}")
    missing = [s for s in sales if not s["filename"]]
    if missing:
        print(f"\n{len(missing)} sale(s) did not match a local filename "
              f"(title changed on the platform, or not in {TITLES.name})")

    if a.dry_run:
        print("\n--dry-run: nothing written")
        return

    AN.mkdir(parents=True, exist_ok=True)
    # The page is a full history, so the ledger is rewritten rather than
    # appended -- no dedupe key can distinguish two genuine same-day sales of
    # the same image at the same price.
    with open(LEDGER, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader(); w.writerows(sales)
    write_snapshot(sales)
    print(f"\nwrote {LEDGER.name} and updated {SNAPSHOTS.name}")


if __name__ == "__main__":
    main()
