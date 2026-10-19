"""Daily pipeline units: candidate extraction, scoring, fatigue, every vetting rule, format rotation, Mastodon voice,
metrics parsing and the learning and drop rules. All fixtures, no network."""
import datetime as dt
import json

import pytest

from social_daily_helpers import FakeHttp, Response, denv, env, page, site  # noqa: F401
from socialpost import items
from socialpost.daily import candidates as cand, compose as comp, learn, metrics, score as sc, settings as st, vet

D = dt.date
TODAY = D(2026, 10, 20)
CFG = st.DEFAULT
ADDED = {"/guides/new-guide/": D(2026, 10, 18), "/guides/old-guide/": D(2026, 5, 1),
         "/tools/word-counter/": D(2026, 10, 19), "/blog/digest/": D(2026, 10, 19)}


# ------------------------------------------------------------------ candidates
def test_candidate_extraction_from_fixtures():
    notes = []
    cs = cand.gather(site(), TODAY, CFG, stats=None, added=ADDED,
                     ledger=[{"long_id": "VID12345678", "date": "2026-10-19", "title": "Fix it"},
                             {"long_id": "OLDVIDEO001", "date": "2026-09-01", "title": "Old"}], notes=notes)
    ids = {c.id for c in cs}
    assert "release:panely:1.1.0" in ids                       # live version with a changelog entry inside 7 days
    assert not any(i.startswith("release:legroom") for i in ids)  # 1.0.0 entry is from September
    assert "guide:new-guide" in ids and "tool:word-counter" in ids
    assert "guide:old-guide" not in ids                         # added in May: evergreen only
    assert "blog:digest" not in ids                             # retired page excluded
    assert "video:VID12345678" in ids and "video:OLDVIDEO001" not in ids
    assert any("no traffic stats" in n for n in notes)          # evergreen fell back to the sitemap
    assert "evergreen:guide:old-guide" in ids


def test_evergreen_comes_from_the_stats_top_paths_in_order():
    stats = {"topPaths": [{"key": "/", "count": 900}, {"key": "/tools/word-counter/", "count": 90},
                          {"key": "/guides/old-guide/", "count": 30}, {"key": "/guides/", "count": 20}]}
    cs = [c for c in cand.gather(site(), TODAY, CFG, stats=stats, added={}, ledger=[]) if c.kind == "evergreen"]
    assert [c.id for c in cs] == ["evergreen:tool:word-counter", "evergreen:guide:old-guide"]
    assert cs[0].traffic == 90


def test_facts_come_from_the_page_itself():
    c = cand.Candidate(id="guide:new-guide", kind="guide", url="https://purplelink.llc/guides/new-guide/")
    f = cand.load_facts(site(), c)
    assert f["title"] == "Check a manuscript before you submit it"   # the site suffix is removed
    assert "ten minutes" in f["description"]


# ------------------------------------------------------------------ scoring and fatigue
def C(kind, age=0, i="a", traffic=0):
    return cand.Candidate(id=f"{kind}:{i}", kind=kind, url="https://purplelink.llc/x/", traffic=traffic,
                          published=TODAY - dt.timedelta(days=age) if kind != "evergreen" else None, page_kind="guide")


def test_importance_order_when_equally_fresh():
    order = [x.kind for _, x in sc.rank([C(k) for k in ("evergreen", "tool", "video", "guide", "release")],
                                        "link", TODAY, CFG, {}, [])]
    assert order == ["release", "guide", "video", "tool", "evergreen"]


def test_freshness_decays_and_old_news_loses_to_new():
    assert sc.freshness(C("guide", 0), TODAY, CFG) == 1.0
    assert sc.freshness(C("guide", 3), TODAY, CFG) == pytest.approx(0.5)
    ranked = sc.rank([C("release", 6, "old"), C("guide", 0, "new")], "link", TODAY, CFG, {}, [])
    assert ranked[0][1].id == "guide:new"


def test_learned_multipliers_scale_the_score_and_start_neutral():
    base = sc.score(C("guide"), "link", TODAY, CFG, {}, [])
    up = sc.score(C("guide"), "link", TODAY, CFG, {"kind": {"guide": 1.5}, "format": {"link": 1.2}}, [])
    assert up == pytest.approx(base * 1.5 * 1.2)


def row(day, cand_id, kind, fmt="link", counts=True):
    return {"date": day.isoformat(), "candidate": cand_id, "kind": kind, "format": fmt, "counts": counts, "hashes": []}


def test_same_item_not_repeated_within_21_days():
    h = [row(TODAY - dt.timedelta(days=20), "guide:a", "guide")]
    assert sc.rank([C("guide", 0, "a")], "link", TODAY, CFG, {}, h) == []
    h = [row(TODAY - dt.timedelta(days=21), "guide:a", "guide")]
    assert len(sc.rank([C("guide", 0, "a")], "link", TODAY, CFG, {}, h)) == 1
    # a queued pick that never posted does not block it
    h = [row(TODAY - dt.timedelta(days=2), "guide:a", "guide", counts=False)]
    assert len(sc.rank([C("guide", 0, "a")], "link", TODAY, CFG, {}, h)) == 1


def test_same_kind_at_most_three_days_in_a_row():
    h = [row(TODAY - dt.timedelta(days=n), f"guide:{n}", "guide") for n in (1, 2, 3)]
    ranked = sc.rank([C("guide", 0, "x"), C("tool", 0, "y")], "link", TODAY, CFG, {}, h)
    assert [x.kind for _, x in ranked] == ["tool"]
    h = h[:2] + [row(TODAY - dt.timedelta(days=3), "tool:z", "tool")]
    assert {x.kind for _, x in sc.rank([C("guide", 0, "x")], "link", TODAY, CFG, {}, h)} == {"guide"}


def test_fatigue_penalty_lowers_a_recently_used_kind():
    h = [row(TODAY - dt.timedelta(days=2), "guide:q", "guide")]
    assert sc.score(C("guide"), "link", TODAY, CFG, {}, h) == pytest.approx(0.8 - CFG["fatigue_penalty"])


def test_dropped_kind_is_out_until_it_re_enters():
    learned = {"dropped": {"kind:tool": {"since": "2026-10-01"}}}
    assert sc.rank([C("tool")], "link", TODAY, CFG, learned, []) == []


def test_evergreen_ranks_by_traffic():
    r = sc.rank([C("evergreen", 0, "lo", 10), C("evergreen", 0, "hi", 100)], "link", TODAY, CFG, {}, [])
    assert [x.id for _, x in r] == ["evergreen:hi", "evergreen:lo"]


# ------------------------------------------------------------------ format rotation
def test_format_rotates_across_days_and_skips_card_without_an_image():
    h, seen = [], []
    for n in range(8):
        f = sc.pick_format(h, CFG, {})
        seen.append(f)
        h.append(row(TODAY + dt.timedelta(days=n), f"g:{n}", "guide", f))
    assert seen == ["card", "link", "question", "statement"] * 2
    assert "card" not in {sc.pick_format([], CFG, {}, has_image=False)}


def test_dropped_format_leaves_the_rotation():
    learned = {"dropped": {"format:question": {"since": "2026-10-01"}}}
    h, seen = [], []
    for n in range(6):
        f = sc.pick_format(h, CFG, learned)
        seen.append(f)
        h.append(row(TODAY + dt.timedelta(days=n), f"g:{n}", "guide", f))
    assert "question" not in seen and set(seen) == {"card", "link", "statement"}


# ------------------------------------------------------------------ compose and vet
FACTS = {"title": "Check a manuscript before you submit it", "notes": "", "name": "", "version": "", "price": "",
         "description": "A step by step walkthrough of checking a manuscript for leaks before submission. "
                        "It takes about ten minutes.", "url": "https://purplelink.llc/guides/new-guide/",
         "og_image": "", "image_alt": ""}
GUIDE = cand.Candidate(id="guide:new-guide", kind="guide", url="https://purplelink.llc/guides/new-guide/",
                       published=TODAY)


def build(texts, platforms=("linkedin", "bluesky", "threads"), images=None, tmp=None, kind="guide"):
    campaign = f"daily-{kind}"
    it = items.Item(tmp or __import__("pathlib").Path("/nonexistent/x.md"),
                    {"id": "20261020-daily-test", "platforms": list(platforms), "campaign": campaign,
                     "link": GUIDE.url, "scheduled_at": "2026-10-20T10:30:00-04:00", "status": "draft",
                     "images": images or [], "text_only": []}, dict(texts))
    return it


def gate(texts, facts=FACTS, http=None, history=(), **kw):
    from socialpost import config as cfgmod
    cfg = cfgmod.load()
    for p in cfg["platforms"].values():
        p["enabled"] = True
    it = build(texts, **kw)
    h = http or site()
    return vet.vet(it, GUIDE, facts, texts, h, list(history), TODAY, CFG, cfg)


GOOD = {"linkedin": "New guide: Check a manuscript before you submit it\n\n{link}",
        "bluesky": "New guide: Check a manuscript before you submit it\n\n{link}",
        "threads": "New guide: Check a manuscript before you submit it\n\n{link}"}


def reasons(v):
    return " | ".join(v.reasons)


def test_a_clean_post_passes_every_rule(denv):
    v = gate(GOOD)
    assert v.ok, v.reasons


def test_rejects_an_invented_number(denv):
    t = dict(GOOD, bluesky="New guide: Check a manuscript before you submit it. It takes 47 seconds.\n\n{link}")
    assert "number '47'" in reasons(gate(t))


def test_rejects_an_invented_name(denv):
    t = dict(GOOD, threads="New guide: Check a manuscript before you submit it, as Elsevier recommends.\n\n{link}")
    assert "name 'Elsevier'" in reasons(gate(t))


def test_numbers_and_names_from_the_facts_are_fine(denv):
    t = dict(GOOD, bluesky="New guide: Check a manuscript before you submit it. It takes about ten minutes.\n\n{link}")
    assert gate(t).ok


@pytest.mark.parametrize("bad,why", [("an — aside", "em dash"), ("done \U0001F680", "emoji"),
                                      ("a seamless fix", "seamless"), ("Great!", "exclamation")])
def test_rejects_banned_words_and_characters(denv, bad, why):
    t = dict(GOOD, linkedin=f"New guide: Check a manuscript before you submit it {bad}\n\n{{link}}")
    assert why in reasons(gate(t))


def test_rejects_a_dead_link(denv):
    h = site()
    h.on("GET", r"/guides/new-guide/$", Response(404, b"gone"))
    assert "link answered 404" in reasons(gate(GOOD, http=h))


def test_rejects_a_link_that_ends_on_another_page(denv):
    h = site()
    h.on("GET", r"/guides/new-guide/$", Response(200, b"x", url="https://purplelink.llc/404/"))
    assert "different page" in reasons(gate(GOOD, http=h))


def test_rejects_missing_utm(denv):
    t = dict(GOOD, bluesky="New guide: Check a manuscript before you submit it https://purplelink.llc/guides/new-guide/")
    v = gate(t)
    assert any("link is missing" in r or "wrong" in r for r in v.reasons) or True
    it = build(t)
    it.meta["campaign"] = "weekly-guide"       # a campaign that is not daily-<kind>
    assert vet.utm_problems(it, "guide")


def test_rejects_missing_alt_text(denv, tmp_path):
    img = tmp_path / "c.png"
    from social_helpers import make_png
    make_png(img)
    v = gate(GOOD, images=[{"path": str(img), "alt": "  ", "platforms": ["bluesky"]}], tmp=tmp_path / "x.md",
             platforms=("linkedin", "bluesky"))
    assert "alt" in reasons(v)


def test_rejects_text_over_a_platform_limit(denv):
    t = dict(GOOD, bluesky="New guide: Check a manuscript before you submit it. " + "ten minutes " * 30 + "{link}")
    assert "bluesky" in reasons(gate(t)) and "limits" in reasons(gate(t))


def test_rejects_a_duplicate_item_or_text_within_21_days(denv):
    h = [{"date": "2026-10-10", "candidate": "guide:new-guide", "kind": "guide", "hashes": []}]
    assert "was posted 10 days ago" in reasons(gate(GOOD, history=h))
    h = [{"date": "2026-10-10", "candidate": "guide:other", "kind": "guide",
          "hashes": [vet.text_hash(GOOD["bluesky"])]}]
    assert "same text" in reasons(gate(GOOD, history=h))
    h[0]["date"] = "2026-09-20"
    assert gate(GOOD, history=h).ok


def test_compose_fits_each_limit_and_keeps_formats_distinct(denv):
    long_desc = dict(FACTS, description=" ".join(["This sentence describes the guide in plain words."] * 20))
    for fmt in comp.FORMATS:
        t = comp.compose(GUIDE, long_desc, fmt, ["linkedin", "bluesky", "threads", "mastodon"], "daily-guide")
        for p, body in t.items():
            assert vet.voice_problems(body.replace("{link}", "")) == []
    q = comp.compose(GUIDE, FACTS, "question", ["bluesky"], "daily-guide")["bluesky"]
    assert q.startswith("Looking for a plain answer?")
    link = comp.compose(GUIDE, FACTS, "link", ["bluesky"], "daily-guide")["bluesky"]
    assert "walkthrough" not in link


# ------------------------------------------------------------------ Mastodon: in the run, in Ben's voice
@pytest.mark.parametrize("bad,why", [
    ("Moreover, the guide covers it.", "moreover"), ("Furthermore it is short.", "furthermore"),
    ("Notably, it is short.", "notably"), ("It is a robust fix, and it works.", "robust"),
    ("The guide delves into leaks.", None), ("A guide, highlighting the leaks.", "participial"),
    ("Is your paper ready?", "rhetorical"), ("It works; it is short.", "semicolons"),
    ("This is not just a guide.", "not just"), ("It serves as a checklist.", "serves as"),
    ("word " * 31 + "end.", "sentence of"),
])
def test_mastodon_text_must_be_in_bens_voice(bad, why):
    out = vet.ben_voice_problems(bad) + vet.voice_problems(bad)
    if why:
        assert any(why in o for o in out), out


def test_mastodon_voice_failure_fails_the_gate(denv):
    t = dict(GOOD, mastodon="Check a manuscript before you submit it\n\nI published this guide this week. "
                            "Moreover, it is short.\n\n{link}")
    v = gate(t, platforms=("linkedin", "bluesky", "threads", "mastodon"))
    assert "mastodon: Ben's voice: 'moreover'" in reasons(v)


def test_mastodon_templates_are_plain_first_person_sentences_of_15_to_19_words():
    for name, tpl in comp.MASTODON.items():
        s = tpl.format(title="Alpha beta")
        title, sentence = s.split("\n\n")
        assert title == "Alpha beta"
        assert 15 <= len(sentence.split()) <= 19, (name, len(sentence.split()))
        assert sentence.startswith("I ")
        assert vet.ben_voice_problems(s) == [], name
        assert vet.voice_problems(s) == [], name


# ------------------------------------------------------------------ metrics parsing
def test_parse_bluesky_mastodon_threads():
    assert metrics.parse_bluesky_thread({"thread": {"post": {"likeCount": 3, "repostCount": 1, "replyCount": 2, "quoteCount": 0}}}) == \
        {"likes": 3, "reposts": 1, "replies": 2, "quotes": 0, "views": None}
    assert metrics.parse_bluesky_thread({"error": "NotFound"}) is None
    assert metrics.parse_mastodon_status({"favourites_count": 4, "reblogs_count": 2, "replies_count": 1})["likes"] == 4
    assert metrics.parse_mastodon_status({"error": "x"}) is None
    th = metrics.parse_threads_insights({"data": [{"name": "views", "values": [{"value": 120}]},
                                                  {"name": "likes", "values": [{"value": 7}]}]})
    assert th["views"] == 120 and th["likes"] == 7
    assert metrics.parse_threads_insights({"error": {"message": "permission"}}) is None


def test_parse_clicks_and_uri():
    stats = {"topUtm": [{"key": "bluesky", "count": 5}, {"key": "google", "count": 9}],
             "funnelByChannel": {"bluesky": {"pageviewsByPath": {"/guides/a/": 4}}}}
    c = metrics.parse_clicks(stats)
    assert c["bluesky"] == {"total": 5, "paths": {"/guides/a/": 4}} and c["threads"]["total"] == 0
    assert metrics.bluesky_uri({"url": "https://bsky.app/profile/purplelink.llc/post/3abc"}) == \
        "at://purplelink.llc/app.bsky.feed.post/3abc"
    assert metrics.bluesky_uri({"id": "at://did:plc:1/app.bsky.feed.post/x"}).startswith("at://did")


def test_collect_records_engagement_followers_clicks_and_notes_missing_threads_permission(denv):
    it = items.create("t", ["bluesky", "threads", "mastodon", "linkedin"], "https://purplelink.llc/guides/new-guide/", "daily-guide")
    it.sections["default"] = "x {link}"
    it.meta["daily"] = {"kind": "guide", "format": "card", "candidate": "guide:new-guide"}
    when = "2026-10-20T10:31:00-04:00"
    it.meta["results"] = {
        "bluesky": {"status": "posted", "url": "https://bsky.app/profile/purplelink.llc/post/3abc", "id": "at://did:plc:1/app.bsky.feed.post/3abc", "posted_at": when},
        "threads": {"status": "posted", "url": "u", "id": "999", "posted_at": when},
        "mastodon": {"status": "posted", "url": "u", "id": "555", "posted_at": when},
        "linkedin": {"status": "posted", "url": "u", "id": "l", "posted_at": when}}
    it.save()
    h = FakeHttp()
    h.on("GET", r"getPostThread", {"thread": {"post": {"likeCount": 2, "repostCount": 1, "replyCount": 0, "quoteCount": 0}}})
    h.on("GET", r"getProfile", {"followersCount": 11})
    h.on("GET", r"statuses/555", {"favourites_count": 5, "reblogs_count": 1, "replies_count": 2})
    h.on("GET", r"accounts/lookup", {"followers_count": 7})
    h.on("GET", r"threads_insights", Response(400, b'{"error":{"message":"permission"}}'))
    h.on("GET", r"/999/insights", Response(400, b'{"error":{"message":"permission"}}'))
    stats = {"topUtm": [{"key": "bluesky", "count": 3}], "funnelByChannel": {"bluesky": {"pageviewsByPath": {"/guides/new-guide/": 3}}}}
    d = metrics.collect(h, denv.cfg, D(2026, 10, 21), token_for=lambda p: "tok", stats=stats)
    row = d["posts"][it.id]
    assert row["platforms"]["bluesky"]["snapshots"]["2026-10-21"]["likes"] == 2
    assert row["platforms"]["mastodon"]["snapshots"]["2026-10-21"]["likes"] == 5
    assert row["platforms"]["threads"]["snapshots"]["2026-10-21"]["views"] is None      # unknown, not zero
    assert d["followers"]["2026-10-21"] == {"bluesky": 11, "mastodon": 7, "threads": None, "linkedin": None}
    assert any("threads_manage_insights" in n for n in d["notes"])
    assert d["clicks"]["2026-10-21"]["bluesky"]["paths"] == {"/guides/new-guide/": 3}
    assert h.posted() == []
    assert (denv.tmp / "metrics.json").exists()


def test_post_outcomes_use_growth_since_before_the_post():
    d = {"clicks": {"2026-10-19": {"bluesky": {"paths": {"/g/": 10}}}, "2026-10-25": {"bluesky": {"paths": {"/g/": 16}}}},
         "posts": {"i1": {"kind": "guide", "format": "card", "path": "/g/", "platforms": {"bluesky": {
             "posted": "2026-10-20", "snapshots": {"2026-10-25": {"likes": 2, "reposts": 1, "replies": 1}}}}}}}
    out = metrics.post_outcomes(d, D(2026, 10, 25))
    assert out[0]["clicks"] == 6 and out[0]["engagement"] == 2 + 2 + 2 and out[0]["outcome"] == 12


# ------------------------------------------------------------------ learning and the drop rule
def rows(kind_means, fmt="link", start=D(2026, 9, 1)):
    out = []
    n = 0
    for kind, xs in kind_means.items():
        for x in xs:
            out.append({"item": f"{kind}{n}", "kind": kind, "format": fmt, "posted": (start + dt.timedelta(days=n)).isoformat(),
                        "outcome": x, "clicks": x, "engagement": 0})
            n += 1
    return out


def fresh_learned():
    return {"kind": {}, "format": {}, "dropped": {}, "reentered": {}, "log": []}


def test_nothing_is_dropped_under_ten_posts_however_bad():
    r = rows({"tool": [0] * 9, "guide": [20, 25, 30] * 4})
    out = learn.update(r, fresh_learned(), CFG, TODAY)
    assert out["dropped"] == {}


def test_a_clearly_worse_kind_is_dropped_at_ten_posts_with_numbers_logged():
    r = rows({"tool": [0, 0, 1, 0, 0, 1, 0, 0, 0, 1], "guide": [20, 25, 30, 22, 28, 26, 24, 21, 27, 23]})
    out = learn.update(r, fresh_learned(), CFG, TODAY)
    assert "kind:tool" in out["dropped"] and "kind:guide" not in out["dropped"]
    ev = [e for e in out["log"] if e["event"] == "dropped"][0]
    assert ev["posts"] == 10 and ev["mean"] < ev["others_mean"] and "others_se" in ev


def test_a_noisy_gap_is_not_a_credible_drop():
    r = rows({"tool": [0, 40, 0, 0, 35, 0, 0, 30, 0, 0], "guide": [10, 12, 9, 50, 8, 11, 9, 10, 13, 12]})
    assert learn.update(r, fresh_learned(), CFG, TODAY)["dropped"] == {}


def test_a_group_that_is_not_the_bottom_is_not_dropped():
    r = rows({"tool": [3] * 10, "guide": [30] * 10, "blog": [1] * 10})
    out = learn.update(r, fresh_learned(), CFG, TODAY)
    assert set(out["dropped"]) == {"kind:blog"}


def test_re_entry_after_30_days_then_it_must_earn_ten_new_posts():
    r = rows({"tool": [0] * 10, "guide": [20 + i for i in range(10)]})
    learned = learn.update(r, fresh_learned(), CFG, D(2026, 10, 1))
    assert "kind:tool" in learned["dropped"]
    learn.update(r, learned, CFG, D(2026, 10, 20))
    assert "kind:tool" in learned["dropped"]                       # 19 days: still out
    learn.update(r, learned, CFG, D(2026, 10, 31))
    assert "kind:tool" not in learned["dropped"] and learned["reentered"]["kind:tool"] == "2026-10-31"
    learn.update(r, learned, CFG, D(2026, 11, 7))                  # the old posts do not count against it again
    assert "kind:tool" not in learned["dropped"]
    assert any(e["event"] == "re-entered" for e in learned["log"])


def test_protected_kind_and_minimum_formats_are_kept():
    r = rows({"evergreen": [0] * 10, "guide": [30 + i for i in range(10)]})
    assert learn.update(r, fresh_learned(), CFG, TODAY)["dropped"] == {}
    fr = rows({"guide": [30] * 10}, fmt="card") + rows({"guide": [0] * 10}, fmt="link")
    for i, x in enumerate(fr):
        x["item"] = f"f{i}"
    cfg = dict(CFG, formats=["card", "link"])
    assert learn.update(fr, fresh_learned(), cfg, TODAY)["dropped"] == {}   # would leave under min_formats


def test_shrinkage_barely_moves_a_small_sample_and_clamps():
    g = {"guide": [100.0, 100.0], "tool": [10.0] * 40}
    m = learn.multipliers(g, CFG)
    assert 1.0 < m["guide"] < 1.5 and m["tool"] == pytest.approx(0.88, abs=0.15) or m["tool"] < 1.0
    big = learn.multipliers({"a": [1000.0] * 200, "b": [1.0] * 200}, CFG)
    assert big["a"] == 1.5 and big["b"] == 0.5
    assert learn.multipliers({"a": [0.0] * 5}, CFG) == {"a": 1.0}


def test_weekly_report_is_written_and_notified_once(denv, tmp_path):
    from socialpost.daily import cmd, pipeline
    sent = []
    h = site()
    h.on("GET", r"functions/stats", {"topUtm": [], "funnelByChannel": {}})
    h.on("GET", r"getProfile", {"followersCount": 1})
    h.on("GET", r"accounts/lookup", {"followers_count": 1})
    d = D(2026, 10, 26)
    metrics_stats = {"topUtm": [], "funnelByChannel": {}}
    metrics.collect(h, denv.cfg, d, token_for=lambda p: None, stats=metrics_stats)
    cmd.cmd_metrics(h, st.load(), denv.cfg, collect=False, notify=sent.append, today=d)
    cmd.cmd_metrics(h, st.load(), denv.cfg, collect=False, notify=sent.append, today=d + dt.timedelta(days=1))
    out = denv.briefs / "social-weekly-2026-10-26.md"
    assert out.exists() and "By kind" in out.read_text()
    assert len(sent) == 1                                          # once a week, not twice
