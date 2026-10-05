#!/usr/bin/env python3.12
"""A 24/7 study-music stream: endless generated chiptune plus the pixel study room, encoded by ffmpeg.

    # a 60-second test file, no network:
    python3.12 stream.py --out test.mp4 --seconds 60

    # live (the full RTMP URL including the stream key comes from STREAM_URL or --url-file, and is never printed):
    STREAM_URL=rtmp://a.rtmp.youtube.com/live2/<key> python3.12 stream.py --live

The audio thread renders the next track while the current one plays, crossfades between them and keeps a timeline of what is
playing; the video thread draws the scene from that timeline and the wall clock. ffmpeg paces both (-re), so the stream runs in
real time. In live mode the whole pipeline restarts with a growing delay if anything fails.
"""
from __future__ import annotations

import argparse
import os
import queue
import random
import signal
import subprocess
import sys
import threading
import time
import multiprocessing
from concurrent.futures import ProcessPoolExecutor

import numpy as np

import chiptune as c
import scene as sc

AUDIO_CHUNK = int(0.5 * c.SR)
XFADE = 3.0
TARGET_RMS = 0.13                          # about -16 LUFS once encoded, the usual level for background music streams
VIDEO_FPS = 15
LOG_EVERY = 300


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, file=sys.stderr, flush=True)


def next_tracks(start_seed: int):
    """An endless run of seeds, skipping any whose key or tempo is too close to the previous track's."""
    seed, prev = start_seed, None
    while True:
        t = c.plan(seed)
        seed += 1
        if prev is None or (t.key != prev.key and abs(t.bpm - prev.bpm) >= 4):
            prev = t
            yield t


def leveled(audio: np.ndarray) -> np.ndarray:
    rms = float(np.sqrt(np.mean(audio ** 2)))
    peak = float(np.max(np.abs(audio)))
    gain = min(1.25, max(0.5, TARGET_RMS / rms if rms else 1.0))
    if peak * gain > 0.9:
        gain = 0.9 / peak
    return audio * gain


def render_seed(seed: int):
    """Runs in a short-lived worker process: a track needs several hundred MB while it renders, and a fresh process hands all of it back."""
    t = c.plan(seed)
    return seed, f"{t.key} {t.mode}, {t.bpm} BPM", t.bpm, leveled(c.render(t))


class Audio:
    """Endless crossfaded PCM, with a timeline of (stream_seconds, title, bpm) for the overlay."""

    def __init__(self, start_seed: int):
        self.tracks = next_tracks(start_seed)
        self.pool = ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context("spawn"), max_tasks_per_child=1)
        self.timeline: list[tuple[float, str, int]] = []
        self.lock = threading.Lock()
        self.written = 0                      # samples handed to the encoder

    def _submit(self):
        return self.pool.submit(render_seed, next(self.tracks).seed)

    def now(self, ts: float):
        with self.lock:
            cur = self.timeline[0] if self.timeline else (0.0, "tuning in", 84)
            for e in self.timeline:
                if e[0] <= ts:
                    cur = e
            return cur

    def chunks(self):
        xf = int(XFADE * c.SR)
        fade_in = np.sin(np.linspace(0, np.pi / 2, xf))
        fade_out = np.cos(np.linspace(0, np.pi / 2, xf))
        fut = self._submit()
        tail = None
        while True:
            _, title, bpm, a = fut.result()
            fut = self._submit()                                 # the next track renders while this one plays
            if tail is not None:
                a = a.copy()
                a[:, :xf] = a[:, :xf] * fade_in + tail * fade_out
            with self.lock:
                self.timeline.append((self.written / c.SR, title, bpm))
                del self.timeline[:-6]
            body, tail = a[:, :-xf], a[:, -xf:]
            for i in range(0, body.shape[1], AUDIO_CHUNK):
                yield body[:, i:i + AUDIO_CHUNK]


def ffmpeg_cmd(out: str, live: bool, audio_fd: int) -> list[str]:
    pace = ["-re"] if live or out.startswith("hls:") else []
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "warning", "-y",
           *pace, "-f", "rawvideo", "-pix_fmt", "rgb24", "-video_size", f"{sc.W}x{sc.H}", "-framerate", str(VIDEO_FPS), "-i", "pipe:0",
           *pace, "-f", "s16le", "-ar", str(c.SR), "-ac", "2", "-i", f"pipe:{audio_fd}",
           "-filter_complex", "[0:v]fps=30,scale=1280:720:flags=neighbor,format=yuv420p[v]", "-map", "[v]", "-map", "1:a",
           "-c:v", "libx264", "-preset", "veryfast", "-tune", "animation", "-profile:v", "high", "-b:v", "2500k", "-maxrate", "2500k",
           "-bufsize", "5000k", "-g", "60", "-keyint_min", "60", "-sc_threshold", "0",
           "-c:a", "aac", "-b:a", "128k", "-ar", str(c.SR)]
    if live:
        return cmd + ["-f", "flv", out]
    if out.startswith("hls:"):
        d = out[4:]
        os.makedirs(d, exist_ok=True)
        return cmd + ["-f", "hls", "-hls_time", "4", "-hls_list_size", "6", "-hls_flags", "delete_segments", os.path.join(d, "live.m3u8")]
    return cmd + ["-movflags", "+faststart", out]


def run_once(out: str, live: bool, start_seed: int, seconds: float | None, stop: threading.Event) -> int:
    r_fd, w_fd = os.pipe()
    proc = subprocess.Popen(ffmpeg_cmd(out, live, r_fd), stdin=subprocess.PIPE, pass_fds=(r_fd,))
    os.close(r_fd)
    audio = Audio(start_seed)
    scene = sc.Scene(seed=start_seed)
    t0_wall = time.time()
    sim0 = (t0_wall % (2 * 3600.0))              # the scene's day cycle follows the real clock, so a restart does not jump
    failed = threading.Event()

    def audio_loop():
        try:
            limit = None if seconds is None else int(seconds * c.SR)
            with os.fdopen(w_fd, "wb") as w:
                for chunk in audio.chunks():
                    if stop.is_set() or failed.is_set():
                        break
                    pcm = (np.clip(chunk.T, -1, 1) * 32767).astype("<i2")
                    if limit is not None and audio.written + len(pcm) > limit:
                        pcm = pcm[: max(0, limit - audio.written)]
                    w.write(pcm.tobytes())
                    audio.written += len(pcm)
                    if limit is not None and audio.written >= limit:
                        break
        except (BrokenPipeError, OSError, ValueError):
            failed.set()
        except Exception as exc:  # noqa: BLE001
            log(f"audio thread: {exc!r}")
            failed.set()

    def video_loop():
        try:
            n, limit = 0, None if seconds is None else int(seconds * VIDEO_FPS)
            while not (stop.is_set() or failed.is_set()):
                ts = n / VIDEO_FPS
                _, title, bpm = audio.now(ts)
                sim = sim0 + ts
                im = scene.frame(ts, sc.hour_at(sim), sc.rain_at(sim), bpm, title, wall=t0_wall + ts)
                proc.stdin.write(im.tobytes())
                n += 1
                if n % (VIDEO_FPS * LOG_EVERY) == 0:
                    log(f"streaming: {n / VIDEO_FPS / 3600:.2f} h, now playing {title}")
                if limit is not None and n >= limit:
                    break
        except (BrokenPipeError, OSError, ValueError):
            failed.set()
        except Exception as exc:  # noqa: BLE001
            log(f"video thread: {exc!r}")
            failed.set()
        finally:
            try:
                proc.stdin.close()
            except OSError:
                pass

    ta, tv = threading.Thread(target=audio_loop, daemon=True), threading.Thread(target=video_loop, daemon=True)
    ta.start()
    tv.start()
    try:
        while proc.poll() is None and not stop.is_set():
            if seconds is not None and not (ta.is_alive() or tv.is_alive()):
                break
            time.sleep(0.5)
    finally:
        failed.set() if stop.is_set() else None
        try:
            proc.wait(timeout=60 if seconds is not None else 5)
        except subprocess.TimeoutExpired:
            proc.kill()
    ta.join(timeout=5)
    tv.join(timeout=5)
    return proc.returncode or 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="stream-test.mp4", help="file to write, hls:DIR for local HLS, ignored with --live")
    ap.add_argument("--live", action="store_true", help="stream to the RTMP URL in STREAM_URL (or --url-file) and keep running")
    ap.add_argument("--url-file", help="a file whose first line is the full RTMP URL including the key")
    ap.add_argument("--seconds", type=float, help="stop after this many seconds of stream time (tests)")
    ap.add_argument("--start-seed", type=int, default=int(time.time() // 3600) % 100000)
    a = ap.parse_args()

    out = a.out
    if a.live:
        out = os.environ.get("STREAM_URL", "")
        if a.url_file:
            out = open(os.path.expanduser(a.url_file)).readline().strip()
        if not out.startswith(("rtmp://", "rtmps://")):
            sys.exit("--live needs STREAM_URL (or --url-file) set to an rtmp:// or rtmps:// URL")

    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())

    delay, seed = 5, a.start_seed
    while not stop.is_set():
        started = time.time()
        log("starting the pipeline" + (" (live)" if a.live else f" -> {out}"))
        code = run_once(out, a.live, seed, a.seconds, stop)
        if not a.live or stop.is_set():
            sys.exit(code)
        ran = time.time() - started
        delay = 5 if ran > 600 else min(120, delay * 2)          # a long healthy run resets the back-off
        seed += 1000
        log(f"the pipeline ended (exit {code}) after {ran:.0f}s; restarting in {delay}s")
        stop.wait(delay)


if __name__ == "__main__":
    main()
