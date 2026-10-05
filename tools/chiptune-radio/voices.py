#!/usr/bin/env python3.12
"""Instruments, drum kits and effects for the chiptune radio.

Everything is synthesised from maths, with no samples. Each instrument is a function (frequency, samples, extras, rng) that
returns one note at the 2x rendering rate with its own envelope. Instruments are loudness-matched at import time by measuring a
reference note, so a flute and a bell sit at the same level before the mixer's per-voice gains.

Three families:
  * 8-bit: pulse waves, a stepped triangle and noise, crushed to 4-bit steps (the original sound)
  * 16-bit: FM electric piano, bells, flute, organ, strings, plucked strings, warm pads and sampled-style drums
  * synth: detuned saw leads, filtered saw bass and plucks, brass, risers and sidechain pumping
"""
from __future__ import annotations

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

RATE = 88200          # the rendering rate: 2x the 44.1 kHz output


def _t(n: int) -> np.ndarray:
    return np.arange(n) / RATE


def env(n: int, a=0.004, d=0.07, s=0.7, rel=0.05) -> np.ndarray:
    a_, d_, r_ = int(a * RATE), int(d * RATE), min(int(rel * RATE), max(1, n // 2))
    e = np.full(n, s, dtype=np.float64)
    a_ = min(a_, n)
    e[:a_] = np.linspace(0, 1, a_, endpoint=False)
    d_end = min(a_ + d_, n)
    e[a_:d_end] = np.linspace(1, s, d_end - a_)
    if r_:
        e[n - r_:] *= np.linspace(1, 0, r_)
    return e


_SOS: dict = {}


def lowpass(x: np.ndarray, fc: float, order: int = 2) -> np.ndarray:
    key = ("lp", round(fc), order)
    if key not in _SOS:
        _SOS[key] = butter(order, min(fc, RATE / 2 - 100), "lowpass", fs=RATE, output="sos")
    return sosfilt(_SOS[key], x)


def highpass(x: np.ndarray, fc: float, order: int = 2) -> np.ndarray:
    key = ("hp", round(fc), order)
    if key not in _SOS:
        _SOS[key] = butter(order, fc, "highpass", fs=RATE, output="sos")
    return sosfilt(_SOS[key], x)


def bandpass(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    key = ("bp", round(lo), round(hi))
    if key not in _SOS:
        _SOS[key] = butter(2, [lo, min(hi, RATE / 2 - 100)], "bandpass", fs=RATE, output="sos")
    return sosfilt(_SOS[key], x)


def _vib(n: int, f: float, depth: float, delay: float = 0.12, rate: float = 5.3) -> np.ndarray:
    tt = _t(n)
    return f * (1 + depth * np.sin(2 * np.pi * rate * tt) * np.clip((tt - delay) / 0.3, 0, 1))


def _phase(freq) -> np.ndarray:
    return np.cumsum(freq) / RATE


def saw_wave(f, n: int, vib: float = 0.0) -> np.ndarray:
    fr = _vib(n, f, vib) if vib else np.full(n, f)
    return (_phase(fr) % 1.0) * 2 - 1


def supersaw(f: float, n: int, voices: int = 5, spread: float = 12.0, vib: float = 0.0) -> np.ndarray:
    """Several saws detuned by a few cents, the classic thick synth sound."""
    out = np.zeros(n)
    for k in range(voices):
        cents = (k - (voices - 1) / 2) * spread / max(1, (voices - 1) / 2)
        fr = _vib(n, f * 2 ** (cents / 1200), vib) if vib else np.full(n, f * 2 ** (cents / 1200))
        out += ((_phase(fr) + k * 0.173) % 1.0) * 2 - 1
    return out / math_sqrt(voices)


def math_sqrt(x):
    return float(np.sqrt(x))


# ---------------------------------------------------------------- 8-bit

def pulse(f, n, ex, rng):
    duty = (ex or {}).get("duty", 0.5)
    vib = (ex or {}).get("vib", 0.0)
    slide = (ex or {}).get("slide", 0.0)
    tt = _t(n)
    fr = _vib(n, f, vib) if vib else np.full(n, f)
    if slide:
        fr = fr * 2 ** ((slide * np.clip(1 - tt / 0.05, 0, 1)) / 12)
    w = np.where((_phase(fr) % 1.0) < duty, 1.0, -1.0)
    return w * env(n, 0.006, 0.09, 0.75, 0.05)


def pulse_arp(f, n, ex, rng):
    return np.where((_phase(np.full(n, f)) % 1.0) < (ex or {}).get("duty", 0.125), 1.0, -1.0) * env(n, 0.002, 0.05, 0.5, 0.02)


def pulse_pad(f, n, ex, rng):
    return np.where((_phase(np.full(n, f)) % 1.0) < 0.5, 1.0, -1.0) * env(n, 0.12, 0.2, 0.8, 0.25)


def tri8(f, n, ex, rng):
    w = 4 * np.abs((_phase(np.full(n, f)) % 1.0) - 0.5) - 1
    return (np.round((w + 1) * 7.5) / 7.5 - 1) * env(n, 0.004, 0.0, 1.0, 0.04)


# ---------------------------------------------------------------- 16-bit and FM

def _fm(f, n, ratio, index, idx_decay, amp, extra_ratio=0.0, extra_index=0.0, extra_decay=30.0):
    tt = _t(n)
    mod = np.sin(2 * np.pi * f * ratio * tt) * index * np.exp(-idx_decay * tt)
    if extra_ratio:
        mod = mod + np.sin(2 * np.pi * f * extra_ratio * tt) * extra_index * np.exp(-extra_decay * tt)
    return np.sin(2 * np.pi * f * tt + mod) * amp


def fm_ep(f, n, ex, rng):
    return _fm(f, n, 1.0, 1.5, 3.5, env(n, 0.003, 0.6, 0.35, 0.14), extra_ratio=14.0, extra_index=0.4)


def fm_bell(f, n, ex, rng):
    tt = _t(n)
    return _fm(f, n, 3.5, 4.5, 1.8, np.exp(-1.6 * tt) * env(n, 0.002, 0.0, 1.0, 0.2))


def fm_bass(f, n, ex, rng):
    tt = _t(n)
    mod = np.sin(2 * np.pi * f * tt) * (3.8 * np.exp(-13 * tt) + 0.5)
    return np.sin(2 * np.pi * f * tt + mod) * env(n, 0.003, 0.15, 0.7, 0.05)


def fm_brass(f, n, ex, rng):
    tt = _t(n)
    mod = np.sin(2 * np.pi * f * tt) * 2.3 * (1 - np.exp(-tt * 16))
    return np.sin(2 * np.pi * f * tt + mod) * env(n, 0.03, 0.12, 0.8, 0.08)


def flute(f, n, ex, rng):
    fr = _vib(n, f, 0.006, delay=0.2)
    ph = _phase(fr)
    w = np.sin(2 * np.pi * ph) + 0.25 * np.sin(4 * np.pi * ph) + 0.08 * np.sin(6 * np.pi * ph)
    breath = bandpass(rng.standard_normal(n), 2500, 7000) * 0.05
    return (w + breath) * env(n, 0.06, 0.1, 0.85, 0.1)


def organ(f, n, ex, rng):
    ph = _phase(_vib(n, f, 0.002, rate=6.0))
    w = 0.7 * np.sin(2 * np.pi * ph) + 0.5 * np.sin(4 * np.pi * ph) + 0.35 * np.sin(6 * np.pi * ph) + 0.2 * np.sin(8 * np.pi * ph)
    return w * env(n, 0.012, 0.05, 0.9, 0.07)


def pulse_soft(f, n, ex, rng):
    tt = _t(n)
    duty = (ex or {}).get("duty", 0.5)
    vib = (ex or {}).get("vib", 0.0)
    fr = _vib(n, f, vib) if vib else np.full(n, f)
    w = np.where((_phase(fr) % 1.0) < duty, 1.0, -1.0)
    return lowpass(w, 4200) * env(n, 0.008, 0.1, 0.75, 0.06)


def strings(f, n, ex, rng):
    return lowpass(supersaw(f, n, 5, 12, vib=0.004), 3200) * env(n, 0.22, 0.3, 0.85, 0.4)


def warm_pad(f, n, ex, rng):
    return lowpass(supersaw(f, n, 7, 18), 1800) * env(n, 0.35, 0.4, 0.8, 0.6)


def pluck(f, n, ex, rng):
    """Karplus-Strong: a burst of noise circulating in a delay line that loses a little energy each lap."""
    N = max(8, int(RATE / f))
    exc = lowpass(rng.standard_normal(N), 6000)
    exc = exc / (np.max(np.abs(exc)) + 1e-9)
    B = 1                                              # one leading zero, so the delay line can look one sample further back
    y = np.zeros(n + N + 4)
    y[B:B + N] = exc[:N]
    g = 0.5 * 0.9985
    for s in range(N, n + N, N):
        e = min(N, n + N - s)
        y[B + s:B + s + e] = g * (y[B + s - N:B + s - N + e] + y[B + s - N - 1:B + s - N - 1 + e])
    out = y[B:B + n]
    return out * env(n, 0.001, 0.0, 1.0, min(0.15, n / RATE / 2))


# ---------------------------------------------------------------- synth

def saw_lead(f, n, ex, rng):
    return lowpass(supersaw(f, n, 3, 9, vib=0.005), 5500) * env(n, 0.01, 0.1, 0.75, 0.07)


def saw_pluck(f, n, ex, rng):
    tt = _t(n)
    w = saw_wave(f, n)
    e1 = np.exp(-tt / 0.08)
    return (lowpass(w, 5200) * e1 + lowpass(w, 900) * (1 - e1)) * env(n, 0.002, 0.2, 0.2, 0.05)


def synth_bass(f, n, ex, rng):
    tt = _t(n)
    w = saw_wave(f, n) * 0.8 + np.sin(2 * np.pi * f * tt) * 0.7
    e1 = np.exp(-tt / 0.14)
    return (lowpass(w, 2600) * e1 + lowpass(w, 420) * (1 - e1)) * env(n, 0.003, 0.2, 0.75, 0.05)


def sub_sine(f, n, ex, rng):
    tt = _t(n)
    return (np.sin(2 * np.pi * f * tt) + 0.15 * np.sin(4 * np.pi * f * tt)) * env(n, 0.01, 0.0, 1.0, 0.06)


def sparkle(f, n, ex, rng):
    return fm_bell(f, n, ex, rng)


INSTRUMENTS = {
    "pulse": pulse, "pulse_arp": pulse_arp, "pulse_pad": pulse_pad, "tri8": tri8,
    "fm_ep": fm_ep, "fm_bell": fm_bell, "fm_bass": fm_bass, "fm_brass": fm_brass, "flute": flute, "organ": organ,
    "pulse_soft": pulse_soft, "strings": strings, "warm_pad": warm_pad, "pluck": pluck,
    "saw_lead": saw_lead, "saw_pluck": saw_pluck, "synth_bass": synth_bass, "sub_sine": sub_sine, "sparkle": sparkle,
}
CRUSHED = {"pulse", "pulse_arp", "pulse_pad", "tri8"}             # the 4-bit voices


def _calibrate() -> dict:
    """Trim each instrument so a reference note has the same RMS, then the mixer only needs one gain per voice."""
    rng = np.random.default_rng(0)
    trims = {}
    for name, fn in INSTRUMENTS.items():
        note = fn(220.0 if name in ("tri8", "fm_bass", "synth_bass", "sub_sine") else 440.0, int(0.45 * RATE), {}, rng)
        peak = float(np.max(np.abs(note))) + 1e-9
        rms = float(np.sqrt(np.mean(note ** 2))) + 1e-9
        trims[name] = min(0.5 / rms, 3.0 / peak)
    return trims


TRIM = _calibrate()


def note(name: str, f: float, n: int, ex, rng) -> np.ndarray:
    return INSTRUMENTS[name](f, n, ex, rng) * TRIM[name]


# ---------------------------------------------------------------- drums

def _noise(n: int, rng) -> np.ndarray:
    return rng.standard_normal(n)


def kick_808(dur, rng):
    n = int(max(dur, 0.32) * RATE)
    tt = _t(n)
    f = 42 + 110 * np.exp(-tt / 0.03)
    body = np.sin(2 * np.pi * np.cumsum(f) / RATE) * np.exp(-tt / 0.2)
    click = highpass(_noise(n, rng), 2500) * np.exp(-tt / 0.004) * 0.15
    return body + click


def kick_soft(dur, rng):
    n = int(max(dur, 0.22) * RATE)
    tt = _t(n)
    f = 55 + 80 * np.exp(-tt / 0.04)
    return np.sin(2 * np.pi * np.cumsum(f) / RATE) * np.exp(-tt / 0.12)


def snare_16(dur, rng):
    n = int(max(dur, 0.22) * RATE)
    tt = _t(n)
    return bandpass(_noise(n, rng), 1400, 7500) * np.exp(-tt / 0.07) + np.sin(2 * np.pi * 185 * tt) * np.exp(-tt / 0.045) * 0.6


def snare_lofi(dur, rng):
    n = int(max(dur, 0.2) * RATE)
    tt = _t(n)
    return lowpass(_noise(n, rng), 5500) * np.exp(-tt / 0.09) * 0.8 + np.sin(2 * np.pi * 170 * tt) * np.exp(-tt / 0.05) * 0.5


def clap(dur, rng):
    n = int(0.28 * RATE)
    tt = _t(n)
    x = bandpass(_noise(n, rng), 900, 6500)
    e = np.zeros(n)
    for k, off in enumerate((0, 0.011, 0.022)):
        i = int(off * RATE)
        e[i:] += np.exp(-(tt[:n - i]) / 0.012) * (0.7 + 0.1 * k)
    e += np.exp(-np.clip(tt - 0.03, 0, None) / 0.09) * (tt > 0.03) * 0.8
    return x * e


def hat_closed(dur, rng):
    n = int(0.06 * RATE)
    return highpass(_noise(n, rng), 7000) * np.exp(-_t(n) / 0.012)


def hat_open(dur, rng):
    n = int(0.28 * RATE)
    return highpass(_noise(n, rng), 6000) * np.exp(-_t(n) / 0.1)


def shaker(dur, rng):
    n = int(0.09 * RATE)
    tt = _t(n)
    return bandpass(_noise(n, rng), 5000, 9500) * np.minimum(tt / 0.012, 1) * np.exp(-tt / 0.03)


def tom_16(dur, rng, pitch=110.0):
    n = int(0.22 * RATE)
    tt = _t(n)
    f = pitch * (1 + 0.5 * np.exp(-tt / 0.05))
    return np.sin(2 * np.pi * np.cumsum(f) / RATE) * np.exp(-tt / 0.09)


def riser(dur: float, rng) -> np.ndarray:
    """White noise that gets louder and brighter over `dur` seconds."""
    n = int(dur * RATE)
    x = _noise(n, rng)
    out = np.zeros(n)
    steps = 8
    for k in range(steps):
        a, b = k * n // steps, (k + 1) * n // steps
        out[a:b] = highpass(x, 500 + 6000 * (k / (steps - 1)) ** 2)[a:b]
    return out * np.linspace(0, 1, n) ** 2.2


KITS = {
    "808": dict(kick=kick_808, snare=snare_16, hat=hat_closed),
    "electro": dict(kick=kick_808, snare=clap, hat=hat_closed),
    "lofi": dict(kick=kick_soft, snare=snare_lofi, hat=shaker),
}


def _calibrate_drums() -> dict:
    rng = np.random.default_rng(1)
    out = {}
    for name, fn in [("kick_808", kick_808), ("kick_soft", kick_soft), ("snare_16", snare_16), ("snare_lofi", snare_lofi), ("clap", clap),
                     ("hat_closed", hat_closed), ("hat_open", hat_open), ("shaker", shaker), ("tom_16", tom_16)]:
        x = fn(0.1, rng)
        out[fn] = 0.5 / (float(np.sqrt(np.mean(x ** 2))) + 1e-9) * (1.0 if fn not in (hat_closed, hat_open, shaker) else 1.0)
    return out


DRUM_TRIM = _calibrate_drums()


# ---------------------------------------------------------------- effects (44.1 kHz stereo)

def make_ir(rt60: float, seed: int, sr: int = 44100) -> np.ndarray:
    """A room: decaying noise that darkens as it decays, a little different in each ear, after a short pre-delay."""
    rng = np.random.default_rng(seed)
    n = int(rt60 * sr)
    tt = np.arange(n) / sr
    pre = int(0.018 * sr)
    out = np.zeros((2, n + pre))
    for ch in range(2):
        x = rng.standard_normal(n) * np.exp(-6.9 * tt / rt60)
        x = sosfilt(butter(1, 5200, "lowpass", fs=sr, output="sos"), x)
        x[: int(0.004 * sr)] *= np.linspace(0, 1, int(0.004 * sr))
        out[ch, pre:] = x
    out /= np.sqrt(np.sum(out ** 2, axis=1, keepdims=True)) + 1e-9
    return out.astype(np.float32)


def reverb(send: np.ndarray, ir: np.ndarray) -> np.ndarray:
    """`send` is (2, n) at 44.1 kHz; returns the wet signal, the same length."""
    n = send.shape[1]
    return np.stack([fftconvolve(send[c], ir[c], mode="full")[:n] for c in range(2)]).astype(np.float32)


def chorus(x: np.ndarray, sr: int = 44100, depth_ms: float = 6.0, rate: float = 0.35, mix: float = 0.5) -> np.ndarray:
    """A slowly swept delay mixed back in, a different phase in each ear."""
    n = x.shape[1]
    idx = np.arange(n)
    out = np.empty_like(x)
    for c in range(2):
        lfo = np.sin(2 * np.pi * rate * idx / sr + c * 1.9)
        d = (14.0 + depth_ms * lfo) * sr / 1000.0
        out[c] = np.interp(idx - d, idx, x[c], left=0.0)
    return (x * (1 - mix * 0.5) + out * mix).astype(np.float32)


def duck_curve(n: int, hits: list, sr: int = 44100, depth: float = 0.55, release: float = 0.16) -> np.ndarray:
    """A gain curve that dips on every kick and recovers: the pumping of sidechain compression."""
    g = np.ones(n, dtype=np.float32)
    rl = int(release * 5 * sr)
    tail = (1 - depth * np.exp(-np.arange(rl) / (release * sr))).astype(np.float32)
    for t in hits:
        i = int(t * sr)
        if i >= n:
            continue
        e = min(rl, n - i)
        g[i:i + e] = np.minimum(g[i:i + e], tail[:e])
    return g
