#!/usr/bin/env python3
"""Create a Fine Art America collection and add artworks to it, by title.

The thirteen collections in photo-licensing-workspace/faa-collections-state.json
were made by hand on 2026-09-23; this does the same through the photo
automation Chrome (the CDP profile faa-update-metadata.py and the daily sweep
use, signed in by faa-autologin.py). It never signs in itself.

MECHANISM (read from FAA's own pages, 2026-10-31)
  New collection: /controlpanel/updateartworkgallery.html?newartworkgallery=true,
    form "artworkgalleryform" (name, description), submitted by validateform().
  Adding: each load of the collection's edit page issues a draft token (the
    form's hidden "collectionid"). The tab "Images NOT in Collection"
    (?tab=unassignedimages&collectionid=<token>), searched by Image Title, has an
    "Add" link per row, addimagetogallery(<artworkid>), which posts to
    /queries/queryartworkgalleryimagemanagementnew.php and answers with a green
    check. Those adds sit in the draft: they only reach the collection when the
    main form is submitted on the SAME token (validateform()). A fresh page load
    gets a new token and drops the draft; that is how the first run on
    2026-10-31 reported ten adds and left "Images = 0".
  The gallery id is read back from the profile's Collections tab by name, and the
  result is checked on the public collection page ("Images = N").

  python3 scripts/faa-collection.py --name "Atlanta and North Georgia" \\
      --description "..." --titles-file titles.txt --dry-run
  python3 scripts/faa-collection.py --name ... --description ... --titles-file titles.txt

titles.txt: one FAA title per line, exactly as the listing shows it.
"""
import argparse, json, re, sys, time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_photo_hubs import WS  # noqa: E402

STATE = WS / "faa-collections-state.json"
CDP = "http://127.0.0.1:9340"
PROFILE = "https://fineartamerica.com/profiles/benjamin-ampel?tab=artworkgalleries"
EDIT = "https://fineartamerica.com/controlpanel/updateartworkgallery.html?artworkgalleryid={}"


def key(t):
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def gallery_ids(pg):
    pg.goto(PROFILE, wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(3500)
    if "login" in pg.url.lower():
        sys.exit("FAA session expired: run scripts/faa-autologin.py --if-needed")
    return pg.evaluate("""()=>{const o={};document.querySelectorAll('a[href*="artworkgalleryid="]').forEach(a=>{
        const m=a.getAttribute('href').match(/artworkgalleryid=(\\d+)/); const t=a.textContent.trim();
        if(m&&t&&!/^(Edit|Position)/.test(t)) o[t]=m[1]});return o}""")


def create(pg, name, description):
    pg.goto("https://fineartamerica.com/controlpanel/updateartworkgallery.html?newartworkgallery=true",
            wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(3000)
    pg.locator('form[name="artworkgalleryform"] input[name="name"]').fill(name)
    pg.locator('form[name="artworkgalleryform"] textarea[name="description"]').fill(description)
    pg.evaluate("()=>validateform()")
    pg.wait_for_timeout(6000)


def draft_token(pg, gid):
    pg.goto(EDIT.format(gid), wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(2500)
    return pg.evaluate("()=>document.forms['artworkgalleryform'].collectionid.value")


def open_unassigned(pg, token, title):
    pg.goto(f"https://fineartamerica.com/controlpanel/updateartworkgallery.html?tab=unassignedimages&collectionid={token}",
            wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(2500)
    pg.select_option('select[name="artworkgalleryimagesearchtype"]', "artworkname")
    pg.fill('input[name="artworkgalleryimagesearchvalue"]', title[:60])
    pg.evaluate("()=>document.forms['artworkgalleryimagesearchform'].submit()")
    pg.wait_for_timeout(3500)
    if token not in pg.url:
        sys.exit(f"the search left the draft token ({pg.url}); stop before adding to a draft that will be dropped")


def public_count(pg, gid):
    pg.goto(f"https://fineartamerica.com/profiles/benjamin-ampel?tab=artworkgalleries&artworkgalleryid={gid}",
            wait_until="networkidle", timeout=60000)
    pg.wait_for_timeout(2000)
    m = re.search(r"Images = (\d+)", pg.evaluate("()=>document.body.innerText"))
    return int(m.group(1)) if m else -1


def rows(pg):
    """[(artworkid, title)] on the current unassigned-images page."""
    return pg.evaluate("""()=>[...document.querySelectorAll('[id^="imagediv["]')].map(d=>{
        const id=d.id.match(/\\[(\\d+)\\]/)[1];
        const a=d.querySelector('p a'); return [id, a ? a.textContent.trim() : '']})""")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True)
    ap.add_argument("--description", required=True)
    ap.add_argument("--titles-file", required=True)
    ap.add_argument("--dry-run", action="store_true", help="find each title, change nothing")
    a = ap.parse_args()
    titles = [t.strip() for t in Path(a.titles_file).read_text().splitlines() if t.strip()]
    state = json.loads(STATE.read_text()) if STATE.exists() else {"collections": {}}

    with sync_playwright() as p:
        pg = p.chromium.connect_over_cdp(CDP).contexts[0].new_page()
        ids = gallery_ids(pg)
        gid = ids.get(a.name)
        if not gid and a.dry_run:
            gid = next(iter(ids.values()))          # any collection's page lists the unassigned images too
            print(f"dry run: '{a.name}' does not exist yet; searching through collection {gid}")
        elif not gid:
            create(pg, a.name, a.description)
            gid = gallery_ids(pg).get(a.name)
            if not gid:
                sys.exit("collection not found after create; check the profile's Collections tab")
            print(f"created '{a.name}' (id {gid})")
        added, missing = [], []
        token = draft_token(pg, gid)
        for t in titles:
            open_unassigned(pg, token, t)
            hit = [(i, rt) for i, rt in rows(pg) if key(rt) == key(t)]
            if not hit:
                missing.append(t)
                print(f"  NOT FOUND (or already in the collection): {t}")
                continue
            if a.dry_run:
                print(f"  would add {hit[0][0]}: {t}")
                continue
            with pg.expect_response(lambda r: "queryartworkgalleryimagemanagement" in r.url) as resp:
                pg.evaluate(f"()=>addimagetogallery({hit[0][0]})")
            if "RoundCheckGreen" not in resp.value.text():
                missing.append(t)
                print(f"  FAA did not confirm the add: {t}")
                continue
            added.append(t)
            print(f"  added {hit[0][0]}: {t}")
            time.sleep(1)
        if a.dry_run:
            return 0
        # commit the draft on the same token, then read the public count
        pg.goto(f"https://fineartamerica.com/controlpanel/updateartworkgallery.html?tab=artworkgalleryimages&collectionid={token}",
                wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(2500)
        pg.evaluate("()=>validateform()")
        pg.wait_for_timeout(6000)
        count = public_count(pg, gid)
        pg.close()
    state["collections"][a.name] = {"id": gid, "planned": len(titles), "public_count": count}
    STATE.write_text(json.dumps(state, indent=1) + "\n")
    print(f"{len(added)} added, {len(missing)} not found; the collection now lists {count}")
    print(f"https://fineartamerica.com/profiles/benjamin-ampel?tab=artworkgalleries&artworkgalleryid={gid}")
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
