#!/usr/bin/env python3
"""Post the latest (or a specific) digest to LinkedIn using a saved browser session.

Usage:
  python3 backend/scripts/linkedin_post.py              # post today's digest
  python3 backend/scripts/linkedin_post.py 2026-06-23   # post a specific date
  python3 backend/scripts/linkedin_post.py --dry-run    # fill post box but don't click Post
  python3 backend/scripts/linkedin_post.py --text-file post.txt   # post arbitrary text (outreach.py uses this)
  python3 backend/scripts/linkedin_post.py --text-file post.txt --document deck.pdf \\
      --document-title "Title" [--headless] [--screenshot out.png] [--dry-run]
      # document (carousel) post: the PDF is uploaded through "Add a document"

One-time setup: python3 backend/scripts/linkedin_login.py

Exit codes: 0 posted  1 nothing to post  2 session expired  3 failed
            4 refused: not on the company admin page, or the composer was not posting as the company

Posts go ONLY to the Purplelink LLC company page, never to Ben's personal profile (Ben, 2026-10-14:
a post landed on his personal account and he had to delete it). Before clicking Post the script
checks the page URL and the composer's "post as" identity, and refuses on any mismatch.
"""
from __future__ import annotations

import argparse
import datetime
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
COMPANY_PATH = "/company/120183926/admin"
COMPANY_NAME = "Purplelink LLC"


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


def _composer_identity(page) -> str:
    """Return the name the open composer will post as (the first line of the dialog header)."""
    dlg = page.locator('[role="dialog"]').first
    lines = [l.strip() for l in dlg.inner_text(timeout=8_000).splitlines() if l.strip()]
    lines = [l for l in lines if l not in ("Dialog content start.", "Create post modal")]
    return lines[0] if lines else ""


def _refuse(page, why: str) -> int:
    """Stop before posting: screenshot, notify, exit code 4."""
    print(f"REFUSED: {why}. Nothing was posted.")
    try:
        shot_dir = Path.home() / ".purplelink" / "linkedin-failures"
        shot_dir.mkdir(parents=True, exist_ok=True)
        shot = shot_dir / f"{datetime.datetime.now():%Y%m%d-%H%M%S}-refused.png"
        page.screenshot(path=str(shot))
        print(f"Saved screenshot: {shot}")
    except Exception:
        pass
    _notify(f"LinkedIn post refused: {why}")
    return 4


def _attach_document(page, pdf: Path, title: str) -> None:
    """Composer: More -> Add a document -> upload the PDF -> set the required title -> Done.

    Waits for LinkedIn's "Your document has finished loading" before pressing Done.
    Raises PWTimeout if any step does not show up.
    """
    add = page.get_by_role("button", name="Add a document")
    if add.count() == 0:  # the document entry sits behind the composer's "More" (+) button
        page.get_by_role("button", name="More", exact=True).first.click(timeout=15_000)
        page.wait_for_timeout(1_000)
    add.first.click(timeout=15_000)
    dlg = page.locator('[role="dialog"]').last
    dlg.locator('input[type="file"]').first.set_input_files(str(pdf), timeout=30_000)
    title_box = dlg.get_by_placeholder(re.compile(r"title to your document", re.I)).first
    title_box.wait_for(state="visible", timeout=60_000)
    title_box.fill(title)
    dlg.get_by_text("finished loading").first.wait_for(state="visible", timeout=180_000)
    dlg.get_by_role("button", name="Done", exact=True).click(timeout=10_000)
    page.wait_for_timeout(2_000)


def post_to_linkedin(post_text: str, dry_run: bool, *, document: Path | None = None,
                     document_title: str = "", headless: bool = False,
                     screenshot: Path | None = None) -> int:
    if not PROFILE_DIR.exists():
        print("No saved session — run: python3 backend/scripts/linkedin_login.py")
        return 2

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=headless,
            viewport={"width": 1280, "height": 1800 if headless else 900},  # tall when headless so the screenshot shows the whole composer
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            print("Navigating to Purplelink LLC admin page...")
            # Transient page-load timeouts happen (network blips, slow LinkedIn
            # response) — retry the navigation itself before giving up, rather
            # than only relying on launchd's 30-min external retry (2026-07-18:
            # single Page.goto timeout burned the whole attempt with 5 launchd
            # retries left in the day).
            last_err: PWTimeout | None = None
            for attempt in range(3):
                try:
                    page.goto(COMPANY_URL, wait_until="domcontentloaded", timeout=30_000)
                    last_err = None
                    break
                except PWTimeout as e:
                    last_err = e
                    print(f"  navigation attempt {attempt + 1}/3 timed out, retrying...")
                    page.wait_for_timeout(2_000)
            if last_err is not None:
                raise last_err

            if "login" in page.url or "signup" in page.url:
                print("Session expired — re-run: python3 backend/scripts/linkedin_login.py")
                _notify("LinkedIn session expired — re-run linkedin_login.py")
                return 2

            # A redirect (to the member feed, a switcher, a checkpoint) would put
            # "Start a post" on Ben's own profile. Only continue on the admin page.
            if COMPANY_PATH not in page.url:
                return _refuse(page, f"landed on {page.url}, not the company admin page")

            # Click "Start a post" on the company admin page
            print("Opening post composer...")
            try:
                page.get_by_text("Start a post", exact=False).first.click(timeout=30_000)
            except PWTimeout:
                # Keep fallbacks narrow: a prior `button[aria-label*="post"]` substring
                # match grabbed an unrelated "switch identity...this post" button and
                # hung on the click (2026-07-13, 2026-07-15). Only match the real
                # share-box trigger, never a generic "*post*" substring.
                page.locator(
                    '.org-share-box__trigger, [data-test-id="share-box-trigger"], '
                    'button[aria-label="Start a post"]'
                ).first.click(timeout=10_000)
            page.locator('[role="dialog"] [role="textbox"]').first.wait_for(state="visible", timeout=30_000)
            page.wait_for_timeout(1_500)

            # The composer has a "post as" switcher. Refuse unless it is the company.
            identity = _composer_identity(page)
            print(f"Composer identity: {identity!r}")
            if identity != COMPANY_NAME:
                page.keyboard.press("Escape")
                return _refuse(page, f"composer would post as {identity!r}, not {COMPANY_NAME}")

            # Attach the document first: a URL typed before it becomes a link-preview card
            # that takes the composer's one media slot.
            if document is not None:
                print(f"Attaching document {document.name} titled {document_title!r}...")
                _attach_document(page, document, document_title)
                # Adding a document re-renders the composer: check the identity again.
                identity = _composer_identity(page)
                if identity != COMPANY_NAME:
                    page.keyboard.press("Escape")
                    return _refuse(page, f"composer would post as {identity!r} after attaching the document")

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
                if screenshot is not None:
                    screenshot.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(screenshot))
                    print(f"Saved screenshot: {screenshot}")
                print(f"Page URL: {page.url}")
                print(f"Composer identity: {_composer_identity(page)!r}")
                print("DRY RUN: post text entered, not clicking Post.")
                if not headless and sys.stdin.isatty():
                    print("Press Enter to close the browser: ", end="", flush=True)
                    input()
                return 0

            # Re-check right before posting, in case the identity changed while typing.
            identity = _composer_identity(page)
            if identity != COMPANY_NAME or COMPANY_PATH not in page.url:
                page.keyboard.press("Escape")
                return _refuse(page, f"identity {identity!r} or page {page.url} changed before Post")

            # Click the Post button
            print("Clicking Post...")
            try:
                page.get_by_role("button", name="Post", exact=True).click(timeout=10_000)
            except PWTimeout:
                page.locator('button.share-actions__primary-action').click(timeout=10_000)
            page.wait_for_timeout(3_000)

            if screenshot is not None:
                try:
                    page.screenshot(path=str(screenshot))
                except Exception:
                    pass
            print("Posted successfully.")
            _notify("Purplelink digest posted to LinkedIn.")
            return 0

        except (PWTimeout, PWError) as e:
            print(f"Browser error: {e}")
            try:
                shot_dir = Path.home() / ".purplelink" / "linkedin-failures"
                shot_dir.mkdir(parents=True, exist_ok=True)
                shot_path = shot_dir / f"{datetime.datetime.now():%Y%m%d-%H%M%S}.png"
                page.screenshot(path=str(shot_path))
                print(f"Saved failure screenshot: {shot_path}")
            except Exception:
                pass
            _notify("LinkedIn post failed — see terminal.")
            return 3
        finally:
            ctx.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("date", nargs="?", help="Digest date (YYYY-MM-DD). Defaults to latest.")
    ap.add_argument("--dry-run", action="store_true", help="Fill post but don't click Post.")
    ap.add_argument("--text-file", help="Post this file's contents instead of a digest.")
    ap.add_argument("--document", help="Attach this PDF as a LinkedIn document (carousel). Needs --text-file.")
    ap.add_argument("--document-title", help="Title LinkedIn requires for the document.")
    ap.add_argument("--headless", action="store_true", help="Run the browser without a window.")
    ap.add_argument("--screenshot", help="Save a screenshot of the composer (dry run) or the page after Post.")
    args = ap.parse_args()

    document = None
    if args.document or args.document_title:
        if not (args.document and args.document_title and args.text_file):
            ap.error("--document needs --document-title and --text-file")
        document = Path(args.document).expanduser().resolve()
        if document.suffix.lower() != ".pdf" or not document.is_file():
            ap.error(f"--document must be an existing .pdf file: {document}")
    shot = Path(args.screenshot).expanduser() if args.screenshot else None

    if args.text_file:
        post = Path(args.text_file).read_text(encoding="utf-8").strip()
        if not post:
            print("ERROR: --text-file is empty")
            sys.exit(1)
        print(f"Text:   {args.text_file} ({len(post)} chars)")
        print()
        sys.exit(post_to_linkedin(post, dry_run=args.dry_run, document=document,
                                  document_title=args.document_title or "",
                                  headless=args.headless, screenshot=shot))

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

    sys.exit(post_to_linkedin(post, dry_run=args.dry_run, headless=args.headless, screenshot=shot))


if __name__ == "__main__":
    main()
