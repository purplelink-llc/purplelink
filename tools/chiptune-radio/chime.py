"""A soft chime at each Pomodoro boundary, so nobody has to watch the clock.

Two sounds, both inharmonic bell tones (the partials of a struck bar or a singing bowl: about 1, 2.76, 5.40, 8.45 times a base
frequency). Because the partials are not whole-number multiples they carry no clear pitch, so the chime is pleasant but
atonal and cannot clash with whatever key the music is in.

    break  : one slow, warm strike with a long tail. "Put it down and rest."
    focus  : two quick, brighter strikes. "Back to work."

The boundaries come from the same clock as the on-screen timer (`t0_wall + stream seconds`), so the sound lands on the
exact second the timer flips. The music dips about 2.5 dB under each chime, which keeps it clear without clipping.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.signal import butter, sosfilt

import scene as sc
import voices as V

SR = 44100
CYCLE = sc.FOCUS + sc.BREAK                      # 1800 s: :00 to :25 focus, :25 to :30 break
BOUNDARIES = {"break": sc.FOCUS, "focus": 0}     # seconds into the cycle at which each chime fires
RATIOS = (1.0, 2.756, 5.404, 8.45)               # a struck bar's first partials, the last nudged off 8.933 (nearly a whole 9) so none sit on a harmonic: pitchless
AMPS = (1.0, 0.55, 0.28, 0.12)
PEAK = {"break": 0.17, "focus": 0.19}            # about -15 dBFS peak: heard as a cue, never as a jolt
DUCK_DEPTH = 0.25                                # the music drops to 75% under a chime


def _bell(base: float, taus: tuple, dur: float, strike_ms: float = 9.0) -> np.ndarray:
    """One struck bell, stereo. A second copy of each partial, detuned a hair and sent to the other ear, gives the slow
    shimmer of a real bowl and a little width."""
    t = np.arange(int(dur * SR)) / SR
    left, right = np.zeros_like(t), np.zeros_like(t)
    for r, a, tau in zip(RATIOS, AMPS, taus):
        f = base * r
        decay = np.exp(-t / tau)
        left += a * np.sin(2 * np.pi * f * t) * decay
        left += 0.6 * a * np.sin(2 * np.pi * (f + 1.3 * math.sqrt(r)) * t + 0.9) * decay
        right += a * np.sin(2 * np.pi * (f + 0.7) * t + 0.4) * decay
        right += 0.6 * a * np.sin(2 * np.pi * (f - 1.1 * math.sqrt(r)) * t + 1.7) * decay
    soft = 1 - np.exp(-t / (strike_ms / 1000))                       # a soft mallet, not a click
    out = np.stack([left * soft, right * soft])
    return out / (np.abs(out).max() + 1e-9)


def make_chime(kind: str) -> tuple[np.ndarray, np.ndarray]:
    """(audio of shape (2, n) float32, the music's gain over the same n samples)."""
    if kind == "break":
        body = _bell(330.0, (3.4, 2.1, 1.2, 0.6), 8.0)
    elif kind == "focus":
        first = _bell(494.0, (2.2, 1.4, 0.8, 0.4), 5.0)
        out = np.zeros((2, int(5.9 * SR)))
        out[:, : first.shape[1]] += first
        gap = int(0.85 * SR)
        out[:, gap: gap + first.shape[1]] += 0.8 * first               # the second strike, a touch softer
        body = out / (np.abs(out).max() + 1e-9)
    else:
        raise ValueError(f"unknown chime {kind!r}")
    n = body.shape[1]
    wet = V.reverb(np.pad(body, ((0, 0), (0, int(1.5 * SR)))).astype(np.float32), V.make_ir(1.6, 11))
    body = np.pad(body, ((0, 0), (0, wet.shape[1] - n))) + 0.28 * wet
    body = sosfilt(butter(2, 6500, "lowpass", fs=SR, output="sos"), body, axis=1)
    body = (body / (np.abs(body).max() + 1e-9) * PEAK[kind]).astype(np.float32)
    # the music dips quickly, holds while the strike is loud, then comes back over about two seconds
    m = body.shape[1]
    tt = np.arange(m) / SR
    duck = 1 - DUCK_DEPTH * np.clip(tt / 0.06, 0, 1) * np.exp(-np.clip(tt - 0.5, 0, None) / 1.6)
    duck = duck.astype(np.float32)
    tail = int(0.4 * SR)
    duck[-tail:] = np.linspace(duck[-tail], 1.0, tail, dtype=np.float32)    # land on exactly 1.0, so there is no step when the chime ends
    return body, duck


def boundaries_between(wall_start: float, wall_end: float) -> list[tuple[float, str]]:
    """Every chime that should sound in [wall_start, wall_end), as (wall time, kind)."""
    found = []
    for kind, off in BOUNDARIES.items():
        b = math.ceil((wall_start - off) / CYCLE) * CYCLE + off
        while b < wall_end:
            found.append((b, kind))
            b += CYCLE
    return sorted(found)


class Chimer:
    """Mixes the chimes into the audio as it streams. Feed it every chunk, in order, with the number of samples written so far."""

    def __init__(self, t0_wall: float, enabled: bool = True):
        self.t0 = t0_wall
        self.enabled = enabled
        self.sounds = {k: make_chime(k) for k in BOUNDARIES} if enabled else {}
        self.active: list[list] = []                      # [kind, position in the chime's samples, offset into the chunk]

    def mix(self, chunk: np.ndarray, written: int) -> np.ndarray:
        if not self.enabled:
            return chunk
        n = chunk.shape[1]
        w0, w1 = self.t0 + written / SR, self.t0 + (written + n) / SR
        for b, kind in boundaries_between(w0, w1):
            self.active.append([kind, 0, int(round((b - self.t0) * SR)) - written])
        if not self.active:
            return chunk
        out = np.array(chunk, dtype=np.float32, copy=True)
        keep = []
        for entry in self.active:
            kind, pos, off = entry
            audio, duck = self.sounds[kind]
            start = max(0, off)                           # where in this chunk it begins sounding
            take = min(audio.shape[1] - pos, n - start)
            if take > 0:
                out[:, start:start + take] = out[:, start:start + take] * duck[pos:pos + take] + audio[:, pos:pos + take]
                entry[1] = pos + take
            entry[2] = 0                                  # after the first chunk it simply continues from the start
            if entry[1] < audio.shape[1]:
                keep.append(entry)
        self.active = keep
        return out
