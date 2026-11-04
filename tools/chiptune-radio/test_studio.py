"""Tests for studio.py (Apple sampled instruments behind the composer). The pure-Python parts run anywhere; the ones that call aurender or
read the GarageBand library skip on machines without them (Linux CI)."""
import copy
import shutil

import numpy as np
import pytest

import chiptune as c
import longform_pub as lp
import studio as S
from themes.racer import Racer

HAVE_LIB = S.LOGIC.is_dir() and S.KITS.is_dir()
HAVE_SWIFT = shutil.which("swiftc") is not None
needs_lib = pytest.mark.skipif(not HAVE_LIB, reason="no Logic/GarageBand library on this machine")
needs_host = pytest.mark.skipif(not (HAVE_LIB and HAVE_SWIFT), reason="needs swiftc and the Logic library")
BASS = "02 Bass/02 Electric Bass/Fingerstyle Electric Bass.exs"


def test_midi_events_sorted_with_offs_first_and_velocity_range():
    notes = [(1.0, 0.5, 40, 0.2, {}), (0.0, 1.0, 43, 1.0, {}), (1.0, 0.5, 47, 0.6, {})]
    rows = S.midi_events(notes, latency=0)
    assert rows == sorted(rows, key=lambda r: (r[0], 0 if r[1] == 0x80 else 1, r[2]))
    vels = [r[3] for r in rows if r[1] == 0x90]
    assert min(vels) >= 30 and max(vels) == 127                     # the loudest note of the channel hits 127
    at = [r for r in rows if r[0] == S.SR]                          # frame 1.0 s: 43 ends, 40 and 47 start
    assert [r[1] for r in at] == [0x80, 0x90, 0x90]


def test_same_pitch_overlap_releases_the_earlier_note():
    rows = S.midi_events([(0.0, 2.0, 40, 1.0, {}), (1.0, 0.5, 40, 1.0, {})], latency=0)
    offs = sorted(r[0] for r in rows if r[1] == 0x80)
    assert offs == [S.SR, int(1.5 * S.SR)]                            # the first note ends where the second starts, not at 2.0 s


def test_latency_shifts_notes_early_but_not_before_zero():
    rows = S.midi_events([(0.0, 0.5, 40, 1.0, {}), (1.0, 0.5, 41, 1.0, {})], latency=500)
    ons = [r[0] for r in rows if r[1] == 0x90]
    assert ons == [0, S.SR - 500]


def test_out_of_range_notes_are_dropped():
    assert S.midi_events([(0.0, 0.5, 130, 1.0, {})], latency=0, transpose=0) == []


def test_level_sets_loud_rms_and_leaves_silence_alone():
    x = np.zeros((2, S.SR), np.float32)
    assert S.level(x, 0.1) is x
    x[:, : S.SR // 2] = 0.5
    y = S.level(x, 0.1)
    assert abs(float(np.sqrt((y[:, : S.SR // 2] ** 2).mean())) - 0.1) < 1e-3


@needs_lib
def test_drum_map_hits_exist_in_the_racer_kit():
    kit = Racer.music["sound"]["studio"]["drums"]["kit"]
    for name in ("Kick_1", "Snare_1", "Snare_3", "Hi-Hat_1", "Hi-Hat_Open", "Tom_High", "Tom_Mid", "Tom_Low"):
        assert S.hit(kit, name).shape[0] == 2


@needs_lib
def test_closed_hat_chokes_an_open_hat():
    kit = "Silverlake GB"
    open_only = S.drum_stem(kit, "hat", [(0.0, 0.3, 0, 1.0, {})], S.SR)
    choked = S.drum_stem(kit, "hat", [(0.0, 0.3, 0, 1.0, {}), (0.1, 0.05, 0, 1.0, {})], S.SR)
    closed = S.hit(kit, "Hi-Hat_1").shape[1]
    tail = slice(int(0.1 * S.SR) + closed + 10, int(0.1 * S.SR) + closed + 2000)
    assert np.abs(open_only[:, tail]).max() > 0 and np.abs(choked[:, tail]).max() == 0


@needs_lib
def test_racer_studio_instruments_exist():
    st = Racer.music["sound"]["studio"]
    for ch in ("bass", "pad"):
        assert (S.LOGIC / st[ch]["exs"]).is_file()


@needs_host
def test_aurender_is_deterministic_and_on_time():
    hits = [(1.0 + 37 / S.SR, 0.2, 40, 1.0, {}), (1.5 + 211 / S.SR, 0.2, 40, 1.0, {})]
    a = S.sampled_stem(BASS, hits, 3 * S.SR)
    b = S.sampled_stem(BASS, hits, 3 * S.SR)
    assert np.array_equal(a, b)
    env = np.abs(a).sum(0)
    onsets = []
    for s, *_ in hits:
        i = int(round(s * S.SR))
        w = env[i - 2000: i + 4000]
        onsets.append(int(np.argmax(w > w.max() * 0.05)) - 2000)
    assert onsets[0] == onsets[1]                                    # same delay for every note: sample-accurate, no block jitter


@needs_host
def test_long_sampled_notes_render_the_same_every_time():
    """The string pad's samples are long. With disk streaming on, an offline render outran the streaming thread and dropped parts of
    notes, differently on each run (and always near the start of a fresh process). aurender loads every sample into memory instead."""
    pad = Racer.music["sound"]["studio"]["pad"]
    chords = [(0.2 + 2.0 * k, 1.9, m, 1.0, {}) for k in range(4) for m in (52, 55, 59, 64)]
    runs = [S.sampled_stem(pad["exs"], chords, 9 * S.SR, pad["latency"]) for _ in range(3)]
    assert all(np.array_equal(runs[0], r) for r in runs[1:])


@needs_host
def test_missing_instrument_fails_loudly():
    with pytest.raises(FileNotFoundError):
        S.sampled_stem("nope/missing.exs", [(0.0, 0.1, 40, 1.0, {})], S.SR)


@needs_host
def test_studio_track_render_is_deterministic():
    def track():
        t = c.plan(313, era="synth", mood=0.85, mode_weights=Racer.music["modes"], style="racer")
        t.sound.update(copy.deepcopy(Racer.music["sound"]))
        return t
    assert np.array_equal(c.render(track()), c.render(track()))


def test_racer_description_admits_the_sampled_instruments():
    md = lp.build_metadata("racer", 7200, "music-to-run-to-2h", music=True, pomodoro=False, seed=313)
    assert "Nothing in this video is sampled" not in md["description"]
    assert "GarageBand and Logic sound library" in md["description"]


def test_chip_themes_keep_the_nothing_sampled_line():
    md = lp.build_metadata("campfire", 7200, "campfire-2h", music=True, pomodoro=False, seed=1)
    assert "Nothing in this video is sampled" in md["description"]
