#!/usr/bin/env python3
"""Per-sale ledgers for Adobe Stock, Shutterstock and Getty/iStock.

Every other collector reports a running total, which says money moved but not
WHICH photograph earned it. These three platforms each expose a signed-in JSON
or export endpoint that does say, so this reads them with in-page fetch() from
the automation Chrome (port 9340). No render waits; a few seconds per platform.

  adobe-sales.csv         one row per asset per day (date, asset_id, filename,
                          title, amount). Adobe has no per-sale list, but its
                          top-sellers endpoint takes a date range, so asking
                          for a single day that earned money yields that day's
                          assets and what each earned.
  shutterstock-days.csv   one row per day with downloads (aggregate endpoint)
  shutterstock-images.csv one row per image: lifetime downloads and earnings
                          (media_summary endpoint; Shutterstock does not
                          expose which image sold on which day)
  getty-sales.csv         one row per transaction from the monthly royalty
                          export (exportFormat=tsv on Reports/Export). Getty
                          posts a statement around the 20th for the prior
                          month, so rows arrive monthly, not daily.

Sources verified 2026-09-30. Each ledger is rewritten from the source on every
run (the sources are full histories), and a platform that fails to read is
reported and left untouched rather than blanked.
"""
import csv, datetime, json, sys, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_tab import Tab

AN = Path(__file__).resolve().parent.parent / "photo-licensing-workspace" / "analytics"
CDP = "http://127.0.0.1:9340"
XHR = "{credentials:'include',headers:{'X-Requested-With':'XMLHttpRequest','Accept':'application/json'}}"


def fetch_json(t, url, opts=XHR):
    return t.eval(f"fetch({url!r},{opts}).then(r=>r.json())")


def write(name, fields, rows):
    AN.mkdir(parents=True, exist_ok=True)
    with open(AN / name, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def adobe(t):
    t.goto("https://contributor.stock.adobe.com/en/insights", settle=6)
    if "auth" in t.url() or "signin" in t.url().lower():
        raise RuntimeError("Adobe: not signed in")
    today = datetime.date.today().isoformat()
    q = lambda ep, a, b: (f"/en/insights/{ep}?start_date={a}&end_date={b}&time_range=day")
    days = fetch_json(t, q("earnings", "2020-01-01", today))["insights"]["statistics"]["data"]
    rows = []
    for d in days:
        if not d["amount"]:
            continue
        top = fetch_json(t, q("top-sellers", d["date"], d["date"]))["sales"]["topSellers"]
        for a in top:
            rows.append({"sale_date": d["date"], "asset_id": a["id"],
                         "filename": a.get("originalName", ""), "title": a.get("title", ""),
                         "amount": round(a["commissionAmount"], 4)})
        got = round(sum(r["amount"] for r in rows if r["sale_date"] == d["date"]), 2)
        if abs(got - d["amount"]) > 0.02:
            print(f"  WARN adobe {d['date']}: assets sum ${got} vs day ${d['amount']:.2f}")
    return write("adobe-sales.csv", ["sale_date", "asset_id", "filename", "title", "amount"], rows)


def shutterstock(t):
    t.goto("https://submit.shutterstock.com/earnings", settle=8)
    if "sign" in t.url().lower() and "earnings" not in t.url():
        raise RuntimeError("Shutterstock: not signed in")
    opts = "{credentials:'include'}"
    days = []
    today = datetime.date.today()
    y, m = 2026, 8                      # account opened Aug 2026; walk months to today
    while (y, m) <= (today.year, today.month):
        r = fetch_json(t, f"/api/next/v2/earnings/aggregate?aggregation_period=day&year={y}&month={m}", opts)
        for d in r.get("days", []):
            days.append({"date": d["date"], "downloads": d["downloads"], "earnings": round(d["earnings"], 4)})
        m += 1
        if m > 12:
            y, m = y + 1, 1
    n_days = write("shutterstock-days.csv", ["date", "downloads", "earnings"], days)
    imgs, page = [], 1
    while True:
        r = fetch_json(t, "/api/next/v2/earnings/media_summary?media_type=photo&display_column="
                          f"single_image_and_other&page={page}&per_page=50", opts)
        for x in r.get("media", []):
            imgs.append({"media_id": x["mediaId"], "upload_date": x.get("uploadDate", ""),
                         "downloads": x["count"], "earnings": round(x["total"], 4),
                         "description": x.get("details", {}).get("description", "")})
        if page >= r.get("pages", 0):
            break
        page += 1
    n_img = write("shutterstock-images.csv",
                  ["media_id", "upload_date", "downloads", "earnings", "description"], imgs)
    return f"{n_days} days, {n_img} images"


def getty(t):
    t.goto("https://accountmanagement.gettyimages.com/Reports/Export", settle=8)
    if "Royalties" not in t.eval("document.body.innerText"):
        raise RuntimeError("Getty: not signed in to Account Management")
    years = t.eval("[...document.querySelector('select[name=Years]').options].map(o=>o.value)")
    contracts = t.eval("[...document.querySelector('select[name=contractId]').options].map(o=>o.value).filter(Boolean)")
    rows = []
    for y in years:
        # Months depend on the year; the page reloads them via the Years select.
        t.eval(f"(()=>{{const s=document.querySelector('select[name=Years]'); s.value='{y}'; s.dispatchEvent(new Event('change',{{bubbles:true}}))}})()")
        import time; time.sleep(2)
        months = t.eval("[...document.querySelector('select[name=Months]').options].map(o=>o.value)")
        for mo in months:
            for c in contracts:
                tsv = t.eval(f"""(async()=>{{const f=document.querySelector('form[action*=Export]'); const p=new URLSearchParams(new FormData(f));
                  p.set('exportFormat','tsv'); p.set('Years','{y}'); p.set('Months','{mo}'); p.set('contractId',{c!r});
                  const x=await fetch(f.action,{{method:'POST',credentials:'include',body:p}}); return x.headers.get('content-disposition')?await x.text():''}})()""")
                if not tsv:
                    continue
                for r in csv.DictReader(tsv.splitlines(), delimiter="\t"):
                    if not r.get("Asset Number"):
                        continue
                    rows.append({"sale_date": r["Sales Date"], "royalty_month": r["Royalty Month"],
                                 "asset_id": r["Asset Number"], "description": r["Asset Description"],
                                 "collection": r["Collection"], "content_type": r["Content Type"],
                                 "product_type": r["Product Type"], "sale_region": r["Sale Region"],
                                 "license_fee": r["License Fee in USD"], "royalty_rate": r["Royalty Rate"],
                                 "gross_royalty": r["Gross Royalty in USD"]})
    return write("getty-sales.csv", ["sale_date", "royalty_month", "asset_id", "description", "collection",
                                     "content_type", "product_type", "sale_region", "license_fee",
                                     "royalty_rate", "gross_royalty"], rows)


def main():
    pages = [x for x in json.load(urllib.request.urlopen(CDP + "/json")) if x["type"] == "page"]
    # The sweep closes its own tabs before this runs, so there may be none.
    t = Tab(pages[0]) if pages else Tab.new()
    t.front()
    for name, fn in (("adobe", adobe), ("shutterstock", shutterstock), ("getty", getty)):
        try:
            print(f"{name}: {fn(t)}")
        except Exception as e:
            print(f"{name}: FAILED {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
