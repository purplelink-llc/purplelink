#!/usr/bin/env python3
"""Offline tests for hub.py on synthetic sources. Run: python3 scripts/hub/test_hub.py"""
import contextlib, importlib.util, io, json, os, sqlite3, tempfile
from pathlib import Path

tmp = Path(tempfile.mkdtemp())
os.environ.update({
    "PURPLELINK_HUB": str(tmp / "hub"), "PURPLELINK_QUEUE": str(tmp / "queue"), "PURPLELINK_REPO": str(tmp / "repo"),
    "PURPLELINK_SOCIAL_QUEUE": str(tmp / "social"), "PURPLELINK_TRAFFIC_HISTORY": str(tmp / "history.json"),
})
spec = importlib.util.spec_from_file_location("hub", Path(__file__).with_name("hub.py"))
hub = importlib.util.module_from_spec(spec); spec.loader.exec_module(hub)


def put(rel, text):
    p = tmp / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


put("repo/site/llms.txt", """## Products — available now

### Widget (macOS)
- **Trial and purchase:** https://purplelink.llc/widget/

### Gadget Pro (macOS)
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
put("history.json", json.dumps({"macupdate": {"gadget": {"url": "https://gadget.macupdate.com/",
                                                         "snapshots": {"2026-10-18": {"downloads": 5, "price": 9.99, "version": "1.0"},
                                                                       "2026-10-19": {"downloads": 7, "price": 9.99, "version": "1.1"}}}}}))


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
    assert [r[0] for r in con.execute("SELECT value FROM results WHERE placement_id = 'macupdate:gadget' ORDER BY date")] == [5, 7]

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


if __name__ == "__main__":
    test_all()
    test_sources_untouched()
    print("ok")
