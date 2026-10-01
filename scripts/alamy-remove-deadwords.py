#!/usr/bin/env python3
"""Remove the 9 tags measured at ZERO buyer demand from every live Alamy image.

WHY THIS EXISTS
alamy-search-terms.json (238 real buyer queries captured 2026-09-10) showed
these exact words -- the most-repeated tags in the whole portfolio -- appear
in ZERO of them: travel (301x), tourism (266x), nature (232x), summer (149x),
outdoor (117x), lifestyle (101x), landmark (99x), wilderness (98x). Alamy's own
endorsed keywording partner warns that over-keywording depresses CTR, and CTR
feeds AlamyRank -- so these are not neutral padding, they occupy tag slots a
real term could use. See scripts/platform-keywords.py's ALAMY_ZERO_DEMAND for
the full writeup; this script performs the removal on ALREADY-LIVE images
(platform-keywords.py only affects what gets embedded on future uploads).

WHAT IT DOES NOT DO
It does not reorder tags, does not add anything, does not touch supertags
beyond removing one if it happens to be dead-demand. Every image keeps its
current tag ORDER; this only deletes exact matches from ALAMY_ZERO_DEMAND.

MECHANISM
Each tag renders as <li id="tagN"><i class="icon-close" onclick="modifyTag(...)">.
Click that icon for any tag whose text matches a dead word, then Save, then
re-read the tag count to confirm the removal actually landed -- clicking Save
is not proof, same discipline as alamy-supertags.py.

USAGE
  scripts/alamy-remove-deadwords.py --limit 40
  scripts/alamy-remove-deadwords.py
  scripts/alamy-remove-deadwords.py --status
"""
import argparse, json, re, subprocess, sys, time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "photo-licensing-workspace" / "analytics" / "alamy-deadwords.json"
URL = "https://www.alamy.com/myupload/Index.aspx"
CDP = "http://127.0.0.1:9340"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE = str(Path.home() / ".photo-automation-chrome")

# Must match scripts/platform-keywords.py's ALAMY_ZERO_DEMAND exactly.
DEAD = {"travel", "tourism", "nature", "summer", "outdoor", "outdoors",
        "lifestyle", "landmark", "wilderness"}

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
         "--no-first-run", "--no-default-browser-check"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(14)


def counts(pg):
    m = re.search(r"(\d+)/50 tags including (\d+)/10 supertags", pg.evaluate(PANEL))
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


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


def dead_tag_indices(pg):
    """Positions of tags whose text is in DEAD, from the currently-selected
    image's tag list.

    modifyTag()'s delete action does NOT remove the <li> -- it calls jQuery
    .toggle() and rebuilds the same id with identical onclick handlers still
    wired to the same tag value (confirmed by reading window.modifyTag's
    source live). toggle() flips visibility, so clicking an already-deleted
    tag's icon-close a second time UN-deletes it. Must skip display:none
    tags here or a stale/duplicate id in the removal loop silently reverts
    a prior removal."""
    return pg.evaluate("""(dead)=>{
        const out=[];
        document.querySelectorAll('ul.sg-w > li').forEach(li=>{
            if (li.style.display === 'none') return;
            const sp = li.querySelector('span');
            if(sp && dead.includes((sp.textContent||'').trim().toLowerCase())) {
                out.push(li.id);
            }
        });
        return out;
    }""", list(DEAD))


def remove_tags(pg, li_ids):
    """Click each tag's icon-close. Removing shifts DOM ids, so re-query and
    click one at a time rather than trusting a stale id list.

    icon-close is display:none until its <li> is hovered (confirmed via
    getComputedStyle: display none, 0x0 rect) -- Playwright's actionability
    check refuses to click a hidden element, which is why every removal on a
    dead-tagged image failed outright while clean images correctly no-op'd.
    Hover the <li> first so the real :hover CSS rule reveals the icon."""
    removed = 0
    for _ in li_ids:
        ids_now = dead_tag_indices(pg)
        if not ids_now:
            break
        lid = ids_now[0]
        try:
            li = pg.locator(f"#{lid}")
            li.scroll_into_view_if_needed(timeout=5000)
            li.hover(timeout=5000)
            pg.wait_for_timeout(200)
            li.locator("i.icon-close").first.click(timeout=5000)
            pg.wait_for_timeout(350)
            removed += 1
        except Exception:
            break
    return removed


def process(pg, ref, state):
    if not click_tile(pg, ref):
        return "unreachable"
    before_total, _ = counts(pg)
    if before_total is None:
        return "no-panel"
    dead_ids = dead_tag_indices(pg)
    if not dead_ids:
        state["done"].append(ref)
        return "clean already"

    n_removed = remove_tags(pg, dead_ids)
    if n_removed == 0:
        return "remove click failed"

    try:
        pg.get_by_role("button", name=re.compile(r"^Save$")).first.click(timeout=8000)
    except Exception:
        return "save button missing"
    pg.wait_for_timeout(4000)

    after_total, _ = counts(pg)
    still_dead = dead_tag_indices(pg)
    if still_dead:
        return f"save unconfirmed ({len(still_dead)} dead tag(s) remain)"
    state["done"].append(ref)
    return f"ok removed {n_removed} ({before_total}->{after_total})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()

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
        # A network hiccup right as the grid starts scrolling can stall
        # load_all_tiles() after only ~200 of ~1144 tiles -- the stall looks
        # identical to a genuinely short list, so it silently reports "0 to
        # do" once every already-done ref happens to be in that partial set.
        # That happened for real on 2026-09-10 (internet dropped mid-run) and
        # would otherwise look like a clean finish while ~176 images were
        # never attempted. Refuse to proceed on an implausibly small load.
        MIN_EXPECTED_TILES = 1000
        if total < MIN_EXPECTED_TILES:
            sys.exit(f"only {total} tiles loaded (expected ~1144) -- grid "
                     f"likely stalled from a network hiccup, not a real "
                     f"finish. Not processing; rerun once the site is stable.")
        items = tile_refs(pg)
        todo = [it for it in items if it["ref"] not in done]
        print(f"\n{total} tiles loaded | {len(items) - len(todo)} already done | {len(todo)} to do")

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
            r = process(pg, ref, state)
            ok = r.startswith("ok") or r == "clean already"
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
