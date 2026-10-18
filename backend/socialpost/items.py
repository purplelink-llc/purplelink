"""Queue items: load, save, render, validate, approve, hash."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import secrets
from pathlib import Path
from zoneinfo import ZoneInfo

from . import fmt, paths
from .spec import IMAGE_EXT, PLATFORMS, SPEC
from .text import link_errors, text_limit_errors, utm_link

STATUSES = ("draft", "approved", "posted", "failed", "cancelled", "stale")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,80}$")
MAGIC = {".png": (b"\x89PNG\r\n\x1a\n",), ".jpg": (b"\xff\xd8\xff",), ".jpeg": (b"\xff\xd8\xff",),
         ".gif": (b"GIF87a", b"GIF89a"), ".webp": (b"RIFF",)}


def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(t: dt.datetime) -> str:
    return t.astimezone().isoformat(timespec="seconds")


def parse_time(s: str) -> dt.datetime:
    """ISO 8601 with an offset (required: a bare time is ambiguous)."""
    t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise ValueError(f"{s!r} has no timezone offset (write e.g. 2026-10-27T08:30:00-04:00)")
    return t


class Item:
    def __init__(self, path: Path, meta: dict, sections: dict[str, str], preface: str = ""):
        self.path, self.meta, self.sections, self.preface = path, meta, sections, preface

    # -- io
    @classmethod
    def load(cls, path: Path) -> "Item":
        meta, sections, preface = fmt.parse(Path(path).read_text(encoding="utf-8"))
        return cls(Path(path), meta, sections, preface)

    def save(self) -> None:
        tmp = self.path.with_suffix(".md.tmp")
        tmp.write_text(fmt.dump(self.meta, self.sections, self.preface), encoding="utf-8")
        os.replace(tmp, self.path)  # atomic: a crash never leaves half a file

    # -- fields
    id = property(lambda s: s.meta.get("id", s.path.stem))
    status = property(lambda s: s.meta.get("status", "draft"))
    platforms = property(lambda s: list(s.meta.get("platforms") or []))
    link = property(lambda s: s.meta.get("link") or "")
    campaign = property(lambda s: s.meta.get("campaign") or "")
    results = property(lambda s: s.meta.setdefault("results", {}))

    def scheduled(self) -> dt.datetime | None:
        return parse_time(self.meta["scheduled_at"]) if self.meta.get("scheduled_at") else None

    def images_for(self, platform: str) -> list[dict]:
        if platform in (self.meta.get("text_only") or []):
            return []
        out = []
        for im in self.meta.get("images") or []:
            only = im.get("platforms")
            if only is None or platform in only:
                out.append(im)
        return out

    def document(self) -> dict | None:
        return self.meta.get("document") or None

    # -- text
    def raw_text(self, platform: str) -> str:
        return self.sections.get(platform) or self.sections.get("default") or ""

    def render(self, platform: str) -> str:
        """The exact text the platform will receive, with the platform's UTM link."""
        text = self.raw_text(platform).strip()
        if not self.link:
            return text
        url = utm_link(self.link, platform, self.campaign)
        if "{link}" in text:
            return text.replace("{link}", url)
        return f"{text}\n\n{url}" if text else url

    # -- approval
    def content_hash(self) -> str:
        h = hashlib.sha256()
        base = self.path.parent
        for p in sorted(self.platforms):
            h.update(f"{p}\0{self.render(p)}\0{json.dumps(self.images_for(p), sort_keys=True)}\0".encode())
        for im in (self.meta.get("images") or []):
            f = _resolve(im.get("path", ""), base)
            h.update(hashlib.sha256(f.read_bytes()).digest() if f.is_file() else b"missing")
        d = self.document()
        if d:
            f = _resolve(d.get("path", ""), base)
            h.update(json.dumps(d, sort_keys=True).encode())
            h.update(hashlib.sha256(f.read_bytes()).digest() if f.is_file() else b"missing")
        h.update(str(self.meta.get("scheduled_at")).encode())
        return h.hexdigest()

    def approval_valid(self) -> tuple[bool, str]:
        m = self.meta
        if m.get("status") != "approved":
            return False, "status is not approved"
        if m.get("approved_by") != "ben" or not m.get("approved_at"):
            return False, "approved_by is not 'ben' or approved_at is missing"
        if m.get("approved_hash") != self.content_hash():
            return False, "content changed after approval; approve it again"
        return True, ""


def _resolve(p: str, base: Path) -> Path:
    q = Path(os.path.expanduser(p))
    return q if q.is_absolute() else (base / q)


def image_path(item: Item, im: dict) -> Path:
    return _resolve(im.get("path", ""), item.path.parent)


# ---------------------------------------------------------------- validation
def validate(item: Item, cfg: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    m = item.meta
    if not ID_RE.match(str(item.id)):
        errors.append("id must be lowercase letters, digits and dashes")
    if m.get("status") not in STATUSES:
        errors.append(f"status must be one of {STATUSES}")
    if not item.platforms:
        errors.append("platforms is empty")
    for p in item.platforms:
        if p not in PLATFORMS:
            errors.append(f"unknown platform {p!r}")
    try:
        if item.scheduled() is None:
            errors.append("scheduled_at is missing")
    except ValueError as e:
        errors.append(str(e))
    if item.link:
        errors += link_errors(item.link, item.campaign, cfg.get("link_hosts") or [])
    elif not item.campaign:
        warnings.append("no link and no campaign: nothing will be tagged")
    for p in item.platforms:
        if p not in PLATFORMS:
            continue
        spec = SPEC[p]
        if not cfg["platforms"].get(p, {}).get("enabled"):
            warnings.append(f"{p}: disabled in config; it will be skipped until Ben enables it")
        if not item.raw_text(p).strip():
            errors.append(f"{p}: no text (add a `## default` or `## {p}` section)")
            continue
        errors += text_limit_errors(p, item.render(p))
        imgs = item.images_for(p)
        if spec["images"] == 0 and (item.meta.get("images")) and p not in (item.meta.get("text_only") or []):
            errors.append(f"{p}: the LinkedIn poster cannot attach images; list {p!r} in text_only to post it "
                          f"without them, or use `document` with a PDF")
        if len(imgs) > spec["images"]:
            errors.append(f"{p}: {len(imgs)} images, limit {spec['images']}")
        if item.document() and not spec["document"]:
            if p in (item.meta.get("document_platforms") or ["linkedin"]):
                errors.append(f"{p}: documents are LinkedIn only")
        for im in imgs:
            errors += _image_errors(p, im, item)
    d = item.document()
    if d:
        f = _resolve(d.get("path", ""), item.path.parent)
        if f.suffix.lower() != ".pdf" or not f.is_file():
            errors.append(f"document must be an existing .pdf: {d.get('path')}")
        if not str(d.get("title") or "").strip():
            errors.append("document needs a title")
        if "linkedin" not in item.platforms:
            errors.append("document is only used by linkedin, which is not in platforms")
    return errors, warnings


def _image_errors(platform: str, im: dict, item: Item) -> list[str]:
    spec = SPEC[platform]
    out: list[str] = []
    f = image_path(item, im)
    tag = f"{platform}: image {im.get('path')!r}"
    if not f.is_file():
        return [f"{tag} does not exist"]
    ext = f.suffix.lower()
    if ext not in IMAGE_EXT or ext not in spec["formats"]:
        out.append(f"{tag} has format {ext or '(none)'}; {platform} takes {', '.join(spec['formats'])}")
    else:
        head = f.open("rb").read(16)
        if not any(head.startswith(sig) for sig in MAGIC[ext]):
            out.append(f"{tag} is not really a {ext} file")
    size = f.stat().st_size
    if size > spec["image_bytes"]:
        out.append(f"{tag} is {size // 1024} KB, limit {spec['image_bytes'] // 1024} KB")
    if size == 0:
        out.append(f"{tag} is empty")
    alt = str(im.get("alt") or "").strip()
    if not alt:
        out.append(f"{tag} has no alt text")
    elif len(alt) > spec["alt"]:
        out.append(f"{tag} alt text is {len(alt)} characters, limit {spec['alt']}")
    return out


# ---------------------------------------------------------------- queue
def new_id(slug: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")[:48] or "post"
    return f"{dt.date.today():%Y%m%d}-{slug}"


def list_items() -> list[Item]:
    d = paths.queue_dir()
    d.mkdir(parents=True, exist_ok=True)
    items = []
    for f in sorted(d.glob("*.md")):
        try:
            items.append(Item.load(f))
        except Exception:
            continue
    return items


def find(item_id: str) -> Item:
    d = paths.queue_dir()
    exact = d / f"{item_id}.md"
    if exact.exists():
        return Item.load(exact)
    hits = [i for i in list_items() if str(i.id).startswith(item_id)]
    if len(hits) != 1:
        raise KeyError(f"{'no' if not hits else 'several'} queue items match {item_id!r}")
    return hits[0]


TEMPLATE_PLATFORMS = ["linkedin", "bluesky"]


def create(slug: str, platforms: list[str] | None = None, link: str = "", campaign: str = "",
           when: str | None = None, text: str = "") -> Item:
    paths.queue_dir().mkdir(parents=True, exist_ok=True)
    iid = new_id(slug)
    path = paths.queue_dir() / f"{iid}.md"
    n = 2
    while path.exists():
        path = paths.queue_dir() / f"{iid}-{n}.md"
        n += 1
    meta = {
        "id": path.stem,
        "created": iso(now()),
        "scheduled_at": when or iso(now() + dt.timedelta(days=1)),
        "status": "draft",
        "approved_by": None,
        "approved_at": None,
        "platforms": platforms or TEMPLATE_PLATFORMS,
        "campaign": campaign,
        "link": link,
        "images": [],
        "text_only": [],
        "experiment_note": "",
        "results": {},
    }
    sections = {"default": text or "Write the post here. Use {link} where the tagged link should go."}
    it = Item(path, meta, sections, "Notes (not posted): who asked for this, what it tests.")
    it.save()
    return it


def approve(item: Item, cfg: dict, who: str = "ben") -> None:
    if item.status not in ("draft", "stale", "failed"):
        raise ValueError(f"cannot approve an item that is {item.status}")
    errors, _ = validate(item, cfg)
    if errors:
        raise ValueError("fix these first:\n  " + "\n  ".join(errors))
    t = item.scheduled()
    if t and (now() - t).total_seconds() > cfg.get("stale_hours", 48) * 3600:
        raise ValueError(f"scheduled_at {item.meta['scheduled_at']} is more than {cfg.get('stale_hours', 48)} hours "
                         f"in the past; set a new scheduled_at first")
    item.meta["status"] = "approved"
    item.meta["approved_by"] = who
    item.meta["approved_at"] = iso(now())
    item.meta["approved_hash"] = item.content_hash()
    # a failed platform gets a fresh start on re-approval; a posted one is never reposted
    for p, r in list(item.results.items()):
        if r.get("status") == "failed":
            item.results[p] = {"status": "pending", "attempts": 0}
    item.save()


def cancel(item: Item) -> None:
    if item.status == "posted":
        raise ValueError("already posted")
    item.meta["status"] = "cancelled"
    item.save()


def due_local_window(t: dt.datetime, cfg: dict) -> bool:
    tz = ZoneInfo(cfg.get("timezone", "America/New_York"))
    local = t.astimezone(tz)
    w = cfg["windows"]
    if local.weekday() not in w["days"]:
        return False
    hm = f"{local:%H:%M}"
    return w["start"] <= hm <= w["end"]
