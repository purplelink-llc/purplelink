"""scripts/yt-playlists.py: playlists are created and filled on the right channel only, by exact title, without duplicates, and never against YouTube in a test.
Fake service objects only: no network, no OAuth, no google libraries needed."""
import importlib.util
import json
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


pl = load("yt_playlists", "yt-playlists.py")

PH = "UC" + "h" * 22      # synthetic ids
PL = "UC" + "p" * 22
OTHER = "UC" + "z" * 22


class Exec:
    def __init__(self, fn):
        self.fn = fn

    def execute(self):
        return self.fn()


class FakeService:
    """A channel with some uploads and playlists. Lists are paged two at a time so the paging code is exercised."""

    def __init__(self, mine=None, uploads=None, playlists=None, items=None, new_channel=PH, page=2):
        self.mine = [{"id": PH, "snippet": {"title": "Pixel Hearth"}}] if mine is None else mine
        self.uploads = uploads if uploads is not None else [("VID_FIRE", "Christmas Fireplace 4K, Crackling Yule Log, 10 Hours, No Music"),
                                                            ("VID_CABIN", "Christmas Cabin Ambience 4K with Christmas Chiptune Music, 10 Hours"),
                                                            ("VID_DARK", "Brown Noise with Snowy Cabin, 10 Hours, Black Screen")]
        self.rows = playlists if playlists is not None else {}             # id -> {"title", "description", "privacy", "channel"}
        self.items = items if items is not None else {}                    # playlist id -> [video ids]
        self.new_channel = new_channel
        self.page = page
        self.calls = []
        self.writes = []
        self.n = 0
        self.other_videos = {"VID_OTHER": OTHER}

    def paged(self, rows, kw):
        start = int(kw.get("pageToken") or 0)
        out = {"items": rows[start:start + self.page]}
        if start + self.page < len(rows):
            out["nextPageToken"] = str(start + self.page)
        return out

    def channels(self):
        svc = self

        class C:
            def list(self, **kw):
                svc.calls.append(("channels.list", kw))
                if kw.get("part") == "contentDetails":
                    return Exec(lambda: {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UPLOADS"}}}]})
                return Exec(lambda: {"items": svc.mine})
        return C()

    def playlistItems(self):
        svc = self

        class P:
            def list(self, **kw):
                svc.calls.append(("playlistItems.list", kw))
                if kw["playlistId"] == "UPLOADS":
                    rows = [{"snippet": {"title": t, "resourceId": {"videoId": v}}} for v, t in svc.uploads]
                else:
                    rows = [{"snippet": {"resourceId": {"videoId": v}}} for v in svc.items.get(kw["playlistId"], [])]
                return Exec(lambda: svc.paged(rows, kw))

            def insert(self, **kw):
                svc.calls.append(("playlistItems.insert", kw))
                svc.writes.append(("playlistItems.insert", kw))
                sn = kw["body"]["snippet"]
                svc.items.setdefault(sn["playlistId"], []).append(sn["resourceId"]["videoId"])
                return Exec(lambda: {})
        return P()

    def playlists(self):
        svc = self

        class PL_:
            def list(self, **kw):
                svc.calls.append(("playlists.list", kw))
                rows = [{"id": i, "snippet": {"title": p["title"], "description": p["description"], "channelId": p["channel"]},
                         "status": {"privacyStatus": p["privacy"]}} for i, p in svc.rows.items() if "id" not in kw or kw["id"] == i]
                return Exec(lambda: svc.paged(rows, kw) if "id" not in kw else {"items": rows})

            def insert(self, **kw):
                svc.calls.append(("playlists.insert", kw))
                svc.writes.append(("playlists.insert", kw))
                svc.n += 1
                pid = f"PL{svc.n}"
                svc.rows[pid] = {"title": kw["body"]["snippet"]["title"], "description": kw["body"]["snippet"]["description"],
                                      "privacy": kw["body"]["status"]["privacyStatus"], "channel": svc.new_channel}
                return Exec(lambda: {"id": pid})

            def update(self, **kw):
                svc.calls.append(("playlists.update", kw))
                svc.writes.append(("playlists.update", kw))
                b = kw["body"]
                p = svc.rows[b["id"]]
                if "snippet" in b:
                    p["title"], p["description"] = b["snippet"]["title"], b["snippet"].get("description", p["description"])
                p["privacy"] = b["status"]["privacyStatus"]
                return Exec(lambda: {})
        return PL_()

    def videos(self):
        svc = self

        class V:
            def list(self, **kw):
                svc.calls.append(("videos.list", kw))
                ch = svc.other_videos.get(kw["id"], PH)
                return Exec(lambda: {"items": [{"id": kw["id"], "snippet": {"channelId": ch}}]})
        return V()


PLAN = {"playlists": [
    {"title": "Christmas Fireplace 4K", "description": "Pixel-art Christmas fireplaces in 4K.",
     "videos": [{"slug": "christmas-fireplace-4k-10h", "title": "Christmas Fireplace 4K, Crackling Yule Log, 10 Hours, No Music"}]},
    {"title": "Cozy Christmas Ambience", "description": "Cabins and study rooms.",
     "videos": [{"slug": "christmas-cabin-chiptune-4k-10h", "title": "Christmas Cabin Ambience 4K with Christmas Chiptune Music, 10 Hours"},
                {"slug": "christmas-study-lofi-4k-3h", "title": "Christmas Lofi Study Music, Cozy Study Room 4K, 3 Hours"}]},
    {"title": "Black Screen Sleep Sounds", "description": "Sounds over a screen that goes black.",
     "videos": [{"slug": "snowy-cabin-brown-4k-10h-black-screen", "title": "Brown Noise with Snowy Cabin, 10 Hours, Black Screen"}]},
]}


class PlaylistCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.registry = {
            "purplelink": {"id": PL, "title": "Purplelink", "token": "~/.config/purplelink/yt_token_purplelink.json",
                           "kinds": ["howto", "tutorial"], "default_category": "28", "confirmed": True},
            "pixelhearth": {"id": PH, "title": "Pixel Hearth", "token": "~/.config/purplelink/yt_token_pixelhearth.json",
                            "kinds": ["ambient", "photo-quiz"], "default_category": "10", "confirmed": True},
            "unconfirmed": {"id": OTHER, "title": "Unconfirmed", "token": "~/.config/purplelink/yt_token_u.json",
                            "kinds": ["ambient"], "default_category": "10", "confirmed": False}}
        self.notes = []

    def go(self, svc, plan=PLAN, channel="pixelhearth", kind="ambient", privacy=None, apply=True):
        return pl.run(plan, channel, kind, privacy, apply, registry=self.registry, service=svc, notify=self.notes.append,
                      lock_path=self.dir / "lock", sleep=lambda s: None)

    def kinds(self, svc):
        return [w[0] for w in svc.writes]

    # ---------------------------------------------------------------- what it does
    def test_dry_run_writes_nothing_and_says_what_it_would_do(self):
        svc = FakeService()
        rep = self.go(svc, apply=False)
        self.assertEqual(svc.writes, [])
        self.assertEqual(rep["channel"], "Pixel Hearth")
        self.assertEqual([a["action"] for a in rep["actions"]].count("create"), 3)
        self.assertEqual([a["action"] for a in rep["actions"]].count("add"), 0)         # nothing exists to add to yet; adds are listed once a playlist exists
        self.assertEqual(len(rep["missing"]), 1)                                        # the study video is not uploaded yet

    def test_apply_creates_private_first_reads_the_channel_back_and_adds_the_uploaded_videos(self):
        svc = FakeService()
        rep = self.go(svc)
        inserted = [w[1]["body"]["status"]["privacyStatus"] for w in svc.writes if w[0] == "playlists.insert"]
        self.assertEqual(inserted, ["private"] * 3)                                     # always created private
        self.assertEqual({p["title"]: p["privacy"] for p in svc.rows.values()},
                         {"Christmas Fireplace 4K": "private", "Cozy Christmas Ambience": "private", "Black Screen Sleep Sounds": "private"})
        by_title = {p["title"]: i for i, p in svc.rows.items()}
        self.assertEqual(svc.items[by_title["Christmas Fireplace 4K"]], ["VID_FIRE"])
        self.assertEqual(svc.items[by_title["Cozy Christmas Ambience"]], ["VID_CABIN"])
        self.assertEqual(rep["missing"][0]["slug"], "christmas-study-lofi-4k-3h")
        self.assertIn("playlists.list", [c[0] for c in svc.calls])                      # the channel was read back after each insert
        self.assertEqual(self.notes, [])

    def test_a_second_run_changes_nothing(self):
        svc = FakeService()
        self.go(svc)
        before = len(svc.writes)
        rep = self.go(svc)
        self.assertEqual(len(svc.writes), before)
        self.assertEqual(rep["actions"], [])
        self.assertEqual(len(svc.rows), 3)

    def test_a_video_uploaded_later_is_added_and_nothing_is_removed(self):
        svc = FakeService()
        self.go(svc)
        svc.uploads.insert(0, ("VID_STUDY", "Christmas Lofi Study Music, Cozy Study Room 4K, 3 Hours"))
        by_title = {p["title"]: i for i, p in svc.rows.items()}
        svc.items[by_title["Christmas Fireplace 4K"]].append("VID_KEEP")                # something Ben added by hand stays
        rep = self.go(svc)
        self.assertEqual([(a["action"], a["detail"]) for a in rep["actions"]], [("add", "VID_STUDY")])
        self.assertEqual(svc.items[by_title["Cozy Christmas Ambience"]], ["VID_CABIN", "VID_STUDY"])
        self.assertIn("VID_KEEP", svc.items[by_title["Christmas Fireplace 4K"]])
        self.assertNotIn("playlistItems.delete", [c[0] for c in svc.calls])

    def test_an_existing_playlist_is_matched_by_exact_title_and_gets_its_description_but_keeps_its_visibility(self):
        svc = FakeService(playlists={"PLX": {"title": "Christmas Fireplace 4K", "description": "old", "privacy": "public", "channel": PH}})
        rep = self.go(svc)
        self.assertEqual(len(svc.rows), 3)                                              # only the two missing playlists were created
        self.assertEqual(svc.rows["PLX"]["privacy"], "public")
        self.assertEqual(svc.rows["PLX"]["description"], "Pixel-art Christmas fireplaces in 4K.")
        self.assertIn(("update", "description"), [(a["action"], a["detail"]) for a in rep["actions"]])
        self.assertEqual(svc.items["PLX"], ["VID_FIRE"])

    def test_privacy_is_applied_to_new_playlists_after_the_channel_check_and_to_old_ones_only_when_asked(self):
        svc = FakeService(playlists={"PLX": {"title": "Christmas Fireplace 4K", "description": "Pixel-art Christmas fireplaces in 4K.", "privacy": "private", "channel": PH}})
        self.go(svc, privacy="public")
        self.assertEqual({p["privacy"] for p in svc.rows.values()}, {"public"})
        for pid in ("PL1", "PL2"):                                                      # each new playlist: inserted private, and only afterwards made public
            ins = next(i for i, w in enumerate(svc.writes) if w[0] == "playlists.insert" and w[1]["body"]["status"]["privacyStatus"] == "private"
                       and svc.rows[pid]["title"] == w[1]["body"]["snippet"]["title"])
            upd = next(i for i, w in enumerate(svc.writes) if w[0] == "playlists.update" and w[1]["body"]["id"] == pid)
            self.assertLess(ins, upd)
        svc2 = FakeService(playlists={"PLX": {"title": "Christmas Fireplace 4K", "description": "Pixel-art Christmas fireplaces in 4K.", "privacy": "public", "channel": PH}})
        self.go(svc2)
        self.assertEqual(svc2.rows["PLX"]["privacy"], "public")                         # no --privacy: left alone

    def test_a_playlist_with_no_uploaded_video_is_not_created(self):
        svc = FakeService(uploads=[])
        rep = self.go(svc)
        self.assertEqual(svc.writes, [])
        self.assertTrue(all(a["action"] == "skip" for a in rep["actions"]))

    def test_a_video_id_in_the_plan_must_be_on_the_channel(self):
        plan = {"playlists": [{"title": "Christmas Fireplace 4K", "description": "", "videos": [{"slug": "x", "title": "x", "video_id": "VID_OTHER"}]}]}
        with self.assertRaises(g.ChannelGuardError):
            self.go(FakeService(), plan)
        ok = {"playlists": [{"title": "Christmas Fireplace 4K", "description": "", "videos": [{"slug": "x", "title": "x", "video_id": "VID_FIRE"}]}]}
        svc = FakeService()
        self.go(svc, ok)
        self.assertEqual(next(iter(svc.items.values())), ["VID_FIRE"])

    # ---------------------------------------------------------------- the guards
    def test_a_playlist_that_lands_on_another_channel_is_set_private_and_the_run_fails(self):
        svc = FakeService(new_channel=OTHER)
        with self.assertRaises(g.ChannelGuardError):
            self.go(svc)
        self.assertEqual(self.kinds(svc).count("playlists.insert"), 1)                  # stopped at the first
        self.assertEqual(next(iter(svc.rows.values()))["privacy"], "private")
        self.assertEqual(self.kinds(svc).count("playlistItems.insert"), 0)
        self.assertEqual(len(self.notes), 1)

    def test_the_token_must_belong_to_the_registry_channel_before_any_write(self):
        svc = FakeService(mine=[{"id": PL, "snippet": {"title": "Purplelink"}}])
        with self.assertRaises(g.ChannelGuardError):
            self.go(svc)
        self.assertEqual(svc.writes, [])
        with self.assertRaises(g.ChannelGuardError):
            self.go(FakeService(mine=[]))
        with self.assertRaises(g.ChannelGuardError):
            self.go(FakeService(mine=[{"id": PH, "snippet": {}}, {"id": PL, "snippet": {}}]))

    def test_the_kind_and_the_registry_are_checked_before_any_api_call(self):
        svc = FakeService()
        with self.assertRaises(g.ChannelGuardError):
            self.go(svc, channel="purplelink")                                          # a Purplelink token cannot carry ambient
        with self.assertRaises(g.ChannelGuardError):
            self.go(svc, channel="unconfirmed")
        with self.assertRaises(g.ChannelGuardError):
            self.go(svc, channel="nope")
        with self.assertRaises(g.ChannelGuardError):
            self.go(svc, kind="howto")
        self.assertEqual(svc.calls, [])

    def test_a_playlist_listed_on_another_channel_stops_the_run(self):
        svc = FakeService(playlists={"PLZ": {"title": "Elsewhere", "description": "", "privacy": "public", "channel": OTHER}})
        with self.assertRaises(g.ChannelGuardError):
            self.go(svc)
        self.assertEqual(svc.writes, [])

    def test_bad_plans_and_bad_privacy_are_argument_errors(self):
        for bad in ({}, {"playlists": "x"}, {"playlists": [{"title": "", "videos": []}]}, {"playlists": [{"title": "a<b", "videos": []}]}):
            with self.assertRaises(g.UploadArgsError):
                self.go(FakeService(), bad)
        with self.assertRaises(g.UploadArgsError):
            self.go(FakeService(), privacy="everyone")

    def test_the_upload_lock_is_held_while_it_runs(self):
        lock = self.dir / "lock"
        svc = FakeService()
        self.go(svc)
        self.assertTrue(lock.exists())

    # ---------------------------------------------------------------- the command line
    def test_cli_is_a_dry_run_unless_apply_is_given_and_exit_codes_match_the_uploader(self):
        plan = self.dir / "plan.json"
        plan.write_text(json.dumps(PLAN))
        svc = FakeService()
        inj = dict(registry=self.registry, service=svc, notify=self.notes.append, lock_path=self.dir / "lock", sleep=lambda s: None)
        self.assertEqual(pl.main(["--plan", str(plan)], **inj), 0)
        self.assertEqual(svc.writes, [])
        self.assertEqual(pl.main(["--plan", str(plan), "--apply"], **inj), 0)
        self.assertEqual(len(svc.rows), 3)
        self.assertEqual(pl.main(["--plan", str(plan), "--channel", "purplelink"], **inj), 3)
        self.assertEqual(pl.main(["--plan", str(self.dir / "missing.json")], **inj), 2)
        bad = self.dir / "bad.json"
        bad.write_text("{}")
        self.assertEqual(pl.main(["--plan", str(bad)], **inj), 2)

    def test_quota_errors_exit_4(self):
        svc = FakeService()
        real = svc.playlists

        class Quota(Exception):
            pass

        class Api:
            def __init__(self, inner):
                self.inner = inner

            def list(self, **kw):
                return self.inner.list(**kw)

            def insert(self, **kw):
                raise Quota("quotaExceeded")
        svc.playlists = lambda: Api(real())
        plan = self.dir / "plan.json"
        plan.write_text(json.dumps(PLAN))
        inj = dict(registry=self.registry, service=svc, notify=self.notes.append, lock_path=self.dir / "lock", sleep=lambda s: None)
        self.assertEqual(pl.main(["--plan", str(plan), "--apply"], **inj), 4)


if __name__ == "__main__":
    unittest.main()
