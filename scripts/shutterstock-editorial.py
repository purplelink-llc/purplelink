#!/usr/bin/env python3
"""Convert Shutterstock's "Correction needed" backlog to editorial submissions.

THE PROBLEM
251 images were refused for COMMERCIAL use and offered editorial instead:

    Eligible for Editorial Use: This content cannot be accepted for commercial
    use but it is eligible for editorial use. If interested, please designate
    this content as "Editorial" and provide an editorial caption. Editorial
    captions must include day, month, year, and geographic location
    information and a description.

Same root cause as Dreamstime moving 59 images RF -> Editorial: recognisable
people, property, logos or trademarks that would need a release to license
commercially. Two platforms reached it independently, so it is a property of
the photographs rather than one reviewer's opinion.

THE CAPTION
    <Country> - <Month DD, YYYY>: <existing description>
Country comes from IPTC Country-PrimaryLocationName (written by
getty-country.py) and the date from EXIF DateTimeOriginal. Both are read from
the file, never inferred: an editorial caption asserts when and where a
photograph was taken, and a guessed date or place would be a false factual
claim on a licensed image. Anything missing either field is SKIPPED.

FOUR THINGS THAT MAKE THE LISTING LIE, ALL HIT WHILE BUILDING THIS
1. Cards lazy-render. Reading straight after page load returned 96 of 100, and
   a different count on each run, so each page is scrolled until the count
   stops changing before it is read.
2. Long filenames are TRUNCATED IN THE MIDDLE for display --
   "DSC_8514-Enh...nced-NR.jpeg". The full name is nowhere in the DOM, so it is
   recovered by matching prefix+suffix against disk, and any name that matches
   zero or several files is skipped rather than guessed.
3. Filenames CONTAINING SPACES ("DSC_0155 (1).jpeg") are missed by the obvious
   \\S+ pattern. That alone hid 6 of the 251.
4. Page size is 100, not the 96/98 that naive scraping suggests.

USAGE
  scripts/shutterstock-editorial.py --plan          # enumerate + captions, no writes
  scripts/shutterstock-editorial.py --limit 1       # do one, verify by hand
  scripts/shutterstock-editorial.py                 # work the backlog
"""
import argparse, csv, datetime, json, os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "photo-licensing-workspace" / "analytics" / "shutterstock-editorial.json"
SRC = Path("/Volumes/Extreme SSD/Nikon Photos")
URL = "https://submit.shutterstock.com/portfolio/correction_needed/photo"
CDP = "http://127.0.0.1:9225"

# Every "<id> - <filename>" label. Deliberately loose about the filename:
# tightening it to \S+ silently dropped every name containing a space.
LABEL = re.compile(r"^(\d{8,})\s*-\s*(.+\.(?:jpe?g|png|tiff?))$", re.I)

SCRAPE = """()=>[...document.querySelectorAll('*')].filter(e=>e.children.length===0)
    .map(e=>(e.textContent||'').trim())
    .filter(t=>/^\\d{8,}\\s*-\\s*.+\\.(jpe?g|png|tiff?)$/i.test(t))"""


def load_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {"done": [], "skipped": {}}


def save_state(s):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=1, sort_keys=True))


def resolve(shown, disk):
    """Display name -> real filename. Returns None when it is not unambiguous."""
    if "..." not in shown:
        return shown if shown in disk else None
    pre, suf = shown.split("...", 1)
    hits = [d for d in disk if d.startswith(pre) and d.endswith(suf)]
    return hits[0] if len(hits) == 1 else None


SS_META = ROOT / "photo-licensing-workspace" / "shutterstock-metadata.csv"


def csv_descriptions():
    """{filename: description} as UPLOADED.

    Preferred over whatever the form currently shows. The form is the only
    thing that can be wrong: a lagging editor panel wrote 26 images the
    description of a neighbouring photograph, and re-reading the form would
    faithfully preserve that corruption. This file is what we sent, so it is
    the authority for what each image actually depicts.
    """
    if not SS_META.exists():
        return {}
    out = {}
    for r in csv.DictReader(open(SS_META)):
        d = (r.get("Description") or "").strip()
        if d:
            out[r["Filename"]] = d
    return out


def exif(path):
    """(date, country) from the file. Either may be None."""
    r = subprocess.run(
        ["exiftool", "-s", "-s", "-s", "-DateTimeOriginal",
         "-Country-PrimaryLocationName", str(path)],
        capture_output=True, text=True)
    lines = [l.strip() for l in r.stdout.strip().split("\n") if l.strip()]
    date = country = None
    for l in lines:
        if re.match(r"^\d{4}:\d{2}:\d{2}", l):
            try:
                date = datetime.datetime.strptime(l, "%Y:%m:%d %H:%M:%S")
            except ValueError:
                pass
        else:
            country = l
    return date, country


MONTHISH = (r"(?:January|February|March|April|May|June|July|August|September"
            r"|October|November|December|Spring|Summer|Autumn|Fall|Winter)")
# A leading date header, with or without a place in front of it. Covers both
# "Downtown city sidewalk - July 2022: " and a bare "September 2023: ".
HEADER = re.compile(rf"^(?:[^:]{{3,60}}\s+-\s+)?{MONTHISH}\s+\d{{0,2}},?\s*\d{{4}}:\s*", re.I)


def strip_header(desc):
    """Remove any pre-existing date header(s) from a description.

    The first version only matched "<place> - <Month> <YYYY>:" and missed bare
    "September 2023:" openers, which produced captions carrying two dates --
    15 of the first 180, and some of them CONTRADICTORY:
        "United States - October 03, 2023: September 2023: A young man..."
        "United States - December 27, 2024: Autumn 2024: A couple sit..."
    An editorial caption asserts when a photograph was taken, so a second,
    disagreeing date is a false claim, not just clutter. Applied repeatedly
    because a few descriptions carry both forms stacked.
    """
    out = desc.strip()
    for _ in range(3):
        stripped = HEADER.sub("", out, count=1).strip()
        if stripped == out:
            break
        out = stripped
    return out


def caption(country, date, description):
    return f"{country} - {date.strftime('%B %d, %Y')}: {description}"


def enumerate_backlog(pg):
    """[(shutterstock_id, shown_name)] across every page, fully rendered."""
    out = []
    for page_i in range(1, 8):
        prev, stable = -1, 0
        for _ in range(30):
            pg.evaluate("()=>window.scrollTo(0, document.body.scrollHeight)")
            pg.wait_for_timeout(1300)
            n = len(set(pg.evaluate(SCRAPE)))
            if n == prev:
                stable += 1
                if stable >= 4:
                    break
            else:
                stable = 0
            prev = n
        got = list(dict.fromkeys(pg.evaluate(SCRAPE)))
        print(f"    page {page_i}: {len(got)}", flush=True)
        out.extend(got)
        pg.evaluate("()=>window.scrollTo(0,0)")
        pg.wait_for_timeout(1200)
        nxt = pg.locator("[aria-label='next page']").first
        if not nxt.is_enabled():
            break
        nxt.click()
        pg.wait_for_timeout(9000)
    seen, rows = set(), []
    for t in out:
        m = LABEL.match(t)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            rows.append((m.group(1), m.group(2)))
    return rows


PAGE_SIZE = 100


def load_page(pg, n):
    """Load page n of the backlog, fully rendered. Returns the ids on it.

    This replaces a reload_first_page() that only ever loaded page 1. The todo
    list spans three pages, so once page 1's cards were used up every remaining
    image was unreachable BY CONSTRUCTION -- the run tripped its own
    five-failure guard at 82 of 219 and the failures were an artefact, not a
    site problem.

    Submitting does NOT remove an image from Correction needed (the count stays
    at 251 and the notice persists until re-review), so the pages are stable
    while we work and can simply be walked in order.
    """
    pg.goto(f"{URL}?page={n}", wait_until="domcontentloaded", timeout=90000)
    pg.wait_for_timeout(13000)
    prev, stable = -1, 0
    for _ in range(20):
        pg.evaluate("()=>window.scrollTo(0, document.body.scrollHeight)")
        pg.wait_for_timeout(1200)
        got = len(set(pg.evaluate(SCRAPE)))
        if got == prev:
            stable += 1
            if stable >= 3:
                break
        else:
            stable = 0
        prev = got
    pg.evaluate("()=>window.scrollTo(0,0)")
    pg.wait_for_timeout(1200)
    return set(re.match(r"^(\d{8,})", t).group(1)
               for t in pg.evaluate(SCRAPE) if re.match(r"^(\d{8,})", t))


def open_card(pg, sid):
    """Click 'Make changes' on the card for this id. True once the editor shows."""
    ok = pg.evaluate("""(sid)=>{
        const lab=[...document.querySelectorAll('*')].find(e=>e.children.length===0
            && (e.textContent||'').trim().startsWith(sid+' -'));
        if(!lab) return false;
        let card=lab; for(let i=0;i<8&&card;i++){
            const b=card.querySelector&&[...card.querySelectorAll('button')]
                .find(x=>/Make changes/i.test(x.textContent||''));
            if(b){ b.scrollIntoView({block:'center'}); b.click(); return true; }
            card=card.parentElement;
        }
        return false;}""", sid)
    if not ok:
        return False
    # The editor panel does NOT repaint synchronously. Checking only that a
    # textarea exists reads the PREVIOUS card's description, which gave 26 of
    # 211 images a caption describing a different photograph -- an off-by-one
    # where each got its neighbour's text. The panel prints the asset id, so
    # wait until it names the image we actually asked for.
    for _ in range(20):
        pg.wait_for_timeout(700)
        if pg.locator("textarea[name=description]").count() == 0:
            continue
        shown = pg.evaluate("""()=>{const p=[...document.querySelectorAll('*')]
            .filter(e=>e.children.length===0 && e.getBoundingClientRect().left>900);
            return p.map(e=>(e.textContent||'').trim()).join('|');}""")
        if re.search(rf"\b{re.escape(sid)}\b", shown):
            return True
    return False


def apply_editorial(pg, text):
    """Set Usage=Editorial and replace the description. Returns an error or ''."""
    found = pg.evaluate("""()=>{const b=[...document.querySelectorAll('button.MuiToggleButton-root')]
        .find(x=>(x.textContent||'').trim()==='Editorial');
        if(!b) return false;
        b.scrollIntoView({block:'center'}); b.click(); return true;}""")
    if not found:
        return "no Editorial toggle"
    # MUI flips aria-pressed on the next React render, so reading it inside the
    # same evaluate() always returns the pre-click value and every image looked
    # like "toggle did not take". Verify in a separate round trip.
    pg.wait_for_timeout(1800)
    if pg.evaluate("""()=>{const b=[...document.querySelectorAll('button.MuiToggleButton-root')]
            .find(x=>(x.textContent||'').trim()==='Editorial');
            return b && b.getAttribute('aria-pressed')==='true';}""") is not True:
        return "toggle did not take"
    # Some cards render the description READ-ONLY -- images that already carry
    # an editorial caption come back locked. Playwright's fill() does not fail
    # fast on that: it retried for 30 seconds and then threw, which killed the
    # whole run nine images in. Detect it and skip.
    if pg.evaluate("""()=>{const t=document.querySelector('textarea[name=description]');
            return !t || t.readOnly || t.hasAttribute('readonly');}"""):
        return "description read-only (already editorial)"
    ta = pg.locator("textarea[name=description]").first
    ta.fill("")
    ta.fill(text)
    pg.wait_for_timeout(800)
    if pg.evaluate("()=>document.querySelector('textarea[name=description]').value") != text:
        return "description did not stick"
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true", help="enumerate and build captions only")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--redo", help="JSON list of filenames to re-process even if journalled")
    a = ap.parse_args()

    redo = set(json.loads(Path(a.redo).read_text())) if a.redo else set()
    descs = csv_descriptions()

    if not SRC.is_dir():
        sys.exit(f"source photos not mounted at {SRC}")
    disk = os.listdir(SRC)
    state = load_state()
    done = set(state["done"])

    sys.path.insert(0, str(ROOT / "scripts"))
    import importlib.util
    spec = importlib.util.spec_from_file_location("st", ROOT / "scripts" / "alamy-supertags.py")
    st = importlib.util.module_from_spec(spec); spec.loader.exec_module(st)
    st.chrome_up()

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        pg = b.contexts[0].new_page()
        pg.set_viewport_size({"width": 1500, "height": 950})
        pg.goto(URL, wait_until="domcontentloaded", timeout=90000)
        pg.wait_for_timeout(14000)
        if "signin" in pg.url or "login" in pg.url:
            sys.exit("not signed in to Shutterstock")

        print("enumerating backlog", flush=True)
        rows = enumerate_backlog(pg)
        print(f"\n{len(rows)} entries in Correction needed")

        plan, skipped = [], {}
        for sid, shown in rows:
            fn = resolve(shown, disk)
            if not fn:
                skipped[sid] = f"cannot resolve filename {shown!r}"
                continue
            date, country = exif(SRC / fn)
            if not date or not country:
                miss = "date" if not date else "country"
                skipped[sid] = f"{fn}: no {miss} in EXIF"
                continue
            plan.append({"sid": sid, "file": fn, "date": date, "country": country})

        print(f"  ready   : {len(plan)}")
        print(f"  skipped : {len(skipped)}")
        for k, v in list(skipped.items())[:6]:
            print(f"      {k}  {v}")

        if a.plan:
            for e in plan[:5]:
                d, c = e["date"], e["country"]
                print(f"\n  {e['file']}\n    {c} - {d.strftime('%B %d, %Y')}: <description>")
            pg.close()
            return

        # --redo forces named files back into the queue even though they are
        # journalled, so a bad caption can be corrected in place.
        todo = [e for e in plan if e["sid"] not in done or e["file"] in redo]
        if redo:
            todo = [e for e in todo if e["file"] in redo]
            print(f"  --redo: {len(todo)} of {len(redo)} named files matched")
        if a.limit:
            todo = todo[:a.limit]
        print(f"\nprocessing {len(todo)}\n", flush=True)

        # Walk the pages in order and do the work each one holds, rather than
        # holding one page and hoping every id is on it.
        pages = max(1, -(-len(rows) // PAGE_SIZE))
        by_sid = {e["sid"]: e for e in todo}
        ordered = []
        for pnum in range(1, pages + 1):
            print(f"  loading page {pnum}/{pages}", flush=True)
            ids = load_page(pg, pnum)
            here = [by_sid[s] for s in ids if s in by_sid]
            print(f"    {len(here)} to do on this page", flush=True)
            ordered.append((pnum, here))

        fails = 0
        i = 0
        for pnum, here in ordered:
          if not here:
              continue
          present = load_page(pg, pnum)
          for e in here:
            i += 1
            sid, fn = e["sid"], e["file"]
            # One bad image must never end the run. A read-only description threw
            # out of fill() and killed a 218-image run after nine, losing the
            # unsaved journal with it; state is now written in a finally below.
            try:
              if sid not in present:
                  present = load_page(pg, pnum)
              if not open_card(pg, sid):
                  present = load_page(pg, pnum)
                  if not open_card(pg, sid):
                    skipped[sid] = "card not reachable after reload"
                    fails += 1
                    print(f"  [{i}] {fn:28s} card not reachable", flush=True)
                    if fails >= 5:
                        print("\n5 consecutive failures — stopping."); break
                    continue
              # CSV first, form only as a fallback -- see csv_descriptions().
              desc = descs.get(fn) or pg.evaluate(
                  "()=>document.querySelector('textarea[name=description]').value").strip()
              if len(desc.split()) < 5:
                  skipped[sid] = f"description too short to caption ({desc!r})"
                  print(f"  [{i}] {fn:28s} description too short", flush=True)
                  continue
              # Strip any existing date header before adding ours. 209 of these
              # already carry one, but the "place" is a scene description
              # ("Downtown city sidewalk") with no day -- which is what
              # Shutterstock refused. Re-prefixing would stack two dates.
              text = caption(e["country"], e["date"], strip_header(desc))
              err = apply_editorial(pg, text)
              if err:
                  skipped[sid] = err
                  fails += 1
                  print(f"  [{i}] {fn:28s} {err}", flush=True)
                  if fails >= 5:
                      print("\n5 consecutive failures — stopping."); break
                  continue
              pg.get_by_role("button", name=re.compile(r"^Submit$")).first.click()
              pg.wait_for_timeout(5000)
              state["done"].append(sid)
              fails = 0
              print(f"  [{i}/{len(todo)}] {fn:28s} -> {text[:60]}", flush=True)
              if i % 10 == 0:
                  save_state(state)
            except Exception as ex:
              skipped[sid] = f"{type(ex).__name__}: {str(ex)[:110]}"
              fails += 1
              print(f"  [{i}] {fn:28s} ERROR {type(ex).__name__}", flush=True)
              if fails >= 5:
                  print("\n5 consecutive failures — stopping."); break
          if fails >= 5:
              break

        state["skipped"] = skipped
        save_state(state)
        print(f"\ndone: {len(state['done'])} | skipped: {len(skipped)}")
        pg.close()


if __name__ == "__main__":
    main()
