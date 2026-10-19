"""`social.py daily ...`: the daily pick, the metrics collector and the weekly report."""
from __future__ import annotations

import datetime as dt

from .. import config as cfgmod
from .. import paths, sysutil
from ..errors import EXIT_FAILED, EXIT_OK
from . import lib219, learn, metrics, pipeline
from . import settings as st


def show(res: dict, say=print) -> None:
    say(f"status: {res['status']}")
    if "candidate" in res:
        say(f"pick: {res['candidate']}  kind {res['kind']}  format {res['format']}  score {res['score']}")
        say(f"item: {res['item']}  scheduled {res['scheduled_at']}  platforms {', '.join(res['platforms'])}")
        for p, t in res["texts"].items():
            say(f"\n--- {p} ({len(t)} chars)\n{t}")
        for im in res["images"]:
            say(f"  [image] {im['path']}\n          alt: {im['alt']}  ({', '.join(im['platforms'])})")
        say("\nnext best: " + ", ".join(f"{i} {s}" for s, i in res["top"][1:5]))
    for k in ("notes", "excluded"):
        for n in res.get(k, []):
            say(f"  {k}: {n}")


def cmd_daily(a, cfg) -> int:
    http = lib219.Http()
    dcfg = st.load()
    if a.what == "run":
        if not a.dry_run:
            st.write_default()
        res = pipeline.run_daily(http, dcfg, cfg, dry_run=a.dry_run, force=a.force)
        if a.dry_run or res["status"] not in ("too-early", "done-already"):  # launchd calls this every 15 minutes
            show(res)
        return EXIT_OK
    if a.what == "metrics":
        return cmd_metrics(http, dcfg, cfg, force_weekly=a.force)
    if a.what == "weekly":
        return cmd_metrics(http, dcfg, cfg, force_weekly=True, collect=False)
    return EXIT_FAILED


def cmd_metrics(http, dcfg, cfg, force_weekly=False, collect=True, notify=None, today=None) -> int:
    notify = notify or sysutil.notify
    today = today or pipeline.local_now(dcfg).date()
    if collect:
        d = metrics.collect(http, cfg, today)
        sysutil.log(f"metrics: collected {today}; notes: {'; '.join(d['notes'][-2:]) or 'none'}")
    else:
        d = metrics.load()
    state = st.read_json(pipeline.state_file(), {})
    week = f"{today.isocalendar().year}-W{today.isocalendar().week:02d}"
    if force_weekly or state.get("last_weekly") != week:
        text, _ = learn.run_weekly(d, today, dcfg)
        bd = paths.briefs_dir()
        if not bd.is_dir():
            sysutil.log("weekly report: docs/growth-briefs is not mounted; retrying at the next run")
            return EXIT_OK
        out = bd / f"social-weekly-{today.isoformat()}.md"
        out.write_text(text, encoding="utf-8")
        state["last_weekly"] = week
        st.write_json(pipeline.state_file(), state)
        sysutil.log(f"weekly report written: {out}")
        notify(f"Social weekly report ready: {out.name}")
    return EXIT_OK
