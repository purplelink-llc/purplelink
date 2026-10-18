"""Checks for the 4K output, the fireplace close-up, the holiday titles and the playlist plan: python3.12 -m pytest -q test_holiday.py"""
import json
import re
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

import keywords
import longform as lf
import longform_pub as pub
import playlists
import themes

EMOJI_OR_FANCY = re.compile(r"[^\x00-\x7f]")
HEALTH = re.compile(r"\b(improve|improves|cure|cures|anxiety|adhd|insomnia|treat|treats|relieve|relieves|therapy|therapeutic|heal|heals|reduce stress|focus better|fall asleep faster|brain)\b", re.I)

KW = {"date": "2026-10-17", "modifiers": {"black screen": 9.9, "dark screen": 0.6, "4k": 11.6, "tv": 5.5},
      "kinds": {"christmas-fireplace": [{"phrase": "christmas fireplace no ads", "score": 9.1, "seeds": 12, "best_pos": 0},
                                        {"phrase": "fireplace for tv screen", "score": 7.3, "seeds": 6, "best_pos": 0},
                                        {"phrase": "yule log fireplace", "score": 3.1, "seeds": 3, "best_pos": 1},
                                        {"phrase": "christmas fireplace 2 hours", "score": 6.4, "seeds": 10, "best_pos": 0},
                                        {"phrase": "christmas music fireplace classic", "score": 3.4, "seeds": 3, "best_pos": 1},
                                        {"phrase": "christmas fireplace sleep music", "score": 3.5, "seeds": 4, "best_pos": 1},
                                        {"phrase": "christmas fireplace 10 hours", "score": 3.2, "seeds": 4, "best_pos": 1}],
                "christmas-ambience": [{"phrase": "christmas cabin ambience", "score": 7.2, "seeds": 6, "best_pos": 0},
                                       {"phrase": "christmas lofi", "score": 3.7, "seeds": 2, "best_pos": 1}],
                "snowy-cabin": [{"phrase": "snowy cabin ambience", "score": 8.4, "seeds": 5, "best_pos": 0}]}}

# the four holiday jobs: (theme, sound, music, view, uhd, dark, season, hours)
JOBS = {
    "christmas-fireplace-4k-10h": ("winter", "fireplace", False, "fireplace", True, 0.0, "christmas", 10),
    "christmas-cabin-chiptune-4k-10h": ("winter", "chiptune", True, "", True, 0.0, "christmas", 10),
    "christmas-study-lofi-4k-3h": ("study", "lofi", True, "", True, 0.0, "christmas", 3),
    "snowy-cabin-brown-4k-10h-black-screen": ("winter", "brown", False, "", True, 600.0, "", 10),
}


def meta(job, kw=KW):
    theme, sound, music, view, uhd, dark, season, hours = JOBS[job]
    return pub.build_metadata(theme, hours * 3600.0, job, music, False, 1, [], 20.0, sound=sound, dark=dark, kw=kw, uhd=uhd, season=season, view=view)


# ------------------------------------------------------------------------------------------------------------------------ 4K
def test_uhd_commands_enlarge_exactly_2x_with_nearest_neighbour_and_level_5_1(tmp_path):
    v = " ".join(lf.video_cmd(1200, 10, Path("v.mp4"), fades=False, uhd=True))
    assert "1920x1080" in v and "scale=3840:2160:flags=neighbor" in v and "-level 5.1" in v and "-tune animation" in v and "-g 60" in v and "fps=30" in v
    assert v.index("format=yuv420p") < v.index("scale=3840")                  # the colour conversion is done at 1080p, then each pixel is copied into a 2x2 block
    plain = " ".join(lf.video_cmd(1200, 10, Path("v.mp4"), fades=False))
    assert "scale=3840" not in plain and "-level 4.1" in plain                # the default output is what it was
    b = " ".join(lf.black_cmd(600, 10, Path("b.mp4"), uhd=True))
    assert "s=3840x2160" in b and "-level 5.1" in b                            # a dark video's black clip must match its picture to be joined by stream copy
    assert "s=1920x1080" in " ".join(lf.black_cmd(600, 10, Path("b.mp4")))
    assert lf.out_size(True) == (3840, 2160) and lf.out_size(False) == (1920, 1080)


def test_verify_accepts_2160p_and_1080p_and_nothing_else():
    assert pub.size_checks({"width": 3840, "height": 2160})["1080p_or_2160p"] and pub.size_checks({"width": 3840, "height": 2160})["2160p"]
    assert pub.size_checks({"width": 1920, "height": 1080})["1080p"] is True
    assert not pub.size_checks({"width": 2560, "height": 1440})["1080p_or_2160p"]


def test_a_short_uhd_render_is_2160p_and_every_art_pixel_is_a_hard_12x12_block(tmp_path):
    out = tmp_path / "u.mp4"
    lf.main(["--theme", "winter", "--view", "fireplace", "--season", "christmas", "--sound", "fireplace", "--uhd", "--seconds", "8", "--out", str(out)])
    rep = pub.verify(out, tmp_path / "frames", "u", sound="fireplace")
    assert (rep["width"], rep["height"]) == (3840, 2160) and rep["video_codec"] == "h264" and rep["checks"]["2160p"] and rep["fps"] == "30/1"
    assert abs(rep["duration"] - 8) < 0.3 and rep["true_peak_dbtp"] <= -1.0
    assert all(Image.open(p).size == (3840, 2160) for p in rep["frames"])
    im = np.asarray(Image.open(rep["frames"][1]).convert("RGB"), np.int16)       # a frame from the middle of the clip, after the fade in
    down = im[::2, ::2]
    again = np.repeat(np.repeat(down, 2, axis=0), 2, axis=1)
    assert np.abs(im - again).mean() < 2.5                                       # a 2x enlargement by copying: only codec noise differs
    assert np.abs(np.diff(im.astype(float), axis=1)).max() > 60                  # and edges are hard, not smoothed


def test_a_dark_uhd_video_joins_a_4k_intro_to_a_4k_black_clip_without_a_decode_error(tmp_path):
    out = tmp_path / "d.mp4"
    lf.main(["--theme", "winter", "--seconds", "50", "--dark", "5", "--sound", "pink", "--uhd", "--out", str(out)])
    assert pub.probe(out)["height"] == 2160
    assert subprocess.run(["ffmpeg", "-v", "error", "-i", str(out), "-f", "null", "-"], capture_output=True).stderr == b""


# ------------------------------------------------------------------------------------------------------------------------ the fireplace close-up
def test_fireplace_view_is_the_same_scene_enlarged_2x_and_is_deterministic():
    full = themes.get("winter")(seed=4, seconds=3600, options={})
    close = themes.get("winter")(seed=4, seconds=3600, options={"view": "fireplace"})
    a, b = close.frame(120.0), themes.get("winter")(seed=4, seconds=3600, options={"view": "fireplace"}).frame(120.0)
    assert a.size == (320, 180) and a.tobytes() == b.tobytes()
    arr = np.asarray(a)
    assert np.array_equal(arr, np.repeat(np.repeat(arr[::2, ::2], 2, axis=0), 2, axis=1))      # every art pixel is a 2x2 block: crisp
    assert a.tobytes() != full.frame(120.0).tobytes()
    arr = arr.astype(int)
    ys, xs = np.where((arr[..., 0] > 170) & (arr[..., 0] - arr[..., 2] > 100))                  # orange and red: the flame is in the picture, and large
    assert len(ys) > 2000 and 120 < xs.mean() < 220
    assert close.frame(121.0).tobytes() != close.frame(120.0).tobytes()                          # it animates


def test_the_default_winter_frame_is_unchanged_by_the_view_option():
    a = themes.get("winter")(seed=4, seconds=3600).frame(300.0)
    b = themes.get("winter")(seed=4, seconds=3600, options={"season": "christmas"}).frame(300.0)
    assert a.tobytes() == b.tobytes() and a.size == (320, 180)


# ------------------------------------------------------------------------------------------------------------------------ keywords
def test_holiday_seeds_are_asked_and_ranked():
    qs = {q for _, _, q in keywords.queries()}
    for q in ("christmas fireplace", "yule log", "fireplace 4k", "christmas fireplace 4k", "christmas ambience", "snowy cabin", "christmas music fireplace",
              "fireplace 10 hours", "winter fireplace", "cozy christmas", "christmas lofi", "christmas chiptune", "thanksgiving ambience",
              "new years eve ambience", "christmas fireplace tv", "christmas fireplace black screen", "christmas fireplace for sleeping", "yule log no music"):
        assert q in qs, q
    cache = {"christmas fireplace": {"date": "2026-10-17", "suggestions": ["christmas fireplace 4k", "christmas fireplace 10 hours", "lofi girl"]},
             "christmas fireplace 4k": {"date": "2026-10-17", "suggestions": ["christmas fireplace 4k", "christmas fireplace for tv"]}}
    rank = keywords.rank(cache)
    rows = rank["kinds"]["christmas-fireplace"]
    assert rows[0]["phrase"] == "christmas fireplace 4k" and "lofi girl" not in [r["phrase"] for r in rows]
    assert rank["modifiers"]["4k"] > 0 and rank["modifiers"]["10 hours"] > 0


# ------------------------------------------------------------------------------------------------------------------------ titles and metadata
@pytest.mark.parametrize("job", sorted(JOBS))
def test_holiday_titles_and_descriptions_are_plain_true_and_tv_shaped(job):
    theme, sound, music, view, uhd, dark, season, hours = JOBS[job]
    m = meta(job)
    t, d = m["title"], m["description"]
    assert len(t) <= 100 and not EMOJI_OR_FANCY.search(t + d) and "!" not in t and "no ads" not in (t + d + " ".join(m["tags"])).lower()
    assert not HEALTH.search(t + " " + d + " ".join(m["tags"]))
    assert f"{hours} Hours" in t and t.count("Hours") == 1
    assert ("No Music" in t) == (not music and sound == "fireplace") and ("no music" in d.lower()) == (not music)
    assert ("4K" in t) == (uhd and not dark)                                   # 4K only for a 2160p file whose picture stays on screen
    assert ("3840x2160" in d) == uhd and "1920x1080" not in d.replace("drawn at 1920x1080", "")
    assert bool(dark) == ("Black Screen" in t) and bool(dark) == ("near black" in d)
    first = d.split("\n")[0]
    assert len(first) <= 150 and first.split(",")[0].lower().startswith(t.split(",")[0].split(" with ")[0].split(" 4K")[0].lower()) and f"{hours} Hours" in first
    assert len(m["tags"]) <= 15 and sum(len(x) for x in m["tags"]) < 480 and len({x.lower() for x in m["tags"]}) == len(m["tags"])
    assert ("4k" in m["tags"]) == uhd
    last = d.strip().split("\n")[-1]
    assert len(last.split()) == 3 and all(w.startswith("#") for w in last.split())
    assert "About this video" in d and "This channel makes" in d and "loop" in d.lower()
    if music:
        assert "No carol" in d and "original" in first.lower()
    json.dumps(m)


def test_the_most_important_words_are_in_the_first_50_characters():
    t = meta("christmas-fireplace-4k-10h")["title"]
    assert t[:50].startswith("Christmas Fireplace 4K for TV") and "Yule Log" in t
    assert meta("christmas-fireplace-4k-10h", kw=None)["title"] == "Christmas Fireplace 4K, Crackling Yule Log, 10 Hours, No Music"
    t = meta("christmas-cabin-chiptune-4k-10h")["title"]
    assert t == "Christmas Cabin Ambience 4K with Christmas Chiptune Music, 10 Hours" and "4K" in t[:40]
    assert meta("christmas-study-lofi-4k-3h")["title"] == "Christmas Lofi Study Music, Cozy Study Room 4K, 3 Hours"
    assert meta("snowy-cabin-brown-4k-10h-black-screen")["title"] == "Brown Noise with Snowy Cabin, 10 Hours, Black Screen"


def test_the_lead_follows_the_keyword_research():
    kw = json.loads(json.dumps(KW))
    kw["kinds"]["christmas-fireplace"] = [{"phrase": "yule log fireplace", "score": 9.0, "seeds": 5, "best_pos": 0}]
    t = meta("christmas-fireplace-4k-10h", kw)["title"]
    assert t.startswith("Yule Log 4K") and "Crackling Fireplace" in t and "Crackling Yule Log" not in t


def test_a_plain_1080p_video_keeps_its_old_metadata_and_a_4k_only_video_says_4k():
    a = pub.build_metadata("campfire", 7200, "c", True, False, 1, [])
    b = pub.build_metadata("campfire", 7200, "c", True, False, 1, [], uhd=False, season="", view="")
    assert a == b and "4K" not in a["title"]
    m = pub.build_metadata("campfire", 36000, "c4k", False, False, 1, [], 20, sound="brown", dark=0.0, uhd=True)
    assert m["title"] == "Brown Noise with Crackling Campfire 4K, 10 Hours" and "3840x2160" in m["description"]


def test_holiday_thumbnails_are_1280x720_and_say_what_the_title_says(tmp_path):
    for job, (theme, sound, music, view, uhd, dark, season, hours) in JOBS.items():
        opts = {"season": season} if season else {}
        if view:
            opts["view"] = view
        p = pub.make_thumbnail(theme, hours * 3600.0, 5, tmp_path / f"{job}.jpg", opts, music=music or sound in ("chiptune", "lofi"), sound=sound, uhd=uhd, dark=dark)
        assert Image.open(p).size == (1280, 720) and p.stat().st_size < 2_000_000
    assert pub.thumb_text("winter", "fireplace", False, "christmas", True, 0.0) == ["CHRISTMAS", "FIREPLACE 4K"]
    assert pub.thumb_text("winter", "brown", False, "", True, 600.0) == ["BROWN NOISE", "SNOWY CABIN"]      # no 4K on a black-screen thumbnail
    assert pub.thumb_text("campfire", "chiptune", True, "", False, 0.0) is None


# ------------------------------------------------------------------------------------------------------------------------ playlists (plan only)
def test_playlist_plan_puts_each_video_where_it_belongs_and_leaves_no_playlist_empty():
    items = [{"slug": s, "title": f"T {s}", "render": {"theme": j[0], "sound": j[1], "season": j[6] or None, "view": j[3] or None, "uhd": j[4],
                                                       "dark_after_seconds": j[5] or None, "seconds": j[7] * 3600}} for s, j in JOBS.items()]
    items += [{"slug": "campfire-2h", "title": "Campfire", "render": {"theme": "campfire", "seconds": 7200, "music": True}},        # an old metadata file: no sound, no uhd
              {"slug": "halloween-2h", "title": "Halloween", "render": {"theme": "halloween", "seconds": 7200}}]
    plan = {p["title"]: [v["slug"] for v in p["videos"]] for p in playlists.plan_from_items(items)}
    assert plan["Christmas Fireplace 4K"] == ["christmas-fireplace-4k-10h"]
    assert plan["Cozy Christmas Ambience"] == ["christmas-cabin-chiptune-4k-10h", "christmas-study-lofi-4k-3h"]
    assert plan["Black Screen Sleep Sounds"] == ["snowy-cabin-brown-4k-10h-black-screen"]
    assert plan["Winter Cabin Ambience"] == ["snowy-cabin-brown-4k-10h-black-screen"]
    assert plan["Campfire Ambience"] == ["campfire-2h"] and plan["Halloween Ambience"] == ["halloween-2h"]
    assert plan["Study Room Ambience"] == ["christmas-study-lofi-4k-3h"] and "New Year's Eve Ambience" not in plan
    assert playlists.plan_from_items([]) == []


def test_playlist_plan_reads_the_metadata_files_and_writes_json(tmp_path, capsys):
    d = tmp_path / "christmas-fireplace-4k-10h"
    d.mkdir()
    (d / "christmas-fireplace-4k-10h.json").write_text(json.dumps(meta("christmas-fireplace-4k-10h")))
    (tmp_path / "empty-dir").mkdir()
    out = tmp_path / "plan.json"
    assert playlists.main(["--root", str(tmp_path), "--out", str(out)]) == 0
    data = json.loads(out.read_text())
    assert [p["title"] for p in data["playlists"]] == ["Christmas Fireplace 4K"]
    v = data["playlists"][0]["videos"][0]
    assert v["slug"] == "christmas-fireplace-4k-10h" and v["title"].startswith("Christmas Fireplace 4K")
    assert "Christmas Fireplace 4K" in capsys.readouterr().out


def test_tags_never_promise_what_the_video_does_not_have():
    m = meta("christmas-fireplace-4k-10h")
    tags = " | ".join(m["tags"])
    assert "no ads" not in tags and "2 hours" not in tags and "classic" not in tags and "sleep music" not in tags      # ranked, but wrong length, carols, or music in a no-music video
    assert "christmas fireplace 10 hours" in m["tags"] and "fireplace for tv screen" in m["tags"]
    assert pub.honest_phrase("christmas fireplace 4k", 10, True, False) and not pub.honest_phrase("christmas fireplace 4k", 10, False, False)
    assert not pub.honest_phrase("christmas ambience for 3 hours", 10, True, False) and pub.honest_phrase("christmas ambience for 3 hours", 3, True, False)
    assert pub.honest_phrase("christmas ambience no music", 10, True, False) and not pub.honest_phrase("christmas lofi", 10, True, False)
    assert not pub.honest_phrase("brown noise rain", 10, True, False, "brown") and pub.honest_phrase("rain sounds 10 hours", 10, True, False, "rain")
    assert not pub.honest_phrase("cozy cabin snow storm", 10, True, True, "chiptune")
    assert pub.merge_tags(["brown noise no ads", "brown noise", "ad-free rain", "rain no copyright"]) == ["brown noise"]
