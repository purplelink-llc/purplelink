#!/usr/bin/env python3
"""Build a contact sheet for curating an art-consultant submission package.

WHY THIS EXISTS
Art consultants (hospitality, healthcare, corporate) are the highest-margin
channel available to this library: they license reproduction rights across a
whole property and pay 50% (NINE dot ARTS) to 60% (Indiewalls) of retail with
zero production cost on our side. Their submission forms want a small curated
set -- Kalisher asks for three images and a price list -- not 850 files.

WHAT DECOR DEMAND ACTUALLY LOOKS LIKE (and why the filters below exist)
Healthcare art buying follows evidence-based-design research, which is unusually
specific and is the reason the negative list is so blunt. A University of
Michigan Medical Center study recommended texturally complex NATURE views and
recommended AGAINST urban views, architecture, portraits, still life, sports and
abstract work; patient-preference studies put landscape top at 28%, with lake
sunset 76% / rocky river 66% / autumn waterfall 66%.
  https://www.healthdesign.org/sites/default/files/Hathorn_Nanda_Mar08.pdf
Hospitality and corporate are a different buyer that DOES want architecture and
cityscapes, with a strong documented preference for imagery local to the venue.

So this splits candidates into the two buckets that map to those two buyers, and
excludes what the research says has near-zero decor demand: the Sonoran desert
work (arid and spiky reads as low-restorative), macro insects, sports action,
and event/people work.

WHAT IT DOES NOT DO
It does not choose the final set. Calmness, palette and open foreground are
visual judgements that metadata cannot make -- the filters here only narrow ~750
images to a reviewable shortlist. Pick the final 25 by eye in the contact sheet.

A NOTE ON THE SPORTS WORK
College sports action is excluded on decor demand, but note separately that
reselling it as decor likely needs school/conference trademark clearance. Do not
put it in a consultant package without checking that.

USAGE
  scripts/decor-shortlist.py                  # contact sheet of all candidates
  scripts/decor-shortlist.py --limit 40       # 40 per bucket
"""
import argparse, base64, csv, json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WS = ROOT / "photo-licensing-workspace"
SRC = Path("/Volumes/Extreme SSD/Nikon Photos")
OUT = WS / "decor-shortlist.html"

# Countries whose work reads strongest for decor: water, green, alpine, tropical.
STRONG = {"Iceland", "Switzerland", "Panama", "Canada", "Norway"}

CALM = ["waterfall", "lake", "river", "stream", "fjord", "glacier", "coast", "beach",
        "forest", "moss", "green valley", "meadow", "reflection", "mist", "fog",
        "calm water", "still water", "rainforest", "jungle", "tropical", "pond",
        "alpine", "mountain lake", "sunrise", "sunset"]
ARCH = ["architecture", "cathedral", "church", "castle", "palace", "bridge", "skyline",
        "cityscape", "downtown", "street", "facade", "temple", "shrine", "tower",
        "museum", "library", "interior"]
NEG = ["desert", "saguaro", "cactus", "arid", "sonoran", "insect", "beetle", "macro",
       "spider", "basketball", "ncaa", "sports", "referee", "player", "arena",
       "wedding", "party", "crowd", "dog", "pet", "hiker"]


def locations():
    loc = {}
    p = WS / "alamy-locations.json"
    if p.exists():
        loc.update(json.loads(p.read_text()))
    p = WS / "getty-country-map.json"
    if p.exists():
        loc.update({k: (v.get("country","") if isinstance(v, dict) else v)
                    for k, v in json.loads(p.read_text()).items()})
    return loc


def thumb(f):
    try:
        r = subprocess.run(["exiftool", "-b", "-ThumbnailImage", str(SRC / f)],
                           capture_output=True)
        if r.stdout:
            return base64.b64encode(r.stdout).decode()
    except Exception:
        pass
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50, help="max per bucket")
    a = ap.parse_args()

    loc = locations()
    rows = [r for r in csv.DictReader(open(WS / "metadata-master.csv"))
            if not r["dupe_of"].strip() and r["use"] in ("commercial", "editorial")]

    def blob(r):
        return " ".join([r["title"], r["description"], r["keywords"]]).lower()

    calm, arch = [], []
    for r in rows:
        b = blob(r)
        if any(n in b for n in NEG):
            continue
        if not (SRC / r["filename"]).exists():
            continue
        c = loc.get(r["filename"], "")
        if any(k in b for k in CALM):
            calm.append((r, c))
        elif any(k in b for k in ARCH):
            arch.append((r, c))

    # strongest-market countries first inside each bucket
    calm.sort(key=lambda x: (x[1] not in STRONG, x[1], x[0]["filename"]))
    arch.sort(key=lambda x: (x[1] not in STRONG, x[1], x[0]["filename"]))
    calm, arch = calm[: a.limit], arch[: a.limit]
    print(f"calm nature: {len(calm)}   architecture: {len(arch)}", flush=True)

    def cards(items, bucket):
        out = []
        for r, c in items:
            b64 = thumb(r["filename"])
            img = (f'<img src="data:image/jpeg;base64,{b64}">' if b64
                   else '<div class="nothumb">no thumb</div>')
            out.append(
                f'<label class="c"><input type="checkbox" data-f="{r["filename"]}" '
                f'data-b="{bucket}">{img}'
                f'<span class="m"><span class="ti">{r["title"]}</span>'
                f'<span class="fn">{r["filename"]}</span>'
                f'<span class="lo">{c or "location unknown"}</span></span></label>')
        return "".join(out)

    html = """<!doctype html><meta charset="utf-8"><title>Decor shortlist</title>
<style>
:root{color-scheme:dark}
body{font:14px system-ui,-apple-system,sans-serif;margin:0;padding:22px;background:#0f1115;color:#e6e9ef}
h1{font-size:20px;margin:0 0 4px} h2{font-size:14px;color:#8b93a7;text-transform:uppercase;
  letter-spacing:.08em;margin:26px 0 10px}
.sub{color:#8b93a7;font-size:13px;max-width:78ch;line-height:1.55;margin-bottom:14px}
#bar{position:sticky;top:0;background:#0f1115;padding:12px 0;border-bottom:1px solid #262b36;
  z-index:9;display:flex;gap:12px;align-items:center}
button{background:#7c5cff;color:#fff;border:0;border-radius:8px;padding:11px 20px;
  font-size:14px;font-weight:600;cursor:pointer}
#count{color:#8b93a7;font-size:13px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(215px,1fr));gap:12px}
.c{background:#171a21;border:1px solid #262b36;border-radius:11px;padding:9px;cursor:pointer;
  display:block;position:relative}
.c:has(input:checked){border-color:#7c5cff;background:#1d1b2e}
.c input{position:absolute;top:14px;left:14px;width:19px;height:19px;accent-color:#7c5cff;z-index:2}
img{width:100%;height:132px;object-fit:cover;border-radius:7px;background:#000;display:block}
.nothumb{width:100%;height:132px;display:grid;place-items:center;background:#000;color:#555;
  border-radius:7px;font-size:11px}
.m{display:block;margin-top:7px}
.ti{display:block;font-size:12.5px;line-height:1.35}
.fn{display:block;font-family:ui-monospace,monospace;font-size:10px;color:#6b7280;margin-top:3px;
  word-break:break-all}
.lo{display:block;font-size:11px;color:#8ab4f8;margin-top:2px}
textarea{width:100%;height:150px;background:#000;color:#7ee787;border:1px solid #262b36;
  border-radius:10px;padding:12px;font-family:ui-monospace,monospace;font-size:12px;margin-top:14px}
</style>
<h1>Art-consultant submission shortlist</h1>
<div class="sub">Pick roughly <b>15 calm nature</b> and <b>10 architecture</b>. Healthcare
buyers want restorative nature and the research explicitly says <i>not</i> architecture or
urban views; hospitality and corporate want architecture and cityscapes, ideally local to the
venue. Desert, macro, sports and event work are already filtered out as near-zero decor
demand. Judge by eye for calm palette and open foreground &mdash; metadata can't see those.
Hit <b>Copy selection</b> and paste it back to Claude.</div>
<div id="bar"><button onclick="go()">Copy selection</button><span id="count"></span></div>
"""
    html += f'<h2>Calm nature &mdash; healthcare + hospitality</h2><div class="grid">{cards(calm,"calm")}</div>'
    html += f'<h2>Architecture &amp; cityscape &mdash; hospitality + corporate</h2><div class="grid">{cards(arch,"arch")}</div>'
    html += """
<textarea id="out" placeholder="selection appears here"></textarea>
<script>
function paint(){
  const n=document.querySelectorAll('input:checked').length;
  const c=document.querySelectorAll('input[data-b=calm]:checked').length;
  const a=document.querySelectorAll('input[data-b=arch]:checked').length;
  document.getElementById('count').textContent=`${n} selected (${c} nature, ${a} architecture)`;
}
document.addEventListener('change',paint);
function go(){
  const rows=[['bucket','file name']];
  document.querySelectorAll('input:checked').forEach(i=>rows.push([i.dataset.b,i.dataset.f]));
  const csv=rows.map(r=>r.map(x=>/[",]/.test(x)?'"'+x.replace(/"/g,'""')+'"':x).join(',')).join('\\n');
  document.getElementById('out').value=csv;
  if(navigator.clipboard) navigator.clipboard.writeText(csv);
}
paint();
</script>
"""
    OUT.write_text(html)
    print(f"wrote {OUT} ({OUT.stat().st_size/1024:.0f}KB)")


if __name__ == "__main__":
    main()
