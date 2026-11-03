#!/usr/bin/env python3
"""Audio for the Circled Hoops ads: narration, the app's own UI sounds, and a synthesised bed.

    python3 mix-circledhoops.py spec.json out.wav

spec: {"dur", "vo": [{"file", "t"}], "sfx": [{"file", "t", "gain_db"}],
       "bed": {"style": {...}, "seed", "gain_db", "drop", "duck_db", "out_at"}}

The bed comes from TikTokPipeline's trends/bed.py (oscillators and noise only, no samples). Before `drop` it is
low-passed (the quiet hook), then opens up. It ducks by `duck_db` under the narration. The result is normalised
to -14 LUFS integrated, true peak -1.5 dB, with ffmpeg's two-pass loudnorm, then a
limiter at -2 dBFS so the AAC encode stays under -1 dBTP.
"""
import json
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, lfilter

SR = 48000
sys.path.insert(0, "/Volumes/Extreme SSD/TikTokPipeline/shared_media")


def load(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype="<f4").reshape(-1, 2).T.copy()


def place(buf, x, t, gain=1.0):
    i = int(round(t * SR))
    if i >= buf.shape[1]:
        return
    if i < 0:
        x, i = x[:, -i:], 0
    n = min(x.shape[1], buf.shape[1] - i)
    buf[:, i:i + n] += x[:, :n] * gain


def smooth(env, ms):
    k = max(1, int(SR * ms / 1000))
    return np.convolve(env, np.ones(k) / k, mode="same")


def write_wav(path, x):
    pcm = (np.clip(x, -1, 1).T * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())


def main(spec_path, out_wav):
    spec = json.loads(Path(spec_path).read_text())
    n = int(round(spec["dur"] * SR))
    vo = np.zeros((2, n), "f4")
    for v in spec["vo"]:
        place(vo, load(v["file"]), v["t"], 10 ** (v.get("gain_db", 0) / 20))
    fx = np.zeros((2, n), "f4")
    for s in spec.get("sfx", []):
        place(fx, load(s["file"]), s["t"], 10 ** (s.get("gain_db", 0) / 20))

    b = spec["bed"]
    from trends.bed import render_bed
    with tempfile.TemporaryDirectory() as td:
        render_bed(b["style"], spec["dur"] + 1, Path(td) / "bed.wav", seed=b.get("seed", 0))
        bed = load(Path(td) / "bed.wav")[:, :n]
    if bed.shape[1] < n:
        bed = np.pad(bed, ((0, 0), (0, n - bed.shape[1])))
    lo_b, lo_a = butter(2, 380 / (SR / 2), "low")
    low = lfilter(lo_b, lo_a, bed, axis=1) * 1.6
    drop = int(b.get("drop", 0) * SR)
    mixk = np.clip((np.arange(n) - drop) / (0.08 * SR), 0, 1)
    bed = low * (1 - mixk) + bed * mixk
    env = smooth(np.abs(vo).mean(axis=0), 30)
    on = smooth((env > 0.01).astype("f4"), 160)
    duck = 10 ** (-b.get("duck_db", 8) * np.clip(on * 1.5, 0, 1) / 20)
    bed *= 10 ** (b.get("gain_db", -14) / 20) * duck
    if b.get("out_at"):
        k = np.clip((np.arange(n) - b["out_at"] * SR) / (1.2 * SR), 0, 1)
        bed *= 1 - k
    mix = vo + fx + bed
    fade = int(0.25 * SR)
    mix[:, -fade:] *= np.linspace(1, 0, fade)

    with tempfile.TemporaryDirectory() as td:
        raw = Path(td) / "raw.wav"
        write_wav(raw, mix)
        m = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(raw), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
                            "-f", "null", "-"], capture_output=True, text=True).stderr
        j = json.loads(m[m.rindex("{"):m.rindex("}") + 1])
        af = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:"
              f"measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true,"
              "alimiter=limit=0.8:attack=1:release=60:level=disabled")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-af", af, "-ar", str(SR), str(out_wav)], check=True)
    print(f"mixed {out_wav} ({spec['dur']:.2f} s, input {j['input_i']} LUFS)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
