"""The daily pick: gather, score, compose, vet, queue under standing approval. The existing engine posts the item.

`run_daily(...)` is safe to call many times a day: it does nothing before `pick_after`, nothing once today is done,
and it never posts. A missed morning is not lost: any later call the same day picks, and the item is scheduled for
"now" (the engine still keeps to its posting window). After `last_pick` the day is recorded as missed.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re
from pathlib import Path
from zoneinfo import ZoneInfo

from .. import config as cfgmod
from .. import items as itemsmod
from .. import paths, sysutil
from ..items import Item, iso
from . import candidates as cand
from . import compose as comp
from . import score as sc
from . import settings as st
from . import vet as vetmod

MAGIC = {b"\x89PNG\r\n\x1a\n": ".png", b"\xff\xd8\xff": ".jpg"}
MAX_TRIES = 25


def state_file() -> Path:
    return paths.daily_dir() / "state.json"


def local_now(cfg: dict, when: dt.datetime | None = None) -> dt.datetime:
    return (when or dt.datetime.now(dt.timezone.utc)).astimezone(ZoneInfo(cfg["timezone"]))


def hm(local: dt.datetime) -> str:
    return f"{local:%H:%M}"


# ---------------------------------------------------------------- history
def reconcile_history(history: list[dict]) -> list[dict]:
    """A queued pick counts for the repeat and fatigue rules only while its item is, or may still become, posted."""
    for h in history:
        try:
            it = itemsmod.find(h["item"])
        except (KeyError, OSError, ValueError):
            continue
        posted_any = any(r.get("status") == "posted" for r in it.results.values())
        h["counts"] = it.status in ("approved", "posted") or posted_any
    return history


def platforms_used_today(local_date: dt.date, tzname: str) -> set[str]:
    """Platforms that already have an approved or posted item scheduled for today (the daily pipeline's or Ben's)."""
    used: set[str] = set()
    tz = ZoneInfo(tzname)
    for it in itemsmod.list_items():
        if it.status not in ("approved", "posted"):
            continue
        try:
            t = it.scheduled()
        except ValueError:
            continue
        if t and t.astimezone(tz).date() == local_date:
            used |= set(it.platforms)
    return used


# ---------------------------------------------------------------- images
def fetch_image(http, url: str) -> Path | None:
    """Download the page's card image into the private media folder. None when it is missing or not a PNG or JPEG."""
    if not url:
        return None
    try:
        r = http.request("GET", url)
    except Exception:
        return None
    if r.status != 200 or not r.body or len(r.body) > 8 * 1024 * 1024:
        return None
    ext = next((e for sig, e in MAGIC.items() if r.body.startswith(sig)), None)
    if not ext:
        return None
    paths.media_dir().mkdir(parents=True, exist_ok=True)
    p = paths.media_dir() / f"{hashlib.sha256(r.body).hexdigest()[:24]}{ext}"
    if not p.exists():
        p.write_bytes(r.body)
    return p


def threads_images_ready(http, cfg_main: dict) -> bool:
    """True when the social-media image function is deployed (it answers an unknown key with a plain-text 404; a
    site without the function answers with the HTML 404 page)."""
    base = cfg_main["media"]["base_url"].rstrip("/")
    try:
        r = http.request("GET", f"{base}/{'0' * 40}.png")
    except Exception:
        return False
    return r.status == 404 and str(r.headers.get("content-type", "")).lower().startswith("text/plain")


# ---------------------------------------------------------------- item
def item_id(c: cand.Candidate, day: dt.date) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", c.id.lower()).strip("-")[:56]
    return f"{day:%Y%m%d}-daily-{slug}"


def build_item(c, facts, fmt, texts, platforms, when_iso, day, image_path, image_platforms, notes_line) -> Item:
    campaign = f"daily-{c.kind}"
    meta = {
        "id": item_id(c, day),
        "created": iso(dt.datetime.now(dt.timezone.utc)),
        "scheduled_at": when_iso,
        "status": "draft",
        "approved_by": None,
        "approved_at": None,
        "platforms": list(platforms),
        "campaign": campaign,
        "link": c.url,
        "images": [],
        "text_only": [],
        "experiment_note": f"format {fmt} and kind {c.kind} compared with the other formats and kinds in the weekly report",
        "results": {},
        "source": itemsmod.STANDING_SOURCE,
        "daily": {"candidate": c.id, "kind": c.kind, "format": fmt},
    }
    if image_path and image_platforms:
        alt = facts.get("image_alt") or f"Preview image for the page: {facts['title']}"
        meta["images"] = [{"path": str(image_path), "alt": alt[:900], "platforms": list(image_platforms)}]
        meta["text_only"] = [p for p in platforms if p not in image_platforms]
    path = paths.queue_dir() / f"{meta['id']}.md"
    return Item(path, meta, dict(texts), notes_line)


# ---------------------------------------------------------------- the run
def run_daily(http, dcfg: dict | None = None, main_cfg: dict | None = None, when: dt.datetime | None = None,
              dry_run: bool = False, force: bool = False, notify=None, say=print, stats=None, added=None,
              ledger=None) -> dict:
    """Returns {"status": ..., ...}. status: queued | dry-run | done-already | too-early | missed | paused |
    no-platform | nothing-passed."""
    dcfg = dcfg or st.load()
    main_cfg = main_cfg or cfgmod.load()
    notify = notify or sysutil.notify
    when = when or dt.datetime.now(dt.timezone.utc)
    local = local_now(dcfg, when)
    today = local.date()
    state = st.read_json(state_file(), {})

    if not dry_run:
        if paths.pause_file().exists():
            say("PAUSE file present: no daily pick")
            return {"status": "paused"}
        if state.get("last_done") == today.isoformat() and not force:
            return {"status": "done-already", "detail": state.get("detail", "")}
        if hm(local) < dcfg["pick_after"] and not force:
            return {"status": "too-early"}
        if hm(local) > dcfg["last_pick"] and not force:
            state.update(last_done=today.isoformat(), detail="missed: past the last pick time")
            st.write_json(state_file(), state)
            say(f"{today}: past {dcfg['last_pick']}, no pick today")
            return {"status": "missed"}

    history = reconcile_history(st.load_history())
    learned = st.load_learned()

    allowed = [p for p in dcfg["platforms"] if p in itemsmod.STANDING_PLATFORMS
               and cfgmod.platform_cfg(main_cfg, p).get("enabled")]
    used = platforms_used_today(today, dcfg["timezone"])
    platforms = [p for p in allowed if p not in used]
    skipped_platforms = [p for p in allowed if p in used]
    if not platforms:
        say(f"every platform already has a post scheduled for {today}")
        if not dry_run:
            state.update(last_done=today.isoformat(), detail="a post was already scheduled for every platform today")
            st.write_json(state_file(), state)
        return {"status": "no-platform"}

    notes: list[str] = []
    stats = stats if stats is not None else cand.fetch_stats(http, dcfg["stats_days"])
    cands = cand.gather(http, today, dcfg, stats=stats, added=added, ledger=ledger, notes=notes)
    fmt0 = sc.pick_format(history, dcfg, learned, has_image=True)
    log_lines: list[str] = []
    ranked = sc.rank(cands, fmt0, today, dcfg, learned, history, log=log_lines.append)
    threads_img = "threads" in platforms and threads_images_ready(http, main_cfg)

    link_cfg = dict(main_cfg)
    link_cfg["link_hosts"] = sorted(set(main_cfg.get("link_hosts") or []) | {"www.youtube.com", "youtu.be"})

    slot = dt.datetime.combine(today, dt.time.fromisoformat(dcfg["slot"]), tzinfo=ZoneInfo(dcfg["timezone"]))
    when_at = slot if local < slot else local + dt.timedelta(minutes=2)

    chosen = None
    tried = 0
    for sc_value, c in ranked:
        if tried >= MAX_TRIES:
            break
        tried += 1
        try:
            facts = cand.load_facts(http, c)
        except Exception as e:  # not live, no title, network
            log_lines.append(f"{c.id}: skipped, {e}")
            continue
        fmt = fmt0
        image = None
        if fmt == "card":
            image = fetch_image(http, facts.get("og_image", ""))
            if image is None:
                fmt = sc.pick_format(history, dcfg, learned, has_image=False)
                log_lines.append(f"{c.id}: no usable card image; format {fmt} instead")
        try:
            texts = comp.compose(c, facts, fmt, platforms, f"daily-{c.kind}")
        except comp.ComposeError as e:
            log_lines.append(f"{c.id}: skipped, {e}")
            continue
        image_platforms = [p for p in platforms if p in ("bluesky", "mastodon") or (p == "threads" and threads_img)] if image else []
        item = build_item(c, facts, fmt, texts, platforms, iso(when_at), today, image if image_platforms else None,
                          image_platforms, f"Built by the daily pipeline from {c.id}; format {fmt}.")
        v = vetmod.vet(item, c, facts, texts, http, history, today, dcfg, link_cfg)
        if not v.ok:
            log_lines.append(f"{c.id}: failed vetting: " + " | ".join(v.reasons))
            continue
        chosen = (sc_value, c, fmt, item, texts)
        break

    result = {"notes": notes, "excluded": log_lines, "platforms": platforms, "skipped_platforms": skipped_platforms}
    if not chosen:
        say(f"{today}: no candidate passed vetting")
        for ln in log_lines:
            say("  " + ln)
        if not dry_run:
            state.update(last_done=today.isoformat(), detail="no candidate passed vetting")
            st.write_json(state_file(), state)
            notify("Daily social: no candidate passed vetting today, nothing posted. See purplelink-social.log")
        return {**result, "status": "nothing-passed" if not dry_run else "dry-run-nothing"}

    sc_value, c, fmt, item, texts = chosen
    result.update(candidate=c.id, kind=c.kind, format=fmt, score=round(sc_value, 3), item=item.id,
                  scheduled_at=item.meta["scheduled_at"], texts={p: item.render(p) for p in item.platforms},
                  images=item.meta["images"], top=[(round(s, 3), x.id) for s, x in ranked[:6]])
    if dry_run:
        result["status"] = "dry-run"
        return result

    paths.queue_dir().mkdir(parents=True, exist_ok=True)
    if item.path.exists():
        say(f"{item.id} already exists in the queue; not writing it twice")
        state.update(last_done=today.isoformat(), detail=f"{item.id} already queued")
        st.write_json(state_file(), state)
        return {**result, "status": "done-already"}
    item.save()
    itemsmod.approve_standing(item, link_cfg)
    history.append({"date": today.isoformat(), "candidate": c.id, "kind": c.kind, "format": fmt, "item": item.id,
                    "platforms": list(item.platforms), "hashes": [vetmod.text_hash(t) for t in texts.values()],
                    "score": round(sc_value, 3), "counts": True})
    st.save_history(history)
    state.update(last_done=today.isoformat(), detail=f"queued {item.id}")
    st.write_json(state_file(), state)
    sysutil.log(f"daily: queued {item.id} ({c.kind}, format {fmt}) for {item.meta['scheduled_at']} on "
                f"{', '.join(item.platforms)}; approved by standing approval")
    result["status"] = "queued"
    return result
