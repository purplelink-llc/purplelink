"""scripts/contests/contests.py: the contest finder (docs/designs/contest-finder.md).

Offline: the fetcher is faked, and the ledger, briefs, queue, photo library and hub live in a temporary directory, so
no test touches the network, Ben's photo library or the real state under ~/.purplelink. The rights-flagger tests run
against a paraphrase of the Sony World Photography Awards 2027 clause 7 (fixtures/contests/creo-2027-clause7.txt),
the reference case: a hand-made shortlist had marked that licence "no rights grab"."""
import datetime as dt
import hashlib
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = Path(__file__).resolve().parent / "fixtures" / "contests"


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cf = load("contests", "scripts/contests/contests.py")
TODAY = dt.date(2026, 11, 2)
PROFILE = json.loads((ROOT / "scripts" / "contests" / "profile.json").read_text())


def flags_of(text):
    return {f["flag"]: f for f in cf.check_terms(text)["flags"]}


class Dedupe(unittest.TestCase):
    def test_editions_share_a_key(self):
        a = cf.norm_key("The 24th Annual Smithsonian Magazine Photo Contest")
        b = cf.norm_key("Smithsonian Magazine Photo Contest 2027")
        self.assertEqual(a, b)
        self.assertEqual(cf.norm_key("Wildlife Photographer of the Year 63"), cf.norm_key("Wildlife Photographer of the Year 62"))
        self.assertEqual(cf.norm_key("Monochrome Photography Awards 2026"), cf.norm_key("Monochrome Photography Award"))

    def test_different_contests_keep_different_keys(self):
        self.assertNotEqual(cf.norm_key("Sony World Photography Awards Youth"), cf.norm_key("Sony World Photography Awards Open"))

    def test_canonical_url_keeps_the_query(self):
        self.assertEqual(cf.canon_url("https://www.Example.com/rules/"), "example.com/rules")
        self.assertNotEqual(cf.canon_url("https://x.com/c?id=1"), cf.canon_url("https://x.com/c?id=2"))

    def test_match_by_id_name_or_url(self):
        recs = {"a": {"id": "a", "name": "Big Photo Contest 2026", "key": cf.norm_key("Big Photo Contest 2026"), "url": "https://big.org/rules"}}
        self.assertEqual(cf.match_record({"id": "a", "name": "x", "url": ""}, recs), ("a", "id"))
        self.assertEqual(cf.match_record({"id": "b", "name": "Big Photo Competition 2027", "url": ""}, recs), ("a", "name"))
        self.assertEqual(cf.match_record({"id": "c", "name": "Other", "url": "https://www.big.org/rules/"}, recs), ("a", "url"))
        self.assertEqual(cf.match_record({"id": "d", "name": "Other", "url": "https://other.org/"}, recs), (None, ""))

    def test_near_matches_are_reported_not_merged(self):
        recs = {"a": {"key": "river-photo-award-open", "url": "https://r.org/a"}, "b": {"key": "river-photo-award-opens", "url": "https://r.org/b"}}
        self.assertEqual(cf.possible_duplicates(recs), [("a", "b")])

    def test_registry_merge_dedupes_and_keeps_editions(self):
        led = {"contests": {}}
        src = {"contests": [{"id": "big", "name": "Big Photo Contest 2026", "url": "https://big.org/r", "edition": "2026"},
                            {"id": "big-dup", "name": "Big Photo Competition", "url": "https://elsewhere.org/"}]}
        st = cf.merge_registry(led, src, PROFILE, TODAY)
        self.assertEqual(list(led["contests"]), ["big"])
        self.assertEqual(st["possible_duplicates"], [("big", "big-dup")])
        led["contests"]["big"].update(status="rejected", queue_id="AQ-1")
        src["contests"][0]["edition"] = "2027"
        cf.merge_registry(led, src, PROFILE, TODAY)
        rec = led["contests"]["big"]
        self.assertEqual(rec["status"], "rejected", "a contest Ben rejected stays rejected in its next edition")
        self.assertEqual(rec["past"][0]["edition"], "2026")
        self.assertNotIn("queue_id", rec)

    def test_entered_contest_reopens_next_edition(self):
        led = {"contests": {}}
        src = {"contests": [{"id": "x", "name": "X Awards", "url": "https://x.org/", "edition": "2026"}]}
        cf.merge_registry(led, src, PROFILE, TODAY)
        led["contests"]["x"]["status"] = "entered"
        src["contests"][0]["edition"] = "2027"
        cf.merge_registry(led, src, PROFILE, TODAY)
        self.assertEqual(led["contests"]["x"]["status"], "open")
        self.assertEqual(led["contests"]["x"]["past"][0]["status"], "entered")

    def test_georgia_state_is_dropped_silently(self):
        led = {"contests": {}}
        src = {"contests": [{"id": "g", "name": "Startup pitch night", "organizer": "Georgia State University", "url": "https://x.org"},
                            {"id": "h", "name": "Pitch", "url": "https://entrepreneurship.gsu.edu/pitch"},
                            {"id": "ok", "name": "Pitch", "organizer": "Gsuite fans club", "url": "https://y.org"}]}
        st = cf.merge_registry(led, src, PROFILE, TODAY)
        self.assertEqual(st["blocked"], 2)
        self.assertEqual(list(led["contests"]), ["ok"], "word-boundary match: 'Gsuite' is not GSU")


class Deadlines(unittest.TestCase):
    def d(self, text):
        r = cf.parse_deadline(text, TODAY)
        return r and r["date"]

    def test_formats(self):
        self.assertEqual(self.d("Entry deadline: 2026-12-03."), "2026-12-03")
        self.assertEqual(self.d("The final deadline is December 1, 2026 at 23:59 PT."), "2026-12-01")
        self.assertEqual(self.d("Entries close 5 January 2027, 16:00 GMT."), "2027-01-05")
        self.assertEqual(self.d("Closing date: Dec. 1st 2026"), "2026-12-01")
        self.assertEqual(self.d("Deadline 1st Dec 2026"), "2026-12-01")
        self.assertEqual(self.d("Submissions due 25/02/2027."), "2027-02-25")

    def test_time_note_is_kept(self):
        r = cf.parse_deadline("The closing date for entries is 5 January 2027 at 16:00 GMT.", TODAY)
        self.assertEqual(r["note"], "16:00 GMT")

    def test_ambiguous_slash_dates_are_ignored(self):
        self.assertIsNone(self.d("Deadline 03/04/2027."))

    def test_past_dates_and_unlabelled_dates_do_not_count(self):
        self.assertIsNone(self.d("Entries closed 12 October 2026. Winners announced 15 March 2027."))
        self.assertIsNone(self.d("The exhibition runs until 30 June 2027."))

    def test_label_priority_then_earliest(self):
        self.assertEqual(self.d("Final deadline: 15 January 2027. Judging deadline 10 December 2026."), "2027-01-15")

    def test_early_bird_is_separate(self):
        r = cf.parse_deadline("Early bird deadline 18 November 2026. Final deadline 10 February 2027.", TODAY)
        self.assertEqual((r["date"], r["early_bird"]), ("2027-02-10", "2026-11-18"))

    def test_yearless_dates(self):
        self.assertEqual(self.d("Entries close on 15 December."), "2026-12-15")
        self.assertEqual(self.d("Entries close on 10 January."), "2027-01-10")
        self.assertIsNone(self.d("Entries close on 12 October."), "an old edition's date is not next year's deadline")


class CreoTerms(unittest.TestCase):
    """The reference case: every entry, irrevocable, three years, and a perpetual device-gallery tail."""

    @classmethod
    def setUpClass(cls):
        cls.text = (FIX / "creo-2027-clause7.txt").read_text()
        cls.result = cf.check_terms(cls.text)
        cls.flags = {f["flag"]: f for f in cls.result["flags"]}

    def test_all_entries(self):
        self.assertEqual(self.flags["licence_all_entries"]["severity"], "high")
        self.assertIn("any image submitted", self.flags["licence_all_entries"]["sentence"])

    def test_irrevocable_worldwide_and_three_years(self):
        self.assertIn("irrevocable", self.flags)
        self.assertIn("worldwide", self.flags)
        self.assertEqual(self.flags["term_years"]["years"], 3)

    def test_perpetual_tail_in_a_lettered_item(self):
        self.assertEqual(self.flags["perpetual"]["severity"], "high")
        self.assertTrue(self.flags["perpetual"]["sentence"].startswith("(h)"))
        self.assertNotIn("scope", self.flags["perpetual"], "(h) sits under an all-entries grant")

    def test_products_need_agreement(self):
        self.assertEqual(self.flags["commercial_use"]["severity"], "medium")
        self.assertEqual(self.flags["commercial_use"]["qualified"], "needs a separate agreement")

    def test_non_commercial_viewing_is_not_commercial(self):
        self.assertFalse(self.flags["commercial_use"]["sentence"].startswith("(g)"))

    def test_sublicensing_fee_ai_and_deadline(self):
        self.assertIn("sublicensable", self.flags)
        self.assertIn("ai_rules", self.flags)
        self.assertEqual(self.result["fee_usd"], 0.0)
        self.assertEqual(cf.parse_deadline(self.text, TODAY)["date"], "2027-01-05")

    def test_gate_and_cost(self):
        self.assertEqual(cf.rights_gate(self.result["flags"], {}), "perpetual licence on every entry")
        self.assertEqual(cf.rights_gate(self.result["flags"], {"allow_rights": True}), "")
        s = PROFILE["score"]
        cost = cf.rights_cost(self.result["flags"], 3, 40, s["rights_multipliers"], s["multiplier_cap"])
        self.assertGreater(cost, 100)


class OtherTerms(unittest.TestCase):
    def test_winners_only_licence(self):
        f = flags_of((FIX / "winners-only.txt").read_text())
        self.assertNotIn("licence_all_entries", f)
        self.assertIn("licence_winners_only", f)
        self.assertNotIn("commercial_use", f, "'will not be used commercially' is negated")

    def test_rights_grab(self):
        f = flags_of((FIX / "rights-grab.txt").read_text())
        for name in ("licence_all_entries", "perpetual", "commercial_use", "copyright_transfer", "automated_entry_banned"):
            self.assertIn(name, f)
        self.assertEqual(f["commercial_use"]["severity"], "high")
        self.assertEqual(cf.rights_gate(list(f.values()), {}), "copyright transfer or exclusive licence")

    def test_silence_is_not_safety(self):
        f = flags_of((FIX / "no-licence.txt").read_text())
        self.assertEqual(f["licence_not_found"]["severity"], "high")

    def test_winners_clause_items_are_scoped(self):
        text = ("(4) For a chance to win an Award, you hereby grant us the right to exhibit any photograph you submit for judging. "
                "(5) For any photograph you submit that wins an Award, you grant us the right to: (i) exhibit it; "
                "(ii) print it in the annual book for sale in all territories.")
        f = flags_of(text)
        self.assertIn("licence_all_entries", f, "the chance to win is not a winners-only limit")
        self.assertEqual(f["commercial_use"].get("scope"), "winners")
        self.assertEqual(f["commercial_use"]["severity"], "medium")

    def test_exclusive_but_not_non_exclusive(self):
        self.assertIn("exclusive", flags_of("Entrants grant an exclusive licence to the organiser."))
        self.assertNotIn("exclusive", flags_of("Entrants grant a non-exclusive licence to the organiser."))

    def test_automation_words_need_a_ban(self):
        self.assertNotIn("automated_entry_banned", flags_of("Entries must not infringe the rights of any third party."))
        self.assertIn("automated_entry_banned", flags_of("Entries submitted by bots or scripts are not permitted."))

    def test_fees(self):
        self.assertEqual(cf.parse_fee("The entry fee is £35 for up to 25 photos."), 44.45)
        self.assertEqual(cf.parse_fee("Fee: $27 per image, or $22 for amateurs."), 22.0)
        self.assertEqual(cf.parse_fee("This contest is free to enter."), 0.0)
        self.assertIsNone(cf.parse_fee("Prizes total $10,000."))

    def test_eligibility(self):
        self.assertFalse(cf.eligibility("Open to residents of the United Kingdom only.")["us_eligible"])
        self.assertFalse(cf.eligibility("Open worldwide, excluding the United States and Quebec.")["us_eligible"])
        self.assertTrue(cf.eligibility("Open to residents of the 50 United States and DC.")["us_eligible"])
        self.assertTrue(cf.eligibility("The competition is open to photographers worldwide.")["us_eligible"])
        self.assertIsNone(cf.eligibility("Prizes are paid by PayPal.")["us_eligible"])


class ScoreAndPicks(unittest.TestCase):
    def rec(self, **kw):
        base = {"id": "x", "name": "X", "url": "https://x.org/", "group": "photo", "size": "small", "themes": ["landscape"],
                "fee_usd": 0, "prize_usd": 1000, "images": 3, "deadline": "2026-12-01", "deadline_status": "verified",
                "status": "open", "source": "registry", "us_eligible": True,
                "licence_text": "Winning images may be licensed for promotion of the awards."}
        base.update(kw)
        cf.evaluate(base, None, PROFILE, 20, TODAY)
        return base

    def test_formula(self):
        r = self.rec()
        si = r["score_inputs"]
        self.assertAlmostEqual(si["ev"], 1000 * PROFILE["score"]["odds"]["photo-small"] * 3 * 1.0, places=2)
        self.assertAlmostEqual(si["score"], round(si["ev"] - 0 - si["rights_cost"], 2), places=2)
        self.assertEqual(cf.pickable(r, PROFILE, TODAY), "")

    def test_free_contests_only(self):
        s = PROFILE["score"]
        self.assertEqual(s["max_fee_usd"], 0)
        self.assertEqual(s["min_score"], 0)
        paid = self.rec(fee_usd=10, prize_usd=10_000_000)
        self.assertGreater(paid["score_inputs"]["score"], 0)
        self.assertIn("fee", cf.pickable(paid, PROFILE, TODAY))
        uncapped = {**PROFILE, "score": {**s, "max_fee_usd": None}}
        self.assertEqual(cf.pickable(paid, uncapped, TODAY), "")

    def test_digest_states_the_bar(self):
        self.assertEqual(cf.bar_line(PROFILE), "Bar: free contests only; a pick must score above 0.")
        self.assertIn("no fee cap", cf.bar_line({"score": {"min_score": -40, "max_fee_usd": None}}))

    def test_free_but_costly_rights_is_not_picked(self):
        r = self.rec(prize_usd=1, licence_text="Every entrant grants the organiser a licence to use all entries "
                     "in its promotion for three years.")
        self.assertLessEqual(r["score_inputs"]["score"], 0)
        self.assertIn("score", cf.pickable(r, PROFILE, TODAY))

    def test_unknown_fee_is_unscored(self):
        r = self.rec(fee_usd=None)
        self.assertIsNone(r["score_inputs"]["score"])
        self.assertIn("fee unknown", cf.pickable(r, PROFILE, TODAY))

    def test_expected_deadline_is_never_picked(self):
        self.assertIn("deadline", cf.pickable(self.rec(deadline_status="expected"), PROFILE, TODAY))

    def test_too_close_and_gated(self):
        self.assertIn("days left", cf.pickable(self.rec(deadline="2026-11-04"), PROFILE, TODAY))
        gated = self.rec(licence_text="Every entrant grants a perpetual licence on all entries.")
        self.assertIn("rights gate", cf.pickable(gated, PROFILE, TODAY))

    def test_thin_material_halves_fit(self):
        self.assertEqual(cf.fit_of(["landscape", "underwater"], PROFILE, 1, 3), 0.25)

    def test_exposure_is_not_added(self):
        self.assertLess(self.rec(exposure_usd=500)["score_inputs"]["score"], 500)


class PhotoRules(unittest.TestCase):
    def ph(self, **kw):
        base = {"file": "a.jpeg", "caption": "A heron by a pond.", "title": "Heron", "tags": {"heron", "bird"},
                "editorial": False, "people": False, "exclusive": False, "taken": "2024-05-01", "location": ""}
        base.update(kw)
        return base

    def test_ai_denoise_ban(self):
        text = "AI enhancement beyond standard correction, AI noise reduction and upscaling are banned."
        self.assertTrue(cf.ai_denoise_banned(text))
        self.assertFalse(cf.ai_denoise_banned("Noise reduction and sharpening are allowed. AI-generated images are banned."))
        rec = {"ai_denoise_banned": True}
        self.assertIn("AI denoise", cf.photo_eligible(self.ph(file="DSC_1906-Enhanced-NR.jpeg"), rec))
        self.assertEqual(cf.photo_eligible(self.ph(file="DSC_1906.jpeg"), rec), "")
        self.assertEqual(cf.photo_eligible(self.ph(file="DSC_1906-Enhanced-NR.jpeg"), {}), "")

    def test_wild_only(self):
        rec = {"wild_only_detected": True}
        self.assertEqual(cf.photo_eligible(self.ph(), rec), "")
        self.assertEqual(cf.photo_eligible(self.ph(caption="A frog in a rainforest exhibit."), rec), "captive animal or cultivated plant")
        self.assertEqual(cf.photo_eligible(self.ph(tags={"botanical garden", "lily pad"}), rec), "captive animal or cultivated plant")
        self.assertEqual(cf.photo_eligible(self.ph(caption="A frog in a rainforest exhibit."), {}), "")

    def test_wild_only_rule_is_read_from_the_terms(self):
        rec = {"id": "w", "name": "W", "url": "https://w.org/", "group": "photo", "themes": ["wildlife"], "fee_usd": 0,
               "licence_text": "All entries must be of non-captive wild animals, plants and habitats."}
        cf.evaluate(rec, None, PROFILE, 5, TODAY)
        self.assertTrue(rec["wild_only_detected"])

    def test_capture_dates(self):
        rec = {"taken_from": "2026-01-01", "taken_to": "2026-12-31"}
        self.assertEqual(cf.photo_eligible(self.ph(taken="2025-06-01"), rec), "taken too early")
        self.assertEqual(cf.photo_eligible(self.ph(taken=None), rec), "capture date unknown")
        self.assertEqual(cf.photo_eligible(self.ph(taken="2026-06-01"), rec), "")


class Statuses(unittest.TestCase):
    def test_transitions(self):
        led = {"contests": {"x": {"id": "x", "status": "queued"}}}
        cf.mark(led, "x", "entered", url="https://x.org/ok", terms_matched="yes", today=TODAY)
        self.assertEqual(led["contests"]["x"]["entered"], "2026-11-02")
        cf.mark(led, "x", "won", note="2nd place", today=TODAY)
        self.assertEqual(led["contests"]["x"]["result"]["status"], "won")
        with self.assertRaises(SystemExit):
            cf.mark(led, "x", "skipped")
        with self.assertRaises(SystemExit):
            cf.mark(led, "x", "submitted")

    def test_scan_never_changes_bens_statuses(self):
        rec = {"status": "entered", "deadline": "2026-10-01"}
        cf.refresh_status(rec, TODAY)
        self.assertEqual(rec["status"], "entered")
        rec = {"status": "queued", "deadline": "2026-10-01"}
        cf.refresh_status(rec, TODAY)
        self.assertEqual(rec["status"], "closed")


def tiny_jpeg(seed: str) -> bytes:
    return b"\xff\xd8\xff\xe0" + hashlib.sha256(seed.encode()).digest() * 8 + b"\xff\xd9"


class EndToEnd(unittest.TestCase):
    """weekly(): scan with a fake fetcher, pick, prefill (photo copies), queue through approval_queue.py, digest."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.env = dict(os.environ)
        lib, ws = self.tmp / "library", self.tmp / "ws"
        (ws / "exports").mkdir(parents=True)
        lib.mkdir()
        rows = ["Filename,Caption,Tags,Supertags,License,Editorial,Title"]
        export = ["Filename,Location,Date taken,Exclusive to Alamy"]
        for i, (tags, ed) in enumerate([("mountain;lake;sunrise;landscape", "No"), ("forest;waterfall;river", "No"),
                                        ("canyon;desert;sunset", "No"), ("crowd;stadium;fans;landscape", "No"),
                                        ("lake;mountain;reflection", "Yes"), ("coast;beach;seascape", "No")]):
            name = f"P{i}.jpeg"
            (lib / name).write_bytes(tiny_jpeg(name))
            rows.append(f'{name},"A view number {i}, somewhere.",{tags},,RF,{ed},View {i}')
            export.append(f"{name},Place {i},0{i + 1}/06/2025,No")
        (ws / "alamy-metadata.csv").write_text("\n".join(rows) + "\n")
        (ws / "exports" / "BenjaminAmpel_01012026.csv").write_text("\n".join(export) + "\n")
        self.originals = {q.name: q.read_bytes() for q in lib.iterdir()}
        sources = {"schema": 1, "contests": [
            {"id": "lake-awards", "name": "Lake Awards 2026", "url": "https://lake.example/rules", "group": "photo", "size": "small",
             "themes": ["landscape"], "edition": "2026", "deadline": "2026-12-01", "deadline_status": "verified", "fee_usd": 0,
             "images": 3, "prize_usd": 1000, "us_eligible": True},
            {"id": "grab", "name": "Grab Contest", "url": "https://grab.example/rules", "group": "photo", "themes": ["landscape"],
             "edition": "2026", "deadline": "2026-12-01", "deadline_status": "verified", "fee_usd": 0, "prize_usd": 2500, "us_eligible": True},
            {"id": "old", "name": "Old Contest", "url": "https://old.example/", "group": "photo", "themes": ["landscape"],
             "edition": "2026", "deadline": "2026-10-01", "deadline_status": "verified", "fee_usd": 0, "prize_usd": 100},
        ]}
        (self.tmp / "sources.json").write_text(json.dumps(sources))
        os.environ.update({
            "PURPLELINK_CONTESTS": str(self.tmp / "state"), "PURPLELINK_CONTEST_BRIEFS": str(self.tmp / "briefs"),
            "PURPLELINK_PHOTO_WORKSPACE": str(ws), "PURPLELINK_PHOTO_LIBRARY": str(lib),
            "PURPLELINK_CONTEST_SOURCES": str(self.tmp / "sources.json"), "PURPLELINK_QUEUE": str(self.tmp / "queue"),
            "PURPLELINK_HUB": str(self.tmp / "hub"), "PURPLELINK_REPO": str(self.tmp / "repo"),
        })
        self.pages = {
            "https://lake.example/rules": (FIX / "winners-only.txt").read_text() * 8,
            "https://grab.example/rules": (FIX / "rights-grab.txt").read_text() * 8,
        }

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.env)

    def fetcher(self, url):
        if url in self.pages:
            return {"status": "ok", "text": self.pages[url], "code": 200}
        return {"status": "blocked", "text": "", "code": 403, "why": "http 403"}

    def test_weekly(self):
        p = cf.paths()
        out = cf.weekly(p, TODAY, offline=True, fetcher=self.fetcher)
        self.assertEqual(out["picks"], [], "offline with no cached pages: no licence text, nothing is picked")
        out = cf.weekly(p, TODAY, offline=False, fetcher=self.fetcher)
        self.assertEqual(out["picks"], ["lake-awards"])
        led = cf.load_ledger(p)
        lake, grab, old = (led["contests"][k] for k in ("lake-awards", "grab", "old"))
        self.assertEqual(grab["gate"], "copyright transfer or exclusive licence")
        self.assertEqual(old["status"], "closed")
        self.assertEqual(lake["status"], "queued")
        self.assertEqual(lake["queue_folder"], "pending", lake.get("queue_problems"))
        entry = Path(lake["entry_dir"])
        copies = sorted(x.name for x in (entry / "photos").iterdir())
        self.assertEqual(len(copies), 3)
        self.assertNotIn("P3.jpeg", copies, "people")
        self.assertNotIn("P4.jpeg", copies, "editorial")
        text = (entry / "entry.md").read_text()
        self.assertIn("Checklist (Ben)", text)
        self.assertIn("mark lake-awards entered", text)
        lib = Path(os.environ["PURPLELINK_PHOTO_LIBRARY"])
        self.assertEqual({q.name: q.read_bytes() for q in lib.iterdir()}, self.originals, "originals unchanged")
        digest = Path(out["digest"]).read_text()
        self.assertIn("Lake Awards 2026", digest)
        self.assertIn("Held back by the rights gate", digest)
        cf.weekly(p, TODAY, offline=False, fetcher=self.fetcher)
        self.assertEqual(len(list((self.tmp / "queue" / "pending").glob("*.md"))), 1, "nothing is queued twice")

    def test_copy_refuses_the_library(self):
        lib = Path(os.environ["PURPLELINK_PHOTO_LIBRARY"])
        with self.assertRaises(SystemExit):
            cf.safe_copy(lib / "P0.jpeg", lib / "sub", lib)
        with self.assertRaises(SystemExit):
            cf.resize_copy(lib / "P0.jpeg", 100, lib)

    def test_product_entry(self):
        site = self.tmp / "site"
        (site / "widget").mkdir(parents=True)
        (site / "widget" / "shot-1.png").write_bytes(b"png")
        (site / "llms.txt").write_text("## Products\n\n### Widget (macOS)\nWidget [tidies](https://x) your menu bar. It runs on macOS 14 and later. "
                                       "It costs $9.99 once. It never sends data anywhere.\n\n### Other (macOS)\nOther.\n")
        os.environ["PURPLELINK_SITE"] = str(site)
        p = cf.paths()
        led = {"contests": {"apps": {"id": "apps", "name": "App Awards", "url": "https://apps.example/", "group": "app-award",
                                      "product": "widget", "status": "open", "edition": "2027", "deadline": "2027-02-01",
                                      "fee_usd": 0, "flags": []}}}
        out = cf.prefill(p, led, "apps", None, TODAY)
        rec = led["contests"]["apps"]
        self.assertIn("utm_content=widget-contest-261102", rec["utm_link"])
        self.assertIn("utm_medium=referral", rec["utm_link"])
        self.assertTrue(rec["statement"].startswith("Widget is made by Purplelink"))
        self.assertNotIn("](", rec["statement"])
        self.assertIn("site/widget/shot-1.png", (out / "entry.md").read_text())
        link = rec["utm_link"]
        cf.prefill(p, led, "apps", None, TODAY)
        self.assertEqual(rec["utm_link"], link, "a second prefill keeps the same tag")

    def test_hub_reads_the_ledger(self):
        hub = load("hub", "scripts/hub/hub.py")
        p = cf.paths()
        cf.weekly(p, TODAY, offline=False, fetcher=self.fetcher)
        led = cf.load_ledger(p)
        cf.mark(led, "lake-awards", "entered", url="https://lake.example/ok", today=TODAY)
        cf.mark(led, "lake-awards", "won", today=TODAY)
        cf.save_json(p["ledger"], led)
        pls, results = hub.from_contests(hub.paths())
        self.assertEqual([(x["id"], x["status"], x["channel"]) for x in pls], [("contest:lake-awards:2026", "live", "contest")])
        self.assertIn(("contest:lake-awards:2026", "2026-11-02", "contest_result", 1.0, "contest-finder", "exact"), results)
        self.assertEqual(hub.from_queue(hub.paths()), [], "the contest's queue item is not counted a second time")


class QueueLint(unittest.TestCase):
    def test_item_passes_the_queue_lint(self):
        aq = load("approval_queue", "scripts/queue/approval_queue.py")
        rec = {"id": "x", "name": "X Awards", "edition": "2026", "url": "https://x.example/rules", "group": "photo",
               "deadline": "2026-12-01", "fee_usd": 5, "fee_text": "$5", "flags": [], "terms_source": "page",
               "read": "2026-11-02", "statement": "3 photos for X Awards: Lake at dawn; River bend; Red canyon.",
               "entry_dir": "/tmp/x", "score_inputs": {"ev": 1.0, "score": -5}}
        fm, body = aq.split_item(cf.queue_item(rec, TODAY))
        fm.update(id="AQ-TEST", created="2026-11-02T09:00:00-05:00", status="pending")  # set by approval_queue.py new
        checks, problems = aq.lint(fm, body, offline=True, others=[], today=TODAY)
        self.assertEqual(problems, [])
        self.assertEqual((fm["kind"], fm["executor"], fm["job"]), ("submission", "ben", "contest-finder"))


if __name__ == "__main__":
    unittest.main()
