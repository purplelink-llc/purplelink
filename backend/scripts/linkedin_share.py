#!/usr/bin/env python3
"""Generate a LinkedIn post for the latest digest and open the composer.

Usage:
  python3 backend/scripts/linkedin_share.py           # latest digest
  python3 backend/scripts/linkedin_share.py 2026-06-23  # specific date

Copies the post text to clipboard and opens linkedin.com/feed.
Just paste (Cmd+V) into the post box and click Post.
"""
from __future__ import annotations

import re
import subprocess
import sys
import webbrowser
from pathlib import Path

SITE_DIR = Path(__file__).resolve().parents[2] / "site"
DIGEST_DIR = SITE_DIR / "blog" / "digest"
BASE_URL = "https://purplelink.llc/blog/digest"


def find_digest_file(date_str: str | None) -> Path:
    files = sorted(DIGEST_DIR.glob("????-??-??.html"))
    if not files:
        raise FileNotFoundError(f"No digest HTML files found in {DIGEST_DIR}")
    if date_str:
        target = DIGEST_DIR / f"{date_str}.html"
        if not target.exists():
            raise FileNotFoundError(f"Digest not found: {target}")
        return target
    return files[-1]


def extract_meta(html: str) -> tuple[str, str, str]:
    """Return (date_str, title, intro) from a digest HTML file."""
    date_match = re.search(r'<time[^>]*datetime="(\d{4}-\d{2}-\d{2})"', html)
    date_str = date_match.group(1) if date_match else "unknown"

    title_match = re.search(r'<title>([^<]+)</title>', html)
    title = title_match.group(1).strip() if title_match else f"Purplelink Daily Digest — {date_str}"

    intro_match = re.search(r'class="digest-intro"[^>]*>([^<]+)<', html)
    intro = intro_match.group(1).strip() if intro_match else ""

    return date_str, title, intro


def build_post(date_str: str, title: str, intro: str) -> str:
    url = f"{BASE_URL}/{date_str}.html"
    lines = [
        title,
        "",
        intro,
        "",
        f"Read the full digest: {url}",
        "",
        "#cybersecurity #AI #research #infosec #digest",
    ]
    return "\n".join(lines)


def copy_to_clipboard(text: str) -> bool:
    try:
        subprocess.run(["pbcopy"], input=text.encode(), check=True)
        return True
    except Exception:
        return False


def main() -> None:
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None

    digest_file = find_digest_file(date_arg)
    html = digest_file.read_text(encoding="utf-8")
    date_str, title, intro = extract_meta(html)
    post = build_post(date_str, title, intro)

    print("=== LinkedIn post ===\n")
    print(post)
    print("\n====================\n")

    copied = copy_to_clipboard(post)
    if copied:
        print("Copied to clipboard.")
    else:
        print("(Could not copy automatically — copy the text above manually.)")

    print("Opening LinkedIn feed...")
    webbrowser.open("https://www.linkedin.com/feed/")
    print("\nPaste (Cmd+V) into the post box, then click Post.")


if __name__ == "__main__":
    main()
