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
import csv, datetime, html, json, statistics, sys
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
    "123rf":          ("123RF",            50,   "30-60% tiered"),
    "depositphotos":  ("Depositphotos",    25,   "30-38%"),
    # Etsy deposits automatically, so there is no threshold to forecast toward.
    "etsy":           ("Etsy",             None, "price less 6.5% + 3% + $0.25"),
}
MONEY = {"balance", "earnings", "revenue", "sales_30d", "available_earnings"}
SALES = {"sales", "sales_to_date", "downloads"}
# alamy_qc is pipeline status (passed/failed QC), alamy_measures is engagement
# (views/zooms/CTR), alamy_sales is money already folded into the "alamy" row
# itself (see platform_money_asof) -- none of the three get their own row.
SKIP_ROW = {"alamy_qc", "alamy_measures", "alamy_sales"}
# metrics worth showing as pipeline state, in display order
#
# "views", "ctr", "zooms" were collected under the alamy_measures platform
# every day from the start but never appeared anywhere on the page -- this
# list is the only thing charts_section()/pipeline_table() iterate over, and
# those three names were simply never added to it. Found 2026-09-09 while
# mining the full history for patterns: Alamy's own traffic numbers had been
# invisible on its own dashboard the whole time.
PIPELINE = ["accepted_live", "on_sale_good", "on_sale_poor", "not_on_sale",
            "in_qc", "passed", "failed", "pending", "not_submitted",
            "recently_reviewed", "marketplace_catalog", "refused_pages",
            "total_images", "visitors_7d", "favorites_7d", "followers",
            "pending_new", "downloads_per_image", "views", "ctr", "zooms",
            # 123RF (draft/approved/rejected) and Depositphotos (online/
            # unfinished/deactivated) pipeline states, added 2026-09-10.
            "draft", "approved", "rejected", "online", "unfinished",
            "deactivated",
            # Etsy (added 2026-09-24): live listings and shop engagement.
            "active_listings", "visits", "favorites", "followers", "reviews"]

# tiny explanatory note attached to a chart card for a metric that reads
# misleadingly on its own -- keyed by metric name, shown under any platform's
# chart for that metric.
CHART_CAVEAT = {
    "ctr": ("CTR here is cumulative clicks over cumulative views, so it "
            "mechanically drifts down as views accumulate against a near-flat "
            "click count -- a falling line is not necessarily falling interest."),
}

DOW_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

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


def platform_money_asof(data, dates, asof):
    """Per-platform (balance, sales-count) as of a given date, carrying
    forward each platform's last known value the same way main()'s dashboard
    does -- a collector that failed on `asof` itself must not silently zero
    out money that was real on an earlier day (see the Dreamstime incident
    note below). Returns (total_money, total_sales, money_rows), where
    money_rows is a list of (label, balance, sales, threshold, pct_to_threshold,
    royalty, as_of_date_if_stale) -- exactly what main() renders into the
    money table, just parameterized by date so a caller (e.g. a monthly
    revenue rollup) can ask "what did this look like as of the Nth" for
    several dates without re-deriving this carry-forward/dedup logic.
    """
    asof_dates = [d for d in dates if d <= asof]
    if not asof_dates:
        return 0.0, 0.0, []

    # Last known value for every (platform, metric), with the day it came from.
    #
    # WHY NOT data[asof]: a collector that fails on `asof` contributes NO
    # rows, so reading only that day silently drops that platform's money
    # from the totals. Dreamstime's bot check did exactly that on
    # 2026-08-18 and the dashboard reported $0.20 of a real $0.90 -- money
    # that had been collected, verified against Dreamstime's own earnings
    # page, and then quietly vanished because one scrape was blocked.
    # Earnings do not un-happen when a scrape fails.
    #
    # Carried-forward values are dated in the return value rather than shown
    # as current, so a stale figure is visible AS stale instead of freezing
    # in place.
    last = {}
    for d in asof_dates:
        for key, v in data[d].items():
            if v is not None:
                last[key] = (v, d)

    platforms = sorted({p for (p, _m) in last})

    total_money = 0.0
    total_sales = 0.0
    money_rows = []
    # alamy_qc is pipeline status (passed/failed QC), alamy_measures is
    # engagement (views/zooms/CTR) -- neither has a money or sales field, so
    # both always render as a dead "--" row. alamy_sales (added 2026-09-13)
    # DOES have real money, but deliberately under its own field names
    # (lifetime_sales_amount, not "balance") so a sale recorded here
    # wouldn't double up with alamy's cleared-balance figure once a payout
    # catches up to it. Fold it into the one "Alamy" row instead of listing
    # it separately: this figure is revenue recorded the moment Alamy logs a
    # sale, which is what a contributor actually wants to see (Adobe's and
    # Shutterstock's "balance" are likewise accrued-earnings figures, not
    # "cash already in your bank" -- this makes Alamy consistent with them,
    # not a special case).
    alamy_sales_amount, _ = last.get(("alamy_sales", "lifetime_sales_amount"), (None, None))
    alamy_sales_count, _ = last.get(("alamy_sales", "sales_count"), (None, None))
    for p in platforms:
        label, thresh, royalty = ECONOMICS.get(p, (p.replace("_", " ").title(), None, "—"))
        bal_e = next((last[(p, k)] for k in MONEY if (p, k) in last), None)
        sal_e = next((last[(p, k)] for k in SALES if (p, k) in last), None)
        bal, bal_as_of = bal_e if bal_e else (None, None)
        sal, _sal_as_of = sal_e if sal_e else (None, None)
        if p == "alamy" and alamy_sales_amount is not None:
            bal = alamy_sales_amount
            if alamy_sales_count is not None:
                sal = alamy_sales_count
        if bal:
            total_money += bal
        if sal:
            total_sales += sal
        if p in SKIP_ROW:
            continue
        pct = (bal / thresh * 100) if (bal is not None and thresh) else (0 if thresh else None)
        as_of = bal_as_of if (bal_as_of and bal_as_of != asof) else None
        money_rows.append((label, bal, sal, thresh, pct, royalty, as_of))
    return total_money, total_sales, money_rows


def monthly_revenue(data, dates):
    """Per-month, per-platform revenue: the change in cumulative balance
    between one month's end and the previous one, using platform_money_asof
    at each boundary so a collector outage on the literal last day of a
    month doesn't zero out that month (same carry-forward reasoning as the
    live dashboard total).

    Called "monthly revenue," not "MRR" -- MRR means subscription-style
    recurring revenue with an expectation it repeats next month on its own.
    Nothing here recurs by itself; it's one-off royalty payments that happen
    to get bucketed by calendar month. Using the SaaS term would claim a
    predictability this business doesn't have.

    The current month is included through today, not through its literal
    calendar end, so a still-running month reads as "so far," not as if the
    remaining days already happened at zero.

    Returns an ordered list of (month_label "YYYY-MM", total, {platform:
    amount}), oldest first. A platform absent from a month's dict earned
    nothing NEW that month (it may still have a nonzero cumulative balance
    from earlier).
    """
    first = datetime.date.fromisoformat(dates[0])
    today_d = datetime.date.fromisoformat(dates[-1])
    boundaries = []
    y, m = first.year, first.month
    while (y, m) <= (today_d.year, today_d.month):
        month_end = (datetime.date(y + (m == 12), m % 12 + 1, 1) - datetime.timedelta(days=1))
        boundaries.append((f"{y:04d}-{m:02d}", min(month_end, today_d).isoformat()))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)

    out = []
    prev_bal = {}
    for label, boundary in boundaries:
        _, _, rows = platform_money_asof(data, dates, boundary)
        cur_bal = {r[0]: (r[1] or 0.0) for r in rows}
        breakdown, total = {}, 0.0
        for plat_label, bal in cur_bal.items():
            # Clip to >=0 for display: a downward jump here would mean a
            # collector's own bug got fixed and a corrected (lower) balance
            # got recorded, not that money was un-earned -- true across
            # every field this pulls from so far, but stacked bars have no
            # honest way to draw a negative segment either way.
            delta = max(0.0, bal - prev_bal.get(plat_label, 0.0))
            if delta > 1e-9:
                breakdown[plat_label] = delta
            total += delta
        out.append((label, total, breakdown))
        prev_bal = cur_bal
    return out


def project_monthly(months, horizon=3):
    """project()'s honest min/median/max band, at month resolution instead
    of daily. With one or two real months behind it the band is necessarily
    wide -- or, with a single month, there's nothing to derive a rate from
    at all -- and that is the correct, honest answer, not a defect to smooth
    over with a fancier model fit to too little data.
    """
    totals = [(label, total) for label, total, _ in months]
    if len(totals) < 2:
        return None
    deltas = [b - a for (_, a), (_, b) in zip(totals, totals[1:])]
    lo, hi = min(deltas), max(deltas)
    mid = sorted(deltas)[len(deltas) // 2]
    last_label, last_val = totals[-1]
    ly, lm = (int(x) for x in last_label.split("-"))
    fut = []
    for i in range(1, horizon + 1):
        ly, lm = (ly + 1, 1) if lm == 12 else (ly, lm + 1)
        fut.append((f"{ly:04d}-{lm:02d}", max(0.0, last_val + lo * i),
                    max(0.0, last_val + mid * i), max(0.0, last_val + hi * i)))
    moving = any(abs(d) > 1e-9 for d in deltas)
    return {"future": fut, "lo": lo, "mid": mid, "hi": hi, "moving": moving}


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

    # alamy's own "balance" is Alamy's CLEARED payout figure, stuck at $0
    # until a sale's money actually transfers -- the money_table() row above
    # already substitutes alamy_sales' lifetime_sales_amount as Alamy's
    # headline figure (real revenue the moment a sale is logged, same as
    # Adobe's/Shutterstock's "balance" already mean). The projection below
    # has to read the same substituted series, or it would keep saying
    # "no earnings yet" under a row that now shows a real dollar amount.
    money_keys = ["balance", "earnings", "available_earnings"]
    lookup_platform = platform
    if platform == "alamy":
        money_keys = ["lifetime_sales_amount"]
        lookup_platform = "alamy_sales"

    series = [(d, data[d].get((lookup_platform, k)))
              for d in dates
              for k in money_keys
              if (lookup_platform, k) in data[d]]
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
        # "flat" only means the rolling window isn't GROWING -- current can
        # still be a real nonzero lifetime balance (Adobe Stock sat at $3.18
        # for 5 straight days and this printed "no earnings yet", which reads
        # as zero when the platform has actually been paid). Say what's true:
        # a real balance not currently accruing, vs genuinely nothing.
        if f["current"]:
            return (f"{fmt(f['current'], True)} earned, not accruing this window",
                    f"$0/day over {f['window_days']}d")
        return ("no earnings yet — nothing to project",
                f"$0/day over {f['window_days']}d")
    d = f["days"]
    when = f"{d:.0f} days" if d < 400 else f"{d/365:.1f} years"
    return (f"~{when} (≈{f['eta']})", f"${f['rate']:.2f}/day")


def series_for(data, dates, platform, metric):
    """[(date, value)] for one metric, days with no reading omitted."""
    return [(d, data[d][(platform, metric)]) for d in dates
            if (platform, metric) in data[d]]


# ---- pattern mining -------------------------------------------------------
#
# Found 2026-09-09 going through the full snapshot history looking for
# anything worth acting on beyond the day's raw numbers. All three of these
# recompute from whatever history exists on each run rather than being
# written once and going stale -- see NEXT-SESSION.md for how each was
# first found and cross-checked before it was trusted.

def weekday_pattern(data, dates, platform, metric):
    """Average day-over-day change by weekday, from every consecutive-day
    pair in the whole history (gaps of >1 day are skipped -- a delta across
    a missed collection isn't comparable to a real single day).

    Needs at least one full week on both sides to say anything: a single
    Sunday reading is an anecdote, four Sundays in a row all reading zero is
    a pattern. Returns None rather than a shaky average from 2-3 points.
    """
    pts = series_for(data, dates, platform, metric)
    by_dow = defaultdict(list)
    for (d1, v1), (d2, v2) in zip(pts, pts[1:]):
        span = (datetime.date.fromisoformat(d2) - datetime.date.fromisoformat(d1)).days
        if span != 1:
            continue
        by_dow[datetime.date.fromisoformat(d2).weekday()].append(v2 - v1)
    if len(by_dow) < 7 or min(len(v) for v in by_dow.values()) < 2:
        return None
    return {dow: statistics.mean(vals) for dow, vals in by_dow.items()}


def getty_type_split(cur):
    """Accept-rate for editorial vs. creative Getty submissions, from
    today's snapshot. Requires the accepted_editorial/creative and
    rejected_editorial/creative metrics (added to collect_getty 2026-09-09);
    older snapshots won't have them, which is fine -- this only ever reads
    `cur`, today's row.
    """
    ae = cur.get(("getty", "accepted_editorial"))
    re_ = cur.get(("getty", "rejected_editorial"))
    ac = cur.get(("getty", "accepted_creative"))
    rc = cur.get(("getty", "rejected_creative"))
    if None in (ae, re_, ac, rc):
        return None
    de, dc = ae + re_, ac + rc
    if de < 10 or dc < 10:          # too few decided images either side to trust a rate
        return None
    return {"editorial_rate": ae / de * 100, "editorial_n": de,
            "creative_rate": ac / dc * 100, "creative_n": dc}


def portfolio_view_effect(data, dates, portfolio_platform, portfolio_metric,
                           view_platform, view_metric, min_jump=0.15, window=7):
    """Does adding inventory actually move traffic proportionally?

    Finds the most recent jump of at least `min_jump` (15% default) in the
    portfolio-size metric, then compares the weekday-only average daily
    change in the view metric for up to `window` weekdays immediately before
    vs. immediately after that jump. Weekends are excluded on both sides so
    a jump that happens to land near a weekend doesn't skew the comparison
    (see weekday_pattern -- Alamy views are ~0 on Sundays regardless of
    portfolio size).

    Returns None if there's no qualifying jump, or fewer than 3 weekdays of
    view data on either side -- a two-point comparison isn't a rate.
    """
    portfolio = series_for(data, dates, portfolio_platform, portfolio_metric)
    jump_at, jump_pct, jump_from, jump_to = None, None, None, None
    for (d1, v1), (d2, v2) in zip(portfolio, portfolio[1:]):
        if v1 and (v2 - v1) / v1 >= min_jump:
            jump_at, jump_pct, jump_from, jump_to = d2, (v2 - v1) / v1 * 100, v1, v2
    if not jump_at:
        return None

    views = dict(series_for(data, dates, view_platform, view_metric))
    vdates = sorted(views)
    jd = datetime.date.fromisoformat(jump_at)

    def weekday_daily_deltas(side):
        out = []
        for d1, d2 in zip(vdates, vdates[1:]):
            dd1, dd2 = datetime.date.fromisoformat(d1), datetime.date.fromisoformat(d2)
            if (dd2 - dd1).days != 1 or dd2.weekday() >= 5:
                continue
            if side == "before" and dd2 < jd:
                out.append(views[d2] - views[d1])
            elif side == "after" and dd1 >= jd:
                out.append(views[d2] - views[d1])
        return out

    before, after = weekday_daily_deltas("before")[-window:], weekday_daily_deltas("after")[:window]
    if len(before) < 3 or len(after) < 3:
        return None
    return {"jump_date": jump_at, "jump_pct": jump_pct,
            "portfolio_before": jump_from, "portfolio_after": jump_to,
            "rate_before": statistics.mean(before), "rate_after": statistics.mean(after),
            "n_before": len(before), "n_after": len(after)}


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


PLATFORM_COLORS = ["#7c5cff", "#3fb950", "#f2b134", "#4fc3f7",
                   "#ff8a65", "#ba68c8", "#4db6ac", "#f85149"]


def monthly_chart(months, proj=None, w=640, h=230):
    """Stacked bar per historical month (one segment per platform, colour
    stable across months), plus a lighter min/median/max range bar per
    projected future month. Returns (svg, legend_html).
    """
    if not months:
        return '<div class="tiny">no data</div>', ""
    all_platforms = []
    for _, _, breakdown in months:
        for p in breakdown:
            if p not in all_platforms:
                all_platforms.append(p)
    color = {p: PLATFORM_COLORS[i % len(PLATFORM_COLORS)] for i, p in enumerate(all_platforms)}

    fut = proj["future"] if proj else []
    max_y = max([t for _, t, _ in months] + [hi for _, _lo, _mid, hi in fut] + [1.0])
    pad_l, pad_b, pad_t, pad_r = 4, 22, 20, 8
    n = len(months) + len(fut)
    slot = (w - pad_l - pad_r) / max(n, 1)
    bar_w = slot * 0.62
    plot_h = h - pad_b - pad_t

    def y_of(v):
        return pad_t + plot_h - (v / max_y * plot_h if max_y else 0.0)

    y0 = y_of(0.0)
    parts = [f'<line x1="{pad_l}" y1="{y0:.1f}" x2="{w - pad_r}" y2="{y0:.1f}" class="gridline"/>',
             f'<text x="{pad_l}" y="{pad_t - 6}" class="axislabel">{fmt(max_y, True)}</text>']

    x = pad_l + (slot - bar_w) / 2
    for label, total, breakdown in months:
        # stack segments cumulatively from the baseline up
        running = 0.0
        for p in all_platforms:
            amt = breakdown.get(p, 0.0)
            if amt <= 0:
                continue
            y_bottom = y_of(running)
            y_top = y_of(running + amt)
            parts.append(f'<rect x="{x:.1f}" y="{y_top:.1f}" width="{bar_w:.1f}" '
                         f'height="{(y_bottom - y_top):.1f}" fill="{color[p]}"/>')
            running += amt
        if total > 0:
            parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{y_of(total) - 5:.1f}" '
                         f'class="barval" text-anchor="middle">{fmt(total, True)}</text>')
        parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{h - 6}" class="axislabel" '
                     f'text-anchor="middle">{html.escape(label[5:])}</text>')
        x += slot

    for flabel, lo, mid, hi in fut:
        y_lo, y_hi, y_mid = y_of(lo), y_of(hi), y_of(mid)
        parts.append(f'<rect x="{x:.1f}" y="{y_hi:.1f}" width="{bar_w:.1f}" '
                     f'height="{max(0.0, y_lo - y_hi):.1f}" class="projband"/>')
        parts.append(f'<line x1="{x:.1f}" y1="{y_mid:.1f}" x2="{x + bar_w:.1f}" '
                     f'y2="{y_mid:.1f}" class="projmid"/>')
        parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{h - 6}" class="axislabel" '
                     f'text-anchor="middle">{html.escape(flabel[5:])}?</text>')
        x += slot

    legend = "".join(f'<span class="legendswatch" style="background:{color[p]}"></span>'
                     f'{html.escape(p)}' for p in all_platforms)
    svg = f'<svg viewBox="0 0 {w} {h}" class="monthlychart">' + "".join(parts) + "</svg>"
    return svg, legend


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
    # See platform_money_asof() for the carry-forward/alamy-dedup logic --
    # extracted so monthly_revenue() below can ask the same question ("what
    # did the money look like as of date X") for every past month-end
    # without re-deriving this.
    total_money, total_sales, money_rows = platform_money_asof(data, dates, today)
    months = monthly_revenue(data, dates)
    monthly_proj = project_monthly(months, horizon=3)
    monthly_svg, monthly_legend = monthly_chart(months, monthly_proj)

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
        if p in SKIP_ROW:
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
                caveat = CHART_CAVEAT.get(m, "")
                cards.append(f'''<div class="chart"><h4>{html.escape(label)}
                  <span class="tiny">{html.escape(m.replace("_"," "))}</span></h4>
                  {spark(pts, pr)}
                  <div class="tiny">range {pr["lo"]:+.1f} to {pr["hi"]:+.1f}/day</div>
                  {f'<div class="tiny caveat">{html.escape(caveat)}</div>' if caveat else ""}
                  </div>''')
        if not cards:
            return ('<div class="card"><div class="tiny">Not enough history to chart yet. '
                    'Charts appear once a metric has two or more readings.</div></div>')
        return '<div class="charts">' + "".join(cards) + "</div>"

    def patterns_section():
        """Things found by mining the full history, not just today's row.
        Each card only renders once its underlying check has enough data to
        say something real -- see the functions themselves for the bar."""
        cards = []

        wk = weekday_pattern(data, dates, "alamy_measures", "views")
        if wk:
            weekday_avg = statistics.mean(wk[d] for d in range(5))
            weekend_avg = statistics.mean(wk[d] for d in (5, 6))
            bars = "".join(
                f'<div class="dowbar"><div class="dowfill" style="height:{max(2, wk[i]/max(wk.values())*100):.0f}%"></div>'
                f'<span class="dowl">{DOW_ABBR[i]}</span><span class="dowv">{wk[i]:+.1f}</span></div>'
                for i in range(7))
            verdict = (f"Weekend view growth runs {weekend_avg/weekday_avg*100:.0f}% of the weekday rate"
                       if weekday_avg else "weekday rate is flat too")
            cards.append(f'''<div class="pattern"><h4>Alamy views go quiet on weekends</h4>
              <div class="dowchart">{bars}</div>
              <div class="tiny">Average daily change in cumulative views, by day of week, across all history.
              {html.escape(verdict)} -- buyers here read like a weekday, B2B audience.
              Consider timing new-batch submissions for Wed/Thu so they're freshly indexed
              going into the Thu/Fri peak rather than sitting over a weekend.</div></div>''')

        gt = getty_type_split(cur)
        if gt:
            gap = gt["creative_rate"] - gt["editorial_rate"]
            cards.append(f'''<div class="pattern"><h4>Getty: creative clears review far more than editorial</h4>
              <div class="splitbar">
                <div class="splitrow"><span>Creative</span>
                  <div class="bar"><span style="width:{gt['creative_rate']:.1f}%"></span></div>
                  <b>{gt['creative_rate']:.0f}%</b><span class="tiny">(n={gt['creative_n']})</span></div>
                <div class="splitrow"><span>Editorial</span>
                  <div class="bar down"><span style="width:{gt['editorial_rate']:.1f}%"></span></div>
                  <b>{gt['editorial_rate']:.0f}%</b><span class="tiny">(n={gt['editorial_n']})</span></div>
              </div>
              <div class="tiny">Acceptance rate of decided images, by actual submission type (not batch name --
              a getty-batch.py bug fixed 2026-09-06 had some batches named "commercial" actually submit as
              editorial). A {gap:.0f}-point gap this size, over {gt['creative_n']+gt['editorial_n']} decided
              images, is a real editorial-quality problem, not noise -- editorial's release-free advantage
              is only worth it if the newsworthiness/caption bar is being met.</div></div>''')

        pv = portfolio_view_effect(data, dates, "alamy_qc", "passed",
                                    "alamy_measures", "views")
        if pv:
            change = pv["rate_after"] / pv["rate_before"] - 1 if pv["rate_before"] else None
            verdict = (f"view growth only moved {change:+.0%}" if change is not None
                       else "view growth didn't move")
            cards.append(f'''<div class="pattern"><h4>More images didn't mean proportionally more views</h4>
              <div class="tiny">
              Portfolio grew {pv['jump_pct']:.0f}% ({fmt(pv['portfolio_before'])} &rarr; {fmt(pv['portfolio_after'])}
              images) on {pv['jump_date']}, but the weekday-only average daily view growth went from
              {pv['rate_before']:+.1f}/day (n={pv['n_before']}) to {pv['rate_after']:+.1f}/day (n={pv['n_after']}) --
              {html.escape(verdict)}. Early signal, small sample -- but consistent with search ranking caring
              more about keyword/category relevance and image age than raw catalog size.</div></div>''')

        if not cards:
            return ('<div class="card"><div class="tiny">Not enough history yet for pattern detection -- '
                    'each check needs at least 1-2 weeks of data to tell a real pattern from noise.</div></div>')
        return '<div class="patterns">' + "".join(cards) + "</div>"

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
 .monthlychart{{width:100%;height:230px;display:block}}
 .monthlychart .gridline{{stroke:var(--line);stroke-width:1}}
 .monthlychart .axislabel{{fill:var(--dim);font-size:10px}}
 .monthlychart .barval{{fill:var(--fg);font-size:10.5px;font-variant-numeric:tabular-nums}}
 .monthlychart .projband{{fill:var(--accent);opacity:.18}}
 .monthlychart .projmid{{stroke:var(--accent);stroke-width:1.4;stroke-dasharray:4 3}}
 .legend{{display:flex;flex-wrap:wrap;gap:12px;margin-top:10px;font-size:12px;color:var(--dim)}}
 .legendswatch{{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px;vertical-align:middle}}
 .evs{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px;margin-bottom:16px}}
 .ev{{display:flex;gap:13px;align-items:flex-start;background:var(--card);border:1px solid var(--line);
   border-left:4px solid var(--line);border-radius:12px;padding:13px 15px}}
 .ev.bad{{border-left-color:var(--down)}} .ev.good{{border-left-color:var(--up)}}
 .ev.neutral{{border-left-color:var(--dim)}}
 .evn{{font-size:22px;font-weight:650;font-variant-numeric:tabular-nums;line-height:1.1;min-width:44px}}
 .ev.bad .evn{{color:var(--down)}} .ev.good .evn{{color:var(--up)}}
 .evl{{font-size:13px;line-height:1.45}}
 h3.dt{{font-size:12px;color:var(--dim);margin:18px 0 8px;letter-spacing:.06em}}
 .caveat{{font-style:italic}}
 .patterns{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:14px}}
 .pattern{{background:var(--card);border:1px solid var(--accent);border-radius:14px;padding:16px 18px}}
 .pattern h4{{margin:0 0 10px;font-size:14px}}
 .dowchart{{display:flex;gap:6px;align-items:flex-end;height:70px;margin-bottom:8px}}
 .dowbar{{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%}}
 .dowfill{{width:100%;background:var(--accent);border-radius:3px 3px 0 0;min-height:2px}}
 .dowl{{font-size:10px;color:var(--dim);margin-top:4px}}
 .dowv{{font-size:9.5px;color:var(--dim)}}
 .splitbar{{display:flex;flex-direction:column;gap:8px;margin-bottom:8px}}
 .splitrow{{display:flex;align-items:center;gap:10px;font-size:13px}}
 .splitrow span:first-child{{width:58px;color:var(--dim)}}
 .splitrow .bar{{flex:1}}
 .splitrow .bar.down span{{background:var(--down)}}
 .splitrow b{{width:36px;text-align:right}}
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

<h2>Monthly revenue</h2>
<div class="sub">Not MRR — nothing here is a subscription that recurs on its own; this is
one-off royalty payments from every platform, bucketed by calendar month. The last bar
is {today[:7]} "so far," not a full month. Projected months (marked with "?") are a
min/median/max range built from real month-over-month changes, not a model fit to the
data: below 2 months there's nothing to project from at all; at exactly 2 months
there's exactly one change to go on, so the range collapses to a single line rather
than a spread; from 3 months on it starts actually showing the real spread between the
best and worst month-over-month change seen so far. That width is the honest answer,
not a defect to smooth over.</div>
{monthly_svg}
<div class="legend">{monthly_legend}</div>

<h2>Patterns &amp; signals</h2>\n{patterns_section()}

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
