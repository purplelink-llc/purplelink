#!/usr/bin/env python3
"""One-time LinkedIn session capture for the automated poster.

Usage:
  python3 backend/scripts/linkedin_login.py          # open browser, log in, save session
  python3 backend/scripts/linkedin_login.py --check  # verify saved session is still live

Run this once. The session is saved to ~/.purplelink/linkedin-profile and
reused by linkedin_post.py every day without re-authenticating.
Re-run when linkedin_post.py reports "session expired".
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILE_DIR = Path.home() / ".purplelink" / "linkedin-profile"


def check_session() -> bool:
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30_000)
        logged_in = "/feed" in page.url and "login" not in page.url
        ctx.close()
        return logged_in


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="Verify saved session without opening browser")
    args = ap.parse_args()

    if args.check:
        if not PROFILE_DIR.exists():
            print("No saved session — run without --check to log in.")
            sys.exit(1)
        print("Checking saved session...", end=" ", flush=True)
        if check_session():
            print("OK — session is live.")
        else:
            print("EXPIRED — re-run without --check to log in again.")
            sys.exit(2)
        return

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    print("Opening browser — log in to LinkedIn, then come back here and press Enter.")
    print(f"Session will be saved to: {PROFILE_DIR}\n")

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
        print("Log in to LinkedIn in the browser window, then press Enter here: ", end="", flush=True)
        input()
        if "/feed" in page.url or "linkedin.com/in/" in page.url:
            print("Session saved. You can now run linkedin_post.py.")
        else:
            print(f"Warning: browser is at {page.url!r} — make sure you're logged in.")
        ctx.close()


if __name__ == "__main__":
    main()
