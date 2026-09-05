#!/usr/bin/env python3
"""Batch-upload photos to Adobe Stock by driving an already-authenticated Chrome.

Adobe's flow is fundamentally different from FAA's — and much better:
  phase 1  push files in chunks through the uploader
  phase 2  import ONE CSV that sets title/keywords/category for every file
  phase 3  select all and submit for moderation

SFTP is not enabled on this account (Adobe restricts it to qualified accounts and
is phasing it out), so the web uploader is the only automated route.

Credentials are never handled here. You sign in yourself in a Chrome started with
remote debugging; this attaches to that session.

SETUP
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \\
    --remote-debugging-port=9223 --user-data-dir="$HOME/.adobe-chrome"
  ...then sign in to contributor.stock.adobe.com in that window.

USAGE
  scripts/adobe-upload.py --phase upload [--chunk 20] [--limit N]
  scripts/adobe-upload.py --phase csv
  scripts/adobe-upload.py --phase submit
  scripts/adobe-upload.py --status
"""
import argparse, json, os, sys, time, random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "photo-licensing-workspace" / "adobe-upload-state.json"
IMG_DIR = ROOT / "photo-licensing-workspace" / "adobe-upload"

# Playwright refuses to transfer more than 50MB per set_input_files call when
# it talks to the browser over CDP (same limit getty-upload.py hit first). A
# flat --chunk file-COUNT ignores this: 20 files at 2-15MB each routinely
# exceeds 50MB, and every over-limit batch fails outright. Bound chunks by
# bytes, not count, same fix as Getty's chunk_by_size. Caught 2026-09-03 when
# 19 of 20 batches failed this way and only the small remainder chunk landed.
CHUNK_BYTES = 35 * 1024 * 1024


def chunk_by_size(names, max_count):
    out, cur, tot = [], [], 0
    for n in names:
        sz = (IMG_DIR / n).stat().st_size
        if cur and (tot + sz > CHUNK_BYTES or len(cur) >= max_count):
            out.append(cur); cur, tot = [], 0
        cur.append(n); tot += sz
    if cur:
        out.append(cur)
    return out


CSV_PATH = ROOT / "photo-licensing-workspace" / "adobe-stock-metadata.csv"
CDP = "http://127.0.0.1:9223"
UPLOADS_URL = "https://contributor.stock.adobe.com/en/uploads"


class SessionError(RuntimeError):
    pass


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"uploaded": [], "csv_imported": False, "submitted": False, "failed": {}}


def save_state(s):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=2))


def get_page(p):
    try:
        browser = p.chromium.connect_over_cdp(CDP)
    except Exception as e:
        print(f"ERROR: could not attach to Chrome on {CDP}\n  {e}")
        print("Start Chrome with --remote-debugging-port=9223 first (see file header).")
        sys.exit(1)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    return ctx.pages[0] if ctx.pages else ctx.new_page()


def ensure_signed_in(page):
    page.goto(UPLOADS_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(6000)
    if "auth" in page.url or "signin" in page.url.lower():
        raise SessionError("not signed in to Adobe Stock in this Chrome profile")
    if page.locator('button:has-text("Upload")').count() == 0:
        raise SessionError(
            "contributor portal not reachable — check sign-in and that onboarding "
            "(phone, address, tax form) is complete"
        )


def send_files(page, paths):
    """Push files through Adobe's uploader. Raises if the drop zone never opens.

    Three separate things were wrong here, and all three had to be right before
    a single file would land (verified 2026-08-19):

    1. `button:has-text("Upload")` also matches "Uploaded Files" and
       "Upload CSV". Taking .first clicked the wrong control, so the drop zone
       never opened. The button must be matched on EXACT text.
    2. The "Drag & Drop files or Browse" zone — and its Browse button — stay
       hidden until that exact button is clicked.
    3. set_input_files() on the page's hidden input[name=file] does NOTHING:
       no upload request, no error, no change in count. Adobe binds its handler
       to the native picker, so the file chooser has to be intercepted instead.

    Together those meant every "successful" batch uploaded nothing at all, which
    is how the journal reached 273 uploads for roughly 50 real files.
    """
    # RETRY opening the panel. Adobe tears the drop zone down after each use and
    # its render is intermittent -- a single click-and-hope failed every batch
    # with "'Browse' never became visible" on a page that was otherwise fine.
    # Getty's uploader needed exactly the same loop for "Upload from device".
    for _ in range(4):
        if page.evaluate("""()=>[...document.querySelectorAll('button')]
                .some(x=>/^Browse$/i.test((x.textContent||'').trim()) && x.offsetParent)"""):
            break
        page.evaluate("""()=>{const b=[...document.querySelectorAll('button')]
            .find(x=>(x.textContent||'').trim()==='Upload' && x.offsetParent);
            if(b) b.click();}""")
        page.wait_for_timeout(4000)
    else:
        raise RuntimeError("'Browse' never became visible after 4 attempts to open the uploader")
    with page.expect_file_chooser(timeout=30_000) as fc:
        page.evaluate("""()=>{const b=[...document.querySelectorAll('button')]
            .find(x=>/^Browse$/i.test((x.textContent||'').trim()) && x.offsetParent);
            if(b) b.click();}""")
    fc.value.set_files(paths)


def new_tab_count(page):
    """How many files the 'New' tab actually holds. -1 if it cannot be read."""
    import re as _re
    try:
        page.goto(UPLOADS_URL, wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_timeout(8000)
        m = _re.search(r"File types:\s*All\s*\((\d+)\)", page.inner_text("body"))
        return int(m.group(1)) if m else -1
    except Exception:
        return -1


def phase_upload(page, state, chunk, limit):
    files = sorted(
        f for f in os.listdir(IMG_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png"))
    )
    done = set(state["uploaded"])
    todo = [f for f in files if f not in done]
    if limit:
        todo = todo[:limit]
    if not todo:
        print("all files already uploaded")
        return
    before = new_tab_count(page)
    groups = chunk_by_size(todo, chunk)
    print(f"{len(todo)} file(s) to upload, up to {chunk} files or "
          f"{CHUNK_BYTES/1e6:.0f}MB per batch (New tab currently holds {before})\n")

    for i, group in enumerate(groups):
        paths = [str(IMG_DIR / f) for f in group]
        try:
            send_files(page, paths)
            # Adobe processes server-side; wait for the count to settle.
            page.wait_for_timeout(4000)
            deadline = time.time() + 600
            while time.time() < deadline:
                busy = page.locator(
                    '[class*="progress" i], [role="progressbar"]'
                ).count()
                if busy == 0:
                    break
                page.wait_for_timeout(3000)
            # VERIFY, don't assume. Progress bars disappearing is not proof a
            # file landed: this used to journal every batch unconditionally and
            # recorded 273 uploads for roughly 50 real ones. Adobe caps
            # pending-moderation files for new contributors and silently drops
            # the overflow -- no error, no failed batch, just nothing arriving.
            after = new_tab_count(page)
            gained = (after - before) if (after >= 0 and before >= 0) else -1
            if gained <= 0:
                print(f"  STOP batch {i+1}: count did not grow "
                      f"({before} -> {after}) — NOTHING LANDED.\n"
                      f"       Cause is unconfirmed. Verified 2026-08-19 that "
                      f"set_input_files on Adobe's hidden input[name=file] "
                      f"triggers no upload request at all: no error, no network "
                      f"call, count unchanged. Could be a changed upload handler "
                      f"or an account limit — do NOT assume a moderation cap "
                      f"without evidence. Upload one file by hand and watch.")
                break
            landed = group[:gained]
            state["uploaded"].extend(landed)
            save_state(state)
            if gained < len(group):
                print(f"  PART batch {i+1}: {gained} of {len(group)} landed "
                      f"({before} -> {after}) — cap reached mid-batch")
                before = after
                break
            print(f"  OK   batch {i+1}: {gained} files "
                  f"({len(state['uploaded'])}/{len(files)} total)")
            before = after
        except Exception as e:
            state["failed"][f"batch@{i+1}"] = f"{type(e).__name__}: {e}"
            save_state(state)
            print(f"  FAIL batch {i+1}: {type(e).__name__}: {e}")
        time.sleep(random.uniform(4, 9))
    print(f"\nuploaded {len(state['uploaded'])} of {len(files)}")


def phase_csv(page, state):
    """Import the metadata CSV — sets title/keywords for every uploaded file at once."""
    if not CSV_PATH.exists():
        print(f"ERROR: {CSV_PATH} not found")
        return
    page.goto(UPLOADS_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(6000)
    btn = page.locator('button:has-text("Upload CSV"), a:has-text("Upload CSV")').first
    if btn.count() == 0:
        print("ERROR: could not find the 'Upload CSV' control")
        return
    btn.click()
    page.wait_for_timeout(2000)
    inputs = page.locator('input[type="file"]')
    # The CSV chooser is typically the last file input added to the DOM.
    inputs.nth(inputs.count() - 1).set_input_files(str(CSV_PATH))
    page.wait_for_timeout(6000)
    state["csv_imported"] = True
    save_state(state)
    print("CSV submitted — verify titles/keywords populated in the portal")


def phase_submit(page, state):
    """Select all uploaded files and submit them for moderation."""
    page.goto(UPLOADS_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(6000)
    sel_all = page.locator(
        'input[type="checkbox"][aria-label*="all" i], button:has-text("Select all")'
    ).first
    if sel_all.count():
        sel_all.click()
        page.wait_for_timeout(1500)
    submit = page.locator('button:has-text("Submit")').first
    if submit.count() == 0:
        print("ERROR: no Submit control found")
        return
    label = (submit.inner_text() or "").strip()
    if submit.is_disabled():
        print(f"Submit is disabled ({label!r}) — files may still be processing, "
              "or metadata/releases are incomplete")
        return
    print(f"clicking: {label!r}")
    before = new_tab_count(page)
    page.goto(UPLOADS_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(6000)
    page.locator('button:has-text("Submit")').first.click()
    page.wait_for_timeout(8000)

    # VERIFY. Clicking Submit is not proof anything was accepted: on 2026-08-19
    # this reported "submitted for moderation" while Adobe showed the banner
    # "Not all of your contents could be submitted for moderation" and moved
    # exactly ONE file of 52. Adobe caps how many files may await moderation
    # (In review sat at 3 and would not go higher), so most of a batch bounces
    # with no per-file error.
    import re as _re
    body = _re.sub(r"[ \t]+", " ", page.inner_text("body"))
    partial = bool(_re.search(r"Not all of your contents could be submitted", body, _re.I))
    after = new_tab_count(page)
    moved = (before - after) if (before >= 0 and after >= 0) else -1
    if partial or (0 <= moved < before):
        print(f"PARTIAL: {moved} of {before} accepted for moderation "
              f"(New {before} -> {after}).")
        print("        Adobe limits how many files may be awaiting moderation. "
              "The rest stay staged with their metadata; re-run --phase submit "
              "once the current batch clears review.")
        state["submitted"] = False
    else:
        print(f"submitted {moved} file(s) for moderation (New {before} -> {after})")
        state["submitted"] = True
    save_state(state)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["upload", "csv", "submit"], default="upload")
    ap.add_argument("--chunk", type=int, default=20)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()

    state = load_state()
    if args.status:
        total = len([f for f in os.listdir(IMG_DIR)
                     if f.lower().endswith((".jpg", ".jpeg", ".png"))])
        print(f"uploaded:     {len(state['uploaded'])}/{total}")
        print(f"csv imported: {state['csv_imported']}")
        print(f"submitted:    {state['submitted']}")
        print(f"failed:       {len(state['failed'])}")
        for k, v in list(state["failed"].items())[:5]:
            print(f"  {k}: {str(v)[:110]}")
        return

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        page = get_page(p)
        try:
            ensure_signed_in(page)
        except SessionError as e:
            print(f"ABORTED: {e}")
            sys.exit(2)
        if args.phase == "upload":
            phase_upload(page, state, args.chunk, args.limit)
        elif args.phase == "csv":
            phase_csv(page, state)
        else:
            phase_submit(page, state)


if __name__ == "__main__":
    main()
