"""The Pomodoro chime: right moments, never clips, same result however the audio is chunked, and genuinely pitchless."""
import numpy as np

import chime

SR = chime.SR


def test_boundaries_follow_the_timer_clock():
    found = chime.boundaries_between(0, 3600)
    assert [(round(b), k) for b, k in found] == [(0, "focus"), (1500, "break"), (1800, "focus"), (3300, "break")]
    assert chime.boundaries_between(1, 1499) == []                         # nothing in the middle of a block


def test_chimes_are_quiet_finite_and_end_cleanly():
    for kind in ("break", "focus"):
        audio, duck = chime.make_chime(kind)
        assert audio.shape[0] == 2 and np.isfinite(audio).all() and np.abs(audio).max() <= 0.2
        assert abs(audio[:, -1]).max() < 1e-3 and duck[-1] == 1.0          # no click at the end, the music is fully back
        assert abs(audio[:, :20]).max() < 0.02                               # a soft mallet: no click at the start
        assert 0.7 < duck.min() < 0.8                                        # a dip of about 2.5 dB


def test_the_partials_are_inharmonic_so_there_is_no_pitch():
    # every ratio is well away from a whole number (the fundamental itself, 1.0, is the reference)
    for r in chime.RATIOS[1:]:
        assert min(r % 1, 1 - r % 1) > 0.2


def test_the_chime_lands_on_the_exact_sample_and_the_music_dips_under_it():
    t0 = 1_000_000 * 1800.0 + 1450.0                                        # the stream began 50 s before a break boundary
    boundary_sample = 50 * SR
    music = np.full((2, 5 * SR), 0.9, dtype=np.float32)
    ch = chime.Chimer(t0)
    out = np.concatenate([ch.mix(music[:, i:i + SR // 2], boundary_sample - 2 * SR + i) for i in range(0, music.shape[1], SR // 2)], axis=1)
    start = 2 * SR                                                          # where the boundary falls inside this 5 s window
    assert np.allclose(out[:, :start - 5], 0.9)                             # untouched before the boundary
    assert abs(out[0, start + 5] - 0.9) < 0.02                              # the strike has barely begun
    assert out[0, start + int(0.3 * SR)] < 0.9 * 0.85                       # the music has dipped
    assert out.max() <= 1.0                                                 # a full-scale-ish music peak plus the chime never clips


def test_chunk_size_does_not_change_the_result():
    t0 = 1_000_000 * 1800.0 + 1498.0
    music = (np.random.default_rng(1).standard_normal((2, 6 * SR)) * 0.1).astype(np.float32)
    def run(size):
        ch = chime.Chimer(t0)
        return np.concatenate([ch.mix(music[:, i:i + size], i) for i in range(0, music.shape[1], size)], axis=1)
    assert np.allclose(run(SR // 2), run(4410 + 7), atol=1e-6)


def test_disabled_chimer_is_a_pass_through():
    x = np.ones((2, 100), dtype=np.float32)
    assert chime.Chimer(0.0, enabled=False).mix(x, 0) is x
