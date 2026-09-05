#!/usr/bin/env python3
"""Upload the country-tagged, cleared set to a Getty ESP batch.

Getty has no FTP, so this drives their ESP web uploader over CDP against an
ordinary Chrome you're already signed into (Playwright-launched Chrome gets
fingerprinted and blocked -- see analytics/README.md).

The set is split by `use`, because ESP batches are typed and the two types have
different rules:
  commercial -> "iStock creative image"   (needs releases for recognisable people)
  editorial  -> "iStock editorial image"  (needs "Place - Month YYYY:" captions)

USAGE
  # create the batch yourself in ESP, then pass its id:
  scripts/getty-upload.py --batch 66154962 --use commercial
  scripts/getty-upload.py --batch <id> --use commercial --limit 40
  scripts/getty-upload.py --batch <id> --use commercial --status
"""
import argparse, csv, json, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WS = ROOT / "photo-licensing-workspace"
SRC = Path("/Volumes/Extreme SSD/Nikon Photos")
SET = WS / "getty-ready-set.csv"
STATE = WS / "getty-upload-state.json"
CDP = "http://127.0.0.1:9225"
# Playwright refuses to transfer more than 50MB per set_input_files call when it
# talks to the browser over CDP (it treats it as "not co-located"), so chunks are
# sized by BYTES, not by file count. Panoramas here run past 40MB on their own.
CHUNK_BYTES = 35 * 1024 * 1024
MAX_PER_CHUNK = 12
SETTLE = 4          # seconds per file to let Getty ingest before the next chunk
# ESP silently stops accepting at 100 files per batch. It returns no error --
# the uploads simply don't land -- so the first run journalled 265 successes for
# 100 real files. The cap is enforced here AND verified against the page.
BATCH_CAP = 100


def chunk_by_size(names):
    """Group filenames so each group stays under the CDP transfer ceiling."""
    out, cur, tot = [], [], 0
    for n in names:
        sz = (SRC / n).stat().st_size
        if cur and (tot + sz > CHUNK_BYTES or len(cur) >= MAX_PER_CHUNK):
            out.append(cur); cur, tot = [], 0
        cur.append(n); tot += sz
    if cur:
        out.append(cur)
    return out


PLAN = WS / "getty-batch-plan.json"
API = "https://esp.gettyimages.com/api/submission/v1/submission_batches/{}/contributions"


def api_uploaded(browser, only_batch=None):
    """Every filename ESP currently holds, across all known batches.

    Read from ESP's own API rather than the journal: a chunk that times out and
    lands late leaves the journal short, and sizing the next batch from a short
    journal is what created duplicates twice.

    `only_batch` narrows the check to a single batch. That is required when
    RESUBMITTING: images Getty rejected still sit in their original batch, so a
    library-wide check reports them as already uploaded and the resubmission
    silently sends nothing. Scoped to the destination batch, the duplicate
    protection still holds for the batch being filled.
    """
    if only_batch:
        plan = {only_batch: only_batch}
    else:
        plan = json.loads(PLAN.read_text()) if PLAN.exists() else {}
    if not plan:
        return set()
    pg = browser.contexts[0].new_page()
    try:
        pg.goto("https://esp.gettyimages.com/contribute/batches",
                wait_until="domcontentloaded", timeout=60_000)
        pg.wait_for_timeout(9_000)
        js = ("async (u) => {const r = await fetch(u,{credentials:'include',"
              "headers:{'Accept':'application/json'}}); return await r.text();}")
        seen = set()
        for bid in sorted(set(plan.values())):
            body = pg.evaluate(js, API.format(bid))
            # A signed-out ESP answers /api/ calls with HTTP 401 and the body
            #   {"ErrorCode":"TokenRequired","ErrorMessage":"Token missing"}
            # (not the SPA shell, which is what the browser navigation gets).
            # Either way there are no filenames in it, so it parses as "this
            # batch is empty" -- i.e. "nothing uploaded yet", precisely the
            # reading that re-sent files and created duplicates twice before.
            # Fail loudly rather than infer emptiness from an auth failure.
            if "TokenRequired" in body or "ErrorCode" in body \
               or "<html" in body[:400].lower():
                raise RuntimeError(
                    "ESP rejected the API call (not signed in). "
                    "Run: python3 scripts/stats-collect.py --login")
            seen |= set(re.findall(r"((?:DSC|IMG)_[\w\-() ]*\.jpe?g)", body))
        return seen
    finally:
        try:
            pg.close()
        except Exception:
            pass


def load_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {"uploaded": {}}


def save_state(s):
    STATE.write_text(json.dumps(s, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", required=True, help="ESP batch id from its URL")
    ap.add_argument("--use", choices=["commercial", "editorial"], required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--set", dest="set_csv", default=None,
                    help="alternative set CSV (default getty-ready-set.csv)")
    ap.add_argument("--resubmit", action="store_true",
                    help="dedupe against the TARGET batch only, so images "
                         "rejected from an earlier batch can be sent again")
    a = ap.parse_args()

    set_path = Path(a.set_csv) if a.set_csv else SET
    rows = [r for r in csv.DictReader(open(set_path)) if r["use"] == a.use]
    st = load_state()
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)

        # WHAT'S ALREADY IN GETTY comes from Getty, never from the journal.
        # The journal under-counts whenever a chunk times out and lands late;
        # computing the remaining work from it re-sent 25 commercial files and
        # then 10 editorial ones into a second batch. Ask ESP directly.
        done = api_uploaded(b, only_batch=a.batch if a.resubmit else None)
        todo = [r["filename"] for r in rows
                if r["filename"] not in done and (SRC / r["filename"]).exists()]
        if a.limit:
            todo = todo[: a.limit]
        print(f"batch {a.batch} · {a.use}: {len(rows)} in set, "
              f"{len(done & {r['filename'] for r in rows})} already in Getty, "
              f"{len(todo)} to send")
        if a.status or not todo:
            return
        pages = [x for x in b.contexts[0].pages if f"batches/{a.batch}" in x.url]
        pg = pages[-1] if pages else b.contexts[0].new_page()
        if f"batches/{a.batch}" not in pg.url:
            pg.goto(f"https://esp.gettyimages.com/contribute/batches/{a.batch}",
                    wait_until="domcontentloaded", timeout=60_000)
            pg.wait_for_timeout(12_000)

        def reopen():
            """ESP tabs die during long runs (a crash took out 13 chunks in a
            row once). Rebuild the page rather than failing every remaining
            chunk against a closed target."""
            nonlocal pg
            pg = b.contexts[0].new_page()
            pg.goto(f"https://esp.gettyimages.com/contribute/batches/{a.batch}",
                    wait_until="domcontentloaded", timeout=60_000)
            pg.wait_for_timeout(14_000)
            return pg

        def count_on_page():
            for _ in range(2):
                try:
                    m = re.search(r"(\d[\d,]*)\s+files?", pg.inner_text("body"))
                    return int(m.group(1).replace(",", "")) if m else -1
                except Exception:
                    reopen()
            return -1

        before = count_on_page()
        print(f"batch currently shows {before} files (cap {BATCH_CAP})")
        room = BATCH_CAP - before
        if room <= 0:
            sys.exit(f"batch {a.batch} is full at {before}/{BATCH_CAP} — create another batch")
        if len(todo) > room:
            print(f"only {room} slots left in this batch; sending {room} of {len(todo)}")
            todo = todo[:room]

        # ESP renders three file inputs, and NONE of them accepts files via
        # set_input_files any more:
        #   upload-release-button        multiple=false, property releases
        #   <no id>                      multiple=true,  accept=""   <- inert
        #   upload-contributions-button  multiple=true,  accept=image/jpeg
        # Targeting the right one by id used to work; as of 2026-08-21 ESP binds
        # its handler to the native picker instead, so set_input_files succeeds
        # silently and not one file arrives. The "Upload from device" label opens
        # that picker, which Playwright can intercept. Adobe changed the same way
        # in the same week.
        def open_panel():
            """ESP tears the Upload panel down after each use, taking the
            'Upload from device' control with it. Re-open it before EVERY chunk
            rather than assuming it persists -- dropping this step made chunks
            3-8 fail with 'control not found' while 1-2 succeeded."""
            for _ in range(3):
                if pg.evaluate("""()=>[...document.querySelectorAll('label,span,button')]
                        .some(x=>/^Upload from device$/i.test((x.textContent||'').trim()))"""):
                    return True
                pg.evaluate("""()=>{const b=[...document.querySelectorAll('button')]
                    .find(x=>(x.textContent||'').trim()==='Upload'); if(b) b.click();}""")
                pg.wait_for_timeout(4000)
            return False

        def send(paths):
            if not open_panel():
                raise RuntimeError("'Upload from device' control never appeared")
            with pg.expect_file_chooser(timeout=45_000) as fc:
                pg.evaluate("""()=>{const e=[...document.querySelectorAll('label,span,button')]
                    .find(x=>/^Upload from device$/i.test((x.textContent||'').trim()));
                    if(e) e.click();}""")
            fc.value.set_files(paths)

        chunks = chunk_by_size(todo)
        running = before
        print(f"sending {len(todo)} files in {len(chunks)} size-bounded chunks")
        for ci, chunk in enumerate(chunks, 1):
            paths = [str((SRC / f).resolve()) for f in chunk]
            mb = sum((SRC / f).stat().st_size for f in chunk) / 1e6
            sent = False
            for attempt in (1, 2):
                try:
                    send(paths)
                    sent = True
                    break
                except Exception as e:
                    msg = str(e)[:80]
                    # A timeout does NOT mean the files were rejected -- ESP is
                    # just slow. Retrying blindly uploaded 6 files twice into
                    # one batch. Check whether they landed before re-sending.
                    landed = count_on_page()
                    if landed > running:
                        print(f"  chunk {ci}/{len(chunks)}: timed out but "
                              f"{landed - running} landed anyway — not retrying")
                        sent = True
                        break
                    if "closed" in msg.lower() and attempt == 1:
                        print(f"  chunk {ci}/{len(chunks)}: page closed — reopening")
                        reopen()
                        continue
                    print(f"  chunk {ci}/{len(chunks)} FAILED ({mb:.0f}MB): {msg}")
                    break
            if not sent:
                continue
            pg.wait_for_timeout(SETTLE * 1000 * len(chunk))
            prev, now = running, count_on_page()
            running = now
            # Trust the PAGE, not the loop. If the batch didn't grow, those
            # files did not land -- journalling them anyway is how 265
            # "successes" turned into 100 real files.
            if now <= prev:
                print(f"  chunk {ci}/{len(chunks)}: batch did NOT grow ({prev}→{now}). "
                      f"Stopping — nothing after this would land either.")
                break
            if now - prev != len(chunk):
                print(f"  chunk {ci}/{len(chunks)}: WARNING sent {len(chunk)} but batch grew by "
                      f"{now - prev}")
            st.setdefault("uploaded", {}).setdefault(a.batch, [])
            st["uploaded"][a.batch] = sorted(set(st["uploaded"][a.batch]) | set(chunk))
            save_state(st)
            print(f"  chunk {ci}/{len(chunks)}: +{len(chunk)} ({mb:.0f}MB) → batch shows {now}")

        print(f"\ndone. batch shows {count_on_page()} files "
              f"(was {before}). Metadata and SUBMIT still to do in ESP.")


if __name__ == "__main__":
    main()
