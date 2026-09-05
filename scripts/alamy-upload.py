#!/usr/bin/env python3
"""Upload the staged Alamy batch over FTP. No browser, no external dependencies.

THE PASSWORD IS NEVER SEEN BY THE AGENT OR WRITTEN ANYWHERE.
It is read from the macOS Keychain at runtime and held only in memory.

Alamy's FTP (per their contributor help):
  host      upload.alamy.com
  port      21
  username  your Alamy account email
  password  your Alamy account password  <-- same login, so guard it accordingly
  folders   Stock | Live News | Archive Stock | Vectors   (upload INTO one of these)

SETUP (once, run these yourself)
  # stores your Alamy password in Keychain; -w with no value prompts interactively
  # so it never lands in shell history
  security add-generic-password -a "ben.ampel@gmail.com" -s alamy-ftp -w

  export ALAMY_USER="ben.ampel@gmail.com"

USAGE
  scripts/alamy-upload.py --set qc           # FIRST submission (Alamy QC inspects at 100%)
  scripts/alamy-upload.py --set editorial
  scripts/alamy-upload.py --set commercial
  scripts/alamy-upload.py --status
"""
import argparse, ftplib, json, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "photo-licensing-workspace" / "alamy-upload"
STATE = ROOT / "photo-licensing-workspace" / "alamy-upload-state.json"
HOST = "upload.alamy.com"
REMOTE_FOLDER = "Stock"          # all of these are stock submissions
SETS = {"qc": "qc-first", "editorial": "editorial", "commercial": "commercial"}


def load_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {"uploaded": [], "failed": {}}


def save_state(s):
    STATE.write_text(json.dumps(s, indent=2))


def keychain_password(account):
    """Read the password from Keychain. Never logged, never persisted."""
    try:
        return subprocess.run(
            ["security", "find-generic-password", "-a", account, "-s", "alamy-ftp", "-w"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        sys.exit(
            f"ERROR: no Keychain entry for account '{account}', service 'alamy-ftp'.\n"
            f'Add it with:  security add-generic-password -a "{account}" -s alamy-ftp -w'
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=list(SETS), default="qc")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--delay", type=float, default=1.0)
    args = ap.parse_args()

    state = load_state()
    if args.status:
        for k, d in SETS.items():
            p = BASE / d
            n = len(list(p.glob("*.jpeg"))) if p.exists() else 0
            done = sum(1 for f in state["uploaded"] if (BASE / d / f).exists())
            print(f"  {k:<11} {done}/{n} uploaded")
        print(f"  failed: {len(state['failed'])}")
        return

    src = BASE / SETS[args.set]
    files = sorted(f for f in os.listdir(src) if f.lower().endswith((".jpg", ".jpeg")))
    # IMG_* is a phone photo, not a Nikon capture. stock-ftp-upload.py and
    # alamy-supertags.py already refuse these; this script didn't, and a
    # 2026-08-30 backlog run sent IMG_9209.jpeg (a recognizable bystander, no
    # release) before anyone noticed. Owner's rule, 2026-08-07: never license
    # phone photos without a one-off, explicit exception reviewed by hand.
    skipped_img = [f for f in files if f.upper().startswith("IMG_")]
    if skipped_img:
        print(f"  skipping {len(skipped_img)} IMG_* file(s), not eligible for "
              f"auto-upload: {', '.join(skipped_img)}")
    files = [f for f in files if not f.upper().startswith("IMG_")]
    todo = [f for f in files if f not in state["uploaded"]]
    if args.limit:
        todo = todo[: args.limit]
    if not todo:
        print("nothing to upload — this set is already done")
        return

    user = os.environ.get("ALAMY_USER")
    if not user:
        sys.exit("ERROR: set ALAMY_USER to your Alamy account email first")
    pw = keychain_password(user)

    print(f"connecting to {HOST} as {user}")
    ftp = ftplib.FTP(HOST, timeout=60)
    try:
        ftp.login(user, pw)
    except ftplib.error_perm as e:
        sys.exit(f"login failed: {e}\n(FTP password is your Alamy account password)")
    finally:
        del pw                                    # drop it from memory promptly

    try:
        folders = []
        try:
            folders = [n for n, _ in ftp.mlsd()]
        except Exception:
            folders = ftp.nlst()
        print("server folders:", folders)
        target = next((f for f in folders if f.lower() == REMOTE_FOLDER.lower()), None)
        if target:
            ftp.cwd(target)
            print(f"uploading into /{target}")
        else:
            print(f"WARNING: no '{REMOTE_FOLDER}' folder found; uploading to root")

        ok = fail = 0
        for i, name in enumerate(todo, 1):
            path = src / name
            try:
                with open(path, "rb") as fh:
                    ftp.storbinary(f"STOR {name}", fh, blocksize=1 << 20)
                state["uploaded"].append(name)
                state["failed"].pop(name, None)
                ok += 1
                print(f"  OK   [{i}/{len(todo)}] {name} ({path.stat().st_size/1e6:.1f}MB)")
            except Exception as e:
                state["failed"][name] = f"{type(e).__name__}: {e}"
                fail += 1
                print(f"  FAIL [{i}/{len(todo)}] {name} — {e}")
            save_state(state)
            time.sleep(args.delay)
        print(f"\ndone: {ok} uploaded, {fail} failed")
        if args.set == "qc":
            print("Alamy QC inspects a first submission at 100% — wait for the result "
                  "before sending the editorial/commercial sets.")
    finally:
        try:
            ftp.quit()
        except Exception:
            ftp.close()


if __name__ == "__main__":
    main()
