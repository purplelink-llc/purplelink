#!/usr/bin/env python3
"""Remove already-submitted photos from 123RF's FTP inbox, so a late FTP import
can't create a second copy of everything.

570 files were FTP'd 2026-09-10 and never ingested; the same photos were
later web-uploaded and submitted (see 123rf-submit-drafts.py). Only files
whose original is recorded as submitted AND still exists on the drive are
eligible. Without --delete this only lists what would be removed.

  scripts/123rf-ftp-cleanup.py            # preview
  scripts/123rf-ftp-cleanup.py --delete   # actually delete
"""
import argparse, ftplib, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUBMITTED = ROOT / "photo-licensing-workspace" / "analytics" / "123rf-submit-state.json"
SRC = Path("/Volumes/Extreme SSD/Nikon Photos")
FOLDERS = ["", "pluspremium", "editorial", "free", "free/editorial"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delete", action="store_true")
    a = ap.parse_args()

    submitted = set(json.loads(SUBMITTED.read_text())["submitted"])
    pw = subprocess.run(["security", "find-generic-password", "-a", "purplelinkpl",
                         "-s", "123rf-ftp", "-w"], capture_output=True, text=True).stdout.strip()
    if not pw:
        sys.exit("no Keychain entry for 123rf-ftp")
    ftp = ftplib.FTP("ftp.123rf.com", timeout=60)
    ftp.login("purplelinkpl", pw)

    targets, kept = [], []
    for folder in FOLDERS:
        try:
            names = ftp.nlst(folder or ".")
        except ftplib.error_perm:
            continue
        for n in names:
            name = n.split("/")[-1]
            if name in (".", "..") or "." not in name:
                continue
            path = f"{folder}/{name}" if folder else name
            if Path(name).stem in submitted and (SRC / name).exists():
                targets.append(path)
            else:
                kept.append(path)

    print(f"{len(targets)} file(s) to remove, {len(kept)} left alone")
    if kept:
        print("  left alone:", kept[:20])
    if not a.delete:
        print("\npreview only -- re-run with --delete to remove them")
        return
    done = 0
    for path in targets:
        try:
            ftp.delete(path)
            done += 1
        except ftplib.all_errors as e:
            print(f"  could not delete {path}: {e}")
    print(f"deleted {done}/{len(targets)}")
    ftp.quit()


if __name__ == "__main__":
    main()
