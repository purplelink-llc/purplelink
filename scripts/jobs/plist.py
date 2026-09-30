#!/usr/bin/env python3
"""Generate a launchd plist for a job. Writes the file only; never loads it."""
from __future__ import annotations

import argparse
import json
import os
import plistlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent


def jobs_dir() -> Path:
    return Path(os.environ.get("PURPLELINK_JOBS") or Path.home() / ".purplelink" / "jobs")


def build_plist(spec: dict, *, daemon: bool = False, user: str | None = None, repo: Path = REPO,
                jobs: Path | None = None) -> dict:
    jobs = jobs or jobs_dir()
    name = spec["name"]
    sched = spec.get("schedule") or {}
    times = []
    days = sched.get("weekdays")
    base = {"Hour": int(sched.get("hour", 0)), "Minute": int(sched.get("minute", 0))}
    for d in (days or [None]):
        t = dict(base)
        if d is not None:
            t["Weekday"] = int(d) % 7  # launchd: 0 and 7 are Sunday; job.json uses 1..7
        times.append(t)
    data = {
        "Label": f"llc.purplelink.job.{name}",
        "ProgramArguments": ["/usr/bin/env", "python3", str(repo / "scripts" / "jobs" / "runner.py"), "run", name],
        "WorkingDirectory": str(repo),
        "StartCalendarInterval": times if len(times) > 1 else times[0],
        "StandardOutPath": str(jobs / "logs" / f"{name}.out.log"),
        "StandardErrorPath": str(jobs / "logs" / f"{name}.err.log"),
        "EnvironmentVariables": {"PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
                                 "PURPLELINK_JOBS": str(jobs)},
    }
    if daemon:
        data["UserName"] = user or os.environ.get("USER", "purplelink")
    return data


def write_plist(spec: dict, out_dir: Path | None = None, **kw) -> Path:
    data = build_plist(spec, **kw)
    out_dir = Path(out_dir) if out_dir else jobs_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / (data["Label"] + ".plist")
    with open(path, "wb") as f:
        plistlib.dump(data, f)
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("job")
    ap.add_argument("--daemon", action="store_true", help="LaunchDaemon variant with a UserName key")
    ap.add_argument("--user")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    spec = json.loads((HERE / "jobs" / a.job / "job.json").read_text())
    path = write_plist(spec, a.out, daemon=a.daemon, user=a.user)
    print(path)
    print("written only; load it yourself (see README)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
