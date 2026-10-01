#!/usr/bin/env python3
"""Place-first captions on Alamy for the photographs the site promotes.

Alamy is pure search: 315 views a week at 0.63% CTR means the thumbnails
show up and are not clicked. The first words of the caption are what the
search page prints under the thumbnail, so this rewrites them to the literal
place and subject ("Skógafoss waterfall, Iceland: ...") for the ~150
photographs on the hub pages, and records the date so the Monday memo can
read views, zooms and CTR before and after (day 28 is the readout; >25% more
views rolls the format out to the rest, otherwise metadata work stops).

  python3 scripts/alamy-caption-rewrite.py --plan            # write the plan, change nothing
  python3 scripts/alamy-caption-rewrite.py --apply [--limit N]

Drives the Alamy image manager (myupload/Index.aspx) in the automation Chrome
over raw CDP: select the tile by its Alamy ref, set #mtCaption (150 chars
max), click Save, re-read the panel to confirm. Tags and supertags are left
alone. State: photo-licensing-workspace/analytics/alamy-rewrite.json
{date, planned, done: {ref: caption}, skipped}.
"""
import argparse, csv, datetime as dt, json, os, re, sys, time, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parent.parent
_WS = Path(os.environ.get("PL_WORKSPACE") or (ROOT / "photo-licensing-workspace"))
WS = _WS if _WS.exists() else Path("/Volumes/Extreme SSD/Purplelink LLC/photo-licensing-workspace")
STATE = WS / "analytics" / "alamy-rewrite.json"
HUB = ROOT / "site" / "photography" / "hub-data.json"
URL = "https://www.alamy.com/myupload/Index.aspx"
CDP = "http://127.0.0.1:9340"
MAXLEN = 150


def plan():
    """{filename: caption} for every non-people photograph on the hub pages."""
    d = json.loads(HUB.read_text(encoding="utf-8"))
    out = {}
    for c in d["countries"]:
        for p in c["places"] + [{"name": c["name"], "images": c["extra"]}]:
            place = p["name"]
            for im in p["images"]:
                if im["people"]:
                    continue
                head = place if place.lower() in c["name"].lower() else f"{place}, {c['name']}"
                cap = im["caption"]
                # Drop an existing editorial dateline so the place leads.
                cap = re.sub(r"^[^:]{3,60}\s-\s[A-Z][a-z]+ \d{1,2},? \d{4}:\s*", "", cap)
                cap = re.sub(r"^[^:]{3,60}:\s*", lambda m: "" if any(w in m.group(0).lower() for w in (place.lower().split(",")[0], c["name"].lower())) else m.group(0), cap)
                cap = re.sub(rf",\s*{re.escape(c['name'])}\.?$", ".", cap).strip()
                text = f"{head}: {cap if cap else im['title']}"
                if len(text) > MAXLEN:
                    cut = text[:MAXLEN - 1]
                    at = max(cut.rfind(", "), cut.rfind("; "))
                    cut = cut[:at] if at > MAXLEN * 0.6 else cut.rsplit(" ", 1)[0]
                    text = cut.rstrip(",; ") + "."
                out[f"{im['stem']}.jpeg"] = text
    return out


def tab():
    from cdp_tab import Tab
    pages = [x for x in json.load(urllib.request.urlopen(f"{CDP}/json")) if x["type"] == "page"]
    t = Tab(pages[0]) if pages else Tab.new()
    t.front()
    return t


def load_all(t):
    t.goto(URL, settle=20)
    if "login" in t.url().lower():
        sys.exit("Alamy session expired; sign in at " + URL)
    for name in ("OK, got it", "Got it"):
        xy = t.eval(f"(()=>{{const b=[...document.querySelectorAll('button,a')].find(b=>/{name}/i.test(b.innerText||'')&&b.getBoundingClientRect().width>0); if(!b) return null; const r=b.getBoundingClientRect(); return [r.x+r.width/2,r.y+r.height/2]}})()")
        if xy:
            t.tap(*xy, 2)
    last, stall = -1, 0
    for _ in range(80):
        t.eval("(()=>{const c=document.getElementById('cnt-wrapper'); if(c) c.scrollTop=c.scrollHeight})()")
        time.sleep(3)
        n = t.eval("document.querySelectorAll('li[ref]').length")
        stall = stall + 1 if n == last else 0
        last = n
        if stall >= 4:
            break
    refs = t.eval("[...document.querySelectorAll('li[ref]')].map(li=>[li.getAttribute('ref'), ((li.querySelector('.img_cap')||{}).textContent||'').trim()])")
    return {name: ref for ref, name in refs if name}


def panel(t):
    return re.sub(r"\s+", " ", t.eval("(document.getElementById('cxpRHS')||{}).innerText||''"))


def select(t, ref):
    for _ in range(2):
        t.eval(f"(()=>{{const e=document.getElementById('automationImage{ref}'); if(e) e.scrollIntoView({{block:'center'}})}})()")
        time.sleep(0.8)
        xy = t.eval(f"(()=>{{const e=document.getElementById('automationImage{ref}'); if(!e) return null; const b=e.getBoundingClientRect(); return [b.x+b.width/2,b.y+b.height/2]}})()")
        if not xy:
            return False
        t.tap(*xy, 2.5)
        if "1 image selected" in panel(t):
            return True
        xy = t.eval("(()=>{const b=[...document.querySelectorAll('a,button')].find(b=>/Clear selection/i.test(b.innerText||'')&&b.getBoundingClientRect().width>0); if(!b) return null; const r=b.getBoundingClientRect(); return [r.x+r.width/2,r.y+r.height/2]})()")
        if xy:
            t.tap(*xy, 1.5)
    return False


def set_caption(t, text):
    return t.eval(f"""(()=>{{const ta=document.getElementById('mtCaption'); if(!ta) return 'no field';
      const set=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set; ta.focus(); set.call(ta,{json.dumps(text)});
      ta.dispatchEvent(new Event('input',{{bubbles:true}})); ta.dispatchEvent(new Event('change',{{bubbles:true}})); ta.dispatchEvent(new KeyboardEvent('keyup',{{bubbles:true}})); return ta.value}})()""")


def save(t):
    xy = t.eval("(()=>{const b=document.getElementById('submitsearch'); if(!b||b.getBoundingClientRect().width===0) return null; b.scrollIntoView({block:'center'}); const r=b.getBoundingClientRect(); return [r.x+r.width/2,r.y+r.height/2]})()")
    if not xy:
        return False
    t.tap(*xy, 4)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true"); ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    want = plan()
    state = json.loads(STATE.read_text()) if STATE.exists() else {"date": None, "planned": 0, "done": {}, "skipped": {}}
    state["planned"] = len(want)
    if a.plan or not a.apply:
        for k, v in list(want.items())[:12]:
            print(f"{k}: {v}")
        print(f"... {len(want)} captions planned, {len(state['done'])} already done")
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(state, indent=1, ensure_ascii=False) + "\n")
        return 0
    t = tab()
    refs = load_all(t)
    print(f"{len(refs)} tiles on Alamy", flush=True)
    n = 0
    for name, text in want.items():
        if a.limit and n >= a.limit:
            break
        ref = refs.get(name)
        if not ref:
            state["skipped"][name] = "not on Alamy"; continue
        if ref in state["done"]:
            continue
        if not select(t, ref):
            state["skipped"][name] = "could not select"; print(f"  {name}: could not select", flush=True); continue
        old = t.eval("(document.getElementById('mtCaption')||{}).value||''")
        got = set_caption(t, text)
        if got != text:
            state["skipped"][name] = f"field refused: {str(got)[:40]}"; continue
        if not save(t):
            state["skipped"][name] = "no save button"; continue
        # Clicking Save is not proof: reselect and read the field back.
        select(t, ref)
        back = t.eval("(document.getElementById('mtCaption')||{}).value||''")
        if back.strip() == text.strip():
            state["done"][ref] = {"file": name, "caption": text, "previous": old}
            state["date"] = state["date"] or dt.date.today().isoformat()
            n += 1
            print(f"[{n}] {name}: ok", flush=True)
        else:
            state["skipped"][name] = "save unconfirmed"; print(f"  {name}: save unconfirmed", flush=True)
        STATE.write_text(json.dumps(state, indent=1, ensure_ascii=False) + "\n")
    STATE.write_text(json.dumps(state, indent=1, ensure_ascii=False) + "\n")
    print(f"done {len(state['done'])} of {len(want)}; skipped {len(state['skipped'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
