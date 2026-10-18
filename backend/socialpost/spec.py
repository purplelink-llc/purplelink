"""Per-platform limits. Verified against primary docs on 2026-10-18; see docs/social-posting.md for sources."""
from __future__ import annotations

PLATFORMS = ("linkedin", "bluesky", "threads", "mastodon", "x")
IMAGE_EXT = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}
MB = 1024 * 1024
URL_WEIGHT = 23  # X and Mastodon count every link as 23 characters

SPEC = {
    # text: limit and how it is counted. images: max count, per-image size, allowed extensions, alt text limit.
    "linkedin": {"text": 3000, "count": "chars", "images": 0, "image_bytes": 0, "formats": (), "alt": 0,
                 "document": True},
    "bluesky":  {"text": 300, "count": "graphemes", "images": 4, "image_bytes": 50 * MB,
                 "formats": (".png", ".jpg", ".jpeg", ".gif", ".webp"), "alt": 2000, "document": False},
    "threads":  {"text": 500, "count": "chars", "images": 20, "image_bytes": 8 * MB,
                 "formats": (".png", ".jpg", ".jpeg"), "alt": 1000, "document": False},
    "mastodon": {"text": 500, "count": "mastodon", "images": 4, "image_bytes": 16 * MB,
                 "formats": (".png", ".jpg", ".jpeg", ".gif", ".webp"), "alt": 1500, "document": False},
    "x":        {"text": 280, "count": "x", "images": 4, "image_bytes": 5 * MB,
                 "formats": (".png", ".jpg", ".jpeg", ".gif", ".webp"), "alt": 1000, "document": False},
}
