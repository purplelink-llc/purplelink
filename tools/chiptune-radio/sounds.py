"""Sound modes for the long-form videos: noise colours, binaural beats, synth pads, rain, fireplace, ocean, wind, fan and airplane cabin.

Everything is made from random numbers and sine waves in code. Nothing is recorded, sampled or downloaded.

    src = make("brown", seconds=600, seed=3, period=int(600 * SR))      # a Source for a 10 minute loop
    x = src.block(SR * 10)                 # the random part, in order, float32 (2, n); filter state carries from block to block
    y = src.periodic(0, SR * 10)           # the part that repeats exactly every `period` samples (tones, slow drones), (2, n)

Why two parts: the loop renderer joins the end of a loop to its start with an equal-power crossfade. That is right for random sound (noise stays
level through the join) and wrong for a steady tone (two copies of the same sine add up to a 3 dB bump). So every tone and every slow swell is
built to repeat exactly once per loop (each frequency is a whole number of cycles per loop) and is added after the crossfade, while the random
part is crossfaded. The seam is then silent in both parts.

Each sound has a loudness target in LUFS (people sleep to noise, so noise masters quieter than music); see SOUNDS.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.signal import bilinear_zpk, butter, sosfilt, sosfreqz, zpk2sos

import ambience
from ambience import _Filt, _Mono, _sos

SR = ambience.SR
DROP_GAIN = 3.5           # how loud single rain drops are against the hiss (higher is peakier)


# ------------------------------------------------------------------------------------------------------------------------ filters
def pink_sos(f_lo: float = 8.0, f_hi: float = 19000.0, per_decade: int = 4) -> np.ndarray:
    """-3 dB per octave (-10 dB per decade) between f_lo and f_hi: a ladder of pole and zero pairs, each pair worth 10/per_decade dB, with the corner
    frequencies pre-warped so the bilinear transform puts them where they were asked for. Flat below f_lo, so there is no runaway at DC."""
    n = int(np.ceil(np.log10(f_hi / f_lo) * per_decade))
    step = 1.0 / per_decade
    fp = f_lo * 10 ** (step * np.arange(n))
    fz = fp * 10 ** (step / 2)
    warp = lambda f: 2 * SR * np.tan(np.pi * f / SR)
    wp, wz = warp(fp), warp(fz)
    k = float(np.prod(wp / wz))
    z, p, kd = bilinear_zpk(-wz, -wp, k, SR)
    hp = butter(1, 8.0, "highpass", fs=SR, output="sos")                  # the ladder is flat below f_lo, which lets very slow wander through: block DC
    return np.vstack([zpk2sos(z, p, kd), hp])


def brown_sos(corner: float = 12.0, dc_block: float = 8.0) -> np.ndarray:
    """-6 dB per octave: a leaky integrator (a one-pole low-pass whose corner is `corner` Hz, so it is flat below that and does not drift), then a
    gentle first-order high-pass at `dc_block` Hz so the output has no DC offset."""
    a = float(np.exp(-2 * np.pi * corner / SR))
    integ = np.array([[1.0, 0.0, 0.0, 1.0, -a, 0.0]])
    hp = butter(1, dc_block, "highpass", fs=SR, output="sos")
    return np.vstack([integ, hp])


def _rms(x) -> float:
    return float(np.sqrt(np.mean(np.square(np.asarray(x, np.float64)))))


def cycles(k: int, N: int, start: int, n: int, phase: float = 0.0) -> np.ndarray:
    """sin of a tone that makes exactly k cycles in N samples, for samples start..start+n. The phase is taken modulo N in integers, so it stays exact
    over hours (float phase would drift)."""
    idx = np.arange(start, start + n, dtype=np.int64)
    return np.sin(2 * np.pi * (((k * idx) % N) / N) + phase)


# ------------------------------------------------------------------------------------------------------------------------ components
class Comp:
    """One ingredient. `block` is the random part (sequential), `periodic` the part that repeats every N samples."""
    kind = "noise"          # "noise": normalises itself to RMS 1 at construction; "tone": the Mix normalises its periodic part

    def block(self, n: int):
        return None

    def periodic(self, start: int, n: int, N: int):
        return None


class NoiseColor(Comp):
    """White, pink or brown noise, independent in the two ears, RMS 1."""

    def __init__(self, color: str, seed: int, norm: float | None = None):
        self.rng = np.random.default_rng(seed)
        self.f = _Filt({"white": None, "pink": pink_sos(), "brown": brown_sos()}[color]) if color != "white" else None
        self.color, self.seed = color, seed
        self._raw(2 * SR)                                              # warm the filters up so the start is not a ramp from silence
        self.norm = norm if norm is not None else self._probe()

    def _probe(self) -> float:
        p = NoiseColor(self.color, self.seed + 101, norm=1.0)
        return 1.0 / max(1e-9, _rms(p._raw(8 * SR)))

    def _raw(self, n: int) -> np.ndarray:
        x = self.rng.standard_normal((2, n))
        return self.f(x) if self.f is not None else x

    def block(self, n: int):
        return (self._raw(n) * self.norm).astype(np.float32)


class Drone(Comp):
    """A slow evolving pad: a chord of pure partials (root, fifth, octave, ninth...) each detuned a little differently in the two ears and each
    swelling on its own slow cycle (60 to 220 s), so the sound changes all the time and nothing ever plays a note. No beat, no melody, no key
    change. Every frequency and every swell is a whole number of cycles per loop."""
    kind = "tone"
    ROOTS = (65.4, 73.4, 82.4, 98.0, 110.0)
    RATIOS = ((1.0, 1.0), (1.5, 0.8), (2.0, 0.7), (3.0, 0.45), (2.25, 0.4), (4.0, 0.28), (2.5, 0.22), (6.0, 0.12))

    def __init__(self, seed: int, soft: bool = False):
        self.seed, self.soft = seed, soft
        self._layout_cache: dict = {}

    def _layout(self, N: int):
        if N in self._layout_cache:
            return self._layout_cache[N]
        rng = np.random.default_rng(self.seed * 17 + 3)
        root = self.ROOTS[int(rng.integers(len(self.ROOTS)))] * (1.0 if not self.soft else 1.5)
        P = N / SR
        parts = []
        for ratio, amp in self.RATIOS:
            f = root * ratio
            det = rng.uniform(0.15, 0.45)                              # Hz: the two ears drift against each other slowly (a pad, not a binaural beat)
            kL, kR = max(1, round((f - det) * P)), max(1, round((f + det) * P))
            lfo = max(1, round(P / rng.uniform(60, 220)))
            parts.append((kL, kR, amp, lfo, float(rng.uniform(0, 6.28)), float(rng.uniform(0, 6.28))))
        self._layout_cache[N] = parts
        return parts

    def periodic(self, start: int, n: int, N: int):
        out = np.zeros((2, n))
        for kL, kR, amp, lfo, ph, phl in self._layout(N):
            swell = 0.55 + 0.45 * cycles(lfo, N, start, n, ph)
            out[0] += cycles(kL, N, start, n, phl) * amp * swell
            out[1] += cycles(kR, N, start, n, phl + 1.3) * amp * swell
        return out.astype(np.float32)


class Tones(Comp):
    """The binaural pair: a carrier in the left ear and carrier + beat in the right, each a whole number of cycles per loop, so the difference between
    the ears is exactly the beat all the way through (and across the loop point)."""
    kind = "tone"

    def __init__(self, beat: float, carrier: float = 200.0):
        self.beat, self.carrier = beat, carrier

    def freqs(self, N: int):
        P = N / SR
        kL = round(self.carrier * P)
        kR = kL + round(self.beat * P)
        return kL, kR

    def periodic(self, start: int, n: int, N: int):
        kL, kR = self.freqs(N)
        return np.stack([cycles(kL, N, start, n), cycles(kR, N, start, n)]).astype(np.float32)


class Hum(Comp):
    """Steady machine tones (a fan motor, an engine) at the given frequencies, the left and right ear a hair apart, with a very slow breathing."""
    kind = "tone"

    def __init__(self, freqs, seed: int = 1, breath: float = 0.12):
        self.freqs, self.seed, self.breath = tuple(freqs), seed, breath

    def periodic(self, start: int, n: int, N: int):
        P, rng = N / SR, np.random.default_rng(self.seed)
        out = np.zeros((2, n))
        for i, (f, amp) in enumerate(self.freqs):
            lfo = max(1, round(P / rng.uniform(40, 120)))
            env = 1.0 + self.breath * cycles(lfo, N, start, n, float(rng.uniform(0, 6.28)))
            out[0] += cycles(max(1, round((f - 0.17) * P)), N, start, n, i) * amp * env
            out[1] += cycles(max(1, round((f + 0.17) * P)), N, start, n, i + 2.0) * amp * env
        return out.astype(np.float32)


class Filtered(Comp):
    """White noise through a band-pass or low-pass chain, with optional resonant peaks. RMS 1."""

    def __init__(self, seed: int, bands, norm: float | None = None):
        # bands: [(kind, hz, order, weight)] where hz is a number (lowpass/highpass) or a (lo, hi) pair (bandpass); outputs are summed
        self.seed, self.bands = seed, bands
        self.rng = np.random.default_rng(seed)
        self.fs = [(_Filt(_sos(k, hz, o)), w) for k, hz, o, w in bands]
        self._raw(SR)
        self.norm = norm if norm is not None else self._probe()

    def _probe(self) -> float:
        p = Filtered(self.seed + 101, self.bands, norm=1.0)
        return 1.0 / max(1e-9, _rms(p._raw(8 * SR)))

    def _raw(self, n: int) -> np.ndarray:
        x = self.rng.standard_normal((2, n))
        return sum(f(x) * w for f, w in self.fs)

    def block(self, n: int):
        return (self._raw(n) * self.norm).astype(np.float32)


def thunder(seed: int, dur: float = 16.0) -> np.ndarray:
    """A distant rumble: low-passed noise with a few rolling swells and a long decay, no crack. Stereo, peak about 1."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    env = np.zeros(n)
    at, amp = 0.0, 1.0
    for _ in range(int(rng.integers(3, 6))):
        rise, tau = rng.uniform(0.5, 1.6), rng.uniform(2.0, 4.0)
        d = np.clip((t - at) / rise, 0, 1) * np.exp(-np.clip(t - at - rise, 0, None) / tau) * (t >= at)
        env += amp * d
        at += rng.uniform(1.2, 3.0)
        amp *= rng.uniform(0.5, 0.9)
    env *= np.minimum(1.0, (dur - t) / 3.0)
    x = rng.standard_normal((2, n))
    x = sosfilt(_sos("lowpass", rng.uniform(110, 180), 3), x, axis=1) + 0.5 * sosfilt(_sos("lowpass", 55, 2), x, axis=1)
    x = x * env
    return (x / (np.abs(x).max() + 1e-9)).astype(np.float32)


class Rain(Comp):
    """Layered rain: a broad hiss, a lower body, and a scatter of single drops in three bands, with a slow swell in how hard it falls. RMS 1.
    Optional distant thunder every `thunder_gap` seconds on average (0 for none); it is added on top of the rain, in units of the rain's RMS."""

    def __init__(self, seed: int, seconds: float, thunder_gap: float = 0.0, thunder_amp: float = 2.0, drops: float = 1.0, norm: float | None = None):
        self.seed, self.seconds, self.thunder_gap, self.thunder_amp, self.drops = seed, seconds, thunder_gap, thunder_amp, drops
        self.rng = np.random.default_rng(seed * 5 + 9)
        self.pos = 0
        self.hiss, self.body = _Filt(_sos("bandpass", (1100.0, 9500.0), 2)), _Filt(_sos("bandpass", (250.0, 1100.0), 1))
        self.pit = [[_Mono(_sos("bandpass", (fc * 0.8, fc * 1.25), 2)) for fc in (2200.0, 3600.0, 5600.0)] for _ in range(2)]
        self.swell = ambience.slow_envelope(np.random.default_rng(seed * 3 + 1), seconds + 30, 0.05, 0.8, 1.2, smooth=5)
        self.events = []
        if thunder_gap > 0:
            r, t = np.random.default_rng(seed * 11 + 2), 0.0
            t = r.uniform(0.3, 1.0) * thunder_gap
            while t < seconds + 20:
                self.events.append((t, int(r.integers(1 << 30))))
                t += r.uniform(0.6, 1.5) * thunder_gap
        self._thunder: dict = {}
        self._rain(SR)
        self.pos = 0
        self.norm = norm if norm is not None else self._probe()

    def _probe(self) -> float:
        p = Rain(self.seed + 101, 60.0, 0.0, drops=self.drops, norm=1.0)
        return 1.0 / max(1e-9, _rms(p._rain(8 * SR)))

    def _rain(self, n: int) -> np.ndarray:
        rng = self.rng
        sw = ambience._interp(self.swell, 0.05, self.pos, n)
        hiss = self.hiss(rng.standard_normal((2, n))) * 0.35 + self.body(rng.standard_normal((2, n))) * 0.45
        out = hiss
        k = int(rng.poisson(110.0 * self.drops * n / SR))
        for ch in range(2):
            idx = rng.integers(0, n, k)
            amp = rng.lognormal(-0.5, 0.6, k)
            which = rng.integers(0, 3, k)
            for r in range(3):
                train = np.zeros(n)
                sel = which == r
                np.add.at(train, idx[sel], amp[sel])
                out[ch] += self.pit[ch][r](train) * (DROP_GAIN / (1 + 0.5 * r))
        self.pos += n
        return out * sw[None, :]

    def block(self, n: int):
        start = self.pos
        x = self._rain(n) * self.norm
        for t, s in self.events:
            i0 = int(t * SR)
            if i0 + 16 * SR <= start or i0 >= start + n:
                continue
            if s not in self._thunder:
                self._thunder[s] = thunder(s)
            th = self._thunder[s]
            lo, hi = max(start, i0), min(start + n, i0 + th.shape[1])
            x[:, lo - start:hi - start] += th[:, lo - i0:hi - i0] * self.thunder_amp
        return x.astype(np.float32)


class Ocean(Comp):
    """Waves: two slowly drifting wave trains (about 9 to 14 s apart), each a swell that builds, crests and slides back. A low rumble follows the
    swell, a mid wash follows it more closely, and the foam hiss only appears at the crest. RMS 1."""

    def __init__(self, seed: int, norm: float | None = None):
        self.seed = seed
        self.rng = np.random.default_rng(seed * 7 + 4)
        self.f = [0.085, 0.067]
        self.ph = list(self.rng.uniform(0, 6.28, 2))
        self.lo, self.mid, self.hi = _Filt(_sos("lowpass", 420.0, 2)), _Filt(_sos("bandpass", (350.0, 2600.0), 2)), _Filt(_sos("bandpass", (1800.0, 8000.0), 2))
        self._raw(2 * SR)
        self.norm = norm if norm is not None else self._probe()

    def _probe(self) -> float:
        p = Ocean(self.seed + 101, norm=1.0)
        return 1.0 / max(1e-9, _rms(p._raw(30 * SR)))

    def _env(self, n: int) -> np.ndarray:
        env = np.zeros(n)
        for j, (base, w) in enumerate(((0.085, 0.6), (0.067, 0.4))):
            target = base * self.rng.uniform(0.8, 1.25)
            fr = np.linspace(self.f[j], target, n)
            self.f[j] = target
            ph = self.ph[j] + 2 * np.pi * np.cumsum(fr) / SR
            self.ph[j] = float(ph[-1] % (2 * np.pi))
            env += w * (0.5 - 0.5 * np.cos(ph + 0.6 * np.sin(ph))) ** 1.6       # the skew makes the swell build slowly and fall faster
        return env

    def _raw(self, n: int) -> np.ndarray:
        env = self._env(n)
        g = lambda: self.rng.standard_normal((2, n))
        return self.lo(g()) * (0.35 + 0.9 * env)[None] + self.mid(g()) * (1.2 * env)[None] + self.hi(g()) * (1.1 * env ** 2.2)[None]

    def block(self, n: int):
        return (self._raw(n) * self.norm).astype(np.float32)


class BedSound(Comp):
    """An ambience.Bed layer used as the main sound (fire crackle, wind), normalised to RMS 1."""

    def __init__(self, layers: dict, seconds: float, seed: int, norm: float | None = None):
        self.layers, self.seconds, self.seed = layers, seconds, seed
        self.bed = ambience.Bed(layers, seconds, seed=seed)
        self.norm = norm if norm is not None else self._probe()

    def _probe(self) -> float:
        p = BedSound(self.layers, 60.0, self.seed + 101, norm=1.0)
        return 1.0 / max(1e-9, _rms(p.bed.block(20 * SR)))

    def block(self, n: int):
        return self.bed.block(n) * self.norm


# ------------------------------------------------------------------------------------------------------------------------ the mix
class Source:
    """A weighted set of components. `block` and `periodic` are what longform.build_audio calls; `rms_unit` is the level a theme's bed is balanced against."""

    def __init__(self, parts, N: int):
        self.N = N
        self.parts = []
        for comp, rel in parts:
            g = rel
            if comp.kind == "tone":
                g = rel / max(1e-9, _rms(comp.periodic(0, min(N, 10 * SR), N)))
            self.parts.append((comp, g))

    def block(self, n: int) -> np.ndarray:
        out = np.zeros((2, n), np.float32)
        for comp, g in self.parts:
            b = comp.block(n)
            if b is not None:
                out += b * np.float32(g)
        return out

    def periodic(self, start: int, n: int) -> np.ndarray:
        out = np.zeros((2, n), np.float32)
        for comp, g in self.parts:
            b = comp.periodic(start, n, self.N)
            if b is not None:
                out += b * np.float32(g)
        return out


@dataclass(frozen=True)
class SoundSpec:
    name: str
    label: str                      # for titles and the thumbnail
    lufs: float                     # the master's loudness target
    bed_level: float = 0.5          # the theme's ambience under this sound, against the sound at 1.0 (0 drops the bed)
    drop: tuple = ()                # theme bed layers that would double this sound
    musical: bool = False           # uses the chiptune engine
    beat_hz: float = 0.0
    what: str = ""                  # plain statement of the sound, for the description
    how: str = ""                   # how it is made
    note: str = ""                  # extra line (headphones)
    build: object = field(default=None, compare=False)


def _white(seconds, seed):
    return [(NoiseColor("white", seed), 1.0)]


def _pink(seconds, seed):
    return [(NoiseColor("pink", seed), 1.0)]


def _brown(seconds, seed):
    return [(NoiseColor("brown", seed), 1.0)]


def _binaural(beat):
    def build(seconds, seed):
        return [(Tones(beat), 0.5), (Drone(seed, soft=True), 0.3), (NoiseColor("pink", seed), 0.3)]
    return build


def _synth(seconds, seed):
    return [(Drone(seed), 1.0), (Filtered(seed, [("lowpass", 1400.0, 2, 1.0)]), 0.06)]


def _rain(seconds, seed):
    return [(Rain(seed, seconds, thunder_gap=540.0, thunder_amp=1.4), 1.0)]


def _storm(seconds, seed):
    return [(Rain(seed, seconds, thunder_gap=110.0, thunder_amp=2.6, drops=1.5), 1.0)]


def _ocean(seconds, seed):
    return [(Ocean(seed), 1.0)]


def _fire(seconds, seed):
    return [(BedSound({"fire": 1.0, "room": 0.15}, seconds, seed), 1.0)]


def _wind(seconds, seed):
    return [(BedSound({"wind": 1.0, "room": 0.15}, seconds, seed), 1.0)]


def _fan(seconds, seed):
    return [(Filtered(seed, [("lowpass", 4500.0, 2, 1.0), ("bandpass", (140.0, 260.0), 2, 1.4), ("bandpass", (480.0, 640.0), 2, 0.5)]), 1.0),
            (Hum([(100.0, 0.5), (200.0, 0.28), (300.0, 0.12)], seed), 0.35)]


def _airplane(seconds, seed):
    return [(Filtered(seed, [("lowpass", 260.0, 3, 1.0), ("bandpass", (300.0, 1300.0), 1, 0.35), ("bandpass", (2200.0, 6500.0), 1, 0.06)]), 1.0),
            (Hum([(78.0, 0.6), (117.0, 0.35), (156.0, 0.12)], seed, breath=0.08), 0.3)]


SOUNDS: dict[str, SoundSpec] = {s.name: s for s in [
    SoundSpec("chiptune", "Chiptune", -14.0, musical=True, what="soft chiptune music"),
    SoundSpec("lofi", "Lofi", -16.0, musical=True, what="slow, soft lofi chiptune music with a warm electric-piano sound"),
    SoundSpec("brown", "Brown Noise", -20.0, 0.7, what="brown noise: deep, smooth noise that falls 6 dB per octave",
              how="generated by integrating white noise with a leaky integrator and removing the DC offset", build=_brown),
    SoundSpec("pink", "Pink Noise", -20.0, 0.7, what="pink noise: smooth noise that falls 3 dB per octave",
              how="generated by filtering white noise to a 1/f spectrum", build=_pink),
    SoundSpec("white", "White Noise", -20.0, 0.6, what="white noise: the same energy at every frequency",
              how="generated from a random number stream, independent in each ear", build=_white),
    SoundSpec("binaural-alpha", "10 Hz Binaural Beats", -20.0, 0.25, beat_hz=10.0,
              what="a 10 Hz binaural beat: a 200 Hz tone in the left ear and a 210 Hz tone in the right, under a soft pad and quiet pink noise",
              how="two sine tones, each an exact whole number of cycles per loop, so the 10 Hz difference never changes", note="Use headphones. The effect needs a different tone in each ear.",
              build=_binaural(10.0)),
    SoundSpec("binaural-theta", "6 Hz Binaural Beats", -20.0, 0.25, beat_hz=6.0,
              what="a 6 Hz binaural beat: a 200 Hz tone in the left ear and a 206 Hz tone in the right, under a soft pad and quiet pink noise",
              how="two sine tones, each an exact whole number of cycles per loop, so the 6 Hz difference never changes", note="Use headphones. The effect needs a different tone in each ear.",
              build=_binaural(6.0)),
    SoundSpec("binaural-delta", "2 Hz Binaural Beats", -20.0, 0.25, beat_hz=2.0,
              what="a 2 Hz binaural beat: a 200 Hz tone in the left ear and a 202 Hz tone in the right, under a soft pad and quiet pink noise",
              how="two sine tones, each an exact whole number of cycles per loop, so the 2 Hz difference never changes", note="Use headphones. The effect needs a different tone in each ear.",
              build=_binaural(2.0)),
    SoundSpec("synth", "Ambient Synth", -18.0, 0.3, what="slow ambient synth pads and drones with no beat and no melody",
              how="a chord of pure sine partials that each swell on their own slow cycle", build=_synth),
    SoundSpec("rain", "Rain Sounds", -20.0, 0.4, drop=("rain",), what="steady rain with a little distant thunder now and then",
              how="layered noise for the hiss and body of the rain plus single drops, with a few low rumbles of thunder", build=_rain),
    SoundSpec("thunderstorm", "Thunderstorm", -20.0, 0.3, drop=("rain",), what="heavy rain with frequent rolling thunder",
              how="layered noise for the rain plus single drops, with low rumbles of thunder every couple of minutes", build=_storm),
    SoundSpec("fireplace", "Fireplace Sounds", -18.0, 0.2, drop=("fire",), what="a crackling fireplace, with the crackle louder than the wind outside",
              how="random pops and a low roar built from filtered noise", build=_fire),
    SoundSpec("ocean", "Ocean Waves", -20.0, 0.2, what="waves rolling onto a shore, about ten seconds apart",
              how="noise shaped by two slowly drifting swells", build=_ocean),
    SoundSpec("wind", "Wind Sounds", -20.0, 0.2, drop=("wind", "hollow_wind", "muffled_wind"), what="wind with slow gusts",
              how="filtered noise with slow random gusts", build=_wind),
    SoundSpec("fan", "Fan Sounds", -20.0, 0.2, what="the steady whoosh and low motor hum of a fan",
              how="filtered noise with a few steady motor tones", build=_fan),
    SoundSpec("airplane", "Airplane Cabin Sounds", -20.0, 0.2, what="the low steady roar of an airplane cabin in flight",
              how="low-passed noise with two engine tones that beat very slowly against each other", build=_airplane),
]}
NAMES = list(SOUNDS)
MUSICAL = {n for n, s in SOUNDS.items() if s.musical}


def spec(name: str) -> SoundSpec:
    if name not in SOUNDS:
        raise KeyError(f"unknown sound {name!r}; choose one of {', '.join(NAMES)}")
    return SOUNDS[name]


def make(name: str, seconds: float, seed: int, period: int) -> Source:
    """A Source for a synthetic sound. `period` is the number of samples after which the periodic part repeats (the loop length, or the whole
    video when it is not a loop)."""
    sp = spec(name)
    if sp.build is None:
        raise ValueError(f"{name} is made by the music engine, not here")
    return Source(sp.build(seconds, seed), period)


def target_lufs(name: str) -> float:
    return spec(name).lufs
