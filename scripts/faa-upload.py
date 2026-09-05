#!/usr/bin/env python3
"""Batch-upload photos to Fine Art America by driving an already-authenticated Chrome.

This never handles credentials. You log into FAA yourself in a Chrome started with
remote debugging; the script attaches to that session over the DevTools protocol.

SETUP (once per run)
  1. Quit Chrome completely (Cmd-Q).
  2. Start it with the debug port open:

     /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \\
       --remote-debugging-port=9222 --user-data-dir="$HOME/.faa-chrome"

     The first time, that fresh profile won't be logged in — sign into
     fineartamerica.com in it once. It persists for later runs.
  3. Run this script.

USAGE
  scripts/faa-upload.py --queue <queue.csv> --dir <image-dir> [--limit N] [--dry-run]
  scripts/faa-upload.py --status          # what's uploaded so far

Resumable: every success is journaled, so re-running skips finished images.
"""
import argparse, csv, json, os, sys, time, random
from pathlib import Path

STATE = Path(__file__).resolve().parent.parent / "photo-licensing-workspace" / "faa-upload-state.json"
CDP = "http://127.0.0.1:9222"
PROFILE = "https://fineartamerica.com/profiles/benjamin-ampel"


class SessionError(RuntimeError):
    """Raised when Chrome isn't signed in — abort the run rather than grind through
    every image failing identically."""


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"uploaded": {}, "failed": {}}


def save_state(s):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=2))


def upload_one(page, img_path, row, dry_run=False):
    """Upload a single image, verify metadata populated, save. Returns (ok, note)."""
    page.goto(PROFILE, wait_until="domcontentloaded")
    link = page.locator('a:has-text("Upload Image")').first
    # Fail fast and legibly when the session isn't authenticated: the upload
    # controls simply don't render for logged-out visitors.
    if link.count() == 0:
        raise SessionError(
            "not signed in to FAA in this Chrome profile — sign in, then re-run"
        )
    href = link.get_attribute("href", timeout=10_000)
    if not href:
        raise SessionError("Upload Image link has no href (page layout changed?)")
    # networkidle matters: the file input is injected after initial DOM load.
    page.goto(href, wait_until="networkidle")

    page.wait_for_selector('input[type="file"]', timeout=60_000)
    page.locator('input[type="file"]').first.set_input_files(str(img_path))
    page.locator('a:has-text("Upload Image")').last.click()

    # Field ids carry a per-upload hash, so always select by NAME.
    # Big panoramas can take minutes to process server-side.
    try:
        page.wait_for_selector('input[name="artworkname"]', timeout=300_000)
    except Exception:
        return False, "timed out waiting for the details form"
    page.wait_for_timeout(1500)

    title_el = page.locator('input[name="artworkname"]').first
    kw_el = page.locator('textarea[name="artworkkeywords"]').first
    desc_el = page.locator('textarea[name="artworkdescription"]').first

    got_title = (title_el.input_value() or "").strip()
    got_kw = (kw_el.input_value() or "").strip() if kw_el.count() else ""
    got_desc = (desc_el.input_value() or "").strip() if desc_el.count() else ""

    # FAA ingests embedded IPTC. Backfill anything that didn't come through.
    if not got_title:
        title_el.fill(row["title"])
    if kw_el.count():
        # FAA prepends a stray comma to ingested keywords; strip it either way.
        v = got_kw.lstrip(", ") if got_kw else row["keywords"].replace(";", ",")
        kw_el.fill(v)
    if desc_el.count() and not got_desc:
        desc_el.fill(row["description"])

    filled = f"title={'auto' if got_title else 'manual'} kw={len(got_kw)}ch desc={'auto' if got_desc else 'manual'}"
    if dry_run:
        return True, f"DRY RUN (not saved) — {filled}"

    submit = page.locator('.buttonSubmit').first
    if not submit.count():
        return False, "no SUBMIT control found"
    submit.click()
    page.wait_for_load_state("domcontentloaded")
    time.sleep(2)

    # Clicking SUBMIT is NOT proof the image landed. The original run recorded
    # 267 successes while only ~101 images actually reached the account: past
    # roughly the 100th upload FAA silently stopped accepting, and every later
    # click was journaled as "saved". Confirm against the account before
    # claiming success, so a silent failure stops the run instead of hiding.
    if page.locator('input[name="artworkname"]').count():
        return False, "SUBMIT did not advance — still on the details form"
    if not confirm_saved(page, row["title"]):
        return False, f"SUBMIT clicked but '{row['title'][:40]}' is not in the account"
    return True, f"saved+verified — {filled}"


def confirm_saved(page, title):
    """Look the title up in the account's own image list. Authoritative."""
    page.goto("https://fineartamerica.com/controlpanel/bulkeditprices.html",
              wait_until="domcontentloaded")
    box = page.locator('input[type="text"]').first
    if not box.count():
        return False
    # Search on a distinctive slice; FAA matches on substring.
    # Press Enter rather than clicking "SEARCH": a hidden mobile-nav span reads
    # "Search Type" and text=SEARCH resolves to that instead of the button,
    # which then never becomes visible and times out.
    box.fill(title[:40])
    box.press("Enter")
    page.wait_for_timeout(3000)
    return "No matches were found" not in page.inner_text("body")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", default="photo-licensing-workspace/faa-upload-queue.csv")
    ap.add_argument("--dir", default="photo-licensing-workspace/faa-upload/batch-01-first25")
    ap.add_argument("--limit", type=int, default=0, help="max images this run (0 = all)")
    ap.add_argument("--dry-run", action="store_true", help="fill the form but don't save")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--min-delay", type=float, default=6.0)
    ap.add_argument("--max-delay", type=float, default=14.0)
    args = ap.parse_args()

    state = load_state()
    if args.status:
        print(f"uploaded: {len(state['uploaded'])}")
        print(f"failed:   {len(state['failed'])}")
        for k, v in list(state["failed"].items())[:10]:
            print(f"  FAIL {k}: {v}")
        return

    rows = {r["filename"]: r for r in csv.DictReader(open(args.queue))}
    img_dir = Path(args.dir)
    todo = []
    for f in sorted(os.listdir(img_dir)):
        if not f.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        if f in state["uploaded"]:
            continue
        if f not in rows:
            print(f"  skip (no metadata row): {f}")
            continue
        todo.append((img_dir / f, rows[f]))
    todo.sort(key=lambda t: int(t[1]["priority"]))
    if args.limit:
        todo = todo[: args.limit]

    if not todo:
        print("nothing to do — everything in this directory is already uploaded")
        return
    print(f"{len(todo)} image(s) queued\n")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(CDP)
        except Exception as e:
            print(f"ERROR: could not attach to Chrome on {CDP}\n  {e}\n")
            print("Start Chrome with the debug port open first — see the header of this file.")
            sys.exit(1)

        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        ok = fail = 0
        streak = 0          # consecutive verification failures
        STREAK_LIMIT = 5
        for i, (img, row) in enumerate(todo, 1):
            # The first run pushed 167 images at a wall: uploads stopped landing
            # around the 100th and every later one silently failed. Now that each
            # save is verified, a run of failures means the wall is back -- stop
            # rather than grinding through the rest of the queue against it.
            if streak >= STREAK_LIMIT:
                print(f"\nSTOPPING: {streak} consecutive images failed verification.")
                print("FAA has stopped accepting (it did this at ~100/session before).")
                print("Re-run later; verified uploads are journaled and will be skipped.")
                break
            label = f"[{i}/{len(todo)}] {img.name}"
            try:
                good, note = upload_one(page, img, row, args.dry_run)
            except SessionError as e:
                print(f"\nABORTED: {e}")
                print("Nothing was uploaded in this run. Fix the session and re-run;")
                print("already-completed images are journaled and will be skipped.")
                save_state(state)
                sys.exit(2)
            except Exception as e:
                good, note = False, f"{type(e).__name__}: {e}"
            if good:
                ok += 1
                streak = 0
                if not args.dry_run:
                    state["uploaded"][img.name] = {"title": row["title"], "note": note}
                    state["failed"].pop(img.name, None)
                print(f"  OK   {label} — {note}")
            else:
                fail += 1
                streak += 1
                state["failed"][img.name] = note
                print(f"  FAIL {label} — {note}")
            save_state(state)
            if i < len(todo):
                # Ramp gently: FAA has a documented history of closing accounts that
                # look like bots. Randomized human-scale gaps.
                time.sleep(random.uniform(args.min_delay, args.max_delay))

        print(f"\ndone: {ok} ok, {fail} failed")
        print(f"state: {STATE}")


if __name__ == "__main__":
    main()
