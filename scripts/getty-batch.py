#!/usr/bin/env python3
"""Create Getty ESP batches and report their state.

ESP has no bulk batch creation and caps a batch at 100 files, so 509 images
means six batches, each created by hand through a dialog. This automates that
dialog and prints the batch ids the uploader needs.

Submission type matters: commercial work goes to "iStock creative image",
editorial to "iStock editorial image". They cannot share a batch.

USAGE
  scripts/getty-batch.py --list
  scripts/getty-batch.py --create "commercial 2" --type creative
  scripts/getty-batch.py --create "editorial 1"  --type editorial
"""
import argparse, re, sys, time
from pathlib import Path

CDP = "http://127.0.0.1:9225"
TYPE_LABEL = {"creative": "iStock creative image",
              "editorial": "iStock editorial image"}


def page(b):
    pgs = [x for x in b.contexts[0].pages if "esp.gettyimages.com" in x.url]
    return pgs[-1] if pgs else b.contexts[0].new_page()


def list_batches(pg):
    pg.goto("https://esp.gettyimages.com/contribute/batches",
            wait_until="domcontentloaded", timeout=60_000)
    pg.wait_for_timeout(13_000)
    t = pg.inner_text("body")
    out = []
    # each card reads: <name> | <type> | <count> | Batch ID #<id>
    for m in re.finditer(r"(iStock \w+ image)\s*\|?\s*(\d+)?\s*.{0,40}?Batch ID #(\d+)",
                         t.replace("\n", " | ")):
        out.append({"type": m.group(1), "count": m.group(2), "id": m.group(3)})
    if not out:
        for m in re.finditer(r"Batch ID #(\d+)", t):
            out.append({"id": m.group(1)})
    return out


def create(pg, name, kind):
    label = TYPE_LABEL[kind]
    pg.goto("https://esp.gettyimages.com/contribute",
            wait_until="domcontentloaded", timeout=60_000)
    pg.wait_for_timeout(13_000)
    pg.locator("text=CREATE BATCH").first.click()
    pg.wait_for_timeout(8_000)

    # Submission type is a MUI Select, not a <select>. Its options render in a
    # portal, and clicking them by text hits the dialog's backdrop instead
    # ("subtree intercepts pointer events"). Target [role=option] by data-value.
    VALUE = {"creative": "istock_creative_still",
             "editorial": "istock_editorial_still"}
    if kind != "creative":
        pg.locator("[data-cy=create-batch-dialog] [role=combobox], "
                   "[data-cy=create-batch-dialog] .MuiSelect-select").first.click()
        pg.wait_for_timeout(3_500)
        pg.locator(f"[role=option][data-value='{VALUE[kind]}']").first.click()
        pg.wait_for_timeout(2_500)

    boxes = pg.locator("input[type=text], input:not([type])")
    n = boxes.count()
    if n:
        boxes.nth(n - 1).fill(name)
        pg.wait_for_timeout(1_500)

    # the dialog's Create is the last enabled button on the page
    btns = pg.locator("button")
    idx = pg.eval_on_selector_all(
        "button", "els=>els.map((e,i)=>[i,(e.textContent||'').trim()])"
                  ".filter(([i,t])=>t==='Create').map(([i])=>i).pop()")
    if idx is None:
        sys.exit("could not find the dialog's Create button")
    btns.nth(idx).click()
    pg.wait_for_timeout(15_000)
    m = re.search(r"/batches/(\d+)", pg.url)
    if not m:
        sys.exit(f"batch creation did not navigate to a batch (url {pg.url})")
    return m.group(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--create")
    ap.add_argument("--type", choices=list(TYPE_LABEL), default="creative")
    a = ap.parse_args()

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        pg = page(b)
        if a.create:
            bid = create(pg, a.create, a.type)
            print(f"created batch {bid}  ({TYPE_LABEL[a.type]}, name={a.create!r})")
            print(f"  scripts/getty-upload.py --batch {bid} --use "
                  f"{'commercial' if a.type=='creative' else 'editorial'}")
        else:
            for x in list_batches(pg):
                print("  ", x)


if __name__ == "__main__":
    main()
