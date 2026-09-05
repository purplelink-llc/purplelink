#!/usr/bin/env python3
"""Request and fetch Alamy's "Send me my data" metadata export.

WHY THIS EXISTS
Alamy has no contributor API, and the Image Manager is the heaviest page in this
whole system -- 575 tiles, lazy-rendered, and it has crashed Chrome repeatedly.
"Download your data" is Alamy's own sanctioned bulk export of every filename and
its metadata, which makes it the right way to read portfolio state (tags,
supertags, discoverability) without scraping a grid at all.

WHAT IT IS AND IS NOT
It is "a copy of all file names and related image metadata". It is NOT sales or
earnings data -- balance and sales_to_date still come from the dashboard
collector. Wiring this up reduces scraping; it does not eliminate it.

IT IS ASYNCHRONOUS. Requesting sets the panel to "Your metadata is being
processed and will be available for download here once complete. This could take
up to 24 hours." So this is two runs: --request today, --check tomorrow.

USAGE
  scripts/alamy-export.py --request      # ask Alamy to build it
  scripts/alamy-export.py --check        # ready? then download it
  scripts/alamy-export.py --check --describe   # ...and print its real columns

COLUMNS (verified against BenjaminAmpel_18082026.csv, 570 rows)
    Filename, ImageRef, Caption, Tags, License type, Username, Super Tags,
    Location, Date taken, Number of People, Model release,
    Is there property in this image?, Property release, Primary category,
    Secondary category, Image Type, Exclusive to Alamy, Additional Info, Status

"Super Tags" is the reason this is worth having: it reports supertag state for
every image at once. Scraping that meant opening 570 tiles one at a time on a
page that crashes Chrome. The export answered it in one file, and immediately
found 11 images the tile-by-tile run had missed.
"""
import argparse, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "photo-licensing-workspace" / "exports"
URL = "https://www.alamy.com/myupload/Index.aspx"
CDP = "http://127.0.0.1:9225"
PANEL = "Download your data"


def open_manager(pg):
    pg.goto(URL, wait_until="domcontentloaded", timeout=90_000)
    pg.wait_for_timeout(20_000)
    if "login" in pg.url.lower() or "signin" in pg.url.lower():
        sys.exit("Alamy session expired — sign in, then re-run")
    # The QC congratulations modal overlays the page and swallows clicks.
    for name in ("OK, got it", "OK got it", "Got it"):
        try:
            pg.get_by_role("button", name=re.compile(name, re.I)).first.click(timeout=4000)
            pg.wait_for_timeout(2000)
            break
        except Exception:
            continue


def panel_text(pg):
    t = re.sub(r"[ \t]+", " ", pg.inner_text("body"))
    i = t.find(PANEL)
    return t[i:i + 500] if i >= 0 else ""


def ingest(which):
    """Roll the export into snapshots.csv. Reads Alamy's own file rather than
    a scrape, so it cannot be wrong about what Alamy holds."""
    import csv, datetime, glob
    if which == "latest":
        cands = sorted(glob.glob(str(DEST / "*_*.csv")))
        if not cands:
            sys.exit(f"no Alamy export in {DEST} — run --check first")
        path = Path(cands[-1])
    else:
        path = Path(which)
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    if not rows or "Super Tags" not in rows[0]:
        sys.exit(f"{path.name} is not an Alamy export (no 'Super Tags' column)")

    def n_super(r):
        s = (r.get("Super Tags") or "").strip()
        return len([x for x in s.split(",") if x.strip()]) if s else 0

    full = sum(1 for r in rows if n_super(r) >= 10)
    none_ = sum(1 for r in rows if n_super(r) == 0)
    on_sale = sum(1 for r in rows if (r.get("Status") or "").strip().lower() == "on sale")
    metrics = {"export_images": len(rows), "export_on_sale": on_sale,
               "export_supertagged_10": full, "export_supertagged_0": none_}

    today = datetime.date.today().isoformat()
    snap = ROOT / "photo-licensing-workspace" / "analytics" / "snapshots.csv"
    keep = []
    if snap.exists():
        keep = [r for r in csv.DictReader(open(snap))
                if not (r["snapshot_date"] == today and r["platform"] == "alamy"
                        and r["metric"].startswith("export_"))]
    for k, v in metrics.items():
        keep.append({"snapshot_date": today, "platform": "alamy", "metric": k,
                     "value": v, "note": f"from {path.name}"})
    keep.sort(key=lambda r: (r["snapshot_date"], r["platform"], r["metric"]))
    with open(snap, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["snapshot_date", "platform", "metric", "value", "note"])
        w.writeheader(); w.writerows(keep)

    print(f"{path.name}: {len(rows)} images")
    for k, v in metrics.items():
        print(f"  {k:24s} {v}")
    gaps = [r["Filename"] for r in rows if n_super(r) == 0]
    if gaps:
        print(f"\n{len(gaps)} image(s) with NO supertags:")
        for g in gaps:
            print(f"    {g}")
    return


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--request", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--describe", action="store_true",
                    help="print the downloaded file's real columns")
    ap.add_argument("--ingest", metavar="CSV", nargs="?", const="latest",
                    help="parse an already-downloaded export into snapshots.csv")
    a = ap.parse_args()
    if a.ingest:
        return ingest(a.ingest)
    if not (a.request or a.check):
        ap.error("pass --request, --check or --ingest")

    import importlib.util
    spec = importlib.util.spec_from_file_location("st", ROOT / "scripts" / "alamy-supertags.py")
    st = importlib.util.module_from_spec(spec); spec.loader.exec_module(st)
    st.chrome_up()

    from playwright.sync_api import sync_playwright
    DEST.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        pg = b.contexts[0].new_page()
        pg.set_viewport_size({"width": 1500, "height": 950})
        open_manager(pg)
        txt = panel_text(pg)
        if not txt:
            sys.exit("'Download your data' panel not found — layout may have changed")

        if a.request:
            clicked = pg.evaluate("""()=>{const b=[...document.querySelectorAll('button')]
                .find(x=>/Send me my data/i.test(x.textContent||''));
                if(!b) return false; b.scrollIntoView({block:'center'}); b.click(); return true;}""")
            if not clicked:
                print("no 'Send me my data' button — a request is probably already pending")
            pg.wait_for_timeout(8000)
            print(panel_text(pg).strip()[:300])
            return

        # --check
        if "being processed" in txt:
            print("still processing — Alamy says up to 24 hours. Re-run --check later.")
            print(txt.strip()[:220])
            return
        link = pg.evaluate("""()=>{const el=[...document.querySelectorAll('a,button')]
            .filter(e=>e.offsetParent && /download/i.test(e.textContent||'')
                       && !/download your data/i.test(e.textContent||''));
            return el.length ? el[el.length-1].textContent.trim() : null;}""")
        if not link:
            print("no download control yet. Panel says:")
            print(txt.strip()[:260])
            return
        try:
            with pg.expect_download(timeout=90_000) as dl:
                pg.evaluate("""()=>{const el=[...document.querySelectorAll('a,button')]
                    .filter(e=>e.offsetParent && /download/i.test(e.textContent||'')
                               && !/download your data/i.test(e.textContent||''));
                    el[el.length-1].click();}""")
            d = dl.value
            target = DEST / (d.suggested_filename or "alamy-export.csv")
            d.save_as(str(target))
            print(f"saved {target} ({target.stat().st_size} bytes)")
        except Exception as e:
            sys.exit(f"download failed: {str(e)[:200]}")

        if a.describe:
            import csv, io
            head = target.read_text(encoding="utf-8-sig", errors="ignore")
            rows = list(csv.reader(io.StringIO(head)))[:3]
            print("\nREAL COLUMNS (write the parser against these, not a guess):")
            for i, r in enumerate(rows):
                print(f"  row {i}: {r}")


if __name__ == "__main__":
    main()
