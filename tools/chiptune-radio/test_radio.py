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


def test_playlist_never_repeats_a_key_and_the_tempo_drifts_gently():
    gen = st.next_tracks(1)
    prev = next(gen)
    for _ in range(60):
        t = next(gen)
        assert t.key != prev.key and abs(t.bpm - prev.bpm) <= st.MAX_BPM_STEP
        prev = t


def test_mood_wave_is_smooth_and_covers_lofi_to_boss():
    waves = [st.mood_at(n) for n in range(2 * st.MOOD_TRACKS)]
    assert min(waves) < 0.05 and max(waves) > 0.95
    assert all(abs(a - b) < 0.2 for a, b in zip(waves, waves[1:]))      # no sudden jump between neighbouring tracks


def test_mood_sets_tempo_and_arpeggio_pace():
    calm, boss = c.plan(7, "16bit", 0.0), c.plan(7, "16bit", 1.0)
    assert calm.bpm < 66 < 90 < boss.bpm
    beat = lambda tr: 60.0 / tr.bpm
    arp = lambda tr: [d / beat(tr) for _, d, *_ in c.compose(tr)["arp"]]
    assert min(arp(calm)) >= 1.0 and min(arp(boss)) >= 0.5               # sustained notes, not 16th-note plinks


def test_melody_is_legato_and_instruments_do_not_click():
    t = c.plan(7, "16bit", 0.2)
    lead = sorted(c.compose(t)["lead"], key=lambda n: n[0])
    beat = 60.0 / t.bpm
    gaps = [lead[i + 1][0] - (lead[i][0] + lead[i][1]) for i in range(len(lead) - 1)]
    assert sum(g > 0.03 for g in gaps) / len(gaps) < 0.35                # most notes run into the next
    import voices as V
    e = V.env(int(0.5 * V.RATE), a=0.001, d=0.0, s=1.0, rel=0.005)       # asks for a 1 ms attack and a 5 ms release
    assert e[:int(V.MIN_ATTACK * V.RATE) // 2].max() < 0.6 and e[-int(V.MIN_RELEASE * V.RATE) // 2:].max() < 0.6


def test_ffmpeg_commands():
    live = st.ffmpeg_cmd("rtmp://example/live/key", True, 5)
    assert live.count("-re") == 2 and live[-3:] == ["-f", "flv", "rtmp://example/live/key"] and "pipe:5" in live
    f = st.ffmpeg_cmd("x.mp4", False, 5)
    assert "-re" not in f and f[-1] == "x.mp4"
    assert "-g" in live and live[live.index("-g") + 1] == "60"          # a keyframe every two seconds at 30 fps
    assert "scale=1920:1080:flags=neighbor" in " ".join(live)           # 1080p, an exact 6x upscale of the 320x180 scene
    for flag in ("-b:v", "-minrate", "-maxrate"):
        assert live[live.index(flag) + 1] == "2500k"                    # constant bitrate, so the platform never sees it dip below the target
    assert "nal-hrd=cbr:force-cfr=1:rc-lookahead=10" in live and live[live.index("-threads") + 1] == "4"
    small = st.ffmpeg_cmd("x.mp4", False, 5, size=(1280, 720), kbps=1500, preset="ultrafast")
    assert "scale=1280:720:flags=neighbor" in " ".join(small) and small[small.index("-b:v") + 1] == "1500k" and "ultrafast" in small


def test_live_mode_refuses_a_missing_url(monkeypatch, capsys):
    monkeypatch.delenv("STREAM_URL", raising=False)
    monkeypatch.setattr("sys.argv", ["stream.py", "--live"])
    with pytest.raises(SystemExit) as e:
        st.main()
    assert "STREAM_URL" in str(e.value)


def test_scene_scales_to_exact_squares():
    assert all(w % sc.W == 0 and h % sc.H == 0 and w // sc.W == h // sc.H for w, h in ((1920, 1080), (3840, 2160), (1280, 720)))


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


def test_pinned_era_changes_sound_not_notes():
    import chiptune as c
    for era in ("8bit", "16bit", "synth", "hybrid"):
        t = c.plan(7, era)
        assert t.sound["era"] == era
    free, pinned = c.plan(7), c.plan(7, "synth")
    assert (free.key, free.bpm, free.mode) == (pinned.key, pinned.bpm, pinned.mode)


def test_era_cycle_persists_between_broadcasts(tmp_path, monkeypatch):
    import stream
    monkeypatch.setattr(stream, "STATE_FILE", str(tmp_path / "state"))
    seen = [stream.next_era() for _ in range(5)]
    assert seen == ["16bit", "8bit", "synth", None, "16bit"]
    assert stream.next_era(advance=False) == "8bit"
