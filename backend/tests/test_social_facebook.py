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


MP4 = b"\x00\x00\x00\x20ftypisom" + b"\0" * 64


class FakeS3:
    def __init__(self):
        self.up, self.deleted = [], []

    def upload_file(self, path, bucket, key, ExtraArgs=None):
        self.up.append(key)

    def delete_object(self, Bucket, Key):
        self.deleted.append(Key)


def reel_env(env, cfg):
    (env.tmp / "r2.env").write_text('export MEDIA_BUCKET="b"\nexport MEDIA_S3_ENDPOINT="https://s3.example"\n'
                                    'export MEDIA_PUBLIC_BASE="https://pub.example"\nexport MEDIA_S3_KEY="k"\n'
                                    'export MEDIA_S3_SECRET="s"\n')
    cfg["media"]["video"] = {"env_file": str(env.tmp / "r2.env"), "prefix": "purplelink-social/"}
    v = env.tmp / "reel.mp4"
    v.write_bytes(MP4)
    return v


def test_facebook_reel_start_upload_finish_and_cleanup(env, cfg):
    v = reel_env(env, cfg)
    it = item(env, ["facebook"], video={"path": str(v), "duration": 44.0, "width": 1080, "height": 1920,
                                        "alt": "Video: x."})
    s3 = FakeS3()
    h = FakeHttp([("GET", "fields=id,name", jresp({"id": PAGE["page_id"], "name": PAGE["name"]})),
                  ("POST", "/video_reels", [jresp({"video_id": "V1"}), jresp({"success": True})]),
                  ("HEAD", "pub.example", Resp(200, b"", {"Content-Length": str(len(MP4))})),
                  ("POST", "rupload.facebook.com/video-upload/v23.0/V1", jresp({"success": True})),
                  ("GET", "/V1?fields=status", jresp({"status": {"video_status": "ready"}}))])
    a = Facebook(dict(cfg["platforms"]["facebook"], _root=cfg), http=h,
                 secret=lambda p, f: "PAGETOKEN", sleep=lambda s: None, video_client=lambda e: s3)
    r = a.post(it)
    assert r.url == "https://www.facebook.com/reel/V1"
    starts = h.posts_to("/video_reels")
    assert starts[0]["form"] == {"upload_phase": "start"}
    fin = starts[1]["form"]
    assert fin["upload_phase"] == "finish" and fin["video_state"] == "PUBLISHED" and "New guide: X" in fin["description"]
    up = h.posts_to("rupload.facebook.com")[0]
    assert up["headers"]["Authorization"] == "OAuth PAGETOKEN" and up["headers"]["file_url"].startswith("https://pub.example/")
    assert s3.deleted == s3.up and len(s3.up) == 1


def test_facebook_reel_limits_and_both_platforms_get_reels(env, cfg):
    import json
    import datetime as dt
    from socialpost.instagram import pipeline as igp
    v = reel_env(env, cfg)
    long = item(env, ["facebook"], video={"path": str(v), "duration": 120.0, "width": 1080, "height": 1920, "alt": "x"})
    errs, _ = items.validate(long, cfg)
    assert any("3 to 90 s" in e for e in errs)
    now = dt.datetime(2026, 10, 28, 15, 0, tzinfo=dt.timezone.utc)
    d = igp.reels_dir() / "AAAAAAAAAA1"
    d.mkdir(parents=True)
    (d / "reel.mp4").write_bytes(MP4)
    (d / "entry.json").write_text(json.dumps({
        "youtube_id": "AAAAAAAAAA1", "also": [], "title": "Spotlight fix on Mac", "link": "https://purplelink.llc/guides/x/",
        "description": "Spotlight keeps a separate index for each volume on a Mac.\n\n#mac #macos #spotlight",
        "added": items.iso(now), "duration": 44.0, "width": 1080, "height": 1920, "trimmed": False, "framed": False}))
    res = igp.run(FakeHttp([("GET", "purplelink.llc/guides/", Resp(200, b"ok"))]), cfg, when=now, say=lambda s: None,
                  render_card=lambda *a: None)
    kinds = sorted(items.find(i).platforms[0] for i in res["queued"])
    assert kinds == ["facebook", "instagram"]
    fb_item = next(items.find(i) for i in res["queued"] if items.find(i).platforms == ["facebook"])
    assert fb_item.approval_valid()[0] and fb_item.meta["source"] == "instagram-reel"
    text = fb_item.render("facebook")
    assert "Link in bio." not in text and "utm_source=facebook" in text and "utm_campaign=fb-reel" in text
    assert igp.run(FakeHttp([("GET", "purplelink.llc/guides/", Resp(200, b"ok"))]), cfg, when=now,
                   say=lambda s: None, render_card=lambda *a: None)["queued"] == []


def test_backfill_entries_never_expire_and_go_oldest_first(env, cfg):
    import json
    import datetime as dt
    from socialpost.instagram import pipeline as igp
    reel_env(env, cfg)
    now = dt.datetime(2026, 11, 20, 15, 0, tzinfo=dt.timezone.utc)
    old_add = items.iso(now - dt.timedelta(days=20))
    for vid, back in (("BBBBBBBBBB1", "2026-10-22"), ("BBBBBBBBBB2", "2026-10-01"), ("BBBBBBBBBB3", "")):
        d = igp.reels_dir() / vid
        d.mkdir(parents=True)
        (d / "entry.json").write_text(json.dumps({"youtube_id": vid, "added": old_add, "duration": 30.0,
                                                  **({"backfill": back} if back else {})}))
    work = igp.pending(cfg, now, igp.read_state(), igp.settings(cfg))
    ids = [e["youtube_id"] for k, e in work if k == "reel"]
    assert ids == ["BBBBBBBBBB2", "BBBBBBBBBB1"]          # the expired non-backfill entry is gone; oldest first
