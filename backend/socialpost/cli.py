"""social.py: the command line. Holds no private data; see docs/social-posting.md."""
from __future__ import annotations

import argparse
import subprocess
import sys

from . import config as cfgmod
from . import engine, items as itemsmod, paths, sysutil
from .errors import EXIT_FAILED, EXIT_NOTHING, EXIT_OK, EXIT_REFUSED, EXIT_SESSION, Refused, SessionExpired
from .spec import PLATFORMS, SPEC
from .text import measure


def _item(arg: str):
    try:
        return itemsmod.find(arg)
    except KeyError as e:
        raise SystemExit(str(e))


def cmd_new(a, cfg) -> int:
    plats = [p.strip() for p in a.platforms.split(",") if p.strip()] if a.platforms else None
    it = itemsmod.create(a.slug, plats, a.link or "", a.campaign or "", a.at)
    print(f"created {it.path}\nEdit it, then: social.py validate {it.id}")
    return EXIT_OK


def cmd_validate(a, cfg) -> int:
    targets = itemsmod.list_items() if a.all or not a.id else [_item(a.id)]
    bad = 0
    for it in targets:
        if it.status in ("posted", "cancelled") and not a.id:
            continue
        errors, warnings = itemsmod.validate(it, cfg)
        print(f"{it.id}  [{it.status}]  {'OK' if not errors else 'ERRORS'}")
        for e in errors:
            print(f"  error:   {e}")
        for w in warnings:
            print(f"  warning: {w}")
        bad += bool(errors)
    return EXIT_FAILED if bad else EXIT_OK


def cmd_preview(a, cfg) -> int:
    it = _item(a.id)
    print(f"{it.id}  [{it.status}]  scheduled {it.meta.get('scheduled_at')}  campaign {it.campaign}")
    for p in it.platforms:
        if a.platform and p != a.platform:
            continue
        txt = it.render(p)
        spec = SPEC[p]
        print(f"\n--- {p} ({measure(txt, spec['count'])}/{spec['text']} {spec['count']}) "
              f"{'ENABLED' if cfgmod.platform_cfg(cfg, p).get('enabled') else 'disabled'}")
        print(txt)
        for im in it.images_for(p):
            print(f"  [image] {im['path']}\n          alt: {im.get('alt')}")
        if p == "linkedin" and it.document():
            print(f"  [document] {it.document()['path']} titled {it.document()['title']!r}")
    return EXIT_OK


def cmd_approve(a, cfg) -> int:
    it = _item(a.id)
    try:
        itemsmod.approve(it, cfg, "ben")
    except ValueError as e:
        print(e)
        return EXIT_FAILED
    print(f"approved {it.id} by ben at {it.meta['approved_at']}; goes out at {it.meta['scheduled_at']} "
          f"(editing it voids the approval)")
    return EXIT_OK


def cmd_cancel(a, cfg) -> int:
    it = _item(a.id)
    try:
        itemsmod.cancel(it)
    except ValueError as e:
        print(e)
        return EXIT_FAILED
    print(f"cancelled {it.id}")
    return EXIT_OK


def cmd_post(a, cfg) -> int:
    it = _item(a.id)
    errors, _ = itemsmod.validate(it, cfg)
    if errors:
        print("not posting; fix these first:\n  " + "\n  ".join(errors))
        return EXIT_FAILED
    if not a.dry_run:
        ok, why = it.approval_valid()
        if not ok:
            print(f"not posting: {why}. Run: social.py approve {it.id}")
            return EXIT_FAILED
    targets = [a.platform] if a.platform else it.platforms
    code = EXIT_OK
    for p in targets:
        if p not in it.platforms:
            print(f"{p} is not in this item's platforms")
            return EXIT_FAILED
        if not cfgmod.platform_cfg(cfg, p).get("enabled"):
            print(f"{p}: disabled in config; skipped")
            continue
        try:
            r = engine.post_platform(it, p, cfg, dry_run=a.dry_run)
            print(f"{p}: {r.get('status')} {r.get('url') or r.get('detail') or ''}")
        except Refused as e:
            sysutil.notify(f"REFUSED {p}: wrong account. Nothing posted.")
            print(f"{p}: REFUSED {e}")
            return EXIT_REFUSED
        except SessionExpired as e:
            print(f"{p}: {e}")
            code = EXIT_SESSION
        except Exception as e:
            print(f"{p}: FAILED {type(e).__name__}: {e}")
            code = EXIT_FAILED
    if not a.dry_run and not engine._pending_platforms(it):
        engine.finish_item(it, cfg, print, sysutil.notify)
    return code


def cmd_run_due(a, cfg) -> int:
    engine.run_due(cfg)
    return EXIT_OK


def cmd_status(a, cfg) -> int:
    print(f"PAUSE: {'ON (nothing will post)' if paths.pause_file().exists() else 'off'}")
    print(f"queue: {paths.queue_dir()}")
    print("platforms: " + ", ".join(f"{p}={'on' if cfgmod.platform_cfg(cfg, p).get('enabled') else 'off'}" for p in PLATFORMS))
    for it in itemsmod.list_items():
        print(f"\n{it.id}  [{it.status}]  {it.meta.get('scheduled_at')}  {','.join(it.platforms)}")
        for p, r in it.results.items():
            print(f"    {p}: {r.get('status')} {r.get('url') or str(r.get('error') or '')[:100]}")
    return EXIT_OK


def cmd_whoami(a, cfg) -> int:
    rc = EXIT_OK
    for p, (state, msg) in engine.whoami_all(cfg).items():
        if a.platform and p != a.platform:
            continue
        print(f"{p:9s} {state:11s} {msg}")
        if state == "REFUSED":
            sysutil.notify(f"whoami: {p} is not the expected account")
            rc = EXIT_REFUSED
        elif state in ("session", "error") and rc == EXIT_OK:
            rc = EXIT_SESSION if state == "session" else EXIT_FAILED
    return rc


def cmd_setup(a, cfg) -> int:
    from .setup import setup
    return setup(a.platform)


def cmd_refresh(a, cfg) -> int:
    from .setup import note_token_time
    ad = engine.build_adapter(cfg, a.platform)
    ad.refresh()
    note_token_time(a.platform)
    print(f"{a.platform}: token refreshed")
    return EXIT_OK


def cmd_pause(a, cfg) -> int:
    paths.home().mkdir(parents=True, exist_ok=True)
    paths.pause_file().touch()
    print(f"paused: {paths.pause_file()} exists")
    return EXIT_OK


def cmd_resume(a, cfg) -> int:
    paths.pause_file().unlink(missing_ok=True)
    print("resumed")
    return EXIT_OK


def cmd_daily(a, cfg) -> int:
    from .daily.cmd import cmd_daily as run
    return run(a, cfg)


def cmd_instagram(a, cfg) -> int:
    from .instagram.cmd import cmd_instagram as run
    return run(a, cfg)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="social.py", description="Purplelink company-account social posting")
    sp = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_):
        p = sp.add_parser(name, help=help_)
        p.set_defaults(fn=fn)
        return p

    p = add("new", cmd_new, "create a draft from the template")
    p.add_argument("slug")
    p.add_argument("--platforms", help="comma list, default linkedin,bluesky")
    p.add_argument("--link")
    p.add_argument("--campaign")
    p.add_argument("--at", help="scheduled_at, ISO 8601 with offset")
    p = add("validate", cmd_validate, "check limits, images, alt text, link and UTM")
    p.add_argument("id", nargs="?")
    p.add_argument("--all", action="store_true")
    p = add("preview", cmd_preview, "show what each platform will receive")
    p.add_argument("id")
    p.add_argument("--platform", choices=PLATFORMS)
    p = add("approve", cmd_approve, "approve an item (records approved_by: ben)")
    p.add_argument("id")
    p = add("cancel", cmd_cancel, "cancel an item")
    p.add_argument("id")
    p = add("post", cmd_post, "post one item now (needs approval unless --dry-run)")
    p.add_argument("id")
    p.add_argument("--platform", choices=PLATFORMS)
    p.add_argument("--dry-run", action="store_true")
    add("run-due", cmd_run_due, "post approved items that are due (the scheduler calls this)")
    add("status", cmd_status, "queue, results and platform switches")
    p = add("whoami", cmd_whoami, "check the identity of every configured account; posts nothing")
    p.add_argument("platform", nargs="?", choices=PLATFORMS)
    p = add("setup", cmd_setup, "guided setup for one platform (Ben runs this in his own terminal)")
    p.add_argument("platform", choices=("threads", "mastodon", "x", "bluesky", "instagram", "facebook"))
    p = add("refresh", cmd_refresh, "renew a token (threads, x, instagram)")
    p.add_argument("platform", choices=("threads", "x", "instagram"))
    p = add("daily", cmd_daily, "daily ranked pipeline: run (pick, vet, queue), metrics, weekly")
    p.add_argument("what", choices=("run", "metrics", "weekly"))
    p.add_argument("--dry-run", action="store_true", help="run: show today's pick, write nothing")
    p.add_argument("--force", action="store_true", help="run: ignore the time of day and done-today; metrics: redo the weekly report")
    p = add("instagram", cmd_instagram, "Instagram Reels and LinkedIn companions: reel-add, run, scan, preview")
    p.add_argument("what", choices=("reel-add", "run", "scan", "preview"))
    p.add_argument("--video", help="reel-add: the video file (9:16 is used as is; 16:9 is padded to 9:16)")
    p.add_argument("--youtube-id", help="reel-add: the YouTube video id this Reel comes from")
    p.add_argument("--title", help="reel-add: the YouTube title")
    p.add_argument("--description-file", help="reel-add: a file holding the YouTube description")
    p.add_argument("--link", help="reel-add: the purplelink.llc page the video is about (bare, no UTM)")
    p.add_argument("--utm-content", default="", help="reel-add: this Reel's own tag (howto-publish.py passes the "
                   "one the marketing hub gave it); without it the hub makes one")
    p.add_argument("--also", default="", help="reel-add: other YouTube ids this Reel covers (the long cut of a Short)")
    p.add_argument("--dry-run", action="store_true", help="run/preview: build and show, queue nothing")
    p.add_argument("--out", help="preview: folder for the rendered Reel and image")
    add("pause", cmd_pause, "create the PAUSE file: the scheduler posts nothing")
    add("resume", cmd_resume, "remove the PAUSE file")
    return ap


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    cfg = cfgmod.load()
    return a.fn(a, cfg)
