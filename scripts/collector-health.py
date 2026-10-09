#!/usr/bin/env python3
"""One-screen health check for the daily collectors.

Installed as a local copy at ~/.purplelink/collector-health.py so it still runs, and
says so, when the external SSD is not mounted.

  python3 collector-health.py             # print the table, write ~/.purplelink/collector-health.json
  python3 collector-health.py --notify    # also post one macOS notification per new problem per day

Checks, read-only:
  * photo stats (stats-collect.py): last day recorded, platforms failing two days or more
  * traffic dashboard: last good run, how old its data is
  * marketplaces (Etsy, Payhip, Gumroad): per-site age and status
  * launchd jobs: loaded, and last exit code
  * the SSD itself
The daily-update task reads collector-health.json, so a dead collector shows up in the
morning report instead of as a quiet gap.
"""
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
VOL = Path("/Volumes/Extreme SSD/Purplelink LLC")
PHOTO_HISTORY = VOL / "photo-licensing-workspace" / "stats" / "history.json"
TRAFFIC = HOME / ".purplelink" / "traffic"
OUT = HOME / ".purplelink" / "collector-health.json"
STATE = HOME / ".purplelink" / "collector-health-state.json"

# label -> what it collects. Only jobs that produce data for the business.
JOBS = {
    "llc.purplelink.photostats": "photo stats sweep",
    "com.benampel.purplelink-traffic.daily": "traffic dashboard",
    "com.purplelink.subscriber-tracking": "subscriber tracking (Mondays)",
    "com.purplelink.muscleonglp-tiktok": "MuscleOnGLP TikTok",
    "com.tiktokpipeline.daily": "TikTok pipeline",
    "com.socialgrowth.streamanalytics": "stream analytics",
    "com.benampel.home-backup": "home backup",
}
STALE_H = 36
now = dt.datetime.now()
problems = []          # (key, message)
rows = []              # (area, status, detail)


def add(area, status, detail, key=None):
    rows.append((area, status, detail))
    if status != "ok":
        problems.append((key or area, f"{area}: {detail}"))


def age_h(ts):
    return (now - ts).total_seconds() / 3600


# --- SSD
ssd = VOL.exists()
add("SSD", "ok" if ssd else "DOWN", "mounted" if ssd else "Extreme SSD is not mounted; photo stats and the repo scripts cannot run")

# --- photo stats
if ssd and PHOTO_HISTORY.exists():
    try:
        hist = json.loads(PHOTO_HISTORY.read_text())
        last = hist[-1]
        d = dt.date.fromisoformat(last["date"])
        days_old = (now.date() - d).days
        oks = sorted(k for k, v in last["platforms"].items() if v.get("ok"))
        status = "ok" if days_old == 0 else ("late" if days_old == 1 and now.hour < 10 else "STALE")
        add("photo stats", status, f"last day {last['date']} ({days_old}d old), {len(oks)} of {len(last['platforms'])} platforms read")
        # platforms failing in each of the last two recorded days
        streak = {}
        for h in hist[-3:][::-1]:
            for k, v in h["platforms"].items():
                if v.get("ok"):
                    streak.setdefault(k, None)
                elif streak.get(k, 0) is not None:
                    streak[k] = streak.get(k, 0) + 1
        bad = sorted(k for k, n in streak.items() if n and n >= 2)
        if bad:
            add("photo platforms", "FAILING", "failing 2+ days: " + ", ".join(bad), key="photo-platforms:" + ",".join(bad))
        else:
            add("photo platforms", "ok", "no platform failing two days running")
        lr = VOL / "photo-licensing-workspace" / "stats" / "last-run.json"
        if lr.exists():
            s = json.loads(lr.read_text())
            add("last sweep", "ok" if s["ok"] else "FAILING",
                f"{s['date']}: {len(s['ok'])} ok, {len(s['failed'])} failed, {s['seconds']}s, network wait {s['network_wait_s']}s")
    except Exception as e:
        add("photo stats", "ERROR", f"{type(e).__name__}: {e}")
else:
    add("photo stats", "ERROR" if ssd else "unknown", "history.json not readable")

# --- traffic dashboard
try:
    h = json.loads((TRAFFIC / "history.json").read_text())
    t = dt.datetime.fromisoformat(h["lastRun"]).astimezone().replace(tzinfo=None)
    a = age_h(t)
    add("traffic dashboard", "ok" if a < STALE_H else "STALE", f"last run {t:%Y-%m-%d %H:%M} ({a:.0f}h ago)")
except Exception as e:
    add("traffic dashboard", "ERROR", f"{type(e).__name__}: {e}")

# --- marketplaces
try:
    m = json.loads((TRAFFIC / "marketplaces.json").read_text())
    for site, st in m.get("status", {}).items():
        asof = m.get("asOf", {}).get(site)
        a = age_h(dt.datetime.fromisoformat(asof).astimezone().replace(tzinfo=None)) if asof else 9999
        ok = st == "ok" and a < STALE_H
        add(f"marketplace {site}", "ok" if ok else "FAILING", f"{st}; last good read {a:.0f}h ago" if a < 9000 else f"{st}; never read")
except Exception as e:
    add("marketplaces", "ERROR", f"{type(e).__name__}: {e}")

# --- launchd
uid = subprocess.run(["id", "-u"], capture_output=True, text=True).stdout.strip()
for label, what in JOBS.items():
    out = subprocess.run(["launchctl", "print", f"gui/{uid}/{label}"], capture_output=True, text=True)
    if out.returncode != 0:
        add(f"job {what}", "NOT LOADED", label)
        continue
    code = next((l.split("=")[1].strip() for l in out.stdout.splitlines() if "last exit code" in l), "?")
    runs = next((l.split("=")[1].strip() for l in out.stdout.splitlines() if l.startswith("\truns =")), "?")
    if code in ("0", "(never exited)"):
        add(f"job {what}", "ok", f"last exit {code}, {runs} runs")
    else:
        add(f"job {what}", "FAILING", f"last exit {code}, {runs} runs", key=f"job:{label}:{code}")

# --- report
width = max(len(r[0]) for r in rows)
print(f"collector health, {now:%Y-%m-%d %H:%M}")
for area, status, detail in rows:
    print(f"  {area:<{width}}  {status:<9} {detail}")
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({"checked": now.isoformat(timespec="seconds"),
                           "problems": [m for _, m in problems],
                           "rows": [{"area": a, "status": s, "detail": d} for a, s, d in rows]}, indent=2))

# --- notify, once per problem per day
if "--notify" in sys.argv and problems:
    try:
        seen = json.loads(STATE.read_text())
    except Exception:
        seen = {}
    today = now.strftime("%Y-%m-%d")
    fresh = [(k, m) for k, m in problems if seen.get(k) != today]
    if fresh:
        text = "; ".join(m for _, m in fresh)[:230].replace('"', "'")
        subprocess.run(["osascript", "-e", f'display notification "{text}" with title "Purplelink collectors need attention"'],
                       capture_output=True)
        for k, _ in fresh:
            seen[k] = today
        STATE.write_text(json.dumps(seen))
sys.exit(1 if problems else 0)
