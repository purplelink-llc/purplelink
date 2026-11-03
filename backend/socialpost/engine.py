"""Posting engine: adapter registry, one-item posting, and the scheduler pass (`run-due`)."""
from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import subprocess
import sys

from . import config as cfgmod
from . import items as itemsmod
from . import paths, sysutil
from .adapters.base import Adapter
from .errors import Ambiguous, Disabled, Refused, SessionExpired, SocialError
from .items import Item, iso, now

SEP_RE = "|"


def registry() -> dict[str, type[Adapter]]:
    from .adapters.bluesky import Bluesky
    from .adapters.facebook import Facebook
    from .adapters.instagram import Instagram
    from .adapters.linkedin import LinkedIn
    from .adapters.mastodon import Mastodon
    from .adapters.threads import Threads
    from .adapters.x import X
    return {"linkedin": LinkedIn, "bluesky": Bluesky, "threads": Threads, "mastodon": Mastodon, "x": X,
            "instagram": Instagram, "facebook": Facebook}


def build_adapter(cfg: dict, platform: str, factory=None, **kw) -> Adapter:
    pc = dict(cfgmod.platform_cfg(cfg, platform))
    pc["_root"] = cfg
    cls = (factory or registry())[platform]
    return cls(pc, **kw)


# ---------------------------------------------------------------- whoami
def whoami_all(cfg: dict, factory=None, **kw) -> dict[str, tuple[str, str]]:
    """Read-only identity check of every enabled platform. Returns {platform: (state, message)}; never posts."""
    out: dict[str, tuple[str, str]] = {}
    for p in itemsmod.PLATFORMS:
        if not cfgmod.platform_cfg(cfg, p).get("enabled"):
            out[p] = ("disabled", "disabled in config")
            continue
        try:
            a = build_adapter(cfg, p, factory, **kw)
            got = a.check_identity()
            out[p] = ("ok", ", ".join(f"{k}={v}" for k, v in got.items() if k in a.identity_keys.values()))
        except Refused as e:
            out[p] = ("REFUSED", str(e))
        except Disabled as e:
            out[p] = ("not set up", str(e))
        except SessionExpired as e:
            out[p] = ("session", str(e))
        except Exception as e:
            out[p] = ("error", f"{type(e).__name__}: {str(e)[:200]}")
    return out


# ---------------------------------------------------------------- one item
def _pending_platforms(item: Item) -> list[str]:
    return [p for p in item.platforms if item.results.get(p, {}).get("status") not in ("posted", "failed", "skipped", "refused")]


def post_platform(item: Item, platform: str, cfg: dict, factory=None, dry_run: bool = False, **kw):
    """Post one platform of one item and write the result back immediately. Returns the result dict."""
    res = item.results.setdefault(platform, {"status": "pending", "attempts": 0})
    if res.get("status") == "posted":
        return res  # never post a platform twice
    if res.get("status") == "posting":
        res.update(status="failed", error="a previous run stopped while posting; it may be live. Check the account")
        item.save()
        return res
    a = build_adapter(cfg, platform, factory, **kw)
    if dry_run:
        r = a.post(item, dry_run=True)
        return {"status": "dry-run", "detail": r.detail}
    res.update(status="posting", started_at=iso(now()), attempts=int(res.get("attempts", 0)) + 1)
    item.save()  # if this process dies after the platform accepted the post, the next run sees "posting", not "pending"
    try:
        r = a.post(item, dry_run=False)
    except Refused as e:
        res.update(status="refused", error=str(e))
        item.save()
        raise
    except SessionExpired as e:
        res.update(status="failed", error=str(e))
        item.save()
        raise
    except Ambiguous as e:
        res.update(status="failed", error=str(e), ambiguous=True)
        item.save()
        raise
    except Exception as e:
        res.update(status="pending", error=f"{type(e).__name__}: {str(e)[:300]}")
        item.save()
        raise
    attempts = res.get("attempts", 1)
    res.clear()
    res.update(status="posted", url=r.url, id=r.id, posted_at=iso(now()), error=None, verified=False, attempts=attempts)
    if r.detail:
        res["detail"] = r.detail
    item.save()
    try:
        res["verified"] = bool(a.verify(r.url))
    except Exception:
        res["verified"] = False
    item.save()
    return res


# ---------------------------------------------------------------- scheduler
@contextlib.contextmanager
def single_instance():
    paths.home().mkdir(parents=True, exist_ok=True)
    fh = open(paths.lock_file(), "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        yield False
        return
    try:
        yield True
    finally:
        fcntl.flock(fh, fcntl.LOCK_UN)
        fh.close()


def backoff(cfg: dict, attempts: int) -> dt.timedelta:
    steps = cfg["retry"]["backoff_minutes"]
    return dt.timedelta(minutes=steps[min(max(attempts, 1) - 1, len(steps) - 1)])


def run_due(cfg: dict | None = None, factory=None, when: dt.datetime | None = None, notify=None,
            finish=None, **kw) -> list[str]:
    """One scheduler pass. Returns log lines. Posts only approved, due, in-window, non-stale items."""
    cfg = cfg or cfgmod.load()
    when = when or now()
    notify = notify or sysutil.notify
    lines: list[str] = []

    def say(s: str) -> None:
        lines.append(s)
        sysutil.log(s)

    if paths.pause_file().exists():
        say("PAUSE file present: posting nothing")
        return lines
    with single_instance() as got:
        if not got:
            say("another run-due is running; skipping")
            return lines
        maybe_refresh_tokens(cfg, factory, say, when, kw)
        for item in sorted(itemsmod.list_items(), key=lambda i: str(i.meta.get("scheduled_at", ""))):
            if item.status != "approved":
                continue
            _process(item, cfg, factory, when, say, notify, finish or finish_item, kw)
    if not lines:
        say("nothing due")
    return lines


REFRESHED = ("threads", "instagram")


def maybe_refresh_tokens(cfg: dict, factory, say, when, kw) -> None:
    """Threads and Instagram tokens last 60 days; renew at 30. A failure is logged and notified, never fatal."""
    from .setup import note_token_time, token_age_days
    for plat in REFRESHED:
        if not cfgmod.platform_cfg(cfg, plat).get("enabled"):
            continue
        age = token_age_days(plat, when)
        if age is None or age < 30:
            continue
        try:
            build_adapter(cfg, plat, factory, **kw).refresh()
            note_token_time(plat, when)
            say(f"{plat}: token refreshed")
        except Exception as e:
            say(f"{plat}: token refresh failed: {type(e).__name__}")
            sysutil.notify(f"{plat.capitalize()} token refresh failed; run: social.py refresh {plat}")


def _process(item: Item, cfg: dict, factory, when, say, notify, finish, kw) -> None:
    ok, why = item.approval_valid()
    if not ok:
        item.meta["status"] = "draft"
        item.save()
        say(f"{item.id}: approval void ({why}); back to draft")
        notify(f"{item.id}: approval void, needs a new approve")
        return
    t = item.scheduled()
    if t is None or t > when:
        return
    if not _pending_platforms(item):
        finish(item, cfg, say, notify)
        return
    if (when - t).total_seconds() > cfg["stale_hours"] * 3600:
        item.meta["status"] = "stale"
        item.save()
        say(f"{item.id}: scheduled {item.meta['scheduled_at']}, more than {cfg['stale_hours']} h ago: stale, needs re-approval")
        notify(f"{item.id} is stale; approve it again to post")
        return
    if not itemsmod.due_local_window(when, cfg):
        say(f"{item.id}: due, outside the posting window; waiting")
        return
    errors, _ = itemsmod.validate(item, cfg)
    if errors:
        item.meta["status"] = "draft"
        item.save()
        say(f"{item.id}: no longer valid ({errors[0]}); back to draft")
        notify(f"{item.id} failed validation and was not posted")
        return
    for p in _pending_platforms(item):
        pc = cfgmod.platform_cfg(cfg, p)
        res = item.results.setdefault(p, {"status": "pending", "attempts": 0})
        if not pc.get("enabled"):
            res.update(status="skipped", error="platform disabled in config")
            item.save()
            say(f"{item.id}/{p}: disabled; skipped")
            continue
        nxt = res.get("next_attempt_at")
        if nxt and itemsmod.parse_time(nxt) > when:
            continue
        try:
            r = post_platform(item, p, cfg, factory, **kw)
            if r.get("status") == "posted":
                say(f"{item.id}/{p}: posted {r.get('url')} verified={r.get('verified')}")
            else:
                say(f"{item.id}/{p}: FAILED {r.get('error')}")
        except Refused as e:
            say(f"{item.id}/{p}: REFUSED {e}")
            notify(f"REFUSED {p}: wrong account. Nothing posted. {e}")
        except (SessionExpired, Ambiguous, Disabled) as e:
            res = item.results[p]
            res.update(status="failed", error=str(e))
            item.save()
            say(f"{item.id}/{p}: FAILED {e}")
        except Exception as e:
            res = item.results[p]
            n = int(res.get("attempts", 1))
            if n >= cfg["retry"]["max_attempts"]:
                res.update(status="failed", error=f"{type(e).__name__}: {str(e)[:300]}")
                say(f"{item.id}/{p}: FAILED after {n} attempts: {e}")
            else:
                res["next_attempt_at"] = iso(when + backoff(cfg, n))
                say(f"{item.id}/{p}: attempt {n} failed ({e}); retry at {res['next_attempt_at']}")
            item.save()
    if not _pending_platforms(item):
        finish(item, cfg, say, notify)


def finish_item(item: Item, cfg: dict, say, notify) -> None:
    """All platforms are final: set the item status, notify once, write the logs."""
    rs = {p: item.results.get(p, {}) for p in item.platforms}
    posted = {p: r for p, r in rs.items() if r.get("status") == "posted"}
    bad = {p: r for p, r in rs.items() if r.get("status") in ("failed", "refused")}
    item.meta["status"] = "posted" if posted and not bad else "failed"
    item.meta["finished_at"] = iso(now())
    item.save()
    parts = [f"{p}: {r['url']}" for p, r in posted.items()] + [f"{p}: FAILED ({str(r.get('error'))[:80]})" for p, r in bad.items()]
    if not any(r.get("status") == "refused" for r in rs.values()):  # a refusal already sent its own notification
        notify(f"{item.id} {item.meta['status']}. " + "; ".join(parts))
    say(f"{item.id}: {item.meta['status']}")
    if posted:
        _log_outreach(item, posted, say)
        _log_change(item, posted, say)


def _log_outreach(item: Item, posted: dict, say) -> None:
    p = paths.outreach_log()
    if not p.exists():
        say(f"{item.id}: outreach log not found at {p}; skipped")
        return
    day = f"{now().astimezone():%Y-%m-%d}"
    try:
        with p.open("a", encoding="utf-8") as fh:
            text = p.read_text(encoding="utf-8")
            if not text.endswith("\n"):
                fh.write("\n")
            for plat, r in posted.items():
                note = f"queue item {item.id}, utm_campaign={item.campaign}, scheduled post, approved by {item.meta.get('approved_by') or 'ben'}"
                fh.write(f"| {day} | {plat}: {item.id} | {r.get('url')} | posted | {note} |\n")
    except OSError as e:
        say(f"{item.id}: could not write the outreach log: {e}")


def _log_change(item: Item, posted: dict, say) -> None:
    script = paths.change_logger()
    if not script.exists():
        say(f"{item.id}: change logger not found; skipped")
        return
    plats = ", ".join(posted)
    what = f"Social post {item.id} on {plats} (company accounts), utm_campaign={item.campaign}"
    cmd = [sys.executable, str(script), "add", "--area", "outreach", "--what", what,
           "--affected", f"traffic with utm_campaign={item.campaign} from {plats}",
           "--comparison", item.meta.get("experiment_note") or "other days without this post",
           "--metric", "pageviews and trial downloads with this utm_campaign", "--confidence", "exact"]
    try:
        subprocess.run(cmd, check=False, capture_output=True, timeout=60)
    except Exception as e:
        say(f"{item.id}: change log failed: {e}")
