"""Check (and, where a plain URL exists, fetch) the CC0 files listed in assets.json, under $AMBIENT_LOOPS/_assets.

    python3 -I fetch_assets.py [--fetch]

Every file must match its recorded sha256; a mismatch stops the build. Kenney zips come from a signed link on their page, so a missing
one is reported with the page to download it from. Zips are unpacked to x/ beside them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
LOOPS = os.environ.get("AMBIENT_LOOPS", "/Volumes/Extreme SSD/PurplelinkVideos/ambient/_loops")


def sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    a = ap.parse_args()
    root = os.path.join(LOOPS, "_assets")
    with open(os.path.join(HERE, "assets.json")) as f:
        spec = json.load(f)
    bad = 0
    for it in spec["assets"]:
        p = os.path.join(root, it["path"])
        if not os.path.exists(p):
            if a.fetch and it["download"].startswith("https://"):
                os.makedirs(os.path.dirname(p), exist_ok=True)
                req = urllib.request.Request(it["download"], headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=120) as r, open(p + ".part", "wb") as out:
                    out.write(r.read())
                os.replace(p + ".part", p)
            else:
                print(f"MISSING {it['path']}  (download from {it['page']})")
                bad += 1
                continue
        got = sha(p)
        if got != it["sha256"]:
            print(f"HASH MISMATCH {it['path']}: {got}")
            bad += 1
            continue
        if it.get("unzip"):
            x = os.path.join(os.path.dirname(p), "x")
            if not os.path.isdir(x):
                with zipfile.ZipFile(p) as z:
                    for n in z.namelist():
                        if n.startswith("/") or ".." in n.split("/"):
                            raise SystemExit(f"unsafe path in {p}: {n}")
                    z.extractall(x)
        print(f"ok {it['path']}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
