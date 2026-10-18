"""Shared pieces of the social poster: HTTP, config files, pinned identities, state, log, notify, limits.

Stdlib only. Nothing here posts. See docs/social-poster.md.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import ssl
import stat
import subprocess
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

SITE = "https://purplelink.llc"
EASTERN = ZoneInfo("America/New_York")

# Every channel the poster knows. Reddit, Hacker News and Product Hunt stay manual (drafts only, by hand) and must
# never be added here.
CHANNELS = ["linkedin", "bluesky", "threads", "x", "mastodon", "devto", "email"]

# Per-channel short-link prefix (netlify.toml redirects). /li/ is the existing LinkedIn set (PR 89).
LINK_PREFIX = {"linkedin": "li", "bluesky": "bs", "threads": "th", "x": "x", "mastodon": "md", "devto": "dev"}
UTM_SOURCE = {"linkedin": "linkedin", "bluesky": "bluesky", "threads": "threads", "x": "x", "mastodon": "mastodon",
              "devto": "devto", "email": "email-release"}

# The company account on each channel. A channel stays disabled until BOTH its pin here is filled in (by a reviewed
# commit) AND its mode-600 config file exists. A config edit alone cannot point the poster at another account, and a
# token for Ben's personal account fails the pin. Fill these from `poster.py whoami <channel> --unpinned` after Ben's
# one-time setup (docs/social-poster.md). None means "not set up yet".
PINS = {
    "bluesky": {"id": None, "handle": None},     # did:plc:..., and the handle
    "threads": {"id": None, "handle": None},     # numeric Threads user id, username
    "x": {"id": None, "handle": None},           # numeric user id, username without @
    "mastodon": {"id": None, "handle": None, "instance": None},  # account id, acct, https://server
    "devto": {"id": None, "handle": None},       # numeric user id, username
    "email": {"id": None, "handle": None},       # Resend segment id, segment name
    # LinkedIn is checked inside backend/scripts/linkedin_post.py (company 120183926, composer "Purplelink LLC").
    "linkedin": {"id": "120183926", "handle": "Purplelink LLC"},
}

# Limits per channel, each in the unit that service counts. links: most links one post may carry.
LIMITS = {
    "linkedin": {"chars": 3000},
    "bluesky": {"graphemes": 300},
    "threads": {"chars": 500, "links": 5},
    "x": {"weighted": 280},
    "mastodon": {"mastodon": 500},
    "devto": {},
    "email": {},
}
# Which event kinds each channel carries.
_ALL = {"guide_live", "video_published", "release_published"}
CHANNEL_KINDS = {"linkedin": _ALL, "bluesky": _ALL, "threads": _ALL, "x": _ALL, "mastodon": _ALL,
                 "devto": {"guide_live"}, "email": {"release_published"}}
STANDING_KINDS = set(_ALL)
DAY_CAP, WEEK_CAP, DUP_DAYS = 1, 3, 30

URL_RE = re.compile(r"https?://[^\s<>()\"']+")


def home() -> Path:
    return Path(os.environ.get("PURPLELINK_SOCIAL_HOME") or Path.home() / ".purplelink" / "social")


def config_dir() -> Path:
    return Path(os.environ.get("PURPLELINK_SOCIAL_CONFIG") or Path.home() / ".config" / "purplelink" / "social")


def now() -> dt.datetime:
    return dt.datetime.now(EASTERN)


def day_of(at: dt.datetime) -> dt.date:
    return at.astimezone(EASTERN).date()


# ---------------------------------------------------------------- errors
class Refused(Exception):
    """An identity check failed. Exit 4, notify, log, and no retry on that channel for the rest of the day."""


class Skip(Exception):
    """Not posted this run, for a reason that may clear later (quota, not live yet, disabled)."""


# ---------------------------------------------------------------- HTTP
class Response:
    def __init__(self, status: int, body: bytes = b"", headers: dict | None = None, url: str = ""):
        self.status, self.body, self.url = status, body, url
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", "replace")

    def json(self):
        try:
            return json.loads(self.body or b"null")
        except ValueError:
            return None


def _ssl_context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        ctx = ssl.create_default_context()
        if not ctx.get_ca_certs() and os.path.isfile("/etc/ssl/cert.pem"):
            ctx = ssl.create_default_context(cafile="/etc/ssl/cert.pem")
        return ctx


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


class Http:
    """The only door to the network. Tests replace it with a fake that never opens a socket."""

    def request(self, method: str, url: str, *, headers: dict | None = None, json_body=None, form: dict | None = None,
                data: bytes | None = None, follow: bool = True, timeout: int = 20) -> Response:
        hdrs = {"User-Agent": "purplelink-social-poster/1 (+https://purplelink.llc)", **(headers or {})}
        if json_body is not None:
            data = json.dumps(json_body).encode()
            hdrs.setdefault("Content-Type", "application/json")
        elif form is not None:
            data = urllib.parse.urlencode(form).encode()
            hdrs.setdefault("Content-Type", "application/x-www-form-urlencoded")
        req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
        handlers = [urllib.request.HTTPSHandler(context=_ssl_context())]
        if not follow:
            handlers.append(_NoRedirect())
        opener = urllib.request.build_opener(*handlers)
        try:
            with opener.open(req, timeout=timeout) as r:
                return Response(r.status, r.read(), dict(r.headers), r.geturl())
        except urllib.error.HTTPError as e:
            return Response(e.code, e.read() if e.fp else b"", dict(e.headers or {}), url)
        except (urllib.error.URLError, OSError) as e:
            return Response(0, str(e).encode(), {}, url)


# ---------------------------------------------------------------- config
def load_config(channel: str) -> dict | None:
    """The channel's private config, or None when it does not exist. Refuses a file others can read."""
    p = config_dir() / f"{channel}.json"
    if not p.exists():
        return None
    mode = stat.S_IMODE(p.stat().st_mode)
    if mode & 0o077:
        raise Refused(f"{p.name} is mode {oct(mode)}; it must be 600")
    return json.loads(p.read_text())


def save_config(channel: str, cfg: dict) -> None:
    """Write a config back (token refresh), mode 600 from the first byte."""
    p = config_dir() / f"{channel}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump(cfg, fh, indent=1)
    os.chmod(tmp, 0o600)
    os.replace(tmp, p)


def pin(channel: str) -> dict:
    return PINS.get(channel) or {}


def pinned(channel: str) -> bool:
    p = pin(channel)
    return bool(p.get("id")) and bool(p.get("handle"))


# ---------------------------------------------------------------- state and log
def load_state() -> dict:
    p = home() / "state.json"
    st = json.loads(p.read_text()) if p.exists() else {}
    st.setdefault("seeded", False)
    st.setdefault("seen", {})
    for k, v in (("guides", []), ("releases", {}), ("videos", [])):
        st["seen"].setdefault(k, v)
    st.setdefault("posts", [])
    st.setdefault("refused", {})
    return st


def save_state(st: dict) -> None:
    home().mkdir(parents=True, exist_ok=True)
    p = home() / "state.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=1))
    os.replace(tmp, p)


def log(event: str, **fields) -> None:
    home().mkdir(parents=True, exist_ok=True)
    rec = {"ts": now().isoformat(timespec="seconds"), "event": event, **fields}
    with (home() / "log.jsonl").open("a") as fh:
        fh.write(json.dumps(rec) + "\n")


def notify(msg: str) -> None:
    if os.environ.get("PURPLELINK_SOCIAL_NO_NOTIFY"):
        return
    try:
        safe = msg.replace("\\", "").replace('"', "'")[:200]
        subprocess.run(["/usr/bin/osascript", "-e", f'display notification "{safe}" with title "Purplelink poster"'],
                       check=False, capture_output=True, timeout=10)
    except Exception:
        pass


def text_hash(text: str) -> str:
    """Hash of the words without links, so the same text with a different short link still counts as a duplicate."""
    norm = re.sub(r"\s+", " ", URL_RE.sub("", text)).strip().lower()
    return hashlib.sha256(norm.encode()).hexdigest()[:16]


# ---------------------------------------------------------------- length rules
def graphemes(s: str) -> int:
    """Bluesky counts graphemes. Without a segmentation library: combining marks, variation selectors, skin tones and
    characters joined by ZWJ do not start a new grapheme. Exact for the plain text the poster writes."""
    n, join = 0, False
    for ch in s:
        if ch == "‍":
            join = True
            continue
        if unicodedata.combining(ch) or 0xFE00 <= ord(ch) <= 0xFE0F or 0x1F3FB <= ord(ch) <= 0x1F3FF:
            continue
        if join:
            join = False
            continue
        n += 1
    return n


def x_weighted(s: str) -> int:
    """X: every URL counts 23; code points above U+10FF (CJK, emoji) count 2; the rest count 1."""
    body = URL_RE.sub("", s)
    return 23 * len(URL_RE.findall(s)) + sum(2 if ord(c) > 0x10FF else 1 for c in body)


def mastodon_len(s: str) -> int:
    """Mastodon: every URL counts 23 characters."""
    return 23 * len(URL_RE.findall(s)) + len(URL_RE.sub("", s))


def length_of(channel: str, text: str) -> tuple[int, int] | None:
    lim = LIMITS.get(channel, {})
    if "graphemes" in lim:
        return graphemes(text), lim["graphemes"]
    if "weighted" in lim:
        return x_weighted(text), lim["weighted"]
    if "mastodon" in lim:
        return mastodon_len(text), lim["mastodon"]
    if "chars" in lim:
        return len(text), lim["chars"]
    return None


def limit_problems(channel: str, text: str) -> list[str]:
    out = []
    if not text.strip():
        return [f"{channel}: empty"]
    ln = length_of(channel, text)
    if ln and ln[0] > ln[1]:
        out.append(f"{channel}: {ln[0]} over the limit of {ln[1]}")
    max_links = LIMITS.get(channel, {}).get("links")
    n_links = len(URL_RE.findall(text))
    if max_links is not None and n_links > max_links:
        out.append(f"{channel}: {n_links} links, more than {max_links}")
    return out


EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐⭕️]")
HYPE = ["game-changer", "game changer", "revolutionize", "revolutionary", "cutting-edge", "cutting edge",
        "unlock the power", "supercharge", "seamless", "leverage", "delve", "in today's fast-paced", "elevate your",
        "next level", "unleash", "empower", "robust solution", "look no further", "dive into", "tapestry",
        "excited to announce", "thrilled to", "must-have", "!!"]


def voice_problems(text: str) -> list[str]:
    """House voice (CLAUDE.md, .agents/product-marketing.md): no emoji, no em dash, no hype."""
    out = []
    if "—" in text:
        out.append("em dash")
    if EMOJI.search(text):
        out.append("emoji")
    low = text.lower()
    out += [f"phrase: {p}" for p in HYPE if p in low]
    return out


def plain(s: str) -> str:
    """Facts copied from a page, cleaned for a post: dashes that read as tics become plain punctuation."""
    s = re.sub(r"\s*—\s*", ", ", s)
    s = s.replace("–", "-").replace(" ", " ")
    return re.sub(r"\s+", " ", s).strip()


def short_link(channel: str, facts: dict) -> str:
    """The tracked link for one channel. Guides: /<p>/g/<slug>. Releases: /<p>/<app>. Videos: the YouTube watch URL
    (UTM tags on youtube.com reach no analytics of ours; YouTube's own traffic report splits visits by site)."""
    kind = facts["kind"]
    if kind == "video_published":
        return facts["url"]
    if channel == "email":
        camp = facts.get("app_slug", "release")
        return f"{facts['url']}?utm_source=email-release&utm_medium=email&utm_campaign=release-{camp}"
    p = LINK_PREFIX[channel]
    if kind == "guide_live":
        return f"{SITE}/{p}/g/{facts['slug']}"
    return f"{SITE}/{p}/{facts['app_slug']}"
