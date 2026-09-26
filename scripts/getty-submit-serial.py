#!/usr/bin/env python3
"""Submit a Getty batch one file at a time, because "Select all" is broken.

WHY ONE AT A TIME
On batch 67091094 (65 files) ESP's "Select all" does nothing: the SUBMIT
counter stays at 1 and only one card ever reports data-cy-selected="true".
Clicking a single card DOES enable SUBMIT for that card, and submitting it
works -- verified twice, review went 0->1->2.

WHAT THAT MEANS (correcting a documented belief)
NEXT-SESSION.md says "PROVEN 2026-08-22: A GETTY BATCH CAN ONLY BE SUBMITTED
ONCE" and concluded that leftover files are stranded forever and must be
re-uploaded into a new batch. That conclusion looks wrong. This script submits
the same batch dozens of times in a row. The earlier "stranding" is far better
explained by this selection bug -- the leftover files were never actually
selected, so SUBMIT only ever moved the handful that were -- than by a Getty
rule. If that holds, the ~170 pending files sitting across the older batches
may be recoverable in place, with no re-upload at all.

Verified against ESP's contributions API after every submit, never the UI.

SUPERSEDES scripts/getty-submit.py, which selects via "Select all" and so
submits at most one file while reporting many ("submitted: 55, excluded: 27,
still_pending: 55" against 82 files, numbers that do not reconcile). Prefer
this script; keep the old one only until nothing references it.

USAGE
  scripts/getty-submit-serial.py 67091094
  scripts/getty-submit-serial.py 66508252     # try the older stranded batches
"""
import json
import re
import sys
import time
from collections import Counter
from cdp_tab import Tab

BID = sys.argv[1] if len(sys.argv) > 1 else "67091094"
API = f"https://esp.gettyimages.com/api/submission/v1/submission_batches/{BID}/contributions"
MAX_CONSEC_FAIL = 5


def main():
    # Raw CDP, not Playwright: connect_over_cdp hangs on this profile's synced
    # extensions. JS clicks (not mouse events) so it runs in a background tab
    # without stealing focus from another job on the same Chrome.
    pg = Tab.new(background=True)
    BATCH_URL = f"https://esp.gettyimages.com/contribute/batches/{BID}"
    pg.goto(BATCH_URL, settle=18)
    wait = lambda ms: time.sleep(ms / 1000)

    if True:
        def statuses():
            r = pg.eval(f"""(async () => {{
                const r = await fetch({API + '?page=1&page_size=200'!r}, {{credentials:'include',
                                          headers:{{'Accept':'application/json'}}}});
                return r.ok ? await r.json() : {{error: r.status}};
            }})()""")
            if isinstance(r, dict) and r.get("error"):
                raise RuntimeError(f"ESP API {r['error']} — session expired")
            items = r if isinstance(r, list) else r.get("items", r.get("contributions", r.get("data", [])))
            return items

        # Getty bans AI-processed editorial. Editorial batches 66508252 and
        # 66928700 hold Topaz/Lightroom-AI files (2.6x upscales among them)
        # that the API reports as submittable -- the API does not enforce
        # the policy, so this has to.
        btype = pg.eval(f"""fetch('/api/submission/v1/submission_batches?page=1&page_size=100',
            {{credentials:'include'}}).then(r=>r.json()).then(j=>((j.items||[]).find(b=>b.id==={BID!r})||{{}}).submission_type)""")
        editorial = "editorial" in (btype or "")
        ai = re.compile(r"(?i)enhanced|topaz|denoise|sharpenai|upscal|gigapixel")
        # The same file sits in several batches (creative + editorial copies).
        # iStock auto-rejects a copy of anything already accepted or in review
        # elsewhere (2026-09-26: 6 of 7 editorial submits bounced in seconds,
        # all already live in creative batch 67091094). Skip those names.
        others = pg.eval(f"""(async()=>{{const j=await fetch('/api/submission/v1/submission_batches?page=1&page_size=100',{{credentials:'include'}}).then(r=>r.json());
            const out=[]; for(const b of (j.items||[])){{ if(b.id==={BID!r}) continue;
              const c=await fetch('/api/submission/v1/submission_batches/'+b.id+'/contributions?page=1&page_size=200',{{credentials:'include'}}).then(r=>r.json());
              for(const r of (c.items||c)) if(['review','processed','revisable'].includes(r.status)) out.push(r.file_name);}}
            return out}})()""")
        elsewhere = set(others or [])
        allowed = lambda name: not (editorial and ai.search(name or "")) and name not in elsewhere

        def sub_counter():
            m = re.search(r"SUBMIT\s*\n?\s*(\d+)", pg.text())
            return int(m.group(1)) if m else None

        def click_exact(label):
            return pg.eval(f"""(()=>{{const e=[...document.querySelectorAll('button')]
                .find(x=>(x.innerText||'').trim().split('\\n')[0].trim()==={label!r} && !x.disabled);
                if(!e) return false; e.click(); return true}})()""")

        def clear_sel():
            pg.eval("""(()=>{const e=[...document.querySelectorAll('button,span,div,a')]
                .find(x=>/^clear selection$/i.test((x.textContent||'').trim())); if(e) e.click();})()""")
            wait(1200)

        def next_card(pending_names, skip=()):
            """First card whose FILENAME is still pending per the API.

            The tile itself does not reliably show review state, so an earlier
            version kept re-picking card 0 -- already submitted -- and SUBMIT
            stayed disabled because nothing submittable was selected. The API's
            pending set is the only trustworthy filter here."""
            return pg.eval(f"""(([names, skip])=>{{
              const want=new Set(names), bad=new Set(skip);
              const cards=[...document.querySelectorAll('[data-cy=item-card]')];
              for(let i=0;i<cards.length;i++){{
                if(bad.has(i)) continue;
                const t=cards[i].textContent||'';
                if(/Upload failed/i.test(t)) continue;
                if(!/ID:\\s*\\d/.test(t)) continue;
                const m=t.match(/DSC_[\\w\\-(). ]+\\.jpe?g/);
                if(m && want.has(m[0])) return i;
              }}
              return -1;}})({json.dumps([list(pending_names), list(skip)])})""")

        items = statuses()
        start = Counter(i.get("status") for i in items)
        target = sum(1 for i in items if i.get("submittable") and i.get("status") == "pending"
                     and allowed(i.get("file_name")))
        held = sorted({i.get("file_name") for i in items if i.get("status") == "pending"
                       and i.get("submittable") and not allowed(i.get("file_name"))})
        print(f"batch {BID} ({btype}): {start.most_common()}  submittable-pending={target}", flush=True)
        if held:
            print(f"  held back, AI-processed in an editorial batch or already accepted/in review "
                  f"in another batch ({len(held)}): {held}", flush=True)

        done = 0
        consec_fail = 0
        # A single card whose SUBMIT click always times out used to eat the
        # whole run: next_card() returns the FIRST candidate, so the loop
        # retried card 50 five times and stopped with 14 files still pending.
        # Park a card after it fails and move on.
        skip = set()
        while consec_fail < MAX_CONSEC_FAIL:
            before = Counter(i.get("status") for i in statuses())
            if before.get("pending", 0) == 0:
                print("nothing pending left", flush=True)
                break

            clear_sel()
            pending_names = {i.get("file_name") for i in statuses()
                             if i.get("status") == "pending" and i.get("submittable")
                             and allowed(i.get("file_name"))}
            if not pending_names:
                print("nothing submittable left", flush=True)
                break
            idx = next_card(pending_names, skip)
            if idx < 0:
                print("no candidate card visible — reloading page", flush=True)
                pg.goto(BATCH_URL, settle=18)
                idx = next_card(pending_names, skip)
                if idx < 0:
                    print("still no candidate — stopping", flush=True)
                    break

            pg.eval(f"(()=>{{const c=document.querySelectorAll('[data-cy=item-card]')[{idx}];"
                    "if(c) c.click();})()")
            wait(2600)
            if (sub_counter() or 0) < 1:
                consec_fail += 1
                skip.add(idx)
                print(f"  card {idx}: SUBMIT not enabled — parked ({consec_fail})", flush=True)
                continue

            if not click_exact("SUBMIT"):
                consec_fail += 1
                skip.add(idx)
                print(f"  card {idx}: SUBMIT button not clickable — parked ({consec_fail})", flush=True)
                continue
            wait(3800)
            if click_exact("YES, SUBMIT"):
                wait(9000)

            after = Counter(i.get("status") for i in statuses())
            if after.get("review", 0) > before.get("review", 0):
                done += 1
                consec_fail = 0
                print(f"  [{done}/{target}] submitted — review={after.get('review',0)} "
                      f"pending={after.get('pending',0)}", flush=True)
            elif after.get("rejected", 0) > before.get("rejected", 0):
                # Submitted, then auto-rejected by iStock's inspector within
                # seconds. Stop: something about this batch is systematically
                # wrong, and every further submit burns a file.
                print(f"  card {idx}: submitted but AUTO-REJECTED (rejected="
                      f"{after.get('rejected',0)}) — stopping to investigate", flush=True)
                break
            else:
                consec_fail += 1
                skip.add(idx)
                print(f"  card {idx}: no status change — parked ({consec_fail})", flush=True)

        final = Counter(i.get("status") for i in statuses())
        print(f"\nfinal: {final.most_common()}  (submitted this run: {done})", flush=True)
    pg.close()


if __name__ == "__main__":
    main()
