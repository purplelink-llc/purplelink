#!/usr/bin/env python3
"""Promote the first 10 tags of every Alamy image to SUPERTAGS.

WHY THIS EXISTS
All 565 images passed QC and went on sale with 0/10 supertags, which Alamy
reports as "poor discoverability". Supertags are what Alamy's search actually
ranks on -- an image with none is close to invisible. Three days of live data
said the same thing: 22 views across 570 images.

WHAT A SUPERTAG IS
Not a new keyword. Each image already carries 20-50 tags; a supertag is one of
those tags flagged as primary. In the DOM every tag is
    <li id="tagN"><i class="icon-tag-star" onclick="modifyTag(name,false,1,'N')">
and clicking that star toggles it. So this script adds no new metadata and
invents nothing -- it only marks which of the existing tags matter most.

WHICH 10
The first ten, in the order the tags were uploaded. That order is not
arbitrary: scripts/photo-metadata.sh wrote keywords subject-first, so tag 0 is
the specific subject and the tail is generic filler. For DSC_7568 that gives
"tropical landscape, mountains, rain clouds, palm trees, volcanic terrain,
lush greenery, valley, overcast, tropical vegetation, nature" and leaves
"weather, foliage, cloud cover" behind -- which is the right split.

If an image carries fewer than 10 tags, all of them are starred.

TWO THINGS THAT BLOCKED THIS BEFORE
1. A "Congratulations / OK, got it" modal sits over the grid on load and
   swallows every click on a tile. Four different selection strategies were
   tried and measured at a zero success rate before the modal was spotted.
2. The grid does not scroll with the window. It lives in #cnt-wrapper and
   loads ~49 more tiles each time that element is scrolled to its bottom.
   Wheel events over the page never move it.

SAFETY
- Only images currently at 0/10 supertags are touched. Anything already
  starred was touched by a human and is left alone, which also makes the
  script idempotent and resumable.
- A save is journalled ONLY after the panel is re-read and confirms the
  supertag count. Clicking Save is not proof it saved -- that assumption is
  what let a Fine Art America run report 267 uploads when 101 had landed.

USAGE
  scripts/alamy-supertags.py --limit 40      # a chunk
  scripts/alamy-supertags.py                 # everything remaining
  scripts/alamy-supertags.py --status        # counts only, changes nothing
"""
import argparse, json, re, subprocess, sys, time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "photo-licensing-workspace" / "analytics" / "alamy-supertags.json"
URL = "https://www.alamy.com/myupload/Index.aspx"
CDP = "http://127.0.0.1:9340"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE = str(Path.home() / ".photo-automation-chrome")

# Count tiles by their filename label. Only DSC_* -- the iPhone frames and the
# purchased race photos are not ours to license and must never be promoted.
#
# The character class MUST allow spaces and parentheses. The original
# [\w.-]+ silently skipped every duplicate-suffixed name -- "DSC_0030 (1).jpeg",
# "DSC_0155 (1).jpeg" and 8 more. They were not reported as failures; they were
# never enumerated at all, so the run finished "complete" with 10 images still
# at 0/10 supertags. Alamy's own data export is what exposed it. The identical
# mistake (\S+) hid 6 files in the Shutterstock backlog the same week.
TAG_RE = r"^DSC_[\w.\-() ]+\.jpe?g$"
COUNT_TILES = (
    "()=>[...document.querySelectorAll('*')].filter(e=>"
    "/^DSC_[\\w.\\-() ]+\\.jpe?g$/i.test((e.textContent||'').trim())"
    "&&e.children.length===0).length"
)


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"done": [], "skipped": {}}


def save_state(s):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=1, sort_keys=True))


def chrome_up():
    """Attach to an ordinary Chrome. Playwright launching its own browser gets
    fingerprinted and Alamy answers with a bare 403 -- same reason
    stats-collect.py attaches instead of launching."""
    import urllib.request
    try:
        urllib.request.urlopen(f"{CDP}/json/version", timeout=4)
        return
    except Exception:
        pass
    subprocess.Popen(
        [CHROME, "--remote-debugging-port=9340", f"--user-data-dir={PROFILE}",
         "--no-first-run", "--no-default-browser-check", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(14)


# Both counters live in the right-hand panel. Reading them from there rather
# than from body innerText matters a lot: with 564 tiles loaded, serialising
# the whole document costs seconds, and this is called 3-4 times per image.
PANEL = ("()=>{const e=document.getElementById('cxpRHS');"
         "return e?e.innerText.replace(/\\s+/g,' '):'';}")


def counts(pg):
    """(tags, supertags) for the current selection. (0,0) means nothing is
    selected -- the panel's empty state looks identical to a tagless image,
    so callers must check the selection count separately."""
    m = re.search(r"(\d+)/50 tags including (\d+)/10 supertags", pg.evaluate(PANEL))
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def selected(pg):
    m = re.search(r"(\d+) images? selected", pg.evaluate(PANEL))
    return int(m.group(1)) if m else 0


def open_grid(pg, verbose=True):
    pg.goto(URL, wait_until="domcontentloaded", timeout=90000)
    pg.wait_for_timeout(22000)
    if "login" in pg.url.lower() or "signin" in pg.url.lower():
        sys.exit("Alamy session expired -- sign in at " + URL)
    dismiss_modal(pg)
    return load_all_tiles(pg, verbose)


def dismiss_modal(pg):
    """The QC congratulations panel overlays the grid and eats tile clicks."""
    for name in ("OK, got it", "OK got it", "Got it"):
        try:
            pg.get_by_role("button", name=re.compile(name, re.I)).first.click(timeout=4000)
            pg.wait_for_timeout(2500)
            return True
        except Exception:
            continue
    return False


def load_all_tiles(pg, verbose=True):
    """Scroll #cnt-wrapper until the tile count stops growing."""
    last, stall = pg.evaluate(COUNT_TILES), 0
    for _ in range(60):
        pg.evaluate("()=>{const c=document.getElementById('cnt-wrapper');"
                    "if(c) c.scrollTop=c.scrollHeight;}")
        pg.wait_for_timeout(4000)
        n = pg.evaluate(COUNT_TILES)
        if n != last:
            stall = 0
            if verbose:
                print(f"    loaded {n} tiles", flush=True)
        else:
            stall += 1
            if stall >= 5:
                break
        last = n
    return last


def tile_refs(pg):
    """(ref, filename) for every rendered tile, keyed by Alamy's own per-image
    ref (e.g. "3FE80D8", shown on-page as "Image ID: 3FE80D8") -- NOT
    filename. Each <li ref="..."> holds one image; the ref is unique and
    stable, unlike the filename.
    2026-09-08: the 285-file batch that failed QC on 2026-08-30 (IMG_9209
    poisoning it) was cleanly resubmitted on 2026-09-03 with the SAME
    filenames as before -- Alamy assigned them brand-new refs/image IDs, but
    the old filename-keyed dedup (tile_names() + state["done"]) saw those
    names already marked done from the original 565-image upload and skipped
    all ~285 of them, leaving the whole resubmitted batch at 0/10 supertags
    ("poor discoverability" on 854/854 on-sale images, 0 sales). Keying by
    ref instead of filename is what actually identifies a unique Alamy asset.
    """
    return pg.evaluate("""()=>[...document.querySelectorAll('li[ref]')].map(li=>{
        const cap = li.querySelector('.img_cap');
        return {ref: li.getAttribute('ref'), name: cap ? cap.textContent.trim() : null};
    }).filter(x=>x.name && /^DSC_[\\w.\\-() ]+\\.jpe?g$/i.test(x.name))""")


def click_tile(pg, ref):
    """Select exactly one image by its Alamy ref (Image ID). Returns True
    once the panel agrees that one image is selected. Selecting by ref via
    its unique #automationImage<ref> id avoids the ambiguity a filename-based
    lookup has whenever two tiles share a filename (see tile_refs)."""
    loc = pg.locator(f"#automationImage{ref}")
    if loc.count() == 0:
        return False
    try:
        loc.first.scroll_into_view_if_needed(timeout=5000)
        pg.wait_for_timeout(700)
        loc.first.click(timeout=5000)
    except Exception:
        return False
    pg.wait_for_timeout(2200)
    if selected(pg) != 1:
        # A stray earlier click can leave two selected; clearing is cheaper
        # than guessing which one the panel is describing.
        try:
            pg.get_by_text("Clear selection", exact=False).first.click(timeout=3000)
            pg.wait_for_timeout(1500)
        except Exception:
            pass
        try:
            loc.first.click(timeout=5000)
        except Exception:
            return False
        pg.wait_for_timeout(2200)
    return selected(pg) == 1


def star_first_ten(pg, n_tags):
    want = min(10, n_tags)
    for i in range(want):
        try:
            pg.locator(f"ul.sg-w > li#tag{i} i.icon-tag-star").first.click(timeout=5000)
            pg.wait_for_timeout(220)
        except Exception:
            pass
    return want


def process(pg, ref, state):
    if not click_tile(pg, ref):
        return "unreachable"
    n_tags, n_super = counts(pg)
    if n_tags is None:
        return "no-panel"
    if n_tags == 0:
        return "no-tags"
    if n_super != 0:
        # Already starred by a human or an earlier run. Never re-toggle:
        # clicking a lit star removes it.
        state["done"].append(ref)
        return f"already {n_super}/10"

    want = star_first_ten(pg, n_tags)
    _, after = counts(pg)
    if after != want:
        return f"starred {after}, wanted {want}"

    try:
        pg.get_by_role("button", name=re.compile(r"^Save$")).first.click(timeout=8000)
    except Exception:
        return "save button missing"
    pg.wait_for_timeout(4500)

    # Clicking Save is not proof. Re-read the panel.
    _, confirmed = counts(pg)
    if confirmed != want:
        return f"save unconfirmed ({confirmed}/{want})"
    state["done"].append(ref)
    return f"ok {want}/10"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="images this run (0 = all)")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()

    state = load_state()
    # "done" is keyed by Alamy's per-image ref (Image ID), not filename -- see
    # tile_refs(). A state file written before 2026-09-08 has filenames in
    # here instead; those never match a real ref, so this run re-verifies
    # every tile once (cheap for the ones already starred -- process() just
    # reads the panel and re-marks them done by ref) and self-heals the file.
    done = set(state["done"])
    chrome_up()

    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        pg = ctx.new_page()
        pg.set_viewport_size({"width": 1500, "height": 950})
        print("opening Image Manager (this takes ~2 min to load all tiles)", flush=True)
        total = open_grid(pg)
        items = tile_refs(pg)
        todo = [it for it in items if it["ref"] not in done]
        print(f"\n{total} tiles loaded | {len(items) - len(todo)} already starred | {len(todo)} to do")

        if a.status:
            pg.close()
            return

        if a.limit:
            todo = todo[:a.limit]
        print(f"processing {len(todo)} this run\n", flush=True)

        # Filename -> refs seen in this scan. Alamy's virtual-scroll grid can
        # momentarily recycle a DOM node between two images: tile_refs() reads
        # a ref off a node that gets reassigned to a different image before
        # click_tile() reaches it, so #automationImage<ref> then matches
        # nothing -- "unreachable" forever, not a real image. Found 2026-09-08:
        # 5 such ghost refs, every one a duplicate of a filename whose OTHER
        # (real) ref had already been supertagged successfully. Confirmed via
        # Alamy's own data (same filename, different ref, real ref already
        # done) before trusting this, per the platform-terms-research skill's
        # confidence-sequencing rule -- do not silently swallow "unreachable"
        # without that cross-check, since a genuinely broken tile looks
        # identical to a ghost one from process()'s point of view.
        by_name = {}
        for it in items:
            by_name.setdefault(it["name"], []).append(it["ref"])

        fails = 0
        for i, it in enumerate(todo, 1):
            name, ref = it["name"], it["ref"]
            r = process(pg, ref, state)
            ok = r.startswith("ok") or r.startswith("already")
            if not ok and r == "unreachable" and any(
                    other in done for other in by_name.get(name, []) if other != ref):
                r = "ghost (duplicate of an already-done ref, ignored)"
                ok = True
                state["done"].append(ref)
                done.add(ref)
            print(f"  [{i}/{len(todo)}] {name:34s} {ref:10s} {r}", flush=True)
            if ok:
                fails = 0
            else:
                state["skipped"][ref] = f"{name}: {r}"
                fails += 1
                # Five in a row means the page state is wrong -- a modal
                # reappeared, the session dropped, or Chrome is wedged.
                # Grinding through 500 failures helps nobody.
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
