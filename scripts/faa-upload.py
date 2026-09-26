#!/usr/bin/env python3
"""Batch-upload photos to Fine Art America by driving an already-authenticated Chrome.

This never handles credentials. You log into FAA yourself in a Chrome started with
remote debugging; the script attaches to that session over the DevTools protocol.

SETUP (once per run)
  1. Quit Chrome completely (Cmd-Q).
  2. Start it with the debug port open:

     /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \\
       --remote-debugging-port=9340 --user-data-dir="$HOME/.photo-automation-chrome"

     The first time, that fresh profile won't be logged in — sign into
     fineartamerica.com in it once. It persists for later runs.
  3. Run this script.

USAGE
  scripts/faa-upload.py --queue <queue.csv> --dir <image-dir> [--limit N] [--dry-run]
  scripts/faa-upload.py --status          # what's uploaded so far

Resumable: every success is journaled, so re-running skips finished images.
"""
import argparse, csv, json, os, re, sys, time, random
from pathlib import Path

STATE = Path(__file__).resolve().parent.parent / "photo-licensing-workspace" / "faa-upload-state.json"
CDP = "http://127.0.0.1:9340"
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


MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"


def faa_title(full):
    """Searchable FAA title: a leading editorial dateline ("Tokyo, Japan - June
    2025: ...") becomes a trailing place, accents fold to plain letters (how
    buyers type them), no colons (FAA rejects them), 100 chars max."""
    import unicodedata
    m = re.match(rf"^(?P<place>.+?)\s*-\s*(?:{MONTHS})\s+\d{{4}}\s*[-:]\s*(?P<desc>.+)$", full)
    if m:
        desc = m["desc"].strip().rstrip(".")
        desc = desc[0].upper() + desc[1:]
        place = m["place"].strip()
        full = desc if (place.lower() in desc.lower() or "," not in place) else f"{desc}, {place}"
    for a, b in (("Þ", "Th"), ("þ", "th"), ("ð", "d"), ("Ð", "D"), ("æ", "ae"), ("Æ", "Ae"), ("ø", "o")):
        full = full.replace(a, b)
    full = unicodedata.normalize("NFKD", full).encode("ascii", "ignore").decode()
    return re.sub(r"\s*:\s*", " - ", full).strip()[:100]


def wait_for(t, js, timeout):
    end = time.time() + timeout
    while time.time() < end:
        if t.eval(js):
            return True
        time.sleep(1)
    return False


def js_set(t, sel, value):
    """Set a plain-HTML field (FAA's forms aren't React) and fire its events."""
    t.eval(f"""(()=>{{const e=document.querySelector({sel!r}); if(!e) return false;
        e.value={value!r}; e.dispatchEvent(new Event('input',{{bubbles:true}}));
        e.dispatchEvent(new Event('change',{{bubbles:true}})); return true}})()""")


def account_count(t, title):
    """How many of the account's OWN images match this title.

    FAA's control-panel image finder (POST /queries/queryimagefinder.php, the
    endpoint behind bulkeditprices.html's lookup) is scoped to this account.
    The previous confirm_saved() typed into the first text input on that page,
    which is the SITE-WIDE header search, so it searched every artist's
    catalogue and could 'confirm' a title that only someone else had."""
    h = t.eval(f"""fetch('/queries/queryimagefinder.php',{{method:'POST',credentials:'include',
        headers:{{'content-type':'application/x-www-form-urlencoded'}},
        body:'page=1&artworkname='+encodeURIComponent({title!r})}}).then(r=>r.text())""") or ""
    if "No matches were found" in h:
        return 0
    m = re.search(r"Displaying:\s*\d+\s*-\s*\d+\s*of\s*(\d+)", re.sub(r"<[^>]+>", " ", h))
    if not m:
        raise SessionError(f"image finder returned something unexpected (signed out?): {h[:120]!r}")
    return int(m.group(1))


_UPLOAD_HREF = None


def upload_one(t, img_path, row, dry_run=False):
    """Upload a single image, verify metadata populated, save. Returns (ok, note)."""
    clean_title = faa_title(row["title"])
    probe = clean_title[:60]
    before = account_count(t, probe)
    if before:
        # The old uploader's "failed" list came from a title check that could
        # miss real uploads; never create a duplicate listing.
        return True, f"already in account ({before} match) — not re-uploaded"

    # The profile page renders every artwork (500+), so loading it per image
    # cost minutes; its Upload link carries a per-login sessionid that stays
    # the same, so fetch it once and reuse it until the upload page stops
    # rendering a file input.
    global _UPLOAD_HREF
    for fresh in (False, True):
        if fresh or not _UPLOAD_HREF:
            t.goto(PROFILE, settle=3)
            _UPLOAD_HREF = t.eval("([...document.querySelectorAll('a')].find(a=>/Upload Image/.test(a.innerText||''))||{}).href")
            # Fail fast and legibly when the session isn't authenticated: the
            # upload controls simply don't render for logged-out visitors.
            if not _UPLOAD_HREF:
                raise SessionError("not signed in to FAA in this Chrome profile — sign in, then re-run")
        t.goto(_UPLOAD_HREF, settle=2)
        # the file input is injected after initial DOM load
        if wait_for(t, "!!document.querySelector('input[type=file]')", 30 if not fresh else 60):
            break
    else:
        return False, "upload page never rendered a file input"
    t.set_files("input[type=file]", [img_path])
    time.sleep(1)
    t.eval("[...document.querySelectorAll('a')].filter(a=>/Upload Image/.test(a.innerText||'')).pop().click()")

    # Field ids carry a per-upload hash, so always select by NAME.
    # Big panoramas can take minutes to process server-side.
    if not wait_for(t, "!!document.querySelector('input[name=artworkname]')", 300):
        return False, "timed out waiting for the details form"
    time.sleep(1.5)

    val = lambda sel: (t.eval(f"(document.querySelector({sel!r})||{{}}).value") or "").strip()
    has = lambda sel: bool(t.eval(f"!!document.querySelector({sel!r})"))
    got_title = val('input[name="artworkname"]')
    got_kw = val('textarea[name="artworkkeywords"]')
    got_desc = val('textarea[name="artworkdescription"]')

    # FAA ingests embedded IPTC. Backfill anything that didn't come through.
    # FAA refuses a colon in titles ("Please use only A-Z in your artwork
    # title") and more than 500 characters of keywords; editorial datelines
    # ("Tokyo, Japan - June 2025: ...") hit the first, a few long keyword sets
    # the second. Those images sat at the head of the queue, so every run
    # failed 5 in a row and stopped -- mistaken for an FAA upload wall until
    # the form's own error was read on 2026-09-23.
    # Always the queue's full title, never FAA's IPTC-ingested one: IPTC
    # ObjectName is capped at 64 bytes and loses accented letters, which left
    # 65 live titles cut mid-phrase or garbled ("Skgafoss"). FAA allows 100.
    if clean_title != got_title:
        js_set(t, 'input[name="artworkname"]', clean_title)
    if has('textarea[name="artworkkeywords"]'):
        # FAA prepends a stray comma to ingested keywords; strip it either way.
        v = got_kw.lstrip(", ") if got_kw else row["keywords"].replace(";", ",")
        if len(v) > 500:
            v = v[:500].rsplit(",", 1)[0]
        js_set(t, 'textarea[name="artworkkeywords"]', v)
    if has('textarea[name="artworkdescription"]') and not got_desc:
        js_set(t, 'textarea[name="artworkdescription"]', row["description"])

    filled = f"title={'auto' if got_title else 'manual'} kw={len(got_kw)}ch desc={'auto' if got_desc else 'manual'}"
    if dry_run:
        return True, f"DRY RUN (not saved) — {filled}"

    if not t.eval("(()=>{const b=document.querySelector('.buttonSubmit'); if(!b) return false; b.click(); return true})()"):
        return False, "no SUBMIT control found"
    time.sleep(3)
    wait_for(t, "document.readyState==='complete'", 60)
    time.sleep(2)

    # Clicking SUBMIT is NOT proof the image landed. The original run recorded
    # 267 successes while only ~101 images actually reached the account: past
    # roughly the 100th upload FAA silently stopped accepting, and every later
    # click was journaled as "saved". Confirm against the account before
    # claiming success, so a silent failure stops the run instead of hiding.
    if has('input[name="artworkname"]'):
        if "logged out of your account" in t.text():
            raise SessionError("FAA answered 'logged out... Error Code 2404'. That is also how FAA "
                                   "refuses uploads past its ~100/day cap (2026-09-23: appeared "
                                   "after 101 uploads while the control panel still showed a "
                                   "signed-in session). If the control panel opens, retry tomorrow; "
                                   "otherwise sign in and re-run.")
        return False, "SUBMIT did not advance — still on the details form"
    after = account_count(t, probe)
    if after <= before:
        return False, f"SUBMIT clicked but '{probe}' is not in the account ({before} -> {after})"
    return True, f"saved+verified ({before} -> {after}) — {filled}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", default="photo-licensing-workspace/faa-upload-queue.csv")
    ap.add_argument("--dir", default="photo-licensing-workspace/faa-upload/batch-01-first25")
    ap.add_argument("--limit", type=int, default=0, help="max images this run (0 = all)")
    ap.add_argument("--dry-run", action="store_true", help="fill the form but don't save")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--min-delay", type=float, default=6.0)
    ap.add_argument("--max-delay", type=float, default=14.0)
    ap.add_argument("--only", help="JSON list or newline file of filenames to restrict to")
    ap.add_argument("--exclude", nargs="*", default=[], help="filenames to skip")
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
    only = None
    if args.only:
        raw = Path(args.only).read_text()
        only = set(json.loads(raw)) if raw.lstrip().startswith("[") else set(raw.split())
    # FAA rejects orders on AI-upscaled images, and only Nikon captures are
    # ever licensed (IMG_* = private iPhone frames).
    ai = re.compile(r"(?i)enhanced|topaz|denoise|sharpenai|upscal|gigapixel|-SR\b")
    todo = []
    for f in sorted(os.listdir(img_dir)):
        if not f.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        if f in state["uploaded"] or f in args.exclude or (only is not None and f not in only):
            continue
        if not f.startswith("DSC") or ai.search(f):
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

    # Raw CDP, not Playwright: connect_over_cdp hangs on this profile's synced
    # extensions (2026-09-24).
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from cdp_tab import Tab

    if True:
        def attach():
            try:
                pg = Tab.new()
            except Exception as e:
                print(f"ERROR: could not attach to Chrome on {CDP}\n  {e}\n")
                print("Start Chrome with the debug port open first — see the header of this file.")
                sys.exit(1)
            # Own tab, kept in front: a borrowed background tab gets throttled
            # and every wait times out (seen on 123RF 2026-09-23, same browser).
            pg.front()
            pg.goto("https://fineartamerica.com/aboutus.html", settle=2)
            return pg

        page = attach()

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
            # "Target ... has been closed" is the tab dying mid-run (observed
            # 2026-09-19: something closes every open tab in this CDP-driven
            # Chrome periodically, unrelated to FAA content). That's a local
            # infra hiccup, not FAA rejecting the image -- one reconnect-and-
            # retry recovers cleanly, so it shouldn't burn the real-failure
            # streak the way a genuine site-side rejection should.
            for attempt in range(2):
                try:
                    good, note = upload_one(page, img, row, args.dry_run)
                    break
                except SessionError as e:
                    print(f"\nABORTED: {e}")
                    print("Nothing was uploaded in this run. Fix the session and re-run;")
                    print("already-completed images are journaled and will be skipped.")
                    save_state(state)
                    sys.exit(2)
                except Exception as e:
                    good, note = False, f"{type(e).__name__}: {e}"
                    # cdp_tab surfaces a closed tab as a dead websocket. Safe to
                    # retry: upload_one checks the account first, so an image that
                    # landed before the tab died is recognised, not re-uploaded.
                    dead = isinstance(e, (ConnectionError, BrokenPipeError, OSError)) or \
                        "closed" in str(e).lower() or "WebSocket" in type(e).__name__
                    if dead and attempt == 0:
                        print(f"  ...  {label} — tab connection lost, reconnecting")
                        try:
                            page = attach()
                            continue
                        except SystemExit:
                            raise
                    break
            if good:
                ok += 1
                streak = 0
                if not args.dry_run:
                    state["uploaded"][img.name] = {"title": row["title"], "note": note}
                    state["failed"].pop(img.name, None)
                print(f"  OK   {time.strftime('%H:%M:%S')} {label} — {note}", flush=True)
            else:
                fail += 1
                streak += 1
                state["failed"][img.name] = note
                print(f"  FAIL {time.strftime('%H:%M:%S')} {label} — {note}", flush=True)
            save_state(state)
            if i < len(todo):
                # Ramp gently: FAA has a documented history of closing accounts that
                # look like bots. Randomized human-scale gaps.
                time.sleep(random.uniform(args.min_delay, args.max_delay))

        print(f"\ndone: {ok} ok, {fail} failed")
        print(f"state: {STATE}")


if __name__ == "__main__":
    main()
