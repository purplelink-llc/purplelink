#!/usr/bin/env python3
"""Push photos onto 123RF via the web uploader, in multi-file batches.

WHY THIS EXISTS
570 images were FTP'd to ftp.123rf.com starting 2026-09-10. A week later
Manage Content still shows "You have no uploaded content yet" across every
type, and the account sits at Contributor Level 0 -- 123RF's FTP ingestion
never picked any of them up. Verified 2026-09-22 that the WEB uploader is a
completely different path that actually works: selecting one file and
clicking Proceed lands on manage-content with "Your image have been
successfully saved to drafts." The FTP inbox is a dead end; this script
re-submits the same 570 files through the working path.

MECHANISM (found 2026-09-22 by trial)
/contributor/upload-content?category=images has input[type=file] (no
`multiple` attribute). set_input_files() with ONE path shows "Uploaded
successfully" and a running "Total: N files" queue. The input element gets
replaced/removed from the DOM the moment a file queues, and clicking the
"Upload Media" tab to get a fresh input back was unreliable (synthetic
click not registering on this SPA's tab component) -- so rather than fight
multi-file accumulation, this does a full page.goto() per file, which
reliably yields a working file input every time. Two buttons match
text "Proceed" (a stepper label plus the real submit button after the
Content Contributor Agreement warranty text); .last is the real one.
Clicking it redirects to manage-content?tab=draft with the confirmation
text and "Processing 1 of 1 Photos."

Clicking Proceed accepts 123RF's Content Contributor Agreement (rights
ownership, no trademark infringement, model releases, indemnification) for
that file -- authorized by the account owner 2026-09-22 for this exact
image set, which already cleared clean-upload-set.json.

BATCHES (2026-09-23): the file input now carries `multiple`, and one
Proceed submits everything queued -- verified with 4 files (3 landed, 1
rejected "Exceeded photo max dimension"). One file per page load ran ~34s
per image; batches of up to 10 cut that several-fold. Each batch stays
under 25MB because Playwright refuses to push more than 50MB through one
set_input_files() call over CDP. Per-file results are read off the Upload
Queue panel: success rows are "N  name  jpeg", failure rows add an error
column. A rejection from 123RF itself (e.g. max dimension) is permanent and
never retried; our own timeouts are.

USAGE
  scripts/123rf-web-upload.py --limit 50
  scripts/123rf-web-upload.py --status
"""
import argparse, json, re, sys, time, random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WS = ROOT / "photo-licensing-workspace"
STATE = WS / "analytics" / "123rf-web-upload-state.json"
SRC = Path("/Volumes/Extreme SSD/Nikon Photos")
CANDIDATES = WS / "ftp-state" / "123rf.json"   # the 570 already FTP'd, still unprocessed
CDP = "http://127.0.0.1:9340"


class SessionError(RuntimeError):
    pass


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"uploaded": {}, "failed": {}}


def save_state(s):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=2))


UPLOAD_URL = "https://www.123rf.com/contributor/upload-content?category=images"
BATCH_MAX_FILES = 10
BATCH_MAX_BYTES = 25_000_000


def make_batches(files):
    batches, cur, size = [], [], 0
    for f in files:
        sz = (SRC / f).stat().st_size
        if cur and (len(cur) >= BATCH_MAX_FILES or size + sz > BATCH_MAX_BYTES):
            batches.append(cur)
            cur, size = [], 0
        cur.append(f)
        size += sz
    if cur:
        batches.append(cur)
    return batches


def parse_queue(text):
    """Stems that uploaded, and {stem: error} for ones 123RF refused."""
    start = text.find("Completed")
    end = text.find("By proceeding", start if start >= 0 else 0)
    panel = text[start:end] if start >= 0 else ""
    ok, bad = set(), {}
    for line in panel.splitlines():
        cols = [c.strip() for c in line.split("\t") if c.strip()]
        if not cols or not cols[0].isdigit():
            continue
        if len(cols) >= 4:
            bad[cols[1]] = cols[3]
        elif len(cols) == 3:
            ok.add(cols[1])
    return ok, bad


def upload_batch(page, batch):
    """Returns (uploaded filenames, {filename: permanent error}, {filename: transient error})."""
    page.bring_to_front()
    page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=60_000)
    page.wait_for_timeout(4000)
    if "login" in page.url.lower():
        raise SessionError("not signed in to 123RF in this Chrome profile — sign in, then re-run")
    if "upload-id" in page.url:
        raise SessionError("123RF is showing the ID/liveness verification page again — "
                           "complete it in the browser, then re-run")
    finput = page.locator('input[type="file"]')
    if finput.count() == 0:
        return [], {}, {f: "no file input on upload-content page" for f in batch}
    # Pushing ~40MB through CDP can exceed the default 30s action timeout
    # (every 30MB+ batch failed that way on 2026-09-23).
    finput.first.set_input_files([str(SRC / f) for f in batch], timeout=180_000)

    by_stem = {Path(f).stem: f for f in batch}
    ok, bad = set(), {}
    for _ in range(90):
        page.wait_for_timeout(2000)
        text = page.inner_text("body")
        ok, bad = parse_queue(text)
        if not re.search(r"Uploading\s+\d+%", text) and len(ok) + len(bad) >= len(batch):
            break
    else:
        return [], {}, {f: "upload queue did not settle in 3 min" for f in batch}

    permanent = {by_stem[s]: f"PERMANENT: {e}" for s, e in bad.items() if s in by_stem}
    if not ok:
        return [], permanent, {}
    page.locator('button:text-is("Proceed")').last.click()
    try:
        page.wait_for_url(re.compile("manage-content"), timeout=60_000)
    except Exception:
        return [], permanent, {by_stem[s]: "Proceed did not land on manage-content" for s in ok if s in by_stem}
    page.wait_for_timeout(2000)
    body = page.inner_text("body")
    if "successfully saved" not in body and "Processing" not in body:
        return [], permanent, {by_stem[s]: "no draft confirmation after Proceed" for s in ok if s in by_stem}
    return [by_stem[s] for s in ok if s in by_stem], permanent, {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="max images this run")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--min-delay", type=float, default=3.0)
    ap.add_argument("--max-delay", type=float, default=6.0)
    a = ap.parse_args()

    state = load_state()
    if a.status:
        perm = sum(1 for v in state["failed"].values() if v.startswith("PERMANENT"))
        print(f"uploaded: {len(state['uploaded'])}")
        print(f"failed:   {len(state['failed'])} ({perm} permanent)")
        for k, v in list(state["failed"].items())[:10]:
            print(f"  FAIL {k}: {v}")
        return

    candidates = json.loads(CANDIDATES.read_text())["uploaded"]
    todo = [f for f in candidates
            if f not in state["uploaded"]
            and not state["failed"].get(f, "").startswith("PERMANENT")
            and (SRC / f).exists()]
    if a.limit:
        todo = todo[: a.limit]
    if not todo:
        print("nothing to do")
        return
    batches = make_batches(todo)
    print(f"{len(todo)} image(s) in {len(batches)} batch(es)\n", flush=True)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        def attach():
            try:
                browser = p.chromium.connect_over_cdp(CDP)
            except Exception as e:
                print(f"ERROR: could not attach to Chrome on {CDP}\n  {e}")
                sys.exit(1)
            ctx = browser.contexts[0] if browser.contexts else browser.new_context()
            # Own tab, kept in front: a background tab gets throttled and every
            # wait times out (2026-09-23).
            pg = ctx.new_page()
            pg.bring_to_front()
            return pg

        page = attach()
        ok_total = fail_total = 0
        dead_batches = 0
        for bi, batch in enumerate(batches, 1):
            if dead_batches >= 3:
                print("\nSTOPPING: 3 batches in a row uploaded nothing. Check the browser.")
                break
            try:
                done, perm, transient = upload_batch(page, batch)
            except SessionError as e:
                print(f"\nABORTED: {e}")
                break
            except Exception as e:
                done, perm = [], {}
                transient = {f: f"{type(e).__name__}: {str(e)[:120]}" for f in batch}
                if "has been closed" in str(e):
                    page = attach()

            for f in done:
                state["uploaded"][f] = "saved to drafts"
                state["failed"].pop(f, None)
            state["failed"].update(perm)
            state["failed"].update(transient)
            save_state(state)
            ok_total += len(done)
            fail_total += len(perm) + len(transient)
            dead_batches = 0 if done or (perm and not transient) else dead_batches + 1

            line = f"  [{bi}/{len(batches)}] {len(done)}/{len(batch)} uploaded"
            if perm:
                line += f" | refused: {', '.join(f'{k} ({v[11:40]})' for k, v in perm.items())}"
            if transient:
                line += f" | retry later: {len(transient)} ({next(iter(transient.values()))[:60]})"
            print(line, flush=True)
            if bi < len(batches):
                time.sleep(random.uniform(a.min_delay, a.max_delay))

        print(f"\ndone: {ok_total} uploaded, {fail_total} not")
        print(f"state: {STATE}")


if __name__ == "__main__":
    main()
