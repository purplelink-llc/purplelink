"""Private config (~/.config/purplelink/social.json). No secrets in it; those live in the keychain."""
from __future__ import annotations

import json

from . import paths
from .spec import PLATFORMS

DEFAULT = {
    "timezone": "America/New_York",
    "windows": {"days": [0, 1, 2, 3, 4, 5, 6], "start": "07:00", "end": "21:00"},
    "link_hosts": ["purplelink.llc", "www.purplelink.llc", "www.youtube.com", "youtu.be"],  # YouTube: video picks
    "media": {"base_url": "https://purplelink.llc/social-media/", "store": "social-media",
              "netlify_cwd": "/Volumes/Extreme SSD/Purplelink LLC",
              # Reels: Instagram fetches the video from a public URL. Netlify functions cannot answer with a file
              # this large, so videos go to an S3-compatible public bucket for the minutes it takes Meta to fetch
              # them, and are deleted after the post. The env file holds MEDIA_BUCKET, MEDIA_S3_ENDPOINT,
              # MEDIA_PUBLIC_BASE, MEDIA_S3_KEY and MEDIA_S3_SECRET; it never enters the repo.
              "video": {"env_file": "", "prefix": "purplelink-social/"}},
    "retry": {"max_attempts": 3, "backoff_minutes": [10, 40, 120]},
    "stale_hours": 48,
    "platforms": {
        "linkedin": {"enabled": True, "expected": {"company_id": "120183926", "name": "Purplelink LLC"}},
        "bluesky": {"enabled": True, "expected": {"handle": "purplelink.llc"}},
        "threads": {"enabled": False, "expected": {"user_id": "", "username": ""}},
        "mastodon": {"enabled": False, "instance": "", "expected": {"acct": ""}},
        "x": {"enabled": False, "paid_posting_ok": False, "expected": {"user_id": "", "username": ""}},
        # api: "instagram" (Instagram Login token) or "facebook" (published through the Purplelink LLC Page's token,
        # used since 2026-10-28 because Instagram's web login loops for this account)
        "instagram": {"enabled": False, "api": "instagram", "expected": {"user_id": "", "username": ""}},
        "facebook": {"enabled": False, "expected": {"page_id": "", "name": ""}},
    },
}


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = _merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def load() -> dict:
    p = paths.config_file()
    if not p.exists():
        return json.loads(json.dumps(DEFAULT))
    return _merge(DEFAULT, json.loads(p.read_text(encoding="utf-8")))


def platform_cfg(cfg: dict, name: str) -> dict:
    return cfg["platforms"].get(name, {"enabled": False})


def enabled(cfg: dict) -> list[str]:
    return [p for p in PLATFORMS if platform_cfg(cfg, p).get("enabled")]


def write_default() -> bool:
    """Create the config file with defaults if it is missing. Returns True when it was created."""
    p = paths.config_file()
    if p.exists():
        return False
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(DEFAULT, indent=2) + "\n", encoding="utf-8")
    p.chmod(0o600)
    return True


def update_platform(name: str, **fields) -> None:
    """Merge fields into one platform's block of the private config file (creates it if needed)."""
    p = paths.config_file()
    raw = json.loads(p.read_text(encoding="utf-8")) if p.exists() else json.loads(json.dumps(DEFAULT))
    blk = raw.setdefault("platforms", {}).setdefault(name, {})
    for k, v in fields.items():
        if isinstance(v, dict) and isinstance(blk.get(k), dict):
            blk[k].update(v)
        else:
            blk[k] = v
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    p.chmod(0o600)
