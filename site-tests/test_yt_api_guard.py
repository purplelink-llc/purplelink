"""The YouTube API upload path must never put content on the wrong channel (Ben, 2026-10-17).
Fake service objects only: no network, no OAuth, no google libraries needed."""
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
import yt_guard as g  # noqa: E402


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cli = load("yt_api_upload", "yt-api-upload.py")
login = load("yt_login", "yt-login.py")

PL_REAL = "UCUv28P5SUzT4RLQOmi3EK8w"
PH = "UC" + "h" * 22      # synthetic ids: tests never depend on the real Pixel Hearth id
PL = "UC" + "p" * 22
OTHER = "UC" + "z" * 22


class Exec:
    def __init__(self, fn):
        self.fn = fn

    def execute(self):
        return self.fn()


class Request:
    """Resumable insert request: next_chunk returns (None, None) once, then the response."""

    def __init__(self, svc, body, media):
        self.svc, self.body, self.media, self.n = svc, body, media, 0

    def next_chunk(self, num_retries=0):
        self.n += 1
        if self.n < 2:
            return None, None
        return None, {"id": self.svc.new_id}


class FakeService:
    def __init__(self, mine_items=None, landed=PH, recent=None, new_id="NEWVIDEO001", insert_error=None):
        self.mine_items = [{"id": PH, "snippet": {"title": "Pixel Hearth"}}] if mine_items is None else mine_items
        self.landed = landed
        self.recent = recent or []
        self.new_id = new_id
        self.insert_error = insert_error
        self.calls = []
        self.inserts = []
        self.updates = []
        self.thumbs = []

    def channels(self):
        svc = self

        class C:
            def list(self, **kw):
                svc.calls.append(("channels.list", kw))
                if kw.get("part") == "contentDetails":
                    return Exec(lambda: {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UUx"}}}]})
                return Exec(lambda: {"items": svc.mine_items})
        return C()

    def playlistItems(self):
        svc = self

        class P:
            def list(self, **kw):
                svc.calls.append(("playlistItems.list", kw))
                return Exec(lambda: {"items": svc.recent})
        return P()

    def videos(self):
        svc = self

        class V:
            def insert(self, **kw):
                svc.calls.append(("videos.insert", kw))
                svc.inserts.append(kw)
                if svc.insert_error:
                    raise svc.insert_error
                return Request(svc, kw["body"], kw["media_body"])

            def list(self, **kw):
                svc.calls.append(("videos.list", kw))
                return Exec(lambda: {"items": [{
                    "id": kw["id"],
                    "snippet": {"channelId": svc.landed, "channelTitle": "Whoever"},
                    "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False,
                               "uploadStatus": "uploaded", "publishAt": "2026-12-01T00:00:00Z"}}]})

            def update(self, **kw):
                svc.calls.append(("videos.update", kw))
                svc.updates.append(kw)
                return Exec(lambda: {})
        return V()

    def thumbnails(self):
        svc = self

        class T:
            def set(self, **kw):
                svc.calls.append(("thumbnails.set", kw))
                svc.thumbs.append(kw)
                return Exec(lambda: {})
        return T()

    def names(self):
        return [c[0] for c in self.calls]


class GuardCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.video = self.dir / "v.mp4"
        self.video.write_bytes(b"x")
        self.registry = {
            "purplelink": {"id": PL, "title": "Purplelink", "token": "~/.config/purplelink/yt_token_purplelink.json",
                           "kinds": ["howto", "howto-short", "product", "tutorial", "latex"], "default_category": "28", "confirmed": True},
            "pixelhearth": {"id": PH, "title": "Pixel Hearth", "token": "~/.config/purplelink/yt_token_pixelhearth.json",
                            "kinds": ["ambient", "photo-quiz"], "default_category": "10", "confirmed": True},
        }
        self.real = g.load_registry()
        self.notes = []

    def up(self, svc, channel="pixelhearth", kind="ambient", title="A title", **kw):
        kw.setdefault("notify", lambda m, title="": self.notes.append(m))
        return g.guarded_upload(channel, kind, self.video, title, registry=self.registry, service=svc,
                                lock_path=self.dir / "lock", media_factory=lambda p, mt, **k: ("media", str(p), mt),
                                sleep=lambda s: None, **kw)


class Registry(GuardCase):
    def test_registry_has_both_channels_and_kinds(self):
        r = self.real
        self.assertEqual(r["purplelink"]["id"], PL_REAL)
        self.assertIs(r["purplelink"]["confirmed"], True)
        self.assertIn("confirmed", r["pixelhearth"])
        self.assertEqual(r["pixelhearth"]["kinds"], ["ambient", "photo-quiz"])
        self.assertEqual(r["purplelink"]["kinds"], ["howto", "howto-short", "product", "tutorial", "latex"])
        self.assertEqual(r["pixelhearth"]["default_category"], "10")
        self.assertEqual(r["purplelink"]["default_category"], "28")
        self.assertNotEqual(r["pixelhearth"]["id"], PL_REAL)

    def test_token_paths_are_outside_the_repo(self):
        for key, ch in self.real.items():
            tp = g.token_path(ch).resolve()
            self.assertFalse(str(tp).startswith(str(ROOT.resolve()) + os.sep), key)
            self.assertEqual(tp.parent, (Path.home() / ".config" / "purplelink").resolve())

    def test_a_token_path_inside_the_repo_is_refused(self):
        bad = self.dir / "reg.json"
        bad.write_text(json.dumps({"channels": {"x": {"id": PH, "title": "X", "token": str(ROOT / "scripts" / "tok.json"),
                                                       "kinds": ["a"], "default_category": "10"}}}))
        with self.assertRaises(g.ChannelGuardError):
            g.load_registry(bad)

    def test_duplicate_ids_are_refused(self):
        bad = self.dir / "reg.json"
        ch = {"id": PH, "title": "X", "token": "~/t.json", "kinds": ["a"], "default_category": "10"}
        bad.write_text(json.dumps({"channels": {"a": ch, "b": dict(ch)}}))
        with self.assertRaises(g.ChannelGuardError):
            g.load_registry(bad)

    def test_unknown_channel_is_refused(self):
        with self.assertRaises(g.ChannelGuardError):
            g.get_channel("nope", self.registry)


class Confirmed(GuardCase):
    def test_unconfirmed_channel_refuses_with_no_api_call(self):
        for flag in (False, None):
            reg = {"pixelhearth": dict(self.registry["pixelhearth"])}
            if flag is None:
                del reg["pixelhearth"]["confirmed"]
            else:
                reg["pixelhearth"]["confirmed"] = flag
            svc = FakeService()
            self.registry = reg
            with self.assertRaises(g.ChannelGuardError) as cm:
                self.up(svc)
            self.assertIn("channel not confirmed by Ben in yt-channels.json", str(cm.exception))
            with self.assertRaises(g.ChannelGuardError):
                g.dry_run("pixelhearth", "ambient", registry=reg, service=svc)
            self.assertEqual(svc.calls, [])

    def test_the_shipped_registry_is_unconfirmed_for_pixelhearth_until_ben_confirms(self):
        # flip this assertion together with the registry when Ben confirms the id
        self.assertIs(self.real["pixelhearth"]["confirmed"], False)
        with self.assertRaises(g.ChannelGuardError):
            g.guarded_upload("pixelhearth", "ambient", __file__, "t", service=FakeService(), lock_path=self.dir / "l")


class KindAndIdentity(GuardCase):
    def test_kind_not_in_registry_refuses_with_no_api_call(self):
        svc = FakeService()
        with self.assertRaises(g.ChannelGuardError):
            self.up(svc, channel="pixelhearth", kind="howto")
        with self.assertRaises(g.ChannelGuardError):
            self.up(svc, channel="purplelink", kind="ambient")
        self.assertEqual(svc.calls, [])

    def test_identity_mismatch_refuses_with_no_insert(self):
        svc = FakeService(mine_items=[{"id": PL, "snippet": {"title": "Purplelink"}}])
        with self.assertRaises(g.ChannelGuardError) as cm:
            self.up(svc)
        self.assertIn(PL, str(cm.exception))
        self.assertNotIn("videos.insert", svc.names())

    def test_multiple_channels_refuse(self):
        svc = FakeService(mine_items=[{"id": PH, "snippet": {"title": "a"}}, {"id": PL, "snippet": {"title": "b"}}])
        with self.assertRaises(g.ChannelGuardError):
            self.up(svc)
        self.assertNotIn("videos.insert", svc.names())

    def test_zero_channels_refuse(self):
        svc = FakeService(mine_items=[])
        with self.assertRaises(g.ChannelGuardError):
            self.up(svc)
        self.assertNotIn("videos.insert", svc.names())

    def test_identity_call_uses_mine_and_id_snippet(self):
        svc = FakeService()
        self.up(svc)
        first = svc.calls[0]
        self.assertEqual(first[0], "channels.list")
        self.assertEqual(first[1], {"part": "id,snippet", "mine": True})


class Uploading(GuardCase):
    def test_duplicate_title_returns_existing_id_without_insert(self):
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        recent = [{"snippet": {"title": "Same title", "publishedAt": (now - datetime.timedelta(hours=3)).isoformat().replace("+00:00", "Z"),
                               "resourceId": {"videoId": "EXISTING001"}}}]
        svc = FakeService(recent=recent)
        r = self.up(svc, title="Same title")
        self.assertEqual(r["id"], "EXISTING001")
        self.assertTrue(r["duplicate"])
        self.assertNotIn("videos.insert", svc.names())

    def test_an_old_or_different_title_does_not_count(self):
        import datetime
        old = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=30)).isoformat().replace("+00:00", "Z")
        recent = [{"snippet": {"title": "Same title", "publishedAt": old, "resourceId": {"videoId": "OLD"}}}]
        svc = FakeService(recent=recent)
        self.assertEqual(self.up(svc, title="Same title")["id"], "NEWVIDEO001")
        self.assertEqual(len(svc.inserts), 1)

    def test_happy_path_returns_dict_and_sends_scheduling_and_synthetic_flags(self):
        svc = FakeService()
        r = self.up(svc, title="Rain", description="d", tags=["a", "b"], privacy="private",
                    publish_at="2026-12-01T09:00:00-05:00", thumbnail=str(self.video))
        self.assertEqual((r["id"], r["url"], r["channel_id"]), ("NEWVIDEO001", "https://youtu.be/NEWVIDEO001", PH))
        self.assertEqual(r["privacy"], "public")
        self.assertIn("channel_title", r)
        body = svc.inserts[0]["body"]
        self.assertEqual(svc.inserts[0]["part"], "snippet,status")
        self.assertEqual(body["snippet"], {"title": "Rain", "description": "d", "tags": ["a", "b"], "categoryId": "10"})
        self.assertEqual(body["status"]["publishAt"], "2026-12-01T14:00:00.000Z")
        self.assertEqual(body["status"]["privacyStatus"], "private")
        self.assertIs(body["status"]["containsSyntheticMedia"], True)
        self.assertIs(body["status"]["selfDeclaredMadeForKids"], False)
        self.assertEqual(len(svc.thumbs), 1)
        self.assertEqual(svc.thumbs[0]["videoId"], "NEWVIDEO001")
        self.assertEqual(svc.names().index("videos.list") > svc.names().index("videos.insert"), True)
        self.assertEqual(self.notes, [])

    def test_synthetic_flag_defaults_by_kind_and_can_be_turned_off(self):
        svc = FakeService()
        self.up(svc, kind="photo-quiz")
        self.assertIs(svc.inserts[0]["body"]["status"]["containsSyntheticMedia"], True)
        svc2 = FakeService()
        self.up(svc2, synthetic=False)
        self.assertIs(svc2.inserts[0]["body"]["status"]["containsSyntheticMedia"], False)

    def test_publish_at_needs_private_and_an_offset(self):
        svc = FakeService()
        with self.assertRaises(g.UploadArgsError):
            self.up(svc, privacy="public", publish_at="2026-12-01T09:00:00Z")
        with self.assertRaises(g.UploadArgsError):
            self.up(svc, privacy="private", publish_at="2026-12-01T09:00:00")
        self.assertEqual(svc.calls, [])

    def test_post_verify_mismatch_sets_private_notifies_and_raises(self):
        svc = FakeService(landed=OTHER)
        with self.assertRaises(g.ChannelGuardError) as cm:
            self.up(svc)
        self.assertIn(OTHER, str(cm.exception))
        self.assertEqual(len(svc.updates), 1)
        upd = svc.updates[0]
        self.assertEqual(upd["body"]["id"], "NEWVIDEO001")
        self.assertEqual(upd["body"]["status"]["privacyStatus"], "private")
        self.assertNotIn("publishAt", upd["body"]["status"])
        self.assertNotIn("uploadStatus", upd["body"]["status"])
        self.assertEqual(self.notes, ["YouTube guard: NEWVIDEO001 landed on the wrong channel, set Private"])

    def test_missing_file_and_bad_title_refuse_before_any_api_call(self):
        svc = FakeService()
        with self.assertRaises(g.UploadArgsError):
            g.guarded_upload("pixelhearth", "ambient", self.dir / "nope.mp4", "t", registry=self.registry, service=svc,
                             lock_path=self.dir / "lock")
        with self.assertRaises(g.UploadArgsError):
            self.up(svc, title="x" * 101)
        self.assertEqual(svc.calls, [])

    def test_a_dropped_connection_after_insert_finds_the_video_instead_of_failing(self):
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")

        class Gone(Exception):
            resp = type("R", (), {"status": 410})()
        svc = FakeService(insert_error=Gone("gone"))
        lookups = []

        orig = svc.playlistItems

        def late():
            p = orig()
            lookups.append(1)
            if len(lookups) >= 2:   # the pre-upload lookup sees nothing, the post-failure lookup sees the video
                svc.recent = [{"snippet": {"title": "A title", "publishedAt": now, "resourceId": {"videoId": "GHOST000001"}}}]
            return p
        svc.playlistItems = late
        self.assertEqual(self.up(svc)["id"], "GHOST000001")

    def test_quota_errors_raise_the_cap_error(self):
        svc = FakeService(insert_error=Exception("The request cannot be completed because you have exceeded your quota. quotaExceeded"))
        with self.assertRaises(g.UploadCapError):
            self.up(svc)


class Lock(GuardCase):
    def test_a_held_lock_blocks_a_second_upload_until_timeout(self):
        with g.UploadLock(self.dir / "l", timeout=0, sleep=lambda s: None):
            with self.assertRaises(g.ChannelGuardError):
                with g.UploadLock(self.dir / "l", timeout=0, sleep=lambda s: None):
                    pass
        with g.UploadLock(self.dir / "l", timeout=0):   # released afterwards
            pass


class Cli(GuardCase):
    def run_cli(self, argv, svc):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cli.main(argv, registry=self.registry, service=svc, lock_path=self.dir / "lock",
                          notify=lambda *a, **k: None, media_factory=lambda p, mt, **k: "m", sleep=lambda s: None)
        return rc, out.getvalue(), err.getvalue()

    def test_success_prints_url_and_verified_line(self):
        svc = FakeService(mine_items=[{"id": PH, "snippet": {"title": "Pixel Hearth"}}])
        rc, out, _ = self.run_cli(["--channel", "pixelhearth", "--kind", "ambient", str(self.video), "--title", "T"], svc)
        self.assertEqual(rc, 0)
        self.assertIn("https://youtu.be/NEWVIDEO001", out)
        self.assertIn(f"verified channel: {PH} (", out)
        self.assertEqual(svc.inserts[0]["body"]["status"]["privacyStatus"], "unlisted")   # safe default

    def test_dry_run_checks_but_never_inserts(self):
        svc = FakeService()
        rc, out, _ = self.run_cli(["--channel", "pixelhearth", "--kind", "ambient", str(self.video), "--title", "T", "--dry-run"], svc)
        self.assertEqual(rc, 0)
        self.assertIn(f"verified channel: {PH} (Pixel Hearth)", out)
        self.assertNotIn("videos.insert", svc.names())

    def test_guard_failures_exit_3(self):
        rc, _, err = self.run_cli(["--channel", "pixelhearth", "--kind", "howto", str(self.video), "--title", "T"], FakeService())
        self.assertEqual(rc, 3)
        rc, _, _ = self.run_cli(["--channel", "pixelhearth", "--kind", "ambient", str(self.video), "--title", "T"],
                                FakeService(mine_items=[{"id": PL, "snippet": {"title": "Purplelink"}}]))
        self.assertEqual(rc, 3)

    def test_description_file_is_read(self):
        f = self.dir / "d.txt"
        f.write_text("from a file")
        svc = FakeService()
        self.run_cli(["--channel", "pixelhearth", "--kind", "ambient", str(self.video), "--title", "T",
                      "--description-file", str(f), "--tags", "a, b"], svc)
        sn = svc.inserts[0]["body"]["snippet"]
        self.assertEqual((sn["description"], sn["tags"]), ("from a file", ["a", " b"][:1] + ["b"]))


class Login(GuardCase):
    class Creds:
        def to_json(self):
            return '{"refresh_token": "r"}'

    def run_login(self, found, registry=None):
        reg = registry or {"pixelhearth": dict(self.registry["pixelhearth"], token=str(self.dir / "tok" / "t.json"))}
        secret = self.dir / "secret.json"
        secret.write_text("{}")
        svc = FakeService(mine_items=found)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = login.main(["--channel", "pixelhearth"], registry=reg, flow=lambda s, scopes: self.Creds(),
                            build=lambda c: svc, secret=secret)
        return rc, out.getvalue(), err.getvalue(), Path(reg["pixelhearth"]["token"])

    def test_wrong_channel_writes_no_token_and_exits_3(self):
        rc, out, err, tp = self.run_login([{"id": PL, "snippet": {"title": "Purplelink"}}])
        self.assertEqual(rc, 3)
        self.assertFalse(tp.exists())
        self.assertFalse(tp.parent.exists())
        self.assertIn(PL, err)
        self.assertIn(f"choose the Pixel Hearth channel ({PH})", out)

    def test_matching_channel_writes_a_600_token(self):
        rc, out, _, tp = self.run_login([{"id": PH, "snippet": {"title": "Pixel Hearth"}}])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(tp.read_text()), {"refresh_token": "r"})
        self.assertEqual(oct(tp.stat().st_mode & 0o777), "0o600")
        self.assertEqual([p.name for p in tp.parent.iterdir()], ["t.json"])   # no temp file left
        self.assertIn("success", out)

    def test_two_channels_write_nothing(self):
        rc, _, _, tp = self.run_login([{"id": PH, "snippet": {"title": "a"}}, {"id": PL, "snippet": {"title": "b"}}])
        self.assertEqual(rc, 3)
        self.assertFalse(tp.exists())

    def test_a_wrong_login_leaves_an_existing_token_alone(self):
        reg = {"pixelhearth": dict(self.registry["pixelhearth"], token=str(self.dir / "t.json"))}
        (self.dir / "t.json").write_text("OLD")
        rc, _, _, tp = self.run_login([{"id": PL, "snippet": {"title": "Purplelink"}}], registry=reg)
        self.assertEqual(rc, 3)
        self.assertEqual(tp.read_text(), "OLD")


class StudioScript(unittest.TestCase):
    real_ph = g.load_registry()["pixelhearth"]["id"]

    def run_studio(self, *args):
        stub = tempfile.TemporaryDirectory()
        self.addCleanup(stub.cleanup)
        (Path(stub.name) / "websocket.py").write_text("")   # cdp_tab imports it; CI does not have it
        env = dict(os.environ, PYTHONPATH=stub.name)
        return subprocess.run([sys.executable, str(SCRIPTS / "yt-upload.py"), "nofile.mp4", "--title", "t", *args],
                              capture_output=True, text=True, env=env, timeout=60)

    def test_non_purplelink_channel_is_refused(self):
        for cid in (PH, OTHER, self.real_ph):
            r = self.run_studio("--channel", cid, "--dry-run")
            self.assertEqual(r.returncode, 3, r.stderr)
            self.assertIn("Studio uploads are Purplelink-only; use yt-api-upload.py for other channels", r.stderr)

    def test_purplelink_channel_passes_the_guard(self):
        r = self.run_studio("--channel", PL_REAL, "--dry-run")   # passes the guard, then stops at the missing file
        self.assertEqual(r.returncode, 1)
        self.assertIn("no such file", r.stderr)

    def test_the_pathname_check_is_still_there(self):
        self.assertIn('f"/channel/{a.channel}/" not in (on or "")', (SCRIPTS / "yt-upload.py").read_text())


if __name__ == "__main__":
    unittest.main()
