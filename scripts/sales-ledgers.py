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
  faa-sales.csv           one row per Fine Art America order (Sales page).
                          The sweep reads only a balance, which says money
                          moved but not what sold; every run names orders
                          new since the last run as "NEW FAA order" lines.
  getty-downloads.csv     one row per asset from ESP's Stats page (last
                          download date, channel counts). Money lags a month
                          behind, downloads do not, so this is where a new
                          Getty sale first shows. Every run names the assets
                          whose count rose since the last run, with the photo
                          and caption, as "NEW getty download" lines.

Sources verified 2026-09-30. Each ledger is rewritten from the source on every
run (the sources are full histories), and a platform that fails to read is
reported and left untouched rather than blanked.
"""
import csv, datetime, json, re, sys, urllib.request
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
    for _ in range(3):
        t.goto("https://contributor.stock.adobe.com/en/insights", settle=7)
        if t.url().startswith("https://contributor.stock.adobe.com/"):
            break
    if not t.url().startswith("https://contributor.stock.adobe.com/") or "auth" in t.url() or "signin" in t.url().lower():
        raise RuntimeError(f"Adobe: not signed in or page did not load ({t.url()[:60]})")
    today = datetime.date.today().isoformat()
    q = lambda ep, a, b: (f"https://contributor.stock.adobe.com/en/insights/{ep}?start_date={a}&end_date={b}&time_range=day")
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


ESP_STATS = ("https://esp.gettyimages.com/contribute/stats?assetTypes=Photo%2CVideo%2CIllustration"
             "&primaryDatePeriod=past_24_months&page=1&pageSize=100&orderResultsBy=LastDownloadDate&sortDirection=Descending")
CHANNELS = ["gi_premium", "gi_subscriptions", "gi_ultrapack", "gi_single", "is_subscriptions", "is_credits", "other"]


def getty_downloads(t):
    """Per-asset download counts from ESP, plus a diff against the previous run."""
    import re
    t.goto(ESP_STATS, settle=11)
    body = t.text()
    if "Content statistics" not in body:
        raise RuntimeError("Getty ESP: not signed in")
    flat = re.sub(r"[ \t]+", " ", body)
    rows = {}
    for mid, total, ch, d, rest in re.findall(r"^\s*(\d{6,})\s+(\d+)\s+((?:\d+\s+){7})(\d{2}/\d{2}/\d{4})\s+(.+?)$", flat, re.M):
        parts = ch.split()
        iso = f"{d[6:]}-{d[:2]}-{d[3:5]}"
        rows[mid] = {"asset_id": mid, "total": int(total), "last_download": iso, "collection_type": rest.strip()[:60],
                     **{c: int(v) for c, v in zip(CHANNELS, parts)}}
    shown = re.search(r"Showing\s+\d+\s*-\s*\d+\s+of\s+(\d+)", flat)
    if shown and int(shown.group(1)) != len(rows):
        raise RuntimeError(f"Getty ESP lists {shown.group(1)} assets but {len(rows)} parsed (layout changed?)")
    path = AN / "getty-downloads.csv"
    old = {}
    if path.exists():
        old = {r["asset_id"]: int(r["total"]) for r in csv.DictReader(open(path, newline="", encoding="utf-8"))}
    new = [r for r in rows.values() if r["total"] > old.get(r["asset_id"], 0)]
    first_run = not old
    if new and not first_run:
        names = getty_names(t, {r["asset_id"] for r in new})
        for r in sorted(new, key=lambda r: r["last_download"], reverse=True):
            how = ", ".join(f"{c.replace('_', ' ')} {r[c]}" for c in CHANNELS if r[c])
            f, cap, _ = names.get(r["asset_id"], ("?", "?", ""))
            gained = r["total"] - old.get(r["asset_id"], 0)
            print(f"NEW getty download: {r['last_download']}  {f}  asset {r['asset_id']}  +{gained} ({how})  {cap[:90]}", flush=True)
    write("getty-downloads.csv", ["asset_id", "total", "last_download", "collection_type"] + CHANNELS,
          sorted(rows.values(), key=lambda r: r["last_download"], reverse=True))
    total = sum(r["total"] for r in rows.values())
    return f"{len(rows)} assets, {total} downloads" + ("" if first_run else f", {len(new)} with new downloads")


def getty_names(t, ids):
    """Map ESP master ids to (file name, caption, status) through the batches API."""
    out = {}
    cache = AN / "getty-assets.json"
    known = json.loads(cache.read_text()) if cache.exists() else {}
    out.update({k: tuple(v) for k, v in known.items() if k in ids})
    missing = set(ids) - set(out)
    if missing:
        t.goto("https://esp.gettyimages.com/contribute/batches", settle=7)
        batches = t.eval("fetch('/api/submission/v1/submission_batches?page=1&page_size=100',{credentials:'include'}).then(r=>r.json())")
        for b in (batches.get("items", batches) if isinstance(batches, dict) else batches):
            if not missing:
                break
            bid = b.get("id") or b.get("batch_id")
            c = t.eval(f"fetch('/api/submission/v1/submission_batches/{bid}/contributions?page=1&page_size=200',{{credentials:'include'}}).then(r=>r.json())")
            for r in (c.get("items", c) if isinstance(c, dict) else c):
                blob = json.dumps(r)
                for w in list(missing):
                    if w in blob:
                        out[w] = (r.get("file_name", "?"), (r.get("caption") or r.get("title") or "")[:200], r.get("status", ""))
                        missing.discard(w)
        known.update({k: list(v) for k, v in out.items()})
        cache.write_text(json.dumps(known, indent=1, ensure_ascii=False) + "\n")
    return out


def faa_sales(t):
    """Orders from FAA's control-panel Sales page, plus a diff against the last run."""
    t.goto("https://fineartamerica.com/controlpanel/sales", settle=9)
    if "login" in t.url().lower() or "controlpanel/sales" not in t.url():
        raise RuntimeError(f"FAA: not signed in ({t.url()[:60]})")
    raw = t.eval("[...document.querySelectorAll('.tableTopRowDiv')].map(r=>[...r.children].map(c=>c.innerText.trim().replace(/\\s+/g,' ')))") or []
    rows = []
    for c in raw:
        if len(c) < 8 or not re.match(r"\d{2}/\d{2}/\d{4}$", c[0]):
            continue
        d = c[0]
        money = lambda x: float(re.sub(r"[^\d.]", "", x) or 0) if re.search(r"\d", x) else None
        rows.append({"sale_date": f"{d[6:]}-{d[:2]}-{d[3:5]}", "order_id": c[1], "product": c[3],
                     "buyer": c[4].replace(" fineartamerica.com", ""), "price": money(c[5]), "qty": c[6],
                     "total": money(c[7])})
    if not rows:
        raise RuntimeError("FAA: Sales page listed no orders (layout changed or empty)")
    path = AN / "faa-sales.csv"
    seen = {r["order_id"] for r in csv.DictReader(open(path, newline="", encoding="utf-8"))} if path.exists() else set()
    new = [r for r in rows if r["order_id"] not in seen]
    if seen:
        for r in new:
            amt = f"${r['total']:.2f}" if r["total"] is not None else "owner purchase, no earnings"
            print(f"NEW FAA order: {r['sale_date']}  {amt}  {r['product'][:90]}  ({r['buyer']}, order {r['order_id']})", flush=True)
    write("faa-sales.csv", ["sale_date", "order_id", "product", "buyer", "price", "qty", "total"], rows)
    earned = sum(r["total"] or 0 for r in rows)
    return f"{len(rows)} orders, ${earned:.2f} earned" + ("" if not seen else f", {len(new)} new")


def main():
    pages = [x for x in json.load(urllib.request.urlopen(CDP + "/json")) if x["type"] == "page"]
    # The sweep closes its own tabs before this runs, so there may be none.
    t = Tab(pages[0]) if pages else Tab.new()
    t.front()
    for name, fn in (("adobe", adobe), ("shutterstock", shutterstock), ("getty", getty), ("getty-downloads", getty_downloads), ("faa-sales", faa_sales)):
        try:
            print(f"{name}: {fn(t)}")
        except Exception as e:
            print(f"{name}: FAILED {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
