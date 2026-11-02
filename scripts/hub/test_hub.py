#!/usr/bin/env python3
"""Offline tests for hub.py on synthetic sources. Run: python3 scripts/hub/test_hub.py"""
import contextlib, importlib.util, io, json, os, sqlite3, tempfile
from pathlib import Path

tmp = Path(tempfile.mkdtemp())
os.environ.update({
    "PURPLELINK_HUB": str(tmp / "hub"), "PURPLELINK_QUEUE": str(tmp / "queue"), "PURPLELINK_REPO": str(tmp / "repo"),
    "PURPLELINK_SOCIAL_QUEUE": str(tmp / "social"), "PURPLELINK_TRAFFIC_HISTORY": str(tmp / "history.json"),
    # doctor's delivery check calls the live stats function; tests pass their own fetch instead
    "PURPLELINK_STATS_OFFLINE": "1",
})
spec = importlib.util.spec_from_file_location("hub", Path(__file__).with_name("hub.py"))
hub = importlib.util.module_from_spec(spec); spec.loader.exec_module(hub)


def put(rel, text):
    p = tmp / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


put("repo/site/llms.txt", """## Products — available now

### Widget (macOS)
- **Pricing:** Free 7-day trial, then $9.99 once.
- **Status:** Shipping, version 1.2.0 (October 2026). Version 1.1.0 added things.
- **Trial and purchase:** https://purplelink.llc/widget/

### Gadget Pro (macOS)
- **Pricing:** Free. Optional Gadget Plus, $2.99 a month.
- **Page:** https://purplelink.llc/gadget/

## Tools (free web tools)
- Thesis Format Checker: https://purplelink.llc/tools/thesis-format-checker/ — checks a PDF.

## Guides (free how-to articles)
- Fix a thing: https://purplelink.llc/guides/fix-a-thing/ — how to fix it.
""")
put("repo/site/sitemap.xml", "<urlset><url><loc>https://purplelink.llc/guides/other-guide/</loc></url></urlset>")
put("repo/Outreach/OUTREACH-LOG.md", """# Outreach Log

## LibGuide outreach

| Date sent | Target | Contact | Status | Notes |
|---|---|---|---|---|
| 2026-10-01 | Example University, Thesis Format Checker | Pat (pat@example.edu) | sent | via ben, tell pat@example.edu |
| | Planned University | (Ask form) | | |

## Directory submissions 2026-10-08

| Directory | URL | Result |
|---|---|---|
| Some Directory | https://dir.example/widget | submitted for Widget |

## Social mirror

| Date | Where | Link | Status | Notes |
|---|---|---|---|---|
| 2026-10-21 | bluesky: 20261021-daily-release-widget-1-2 | https://bsky.app/x | posted | mirror of the social item |
| 2026-10-20 | email: Reviewer | Mail.app | sent | queue item q-20261020-rev, Widget review pitch |
""")
put("queue/done/2026-10-20-email-reviewer.md", """---
id: q-20261020-rev
created: 2026-10-20T08:00:00-04:00
kind: email
target: "Reviewer, review pitch for Widget"
status: done
---

## Ask
Send a review pitch for Widget, https://purplelink.llc/widget/

## Result
sent from Mail (2026-10-20T19:31-04:00)
""")
put("queue/pending/2026-10-23-pr-guide.md", "---\nid: q-20261023-001\nkind: pr\ntarget: \"a guide\"\n---\n\n## Ask\nA PR.\n")
put("social/20261021-daily-release-widget-1-2.md", """---
id: "20261021-daily-release-widget-1-2"
status: "posted"
approved_by: "ben (standing, 2026-10-18)"
platforms: ["bluesky", "mastodon"]
campaign: "daily-release"
link: "https://purplelink.llc/widget/"
results: {"bluesky": {"status": "posted", "url": "https://bsky.app/x", "posted_at": "2026-10-21T10:33:18-04:00"}}
---

## bluesky
Widget 1.2 is out.
""")
put("social/20261018-dryrun-bluesky-test.md", '---\nid: "20261018-dryrun-bluesky-test"\nplatforms: ["bluesky"]\n---\n')
put("repo/video/howto/ledger.json", json.dumps([{"slug": "howto-x", "app": "widget", "date": "2026-10-22",
                                                  "title": "Fix x", "long_id": "LONG1", "short_id": "SHORT1",
                                                  "link_utm_content": "howto-x"}]))
put("history.json", json.dumps({
    "macupdate": {"gadget": {"url": "https://gadget.macupdate.com/",
                             "snapshots": {"2026-10-18": {"downloads": 5, "price": 9.99, "version": "1.0"},
                                           "2026-10-19": {"downloads": 7, "price": 9.99, "version": "1.1"}}}},
    "ledger": {
        # "a" is a Stripe checkout ("purchase", as sales.mjs writes it); "e" is a renewal, never a new buyer
        "a": {"kind": "purchase", "product": "widget", "ts": 1792700000, "attr": {"first": {"s": "bluesky"}}, "heard": "reddit"},
        "b": {"kind": "order", "product": "widget", "ts": 1792700000, "attr": {"first": {"s": "bluesky"}}, "refunded": 1},
        "c": {"kind": "order", "product": "widget", "ts": 1700000000, "attr": {"first": {"s": "bluesky"}}},
        "d": {"kind": "order", "product": "widget", "ts": 1793050000, "attr": {"first": {"s": "otherdir", "t": "widget-directory-261025"}}},
        "e": {"kind": "renewal", "product": "widget", "ts": 1792700000, "attr": {"first": {"s": "bluesky"}}, "heard": "youtube"},
    }}))
put("social-metrics.json", json.dumps({"posts": {"20261021-daily-release-widget-1-2": {"platforms": {"bluesky": {
    "snapshots": {"2026-10-21": {"likes": 1, "views": None}, "2026-10-22": {"likes": 3, "views": None}}}}}}}))
os.environ["PURPLELINK_SOCIAL_METRICS"] = str(tmp / "social-metrics.json")
FUNNEL = {"bluesky": {"pageviews": 9, "pageviewsByPath": {"/widget/": 6, "/": 3}, "trial": {"widget": 2}, "checkout": {"widget": 1}},
          "youtube-latex": {"pageviews": 4, "pageviewsByPath": {"/widget/": 4}, "trial": {}, "checkout": {}}}
put("hub/funnel.json", json.dumps({"asOf": "2026-10-23", "windows": {str(w): FUNNEL for w in hub.FUNNEL_WINDOWS}}))


def run(*argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        hub.main(list(argv))
    return buf.getvalue()


def db():
    con = sqlite3.connect(tmp / "hub" / "hub.sqlite")
    con.row_factory = sqlite3.Row
    return con


def assets_of(con, pid):
    return sorted(r[0] for r in con.execute("SELECT asset_id FROM placement_assets WHERE placement_id = ?", (pid,)))


def test_all():
    out = run("import")
    assert "unmatched" in out, out
    con = db()
    ids = {r["id"] for r in con.execute("SELECT id FROM placements")}

    # assets: products from llms.txt headings, tools by name, guides from llms and sitemap
    a = {r["id"]: r["kind"] for r in con.execute("SELECT id, kind FROM assets")}
    assert a["widget"] == "product" and a["gadget"] == "product", a
    assert a["tool:thesis-format-checker"] == "tool" and a["guide:fix-a-thing"] == "guide" and a["guide:other-guide"] == "guide"

    # approval queue: outward kinds only; a pr item is not a placement
    assert "queue:q-20261020-rev" in ids and "queue:q-20261023-001" not in ids
    # the log row citing the queue id is merged into the queue placement, not counted twice
    q = con.execute("SELECT * FROM placements WHERE id = 'queue:q-20261020-rev'").fetchone()
    assert q["contact_ref"].startswith("OUTREACH-LOG.md:") and q["status"] == "live" and q["date"] == "2026-10-20"
    assert assets_of(con, "queue:q-20261020-rev") == ["widget"]
    assert not [r for r in con.execute("SELECT target FROM placements WHERE source = 'outreach-log'") if "Reviewer" in r[0]]

    # social: one placement per platform, standing approval recorded, dry runs skipped, log mirror rows dropped
    b = con.execute("SELECT * FROM placements WHERE id = 'social:20261021-daily-release-widget-1-2:bluesky'").fetchone()
    assert b["status"] == "live" and b["url"] == "https://bsky.app/x" and b["approval"] == "standing:2026-10-18"
    assert "utm_source=bluesky" in b["utm"]
    m = con.execute("SELECT status FROM placements WHERE id = 'social:20261021-daily-release-widget-1-2:mastodon'").fetchone()
    assert m["status"] == "approved"
    assert not any("dryrun" in i for i in ids)
    assert not [r for r in con.execute("SELECT target FROM placements WHERE source = 'outreach-log'") if "bluesky:" in r[0]]

    # outreach: emails masked, contact kept only as a reference; a row with no date is planned; tool matched by name
    rows = list(con.execute("SELECT * FROM placements WHERE source = 'outreach-log'"))
    assert all("@" not in (r["notes"] + r["target"]) for r in rows)
    lib = next(r for r in rows if r["target"].startswith("Example University"))
    assert lib["channel"] == "libguide" and lib["status"] == "live" and lib["contact_ref"] == "OUTREACH-LOG.md:7"
    assert assets_of(con, lib["id"]) == ["tool:thesis-format-checker"]
    assert next(r for r in rows if r["target"] == "Planned University")["status"] == "planned"
    d = next(r for r in rows if r["target"] == "Some Directory")
    assert d["channel"] == "directory" and d["date"] == "2026-10-08" and d["url"] == "https://dir.example/widget"
    assert assets_of(con, d["id"]) == ["widget"]

    # video and MacUpdate: tied to their product, MacUpdate readings kept as results
    assert assets_of(con, "video:LONG1") == ["widget"] and "video:SHORT1" in ids
    assert assets_of(con, "macupdate:gadget") == ["gadget"]
    assert [r[0] for r in con.execute("SELECT value FROM results WHERE placement_id = 'macupdate:gadget' AND metric = 'downloads-total' ORDER BY date")] == [5, 7]

    # commands
    assert "widget:" in run("where", "Widget")
    assert "widget" in run("grid")
    assert "placements" in run("status")
    assert "assets with no live placement" in run("gaps", "--days", "10000")

    # rebuild is idempotent
    run("import")
    assert db().execute("SELECT count(*) FROM placements").fetchone()[0] == len(ids)


def test_sources_untouched():
    snap = lambda: {p: p.read_bytes() for p in tmp.rglob("*") if p.is_file() and "hub" not in p.parts}
    before = snap()
    run("import")
    assert snap() == before


def test_results_and_followups():
    import datetime as dt
    run("import")
    con = db()
    # llms.txt: newest version on the status line; a free app with a paid add-on has no price to check
    w = con.execute("SELECT version, price FROM assets WHERE id = 'widget'").fetchone()
    assert (w["version"], w["price"]) == ("1.2.0", "9.99"), tuple(w)
    assert con.execute("SELECT price FROM assets WHERE id = 'gadget'").fetchone()[0] is None
    r = {row["metric"]: (row["value"], row["confidence"]) for row in
         con.execute("SELECT * FROM results WHERE placement_id = 'social:20261021-daily-release-widget-1-2:bluesky'")}
    assert r["first-touch-visits"][0] == 6 and r["trials"][0] == 2 and r["checkout-clicks"][0] == 1
    assert r["orders"][0] == 1, r  # refunded and older orders do not count
    assert r["likes"][0] == 3       # latest social snapshot
    # the YouTube video counts its "youtube-latex" family
    v = {row["metric"]: row["value"] for row in con.execute("SELECT * FROM results WHERE placement_id = 'video:LONG1'")}
    assert v["first-touch-visits"] == 4
    # how-heard answers are their own table, never merged into tagged counts
    assert [tuple(x) for x in con.execute("SELECT product, answer, channel, orders FROM heard")] == [("widget", "reddit", "reddit", 1)]
    # channel stats exist and are judged on visits, not placement count
    rows = {(x["product"], x["channel"]): x for x in con.execute("SELECT * FROM channel_stats")}
    assert rows[("widget", "bluesky")]["verdict"] == "building"


def test_follow_up_rules():
    import datetime as dt
    today = dt.date(2026, 10, 23)
    mk = lambda days, ch="email", notes="": {"channel": ch, "status": "live", "notes": notes,
                                              "date": (today - dt.timedelta(days=days)).isoformat()}
    assert hub.follow_up(mk(2), today) == ("live", "2026-10-25")       # waiting
    assert hub.follow_up(mk(6), today)[1] == "2026-10-21"               # due
    assert hub.follow_up(mk(20), today) == ("live", "")                 # window closed, not nagged
    assert hub.follow_up(mk(30), today) == ("no-response", "")
    assert hub.follow_up(mk(6, notes="replied 10-20"), today) == ("live", "")
    assert hub.follow_up(mk(6, ch="photo-pitch"), today) == ("live", "")  # paused line: never prompted
    assert hub.follow_up(mk(6, ch="bluesky"), today) == ("live", "")


def test_stop_rule_and_interval():
    import datetime as dt
    lo, hi = hub.clopper_pearson(0, 150)
    assert lo == 0 and 0.023 < hi < 0.026        # rule of three: about 3/150
    lo, hi = hub.clopper_pearson(5, 50)
    assert 0.03 < lo < 0.04 and 0.21 < hi < 0.23
    today = dt.date(2026, 10, 23)
    assets = {"widget": {"kind": "product", "url": "https://purplelink.llc/widget/"}}
    start = (today - dt.timedelta(days=44)).isoformat()
    pls = [{"id": f"p{i}", "channel": "bluesky", "status": "live", "date": start, "url": "", "landing_url": "", "utm": ""}
           for i in range(8)]
    links = {f"p{i}": ["widget"] for i in range(8)}

    def verdict(visits, trials):
        fun = {"asOf": "x", "windows": {"45": {"bluesky": {"pageviewsByPath": {"/widget/": visits}, "trial": {"widget": trials}}}}}
        return hub.channel_stats(pls, links, assets, fun, [], today)[0][9]
    assert verdict(149, 0) == "unmeasured"
    assert verdict(150, 0) == "pause-candidate"
    assert verdict(150, 3) == "early"
    assert verdict(150, 6) == "working"
    assert hub.channel_stats(pls[:7], links, assets, {"windows": {"45": {}}}, [], today)[0][9] == "building"


def test_listing_checks():
    assert hub.listing_check({"error": "403"}, {"version": "1.2.0"}) == "manual"
    assert hub.listing_check({"versions": [], "prices": []}, {"version": "1.2.0"}) == "manual"
    assert hub.listing_check({"versions": ["1.1.0"], "prices": []}, {"version": "1.2.0"}) == "stale"
    assert hub.listing_check({"versions": ["1.2.0"], "prices": ["9.99"]}, {"version": "1.2.0", "price": "9.99"}) == "ok"
    assert hub.listing_check({"versions": ["1.2.0"], "prices": ["4.99"]}, {"version": "1.2.0", "price": "9.99"}) == "stale"
    # only text near our app's name counts on a page that lists many apps
    f = hub.read_facts("<p>Other App version 1.0 $1.00</p>" + "x" * 900 + "<p>Widget version 1.2.0, $9.99</p>", "Widget")
    assert f["versions"] == ["1.2.0"] and f["prices"] == ["9.99"]
    assert hub.read_facts("<p>Nothing here version 3.0</p>", "Widget")["mentions"] is False
    # script and style contents never count, whatever the end tag looks like
    f = hub.read_facts("<script>var x='Widget version 9.9.9 $1.00'</script ><style>p{}</style\n><p>Widget version 1.2.0</p>", "Widget")
    assert f["versions"] == ["1.2.0"] and f["prices"] == []
    # MacUpdate's daily reading is compared without a fetch
    run("import")
    con = db()
    assert con.execute("SELECT check_state FROM placements WHERE id = 'macupdate:gadget'").fetchone()[0] in ("ok", "manual", "stale")
    # check-listings fetches, records and never marks a failed fetch stale
    put("repo/Outreach/OUTREACH-LOG.md", (tmp / "repo/Outreach/OUTREACH-LOG.md").read_text())
    calls = []

    def fake(url):
        calls.append(url)
        raise OSError("blocked")
    out = hub.check_listings(hub.paths(), get=fake)
    assert out["checked"] == len(calls) == 1 and calls == ["https://dir.example/widget"]
    run("import")
    assert db().execute("SELECT check_state FROM placements WHERE url = 'https://dir.example/widget'").fetchone()[0] == "manual"
    hub.check_listings(hub.paths(), get=lambda u: "<h2>Widget</h2> Version 1.1.0 for $9.99")
    run("import")
    assert db().execute("SELECT check_state FROM placements WHERE url = 'https://dir.example/widget'").fetchone()[0] == "stale"
    assert hub.check_listings(hub.paths(), if_older=7, get=fake)["skipped"] == 1


def test_fetch_funnel_keeps_token_out_of_url():
    put("traffic.env", "PURPLELINK_STATS_TOKEN=secret-token\n")
    os.environ["PURPLELINK_TRAFFIC_ENV"] = str(tmp / "traffic.env")
    seen = []

    def fake(url, headers):
        seen.append((url, headers))
        return {"funnelByChannel": FUNNEL}
    saved = (tmp / "hub" / "funnel.json").read_text()
    out = hub.fetch_funnel(hub.paths(), get=fake)
    assert len(seen) == len(hub.FUNNEL_WINDOWS) and all("secret" not in u and h["x-stats-token"] == "secret-token" for u, h in seen)
    assert set(out["windows"]) == {str(w) for w in hub.FUNNEL_WINDOWS}
    put("hub/funnel.json", saved)


def test_funnel_stale_until_fetched_on_the_day():
    # The export used to skip the fetch when funnel.json was under 20 hours old. A daytime fetch (10-28 17:34) then
    # left the next morning's dashboard without the previous evening, the first day of the Reddit test (2026-10-29).
    f = tmp / "stale-check" / "funnel.json"
    day = hub.dt.date(2026, 10, 29)
    assert hub.funnel_stale(f, day)                                   # never fetched
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("not json")
    assert hub.funnel_stale(f, day)                                   # unreadable
    f.write_text(json.dumps({"asOf": "2026-10-28", "windows": {}}))
    assert hub.funnel_stale(f, day)                                   # yesterday's fetch misses yesterday's evening
    f.write_text(json.dumps({"asOf": "2026-10-29", "windows": {}}))
    assert not hub.funnel_stale(f, day)                               # fetched today: at most one fetch a day


def test_export_has_no_contacts():
    run("import")
    out = tmp / "export"
    run("export", str(out))
    names = sorted(f.name for f in out.glob("*.json"))
    assert names == sorted(f"marketing_{n}.json" for n in ("summary", "grid", "channels", "placements", "followups", "listings", "heard", "campaigns", "rechecks"))
    blob = "".join(f.read_text() for f in out.glob("*.json"))
    assert not hub.EMAIL_RE.search(blob.replace("@purplelink", ""))
    assert "OUTREACH-LOG" not in blob and "Pat" not in blob and "Reviewer" not in blob and "Example University" not in blob
    for f in out.glob("*.json"):
        assert isinstance(json.loads(f.read_text()), list), f.name
    pl = json.loads((out / "marketing_placements.json").read_text())
    em = [r for r in pl if r["channel"] in ("email", "libguide")]
    assert em and all(r["target"] is None and r["url"] is None for r in em)
    s = json.loads((out / "marketing_summary.json").read_text())[0]
    assert s["placements"] > 0 and "gadget" not in s["untouched"]


def test_phase2_tags_and_link_results():
    import datetime as dt
    P = hub.paths()
    u = hub.make_utm(P, "https://purplelink.llc/widget/#buy", "widget", "directory", "somedir", today=dt.date(2026, 10, 25))
    assert u == "https://purplelink.llc/widget/?utm_source=somedir&utm_medium=referral&utm_campaign=hub-widget&utm_content=widget-directory-261025#buy", u
    # a tag already used anywhere gets a suffix
    put("queue/done/2026-10-25-listing-dir.md", """---
id: q-20261025-dir
created: 2026-10-25T08:00:00-04:00
kind: listing
target: "Some Other Directory"
assets: widget
channel: directory
placement_url: "https://other.example/widget"
live: 2026-10-26
status: done
---

## Ask
List Widget.

## Draft
https://purplelink.llc/widget/?utm_source=otherdir&utm_content=widget-directory-261025
""")
    assert hub.make_utm(P, "https://purplelink.llc/widget/", "widget", "directory", today=dt.date(2026, 10, 25)).endswith("utm_content=widget-directory-261025-2")
    try:
        hub.make_utm(P, "https://example.com/", "widget", "directory"); assert False
    except SystemExit:
        pass
    # the queue item's own fields win, and its link tag is read exactly from funnelByContent
    saved = (tmp / "hub" / "funnel.json").read_text()
    f = json.loads(saved)
    f["content"] = {str(w): {"widget-directory-261025": {"channel": "otherdir", "pageviews": 5, "pageviewsByPath": {"/widget/": 5},
                                                         "trial": {"widget": 2}, "checkout": {}}} for w in hub.FUNNEL_WINDOWS}
    put("hub/funnel.json", json.dumps(f))
    run("import")
    con = db()
    q = con.execute("SELECT * FROM placements WHERE id = 'queue:q-20261025-dir'").fetchone()
    assert (q["channel"], q["url"], q["date"]) == ("directory", "https://other.example/widget", "2026-10-26"), tuple(q)
    assert "widget-directory-261025" in q["utm"]
    r = {x["metric"]: (x["value"], x["confidence"]) for x in con.execute("SELECT * FROM results WHERE placement_id = 'queue:q-20261025-dir'")}
    assert r.get("link-visits") == (5, "exact-link") and r.get("link-trials") == (2, "exact-link"), r
    assert r.get("link-orders") == (1, "exact-link"), r  # the order whose first touch carried this link's tag
    put("hub/funnel.json", saved)
    (tmp / "queue/done/2026-10-25-listing-dir.md").unlink()
    run("import")


def test_phase2_kits_rules_week_log():
    import datetime as dt
    P = hub.paths()
    rows = {r["asset"]: r for r in hub.kits(P)}
    assert rows["widget"]["state"] == "none"
    hub.kits(P, ["widget"])
    assert {r["asset"]: r for r in hub.kits(P)}["widget"]["state"] == "current"
    kit = json.loads((tmp / "hub" / "kits" / "widget.json").read_text())
    assert kit["version"] == "1.2.0" and kit["price"] == "9.99" and kit["url"] == "https://purplelink.llc/widget/"
    # the site changes: the stored kit is out of date and says what changed
    llms = (tmp / "repo/site/llms.txt").read_text()
    put("repo/site/llms.txt", llms.replace("version 1.2.0", "version 1.3.0"))
    w = {r["asset"]: r for r in hub.kits(P)}["widget"]
    assert w["state"] == "out of date" and "version" in w["changed"], w
    put("repo/site/llms.txt", llms)
    # rules: seeded once, re-check due after 90 days; account-setting actions only listed, never done
    r = {x["channel"]: x for x in hub.rules(P, today=dt.date(2026, 10, 23))}
    assert r["bluesky"]["due"] and "needs Ben's yes" in r["bluesky"]["action"]
    r = {x["channel"]: x for x in hub.rules(P, checked="bluesky", today=dt.date(2026, 10, 23))}
    assert not r["bluesky"]["due"] and r["threads"]["due"]
    assert {x["channel"]: x for x in hub.rules(P, today=dt.date(2027, 2, 1))}["bluesky"]["due"]
    # weekly loop
    run("import")
    picks, hints = hub.week_pick(P, dt.date(2026, 10, 23))
    assert len(picks) <= 5 and all(isinstance(w, str) and w for _, w in picks)
    assert "pick" in run("week", "pick") and "measured" in run("week", "measure")
    out = run("week", "measure", "--write")
    assert (tmp / "repo/docs/growth-briefs/hub").is_dir() and "wrote" in out
    # generated log: read-only view with no email addresses
    run("log")
    log = (tmp / "repo/Outreach/PLACEMENTS.md").read_text()
    assert log.startswith("# Placements (generated)") and "Do not edit" in log and not hub.EMAIL_RE.search(log)


def test_overrides():
    run("import")
    con = db()
    d = con.execute("SELECT id FROM placements WHERE target = 'Planned University'").fetchone()[0]
    lib = con.execute("SELECT id FROM placements WHERE target LIKE 'Example University%'").fetchone()[0]
    put("hub/overrides.json", json.dumps({
        lib: {"url": "https://guides.example.edu/latex", "assets": ["widget", "paper-review"], "status": "live"},
        d: {"exclude": True},
    }))
    run("import")
    con = db()
    row = con.execute("SELECT url, status FROM placements WHERE id = ?", (lib,)).fetchone()
    assert tuple(row) == ("https://guides.example.edu/latex", "live")
    assert sorted(r[0] for r in con.execute("SELECT asset_id FROM placement_assets WHERE placement_id = ?", (lib,))) == ["paper-review", "widget"]
    assert con.execute("SELECT kind FROM assets WHERE id = 'paper-review'").fetchone()[0] == "line"
    assert con.execute("SELECT count(*) FROM placements WHERE id = ?", (d,)).fetchone()[0] == 0
    (tmp / "hub" / "overrides.json").unlink()
    run("import")


def test_utm_edges():
    import datetime as dt
    P = hub.paths()
    d = dt.date(2026, 11, 2)
    # channel picks the medium, source defaults to the channel, an old tag on the link is replaced, not doubled
    u = hub.make_utm(P, "https://purplelink.llc/keyfeel/?utm_source=old&utm_content=old-tag&x=1", "keyfeel", "email", today=d)
    assert "utm_source=email&utm_medium=email&utm_campaign=hub-keyfeel&utm_content=keyfeel-email-261102" in u and "old" not in u, u
    assert "x=1" in u
    assert "utm_medium=community" in hub.make_utm(P, "https://purplelink.llc/keyfeel/", "keyfeel", "texse", today=d)
    assert "utm_medium=social" in hub.make_utm(P, "https://purplelink.llc/keyfeel/", "keyfeel", "bluesky", today=d)
    # guide ids keep only the slug in the tag
    assert "utm_content=fix-a-thing-directory-261102" in hub.make_utm(P, "https://purplelink.llc/guides/fix-a-thing/", "guide:fix-a-thing", "directory", today=d)
    # the video ledger's tags count as used
    assert "howto-x" in hub.used_contents(P)


def test_candidate_assets_and_no_response_results():
    import datetime as dt
    apps = {"LONG1": "widget"}
    assert hub.candidate_assets("release:widget:1.2.0", apps) == ["widget"]
    assert hub.candidate_assets("video:LONG1", apps) == ["widget"]
    assert hub.candidate_assets("video:UNKNOWN", apps) == []
    assert hub.candidate_assets("guide:fix-a-thing", apps) == ["guide:fix-a-thing"]
    assert hub.candidate_assets("", apps) == []
    # a social post whose link is a YouTube video is tied to the video's app through its daily candidate
    put("social/20261024-daily-video-long1.md", """---
id: "20261024-daily-video-long1"
status: "posted"
approved_by: "ben (standing, 2026-10-18)"
platforms: ["bluesky"]
link: "https://www.youtube.com/watch?v=LONG1"
daily: {"candidate": "video:LONG1", "kind": "video", "format": "link"}
results: {"bluesky": {"status": "posted", "url": "https://bsky.app/y", "posted_at": "2026-10-24T10:30:00-04:00"}}
---
""")
    run("import")
    con = db()
    assert [r[0] for r in con.execute("SELECT asset_id FROM placement_assets WHERE placement_id = 'social:20261024-daily-video-long1:bluesky'")] == ["widget"]
    # an outreach email past 28 days becomes no-response and keeps its results
    pls = [{"id": "e1", "channel": "email", "status": "no-response", "date": "2026-09-01", "url": "", "landing_url": "https://purplelink.llc/widget/", "utm": ""}]
    fun = {"asOf": "2026-10-23", "windows": {str(w): {"email": {"pageviewsByPath": {"/widget/": 3}, "trial": {}, "checkout": {}}} for w in hub.FUNNEL_WINDOWS}}
    rows = hub.placement_results(pls, {"e1": ["widget"]}, {"widget": {"kind": "product", "url": "https://purplelink.llc/widget/"}}, fun, [], {}, dt.date(2026, 10, 23))
    assert ("e1", "2026-10-23", "first-touch-visits", 3) in [r[:4] for r in rows], rows
    (tmp / "social/20261024-daily-video-long1.md").unlink()


def test_campaigns():
    import datetime as dt
    P = hub.paths()
    os.environ["PURPLELINK_MANUAL_ADS"] = str(tmp / "manual-ads.json")
    P = hub.paths()
    put("manual-ads.json", json.dumps({"appleSearchAds": {"asOf": "2026-10-05", "campaigns": [{"key": "other", "spend": 40.47}]}}))
    put("hub/campaigns.json", json.dumps({"_note": "test", "widget-test-2026-11": {
        "platformKey": "redditAds", "channel": "reddit-ads", "asset": "widget", "start": "2026-10-20", "end": "2026-11-12",
        "budget": 80, "breakEven": 18, "approval": "ben test", "readings": ["2026-11-13", "2026-12-03"],
        "ads": [{"id": "a", "label": "angle A", "url": "https://purplelink.llc/widget/?utm_source=reddit&utm_medium=cpc&utm_campaign=widget-test-2026-11&utm_content=widget-reddit-a"},
                {"id": "b", "label": "angle B", "url": "https://purplelink.llc/widget/?utm_source=reddit&utm_medium=cpc&utm_campaign=widget-test-2026-11&utm_content=widget-reddit-b"}]}}))
    pls = hub.from_campaigns(P, dt.date(2026, 10, 28))
    assert [x["id"] for x in pls] == ["campaign:widget-test-2026-11:a", "campaign:widget-test-2026-11:b"]
    assert pls[0]["status"] == "live" and pls[0]["_contents"] == ["widget-reddit-a"] and pls[0]["channel"] == "reddit-ads"
    assert hub.from_campaigns(P, dt.date(2026, 10, 1))[0]["status"] == "scheduled"
    # no reading yet: nothing reported, the report says so
    run("import")
    rows = hub.campaign_report(db(), P, dt.date(2026, 10, 28))
    assert rows[0]["spend"] is None and "no spend recorded" in rows[0]["reading"] and rows[0]["nextReading"] == "2026-11-13"
    # a campaign-wide reading lands on the first ad only, marked as a campaign total; other platforms are untouched
    hub.record_campaign_spend(P, "widget-test-2026-11", 12.5, 900, 40, as_of="2026-10-30")
    m = json.loads((tmp / "manual-ads.json").read_text())
    assert m["appleSearchAds"]["campaigns"][0]["spend"] == 40.47
    assert m["redditAds"]["campaigns"][0] == {"key": "widget-test-2026-11", "spend": 12.5, "impressions": 900, "clicks": 40}
    run("import")
    r = {x["metric"]: (x["value"], x["confidence"]) for x in db().execute("SELECT * FROM results WHERE placement_id = 'campaign:widget-test-2026-11:a'")}
    assert r["spend"] == (12.5, "reported-campaign-total") and r["clicks"][0] == 40
    assert not db().execute("SELECT 1 FROM results WHERE placement_id = 'campaign:widget-test-2026-11:b' AND metric = 'spend'").fetchone()
    # per-ad readings replace it, and the campaign line is their sum
    hub.record_campaign_spend(P, "widget-test-2026-11", 9.0, 600, 30, ad="a", as_of="2026-11-01")
    hub.record_campaign_spend(P, "widget-test-2026-11", 7.0, 500, 20, ad="b", as_of="2026-11-01")
    e = json.loads((tmp / "manual-ads.json").read_text())["redditAds"]["campaigns"][0]
    assert (e["spend"], e["clicks"], e["impressions"]) == (16.0, 50, 1100)
    # exact-link trials and an order whose first touch carried ad b's tag
    saved = (tmp / "hub" / "funnel.json").read_text()
    f = json.loads(saved)
    f["content"] = {str(w): {"widget-reddit-a": {"channel": "paid:reddit", "pageviews": 20, "pageviewsByPath": {"/widget/": 20}, "trial": {"widget": 2}, "checkout": {}, "os": {"mac": 6, "windows": 4}},
                             "widget-reddit-b": {"channel": "paid:reddit", "pageviews": 10, "pageviewsByPath": {"/widget/": 10}, "trial": {"widget": 1}, "checkout": {}}}
                    for w in hub.FUNNEL_WINDOWS}
    put("hub/funnel.json", json.dumps(f))
    hist = json.loads((tmp / "history.json").read_text())
    hist["ledger"]["r1"] = {"kind": "purchase", "product": "widget", "ts": 1793050000, "attr": {"first": {"s": "paid:reddit", "t": "widget-reddit-b"}}}
    put("history.json", json.dumps(hist))
    run("import")
    rep = hub.campaign_report(db(), P, dt.date(2026, 11, 2))[0]
    assert (rep["spend"], rep["clicks"], rep["visits"], rep["trials"], rep["orders"]) == (16.0, 50, 30, 3, 1), rep
    assert rep["costPerTrial"] == 5.33 and rep["costPerOrder"] == 16.0 and "under the $18 break-even" in rep["reading"]
    assert "not a rate" in rep["reading"]
    assert {a["ad"]: a["orders"] for a in rep["ads"]} == {"a": 0, "b": 1}
    # visitor OS summed over the ad links (ad b has no os field: older stats)
    assert rep["os"] == {"mac": 6, "windows": 4}
    assert hub.os_line(rep["os"]) == "mac 6 of 10 (60%); windows 4" and hub.os_line({}) == ""
    assert "mac 6 of 10 (60%)" in run("campaigns")
    assert "widget-test-2026-11" in run("campaigns")
    try:
        hub.record_campaign_spend(P, "nope", 1.0, None, None); assert False
    except SystemExit:
        pass
    # restore shared fixtures
    put("hub/funnel.json", saved)
    del hist["ledger"]["r1"]
    put("history.json", json.dumps(hist))
    (tmp / "hub" / "campaigns.json").unlink()
    run("import")


def test_doctor():
    import datetime as dt
    P = hub.paths()
    run("import")
    con = db()
    # links: a 404, a redirect to 200, an unverifiable host, and a refusal; only the 404 is reported
    urls = ["https://dir.example/widget", "https://bsky.app/x", "https://purplelink.llc/widget/", "https://www.reddit.com/r/x/"]

    def fake(u):
        return {"https://dir.example/widget": (404, u), "https://purplelink.llc/widget/": (200, u)}.get(u, (200, u))
    store = hub.check_links(P, urls, get=fake)
    assert store["https://www.reddit.com/r/x/"]["status"] is None and "refuses" in store["https://www.reddit.com/r/x/"]["note"]
    d = hub.doctor(con, P, dt.date(2026, 10, 28))
    bad = [(b["url"], b["status"]) for b in d["bad_links"]]
    assert ("https://dir.example/widget", 404) in bad and all(s != 200 for _, s in bad), bad
    # a how-to video and its Short each have their own tag (the Short's is recorded or <tag>-short): no duplicate
    dups = {x["utm_content"]: x for x in d["duplicates"]}
    assert "howto-x" not in dups and "howto-x-short" not in dups, dups
    # every live placement without a result says why
    assert all(m["why"] for m in d["missing"])
    out = run("doctor")
    assert "links that did not answer 200" in out and "dir.example" in out
    # Stack Exchange answers are checked through the API: a deleted answer is a 404, a live one a 200
    se = hub.check_links(P, ["https://tex.stackexchange.com/a/1", "https://tex.stackexchange.com/a/2", "https://medium.com/@x"], get=fake,
                         se_fetch=lambda u: {"items": [{"answer_id": 1}]} if "/answers/1?" in u else {"items": []})
    assert se["https://tex.stackexchange.com/a/1"]["status"] == 200 and se["https://tex.stackexchange.com/a/2"]["status"] == 404
    assert se["https://medium.com/@x"]["status"] is None
    (tmp / "hub" / "links.json").unlink()


def test_campaign_decisions_and_ad_check():
    import datetime as dt
    c = {"readings": ["2026-11-13", "2026-11-20", "2026-12-03"], "breakEven": 18,
         "rules": {"2026-11-13": "stop-if-no-trials", "2026-11-20": "look", "2026-12-03": "verdict"}}
    ads = [{"ad": "a", "orders": 0, "trials": 1, "visits": 9}, {"ad": "b", "orders": 2, "trials": 3, "visits": 7}]

    def row(trials, orders, spend):
        return {"trials": trials, "orders": orders, "spend": spend, "ads": ads,
                "costPerTrial": round(spend / trials, 2) if trials else None,
                "costPerOrder": round(spend / orders, 2) if orders else None}
    d = hub.campaign_decision(c, row(0, 0, 30.0), dt.date(2026, 11, 12))
    assert d["stage"] is None and "first reading (2026-11-13)" in d["text"]
    assert hub.campaign_decision(c, row(0, 0, 80.0), dt.date(2026, 11, 13))["text"].startswith("stop: 0 trial downloads from $80.00")
    d = hub.campaign_decision(c, row(4, 0, 80.0), dt.date(2026, 11, 14))
    assert d["text"].startswith("keep reading: 4 trials at $20.00 each") and d["due"] == "2026-11-20"
    assert hub.campaign_decision(c, row(4, 1, 80.0), dt.date(2026, 11, 20))["text"].startswith("look only")
    assert hub.campaign_decision(c, row(4, 1, 80.0), dt.date(2026, 12, 3))["text"] == "no second round: 1 order by 2026-12-03"
    d = hub.campaign_decision(c, row(5, 5, 80.0), dt.date(2026, 12, 3))
    assert d["text"].startswith("one more 10-day round with ad b: 5 orders at $16.00") and d["due"] is None
    assert "over the $18 break-even" in hub.campaign_decision(c, row(5, 2, 80.0), dt.date(2026, 12, 4))["text"]
    # ad check: missing data, too few impressions, about even, clearly trails
    today = dt.date(2026, 11, 3)
    assert "no per-ad" in hub.ad_ctr_check([{"ad": "a", "clicks": 5, "impressions": None}], "2026-11-03", today)["verdict"]
    r = hub.ad_ctr_check([{"ad": "a", "clicks": 2, "impressions": 300}, {"ad": "b", "clicks": 9, "impressions": 300}], "2026-11-03", today)
    assert r["isDue"] and "too few impressions" in r["verdict"] and r["trailing"] is None
    r = hub.ad_ctr_check([{"ad": "a", "clicks": 10, "impressions": 2000}, {"ad": "b", "clicks": 12, "impressions": 2000}], None, today)
    assert "about even" in r["verdict"] and r["p"] > 0.5 and r["ctr"] == {"a": 0.005, "b": 0.006}
    r = hub.ad_ctr_check([{"ad": "a", "clicks": 40, "impressions": 4000}, {"ad": "b", "clicks": 10, "impressions": 4000}], "2026-11-03", today)
    assert r["trailing"] == "b" and r["p"] < 0.001 and "ad b clearly trails" in r["verdict"]


def test_rechecks():
    import datetime as dt
    P = hub.paths()
    run("import")
    con = db()
    con.execute("DELETE FROM channel_stats")
    con.executemany("INSERT INTO channel_stats VALUES (?,?,?,?,?,?,?,?,?,?,?)", [
        ("widget", "email", 60, 5, 1, 0, 0, None, None, "unmeasured", ""),
        ("gadget", "email", 3, 4, 0, 0, 0, None, None, "building", ""),
        ("widget", "directory", 2, 1, 0, 0, 0, None, None, "building", "")])
    con.execute("INSERT INTO placements VALUES ('t1', 'test', 'directory', 'listing', 'On My Menubar: resubmit Widget', "
                "'queued', '2026-10-28', '', '', '', '', '', '', '', '', '')")
    con.commit()
    put("hub/rechecks.json", json.dumps({"_note": "test", "widget-email": {
        "question": "keep or pause widget email", "due": "2026-11-08", "product": "widget", "channel": "email",
        "baseline": {"date": "2026-10-25", "placements": 52, "visits": 2, "trials": 0, "orders": 0}, "rule": "pause if 0 trials"},
        "dirs": {"question": "did directories bring visits", "due": "2026-11-25", "product": "*", "channel": "directory",
                 "baseline": {"date": "2026-10-28", "visits": 0}, "targets": ["On My Menubar", "Nowhere"]}}))
    rows = hub.recheck_report(con, P, dt.date(2026, 11, 8))
    assert [r["id"] for r in rows] == ["widget-email", "dirs"]
    e = rows[0]
    assert e["isDue"] and e["daysLeft"] == 0 and e["current"] == {"placements": 60, "visits": 5, "trials": 1, "orders": 0}
    assert e["change"] == {"placements": 8, "visits": 3, "trials": 1, "orders": 0}
    assert "+3 first-touch visits, +1 trials" in e["reading"] and "window has moved" not in e["reading"]
    d = rows[1]
    assert not d["isDue"] and d["daysLeft"] == 17 and d["current"]["visits"] == 1
    assert [(t["target"], t["status"]) for t in d["targets"]] == [("On My Menubar", "queued"), ("Nowhere", "none")]
    assert "0 of 2 submissions live" in d["reading"]
    assert "window has moved" in hub.recheck_report(con, P, dt.date(2026, 12, 20))[0]["reading"]
    out = run("rechecks")
    assert "widget-email" in out and "rule: pause if 0 trials" in out
    # the export carries the reading but not the target list
    ex = hub.export_rows(P)["marketing_rechecks"]
    assert {r["id"] for r in ex} == {"widget-email", "dirs"} and all("targets" not in r for r in ex)
    (tmp / "hub" / "rechecks.json").unlink()
    run("import")


def test_one_listing_is_one_placement():
    """A listing URL logged several times (the submission, a later update, the MacUpdate tracker) is one placement:
    otherwise each row gets the listing's full visits and the channel's visits per placement are divided by N."""
    log = tmp / "repo/Outreach/OUTREACH-LOG.md"
    orig = log.read_text()
    log.write_text(orig + """
## MacUpdate submissions

| Date | Where | App | Status | Note |
|---|---|---|---|---|
| 2026-10-10 | MacUpdate | Gadget | submitted | https://gadget.macupdate.com/ |
| 2026-10-18 | MacUpdate | Gadget | update submitted | https://gadget.macupdate.com/ |
""")
    try:
        run("import")
        con = db()
        rows = list(con.execute("SELECT * FROM placements WHERE url LIKE '%gadget.macupdate.com%'"))
        assert [r["id"] for r in rows] == ["macupdate:gadget"], [tuple(r) for r in rows]
        g = rows[0]
        assert g["date"] == "2026-10-10" and g["contact_ref"].startswith("OUTREACH-LOG.md:"), tuple(g)
        # its MacUpdate download readings stay attached to it
        assert con.execute("SELECT count(*) FROM results WHERE placement_id = 'macupdate:gadget' AND metric = 'downloads-total'").fetchone()[0] == 2
    finally:
        log.write_text(orig)
def test_social_engine_rows_under_a_headerless_table():
    """The social engine appends one row per post at the end of the outreach log, under whatever heading is last, with
    no table header of its own. Every such row is a mirror of a social queue item (Instagram and Facebook included),
    and a row that is not keeps its own date and platform rather than the heading's."""
    log = tmp / "repo/Outreach/OUTREACH-LOG.md"
    orig = log.read_text()
    put("social/20261029-ig-reel-abc.md", """---
id: "20261029-ig-reel-abc"
status: "posted"
approved_by: "ben (standing, 2026-10-23)"
platforms: ["instagram"]
campaign: "ig-reel"
link: "https://purplelink.llc/widget/"
results: {"instagram": {"status": "posted", "url": "https://www.instagram.com/reel/X/", "posted_at": "2026-10-29T07:16:39-04:00"}}
---

## instagram
A Reel.
""")
    log.write_text(orig + """
### AlternativeTo: Gadget linked to Widget (2026-10-20, q-20261020-alto, approved by Ben)
Done in Chrome.
| 2026-10-21 | linkedin: 20261021-daily-release-widget-1-2 | https://www.linkedin.com/company/1/admin/ | posted | queue item 20261021-daily-release-widget-1-2 |
| 2026-10-29 | instagram: 20261029-ig-reel-abc | https://www.instagram.com/reel/X/ | posted | queue item 20261029-ig-reel-abc |
| 2026-10-29 | facebook: 20261029-fb-reel-gone | https://www.facebook.com/reel/1/ | posted | queue item 20261029-fb-reel-gone |
""")
    try:
        run("import")
        rows = list(db().execute("SELECT * FROM placements WHERE source = 'outreach-log'"))
        assert not [r for r in rows if r["target"].startswith(("instagram:", "linkedin:"))], [tuple(r) for r in rows]
        assert not [r for r in rows if r["channel"] == "alternativeto"], [tuple(r) for r in rows]
        fb = next(r for r in rows if r["target"].startswith("facebook:"))
        assert fb["channel"] == "facebook" and fb["date"] == "2026-10-29" and fb["status"] == "live", tuple(fb)
    finally:
        log.write_text(orig)
        (tmp / "social/20261029-ig-reel-abc.md").unlink()
        run("import")


def test_pull_request_on_someone_elses_repo_is_a_placement():
    """A queue "pr" item that opened a pull request on another owner's GitHub repo (an awesome list) is an outward
    placement; a PR on our own repos is not."""
    put("queue/done/2026-10-09-pr-awesome.md", """---
id: q-20261009-aw1
created: 2026-10-09T08:00:00-04:00
kind: pr
target: "GitHub PR: someone/awesome-things, Widget under Tools"
status: done
---

## Ask
Open a PR adding Widget, https://purplelink.llc/widget/

## Result
PR opened from Ben's account 2026-10-11: https://github.com/someone/awesome-things/pull/55 (2026-10-11T17:56-04:00)
""")
    put("queue/done/2026-10-12-pr-site.md", """---
id: q-20261012-own
created: 2026-10-12T08:00:00-04:00
kind: pr
target: "site/guides: a new guide about Widget"
status: done
---

## Result
https://github.com/purplelink-llc/purplelink/pull/9 merged (2026-10-12T10:00-04:00)
""")
    try:
        run("import")
        con = db()
        row = con.execute("SELECT * FROM placements WHERE id = 'queue:q-20261009-aw1'").fetchone()
        assert row is not None
        assert row["channel"] == "github" and row["status"] == "live" and row["date"] == "2026-10-11", tuple(row)
        assert row["url"] == "https://github.com/someone/awesome-things/pull/55"
        assert assets_of(con, "queue:q-20261009-aw1") == ["widget"]
        assert con.execute("SELECT count(*) FROM placements WHERE id = 'queue:q-20261012-own'").fetchone()[0] == 0
    finally:
        (tmp / "queue/done/2026-10-09-pr-awesome.md").unlink()
        (tmp / "queue/done/2026-10-12-pr-site.md").unlink()
        run("import")


def test_reddit_ads_traffic_and_orders_reach_the_campaign():
    """The ads' first touch reads "paid:reddit" (analytics.js folds utm_medium=cpc), not "reddit": the campaign's
    channel figure must count it, organic Reddit must not, and orders flagged reddit_ad by checkout count for the
    campaign, and for an ad when the buyer's first touch kept that ad's tag."""
    import datetime as dt
    P = hub.paths()
    put("hub/campaigns.json", json.dumps({"widget-test-2026-11": {
        "platformKey": "redditAds", "channel": "reddit-ads", "asset": "widget", "start": "2026-10-20", "end": "2026-11-12",
        "budget": 80, "breakEven": 18, "approval": "ben test", "readings": ["2026-11-13"],
        "ads": [{"id": "a", "label": "angle A", "url": "https://purplelink.llc/widget/?utm_source=reddit&utm_medium=cpc&utm_campaign=widget-test-2026-11&utm_content=widget-reddit-a"},
                {"id": "b", "label": "angle B", "url": "https://purplelink.llc/widget/?utm_source=reddit&utm_medium=cpc&utm_campaign=widget-test-2026-11&utm_content=widget-reddit-b"}]}}))
    saved_f, saved_h = (tmp / "hub" / "funnel.json").read_text(), (tmp / "history.json").read_text()
    f = json.loads(saved_f)
    for w in hub.FUNNEL_WINDOWS:
        f["windows"][str(w)] = dict(f["windows"][str(w)], **{
            "paid:reddit": {"pageviews": 25, "pageviewsByPath": {"/widget/": 24, "/guides/x/": 1}, "trial": {"widget": 1}, "checkout": {}},
            "reddit": {"pageviews": 7, "pageviewsByPath": {"/widget/": 7}, "trial": {}, "checkout": {}}})
    put("hub/funnel.json", json.dumps(f))
    h = json.loads(saved_h)
    h["ledger"].update({
        # as sales.mjs writes them: source and medium, not the folded label
        "ra": {"kind": "purchase", "product": "widget", "ts": 1793050000, "reddit": {"ad": True, "click": True},
               "attr": {"first": {"s": "reddit", "m": "cpc", "t": "widget-reddit-a"}}},
        # restored from the pl_attr cookie: paid:reddit but no tag, so no ad
        "rc": {"kind": "purchase", "product": "widget", "ts": 1793050000, "reddit": {"ad": True, "click": False},
               "attr": {"first": {"s": "reddit", "m": "cpc", "c": "attr-cookie"}}},
        # flagged by checkout with no first touch at all (storage blocked, no cookie channel)
        "rf": {"kind": "purchase", "product": "widget", "ts": 1793050000, "reddit": {"ad": True, "click": True}},
        # an organic Reddit buyer stays organic
        "ro": {"kind": "purchase", "product": "widget", "ts": 1793050000, "attr": {"first": {"s": "reddit"}}},
    })
    put("history.json", json.dumps(h))
    try:
        assert hub.first_touch_key({"s": "reddit", "m": "cpc"}) == "paid:reddit"
        assert hub.first_touch_key({"g": 1}) == "paid:google" and hub.first_touch_key({"s": "reddit"}) == "reddit"
        run("import")
        con = db()
        ch = {r["channel"]: r for r in con.execute("SELECT * FROM channel_stats WHERE product = 'widget'")}
        assert ch["reddit-ads"]["visits"] == 24 and ch["reddit-ads"]["trials"] == 1, dict(ch["reddit-ads"])
        assert ch["reddit-ads"]["orders"] == 3, dict(ch["reddit-ads"])
        res = {(r[0], r[1]): r[2] for r in con.execute("SELECT placement_id, metric, value FROM results WHERE placement_id LIKE 'campaign:%'")}
        assert res[("campaign:widget-test-2026-11:a", "first-touch-visits")] == 24
        rep = hub.campaign_report(con, P, dt.date(2026, 11, 2))[0]
        assert rep["orders"] == 3 and rep["redditFlagged"] == 3, rep
        assert {a["ad"]: a["orders"] for a in rep["ads"]} == {"a": 1, "b": 0}
        assert rep["ordersNoAd"] == 2, rep
    finally:
        put("hub/funnel.json", saved_f)
        put("history.json", saved_h)
        (tmp / "hub" / "campaigns.json").unlink()
        run("import")


def test_doctor_catches_overrides_that_no_longer_point_at_their_row():
    """Outreach placement ids are line numbers. A pinned override records its row's text; an edit above the row moves
    the line, and the doctor must say which override lost its row and where that row went."""
    P = hub.paths()
    log = tmp / "repo/Outreach/OUTREACH-LOG.md"
    saved_log = log.read_text()
    ov = tmp / "hub" / "overrides.json"
    saved_ov = ov.read_text() if ov.exists() else None
    n = next(i for i, l in enumerate(saved_log.splitlines(), 1) if l.startswith("| 2026-10-01 | Example University"))
    try:
        put("hub/overrides.json", json.dumps({"_note": "t", f"outreach:{n}": {"status": "replied"},
                                              "outreach:1": {"status": "live"}}))
        d = hub.doctor(db(), P)
        pins = {x["id"]: x for x in d["pins"]}
        assert pins[f"outreach:{n}"]["problem"] == "unpinned", pins
        assert pins["outreach:1"]["problem"] == "not a log row", pins
        # --pin records the row text for every unpinned override that points at a row, and nothing else
        assert hub.pin_overrides(P) == [f"outreach:{n}"]
        o = json.loads(ov.read_text())
        assert o[f"outreach:{n}"]["_row"].startswith("2026-10-01 | Example University"), o
        assert "_row" not in o["outreach:1"]
        assert f"outreach:{n}" not in {x["id"] for x in hub.doctor(db(), P)["pins"]}
        # a line inserted above the row: the override now points at another line, and the doctor says where it went
        lines = saved_log.splitlines()
        lines.insert(n - 3, "Inserted paragraph above the table.")
        log.write_text("\n".join(lines) + "\n")
        pins = {x["id"]: x for x in hub.doctor(db(), P)["pins"]}
        assert pins[f"outreach:{n}"]["problem"] == "row moved", pins
        assert pins[f"outreach:{n}"]["now"] == [f"outreach:{n + 1}"], pins
        assert "row moved" in run("doctor")
        # a checkout without the git-ignored log: one finding, not a false "not a log row" per override
        pins = hub.override_pins(dict(P, outreach=tmp / "nowhere" / "OUTREACH-LOG.md"))
        assert [x["id"] for x in pins] == ["OUTREACH-LOG.md"], pins
    finally:
        log.write_text(saved_log)
        if saved_ov is None:
            ov.unlink()
        else:
            ov.write_text(saved_ov)


def test_doctor_notices_missing_reddit_attribution_fields():
    """From the 2026-10-29 evening build every Stripe purchase carries sales.mjs's `reddit` field, an ad buyer's
    order carries both the checkout flag and a paid:reddit first touch, and that first touch keeps the ad's tag
    (pl_attr v2). A purchase missing any of them is a broken link in the chain, and the doctor must name it."""
    P = hub.paths()
    saved_h = (tmp / "history.json").read_text()
    h = json.loads(saved_h)
    h["ledger"].update({
        # before the fields existed: never flagged
        "old": {"kind": "purchase", "product": "widget", "ts": 1793050000},
        # complete: flag, paid first touch, ad tag
        "ok": {"kind": "purchase", "product": "widget", "ts": 1793577600, "reddit": {"ad": True, "click": True},
               "attr": {"first": {"s": "reddit", "m": "cpc", "t": "widget-reddit-a"}}},
        "plain": {"kind": "purchase", "product": "widget", "ts": 1793577600, "reddit": None,
                  "attr": {"first": {"s": "www.google.com"}}},
        "nofield": {"kind": "purchase", "product": "widget", "ts": 1793577600},
        "noflag": {"kind": "purchase", "product": "widget", "ts": 1793577600, "reddit": None,
                   "attr": {"first": {"s": "reddit", "m": "cpc", "t": "widget-reddit-b"}}},
        "notouch": {"kind": "purchase", "product": "widget", "ts": 1793577600, "reddit": {"ad": True, "click": False}},
        "notag": {"kind": "purchase", "product": "widget", "ts": 1793577600, "reddit": {"ad": True, "click": True},
                  "attr": {"first": {"s": "reddit", "m": "cpc", "c": "attr-cookie"}}},
        # marketplace sales never pass through sales.mjs
        "mkt": {"kind": "order", "product": "widget", "ts": 1793577600},
    })
    put("history.json", json.dumps(h))
    try:
        gaps = {x["id"]: x["problem"] for x in hub.attribution_gaps(P)}
        assert gaps == {"nofield": "no reddit field", "noflag": "paid:reddit first touch, no reddit_ad flag",
                        "notouch": "reddit_ad flag, no first touch", "notag": "paid:reddit first touch, no ad tag"}, gaps
        out = run("doctor")
        assert "4 purchases since 2026-10-30 missing an attribution field" in out, out
        assert "nofield" in out and "no ad tag" in out
    finally:
        put("history.json", saved_h)


def test_doctor_flags_campaigns_with_no_spend_or_no_trials():
    """A running campaign whose spend was never recorded has no cost figures at all, and one whose ad traffic brings
    no trials for a week has either a broken trial link or an ad that does not convert: the doctor names both."""
    import datetime as dt
    P = hub.paths()
    put("hub/campaigns.json", json.dumps({"widget-test-2026-11": {
        "platformKey": "redditAds", "channel": "reddit-ads", "asset": "widget", "start": "2026-10-20", "end": "2026-11-12",
        "budget": 80, "breakEven": 18, "approval": "ben test", "readings": ["2026-11-13"],
        "ads": [{"id": "a", "label": "angle A", "url": "https://purplelink.llc/widget/?utm_source=reddit&utm_medium=cpc&utm_campaign=widget-test-2026-11&utm_content=widget-reddit-a"}]}}))
    saved_f = (tmp / "hub" / "funnel.json").read_text()
    ads = P["manual_ads"]
    saved_ads = ads.read_text() if ads.exists() else None
    f = json.loads(saved_f)
    f["windows"]["7"] = dict(f["windows"]["7"], **{"paid:reddit": {
        "pageviews": 120, "pageviewsByPath": {"/widget/": 120}, "trial": {}, "checkout": {}}})
    put("hub/funnel.json", json.dumps(f))
    ads.write_text("{}")  # no spend reading, whatever earlier tests recorded
    try:
        run("import")
        found = {x["problem"] for x in hub.campaign_gaps(db(), P, dt.date(2026, 11, 2))}
        assert found == {"no spend recorded", "no trials"}, found
        # one day in, a missing spend reading is not news yet
        assert "no spend recorded" not in {x["problem"] for x in hub.campaign_gaps(db(), P, dt.date(2026, 10, 21))}
        # long after the campaign, neither applies
        assert hub.campaign_gaps(db(), P, dt.date(2026, 12, 30)) == []
        hub.record_campaign_spend(P, "widget-test-2026-11", 30.0, 4000, 110, as_of="2026-11-01")
        f["windows"]["7"]["paid:reddit"]["trial"] = {"widget": 1}
        put("hub/funnel.json", json.dumps(f))
        run("import")
        assert hub.campaign_gaps(db(), P, dt.date(2026, 11, 2)) == []
        assert "0 campaign problems" in run("doctor")
    finally:
        put("hub/funnel.json", saved_f)
        if saved_ads is None:
            ads.unlink(missing_ok=True)
        else:
            ads.write_text(saved_ads)
        (tmp / "hub" / "campaigns.json").unlink()
        run("import")


def test_doctor_notices_a_campaign_that_stopped_serving():
    """Reddit showed no impressions on 2026-10-29 and the ad manager cannot be opened from this Mac. A running campaign
    that had first-touch visits and has none in the last day has most likely stopped serving; a stats fetch that
    times out must say it could not check, never raise the alarm."""
    import datetime as dt
    P = hub.paths()
    put("hub/campaigns.json", json.dumps({"widget-test-2026-11": {
        "platformKey": "redditAds", "channel": "reddit-ads", "asset": "widget", "start": "2026-10-20", "end": "2026-11-12",
        "budget": 80, "breakEven": 18, "approval": "ben test", "readings": ["2026-11-13"],
        "ads": [{"id": "a", "label": "angle A", "url": "https://purplelink.llc/widget/?utm_source=reddit&utm_medium=cpc&utm_campaign=widget-test-2026-11&utm_content=widget-reddit-a"}]}}))
    saved_f = (tmp / "hub" / "funnel.json").read_text()
    f = json.loads(saved_f)
    f["windows"]["7"] = dict(f["windows"]["7"], **{"paid:reddit": {
        "pageviews": 39, "pageviewsByPath": {"/widget/": 39}, "trial": {}, "checkout": {}}})
    put("hub/funnel.json", json.dumps(f))
    day = dt.date(2026, 11, 2)
    seen = []

    def serving(days):
        seen.append(days)
        return {"paid:reddit": {"pageviews": 2}}

    def stopped(days):
        return {"www.google.com": {"pageviews": 30}}

    def timed_out(days):
        return None
    try:
        run("import")
        probs = lambda get: {x["problem"]: x["detail"] for x in hub.campaign_gaps(db(), P, day, recent=get)}
        assert "not serving" not in probs(serving) and seen == [1], seen
        got = probs(stopped)
        assert "ads may have stopped serving: check billing, ad review status and bid in the ad manager" in got["not serving"], got
        got = probs(timed_out)
        assert "not serving" not in got and "could not check" in got["delivery not checked"], got
        # after the campaign ended, no delivery check (and no fetch)
        seen.clear()
        assert "not serving" not in {x["problem"] for x in hub.campaign_gaps(db(), P, dt.date(2026, 11, 15), recent=serving)}
        assert seen == []
        # never had visits: nothing to compare against
        f["windows"]["7"]["paid:reddit"]["pageviews"] = 0
        put("hub/funnel.json", json.dumps(f))
        assert "not serving" not in probs(stopped)
        # a fetch that raises is a failed check, not a crash
        assert hub.fetch_recent(P, 1, get=lambda url, headers: (_ for _ in ()).throw(TimeoutError())) is None
    finally:
        put("hub/funnel.json", saved_f)
        (tmp / "hub" / "campaigns.json").unlink()
        run("import")


if __name__ == "__main__":
    test_all()
    test_doctor_notices_a_campaign_that_stopped_serving()
    test_doctor_flags_campaigns_with_no_spend_or_no_trials()
    test_doctor_notices_missing_reddit_attribution_fields()
    test_sources_untouched()
    test_results_and_followups()
    test_follow_up_rules()
    test_stop_rule_and_interval()
    test_listing_checks()
    test_fetch_funnel_keeps_token_out_of_url()
    test_funnel_stale_until_fetched_on_the_day()
    test_export_has_no_contacts()
    test_phase2_tags_and_link_results()
    test_phase2_kits_rules_week_log()
    test_overrides()
    test_utm_edges()
    test_candidate_assets_and_no_response_results()
    test_campaigns()
    test_campaign_decisions_and_ad_check()
    test_rechecks()
    test_doctor()
    test_one_listing_is_one_placement()
    test_social_engine_rows_under_a_headerless_table()
    test_pull_request_on_someone_elses_repo_is_a_placement()
    test_reddit_ads_traffic_and_orders_reach_the_campaign()
    test_doctor_catches_overrides_that_no_longer_point_at_their_row()
    print("ok")


def test_long_video_and_its_short_never_share_a_tag():
    """Fails if any ledger entry's long video and Short come out of the hub with the same utm_content."""
    P = hub.paths()
    vids = hub.from_videos(P)
    by_tag = {}
    for v in vids:
        for t in v["_contents"]:
            by_tag.setdefault(t, []).append(v["id"])
    assert all(len(ids) == 1 for ids in by_tag.values()), by_tag
    # a recorded Short tag wins over the derived one
    assert hub.video_tag({"link_utm_content": "a", "short_utm_content": "a-short-2"}, "short_id") == "a-short-2"
    assert hub.video_tag({"link_utm_content": "a"}, "short_id") == "a-short"
    # and the real ledger in this repo holds no pair that shares a tag
    import json as _json
    real = _json.loads((Path(hub.__file__).resolve().parents[2] / "video" / "howto" / "ledger.json").read_text())
    for v in real:
        if v.get("long_id") and v.get("short_id"):
            assert hub.video_tag(v, "long_id") != hub.video_tag(v, "short_id") or not hub.video_tag(v, "long_id"), v["slug"]


def test_utm_takes_a_preferred_content_and_medium():
    P = hub.paths()
    u = hub.make_utm(P, "https://purplelink.llc/widget/", "widget", "youtube-short", source="youtube",
                     campaign="howto-link-test", content="howto-new-short")
    assert u.endswith("?utm_source=youtube&utm_medium=short&utm_campaign=howto-link-test&utm_content=howto-new-short")
    # a preferred tag that is taken gets -2 ("howto-x" is in the ledger)
    assert hub.make_utm(P, "https://purplelink.llc/widget/", "widget", "youtube", content="howto-x").endswith(
        "utm_content=howto-x-2")
    assert "utm_medium=email" in hub.make_utm(P, "https://purplelink.llc/widget/", "widget", "youtube", medium="email")
