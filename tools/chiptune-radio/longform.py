#!/usr/bin/env python3.12
"""Render a fixed-length ambient video for uploading: generated chiptune (or none), synthesised ambience, and a pixel-art scene drawn in code.

    python3.12 longform.py --theme campfire --hours 2 --out campfire-2h.mp4
    python3.12 longform.py --theme campfire --hours 1 --no-music --out campfire-ambience-1h.mp4
    python3.12 longform.py --theme study --hours 2 --pomodoro 25/5 --out study-2h.mp4
    python3.12 longform.py --theme halloween --seconds 40 --out test.mp4          # a short test file
    python3.12 longform.py --theme winter --preview-frame 1800 --out frame.png    # one 1920x1080 frame, no video

The file is 1920x1080, 30 fps H.264, AAC 192 kbps at 48 kHz, -14 LUFS integrated, true peak under -1 dBTP, faststart. Nothing is loaded from
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
import themes

SR = c.SR
XFADE = 6.0                    # seconds of crossfade between tracks
FADE_IN_AUDIO, FADE_OUT_AUDIO = 3.0, 8.0
FADE_IN_VIDEO, FADE_OUT_VIDEO = 2.0, 5.0
TARGET_LUFS, TARGET_TP, TARGET_LRA = -14.0, -2.0, 20.0     # a true-peak ceiling of -2 leaves room for the AAC encoder's overshoot, so the file stays under -1 dBTP
MUSIC_RMS = 0.13               # each track is levelled to this before mixing (the same level the 24/7 stream uses)
PRE_RMS = 0.15                 # the pre-master's RMS: about -14 LUFS for this kind of music, so the loudness pass only trims a little
MAX_BPM_STEP = 8
VIDEO_SIZE = (1920, 1080)
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


def plan_tracks(theme_cls, seconds: float, seed: int) -> list[dict]:
    """The tracks for a video, in order, as dicts with seed, era, mood, start (seconds into the video), seconds, key, mode, bpm. The next track is
    skipped if it repeats the previous key or jumps the tempo by more than MAX_BPM_STEP, so the music wanders instead of lurching."""
    cfg = theme_cls.music
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


def build_audio(theme, tracks: list[dict], seconds: float, work: Path, music: bool, workers: int, pomodoro: bool) -> dict:
    """Mixes music, ambience and (for a Pomodoro video) chimes into float32 on disk, then writes the pre-master as s16 PCM. Returns stats."""
    n = int(round(seconds * SR))
    mm_path = work / "mix.f32"
    mm = np.memmap(mm_path, dtype=np.float32, mode="w+", shape=(2, n))
    cfg = type(theme).music
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
    layers = dict(theme.bed if music else (theme.bed_solo or theme.bed))
    level = theme.music_bed_level if music else 1.0
    layers = {k: v * level for k, v in layers.items()}
    layers["room"] = max(layers.get("room", 0.0), 0.3)
    bed = ambience.Bed(layers, seconds, seed=theme.seed, events=theme.audio_events(), rain=theme.rain_spans())
    step = SR * 60
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
    mm.flush()
    # loudness of the raw mix, then the pre-master with fades and a soft clip
    ss, cnt = 0.0, 0
    for i in range(0, n, step):
        x = np.asarray(mm[:, i:min(n, i + step)], dtype=np.float64)
        ss += float((x ** 2).sum())
        cnt += x.size
    rms = math.sqrt(ss / max(1, cnt))
    gain = PRE_RMS / rms if rms > 0 else 1.0
    pcm_path = work / "audio.pcm"
    fi, fo = int(FADE_IN_AUDIO * SR), int(FADE_OUT_AUDIO * SR)
    peak = 0.0
    with open(pcm_path, "wb") as f:
        for i in range(0, n, step):
            j = min(n, i + step)
            x = np.asarray(mm[:, i:j], dtype=np.float32) * np.float32(gain)
            idx = np.arange(i, j)
            env = np.ones(j - i, np.float32)
            if i < fi:
                env[: min(fi - i, j - i)] = (0.5 - 0.5 * np.cos(np.pi * np.arange(i, min(fi, j)) / fi)).astype(np.float32)
            if j > n - fo:
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


def audio_stage(theme, tracks, seconds, work: Path, music: bool, workers: int, pomodoro: bool) -> None:
    stats = build_audio(theme, tracks, seconds, work, music, workers, pomodoro)
    meas = measure_loudness(work / "audio.pcm")
    stats["loudnorm"] = meas
    (work / "audio.json").write_text(json.dumps(stats, indent=1))
    log(f"audio done: pre-master {meas['input_i']} LUFS, sample peak {stats['peak']:.3f}")


# ------------------------------------------------------------------------------------------------------------------------ video
def video_cmd(seconds: float, fps: int, out: Path, fades: bool = True) -> list[str]:
    fade = (f"fps=30,fade=t=in:st=0:d={FADE_IN_VIDEO},fade=t=out:st={max(0.0, seconds - FADE_OUT_VIDEO):.3f}:d={FADE_OUT_VIDEO},format=yuv420p"
            if fades else "fps=30,format=yuv420p")
    return [FFMPEG, "-hide_banner", "-loglevel", "warning", "-y",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-video_size", f"{VIDEO_SIZE[0]}x{VIDEO_SIZE[1]}", "-framerate", str(fps), "-i", "pipe:0",
            "-vf", fade, "-c:v", "libx264", "-preset", "veryfast", "-tune", "animation", "-crf", "19", "-profile:v", "high", "-level", "4.1",
            "-maxrate", "9M", "-bufsize", "18M", "-g", "60", "-keyint_min", "60", "-sc_threshold", "0", "-r", "30", "-an", str(out)]


_THEME_CACHE: dict = {}


def render_chunk(theme_name: str, seed: int, seconds: float, options: dict, tracks: list, n0: int, n1: int) -> list[bytes]:
    """Runs in a worker process: the 320x180 frames n0..n1-1 as raw RGB bytes. (The flame in the fire themes is stepped frame to frame, so each chunk
    starts it fresh with a short warm-up: once per chunk the flicker pattern changes, which looks like any other flicker.)"""
    key = (theme_name, seed, seconds)
    if key not in _THEME_CACHE:
        _THEME_CACHE.clear()
        _THEME_CACHE[key] = themes.get(theme_name)(seed, seconds, bpm_at=bpm_lookup(tracks), options=options)
    th = _THEME_CACHE[key]
    return [th.frame(n / th.fps).tobytes() for n in range(n0, n1)]


def video_stage(theme, seconds: float, work: Path, spec: dict, workers: int = 2, chunk_seconds: float = 30.0, loop_s: float = 0.0) -> None:
    """Draws the frames in worker processes (a chunk of `chunk_seconds` each, handed back in order), enlarges each exactly 6x here, draws any overlay,
    and pipes it to x264. With `loop_s` only the first `loop_s` seconds are drawn (no fades) and repeated to the full length by stream copy, with no
    re-encode: about seconds/loop_s times less drawing. The audio stays unique for the whole length and carries the fade in and out."""
    fps = theme.fps
    assert 30 % fps == 0, "the video rate must divide 30 so every frame is shown the same number of times"
    looping = 0 < loop_s < seconds
    drawn = loop_s if looping else seconds
    out = work / ("loop.mp4" if looping else "video.mp4")
    proc = subprocess.Popen(video_cmd(drawn, fps, out, fades=not looping), stdin=subprocess.PIPE)
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
                    futs[nxt] = pool.submit(render_chunk, spec["theme"], spec["seed"], seconds, spec["options"], spec["tracks"], *bounds[nxt])
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
    if looping:
        log(f"video: {drawn / 60:.0f} min loop drawn; the mux repeats it to {seconds / 60:.0f} min")
    (work / "video.json").write_text(json.dumps({"frames": total, "loop_seconds": drawn if looping else 0,
                                                 "seconds_of_work": round(time.time() - t0, 1)}))


# ------------------------------------------------------------------------------------------------------------------------ mux
def mux_cmd(work: Path, meas: dict, seconds: float, out: Path, title: str | None = None, loop: bool = False) -> list[str]:
    gain = TARGET_LUFS - float(meas["input_i"])
    limit = 10 ** (TARGET_TP / 20)
    af = f"volume={gain:.2f}dB,alimiter=limit={limit:.4f}:attack=5:release=50:level=0,aresample=48000"
    video = ["-stream_loop", "-1", "-i", str(work / "loop.mp4")] if loop else ["-i", str(work / "video.mp4")]
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "warning", "-y", *video,
           "-f", "s16le", "-ar", str(SR), "-ac", "2", "-i", str(work / "audio.pcm"),
           "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-af", af, "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{seconds:.3f}",
           "-movflags", "+faststart"]
    if title:
        cmd += ["-metadata", f"title={title}"]
    return cmd + [str(out)]


def mux_stage(work: Path, seconds: float, out: Path) -> None:
    meas = json.loads((work / "audio.json").read_text())["loudnorm"]
    part = out.with_name(out.stem + ".part" + out.suffix)          # written under a temporary name, so an interrupted mux leaves no finished-looking file
    vj = work / "video.json"                                        # the finished picture says which file it is; a stale partial file never decides
    loop = bool(json.loads(vj.read_text()).get("loop_seconds")) if vj.exists() else (work / "loop.mp4").exists()
    subprocess.run(mux_cmd(work, meas, seconds, part, loop=loop), check=True)
    part.replace(out)


def clean_work(work: Path) -> None:
    """Removes the work files by name (never a pattern or a variable-rooted wildcard), then the folder if nothing else is in it."""
    for name in ("mix.f32", "audio.pcm", "audio.json", "video.mp4", "loop.mp4", "video.json", "plan.json"):
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
    tracks = tracks if tracks is not None else plan_tracks(cls, seconds, args.seed)
    return cls(args.seed, seconds, bpm_at=bpm_lookup(tracks), options=options), tracks, seconds


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--theme", required=True, help="one of: " + ", ".join(themes.names()))
    ap.add_argument("--hours", type=float, default=2.0)
    ap.add_argument("--seconds", type=float, default=0.0, help="a length in seconds instead of --hours (tests)")
    ap.add_argument("--out", required=True, help="the .mp4 to write (or a .png with --preview-frame)")
    ap.add_argument("--seed", type=int, default=None, help="changes the music, the events and the details of the scene; the default depends on the theme")
    ap.add_argument("--no-music", action="store_true", help="ambience only: no chiptune")
    ap.add_argument("--pomodoro", default="", help="study themes only: draw a Pomodoro timer, FOCUS/BREAK minutes, for example 25/5")
    ap.add_argument("--season", default="", help="study theme: halloween, christmas or newyear decor")
    ap.add_argument("--workers", type=int, default=2, help="processes rendering music, and separately drawing frames, at once")
    ap.add_argument("--stage", choices=["all", "audio", "video", "mux"], default="all")
    ap.add_argument("--keep-work", action="store_true")
    ap.add_argument("--video-loop", type=float, default=0.0, help="draw only this many minutes of picture and repeat it (the music stays unique)")
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
    theme, tracks, seconds = build_theme(a)
    work = out.parent / (out.name + ".work")
    work.mkdir(parents=True, exist_ok=True)
    music = not a.no_music
    log(f"{a.theme}: {seconds / 3600:.2f} h, seed {a.seed}, {'music + ambience' if music else 'ambience only'}, {len(tracks)} tracks planned")
    (work / "plan.json").write_text(json.dumps({"theme": a.theme, "seed": a.seed, "seconds": seconds, "music": music, "tracks": tracks if music else [],
                                                "events": theme.events}, indent=1))
    spec = {"theme": a.theme, "seed": a.seed, "options": theme.options, "tracks": tracks}
    t0 = time.time()

    if a.stage == "audio":
        audio_stage(theme, tracks, seconds, work, music, a.workers, bool(a.pomodoro))
        return
    if a.stage == "video":
        video_stage(theme, seconds, work, spec, a.workers, loop_s=a.video_loop * 60)
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
        video_stage(theme, seconds, work, spec, a.workers, loop_s=a.video_loop * 60)
    if child is not None and child.wait() != 0:
        sys.exit("the audio stage failed")
    mux_stage(work, seconds, out)
    if not a.keep_work:
        clean_work(work)
    log(f"finished {out.name} in {(time.time() - t0) / 60:.1f} min ({(time.time() - t0) / 3600 / (seconds / 3600):.2f} h of work per hour of video)")


if __name__ == "__main__":
    main()
