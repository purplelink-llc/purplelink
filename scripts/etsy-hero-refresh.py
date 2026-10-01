#!/usr/bin/env python3
"""Apply the refreshed copy and mockups (etsy/<slug>/v2/) to the live hero listings.

etsy-hero-assets.py writes, per hero, a v2/listing.json (place-first title,
13 search-phrase tags, plain description with pixel sizes and a facts block)
and v2/photos/ (living room, office, gallery-sizes, size card, detail). This
script edits the EXISTING listing in the Etsy listing editor over raw CDP;
it never creates a listing, so there is no $0.20 fee and no duplicate risk.

Per listing: find it by its current title in the listings manager, open the
editor, replace title and description, delete the old tags and add the new
13, append the four new mockups (the photographs already there stay, and the
first one stays first), click "Publish changes", then reload the editor and
read title, tags and photo count back. State: etsy/hero-refresh.json.

  python3 scripts/etsy-hero-refresh.py DSC_1326          # one listing
  python3 scripts/etsy-hero-refresh.py --all [--dry-run]

Needs the automation Chrome (port 9340) signed in to Etsy and in the
foreground: Etsy's editor only reacts to real input in the visible tab.
"""
import argparse, json, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_tab import Tab

WS = Path(__file__).resolve().parent.parent / "photo-licensing-workspace"
ETSY = WS / "etsy"
STATE = ETSY / "hero-refresh.json"
LISTED = ETSY / "listed.json"
CDP = "http://127.0.0.1:9340"
HEROES = ["DSC_1326", "DSC_4368", "DSC_8669", "DSC_6629-Edit", "DSC_1601", "DSC_7583",
          "DSC_8714", "DSC_4380", "DSC_3638", "DSC_7559-Pano-Edit"]
NEW_PHOTOS = ["1-living-room.jpg", "2-office.jpg", "3-gallery-sizes.jpg", "4-size-card.jpg"]


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def v2(stem):
    for lj in ETSY.glob("*/v2/listing.json"):
        L = json.loads(lj.read_text())
        if L["stem"] == stem:
            L["_dir"] = lj.parent
            return L
    raise LookupError(f"no v2 kit for {stem}")


def tab():
    pages = [x for x in json.load(urllib.request.urlopen(f"{CDP}/json")) if x["type"] == "page"]
    t = Tab(pages[0]) if pages else Tab.new()
    t.front()
    return t


def listing_id(t, title):
    # The manager's search chokes on commas; search the lead phrase, then keep
    # only the rows whose own text carries the full title.
    lead = title.split(",")[0].replace(" Print", "").strip()[:60]
    t.goto("https://www.etsy.com/your/shops/me/tools/listings?query=" + urllib.parse.quote(lead), 9)
    rows = t.eval("""[...document.querySelectorAll('a')].map(a=>{const m=a.href.match(/listing-editor\\/edit\\/(\\d+)/); if(!m) return null;
        let r=a; for(let i=0;i<8&&r.parentElement;i++){r=r.parentElement; if((r.innerText||'').length>40) break}
        return [m[1], (r.innerText||'').replace(/\\s+/g,' ')]}).filter(Boolean)""") or []
    exact = sorted({i for i, txt in rows if title[:60] in txt})
    return exact or sorted({i for i, _ in rows}) if len({i for i, _ in rows}) == 1 else exact


def set_value(t, selector, text):
    """React-controlled field: native setter plus input/change/blur events."""
    return t.eval(f"""(()=>{{const e=document.querySelector({selector!r}); if(!e) return null;
      const proto=e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;
      e.focus(); Object.getOwnPropertyDescriptor(proto,'value').set.call(e,{json.dumps(text)});
      e.dispatchEvent(new Event('input',{{bubbles:true}})); e.dispatchEvent(new Event('change',{{bubbles:true}})); e.blur(); return e.value}})()""")


def tags_now(t):
    return t.eval("[...document.querySelectorAll('button[aria-label^=\"Delete tag \"]')].map(b=>b.getAttribute('aria-label').slice(11))") or []


def photo_count(t):
    return t.eval("document.querySelectorAll('#field-images img, [class*=media] img').length") or 0


def read_back(t):
    return {"title": t.eval("(document.querySelector('#listing-title-input')||{}).value"),
            "desc": t.eval("(document.querySelector('#listing-description-textarea')||{}).value"),
            "tags": tags_now(t), "photos": photo_count(t)}


def refresh(t, stem, old_title, dry_run):
    L = v2(stem)
    ids = listing_id(t, old_title) or listing_id(t, L["title"])
    if len(ids) != 1:
        raise RuntimeError(f"expected exactly one listing for {old_title[:40]!r}, found {ids}")
    edit = f"https://www.etsy.com/your/shops/me/listing-editor/edit/{ids[0]}"
    t.front(); t.goto(edit, 12)
    before = read_back(t)
    if before["title"] == L["title"] and sorted(before["tags"]) == sorted(L["tags"]):
        return {"id": ids[0], "status": "already current", **{k: before[k] for k in ("photos",)}}
    if dry_run:
        return {"id": ids[0], "status": "dry-run", "old_title": before["title"], "new_title": L["title"], "photos_before": before["photos"]}

    # photos: append the mockups (existing ones stay, first stays first)
    want_photos = before["photos"]
    todo = [L["_dir"] / "photos" / p for p in NEW_PHOTOS if (L["_dir"] / "photos" / p).exists()]
    if todo and before["photos"] <= 5:
        t.set_files("input[type=file]", todo)
        want_photos = before["photos"] + len(todo)
        for _ in range(40):
            time.sleep(2)
            if photo_count(t) >= want_photos:
                break
        time.sleep(3)

    if set_value(t, "#listing-title-input", L["title"]) != L["title"]:
        raise RuntimeError("title did not take")
    if set_value(t, "#listing-description-textarea", L["description"]) != L["description"]:
        raise RuntimeError("description did not take")

    # tags: delete the old ones, then type the new
    for _ in range(30):
        xy = t.eval("""(()=>{const b=document.querySelector('button[aria-label^="Delete tag "]'); if(!b) return null;
            b.scrollIntoView({block:'center'}); const r=b.getBoundingClientRect(); return [r.x+r.width/2,r.y+r.height/2]})()""")
        if not xy:
            break
        t.tap(*xy, 0.6)
    if tags_now(t):
        raise RuntimeError(f"old tags would not delete: {tags_now(t)}")
    # Etsy drops a tag typed too soon after the last one (7 of 13 committed at
    # 0.6 s spacing on 2026-10-01), so pace it and retry only what is missing.
    for attempt in range(5):
        have = set(tags_now(t))
        missing = [x for x in L["tags"] if x not in have]
        if not missing:
            break
        for tag in missing:
            t.eval("document.querySelector('#listing-tags-input').scrollIntoView({block:'center'})")
            t.type("#listing-tags-input", tag); time.sleep(0.9); t.key("Enter"); time.sleep(1.6)
    if sorted(tags_now(t)) != sorted(L["tags"]):
        raise RuntimeError(f"tags did not all commit: {tags_now(t)}")

    # publish and confirm
    t.click_text("Publish changes", tag="button"); time.sleep(4)
    try:
        t.click_topmost("Publish"); time.sleep(8)
    except Exception:
        time.sleep(6)
    # Clicking is not proof: reload the editor and read everything back.
    t.goto(edit, 12)
    after = read_back(t)
    ok = (after["title"] == L["title"] and sorted(after["tags"]) == sorted(L["tags"])
          and after["desc"].strip()[:80] == L["description"].strip()[:80] and after["photos"] >= want_photos)
    return {"id": ids[0], "status": "ok" if ok else "UNCONFIRMED", "title": after["title"],
            "tags": len(after["tags"]), "photos": after["photos"], "photos_before": before["photos"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stems", nargs="*"); ap.add_argument("--all", action="store_true"); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    stems = HEROES if a.all else a.stems
    if not stems:
        ap.error("name a stem or pass --all")
    listed = json.loads(LISTED.read_text())
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    t = tab()
    for stem in stems:
        if state.get(stem, {}).get("status") == "ok" and not a.dry_run:
            log(stem, "already refreshed"); continue
        try:
            r = refresh(t, stem, listed[stem]["title"], a.dry_run)
        except Exception as e:
            r = {"status": f"FAILED {type(e).__name__}: {e}"[:200]}
        log(stem, json.dumps(r, ensure_ascii=False)[:300])
        if not a.dry_run:
            state[stem] = {**r, "at": time.strftime("%Y-%m-%dT%H:%M")}
            STATE.write_text(json.dumps(state, indent=1, ensure_ascii=False) + "\n")
            if r["status"].startswith(("FAILED", "UNCONFIRMED")):
                log("stopping: fix this one before touching the rest"); return 1
            time.sleep(8)      # a human pace between listings
    return 0


if __name__ == "__main__":
    sys.exit(main())
