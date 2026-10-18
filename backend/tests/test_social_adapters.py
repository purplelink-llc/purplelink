"""Every adapter with mocked HTTP, a fake browser page, and a fake keychain: identity refusals, flows, no double posting."""
import contextlib
import datetime as dt
import json
import subprocess

import pytest

from social_helpers import FakeHttp, env, jresp, make_png  # noqa: F401
from socialpost import config as cfgmod
from socialpost import items, media
from socialpost.adapters.bluesky import Bluesky, parse_storage
from socialpost.adapters.linkedin import LinkedIn
from socialpost.adapters.mastodon import Mastodon
from socialpost.adapters.threads import Threads
from socialpost.adapters.x import X
from socialpost.errors import Ambiguous, Disabled, Refused, SessionExpired, SocialError
from socialpost.http import Resp


def blk(name, **over):
    cfg = cfgmod.load()
    b = dict(cfg["platforms"][name])
    b.update(over)
    b["_root"] = cfg
    return b


def secrets(**kw):
    return lambda platform, field: kw.get(field)


def item(env, platforms, text="Release notes. {link}", images=None, **meta):
    it = items.create("t", platforms, "https://purplelink.llc/vitae/", "vitae-140")
    it.sections["default"] = text
    it.meta["images"] = images or []
    it.meta.update(meta)
    it.save()
    return it


# ------------------------------------------------------------------ Mastodon
class TestMastodon:
    def mk(self, http, **over):
        kw = dict(enabled=True, instance="https://mastodon.social", expected={"acct": "purplelink"})
        kw.update(over)
        return Mastodon(blk("mastodon", **kw), http=http, secret=secrets(access_token="tok-123456"),
                        sleep=lambda s: None)

    def routes(self, acct="purplelink"):
        return [("GET", "verify_credentials", jresp({"acct": acct, "id": "42"}))]

    def test_whoami_and_identity_ok_with_bare_or_full_acct(self):
        http = FakeHttp(self.routes())
        a = self.mk(http)
        assert a.check_identity()["acct"] == "purplelink@mastodon.social"
        a = self.mk(http, expected={"acct": "@purplelink@mastodon.social"})
        assert a.check_identity()
        assert http.calls[0]["headers"]["Authorization"] == "Bearer tok-123456"
        assert "tok-123456" not in http.calls[0]["url"]

    def test_wrong_account_is_refused_and_nothing_is_posted(self, env):
        http = FakeHttp(self.routes(acct="ben"))
        with pytest.raises(Refused):
            self.mk(http).post(item(env, ["mastodon"]))
        assert http.posts_to("/statuses") == []

    def test_empty_expected_is_refused(self, env):
        http = FakeHttp(self.routes())
        with pytest.raises(Refused):
            self.mk(http, expected={"acct": ""}).post(item(env, ["mastodon"]))

    def test_post_with_image_uploads_alt_text_and_polls_processing(self, env):
        png = make_png(env.tmp / "a.png")
        it = item(env, ["mastodon"], images=[{"path": str(png), "alt": "a card"}])
        http = FakeHttp(self.routes() + [
            ("POST", "/api/v2/media", jresp({"id": "m1", "url": None}, status=202)),
            ("GET", "/api/v1/media/m1", [Resp(206, b"{}"), Resp(200, b"{}")]),
            ("POST", "/api/v1/statuses", jresp({"id": "s9", "url": "https://mastodon.social/@purplelink/s9"})),
        ])
        r = self.mk(http).post(it)
        assert r.url == "https://mastodon.social/@purplelink/s9" and r.id == "s9"
        up = http.posts_to("/api/v2/media")[0]
        assert b'name="description"' in up["data"] and b"a card" in up["data"]
        st = http.posts_to("/api/v1/statuses")[0]
        assert st["json"]["media_ids"] == ["m1"] and "utm_source=mastodon" in st["json"]["status"]
        assert st["headers"]["Idempotency-Key"] == f"{it.id}-mastodon"

    def test_dry_run_sends_nothing(self, env):
        http = FakeHttp()
        r = self.mk(http).post(item(env, ["mastodon"]), dry_run=True)
        assert r.dry_run and http.calls == []

    def test_missing_token_is_disabled(self, env):
        a = Mastodon(blk("mastodon", enabled=True, instance="https://mastodon.social", expected={"acct": "p"}),
                     http=FakeHttp(), secret=secrets())
        with pytest.raises(Disabled):
            a.whoami()

    def test_instance_must_be_https(self):
        a = Mastodon(blk("mastodon", instance="http://x"), http=FakeHttp(), secret=secrets(access_token="t" * 10))
        with pytest.raises(Disabled):
            a.whoami()

    def test_verify(self):
        http = FakeHttp([("GET", "/api/v1/statuses/s9", jresp({"id": "s9"}))])
        assert self.mk(http).verify("https://mastodon.social/@purplelink/s9")
        assert not self.mk(FakeHttp()).verify("https://mastodon.social/@purplelink/s9")


# ------------------------------------------------------------------ Threads
class TestThreads:
    def mk(self, http, runner=None, **over):
        kw = dict(enabled=True, expected={"user_id": "77", "username": "purplelink"})
        kw.update(over)
        return Threads(blk("threads", **kw),
                       http=http, secret=secrets(access_token="tok-abcdefg"), sleep=lambda s: None)

    def base_routes(self, username="purplelink", uid="77"):
        return [
            ("GET", "/me?fields", jresp({"id": uid, "username": username})),
            ("GET", "fields=status", jresp({"status": "FINISHED"})),
            ("GET", "fields=permalink", jresp({"permalink": "https://www.threads.com/@purplelink/post/AbC"})),
        ]

    def test_text_post_flow_and_permalink(self, env):
        http = FakeHttp(self.base_routes() + [
            ("POST", "/77/threads_publish", jresp({"id": "M1"})),
            ("POST", "/77/threads", jresp({"id": "C1"})),
        ])
        r = self.mk(http).post(item(env, ["threads"]))
        assert r.url.endswith("/post/AbC") and r.id == "M1"
        create = http.posts_to("/77/threads")[0]
        assert create["form"]["media_type"] == "TEXT" and "utm_source=threads" in create["form"]["text"]
        assert http.posts_to("threads_publish")[0]["form"] == {"creation_id": "C1"}
        assert all("tok-abcdefg" not in c["url"] for c in http.calls)

    def test_wrong_account_refused_before_any_container(self, env):
        http = FakeHttp(self.base_routes(username="ben", uid="1"))
        with pytest.raises(Refused):
            self.mk(http).post(item(env, ["threads"]))
        assert http.posts_to("/threads") == []

    def test_identity_is_checked_again_before_publish(self, env):
        seq = [jresp({"id": "77", "username": "purplelink"}), jresp({"id": "1", "username": "ben"})]
        http = FakeHttp([("GET", "/me?fields", seq), ("GET", "fields=status", jresp({"status": "FINISHED"})),
                         ("POST", "/threads", jresp({"id": "C1"}))])
        with pytest.raises(Refused):
            self.mk(http).post(item(env, ["threads"]))
        assert http.posts_to("threads_publish") == []

    def test_single_image_uses_hosted_url_and_alt_text(self, env, monkeypatch):
        png = make_png(env.tmp / "a.png")
        monkeypatch.setattr(media, "ensure_hosted", lambda cfg, path, http, run=None: "https://purplelink.llc/social-media/k.png")
        http = FakeHttp(self.base_routes() + [("POST", "/77/threads_publish", jresp({"id": "M1"})),
                                              ("POST", "/77/threads", jresp({"id": "C1"}))])
        self.mk(http).post(item(env, ["threads"], images=[{"path": str(png), "alt": "chart"}]))
        f = http.posts_to("/77/threads")[0]["form"]
        assert f["media_type"] == "IMAGE" and f["image_url"].startswith("https://purplelink.llc/social-media/") and f["alt_text"] == "chart"

    def test_carousel_creates_children_then_parent(self, env, monkeypatch):
        pngs = [make_png(env.tmp / f"{i}.png", i) for i in range(3)]
        monkeypatch.setattr(media, "ensure_hosted", lambda cfg, path, http, run=None: f"https://purplelink.llc/social-media/{path.stem}.png")
        counter = iter(["K1", "K2", "K3", "P1"])
        http = FakeHttp(self.base_routes() + [("POST", "/77/threads_publish", jresp({"id": "M1"})),
                                              ("POST", "/77/threads", lambda c: jresp({"id": next(counter)}))])
        self.mk(http).post(item(env, ["threads"], images=[{"path": str(p), "alt": f"a{i}"} for i, p in enumerate(pngs)]))
        creates = http.posts_to("/77/threads")
        assert [c["form"].get("is_carousel_item") for c in creates[:3]] == ["true"] * 3
        assert [c["form"]["alt_text"] for c in creates[:3]] == ["a0", "a1", "a2"]
        assert creates[3]["form"]["media_type"] == "CAROUSEL" and creates[3]["form"]["children"] == "K1,K2,K3"
        assert http.posts_to("threads_publish")[0]["form"] == {"creation_id": "P1"}

    def test_publish_timeout_is_ambiguous_never_a_plain_failure(self, env):
        http = FakeHttp(self.base_routes() + [("POST", "/77/threads_publish", Resp(0)),
                                              ("POST", "/77/threads", jresp({"id": "C1"}))])
        with pytest.raises(Ambiguous):
            self.mk(http).post(item(env, ["threads"]))

    def test_missing_permalink_still_returns_the_post(self, env):
        routes = [r for r in self.base_routes() if "permalink" not in r[1]]
        http = FakeHttp(routes + [("POST", "/77/threads_publish", jresp({"id": "M1"})),
                                  ("POST", "/77/threads", jresp({"id": "C1"}))])
        r = self.mk(http).post(item(env, ["threads"]))
        assert r.id == "M1" and "threads.com/@purplelink" in r.url

    def test_container_error_raises(self, env):
        http = FakeHttp([("GET", "/me?fields", jresp({"id": "77", "username": "purplelink"})),
                         ("GET", "fields=status", jresp({"status": "ERROR", "error_message": "bad image"})),
                         ("POST", "/threads", jresp({"id": "C1"}))])
        with pytest.raises(SocialError, match="ERROR"):
            self.mk(http).post(item(env, ["threads"]))

    def test_refresh_stores_new_token(self, monkeypatch):
        stored = {}
        from socialpost import sysutil
        monkeypatch.setattr(sysutil, "keychain_set", lambda p, f, v: stored.update({(p, f): v}))
        http = FakeHttp([("POST", "refresh_access_token", jresp({"access_token": "new-token-123"}))])
        self.mk(http).refresh()
        assert stored[("threads", "access_token")] == "new-token-123"
        assert "tok-abcdefg" not in http.calls[0]["url"]


class FakeHttpHead(FakeHttp):
    pass


def test_media_hosting_uploads_then_verifies(env, tmp_path):
    png = make_png(tmp_path / "a.png")
    key = media.key_for(png)
    assert len(key.split(".")[0]) == 40 and key.endswith(".png")
    cfg = cfgmod.load()
    url = media.public_url(cfg, key)
    state = {"up": False}
    http = FakeHttp([("HEAD", key, lambda c: Resp(200, b"", {"content-type": "image/png", "content-length": str(png.stat().st_size)}) if state["up"] else Resp(404))])
    ran = []

    def run(cmd, **kw):
        ran.append(cmd)
        state["up"] = True
        return subprocess.CompletedProcess(cmd, 0, "", "")

    assert media.ensure_hosted(cfg, png, http, run) == url
    assert ran[0][:3] == ["netlify", "blobs:set", "social-media"] and key in ran[0]
    ran.clear()
    assert media.ensure_hosted(cfg, png, http, run) == url
    assert ran == []  # already live: no second upload


def test_media_hosting_fails_when_function_not_live(env, tmp_path):
    png = make_png(tmp_path / "a.png")
    with pytest.raises(SocialError, match="does not serve it yet"):
        media.ensure_hosted(cfgmod.load(), png, FakeHttp(), lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, "", ""))
    gif = tmp_path / "a.gif"
    gif.write_bytes(b"GIF89a")
    with pytest.raises(SocialError):
        media.key_for(gif)


# ------------------------------------------------------------------ X
class TestX:
    def mk(self, http, **over):
        base = dict(enabled=True, paid_posting_ok=True, expected={"user_id": "9", "username": "purplelink"})
        base.update(over)
        return X(blk("x", **base), http=http, secret=secrets(access_token="xtok-1234567", refresh_token="r-12345678", client_id="cid-12345678"))

    def routes(self, uname="purplelink", uid="9"):
        return [("GET", "/2/users/me", jresp({"data": {"id": uid, "username": uname}}))]

    def test_refused_when_not_paid_ok(self, env):
        with pytest.raises(Disabled):
            self.mk(FakeHttp(self.routes()), paid_posting_ok=False).post(item(env, ["x"], text="hi"))

    def test_wrong_account_refused(self, env):
        http = FakeHttp(self.routes(uname="ben", uid="1"))
        with pytest.raises(Refused):
            self.mk(http).post(item(env, ["x"], text="hi"))
        assert http.posts_to("/2/tweets") == []

    def test_post_with_image_and_alt_text(self, env):
        png = make_png(env.tmp / "a.png")
        http = FakeHttp(self.routes() + [
            ("POST", "/2/media/upload", jresp({"data": {"id": "mm1"}})),
            ("POST", "/2/media/metadata", jresp({})),
            ("POST", "/2/tweets", jresp({"data": {"id": "t1"}}))])
        r = self.mk(http).post(item(env, ["x"], text="Short. {link}", images=[{"path": str(png), "alt": "alt!"}]))
        assert r.url == "https://x.com/purplelink/status/t1"
        assert http.posts_to("/2/media/metadata")[0]["json"] == {"id": "mm1", "metadata": {"alt_text": {"text": "alt!"}}}
        t = http.posts_to("/2/tweets")[0]["json"]
        assert t["media"] == {"media_ids": ["mm1"]} and "utm_source=x" in t["text"]

    def test_401_refreshes_the_token_once(self, env, monkeypatch):
        from socialpost import sysutil
        stored = {}
        monkeypatch.setattr(sysutil, "keychain_set", lambda p, f, v: stored.update({f: v}))
        http = FakeHttp([("GET", "/2/users/me", [Resp(401), jresp({"data": {"id": "9", "username": "purplelink"}})]),
                         ("POST", "oauth2/token", jresp({"access_token": "new-a-1234567", "refresh_token": "new-r-1234567"}))])
        assert self.mk(http).whoami()["username"] == "purplelink"
        assert stored == {"access_token": "new-a-1234567", "refresh_token": "new-r-1234567"}

    def test_create_timeout_is_ambiguous(self, env):
        http = FakeHttp(self.routes() + [("POST", "/2/tweets", Resp(503))])
        with pytest.raises(Ambiguous):
            self.mk(http).post(item(env, ["x"], text="hi"))


# ------------------------------------------------------------------ Bluesky
class FakeLocator:
    def __init__(self, page, tid, n=1):
        self.page, self.tid = page, tid

    def click(self, **kw):
        self.page.log.append(("click", self.tid))
        if self.tid == "composerPublishBtn":
            self.page.published = True
        if self.tid == "removePhotoButton":
            self.page.thumbs -= 1

    def wait_for(self, **kw):
        pass

    def count(self):
        return self.page.thumbs if self.tid == "selectedPhotoImage" else 1

    def nth(self, i):
        self.page.log.append(("nth", self.tid, i))
        return self

    @property
    def last(self):
        return self


class FakeDialog:
    def __init__(self, page):
        self.page = page

    def get_by_label(self, *a, **k):
        return self

    def get_by_role(self, *a, **k):
        return self

    @property
    def first(self):
        return self

    @property
    def last(self):
        return self

    def fill(self, text):
        self.page.log.append(("alt", text))

    def click(self, **kw):
        self.page.log.append(("save",))


class FakeChooser:
    def __init__(self, page):
        self.page = page

    @property
    def value(self):
        return self

    def set_files(self, files):
        self.page.log.append(("files", list(files)))
        self.page.thumbs += len(files) * self.page.dup_factor

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeKeyboard:
    def __init__(self, page):
        self.page = page

    def insert_text(self, t):
        self.page.log.append(("text", t))


class FakePage:
    def __init__(self, handle="purplelink.llc", did="did:plc:abc", dup_factor=1, storage=True):
        self.handle, self.did, self.dup_factor, self.storage = handle, did, dup_factor, storage
        self.thumbs, self.log, self.published = 0, [], False
        self.keyboard = FakeKeyboard(self)

    def goto(self, url, **kw):
        self.log.append(("goto", url))

    def wait_for_timeout(self, ms):
        pass

    def evaluate(self, js):
        if "BSKY_STORAGE" in js and not self.storage:
            return None
        if "BSKY_STORAGE" in js:
            return json.dumps({"session": {"currentAccount": {"handle": self.handle, "did": self.did}}}) if self.handle else None
        if "profile" in js.lower():  # the left-nav Profile link fallback
            return f"/profile/{self.handle}" if self.handle else None
        return None

    def get_by_role(self, role, **kw):
        return FakeDialog(self) if role == "dialog" else FakeLocator(self, "new-post")

    def get_by_test_id(self, tid):
        return FakeLocator(self, tid)

    def expect_file_chooser(self, **kw):
        return FakeChooser(self)


def bsky(page, http, **over):
    @contextlib.contextmanager
    def factory():
        yield page

    exp = {"handle": "purplelink.llc"}
    exp.update(over.pop("expected", {}))
    return Bluesky(blk("bluesky", enabled=True, expected=exp), http=http, session_factory=factory, sleep=lambda s: None)


def feed(handle, text, when, rkey="3abc"):
    return jresp({"feed": [{"post": {"uri": f"at://did:plc:abc/app.bsky.feed.post/{rkey}", "author": {"handle": handle},
                                     "record": {"text": text, "createdAt": when.isoformat().replace("+00:00", "Z")}}}]})


PROFILE = ("GET", "getProfile", jresp({"did": "did:plc:abc", "handle": "purplelink.llc"}))


class TestBluesky:
    def test_parse_storage(self):
        raw = json.dumps({"session": {"currentAccount": {"handle": "a.b", "did": "did:plc:z"}}})
        assert parse_storage(raw) == {"handle": "a.b", "did": "did:plc:z"}
        assert parse_storage("not json") is None and parse_storage(None) is None and parse_storage("{}") is None

    def test_identity_falls_back_to_the_nav_profile_link(self):
        assert bsky(FakePage(storage=False), FakeHttp([PROFILE])).check_identity()["did"] == "did:plc:abc"
        with pytest.raises(Refused):
            bsky(FakePage(storage=False, handle="ben.bsky.social"),
                 FakeHttp([("GET", "getProfile", jresp({"did": "did:plc:ben", "handle": "ben.bsky.social"}))])).check_identity()

    def test_whoami_ok(self):
        assert bsky(FakePage(), FakeHttp([PROFILE])).check_identity()["handle"] == "purplelink.llc"

    def test_personal_account_is_refused_and_never_composes(self, env):
        page = FakePage(handle="ben.bsky.social", did="did:plc:ben")
        http = FakeHttp([("GET", "getProfile", jresp({"did": "did:plc:ben", "handle": "ben.bsky.social"}))])
        with pytest.raises(Refused):
            bsky(page, http).post(item(env, ["bluesky"]))
        assert not any(e[0] == "text" for e in page.log) and not page.published

    def test_session_did_must_match_the_public_handle(self, env):
        page = FakePage(did="did:plc:other")
        with pytest.raises(Refused):
            bsky(page, FakeHttp([PROFILE])).whoami()

    def test_not_signed_in_is_session_expired(self):
        with pytest.raises(SessionExpired):
            bsky(FakePage(handle=None), FakeHttp([PROFILE])).whoami()

    def test_post_text_then_verified_through_the_public_feed(self, env):
        text_start = "Release notes."
        it = item(env, ["bluesky"], text=text_start + " {link}")
        page = FakePage()
        now = dt.datetime.now(dt.timezone.utc)
        feeds = [Resp(200, b'{"feed": []}'), feed("purplelink.llc", it.render("bluesky"), now)]
        http = FakeHttp([PROFILE, ("GET", "getAuthorFeed", feeds)])
        r = bsky(page, http).post(it)
        assert r.url == "https://bsky.app/profile/purplelink.llc/post/3abc" and r.id.startswith("at://")
        assert page.published and ("text", it.render("bluesky")) in page.log

    def test_images_attached_through_the_file_chooser_with_alt_text(self, env):
        a, b = make_png(env.tmp / "a.png"), make_png(env.tmp / "b.png", 2)
        it = item(env, ["bluesky"], images=[{"path": str(a), "alt": "first"}, {"path": str(b), "alt": "second"}])
        page = FakePage()
        now = dt.datetime.now(dt.timezone.utc)
        http = FakeHttp([PROFILE, ("GET", "getAuthorFeed", [Resp(200, b'{"feed": []}'), feed("purplelink.llc", it.render("bluesky"), now)])])
        bsky(page, http).post(it)
        assert ("files", [str(a), str(b)]) in page.log
        assert [e[1] for e in page.log if e[0] == "alt"] == ["first", "second"]

    def test_double_added_images_are_deduplicated(self, env):
        a = make_png(env.tmp / "a.png")
        it = item(env, ["bluesky"], images=[{"path": str(a), "alt": "one"}])
        page = FakePage(dup_factor=2)  # the composer adds the image twice
        now = dt.datetime.now(dt.timezone.utc)
        http = FakeHttp([PROFILE, ("GET", "getAuthorFeed", [Resp(200, b'{"feed": []}'), feed("purplelink.llc", it.render("bluesky"), now)])])
        bsky(page, http).post(it)
        assert page.thumbs == 1
        assert [e for e in page.log if e == ("click", "removePhotoButton")]

    def test_missing_image_aborts_before_publish(self, env):
        a = make_png(env.tmp / "a.png")
        it = item(env, ["bluesky"], images=[{"path": str(a), "alt": "one"}])
        page = FakePage(dup_factor=0)
        with pytest.raises(SocialError, match="expected 1"):
            bsky(page, FakeHttp([PROFILE, ("GET", "getAuthorFeed", Resp(200, b'{"feed": []}'))])).post(it)
        assert not page.published

    def test_already_live_text_is_not_reposted(self, env):
        it = item(env, ["bluesky"])
        page = FakePage()
        now = dt.datetime.now(dt.timezone.utc)
        http = FakeHttp([PROFILE, ("GET", "getAuthorFeed", feed("purplelink.llc", it.render("bluesky"), now))])
        r = bsky(page, http).post(it)
        assert "already live" in r.detail and not page.published

    def test_click_without_feed_confirmation_is_ambiguous(self, env):
        it = item(env, ["bluesky"])
        page = FakePage()
        with pytest.raises(Ambiguous):
            bsky(page, FakeHttp([PROFILE, ("GET", "getAuthorFeed", Resp(200, b'{"feed": []}'))])).post(it)
        assert page.published

    def test_dry_run_fills_the_composer_but_never_publishes(self, env):
        page = FakePage()
        r = bsky(page, FakeHttp([PROFILE])).post(item(env, ["bluesky"]), dry_run=True)
        assert r.dry_run and not page.published

    def test_verify_uses_the_public_appview(self):
        http = FakeHttp([PROFILE, ("GET", "getPosts", jresp({"posts": [{"uri": "x"}]}))])
        assert bsky(FakePage(), http).verify("https://bsky.app/profile/purplelink.llc/post/3abc")
        assert not bsky(FakePage(), http).verify("https://example.com/x")

    def test_no_api_credential_is_ever_read(self, env):
        calls = []
        a = bsky(FakePage(), FakeHttp([PROFILE]))
        a._secret = lambda p, f: calls.append((p, f))
        a.whoami()
        assert calls == []


# ------------------------------------------------------------------ LinkedIn
class FakeLiPage:
    def __init__(self, url="https://www.linkedin.com/company/120183926/admin/page-posts/published/", body="Purplelink LLC page posts"):
        self.url, self.body = url, body

    def goto(self, url, **kw):
        pass

    def wait_for_timeout(self, ms):
        pass

    def inner_text(self, sel, **kw):
        return self.body


def li(page, runner=None, **over):
    @contextlib.contextmanager
    def factory():
        yield page

    return LinkedIn(blk("linkedin", enabled=True, **over), http=FakeHttp(), session_factory=factory,
                    runner=runner or (lambda *a, **k: subprocess.CompletedProcess(a, 0, "", "")), sleep=lambda s: None)


class TestLinkedIn:
    def test_identity_ok(self):
        assert li(FakeLiPage()).check_identity() == {"company_id": "120183926", "name": "Purplelink LLC"}

    def test_other_company_or_name_refused(self, env):
        with pytest.raises(Refused):
            li(FakeLiPage(url="https://www.linkedin.com/company/999/admin/page-posts/")).check_identity()
        with pytest.raises(Refused):
            li(FakeLiPage(body="Ben Ampel")).check_identity()

    def test_login_redirect_is_session_expired(self):
        with pytest.raises(SessionExpired):
            li(FakeLiPage(url="https://www.linkedin.com/login")).whoami()

    def test_post_runs_the_company_poster_and_confirms_on_the_page(self, env):
        it = item(env, ["linkedin"], text="Company update. {link}")
        page = FakeLiPage()
        calls = []

        def runner(cmd, **kw):
            calls.append(cmd)
            page.body += " " + it.render("linkedin")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        r = li(page, runner).post(it)
        assert r.url.startswith("https://www.linkedin.com/company/120183926/")
        assert "--headless" in calls[0] and "--text-file" in calls[0] and "--dry-run" not in calls[0]

    def test_exit_4_from_the_poster_is_a_refusal(self, env):
        r = lambda cmd, **kw: subprocess.CompletedProcess(cmd, 4, "", "")
        with pytest.raises(Refused):
            li(FakeLiPage(), r).post(item(env, ["linkedin"]))

    def test_exit_2_is_session_expired_and_3_is_a_plain_failure(self, env):
        with pytest.raises(SessionExpired):
            li(FakeLiPage(), lambda c, **k: subprocess.CompletedProcess(c, 2, "", "")).post(item(env, ["linkedin"]))
        with pytest.raises(SocialError):
            li(FakeLiPage(), lambda c, **k: subprocess.CompletedProcess(c, 3, "", "")).post(item(env, ["linkedin"]))

    def test_text_already_on_the_page_is_not_reposted(self, env):
        it = item(env, ["linkedin"])
        page = FakeLiPage(body="Purplelink LLC " + it.render("linkedin"))
        called = []
        r = li(page, lambda c, **k: called.append(c)).post(it)
        assert r.id == "already-live" and called == []

    def test_success_exit_but_not_on_page_is_ambiguous(self, env):
        with pytest.raises(Ambiguous):
            li(FakeLiPage()).post(item(env, ["linkedin"]))

    def test_document_is_passed_with_its_title(self, env):
        pdf = env.tmp / "deck.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        it = item(env, ["linkedin"], document={"path": str(pdf), "title": "Deck"})
        calls = []
        r = li(FakeLiPage(), lambda c, **k: (calls.append(c), subprocess.CompletedProcess(c, 0, "", ""))[1]).post(it, dry_run=True)
        assert r.dry_run and "--document" in calls[0] and "Deck" in calls[0] and "--dry-run" in calls[0]
