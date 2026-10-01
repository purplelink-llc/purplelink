#!/usr/bin/env python3
"""Flip Depositphotos files to Editorial=Yes and set their country and city.

Reads a plan {filename: {country, city, page}}, drives the Unfinished list in
the automation Chrome over raw CDP, and verifies every change from a fresh
page load. Never clicks "Submit Selected".

  python3 scripts/depositphotos-editorial.py PLAN.json --page 2 [--limit 3]
"""
import argparse, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_tab import Tab

ROW = """((name)=>{const e=[...document.querySelectorAll('span.itemeditor__name')].find(x=>x.textContent.trim()===name); if(!e) return null;
 let r=e; for(let i=0;i<14&&r;i++){ if(r.querySelector('select._itemeditor__value_is_editorial')) break; r=r.parentElement;} return r})"""
URL = "https://depositphotos.com/files/unfinished/page{}.html"
# The plan uses English names; Depositphotos may list a city under its local name.
ALIASES = {"Cologne": ["Cologne", "Koln"], "Copenhagen": ["Copenhagen", "Kobenhavn"], "Bern": ["Bern", "Berne"],
           "Panama": ["Panama City", "Panama"], "Reykjavik": ["Reykjavik"], "Honolulu": ["Honolulu", "Urban Honolulu"], "Atlanta": ["Atlanta, Georgia"]}


def setsel(t, row, cls, text=None, value=None, startswith=None):
    return t.eval(f"""(()=>{{const r=({ROW})({json.dumps(row)}); if(!r) return 'norow'; const s=r.querySelector('select._itemeditor__value_{cls}'); if(!s) return 'nosel';
      const opts=[...s.options]; let o=null;
      if({json.dumps(value)}!==null) o=opts.find(o=>o.value==={json.dumps(value)});
      if(!o && {json.dumps(text)}!==null) o=opts.find(o=>o.text.trim()==={json.dumps(text)});
      if(!o && {json.dumps(startswith)}!==null){{
        const norm=x=>x.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();
        const names={json.dumps(ALIASES)}[{json.dumps(startswith)}]||[{json.dumps(startswith)}];
        const m=opts.filter(o=>names.some(n=>norm(o.text)===norm(n)||norm(o.text).startsWith(norm(n)+',')));
        if(m.length===1) o=m[0]; else return (m.length?'ambiguous:':'nomatch:')+m.map(o=>o.text).join(' / ')}}
      if(!o) return 'none';
      Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(s,o.value);
      s.dispatchEvent(new Event('input',{{bubbles:true}})); s.dispatchEvent(new Event('change',{{bubbles:true}})); return 'ok:'+o.text.trim()}})()""")


def read(t, row):
    return t.eval(f"""(()=>{{const r=({ROW})({json.dumps(row)}); if(!r) return null; const g=c=>{{const s=r.querySelector('select._itemeditor__value_'+c); return s?(s.options[s.selectedIndex]||{{}}).text.trim():null}};
      return {{editorial:g('is_editorial'), country:g('location_country_code'), city:g('location_city_id')}}}})()""")


def run_page(t, plan, files):
    """Edit `files` (all present on the current page), saving every 20."""
    def save():
        for attempt in range(4):
            try:
                t.eval("window.scrollTo(0,0)")
                time.sleep(1)
                xy = t.eval("(()=>{const b=[...document.querySelectorAll('button,input[type=button],a')].find(b=>(b.innerText||b.value||'').trim()==='Save'&&b.getBoundingClientRect().width>0); if(!b) return null; b.scrollIntoView({block:'center'}); const q=b.getBoundingClientRect(); return [q.x+q.width/2,q.y+q.height/2]})()")
                if xy:
                    t.tap(*xy, 7)
                    return True
            except Exception as e:
                print(f"  save retry ({type(e).__name__})", flush=True)
            time.sleep(3)
        print("  WARNING: save did not go through; edits remain for the next pass", flush=True)
        return False

    def process(f):
        p = plan[f]
        t.eval(f"(({ROW})({json.dumps(f)})||{{scrollIntoView(){{}}}}).scrollIntoView({{block:'center'}})")
        cur = read(t, f) or {}
        r1 = "same" if cur.get("editorial") == "Yes" else setsel(t, f, "is_editorial", text="Yes")
        time.sleep(0.4)
        if cur.get("country") == p["country"]:
            r2 = "same"
        else:
            r2 = setsel(t, f, "location_country_code", text=p["country"])
            last, stable = -1, 0
            for _ in range(40):
                n_opts = t.eval(f"(({ROW})({json.dumps(f)})||{{querySelector(){{return null}}}}).querySelector('select._itemeditor__value_location_city_id')?.options.length") or 0
                stable = stable + 1 if (n_opts == last and n_opts > 5) else 0
                last = n_opts
                if stable >= 3:
                    break
                time.sleep(0.4)
        r3 = "skip"
        if p["city"]:
            for _ in range(3):
                r3 = setsel(t, f, "location_city_id", startswith=p["city"])
                time.sleep(0.6)
                got = (read(t, f) or {}).get("city") or ""
                if r3.startswith("ok") and got:
                    break
                time.sleep(1)
        return r1, r2, r3

    edited = 0
    for n, f in enumerate(files, 1):
        res = None
        for attempt in range(3):
            try:
                res = process(f)
                break
            except Exception as e:
                print(f"  retry {f} ({type(e).__name__})", flush=True)
                time.sleep(2)
        if res is None:
            print(f"[{n}/{len(files)}] {f}: ERROR, will retry next pass", flush=True)
            continue
        good = lambda x: x.startswith("ok") or x in ("same", "skip")
        flag = "" if all(good(x) for x in res) else "   <-- CHECK"
        print(f"[{n}/{len(files)}] {f}: {' | '.join(res)}{flag}", flush=True)
        edited += 1
    save()
    return edited


def names_on_page(t):
    return set(t.eval("[...document.querySelectorAll('span.itemeditor__name')].map(x=>x.textContent.trim())") or [])


def matches(got, want):
    return bool(got) and got["editorial"] == "Yes" and got["country"] == want["country"] and (
        not want["city"] or (got["city"] or "").startswith(want["city"]) or want["city"].lower() in (got["city"] or "").lower())


BATCH = 20


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan"); ap.add_argument("--sweeps", type=int, default=8)
    a = ap.parse_args()
    plan = json.loads(Path(a.plan).read_text())
    t = Tab.new(); t.front()
    # 160 rows per page is ~190k DOM nodes and every call takes seconds; 24 is light.
    t.goto(URL.format(1), settle=8)
    t.eval("""(()=>{const s=[...document.querySelectorAll('select')].find(s=>[...s.options].some(o=>/per page/.test(o.text))); const o=[...s.options].find(o=>/^24 per page/.test(o.text));
      Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(s,o.value); s.dispatchEvent(new Event('change',{bubbles:true}))})()""")
    time.sleep(8)
    tries = {}
    for sweep in range(1, a.sweeps + 1):
        done_this_sweep = 0
        print(f"##### sweep {sweep}", flush=True)
        for pageno in range(1, 31):
            while True:
                # A fresh page each batch: one page that piles up dozens of unsaved
                # edits gets slow and starts dropping rows.
                t.goto(URL.format(pageno), settle=6)
                here = names_on_page(t)
                if not here:
                    break
                todo = [f for f in plan if f in here and tries.get(f, 0) < 3 and not matches(read(t, f), plan[f])]
                print(f"=== page {pageno}: {len(here)} rows, {len(todo)} to change", flush=True)
                if not todo:
                    break
                batch = todo[:BATCH]
                for f in batch:
                    tries[f] = tries.get(f, 0) + 1
                done_this_sweep += run_page(t, plan, batch)
        print(f"##### sweep {sweep} processed {done_this_sweep}", flush=True)
        if done_this_sweep == 0:
            break
    # final audit
    missing, wrong = [], []
    seen = set()
    for pageno in range(1, 31):
        t.goto(URL.format(pageno), settle=8)
        here = names_on_page(t)
        if not here:
            break
        for f in plan:
            if f in here:
                seen.add(f)
                if not matches(read(t, f), plan[f]):
                    wrong.append((f, read(t, f), plan[f]))
    missing = [f for f in plan if f not in seen]
    print(f"AUDIT: {len(seen) - len(wrong)} of {len(plan)} correct | not found on any page: {missing} | wrong: {len(wrong)}", flush=True)
    for w in wrong[:15]:
        print("  WRONG", w, flush=True)
    t.close()


if __name__ == "__main__":
    main()
