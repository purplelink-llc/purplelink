#!/usr/bin/env python3.12
"""Render a fixed-length ambient video for uploading: generated chiptune (or none), synthesised ambience, and a pixel-art scene drawn in code.

    python3.12 longform.py --theme campfire --hours 2 --out campfire-2h.mp4
    python3.12 longform.py --theme campfire --hours 1 --no-music --out campfire-ambience-1h.mp4
    python3.12 longform.py --theme study --hours 2 --pomodoro 25/5 --out study-2h.mp4
    python3.12 longform.py --theme halloween --seconds 40 --out test.mp4          # a short test file
    python3.12 longform.py --theme winter --preview-frame 1800 --out frame.png    # one 1920x1080 frame, no video
    python3.12 longform.py --theme campfire --hours 10 --loop-min 20 --sound brown --dark 300 --out b.mp4   # another sound (sounds.py), screen dims after 300 s

The file is 1920x1080 (3840x2160 with --uhd), 30 fps H.264, AAC 192 kbps at 48 kHz, -14 LUFS integrated, true peak under -1 dBTP, faststart. Nothing is loaded from
disk or the network: the music is composed and the sounds and pictures are drawn by code, so there is nothing to license.

How it goes together (see README.md, "Long-form videos"):
    plan     a list of tracks whose key, tempo and mood drift over the length, crossfaded 6 s so there is no seam; the last track fades out
    audio    tracks rendered in worker processes, mixed with the ambience bed (ambience.py), written as 16-bit PCM, loudness measured
    video    the theme draws a 320x180 frame, enlarged exactly 6x; piped to x264 at 10 fps and repeated to 30 (every frame shown 3 times)
    mux      the video is copied, the audio is loudness-normalised in a second ffmpeg pass (linear, so the music's dynamics are kept) and encoded
Audio and video run side by side, each in its own process. The work files sit in `<out>.work/` and are removed when the file is finished
(`--keep-work` keeps them); `--stage audio|video|mux` runs one step, so an interrupted render can continue.
"""
from __future__ import annotations

import argparse
import json
import math
import multiprocessing
import os
import re
import subprocess
import sys
import time
import zlib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

import ambience
import chiptune as c
import px
import sounds
import themes

SR = c.SR
XFADE = 6.0                    # seconds of crossfade between tracks
FADE_IN_AUDIO, FADE_OUT_AUDIO = 3.0, 8.0
FADE_IN_VIDEO, FADE_OUT_VIDEO = 2.0, 5.0
LOOP_XF = 4.0                  # seconds of equal-power crossfade that join the end of a loop to its start
TARGET_LUFS, TARGET_TP, TARGET_LRA = -14.0, -2.0, 20.0     # a true-peak ceiling of -2 leaves room for the AAC encoder's overshoot, so the file stays under -1 dBTP
MUSIC_RMS = 0.13               # each track is levelled to this before mixing (the same level the 24/7 stream uses)
PRE_RMS = 0.15                 # the pre-master's RMS: about -14 LUFS for this kind of music, so the loudness pass only trims a little
MAX_BPM_STEP = 8
SOUND_RMS = 0.13               # a synthetic sound (noise, rain, drone...) is levelled to this before the bed is added, as music is to MUSIC_RMS
DARK_FADE = 20.0               # seconds the picture takes to dim to near black in a --dark video
DARK_COLOR = "0x040404"
DARK_SEGMENT = 600.0           # seconds in the one black clip that a dark video repeats by stream copy
# the lofi sound: the chiptune engine, slowed and softened (a warm electric-piano lead, soft kit with vinyl crackle, a duller top end)
LOFI_CFG = {"modes": {"major": 3, "dorian": 3, "lydian": 1, "mixolydian": 2}, "eras": ["16bit"], "mood": (0.0, 0.1),
            "sound": {"lead": ["fm_ep", "flute"], "arp": ["fm_ep", "pluck"], "pad": "warm_pad", "bass": "sub_sine", "kit": "lofi", "wet": 0.3, "cut": 5200,
                      "crackle": True, "duck": False, "risers": False, "spark": False, "chorus": True}}
VIDEO_SIZE = (1920, 1080)
UHD_SIZE = (3840, 2160)        # --uhd: the 1080p picture (pixel art at exactly 6x) enlarged exactly 2x, so every art pixel is a 12x12 block
HD = VIDEO_SIZE[0] // px.W      # 6
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, file=sys.stderr, flush=True)


# ------------------------------------------------------------------------------------------------------------------------ the plan
def mood_wave(frac_time: float, seconds: float, lo: float, hi: float, period: float = 2700.0) -> float:
    """The music's mood (0 = soft lofi, 1 = driving) at a moment: a slow cosine between lo and hi with about 45 minutes per wave, starting low."""
    if hi <= lo:
        return lo
    x = 0.5 - 0.5 * math.cos(2 * math.pi * (frac_time * seconds) / period)
    return lo + (hi - lo) * x


def music_cfg(theme_cls, sound: str = "chiptune") -> dict:
    """The music settings for a sound: the theme's own for chiptune, the slowed and softened ones for lofi."""
    return LOFI_CFG if sound == "lofi" else theme_cls.music


def plan_tracks(theme_cls, seconds: float, seed: int, cfg: dict | None = None) -> list[dict]:
    """The tracks for a video, in order, as dicts with seed, era, mood, start (seconds into the video), seconds, key, mode, bpm. The next track is
    skipped if it repeats the previous key or jumps the tempo by more than MAX_BPM_STEP, so the music wanders instead of lurching."""
    cfg = cfg or theme_cls.music
    lo, hi = cfg["mood"]
    out, total, s, prev = [], 0.0, seed * 1000, None
    while total < seconds + 2.0:
        era = cfg["eras"][len(out) % len(cfg["eras"])]
        mood = mood_wave(min(1.0, total / seconds), seconds, lo, hi)
        t = c.plan(s, era, mood, cfg.get("modes"))
        s += 1
        if prev is not None and (t.key == prev.key or abs(t.bpm - prev.bpm) > MAX_BPM_STEP):
            continue
        start = total - (XFADE if prev else 0.0)               # each track begins inside the end of the one before, where they crossfade
        out.append({"seed": t.seed, "era": era, "mood": round(mood, 3), "start": start, "seconds": t.seconds, "key": t.key, "mode": t.mode, "bpm": t.bpm})
        total = start + t.seconds
        prev = t
    return out


def bpm_lookup(tracks: list[dict]):
    starts = [t["start"] for t in tracks]

    def bpm_at(ts: float) -> int:
        i = max(0, int(np.searchsorted(starts, ts, side="right")) - 1)
        return tracks[i]["bpm"]
    return bpm_at


def leveled(audio: np.ndarray) -> np.ndarray:
    rms = float(np.sqrt(np.mean(audio ** 2)))
    peak = float(np.max(np.abs(audio)))
    gain = min(1.25, max(0.5, MUSIC_RMS / rms if rms else 1.0))
    if peak * gain > 0.9:
        gain = 0.9 / peak
    return audio * gain


def render_track(spec: dict, modes: dict | None, sound: dict | None) -> np.ndarray:
    """Runs in a worker process (a track needs a few hundred MB while it renders; a fresh process hands it all back)."""
    t = c.plan(spec["seed"], spec["era"], spec["mood"], modes)
    if sound:
        t.sound.update({k: (list(v) if isinstance(v, list) else v) for k, v in sound.items()})
    audio = c.render(t)[:, : int(t.seconds * SR)]            # drop the reverb tail: under a crossfade it is only a dip
    return leveled(audio)


# ------------------------------------------------------------------------------------------------------------------------ audio
def soft_clip(x: np.ndarray, knee: float = 0.7) -> np.ndarray:
    """Leaves everything under `knee` alone and rounds anything above it toward 0.97, so a crackle pop never hard-clips."""
    a = np.abs(x)
    over = a > knee
    if not over.any():
        return x
    y = x.copy()
    y[over] = np.sign(x[over]) * (knee + (0.97 - knee) * np.tanh((a[over] - knee) / (0.97 - knee)))
    return y


def build_audio(theme, tracks: list[dict], seconds: float, work: Path, music: bool, workers: int, pomodoro: bool, loop_tail: float = 0.0,
                sound: str = "chiptune", bed_on: bool = True, seed: int = 1) -> dict:
    """Mixes music, ambience and (for a Pomodoro video) chimes into float32 on disk, then writes the pre-master as s16 PCM. Returns stats.
    With `loop_tail` the mix runs that many seconds past the loop, the overrun is crossfaded (equal power) into the start, and the pre-master is the
    loop alone with no fades: played end to start it has no click or gap."""
    n = int(round(seconds * SR))
    mm_path = work / "mix.f32"
    mm = np.memmap(mm_path, dtype=np.float32, mode="w+", shape=(2, n))
    cfg = music_cfg(type(theme), sound)
    sp = sounds.spec(sound)
    step = SR * 60
    src = None
    if sp.build is not None:                                       # a synthetic sound instead of music: noise, binaural beats, rain...
        period = n - int(round(loop_tail * SR)) if loop_tail > 0 else n
        src = sounds.make(sound, seconds, seed, period)
        for i in range(0, n, step):
            j = min(n, i + step)
            mm[:, i:j] += src.block(j - i) * np.float32(SOUND_RMS)
    if music:
        xf = int(XFADE * SR)
        fade_in = np.sin(np.linspace(0, np.pi / 2, xf)).astype(np.float32)
        fade_out = np.cos(np.linspace(0, np.pi / 2, xf)).astype(np.float32)
        ctx = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(max_workers=workers, mp_context=ctx, max_tasks_per_child=1) as pool:
            futs, nxt = {}, 0
            for i, spec in enumerate(tracks):
                while nxt < len(tracks) and nxt < i + workers + 1:
                    futs[nxt] = pool.submit(render_track, tracks[nxt], cfg.get("modes"), cfg.get("sound"))
                    nxt += 1
                a = futs.pop(i).result()
                s0 = int(round(spec["start"] * SR))
                if s0 >= n:
                    break
                m = min(a.shape[1], n - s0)
                a = a[:, :m]
                if i == 0:
                    mm[:, s0:s0 + m] = a
                else:
                    k = min(xf, m)
                    mm[:, s0:s0 + k] = mm[:, s0:s0 + k] * fade_out[:k] + a[:, :k] * fade_in[:k]
                    mm[:, s0 + k:s0 + m] = a[:, k:]
                log(f"audio: track {i + 1}/{len(tracks)} in place ({spec['key']} {spec['mode']}, {spec['bpm']} BPM, {spec['era']}), {s0 / SR / 3600:.2f} h")
    # ambience bed
    if src is not None:
        layers = {k: v for k, v in (theme.bed_solo or theme.bed).items() if k not in sp.drop}
        level = sp.bed_level
    else:
        layers = dict(theme.bed if music else (theme.bed_solo or theme.bed))
        level = theme.music_bed_level if music else 1.0
    layers = {k: v * level for k, v in layers.items()}
    layers["room"] = max(layers.get("room", 0.0), 0.3 if src is None else 0.05)
    if bed_on and level > 0:
        bed = ambience.Bed(layers, seconds, seed=theme.seed, events=theme.audio_events(), rain=theme.rain_spans() if "rain" not in sp.drop else [])
        for i in range(0, n, step):
            j = min(n, i + step)
            mm[:, i:j] += bed.block(j - i)
    if pomodoro:
        import chime
        for t0 in np.arange(0.0, seconds, chime.CYCLE):
            for kind, off in chime.BOUNDARIES.items():
                tb = t0 + off
                if tb < 20 or tb > seconds - 20:
                    continue
                body, duck = chime.make_chime(kind)
                i = int(tb * SR)
                m = min(body.shape[1], n - i)
                mm[:, i:i + m] = mm[:, i:i + m] * duck[:m] + body[:, :m]
    if loop_tail > 0:
        xf = int(round(loop_tail * SR))
        n -= xf                                                     # the loop's own length; the overrun becomes the crossfade into the start
        k = np.linspace(0.0, 1.0, xf, dtype=np.float64)
        head = np.asarray(mm[:, :xf], dtype=np.float64)
        tail = np.asarray(mm[:, n:n + xf], dtype=np.float64)
        mm[:, :xf] = (head * np.sin(k * np.pi / 2) + tail * np.cos(k * np.pi / 2)).astype(np.float32)
    if src is not None:                                             # tones and swells repeat exactly once per loop, so they go in after the crossfade
        for i in range(0, n, step):
            j = min(n, i + step)
            mm[:, i:j] += src.periodic(i, j - i) * np.float32(SOUND_RMS)
    mm.flush()
    # loudness of the raw mix, then the pre-master with fades and a soft clip
    ss, cnt, pk = 0.0, 0, 0.0
    for i in range(0, n, step):
        x = np.asarray(mm[:, i:min(n, i + step)], dtype=np.float64)
        ss += float((x ** 2).sum())
        cnt += x.size
        pk = max(pk, float(np.abs(x).max()))
    rms = math.sqrt(ss / max(1, cnt))
    gain = PRE_RMS / rms if rms > 0 else 1.0
    if src is not None and pk > 0:                                  # rain drops and thunder are far peakier than music: keep the pre-master out of the soft clip
        gain = min(gain, 0.85 / pk)
    pcm_path = work / "audio.pcm"
    fi, fo = (0, 0) if loop_tail > 0 else (int(FADE_IN_AUDIO * SR), int(FADE_OUT_AUDIO * SR))
    peak = 0.0
    with open(pcm_path, "wb") as f:
        for i in range(0, n, step):
            j = min(n, i + step)
            x = np.asarray(mm[:, i:j], dtype=np.float32) * np.float32(gain)
            idx = np.arange(i, j)
            env = np.ones(j - i, np.float32)
            if fi and i < fi:
                env[: min(fi - i, j - i)] = (0.5 - 0.5 * np.cos(np.pi * np.arange(i, min(fi, j)) / fi)).astype(np.float32)
            if fo and j > n - fo:
                lo = max(i, n - fo)
                env[lo - i:] = (0.5 + 0.5 * np.cos(np.pi * (idx[lo - i:] - (n - fo)) / fo)).astype(np.float32)
            x = soft_clip(x * env)
            peak = max(peak, float(np.abs(x).max()))
            f.write((x.T * 32767.0).astype("<i2").tobytes())
    del mm
    os.remove(mm_path)
    return {"samples": n, "rms_before": rms, "gain": gain, "peak": peak}


def measure_loudness(pcm: Path) -> dict:
    """Integrated loudness of the pre-master with ffmpeg's ebur128 meter, one pass at the file's own rate. (loudnorm resamples everything to 192 kHz,
    which took hours on a two-hour file.) The mux applies a fixed gain to the target and a limiter, which is what loudnorm's linear mode does."""
    cmd = [FFMPEG, "-hide_banner", "-nostats", "-f", "s16le", "-ar", str(SR), "-ac", "2", "-i", str(pcm),
           "-af", "ebur128=framelog=quiet", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    if not m:
        raise RuntimeError("could not read the ebur128 measurement:\n" + r.stderr[-800:])
    return {"input_i": m[-1], "method": "ebur128"}


def audio_stage(theme, tracks, seconds, work: Path, music: bool, workers: int, pomodoro: bool, loop_tail: float = 0.0,
                sound: str = "chiptune", bed_on: bool = True, seed: int = 1) -> None:
    stats = build_audio(theme, tracks, seconds, work, music, workers, pomodoro, loop_tail, sound, bed_on, seed)
    stats["sound"], stats["target_lufs"] = sound, sounds.target_lufs(sound)
    meas = measure_loudness(work / "audio.pcm")
    stats["loudnorm"] = meas
    (work / "audio.json").write_text(json.dumps(stats, indent=1))
    log(f"audio done: pre-master {meas['input_i']} LUFS, sample peak {stats['peak']:.3f}")


# ------------------------------------------------------------------------------------------------------------------------ video
X264 = ["-c:v", "libx264", "-preset", "veryfast", "-tune", "animation", "-crf", "19", "-profile:v", "high", "-level", "4.1",
        "-maxrate", "9M", "-bufsize", "18M", "-g", "60", "-keyint_min", "60", "-sc_threshold", "0", "-r", "30", "-an"]
# 4K: level 5.1 (3840x2160 at 30 fps is within it), a higher rate ceiling for the 12x12 blocks' edges, the same keyframe spacing and the same tune
X264_UHD = ["-c:v", "libx264", "-preset", "veryfast", "-tune", "animation", "-crf", "20", "-profile:v", "high", "-level", "5.1",
            "-maxrate", "24M", "-bufsize", "48M", "-g", "60", "-keyint_min", "60", "-sc_threshold", "0", "-r", "30", "-an"]
# the exact enlargement: after the fades and the colour conversion (so the work is done at 1080p), by copying each pixel into a 2x2 block
UHD_SCALE = f"scale={UHD_SIZE[0]}:{UHD_SIZE[1]}:flags=neighbor"


def out_size(uhd: bool) -> tuple:
    return UHD_SIZE if uhd else VIDEO_SIZE


def video_cmd(seconds: float, fps: int, out: Path, fades: bool = True, dark: float = 0.0, uhd: bool = False) -> list[str]:
    """`dark` (seconds, with `seconds` = dark + DARK_FADE): the picture fades in, then dims to near black from `dark` to the end of the clip.
    `uhd`: the piped 1920x1080 frames leave as 3840x2160, each pixel copied into a 2x2 block (nearest neighbour, no smoothing)."""
    if dark:
        fade = (f"fps=30,fade=t=in:st=0:d={FADE_IN_VIDEO},fade=t=out:st={dark:.3f}:d={DARK_FADE}:color={DARK_COLOR},format=yuv420p")
    elif fades:
        fade = f"fps=30,fade=t=in:st=0:d={FADE_IN_VIDEO},fade=t=out:st={max(0.0, seconds - FADE_OUT_VIDEO):.3f}:d={FADE_OUT_VIDEO},format=yuv420p"
    else:
        fade = "fps=30,format=yuv420p"
    if uhd:
        fade += "," + UHD_SCALE
    return [FFMPEG, "-hide_banner", "-loglevel", "warning", "-y",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-video_size", f"{VIDEO_SIZE[0]}x{VIDEO_SIZE[1]}", "-framerate", str(fps), "-i", "pipe:0",
            "-vf", fade, *(X264_UHD if uhd else X264), str(out)]


def black_cmd(seconds: float, fps: int, out: Path, uhd: bool = False) -> list[str]:
    """A near-black clip encoded exactly like the picture (same size, rate and x264 settings), so the two can be joined by stream copy."""
    w, h = out_size(uhd)
    return [FFMPEG, "-hide_banner", "-loglevel", "warning", "-y", "-f", "lavfi", "-i", f"color=c={DARK_COLOR}:s={w}x{h}:r={fps}",
            "-t", f"{seconds:.3f}", "-vf", "fps=30,format=yuv420p", *(X264_UHD if uhd else X264), str(out)]


def write_dark_list(work: Path, intro_s: float, final_s: float, black_s: float) -> Path:
    """The ffmpeg concat list for a dark video: the intro once, then the black clip as many times as the length needs."""
    reps = max(1, int(math.ceil((final_s - intro_s) / black_s)) + 1)
    lines = [f"file '{work / 'intro.mp4'}'"] + [f"file '{work / 'black.mp4'}'"] * reps
    p = work / "dark.txt"
    p.write_text("\n".join(lines) + "\n")
    return p


_THEME_CACHE: dict = {}


def render_chunk(theme_name: str, seed: int, seconds: float, options: dict, tracks: list, n0: int, n1: int, loop_s: float = 0.0) -> list[bytes]:
    """Runs in a worker process: the 320x180 frames n0..n1-1 as raw RGB bytes. (The flame in the fire themes is stepped frame to frame, so each chunk
    starts it fresh with a short warm-up: once per chunk the flicker pattern changes, which looks like any other flicker.)"""
    key = (theme_name, seed, seconds)
    if key not in _THEME_CACHE:
        _THEME_CACHE.clear()
        _THEME_CACHE[key] = themes.get(theme_name)(seed, seconds, bpm_at=bpm_lookup(tracks), options=options)
    th = _THEME_CACHE[key]
    out = []
    for n in range(n0, n1):
        t = n / th.fps
        im = th.frame(t)
        if loop_s and t < LOOP_XF:                                  # the loop's first seconds fade in from the frames that follow its end
            im = Image.blend(th.frame(t + loop_s).convert("RGB"), im.convert("RGB"), t / LOOP_XF)
        out.append(im.tobytes())
    return out


def video_stage(theme, seconds: float, work: Path, spec: dict, workers: int = 2, chunk_seconds: float = 30.0, loop: bool = False, dark: float = 0.0,
                final_s: float = 0.0, uhd: bool = False) -> None:
    """Draws the frames in worker processes (a chunk of `chunk_seconds` each, handed back in order), enlarges each exactly 6x here, draws any overlay,
    and pipes it to x264. With `loop` the picture is a loop (loop.mp4, no fades) that the mux repeats by stream copy."""
    fps = theme.fps
    assert 30 % fps == 0, "the video rate must divide 30 so every frame is shown the same number of times"
    drawn = dark + DARK_FADE if dark else seconds                  # a dark video only draws the part that is seen, then the black clip takes over
    out = work / ("intro.mp4" if dark else "loop.mp4" if loop else "video.mp4")
    proc = subprocess.Popen(video_cmd(drawn, fps, out, fades=not loop, dark=dark, uhd=uhd), stdin=subprocess.PIPE)
    total = int(round(drawn * fps))
    per = max(1, int(chunk_seconds * fps))
    bounds = [(n, min(total, n + per)) for n in range(0, total, per)]
    t0 = time.time()
    ctx = multiprocessing.get_context("spawn")
    try:
        with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as pool:
            futs, nxt = {}, 0
            for i, (n0, n1) in enumerate(bounds):
                while nxt < len(bounds) and nxt < i + workers + 1:
                    futs[nxt] = pool.submit(render_chunk, spec["theme"], spec["seed"], spec["seconds"], spec["options"], spec["tracks"], *bounds[nxt],
                                            seconds if loop and not dark else 0.0)
                    nxt += 1
                for k, raw in enumerate(futs.pop(i).result()):
                    ts = (n0 + k) / fps
                    hd = Image.frombytes("RGB", (px.W, px.H), raw).resize(VIDEO_SIZE, Image.NEAREST)
                    theme.overlay(hd, ts)
                    proc.stdin.write(hd.tobytes())
                el = time.time() - t0
                log(f"video: {n1 / fps / 60:.0f} of {drawn / 60:.0f} min drawn, {el / (n1 / fps / 3600):.0f} s of work per hour of video so far")
    finally:
        try:
            proc.stdin.close()
        except OSError:
            pass
        rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg video encode failed with exit {rc}")
    if dark:
        black_s = min(DARK_SEGMENT, max(10.0, (final_s or seconds) - drawn + 5.0))
        subprocess.run(black_cmd(black_s, fps, work / "black.mp4", uhd), check=True)
        write_dark_list(work, drawn, final_s or seconds, black_s)
    (work / "video.json").write_text(json.dumps({"frames": total, "loop_seconds": seconds if loop else 0, "dark_seconds": dark, "uhd": uhd,
                                                 "seconds_of_work": round(time.time() - t0, 1)}))


# ------------------------------------------------------------------------------------------------------------------------ mux
def master_af(meas: dict, limit_db: float = TARGET_TP, target: float = TARGET_LUFS) -> str:
    """A fixed gain to the loudness target and a limiter under the true-peak ceiling: what loudnorm's linear mode does, without its 192 kHz resample."""
    gain = target - float(meas["input_i"])
    return f"volume={gain:.2f}dB,alimiter=limit={10 ** (limit_db / 20):.4f}:attack=5:release=50:level=0,aresample=48000"


def true_peak(path: Path) -> float | None:
    """True peak of a finished file's audio in dBTP (ebur128, 4x oversampled)."""
    r = subprocess.run([FFMPEG, "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af", "ebur128=peak=true:framelog=quiet", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r.stderr[r.stderr.rfind("Summary:"):])
    return float(m[-1]) if m else None


def mux_cmd(work: Path, meas: dict, seconds: float, out: Path, title: str | None = None, loop: bool = False, fades: bool = False,
            limit_db: float = TARGET_TP, target: float = TARGET_LUFS, video_in: list | None = None) -> list[str]:
    """The finished file. `loop`: repeat loop.mp4 (stream copy) and the PCM loop (raw samples, so the repeats join with no encoder gap) to `seconds`,
    with one AAC encode of the whole length. `fades`: an audio fade in and out at the ends of the full-length file."""
    af = master_af(meas, limit_db, target)
    if fades:
        af += f",afade=t=in:d={FADE_IN_AUDIO},afade=t=out:st={max(0.0, seconds - FADE_OUT_AUDIO):.3f}:d={FADE_OUT_AUDIO}"
    rep = ["-stream_loop", "-1"] if loop else []
    video = video_in if video_in is not None else rep + ["-i", str(work / ("loop.mp4" if loop else "video.mp4"))]
    audio = rep + ["-f", "s16le", "-ar", str(SR), "-ac", "2", "-i", str(work / "audio.pcm")]
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "warning", "-y", *video, *audio,
           "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-af", af, "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{seconds:.3f}",
           "-movflags", "+faststart"]
    if title:
        cmd += ["-metadata", f"title={title}"]
    return cmd + [str(out)]


def loop_path(out: Path, loop_s: float) -> Path:
    return out.with_name(f"{out.stem}-loop{loop_s / 60:g}min{out.suffix}")


def mux_stage(work: Path, seconds: float, out: Path) -> None:
    """Writes under a temporary name and renames, so an interrupted mux leaves no finished-looking file. For a loop render it writes two files: the
    bare loop (`<name>-loop<L>min.mp4`, which plays seamlessly on repeat) and the full length."""
    aj = json.loads((work / "audio.json").read_text())
    meas, target = aj["loudnorm"], float(aj.get("target_lufs", TARGET_LUFS))
    vj = work / "video.json"                                        # the finished picture says which file it is; a stale partial file never decides
    vinfo = json.loads(vj.read_text()) if vj.exists() else {}
    loop_s, dark = float(vinfo.get("loop_seconds") or 0), float(vinfo.get("dark_seconds") or 0)
    jobs = [(loop_path(out, loop_s), loop_s, False), (out, seconds, True)] if loop_s else [(out, seconds, False)]
    limit_db = TARGET_TP
    for k, (dest, length, fades) in enumerate(jobs):
        part = dest.with_name(dest.stem + ".part" + dest.suffix)
        video_in = None
        if dark:                                                    # the bare loop shows the black clip; the full file is the dimming intro, then black
            video_in = (["-f", "concat", "-safe", "0", "-i", str(work / "dark.txt")] if length == seconds
                        else ["-stream_loop", "-1", "-i", str(work / "black.mp4")])
        for _ in range(4):
            subprocess.run(mux_cmd(work, meas, length, part, loop=bool(loop_s), fades=fades, limit_db=limit_db, target=target, video_in=video_in), check=True)
            if k or not loop_s:
                break
            # sharp transients (fire crackle) can overshoot the limiter after AAC: measure the loop, pull the limiter down by the excess
            tp = true_peak(part)
            if tp is None or tp <= TARGET_TP + 0.8:
                break
            limit_db -= tp - TARGET_TP
            log(f"loop true peak {tp:+.1f} dBTP; limiter lowered to {limit_db:.1f} dB")
        part.replace(dest)


def clean_work(work: Path) -> None:
    """Removes the work files by name (never a pattern or a variable-rooted wildcard), then the folder if nothing else is in it."""
    for name in ("mix.f32", "audio.pcm", "audio.json", "video.mp4", "loop.mp4", "intro.mp4", "black.mp4", "dark.txt", "video.json", "plan.json"):
        p = work / name
        if p.is_file():
            p.unlink()
    try:
        work.rmdir()
    except OSError:
        pass


# ------------------------------------------------------------------------------------------------------------------------ the command line
def build_theme(args, tracks=None):
    cls = themes.get(args.theme)
    seconds = args.seconds if args.seconds else args.hours * 3600.0
    options = {}
    if args.pomodoro:
        if not cls.is_study:
            sys.exit("--pomodoro is for study themes only")
        try:
            f, b = (int(x) for x in args.pomodoro.split("/"))
        except ValueError:
            sys.exit("--pomodoro takes minutes as FOCUS/BREAK, for example 25/5")
        options["pomodoro"] = (f, b)
    if args.season:
        options["season"] = args.season
    if getattr(args, "view", ""):
        options["view"] = args.view
    tracks = tracks if tracks is not None else plan_tracks(cls, seconds, args.seed, music_cfg(cls, args.sound))
    return cls(args.seed, seconds, bpm_at=bpm_lookup(tracks), options=options), tracks, seconds


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--theme", required=True, help="one of: " + ", ".join(themes.names()))
    ap.add_argument("--hours", type=float, default=2.0)
    ap.add_argument("--seconds", type=float, default=0.0, help="a length in seconds instead of --hours (tests)")
    ap.add_argument("--out", required=True, help="the .mp4 to write (or a .png with --preview-frame)")
    ap.add_argument("--seed", type=int, default=None, help="changes the music, the events and the details of the scene; the default depends on the theme")
    ap.add_argument("--no-music", action="store_true", help="ambience only: no chiptune (same as a synthetic --sound, which never has music)")
    ap.add_argument("--sound", default="chiptune", choices=sounds.NAMES,
                    help="what plays: chiptune (the default), lofi, brown/pink/white noise, binaural-alpha/theta/delta, synth, rain, thunderstorm, fireplace, ocean, wind, fan, airplane")
    ap.add_argument("--no-bed", action="store_true", help="drop the theme's ambience bed (fire, wind, crickets) from the sound")
    ap.add_argument("--dark", type=float, default=0.0, metavar="SECONDS",
                    help="dim the picture to near black after this many seconds (the sound goes on); for sleep videos")
    ap.add_argument("--pomodoro", default="", help="study themes only: draw a Pomodoro timer, FOCUS/BREAK minutes, for example 25/5")
    ap.add_argument("--season", default="", help="study theme: halloween, christmas or newyear decor")
    ap.add_argument("--view", default="", choices=["", "fireplace"],
                    help="winter theme: frame the fireplace large (the fire, the mantel and the stockings) instead of the whole room")
    ap.add_argument("--uhd", action="store_true",
                    help="3840x2160 output: the 1080p picture enlarged exactly 2x (nearest neighbour) in the loop's encode; YouTube labels a 2160p file 4K")
    ap.add_argument("--workers", type=int, default=2, help="processes rendering music, and separately drawing frames, at once")
    ap.add_argument("--stage", choices=["all", "audio", "video", "mux"], default="all")
    ap.add_argument("--keep-work", action="store_true")
    ap.add_argument("--loop-min", type=float, default=0.0,
                    help="render a seamless loop of this many minutes (picture and music) and repeat it to --hours by stream copy; 10 to 20 is typical")
    ap.add_argument("--preview-frame", type=float, default=None, help="write one frame at this many seconds to --out as a PNG and stop")
    a = ap.parse_args(argv)
    if a.seed is None:
        a.seed = zlib.crc32(a.theme.encode()) % 900 + 1
    out = Path(a.out).expanduser().resolve()
    if a.preview_frame is not None:
        theme, _, _ = build_theme(a)
        hd = theme.frame(a.preview_frame).resize(VIDEO_SIZE, Image.NEAREST)
        theme.overlay(hd, a.preview_frame)
        hd.save(out)
        print(out)
        return
    final = a.seconds if a.seconds else a.hours * 3600.0
    loop_s = a.loop_min * 60.0 if 0 < a.loop_min * 60.0 < final else 0.0
    if loop_s:                                                      # the scene and music are made for the loop plus the crossfade overrun only
        b = argparse.Namespace(**vars(a)); b.seconds = loop_s + LOOP_XF
        theme, tracks, render_s = build_theme(b)
    else:
        theme, tracks, render_s = build_theme(a)
    seconds = final
    work = out.parent / (out.name + ".work")
    work.mkdir(parents=True, exist_ok=True)
    music = sounds.spec(a.sound).musical and not a.no_music
    if a.dark and loop_s and a.dark + DARK_FADE > loop_s:
        sys.exit("--dark plus its 20 s fade must be shorter than the loop (--loop-min)")
    kind = f"{a.sound} sound" if not sounds.spec(a.sound).musical else ("music + ambience" if music else "ambience only")
    log(f"{a.theme}: {seconds / 3600:.2f} h{f' from a {loop_s / 60:g} min loop' if loop_s else ''}, seed {a.seed}, "
        f"{kind}{'' if not a.dark else f', dark after {a.dark:g} s'}, {len(tracks)} tracks planned")
    (work / "plan.json").write_text(json.dumps({"theme": a.theme, "seed": a.seed, "seconds": seconds, "music": music, "sound": a.sound, "dark": a.dark, "tracks": tracks if music else [],
                                                "events": theme.events}, indent=1))
    spec = {"theme": a.theme, "seed": a.seed, "options": theme.options, "tracks": tracks, "seconds": render_s}
    t0 = time.time()

    def do_audio():
        audio_stage(theme, tracks, render_s, work, music, a.workers, bool(a.pomodoro), loop_tail=LOOP_XF if loop_s else 0.0,
                    sound=a.sound, bed_on=not a.no_bed, seed=a.seed)

    def do_video():
        video_stage(theme, loop_s or seconds, work, spec, a.workers, loop=bool(loop_s), dark=a.dark, final_s=seconds, uhd=a.uhd)

    if a.stage == "audio":
        do_audio()
        return
    if a.stage == "video":
        do_video()
        return
    if a.stage == "mux":
        mux_stage(work, seconds, out)
        return

    # all: audio in a child process while this one draws the video
    child = None
    if not (work / "audio.json").exists():
        cmd = [sys.executable, str(Path(__file__).resolve())] + [x for x in (argv if argv is not None else sys.argv[1:])] + ["--stage", "audio"]
        child = subprocess.Popen(cmd)
    if not (work / "video.json").exists():
        do_video()
    if child is not None and child.wait() != 0:
        sys.exit("the audio stage failed")
    mux_stage(work, seconds, out)
    if not a.keep_work:
        clean_work(work)
    log(f"finished {out.name} in {(time.time() - t0) / 60:.1f} min ({(time.time() - t0) / 3600 / (seconds / 3600):.2f} h of work per hour of video)")


if __name__ == "__main__":
    main()
