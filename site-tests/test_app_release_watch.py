"""scripts/app-release-watch.py (Ben, 2026-10-25): publish an app's prepared YouTube videos when the app is live.

Everything is faked: App Store Connect, the store page, the YouTube API, yt-abtest.py and the notifier are injected, and
the state, the lock, the PAUSE file and the release.json files live in a temporary directory. No test touches the
network, a real video, Chrome or the real state under ~/.purplelink."""
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import yt_guard as g  # noqa: E402

spec = importlib.util.spec_from_file_location("arw", ROOT / "scripts" / "app-release-watch.py")
arw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(arw)

PL = "UCUv28P5SUzT4RLQOmi3EK8w"
OTHER = "UC" + "x" * 22
REG = {"purplelink": {"id": PL, "title": "Purplelink", "token": "~/nope.json", "kinds": ["howto"],
                      "default_category": "28", "confirmed": True}}
PH = "App Store link: ADD BEFORE PUBLISHING"
LONG_DESC = f"Long text.\n\n{PH}\nPrivacy: https://purplelink.llc/x/\n\n#tag"
SHORT_DESC = "Short text.\n\nFull how-to: LINK THE LONG VIDEO WHEN BOTH ARE PUBLIC\n\n#tag #shorts"
LINK = "https://apps.apple.com/app/id111"


def asc_version(state, platform="IOS", version="1.0"):
    return {"version": version, "platform": platform, "state": state}


class FakeAsc:
    def __init__(self, by_app=None, error=None):
        self.by_app, self.error, self.calls = by_app or {}, error, []

    def versions(self, app_id):
        self.calls.append(app_id)
        if self.error:
            raise arw.StepError(self.error)
        return self.by_app.get(app_id, [])


class FakeYouTube:
    """Just enough of the youtube v3 client: channels.list, videos.list, videos.update. Records every write."""

    def __init__(self, videos, mine=PL):
        self.videos_by_id, self.writes, self.mine = videos, [], mine
        self.update_fails = False

    def channels(self):
        outer = self

        class C:
            def list(self, **kw):
                return type("E", (), {"execute": lambda s: {"items": [{"id": outer.mine, "snippet": {"title": "T"}}]}})()
        return C()

    def videos(self):
        outer = self

        class V:
            def list(self, part, id):
                items = [outer.videos_by_id[i] for i in id.split(",") if i in outer.videos_by_id]
                return type("E", (), {"execute": lambda s: {"items": items}})()

            def update(self, part, body):
                def run():
                    outer.writes.append((part, body))
                    if outer.update_fails:
                        return {}
                    v = outer.videos_by_id[body["id"]]
                    if part == "snippet":
                        v["snippet"].update(body["snippet"])
                    else:
                        v["status"].update(body["status"])
                    return {}
                return type("E", (), {"execute": lambda s: run()})()
        return V()


def video(vid, desc, privacy="private", channel=PL, title="A title"):
    return {"id": vid, "snippet": {"channelId": channel, "title": title, "description": desc, "categoryId": "28"},
            "status": {"privacyStatus": privacy, "uploadStatus": "processed", "selfDeclaredMadeForKids": False,
                       "embeddable": True, "license": "youtube"}}


class Env:
    """A temp world: state dir, videos dir with release.json files, fakes, and a run() that calls main()."""

    def __init__(self, test):
        self.tmp = Path(tempfile.mkdtemp())
        test.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.state_dir, self.videos = self.tmp / "state", self.tmp / "videos"
        self.changelog = self.tmp / "log_change.py"
        self.changelog.write_text("# fake")
        self.notes, self.cmds, self.cmd_rc, self.cmd_text = [], [], 0, ""
        self.asc = FakeAsc({"111": [asc_version("READY_FOR_SALE")]})
        self.status = 200
        self.yt = FakeYouTube({"LONGLONG001": video("LONGLONG001", LONG_DESC), "SHORTSHORT1": video("SHORTSHORT1", SHORT_DESC)})
        self.add_release("Alpha", "111", "LONGLONG001", "SHORTSHORT1")

    def add_release(self, app, asc_id, long_id, short_id, thumbs=True, extra=None):
        d = self.videos / app.lower().replace(" ", "-")
        d.mkdir(parents=True, exist_ok=True)
        names = []
        for n in "ABC":
            (d / f"thumb-{n}.jpg").write_bytes(b"jpg")
            names.append(f"thumb-{n}.jpg")
        data = {"app": app, "ascAppId": asc_id, "descriptionPlaceholder": PH,
                "long": {"id": long_id, "thumbs": names if thumbs else names[:2]}, "short": {"id": short_id}}
        data.update(extra or {})
        (d / "release.json").write_text(json.dumps(data))
        return d

    def run_cmd(self, cmd, env=None, timeout=0):
        self.cmds.append((cmd, env))
        if cmd[1].endswith("yt-abtest.py") and cmd[2] == "start" and self.cmd_rc == 0:
            pass
        if "status" in cmd and cmd[1].endswith("yt-abtest.py"):
            return 0, self.cmd_text
        return self.cmd_rc, self.cmd_text

    def run(self, *args, factory=None):
        out = io.StringIO()
        base = ["--videos-dir", str(self.videos), "--state-dir", str(self.state_dir), "--changelog", str(self.changelog),
                "--asc-env", str(self.tmp / "no.env")]
        rc = arw.main(list(args) + base, asc=self.asc, service_factory=factory or (lambda ch: self.yt),
                      status_fn=lambda url: self.status, run_cmd=self.run_cmd, notify=self.notes.append,
                      registry=REG, out=lambda m: out.write(m + "\n"))
        self.output = out.getvalue()
        return rc

    def state(self):
        return json.loads((self.state_dir / "state.json").read_text())


class PureHelpers(unittest.TestCase):
    def test_description_replaces_placeholder_and_is_idempotent(self):
        new = arw.new_description(LONG_DESC, PH, LINK)
        self.assertIn(LINK, new)
        self.assertNotIn("ADD BEFORE", new)
        self.assertEqual(arw.new_description(new, PH, LINK), new)

    def test_short_gets_full_video_line_replacing_the_stub(self):
        new = arw.new_description(SHORT_DESC, PH, LINK, "https://youtu.be/LONGLONG001", "Alpha")
        self.assertIn("Full video: https://youtu.be/LONGLONG001", new)
        self.assertNotIn("LINK THE LONG VIDEO", new)
        self.assertIn(f"Alpha on the App Store: {LINK}", new)
        self.assertTrue(new.rstrip().endswith("#tag #shorts"))
        self.assertEqual(arw.new_description(new, PH, LINK, "https://youtu.be/LONGLONG001", "Alpha"), new)

    def test_short_without_a_stub_gets_a_full_video_line_after_the_link(self):
        new = arw.new_description("Text.\n\n#a #b", PH, LINK, "https://youtu.be/LONGLONG001", "Alpha")
        lines = new.split("\n")
        self.assertEqual(lines[lines.index(f"Alpha on the App Store: {LINK}") + 1], "Full video: https://youtu.be/LONGLONG001")

    def test_description_limits(self):
        with self.assertRaises(arw.StepError):
            arw.new_description("x" * 4990, PH, LINK)
        with self.assertRaises(arw.StepError):
            arw.new_description(f"a <b>\n{PH}", PH, LINK)

    def test_live_means_ready_for_sale_on_ios(self):
        self.assertIsNone(arw.live_version([asc_version("PREPARE_FOR_SUBMISSION"), asc_version("WAITING_FOR_REVIEW")]))
        self.assertIsNone(arw.live_version([asc_version("PENDING_DEVELOPER_RELEASE")]))
        self.assertIsNone(arw.live_version([asc_version("READY_FOR_SALE", platform="MAC_OS")]))
        self.assertEqual(arw.live_version([asc_version("REJECTED"), asc_version("READY_FOR_SALE", version="1.1")])["version"], "1.1")

    def test_store_url(self):
        self.assertEqual(arw.store_url("6824584515"), "https://apps.apple.com/app/id6824584515")

    def test_env_file_and_home_expansion(self):
        p = Path(tempfile.mkdtemp()) / "x.env"
        p.write_text('# c\nASC_KEY_ID=ABC\nexport ASC_ISSUER_ID="iss"\nASC_KEY_PATH=$HOME/k/AuthKey.p8\n')
        env = arw.parse_env_file(p)
        self.assertEqual(env["ASC_KEY_ID"], "ABC")
        self.assertEqual(env["ASC_ISSUER_ID"], "iss")
        self.assertEqual(arw.expand_home(env["ASC_KEY_PATH"]), Path.home() / "k" / "AuthKey.p8")
        self.assertEqual(arw.expand_home("${HOME}/a"), Path.home() / "a")

    def test_jwt_is_es256_with_the_right_claims(self):
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import ec
            from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
        except ImportError:
            self.skipTest("cryptography not installed")
        import base64
        key = ec.generate_private_key(ec.SECP256R1())
        pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        tok = arw.es256_jwt(pem, "KID123", "ISSUER", 1_700_000_000)
        h, p, s = tok.split(".")
        pad = lambda x: x + "=" * (-len(x) % 4)
        header, payload = json.loads(base64.urlsafe_b64decode(pad(h))), json.loads(base64.urlsafe_b64decode(pad(p)))
        self.assertEqual(header, {"alg": "ES256", "kid": "KID123", "typ": "JWT"})
        self.assertEqual((payload["iss"], payload["aud"], payload["exp"] - payload["iat"]), ("ISSUER", "appstoreconnect-v1", 600))
        raw = base64.urlsafe_b64decode(pad(s))
        self.assertEqual(len(raw), 64)
        key.public_key().verify(encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big")),
                                f"{h}.{p}".encode(), ec.ECDSA(hashes.SHA256()))

    def test_asc_client_never_leaks_the_token_in_errors(self):
        import urllib.error

        def opener(req, timeout=0):
            raise urllib.error.HTTPError(req.full_url, 401, "no", {}, io.BytesIO(b'{"errors":[{"title":"NOT_AUTHORIZED"}]}'))
        c = arw.AscClient(Path("/nonexistent"), opener=opener)
        c._token, c._exp = "SECRET-TOKEN", 1e18
        with self.assertRaises(arw.StepError) as cm:
            c.versions("1")
        self.assertIn("401", str(cm.exception))
        self.assertNotIn("SECRET-TOKEN", str(cm.exception))

    def test_make_public_refuses_without_live_proof(self):
        v = video("V", "d")
        svc = FakeYouTube({"V": v})
        for flag in (False, None, "yes", 1):
            with self.assertRaises(g.ChannelGuardError):
                arw.make_public(svc, REG["purplelink"], "V", v, flag)
        self.assertEqual(svc.writes, [])
        self.assertEqual(v["status"]["privacyStatus"], "private")


class Releases(unittest.TestCase):
    def test_a_third_app_is_just_another_file(self):
        e = Env(self)
        e.add_release("haea", "222", "haeaLONG001", "haeaSHORT01")
        e.add_release("Circled Hoops", "6826945896", "HOOPLONG001", "HOOPSHORT01")
        good, bad = arw.find_releases(e.videos)
        self.assertEqual(sorted(r["app"] for r in good), ["Alpha", "Circled Hoops", "haea"])
        self.assertEqual(bad, [])

    def test_incomplete_files_are_ignored_not_guessed(self):
        e = Env(self)
        e.add_release("NoThumbs", "333", "NOTHUMBS001", "NOTHUMBS002", thumbs=False)
        e.add_release("BadId", "abc", "BADIDLONG01", "BADIDSHORT1")
        e.add_release("Dup", "111", "DUPLONG0001", "DUPSHORT001")
        d = e.videos / "half"
        d.mkdir()
        (d / "release.json").write_text('{"app": "Half"')
        good, bad = arw.find_releases(e.videos)
        self.assertEqual([r["app"] for r in good], ["Alpha"])
        self.assertEqual(len(bad), 4)
        self.assertTrue(any("three images" in why for _, why in bad))
        self.assertTrue(any("duplicates" in why for _, why in bad))


class Run(unittest.TestCase):
    def test_not_live_changes_nothing(self):
        e = Env(self)
        e.asc.by_app["111"] = [asc_version("PREPARE_FOR_SUBMISSION"), asc_version("WAITING_FOR_REVIEW", version="1.1")]
        self.assertEqual(e.run(), 0)
        self.assertEqual(e.yt.writes, [])
        self.assertEqual(e.cmds, [])
        self.assertEqual(e.notes, [])
        self.assertFalse(e.state()["apps"]["Alpha"]["released"])
        self.assertIn("not live", e.output)

    def test_live_in_connect_but_store_page_not_200_changes_nothing_and_counts_a_failure(self):
        e = Env(self)
        e.status = 404
        self.assertEqual(e.run(), 1)
        self.assertEqual(e.yt.writes, [])
        self.assertEqual(e.cmds, [])
        self.assertEqual(e.state()["apps"]["Alpha"]["failures"], 1)

    def test_happy_path_publishes_in_order_and_runs_only_once(self):
        e = Env(self)
        self.assertEqual(e.run(), 0, e.output)
        # both descriptions, then long public, then short public
        self.assertEqual([(p, b["id"]) for p, b in e.yt.writes],
                         [("snippet", "LONGLONG001"), ("snippet", "SHORTSHORT1"),
                          ("status", "LONGLONG001"), ("status", "SHORTSHORT1")])
        long_v, short_v = e.yt.videos_by_id["LONGLONG001"], e.yt.videos_by_id["SHORTSHORT1"]
        self.assertIn(LINK, long_v["snippet"]["description"])
        self.assertNotIn("ADD BEFORE", long_v["snippet"]["description"])
        self.assertIn(LINK, short_v["snippet"]["description"])
        self.assertIn("Full video: https://youtu.be/LONGLONG001", short_v["snippet"]["description"])
        self.assertEqual(long_v["status"]["privacyStatus"], "public")
        self.assertEqual(short_v["status"]["privacyStatus"], "public")
        # the rest of the status survives the update
        self.assertTrue(long_v["status"]["embeddable"])
        # the thumbnail test starts on the long video with A, B, C, writing to the watcher's own log
        starts = [c for c, _ in e.cmds if "yt-abtest.py" in c[1] and c[2] == "start"]
        self.assertEqual(len(starts), 1)
        self.assertEqual(starts[0][3], "LONGLONG001")
        self.assertEqual([Path(x).name for x in starts[0][4:]], ["thumb-A.jpg", "thumb-B.jpg", "thumb-C.jpg"])
        env = [en for c, en in e.cmds if c[2] == "start"][0]
        self.assertTrue(env["YT_ABTEST_LOG"].startswith(str(e.state_dir)))
        # change log and hub ran; one notification; state says released
        self.assertTrue(any(c[2] == "add" and "--area" in c for c, _ in e.cmds))
        self.assertTrue(any(c[1].endswith("hub.py") and c[2] == "import" for c, _ in e.cmds))
        self.assertEqual(len(e.notes), 1)
        self.assertIn("Alpha", e.notes[0])
        st = e.state()["apps"]["Alpha"]
        self.assertTrue(st["released"])
        self.assertEqual({p["video"] for p in st["placements"]}, {"LONGLONG001", "SHORTSHORT1"})
        # a second run touches nothing
        n_writes, n_cmds, n_asc = len(e.yt.writes), len(e.cmds), len(e.asc.calls)
        self.assertEqual(e.run(), 0)
        self.assertEqual((len(e.yt.writes), len(e.cmds), len(e.notes)), (n_writes, n_cmds, 1))
        self.assertEqual(len(e.asc.calls), n_asc)

    def test_missing_placeholder_in_long_adds_nothing_public_and_retries(self):
        e = Env(self)
        e.yt.videos_by_id["LONGLONG001"]["snippet"]["description"] = "<broken>"
        self.assertEqual(e.run(), 1)
        self.assertEqual(e.yt.writes, [])
        self.assertEqual(e.cmds, [])
        self.assertEqual(e.state()["apps"]["Alpha"]["failures"], 1)
        # fixed text: the next run resumes and finishes
        e.yt.videos_by_id["LONGLONG001"]["snippet"]["description"] = LONG_DESC
        self.assertEqual(e.run(), 0, e.output)
        self.assertTrue(e.state()["apps"]["Alpha"]["released"])
        self.assertEqual(e.state()["apps"]["Alpha"]["failures"], 0)

    def test_description_failure_never_leads_to_public(self):
        e = Env(self)
        e.yt.update_fails = True            # YouTube accepts the call but keeps the old text
        self.assertEqual(e.run(), 1)
        for v in e.yt.videos_by_id.values():
            self.assertEqual(v["status"]["privacyStatus"], "private")
        self.assertFalse([w for w in e.yt.writes if w[0] == "status"])

    def test_abtest_failure_is_retried_without_redoing_the_earlier_steps(self):
        e = Env(self)
        e.cmd_rc, e.cmd_text = 1, "Studio does not show a running test"
        self.assertEqual(e.run(), 1)
        st = e.state()["apps"]["Alpha"]
        self.assertFalse(st["released"])
        self.assertTrue(st["steps"]["public:short"]["done"])
        writes = len(e.yt.writes)
        e.cmd_rc, e.cmd_text = 0, ""
        self.assertEqual(e.run(), 0, e.output)
        self.assertEqual(len(e.yt.writes), writes)          # no second round of YouTube writes
        self.assertTrue(e.state()["apps"]["Alpha"]["released"])

    def test_abtest_retry_does_not_start_a_second_test_when_one_is_running(self):
        e = Env(self)
        e.cmd_rc, e.cmd_text = 1, "boom"
        e.run()
        e.cmd_text = "open LONGLONG001: Running... custom_1"
        e.cmd_rc = 1                                          # a second start would fail, but must not be tried
        e.run()
        starts = [c for c, _ in e.cmds if c[2] == "start"]
        self.assertEqual(len(starts), 1)
        self.assertTrue(e.state()["apps"]["Alpha"]["steps"]["abtest"]["done"])

    def test_best_effort_steps_give_up_after_three_tries_and_say_so(self):
        e = Env(self)
        e.changelog.unlink()                                   # the change-log tool is missing
        for _ in range(3):
            e.run()
        st = e.state()["apps"]["Alpha"]
        self.assertTrue(st["released"])
        self.assertIn("changelog", e.notes[-1])
        self.assertEqual(len(e.notes), 1)

    def test_failure_notification_after_three_in_a_row_once(self):
        e = Env(self)
        e.asc.error = "App Store Connect unreachable (URLError)"
        for _ in range(2):
            e.run()
        self.assertEqual(e.notes, [])
        e.run()
        self.assertEqual(len(e.notes), 1)
        self.assertIn("3 runs in a row", e.notes[0])
        e.run()
        self.assertEqual(len(e.notes), 1)
        self.assertEqual(e.state()["apps"]["Alpha"]["failures"], 4)
        e.asc.error = None                                    # recovery resets the count
        e.asc.by_app["111"] = [asc_version("PREPARE_FOR_SUBMISSION")]
        e.run()
        self.assertEqual(e.state()["apps"]["Alpha"]["failures"], 0)

    def test_a_video_on_another_channel_is_never_touched(self):
        e = Env(self)
        e.yt.videos_by_id["SHORTSHORT1"] = video("SHORTSHORT1", SHORT_DESC, channel=OTHER)
        self.assertEqual(e.run(), 1)
        self.assertEqual([w for w in e.yt.writes if w[1]["id"] == "SHORTSHORT1"], [])
        self.assertEqual(e.yt.videos_by_id["SHORTSHORT1"]["status"]["privacyStatus"], "private")
        self.assertFalse([w for w in e.yt.writes if w[0] == "status"])

    def test_a_token_for_another_channel_is_refused_before_any_write(self):
        e = Env(self)
        e.yt.mine = OTHER
        self.assertEqual(e.run(), 1)
        self.assertEqual(e.yt.writes, [])
        self.assertEqual(e.cmds, [])

    def test_unconfirmed_channel_is_refused(self):
        e = Env(self)
        reg = {"purplelink": dict(REG["purplelink"], confirmed=False)}
        out = io.StringIO()
        base = ["--videos-dir", str(e.videos), "--state-dir", str(e.state_dir)]
        rc = arw.main(base, asc=e.asc, service_factory=lambda ch: e.yt, status_fn=lambda u: 200, run_cmd=e.run_cmd,
                      notify=e.notes.append, registry=reg, out=lambda m: out.write(m + "\n"))
        self.assertEqual(rc, 1)
        self.assertEqual(e.yt.writes, [])

    def test_two_apps_are_independent(self):
        e = Env(self)
        e.add_release("Beta", "222", "BETALONG001", "BETASHORT01")
        e.yt.videos_by_id.update({"BETALONG001": video("BETALONG001", LONG_DESC.replace("1", "2")),
                                  "BETASHORT01": video("BETASHORT01", SHORT_DESC)})
        e.asc.by_app["222"] = [asc_version("IN_REVIEW")]
        self.assertEqual(e.run(), 0, e.output)
        self.assertTrue(e.state()["apps"]["Alpha"]["released"])
        self.assertFalse(e.state()["apps"]["Beta"]["released"])
        self.assertEqual(e.yt.videos_by_id["BETALONG001"]["status"]["privacyStatus"], "private")


class Safety(unittest.TestCase):
    def test_pause_file_stops_everything(self):
        e = Env(self)
        e.state_dir.mkdir(parents=True)
        (e.state_dir / "PAUSE").write_text("")
        self.assertEqual(e.run(), 0)
        self.assertEqual(e.asc.calls, [])
        self.assertEqual((e.yt.writes, e.cmds, e.notes), ([], [], []))
        self.assertIn("paused", e.output)

    def test_lock_held_skips_the_run(self):
        e = Env(self)
        fd = arw.acquire_lock(e.state_dir / "run.lock")
        self.assertIsNotNone(fd)
        try:
            self.assertEqual(e.run(), 0)
            self.assertEqual(e.asc.calls, [])
            self.assertIn("lock", e.output)
        finally:
            os.close(fd)
        self.assertEqual(e.run(), 0)
        self.assertTrue(e.asc.calls)

    def test_dry_run_changes_nothing_and_shows_the_plan(self):
        e = Env(self)
        self.assertEqual(e.run("--dry-run"), 0, e.output)
        self.assertEqual(e.yt.writes, [])
        self.assertEqual(e.cmds, [])
        self.assertEqual(e.notes, [])
        self.assertFalse((e.state_dir / "state.json").exists())
        self.assertIn(LINK, e.output)
        self.assertIn("would change private to public", e.output)
        self.assertIn("yt-abtest.py start LONGLONG001", e.output)
        self.assertEqual(e.yt.videos_by_id["LONGLONG001"]["status"]["privacyStatus"], "private")

    def test_dry_run_with_assume_live_shows_the_plan_for_an_app_that_is_not_live(self):
        e = Env(self)
        e.asc.by_app["111"] = [asc_version("PREPARE_FOR_SUBMISSION")]
        e.run("--dry-run", "--assume-live")
        self.assertIn("would change private to public", e.output)
        self.assertEqual((e.yt.writes, e.cmds), ([], []))
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            e.run("--assume-live")

    def test_dry_run_still_runs_while_paused_and_says_so(self):
        e = Env(self)
        e.state_dir.mkdir(parents=True)
        (e.state_dir / "PAUSE").write_text("")
        e.run("--dry-run")
        self.assertIn("PAUSE is on", e.output)

    def test_check_lists_state_and_privacy_and_writes_nothing(self):
        e = Env(self)
        self.assertEqual(e.run("--check"), 0)
        self.assertIn("Alpha (ascAppId 111)", e.output)
        self.assertIn("LIVE", e.output)
        self.assertIn("HTTP 200", e.output)
        self.assertIn("LONGLONG001: private  placeholder still in description", e.output)
        self.assertIn("SHORTSHORT1: private", e.output)
        self.assertEqual((e.yt.writes, e.cmds, e.notes), ([], [], []))
        self.assertFalse((e.state_dir / "state.json").exists())

    def test_check_reports_a_video_on_the_wrong_channel(self):
        e = Env(self)
        e.yt.videos_by_id["LONGLONG001"] = video("LONGLONG001", LONG_DESC, channel=OTHER)
        e.run("--check")
        self.assertIn("WRONG CHANNEL", e.output)

    def test_unknown_app_filter(self):
        e = Env(self)
        self.assertEqual(e.run("--app", "Nope"), 2)

    def test_no_step_sends_keystrokes(self):
        import ast
        tree = ast.parse((ROOT / "scripts" / "app-release-watch.py").read_text())
        for node in ast.walk(tree):          # docstrings may talk about keystrokes; code may not do them
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) and ast.get_docstring(node):
                node.body = node.body[1:] or [ast.Pass()]
        code = ast.unparse(tree)
        for needle in ("System Events", "keystroke", "key code", "pyautogui", "cliclick", "Input.dispatchKeyEvent"):
            self.assertNotIn(needle, code)

    def test_shell_wrapper_follows_the_house_rules(self):
        sh = (ROOT / "scripts" / "app-release-watch.sh").read_text()
        self.assertIn("\nset -u\n", sh)
        self.assertIn("repo-ro.sh", sh)
        self.assertNotIn("rm ", sh)

    def test_plist_runs_hourly_at_minute_20_through_the_wrapper(self):
        import plistlib
        pl = plistlib.loads((ROOT / "scripts" / "com.purplelink.app-release-watch.plist").read_bytes())
        self.assertEqual(pl["Label"], "com.purplelink.app-release-watch")
        self.assertEqual(pl["StartCalendarInterval"], {"Minute": 20})
        self.assertTrue(pl["ProgramArguments"][-1].endswith("/.purplelink/bin/app-release-watch.sh"))


class HubSource(unittest.TestCase):
    def test_hub_reads_the_launch_videos_from_state(self):
        tmp = Path(tempfile.mkdtemp())
        state = tmp / "state.json"
        state.write_text(json.dumps({"apps": {"Circled Hoops": {"released": True, "storeUrl": "https://apps.apple.com/app/id1",
                                      "placements": [{"video": "HOOPLONG001", "kind": "long", "date": "2026-11-01"},
                                                     {"video": "HOOPSHORT01", "kind": "short", "date": "2026-11-01"}]}}}))
        old = {k: os.environ.get(k) for k in ("PURPLELINK_APP_RELEASE_STATE", "PURPLELINK_HUB")}
        os.environ["PURPLELINK_APP_RELEASE_STATE"] = str(state)
        os.environ["PURPLELINK_HUB"] = str(tmp / "hub")
        try:
            hs = importlib.util.spec_from_file_location("hub_under_test", ROOT / "scripts" / "hub" / "hub.py")
            hub = importlib.util.module_from_spec(hs)
            hs.loader.exec_module(hub)
            rows = hub.from_app_releases(hub.paths())
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        self.assertEqual({r["id"] for r in rows}, {"release-video:HOOPLONG001", "release-video:HOOPSHORT01"})
        short = next(r for r in rows if r["id"].endswith("SHORT01"))
        self.assertEqual((short["channel"], short["status"], short["_assets"]), ("youtube", "live", ["circled-hoops"]))
        self.assertTrue(short["url"].startswith("https://www.youtube.com/shorts/"))


if __name__ == "__main__":
    unittest.main()
