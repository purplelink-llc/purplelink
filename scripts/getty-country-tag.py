#!/usr/bin/env python3
"""Build a one-click page for tagging country of shoot, and read the result back.

WHY THIS EXISTS
Getty refuses to submit an image with a blank country_of_shoot (its API says
literally `country_of_shoot: ["can't be blank"]`), and 84 pending images across
the batches have no country in EXIF, keywords, or caption. Guessing is not an
option -- it is a factual claim about where a photo was taken -- so the only
path is asking Ben. The earlier free-text page made him type a country per
image, which is both slow and typo-prone.

TWO THINGS MAKE THIS FAST
1. The country list is not free text. Ben has already labelled ~1,040 images
   across alamy-locations.json, getty-country-map.json and the Getty metadata
   CSVs, and those resolve to exactly TEN countries. So every image gets ten
   buttons, not a text box.
2. Trips cluster in time. For each unlabelled image this finds the nearest
   labelled image BY CAPTURE DATE and pre-selects its country, showing how many
   days apart they were. Same-day evidence is strong; a week apart is a hint and
   is labelled as such. Ben confirms rather than recalls.

Nothing here writes a country on its own. A pre-selection is a suggestion with
its evidence shown; the CSV only contains what he actually clicked.

USAGE
  scripts/getty-country-tag.py --batch 67091094        # just that batch
  scripts/getty-country-tag.py --all-pending           # every blocked image
  scripts/getty-country-tag.py --apply countries.csv   # write answers back
"""
import argparse, base64, csv, json, subprocess, sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WS = ROOT / "photo-licensing-workspace"
SRC = Path("/Volumes/Extreme SSD/Nikon Photos")
OUT = WS / "getty-country-tag.html"
ANSWERS = WS / "getty-country-answers.csv"
CDP = "http://127.0.0.1:9340"
API = "https://esp.gettyimages.com/api/submission/v1/submission_batches/{}/contributions"


def _country_of(v):
    """Accept both shapes this project stores.

    getty-country.py writes {"country","code","how"} dicts; answers merged by
    apply_answers() used to land as bare strings. An earlier version of this
    function filtered on isinstance(v, str), which silently DISCARDED all 501
    dict entries -- the tagger was running on alamy-locations.json alone and
    ignoring most of the labels Ben had already given. The map is normalised to
    dicts now, but read both so an older file still works.
    """
    if isinstance(v, dict):
        v = v.get("country", "")
    return v.strip() if isinstance(v, str) else ""


def known_labels():
    """filename -> country, from every source Ben has already labelled."""
    out = {}
    for name in ("alamy-locations.json", "getty-country-map.json"):
        p = WS / name
        if not p.exists():
            continue
        for k, v in json.loads(p.read_text()).items():
            c = _country_of(v)
            if c:
                out[k] = c
    for name in ("getty-stranded-metadata-v2.csv", "getty-country-fix.csv"):
        p = WS / name
        if not p.exists():
            continue
        for r in csv.DictReader(open(p)):
            f = r.get("file name") or r.get("filename")
            c = (r.get("country") or "").strip()
            if f and c:
                out[f] = c
    return out


def country_vocab(labels):
    """The countries Ben actually shoots in, most-used first."""
    return [c for c, _ in Counter(labels.values()).most_common()]


def capture_dates(names):
    """One exiftool pass; per-file calls cost minutes on a set this size."""
    paths = [str(SRC / n) for n in names if (SRC / n).exists()]
    if not paths:
        return {}
    out = subprocess.run(["exiftool", "-j", "-FileName", "-DateTimeOriginal"] + paths,
                         capture_output=True, text=True).stdout
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return {}
    res = {}
    for d in data:
        raw = (d.get("DateTimeOriginal") or "")[:10].replace(":", "-")
        try:
            res[Path(d["FileName"]).name] = datetime.strptime(raw, "%Y-%m-%d").date()
        except (ValueError, KeyError):
            pass
    return res


def suggest(todo, labels, dates):
    """Nearest labelled image by capture date, with the gap in days.

    A 0-day gap means the same shooting day as an image whose country Ben
    already confirmed, which is about as strong as inference gets here. The gap
    is surfaced in the UI so a 200-day "nearest" is visibly not evidence.
    """
    labelled = [(f, dates[f], c) for f, c in labels.items()
                if f in dates and c]
    out = {}
    for f in todo:
        d = dates.get(f)
        if not d or not labelled:
            continue
        best = min(labelled, key=lambda x: abs((x[1] - d).days))
        gap = abs((best[1] - d).days)
        out[f] = {"country": best[2], "gap": gap, "via": best[0]}
    return out


def thumb_b64(f):
    """Embedded JPEG thumbnail so the page is one self-contained file."""
    try:
        r = subprocess.run(["exiftool", "-b", "-ThumbnailImage", str(SRC / f)],
                           capture_output=True)
        if r.stdout:
            return base64.b64encode(r.stdout).decode()
    except Exception:
        pass
    return ""


def pending_missing_country(batches):
    """Ask ESP which pending images still have no country."""
    from playwright.sync_api import sync_playwright
    todo = []
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        pg = b.contexts[0].new_page()
        pg.goto("https://esp.gettyimages.com/contribute/batches",
                wait_until="domcontentloaded", timeout=60_000)
        pg.wait_for_timeout(8000)
        for bid in batches:
            r = pg.evaluate("""async (u) => {
                const r = await fetch(u, {credentials:'include',
                                          headers:{'Accept':'application/json'}});
                return r.ok ? await r.json() : {error:r.status};
            }""", API.format(bid))
            if isinstance(r, dict) and r.get("error"):
                print(f"  batch {bid}: HTTP {r['error']} (session expired?)", file=sys.stderr)
                continue
            items = r if isinstance(r, list) else r.get("contributions", r.get("data", []))
            for i in items:
                if i.get("status") == "pending" and not i.get("country_of_shoot"):
                    n = i.get("file_name") or i.get("filename")
                    if n:
                        todo.append(n)
        pg.close()
    return sorted(set(todo))


def build_page(todo, vocab, sugg, dates, titles):
    cards = []
    for f in sorted(todo, key=lambda x: (dates.get(x) or datetime.min.date(), x)):
        s = sugg.get(f)
        b64 = thumb_b64(f)
        img = (f'<img src="data:image/jpeg;base64,{b64}">' if b64
               else '<div class="nothumb">no thumbnail</div>')
        if s:
            strength = ("same day" if s["gap"] == 0 else
                        f"{s['gap']}d apart" if s["gap"] <= 14 else
                        f"{s['gap']}d apart — weak")
            hint = (f'<div class="hint">nearest labelled shot: <b>{s["country"]}</b> '
                    f'<span class="gap">({strength}, via {s["via"]})</span></div>')
            pre = s["country"] if s["gap"] <= 14 else ""
        else:
            hint = '<div class="hint">no dated neighbour to compare against</div>'
            pre = ""
        btns = "".join(
            f'<button class="cb{" sel" if c == pre else ""}" data-f="{f}" data-c="{c}">{c}</button>'
            for c in vocab)
        cards.append(
            f'<div class="c" data-file="{f}">{img}'
            f'<div class="m"><div class="fn">{f}</div>'
            f'<div class="dt">{dates.get(f, "date unknown")}</div>'
            f'<div class="ti">{titles.get(f, "")}</div>{hint}'
            f'<div class="btns">{btns}'
            f'<button class="cb none" data-f="{f}" data-c="">can\'t place it</button>'
            f'</div></div></div>')

    return """<!doctype html><meta charset="utf-8"><title>Country of shoot</title>
<style>
:root{color-scheme:dark}
body{font:14px system-ui,-apple-system,sans-serif;margin:0;padding:22px;background:#0f1115;color:#e6e9ef}
h1{font-size:20px;margin:0 0 4px} .sub{color:#8b93a7;font-size:13px;margin-bottom:16px;max-width:70ch;line-height:1.5}
#bar{position:sticky;top:0;background:#0f1115;padding:12px 0;border-bottom:1px solid #262b36;
  margin-bottom:14px;z-index:9;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
#count{color:#8b93a7;font-size:13px}
.go{background:#7c5cff;color:#fff;border:0;border-radius:8px;padding:11px 20px;font-size:14px;
  font-weight:600;cursor:pointer}
.accept{background:#2a2f3a;color:#e6e9ef;border:1px solid #3a4150;border-radius:8px;padding:11px 16px;cursor:pointer}
.c{display:flex;gap:14px;background:#171a21;border:1px solid #262b36;border-radius:12px;
  padding:12px;margin-bottom:10px}
.c.done{border-color:#3fb950}
img{width:168px;height:112px;object-fit:cover;border-radius:8px;background:#000;flex:none}
.nothumb{width:168px;height:112px;display:grid;place-items:center;background:#000;color:#555;
  border-radius:8px;font-size:11px;flex:none}
.m{flex:1;min-width:0}
.fn{font-family:ui-monospace,monospace;font-size:11.5px;color:#8ab4f8;word-break:break-all}
.dt{color:#8b93a7;font-size:11.5px;margin-top:2px}
.ti{margin:4px 0 5px;font-size:13.5px}
.hint{font-size:12px;color:#8b93a7;margin-bottom:8px} .hint b{color:#e6e9ef}
.gap{color:#6b7280}
.btns{display:flex;gap:6px;flex-wrap:wrap}
.cb{background:#1f2430;border:1px solid #333a49;color:#c9d1d9;border-radius:999px;
  padding:6px 12px;font-size:12.5px;cursor:pointer}
.cb:hover{border-color:#7c5cff}
.cb.sel{background:#7c5cff;border-color:#7c5cff;color:#fff;font-weight:600}
.cb.none{color:#8b93a7} .cb.none.sel{background:#4b5563;border-color:#4b5563;color:#fff}
textarea{width:100%;height:170px;background:#000;color:#7ee787;border:1px solid #262b36;
  border-radius:10px;padding:12px;font-family:ui-monospace,monospace;font-size:12px;margin-top:14px}
</style>
<h1>Country of shoot</h1>
<div class="sub">Getty won't accept a submission without this field. The buttons are the ten
countries you've already labelled images in. Where a shot was taken near a trip you've already
labelled, that country is pre-selected and the evidence is shown &mdash; confirm or correct it.
When you're done, hit <b>Copy CSV</b> and paste the result back to Claude.</div>
<div id="bar">
  <button class="go" onclick="go()">Copy CSV</button>
  <button class="accept" onclick="acceptAll()">Accept all pre-selected</button>
  <span id="count"></span>
</div>
""" + "".join(cards) + """
<textarea id="out" placeholder="CSV appears here after you hit Copy CSV"></textarea>
<script>
const picks = {};
document.querySelectorAll('.cb.sel').forEach(b => picks[b.dataset.f] = b.dataset.c);
function paint(){
  document.querySelectorAll('.c').forEach(c => {
    c.classList.toggle('done', picks[c.dataset.file] !== undefined);
  });
  const total = document.querySelectorAll('.c').length;
  const done = Object.keys(picks).length;
  document.getElementById('count').textContent = done + ' of ' + total + ' tagged';
}
document.addEventListener('click', e => {
  const b = e.target.closest('.cb');
  if(!b) return;
  const f = b.dataset.f;
  document.querySelectorAll('.cb[data-f="'+CSS.escape(f)+'"]').forEach(x => x.classList.remove('sel'));
  b.classList.add('sel');
  picks[f] = b.dataset.c;
  paint();
});
function acceptAll(){ paint(); }
function go(){
  const rows = [['file name','country']];
  Object.entries(picks).forEach(([f,c]) => { if(c) rows.push([f,c]); });
  const csv = rows.map(r => r.map(x => /[",]/.test(x) ? '"'+x.replace(/"/g,'""')+'"' : x).join(',')).join('\\n');
  document.getElementById('out').value = csv;
  if(navigator.clipboard) navigator.clipboard.writeText(csv);
}
paint();
</script>
"""


def apply_answers(path):
    """Fold answers into getty-country-map.json so nothing has to be asked twice."""
    rows = list(csv.DictReader(open(path)))
    p = WS / "getty-country-map.json"
    cmap = json.loads(p.read_text()) if p.exists() else {}
    added = 0
    for r in rows:
        f = (r.get("file name") or r.get("filename") or "").strip()
        c = (r.get("country") or "").strip()
        if f and c and cmap.get(f) != c:
            cmap[f] = c
            added += 1
    p.write_text(json.dumps(cmap, indent=1, sort_keys=True))
    print(f"merged {added} answer(s) into {p}")
    print("next: apply them to the ESP batch, then submit")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", action="append", default=[],
                    help="ESP batch id (repeatable)")
    ap.add_argument("--all-pending", action="store_true",
                    help="every pending image missing a country, across known batches")
    ap.add_argument("--files", help="CSV/TXT of filenames instead of asking ESP")
    ap.add_argument("--apply", help="read a filled-in answers CSV back in")
    a = ap.parse_args()

    if a.apply:
        apply_answers(a.apply)
        return

    labels = known_labels()
    vocab = country_vocab(labels)
    print(f"{len(labels)} already-labelled images -> {len(vocab)} countries: {', '.join(vocab)}")

    if a.files:
        p = Path(a.files)
        if p.suffix.lower() == ".csv":
            todo = [(r.get("file name") or r.get("filename") or "").strip()
                    for r in csv.DictReader(open(p))]
        else:
            todo = [l.strip() for l in p.read_text().splitlines()]
        todo = [t for t in todo if t]
    else:
        batches = a.batch
        if a.all_pending or not batches:
            plan = WS / "getty-batch-plan.json"
            known = set(json.loads(plan.read_text()).values()) if plan.exists() else set()
            batches = sorted(known | {"67091094", "66928700", "66508252", "66549899",
                                      "66545323", "66168987", "66167467", "66167070",
                                      "66161991", "66157501", "66154962"})
        print(f"asking ESP about {len(batches)} batch(es)...")
        todo = pending_missing_country(batches)

    todo = [t for t in todo if (SRC / t).exists()]
    if not todo:
        print("nothing is missing a country — nothing to tag")
        return
    print(f"{len(todo)} image(s) need a country")

    master = {r["filename"]: r for r in csv.DictReader(open(WS / "metadata-master.csv"))}
    titles = {f: master.get(f, {}).get("title", "") for f in todo}
    dates = capture_dates(list(todo) + list(labels))
    sugg = suggest(todo, labels, dates)
    strong = sum(1 for s in sugg.values() if s["gap"] == 0)
    near = sum(1 for s in sugg.values() if 0 < s["gap"] <= 14)
    print(f"  pre-selected from a same-day labelled shot: {strong}")
    print(f"  pre-selected from within two weeks:         {near}")
    print(f"  no usable neighbour:                        {len(todo) - strong - near}")

    OUT.write_text(build_page(todo, vocab, sugg, dates, titles))
    print(f"\nwrote {OUT}  ({OUT.stat().st_size/1024:.0f}KB)")
    print(f"open it, tag, Copy CSV, then: scripts/getty-country-tag.py --apply <file>")


if __name__ == "__main__":
    main()
