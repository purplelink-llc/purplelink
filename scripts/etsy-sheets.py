#!/usr/bin/env python3
"""Create Etsy listings for the spreadsheet products, as drafts by default.

Same raw-CDP approach as etsy-list.py (the automation Chrome on port 9340,
signed in to the shop), adapted for a digital template instead of a print:
category "Planner Templates", type Digital, the .xlsx as the digital file, no
print attributes, shop section "Spreadsheets". Listing copy and images come
from kit-src/spreadsheets/listings/<slug>/ (listing.json + images/).

  python3 scripts/etsy-sheets.py glp1-tracker submission-tracker ...   # save drafts
  python3 scripts/etsy-sheets.py --publish glp1-tracker ...            # publish ($0.20 each)

A draft costs nothing; Etsy charges the listing fee on publish. State lives in
kit-src/spreadsheets/listings/etsy-state.json.
"""
import json, re, sys, time
from pathlib import Path
from cdp_tab import Tab

ROOT = Path(__file__).resolve().parent.parent
LIST = ROOT / "kit-src" / "spreadsheets" / "listings"
DIST = ROOT / "kit-src" / "spreadsheets" / "dist"
STATE = LIST / "etsy-state.json"
CREATE = "https://www.etsy.com/your/shops/me/listing-editor/create"
CATEGORY = "Planner Templates"
SECTION = "Spreadsheets"


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def radio(t, name, label_start):
    lid = t.eval(f"""(()=>{{const e=[...document.querySelectorAll('input[type=radio][name="{name}"]')]
        .find(e=>((document.querySelector('label[for="'+e.id+'"]')||{{}}).innerText||'').trim().startsWith({label_start!r}));
        return e?e.id:null}})()""")
    if not lid:
        raise LookupError(f"{name}={label_start}")
    t.click(f'label[for="{lid}"]')


def select(t, sel, text):
    return t.eval(f"""(()=>{{const s=document.querySelector({sel!r}); if(!s) return false;
        const o=[...s.options].find(o=>o.text.trim()==={text!r}); if(!o) return false;
        Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(s,o.value);
        s.dispatchEvent(new Event('input',{{bubbles:true}})); s.dispatchEvent(new Event('change',{{bubbles:true}})); return true}})()""")


def section(t, name):
    have = t.eval("[...(document.querySelector('#shop-section-select')||{options:[]}).options].map(o=>o.text.trim())")
    if name in have:
        select(t, "#shop-section-select", name); return
    select(t, "#shop-section-select", "Add a section"); time.sleep(2)
    t.type("#section", name); time.sleep(1)
    t.click_topmost("Save"); time.sleep(3)


def fill(t, slug):
    L = json.loads((LIST / slug / "listing.json").read_text())
    photos = sorted((LIST / slug / "images").glob("*.png"))[:10]
    t.front()
    t.goto(CREATE, 8)
    t.set_files("input[type=file]", photos); time.sleep(12)
    for _ in range(30):
        if t.eval("!!(document.querySelector('#field-category')&&document.querySelector('#listing-editor_category-search-typeahead'))"):
            break
        time.sleep(1)
    time.sleep(2)
    for attempt in range(4):
        # Once the shop has used the category, Etsy offers it as a shortcut
        # button under the field, which is more reliable than the typeahead.
        xy = t.eval(f"""(()=>{{const f=document.querySelector('#field-category');
            const b=f&&[...f.querySelectorAll('button')].find(b=>b.innerText.replace(/^\\+\\s*/,'').trim().startsWith({CATEGORY!r}));
            if(!b) return null; b.scrollIntoView({{block:'center'}}); const r=b.getBoundingClientRect(); return [r.x+r.width/2,r.y+r.height/2]}})()""")
        if xy:
            t.tap(*xy, 3)
            if t.eval("!!document.querySelector('#category-mixed-listing-type')"):
                break
        t.type("#listing-editor_category-search-typeahead", CATEGORY); time.sleep(3 + 2 * attempt)
        xy = t.eval(f"""(()=>{{const e=[...document.querySelectorAll('[role=option]')].find(e=>e.getBoundingClientRect().width>0&&e.innerText.trim().startsWith({CATEGORY!r}));
            if(!e) return null; e.scrollIntoView({{block:'center'}}); const b=e.getBoundingClientRect(); return [b.x+b.width/2,b.y+b.height/2]}})()""")
        if xy:
            t.tap(*xy, 3)
        if t.eval("!!document.querySelector('#category-mixed-listing-type')"):
            break
    for _ in range(20):
        if t.eval("!!document.querySelector('#category-mixed-listing-type')"):
            break
        time.sleep(1)
    else:
        raise RuntimeError("category did not commit (no item-type picker)")
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
        raise RuntimeError("listing-type picker never appeared")
    t.tap(*xy, 3)
    if t.eval("document.querySelector('#category-mixed-listing-type').innerText.trim()") != "Digital":
        raise RuntimeError("item type did not switch to Digital")
    t.type("#listing-title-input", L["title"]); time.sleep(0.5)
    idx = t.eval("[...document.querySelectorAll('input[type=file]')].findIndex(e=>!e.accept)")
    t.set_files("input[type=file]", [DIST / f for f in L["files"]], index=idx)
    for _ in range(60):
        time.sleep(3)
        seg = re.sub(r"\s+", " ", t.text()); seg = seg[seg.find("Digital files"):][:900]
        if all(f in seg for f in L["files"]) and "%" not in seg:
            break
    else:
        raise RuntimeError("digital files did not finish uploading")
    t.type("#listing-description-textarea", L["description"]); time.sleep(0.5)

    def left():
        txt = t.text()
        if re.search(r"All \d+ used\b", txt):
            return 0
        if re.search(r"\bto go!", txt):
            return 1
        m = re.search(r"(\d+)\s+left\b", txt)
        return int(m.group(1)) if m else None
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
        raise RuntimeError(f"tags did not all commit: {left()} left")
    t.type("#listing-price-input", f"{L['price']:.2f}")
    t.type("#listing-quantity-input", "999")
    radio(t, "whoMade", "I did"); radio(t, "isSupply", "A finished product")
    try:
        radio(t, "whatContent", "Created by me")
    except LookupError:
        pass
    section(t, SECTION)
    got = {"title": t.eval("document.querySelector('#listing-title-input').value"),
           "price": t.eval("document.querySelector('#listing-price-input').value"),
           "type": t.eval("document.querySelector('#category-mixed-listing-type').innerText.trim()"),
           "tags": left() == want}
    if got["title"] != L["title"] or got["type"] != "Digital" or not got["tags"] or float(got["price"]) != L["price"]:
        raise RuntimeError(f"pre-save check failed: {got}")
    return L


def main():
    args = sys.argv[1:]
    publish = "--publish" in args
    slugs = [a for a in args if not a.startswith("--")]
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    t = Tab.new("about:blank"); t.front()
    try:
        for slug in slugs:
            want = "live" if publish else "draft"
            if state.get(slug, {}).get("state") in (want, "live"):
                log("skip", slug, state[slug]["state"]); continue
            log("filling", slug)
            try:
                L = fill(t, slug)
            except Exception as e:   # the editor is occasionally flaky; one clean retry
                log("  retrying after:", e); time.sleep(10)
                L = fill(t, slug)
            if publish:
                t.click_text("Publish", tag="button"); time.sleep(3)
                t.click_topmost("Publish"); time.sleep(10)
                if "/tools/listings" not in t.url():
                    raise RuntimeError(f"publish did not complete: {t.url()}")
            else:
                t.click_text("Save as draft", tag="button"); time.sleep(8)
                if "/tools/listings" not in t.url() and "listing-editor/edit" not in t.url():
                    raise RuntimeError(f"draft save did not complete: {t.url()}")
            state[slug] = {"state": want, "title": L["title"], "url": t.url(), "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
            STATE.write_text(json.dumps(state, indent=1))
            log("  ", want.upper(), L["title"][:70])
            time.sleep(15)
    finally:
        t.close()


if __name__ == "__main__":
    main()
