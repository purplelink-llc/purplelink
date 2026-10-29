"""Facebook Page adapter, Instagram through the Page, and `setup facebook`. No network, keychain or real config."""
from __future__ import annotations

import pytest
from PIL import Image

from social_helpers import FakeHttp, env, jresp  # noqa: F401
from socialpost import config as cfgmod
from socialpost import items
from socialpost.adapters.facebook import Facebook
from socialpost.adapters.instagram import Instagram
from socialpost.errors import Ambiguous, Refused
from socialpost.http import Resp

PAGE = {"page_id": "61595915854939", "name": "Purplelink LLC"}


def fb(cfg, http):
    return Facebook(dict(cfg["platforms"]["facebook"], _root=cfg), http=http,
                    secret=lambda p, f: "PAGETOKEN" if (p, f) == ("facebook", "page_token") else None)


@pytest.fixture
def cfg(env):
    c = cfgmod.load()
    c["platforms"]["facebook"] = {"enabled": True, "expected": dict(PAGE)}
    c["platforms"]["instagram"] = {"enabled": True, "api": "facebook",
                                   "expected": {"user_id": "17841427275335240", "username": "purplelink.llc"}}
    return c


def item(env, platforms, **meta):
    it = items.create("fb", platforms, "https://purplelink.llc/guides/x/", "daily-guide")
    it.sections = {"default": "New guide: X\n\nA fact.\n\n{link}", "instagram": "New guide: X\n\nLink in bio."}
    it.meta.update(meta)
    it.save()
    return it


def test_text_post_goes_to_the_feed_with_its_tagged_link(env, cfg):
    h = FakeHttp([("GET", "/61595915854939?fields=id,name", jresp({"id": PAGE["page_id"], "name": PAGE["name"]})),
                  ("POST", "/61595915854939/feed", jresp({"id": "61595915854939_1"})),
                  ("GET", "permalink_url", jresp({"permalink_url": "https://www.facebook.com/p/1"}))])
    r = fb(cfg, h).post(item(env, ["facebook"]))
    form = h.posts_to("/feed")[0]["form"]
    assert form["link"].endswith("utm_source=facebook&utm_medium=social&utm_campaign=daily-guide")
    assert "New guide: X" in form["message"] and r.url == "https://www.facebook.com/p/1"
    assert all("PAGETOKEN" not in c["url"] for c in h.calls)


def test_photo_post_and_ambiguous_publish(env, cfg):
    img = env.tmp / "c.jpg"
    Image.new("RGB", (10, 10)).save(img, "JPEG")
    it = item(env, ["facebook"], images=[{"path": str(img), "alt": "card"}])
    h = FakeHttp([("GET", "fields=id,name", jresp({"id": PAGE["page_id"], "name": PAGE["name"]})),
                  ("HEAD", "social-media", Resp(200, b"", {"Content-Type": "image/jpeg",
                                                           "Content-Length": str(img.stat().st_size)})),
                  ("POST", "/photos", Resp(502, b""))])
    with pytest.raises(Ambiguous):
        fb(cfg, h).post(it)
    assert h.posts_to("/photos")[0]["form"]["url"].startswith("https://purplelink.llc/social-media/")


def test_refuses_other_pages(env, cfg):
    cfg["platforms"]["facebook"]["expected"] = {"page_id": "1", "name": "RubbleFront"}
    h = FakeHttp([("GET", "fields=id,name", jresp({"id": "1", "name": "RubbleFront"}))])
    with pytest.raises(Refused):
        fb(cfg, h).check_identity()
    cfg["platforms"]["facebook"]["expected"] = dict(PAGE)
    h = FakeHttp([("GET", "fields=id,name", jresp({"id": "2", "name": "Someone else"}))])
    with pytest.raises(Refused):
        fb(cfg, h).check_identity()


def test_instagram_through_the_page_uses_the_page_token_on_graph_facebook(env, cfg):
    img = env.tmp / "c.jpg"
    Image.new("RGB", (10, 10)).save(img, "JPEG")
    it = item(env, ["instagram"], images=[{"path": str(img), "alt": "A card"}])
    h = FakeHttp([("GET", "/17841427275335240?fields=id,username", jresp({"id": "17841427275335240",
                                                                         "username": "purplelink.llc"})),
                  ("HEAD", "social-media", Resp(200, b"", {"Content-Type": "image/jpeg",
                                                           "Content-Length": str(img.stat().st_size)})),
                  ("POST", "/17841427275335240/media_publish", jresp({"id": "M1"})),
                  ("POST", "/17841427275335240/media", jresp({"id": "C1"})),
                  ("GET", "/C1?", jresp({"status_code": "FINISHED"})),
                  ("GET", "/M1?fields=permalink", jresp({"permalink": "https://www.instagram.com/p/x/"}))])
    a = Instagram(dict(cfg["platforms"]["instagram"], _root=cfg), http=h,
                  secret=lambda p, f: "PAGETOKEN" if (p, f) == ("facebook", "page_token") else None,
                  sleep=lambda s: None)
    r = a.post(it)
    assert r.url == "https://www.instagram.com/p/x/"
    graph = [c for c in h.calls if "graph." in c["url"]]
    assert graph and all(c["url"].startswith("https://graph.facebook.com/") for c in graph)
    assert all(c["headers"].get("Authorization") == "Bearer PAGETOKEN" for c in graph)
    assert h.posts_to("/media")[0]["form"]["alt_text"] == "A card"
    a.refresh()   # no-op through the Page: nothing to call
    assert not [c for c in h.calls if "refresh" in c["url"]]


def test_setup_facebook_pins_the_page_and_switches_instagram_to_it(env, monkeypatch):
    from socialpost import setup as st, sysutil
    stored = []
    monkeypatch.setattr(sysutil, "keychain_set", lambda *a: stored.append(a))
    secrets_in = iter(["SHORT", "APPSECRET"])
    monkeypatch.setattr(st, "_ask_secret", lambda label, required=True: next(secrets_in))
    answers = iter(["1029154422782255", "yes"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    pages = {"data": [{"id": "9", "name": "RubbleFront", "access_token": "RF"},
                      {"id": PAGE["page_id"], "name": "Purplelink LLC", "access_token": "PAGETOKEN",
                       "instagram_business_account": {"id": "17841427275335240", "username": "purplelink.llc"}}]}
    h = FakeHttp([("GET", "oauth/access_token", jresp({"access_token": "LONG"})),
                  ("GET", "/me/accounts", jresp(pages))])
    assert st._setup_facebook(cfgmod.load(), http=h) == 0
    assert stored == [("facebook", "page_token", "PAGETOKEN")]
    c = cfgmod.load()
    assert c["platforms"]["facebook"]["expected"] == PAGE and c["platforms"]["facebook"]["enabled"]
    assert c["platforms"]["instagram"]["api"] == "facebook"
    assert c["platforms"]["instagram"]["expected"]["user_id"] == "17841427275335240"


def test_daily_text_for_facebook_is_written_like_linkedin():
    from socialpost.daily import compose
    assert compose.SOFT_LIMIT["facebook"] == 600 and "facebook" in items.STANDING_PLATFORMS
