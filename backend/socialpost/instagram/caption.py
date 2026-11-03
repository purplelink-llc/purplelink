"""Instagram captions, built only from text that already exists: the YouTube title and description (a Reel) or the
LinkedIn company post (a companion image post). Nothing is paraphrased, so the vetting gate can check every name and
number against its source. Links are dropped (a caption link is not clickable); the caption ends with "Link in bio."
and at most 5 hashtags. Voice: calm, plain, specific (PRODUCT.md); the daily gate's voice rules apply.
"""
from __future__ import annotations

import re

from ..daily import compose as comp
from ..daily import vet as vetmod
from ..items import HASHTAG_RE
from ..text import URL_RE

BIO = "Link in bio."
REEL_TAIL = "The full walkthrough is on our YouTube channel."
# Every sentence the caption templates add; the gate treats these words as template wording.
TEMPLATES = [BIO, REEL_TAIL]
FALLBACK_TAGS = ["mac", "macos", "mactips"]
MAX_TAGS = 5

# Companion posts: a topic tag from words in the post (lowercase, plain, no brand-new coinages).
TOPIC_TAGS = [
    (r"\blatex\b|bibtex|overleaf", "latex"), (r"citation|reference|bibliograph|manuscript|journal|paper", "academicwriting"),
    (r"\bmac\b|macos|menu bar|finder|spotlight", "macos"), (r"transcri", "transcription"),
    (r"privacy|tracking|on-device", "privacy"), (r"storage|disk|space", "macstorage"),
    (r"research|phd|academic|grant", "academiclife"), (r"keyboard|typing", "mechanicalkeyboard"),
]
APP_TAGS = {"latex-errors": "latex", "paper-review": "academicwriting", "globepin": "travel",
            "scholar-utility-belt": "googlescholar", "moderntex": "latex", "legroom": "macstorage", "outbound-veil": "dataprivacy", "panely": "windowmanagement",
            "summonly": "spotlight", "tapefolio": "transcription", "keyfeel": "typingsounds", "batterymeter": "macbattery",
            "vitae": "academiclife"}


def app_tags_for_link(link: str) -> list[str]:
    """The app's own tag when the link is its product page (https://purplelink.llc/<app>/...)."""
    m = re.match(r"https://(?:www\.)?purplelink\.llc/(?:tools/)?([a-z0-9-]+)/", link or "")
    return [APP_TAGS[m.group(1)]] if m and m.group(1) in APP_TAGS else []


def clean_title(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").replace("#shorts", "")).strip()


def _prose_paragraphs(description: str) -> list[str]:
    """Paragraphs of a YouTube description that are prose: no link, no hashtag line, no command block, no source list."""
    out = []
    for para in re.split(r"\n\s*\n", description or ""):
        p = para.strip()
        if not p or URL_RE.search(p) or p.startswith("#") or "\n" in p and ":" in p.split("\n", 1)[0]:
            continue
        if p.lower().startswith(("where this comes up", "full walkthrough", "the fix, in terminal")):
            continue
        out.append(re.sub(r"\s+", " ", p))
    return out


def _ok_sentence(s: str) -> bool:
    return not vetmod.voice_problems(s) and len(s.split()) <= 40


def _restates(sentence: str, title: str) -> bool:
    """True when most of the sentence's words are already in the title (a how-to opener repeats it as a question)."""
    words = set(re.findall(r"[a-z0-9]+", sentence.lower()))
    return bool(words) and len(words & set(re.findall(r"[a-z0-9]+", title.lower()))) / len(words) >= 0.7


def tags_from(text: str, extra: list[str] | None = None, fallback=FALLBACK_TAGS, limit: int = MAX_TAGS) -> list[str]:
    tags = []
    for t in [x.lstrip("#").lower() for x in HASHTAG_RE.findall(text or "")] + list(extra or []):
        if t and t != "shorts" and re.fullmatch(r"[a-z0-9]{2,30}", t) and t not in tags:
            tags.append(t)
    return (tags or list(fallback))[:limit]


def hashtag_line(tags: list[str]) -> str:
    return " ".join(f"#{t}" for t in tags)


def reel_caption(title: str, description: str, trimmed: bool = False, extra_tags: list[str] | None = None) -> str:
    """Title, then up to two prose sentences of the description, the YouTube pointer when the Reel was cut short,
    'Link in bio.' and the description's own hashtags (fallback #mac #macos #mactips)."""
    title = clean_title(title)
    body: list[str] = []
    for para in _prose_paragraphs(description):
        for s in comp.sentences(para) or [para]:
            s = s.strip()
            if s and not _restates(s, title) and _ok_sentence(s) and s not in body:
                body.append(s)
        if len(body) >= 2:
            break
    parts = [title if title[-1:] in ".?!" else title + "."] + ([" ".join(body[:2])] if body else [])
    if trimmed:
        parts.append(REEL_TAIL)
    parts.append(BIO)
    tags = tags_from(description, extra_tags, fallback=[])
    tags += [t for t in FALLBACK_TAGS if t not in tags][:max(0, 3 - len(tags))]   # at least 3, at most 5
    parts.append(hashtag_line(tags[:MAX_TAGS]))
    return "\n\n".join(parts)


def companion_caption(linkedin_text: str, extra_tags: list[str] | None = None) -> str:
    """The LinkedIn post as it went out, minus its link, plus 'Link in bio.' and up to 3 topic hashtags."""
    text = URL_RE.sub("", (linkedin_text or "").replace("{link}", ""))
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    low = text.lower()
    tags = list(extra_tags or [])
    tags += [tag for pat, tag in TOPIC_TAGS if re.search(pat, low)]
    tags = tags_from("", tags, fallback=["purplelink"], limit=3)
    return f"{text}\n\n{BIO}\n\n{hashtag_line(tags)}"


# ---------------------------------------------------------------- the card's words
HEAD_KICKERS = [
    (r"^New guide: (.+)$", "Guide"), (r"^New on the blog: (.+)$", "Blog"), (r"^New tool: (.+)$", "Tool"),
    (r"^New video: (.+)$", "Video"), (r"^From our guides: (.+)$", "Guide"), (r"^From our tools: (.+)$", "Tool"),
    (r"^From the blog: (.+)$", "Blog"), (r"^(.+?) is out\.$", "Release"),
]
BG_BY_KICKER = {"Release": "apps", "Guide": "research", "Tool": "research", "Blog": "general", "Video": "apps"}


def card_words(linkedin_text: str) -> dict:
    """{"title", "kicker", "sub", "bg"} for the feed image, read from the LinkedIn post's own first lines."""
    text = URL_RE.sub("", (linkedin_text or "").replace("{link}", "")).strip()
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    first = paras[0] if paras else ""
    head = first.split("\n", 1)[0].strip()
    title, kicker = head, ""
    for pat, k in HEAD_KICKERS:
        m = re.match(pat, head)
        if m:
            title, kicker = m.group(1).strip(), k
            break
    if not kicker and "? " in head:          # the question format: "<question>? <title>"
        title = head.split("? ", 1)[1].strip()
    title = title.rstrip(".")
    rest = " ".join(paras[1:]) if len(paras) > 1 else first[len(head):].strip()
    sub = next((s for s in comp.sentences(rest) if len(s) <= 150), "")
    bg = "latex" if re.search(r"latex|bibtex|overleaf", text, re.I) else BG_BY_KICKER.get(kicker, "general")
    return {"title": title, "kicker": kicker or "Purplelink", "sub": sub, "bg": bg}
