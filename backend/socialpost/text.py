"""Text measuring and link/UTM building."""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .spec import SPEC, URL_WEIGHT

URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.I)


def graphemes(s: str) -> int:
    """Approximate user-perceived characters: combining marks, variation selectors, ZWJ sequences and
    regional-indicator pairs do not add to the count."""
    n = 0
    prev_zwj = False
    ri = 0
    for ch in s:
        cp = ord(ch)
        if unicodedata.combining(ch) or 0xFE00 <= cp <= 0xFE0F or 0x1F3FB <= cp <= 0x1F3FF or cp == 0x200D \
                or unicodedata.category(ch) in ("Mn", "Me"):
            prev_zwj = cp == 0x200D
            continue
        if prev_zwj:
            prev_zwj = False
            continue
        if 0x1F1E6 <= cp <= 0x1F1FF:
            ri += 1
            if ri % 2 == 0:
                continue
        else:
            ri = 0
        n += 1
    return n


def measure(text: str, how: str) -> int:
    if how == "graphemes":
        return graphemes(text)
    if how in ("x", "mastodon"):
        return len(URL_RE.sub("x" * URL_WEIGHT, text))
    return len(text)


def text_limit_errors(platform: str, text: str) -> list[str]:
    spec = SPEC[platform]
    n = measure(text, spec["count"])
    if n > spec["text"]:
        return [f"{platform}: text is {n} {spec['count']} long, limit {spec['text']}"]
    if not text.strip():
        return [f"{platform}: text is empty"]
    return []


def utm_link(link: str, platform: str, campaign: str) -> str:
    """Add utm_source=<platform>&utm_medium=social&utm_campaign=<campaign>, keeping other query parameters."""
    parts = urlsplit(link)
    q = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not k.startswith("utm_")]
    q += [("utm_source", platform), ("utm_medium", "social"), ("utm_campaign", campaign)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment))


def link_errors(link: str, campaign: str, allowed_hosts: list[str]) -> list[str]:
    errs: list[str] = []
    p = urlsplit(link)
    if p.scheme != "https" or not p.netloc:
        errs.append("link must be an https URL")
    elif allowed_hosts and p.hostname not in allowed_hosts:
        errs.append(f"link host {p.hostname!r} is not in link_hosts {allowed_hosts}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,60}", campaign or ""):
        errs.append("campaign must be lowercase letters, digits, dots, dashes or underscores")
    if re.search(r"[?&]utm_", link):
        errs.append("put the bare link in `link`; per-platform UTM tags are added when rendering")
    return errs
