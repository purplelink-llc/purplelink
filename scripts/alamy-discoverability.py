#!/usr/bin/env python3
"""Fill the Optional-tab fields (Primary category, Location) Alamy's
discoverability score actually weighs.

WHY THIS EXISTS
alamy-supertags.py fixed the Mandatory tab (tags/supertags) for every image,
but Alamy's own per-image discoverability meter (a live % shown on the
right-hand panel, e.g. "width:55.25%") did not move the account-level
"854 poor / 0 good" bucket at all. Investigated 2026-09-08: the panel has a
SEPARATE "Discoverability" view with "Mandatory" and "Optional" sub-tabs.
Mandatory was already 100% complete (150/150 caption, 10/10 supertags) for a
test image, yet its meter sat at 55.25% -- meaning the remaining ~45% comes
from the Optional tab: number of people, releases, location, date taken,
primary/secondary category, public-domain flag, exclusivity, additional
info, editorial-only flag.

Confirmed by live test on DSC_7299-Edit.jpeg / ref 3FE800H:
  baseline                          55.25%
  + Primary category (dropdown)     56.20%  (+0.95)
  + Location (free text)            57.16%  (+0.96)
Both values were re-verified after a full page reload -- real, persisted,
not a UI-only change.

WHAT THIS SCRIPT SETS
Only Primary category and Location, and only for filenames that already
have prepared, human/EXIF-derived data in:
  photo-licensing-workspace/alamy-categories.json  (553 filenames)
  photo-licensing-workspace/alamy-locations.json   (535 filenames)
All 553 category values were checked against Alamy's live dropdown list
before this script was written -- every one matches exactly.

It does NOT touch number-of-people, model/property release, or the
public-domain/exclusive/editorial-only checkboxes. Those need real
per-image judgment (a release claim or a "no people in this image" claim
that's actually false is a compliance problem, not a metadata nicety) and
there is no prepared, verified data for them. Guessing is out of scope --
see the platform-terms-research skill's confidence-sequencing rule.

SAFETY
- A field already set (category != "Select", or LocationAddress non-empty,
  read straight from Angular's scope so no click is needed to check) is
  left alone -- never overwrites a human's or an earlier run's answer.
- Save is not trusted by itself. After Save, this re-reads the selected
  category text and the scope's LocationAddress and only marks an image
  done if both match what was requested.
- Same ref-keyed dedup and ghost-duplicate handling as alamy-supertags.py
  (see that file's docstring/comments for why filename-keyed dedup broke).

USAGE
  scripts/alamy-discoverability.py --limit 40
  scripts/alamy-discoverability.py
  scripts/alamy-discoverability.py --status
"""
import argparse, json, re, subprocess, sys, time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "photo-licensing-workspace" / "analytics" / "alamy-discoverability.json"
CATEGORIES = ROOT / "photo-licensing-workspace" / "alamy-categories.json"
LOCATIONS = ROOT / "photo-licensing-workspace" / "alamy-locations.json"
URL = "https://www.alamy.com/myupload/Index.aspx"
CDP = "http://127.0.0.1:9340"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE = str(Path.home() / ".photo-automation-chrome")

COUNT_TILES = (
    "()=>[...document.querySelectorAll('*')].filter(e=>"
    "/^DSC_[\\w.\\-() ]+\\.jpe?g$/i.test((e.textContent||'').trim())"
    "&&e.children.length===0).length"
)

PANEL = ("()=>{const e=document.getElementById('cxpRHS');"
         "return e?e.innerText.replace(/\\s+/g,' '):'';}")


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
        [CHROME, "--remote-debugging-port=9340", f"--user-data-dir={PROFILE}",
         "--no-first-run", "--no-default-browser-check", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(14)


def selected(pg):
    m = re.search(r"(\d+) images? selected", pg.evaluate(PANEL))
    return int(m.group(1)) if m else 0


def dismiss_modal(pg):
    for name in ("OK, got it", "OK got it", "Got it"):
        try:
            pg.get_by_role("button", name=re.compile(name, re.I)).first.click(timeout=4000)
            pg.wait_for_timeout(2500)
            return True
        except Exception:
            continue
    return False


def load_all_tiles(pg, verbose=True):
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


def open_grid(pg, verbose=True):
    pg.goto(URL, wait_until="domcontentloaded", timeout=90000)
    pg.wait_for_timeout(22000)
    if "login" in pg.url.lower() or "signin" in pg.url.lower():
        sys.exit("Alamy session expired -- sign in at " + URL)
    dismiss_modal(pg)
    return load_all_tiles(pg, verbose)


def tile_refs(pg):
    """Same ref-keyed enumeration as alamy-supertags.py -- see that file for
    why filename is not a safe key (a resubmitted batch can reuse names)."""
    return pg.evaluate("""()=>[...document.querySelectorAll('li[ref]')].map(li=>{
        const cap = li.querySelector('.img_cap');
        return {ref: li.getAttribute('ref'), name: cap ? cap.textContent.trim() : null};
    }).filter(x=>x.name && /^DSC_[\\w.\\-() ]+\\.jpe?g$/i.test(x.name))""")


def click_tile(pg, ref):
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


def open_optional_tab(pg):
    try:
        pg.locator("#automationOptionalInformation").first.click(timeout=5000)
        pg.wait_for_timeout(1000)
        return True
    except Exception:
        return False


def current_category(pg):
    return pg.evaluate(
        "()=>{const e=document.querySelector('#automationChangePrimaryCategory .selectedItem span');"
        "return e ? e.textContent.trim() : null;}")


def current_location(pg):
    """Read straight from Angular's scope -- the display span for a saved
    location is commented out in Alamy's own template (confirmed 2026-09-08),
    so nothing in the rendered text ever shows a set value."""
    return pg.evaluate("""()=>{
        const el = document.getElementById('location');
        if(!el || !window.angular) return null;
        const scope = window.angular.element(el).scope();
        return scope && scope.common ? scope.common.LocationAddress : null;
    }""")


def set_category(pg, want):
    try:
        pg.locator("#automationChangePrimaryCategory .selectedItem").first.click(timeout=6000)
        pg.wait_for_timeout(700)
        pg.locator("#automationChangePrimaryCategory li", has_text=want).first.click(timeout=6000)
        pg.wait_for_timeout(1000)
    except Exception:
        return False
    return current_category(pg) == want


def set_location(pg, want):
    try:
        add = pg.locator("span.cyan", has_text="Add location")
        if add.count() > 0:
            add.first.click(timeout=6000)
            pg.wait_for_timeout(600)
        inp = pg.locator("#from")
        inp.click(timeout=6000)
        inp.fill("")
        inp.type(want, delay=40)
        pg.wait_for_timeout(600)
        inp.press("Enter")
        pg.wait_for_timeout(1000)
    except Exception:
        return False
    return current_location(pg) == want


def process(pg, ref, name, want_cat, want_loc, state):
    if not click_tile(pg, ref):
        return "unreachable"
    if not open_optional_tab(pg):
        return "no-optional-tab"

    have_cat = current_category(pg)
    have_loc = current_location(pg)

    need_cat = want_cat and have_cat in (None, "Select")
    need_loc = want_loc and not have_loc

    if not need_cat and not need_loc:
        state["done"].append(ref)
        return "already set"

    changed = False
    if need_cat:
        if not set_category(pg, want_cat):
            return f"category set failed (wanted {want_cat!r})"
        changed = True
    if need_loc:
        if not set_location(pg, want_loc):
            return f"location set failed (wanted {want_loc!r})"
        changed = True

    if not changed:
        state["done"].append(ref)
        return "already set"

    try:
        pg.get_by_role("button", name=re.compile(r"^Save$")).first.click(timeout=8000)
    except Exception:
        return "save button missing"
    pg.wait_for_timeout(3500)

    # Re-verify after Save, not just after the local field edit.
    if want_cat and current_category(pg) != want_cat:
        return "save unconfirmed (category)"
    if want_loc and current_location(pg) != want_loc:
        return "save unconfirmed (location)"

    state["done"].append(ref)
    parts = []
    if need_cat:
        parts.append(f"category={want_cat}")
    if need_loc:
        parts.append(f"location={want_loc}")
    return "ok " + ", ".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="images this run (0 = all)")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()

    categories = json.loads(CATEGORIES.read_text())
    locations = json.loads(LOCATIONS.read_text())
    have_data = set(categories) | set(locations)

    state = load_state()
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
        candidates = [it for it in items if it["name"] in have_data]
        todo = [it for it in candidates if it["ref"] not in done]
        print(f"\n{total} tiles loaded | {len(candidates)} have prepared category/location data "
              f"| {len(candidates) - len(todo)} already done | {len(todo)} to do")

        if a.status:
            pg.close()
            return

        if a.limit:
            todo = todo[:a.limit]
        print(f"processing {len(todo)} this run\n", flush=True)

        by_name = {}
        for it in items:
            by_name.setdefault(it["name"], []).append(it["ref"])

        fails = 0
        for i, it in enumerate(todo, 1):
            name, ref = it["name"], it["ref"]
            want_cat = categories.get(name)
            want_loc = locations.get(name)
            r = process(pg, ref, name, want_cat, want_loc, state)
            ok = r.startswith("ok") or r == "already set"
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
