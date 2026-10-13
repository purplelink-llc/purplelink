#!/usr/bin/env python3
"""Mechanical voice audit for site pages, following the benampel skill's pre-flight check.

  python3 scripts/voice_audit.py                 table of every page, worst first
  python3 scripts/voice_audit.py PATH [PATH...]  detail for chosen pages (files or folders under site/)
  python3 scripts/voice_audit.py --summary       totals only

It reads the visible text of each page (scripts, styles, JSON-LD, comments and nav chrome removed),
and counts what the skill bans: AI-cliche vocabulary, Moreover/Furthermore-type connectives, throat-clearing,
negative parallelism, participial tails, em-dashes, semicolons, mid-sentence contrast words, and Title Case
headings, plus the median sentence length. It does not judge meaning, glosses or paragraph structure.
"""
import html
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"

BANNED = [
    "delve", "landscape of", "crucial role", "pivotal", "it is important to note", "in today", "realm",
    "tapestry", "paramount", "myriad", "moreover", "furthermore", "notably", "importantly", "nevertheless",
    "consequently", "it is worth noting", "truly ", "extremely ", "seamless", "unlock", "leverage", "robust",
    "cutting-edge", "game-changer", "powerful", "streamline", "elevate", "supercharge", "effortless",
    "journey", "embark", "foster", "showcase", "unpack", "plethora", "multifaceted", "testament", "transformative",
    "boasts", "utilize", "synergy", "intricate", "meticulous", "groundbreaking", "revolutionize", "unparalleled",
    "vibrant", "beacon", "paradigm", "poised",
]
THROAT = [
    r"\bour overall message\b", r"\bit is worth noting\b", r"\bit should be emphasized\b", r"\bwhat we found is that\b",
    r"\bthe key point here\b", r"\bone thing to note\b", r"\bwe would like to point out\b", r"\bit is important to (understand|note|remember)\b",
    r"\bthe fact that\b", r"\bin terms of\b", r"\bwhen it comes to\b", r"\bdue to the fact\b", r"\bin order to\b",
    r"\bas mentioned (above|previously)\b", r"\bit turns out that\b", r"\bkeep in mind that\b", r"\bneedless to say\b",
    r"\bat the end of the day\b", r"\bsimply put\b",
]
NEG_PARALLEL = [r"\bnot just\b[^.]{0,80}\bbut\b", r"\bnot only\b[^.]{0,80}\bbut\b", r"\bnot merely\b", r"\bisn't just\b", r"\bis not just\b"]
PARTICIPIAL = [r",\s+(highlighting|underscoring|showcasing|contributing to|reflecting|ensuring|enabling|allowing|making it)\b"]
COPULA = [r"\b(serves as|stands as|functions as|acts as|represents a)\b"]
SIGNIFICANCE = [r"\bfar-reaching\b", r"\bpivotal moment\b", r"\bsignificant shift\b", r"\bbroader landscape\b", r"\bgame[- ]changing\b"]
MIDCONTRAST = re.compile(r",\s+(although|while|whereas)\b", re.I)


def visible_text(raw: str) -> str:
    raw = re.sub(r"<!--.*?-->", " ", raw, flags=re.S)
    raw = re.sub(r"<(script|style|noscript|svg|template|pre|code|kbd|samp)\b.*?</\1>", " ", raw, flags=re.S | re.I)
    m = re.search(r"<main\b.*?</main>", raw, flags=re.S | re.I)
    if m:
        raw = m.group(0)
    raw = re.sub(r"<(nav|header|footer|form|button)\b.*?</\1>", " ", raw, flags=re.S | re.I)
    raw = re.sub(r"</(p|div|li|h[1-6]|tr|section|article|ul|ol|table|blockquote|pre)>", "\n", raw, flags=re.I)
    raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return html.unescape(re.sub(r"[ \t]+", " ", raw))


def headings(raw: str):
    return [html.unescape(re.sub(r"<[^>]+>", "", h)).strip() for h in re.findall(r"<h[2-4][^>]*>(.*?)</h[2-4]>", raw, flags=re.S | re.I)]


def title_case(h: str) -> bool:
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'-]*", h) if len(w) > 3]
    return len(words) >= 3 and sum(w[0].isupper() for w in words) >= len(words) - 1 and not h.isupper()


def sentences(text: str):
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        out += [s for s in re.split(r"(?<=[.!?])\s+", line) if len(s.split()) > 3]
    return out


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def _count(low: str, word: str) -> int:
    """Count a banned word, but let real terms through ("robustness" is a statistics term, "robust" as filler is not)."""
    if word == "robust":
        return len(re.findall(r"\brobust\b(?!ness)", low))
    return low.count(word)


def audit(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8", errors="replace")
    text = visible_text(raw)
    low = text.lower()
    words = max(len(text.split()), 1)
    sents = sentences(text)
    med = statistics.median(len(s.split()) for s in sents) if sents else 0
    long_sents = sum(1 for s in sents if len(s.split()) > 30)
    r = {
        "words": words,
        "banned": {b.strip(): _count(low, b) for b in BANNED if _count(low, b)},
        "throat": sum(len(re.findall(p, low)) for p in THROAT),
        "negpar": sum(len(re.findall(p, low)) for p in NEG_PARALLEL),
        "partic": sum(len(re.findall(p, low)) for p in PARTICIPIAL),
        "copula": sum(len(re.findall(p, low)) for p in COPULA),
        "signif": sum(len(re.findall(p, low)) for p in SIGNIFICANCE),
        "emdash": text.count("—") + text.count(" -- "),
        "semis": text.count(";"),
        "midcontrast": len(MIDCONTRAST.findall(text)),
        "titlecase": sum(title_case(h) for h in headings(raw)),
        "median": med,
        "long": long_sents,
    }
    r["score"] = (sum(r["banned"].values()) * 3 + r["throat"] * 3 + r["negpar"] * 4 + r["partic"] * 3 + r["copula"] * 2
                  + r["signif"] * 3 + r["emdash"] * 2 + r["semis"] + r["midcontrast"] * 2 + r["titlecase"] * 2 + r["long"]
                  + (3 if med > 22 else 0))
    r["per1k"] = round(r["score"] * 1000 / words, 1)
    return r


def pages(args):
    if args:
        for a in args:
            p = Path(a)
            p = p if p.is_absolute() else ROOT / a
            if p.is_dir():
                yield from sorted(p.rglob("index.html"))
            else:
                yield p
        return
    skip = ("blog/digest/", "privacy/", "terms/", "refunds/")
    for p in sorted(SITE.rglob("*.html")):
        rel = p.relative_to(SITE).as_posix()
        if rel.startswith(skip) or "/success/" in rel or rel.startswith(("kits-delivery", "assets/")):
            continue
        yield p


def main(argv):
    detail = [a for a in argv[1:] if not a.startswith("--")]
    rows = []
    for p in pages(detail):
        try:
            rows.append((p, audit(p)))
        except Exception as e:   # noqa: BLE001
            print("skip", p, e)
    rows.sort(key=lambda x: -x[1]["per1k"])
    if "--summary" in argv:
        n = len(rows)
        print(f"{n} pages, {sum(r['words'] for _, r in rows)} words, "
              f"{sum(r['score'] for _, r in rows)} points; pages over 8 per 1000 words: {sum(1 for _, r in rows if r['per1k'] > 8)}")
        return 0
    if detail:
        for p, r in rows:
            print(f"\n{_rel(p)}  words={r['words']}  score={r['score']}  per1k={r['per1k']}  median={r['median']}")
            for k, v in r.items():
                if k not in ("words", "score", "per1k", "median") and v:
                    print(f"   {k}: {v}")
        return 0
    print(f"{'per1k':>6} {'score':>5} {'words':>6} {'med':>4}  page")
    for p, r in rows:
        print(f"{r['per1k']:>6} {r['score']:>5} {r['words']:>6} {r['median']:>4}  {p.relative_to(SITE).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
