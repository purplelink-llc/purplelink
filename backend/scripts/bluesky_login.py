#!/usr/bin/env python3
"""One-time Bluesky session capture for the unified social poster (same pattern as linkedin_login.py).

  python3 backend/scripts/bluesky_login.py          # open a window, log in as the company account, save the session
  python3 backend/scripts/bluesky_login.py --check  # headless: is the saved session still signed in, and as whom

Run this yourself, in your own terminal. Log in as @purplelink.llc (the company account), then press Enter.
The session is kept in ~/.purplelink/bluesky-profile and reused headless by social.py. No API credential is
used or stored. Re-run when social.py reports "not signed in".
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import sync_playwright  # noqa: E402

from socialpost import paths  # noqa: E402
from socialpost.adapters.bluesky import STORAGE_JS, parse_storage  # noqa: E402

EXPECTED = "purplelink.llc"


def signed_in_as(page) -> dict | None:
    page.goto("https://bsky.app/", wait_until="domcontentloaded", timeout=45_000)
    page.wait_for_timeout(3_000)
    return parse_storage(page.evaluate(STORAGE_JS))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    prof = paths.bluesky_profile()
    if args.check and not prof.exists():
        print("No saved session. Run without --check to log in.")
        return 2
    prof.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            str(prof), headless=args.check, viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            if not args.check:
                page.goto("https://bsky.app/", wait_until="domcontentloaded")
                print(f"A window opened. Log in to Bluesky as @{EXPECTED}, then press Enter here: ", end="", flush=True)
                input()
            acct = signed_in_as(page)
        finally:
            ctx.close()
    if not acct:
        print("Not signed in." + ("" if args.check else " Run this again and finish logging in."))
        return 2
    print(f"Signed in as @{acct['handle']}.")
    if acct["handle"].lower() != EXPECTED:
        print(f"WARNING: that is not @{EXPECTED}. social.py will refuse to post until the session is the company account.")
        return 4
    print("Session saved. Check: python3 backend/scripts/social.py whoami bluesky")
    return 0


if __name__ == "__main__":
    sys.exit(main())
