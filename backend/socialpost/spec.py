"""Per-platform limits. Verified against primary docs on 2026-10-18; see docs/social-posting.md for sources."""
from __future__ import annotations

PLATFORMS = ("linkedin", "bluesky", "threads", "mastodon", "x", "instagram")
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
    # Instagram (read 2026-10-23, developers.facebook.com/docs/instagram-platform/content-publishing): JPEG only,
    # caption 2,200 characters, at most 5 hashtags, alt_text on image posts only (not Reels). One image or one Reel
    # per post here (carousels are not used). Links in a caption are not clickable, so the caption says "link in bio".
    "instagram": {"text": 2200, "count": "chars", "images": 1, "image_bytes": 8 * MB,
                  "formats": (".jpg", ".jpeg"), "alt": 1000, "document": False, "hashtags": 5},
}

# Reels through the API: MP4 (H.264, AAC), 3 seconds to 15 minutes, 9:16 recommended. This pipeline keeps a Reel to
# 3 minutes (Instagram's in-app Reel length) and re-encodes every file to 1080x1920 so the container never fails on
# codec or frame rate.
REEL = {"min_s": 3.0, "max_s": 180.0, "max_bytes": 300 * MB, "width": 1080, "height": 1920}
