#!/usr/bin/env python3
"""The Monday memo for the photo arm: five lines that each name an action.

Replaces reading the dashboard. Every line is a rule that either fired or
did not; a number that never changes a decision does not belong here.

  python3 scripts/photo-weekly-memo.py            # print the memo, write docs/growth-briefs/photo-memo-<date>.md
  python3 scripts/photo-weekly-memo.py --no-write

Inputs (all produced by the daily sweep, scripts/stats-collect.py):
  photo-licensing-workspace/analytics/snapshots.csv            platform metrics by day
  photo-licensing-workspace/analytics/adobe-sales.csv, shutterstock-days.csv,
      getty-sales.csv, dreamstime-sales.csv                    per-sale ledgers
  photo-licensing-workspace/analytics/owner-hours.csv          date,hours,note (Ben appends)
  photo-licensing-workspace/analytics/alamy-rewrite.json       {"date": ..., "stems": [...]} written by the caption rewrite
  purplelink.llc stats + sales functions (STATS_TOKEN via `netlify env:get`)  hub traffic, direct photo sales

The $/hour rule: trailing-4-week royalties plus direct sales, divided by the
owner hours logged in the same window. Above $5/hour the arm keeps growing;
below it, hold the freeze and run the inventory as an annuity.
"""
import argparse, csv, datetime as dt, json, os, ssl, subprocess, sys, urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_WS = Path(os.environ.get("PL_WORKSPACE") or (ROOT / "photo-licensing-workspace"))
WS = _WS if _WS.exists() else Path("/Volumes/Extreme SSD/Purplelink LLC/photo-licensing-workspace")
AN = WS / "analytics"
OUT = ROOT / "docs" / "growth-briefs"
TODAY = dt.date.today()
WEEK = dt.timedelta(days=7)
WINDOW = dt.timedelta(days=28)
RATE_FLOOR = 5.0           # $/owner-hour that justifies growth work
MIN_HOURS = 4.0            # below this the ratio is noise, not a reading
NETLIFY_DIR = ROOT if (ROOT / ".netlify").exists() else Path("/Volumes/Extreme SSD/Purplelink LLC")
MIN_PAYOUT = {"getty": 100, "adobe_stock": 25, "shutterstock": 35, "alamy": 75, "dreamstime": 100,
              "123rf": 50, "depositphotos": 25}


def read_csv(path):
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def num(s):
    try:
        return float(str(s).replace(",", "").replace("$", ""))
    except (TypeError, ValueError):
        return None


def snapshots():
    """{(platform, metric): [(date, value)]} sorted by date."""
    out = defaultdict(list)
    for r in read_csv(AN / "snapshots.csv"):
        v = num(r["value"])
        if v is None:
            continue
        out[(r["platform"], r["metric"])].append((dt.date.fromisoformat(r["snapshot_date"]), v))
    for k in out:
        out[k].sort()
    return out


def at(series, when):
    """Latest value on or before `when`."""
    v = None
    for d, x in series:
        if d <= when:
            v = x
        else:
            break
    return v


def ledger_sum(path, date_key, amount_key, since):
    total, n = 0.0, 0
    for r in read_csv(path):
        d = r.get(date_key, "")
        try:
            day = dt.datetime.strptime(d, "%d-%b-%Y").date() if "-" in d and d[:2].isdigit() and not d[4:5] == "-" else dt.date.fromisoformat(d[:10])
        except ValueError:
            continue
        if day >= since:
            a = num(r.get(amount_key))
            if a:
                total += a; n += 1
    return total, n


def netlify_env(name):
    try:
        r = subprocess.run(["netlify", "env:get", name, "--context", "production"], capture_output=True, text=True, timeout=40, cwd=NETLIFY_DIR)
        v = r.stdout.strip().splitlines()[-1].strip() if r.returncode == 0 and r.stdout.strip() else ""
        return v if v and " " not in v else ""
    except Exception:
        return ""


def _pairs(obj, k1=("key", "path", "product"), k2=("count", "views", "orders", "sales")):
    """Normalise {key: n} dicts and [{key, count}] lists to (key, value) pairs."""
    if isinstance(obj, dict):
        return [(k, v) for k, v in obj.items()]
    out = []
    for row in obj or []:
        if not isinstance(row, dict):
            continue
        k = next((row[x] for x in k1 if x in row), None)
        v = next((row[x] for x in k2 if x in row), row)
        out.append((k, v))
    return out


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def site_numbers(token, days=28):
    """Hub-page views, license-button clicks and direct photo sales from the site's own functions."""
    out = {"hub_views": None, "hub_top": [], "direct_sales": None, "direct_revenue": None, "license_clicks": None}
    if not token:
        return out
    try:
        with urllib.request.urlopen(f"https://purplelink.llc/.netlify/functions/stats?token={token}&days={days}", timeout=120, context=_ctx()) as r:
            s = json.load(r)
        hub = [(p, int(v or 0)) for p, v in _pairs(s.get("topPaths") or s.get("top_paths")) if p and str(p).startswith("/photography")]
        hub.sort(key=lambda x: -x[1])
        out["hub_views"] = sum(v for _, v in hub)
        out["hub_top"] = hub[:5]
        out["license_clicks"] = sum(int(v or 0) for k, v in _pairs(s.get("checkoutByProduct")) if str(k).startswith("photo-"))
    except Exception as e:
        out["stats_error"] = f"{type(e).__name__}"
    try:
        with urllib.request.urlopen(f"https://purplelink.llc/.netlify/functions/sales?token={token}&days={days}", timeout=120, context=_ctx()) as r:
            s = json.load(r)
        n, rev = 0, 0.0
        found = False
        for key in ("byProduct", "by_product", "products", "windowByProduct"):
            if key in s:
                found = True
                for k, v in _pairs(s[key]):
                    if not str(k).startswith("photo-"):
                        continue
                    if isinstance(v, dict):
                        n += int(v.get("orders") or v.get("count") or v.get("sales") or 0)
                        rev += float(v.get("gross") or 0) / 100 + float(v.get("revenue") or v.get("amount") or 0)
                    else:
                        n += int(v or 0)
        out["direct_sales"], out["direct_revenue"] = (n, round(rev, 2)) if found else (None, None)
        out["sales_window"] = s.get("window")
    except Exception as e:
        out["sales_error"] = f"{type(e).__name__}"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args()
    snap = snapshots()
    since = TODAY - WINDOW
    lines, detail = [], []

    # 1. money in the window: ledgers where they exist, balance deltas elsewhere
    royalties = 0.0
    parts = []
    for name, path, dk, ak in (("adobe", AN / "adobe-sales.csv", "sale_date", "amount"),
                               ("shutterstock", AN / "shutterstock-days.csv", "date", "earnings"),
                               ("getty", AN / "getty-sales.csv", "sale_date", "gross_royalty"),
                               ("dreamstime", AN / "dreamstime-sales.csv", "sale_date", "amount")):
        t, n = ledger_sum(path, dk, ak, since)
        royalties += t
        if n:
            parts.append(f"{name} {n} sale(s) ${t:.2f}")
    for plat, metric in (("alamy_sales", "lifetime_sales_amount"), ("123rf", "balance"), ("depositphotos", "balance"), ("fineartamerica", "balance"), ("etsy", "revenue")):
        s = snap.get((plat, metric), [])
        now, before = at(s, TODAY), at(s, since)
        if now is not None and before is not None and now - before > 0:
            royalties += now - before
            parts.append(f"{plat.split('_')[0]} +${now - before:.2f}")
    # The dashboard's private env file is the reliable source; the Netlify
    # variable stopped answering `env:get` on 2026-10-04.
    token = ""
    envf = Path.home() / ".config" / "purplelink" / "traffic.env"
    if envf.exists():
        for line in envf.read_text().splitlines():
            if line.startswith("PURPLELINK_STATS_TOKEN="):
                token = line.split("=", 1)[1].strip()
    token = token or netlify_env("STATS_TOKEN")
    site = site_numbers(token)
    direct = site["direct_revenue"] or 0.0
    hours = sum(num(r["hours"]) or 0 for r in read_csv(AN / "owner-hours.csv") if r.get("date", "") >= since.isoformat())
    total = royalties + direct
    if hours >= MIN_HOURS:
        rate = total / hours
        verdict = "keep growing" if rate >= RATE_FLOOR else "hold the freeze"
        lines.append(f"1. ${total:.2f} in 4 weeks over {hours:g} owner hours = ${rate:.2f}/hour; rule: {verdict} (floor ${RATE_FLOOR:.0f}/hour).")
    else:
        lines.append(f"1. ${total:.2f} in 4 weeks (royalties ${royalties:.2f}, direct ${direct:.2f}); only {hours:g} owner hours logged in analytics/owner-hours.csv (rule needs {MIN_HOURS:g}), so the $/hour rule cannot fire yet.")
    if parts:
        detail.append("Royalties: " + "; ".join(parts) + ".")

    # 2. payout floors: which platform is closest to paying out
    best = None
    for plat, floor in MIN_PAYOUT.items():
        b = at(snap.get((plat, "balance"), []), TODAY)
        if b is None:
            continue
        gap = floor - b
        if best is None or gap < best[1]:
            best = (plat, gap, b)
    if best:
        plat, gap, b = best
        lines.append(f"2. Closest payout: {plat} ${b:.2f} of ${MIN_PAYOUT[plat]} ({'reached' if gap <= 0 else f'${gap:.2f} short'}); action: {'request the payout' if gap <= 0 else 'no action'}.")

    # 3. hub traffic and direct sales (the only channel we own)
    if site.get("hub_views") is not None:
        top = ", ".join(f"{p} {v}" for p, v in site["hub_top"][:3])
        ds = site["direct_sales"]
        lines.append(f"3. /photography/ pages: {site['hub_views']} views in 28 days ({top or 'none'}); license clicks {site['license_clicks'] or 0}; direct sales {ds if ds is not None else 'not split by product yet'} (${direct:.2f}); "
                     f"rule: {'first direct sale happened, keep the license page' if (ds or 0) > 0 else 'no direct sale yet; day-90 gate is the decision point'}.")
    else:
        lines.append(f"3. /photography/ traffic unavailable ({site.get('stats_error', 'no STATS_TOKEN')}); fix the token before next Monday.")

    # 4. Alamy caption rewrite: before/after on the account-level views and CTR
    rw = AN / "alamy-rewrite.json"
    views = snap.get(("alamy_measures", "views"), []); ctr = snap.get(("alamy_measures", "ctr"), [])
    if rw.exists():
        d = json.loads(rw.read_text())
        start = dt.date.fromisoformat(d["date"])
        v_before, v_after = at(views, start), at(views, TODAY)
        c_before, c_after = at(ctr, start), at(ctr, TODAY)
        age = (TODAY - start).days
        if v_before and v_after:
            lift = (v_after - v_before) / v_before * 100
            rule = ("too early" if age < 28 else "roll out to the rest" if lift > 25 else "stop touching metadata; move to selection")
            lines.append(f"4. Alamy rewrite day {age}: views {v_before:.0f} -> {v_after:.0f} ({lift:+.0f}%), CTR {c_before} -> {c_after}; rule: {rule}.")
        else:
            lines.append(f"4. Alamy rewrite day {age}: not enough measures yet.")
    else:
        v = at(views, TODAY); c = at(ctr, TODAY)
        lines.append(f"4. Alamy views/week {v if v is not None else '?'} at CTR {c if c is not None else '?'}; the caption rewrite has not started (no analytics/alamy-rewrite.json).")

    # 5. pipeline health: review backlog and pending flags from the latest snapshot
    flags = []
    for plat, metric, label in (("depositphotos", "pending", "Depositphotos in review"), ("123rf", "pending", "123RF in review"),
                                ("getty", "in_review", "Getty in review"), ("adobe_stock", "in_review", "Adobe in review"),
                                ("getty", "need_revisions", "Getty need revisions"), ("shutterstock", "correction_needed", "Shutterstock corrections")):
        v = at(snap.get((plat, metric), []), TODAY)
        if v:
            flags.append(f"{label} {v:.0f}")
    last = max((d for s in snap.values() for d, _ in s), default=None)
    stale = last is None or (TODAY - last).days > 2
    lines.append(f"5. Sweep last ran {last or 'never'}{' (STALE: check Chrome and logins)' if stale else ''}; {'; '.join(flags) if flags else 'no review backlog'}; "
                 f"rule: {'fix the sweep first' if stale else 'nothing to do'}.")

    memo = f"# Photo arm memo, {TODAY.isoformat()}\n\n" + "\n".join(lines) + "\n\n" + ("\n".join(detail) + "\n" if detail else "")
    print(memo)
    if not a.no_write:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f"photo-memo-{TODAY.isoformat()}.md").write_text(memo, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
