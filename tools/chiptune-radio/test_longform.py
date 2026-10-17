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
