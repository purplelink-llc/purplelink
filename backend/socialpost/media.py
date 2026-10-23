"""Public image hosting for Threads (it fetches images from a public URL).

Images are uploaded to the `social-media` Netlify Blobs store under a content-addressed key
(<first 40 hex of sha256>.<ext>) with the Netlify CLI, and served read-only by netlify/functions/social-media.mjs
at https://purplelink.llc/social-media/<key>. Content addressing means a key can never be overwritten with
different bytes, and the URL carries no private path.
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from .errors import SocialError

CONTENT_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


def key_for(path: Path) -> str:
    ext = path.suffix.lower()
    if ext not in CONTENT_TYPES:
        raise SocialError(f"cannot host {ext} images (Threads takes JPEG and PNG)")
    return f"{hashlib.sha256(path.read_bytes()).hexdigest()[:40]}{ext}"


def public_url(cfg: dict, key: str) -> str:
    return cfg["media"]["base_url"].rstrip("/") + "/" + key


def ensure_hosted(cfg: dict, path: Path, http, run=subprocess.run) -> str:
    """Make sure the image is served publicly and return its URL. Raises SocialError if it never goes live."""
    key = key_for(path)
    url = public_url(cfg, key)
    size = path.stat().st_size

    def live() -> bool:
        r = http.request("HEAD", url)
        return r.status == 200 and r.header("Content-Type").lower().startswith("image/") and \
            r.header("Content-Length", str(size)) == str(size)

    if live():
        return url
    cwd = cfg["media"].get("netlify_cwd") or None
    p = run(["netlify", "blobs:set", cfg["media"].get("store", "social-media"), key, "--input", str(path), "--force"],
            capture_output=True, text=True, timeout=180, cwd=cwd)
    if p.returncode != 0:
        raise SocialError("could not upload the image to the social-media Blobs store (is `netlify login` current?)")
    if not live():
        raise SocialError(f"uploaded {key} but {url} does not serve it yet (is the social-media function deployed?)")
    return url


# ---------------------------------------------------------------- videos (Instagram Reels)
VIDEO_ENV_KEYS = ("MEDIA_BUCKET", "MEDIA_S3_ENDPOINT", "MEDIA_PUBLIC_BASE", "MEDIA_S3_KEY", "MEDIA_S3_SECRET")


def read_env_file(path: str) -> dict:
    """`export NAME="value"` lines of a private env file. Values are returned, never printed."""
    out: dict[str, str] = {}
    if not path:
        return out
    try:
        text = Path(path).expanduser().read_text(encoding="utf-8")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[7:]
        name, sep, value = line.partition("=")
        if sep and name.strip() in VIDEO_ENV_KEYS:
            out[name.strip()] = value.strip().strip('"').strip("'")
    return out


def video_key(cfg: dict, path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return f"{cfg['media'].get('video', {}).get('prefix', 'purplelink-social/')}{h.hexdigest()[:40]}.mp4"


def _s3(env: dict, client_factory=None):
    if client_factory:
        return client_factory(env)
    import boto3  # only needed on the posting Mac
    return boto3.client("s3", endpoint_url=env["MEDIA_S3_ENDPOINT"], aws_access_key_id=env["MEDIA_S3_KEY"],
                        aws_secret_access_key=env["MEDIA_S3_SECRET"], region_name="auto")


def host_video(cfg: dict, path: Path, http, client_factory=None) -> tuple[str, str]:
    """Upload the Reel to the public bucket and return (url, key). Raises SocialError unless an anonymous HEAD sees
    the same size. The caller deletes it with delete_video once Instagram has fetched it."""
    env = read_env_file(cfg["media"].get("video", {}).get("env_file", ""))
    missing = [k for k in VIDEO_ENV_KEYS if not env.get(k)]
    if missing:
        raise SocialError("no public video host configured (media.video.env_file in social.json); Reels cannot post")
    key = video_key(cfg, path)
    url = env["MEDIA_PUBLIC_BASE"].rstrip("/") + "/" + key
    try:
        _s3(env, client_factory).upload_file(str(path), env["MEDIA_BUCKET"], key,
                                             ExtraArgs={"ContentType": "video/mp4"})
    except Exception as e:
        raise SocialError(f"could not upload the Reel to the video host ({type(e).__name__})")
    r = http.request("HEAD", url)
    if r.status != 200 or r.header("Content-Length", "") not in ("", str(path.stat().st_size)):
        raise SocialError(f"uploaded the Reel but {url} answers {r.status}; Instagram could not fetch it")
    return url, key


def delete_video(cfg: dict, key: str, client_factory=None) -> bool:
    env = read_env_file(cfg["media"].get("video", {}).get("env_file", ""))
    if not env.get("MEDIA_BUCKET") or not key.startswith(cfg["media"].get("video", {}).get("prefix", "purplelink-social/")):
        return False
    try:
        _s3(env, client_factory).delete_object(Bucket=env["MEDIA_BUCKET"], Key=key)
        return True
    except Exception:
        return False
