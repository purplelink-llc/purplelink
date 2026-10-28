"""`social.py instagram ...`

  reel-add --video F --youtube-id ID --title T [--description-file D] [--link URL] [--also ID2]
           make the 9:16 Reel for one Purplelink YouTube video and put it in the inbox (howto-publish.py and
           yt-api-upload.py call this; it never posts)
  run      queue what is due under the 2026-10-23 standing approval (the daily wrapper calls this every 15 minutes)
  scan     list Purplelink uploads of the last week that have no Reel; notifies once per video
  preview  the dry run: build the next Reel and the next companion image, vet them, copy them to --out, queue nothing
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from .. import paths
from ..daily import lib219
from ..errors import EXIT_FAILED, EXIT_OK
from . import pipeline


def cmd_instagram(a, cfg) -> int:
    http = lib219.Http()
    if a.what == "reel-add":
        if not (a.video and a.youtube_id and a.title):
            print("reel-add needs --video, --youtube-id and --title")
            return EXIT_FAILED
        desc = Path(a.description_file).read_text(encoding="utf-8") if a.description_file else ""
        e = pipeline.reel_add(Path(a.video), a.youtube_id, a.title, desc, a.link or "",
                              [x for x in a.also.split(",") if x.strip()], utm_content=a.utm_content)
        print(f"Reel ready: {pipeline.reels_dir() / e['youtube_id'] / 'reel.mp4'} ({e['duration']} s)")
        return EXIT_OK
    if a.what == "run":
        res = pipeline.run(http, cfg)
        if res["status"] == "ok" and (res["queued"] or res["skipped"]):
            print(f"instagram: queued {len(res['queued'])}, skipped {len(res['skipped'])}")
        if dt.datetime.now().hour >= 12:    # once a day is enough for the channel check
            st = pipeline.read_state()
            today = dt.date.today().isoformat()
            if st.get("last_scan") != today and res["status"] == "ok":
                pipeline.scan(http, cfg)
                st = pipeline.read_state()
                st["last_scan"] = today
                pipeline.write_state(st)
        return EXIT_OK
    if a.what == "scan":
        pipeline.scan(http, cfg)
        return EXIT_OK
    if a.what == "preview":
        return preview(http, cfg, Path(a.out) if a.out else paths.instagram_dir() / "preview")
    return EXIT_FAILED


def preview(http, cfg, out: Path, say=print) -> int:
    res = pipeline.run(http, cfg, dry_run=True, say=say)
    for item in res["would_queue"]:
        files = pipeline.copy_preview(item, out)
        say(f"\n=== {item.id}  ({item.meta['instagram']['kind']}, would go out {item.meta['scheduled_at']})")
        say(item.render("instagram"))
        v = item.video()
        if v:
            say(f"  [reel] {v['duration']} s {v['width']}x{v['height']}  description: {v['alt']}")
        for im in item.meta.get("images") or []:
            say(f"  [image] alt: {im['alt']}")
        say("  files: " + ", ".join(str(f) for f in files))
        say("  gate: PASSED")
    for key, why in res["skipped"]:
        say(f"\n--- {key}: would not be queued: " + " | ".join(why if isinstance(why, list) else [why]))
    if not res["would_queue"] and not res["skipped"]:
        say("nothing waiting: no recent LinkedIn post without a companion and no Reel in the inbox")
    return EXIT_OK
