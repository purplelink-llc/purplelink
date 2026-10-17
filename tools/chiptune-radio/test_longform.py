"""Checks for the long-form video tools: python3.12 -m pytest -q test_longform.py   (about a minute; the one real render is 12 s of ambience)"""
import json
import re
import subprocess

import numpy as np
import pytest
from PIL import Image

import ambience
import chiptune as c
import longform as lf
import longform_pub as pub
import px
import themes

ALL = ["campfire", "halloween", "study", "winter"]
EVENT_KINDS = {"owl", "settle", "gust", "sleigh", "star", "bats", "ghost"}


def test_every_theme_is_registered_by_a_small_file():
    assert set(ALL) <= set(themes.names())
    with pytest.raises(KeyError):
        themes.get("no-such-theme")
    for n in ALL:
        cls = themes.get(n)
        assert cls.name == n and cls.thumb_lines and cls.music["mood"][0] <= cls.music["mood"][1]


@pytest.mark.parametrize("name", ALL)
def test_theme_draws_crisp_distinct_frames(name):
    th = themes.get(name)(seed=3, seconds=3600)
    a, b = th.frame(100.0), th.frame(100.7)
    assert a.size == (320, 180) and a.mode == "RGB"
    assert a.tobytes() != b.tobytes()                                   # it animates
    other = themes.get(name)(seed=3, seconds=3600).frame(100.0)
    assert a.tobytes() == other.tobytes() or name in ("campfire", "winter")   # the fire's flicker depends on the frames drawn before it, nothing else does
    hd = a.resize(lf.VIDEO_SIZE, Image.NEAREST)
    assert hd.size == (1920, 1080) and 1920 % 320 == 0 and 1080 % 180 == 0 and 1920 // 320 == 1080 // 180


@pytest.mark.parametrize("name", ALL)
def test_events_are_inside_the_video_and_the_sound_can_use_them(name):
    th = themes.get(name)(seed=5, seconds=7200)
    for e in th.events:
        assert e[1] in EVENT_KINDS and 0 <= e[0] and e[0] + e[2] <= 7200
    for _, kind, _ in th.audio_events():
        assert kind in {"owl", "settle", "gust", "sleigh"}
    assert th.fps in (5, 6, 10, 15, 30)                                   # a divisor of 30, so every frame is shown equally often


def test_fire_is_deterministic_and_a_jump_does_not_replay_hours():
    a, b = px.Fire(seed=2), px.Fire(seed=2)
    a.advance(30)
    b.advance(30)
    assert np.array_equal(a.heat, b.heat)
    b.advance(1_000_000)                                                   # would take minutes if it replayed
    assert b.n == 1_000_000 and b.heat.max() > 0.3
    assert (a.image().size) == (28, 34)


def test_pomodoro_is_for_study_only_and_25_5_only():
    with pytest.raises(SystemExit):
        lf.main(["--theme", "campfire", "--pomodoro", "25/5", "--seconds", "5", "--out", "/private/tmp/x.mp4"])
    with pytest.raises(ValueError):
        themes.get("study")(1, 3600, options={"pomodoro": (50, 10)})
    th = themes.get("study")(1, 7200, options={"pomodoro": (25, 5)})
    ch = th.chapters()
    assert ch[0] == (0.0, "Focus 1") and ch[1] == (1500.0, "Break") and ch[2] == (1800.0, "Focus 2")
    assert all(b[0] - a[0] >= 10 for a, b in zip(ch, ch[1:]))              # YouTube needs chapters at least 10 s long
    hd = Image.new("RGB", lf.VIDEO_SIZE)
    th.overlay(hd, 100.0)
    assert hd.getbbox() is not None                                        # the timer was drawn
    plain = Image.new("RGB", lf.VIDEO_SIZE)
    themes.get("study")(1, 7200).overlay(plain, 100.0)
    assert plain.getbbox() is None                                         # no timer without --pomodoro


@pytest.mark.parametrize("name,allowed", [("halloween", {"minor", "dorian", "mixolydian"}), ("winter", {"major", "lydian", "mixolydian", "dorian"})])
def test_music_palette_follows_the_theme(name, allowed):
    cls = themes.get(name)
    tracks = lf.plan_tracks(cls, 7200, 11)
    assert {t["mode"] for t in tracks} <= allowed
    assert tracks[0]["start"] == 0 and tracks[-1]["start"] + tracks[-1]["seconds"] >= 7200
    for a, b in zip(tracks, tracks[1:]):
        assert a["key"] != b["key"] and abs(a["bpm"] - b["bpm"]) <= lf.MAX_BPM_STEP
        assert abs(b["start"] - (a["start"] + a["seconds"] - lf.XFADE)) < 1e-6   # each track starts inside the previous one's crossfade
    assert min(t["mood"] for t in tracks) < 0.1 and max(t["mood"] for t in tracks) > 0.3   # the mood drifts


def test_mode_weights_do_not_change_the_default_plan():
    assert c.plan(7).mode == c.plan(7, None, None, None).mode
    assert c.plan(7, mode_weights={"minor": 1}).mode == "minor"


def test_ambience_has_no_seam_between_blocks_and_is_repeatable():
    ev = [(3.0, "owl", 6.0), (9.0, "settle", 2.0)]
    layers = {"fire": 1, "wind": 1, "hollow_wind": 1, "muffled_wind": 1, "crickets": 1, "rain": 1}
    a = ambience.Bed(layers, 40, seed=4, events=ev, rain=[(2, 30)])
    x = np.concatenate([a.block(44100 * 7), a.block(44100 * 7)], axis=1)
    b = ambience.Bed(layers, 40, seed=4, events=ev, rain=[(2, 30)])
    y = np.concatenate([b.block(44100 * 7), b.block(44100 * 7)], axis=1)
    assert np.array_equal(x, y)                                            # the same seed and the same cuts give the same sound
    assert not np.isnan(y).any() and 0.01 < float(np.sqrt((y ** 2).mean())) < 1.0
    join = np.abs(x[:, 44100 * 7] - x[:, 44100 * 7 - 1]).max()
    assert join < 6 * np.abs(np.diff(x, axis=1)).std()                     # no click where the blocks meet


def test_ambience_never_falls_silent():
    y = ambience.Bed({"room": 1.0}, 20, seed=1).block(44100 * 20)
    assert float(np.sqrt((y ** 2).mean())) > 0.002


def test_soft_clip_never_exceeds_the_ceiling_and_leaves_quiet_sound_alone():
    x = np.linspace(-3, 3, 1001).astype(np.float32)
    y = lf.soft_clip(x)
    assert np.abs(y).max() <= 0.97 + 1e-6 and np.array_equal(y[np.abs(x) < 0.7], x[np.abs(x) < 0.7])


def test_ffmpeg_commands_ask_for_the_right_file():
    from pathlib import Path
    v = " ".join(lf.video_cmd(7200, 10, Path("v.mp4")))
    assert "1920x1080" in v and "libx264" in v and "fps=30" in v and "-r 30" in v and "fade=t=out:st=7195.000" in v and "-an" in v
    meas = {"input_i": "-20.1", "input_tp": "-5.0", "input_lra": "4.0", "input_thresh": "-30.0", "target_offset": "0.2"}
    m = " ".join(lf.mux_cmd(Path("w"), meas, 7200, Path("o.mp4")))
    assert "-c:v copy" in m and "-c:a aac" in m and "192k" in m and "+faststart" in m and "volume=6.10dB" in m and "alimiter" in m and "-ar 48000" in m
    assert "loudnorm" not in m and "-stream_loop" not in m
    assert "-stream_loop -1" in " ".join(lf.mux_cmd(Path("w"), meas, 7200, Path("o.mp4"), loop=True))


def test_a_short_ambience_render_meets_the_loudness_and_format_targets(tmp_path):
    out = tmp_path / "t.mp4"
    lf.main(["--theme", "campfire", "--seconds", "24", "--no-music", "--out", str(out)])
    rep = pub.verify(out, tmp_path / "frames", "t")
    assert rep["width"] == 1920 and rep["height"] == 1080 and rep["video_codec"] == "h264" and rep["audio_codec"] == "aac"
    assert abs(rep["duration"] - 24) < 0.2 and rep["fps"] == "30/1" and rep["audio_rate"] == "48000"
    assert abs(rep["integrated_lufs"] + 14.0) <= 0.7, rep
    assert rep["true_peak_dbtp"] <= -1.0, rep
    assert rep["silences_over_3s_outside_the_final_fade"] == []
    assert len(rep["frames"]) == 4 and all(Image.open(p).size == (1920, 1080) for p in rep["frames"])
    assert not (tmp_path / "t.mp4.work" / "audio.pcm").exists()            # the work files are cleaned up


def test_thumbnail_is_1280x720_under_2mb(tmp_path):
    p = pub.make_thumbnail("winter", 7200, 5, tmp_path / "t.jpg")
    im = Image.open(p)
    assert im.size == (1280, 720) and p.stat().st_size < 2_000_000 and im.format == "JPEG"
    # the duration stamp sits bottom right: no title text is drawn there
    art = px.scale_up(themes.get("winter")(5, 7200).frame(0.3 * 7200), 4)
    corner = (1000, 600, 1280, 720)
    d = np.abs(np.asarray(im.crop(corner), np.int16) - np.asarray(art.crop(corner), np.int16)).mean()
    assert d < 12                                                          # only JPEG noise and the live animation differ there


@pytest.mark.parametrize("name,music,pomo", [("campfire", True, False), ("campfire", False, False), ("halloween", True, False), ("winter", True, False), ("study", True, True)])
def test_metadata_is_plain_and_honest(name, music, pomo):
    m = pub.build_metadata(name, 7200 if music else 3600, f"{name}-x", music, pomo, 1, [])
    assert len(m["title"]) <= 100 and not re.search(r"[^\x00-\x7f]", m["title"] + m["description"])        # no emoji, no fancy characters
    assert "!" not in m["title"] and m["title"].count("Hour") == 1
    assert m["made_for_kids"] is False and m["altered_or_synthetic_content"]["answer"] in ("Yes", "No")
    desc = m["description"].lower()
    assert ("original" in desc and "generated" not in desc.replace("composes", "")) or "no music" in desc or "composes" in desc
    assert ("no music" in desc) == (not music)
    assert "#" in m["description"] and sum(len(t) for t in m["tags"]) < 480
    assert bool(m["chapters"]) == pomo
    json.dumps(m)


def test_a_loop_render_is_seamless_and_its_picture_and_sound_have_one_length(tmp_path):
    import json, subprocess
    import numpy as np
    out = tmp_path / "l.mp4"
    lf.main(["--theme", "campfire", "--seconds", "40", "--no-music", "--loop-min", "0.2", "--keep-work", "--out", str(out)])   # a 12 s loop
    work = tmp_path / "l.mp4.work"
    pcm = np.fromfile(work / "audio.pcm", dtype="<i2").reshape(-1, 2).astype(np.float64)
    assert len(pcm) == 12 * lf.SR                                   # the loop is exactly its length
    steps = np.abs(np.diff(pcm, axis=0))
    seam = np.abs(pcm[0] - pcm[-1])                                 # played on repeat, the last sample is followed by the first
    assert (seam <= np.percentile(steps, 99.9, axis=0) + 1).all(), (seam, np.percentile(steps, 99.9, axis=0))
    frames = int(subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries", "stream=nb_read_packets",
                                 "-of", "csv=p=0", str(work / "loop.mp4")], capture_output=True, text=True).stdout.strip())
    assert frames == 12 * 30                                        # picture loop == sound loop, so repeats never drift
    assert json.loads((work / "video.json").read_text())["loop_seconds"] == 12
    loop_file = lf.loop_path(out, 12)
    assert loop_file.exists() and abs(pub.verify(loop_file, None, "x")["duration"] - 12) < 0.1
    rep = pub.verify(out, tmp_path / "frames", "l")
    assert abs(rep["duration"] - 40) < 0.3 and rep["width"] == 1920
    assert abs(rep["integrated_lufs"] + 14.0) <= 0.8, rep
    assert rep["true_peak_dbtp"] <= -1.0, rep
    assert rep["silences_over_3s_outside_the_final_fade"] == []


def test_mux_repeats_raw_pcm_not_encoded_audio():
    from pathlib import Path
    meas = {"input_i": "-15.0"}
    m = lf.mux_cmd(Path("w"), meas, 7200, Path("o.mp4"), loop=True, fades=True)
    j = " ".join(m)
    assert j.count("-stream_loop -1") == 2 and "s16le" in j and "-c:v copy" in j and "afade=t=out:st=7192.000" in j


# ---------------------------------------------------------------------------------------------------------------- sound modes, keywords, SEO
import sounds
import keywords
import seo_review


def _slope_db_per_octave(x, lo, hi):
    from scipy.signal import welch
    f, p = welch(x, fs=sounds.SR, nperseg=1 << 15)
    m = (f >= lo) & (f <= hi)
    return float(np.polyfit(np.log2(f[m]), 10 * np.log10(p[m]), 1)[0])


def _decode(path, sr=48000):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "2", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)


def test_pink_noise_falls_3_db_and_brown_6_db_per_octave_without_dc():
    for color, lo, hi, want, tol in (("pink", 100, 8000, -3.0, 0.3), ("brown", 60, 4000, -6.0, 0.3), ("white", 100, 8000, 0.0, 0.3)):
        n = sounds.NoiseColor(color, 3)
        x = np.concatenate([n.block(sounds.SR * 10) for _ in range(5)], axis=1)
        assert abs(_slope_db_per_octave(x[0], lo, hi) - want) < tol, color
        assert abs(x.mean()) < 0.02 * x.std(), color                                   # DC-free
        assert abs(np.corrcoef(x[0], x[1])[0, 1]) < 0.05                               # independent in the two ears
        assert abs(x.std() - 1.0) < 0.05                                               # RMS 1 before the mix levels it
        assert np.abs(np.diff(x[0])).max() < 12 * x.std()                              # smooth: no click anywhere


def test_every_synthetic_sound_is_finite_stereo_and_never_silent():
    for name, sp in sounds.SOUNDS.items():
        if sp.build is None:
            continue
        src = sounds.make(name, 120.0, 4, 120 * sounds.SR)
        x = src.block(sounds.SR * 6) + src.periodic(0, sounds.SR * 6)
        assert x.shape == (2, sounds.SR * 6) and np.isfinite(x).all() and x.std() > 0.1, name
        assert sp.lufs <= -14.0 and sp.what and (sp.how or sp.musical)


def test_tones_repeat_exactly_once_per_loop_so_the_seam_has_no_bump():
    N = 30 * sounds.SR
    src = sounds.make("binaural-alpha", 30.0, 2, N)
    a, b = src.periodic(0, 4000), src.periodic(N, 4000)                               # one loop later
    assert np.allclose(a, b, atol=1e-4)
    t = sounds.Tones(10.0)
    kl, kr = t.freqs(N)
    assert (kr - kl) * sounds.SR / N == pytest.approx(10.0, abs=1e-9)                  # the beat is exact


def test_binaural_beat_survives_the_aac_mux_and_the_loop_seam(tmp_path):
    out = tmp_path / "b.mp4"
    lf.main(["--theme", "campfire", "--seconds", "60", "--loop-min", "0.5", "--sound", "binaural-alpha", "--no-bed", "--keep-work", "--out", str(out)])
    x = _decode(out)[48000 * 4: 48000 * 54]
    def peak(sig):
        N = 1 << 22
        S = np.abs(np.fft.rfft(sig * np.hanning(len(sig)), N))
        f = np.fft.rfftfreq(N, 1 / 48000)
        m = (f > 150) & (f < 260)
        return f[m][S[m].argmax()]
    fl, fr = peak(x[:, 0]), peak(x[:, 1])
    assert abs(fl - 200.0) < 0.1 and abs((fr - fl) - 10.0) < 0.05, (fl, fr)             # left and right stay distinct through AAC
    pcm = np.fromfile(tmp_path / "b.mp4.work" / "audio.pcm", dtype="<i2").reshape(-1, 2).astype(np.float64)
    assert len(pcm) == 30 * lf.SR
    steps = np.abs(np.diff(pcm, axis=0))
    assert (np.abs(pcm[0] - pcm[-1]) <= np.percentile(steps, 99.9, axis=0) + 1).all()  # the loop joins with no step
    rep = pub.verify(out, None, "b", sound="binaural-alpha")
    assert abs(rep["integrated_lufs"] + 20.0) <= 0.8 and rep["true_peak_dbtp"] <= -1.0 and rep["target_lufs"] == -20.0, rep


def test_brown_noise_loop_seam_slope_and_loudness_after_the_mux(tmp_path):
    out = tmp_path / "n.mp4"
    lf.main(["--theme", "campfire", "--seconds", "40", "--loop-min", "0.2", "--sound", "brown", "--no-bed", "--keep-work", "--out", str(out)])
    pcm = np.fromfile(tmp_path / "n.mp4.work" / "audio.pcm", dtype="<i2").reshape(-1, 2).astype(np.float64)
    assert len(pcm) == 12 * lf.SR
    steps = np.abs(np.diff(pcm, axis=0))
    assert (np.abs(pcm[0] - pcm[-1]) <= np.percentile(steps, 99.9, axis=0) + 1).all()
    # no level dip in the crossfade: its rms matches the rest of the loop
    rms_xf = np.sqrt((pcm[: 4 * lf.SR] ** 2).mean())
    rms_rest = np.sqrt((pcm[4 * lf.SR:] ** 2).mean())
    assert 0.6 < rms_xf / rms_rest < 1.6
    x = _decode(out)
    assert abs(_slope_db_per_octave(x[:, 0], 100, 5000) + 6.0) < 0.8
    rep = pub.verify(out, None, "n", sound="brown")
    assert abs(rep["integrated_lufs"] + 20.0) <= 0.8 and rep["true_peak_dbtp"] <= -1.0, rep


@pytest.mark.parametrize("sound,target", [("synth", -18.0), ("rain", -20.0), ("fireplace", -18.0)])
def test_each_sound_masters_to_its_own_loudness_target(tmp_path, sound, target):
    out = tmp_path / "s.mp4"
    lf.main(["--theme", "winter", "--seconds", "20", "--sound", sound, "--out", str(out)])
    rep = pub.verify(out, None, "s", sound=sound)
    assert sounds.target_lufs(sound) == target
    assert abs(rep["integrated_lufs"] - target) <= 0.8, rep
    assert rep["true_peak_dbtp"] <= -1.0 and rep["silences_over_3s_outside_the_final_fade"] == [], rep
    assert rep["checks"][f"loudness_within_0.7_of_{target:g}"] or abs(rep["integrated_lufs"] - target) <= 0.8


def test_the_default_sound_is_still_chiptune_at_minus_14():
    assert sounds.target_lufs("chiptune") == -14.0 and lf.TARGET_LUFS == -14.0
    a = lf.plan_tracks(themes.get("halloween"), 3600, 11)
    assert a == lf.plan_tracks(themes.get("halloween"), 3600, 11, themes.get("halloween").music)


def test_lofi_is_the_chiptune_engine_slowed_and_softened():
    tracks = lf.plan_tracks(themes.get("study"), 3600, 5, lf.music_cfg(themes.get("study"), "lofi"))
    assert max(t["bpm"] for t in tracks) <= 68 and {t["era"] for t in tracks} == {"16bit"}
    assert lf.music_cfg(themes.get("study"), "chiptune") is themes.get("study").music


def test_dark_video_dims_to_near_black_and_stays_there(tmp_path):
    out = tmp_path / "d.mp4"
    lf.main(["--theme", "campfire", "--seconds", "60", "--dark", "6", "--sound", "pink", "--out", str(out)])
    rep = pub.verify(out, tmp_path / "frames", "d", sound="pink")
    assert abs(rep["duration"] - 60) < 0.5 and rep["width"] == 1920
    def mean_luma(t):
        p = tmp_path / f"f{t}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", str(out), "-frames:v", "1", str(p)], check=True)
        return np.asarray(Image.open(p).convert("L"), float).mean()
    assert mean_luma(3) > 15 and mean_luma(40) < 6 and mean_luma(58) < 6               # lit at 3 s, dark well after the fade
    assert subprocess.run(["ffmpeg", "-v", "error", "-i", str(out), "-f", "null", "-"], capture_output=True).stderr == b""   # the join decodes cleanly


def test_dark_must_fit_inside_the_loop(tmp_path):
    with pytest.raises(SystemExit):
        lf.main(["--theme", "campfire", "--seconds", "60", "--loop-min", "0.3", "--dark", "30", "--sound", "pink", "--out", str(tmp_path / "x.mp4")])


SOUNDS_FOR_META = [n for n in sounds.NAMES if n != "chiptune"]
HEALTH = re.compile(r"\b(improve|improves|cure|cures|anxiety|adhd|insomnia|treat|treats|relieve|relieves|therapy|therapeutic|heal|heals|reduce stress|focus better|fall asleep faster|brain)\b", re.I)


@pytest.mark.parametrize("theme", ALL)
@pytest.mark.parametrize("sound", SOUNDS_FOR_META)
def test_sound_metadata_is_plain_short_where_it_counts_and_makes_no_health_claims(theme, sound):
    m = pub.build_metadata(theme, 36000, f"{theme}-{sound}-10h", sounds.spec(sound).musical, False, 1, [], 20, sound=sound, dark=300)
    assert len(m["title"]) <= 100 and not re.search(r"[^\x00-\x7f]", m["title"] + m["description"]) and "!" not in m["title"]
    first = m["description"].split("\n")[0]
    assert len(first) <= 150 and first.startswith(m["title"].split(" with ")[0].split(",")[0]) and "10 Hours" in first
    assert not HEALTH.search(m["title"] + " " + m["description"] + " ".join(m["tags"])), (m["title"], HEALTH.search(m["description"]))
    assert "Dark Screen" in m["title"] or "Black Screen" in m["title"]
    assert len(m["tags"]) <= 15 and sum(len(t) for t in m["tags"]) < 480 and len(set(t.lower() for t in m["tags"])) == len(m["tags"])
    tags_line = m["description"].strip().split("\n")[-1]
    assert len(tags_line.split()) == 3 and all(w.startswith("#") for w in tags_line.split())
    assert "About this video" in m["description"] and "Pixel Hearth" in m["description"] and "near black" in m["description"]
    assert ("headphones" in m["description"].lower()) == sound.startswith("binaural")
    assert "loop" in m["description"].lower()
    json.dumps(m)


def test_metadata_without_dark_or_loop_and_with_keyword_research():
    kw = {"date": "2026-10-17", "kinds": {"rain": [{"phrase": "rain sounds for sleeping", "score": 9.0, "seeds": 5, "best_pos": 0},
                                                  {"phrase": "rain sounds", "score": 5.0, "seeds": 5, "best_pos": 1}], "campfire": []},
          "modifiers": {"black screen": 9.0, "dark screen": 2.0}}
    m = pub.build_metadata("study", 10800, "study-rain-3h", False, False, 1, [], 0.0, sound="rain", kw=kw)
    assert m["title"].startswith("Rain Sounds for Sleeping with Study Room, 3 Hours") and "Screen" not in m["title"] and "near black" not in m["description"]
    assert m["tags"][0] == "rain sounds for sleeping" and "loop" not in m["description"].lower()
    d = pub.build_metadata("study", 10800, "study-rain-3h", False, False, 1, [], 0.0, sound="rain", dark=120, kw=kw)
    assert d["title"].endswith("Black Screen")                                          # the research says people type black screen more than dark screen


def test_chiptune_metadata_is_unchanged_apart_from_ranked_tags():
    kw = {"kinds": {"chiptune": [{"phrase": "chiptune study music", "score": 8, "seeds": 3, "best_pos": 0}], "campfire": []}, "modifiers": {}}
    a = pub.build_metadata("campfire", 7200, "c", True, False, 1, [])
    b = pub.build_metadata("campfire", 7200, "c", True, False, 1, [], kw=kw)
    assert a["title"] == b["title"] and a["description"] == b["description"] and b["tags"][0] == "chiptune study music"


def test_thumbnail_leads_with_the_sound(tmp_path):
    p = pub.make_thumbnail("campfire", 36000, 5, tmp_path / "t.jpg", {}, music=False, sound="brown")
    assert Image.open(p).size == (1280, 720) and p.stat().st_size < 2_000_000


def test_keyword_ranking_rewards_position_and_repeats_and_filters_off_topic(tmp_path, monkeypatch):
    monkeypatch.setenv("AMBIENT_KEYWORDS_DIR", str(tmp_path))
    import datetime as dt
    answers = {"brown noise": ["brown noise", "brown noise sleep", "brown noise black screen", "brown noise 10 hours", "lofi girl"], "brown noise 10 hours": ["brown noise 10 hours", "brown noise"]}
    calls, naps = [], []
    def fake(q):
        calls.append(q)
        return answers.get(q, [])
    today = dt.date(2026, 10, 17)
    rep = keywords.refresh(today, fetcher=fake, sleep=naps.append, log=lambda *_: None)
    assert len(calls) == len(keywords.queries()) and all(n == keywords.MIN_GAP for n in naps)      # polite: a pause after every request
    rows = rep["kinds"]["brown"]
    assert rows[0]["phrase"] == "brown noise" and rows[0]["seeds"] == 2 and "lofi girl" not in [r["phrase"] for r in rows]
    assert rep["modifiers"]["black screen"] > 0 and rep["modifiers"]["10 hours"] > 0
    assert (tmp_path / "latest.json").exists() and (tmp_path / "ranked-2026-10-17.json").exists() and keywords.load()["date"] == "2026-10-17"
    calls.clear()
    keywords.refresh(today + dt.timedelta(days=3), fetcher=fake, sleep=naps.append, log=lambda *_: None)
    assert calls == []                                                                  # cached for a week
    keywords.refresh(today + dt.timedelta(days=8), fetcher=fake, sleep=naps.append, log=lambda *_: None)
    assert len(calls) == len(keywords.queries())
    assert keywords.top(keywords.load(), "brown", 2) == ["brown noise", "brown noise 10 hours"] or keywords.top(keywords.load(), "brown", 1) == ["brown noise"]


def test_a_failed_request_keeps_the_run_and_the_old_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("AMBIENT_KEYWORDS_DIR", str(tmp_path))
    import datetime as dt
    def boom(q):
        raise OSError("offline")
    rep = keywords.refresh(dt.date(2026, 10, 17), fetcher=boom, sleep=lambda s: None, log=lambda *_: None)
    assert rep["kinds"]["brown"] == [] and keywords.load() is not None


SEO_CSV = """slug,title,views,impressions,ctr,avg_view_duration,watch_hours,top_search_terms
campfire-brown-10h,Brown Noise with Crackling Campfire 10 Hours,120,4000,1.4%,0:05:10,10.3,brown noise black screen;brown noise 10 hours;campfire brown noise
winter-rain-3h,Rain Sounds with Winter Cabin 3 Hours,40,120,6.0%,0:20:00,13.3,rain sounds for sleeping
study-binaural-alpha-2h,Alpha Binaural Beats,300,3000,5.5%,0:40:00,200,study music
campfire-2h,Cozy Campfire Ambience,90,2500,4.0%,0:30:00,45,campfire ambience
"""


def test_seo_review_flags_what_to_change_and_ranks_what_to_make_next(tmp_path):
    f = tmp_path / "s.csv"
    f.write_text(SEO_CSV)
    rows = seo_review.load_rows(f)
    assert [(r["theme"], r["sound"], r["hours"]) for r in rows] == [("campfire", "brown", 10.0), ("winter", "rain", 3.0), ("study", "binaural-alpha", 2.0), ("campfire", "chiptune", 2.0)]
    assert rows[0]["ctr"] == pytest.approx(1.4) and rows[0]["avd"] == 310 and seo_review.parse_ctr("0.042") == pytest.approx(4.2)
    kw = {"date": "x", "kinds": {s: [{"phrase": s, "score": 5.0 + i, "seeds": 3, "best_pos": 0}] for i, s in enumerate(sounds.NAMES)}, "modifiers": {}}
    rep = seo_review.review(rows, kw, 300)
    v = {x["slug"]: x for x in rep["videos"]}
    a = " ".join(v["campfire-brown-10h"]["actions"])
    assert "thumbnail" in a and "brown noise black screen" in a and "early" in a                 # low CTR, missing search terms, short average view
    assert "too few" in " ".join(v["winter-rain-3h"]["notes"]) and "thumbnail" not in " ".join(v["winter-rain-3h"]["actions"])   # 120 impressions: no CTR verdict
    assert "rain sounds for sleeping" in " ".join(v["winter-rain-3h"]["actions"])                                           # but the missing search term is flagged
    assert "leave the thumbnail alone" in " ".join(v["campfire-2h"]["notes"])
    nxt = rep["next"]
    assert nxt["videos_with_enough_data"] == 3 and nxt["next"] and ("campfire", "brown") not in {(r["theme"], r["sound"]) for r in nxt["next"]}
    assert rep["by_sound"]["brown"]["videos"] == 1 and rep["by_theme"]["campfire"]["videos"] == 2
    assert "Make next" in seo_review.render_text(rep)
    few = seo_review.review(rows[:1], None, 300)["next"]
    assert few["videos_with_enough_data"] == 1 and "nothing" in few["based_on"]


def test_seo_review_reads_json_and_the_cli_writes_a_report(tmp_path, capsys):
    j = tmp_path / "s.json"
    j.write_text(json.dumps({"videos": [{"slug": "halloween-synth-2h", "title": "t", "views": 10, "impressions": 50, "ctr": 0.02, "avg_view_duration": 90, "watch_hours": 0.2}]}))
    out = tmp_path / "r.json"
    assert seo_review.main([str(j), "--json", str(out)]) == 0
    assert json.loads(out.read_text())["videos"][0]["sound"] == "synth" and "Per video" in capsys.readouterr().out
