#!/usr/bin/env python3
"""Rebuild ~/.purplelink/traffic/dashboard.html from what is already on disk (no network).

The photography and TikTok dashboards are embedded as tabs in the traffic dashboard, so each of
their generators calls this when it finishes writing its own page:

    python3 scripts/traffic-dashboard/rebuild_hook.py photography

Safe to call from anywhere, any number of times, and it never raises:
  - one rebuild runs at a time (flock); a call that arrives while one is running leaves a "dirty"
    flag, and the running rebuild goes round once more so the newest file is picked up;
  - set PURPLELINK_NO_REBUILD=1 to skip (so a rebuild can never trigger itself);
  - the rebuild's output goes to ~/.purplelink/traffic/rebuild.log, not to the caller.
"""
import datetime
import fcntl
import os
import subprocess
import sys
from pathlib import Path

TRAFFIC = Path(os.environ.get("PURPLELINK_TRAFFIC_DIR") or Path.home() / ".purplelink" / "traffic")
SCRIPT = Path(__file__).resolve().parent / "traffic_dashboard.py"
PY312 = "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
LOCK = TRAFFIC / ".rebuild.lock"
DIRTY = TRAFFIC / ".rebuild.dirty"
LOG = TRAFFIC / "rebuild.log"
MAX_ROUNDS = 3
TIMEOUT = 300


def log(msg):
    try:
        with open(LOG, "a") as f:
            f.write("%s %s\n" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg))
    except OSError:
        pass


def main(argv):
    reason = argv[1] if len(argv) > 1 else "unspecified"
    if os.environ.get("PURPLELINK_NO_REBUILD"):
        return 0
    try:
        TRAFFIC.mkdir(parents=True, exist_ok=True)
        lock = open(LOCK, "w")
    except OSError:
        return 0
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        DIRTY.touch()
        log("busy, queued another round (%s)" % reason)
        return 0
    python = PY312 if os.path.exists(PY312) else sys.executable
    env = dict(os.environ, PURPLELINK_NO_REBUILD="1")
    for round_no in range(1, MAX_ROUNDS + 1):
        try:
            DIRTY.unlink()
        except OSError:
            pass
        try:
            r = subprocess.run([python, str(SCRIPT), "--no-fetch"], capture_output=True, text=True,
                               timeout=TIMEOUT, env=env)
            log("rebuilt after %s (round %d, exit %d)" % (reason, round_no, r.returncode))
            if r.returncode != 0:
                log((r.stderr or "")[-400:].replace("\n", " | "))
        except Exception as e:  # noqa: BLE001 - a failed rebuild must never break the caller
            log("rebuild failed after %s: %s" % (reason, e))
            break
        if not DIRTY.exists():
            break
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Exception:  # noqa: BLE001
        sys.exit(0)
