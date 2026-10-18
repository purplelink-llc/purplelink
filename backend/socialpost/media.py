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
