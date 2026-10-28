"""Instagram: adapter (identity, image post, Reel, RubbleFront refusal), queue rules, captions, the Reel builder and
the queueing pipeline (LinkedIn companions, the Reel inbox, the gate, the daily cap, the channel scan). No network, no
keychain, no Chrome, no ffmpeg, no real queue."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest
from PIL import Image

from social_helpers import FakeHttp, env, jresp  # noqa: F401
from socialpost import config as cfgmod
from socialpost import engine, items, media
from socialpost.adapters.instagram import Instagram
from socialpost.errors import Ambiguous, Refused
from socialpost.http import Resp
from socialpost.instagram import caption as cap
from socialpost.instagram import pipeline as igp
from socialpost.instagram import render

MP4 = b"\x00\x00\x00\x20ftypisom" + b"\0" * 64
UTC = dt.timezone.utc
NOW = dt.datetime(2026, 10, 23, 15, 0, tzinfo=UTC)   # 11:00 US Eastern


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch):
    # approve() checks staleness against items.now(); pin it to NOW so the fixed dates above never go stale.
    monkeypatch.setattr(items, "now", lambda: NOW)


def jpeg(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1080, 1350), (20, 10, 34)).save(path, "JPEG")
    return path


def mp4(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(MP4)
    return path


@pytest.fixture
def cfg(env):
    c = cfgmod.load()
    c["platforms"]["instagram"] = {"enabled": True, "expected": {"user_id": "1784", "username": "purplelink.llc"}}
    c["media"]["video"] = {"env_file": str(env.tmp / "r2.env"), "prefix": "purplelink-social/"}
    (env.tmp / "r2.env").write_text('export MEDIA_BUCKET="b"\nexport MEDIA_S3_ENDPOINT="https://s3.example"\n'
                                    'export MEDIA_PUBLIC_BASE="https://pub.example"\nexport MEDIA_S3_KEY="k"\n'
                                    'export MEDIA_S3_SECRET="s"\n')
    return c


def ig_item(env, **meta) -> items.Item:
    it = items.create("ig", ["instagram"], "https://purplelink.llc/guides/x/", "ig-test")
    it.sections = {"instagram": "A plain caption about the guide.\n\nLink in bio.\n\n#mac #macos {link}"}
    it.meta.update(meta)
    it.save()
    return it


# ---------------------------------------------------------------- adapter
def adapter(cfg, http, video_client=None):
    pc = dict(cfg["platforms"]["instagram"], _root=cfg)
    return Instagram(pc, http=http, secret=lambda p, f: "TOKEN", sleep=lambda s: None, video_client=video_client)


def me(username="purplelink.llc", uid="1784"):
    return jresp({"user_id": uid, "username": username, "account_type": "BUSINESS"})


def test_refuses_rubblefront_even_if_config_names_it(cfg):
    cfg["platforms"]["instagram"]["expected"] = {"user_id": "99", "username": "rubblefront"}
    h = FakeHttp([("GET", "/me?", me("rubblefront", "99"))])
    with pytest.raises(Refused, match="never posts there"):
        adapter(cfg, h).check_identity()


def test_refuses_unpinned_and_wrong_account(cfg):
    cfg["platforms"]["instagram"]["expected"] = {"user_id": "", "username": ""}
    with pytest.raises(Refused, match="nobody named"):
        adapter(cfg, FakeHttp([("GET", "/me?", me())])).check_identity()
    cfg["platforms"]["instagram"]["expected"] = {"user_id": "1784", "username": "purplelink.llc"}
    with pytest.raises(Refused, match="expected"):
        adapter(cfg, FakeHttp([("GET", "/me?", me("someone.else", "5"))])).check_identity()


def test_image_post_sends_alt_text_and_a_caption_without_link(env, cfg):
    img = jpeg(env.tmp / "card.jpg")
    it = ig_item(env, images=[{"path": str(img), "alt": "A card"}])
    h = FakeHttp([("GET", "/me?", me()), ("HEAD", "social-media", Resp(200, b"", {"Content-Type": "image/jpeg",
                                                                                  "Content-Length": str(img.stat().st_size)})),
                  ("POST", "/1784/media_publish", jresp({"id": "M1"})), ("POST", "/1784/media", jresp({"id": "C1"})),
                  ("GET", "/C1?", jresp({"status_code": "FINISHED"})),
                  ("GET", "/M1?fields=permalink", jresp({"permalink": "https://www.instagram.com/p/abc/"}))])
    r = adapter(cfg, h).post(it)
    assert r.url == "https://www.instagram.com/p/abc/" and r.id == "M1"
    form = h.posts_to("/1784/media")[0]["form"]
    assert form["alt_text"] == "A card" and form["image_url"].startswith("https://purplelink.llc/social-media/")
    assert "http" not in form["caption"] and "Link in bio." in form["caption"]
    assert all("TOKEN" not in c["url"] for c in h.calls)       # the token never travels in a URL
    assert all(c["headers"].get("Authorization") == "Bearer TOKEN" for c in h.calls if "graph.instagram" in c["url"])


class FakeS3:
    def __init__(self):
        self.up, self.deleted = [], []

    def upload_file(self, path, bucket, key, ExtraArgs=None):
        self.up.append((bucket, key, ExtraArgs))

    def delete_object(self, Bucket, Key):
        self.deleted.append(Key)


def test_reel_post_hosts_the_video_and_deletes_it_after(env, cfg):
    v = mp4(env.tmp / "reel.mp4")
    it = ig_item(env, video={"path": str(v), "duration": 42.0, "width": 1080, "height": 1920, "alt": "Video: x."})
    s3 = FakeS3()
    h = FakeHttp([("GET", "/me?", me()), ("HEAD", "pub.example", Resp(200, b"", {"Content-Length": str(len(MP4))})),
                  ("POST", "/1784/media_publish", jresp({"id": "M2"})), ("POST", "/1784/media", jresp({"id": "C2"})),
                  ("GET", "/C2?", [jresp({"status_code": "IN_PROGRESS"}), jresp({"status_code": "FINISHED"})]),
                  ("GET", "permalink", jresp({"permalink": "https://www.instagram.com/reel/xyz/"}))])
    r = adapter(cfg, h, video_client=lambda env_: s3).post(it)
    form = h.posts_to("/1784/media")[0]["form"]
    assert form["media_type"] == "REELS" and form["video_url"].startswith("https://pub.example/purplelink-social/")
    assert form["share_to_feed"] == "true" and "alt_text" not in form
    assert s3.up[0][2] == {"ContentType": "video/mp4"} and s3.deleted == [s3.up[0][1]]
    assert r.url.endswith("/reel/xyz/")


def test_publish_5xx_is_ambiguous_and_video_still_deleted(env, cfg):
    v = mp4(env.tmp / "reel.mp4")
    it = ig_item(env, video={"path": str(v), "duration": 42.0, "width": 1080, "height": 1920, "alt": "Video: x."})
    s3 = FakeS3()
    h = FakeHttp([("GET", "/me?", me()), ("HEAD", "pub.example", Resp(200, b"", {})),
                  ("POST", "/1784/media_publish", Resp(502, b"")), ("POST", "/1784/media", jresp({"id": "C3"})),
                  ("GET", "/C3?", jresp({"status_code": "FINISHED"}))])
    with pytest.raises(Ambiguous):
        adapter(cfg, h, video_client=lambda env_: s3).post(it)
    assert len(s3.deleted) == 1


def test_registry_and_refresh_list_include_instagram():
    assert "instagram" in engine.registry() and "instagram" in engine.REFRESHED


# ---------------------------------------------------------------- queue rules
def test_validate_instagram_rules(env, cfg):
    it = ig_item(env)
    errs, _ = items.validate(it, cfg)
    assert any("needs one image or a Reel" in e for e in errs)
    it.sections["instagram"] = "Text https://purplelink.llc/ #a #b #c #d #e #f"
    it.meta["images"] = [{"path": str(jpeg(env.tmp / "c.jpg")), "alt": "x"}]
    errs, _ = items.validate(it, cfg)
    assert any("6 hashtags" in e for e in errs) and any("not clickable" in e for e in errs)
    it.sections["instagram"] = "Text. Link in bio."
    it.meta["images"] = [{"path": str(mp4(env.tmp / "p.png")), "alt": "x"}]
    errs, _ = items.validate(it, cfg)
    assert any("takes .jpg" in e for e in errs)        # Instagram is JPEG only


def test_validate_reel_shape(env, cfg):
    v = mp4(env.tmp / "r.mp4")
    it = ig_item(env, video={"path": str(v), "duration": 200, "width": 1920, "height": 1080, "alt": ""})
    errs, _ = items.validate(it, cfg)
    assert any("3 to 180 s" in e for e in errs) and any("not 1080x1920" in e for e in errs)
    assert any("no description" in e for e in errs)
    it.meta["platforms"] = ["instagram", "bluesky"]
    errs, _ = items.validate(it, cfg)
    assert any("Instagram only" in e for e in errs)


def test_instagram_standing_approval_is_narrow(env, cfg):
    it = ig_item(env, images=[{"path": str(jpeg(env.tmp / "c.jpg")), "alt": "x"}], source="instagram-companion")
    items.approve_instagram_standing(it, cfg)
    assert items.Item.load(it.path).approval_valid() == (True, "")
    other = ig_item(env, images=[{"path": str(jpeg(env.tmp / "d.jpg")), "alt": "x"}], source="social-daily")
    with pytest.raises(ValueError):
        items.approve_instagram_standing(other, cfg)
    # the 2026-10-18 approval does not reach Instagram, and the new one does not reach LinkedIn
    items.approve(other, cfg, items.STANDING_BY)
    assert not items.Item.load(other.path).approval_valid()[0]
    li = items.create("li", ["linkedin"], "https://purplelink.llc/", "x-y")
    li.sections["default"] = "Hello. {link}"
    li.meta["source"] = "instagram-companion"
    li.save()
    with pytest.raises(ValueError):
        items.approve_instagram_standing(li, cfg)


# ---------------------------------------------------------------- captions
HOWTO_DESC = """Spotlight not finding files on an external drive? Spotlight skips some drives until you reindex them.

Spotlight keeps a separate index for each volume, and a drive added while indexing was off has none.

The fix, in Terminal:
mdutil -i on /Volumes/Drive
mdutil -E /Volumes/Drive

Summonly: https://purplelink.llc/summonly/?utm_source=youtube

Where this comes up:
https://discussions.apple.com/thread/1

#mac #macos #spotlight #shorts"""


def test_reel_caption_uses_only_the_description_prose():
    c = cap.reel_caption("Spotlight not finding files on an external drive on Mac", HOWTO_DESC)
    assert "http" not in c and "mdutil" not in c and "#shorts" not in c
    assert c.endswith("Link in bio.\n\n#mac #macos #spotlight")
    assert "Spotlight keeps a separate index for each volume" in c


def test_companion_caption_and_card_words():
    li = "New guide: How to cite a dataset in APA\n\nThe page shows the reference format for a dataset in APA 7.\n\n{link}"
    c = cap.companion_caption(li)
    assert "{link}" not in c and "http" not in c and "Link in bio." in c and "#academicwriting" in c
    w = cap.card_words(li)
    assert w == {"title": "How to cite a dataset in APA", "kicker": "Guide",
                 "sub": "The page shows the reference format for a dataset in APA 7.", "bg": "research"}
    assert cap.card_words("Panely 1.1.0 is out.\n\nWindows resize together.")["kicker"] == "Release"


# ---------------------------------------------------------------- reel builder
class FakeRun:
    """Answers ffprobe with a scripted stream and makes the output file for ffmpeg and Chrome."""

    def __init__(self, src_info, out_info=(1080, 1920)):
        self.src_info, self.out_info, self.cmds = src_info, out_info, []

    def __call__(self, cmd, **kw):
        self.cmds.append(cmd)

        class R:
            returncode, stderr, stdout = 0, "", ""
        r = R()
        if "ffprobe" in cmd[0]:
            w, h, d = self.src_info if "reel.mp4" not in cmd[-1] else (*self.out_info, min(self.src_info[2], 179.5))
            r.stdout = json.dumps({"format": {"duration": str(d)},
                                   "streams": [{"codec_type": "video", "width": w, "height": h}, {"codec_type": "audio"}]})
        elif "ffmpeg" in cmd[0]:
            Path(cmd[-1]).write_bytes(MP4)
        else:   # chrome
            png = next(a for a in cmd if a.startswith("--screenshot=")).split("=", 1)[1]
            Image.new("RGB", (1080, 1920)).save(png)
        return r


def test_vertical_short_is_scaled_not_framed(tmp_path):
    run = FakeRun((1080, 1920, 58.0))
    meta = render.reel(mp4(tmp_path / "s.mp4"), tmp_path / "o" / "reel.mp4", run=run)
    assert meta == {"duration": 58.0, "width": 1080, "height": 1920, "trimmed": False, "framed": False}
    assert not any("chrome" in c[0].lower() for c in run.cmds)


def test_long_landscape_video_is_framed_and_trimmed(tmp_path, monkeypatch):
    monkeypatch.setenv("PL_CHROME", "/fake/chrome")
    run = FakeRun((1920, 1080, 600.0))
    meta = render.reel(mp4(tmp_path / "l.mp4"), tmp_path / "o" / "reel.mp4", title="T", run=run)
    assert meta["framed"] and meta["trimmed"] and meta["duration"] <= 180
    ff = next(c for c in run.cmds if "ffmpeg" in c[0])
    assert "-filter_complex" in ff and "179.50" in ff and "+faststart" in ff


def test_too_short_video_is_refused(tmp_path):
    with pytest.raises(Exception, match="at least"):
        render.reel(mp4(tmp_path / "s.mp4"), tmp_path / "reel.mp4", run=FakeRun((1080, 1920, 1.0)))


# ---------------------------------------------------------------- pipeline
def posted_linkedin(env, text, posted_at=NOW - dt.timedelta(hours=1), iid="li"):
    it = items.create(iid, ["linkedin"], "https://purplelink.llc/guides/cite-dataset/", "daily-guide")
    it.sections = {"default": text}
    it.meta.update(status="posted", results={"linkedin": {"status": "posted", "posted_at": items.iso(posted_at)}})
    it.save()
    return it


def fake_card(path, title, kicker, sub, foot, bg):
    return jpeg(path)


OK_LINK = [("GET", "purplelink.llc/guides/", Resp(200, b"ok"))]


def run_ig(cfg, **kw):
    return igp.run(FakeHttp(OK_LINK), cfg, when=kw.pop("when", NOW), say=lambda s: None, render_card=fake_card, **kw)


def test_companion_is_queued_for_a_posted_linkedin_post(env, cfg):
    li = posted_linkedin(env, "New guide: How to cite a dataset in APA\n\nThe page shows the reference format for a "
                              "dataset in APA 7.\n\n{link}")
    res = run_ig(cfg)
    assert res["status"] == "ok" and len(res["queued"]) == 1
    it = items.find(res["queued"][0])
    assert it.platforms == ["instagram"] and it.meta["source"] == "instagram-companion"
    assert it.meta["approved_by"] == items.IG_STANDING_BY and it.approval_valid()[0]
    assert it.images_for("instagram")[0]["alt"].startswith("Purplelink card")
    assert items.parse_time(it.meta["scheduled_at"]) == NOW + dt.timedelta(minutes=2)
    assert run_ig(cfg)["queued"] == []            # never twice
    assert igp.read_state()["companions"][str(li.id)] == it.id


def test_gate_blocks_hype_and_notifies(env, cfg):
    posted_linkedin(env, "New guide: The ultimate guide!\n\nIt is amazing.\n\n{link}")
    res = run_ig(cfg)
    assert res["queued"] == [] and res["skipped"] and env.notes
    assert "voice" in res["skipped"][0][1][0]


def test_old_or_unposted_linkedin_items_are_ignored(env, cfg):
    posted_linkedin(env, "New guide: Old one\n\nThe page shows the reference format.\n\n{link}",
                    posted_at=NOW - dt.timedelta(days=5), iid="old")
    draft = items.create("d", ["linkedin"], "https://purplelink.llc/", "x-y")
    draft.sections["default"] = "Draft. {link}"
    draft.save()
    assert run_ig(cfg)["queued"] == []


def test_reel_from_the_inbox_is_queued_and_the_daily_cap_holds(env, cfg):
    for n, vid in enumerate(["AAAAAAAAAA1", "AAAAAAAAAA2", "AAAAAAAAAA3", "AAAAAAAAAA4"]):
        d = igp.reels_dir() / vid
        mp4(d / "reel.mp4")
        (d / "entry.json").write_text(json.dumps({
            "youtube_id": vid, "also": [], "title": f"Spotlight fix part {n + 1}", "description": HOWTO_DESC,
            "link": "https://purplelink.llc/guides/x/", "added": items.iso(NOW), "duration": 50.0, "width": 1080,
            "height": 1920, "trimmed": False, "framed": False}))
    res = run_ig(cfg)
    assert len(res["queued"]) == 3                 # max_per_day
    times = sorted(items.parse_time(items.find(i).meta["scheduled_at"]) for i in res["queued"])
    assert times[1] - times[0] >= dt.timedelta(minutes=90)
    it = items.find(res["queued"][0])
    assert it.meta["source"] == "instagram-reel" and it.video()["alt"].startswith("Video: ")
    assert "Link in bio." in it.render("instagram") and it.approval_valid()[0]


def test_disabled_and_paused_queue_nothing(env, cfg):
    posted_linkedin(env, "New guide: How to cite a dataset in APA\n\nThe page shows the reference format.\n\n{link}")
    cfg["platforms"]["instagram"]["enabled"] = False
    assert run_ig(cfg)["status"] == "disabled"
    cfg["platforms"]["instagram"]["enabled"] = True
    env.home.mkdir(parents=True, exist_ok=True)
    (env.home / "PAUSE").touch()
    assert run_ig(cfg)["status"] == "paused"
    assert all("instagram" not in i.platforms for i in items.list_items())


def test_dry_run_builds_but_writes_nothing(env, cfg):
    posted_linkedin(env, "New guide: How to cite a dataset in APA\n\nThe page shows the reference format.\n\n{link}")
    cfg["platforms"]["instagram"]["enabled"] = False
    res = run_ig(cfg, dry_run=True)
    assert res["status"] == "dry-run" and len(res["would_queue"]) == 1
    assert len(items.list_items()) == 1 and not igp.state_file().exists()


def test_scan_flags_uploads_without_a_reel_once(env, cfg):
    d = igp.reels_dir() / "SHORT000001"
    d.mkdir(parents=True)
    (d / "entry.json").write_text(json.dumps({"youtube_id": "SHORT000001", "also": [], "added": items.iso(NOW)}))
    feed = ("<feed>" + "".join(f"<entry><yt:videoId>{v}</yt:videoId><title>{t}</title><published>{p}</published></entry>"
                               for v, t, p in [("SHORT000001", "s", "2026-10-23T10:00:00+00:00"),
                                               ("LONG0000001", "long", "2026-10-23T10:00:00+00:00"),
                                               ("OTHER000001", "tour", "2026-10-22T10:00:00+00:00"),
                                               ("OLD00000001", "old", "2026-09-01T10:00:00+00:00")]) + "</feed>")
    h = FakeHttp([("GET", "feeds/videos.xml", Resp(200, feed.encode()))])
    ledger = [{"long_id": "LONG0000001", "short_id": "SHORT000001"}]
    miss = igp.scan(h, cfg, when=NOW, say=lambda s: None, ledger=ledger, cid="UCx")
    assert [v["id"] for v in miss] == ["OTHER000001"] and len(env.notes) == 1
    igp.scan(h, cfg, when=NOW, say=lambda s: None, ledger=ledger, cid="UCx")
    assert len(env.notes) == 1                     # once per video


def test_bio_links_list_posted_items_with_instagram_utm(env, cfg):
    ig_item(env, images=[{"path": str(jpeg(env.tmp / "c.jpg")), "alt": "x"}],
            instagram={"kind": "companion", "title": "How to cite a dataset"},
            results={"instagram": {"status": "posted", "posted_at": items.iso(NOW)}})
    rows = igp.links(cfg, 12)
    assert rows == [{"title": "How to cite a dataset", "kind": "companion", "date": "2026-10-23",
                     "url": "https://purplelink.llc/guides/x/?utm_source=instagram&utm_medium=social&utm_campaign=ig-test"}]
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        return type("R", (), {"returncode": 0})()
    assert igp.sync_links(cfg, say=lambda s: None, run=run) is True
    assert calls[0][:4] == ["netlify", "blobs:set", "instagram-links", "latest.json"]
    assert igp.sync_links(cfg, say=lambda s: None, run=run) is False     # unchanged: no second upload


def test_video_env_file_is_read_without_printing(env, cfg, capsys):
    got = media.read_env_file(cfg["media"]["video"]["env_file"])
    assert set(got) == set(media.VIDEO_ENV_KEYS) and capsys.readouterr().out == ""


def test_reel_caption_adds_the_app_tag_and_skips_title_repeats():
    desc = ("BatteryMeter is a free battery meter for the Mac menu bar. It shows charge and the rate per hour.\n\n"
            "Download: https://purplelink.llc/batterymeter/")
    c = cap.reel_caption("BatteryMeter: a free battery meter for the Mac menu bar", desc,
                         extra_tags=cap.app_tags_for_link("https://purplelink.llc/batterymeter/"))
    assert c.count("free battery meter") == 1 and "It shows charge and the rate per hour." in c
    assert c.endswith("#macbattery #mac #macos")
    assert cap.app_tags_for_link("https://www.youtube.com/watch?v=x") == []


class FakeHub:
    """The two calls hub_tag makes, with a taken-tag set like the real hub's used_contents."""

    def __init__(self, taken=()):
        self.taken = set(taken)

    @staticmethod
    def site_path(url):
        return "/x/" if url.startswith("https://purplelink.llc/") else None

    @staticmethod
    def paths():
        return {}

    def make_utm(self, p, url, asset, channel, source="", campaign="", medium="", content=""):
        tag, n = content, 2
        while tag in self.taken:
            tag, n = f"{content}-{n}", n + 1
        self.taken.add(tag)
        return f"{url}?utm_source={source}&utm_medium={medium}&utm_campaign={campaign}&utm_content={tag}"


def test_each_reel_gets_its_own_tag_in_the_bio_link(env, cfg):
    hub = FakeHub(taken={"AAAAAAAAAA1-reel"})
    assert igp.hub_tag("https://purplelink.llc/guides/x/", "AAAAAAAAAA1", hub) == "AAAAAAAAAA1-reel-2"
    assert igp.hub_tag("https://www.youtube.com/watch?v=AAAAAAAAAA1", "AAAAAAAAAA1", hub) == ""
    entry = {"youtube_id": "AAAAAAAAAA2", "title": "Spotlight fix", "description": HOWTO_DESC, "duration": 50.0,
             "width": 1080, "height": 1920, "link": "https://purplelink.llc/guides/x/", "utm_content": "howto-x-reel"}
    it = igp.reel_item(entry, items.iso(NOW))
    assert it.meta["utm_content"] == "howto-x-reel"
    it.meta["results"] = {"instagram": {"status": "posted", "posted_at": items.iso(NOW)}}
    it.path.parent.mkdir(parents=True, exist_ok=True)
    it.save()
    url = igp.links(cfg, 12)[0]["url"]
    assert url.endswith("utm_campaign=ig-reel&utm_content=howto-x-reel")


def test_business_login_link_code_and_exchange():
    from socialpost import setup as st
    url = st.ig_authorize_url("123", "STATE")
    assert url.startswith("https://www.instagram.com/oauth/authorize?client_id=123&redirect_uri=")
    assert "scope=instagram_business_basic%2Cinstagram_business_content_publish" in url and "state=STATE" in url
    back = "https://purplelink.llc/instagram/?code=AQBabc&state=STATE#_"
    assert st.ig_code_from(back, "STATE") == "AQBabc"
    assert st.ig_code_from(back, "OTHER") is None             # a sign-in this run did not start
    assert st.ig_code_from("AQBabc#_", "STATE") == "AQBabc"   # the bare code works too
    h = FakeHttp([("POST", "api.instagram.com/oauth/access_token", jresp({"access_token": "SHORT", "user_id": 1}))])
    assert st.ig_exchange_code(h, "123", "SECRET", "AQBabc") == ("SHORT", "")
    assert h.calls[0]["form"]["redirect_uri"] == "https://purplelink.llc/instagram/" and "SECRET" not in h.calls[0]["url"]
    bad = FakeHttp([("POST", "oauth/access_token", jresp({"error_message": "code SECRET used"}, status=400))])
    tok, err = st.ig_exchange_code(bad, "123", "SECRET", "AQBabc")
    assert tok is None and "SECRET" not in err and "400" in err


def test_setup_stores_nothing_for_a_rejected_or_wrong_token(env, monkeypatch, capsys):
    from socialpost import setup as st, sysutil
    stored = []
    monkeypatch.setattr(sysutil, "keychain_set", lambda *a: stored.append(a))
    answers = iter(["not-a-token"])
    monkeypatch.setattr(st, "_ask_secret", lambda label, required=True: next(answers))
    assert st._setup_instagram(cfgmod.load()) == 1 and not stored
    assert "start with IG" in capsys.readouterr().out
    answers = iter(["IGAAbad", ""])
    monkeypatch.setattr(st, "_ask_secret", lambda label, required=True: next(answers))
    monkeypatch.setattr(st, "build_adapter", lambda cfg, p, secret=None: adapter(
        dict(cfg, platforms={"instagram": {"expected": {}}}), FakeHttp([("GET", "/me?", Resp(401, b"{}"))])))
    assert st._setup_instagram(cfgmod.load()) == 1 and not stored
    assert "Nothing stored" in capsys.readouterr().out
