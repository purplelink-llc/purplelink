"""Event detection and facts, read only from the live site and the public YouTube feed.

Three event kinds:
  guide_live         a /guides/<slug>/ URL appears in the live sitemap.xml and the page answers 200
  release_published  a product page's JSON-LD softwareVersion changes AND the live changelog has "<App> <version>"
  video_published    a new long video (not a Short) in the Purplelink channel's public RSS feed

Builds are batched (06:00 and 17:00 Eastern), so a merged page is not live until the next build. Reading the live
site means a merge alone never produces an event, and every fact (title, version, price) comes from what visitors see.
"""
from __future__ import annotations

import html as html_lib
import json
import re
from pathlib import Path

from core import SITE, Skip, plain

ROOT = Path(__file__).resolve().parents[2]

# Product pages whose releases are announced. The slug is also the short-link name (/bs/<slug> and so on).
PRODUCTS = {
    "moderntex": "/moderntex/",
    "outbound-veil": "/outbound-veil/",
    "legroom": "/legroom/",
    "keyfeel": "/keyfeel/",
    "tapefolio": "/tapefolio/",
    "vitae": "/vitae/",
    "panely": "/panely/",
    "summonly": "/summonly/",
    "batterymeter": "/batterymeter/",
}
CHANGELOG = f"{SITE}/changelog/"
GUIDE_RE = re.compile(r"^https://purplelink\.llc/guides/([a-z0-9][a-z0-9-]*)/$")


def youtube_channel_id() -> str:
    """The Purplelink channel id, from the one registry of channels (scripts/yt-channels.json)."""
    reg = json.loads((ROOT / "scripts" / "yt-channels.json").read_text())
    ch = reg["channels"]["purplelink"]
    if not ch.get("confirmed"):
        raise Skip("purplelink channel is not confirmed in yt-channels.json")
    return ch["id"]


def get_live(http, url: str) -> str:
    r = http.request("GET", url)
    if r.status != 200:
        raise Skip(f"{url} answered {r.status}, not 200 (not live yet?)")
    return r.text


# ---------------------------------------------------------------- small HTML readers
def meta(page: str, key: str) -> str:
    for pat in (rf'<meta[^>]+(?:name|property)="{re.escape(key)}"[^>]+content="([^"]*)"',
                rf'<meta[^>]+content="([^"]*)"[^>]+(?:name|property)="{re.escape(key)}"'):
        m = re.search(pat, page, re.I)
        if m:
            return html_lib.unescape(m.group(1)).strip()
    return ""


def strip_tags(s: str) -> str:
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    s = html_lib.unescape(re.sub(r"<[^>]+>", " ", s))
    # Removing a tag leaves a space before the punctuation that followed it ("<b>1.9.0</b> ."). Close that gap only
    # when the mark ends a phrase, so a dot-prefixed word keeps its space ("a project's .claude/worktrees folder").
    s = re.sub(r" ([.,])(?=\s|$|[)\"'])", r"\1", plain(s))
    return s.replace("( ", "(").replace(" )", ")")


def jsonld_objects(page: str) -> list:
    out = []
    for blob in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page, re.S | re.I):
        try:
            data = json.loads(blob)
        except ValueError:
            continue
        stack = [data]
        while stack:
            o = stack.pop()
            if isinstance(o, list):
                stack += o
            elif isinstance(o, dict):
                out.append(o)
                stack += [v for v in o.values() if isinstance(v, (dict, list))]
    return out


def h1(page: str) -> str:
    m = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S | re.I)
    return strip_tags(m.group(1)) if m else ""


def article_html(page: str) -> str:
    m = re.search(r'<article[^>]*class="[^"]*post-body[^"]*"[^>]*>(.*)</article>', page, re.S | re.I)
    if not m:
        m = re.search(r"<article[^>]*>(.*)</article>", page, re.S | re.I)
    return m.group(1) if m else ""


def paragraphs(fragment: str) -> list[str]:
    return [t for t in (strip_tags(p) for p in re.findall(r"<p[^>]*>(.*?)</p>", fragment, re.S | re.I)) if t]


def first_sentences(text: str, n: int = 1) -> str:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text.strip())
    return " ".join(parts[:n]).strip()


# ---------------------------------------------------------------- facts
def guide_facts(http, slug: str) -> dict:
    url = f"{SITE}/guides/{slug}/"
    page = get_live(http, url)
    title = plain(meta(page, "og:title") or h1(page))
    if not title:
        raise Skip(f"{url} has no title")
    return {"kind": "guide_live", "event_key": f"guide:{slug}", "slug": slug, "url": url, "title": title,
            "description": plain(meta(page, "description")), "paragraphs": paragraphs(article_html(page))[:4],
            "og_image": meta(page, "og:image")}


def release_facts(http, app: str) -> dict:
    """Version, name and price from the live product page's JSON-LD; the notes from the live changelog."""
    url = SITE + PRODUCTS[app]
    page = get_live(http, url)
    soft = next((o for o in jsonld_objects(page) if o.get("softwareVersion")), None)
    if not soft:
        raise Skip(f"{url} has no softwareVersion in its JSON-LD")
    name, version = str(soft.get("name") or "").strip(), str(soft["softwareVersion"]).strip()
    offers = soft.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    price = str(offers.get("price", "")).strip()
    once = bool(price) and price != "0" and bool(
        re.search(rf"\${re.escape(price)}[^<.]{{0,40}}\b(once|one-time)\b|single \${re.escape(price)}", page, re.I))
    log_page = get_live(http, CHANGELOG)
    m = re.search(rf"<h2[^>]*>\s*{re.escape(name)}\s+{re.escape(version)}\s*</h2>\s*<p[^>]*>(.*?)</p>",
                  log_page, re.S | re.I)
    if not m:
        raise Skip(f"the live changelog has no '{name} {version}' entry yet")
    return {"kind": "release_published", "event_key": f"release:{app}:{version}", "app_slug": app, "name": name,
            "version": version, "price": price, "price_once": once, "notes": strip_tags(m.group(1)), "url": url,
            "title": f"{name} {version}", "og_image": meta(page, "og:image")}


def _rss_entries(xml: str) -> list[dict]:
    out = []
    for e in re.findall(r"<entry>(.*?)</entry>", xml, re.S):
        vid = re.search(r"<yt:videoId>([\w-]{6,20})</yt:videoId>", e)
        title = re.search(r"<title>(.*?)</title>", e, re.S)
        desc = re.search(r"<media:description>(.*?)</media:description>", e, re.S)
        if vid and title:
            out.append({"video_id": vid.group(1), "title": plain(html_lib.unescape(title.group(1))),
                        "description": html_lib.unescape(desc.group(1)) if desc else ""})
    return out


def feed_videos(http) -> list[dict]:
    return _rss_entries(get_live(http, f"https://www.youtube.com/feeds/videos.xml?channel_id={youtube_channel_id()}"))


def is_short(http, video_id: str) -> bool:
    """youtube.com/shorts/<id> answers 200 for a Short and redirects to /watch for a normal video."""
    return http.request("HEAD", f"https://www.youtube.com/shorts/{video_id}", follow=False).status == 200


def clean_description(desc: str) -> str:
    """First paragraph of a video description, without links (they carry other channels' tags) or hashtags."""
    first = re.split(r"\n\s*\n", desc.strip())[0] if desc.strip() else ""
    first = re.sub(r"https?://\S+", "", first)
    first = re.sub(r"(^|\s)#\w+", " ", first)
    return plain(first).rstrip(" :")


def video_facts(http, video_id: str, entry: dict | None = None) -> dict:
    """Title from the public oEmbed endpoint (it answers only for a public video), description from the feed."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    r = http.request("GET", f"https://www.youtube.com/oembed?format=json&url={url}")
    data = r.json() if r.status == 200 else None
    if not isinstance(data, dict) or not data.get("title"):
        raise Skip(f"video {video_id} is not public yet (oEmbed {r.status})")
    if entry is None:
        entry = next((e for e in feed_videos(http) if e["video_id"] == video_id), {})
    return {"kind": "video_published", "event_key": f"video:{video_id}", "video_id": video_id, "url": url,
            "title": plain(data["title"]), "description": clean_description(entry.get("description", ""))}


def refetch(http, facts: dict) -> dict:
    """The same facts read again from the live source (standing approval compares them before posting)."""
    k = facts["kind"]
    if k == "guide_live":
        return guide_facts(http, facts["slug"])
    if k == "release_published":
        return release_facts(http, facts["app_slug"])
    if k == "video_published":
        return video_facts(http, facts["video_id"])
    raise Skip(f"unknown kind {k}")


FACT_KEYS = {"guide_live": ["title", "url"], "release_published": ["name", "version", "price", "url"],
             "video_published": ["title", "url"]}


def fact_drift(old: dict, new: dict) -> list[str]:
    return [f"{k}: queued {old.get(k)!r}, live {new.get(k)!r}" for k in FACT_KEYS[old["kind"]] if old.get(k) != new.get(k)]


# ---------------------------------------------------------------- scan
def scan(http, state: dict, *, seed: bool = False) -> tuple[list[dict], list[str]]:
    """New events since the last scan. With seed (or on the first run) everything live is recorded as seen and no
    event is returned, so the poster never announces the back catalogue. Returns (facts list, notes)."""
    seen, found, notes = state["seen"], [], []
    seed = seed or not state.get("seeded")

    try:
        sm = get_live(http, f"{SITE}/sitemap.xml")
        slugs = []
        for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sm):
            m = GUIDE_RE.match(loc)
            if m:
                slugs.append(m.group(1))
        for slug in slugs:
            if slug in seen["guides"]:
                continue
            if seed:
                seen["guides"].append(slug)
                continue
            try:
                found.append(guide_facts(http, slug))
                seen["guides"].append(slug)
            except Skip as e:
                notes.append(f"guide {slug}: {e}")
    except Skip as e:
        notes.append(f"sitemap: {e}")

    for app in PRODUCTS:
        try:
            f = release_facts(http, app)
        except Skip as e:
            notes.append(f"{app}: {e}")
            continue
        if seen["releases"].get(app) == f["version"]:
            continue
        if not seed and app in seen["releases"]:
            found.append(f)
        seen["releases"][app] = f["version"]

    try:
        for e in feed_videos(http):
            vid = e["video_id"]
            if vid in seen["videos"]:
                continue
            if seed:
                seen["videos"].append(vid)
                continue
            if is_short(http, vid):
                seen["videos"].append(vid)
                notes.append(f"video {vid}: a Short, not announced")
                continue
            try:
                found.append(video_facts(http, vid, e))
                seen["videos"].append(vid)
            except Skip as err:
                notes.append(f"video {vid}: {err}")
    except Skip as e:
        notes.append(f"youtube feed: {e}")

    state["seeded"] = True
    return found, notes
