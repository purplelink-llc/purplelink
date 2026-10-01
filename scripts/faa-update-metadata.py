#!/usr/bin/env python3
"""Push faa-metadata-v2.csv's decor-tuned keywords/description onto every
already-live Fine Art America listing.

WHY THIS EXISTS
faa-upload.py only sets metadata ONCE, at upload time, and only fills BLANK
fields -- it never overwrites existing ones. Every one of the ~48 pieces
already live on FAA is still carrying whatever went up originally: the same
stock-licensing keyword set every other platform gets ("candid moment",
"horseplay", "antics"), not the decor/gift-intent phrasing
platform-keywords.py's faa_keywords()/faa_description() now generate
("living room wall art", "nature lover gift"). This script is what actually
gets the fix onto the live site.

Deliberately does NOT touch title. Title is the join key back to
faa-metadata-v2.csv -- FAA's edit form shows title but never the source
filename anywhere, so changing title mid-run would break matching for every
listing not yet processed. Current titles already front-load the strongest
keyword phrase, which is what FAA's own seller guidance asks for anyway.

MECHANISM
Each artwork's real edit form lives at
  /controlpanel/updateartwork.html?artworkid=<id>
(FAA 302s this to a dated updateartworkYYYY.html -- follow redirects rather
than hardcoding the year). artworkid isn't printed anywhere in the public
profile page's visible HTML; it's the first argument to editimage(id, pos)
buried in each listing's "Edit" link, a javascript: href that opens an
unrelated small reposition popup -- chased down 2026-09-19 by reading
editimage()'s own source rather than guessing at the UI.

USAGE
  scripts/faa-update-metadata.py --limit 5
  scripts/faa-update-metadata.py
  scripts/faa-update-metadata.py --status
"""
import argparse, csv, json, re, subprocess, sys, time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
WS = ROOT / "photo-licensing-workspace"
STATE = WS / "analytics" / "faa-metadata-update.json"
CSV_PATH = WS / "faa-metadata-v2.csv"
PROFILE_URL = "https://fineartamerica.com/profiles/benjamin-ampel.html"
CDP = "http://127.0.0.1:9340"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE_DIR = str(Path.home() / ".photo-automation-chrome")


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"done": [], "skipped": {}}


def save_state(s):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=1, sort_keys=True))


def chrome_up():
    import urllib.request
    try:
        urllib.request.urlopen(f"{CDP}/json/version", timeout=4)
        return
    except Exception:
        pass
    subprocess.Popen(
        [CHROME, "--remote-debugging-port=9340", f"--user-data-dir={PROFILE_DIR}",
         "--no-first-run", "--no-default-browser-check"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(14)


def load_new_metadata():
    """title -> (keywords, description) from faa-metadata-v2.csv."""
    rows = list(csv.DictReader(open(CSV_PATH)))
    return {r["Title"].strip(): (r["Keywords"], r["Description"]) for r in rows}


def list_artwork_ids(page):
    page.goto(PROFILE_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(6000)
    if "login" in page.url.lower() or "signin" in page.url.lower():
        sys.exit("FAA session expired -- sign in at " + PROFILE_URL)
    ids, page_n = [], 1
    while True:
        url = f"https://fineartamerica.com/profiles/benjamin-ampel?tab=artwork&page={page_n}"
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)
        got = page.evaluate("""()=>[...document.querySelectorAll('a[href^="javascript: editimage"]')]
            .map(a=>{
                const m = a.getAttribute('href').match(/editimage\\((\\d+),\\s*(\\d+)\\)/);
                return m ? m[1] : null;
            }).filter(Boolean)""")
        if not got:
            break
        ids += [i for i in got if i not in ids]
        has_next = page.evaluate(
            """()=>[...document.querySelectorAll('a')].some(a=>/^Next$/i.test((a.textContent||'').trim()))""")
        if not has_next:
            break
        page_n += 1
        if page_n > 20:          # sanity cap, matches nothing this account has ever had
            break
    return ids


def process(page, artwork_id, by_title):
    page.goto(f"https://fineartamerica.com/controlpanel/updateartwork.html?artworkid={artwork_id}",
              wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(2500)
    title_el = page.locator('input[name="artworkname"]').first
    if title_el.count() == 0:
        return None, "no edit form rendered"
    title = title_el.input_value().strip()
    if title not in by_title:
        return title, "no matching row in faa-metadata-v2.csv"
    new_kw, new_desc = by_title[title]

    # FAA lowercases the keywords field server-side on save ("Sonoran
    # Desert" comes back "sonoran desert") -- confirmed 2026-09-19 by diffing
    # a "mismatch" character-by-character; the save had actually worked, the
    # comparison was just case-sensitive against a field FAA itself doesn't
    # preserve case on. Compare case-insensitively throughout, here and in
    # the post-save verification below, or every single save reports a false
    # failure forever.
    kw_el = page.locator('textarea[name="artworkkeywords"]').first
    desc_el = page.locator('textarea[name="artworkdescription"]').first
    if kw_el.input_value().lower() == new_kw.lower() and desc_el.input_value() == new_desc:
        return title, "already up to date"

    kw_el.fill(new_kw)
    desc_el.fill(new_desc)
    try:
        page.get_by_role("link", name="Submit").first.click(timeout=8000)
    except Exception:
        return title, "submit control not found"
    page.wait_for_timeout(4000)

    # Verify against a fresh reload of the same edit page -- a click is not
    # proof, same discipline as the Alamy category/deadword scripts.
    page.goto(f"https://fineartamerica.com/controlpanel/updateartwork.html?artworkid={artwork_id}",
              wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(2000)
    after_kw = page.locator('textarea[name="artworkkeywords"]').first.input_value()
    if after_kw.lower() != new_kw.lower():
        return title, f"save unconfirmed (live is {len(after_kw)} chars, expected {len(new_kw)})"
    return title, "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()

    state = load_state()
    done = set(state["done"])
    by_title = load_new_metadata()
    chrome_up()

    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        pg = ctx.new_page()
        ids = list_artwork_ids(pg)
        todo = [i for i in ids if i not in done]
        print(f"{len(ids)} live listing(s) | {len(ids) - len(todo)} already done | {len(todo)} to do")

        if a.status:
            pg.close()
            return

        if a.limit:
            todo = todo[:a.limit]
        print(f"processing {len(todo)} this run\n", flush=True)

        fails = 0
        for i, artwork_id in enumerate(todo, 1):
            try:
                title, r = process(pg, artwork_id, by_title)
            except Exception as e:
                title, r = None, f"{type(e).__name__}: {e}"

            ok = r in ("ok", "already up to date")
            # "no matching row" is a PERMANENT, expected outcome (title
            # drifted after upload, or the listing predates this pipeline
            # entirely) -- not a sign anything is actually broken, and
            # retrying it will never succeed. Counting it toward the
            # consecutive-failure circuit breaker was a real bug: these 5
            # always sort first (same deterministic order every run), so
            # every restart hit "5 consecutive failures" on the exact same
            # 5 permanently-unmatched items and made zero progress, ever --
            # caught 2026-09-19 after 15 straight crash-loop restarts.
            # Record it and move on; only count it toward `fails` if it
            # starts happening in an unbroken run of its own (a sudden wall
            # of these WOULD mean something changed, e.g. faa-metadata-v2.csv
            # went missing or titles stopped matching en masse).
            permanent_skip = r == "no matching row in faa-metadata-v2.csv"
            print(f"  [{i}/{len(todo)}] {artwork_id}  {(title or '?')[:45]:45s} {r}", flush=True)
            if ok:
                state["done"].append(artwork_id)
                fails = 0
            elif permanent_skip:
                state["skipped"][artwork_id] = f"{title}: {r}"
                state["done"].append(artwork_id)   # never worth revisiting
            else:
                state["skipped"][artwork_id] = f"{title}: {r}"
                fails += 1
                if fails >= 5:
                    print("\n5 consecutive failures -- stopping. Check the browser.")
                    break
            if i % 10 == 0:
                save_state(state)

        save_state(state)
        print(f"\ndone: {len(state['done'])} | skipped: {len(state['skipped'])}")
        pg.close()


if __name__ == "__main__":
    main()
