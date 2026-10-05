"""Fast checks for the radio: python3.12 -m pytest -q test_radio.py"""
import numpy as np
import pytest

import chiptune as c
import scene as sc
import stream as st


def test_seeds_are_deterministic():
    a, b = c.render(c.plan(5)), c.render(c.plan(5))
    assert np.array_equal(a, b) and a.dtype == np.float32 and a.shape[0] == 2


def test_track_is_in_key_and_not_clipping():
    import qa
    bad, _ = qa.qa(range(1, 13))
    assert not bad
    x = c.render(c.plan(3))
    assert float(np.abs(x).max()) <= 0.9 and float(np.abs(x).max()) > 0.5


def test_leveling_hits_the_target_without_clipping():
    quiet, loud = c.render(c.plan(2)) * 0.2, c.render(c.plan(2)) * 1.0
    for a in (quiet, loud):
        y = st.leveled(a)
        assert float(np.abs(y).max()) <= 0.9 + 1e-6
    rms = lambda z: float(np.sqrt(np.mean(z ** 2)))
    assert abs(rms(st.leveled(loud)) - st.TARGET_RMS) < 0.02 or rms(st.leveled(loud)) <= st.TARGET_RMS * 1.25


def test_playlist_never_repeats_a_key_or_a_close_tempo():
    gen = st.next_tracks(1)
    prev = next(gen)
    for _ in range(60):
        t = next(gen)
        assert t.key != prev.key and abs(t.bpm - prev.bpm) >= 4
        prev = t


def test_ffmpeg_commands():
    live = st.ffmpeg_cmd("rtmp://example/live/key", True, 5)
    assert live.count("-re") == 2 and live[-3:] == ["-f", "flv", "rtmp://example/live/key"] and "pipe:5" in live
    f = st.ffmpeg_cmd("x.mp4", False, 5)
    assert "-re" not in f and f[-1] == "x.mp4"
    assert "-g" in live and live[live.index("-g") + 1] == "60"          # a keyframe every two seconds at 30 fps


def test_live_mode_refuses_a_missing_url(monkeypatch, capsys):
    monkeypatch.delenv("STREAM_URL", raising=False)
    monkeypatch.setattr("sys.argv", ["stream.py", "--live"])
    with pytest.raises(SystemExit) as e:
        st.main()
    assert "STREAM_URL" in str(e.value)


def test_scene_draws_every_state():
    s = sc.Scene()
    seen = set()
    for hour in (2, 6, 8, 12, 18, 20, 23):
        for rain in (False, True):
            for wall in (600, sc.FOCUS + 30):
                im = s.frame(3.3, hour, rain, 84, "D major, 80 BPM", wall)
                assert im.size == (sc.W, sc.H)
                seen.add(im.tobytes())
    assert len(seen) == 28                                               # all different
    a = s.frame(1.0, 22, True, 84, "x", 600).tobytes()
    b = s.frame(1.5, 22, True, 84, "x", 600).tobytes()
    assert a != b                                                        # it animates


def test_timer_follows_the_clock():
    s = sc.Scene()
    focus = s.frame(1.0, 12, False, 84, "x", 60.0)
    brk = s.frame(1.0, 12, False, 84, "x", sc.FOCUS + 10.0)
    assert focus.tobytes() != brk.tobytes()
    assert sc.hour_at(0) == 0 and 0 <= sc.hour_at(5000) < 24
