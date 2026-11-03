"""Every social-engine post carries its own utm_content from the marketing hub, set before approval, and the gates
reject an untagged purplelink.llc link (hub request 2026-10-29: 30 of 44 placements since 2026-10-24 had none)."""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
from pathlib import Path

import pytest

from social_helpers import FakeHttp, env, jresp  # noqa: F401
from socialpost import config as cfgmod
from socialpost import hubtags, items
from socialpost.http import Resp


def item(env, platforms, **meta):
    it = items.create("t", platforms, "https://purplelink.llc/guides/x/", "daily-guide")
    it.sections = {"default": "New guide: X\n\nA fact.\n\n{link}"}
    it.meta.update(meta)
    it.save()
    return it


def test_render_carries_the_items_own_tag_per_platform(env):
    it = item(env, ["linkedin", "bluesky"], utm_contents={"linkedin": "x-linkedin-261029", "bluesky": "x-bluesky-261029"})
    assert "utm_campaign=daily-guide&utm_content=x-linkedin-261029" in it.render("linkedin")
    assert "utm_content=x-bluesky-261029" in it.render("bluesky")


def test_the_tag_is_part_of_the_approved_content(env):
    cfg = cfgmod.load()
    it = item(env, ["bluesky"], utm_contents={"bluesky": "a"})
    h = it.content_hash()
    it.meta["utm_contents"] = {"bluesky": "b"}
    assert it.content_hash() != h          # changing a tag after approval voids the approval


def test_daily_gate_rejects_an_untagged_purplelink_link(env):
    from socialpost.daily import vet
    it = item(env, ["bluesky"])
    assert any("utm_content" in r for r in vet.utm_problems(it, "guide"))
    it.meta["utm_contents"] = {"bluesky": "x-bluesky-261029"}
    assert vet.utm_problems(it, "guide") == []


def test_daily_items_get_one_tag_per_platform(env, monkeypatch):
    from socialpost.daily import pipeline, candidates as cand
    got = []
    monkeypatch.setattr(hubtags, "tag", lambda link, asset, channel, campaign, **kw:
                        got.append((asset, channel, campaign)) or f"{asset}-{channel}-261029")
    c = cand.Candidate(id="guide:new-guide", kind="guide", url="https://purplelink.llc/guides/new-guide/")
    it = pipeline.build_item(c, {"title": "T"}, "link", {"linkedin": "a {link}", "bluesky": "b {link}"},
                             ["linkedin", "bluesky"], "2026-10-29T10:30:00-04:00", dt.date(2026, 10, 29), None, [], "n")
    assert it.meta["utm_contents"] == {"linkedin": "new-guide-linkedin-261029", "bluesky": "new-guide-bluesky-261029"}
    assert ("new-guide", "linkedin", "daily-guide") in got


def test_youtube_links_need_no_tag(env, monkeypatch):
    from socialpost.daily import vet
    it = item(env, ["bluesky"])
    it.meta["link"] = "https://www.youtube.com/watch?v=abcdefghijk"
    assert vet.utm_problems(it, "guide") == []


def test_facebook_feed_link_parameter_carries_the_tag(env):
    from socialpost.adapters.facebook import Facebook
    cfg = cfgmod.load()
    cfg["platforms"]["facebook"] = {"enabled": True, "expected": {"page_id": "1", "name": "Purplelink LLC"}}
    it = item(env, ["facebook"], utm_contents={"facebook": "x-facebook-261029"})
    h = FakeHttp([("GET", "fields=id,name", jresp({"id": "1", "name": "Purplelink LLC"})),
                  ("POST", "/1/feed", jresp({"id": "1_2"}))])
    Facebook(dict(cfg["platforms"]["facebook"], _root=cfg), http=h, secret=lambda p, f: "T").post(it)
    assert h.posts_to("/feed")[0]["form"]["link"].endswith("utm_content=x-facebook-261029")


def test_instagram_items_are_tagged_and_the_gate_rejects_untagged(env, monkeypatch):
    from socialpost.instagram import pipeline as igp
    monkeypatch.setattr(hubtags, "tag", lambda link, asset, channel, campaign, **kw: f"{asset}-{channel}-261029")
    entry = {"youtube_id": "AAAAAAAAAA1", "title": "T", "description": "", "duration": 40.0, "width": 1080,
             "height": 1920, "link": "https://purplelink.llc/guides/x/"}
    fb = igp.fb_reel_item(entry, "2026-10-29T12:00:00-04:00")
    assert list(fb.meta["utm_contents"]) == ["facebook"] and fb.meta["utm_contents"]["facebook"].endswith("-261029")
    assert "utm_content=" in fb.render("facebook")
    ig = igp.reel_item(entry, "2026-10-29T12:00:00-04:00")
    assert ig.meta["utm_contents"]["instagram"]
    bare = igp.reel_item(dict(entry), "2026-10-29T12:00:00-04:00")
    bare.meta.pop("utm_contents"); bare.meta.pop("utm_content", None)
    assert any("utm_content" in r for r in igp.tag_problems(bare))


def test_hub_reads_per_platform_tags_from_the_social_queue(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("hub_u", Path(__file__).resolve().parents[2] / "scripts" / "hub" / "hub.py")
    hub = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hub)
    q = tmp_path / "social"
    q.mkdir()
    (q / "20261029-x.md").write_text('---\nid: "20261029-x"\nplatforms: ["linkedin", "bluesky"]\ncampaign: "daily-guide"\n'
                                    'link: "https://purplelink.llc/guides/x/"\nstatus: "posted"\n'
                                    'utm_contents: {"linkedin": "x-linkedin-261029", "bluesky": "x-bluesky-261029"}\n'
                                    'results: {"linkedin": {"status": "posted", "posted_at": "2026-10-29T10:31:00-04:00"}}\n---\n\n## default\nHi {link}\n')
    for k, v in (("PURPLELINK_SOCIAL_QUEUE", q), ("PURPLELINK_QUEUE", tmp_path / "queue"), ("PURPLELINK_HUB", tmp_path / "hub"),
                 ("PURPLELINK_REPO", tmp_path / "repo")):
        monkeypatch.setenv(k, str(v))
    p = hub.paths()
    assert {"x-linkedin-261029", "x-bluesky-261029"} <= hub.used_contents(p)
    li = next(pl for pl in hub.from_social(p) if pl["channel"] == "linkedin")
    assert li["utm"].endswith("&utm_content=x-linkedin-261029")


def test_linkedin_finds_the_public_post_url_by_its_text():
    from socialpost.adapters.linkedin import permalink_for
    rows = [["urn:li:activity:7521217420435439616", "Feed post number 1 Purplelink LLC New guide: X A fact."],
            ["urn:li:activity:7520856782970343424", "Feed post number 2 Purplelink LLC Older post"]]
    assert permalink_for(rows, "New guide: X\n\nA fact.\n\nhttps://purplelink.llc/guides/x/") == \
        "https://www.linkedin.com/feed/update/urn:li:activity:7521217420435439616/"
    assert permalink_for(rows, "Something never posted") is None


def test_release_tags_keep_the_app_name(env, monkeypatch):
    from socialpost.daily import pipeline, candidates as cand
    seen = []
    monkeypatch.setattr(hubtags, "tag", lambda link, asset, channel, campaign, **kw: seen.append(asset) or "t")
    c = cand.Candidate(id="release:legroom:1.9.0", kind="release", url="https://purplelink.llc/legroom/")
    pipeline.build_item(c, {"title": "T"}, "link", {"bluesky": "b {link}"}, ["bluesky"], "2026-10-29T10:30:00-04:00",
                        dt.date(2026, 10, 29), None, [], "n")
    assert seen == ["legroom-1.9.0"]
