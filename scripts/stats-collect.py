#!/usr/bin/env python3
"""Collect daily stats from every photo-licensing platform into one history file.

None of these platforms offer a public API, so this drives a saved browser
session. It uses a DEDICATED Chrome profile (~/.photo-automation-chrome) so it never
conflicts with the upload profiles or your everyday browser.

SETUP (once)
  scripts/stats-collect.py --login
    ...opens a visible browser. Sign in to Fine Art America, Adobe Stock,
    Alamy, Shutterstock, Getty ESP, 123RF and Depositphotos in that window,
    then close it. Sessions persist for months.

USAGE
  scripts/stats-collect.py              # collect once, update dashboard
  scripts/stats-collect.py --show       # print the latest numbers
  scripts/stats-collect.py --login      # sign in to everything at once, up front

Each platform is collected independently: one expired login degrades that row
to "stale", it does not abort the run.

AUTO-LOGIN FALLBACK (on by default)
When a platform reports a dead session or a solvable anti-bot challenge --
never for a slow render or a genuine platform problem -- this brings that
platform's page to the front of a visible Chrome window and waits (default
180s/platform) for you to sign in or clear the challenge yourself, then
retries automatically and folds the result in as if it had worked the first
time. Nothing is solved on your behalf; it only puts the right page in front
of you at the right moment instead of failing and asking you to re-run.
Needs a headed browser to have a window to show, so it forces one on whenever
enabled -- pass --no-auto-login for the old fail-fast, always-headless behavior.
"""
import argparse, json, os, re, sys, time, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "photo-licensing-workspace" / "stats"
HISTORY = OUT / "history.json"
ANALYTICS = ROOT / "photo-licensing-workspace" / "analytics"
SNAPSHOTS = ANALYTICS / "snapshots.csv"      # tidy long format, like TikTok's growth.csv
PROFILE = Path.home() / ".photo-automation-chrome"

# What each platform pays and what it withholds until you cross the threshold.
# Money is the point of the dashboard, so this lives next to the collectors.
ECONOMICS = {
    "fineartamerica": {"royalty": "your markup over base", "payout_min": None},
    "adobe_stock":    {"royalty": "33% flat",              "payout_min": 25},
    "shutterstock":   {"royalty": "15-40% tiered",         "payout_min": 25},
    "alamy":          {"royalty": "15-40% tiered",         "payout_min": 75},
    "dreamstime":     {"royalty": "25-50%",                "payout_min": 100},
    "getty":          {"royalty": "15% non-exclusive",     "payout_min": 100},
    "123rf":          {"royalty": "30-60% tiered",         "payout_min": 50},
    "depositphotos":  {"royalty": "30-38%; subs $0.25-0.33", "payout_min": 25},
    "etsy":           {"royalty": "price less 6.5% + 3% + $0.25", "payout_min": None},
}

# Metrics that represent money, so the dashboard can total them.
MONEY_KEYS = {"balance", "earnings", "revenue", "sales_30d", "available_earnings"}
SALES_KEYS = {"sales", "sales_to_date", "downloads"}


# Adobe (and Google) refuse sign-in from a browser advertising automation.
# Dropping the automation switches makes this an ordinary Chrome window.
STEALTH = {
    "ignore_default_args": ["--enable-automation"],
    "args": [
        "--disable-blink-features=AutomationControlled",
        "--no-default-browser-check",
        "--no-first-run",
    ],
}


def load_history():
    if HISTORY.exists():
        return json.loads(HISTORY.read_text())
    return []


def money(s):
    m = re.search(r"\$\s*([\d,]+\.?\d*)", s or "")
    return float(m.group(1).replace(",", "")) if m else None


def num(s):
    """First number in s. Int when it is whole, float when it has decimals.

    This used to match only [\\d,]+ and so stopped dead at the decimal point:
    num("$0.20") returned 0. Every balance below a dollar therefore read as
    zero, and Shutterstock's first two downloads (2026-08-10 and 2026-08-14)
    were recorded as $0 revenue. Cents matter here precisely because the
    numbers are small -- a payout forecast built on truncated pennies would
    never move off "no earnings yet".

    Counts stay ints so 482 does not become 482.0 in the CSV.
    """
    m = re.search(r"([\d,]+(?:\.\d+)?)", s or "")
    if not m:
        return None
    raw = m.group(1).replace(",", "")
    return float(raw) if "." in raw else int(raw)


# --- per-platform collectors -------------------------------------------------

def collect_faa(page):
    page.goto("https://fineartamerica.com/controlpanel/main", wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    if "login" in page.url.lower() or "signin" in page.url.lower():
        raise RuntimeError("not signed in")
    # FAA renders each tile as LABEL, blank lines, then the value -- so match
    # across whitespace rather than expecting the value on the next line.
    # /controlpanel/main now redirects to the heavier /controlpanel/analytics
    # page, whose tiles render async -- a fixed 5s wait sometimes beat the
    # numbers there, scraping blank labels and reporting a false "not signed
    # in" (2026-09-20). Poll for VISITORS actually landing before reading.
    body = page.inner_text("body")
    for _ in range(5):
        if re.search(r"\bVISITORS\b\s+[\$\d,\.]+", body):
            break
        page.wait_for_timeout(2000)
        body = page.inner_text("body")
    def tile(label):
        m = re.search(rf"\b{label}\b\s+([\$\d,\.]+)", body)
        return m.group(1) if m else None
    return {
        "sales_30d": money(tile("SALES")),
        "balance": money(tile("BALANCE")),
        "visitors_7d": num(tile("VISITORS")),
        "comments_7d": num(tile("COMMENTS")),
        "favorites_7d": num(tile("FAVORITES")),
        "followers": num(tile("FOLLOWERS")),
    }


# Each uploads tab is its own URL and prints its size as "File types: All (N)".
# Nothing carries a count in the tab label, so they must be visited.
ADOBE_TABS = (("", "pending_new"),               # "New" = uploaded, NOT submitted
              ("/review", "in_review"),
              ("/reminder", "reminder"),
              ("/rejected", "not_accepted"),
              ("/logs/failure", "upload_issues"))


def collect_adobe(page):
    """Portfolio pipeline plus sales.

    Until 2026-08-17 this reported exactly one number, pending_new, frozen at
    50 for a week -- and the freeze was real, not a scrape bug: those 50 files
    are sitting in the "New" tab, uploaded but NEVER SUBMITTED for review. Only
    6 were ever submitted (1 in review, 5 not accepted). A single unchanging
    figure hid that completely.

    The old Downloads/Revenue/Views/Earnings patterns never matched anything.
    Those words are options in the Insights page's "Select Data type" dropdown,
    not printed values, so the regexes silently found nothing and the money
    keys were simply absent every day rather than reported as zero.
    """
    page.goto("https://contributor.stock.adobe.com/en/insights", wait_until="domcontentloaded")
    page.wait_for_timeout(8000)
    if "auth" in page.url or "signin" in page.url.lower():
        raise RuntimeError("not signed in")
    stats = {}
    # MONEY COMES FROM THE DASHBOARD, NOT INSIGHTS.
    # Insights only prints "You have no sales activity" until the first sale;
    # after that it shows a chart whose axis labels (Downloads, Earnings, ...)
    # are DROPDOWN OPTIONS, not values. So once Adobe actually started earning
    # on 2026-08-20 the old branch stopped matching, the fallback patterns
    # matched nothing, and the balance key simply vanished from the CSV --
    # $2.19 of real revenue reported as no data at all.
    # /en/portfolio prints the figures as plain label-then-value tiles.
    page.goto("https://contributor.stock.adobe.com/en/portfolio", wait_until="domcontentloaded")
    page.wait_for_timeout(9000)
    dash = re.sub(r"[ \t]+", " ", page.inner_text("body"))
    for label, key in (("DOWNLOADS", "downloads"), ("EARNINGS", "balance"),
                       ("AVAILABLE EARNINGS", "available_earnings")):
        m = re.search(rf"^{label}\s*\n\s*\$?([\d,]+\.?\d*)\s*$", dash, re.M)
        if m:
            stats[key] = num(m.group(1))
    # A dash means Adobe has nothing to report yet, which is a real zero.
    if "downloads" not in stats and re.search(r"^DOWNLOADS\s*\n\s*-\s*$", dash, re.M):
        stats["downloads"] = 0
        stats["balance"] = 0.0

    for suffix, key in ADOBE_TABS:
        page.goto(f"https://contributor.stock.adobe.com/en/uploads{suffix}",
                  wait_until="domcontentloaded")
        page.wait_for_timeout(6000)
        # A slow-rendering tab here used to raise out of the whole function,
        # throwing away the DOWNLOADS/EARNINGS/AVAILABLE EARNINGS already
        # scraped above (2026-09-20: one timed-out "review" tab lost a day's
        # real balance). One flaky tab should cost that tab's count, not
        # everything already gathered.
        try:
            body = page.inner_text("body", timeout=45_000)
        except Exception:
            stats[key] = None
            continue
        m = re.search(r"File types:\s*All\s*\((\d+)\)", body)
        stats[key] = int(m.group(1)) if m else None
    return stats


def collect_alamy(page):
    # mydashboard.aspx 404s -- the contributor dashboard is myalamy-aim.aspx.
    page.goto("https://www.alamy.com/myalamy-aim.aspx", wait_until="domcontentloaded")
    page.wait_for_timeout(7000)
    body = page.inner_text("body")
    if bot_challenged(body):
        raise RuntimeError("blocked by anti-bot human check — collect manually")
    if not re.search(r"dashboard|Cleared Balance|Logout", body, re.I):
        raise RuntimeError("not signed in")
    def after(label):
        m = re.search(rf"(\d[\d,]*)\s*\n\s*{label}", body, re.I)
        return num(m.group(1)) if m else None
    bal = re.search(r"Current Cleared Balance:\s*(\$[\d,\.]+)", body)
    sales = re.search(r"(\d[\d,]*)\s*sales to date", body)
    return {
        "balance": money(bal.group(1)) if bal else None,
        "sales_to_date": num(sales.group(1)) if sales else None,
        "on_sale_good": after("Images on sale with good or optimized discoverability"),
        "on_sale_poor": after("Images on sale with poor discoverability"),
        "not_on_sale": after("Images not on sale"),
    }


def collect_alamy_qc(page):
    """QC/pipeline state, which the dashboard doesn't show. Alamy locks images
    while 'In QC', so this is what tells us when the supertag work can start."""
    page.goto("https://www.alamy.com/myupload/Index.aspx", wait_until="domcontentloaded")
    page.wait_for_timeout(8000)
    t = page.inner_text("body")
    # Each submission in the sidebar prints its own "Passed: N" / "Failed: N" /
    # "In QC: N" line. re.search grabbed only the FIRST one (today's newest
    # submission, since the list sorts newest-first) and silently reported it
    # as the portfolio total -- caught 2026-09-04 when a fresh 285-image
    # resubmit made "passed" read as 285 right after 565 other images had
    # already passed weeks earlier. Sum every match, same fix Getty's
    # collector already uses for its per-batch breakdown.
    def total(label):
        hits = re.findall(rf"{label}:\s*(\d[\d,]*)", t, re.I)
        return sum(num(h) for h in hits) if hits else None
    # The top-of-page "Images: N" summary line is the true aggregate and comes
    # before any per-submission breakdown, so first-match is correct here --
    # summing would double-count every submission's own "Images: N" too.
    m = re.search(r"Images:\s*(\d[\d,]*)", t, re.I)
    return {"total_images": num(m.group(1)) if m else None,
            "in_qc": total("In QC"),
            "passed": total("Passed"),
            "failed": total("Failed")}


def bot_challenged(text):
    """Detect an anti-bot interstitial. These must be surfaced, never worked
    around -- solving one would be circumventing a site's access controls."""
    return bool(re.search(r"press & hold|press and hold|confirm you are\s+a?\s*human|"
                          r"are you a robot|unusual traffic", text, re.I))


def collect_alamy_measures(page):
    """Views, zooms and CTR -- the leading indicators before any sale.

    Alamy's own definitions: a VIEW is your thumbnail appearing in a page of
    search results; a ZOOM is a customer clicking it to see the larger preview.
    Zooms matter far more than views -- someone examining an image closely is
    the closest thing to buying intent this data offers.
    """
    page.goto("https://www.alamy.com/Alamysearchhistory/contributorsearch.aspx",
              wait_until="domcontentloaded")
    page.wait_for_timeout(11000)
    t = re.sub(r"[ \t]+", " ", page.inner_text("body"))
    if bot_challenged(t):
        raise RuntimeError("blocked by anti-bot human check — collect manually")
    if "Pseudonym Summary" not in t:
        raise RuntimeError("not signed in")
    def g(pat):
        m = re.search(pat, t, re.I)
        return float(m.group(1).replace(",", "")) if m else None
    return {"views": g(r"Total Views for [^:]+:\s*([\d,]+)"),
            "zooms": g(r"Total Zooms for [^:]+:\s*([\d,]+)"),
            "ctr": g(r"Average CTR for [^:]+:\s*([\d.]+)")}


def collect_alamy_sales(page):
    """Real per-sale dollar amounts from Alamy's own sales-history report --
    added 2026-09-13 after Ben checked this page by hand and found a $6.66
    sale (the page's own header rounds it to "$7") that collect_alamy()'s
    dashboard scrape had missed entirely: that scrape reads "Current Cleared
    Balance", which stays $0 until Alamy actually pays out, not the moment a
    sale happens. This is the earlier, truer signal.

    Deliberately its own metric names (lifetime_sales_amount / sales_count),
    NOT "balance" -- MONEY_KEYS-driven totals elsewhere (the dashboard's
    combined "$X total balance" card) look up "balance" per platform, and
    "alamy" already owns that key for its cleared-balance figure. Writing
    the same money under a second name here would double-count it the day
    Alamy's cleared balance finally catches up to a sale already counted
    here.

    #drpPeriod defaults to the current month; select "All" or the summary
    silently reports June's-worth of sales as if it were everything.
    """
    page.goto("https://www.alamy.com/alamycontributorreports/Reports.aspx?Rep=0",
              wait_until="domcontentloaded")
    page.wait_for_timeout(7000)
    if "login" in page.url.lower() or "signin" in page.url.lower():
        raise RuntimeError("not signed in")
    t0 = page.inner_text("body")
    if "Sales history" not in t0:
        raise RuntimeError("sales history page didn't render")
    page.select_option("#drpPeriod", label="All")
    page.wait_for_timeout(4000)
    t = re.sub(r"[ \t]+", " ", page.inner_text("body"))
    out = {}
    # The "Sales to date: $X" header rounds to whole dollars ($6.66 -> "$7").
    # With the period forced to All, the itemized summary line covers the
    # exact same lifetime range but keeps the cents -- prefer it, and only
    # fall back to the rounded header if that line is somehow missing.
    m = re.search(r"\(\s*(\d+)\s*item\(s\)\s*totalling\s*\$\s*([\d,]+\.?\d*)\s*\)", t)
    if m:
        out["sales_count"] = int(m.group(1))
        out["lifetime_sales_amount"] = num(m.group(2))
    else:
        m = re.search(r"Sales to date:\s*\$\s*([\d,]+\.?\d*)", t)
        if m:
            out["lifetime_sales_amount"] = num(m.group(1))
    return out


def collect_dreamstime(page):
    """Public contributor profile carries the accepted count and sales; the
    upload area carries the pipeline. Refused count matters most day to day.

    NOTE 2026-08-08: Dreamstime now serves a press-and-hold human check to this
    browser profile in both headless and headed mode, so it cannot be collected
    automatically. Check it by hand until the challenge clears.
    """
    page.goto("https://www.dreamstime.com/benampel_info", wait_until="domcontentloaded")
    page.wait_for_timeout(6000)
    t = page.inner_text("body")
    if bot_challenged(t):
        raise RuntimeError("blocked by anti-bot human check — collect manually")
    def g(pat):
        m = re.search(pat, t, re.I)
        return m.group(1).strip() if m else None
    out = {"accepted_live": num(g(r"Uploaded files:\s*\n?\s*([\d,]+)")),
           "sales": num(g(r"Total sales:\s*\n?\s*([\d,]+)")),
           "downloads_per_image": g(r"Downloads per image:\s*\n?\s*([\d.]+)")}
    # exposure = share of Dreamstime searches your portfolio appears in.
    # The closest thing they publish to an impressions metric.
    for lbl, key in (("Portfolio exposure", "portfolio_exposure_pct"),
                     ("Database exposure", "database_exposure_pct")):
        m = re.search(rf"{lbl}:?\s*\n?\s*([\d.]+)\s*%", t, re.I)
        if m:
            out[key] = float(m.group(1))
    page.goto("https://www.dreamstime.com/upload/refused-files", wait_until="domcontentloaded")
    page.wait_for_timeout(6000)
    lab = page.inner_text("body")
    m = re.search(r"(\d+) of (\d+) pages", lab)
    out["refused_pages"] = int(m.group(2)) if m else None

    # The signed-in dashboard is the only place the MONEY appears. The public
    # profile above carries the sales COUNT but never the balance, which is why
    # the first two sales (2026-08-14, $0.35 each) showed up as "sales 2" with
    # no earnings figure and the payout forecast stayed silent.
    #
    # Wrapped in try/except on purpose: Dreamstime's press-and-hold check is
    # intermittent, and a block here must not throw away the profile numbers
    # already collected above.
    try:
        page.goto("https://www.dreamstime.com/account", wait_until="domcontentloaded")
        page.wait_for_timeout(6000)
        d = page.inner_text("body")
        if not bot_challenged(d):
            def dash(label):
                m = re.search(rf"{label}\s*\n?\s*\$?\s*([\d,]+\.?\d*)", d, re.I)
                return num(m.group(1)) if m else None
            for label, key in (("CURRENT EARNINGS", "balance"),
                               ("ONLINE FILES", "online_files"),
                               ("PENDING FILES", "pending"),
                               ("REFUSED FILES", "refused")):
                v = dash(label)
                if v is not None:
                    out[key] = v
    except Exception:
        pass
    return out


def collect_shutterstock(page):
    """Pipeline tabs plus the money.

    The money was missing entirely until 2026-08-17: this only ever read the
    portfolio tabs, so two real downloads (2026-08-10 and 2026-08-14, $0.10
    each) sat uncollected while the dashboard reported Shutterstock as $0.

    "Correction needed" is the tab that explains the backlog and it was also
    never read. Those images are not stuck at random -- Shutterstock rejected
    them for COMMERCIAL use and is offering editorial instead, which needs a
    caption carrying day, month, year and location.
    """
    page.goto("https://submit.shutterstock.com/portfolio/pending/photo", wait_until="domcontentloaded")
    # Wait for the tab counts to actually render rather than sleeping a fixed
    # 8s. The portfolio got heavier as the editorial backlog moved into Pending
    # (38 -> 263 on 2026-08-17) and the fixed wait started expiring, which
    # surfaced as "no numeric fields scraped" on a page that was perfectly fine.
    #
    # A 2-attempt/60s budget still missed 3 of 4 days the week of 2026-08-24,
    # even though a standalone check outside the full run always rendered in
    # 6-10s -- session valid, page fine, tabs present. Something about running
    # after the other collectors makes THIS run slower than a fresh one; cause
    # unconfirmed (candidate: memory/tab pressure from Alamy's heavy grid
    # collector running first), so this widens the budget rather than asserting
    # a fix. If it still misses at 4 attempts, that guess is wrong.
    t = ""
    for attempt in (1, 2, 3, 4):
        for _ in range(12):
            page.wait_for_timeout(2500)
            t = page.inner_text("body")
            if re.search(r"Not submitted \(\d+\)", t):
                break
        if re.search(r"Not submitted \(\d+\)", t):
            break
        if "sign in" in t.lower()[:300]:
            raise RuntimeError("not signed in")
        if attempt < 4:
            page.reload(wait_until="domcontentloaded")
    if "sign in" in t.lower()[:300]:
        raise RuntimeError("not signed in")
    if not re.search(r"Not submitted \(\d+\)", t):
        raise RuntimeError("portfolio tabs never rendered after reload "
                           "(page slow or layout changed) — session looks valid")
    def g(label):
        m = re.search(rf"{label} \((\d+)\)", t)
        return int(m.group(1)) if m else None
    out = {"not_submitted": g("Not submitted"), "pending": g("Pending"),
           "recently_reviewed": g("Recently reviewed"),
           "marketplace_catalog": g("Marketplace catalog"),
           # The tab DISAPPEARS once the backlog is cleared rather than showing
           # (0) -- it went from 251 to absent on 2026-08-21 when the editorial
           # resubmissions were reviewed. Absent means none outstanding, which
           # is a real zero, not unknown.
           "correction_needed": g("Correction needed") or 0}

    page.goto("https://submit.shutterstock.com/earnings", wait_until="domcontentloaded")
    page.wait_for_timeout(9000)
    e = re.sub(r"[ \t]+", " ", page.inner_text("body"))
    # "Total earnings" and "Total downloads" are label-then-value on their own
    # lines; the header's "UNPAID EARNINGS: $x" is a separate running figure.
    m = re.search(r"Total earnings\s*\n?\s*\$?([\d,]+\.?\d*)", e, re.I)
    if m:
        out["balance"] = num(m.group(1))
    m = re.search(r"Total downloads\s*\n?\s*([\d,]+)", e, re.I)
    if m:
        out["downloads"] = num(m.group(1))
    return out


def collect_getty(page):
    """Getty accepted us 2026-08-08. Content lives in ESP, not on the marketing
    site: contributors.gettyimages.com is PUBLIC and says "Contributor" and
    "Upload" whether or not you're signed in, so checking it reported a healthy
    session for an account that wasn't logged in at all. Only esp.gettyimages.com
    proves the session and carries the batch counts.

    REBUILT 2026-09-18: Getty replaced the whole ESP batches UI with a MUI SPA
    that no longer renders per-batch Accepted/Rejected/In review text anywhere
    -- the old text-scraping approach (walk paginated HTML, split blocks on
    "More details", regex out labelled counts) had nothing left to scrape and
    started silently returning None/0 for everything. The SPA turned out to
    be backed by a clean JSON API the whole time
    (api/submission/v1/submission_batches), found by sniffing this page's own
    network requests. Calling it directly via page.request (which reuses the
    page's auth cookies) replaces ~110 lines of pagination/regex/block-
    splitting with one HTTP call and a few sums -- no scrolling, no "is this
    digit a real count or a stray status badge" guessing, no page-count math.
    """
    page.goto("https://esp.gettyimages.com/contribute/batches",
              wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(4000)
    if bot_challenged(page.inner_text("body")):
        raise RuntimeError("blocked by anti-bot human check — collect manually")
    if "sign-in" in page.url:
        raise RuntimeError("not signed in to ESP")

    resp = page.request.get(
        "https://esp.gettyimages.com/api/submission/v1/submission_batches"
        "?page_size=50&page=1&sort_column=created_at&sort_order=Descending")
    if resp.status != 200:
        raise RuntimeError(f"submission_batches API returned {resp.status}")
    items = resp.json().get("items", [])
    # A submission with contributions_count 0 is an empty scratch/test batch
    # (e.g. one literally named "country-test" sitting in this account) --
    # it carries no real review activity and would just be noise in the count.
    items = [it for it in items if it.get("contributions_count")]
    if not items:
        raise RuntimeError("no batches with content returned — nothing to scrape")

    # processed_contributions_count IS the accepted count, not something to
    # derive -- verified against all 15 real batches 2026-09-18:
    # processed == reviewed - rejected in every single one, with zero
    # residual, so Getty is already handing this over as its own field.
    # pending_contributions_count is the modern equivalent of the old
    # "not submitted" bucket: files added to a batch but not yet sent for
    # review at all (distinct from awaiting_review, which HAS been submitted
    # and is just waiting its turn).
    def total(field):
        return sum(it.get(field) or 0 for it in items)

    out = {
        "accepted": total("processed_contributions_count"),
        "rejected": total("rejected_contributions_count"),
        "need_revisions": total("revisable_contributions_count"),
        "in_review": total("contributions_awaiting_review_count"),
        "not_submitted": total("pending_contributions_count"),
        "batches": len(items),
    }

    # submission_type ("istock_creative_still" / "istock_editorial_still" /
    # ...) is Getty's own classification, not a name we're pattern-matching --
    # strictly better than the old "purplelink commercial 4" text-sniffing,
    # which a 2026-09-06 getty-batch.py bug had already proven unreliable
    # (batches NAMED commercial that were actually created editorial).
    for it in items:
        typ = "creative" if "creative" in it.get("submission_type", "") else \
              "editorial" if "editorial" in it.get("submission_type", "") else None
        if not typ:
            continue
        out[f"accepted_{typ}"] = out.get(f"accepted_{typ}", 0) + (it.get("processed_contributions_count") or 0)
        out[f"rejected_{typ}"] = out.get(f"rejected_{typ}", 0) + (it.get("rejected_contributions_count") or 0)

    return out


def collect_getty_stats(page):
    """Real download activity from ESP's own Stats page -- added 2026-09-15
    after Ben found this page showed 10 real downloads across 9 assets while
    collect_getty()'s batch-review counts (accepted/rejected/in_review) never
    surfaced any of it. Same shape of gap as the Alamy dashboard hiding a
    real sale behind "cleared balance": collect_getty() only ever looked at
    SUBMISSION review status, never at what actually sells after acceptance.

    The dollar side of this (Account Management > Royalties) explicitly
    says "Royalties data will not be available until your first transaction
    has occurred. Please try again next month" -- Getty batches payout by
    statement month, so there is no per-sale dollar figure to read yet, only
    a download count. That still beats reporting zero activity that isn't
    zero. Revisit once a royalty statement actually posts.

    Deliberately its own platform/metric names, not "downloads" under
    "getty" -- collect_getty() doesn't currently write a "downloads" field,
    so there's no double-count risk today, but keeping this data under
    "getty_stats" instead keeps that true if that ever changes.

    REBUILT 2026-09-18, one day after it shipped: Getty redesigned this page
    too, in the same overhaul that broke collect_getty(). The old tabular
    row ("MasterID TotalDownloads <7 channel columns> MM/DD/YYYY Collection
    AssetType UsageType" all on one line) is gone, replaced by one
    label:value block per asset -- actually simpler to parse, once found. A
    JSON API backs this page too (statistics/downloads_for_search, sniffed
    from network traffic the same way submission_batches was), but its exact
    query parameters didn't reproduce cleanly outside the page's own request
    context; the rendered text is simple and reliable enough here that
    chasing the API further wasn't worth it.
    """
    page.goto("https://esp.gettyimages.com/contribute/stats"
              "?assetTypes=Photo%2CVideo%2CIllustration&primaryDatePeriod=past_24_months"
              "&page=1&pageSize=50&orderResultsBy=LastDownloadDate&sortDirection=Descending",
              wait_until="domcontentloaded")
    page.wait_for_timeout(9000)
    if bot_challenged(page.inner_text("body")):
        raise RuntimeError("blocked by anti-bot human check — collect manually")
    if "sign-in" in page.url or "Content statistics" not in page.inner_text("body"):
        raise RuntimeError("not signed in to ESP")
    t = page.inner_text("body")

    # Each asset is its own block:
    #   <master id>\nCollection: X\nAsset type: Y\nUsage type: Z\n
    #   Last download: MM/DD/YYYY\nTotal downloads: N
    rows = re.findall(
        r"(\d{6,})\s*\nCollection:.*?\nAsset type:.*?\nUsage type:.*?\n"
        r"Last download:\s*(\d{2}/\d{2}/\d{4})\s*\nTotal downloads:\s*(\d+)",
        t, re.S)
    # The same page renders as a TABLE when the window is wide:
    #   <master id> <total> <7 channel counts> MM/DD/YYYY <collection> ...
    # Only the card layout was parsed, so every day the window happened to be
    # wide read as 0 downloads (the 0 / 11 / 0 flip-flop, found 2026-09-23).
    if not rows:
        rows = [(mid, date, total) for mid, total, date in re.findall(
            r"^\s*(\d{6,})\s+(\d+)\s+(?:\d+\s+){7}(\d{2}/\d{2}/\d{4})", t, re.M)]
    shown = re.search(r"Showing\s+\d+\s*-\s*\d+\s+of\s+(\d+)", t)
    if shown and int(shown.group(1)) > 0 and not rows:
        raise RuntimeError(f"stats page lists {shown.group(1)} assets but none parsed (layout changed?)")
    out = {"assets_with_downloads": len(rows),
           "downloads_total": sum(int(r[2]) for r in rows)}
    if rows:
        out["last_download_date"] = max(rows, key=lambda r: datetime.datetime.strptime(r[1], "%m/%d/%Y"))[1]
    return out


def collect_123rf(page):
    """Pipeline counts plus lifetime money. Added 2026-09-10, the day 570
    images were FTP'd to ftp.123rf.com.

    Two pages, dashboard first -- it's also LOGIN_URLS["123rf"], the page the
    auto-login fallback opens for a human to sign in on. Visiting upload-
    history (a table of individual photo IDs/thumbnails, not a sign-in-
    friendly screen) first meant a retry after signing in on the dashboard
    immediately navigated away from it. Order swapped 2026-09-13; same two
    pages, same fields, dashboard just goes first now.

    Dashboard carries "Total Earnings $x" / "Total Downloads n" and the
    "Contributor Level N" badge. upload-history renders a table whose Photos
    row is "Photos <draft> <pending> <rejected> <approved>". The level
    matters: 123RF's FAQ gates full contributor status on ID verification
    plus an initial 10-image review, and at Level 0 the FTP'd files sat
    unprocessed (0/0/0/0) -- so a stuck all-zero row here is a real account
    state, not a scrape failure. Signed-out, 123RF bounces to a login page
    rather than rendering the contributor chrome, so the absence of
    "Contributor Level" is the sign-in check.
    """
    # The dashboard and upload-history redirect to the face/liveness check
    # (/contrib/account-settings/upload-id/) once per browser session, even
    # after it has been passed before; manage-content is not gated and shows
    # the same pipeline counts (2026-09-23). So a gated session still reports
    # counts, just not the dashboard's money figures, instead of prompting.
    def counts_from_manage_content():
        page.goto("https://www.123rf.com/contributor/manage-content", wait_until="domcontentloaded")
        # The tab counts fill in progressively. Requiring just two consecutive
        # equal reads was not enough: 2026-09-25 read PENDING=286 twice in a
        # row (a stalled intermediate render) while the true, stably-displayed
        # value was 577 -- confirmed by polling the live page afterward.
        # Three consecutive matches, spaced further apart, is what it took to
        # rule that false-stable case out.
        pat = r"DRAFT\s*(\d+)\s*PENDING\s*(\d+)\s*REJECTED\s*(\d+)\s*APPROVED\s*(\d+)"
        page.wait_for_timeout(5000)
        m, streak, prev = None, 0, None
        for _ in range(15):
            t = page.inner_text("body")
            if "login" in page.url.lower():
                raise RuntimeError("not signed in")
            m = re.search(pat, t)
            cur = m.groups() if m else None
            streak = streak + 1 if cur and cur == prev else (1 if cur else 0)
            if streak >= 3:
                break
            prev = cur
            page.wait_for_timeout(4000)
        if not m:
            raise RuntimeError("manage-content counts not found (layout changed?)")
        got = dict(draft=int(m.group(1)), pending=int(m.group(2)),
                   rejected=int(m.group(3)), approved=int(m.group(4)))
        lvl = re.search(r"Contributor Level (\d+)", t, re.I)
        if lvl:
            got["contributor_level"] = int(lvl.group(1))
        return got

    page.goto("https://www.123rf.com/contributor/dashboard", wait_until="domcontentloaded")
    page.wait_for_timeout(7000)
    if "upload-id" in page.url:
        return counts_from_manage_content()
    d = re.sub(r"[ \t]+", " ", page.inner_text("body"))
    if "login" in page.url.lower() or "Contributor Level" not in d:
        raise RuntimeError("not signed in")
    out = {}
    # Label-then-value on separate lines, same shape as Shutterstock's
    # earnings page; "Total Earnings" is lifetime, mapped to balance to match
    # how the Shutterstock collector already reports its lifetime total.
    m = re.search(r"Total Earnings\s*\n?\s*\$?([\d,]+\.?\d*)", d, re.I)
    if m:
        out["balance"] = num(m.group(1))
    m = re.search(r"Total Downloads\s*\n?\s*([\d,]+)", d, re.I)
    if m:
        out["downloads"] = num(m.group(1))
    m = re.search(r"Contributor Level (\d+)", d, re.I)
    if m:
        out["contributor_level"] = int(m.group(1))

    page.goto("https://www.123rf.com/contributor/upload-history", wait_until="domcontentloaded")
    page.wait_for_timeout(7000)
    if "upload-id" in page.url:
        out.update(counts_from_manage_content())
        return out
    t = re.sub(r"[ \t]+", " ", page.inner_text("body"))
    m = re.search(r"\bPhotos\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", t)
    if m:
        out.update(draft=int(m.group(1)), pending=int(m.group(2)),
                   rejected=int(m.group(3)), approved=int(m.group(4)))
    return out


def collect_depositphotos(page):
    """Seller's Menu counts, plus money once the account is out of examination.

    Added 2026-09-10. A brand-new Depositphotos seller is in an "Examination
    Test": every seller page (files, sales, request_earnings) redirects to
    files_menu_examination.html until the sample uploads are approved. The
    six pipeline counters still render on that page, so they are collected
    and examination_pending is set from the redirect. The sales page is only
    parsed when it actually loads -- while the redirect is in force there is
    simply no money to read, which is a real zero and not an error.
    """
    page.goto("https://depositphotos.com/files.html", wait_until="domcontentloaded")
    page.wait_for_timeout(7000)
    t = re.sub(r"[ \t]+", " ", page.inner_text("body"))
    if "/login" in page.url.lower() or "Seller's Menu" not in t:
        raise RuntimeError("not signed in")
    out = {"examination_pending": "files_menu_examination" in page.url
                                  or "Examination Test" in t}
    # Each counter is "Label\n<n>" in the Seller's Menu strip.
    for label, key in (("Online", "online"), ("Pending", "pending"),
                       ("Unfinished", "unfinished"), ("Rejected", "rejected"),
                       ("Deactivated", "deactivated")):
        m = re.search(rf"\b{label}\s*\n\s*(\d+)", t)
        if m:
            out[key] = int(m.group(1))

    # While in examination the sales redirect can abort the navigation
    # outright (net::ERR_ABORTED, first seen 2026-09-24) instead of landing
    # on the examination page; either way there is no money to read.
    try:
        page.goto("https://depositphotos.com/sales.html", wait_until="domcontentloaded")
    except Exception:
        if out["examination_pending"]:
            return out
        raise
    page.wait_for_timeout(6000)
    if "sales.html" in page.url:
        s = re.sub(r"[ \t]+", " ", page.inner_text("body"))
        m = re.search(r"(?:Balance|Earnings)\s*:?\s*\n?\s*\$\s*([\d,]+\.?\d*)", s, re.I)
        if m:
            out["balance"] = num(m.group(1))
    return out


def collect_etsy(page):
    """Etsy shop PurplelinkDesigns: all-time shop stats plus active listings.

    Added 2026-09-24, the day the shop opened with printable-download
    listings. Shop Manager's Stats page takes date_range=all_time, so visits,
    orders and revenue are cumulative like every other platform's balance and
    the dashboard's day-over-day deltas mean something. Orders are recorded as
    "sales" and revenue as "revenue" so the existing money/sales rollups pick
    them up without special cases.
    """
    page.goto("https://www.etsy.com/your/shops/me/stats?date_range=all_time",
              wait_until="domcontentloaded")
    page.wait_for_timeout(7000)
    if re.search(r"signin|/login", page.url, re.I):
        raise RuntimeError("not signed in")
    t = re.sub(r"\s+", " ", page.inner_text("body"))
    if "Shop stats" not in t:
        raise RuntimeError("not signed in")
    out = {}
    for label, key in (("Visits", "visits"), ("Orders", "sales"),
                       ("Item favorites", "favorites"), ("Shop follows", "followers"),
                       ("Reviews", "reviews")):
        m = re.search(rf"\b{label} (\d[\d,]*)", t)
        if m:
            out[key] = num(m.group(1))
    m = re.search(r"\bRevenue \$([\d,]+\.\d{2})", t)
    if m:
        out["revenue"] = num(m.group(1))
    m = re.search(r"Conversion rate ([\d.]+)%", t)
    if m:
        out["conversion_pct"] = num(m.group(1))
    if "visits" not in out or "sales" not in out:
        raise RuntimeError("Etsy stats layout changed: visits/orders not found")

    page.goto("https://www.etsy.com/your/shops/me/tools/listings", wait_until="domcontentloaded")
    page.wait_for_timeout(6000)
    t = re.sub(r"\s+", " ", page.inner_text("body"))
    # The "Active N / Draft N" tab counts only render on an EMPTY shop; once
    # there are real listings that strip is replaced by a "Filter" dropdown
    # and the count vanishes entirely (found 2026-09-25, the day after the
    # first 15 listings went live -- active_listings was silently missing
    # from history.json with no error). Count listing rows instead: every
    # row -- digital or physical -- prints its stock line, "N in stock".
    m = re.search(r"\bActive\s*(\d+)", t)
    if m:
        out["active_listings"] = int(m.group(1))
    else:
        out["active_listings"] = len(re.findall(r"\d[\d,]*\s+in stock", t))
    return out


PLATFORMS = [("fineartamerica", collect_faa), ("adobe_stock", collect_adobe),
             ("alamy", collect_alamy), ("alamy_qc", collect_alamy_qc),
             ("alamy_measures", collect_alamy_measures),
             ("alamy_sales", collect_alamy_sales),
             ("shutterstock", collect_shutterstock),
             ("getty", collect_getty),
             ("getty_stats", collect_getty_stats),
             ("123rf", collect_123rf),
             ("depositphotos", collect_depositphotos),
             ("etsy", collect_etsy)]

# Dreamstime dropped from the daily crawl 2026-09-03: its anti-bot "Press &
# Hold" challenge blocks the automation profile often enough that it stopped
# being worth the auto-login wait, and there's no contributor-side API to fall
# back to (Dreamstime's API products are all buyer-side -- see
# scripts/dreamstime-sales.py's docstring). collect_dreamstime is still
# defined above; pass --include-dreamstime to run it on a given day by hand.
DREAMSTIME = ("dreamstime", collect_dreamstime)


CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
# Not 9222-9229: something on this Mac hides any Chrome running a debug port
# in that range within a second of launch (2026-09-23: a fresh profile on
# 9225 hid, the same profile on 9234 stayed visible), which made every
# sign-in prompt vanish before it could be used.
CDP_PORT = 9340


def launch_chrome(headless=True):
    """Start an ordinary Chrome with a debug port and attach to it.

    NOT launch_persistent_context: a Playwright-launched Chrome gets fingerprinted
    and Alamy/Shutterstock/FAA answer it with 403 Forbidden or a login redirect no
    matter how valid the cookies are. Attaching over CDP to a normally-started
    Chrome is indistinguishable from the user's own browsing and sails through.
    """
    import socket, subprocess, time as _t
    def up():
        with socket.socket() as s:
            s.settimeout(0.4)
            return s.connect_ex(("127.0.0.1", CDP_PORT)) == 0

    def probe():
        """('ok'|'busy'|'dead'). An open port is NOT proof of a working browser:
        after a crash it keeps answering from a dead process with no browser
        context. But a FAILED probe is not proof of a dead one either -- when a
        second Playwright client is already attached, connect_over_cdp raises
        'Browser context management is not supported' against a completely
        healthy Chrome. Treating that as dead is what killed a browser holding
        freshly signed-in Getty and Fine Art America sessions."""
        if not up():
            return "dead"
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as _p:
                _b = _p.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
                _pg = _b.contexts[0].new_page()
                _pg.close()
            return "ok"
        except Exception as e:
            msg = str(e).lower()
            if "context management" in msg or "already" in msg or "target closed" in msg:
                return "busy"            # someone else is driving it — leave it alone
            return "dead"

    state = probe()
    if state == "dead" and up():
        # One failure is not enough to justify killing a browser that may hold
        # every session we have. Re-probe before concluding anything.
        _t.sleep(4)
        state = probe()

    if state == "ok":
        return None                      # a real browser is already there
    if state == "busy":
        raise SystemExit(
            "Another process is already attached to Chrome on port "
            f"{CDP_PORT}. Two Playwright clients cannot share one CDP endpoint.\n"
            "Wait for it to finish rather than restarting Chrome -- restarting "
            "destroys every signed-in session in the profile.")
    if up():
        # Before killing anything: a Chrome whose last tab was closed keeps the
        # port open with ZERO targets, and Playwright then fails with "Browser
        # context management is not supported" -- indistinguishable from a real
        # zombie. Opening a target through the plain CDP HTTP API revives it
        # WITHOUT a restart, which is the difference between keeping every
        # signed-in session and losing all of them.
        try:
            import urllib.request
            urllib.request.urlopen(
                urllib.request.Request(f"http://127.0.0.1:{CDP_PORT}/json/new?about:blank",
                                       method="PUT"), timeout=6).read()
            _t.sleep(3)
            if probe() == "ok":
                return None
        except Exception:
            pass
        # Genuinely a zombie: port open, no usable browser, revival failed.
        subprocess.run(["pkill", "-f", f"remote-debugging-port={CDP_PORT}"],
                       capture_output=True)
        _t.sleep(6)
    args = [CHROME, f"--remote-debugging-port={CDP_PORT}",
            f"--user-data-dir={PROFILE}", "--no-first-run",
            "--no-default-browser-check", "about:blank"]
    if headless:
        args.insert(1, "--headless=new")
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        if up():
            return proc
        _t.sleep(0.5)
    raise RuntimeError("Chrome did not open its debug port")


def quit_chrome(proc):
    """Terminate gracefully so Chrome flushes cookies. A hard kill loses the
    session and the next run reports everything as signed out."""
    if proc is None:
        return
    import time as _t
    proc.terminate()
    for _ in range(20):
        if proc.poll() is not None:
            return
        _t.sleep(0.5)
    proc.kill()


# Where to send the user for each platform when a collector reports a dead
# session. ESP, not contributors.gettyimages.com -- that one is public
# marketing and looks logged-in whether or not you actually are.
LOGIN_URLS = {
    "fineartamerica": "https://fineartamerica.com/login.html",
    "adobe_stock": "https://contributor.stock.adobe.com/en/uploads",
    "alamy": "https://www.alamy.com/log-in/",
    "dreamstime": "https://www.dreamstime.com/manage-account",
    "shutterstock": "https://submit.shutterstock.com/",
    "getty": "https://esp.gettyimages.com/contribute/batches",
    "123rf": "https://www.123rf.com/contributor/dashboard",
    "depositphotos": "https://depositphotos.com/files.html",
    "etsy": "https://www.etsy.com/signin",
}

# Only these failure shapes get the interactive fallback. A dead session
# ("not signed in") and a solvable anti-bot challenge are things a human
# sitting at the browser can fix in seconds. Everything else -- a slow
# render, a changed layout, a genuine platform outage -- would just show the
# person a page that looks fine and waste their time waiting for nothing to
# happen, so those still fail immediately and get reported as before.
def _needs_human(err_msg):
    m = err_msg.lower()
    return "not signed in" in m or "anti-bot human check" in m


def _wait_for_fix(page, url, fn, budget_s=180):
    """Bring the login/challenge page to the front and retry fn(page) every
    few seconds until it stops raising or the budget runs out.

    This only makes sense with a HEADED browser -- bring_to_front() has
    nothing to raise on a headless one. run() forces headed whenever the
    fallback is enabled, which is the whole point of this function existing.
    """
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        page.bring_to_front()
    except Exception:
        pass
    # bring_to_front() alone was not enough: verified 2026-08-27 that after a
    # run finished, Chrome WAS the frontmost app but sitting on about:blank --
    # CDP raised the tab within its own window but never made the browser
    # window itself jump above whatever else was in front (or across Spaces).
    # A real macOS "activate" on the app is the belt-and-suspenders fix.
    try:
        import subprocess as _sp
        _sp.run(["osascript", "-e", 'tell application "Google Chrome" to activate'],
                capture_output=True, timeout=5)
    except Exception:
        pass
    # Never call fn(page) while the person is still on a sign-in screen: every
    # collector starts with page.goto(), so retrying on a timer yanked the
    # login tab away every 5s and wiped half-typed credentials (FAA,
    # 2026-09-23: "the window hides itself too quickly"). Watch the URL
    # passively instead and only retry once it has left the login flow.
    login_markers = ("login", "signin", "sign-in", "auth", "sso", "ims-na1",
                     "upload-id", "challenge", "captcha", "verify")
    def on_login_screen():
        try:
            u = page.url.lower()
        except Exception:
            return True
        return any(m in u for m in login_markers)

    deadline = time.time() + budget_s
    while time.time() < deadline:
        time.sleep(3)
        if on_login_screen():
            continue
        try:
            return fn(page)
        except Exception:
            # fn navigated away; put the sign-in page back for another try.
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            except Exception:
                pass
    return fn(page)


def run(headless=True, auto_login=True, login_budget_s=180, include_dreamstime=False):
    from playwright.sync_api import sync_playwright
    OUT.mkdir(parents=True, exist_ok=True)
    entry = {"date": datetime.date.today().isoformat(),
             "collected_at": datetime.datetime.now().isoformat(timespec="seconds"),
             "platforms": {}}
    # A login prompt only means something if there is a window to show it in.
    # Headless Chrome has no OS window bring_to_front() can raise, so the
    # fallback silently forces headed rather than pretending to offer it.
    if auto_login:
        headless = False
    platforms = PLATFORMS + [DREAMSTIME] if include_dreamstime else PLATFORMS
    proc = launch_chrome(headless=headless)
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
        ctx = browser.contexts[0]
        for name, fn in platforms:
            # A fresh tab per platform. Sharing one page let a redirect or an
            # interstitial from the previous site bleed into the next collector
            # and read as "signed out".
            page = ctx.new_page()
            recovered = False
            try:
                got = fn(page)
                # A collector that returns only nulls has silently failed --
                # usually an expired session that didn't trip the sign-in check.
                # Reporting that as OK would freeze a stale number on the
                # dashboard and look like "no change", which is worse than a gap.
                # Judge health on the NUMBERS only. A collector whose sole
                # surviving field is a string (a profile URL, a page snippet)
                # has scraped nothing useful but would otherwise pass as OK.
                nums = [v for v in got.values()
                        if isinstance(v, (int, float)) and not isinstance(v, bool)]
                if got and not nums:
                    raise RuntimeError("no numeric fields scraped (layout changed or session expired)")
                entry["platforms"][name] = {"ok": True, **got}
                print(f"  OK   {name}")
            except Exception as e:
                url = LOGIN_URLS.get(name)
                if auto_login and url and _needs_human(str(e)):
                    print(f"  ...  {name}: {str(e)[:70]} -- opening the page for you, "
                          f"waiting up to {login_budget_s}s", flush=True)
                    try:
                        got = _wait_for_fix(page, url, fn, budget_s=login_budget_s)
                        nums = [v for v in got.values()
                                if isinstance(v, (int, float)) and not isinstance(v, bool)]
                        if got and not nums:
                            raise RuntimeError("no numeric fields scraped after sign-in")
                        entry["platforms"][name] = {"ok": True, **got}
                        print(f"  OK   {name} (after sign-in)")
                        recovered = True
                    except Exception as e2:
                        entry["platforms"][name] = {"ok": False,
                                                    "error": f"{type(e2).__name__}: {e2}"[:160]}
                        print(f"  WARN {name}: still failing after waiting: "
                              f"{type(e2).__name__}: {str(e2)[:80]}")
                else:
                    entry["platforms"][name] = {"ok": False, "error": f"{type(e).__name__}: {e}"[:160]}
                    print(f"  WARN {name}: {type(e).__name__}: {str(e)[:80]}")
            finally:
                # Only close on success. A tab left open on failure is the
                # whole point of the fallback: closing it the instant the wait
                # budget expires means the login page flashes by and is gone
                # by the time anyone actually looks at the screen -- verified
                # 2026-08-27, screen showed about:blank because every platform
                # that needed a sign-in had already opened AND closed its tab
                # before the run finished. Leaving it open means a person who
                # checks a minute later, or five, still finds it waiting.
                if entry["platforms"].get(name, {}).get("ok"):
                    try:
                        page.close()
                    except Exception:
                        pass
    quit_chrome(proc)
    hist = load_history()
    hist = [h for h in hist if h["date"] != entry["date"]] + [entry]
    hist.sort(key=lambda h: h["date"])
    HISTORY.write_text(json.dumps(hist, indent=2))
    append_snapshots(entry)
    print(f"\nwrote {HISTORY} ({len(hist)} day(s) of history)")
    return entry


def append_snapshots(entry):
    """Append today's numbers to a tidy long-format CSV.

    One row per (date, platform, metric). Same shape as the TikTok pipeline's
    growth.csv, so the same kind of week-over-week analysis works here.
    Re-running on the same day replaces that day's rows rather than duplicating.
    """
    import csv as _csv
    ANALYTICS.mkdir(parents=True, exist_ok=True)
    rows = []
    if SNAPSHOTS.exists():
        rows = [r for r in _csv.DictReader(open(SNAPSHOTS))
                if r["snapshot_date"] != entry["date"]]
    for platform, data in entry["platforms"].items():
        if not data.get("ok"):
            rows.append({"snapshot_date": entry["date"], "platform": platform,
                         "metric": "collector_ok", "value": 0,
                         "note": data.get("error", "")[:80]})
            continue
        for k, v in data.items():
            if k == "ok" or v is None or isinstance(v, bool):
                continue
            if isinstance(v, str):
                continue                      # snippets aren't timeseries
            rows.append({"snapshot_date": entry["date"], "platform": platform,
                         "metric": k, "value": v, "note": ""})
        rows.append({"snapshot_date": entry["date"], "platform": platform,
                     "metric": "collector_ok", "value": 1, "note": ""})
    rows.sort(key=lambda r: (r["snapshot_date"], r["platform"], r["metric"]))
    with open(SNAPSHOTS, "w", newline="") as fh:
        w = _csv.DictWriter(fh, fieldnames=["snapshot_date", "platform", "metric", "value", "note"])
        w.writeheader(); w.writerows(rows)
    print(f"wrote {SNAPSHOTS} ({len(rows)} rows)")


def login():
    from playwright.sync_api import sync_playwright
    print("Opening a SEPARATE browser profile (~/.photo-automation-chrome), not your\n"
          "everyday Chrome. Signing in to your normal browser does NOT give the\n"
          "collector a session -- they keep different cookie stores.\n\n"
          "Sign in to each tab:\n"
          "  1. fineartamerica.com\n  2. contributor.stock.adobe.com\n  3. alamy.com\n"
          "  4. dreamstime.com\n  5. submit.shutterstock.com\n  6. esp.gettyimages.com\n"
          "Then press Enter here.")
    proc = launch_chrome(headless=False)
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
        ctx = browser.contexts[0]
        for url in ("https://fineartamerica.com/login.html",
                    "https://contributor.stock.adobe.com/en/uploads",
                    "https://www.alamy.com/log-in/",
                    "https://www.dreamstime.com/login",
                    "https://submit.shutterstock.com/",
                    # ESP, not contributors.gettyimages.com -- that one is public
                    # marketing and renders "Contributor"/"Upload" whether or not
                    # you are signed in, so signing in there leaves the collector
                    # logged out and reports a healthy session for a dead one.
                    "https://esp.gettyimages.com/contribute/batches"):
            ctx.new_page().goto(url)
        input("\nPress Enter here once you've signed in to all of them...")
    # graceful quit so the cookies actually reach disk
    quit_chrome(proc)
    print("sessions saved to", PROFILE)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--login", action="store_true")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--headed", action="store_true", help="run visibly, for debugging")
    ap.add_argument("--no-auto-login", action="store_true",
                    help="don't pop up a login page on a dead session; just "
                         "fail like before. Auto-login is on by default and "
                         "forces a headed browser so it has a window to show.")
    ap.add_argument("--login-wait", type=int, default=180,
                    help="seconds to wait per platform for you to sign in "
                         "before giving up on it (default 180)")
    ap.add_argument("--include-dreamstime", action="store_true",
                    help="Dreamstime is off the daily crawl (its anti-bot "
                         "challenge blocks the automation profile too often "
                         "to be worth it, and there's no contributor API). "
                         "Pass this to try it anyway on a given run.")
    a = ap.parse_args()
    if a.login:
        login()
    elif a.show:
        h = load_history()
        print(json.dumps(h[-1] if h else {}, indent=2))
    else:
        run(headless=not a.headed, auto_login=not a.no_auto_login,
            login_budget_s=a.login_wait, include_dreamstime=a.include_dreamstime)
        import subprocess
        # Mail second: it survives when browser sessions don't, so it fills gaps
        # the scraper leaves. Failure here must not lose the browser results.
        try:
            subprocess.run([sys.executable, str(ROOT / "scripts" / "mail-collect.py"),
                            "--days", "1"], timeout=300)
        except Exception as e:
            print(f"  WARN mail-collect: {type(e).__name__}: {e}")
        # regenerate the HTML view
        subprocess.run([sys.executable, str(ROOT / "scripts" / "photo-dashboard.py")])
