#!/usr/bin/env python3
"""Create Etsy digital-download listings from the kits etsy-build.py makes.

Drives the signed-in automation Chrome (port 9340) through the listing editor
over raw CDP (scripts/cdp_tab.py), one listing at a time and at a human pace:
a brand-new shop that behaves like a bot risks Etsy's fraud checks. The flow
was worked out by hand on the first listing (Matterhorn, 2026-09-24):

  photos -> category "Digital Prints" -> type Digital -> title -> 5 print files
  -> description -> 13 tags -> $ price / qty 999 -> attributes (unframed, no
  mat, 1 piece, orientation, aspect ratios, subject, room) -> I did / finished
  product / created by me -> shop section -> Publish -> confirm $0.20 fee

Each listing is verified before publishing (title, file count, 13 tags, price)
and after (the editor redirects with newly_created=1). State lives in
photo-licensing-workspace/etsy/listed.json so reruns skip what is live.

  python3 scripts/etsy-list.py DSC_1326 DSC_4038 ...
"""
import json, re, sys, time
from pathlib import Path
from PIL import Image
from cdp_tab import Tab

Image.MAX_IMAGE_PIXELS = None
WS = Path(__file__).resolve().parent.parent / "photo-licensing-workspace"
ETSY = WS / "etsy"
STATE = ETSY / "listed.json"
SRC = Path("/Volumes/Extreme SSD/Nikon Photos")
CREATE = "https://www.etsy.com/your/shops/me/listing-editor/create"

SECTION = [("Iceland", "Iceland"), ("Switzerland", "Switzerland"), ("Japan", "Japan"),
           ("Germany", "Germany"), ("Denmark", "Copenhagen"), ("Netherlands", "Amsterdam"),
           ("London", "London"), ("Hawaii", "Hawaii"), ("Arizona", "Arizona Desert"),
           ("Georgia", "Atlanta and Georgia"), ("California", "California"),
           ("British Columbia", "Vancouver")]
RATIO = {"2x3": "2:3", "3x4": "3:4", "4x5": "4:5", "ISO": "5:7 (ISO ratio)", "11x14": "11:14", "2x1": "1:2"}
SUBJECT = {"city": ["Architecture & cityscape", "Travel & transportation", "Geography & locale"],
           "temple": ["Architecture & cityscape", "Travel & transportation", "Geography & locale"],
           "flower": ["Flowers", "Plants & trees", "Landscape & scenery"],
           "forest": ["Landscape & scenery", "Plants & trees", "Geography & locale"],
           "night": ["Stars & celestial", "Landscape & scenery", "Geography & locale"]}
DEFAULT_SUBJECT = ["Landscape & scenery", "Travel & transportation", "Geography & locale"]


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def kit(stem):
    for lj in ETSY.glob("*/listing.json"):
        L = json.loads(lj.read_text())
        if L["stem"] == stem:
            return L
    raise LookupError(stem)


def theme_place(stem):
    # etsy-build.py's SEL table is the source of truth for place and theme
    import importlib.util
    spec = importlib.util.spec_from_file_location("eb", Path(__file__).parent / "etsy-build.py")
    eb = importlib.util.module_from_spec(spec); spec.loader.exec_module(eb)
    name, place, theme, _ = eb.SEL[stem]
    return place, theme


class Editor:
    def __init__(self, t):
        self.t = t

    def radio(self, name, label_start):
        lid = self.t.eval(f"""(()=>{{const e=[...document.querySelectorAll('input[type=radio][name="{name}"]')]
            .find(e=>((document.querySelector('label[for="'+e.id+'"]')||{{}}).innerText||'').trim().startsWith({label_start!r}));
            return e?e.id:null}})()""")
        if not lid:
            raise LookupError(f"{name}={label_start}")
        self.t.click(f'label[for="{lid}"]')

    def select(self, sel, text):
        ok = self.t.eval(f"""(()=>{{const s=document.querySelector({sel!r}); if(!s) return false;
            const o=[...s.options].find(o=>o.text.trim()==={text!r}); if(!o) return false;
            Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(s,o.value);
            s.dispatchEvent(new Event('input',{{bubbles:true}})); s.dispatchEvent(new Event('change',{{bubbles:true}})); return true}})()""")
        if not ok:
            raise LookupError(f"{sel}={text}")

    def multi(self, name, values):
        t = self.t
        fid = t.eval(f"""(()=>{{const l=[...document.querySelectorAll('label[for^="typeahead-input"]')]
            .find(l=>l.innerText.trim().startsWith({name!r})); return l?l.getAttribute('for'):null}})()""")
        if not fid:
            log("   no attribute", name); return
        t.click(f"#{fid}"); time.sleep(2)
        for v in values:
            lid = None
            for _ in range(3):
                lid = t.eval(f"""(()=>{{const l=[...document.getElementById({fid!r}).closest('.wt-menu').querySelectorAll('label')]
                    .find(l=>l.textContent.trim()==={v!r}); return l?l.getAttribute('for'):null}})()""")
                if not lid or t.eval(f"document.getElementById({lid!r}).checked"):
                    break
                if t.eval(f"document.getElementById({fid!r}).closest('.wt-menu').querySelector('[data-wt-menu-trigger]').getAttribute('aria-expanded')")!="true":
                    t.click(f"#{fid}"); time.sleep(1.5)
                t.click(f'label[for="{lid}"]'); time.sleep(1)
            if not lid or not t.eval(f"document.getElementById({lid!r}).checked"):
                log(f"   could not set {name}={v}")
        t.key("Escape"); time.sleep(1)

    def section(self, name):
        t = self.t
        have = t.eval("[...document.querySelector('#shop-section-select').options].map(o=>o.text.trim())")
        if name in have:
            self.select("#shop-section-select", name); return
        self.select("#shop-section-select", "Add a section"); time.sleep(2)
        t.type("#section", name); time.sleep(1)
        t.click_topmost("Save"); time.sleep(3)
        cur = t.eval("(()=>{const s=document.querySelector('#shop-section-select');return s.options[s.selectedIndex].text.trim()})()")
        if cur != name:
            raise RuntimeError(f"section {name} not selected ({cur})")


def create(t, stem):
    L = kit(stem)
    place, theme = theme_place(stem)
    ed = Editor(t)
    d = Path(L["dir"])
    w, h = Image.open(SRC / f"{stem}.jpeg").size
    orient = "Horizontal" if w >= h else "Vertical"

    t.front()
    t.goto(CREATE, 8)
    t.set_files("input[type=file]", [d / "photos" / p for p in L["photos"]]); time.sleep(12)
    # category + digital
    # Wait for the category field to render: on a cold first load it can lag
    # behind the photo uploads, which is what failed the first listing of a run.
    for _ in range(30):
        if t.eval("!!(document.querySelector('#field-category')&&document.querySelector('#listing-editor_category-search-typeahead'))"):
            break
        time.sleep(1)
    time.sleep(2)
    # Committed = the field no longer offers "+ Digital Prints" as a suggestion.
    committed = lambda: bool(t.eval("!/\\+\\s*Digital Prints/.test(document.querySelector('#field-category').innerText)"))
    for attempt in range(4):
        if committed():
            break
        # Once a shop has used a category, Etsy offers it as a "Your top
        # categories" shortcut under the field -- more reliable than the
        # typeahead, but the tap occasionally lands before the button is
        # truly interactive (2026-09-25: it recorded no error and did
        # nothing), so this is verified and retried, not just tapped once.
        xy = t.eval("""(()=>{const f=document.querySelector('#field-category');
            const b=[...f.querySelectorAll('button')].find(b=>/^\\+?\\s*Digital Prints/.test(b.innerText.trim()));
            if(!b) return null; b.scrollIntoView({block:'center'}); const r=b.getBoundingClientRect(); return [r.x+r.width/2,r.y+r.height/2]})()""")
        if xy:
            t.tap(*xy, 3)
            if committed():
                break
        t.type("#listing-editor_category-search-typeahead", "Digital prints"); time.sleep(3 + 2 * attempt)
        xy = t.eval("""(()=>{const e=[...document.querySelectorAll('[role=option],li')].find(e=>e.getBoundingClientRect().width>0&&/^Digital Prints/.test(e.innerText.trim()));
            if(!e) return null; e.scrollIntoView({block:'center'}); const b=e.getBoundingClientRect(); return [b.x+b.width/2,b.y+b.height/2]})()""")
        if xy:
            t.tap(*xy, 3)
    if not committed():
        raise RuntimeError("category never committed to Digital Prints")
    for _ in range(20):
        if t.eval("!!document.querySelector('#category-mixed-listing-type')"):
            break
        time.sleep(1)
    # The picker only renders in the foreground tab (Chrome pauses rAF in
    # background tabs), and any other tab opened on this Chrome steals focus.
    xy = None
    for _ in range(3):
        t.front(); time.sleep(0.5)
        t.click("#category-mixed-listing-type"); time.sleep(1.5)
        xy = t.eval("""(()=>{const e=[...document.querySelectorAll('#field-listingType li')].find(e=>e.innerText.trim()==='Digital');
            if(!e) return null; const b=e.getBoundingClientRect(); return [b.x+b.width/2,b.y+b.height/2]})()""")
        if xy:
            break
        t.key("Escape")
    if not xy:
        raise RuntimeError("listing-type picker (Physical/Digital) never appeared")
    t.tap(*xy, 3)
    if t.eval("document.querySelector('#category-mixed-listing-type').innerText.trim()") != "Digital":
        raise RuntimeError("item type did not switch to Digital")
    # text
    t.type("#listing-title-input", L["title"]); time.sleep(0.5)
    idx = t.eval("[...document.querySelectorAll('input[type=file]')].findIndex(e=>!e.accept)")
    t.set_files("input[type=file]", [d / "files" / f for f in L["files"]], index=idx)
    for _ in range(60):
        time.sleep(3)
        seg = re.sub(r"\s+", " ", t.text()); seg = seg[seg.find("Digital files"):][:900]
        if all(f in seg for f in L["files"]) and "%" not in seg:
            break
    else:
        raise RuntimeError("digital files did not finish uploading")
    t.type("#listing-description-textarea", L["description"]); time.sleep(0.5)
    # The counter next to the tags input is the ground truth for how many
    # actually committed -- typing+Enter can silently drop one (2026-09-25:
    # a full pass left "13 left", i.e. none committed, no error raised), so
    # this checks that counter and retries only what's missing, up to twice.
    # Etsy's copy changes near the end: "2 left" -> "1 to go!" -> "All 13
    # used" (2026-09-26: the old "(\d+) left"-only regex never matched the
    # last two states, so left() always returned None and every listing in
    # a 28-item batch failed right at the finish line).
    def left():
        txt = t.text()
        if re.search(r"All \d+ used\b", txt):
            return 0
        if re.search(r"\bto go!", txt):
            return 1
        m = re.search(r"(\d+)\s+left\b", txt)
        return int(m.group(1)) if m else None
    # Some kits carry fewer than 13 tags, so "done" is 13 - len(tags), not 0.
    # Retries re-send the tags actually absent from the field, not the tail:
    # a dropped tag can be any of them, and re-sending a present one is a no-op.
    want = 13 - len(L["tags"])
    have = lambda: t.eval("""(()=>{let e=document.querySelector('#listing-tags-input');
        while(e && !/Add up to 13 tags/.test(e.innerText||'')) e=e.parentElement;
        return e ? e.innerText.split('\\n').map(s=>s.trim()) : []})()""") or []
    todo = list(L["tags"])
    for _ in range(3):
        for tag in todo:
            t.type("#listing-tags-input", tag); t.key("Enter"); time.sleep(0.5)
        if left() == want:
            break
        present = set(have())
        todo = [x for x in L["tags"] if x not in present]
    if left() != want:
        raise RuntimeError(f"tags did not all commit: {left()} left, expected {want}")
    t.type("#listing-price-input", f"{L['price']:.2f}")
    t.type("#listing-quantity-input", "999")
    # attributes
    t.click_text("Show all attributes", tag="button"); time.sleep(2)
    ed.radio("attribute-767", "No"); ed.radio("attribute-346", "Unframed")
    ed.select("#attribute-756", "1"); ed.select("#attribute-479", orient)
    ratios = [RATIO[f.rsplit("_", 1)[1][:-4]] for f in L["files"] if f.rsplit("_", 1)[1][:-4] in RATIO]
    if ratios:
        ed.multi("Aspect ratio", ratios[:5])
    ed.multi("Subject", SUBJECT.get(theme, DEFAULT_SUBJECT))
    ed.multi("Room", ["Living room", "Bedroom", "Office"])
    ed.radio("whoMade", "I did"); ed.radio("isSupply", "A finished product"); ed.radio("whatContent", "Created by me")
    ed.section(next(s for k, s in SECTION if k in place) if place else "Nature")
    # verify before publishing
    got = {"title": t.eval("document.querySelector('#listing-title-input').value"),
           "price": t.eval("document.querySelector('#listing-price-input').value"),
           "tags": left() == want,
           "type": t.eval("document.querySelector('#category-mixed-listing-type').innerText.trim()")}
    if got["title"] != L["title"] or got["type"] != "Digital" or not got["tags"] or float(got["price"]) != L["price"]:
        raise RuntimeError(f"pre-publish check failed: {got}")
    # publish + confirm fee dialog
    t.click_text("Publish", tag="button"); time.sleep(3)
    t.click_topmost("Publish"); time.sleep(10)
    # success lands on the listings manager, with or without newly_created=1
    if "/tools/listings" not in t.url():
        raise RuntimeError(f"publish did not complete: {t.url()}")
    return L["title"]


FAILED = ETSY / "failed.json"


def main():
    stems = sys.argv[1:]
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    failed = json.loads(FAILED.read_text()) if FAILED.exists() else {}
    t = Tab.new("about:blank"); t.front()
    try:
        for s in stems:
            # A dropped websocket (seen 2026-09-25: one "Connection reset by
            # peer" cascaded into "Broken pipe" for every remaining stem,
            # because the same dead Tab object kept getting reused) is
            # recovered by opening a fresh tab rather than losing the batch.
            try:
                t.eval("1")
            except Exception:
                log("  tab connection dead, reopening")
                try:
                    t.close()
                except Exception:
                    pass
                t = Tab.new("about:blank"); t.front()
            if s in state:
                log("skip (live)", s); continue
            log("listing", s)
            try:
                try:
                    title = create(t, s)
                except Exception as e:      # the editor is occasionally flaky; one clean retry
                    log("  retrying after:", e)
                    time.sleep(15)
                    want = kit(s)["title"]
                    t.goto("https://www.etsy.com/your/shops/me/tools/listings", 8)
                    if want[:40] in t.text():   # it did publish before failing: don't duplicate
                        title = want
                    else:
                        title = create(t, s)
            except Exception as e:
                # One bad listing must not cost the rest of the batch: log it
                # and move on. 2026-09-25: an uncaught retry failure here
                # killed the whole run and stranded 27 unlisted photos for
                # hours before anyone noticed.
                log("  FAILED, skipping:", s, "--", e)
                failed[s] = str(e)
                FAILED.write_text(json.dumps(failed, indent=1))
                try:
                    t.goto("about:blank", 2)   # clear any stuck editor state before the next stem
                except Exception:
                    pass
                continue
            failed.pop(s, None)
            FAILED.write_text(json.dumps(failed, indent=1))
            state[s] = {"title": title, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
            STATE.write_text(json.dumps(state, indent=1))
            log("  LIVE", title[:70])
            time.sleep(20)   # human pace between listings
    finally:
        t.close()
    if failed:
        log(f"{len(failed)} failed (see {FAILED}): {list(failed)}")


if __name__ == "__main__":
    main()
