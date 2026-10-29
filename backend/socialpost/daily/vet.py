"""The vetting gate. A post is queued only when every rule passes; the first failure is the reason the pipeline logs
before it tries the next candidate. Rules:

  voice      none of the banned words or characters (em dash, emoji, hype phrases, exclamation marks); Mastodon
             text is also held to Ben's own voice rules (his benampel skill), see ben_voice_problems
  facts      every number and every name in the text appears in the source facts (or is template wording)
  link       the link answers HTTP 200 and is the live page (a page waiting for a build is not live)
  utm        every platform's link carries utm_source=<platform>&utm_medium=social&utm_campaign=daily-<kind>
  alt        every image has alt text
  limits     each platform's text, image count and size are within its limits (the queue validator)
  duplicate  no near-duplicate of a post from the last `dup_days`
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re
from urllib.parse import parse_qs, urlsplit

from .. import hubtags
from .. import items as itemsmod
from ..text import URL_RE
from . import lib219 as L
from .compose import FILLER_PHRASES
from .compose import MAX_SENTENCE_WORDS as _MAX
from .compose import TEMPLATE_VOCAB
from .candidates import source_text

BANNED_PHRASES = [
    "game-changer", "game changer", "revolutionize", "revolutionary", "cutting-edge", "cutting edge", "unlock",
    "supercharge", "turbocharge", "seamless", "leverage", "delve", "fast-paced", "elevate", "next level",
    "unleash", "empower", "robust", "look no further", "dive into", "tapestry", "excited to", "thrilled",
    "must-have", "powerful", "innovative", "world-class", "best-in-class", "state-of-the-art", "blazing",
    "effortless", "ultimate", "stunning", "amazing", "incredible", "reimagine", "no-brainer", "synergy",
    "streamline", "transform your", "take your", "in today's",
]
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️‍]")
BAD_CHARS = {"—": "em dash", "–": "en dash", "!": "exclamation mark", "--": "double hyphen"}


class Verdict:
    def __init__(self):
        self.reasons: list[str] = []

    def fail(self, rule: str, why: str) -> None:
        self.reasons.append(f"{rule}: {why}")

    @property
    def ok(self) -> bool:
        return not self.reasons


def strip_urls(s: str) -> str:
    return URL_RE.sub(" ", s)


def voice_problems(text: str) -> list[str]:
    body = strip_urls(text)
    out = [f"{name}" for ch, name in BAD_CHARS.items() if ch in body]
    if EMOJI.search(body):
        out.append("emoji")
    low = body.lower()
    out += [f"banned word or phrase {p!r}" for p in BANNED_PHRASES if p in low]
    out += [f"house voice: {p}" for p in L.voice_problems(body) if p not in ("em dash", "emoji")
            and not p.startswith("phrase:")]
    return out


# Ben's voice for Mastodon (his `benampel` skill, tutorial register). Rejects the AI tells that skill names.
BEN_BANNED = [
    "moreover", "furthermore", "notably", "importantly", "nevertheless", "consequently", "that said", "thus",
    "delve", "landscape of", "crucial", "pivotal", "paramount", "myriad", "multifaceted", "realm", "tapestry",
    "boasts", "bolstered", "embark", "enduring", "foster", "garner", "groundbreaking", "interplay", "intricate",
    "meticulous", "showcas", "synergy", "testament", "transformative", "unparalleled", "utilize", "vibrant",
    "poised", "beacon", "paradigm", "plethora", "nuanced", "unpack", "rapidly evolving", "in order to",
    "it is worth noting", "it is important to", "it should be emphasized", "when it comes to", "serves as",
    "stands as", "functions as", "not only", "not just", "rather than", "well-known that",
]
PARTICIPIAL_TAIL = re.compile(r",\s+(highlighting|underscoring|showcasing|contributing|emphasizing|reflecting|"
                              r"demonstrating|illustrating)\b", re.I)
MAX_SENTENCE_WORDS = _MAX


def ben_voice_problems(text: str) -> list[str]:
    """Mastodon is posted as Ben. Beyond the global voice rules: none of his skill's banned words or constructions,
    no rhetorical questions, no semicolons, no sentence over 30 words, no negative parallelism or participial tail."""
    body = strip_urls(text)
    low = body.lower()
    out = [f"Ben's voice: {w!r} is not how he writes" for w in BEN_BANNED if re.search(rf"\b{re.escape(w)}", low)]
    if PARTICIPIAL_TAIL.search(body):
        out.append("Ben's voice: participial tail (', highlighting ...')")
    if "?" in body:
        out.append("Ben's voice: no rhetorical questions in a post")
    if ";" in body:
        out.append("Ben's voice: no semicolons")
    for sent in re.split(r"(?<=[.!?])\s+|\n+", body):
        if len(sent.split()) > MAX_SENTENCE_WORDS:
            out.append(f"Ben's voice: a sentence of {len(sent.split())} words (limit {MAX_SENTENCE_WORDS})")
    return out


STOP = set("""that this with from have will your they them then than were what when where which there their about into
    also been being does done each even ever just like made make many more most much must only other over same
    some such take than very well week release changelog page link words word guide tool video post site new""".split())


def filler_problems(text: str, source: str) -> list[str]:
    """No sentence that says nothing: the old fixed phrases are rejected outright, and every sentence must contain at
    least one content word (a noun, a name or a number) that is in the page's own facts."""
    body = strip_urls(text)
    low = body.lower()
    out = [f"filler phrase {p!r}" for p in FILLER_PHRASES if p in low]
    src = _words(source)
    for sent in re.split(r"(?<=[.!?])\s+|\n+", body):
        sent = sent.strip()
        if not sent:
            continue
        toks = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9'\-]+|\d[\d.,]*\d", sent)]
        content = [w for w in toks if (len(w) >= 4 or w[0].isdigit()) and w not in STOP]
        if not any(w in src for w in content):
            out.append(f"filler sentence with no noun from the source facts: {sent[:60]!r}")
    return out


def _words(s: str) -> set[str]:
    return {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9'\-]*|\d[\d.,]*\d|\d", s)}


def facts_problems(text: str, source: str) -> list[str]:
    """Numbers: every number in the text must be in the source. Names: every capitalised word or word containing a
    digit must be in the source or in the template wording."""
    body = strip_urls(text)
    src_words = _words(source)
    src_nums = set(re.findall(r"\d[\d.,]*\d|\d", source))
    out = []
    for num in sorted(set(re.findall(r"\d[\d.,]*\d|\d", body))):
        if num not in src_nums:
            out.append(f"number {num!r} is not in the page's own facts")
    for w in sorted(set(re.findall(r"\b[A-Z][A-Za-z0-9'\-]*\b|\b[A-Za-z]+\d[A-Za-z0-9]*\b", body))):
        lw = w.lower()
        if lw in src_words or lw in TEMPLATE_VOCAB:
            continue
        if re.fullmatch(r"[A-Z]", w):
            continue
        out.append(f"name {w!r} is not in the page's own facts")
    return out


def utm_problems(item, kind: str) -> list[str]:
    out = []
    for p in item.platforms:
        urls = URL_RE.findall(item.render(p))
        if not urls:
            out.append(f"{p}: no link in the text")
            continue
        for u in urls:
            q = parse_qs(urlsplit(u).query)
            want = {"utm_source": [p], "utm_medium": ["social"], "utm_campaign": [f"daily-{kind}"]}
            miss = [k for k, v in want.items() if q.get(k) != v]
            if miss:
                out.append(f"{p}: link is missing or has wrong {', '.join(miss)}")
            if hubtags.on_site(u) and not (q.get("utm_content") or [""])[0]:
                out.append(f"{p}: the purplelink.llc link has no utm_content from the marketing hub (unmeasurable)")
    return out


def alt_problems(item) -> list[str]:
    return [f"image {im.get('path')!r} has no alt text" for im in item.meta.get("images") or []
            if not str(im.get("alt") or "").strip()]


def text_hash(text: str) -> str:
    norm = re.sub(r"\s+", " ", strip_urls(text)).strip().lower()
    return hashlib.sha256(norm.encode()).hexdigest()[:16]


def duplicate_problems(c, texts: dict[str, str], history: list[dict], today: dt.date, dup_days: int,
                       platforms: list[str]) -> list[str]:
    """No repeat of this item on a platform within `dup_days` (outside posts count), and no identical text."""
    from .score import blocked_platforms
    out = [f"{c.id} was already posted on {p} within {dup_days} days"
           for p in sorted(blocked_platforms(c, history, today, dup_days, platforms) & set(platforms))]
    hashes = {text_hash(t) for t in texts.values()}
    for h in history:
        if h.get("external") or not h.get("counts", True):
            continue
        age = (today - dt.date.fromisoformat(str(h["date"])[:10])).days
        if age < dup_days and h.get("candidate") != c.id and hashes & set(h.get("hashes", [])):
            out.append(f"the same text was posted {age} days ago ({h.get('candidate')})")
    return out


def link_problems(http, url: str) -> list[str]:
    """The link answers 200 and, for a page on our own site, ends on the same page (not a redirect elsewhere)."""
    try:
        r = http.request("GET", url)
    except Exception as e:
        return [f"link could not be read: {type(e).__name__}"]
    if r.status != 200:
        return [f"link answered {r.status}, not 200 (not live yet?)"]
    if urlsplit(url).hostname in ("www.youtube.com", "youtube.com", "youtu.be"):
        return []
    final = getattr(r, "url", "") or url
    a, b = urlsplit(url), urlsplit(final)
    if b.netloc and (b.netloc != a.netloc or b.path.rstrip("/") != a.path.rstrip("/")):
        return [f"link ends on {final}, a different page"]
    return []


def vet(item, c, facts: dict, texts: dict[str, str], http, history: list[dict], today: dt.date, cfg: dict,
        main_cfg: dict, link_check: bool = True) -> Verdict:
    """Run every rule. `item` is the in-memory queue item built for this post."""
    v = Verdict()
    source = source_text(facts)
    for p in item.platforms:
        rendered = item.render(p)
        for why in voice_problems(rendered):
            v.fail("voice", f"{p}: {why}")
        if p == "mastodon":
            for why in ben_voice_problems(rendered) + filler_problems(rendered, source):
                v.fail("voice", f"{p}: {why}")
        for why in facts_problems(item.raw_text(p), source):
            v.fail("facts", f"{p}: {why}")
    for why in utm_problems(item, c.kind):
        v.fail("utm", why)
    for why in alt_problems(item):
        v.fail("alt", why)
    errors, _ = itemsmod.validate(item, main_cfg)
    for why in errors:
        v.fail("limits", why)
    for why in duplicate_problems(c, texts, history, today, cfg["dup_days"], list(item.platforms)):
        v.fail("duplicate", why)
    if link_check:
        for why in link_problems(http, c.url):
            v.fail("link", why)
    return v
