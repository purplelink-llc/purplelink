#!/usr/bin/env python3
"""assets/clink.wav: a short link-clink for each reveal in the chain videos (two bright partials with a fast decay and a tiny click)."""
import wave, numpy as np
from pathlib import Path
sr = 44100; n = int(sr * 0.55); t = np.arange(n) / sr
rng = np.random.default_rng(7)
y = (0.55 * np.sin(2 * np.pi * 2093 * t) * np.exp(-t * 11) + 0.35 * np.sin(2 * np.pi * 3136 * t) * np.exp(-t * 14) + 0.2 * np.sin(2 * np.pi * 4186 * t) * np.exp(-t * 20))
click = rng.standard_normal(int(sr * 0.012)) * np.exp(-np.arange(int(sr * 0.012)) / (sr * 0.003)) * 0.25
y[:len(click)] += click
y = y / max(1e-9, np.abs(y).max()) * 0.8
out = Path(__file__).resolve().parent / "assets" / "clink.wav"
with wave.open(str(out), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((y * 32767).astype("<i2").tobytes())
print("wrote", out)
