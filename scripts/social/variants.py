"""One variant per channel from one set of live facts. Plain templates, house voice: no emoji, no hype, no em dash.

Each short variant is fitted to its channel's limit by dropping whole sentences from the summary, never by
cutting a word or a fact (name, version, price, link) out.
"""
from __future__ import annotations

from core import CHANNEL_KINDS, CHANNELS, length_of, limit_problems, short_link, voice_problems
from events import first_sentences

POSTAL_ADDRESS = "Purplelink LLC, 8735 Dunwoody Place STE N, Atlanta, GA 30350, USA"  # netlify/lib/rubblefront-list.mjs
SHORT = ("bluesky", "threads", "x", "mastodon")


def _sentences(text: str) -> list[str]:
    out, rest = [], text.strip()
    while rest:
        s = first_sentences(rest, 1)
        if not s:
            break
        out.append(s)
        rest = rest[len(s):].strip()
    return out


def _fit(channel: str, build, summary: str) -> str:
    """build(summary_text) -> post. Uses as many leading sentences of summary as fit, else none."""
    sents = _sentences(summary)
    for n in range(len(sents), -1, -1):
        text = build(" ".join(sents[:n]))
        ln = length_of(channel, text)
        if not ln or ln[0] <= ln[1]:
            return text
    return build("")


def _join(*parts: str) -> str:
    return "\n\n".join(p.strip() for p in parts if p and p.strip())


def price_line(f: dict) -> str:
    if f.get("price") in ("0", "0.00"):
        return f"{f['name']} is free to download."
    if f.get("price"):
        return f"Price: ${f['price']}{' once' if f.get('price_once') else ''}."
    return ""


def short_variant(channel: str, f: dict) -> str:
    link = short_link(channel, f)
    if f["kind"] == "guide_live":
        return _fit(channel, lambda s: _join(f"New guide: {f['title']}", s, link), f.get("description", ""))
    if f["kind"] == "release_published":
        return _fit(channel, lambda s: _join(f"{f['name']} {f['version']} is out.", s, price_line(f), link), f["notes"])
    return _fit(channel, lambda s: _join(f"New video: {f['title']}", s, link), f.get("description", ""))


def linkedin_variant(f: dict) -> str:
    link = short_link("linkedin", f)
    if f["kind"] == "guide_live":
        body, used = [], 0
        for p in f.get("paragraphs", []):
            if used + len(p) > 1100:
                break
            body.append(p)
            used += len(p)
        return _join(f["title"], f.get("description", ""), *body, f"Read the guide: {link}")
    if f["kind"] == "release_published":
        return _join(f"{f['name']} {f['version']}", f["notes"][:1800], price_line(f), f"Details and download: {link}")
    return _join(f"New video: {f['title']}", f.get("description", "")[:1200], f"Watch: {link}")


def email_variant(f: dict) -> dict:
    link = short_link("email", f)
    text = _join(f"{f['name']} {f['version']} is out.", f["notes"], price_line(f),
                 f"Download it, or update from inside the app with Check for Updates: {link}")
    return {"subject": f"{f['name']} {f['version']}", "text": text}


def devto_variant(f: dict) -> dict:
    """Metadata only: the article body is read from the live page at post time (events.devto_markdown)."""
    tags = ["mac", "macos", "productivity", "guide"]  # dev.to allows 4
    return {"title": f["title"], "canonical_url": f["url"], "description": f.get("description", "")[:250], "tags": tags}


def build_all(f: dict) -> dict:
    """{channel: text or dict} for every channel that carries this event kind."""
    out = {}
    for ch in CHANNELS:
        if f["kind"] not in CHANNEL_KINDS[ch]:
            continue
        if ch in SHORT:
            out[ch] = short_variant(ch, f)
        elif ch == "linkedin":
            out[ch] = linkedin_variant(f)
        elif ch == "email":
            out[ch] = email_variant(f)
        elif ch == "devto":
            out[ch] = devto_variant(f)
    return out


def variant_text(v) -> str:
    return v if isinstance(v, str) else v.get("text") or v.get("title", "")


def problems(variants: dict) -> list[str]:
    out = []
    for ch, v in variants.items():
        t = variant_text(v)
        out += limit_problems(ch, t)
        out += [f"{ch}: {p}" for p in voice_problems(t)]
    return out
