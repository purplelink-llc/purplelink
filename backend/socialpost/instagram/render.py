"""Pictures and video for Instagram: the 1080x1350 feed image and the 9:16 Reel.

The feed image is scripts/ig-card.html (the site's social-card system: Fraunces title, hue-310 purple, the brand mark)
rendered by headless Chrome from a local server rooted at the repo, then saved as JPEG (Instagram takes JPEG only).
A Reel is re-encoded to 1080x1920 H.264/AAC at 30 fps with the moov atom first. A vertical source is scaled to fit;
a 16:9 source is laid into the window of the same card drawn as a 1080x1920 frame. Anything longer than the Reel
limit is cut with a short fade at the end.
"""
from __future__ import annotations

import http.server
import json
import socketserver
import subprocess
import tempfile
import threading
import urllib.parse
from pathlib import Path

from PIL import Image

from .. import paths
from ..errors import SocialError
from ..spec import REEL

CARD = (1080, 1350)
WINDOW_Y, WINDOW_H = 656, 608  # scripts/ig-card.html, .reel .window


def _serve(root: Path):
    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(root), **k)

        def log_message(self, *a):
            pass

    srv = socketserver.TCPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _chrome_png(params: dict, size: tuple[int, int], png: Path, run=subprocess.run) -> None:
    root = paths.repo_root()
    if not (root / "scripts" / "ig-card.html").is_file():
        raise SocialError(f"scripts/ig-card.html not found under {root}")
    srv = _serve(root)
    try:
        url = f"http://127.0.0.1:{srv.server_address[1]}/scripts/ig-card.html?{urllib.parse.urlencode(params)}"
        r = run([str(paths.chrome()), "--headless=new", "--disable-gpu", "--hide-scrollbars",
                 f"--window-size={size[0]},{size[1]}", "--force-device-scale-factor=1", "--virtual-time-budget=6000",
                 f"--user-data-dir={tempfile.mkdtemp(prefix='igcard-')}", f"--screenshot={png}", url],
                capture_output=True, timeout=120)
    finally:
        srv.shutdown()
        srv.server_close()
    if r.returncode != 0 or not png.is_file():
        raise SocialError("headless Chrome did not render the Instagram card")


def card(out: Path, title: str, kicker: str = "", sub: str = "", foot: str = "", bg: str = "general",
         run=subprocess.run) -> Path:
    """Render the 1080x1350 feed image to `out` (.jpg). Returns out."""
    out.parent.mkdir(parents=True, exist_ok=True)
    png = out.with_suffix(".png")
    _chrome_png({"t": title, "k": kicker, "s": sub, "f": foot, "bg": bg}, CARD, png, run)
    im = Image.open(png).convert("RGB")
    if im.size != CARD:
        im = im.resize(CARD)
    im.save(out, "JPEG", quality=88, optimize=True, progressive=True)
    png.unlink(missing_ok=True)
    return out


# ---------------------------------------------------------------- video
def probe(path: Path, run=subprocess.run) -> dict:
    """{"duration": s, "width": px, "height": px, "audio": bool} from ffprobe."""
    r = run([paths.ffprobe(), "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height",
             "-of", "json", str(path)], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise SocialError(f"ffprobe could not read {path.name}")
    j = json.loads(r.stdout or "{}")
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), None)
    if not v:
        raise SocialError(f"{path.name} has no video stream")
    return {"duration": round(float((j.get("format") or {}).get("duration") or 0), 2), "width": int(v["width"]),
            "height": int(v["height"]), "audio": any(s.get("codec_type") == "audio" for s in j.get("streams", []))}


def is_vertical(info: dict) -> bool:
    return info["height"] > info["width"] and 1.6 <= info["height"] / info["width"] <= 1.95


ENCODE = ["-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", "30", "-crf", "21",
          "-maxrate", "8M", "-bufsize", "16M", "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
          "-movflags", "+faststart"]


def reel(src: Path, out: Path, title: str = "", kicker: str = "Video", sub: str = "", bg: str = "general",
         run=subprocess.run) -> dict:
    """Make the Instagram Reel file. Returns {"duration", "width", "height", "trimmed", "framed"}."""
    info = probe(src, run)
    if info["duration"] < REEL["min_s"]:
        raise SocialError(f"{src.name} is {info['duration']} s; a Reel needs at least {REEL['min_s']:.0f} s")
    out.parent.mkdir(parents=True, exist_ok=True)
    w, h = REEL["width"], REEL["height"]
    keep = min(info["duration"], REEL["max_s"] - 0.5)
    trimmed = info["duration"] > keep
    fade = [f"fade=t=out:st={keep - 1.5:.2f}:d=1.5"] if trimmed else []
    afade = ["-af", f"afade=t=out:st={keep - 1.5:.2f}:d=1.5"] if trimmed and info["audio"] else []
    audio = [] if info["audio"] else ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
    amap = ["-map", "0:a:0"] if info["audio"] else ["-map", f"{2 if not is_vertical(info) else 1}:a:0", "-shortest"]
    framed = not is_vertical(info)
    if not framed:
        vf = ",".join([f"scale={w}:{h}:force_original_aspect_ratio=decrease:force_divisible_by=2",
                       f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=0x140a22", "setsar=1", *fade])
        cmd = [paths.ffmpeg(), "-y", "-v", "error", "-i", str(src), *audio, "-t", f"{keep:.2f}",
               "-map", "0:v:0", *amap, "-vf", vf, *afade, *ENCODE, str(out)]
    else:
        frame = out.with_name(out.stem + "-frame.png")
        _chrome_png({"t": title, "k": kicker, "s": sub, "f": "Full video on YouTube" if trimmed else "", "bg": bg,
                     "reel": "1"}, (w, h), frame, run)
        fc = (f"[0:v]scale={w}:{WINDOW_H}:force_original_aspect_ratio=decrease:force_divisible_by=2,"
              f"pad={w}:{WINDOW_H}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1[v];"
              f"[1:v]scale={w}:{h},format=rgba[f];[f][v]overlay=0:{WINDOW_Y}" + ("," + ",".join(fade) if fade else "")
              + "[o]")
        cmd = [paths.ffmpeg(), "-y", "-v", "error", "-i", str(src), "-loop", "1", "-i", str(frame), *audio,
               "-t", f"{keep:.2f}", "-filter_complex", fc, "-map", "[o]", *amap, *afade, *ENCODE, str(out)]
    r = run(cmd, capture_output=True, text=True, timeout=1800)
    if r.returncode != 0 or not out.is_file():
        raise SocialError(f"ffmpeg could not make the Reel: {(r.stderr or '')[-300:]}")
    got = probe(out, run)
    return {"duration": got["duration"], "width": got["width"], "height": got["height"], "trimmed": trimmed,
            "framed": framed}
