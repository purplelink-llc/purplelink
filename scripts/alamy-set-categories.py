#!/usr/bin/env python3
"""Set Alamy's Primary Category on every live image where it's still unset.

WHY THIS EXISTS
alamy-metadata-v2.csv has no Category column, and Alamy has no bulk-CSV
metadata import -- Primary category can only be set one image at a time,
live, in the Image Manager. Nothing in this pipeline had ever done that.
Spot-checked 2026-09-11: 3 of 10 sampled images had Primary category still
at the unset "Select" placeholder. This is the same *shape* of gap as the
Shutterstock "Needs attention" bug (a listing-quality field silently left
blank), found the same day by the same audit, just via a different
mechanism (manual per-image field vs. an empty bulk-CSV column).

CATEGORY SOURCE OF TRUTH
scripts/platform-keywords.py's alamy_category() -- same function, imported
directly here rather than duplicated, scored from each image's own existing
title/description/keywords in metadata-master.csv. It returns None when
nothing in the existing text confidently matches one of Alamy's 25 fixed
category names; those images are left alone and reported, not guessed at.

MECHANISM
Primary category lives in a custom Angular dropdown, not a native <select>:
  <div id="automationChangePrimaryCategory" ...>
    <span class="selectedItem" toggle-drop-down><span>Sport</span></span>
    <ul class="dropdown-menu"><li id="automationchangeprimarycategoryN">NAME</li>...
Click .selectedItem to open it, click the <li> whose text matches the target
category, then Save -- then re-read Primary category to confirm the click
actually landed, same discipline as alamy-remove-deadwords.py.

USAGE
  scripts/alamy-set-categories.py --limit 40
  scripts/alamy-set-categories.py
  scripts/alamy-set-categories.py --status
"""
import argparse, csv, importlib.util, json, re, subprocess, sys, time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
WS = ROOT / "photo-licensing-workspace"
STATE = WS / "analytics" / "alamy-categories.json"
MASTER = WS / "metadata-master.csv"
URL = "https://www.alamy.com/myupload/Index.aspx"
CDP = "http://127.0.0.1:9340"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE = str(Path.home() / ".photo-automation-chrome")

_pk_spec = importlib.util.spec_from_file_location(
    "platform_keywords", str(Path(__file__).resolve().parent / "platform-keywords.py"))
pk = importlib.util.module_from_spec(_pk_spec)
_pk_spec.loader.exec_module(pk)

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


def category_by_filename():
    """filename -> alamy_category(row) for every row load_rows() would emit,
    i.e. the exact same eligible set platform-keywords.py already uses."""
    return {r["filename"]: pk.alamy_category(r) for r in pk.load_rows()}


def chrome_up():
    import urllib.request
    try:
        urllib.request.urlopen(f"{CDP}/json/version", timeout=4)
        return
    except Exception:
        pass
    subprocess.Popen(
        [CHROME, "--remote-debugging-port=9340", f"--user-data-dir={PROFILE}",
         "--no-first-run", "--no-default-browser-check"],
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


def current_primary_category(pg):
    m = re.search(r"Primary category\s*(.+?)\s*Secondary category", pg.evaluate(PANEL))
    return m.group(1).strip() if m else None


def set_primary_category(pg, target):
    """Open the Primary Category dropdown, click the <li> matching `target`
    exactly, close the dropdown. Does not Save -- caller does that once,
    after every field change, matching the rest of this project's discipline
    of a single Save per image rather than one per field."""
    trigger = pg.locator("#automationChangePrimaryCategory .selectedItem")
    if trigger.count() == 0:
        return False
    trigger.first.click(timeout=5000)
    pg.wait_for_timeout(600)
    li = pg.locator("#automationChangePrimaryCategory ul.dropdown-menu li",
                     has_text=re.compile(rf"^{re.escape(target)}$"))
    if li.count() == 0:
        return False
    li.first.click(timeout=5000)
    pg.wait_for_timeout(500)
    return True


def process(pg, ref, target, state):
    if not click_tile(pg, ref):
        return "unreachable"
    try:
        pg.get_by_text("Optional", exact=True).first.click(timeout=5000)
        pg.wait_for_timeout(1000)
    except Exception:
        return "optional tab not found"

    current = current_primary_category(pg)
    if current is None:
        return "no-panel"
    if current != "Select":
        state["done"].append(ref)
        return f"already set ({current})"

    if not set_primary_category(pg, target):
        return "dropdown click failed"

    try:
        pg.get_by_role("button", name=re.compile(r"^Save$")).first.click(timeout=8000)
    except Exception:
        return "save button missing"
    pg.wait_for_timeout(4000)

    after = current_primary_category(pg)
    if after != target:
        return f"save unconfirmed (reads {after!r})"
    state["done"].append(ref)
    return f"ok set to {target}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()

    state = load_state()
    done = set(state["done"])
    by_name = category_by_filename()
    no_signal = sorted(f for f, c in by_name.items() if c is None)
    if no_signal and a.status:
        print(f"{len(no_signal)} image(s) have no confident category match "
              f"(left for manual review): {', '.join(no_signal[:10])}"
              + (" ..." if len(no_signal) > 10 else ""))

    chrome_up()

    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        pg = ctx.new_page()
        pg.set_viewport_size({"width": 1500, "height": 950})
        print("opening Image Manager (this takes ~2 min to load all tiles)", flush=True)
        total = open_grid(pg)
        MIN_EXPECTED_TILES = 1000
        if total < MIN_EXPECTED_TILES:
            sys.exit(f"only {total} tiles loaded (expected ~1144) -- grid "
                     f"likely stalled from a network hiccup, not a real "
                     f"finish. Not processing; rerun once the site is stable.")
        items = tile_refs(pg)
        # only images we have a confident category for AND haven't done yet
        todo = [it for it in items
                if it["ref"] not in done and by_name.get(it["name"]) is not None]
        skipped_no_signal = [it for it in items if by_name.get(it["name"]) is None]
        print(f"\n{total} tiles loaded | {len(done)} already done | "
              f"{len(skipped_no_signal)} have no confident category | "
              f"{len(todo)} to do")

        if a.status:
            pg.close()
            return

        if a.limit:
            todo = todo[:a.limit]
        print(f"processing {len(todo)} this run\n", flush=True)

        by_ref_dupe = {}
        for it in items:
            by_ref_dupe.setdefault(it["name"], []).append(it["ref"])

        fails = 0
        for i, it in enumerate(todo, 1):
            name, ref = it["name"], it["ref"]
            target = by_name[name]
            r = process(pg, ref, target, state)
            ok = r.startswith("ok") or r.startswith("already set")
            if not ok and r == "unreachable" and any(
                    other in done for other in by_ref_dupe.get(name, []) if other != ref):
                r = "ghost (duplicate of an already-done ref, ignored)"
                ok = True
                state["done"].append(ref)
                done.add(ref)
            print(f"  [{i}/{len(todo)}] {name:34s} {ref:10s} -> {target:28s} {r}", flush=True)
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
