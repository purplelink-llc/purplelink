"""Synthesised ambience for the long-form videos: fire crackle, wind, rain, crickets, an owl, sleigh bells. Every sound is made from
noise and sine waves in code; nothing is recorded or downloaded, so there is nothing to license.

A `Bed` makes the sound in order, a block at a time, carrying every filter's state across blocks, so a two hour bed has no seams and
never needs the whole thing in memory.

    bed = Bed({"fire": 1.0, "wind": 0.5, "crickets": 0.3}, seconds=7200, seed=3, events=[(600.0, "owl", 6.0)])
    while ...: block = bed.block(44100 * 10)      # float32, shape (2, n)

Events (an owl, a log settling in the fire, a gust, sleigh bells) come from the same list the picture uses, so a hoot is heard when the owl is
seen.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi

SR = 44100
LAYERS = ("fire", "wind", "hollow_wind", "muffled_wind", "crickets", "rain", "room")
# measured RMS of each layer at level 1.0 was 0.047 (fire), 0.016, 0.009, 0.0095, 0.004 to 0.01 (crickets, which chirp in bursts), 0.09; these factors bring each to about 0.04 (crickets about 0.015) so a level of 1.0 means
# "the same loudness" for every layer and a theme can balance them by ear-sized numbers
CAL = {"fire": 0.85, "wind": 2.4, "hollow_wind": 4.2, "muffled_wind": 4.0, "crickets": 5.0, "rain": 0.45}


def _sos(kind: str, hz, order: int = 2):
    return butter(order, hz, kind, fs=SR, output="sos")


class _Filt:
    """A stateful stereo filter: process() keeps the filter memory between calls, so consecutive blocks join without a click."""

    def __init__(self, sos):
        self.sos = sos
        self.zi = [sosfilt_zi(sos) * 0.0 for _ in range(2)]

    def __call__(self, x: np.ndarray) -> np.ndarray:           # x: (2, n)
        out = np.empty_like(x)
        for ch in range(2):
            out[ch], self.zi[ch] = sosfilt(self.sos, x[ch], zi=self.zi[ch])
        return out


class _Mono:
    def __init__(self, sos):
        self.sos = sos
        self.zi = sosfilt_zi(sos) * 0.0

    def __call__(self, x: np.ndarray) -> np.ndarray:
        y, self.zi = sosfilt(self.sos, x, zi=self.zi)
        return y


def slow_envelope(rng: np.random.Generator, seconds: float, hz: float, lo: float, hi: float, smooth: int = 6) -> np.ndarray:
    """A smooth random curve between lo and hi, sampled `hz` times a second (used for gusts and for how busy the fire is)."""
    n = int(seconds * hz) + 4
    x = rng.random(n)
    k = np.hanning(smooth * 2 + 1)
    x = np.convolve(np.pad(x, smooth, mode="reflect"), k / k.sum(), mode="valid")[:n]
    x = (x - x.min()) / max(1e-9, (x.max() - x.min()))
    return lo + (hi - lo) * x


def _interp(env: np.ndarray, hz: float, start: int, n: int) -> np.ndarray:
    """The envelope at samples start..start+n, linearly interpolated."""
    pos = (start + np.arange(n)) / SR * hz
    return np.interp(pos, np.arange(len(env)), env).astype(np.float32)


def owl_hoot(duration: float = 5.0, pitch: float = 360.0) -> np.ndarray:
    """A soft great-horned-owl style call, hoo, hoo-hoo-hoo, made from a sine with a little breath and two echoes. Stereo float32."""
    n = int(duration * SR)
    mono = np.zeros(n, np.float32)
    rng = np.random.default_rng(5)
    for start, length, f in ((0.15, 0.55, pitch), (1.05, 0.28, pitch * 1.03), (1.5, 0.28, pitch * 1.01), (1.95, 0.6, pitch * 0.96)):
        m = int(length * SR)
        t = np.arange(m) / SR
        glide = f * (1.0 - 0.05 * t / length)
        ph = np.cumsum(glide) / SR * 2 * np.pi
        env = np.minimum(1.0, t / 0.07) * np.minimum(1.0, (length - t) / 0.12)
        tone = (np.sin(ph) + 0.28 * np.sin(2 * ph) + 0.08 * np.sin(3 * ph)) * env
        tone += 0.05 * rng.standard_normal(m) * env
        i = int(start * SR)
        mono[i:i + m] += tone[: n - i]
    mono = sosfilt(_sos("lowpass", 1400), mono).astype(np.float32)
    out = np.zeros((2, n), np.float32)
    for delay, gain, pan in ((0.0, 1.0, 0.45), (0.21, 0.35, 0.6), (0.47, 0.18, 0.7)):
        i = int(delay * SR)
        out[0, i:] += mono[: n - i] * gain * (1 - pan * 0.5)
        out[1, i:] += mono[: n - i] * gain * (0.5 + pan * 0.5)
    return out / (np.abs(out).max() + 1e-9) * 0.5


def sleigh_bells(duration: float = 14.0, seed: int = 4) -> np.ndarray:
    """A cluster of small bells shaken in a loose gallop, fading in and out and drifting from one ear to the other. No tune, just shimmer."""
    n = int(duration * SR)
    rng = np.random.default_rng(seed)
    out = np.zeros((2, n), np.float32)
    freqs = [2350.0, 2870.0, 3310.0, 3760.0, 4190.0]
    t = np.arange(int(0.5 * SR)) / SR
    bells = [sum(a * np.sin(2 * np.pi * f * r * t) for r, a in ((1.0, 1.0), (2.41, 0.5), (3.7, 0.25))) * np.exp(-t / 0.11) for f in freqs]
    hits = int(duration * 7)
    for k in range(hits):
        when = (k + rng.uniform(-0.25, 0.25)) / 7.0 + 0.1
        i = int(when * SR)
        b = bells[int(rng.integers(len(freqs)))] * rng.uniform(0.3, 1.0)
        m = min(len(b), n - i)
        if m <= 0:
            continue
        pos = when / duration
        env = math.sin(math.pi * min(1.0, pos)) ** 2                    # fades in and out across the pass
        pan = 1 - pos                                                    # right to left
        out[0, i:i + m] += (b[:m] * env * (1 - pan * 0.8)).astype(np.float32)
        out[1, i:i + m] += (b[:m] * env * (0.2 + pan * 0.8)).astype(np.float32)
    out = sosfilt(_sos("lowpass", 7000), out, axis=1).astype(np.float32)
    return out / (np.abs(out).max() + 1e-9) * 0.35


class Bed:
    """The ambience, block by block. `layers` maps a name in LAYERS to its level (about 1.0 is the natural level for that sound against the others).
    `events` are (seconds, kind, duration) with kind in owl, settle (a log shifts in the fire), gust, sleigh. `rain` is an optional
    list of (start, end) seconds when it rains; the rain fades in and out over 8 s."""

    BLOCK = SR * 10

    def __init__(self, layers: dict, seconds: float, seed: int = 1, events: list | None = None, rain: list | None = None):
        self.layers, self.seconds, self.events, self.rain = dict(layers), seconds, list(events or []), list(rain or [])
        self.rng = np.random.default_rng(seed * 7 + 1)
        self.pos = 0
        env_rng = np.random.default_rng(seed * 13 + 5)
        self.fire_busy = slow_envelope(env_rng, seconds + 30, 0.1, 0.55, 1.5, smooth=4)      # how lively the fire is, over minutes
        self.gust = slow_envelope(env_rng, seconds + 30, 0.25, 0.0, 1.0, smooth=6) ** 2        # gusts: mostly quiet, sometimes a swell
        self.gust2 = slow_envelope(env_rng, seconds + 30, 0.18, 0.0, 1.0, smooth=8) ** 2
        self.chirp_gate = slow_envelope(env_rng, seconds + 30, 0.08, 0.0, 1.0, smooth=5)
        self.pop_filters = [[_Mono(_sos("bandpass", (fc * 0.8, fc * 1.25), 2)) for fc in (1600.0, 2900.0, 4600.0)] for _ in range(2)]
        self.roar = _Filt(_sos("bandpass", (180.0, 2200.0), 1))
        self.rumble = _Filt(_sos("lowpass", 140.0, 2))
        self._wind_filters: dict = {}              # each wind variant keeps its own filter memory, so they can be mixed
        self.muffle = _Filt(_sos("lowpass", 260.0, 3))
        self.rain_hi = _Filt(_sos("bandpass", (900.0, 9000.0), 2))
        self.rain_mod = _Mono(_sos("lowpass", 25.0, 2))
        self.room = _Filt(_sos("lowpass", 600.0, 1))
        self._cache: dict = {}
        self.cricket_ph = self.rng.random(3) * 6.28

    # --------------------------------------------------------------------------------------------- one-shot sounds
    def _oneshot(self, kind: str):
        if kind not in self._cache:
            self._cache[kind] = {"owl": owl_hoot, "sleigh": sleigh_bells}[kind]()
        return self._cache[kind]

    def _events_into(self, out: np.ndarray, start: int, n: int, level: float) -> None:
        for when, kind, dur in self.events:
            i0 = int(when * SR)
            if kind in ("owl", "sleigh"):
                snd = self._oneshot(kind)
                lo, hi = max(start, i0), min(start + n, i0 + snd.shape[1])
                if hi > lo:
                    out[:, lo - start:hi - start] += snd[:, lo - i0:hi - i0] * (0.6 if kind == "owl" else 0.5)

    # --------------------------------------------------------------------------------------------- layers
    def _fire(self, start: int, n: int, lvl: float) -> np.ndarray:
        rng = self.rng
        busy = float(np.mean(_interp(self.fire_busy, 0.1, start, n)))
        rate = 9.0 * busy
        k = int(rng.poisson(rate * n / SR))
        idx = rng.integers(0, n, k)
        amp = rng.lognormal(-1.0, 0.9, k) * 0.22
        big = rng.random(k) < 0.012
        amp[big] *= 3.5
        # a log settling in the fire: a puff of pops and a soft thump
        for when, kind, dur in self.events:
            if kind == "settle" and start <= when * SR < start + n:
                j0 = int(when * SR) - start
                extra = rng.integers(j0, min(n, j0 + int(1.6 * SR)), 36)
                idx = np.concatenate([idx, extra])
                amp = np.concatenate([amp, rng.lognormal(-0.5, 0.7, 36) * 0.35])
        which = rng.integers(0, 3, len(idx))
        pan = rng.random(len(idx))
        out = np.zeros((2, n), np.float32)
        for ch in range(2):
            w = pan if ch else 1 - pan
            for r in range(3):
                train = np.zeros(n, np.float32)
                sel = which == r
                np.add.at(train, idx[sel], (amp[sel] * (0.4 + w[sel])).astype(np.float32))
                out[ch] += self.pop_filters[ch][r](train) * (14.0 / (1 + r))
        noise = rng.standard_normal((2, n)).astype(np.float32)
        flick = (0.6 + 0.4 * np.sin(np.arange(n) / SR * 2 * np.pi * rng.uniform(0.4, 1.3) + rng.uniform(0, 6))).astype(np.float32)
        out += self.roar(noise) * 0.10 * flick * busy
        out += self.rumble(rng.standard_normal((2, n)).astype(np.float32)) * 0.55 * busy
        for when, kind, dur in self.events:                                   # the thump of a settling log
            if kind == "settle" and start <= when * SR < start + n:
                j0 = int(when * SR) - start
                m = min(n - j0, int(0.5 * SR))
                tt = np.arange(m) / SR
                out[:, j0:j0 + m] += (np.sin(2 * np.pi * (70 - 25 * tt) * tt) * np.exp(-tt / 0.12) * 0.5).astype(np.float32)[None, :]
        return out * lvl

    def _wind(self, start: int, n: int, lvl: float, hollow: bool = False, muffled: bool = False) -> np.ndarray:
        rng = self.rng
        g1 = _interp(self.gust, 0.25, start, n)
        g2 = _interp(self.gust2, 0.18, start, n)
        for when, kind, dur in self.events:                                   # a planned gust swells over `dur` seconds
            if kind == "gust":
                i0 = int(when * SR)
                lo, hi = max(start, i0), min(start + n, i0 + int(dur * SR))
                if hi > lo:
                    x = (np.arange(lo, hi) - i0) / (dur * SR)
                    g1[lo - start:hi - start] = np.maximum(g1[lo - start:hi - start], (np.sin(np.pi * x) ** 2).astype(np.float32))
        variant = "hollow" if hollow else "muffled" if muffled else "plain"
        if variant not in self._wind_filters:
            self._wind_filters[variant] = (_Filt(_sos("bandpass", (90.0, 700.0), 2)), _Filt(_sos("bandpass", (820.0, 1150.0), 2)),
                                           [_Filt(_sos("bandpass", (fc * 0.93, fc * 1.07), 2)) for fc in (210.0, 330.0, 470.0)])
        wind_lo, wind_whistle, hollow_filters = self._wind_filters[variant]
        noise = rng.standard_normal((2, n)).astype(np.float32)
        if hollow:
            out = np.zeros((2, n), np.float32)
            for i, f in enumerate(hollow_filters):
                out += f(rng.standard_normal((2, n)).astype(np.float32)) * (g1 if i % 2 == 0 else g2)[None, :] * (0.9 + 0.1 * i) * 5.0
            out += wind_lo(noise) * (0.12 + 0.35 * g1)[None, :]
            return out * lvl * 0.25
        out = wind_lo(noise) * (0.08 + 0.55 * g1)[None, :]
        out += wind_whistle(rng.standard_normal((2, n)).astype(np.float32)) * (0.35 * g2 * g2)[None, :]
        if muffled:                                                            # wind heard through a wall: only the low rumble
            out = self.muffle(out * 2.0) * (0.5 + 0.8 * g1)[None, :]
        return out * lvl * 0.9

    def _crickets(self, start: int, n: int, lvl: float) -> np.ndarray:
        t = (start + np.arange(n)) / SR
        gate_env = _interp(self.chirp_gate, 0.08, start, n)
        out = np.zeros((2, n), np.float32)
        for i, (f, pulse_hz, period, pan) in enumerate(((4300.0, 29.0, 1.30, 0.3), (4650.0, 33.0, 1.71, 0.7), (3950.0, 26.0, 2.2, 0.5))):
            on = ((t * 1.0 + i * 0.37) % period) < (0.45 * period)                     # a burst of pulses, then a rest
            pulses = np.clip(np.sin(2 * np.pi * pulse_hz * t + self.cricket_ph[i]) * 2.2, 0, 1)
            vib = 1 + 0.003 * np.sin(2 * np.pi * 0.7 * t + i)
            tone = np.sin(2 * np.pi * f * t * vib)
            sig = (tone * pulses * on * (gate_env > 0.25 + 0.15 * i)).astype(np.float32) * 0.012
            out[0] += sig * (1 - pan)
            out[1] += sig * pan
        return out * lvl

    def _rain(self, start: int, n: int, lvl: float) -> np.ndarray:
        if not self.rain:
            return np.zeros((2, n), np.float32)
        t = (start + np.arange(n)) / SR
        env = np.zeros(n, np.float32)
        for a, b in self.rain:
            env = np.maximum(env, np.clip(np.minimum((t - a) / 8.0, (b - t) / 8.0), 0, 1).astype(np.float32))
        if not env.any():
            return np.zeros((2, n), np.float32)
        noise = self.rng.standard_normal((2, n)).astype(np.float32)
        patter = 0.75 + 0.25 * np.tanh(self.rain_mod(self.rng.standard_normal(n).astype(np.float32)) * 25.0)
        return self.rain_hi(noise) * (env * patter)[None, :] * 0.22 * lvl

    def _room(self, start: int, n: int, lvl: float) -> np.ndarray:
        """A very quiet low room tone, so a stretch with nothing else playing is never digital silence."""
        return self.room(self.rng.standard_normal((2, n)).astype(np.float32)) * 0.01 * lvl

    # --------------------------------------------------------------------------------------------- the block
    def block(self, n: int) -> np.ndarray:
        """The next n samples, stereo float32. Long requests are made in pieces of BLOCK so slow envelopes stay accurate."""
        parts = []
        done = 0
        while done < n:
            m = min(self.BLOCK, n - done)
            start = self.pos + done
            out = np.zeros((2, m), np.float32)
            L = self.layers
            if L.get("fire"):
                out += self._fire(start, m, L["fire"] * CAL["fire"])
            if L.get("wind"):
                out += self._wind(start, m, L["wind"] * CAL["wind"])
            if L.get("hollow_wind"):
                out += self._wind(start, m, L["hollow_wind"] * CAL["hollow_wind"], hollow=True)
            if L.get("muffled_wind"):
                out += self._wind(start, m, L["muffled_wind"] * CAL["muffled_wind"], muffled=True)
            if L.get("crickets"):
                out += self._crickets(start, m, L["crickets"] * CAL["crickets"])
            if L.get("rain"):
                out += self._rain(start, m, L["rain"] * CAL["rain"])
            out += self._room(start, m, L.get("room", 1.0))
            self._events_into(out, start, m, 1.0)
            parts.append(out)
            done += m
        self.pos += n
        return np.concatenate(parts, axis=1) if len(parts) > 1 else parts[0]
