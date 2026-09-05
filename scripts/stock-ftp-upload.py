#!/usr/bin/env python3
"""Upload a photo library to any FTP-capable stock agency.

One script, several agencies. Each has its own host, folder convention and
minimum resolution; all of that lives in AGENCIES below.

CREDENTIALS ARE NEVER STORED HERE OR SEEN BY THE AGENT.
Each agency's password lives in the macOS Keychain under its own service name
and is read at runtime only.

SETUP (per agency, run these yourself)
  security add-generic-password -a "<your-username>" -s <keychain-service> -w
  export SHUTTERSTOCK_USER="..."      # etc, see --list

USAGE
  scripts/stock-ftp-upload.py --list
  scripts/stock-ftp-upload.py --agency shutterstock --set qc
  scripts/stock-ftp-upload.py --agency shutterstock --set all
  scripts/stock-ftp-upload.py --agency dreamstime --set all --limit 25
  scripts/stock-ftp-upload.py --status
"""
import argparse, ftplib, json, os, re, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WS = ROOT / "photo-licensing-workspace"
SRC = Path("/Volumes/Extreme SSD/Nikon Photos")
MASTER = WS / "metadata-master.csv"
STATE_DIR = WS / "ftp-state"          # one file per agency; concurrent-safe

# min_mp: agency's stated minimum. folder: remote dir to upload into ("" = root).
AGENCIES = {
    # Shutterstock requires FTPS (FTP over explicit TLS); username is your account
    # email, password is your contributor password.
    "shutterstock": {"host": "ftp.shutterstock.com", "folder": "", "min_mp": 4.0,
                     "service": "shutterstock-ftp", "env": "SHUTTERSTOCK_USER",
                     "tls": True},
    "dreamstime":   {"host": "upload.dreamstime.com", "folder": "", "min_mp": 3.0,
                     "service": "dreamstime-ftp", "env": "DREAMSTIME_USER"},
    "depositphotos":{"host": "ftp.depositphotos.com", "folder": "", "min_mp": 3.8,
                     "service": "depositphotos-ftp", "env": "DEPOSITPHOTOS_USER"},
    "123rf":        {"host": "submit.123rf.com", "folder": "", "min_mp": 6.0,
                     "service": "123rf-ftp", "env": "RF123_USER"},
    "alamy":        {"host": "upload.alamy.com", "folder": "Stock", "min_mp": 6.0,
                     "service": "alamy-ftp", "env": "ALAMY_USER"},
}


def _state_path(agency):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR / f"{agency}.json"


def load_state(agency):
    p = _state_path(agency)
    return json.loads(p.read_text()) if p.exists() else {"uploaded": [], "failed": {}}


def save_state(agency, s):
    _state_path(agency).write_text(json.dumps(s, indent=2))


def password(account, service):
    try:
        return subprocess.run(
            ["security", "find-generic-password", "-a", account, "-s", service, "-w"],
            capture_output=True, text=True, check=True).stdout.strip()
    except subprocess.CalledProcessError:
        sys.exit(f"ERROR: no Keychain entry (account '{account}', service '{service}').\n"
                 f'Add it:  security add-generic-password -a "{account}" -s {service} -w')


CLEAN_SET = WS / "clean-upload-set.json"


def eligible(min_mp):
    """Images cleared for upload: keepers that pass the resolution floor AND the
    exclusion filters (franchise IP, private events, camera shake, provenance).

    clean-upload-set.json is authoritative when present — it encodes decisions made
    after reviewing agency policies. Uploading the raw keeper set once sent Warner
    Bros. studio props to two agencies; don't reintroduce that path."""
    import csv
    rows = [r for r in csv.DictReader(open(MASTER))
            if not r["dupe_of"].strip() and r["use"] in ("commercial", "editorial")
            and r["rating"].strip().isdigit() and int(r["rating"]) >= 3
            # IMG_* are iPhone frames, not Nikon captures — private wedding
            # photography that must never be licensed. Owner's rule, 2026-08-07.
            and not r["filename"].upper().startswith("IMG_")
            # 11156_* are purchased race-event photos. Ben is the SUBJECT, not the
            # photographer; he holds no copyright and cannot license them.
            and not r["filename"].startswith("11156_")
            # Anything that isn't DSC_* came off a phone, not the Nikon.
            and r["filename"].upper().startswith("DSC")]
    if CLEAN_SET.exists():
        allowed = set(json.loads(CLEAN_SET.read_text()))
        before = len(rows)
        rows = [r for r in rows if r["filename"] in allowed]
        print(f"  clean-set filter: {len(rows)} of {before} images cleared for upload")
    paths = [SRC / r["filename"] for r in rows]
    out = subprocess.run(["exiftool", "-j", "-ImageWidth", "-ImageHeight", "-FileName"]
                         + [str(p) for p in paths], capture_output=True, text=True).stdout
    dim = {os.path.basename(d["FileName"]): d["ImageWidth"] * d["ImageHeight"] / 1e6
           for d in json.loads(out)}
    keep = [r for r in rows if dim.get(r["filename"], 0) >= min_mp]
    keep.sort(key=lambda r: (-int(r["rating"]), r["filename"]))
    return keep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agency", choices=list(AGENCIES))
    ap.add_argument("--set", choices=["qc", "all"], default="qc",
                    help="qc = first 5 (for agencies that inspect a first batch)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()

    if a.list:
        print(f"{'agency':<15}{'host':<32}{'min MP':<8}{'keychain service':<22}env var")
        for k, c in AGENCIES.items():
            print(f"{k:<15}{c['host']:<32}{c['min_mp']:<8}{c['service']:<22}{c['env']}")
        return

    if a.status:
        for k in AGENCIES:
            st = load_state(k)
            print(f"  {k:<15} {len(st['uploaded'])} uploaded, {len(st['failed'])} failed")
        return

    if not a.agency:
        sys.exit("specify --agency (see --list)")
    cfg = AGENCIES[a.agency]
    user = os.environ.get(cfg["env"])
    if not user:
        sys.exit(f"ERROR: set {cfg['env']} to your {a.agency} username first")

    rows = eligible(cfg["min_mp"])
    names = [r["filename"] for r in rows]
    if a.set == "qc":
        names = names[:5]
    st = load_state(a.agency)
    todo = [n for n in names if n not in st["uploaded"]]
    if a.limit:
        todo = todo[: a.limit]
    if not todo:
        print("nothing to upload — this set is already done")
        return
    print(f"{a.agency}: {len(todo)} file(s) (>= {cfg['min_mp']}MP), host {cfg['host']}")

    keychain_pw = [password(user, cfg["service"])]
    ftp = (ftplib.FTP_TLS if cfg.get("tls") else ftplib.FTP)(cfg["host"], timeout=60)
    try:
        ftp.login(user, keychain_pw[0])
        if cfg.get("tls"):
            ftp.prot_p()          # encrypt the data channel too, not just the login
    except ftplib.error_perm as e:
        sys.exit(f"login failed: {e}")

    try:
        if cfg["folder"]:
            try:
                ftp.cwd(cfg["folder"])
                print(f"uploading into /{cfg['folder']}")
            except Exception:
                print(f"WARNING: folder '{cfg['folder']}' missing; using root")
        def connect():
            """Fresh control connection — some servers desync mid-session."""
            f = (ftplib.FTP_TLS if cfg.get("tls") else ftplib.FTP)(cfg["host"], timeout=60)
            f.login(user, keychain_pw[0])
            if cfg.get("tls"):
                f.prot_p()
            if cfg["folder"]:
                try: f.cwd(cfg["folder"])
                except Exception: pass
            return f

        ok = fail = 0
        RECYCLE = 40          # rebuild the control connection every N files
        for i, name in enumerate(todo, 1):
            if i > 1 and (i - 1) % RECYCLE == 0:
                try: ftp.quit()
                except Exception:
                    try: ftp.close()
                    except Exception: pass
                ftp = connect()
                print(f"  ...  reconnected after {RECYCLE} files")
            p = SRC / name
            last_err = None
            for attempt in (1, 2, 3):
                try:
                    with open(p, "rb") as fh:
                        ftp.storbinary(f"STOR {name}", fh, blocksize=1 << 20)
                    last_err = None
                    break
                except Exception as e:
                    last_err = e
                    # "200 Type set to I", broken pipe, aborted transfer: the control
                    # channel is out of step. Rebuild it and try this file again.
                    try: ftp.close()
                    except Exception: pass
                    time.sleep(2 * attempt)
                    try:
                        ftp = connect()
                    except Exception as ce:
                        last_err = ce
                        break
            if last_err is None:
                st["uploaded"].append(name); st["failed"].pop(name, None); ok += 1
                print(f"  OK   [{i}/{len(todo)}] {name}")
            else:
                st["failed"][name] = f"{type(last_err).__name__}: {last_err}"; fail += 1
                print(f"  FAIL [{i}/{len(todo)}] {name} — {last_err}")
            save_state(a.agency, st)
            time.sleep(a.delay)
        print(f"\ndone: {ok} uploaded, {fail} failed")
    finally:
        try: ftp.quit()
        except Exception: ftp.close()


if __name__ == "__main__":
    main()
