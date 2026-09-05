#!/usr/bin/env python3
"""Render the photo-licensing analytics into one self-contained page.

Reads photo-licensing-workspace/analytics/snapshots.csv (tidy long format,
written by stats-collect.py) and produces:

  analytics/dashboard.html    the page you actually look at
  analytics/growth_summary.txt week-over-week deltas, same shape as the
                               TikTok pipeline's growth_summary.txt

The page answers "how much am I making?" first and everything else second,
because for a long stretch the honest answer is zero and the useful signal is
how far each platform still is from paying out at all.
"""
import csv, datetime, html, json, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AN = ROOT / "photo-licensing-workspace" / "analytics"
SNAPSHOTS = AN / "snapshots.csv"
PAGE = AN / "dashboard.html"
SUMMARY = AN / "growth_summary.txt"

# threshold you must cross before the platform sends money, and the cut you keep
ECONOMICS = {
    "adobe_stock":    ("Adobe Stock",      25,   "33% flat"),
    "shutterstock":   ("Shutterstock",     25,   "15-40% tiered"),
    "alamy":          ("Alamy",            75,   "15-40% tiered"),
    "dreamstime":     ("Dreamstime",       100,  "25-50%"),
    "getty":          ("Getty / iStock",   100,  "15% non-exclusive"),
    "fineartamerica": ("Fine Art America", None, "your markup"),
}
MONEY = {"balance", "earnings", "revenue", "sales_30d", "available_earnings"}
SALES = {"sales", "sales_to_date", "downloads"}
# metrics worth showing as pipeline state, in display order
PIPELINE = ["accepted_live", "on_sale_good", "on_sale_poor", "not_on_sale",
            "in_qc", "passed", "failed", "pending", "not_submitted",
            "recently_reviewed", "marketplace_catalog", "refused_pages",
            "total_images", "visitors_7d", "favorites_7d", "followers",
            "pending_new", "downloads_per_image"]

# Events parsed out of notification email. These are things the web UIs do not
# show at all -- Dreamstime silently reclassified 59 Royalty Free images as
# Editorial and only said so by mail -- so they get their own section rather
# than being buried among the pipeline counters.
#   metric -> (label, tone)  tone: bad | good | neutral
EMAIL_EVENTS = {
    "email_rf_to_editorial":      ("Royalty Free downgraded to Editorial", "bad"),
    "email_not_accepted":         ("Rejected in review", "bad"),
    "email_refused":              ("Refused", "bad"),
    "email_qc_failed":            ("Failed QC", "bad"),
    "email_accepted":             ("Accepted in review", "good"),
    "email_approved":             ("Approved", "good"),
    "email_qc_passed":            ("Passed QC", "good"),
    "email_accepted_contributor": ("Contributor application accepted", "good"),
    "email_earnings":             ("Earnings reported by email", "good"),
    "email_pending_reminders":    ("Pending reminders", "neutral"),
    "email_downloads":            ("Downloads", "good"),
}
EXPLAIN = {
    "email_rf_to_editorial":
        "Editorial licences cannot be used in advertising or marketing, so these "
        "earn less than the Royalty Free submission intended. Usually triggered by "
        "recognisable people, private property, or visible logos.",
    "email_not_accepted":
        "Check the platform for per-image reasons; Dreamstime reports codes such "
        "as MR/PR (missing model or property release).",
}


def load():
    if not SNAPSHOTS.exists():
        sys.exit(f"no snapshots yet at {SNAPSHOTS} — run scripts/stats-collect.py first")
    rows = list(csv.DictReader(open(SNAPSHOTS)))
    data = defaultdict(dict)          # date -> (platform, metric) -> value
    for r in rows:
        try:
            v = float(r["value"])
        except (TypeError, ValueError):
            continue
        data[r["snapshot_date"]][(r["platform"], r["metric"])] = v
    return data


def fmt(v, money=False):
    if v is None:
        return "—"
    if money:
        return f"${v:,.2f}"
    return f"{int(v):,}" if float(v).is_integer() else f"{v:,.2f}"


MIN_DAYS = 3          # never project from fewer observations than this
WINDOW = 7            # rolling window, in days


def forecast(data, dates, platform, threshold):
    """Days until this platform crosses its payout threshold.

    Uses the rolling 7-day change in balance. Returns a dict describing what
    can honestly be said, which is usually "not yet":

      state = "earning"      -> a real rate, so an ETA in days
      state = "flat"         -> observed, but no money is accruing
      state = "insufficient" -> too few days to say anything
      state = "no_threshold" -> platform doesn't publish one (FAA)

    Deliberately refuses to extrapolate from a single data point or from zero.
    A projection built on no earnings is not a forecast, it's a decoration.
    """
    if not threshold:
        return {"state": "no_threshold"}

    series = [(d, data[d].get((platform, k)))
              for d in dates
              for k in ("balance", "earnings", "available_earnings")
              if (platform, k) in data[d]]
    # keep one reading per day, latest wins
    per_day = {}
    for d, v in series:
        if v is not None:
            per_day[d] = v
    days = sorted(per_day)
    if len(days) < MIN_DAYS:
        return {"state": "insufficient", "have": len(days), "need": MIN_DAYS,
                "current": per_day[days[-1]] if days else None}

    window = days[-WINDOW:]
    span = (datetime.date.fromisoformat(window[-1])
            - datetime.date.fromisoformat(window[0])).days
    if span <= 0:
        return {"state": "insufficient", "have": len(days), "need": MIN_DAYS,
                "current": per_day[days[-1]]}

    gained = per_day[window[-1]] - per_day[window[0]]
    rate = gained / span                      # $/day
    current = per_day[days[-1]]
    if rate <= 0:
        return {"state": "flat", "current": current, "threshold": threshold,
                "window_days": span}

    remaining = max(threshold - current, 0)
    eta_days = remaining / rate
    eta = datetime.date.today() + datetime.timedelta(days=round(eta_days))
    return {"state": "earning", "current": current, "threshold": threshold,
            "rate": rate, "days": eta_days, "eta": eta.isoformat(),
            "window_days": span}


def forecast_label(f):
    if f["state"] == "no_threshold":
        return "no payout threshold", ""
    if f["state"] == "insufficient":
        return (f"need {f['need'] - f['have']} more day(s) of data",
                "collecting")
    if f["state"] == "flat":
        return ("no earnings yet — nothing to project",
                f"$0/day over {f['window_days']}d")
    d = f["days"]
    when = f"{d:.0f} days" if d < 400 else f"{d/365:.1f} years"
    return (f"~{when} (≈{f['eta']})", f"${f['rate']:.2f}/day")


def series_for(data, dates, platform, metric):
    """[(date, value)] for one metric, days with no reading omitted."""
    return [(d, data[d][(platform, metric)]) for d in dates
            if (platform, metric) in data[d]]


def project(points, horizon=30, threshold=None):
    """Fan out a RANGE of futures from the observed day-over-day deltas.

    The band is min/median/max of what has actually been observed -- not a
    model, not a guess. Two or three flat days therefore produce a flat band,
    and that is the correct answer: the honest width of a projection built on
    no movement is zero.

    Returns None when there is nothing to project from.
    """
    if len(points) < 2:
        return None
    deltas = []
    for (d1, v1), (d2, v2) in zip(points, points[1:]):
        span = (datetime.date.fromisoformat(d2) - datetime.date.fromisoformat(d1)).days or 1
        deltas.append((v2 - v1) / span)
    lo, hi = min(deltas), max(deltas)
    mid = sorted(deltas)[len(deltas) // 2]
    last_date = datetime.date.fromisoformat(points[-1][0])
    last_val = points[-1][1]
    fut = []
    for i in range(1, horizon + 1):
        d = (last_date + datetime.timedelta(days=i)).isoformat()
        fut.append((d, last_val + lo * i, last_val + mid * i, last_val + hi * i))
    moving = any(abs(x) > 1e-9 for x in deltas)
    return {"future": fut, "lo": lo, "mid": mid, "hi": hi, "moving": moving,
            "threshold": threshold}


def spark(points, proj=None, threshold=None, w=300, h=90, money=False):
    """Self-contained inline SVG: history solid, projected range shaded."""
    if not points:
        return '<div class="tiny">no data</div>'
    hist = [(datetime.date.fromisoformat(d).toordinal(), v) for d, v in points]
    fut = proj["future"] if proj else []
    futo = [(datetime.date.fromisoformat(d).toordinal(), lo, mid, hi) for d, lo, mid, hi in fut]
    xs = [x for x, *_ in hist] + [x for x, *_ in futo]
    ys = [v for _x, v in hist] + [v for _x, lo, mid, hi in futo for v in (lo, mid, hi)]
    if threshold:
        ys.append(threshold)
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys + [0]), max(ys + [1])
    if x1 == x0:
        x1 = x0 + 1
    if y1 == y0:
        y1 = y0 + 1
    pad = 6

    def px(x):
        return pad + (x - x0) / (x1 - x0) * (w - 2 * pad)

    def py(y):
        return h - pad - (y - y0) / (y1 - y0) * (h - 2 * pad)

    parts = []
    if threshold is not None:
        parts.append(f'<line x1="{px(x0):.1f}" y1="{py(threshold):.1f}" '
                     f'x2="{px(x1):.1f}" y2="{py(threshold):.1f}" '
                     f'class="thr"/>')
    if futo:
        up = " ".join(f"{px(x):.1f},{py(hi):.1f}" for x, lo, mid, hi in futo)
        dn = " ".join(f"{px(x):.1f},{py(lo):.1f}" for x, lo, mid, hi in reversed(futo))
        j = f"{px(hist[-1][0]):.1f},{py(hist[-1][1]):.1f}"
        parts.append(f'<polygon points="{j} {up} {dn}" class="band"/>')
        midline = f"{j} " + " ".join(f"{px(x):.1f},{py(mid):.1f}" for x, lo, mid, hi in futo)
        parts.append(f'<polyline points="{midline}" class="mid"/>')
    parts.append('<polyline points="' +
                 " ".join(f"{px(x):.1f},{py(v):.1f}" for x, v in hist) + '" class="hist"/>')
    for x, v in hist:
        parts.append(f'<circle cx="{px(x):.1f}" cy="{py(v):.1f}" r="2.4" class="dot"/>')
    return (f'<svg viewBox="0 0 {w} {h}" class="spark" preserveAspectRatio="none">'
            + "".join(parts) + "</svg>")


def main():
    data = load()
    dates = sorted(data)
    today, prev = dates[-1], (dates[-2] if len(dates) > 1 else None)
    week = None
    if len(dates) > 1:
        target = (datetime.date.fromisoformat(today) - datetime.timedelta(days=7)).isoformat()
        earlier = [d for d in dates if d <= target]
        week = earlier[-1] if earlier else dates[0]

    cur = data[today]

    # Last known value for every (platform, metric), with the day it came from.
    #
    # WHY NOT data[today]: a collector that fails today contributes NO rows, so
    # reading only today silently drops that platform's money from the totals.
    # Dreamstime's bot check did exactly that on 2026-08-18 and the dashboard
    # reported $0.20 of a real $0.90 -- money that had been collected, verified
    # against Dreamstime's own earnings page, and then quietly vanished because
    # one scrape was blocked. Earnings do not un-happen when a scrape fails.
    #
    # Carried-forward values are dated in the UI rather than shown as current,
    # so a stale figure is visible AS stale instead of freezing in place.
    last = {}
    for d in dates:
        for key, v in data[d].items():
            if v is not None:
                last[key] = (v, d)

    platforms = sorted({p for (p, _m) in last})

    # ---- money -------------------------------------------------------------
    total_money = 0.0
    total_sales = 0.0
    money_rows = []
    for p in platforms:
        label, thresh, royalty = ECONOMICS.get(p, (p.replace("_", " ").title(), None, "—"))
        bal_e = next((last[(p, k)] for k in MONEY if (p, k) in last), None)
        sal_e = next((last[(p, k)] for k in SALES if (p, k) in last), None)
        bal, bal_as_of = bal_e if bal_e else (None, None)
        sal, _sal_as_of = sal_e if sal_e else (None, None)
        if bal:
            total_money += bal
        if sal:
            total_sales += sal
        if p == "alamy_qc":
            continue
        pct = (bal / thresh * 100) if (bal is not None and thresh) else (0 if thresh else None)
        as_of = bal_as_of if (bal_as_of and bal_as_of != today) else None
        money_rows.append((label, bal, sal, thresh, pct, royalty, as_of))

    # ---- week-over-week summary -------------------------------------------
    lines = [f"Photo licensing — week-over-week ({week} → {today})" if week
             else f"Photo licensing — first snapshot ({today})", ""]
    for p in platforms:
        for (pp, m), v in sorted(cur.items()):
            if pp != p or m == "collector_ok":
                continue
            old = data.get(week, {}).get((p, m)) if week else None
            if old is None:
                lines.append(f"  {p}/{m}  {fmt(v)}")
            else:
                d = v - old
                pctd = (d / old * 100) if old else 0.0
                lines.append(f"  {p}/{m}  {fmt(old)} → {fmt(v)}  ({d:+,.0f}, {pctd:+.1f}%)")
    lines.append("")
    lines.append("Projected time to payout threshold (rolling %d-day rate):" % WINDOW)
    for p in platforms:
        label, thresh, _r = ECONOMICS.get(p, (p, None, ""))
        if p == "alamy_qc":
            continue
        f = forecast(data, dates, p, thresh)
        eta, rate = forecast_label(f)
        lines.append(f"  {label:<18} {eta}{('  [' + rate + ']') if rate else ''}")

    stale = [p for p in platforms if cur.get((p, "collector_ok")) == 0]
    if stale:
        lines += ["", "STALE (collector could not sign in): " + ", ".join(stale)]
    SUMMARY.write_text("\n".join(lines) + "\n")

    # ---- page --------------------------------------------------------------
    def money_table():
        out = []
        for label, bal, sal, thresh, pct, royalty, as_of in money_rows:
            key = next((p for p in platforms
                        if ECONOMICS.get(p, ("",))[0] == label), None)
            f = forecast(data, dates, key, thresh) if key else {"state": "insufficient",
                                                               "have": 0, "need": MIN_DAYS}
            eta, rate = forecast_label(f)
            cls = {"earning": "up", "flat": "dim", "insufficient": "dim",
                   "no_threshold": "dim"}[f["state"]]
            if thresh:
                w = min(100, pct or 0)
                bar = (f'<div class="bar"><span style="width:{w:.1f}%"></span></div>'
                       f'<div class="tiny">{fmt(bal or 0, True)} of ${thresh} payout</div>')
            else:
                bar = '<div class="tiny">no stated threshold</div>'
            stale_note = (f'<div class="tiny">as of {html.escape(as_of)}</div>'
                          if as_of else "")
            out.append(f"""<tr><td><b>{html.escape(label)}</b><div class="tiny">{html.escape(royalty)}</div></td>
              <td class="num">{fmt(bal, True) if bal is not None else '—'}{stale_note}</td>
              <td class="num">{fmt(sal) if sal is not None else '—'}</td>
              <td>{bar}</td>
              <td><span class="{cls}">{html.escape(eta)}</span>
                  <div class="tiny">{html.escape(rate)}</div></td></tr>""")
        return "\n".join(out)

    def charts_section():
        """Small multiples: money first, then whatever pipeline metrics move."""
        cards=[]
        # money charts, one per platform with a payout threshold
        for pf in platforms:
            label, thresh, _r = ECONOMICS.get(pf, (pf.replace("_"," ").title(), None, ""))
            if not thresh: continue
            pts=[]
            for k in ("balance","earnings","available_earnings"):
                pts = series_for(data, dates, pf, k)
                if pts: break
            if not pts: continue
            pr = project(pts, horizon=30, threshold=thresh)
            note = ("no movement observed — band is flat because the data is flat"
                    if (pr and not pr["moving"]) else
                    (f"observed {fmt(pr['lo'],True)}–{fmt(pr['hi'],True)}/day" if pr else
                     "need a second reading to project"))
            cards.append(f'''<div class="chart"><h4>{html.escape(label)}
              <span class="tiny">balance vs ${thresh} payout</span></h4>
              {spark(pts, pr, threshold=thresh, money=True)}
              <div class="tiny">{html.escape(note)}</div></div>''')
        # pipeline charts for metrics that actually vary across days
        for pf in platforms:
            label = ECONOMICS.get(pf, (pf.replace("_"," ").title(),))[0]
            for m in PIPELINE:
                pts = series_for(data, dates, pf, m)
                if len(pts) < 2: continue
                if len({v for _d,v in pts}) < 2: continue      # flat: not worth a chart
                pr = project(pts, horizon=14)
                cards.append(f'''<div class="chart"><h4>{html.escape(label)}
                  <span class="tiny">{html.escape(m.replace("_"," "))}</span></h4>
                  {spark(pts, pr)}
                  <div class="tiny">range {pr["lo"]:+.1f} to {pr["hi"]:+.1f}/day</div></div>''')
        if not cards:
            return ('<div class="card"><div class="tiny">Not enough history to chart yet. '
                    'Charts appear once a metric has two or more readings.</div></div>')
        return '<div class="charts">' + "".join(cards) + "</div>"

    def email_section():
        """Events from notification email, newest day first."""
        rows_out = []
        for d in reversed(dates):
            hits = [(p, m, v) for (p, m), v in sorted(data[d].items())
                    if m in EMAIL_EVENTS and v]
            if not hits:
                continue
            cells = []
            for p, m, v in hits:
                label, tone = EMAIL_EVENTS[m]
                plat = ECONOMICS.get(p, (p.replace("_", " ").title(),))[0]
                note = EXPLAIN.get(m, "")
                cells.append(
                    f'<div class="ev {tone}"><div class="evn">{fmt(v)}</div>'
                    f'<div class="evl"><b>{html.escape(plat)}</b> — {html.escape(label)}'
                    + (f'<div class="tiny">{html.escape(note)}</div>' if note else "")
                    + "</div></div>")
            rows_out.append(f'<h3 class="dt">{d}</h3><div class="evs">{"".join(cells)}</div>')
        if not rows_out:
            return ('<div class="card"><div class="tiny">No notification email parsed yet. '
                    'Run <code>scripts/mail-collect.py --discover</code> to see what is arriving.'
                    "</div></div>")
        return "\n".join(rows_out)

    def pipeline_table():
        out = []
        for p in platforms:
            label = ECONOMICS.get(p, (p.replace("_", " ").title(),))[0]
            cells = []
            for m in PIPELINE:
                if (p, m) in cur:
                    old = data.get(week, {}).get((p, m)) if week else None
                    d = ""
                    if old is not None and cur[(p, m)] != old:
                        diff = cur[(p, m)] - old
                        d = f'<span class="{"up" if diff>0 else "down"}">{diff:+,.0f}</span>'
                    cells.append(f'<div class="kv"><span>{html.escape(m.replace("_"," "))}</span>'
                                 f'<b>{fmt(cur[(p,m)])} {d}</b></div>')
            if not cells:
                continue
            ok = cur.get((p, "collector_ok"), 1)
            badge = "" if ok else '<span class="stale">stale</span>'
            out.append(f'<div class="card"><h3>{html.escape(label)}{badge}</h3>{"".join(cells)}</div>')
        return "\n".join(out)

    page = f"""<!doctype html><meta charset="utf-8">
<title>Photo licensing analytics</title>
<style>
 :root{{--bg:#0f1115;--card:#171a21;--line:#262b36;--fg:#e6e9ef;--dim:#8b93a7;--up:#3fb950;--down:#f85149;--accent:#7c5cff}}
 /* Dark only, by choice. Every colour is defined on bare :root and nothing is
    left to the viewer's theme, so the page looks identical wherever it opens
    -- including when a browser or client is set to light. */
 html{{color-scheme:dark}}
 *{{box-sizing:border-box}}
 body{{margin:0;padding:28px;background:var(--bg);color:var(--fg);
   font:15px/1.5 ui-sans-serif,-apple-system,"Segoe UI",Roboto,sans-serif}}
 h1{{margin:0 0 4px;font-size:22px}} h2{{font-size:15px;margin:30px 0 10px;color:var(--dim);
   text-transform:uppercase;letter-spacing:.08em}}
 .sub{{color:var(--dim);font-size:13px;margin-bottom:22px}}
 .hero{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:8px}}
 .big{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 22px;min-width:190px}}
 .big .n{{font-size:30px;font-weight:650;letter-spacing:-.02em}}
 .big .l{{color:var(--dim);font-size:12px;text-transform:uppercase;letter-spacing:.07em;margin-top:2px}}
 table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden}}
 td,th{{padding:12px 14px;border-bottom:1px solid var(--line);text-align:left;vertical-align:middle}}
 tr:last-child td{{border-bottom:none}}
 th{{font-size:11px;color:var(--dim);text-transform:uppercase;letter-spacing:.07em}}
 .num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
 .bar{{height:7px;background:var(--line);border-radius:4px;overflow:hidden;max-width:230px}}
 .bar span{{display:block;height:100%;background:var(--accent)}}
 .tiny{{color:var(--dim);font-size:11.5px;margin-top:4px}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}}
 .card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:15px 17px}}
 .card h3{{margin:0 0 10px;font-size:14px}}
 .kv{{display:flex;justify-content:space-between;gap:10px;padding:4px 0;font-size:13px}}
 .kv span{{color:var(--dim)}}
 .up{{color:var(--up)}} .down{{color:var(--down)}} .dim{{color:var(--dim)}}
 .stale{{background:var(--down);color:#fff;font-size:10px;padding:2px 6px;border-radius:5px;margin-left:8px;
   text-transform:uppercase;letter-spacing:.06em}}
 .note{{color:var(--dim);font-size:12.5px;margin-top:26px;line-height:1.6}}
 .charts{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}}
 .chart{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px}}
 .chart h4{{margin:0 0 8px;font-size:13px;display:flex;justify-content:space-between;gap:10px;align-items:baseline}}
 .spark{{width:100%;height:90px;display:block;margin-bottom:6px}}
 .spark .hist{{fill:none;stroke:var(--accent);stroke-width:2;stroke-linejoin:round}}
 .spark .mid{{fill:none;stroke:var(--accent);stroke-width:1.4;stroke-dasharray:4 3;opacity:.85}}
 .spark .band{{fill:var(--accent);opacity:.15}}
 .spark .dot{{fill:var(--accent)}}
 .spark .thr{{stroke:var(--dim);stroke-width:1;stroke-dasharray:3 4}}
 .evs{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px;margin-bottom:16px}}
 .ev{{display:flex;gap:13px;align-items:flex-start;background:var(--card);border:1px solid var(--line);
   border-left:4px solid var(--line);border-radius:12px;padding:13px 15px}}
 .ev.bad{{border-left-color:var(--down)}} .ev.good{{border-left-color:var(--up)}}
 .ev.neutral{{border-left-color:var(--dim)}}
 .evn{{font-size:22px;font-weight:650;font-variant-numeric:tabular-nums;line-height:1.1;min-width:44px}}
 .ev.bad .evn{{color:var(--down)}} .ev.good .evn{{color:var(--up)}}
 .evl{{font-size:13px;line-height:1.45}}
 h3.dt{{font-size:12px;color:var(--dim);margin:18px 0 8px;letter-spacing:.06em}}
</style>
<h1>Photo licensing</h1>
<div class="sub">{today}{f" · compared with {week}" if week else ""} · {len(dates)} day(s) of history</div>

<div class="hero">
  <div class="big"><div class="n">{fmt(total_money, True)}</div><div class="l">total balance</div></div>
  <div class="big"><div class="n">{fmt(total_sales)}</div><div class="l">lifetime sales</div></div>
  <div class="big"><div class="n">{len([1 for p in platforms if cur.get((p,'collector_ok'))==1])}/{len(platforms)}</div><div class="l">collectors healthy</div></div>
</div>

<h2>Money</h2>
<table><tr><th>Platform</th><th class="num">Balance</th><th class="num">Sales</th><th>Progress to payout</th><th>Projected payout</th></tr>
{money_table()}
</table>

<h2>Trends &amp; projections</h2>\n{charts_section()}\n\n<h2>Review &amp; licence activity — from email</h2>
{email_section()}

<h2>Pipeline</h2>
<div class="grid">{pipeline_table()}</div>

<div class="note">
Balances are withheld until each platform's threshold is crossed, so a non-zero balance
is not money you can spend yet. Sales counts are lifetime. A <b>stale</b> badge means the
collector could not sign in that day — the number shown is not current; re-run
<code>scripts/stats-collect.py --login</code> to refresh saved sessions.
</div>
"""
    AN.mkdir(parents=True, exist_ok=True)
    PAGE.write_text(page)
    print(f"wrote {PAGE}")
    print(f"wrote {SUMMARY}")


if __name__ == "__main__":
    main()
