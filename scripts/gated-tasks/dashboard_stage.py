#!/usr/bin/env python3
"""Stage, hand over and record dashboard builds (2026-11-07). Installed as ~/.purplelink/bin/dashboard_stage.py.

The Artifact publish needs the Artifact tool, which only the Claude desktop app has reliably (headless `claude -p` from
launchd lacked it on 11-06 and 11-07, so the dashboard went stale while the jobs logged "done"). So the work is split:

    stage    build the page into a side folder, check it, swap it in as ~/.purplelink/traffic/live-build under
             .export.lock, then write publish-pending.json. Used by dashboard-refresh.sh (nightly) and forecast_watch.py.
    prep     for the desktop task dashboard-live-publish: copy live-build to DEST under the lock, check the copy against
             the staged tree hash, print the buildId and the `files` map for the Artifact publish.
    record   after a successful publish: published.json, last-published.html, publish-status.json, and remove
             publish-pending.json only if its buildId is unchanged.
    watchdog exit 1 with a reason when a staged build missed a publish slot or nothing was published for 30 hours.

Exit codes: 0 ok, 1 error, 3 nothing staged (prep), 4 export lock held (prep), 5 copy did not match the staged build.
Never deletes anything except its own fixed folders under ~/.purplelink/traffic (.live-build.new, .live-build.old) and
publish-pending.json.
"""
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

T = Path.home() / ".purplelink/traffic"
X = T / "artifact-export"
LOCK = T / ".export.lock"
LIVE = T / "live-build"
NEW = T / ".live-build.new"
OLD = T / ".live-build.old"
PENDING = T / "publish-pending.json"
STATUS = T / "publish-status.json"
PUBLISHED = X / "published.json"
LAST = X / "last-published.html"
DATASETS = X / "page/datasets.json"
BUILD = X / "page/build_page.sh"
SLOTS = (5, 11, 15, 19)          # desktop task dashboard-live-publish, US Eastern (cron 0 5,11,15,19 * * *)
STALE_HOURS = 30


def now():
    return dt.datetime.now(dt.timezone.utc)


def write_json(path, obj):
    tmp = path.with_name("." + path.name + ".tmp")
    tmp.write_text(json.dumps(obj, separators=(",", ":"), default=str))
    os.replace(tmp, path)


def read_json(path, default=None):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_sha(root):
    """One hash over every file's relative path and content, so a half-copied or half-built folder never matches."""
    h = hashlib.sha256()
    for f in sorted(p for p in root.rglob("*") if p.is_file()):
        h.update(f.relative_to(root).as_posix().encode() + b"\0" + sha(f).encode() + b"\n")
    return h.hexdigest()


def take_lock(wait_s):
    """mkdir lock shared with export_all.sh and forecast_watch.py. A lock older than 3 hours is a crashed holder."""
    end = time.time() + wait_s
    while True:
        try:
            LOCK.mkdir()
            return True
        except FileExistsError:
            try:
                if time.time() - LOCK.stat().st_mtime > 3 * 3600:
                    LOCK.touch()
                    return True
            except FileNotFoundError:
                continue
            if time.time() >= end:
                return False
            time.sleep(5)


def drop_lock():
    try:
        LOCK.rmdir()
    except OSError:
        pass


def rm_fixed(path):
    # Only the two fixed side folders are ever removed.
    if path in (NEW, OLD) and path.exists():
        shutil.rmtree(path)


def verify_build(root):
    ids = list(json.loads(DATASETS.read_text()))
    idx = root / "index.html"
    if not idx.is_file() or idx.stat().st_size < 10000:
        raise RuntimeError("index.html missing or too small")
    missing, bad = [], []
    for i in ids:
        f = root / "data" / f"{i}.json"
        if not f.is_file():
            missing.append(i)
            continue
        try:
            json.loads(f.read_text())
        except ValueError:
            bad.append(i)
    if bad:
        raise RuntimeError("data files that do not parse: " + ", ".join(bad))
    allj = read_json(root / "data/all.json")
    if not isinstance(allj, dict):
        raise RuntimeError("data/all.json missing or unreadable")
    return missing


def cmd_stage(args):
    held = "--lock-held" in args
    orders = int(args[args.index("--new-orders") + 1]) if "--new-orders" in args else 0
    source = args[args.index("--source") + 1] if "--source" in args else "manual"
    suffix = args[args.index("--id-suffix") + 1] if "--id-suffix" in args else source
    if held and not LOCK.exists():
        print("stage: --lock-held given but no lock exists", file=sys.stderr)
        return 1
    rm_fixed(NEW)
    NEW.mkdir(parents=True)
    r = subprocess.run(["bash", str(BUILD), str(NEW)], capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        print(f"stage: build_page.sh exited {r.returncode}: {r.stderr[-300:]}", file=sys.stderr)
        return 1
    try:
        missing = verify_build(NEW)
    except (RuntimeError, OSError, ValueError) as e:
        print(f"stage: build check failed: {e}", file=sys.stderr)
        return 1
    if missing:  # build_page.sh carries these on the page as "missing"; the page copes, so warn, do not fail
        print("stage: no file for dataset(s): " + ", ".join(missing), file=sys.stderr)
    if not held and not take_lock(600):
        print("stage: export lock still held after 10 minutes", file=sys.stderr)
        return 1
    try:
        rm_fixed(OLD)
        if LIVE.exists():
            os.rename(LIVE, OLD)
        os.rename(NEW, LIVE)
        rm_fixed(OLD)
        t = now()
        prev = read_json(PENDING, {}) or {}
        build_id = t.strftime("%Y%m%dT%H%M%SZ") + "-" + suffix
        write_json(PENDING, {"buildId": build_id, "builtAt": t.isoformat(timespec="minutes"), "sha256": sha(LIVE / "index.html"),
                             "treeSha256": tree_sha(LIVE), "stagingPath": str(LIVE), "source": source,
                             "newOrders": orders + int(prev.get("newOrders") or 0)})
    finally:
        if not held:
            drop_lock()
    print(build_id)
    return 0


def cmd_prep(args):
    if len(args) != 1:
        print("usage: prep DEST (a folder that does not exist yet, inside the session scratchpad)", file=sys.stderr)
        return 1
    dest = Path(args[0]).expanduser()
    if dest.exists():
        print(f"prep: {dest} already exists; pass a new folder", file=sys.stderr)
        return 1
    pend = read_json(PENDING)
    if not pend:
        print("NOTHING_STAGED")
        return 3
    if not take_lock(300):
        print("EXPORT_RUNNING")
        return 4
    try:
        pend = read_json(PENDING)          # re-read under the lock: a stage may have swapped in a newer build
        if not pend or not LIVE.is_dir():
            print("NOTHING_STAGED")
            return 3
        shutil.copytree(LIVE, dest)
    finally:
        drop_lock()
    want = pend.get("treeSha256")
    got = tree_sha(dest) if want else sha(dest / "index.html")
    if got != (want or pend.get("sha256")):
        print("prep: copy does not match the staged build", file=sys.stderr)
        return 5
    files = {f"data/{p.name}": f"data/{p.name}" for p in sorted((dest / "data").glob("*.json"))}
    print(json.dumps({"buildId": pend["buildId"], "builtAt": pend.get("builtAt"), "root": str(dest),
                      "file_path": str(dest / "index.html"), "files": files}))
    return 0


def cmd_record(args):
    if len(args) < 2:
        print("usage: record BUILD_ID DEST [VERSION]", file=sys.stderr)
        return 1
    build_id, dest = args[0], Path(args[1]).expanduser()
    version = args[2] if len(args) > 2 else None
    if not (dest / "index.html").is_file():
        print(f"record: {dest}/index.html not found", file=sys.stderr)
        return 1
    old = read_json(PUBLISHED, {}) or {}
    new = {p.stem: sha(p) for p in sorted((dest / "data").glob("*.json"))}
    write_json(PUBLISHED, new)
    tmp = LAST.with_name("." + LAST.name + ".tmp")
    shutil.copyfile(dest / "index.html", tmp)
    os.replace(tmp, LAST)
    pend = read_json(PENDING)
    removed = bool(pend and pend.get("buildId") == build_id)
    if removed:
        PENDING.unlink()
    write_json(STATUS, {"lastSuccessAt": now().isoformat(timespec="minutes"), "buildId": build_id, "version": version})
    changed = sorted(k for k in new if old.get(k) != new[k])
    print(f"recorded {build_id}; {len(changed)} of {len(new)} datasets changed; pending "
          + ("cleared" if removed else "kept (a newer build was staged meanwhile)"))
    return 0


def last_slot(t_local):
    for back in range(0, 3):
        day = t_local.date() - dt.timedelta(days=back)
        for h in sorted(SLOTS, reverse=True):
            s = dt.datetime.combine(day, dt.time(h), t_local.tzinfo)
            if s <= t_local:
                return s
    return None


def cmd_watchdog(_args):
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("America/New_York")
    except Exception:
        tz = dt.datetime.now().astimezone().tzinfo
    t = dt.datetime.now(tz)
    problems = []
    pend = read_json(PENDING)
    if pend:
        try:
            built = dt.datetime.fromisoformat(pend["builtAt"]).astimezone(tz)
        except (KeyError, ValueError):
            built = dt.datetime.fromtimestamp(PENDING.stat().st_mtime, tz)
        slot = last_slot(t)
        if slot and built < slot:
            problems.append(f"build {pend.get('buildId')} staged {built:%m-%d %H:%M} missed the {slot:%H:%M} publish slot")
    st = read_json(STATUS) or {}
    try:
        last = dt.datetime.fromisoformat(st["lastSuccessAt"]).astimezone(tz)
    except (KeyError, ValueError):
        last = dt.datetime.fromtimestamp(PUBLISHED.stat().st_mtime, tz) if PUBLISHED.exists() else None
    if last is None or (t - last).total_seconds() > STALE_HOURS * 3600:
        problems.append("no dashboard publish since " + (f"{last:%m-%d %H:%M}" if last else "ever"))
    if problems:
        print("; ".join(problems))
        return 1
    print(f"ok; last publish {last:%m-%d %H:%M}" + (f"; {pend.get('buildId')} waiting for the next slot" if pend else ""))
    return 0


def main(argv):
    cmds = {"stage": cmd_stage, "prep": cmd_prep, "record": cmd_record, "watchdog": cmd_watchdog}
    if len(argv) < 2 or argv[1] not in cmds:
        print(__doc__)
        return 1
    return cmds[argv[1]](argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
