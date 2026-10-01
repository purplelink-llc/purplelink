#!/usr/bin/env python3
"""Submit 123RF drafts for review, with the right license type.

On 123RF an upload lands in Draft and sits there until "Submit for review"
is clicked -- 560+ web-uploaded photos showed PENDING 0 for exactly this
reason (2026-09-23). Every draft also arrives as Commercial, but about half
of this library is editorial per metadata-master.csv, and Commercial implies
model/property releases, so the license has to be set per photo first.

API (sniffed from the page's own requests 2026-09-23, same approach as
collect_getty):
  GET  /apicore-contributors/draft_items?page=N&limit=20&content_type=photoIllustration&editorial=no|yes
       -> data[]: id, oldFilename (the original's stem), filetype (20 commercial,
          21 editorial), kwDesc{description, keywords}, createdAt
  PUT  /apicore-contributors/draft_items
       {"data":[{"type":"draft_item","id":ID,"attributes":{"filetype":21}}]}
  POST /apicore-contributors/draft_items/to_pending
       {"data":{"type":"draft_item","attributes":{"draft_ids":[ID,...]}}}
       -> data[]: {draftId, status}

Duplicates: flaky upload runs left some originals with 2-3 drafts. Only one
draft per original is ever submitted, and an original already submitted is
never submitted again (tracked in STATE), so leftover copies stay in Draft.

Submitting warrants rights to 123RF (Content Contributor Agreement) --
authorized by the account owner 2026-09-23 for this image set.

USAGE
  scripts/123rf-submit-drafts.py --dry-run
  scripts/123rf-submit-drafts.py --limit 20
  scripts/123rf-submit-drafts.py
"""
import argparse, csv, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WS = ROOT / "photo-licensing-workspace"
MASTER = WS / "metadata-master.csv"
STATE = WS / "analytics" / "123rf-submit-state.json"
CDP = "http://127.0.0.1:9340"
API = "https://www.123rf.com/apicore-contributors"
FILETYPE = {"commercial": 20, "editorial": 21}
CHUNK = 20


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"submitted": {}}


def save_state(s):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=2, sort_keys=True))


def fetch_drafts(pg):
    items = []
    for editorial in ("no", "yes"):
        page = 1
        while True:
            r = pg.request.get(f"{API}/draft_items?page={page}&limit=20"
                               f"&content_type=photoIllustration&editorial={editorial}")
            if r.status != 200:
                sys.exit(f"draft_items returned {r.status} -- signed out?")
            d = json.loads(r.text())
            items += d["data"]
            if page >= d["meta"]["pagination"]["total_pages"]:
                break
            page += 1
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="max photos to submit this run")
    a = ap.parse_args()

    use = {r["filename"].rsplit(".", 1)[0]: r["use"] for r in csv.DictReader(open(MASTER))}
    state = load_state()

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        pg = p.chromium.connect_over_cdp(CDP).contexts[0].new_page()
        pg.goto("https://www.123rf.com/contributor/manage-content", wait_until="domcontentloaded")
        pg.wait_for_timeout(3000)
        if "login" in pg.url.lower():
            sys.exit("not signed in to 123RF")

        drafts = fetch_drafts(pg)
        chosen, dupes, unknown, skipped_done = {}, [], [], []
        for it in sorted(drafts, key=lambda i: i["createdAt"]):
            stem = it["oldFilename"]
            if stem in state["submitted"]:
                skipped_done.append(stem)
            elif stem not in use or use[stem] not in FILETYPE:
                unknown.append(stem)
            elif stem in chosen:
                dupes.append(stem)
            elif len(it["kwDesc"]["keywords"]) < 7 or not (it["kwDesc"]["description"] or "").strip():
                unknown.append(f"{stem} (missing description/keywords)")
            else:
                chosen[stem] = it
        todo = list(chosen.values())
        if a.limit:
            todo = todo[: a.limit]
        retype = [it for it in todo if it["filetype"] != FILETYPE[use[it["oldFilename"]]]]

        print(f"drafts: {len(drafts)} | to submit: {len(todo)} "
              f"({sum(use[i['oldFilename']] == 'editorial' for i in todo)} editorial) | "
              f"license changes: {len(retype)} | duplicate copies left in Draft: {len(dupes)} | "
              f"copies of already-submitted: {len(skipped_done)} | skipped (no metadata): {len(unknown)}")
        if unknown:
            print("  no usable metadata:", unknown[:10])
        if a.dry_run:
            return

        for i in range(0, len(retype), CHUNK):
            chunk = retype[i:i + CHUNK]
            body = {"data": [{"type": "draft_item", "id": it["id"],
                              "attributes": {"filetype": FILETYPE[use[it["oldFilename"]]]}}
                             for it in chunk]}
            r = pg.request.put(f"{API}/draft_items", data=json.dumps(body),
                               headers={"content-type": "application/json"})
            if r.status != 200:
                sys.exit(f"license update failed ({r.status}): {r.text()[:300]}")
        if retype:
            # Re-read so a silently ignored license change can't get submitted wrong.
            now = {it["id"]: it["filetype"] for it in fetch_drafts(pg)}
            wrong = [it["oldFilename"] for it in retype
                     if now.get(it["id"]) != FILETYPE[use[it["oldFilename"]]]]
            if wrong:
                sys.exit(f"license type did not stick for {len(wrong)}: {wrong[:10]} -- nothing submitted")
            print(f"license type set on {len(retype)} draft(s), verified")

        ok = fail = 0
        for i in range(0, len(todo), CHUNK):
            chunk = todo[i:i + CHUNK]
            body = {"data": {"type": "draft_item", "attributes": {"draft_ids": [it["id"] for it in chunk]}}}
            r = pg.request.post(f"{API}/draft_items/to_pending", data=json.dumps(body),
                                headers={"content-type": "application/json"})
            if r.status != 200:
                save_state(state)
                sys.exit(f"to_pending failed ({r.status}): {r.text()[:300]}")
            results = {d["draftId"]: d["status"] for d in json.loads(r.text()).get("data", [])}
            for it in chunk:
                if results.get(it["id"]):
                    state["submitted"][it["oldFilename"]] = {"draft_id": it["id"],
                                                            "license": use[it["oldFilename"]]}
                    ok += 1
                else:
                    fail += 1
            save_state(state)
            print(f"  submitted {ok}/{len(todo)}", flush=True)
        print(f"\ndone: {ok} submitted, {fail} refused")
        pg.close()


if __name__ == "__main__":
    main()
