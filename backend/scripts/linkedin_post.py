#!/usr/bin/env python3
"""Post the latest (or a specific) digest to LinkedIn using a saved browser session.

Usage:
  python3 backend/scripts/linkedin_post.py              # post today's digest
  python3 backend/scripts/linkedin_post.py 2026-06-23   # post a specific date
  python3 backend/scripts/linkedin_post.py --dry-run    # fill post box but don't click Post

One-time setup: python3 backend/scripts/linkedin_login.py

Exit codes: 0 posted  1 nothing to post  2 session expired  3 failed
"""
from __future__ import annotations

import argparse
import html as html_module
import re
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout, Error as PWError

PROFILE_DIR  = Path.home() / ".purplelink" / "linkedin-profile"
SITE_DIR     = Path(__file__).resolve().parents[2] / "site"
DIGEST_DIR   = SITE_DIR / "blog" / "digest"
BASE_URL     = "https://purplelink.llc/blog/digest"
COMPANY_URL  = "https://www.linkedin.com/company/120183926/admin/page-posts/published/"


# ── digest content ────────────────────────────────────────────────────────────

def find_digest(date_str: str | None) -> Path:
    files = sorted(DIGEST_DIR.glob("????-??-??.html"))
    if not files:
        raise FileNotFoundError(f"No digest HTML files in {DIGEST_DIR}")
    if date_str:
        target = DIGEST_DIR / f"{date_str}.html"
        if not target.exists():
            raise FileNotFoundError(f"Digest not found: {target}")
        return target
    return files[-1]


def extract_meta(html: str) -> tuple[str, str, str]:
    date_match = re.search(r'<time[^>]*datetime="(\d{4}-\d{2}-\d{2})"', html)
    date_str   = date_match.group(1) if date_match else "unknown"

    title_match = re.search(r'<title>([^<]+)</title>', html)
    title = html_module.unescape(title_match.group(1).strip()) if title_match else f"Purplelink Daily Digest - {date_str}"

    intro_match = re.search(r'class="digest-intro"[^>]*>([^<]+)<', html)
    intro = html_module.unescape(intro_match.group(1).strip()) if intro_match else ""

    # Strip any remaining em-dashes or non-ASCII that LinkedIn renders as garbage
    title = title.replace("—", "-").replace("–", "-")
    intro = intro.replace("—", "-").replace("–", "-")

    return date_str, title, intro


def build_post(date_str: str, title: str, intro: str) -> str:
    url = f"{BASE_URL}/{date_str}.html"
    return "\n".join([
        title,
        "",
        intro,
        "",
        f"Read the full digest: {url}",
        "",
        "#cybersecurity #AI #research #infosec #digest",
    ])


# ── browser ───────────────────────────────────────────────────────────────────

def _logged_in(page) -> bool:
    return "/feed" in page.url and "login" not in page.url


def _notify(msg: str) -> None:
    try:
        subprocess.run(
            ["/usr/bin/osascript", "-e",
             f'display notification "{msg}" with title "Purplelink"'],
            check=False, capture_output=True,
        )
    except Exception:
        pass


def _paste_text(page, text: str) -> None:
    """Insert text as a single operation — avoids garbled characters from keyboard.type()."""
    page.keyboard.insert_text(text)


def post_to_linkedin(post_text: str, dry_run: bool) -> int:
    if not PROFILE_DIR.exists():
        print("No saved session — run: python3 backend/scripts/linkedin_login.py")
        return 2

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            print("Navigating to Purplelink LLC admin page...")
            page.goto(COMPANY_URL, wait_until="domcontentloaded", timeout=30_000)

            if "login" in page.url or "signup" in page.url:
                print("Session expired — re-run: python3 backend/scripts/linkedin_login.py")
                _notify("LinkedIn session expired — re-run linkedin_login.py")
                return 2

            # Click "Start a post" on the company admin page
            print("Opening post composer...")
            try:
                page.get_by_text("Start a post", exact=False).first.click(timeout=10_000)
            except PWTimeout:
                page.locator('[data-test-id*="create"], button[aria-label*="post"], .org-share-box__trigger').first.click(timeout=10_000)
            page.wait_for_timeout(1_500)

            # Type post text via clipboard paste (avoids garbled characters)
            print("Entering post text...")
            editor = page.locator('div[role="textbox"], div[contenteditable="true"]').first
            editor.wait_for(state="visible", timeout=15_000)
            editor.click()
            page.wait_for_timeout(300)
            page.keyboard.press("Meta+A")
            page.keyboard.press("Backspace")
            page.wait_for_timeout(200)
            _paste_text(page, post_text)
            page.wait_for_timeout(500)

            if dry_run:
                print("DRY RUN — post text entered, not clicking Post.")
                print("Press Enter to close the browser: ", end="", flush=True)
                input()
                return 0

            # Click the Post button
            print("Clicking Post...")
            try:
                page.get_by_role("button", name="Post", exact=True).click(timeout=10_000)
            except PWTimeout:
                page.locator('button.share-actions__primary-action').click(timeout=10_000)
            page.wait_for_timeout(3_000)

            print("Posted successfully.")
            _notify("Purplelink digest posted to LinkedIn.")
            return 0

        except (PWTimeout, PWError) as e:
            print(f"Browser error: {e}")
            _notify("LinkedIn post failed — see terminal.")
            return 3
        finally:
            ctx.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("date", nargs="?", help="Digest date (YYYY-MM-DD). Defaults to latest.")
    ap.add_argument("--dry-run", action="store_true", help="Fill post but don't click Post.")
    args = ap.parse_args()

    try:
        digest_file = find_digest(args.date)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    html = digest_file.read_text(encoding="utf-8")
    date_str, title, intro = extract_meta(html)
    post = build_post(date_str, title, intro)

    print(f"Digest: {digest_file.name}")
    print(f"Title:  {title}")
    print()

    sys.exit(post_to_linkedin(post, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
