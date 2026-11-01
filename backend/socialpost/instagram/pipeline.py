"""Queue Instagram posts under Ben's standing approval of 2026-10-23. Nothing here posts: the scheduler (`run-due`)
posts the queued items through the Instagram adapter, with the same identity check, PAUSE switch and logging as
every other platform.

Two flows:
  Reels       every video on the Purplelink YouTube channel. `reel-add` (called by howto-publish.py and by
              yt-api-upload.py for Purplelink uploads, or by hand) makes the 9:16 file and puts it in the inbox;
              `run` captions, vets and queues it. `scan` reads the channel's public feed and notifies about any upload
              that has no Reel (a video uploaded some other way), so none is missed silently.
  Companions  every queue item whose LinkedIn company post went out gets an Instagram image post: a 1080x1350
              card from the post's own headline and first fact, and the post's text with "Link in bio.".

The gate (vet) must pass or the item is not queued and the reason is logged: voice, facts, alt text, platform limits,
a live link, no repeat. At most `max_per_day` Instagram posts a day, spaced `spacing_minutes` apart.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from zoneinfo import ZoneInfo

from .. import config as cfgmod
from .. import items as itemsmod
from .. import hubtags, paths, sysutil
from ..daily import vet as vetmod
from ..items import Item, iso
from ..text import utm_link
from . import caption as cap
from . import render

SOURCE_REEL, SOURCE_COMPANION = itemsmod.IG_STANDING_SOURCES
DEFAULTS = {"max_per_day": 3, "spacing_minutes": 90, "reel_days": 7, "companion_days": 3, "dup_days": 21,
            "links_store": "instagram-links", "links_key": "latest.json", "links_count": 12}
CHANNEL_KEY = "purplelink"
FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={cid}"


# ---------------------------------------------------------------- state
def ig_dir() -> Path:
    return paths.instagram_dir()


def state_file() -> Path:
    return ig_dir() / "state.json"


def read_state() -> dict:
    try:
        s = json.loads(state_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        s = {}
    for k, v in (("reels", {}), ("fb_reels", {}), ("companions", {}), ("hashes", []), ("warned", []), ("log", [])):
        s.setdefault(k, v)
    return s


def write_state(s: dict) -> None:
    ig_dir().mkdir(parents=True, exist_ok=True)
    s["log"] = s["log"][-200:]
    tmp = state_file().with_suffix(".tmp")
    tmp.write_text(json.dumps(s, indent=1, default=str), encoding="utf-8")
    tmp.replace(state_file())


def settings(cfg: dict) -> dict:
    return {**DEFAULTS, **{k: v for k, v in cfgmod.platform_cfg(cfg, "instagram").items() if k in DEFAULTS}}


def local(cfg: dict, when: dt.datetime) -> dt.datetime:
    return when.astimezone(ZoneInfo(cfg.get("timezone", "America/New_York")))


# ---------------------------------------------------------------- reels inbox
def reels_dir() -> Path:
    return ig_dir() / "reels"


def inbox() -> list[dict]:
    out = []
    for f in sorted(reels_dir().glob("*/entry.json")):
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return out


def hub_tag(link: str, asset: str, hub=None, channel: str = "instagram", campaign: str = "ig-reel",
            preferred: str | None = None) -> str:
    """A utm_content no other placement uses, from the marketing hub, for one Reel or post on `channel`. "" when the
    link is not on purplelink.llc (a YouTube fallback is not tagged) or the hub is unavailable (the gate then rejects a
    site link without a tag). `hub` lets tests pass a fake hub module."""
    pref = f"{asset}-reel" if preferred is None and channel == "instagram" else (preferred or "")
    try:
        if hub is not None:
            if not hub.site_path(link):
                return ""
            url = hub.make_utm(hub.paths(), link, asset, channel, source=channel, medium="social",
                               campaign=campaign, content=pref)
            m = re.search(r"utm_content=([\w.\-]+)", url)
            return m.group(1) if m else ""
        return hubtags.tag(link, asset, channel, campaign, preferred=pref)
    except (Exception, SystemExit) as e:
        sysutil.log(f"instagram: no hub tag for {link} ({type(e).__name__})")
        return ""


def reel_add(video: Path, youtube_id: str, title: str, description: str = "", link: str = "",
             also: list[str] | None = None, run=subprocess.run, when: dt.datetime | None = None,
             utm_content: str = "", hub=None, backfill: str = "") -> dict:
    """Make the Reel for one Purplelink YouTube video and put it in the inbox. Idempotent per YouTube id.
    backfill: the video's YouTube publish date (YYYY-MM-DD) for an older video added later; such an entry never
    expires from the queue and backfill entries go out oldest first, after any new video."""
    if not re.fullmatch(r"[\w-]{11}", youtube_id or ""):
        raise ValueError("--youtube-id must be an 11-character YouTube video id")
    d = reels_dir() / youtube_id
    ent = d / "entry.json"
    if ent.exists():
        return json.loads(ent.read_text(encoding="utf-8"))
    d.mkdir(parents=True, exist_ok=True)
    prose = cap._prose_paragraphs(description)
    sub = next((s for p in prose for s in cap.comp.sentences(p) if len(s) <= 150 and not cap._restates(s, title)), "")
    bg = "latex" if re.search(r"latex|bibtex|overleaf", f"{title} {description}", re.I) else "apps"
    meta = render.reel(Path(video), d / "reel.mp4", title=cap.clean_title(title), kicker="Video", sub=sub, bg=bg,
                       run=run)
    entry = {"youtube_id": youtube_id, "also": [a for a in (also or []) if a], "title": cap.clean_title(title),
             "description": description, "link": link, "source": str(video),
             "added": iso(when or dt.datetime.now(dt.timezone.utc)),
             "utm_content": utm_content or (hub_tag(link, youtube_id, hub) if link else ""),
             **({"backfill": backfill} if backfill else {}), **meta}
    ent.write_text(json.dumps(entry, indent=1), encoding="utf-8")
    sysutil.log(f"instagram: Reel ready for {youtube_id} ({meta['duration']} s, framed={meta['framed']}, "
                f"trimmed={meta['trimmed']})")
    return entry


# ---------------------------------------------------------------- items
def _item_path(iid: str) -> Path:
    return paths.queue_dir() / f"{iid}.md"


def reel_item(entry: dict, when_iso: str) -> Item:
    ytid = entry["youtube_id"]
    text = cap.reel_caption(entry["title"], entry.get("description", ""), entry.get("trimmed", False),
                            cap.app_tags_for_link(entry.get("link", "")))
    first = next((s for p in cap._prose_paragraphs(entry.get("description", "")) for s in cap.comp.sentences(p)
                  if not cap._restates(s, entry["title"])), "")
    alt = f"Video: {entry['title']}." + (f" {first}" if first else "")
    slug = re.sub(r"[^a-z0-9]+", "-", ytid.lower()).strip("-")
    iid = f"{dt.date.today():%Y%m%d}-ig-reel-{slug}"
    meta = {
        "id": iid, "created": iso(dt.datetime.now(dt.timezone.utc)), "scheduled_at": when_iso, "status": "draft",
        "approved_by": None, "approved_at": None, "platforms": ["instagram"], "campaign": "ig-reel",
        "link": entry.get("link") or f"https://www.youtube.com/watch?v={ytid}", "images": [], "text_only": [],
        "video": {"path": str(reels_dir() / ytid / "reel.mp4"), "duration": entry["duration"],
                  "width": entry["width"], "height": entry["height"], "alt": alt[:900]},
        "experiment_note": "Instagram Reel of a Purplelink YouTube video; compared with the same video's YouTube views",
        "results": {}, "source": SOURCE_REEL,
        "instagram": {"kind": "reel", "youtube_id": ytid, "title": entry["title"]},
        **({"utm_content": entry["utm_content"]} if entry.get("utm_content") else {}),
        "utm_contents": {"instagram": entry.get("utm_content") or hub_tag(entry.get("link", ""), ytid)},
    }
    return Item(_item_path(iid), meta, {"instagram": text},
                f"Built by socialpost.instagram from YouTube {ytid}; Reel {entry['duration']} s.")


def fb_reel_item(entry: dict, when_iso: str) -> Item:
    """The same Reel for the Purplelink LLC Facebook Page: the Instagram caption with the tagged link where Instagram
    says "Link in bio." (Ben, 2026-10-28: "back fill my instagram and facebook reels with our youtube shorts")."""
    ig = reel_item(entry, when_iso)
    text = ig.sections["instagram"].replace(cap.BIO, "{link}")
    iid = ig.id.replace("-ig-reel-", "-fb-reel-")
    meta = dict(ig.meta, id=iid, platforms=["facebook"], campaign="fb-reel",
                experiment_note="Facebook Reel of a Purplelink YouTube Short; compared with the same video's YouTube views")
    meta["instagram"] = dict(meta["instagram"], kind="fb-reel")
    meta.pop("utm_content", None)
    meta["utm_contents"] = {"facebook": hub_tag(meta["link"], entry["youtube_id"], channel="facebook",
                                                campaign="fb-reel", preferred=f"{entry['youtube_id']}-fb-reel")}
    return Item(_item_path(iid), meta, {"facebook": text}, f"Built by socialpost.instagram from YouTube "
                f"{entry['youtube_id']}; Facebook Reel {entry['duration']} s.")


def companion_item(li: Item, card_path: Path, words: dict, when_iso: str) -> Item:
    text = cap.companion_caption(li.raw_text("linkedin"), _app_tags(li))
    alt = (f"Purplelink card on a dark purple background. {words['kicker']}: {words['title']}."
           + (f" {words['sub']}" if words.get("sub") else ""))
    iid = f"{str(li.id)[:60]}-ig"
    meta = {
        "id": iid, "created": iso(dt.datetime.now(dt.timezone.utc)), "scheduled_at": when_iso, "status": "draft",
        "approved_by": None, "approved_at": None, "platforms": ["instagram"], "campaign": li.campaign or "ig-companion",
        "link": li.link, "images": [{"path": str(card_path), "alt": alt[:900]}], "text_only": [],
        "experiment_note": f"Instagram companion of LinkedIn post {li.id}",
        "results": {}, "source": SOURCE_COMPANION,
        "instagram": {"kind": "companion", "of": str(li.id), "title": words["title"]},
        "utm_contents": {"instagram": hub_tag(li.link, str((li.meta.get("daily") or {}).get("candidate") or li.id)
                                              .split(":", 1)[-1], channel="instagram",
                                              campaign=li.campaign or "ig-companion", preferred="")},
    }
    return Item(_item_path(iid), meta, {"instagram": text}, f"Built by socialpost.instagram from {li.id}.")


def _app_tags(li: Item) -> list[str]:
    cand = str((li.meta.get("daily") or {}).get("candidate") or "")
    m = re.match(r"release:([a-z0-9-]+):", cand)
    return [cap.APP_TAGS[m.group(1)]] if m and m.group(1) in cap.APP_TAGS else []


def linkedin_posted(li: Item) -> dt.datetime | None:
    r = li.results.get("linkedin") or {}
    if r.get("status") != "posted" or not r.get("posted_at"):
        return None
    try:
        return itemsmod.parse_time(r["posted_at"])
    except ValueError:
        return None


# ---------------------------------------------------------------- gate
def tag_problems(item: Item) -> list[str]:
    """Every post whose link is on purplelink.llc carries its own utm_content (the marketing hub's), so it can be
    measured; the bio link for Instagram, the caption link for Facebook."""
    return [f"utm: {p} has no utm_content for its purplelink.llc link (unmeasurable)" for p in item.platforms
            if hubtags.on_site(item.link) and not item.utm_content(p)]


def vet(item: Item, source: str, http, state: dict, today: dt.date, cfg: dict, s: dict,
        link_check: bool = True) -> list[str]:
    """Reasons the item may not go out; empty means it passes."""
    reasons: list[str] = []
    plat = item.platforms[0]
    text = item.render(plat)
    body = itemsmod.HASHTAG_RE.sub(" ", text)
    for why in vetmod.voice_problems(text):
        reasons.append(f"voice: {why}")
    src = " ".join([source, *cap.TEMPLATES, "Purplelink Video Guide Tool Blog Release"])
    for why in vetmod.facts_problems(body, src):
        reasons.append(f"facts: {why}")
    v = item.video()
    if v and not str(v.get("alt") or "").strip():
        reasons.append("alt: the Reel has no description")
    for why in vetmod.alt_problems(item):
        reasons.append(f"alt: {why}")
    errors, _ = itemsmod.validate(item, cfg)
    reasons += [f"limits: {e}" for e in errors]
    reasons += tag_problems(item)
    h = vetmod.text_hash(body)
    for old in state["hashes"]:
        age = (today - dt.date.fromisoformat(old["date"])).days
        if old["hash"] == h and old.get("platform", "instagram") == plat and age < s["dup_days"]:
            reasons.append(f"duplicate: the same caption went out {age} days ago")
    if link_check and item.link:
        reasons += [f"link: {why}" for why in vetmod.link_problems(http, item.link)]
    return reasons


# ---------------------------------------------------------------- scheduling
def ig_items_on(day: dt.date, cfg: dict, platform: str = "instagram") -> list[Item]:
    tz = ZoneInfo(cfg.get("timezone", "America/New_York"))
    out = []
    for it in itemsmod.list_items():
        if platform not in it.platforms or it.status not in ("approved", "posted"):
            continue
        try:
            t = it.scheduled()
        except ValueError:
            continue
        if t and t.astimezone(tz).date() == day:
            out.append(it)
    return out


def next_slot(cfg: dict, s: dict, when: dt.datetime, platform: str = "instagram") -> dt.datetime | None:
    """When the next post on `platform` may go out today, or None when today's quota is used. Facebook Reels count
    against the Page's own quota; the daily ranked text post there is not counted."""
    today = local(cfg, when).date()
    taken = [it for it in ig_items_on(today, cfg, platform)
             if platform == "instagram" or str(it.meta.get("source", "")).startswith("instagram")]
    if len(taken) >= s["max_per_day"]:
        return None
    t = when + dt.timedelta(minutes=2)
    for it in taken:
        t = max(t, it.scheduled() + dt.timedelta(minutes=s["spacing_minutes"]))
    return t if local(cfg, t).date() == today else None


# ---------------------------------------------------------------- the run
def pending(cfg: dict, when: dt.datetime, state: dict, s: dict) -> list[tuple[str, object]]:
    """[(kind, obj)] waiting for an Instagram post: LinkedIn posts without a companion, inbox Reels not queued."""
    work: list[tuple[str, object]] = []
    for li in itemsmod.list_items():
        t = linkedin_posted(li)
        if t is None or str(li.meta.get("source", "")).startswith("instagram") or "instagram" in li.platforms:
            continue
        if str(li.id) in state["companions"] or (when - t).days >= s["companion_days"]:
            continue
        work.append(("companion", li))
    fb_on = cfgmod.platform_cfg(cfg, "facebook").get("enabled")
    # new videos first (in the order they were added), then backfilled older ones (oldest YouTube date first)
    for e in sorted(inbox(), key=lambda e: (bool(e.get("backfill")), e.get("backfill") or "",
                                           "" if e.get("backfill") else e.get("added", ""))):
        try:
            age = (when - itemsmod.parse_time(e["added"])).days
        except (KeyError, ValueError):
            continue
        if age >= s["reel_days"] and not e.get("backfill"):
            continue
        if e["youtube_id"] not in state["reels"]:
            work.append(("reel", e))
        if fb_on and e["youtube_id"] not in state["fb_reels"] and e.get("duration", 0) <= itemsmod.FB_REEL_MAX_S:
            work.append(("fb_reel", e))
    return work


def build(kind: str, obj, slot: dt.datetime, render_card=render.card) -> tuple[Item, str, str]:
    """(item, source text for the facts check, state key) for one piece of work."""
    if kind in ("reel", "fb_reel"):
        make = reel_item if kind == "reel" else fb_reel_item
        return make(obj, iso(slot)), f"{obj['title']} {obj.get('description', '')}", obj["youtube_id"]
    words = cap.card_words(obj.raw_text("linkedin"))
    card_path = ig_dir() / "cards" / f"{obj.id}.jpg"
    render_card(card_path, words["title"], words["kicker"], words["sub"], "", words["bg"])
    return companion_item(obj, card_path, words, iso(slot)), obj.raw_text("linkedin"), str(obj.id)


def run(http, cfg: dict | None = None, when: dt.datetime | None = None, dry_run: bool = False, say=print,
        notify=None, render_card=render.card, link_check: bool = True) -> dict:
    """One pass: queue what is due under the standing approval. Returns {"queued", "skipped", "would_queue"}."""
    cfg = cfg or cfgmod.load()
    notify = notify or sysutil.notify
    when = when or dt.datetime.now(dt.timezone.utc)
    s = settings(cfg)
    out: dict = {"queued": [], "skipped": [], "would_queue": []}
    if paths.pause_file().exists():
        say("PAUSE file present: no Instagram queueing")
        return {**out, "status": "paused"}
    if not cfgmod.platform_cfg(cfg, "instagram").get("enabled") and not dry_run:
        return {**out, "status": "disabled"}
    state = read_state()
    today = local(cfg, when).date()

    full: set[str] = set()
    for kind, obj in pending(cfg, when, state, s):
        plat = "facebook" if kind == "fb_reel" else "instagram"
        slot = next_slot(cfg, s, when, plat) if not dry_run else when + dt.timedelta(minutes=2)
        if slot is None:
            if plat not in full:
                say(f"{plat}: today's {s['max_per_day']} posts are queued; the rest wait for tomorrow")
                full.add(plat)
            continue
        try:
            item, source, key = build(kind, obj, slot, render_card)
        except Exception as e:
            out["skipped"].append((str(getattr(obj, "id", "") or obj.get("youtube_id")), [f"build: {e}"]))
            say(f"instagram: could not build the {kind}: {e}")
            continue
        reasons = vet(item, source, http, state, today, cfg, s, link_check)
        if reasons:
            out["skipped"].append((key, reasons))
            say(f"instagram: {item.id} failed vetting: " + " | ".join(reasons))
            if not dry_run:
                state[f"{kind}s"][key] = f"failed: {reasons[0]}"[:200]
                state["log"].append({"at": iso(when), "item": item.id, "failed": reasons})
                notify(f"Instagram: {item.id} not queued ({reasons[0][:80]})")
            continue
        if dry_run:
            out["would_queue"].append(item)
            continue
        if item.path.exists():
            state[f"{kind}s"][key] = item.id
            continue
        paths.queue_dir().mkdir(parents=True, exist_ok=True)
        item.save()
        itemsmod.approve_instagram_standing(item, cfg)
        state[f"{kind}s"][key] = item.id
        state["hashes"].append({"date": today.isoformat(), "platform": plat, "hash": vetmod.text_hash(
            itemsmod.HASHTAG_RE.sub(" ", item.render(plat)))})
        state["log"].append({"at": iso(when), "item": item.id, "queued_for": item.meta["scheduled_at"]})
        out["queued"].append(item.id)
        sysutil.log(f"instagram: queued {item.id} for {item.meta['scheduled_at']}; approved by standing approval "
                    f"{item.meta['approved_by']}")
    if not dry_run:
        write_state(state)
        sync_links(cfg, say)
    return {**out, "status": "dry-run" if dry_run else "ok"}


# ---------------------------------------------------------------- link in bio
def links(cfg: dict, n: int) -> list[dict]:
    """The latest posted Instagram items as tagged links, newest first, for the /instagram/ page."""
    rows = []
    for it in itemsmod.list_items():
        r = it.results.get("instagram") or {}
        if "instagram" not in it.platforms or r.get("status") != "posted" or not it.link:
            continue
        ig = it.meta.get("instagram") or {}
        rows.append({"title": str(ig.get("title") or it.id)[:140], "kind": ig.get("kind", ""),
                     "url": utm_link(it.link, "instagram", it.campaign, it.utm_content("instagram")),
                     "date": str(r.get("posted_at", ""))[:10],
                     "at": str(r.get("posted_at", ""))})
    rows.sort(key=lambda x: x["at"], reverse=True)
    return [{k: v for k, v in r.items() if k != "at"} for r in rows[:n]]


def sync_links(cfg: dict, say=print, run=subprocess.run) -> bool:
    """Publish the link list to the instagram-links Blobs store when it changed. Never fatal."""
    s = settings(cfg)
    data = json.dumps(links(cfg, s["links_count"]), indent=1)
    h = hashlib.sha256(data.encode()).hexdigest()[:16]
    state = read_state()
    if state.get("links_hash") == h or data == "[]":
        return False
    f = ig_dir() / "links.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(data, encoding="utf-8")
    try:
        p = run(["netlify", "blobs:set", s["links_store"], s["links_key"], "--input", str(f), "--force"],
                capture_output=True, text=True, timeout=180, cwd=cfg["media"].get("netlify_cwd") or None)
    except Exception as e:
        say(f"instagram: link list not published ({type(e).__name__})")
        return False
    if p.returncode != 0:
        say("instagram: link list not published (is `netlify login` current?)")
        return False
    state["links_hash"] = h
    write_state(state)
    say("instagram: link-in-bio list updated")
    return True


# ---------------------------------------------------------------- channel scan
def channel_id(root: Path | None = None) -> str:
    reg = json.loads(((root or paths.repo_root()) / "scripts" / "yt-channels.json").read_text(encoding="utf-8"))
    chans = reg.get("channels", reg)
    return chans[CHANNEL_KEY]["id"]


def feed_videos(http, cid: str) -> list[dict]:
    r = http.request("GET", FEED.format(cid=cid))
    if r.status != 200:
        return []
    xml = r.body.decode("utf-8", "replace")
    out = []
    for blk in re.findall(r"<entry>(.*?)</entry>", xml, re.S):
        vid = re.search(r"<yt:videoId>([\w-]{11})</yt:videoId>", blk)
        pub = re.search(r"<published>([^<]+)</published>", blk)
        title = re.search(r"<title>([^<]*)</title>", blk)
        if vid and pub:
            out.append({"id": vid.group(1), "published": pub.group(1), "title": title.group(1) if title else ""})
    return out


def scan(http, cfg: dict | None = None, when: dt.datetime | None = None, notify=None, say=print,
         ledger: list | None = None, cid: str | None = None) -> list[dict]:
    """Purplelink uploads of the last week with no Reel in the inbox. Notifies once per video."""
    cfg = cfg or cfgmod.load()
    notify = notify or sysutil.notify
    when = when or dt.datetime.now(dt.timezone.utc)
    covered = set()
    for e in inbox():
        covered.add(e["youtube_id"])
        covered |= set(e.get("also") or [])
    for e in (ledger if ledger is not None else _ledger()):
        if e.get("short_id") in covered:
            covered.add(e.get("long_id"))
    state = read_state()
    missing = []
    for v in feed_videos(http, cid or channel_id()):
        try:
            age = (when - itemsmod.parse_time(v["published"])).days
        except ValueError:
            continue
        if age < settings(cfg)["reel_days"] and v["id"] not in covered:
            missing.append(v)
    new = [v for v in missing if v["id"] not in state["warned"]]
    if new:
        names = "; ".join(f"{v['title'][:50]} ({v['id']})" for v in new[:3])
        notify(f"Instagram: {len(new)} Purplelink video(s) have no Reel: {names}. Run social.py instagram reel-add")
        state["warned"] = (state["warned"] + [v["id"] for v in new])[-200:]
        write_state(state)
    for v in missing:
        say(f"no Reel yet: {v['id']}  {v['published'][:10]}  {v['title']}")
    return missing


def _ledger() -> list:
    try:
        return json.loads((paths.repo_root() / "video" / "howto" / "ledger.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def copy_preview(item: Item, out_dir: Path) -> list[Path]:
    """Copy an item's media and caption into out_dir for Ben to look at (dry run)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    got = []
    v = item.video()
    for src in ([Path(v["path"])] if v else []) + [Path(im["path"]) for im in item.meta.get("images") or []]:
        dst = out_dir / f"{item.id}{src.suffix}"
        shutil.copyfile(src, dst)
        got.append(dst)
    cap_file = out_dir / f"{item.id}-caption.txt"
    cap_file.write_text(item.render(item.platforms[0]) + "\n", encoding="utf-8")
    return got + [cap_file]
