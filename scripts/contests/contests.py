#!/usr/bin/env python3
"""Contest finder: open contests, their terms, a score, and entries prepared up to the submit button.
Design: docs/designs/contest-finder.md.

Nothing here is outward. It reads public pages with plain GET requests and writes private files and local queue
items. It never signs in, submits, pays, accepts terms, uploads or contacts an organiser; those steps are Ben's.
Photo originals are opened for reading only: picks are copied into the entry folder. Stdlib only.

  contests.py scan [--offline] [--only ID]   read the registry (sources.json), fetch each rules page, update the ledger
  contests.py list [--all]                   the ledger, ranked
  contests.py show ID                        one contest: flags, score inputs, history
  contests.py digest [--write]               the weekly digest (top 5, deadlines, red flags, changes)
  contests.py prefill ID [--n N]             build the entry folder for one contest
  contests.py queue ID [--offline]           write and lint an approval-queue item for a prefilled entry
  contests.py mark ID STATUS [--note T] [--url U] [--terms-matched yes|no]
                                             entered, skipped, rejected, shortlisted, won, lost (Ben's record)
  contests.py weekly [--offline]             scan, pick, prefill and queue the picks, write the digest (launchd job)

State lives in ~/.purplelink/contests/ (PURPLELINK_CONTESTS): ledger.json, pages/<id>.txt and proposals/*.json
(research finds that are not in the registry yet; shown in the digest, never picked).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import difflib
import hashlib
import html
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
HOME = Path.home()
SHARED = Path("/Volumes/Extreme SSD/Purplelink LLC")
SCHEMA_VERSION = 1


def env_path(name: str, default: Path) -> Path:
    return Path(os.environ.get(name) or default)


def paths() -> dict:
    state = env_path("PURPLELINK_CONTESTS", HOME / ".purplelink" / "contests")
    return {
        "state": state, "ledger": state / "ledger.json", "pages": state / "pages", "proposals": state / "proposals",
        "sources": env_path("PURPLELINK_CONTEST_SOURCES", HERE / "sources.json"),
        "profile": env_path("PURPLELINK_CONTEST_PROFILE", HERE / "profile.json"),
        "briefs": env_path("PURPLELINK_CONTEST_BRIEFS", SHARED / "docs" / "growth-briefs" / "contests"),
        "photo_ws": env_path("PURPLELINK_PHOTO_WORKSPACE", SHARED / "photo-licensing-workspace"),
        "photo_lib": env_path("PURPLELINK_PHOTO_LIBRARY", Path("/Volumes/Extreme SSD/Nikon Photos")),
        "site": env_path("PURPLELINK_SITE", REPO / "site"),
        "queue_script": REPO / "scripts" / "queue" / "approval_queue.py",
        "hub_script": REPO / "scripts" / "hub" / "hub.py",
    }


def load_json(path: Path, default):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True, default=str) + "\n")
    os.replace(tmp, path)


# ---------------------------------------------------------------- identity and dedupe
EDITION_WORDS = re.compile(r"\b(19|20)\d\d(/\d\d)?\b|\b\d+(st|nd|rd|th)\b|\b(annual|edition|inaugural)\b")
FOLDS = [(r"\bphotographer of the year\b", "poty"), (r"\bawards?\b", "award"), (r"\bcompetitions?\b", "contest"),
         (r"\bcontests?\b", "contest"), (r"\bprizes?\b", "prize"), (r"\bgrants?\b", "grant"), (r"&", " and ")]


def norm_key(name: str) -> str:
    """A contest's name without its edition, so 'The 24th Annual Smithsonian Photo Contest' and 'Smithsonian Photo
    Contest 2027' get one key."""
    s = (name or "").lower()
    s = re.sub(r"\(.*?\)", " ", s)
    s = EDITION_WORDS.sub(" ", s)
    for pat, rep in FOLDS:
        s = re.sub(pat, rep, s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"^\s*the\b", " ", s)
    s = re.sub(r"\b\d{1,3}\b", " ", s)  # a bare edition number ("WPY 63")
    return "-".join(s.split())


def canon_url(url: str) -> str:
    """Host without www and the path without a trailing slash. The query is kept: listing pages tell contests apart
    by ?id=."""
    u = urllib.parse.urlsplit((url or "").strip())
    host = u.netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    path = u.path.rstrip("/") or "/"
    return f"{host}{path}" + (f"?{u.query}" if u.query else "")


def host_of(url: str) -> str:
    return canon_url(url).split("/")[0]


def match_record(rec: dict, records: dict) -> tuple:
    """(id of the same contest, how) or (None, ''). Only exact matches merge (id, normalised name, canonical URL).
    Near matches are reported by possible_duplicates and never merged: a false merge would hand a contest another
    one's entered or rejected status and hide it."""
    if rec.get("id") in records:
        return rec["id"], "id"
    key, url = norm_key(rec.get("name", "")), canon_url(rec.get("url", ""))
    for rid, other in records.items():
        if key and key == other.get("key"):
            return rid, "name"
        if url and url == canon_url(other.get("url", "")):
            return rid, "url"
    return None, ""


def possible_duplicates(records: dict) -> list:
    out, items = [], sorted(records.items())
    for i, (a, ra) in enumerate(items):
        for b, rb in items[i + 1:]:
            if host_of(ra.get("url", "")) == host_of(rb.get("url", "")) and \
                    difflib.SequenceMatcher(None, ra.get("key", ""), rb.get("key", "")).ratio() >= 0.92:
                out.append((a, b))
    return out


# ---------------------------------------------------------------- dates
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
MON = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
DAY = r"(\d{1,2})(?:st|nd|rd|th)?"
TIME = re.compile(r"[,\s]+(?:at\s+)?(\d{1,2}(?::\d\d)?\s*(?:am|pm)|\d\d:\d\d)(?:\s*\(?([A-Z]{2,4}(?:[+-]\d+)?)\)?)?", re.I)
DATE_PATTERNS = [
    ("iso", re.compile(r"\b(20\d\d)-(\d\d)-(\d\d)\b")),
    ("mdy", re.compile(rf"\b{MON}\s+{DAY}(?:,?\s+(20\d\d))?\b", re.I)),
    ("dmy", re.compile(rf"\b{DAY}\s+(?:of\s+)?{MON}(?:,?\s*(20\d\d))?\b", re.I)),
    ("slash", re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](20\d\d)\b")),
]
# Label priority: an explicit closing word beats a softer one. "until" and "ends" are left out on purpose: they
# label voting windows, exhibitions and judging as often as entry deadlines.
DEADLINE_LABELS = [
    (3, re.compile(r"\b(final deadline|entry deadline|entries close|closing date|submission deadline|deadline for entries|competition closes)\b", re.I)),
    (2, re.compile(r"\b(deadline|closes|close on|closing|submit by|submissions? due|entries due|last day to enter)\b", re.I)),
]
EARLY = re.compile(r"\b(early[- ]?bird|early deadline|early entry|discount)\b", re.I)


def _mk(y: int, m: int, d: int):
    try:
        return dt.date(y, m, d)
    except ValueError:
        return None


def find_dates(text: str, today: dt.date) -> list:
    """Every date in the text as (date, start, end, time note). Slash dates are read only when unambiguous (one part
    above 12); a date without a year takes its next occurrence on or after today."""
    out = []
    for kind, rx in DATE_PATTERNS:
        for m in rx.finditer(text):
            g = m.groups()
            if kind == "iso":
                d = _mk(int(g[0]), int(g[1]), int(g[2]))
            elif kind == "slash":
                a, b, y = int(g[0]), int(g[1]), int(g[2])
                if a > 12 and b <= 12:
                    d = _mk(y, b, a)
                elif b > 12 and a <= 12:
                    d = _mk(y, a, b)
                else:
                    d = None
            else:
                mon = MONTHS[(g[0] if kind == "mdy" else g[1])[:3].lower()]
                day = int(g[1] if kind == "mdy" else g[0])
                if g[2]:
                    d = _mk(int(g[2]), mon, day)
                else:
                    d = _mk(today.year, mon, day)
                    if d and d < today:
                        # A yearless date already past this year is read as next year only when that is close (an
                        # old edition's "12 October" must not become next October's deadline).
                        d = _mk(today.year + 1, mon, day)
                        d = d if d and (d - today).days <= 120 else None
            if d:
                tm = TIME.match(text[m.end():m.end() + 40])
                note = " ".join(x for x in tm.groups() if x) if tm else ""
                out.append((d, m.start(), m.end(), note.strip()))
    # Overlapping reads of one date (an "mdy" and a "dmy" over the same words) keep the longest.
    out.sort(key=lambda t: (t[1], -(t[2] - t[1])))
    kept, last_end = [], -1
    for t in out:
        if t[1] >= last_end:
            kept.append(t)
            last_end = t[2]
    return kept


def parse_deadline(text: str, today: dt.date):
    """The entry deadline in a page's text: {date, early_bird, note, label} or None. A date counts when a deadline
    label sits in the 80 characters before it, or the 30 after it, within one sentence. The highest label priority
    wins, then the earliest date on or after today. Dates labelled early-bird are reported separately."""
    best, early = None, None
    for sent in split_sentences(text):
        for d, s, e, note in find_dates(sent, today):
            before, after = sent[max(0, s - 80):s], sent[e:e + 30]
            prio = max([p for p, rx in DEADLINE_LABELS if rx.search(before) or rx.search(after)], default=0)
            if not prio or d < today:
                continue
            if EARLY.search(before[-50:]) or EARLY.search(after):
                early = d if early is None or d < early else early
                continue
            cand = (-prio, d, note)
            if best is None or cand < best:
                best = cand
    if best is None:
        return {"date": None, "early_bird": early.isoformat(), "note": "", "label": 0} if early else None
    return {"date": best[1].isoformat(), "early_bird": early.isoformat() if early else None, "note": best[2],
            "label": -best[0]}


# ---------------------------------------------------------------- terms check
ITEM_START = re.compile(r"\s(?=\(?[a-z]\)\s|\([ivx]{1,4}\)\s|\(\d{1,2}\)\s|\d{1,2}(?:\.\d{1,2}){1,2}\.?\s)")


def split_sentences(text: str) -> list:
    """Sentences, with each lettered or numbered rule item ('(h) ...', '7.2 ...') as its own unit."""
    t = re.sub(r"\s+", " ", text or "")
    t = ITEM_START.sub("\n", t)
    parts = []
    for chunk in t.split("\n"):
        parts += re.split(r"(?<=[.;!?])\s+(?=[A-Z(\"'])", chunk)
    return [p.strip() for p in parts if p.strip()]


LICENCE = re.compile(r"\b(licen[cs]e[sd]?|grants?|granting|right to (use|reproduce|publish|display)|permission to use)\b", re.I)
ITEM = re.compile(r"^\(?([a-z]|[ivx]{1,4})\)\s")
ALL_SCOPE = re.compile(r"\b(each|every|all|any)\s+(entrant|participant|entry|entries|image|images|photograph|photographs|submission|submissions|work|works)\b"
                       r"|\bby (entering|submitting|participating)\b|\bentrants? (hereby )?grants?\b|\byou (hereby )?grant\b"
                       r"|\b(images?|photographs?|entries|submissions|works?) (submitted|entered)\b", re.I)
LIMIT_SCOPE = re.compile(r"\b(winners?|winning (image|images|entr\w+|photo\w*|works?|submissions?)|finalists?|shortlisted|short-listed|prize[- ]winning|(that|which) (wins?|is awarded|are awarded|is shortlisted|are shortlisted)|awarded (images?|entr\w+|photo\w*))\b", re.I)
NEG = r"(not|never|no|without|nor|neither|won't|will not|shall not|may not|cannot)"


def negated(sent: str, start: int) -> bool:
    """True when a negation sits within the six words before a trigger, as in 'will not be used commercially'."""
    pre = sent[:start].split()[-6:]
    return bool(re.search(rf"\b{NEG}\b", " ".join(pre), re.I))


ALL_WORDING = re.compile(r"\b(all|every|each|any) (other )?(entries|entrants|images|entry|image)\b", re.I)


def limited(sent: str) -> bool:
    """True when a sentence's grant is about winners, finalists or shortlisted entries only."""
    return bool(LIMIT_SCOPE.search(sent)) and not (ALL_WORDING.search(sent) and not re.search(r"\b(that|which) (wins?|is awarded|are awarded|is shortlisted)\b", sent, re.I))


def clause_units(sents: list) -> list:
    """(text, in_licence, winners_only) triples. A lettered item ('(h) ...') inherits the licence context and the scope
    of the last sentence that introduced a grant, so 'a licence on any image submitted ... for: (a) ... (h) remains
    perpetually' reads (h) as part of an all-entries grant, and the items under 'for any photograph that wins an
    Award, you grant ...' are winners-only."""
    units, ctx, ctx_lim = [], False, False
    for s in sents:
        lic = bool(LICENCE.search(s))
        if ITEM.match(s):
            units.append((s, lic or ctx, ctx_lim if (ctx and not lic) else (ctx_lim or limited(s))))
        else:
            ctx, ctx_lim = lic, lic and limited(s)
            units.append((s, lic, ctx_lim))
    return units


RULES = [
    # flag, severity, regex, needs licence context
    ("irrevocable", "medium", re.compile(r"\birrevocabl[ey]\b", re.I), True),
    ("perpetual", "high", re.compile(r"\b(perpetual(ly)?|in perpetuity|without (any )?time limit|for an unlimited (period|time))\b", re.I), True),
    ("worldwide", "low", re.compile(r"\b(worldwide|world-wide|throughout the world|in all territories)\b", re.I), True),
    ("sublicensable", "medium", re.compile(r"\b(sub-?licen[cs](e|es|able|ed|ing)|transferable)\b", re.I), True),
    ("commercial_use", "high", re.compile(r"\b(any purpose|(?<!non-)(?<!non)commercial(ly)?|merchandis(e|ing)|sold|for sale|resale|advertising)\b", re.I), True),
    ("royalty_free", "low", re.compile(r"\b(royalty[- ]free|without (payment|compensation|remuneration)|free of charge)\b", re.I), True),
    ("copyright_transfer", "severe", re.compile(r"\b(assigns? (all |the )?(copyright|rights)|assignment of (copyright|rights)|transfers? (all |the )?(copyright|ownership)|becomes? the (sole |exclusive )?property of|all rights (are )?(transferred|assigned))\b", re.I), False),
    ("exclusive", "severe", re.compile(r"(?<!non-)(?<!non )\bexclusive (licen[cs]e|rights?)\b", re.I), False),
    ("moral_rights_waiver", "medium", re.compile(r"\bwaives?\b[^.]{0,60}\bmoral rights\b", re.I), False),
]
AUTOMATION = re.compile(r"\b(automated|bots?|robots?|scripts?|macros?|bulk (entry|entries|upload|submission)s?|software to (enter|submit)|entry services?)\b", re.I)
AUTO_BAN = re.compile(rf"\b({NEG}|prohibited|forbidden|void|disqualif\w*|only by)\b", re.I)
AI_WORDS = re.compile(r"\b(artificial intelligence|ai[- ]generated|generative|computer[- ]generated|ai tools?|AI|upscal\w*|machine learning)\b")
TERM = re.compile(r"\b(?:for|period of|term of)\s+(?:a\s+)?(?:maximum of\s+)?(\w+)\s*(?:\(\d+\)\s*)?years?\b|\b(\d+)[- ]year\b", re.I)
NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
AGREEMENT = re.compile(r"\b(following (the )?(individual |separate )?agreement|separate (written )?agreement|individual agreement|with (the )?(author'?s? |your |prior )?(written )?(consent|permission|agreement)|seek your (prior )?(written )?permission|subject to agreement)\b", re.I)
SEVERITY = {"info": 0, "low": 1, "medium": 2, "high": 3, "severe": 4}


def check_terms(text: str) -> dict:
    """Flags from a contest's rules text, biased toward flagging. A limit to winners or finalists clears the
    all-entries flag only when it sits in the same grant sentence and no 'all entries' wording does; a limit in a
    separate clause only adds a 'check scope' note. Never returns 'clean': a text with no licence wording at all is
    flagged licence_not_found."""
    units = clause_units(split_sentences(text))
    flags: dict = {}
    units_lic = [(s, lic) for s, lic, _ in units]

    def add(name, sev, sent, **extra):
        f = flags.get(name)
        if f is None or SEVERITY[sev] > SEVERITY[f["severity"]] or (f.get("scope") and not extra.get("scope") and SEVERITY[sev] >= SEVERITY[f["severity"]]):
            flags[name] = {"flag": name, "severity": sev, "sentence": " ".join(sent.split()[:25]), **extra}

    licence_seen, limit_elsewhere = False, False
    down = {"severe": "high", "high": "medium", "medium": "low", "low": "low", "info": "info"}
    for sent, in_lic, win in units:
        if in_lic:
            licence_seen = True
            if win:
                limit_elsewhere = True  # this grant is about winners or finalists only
            elif ALL_SCOPE.search(sent):
                add("licence_all_entries", "high", sent)
        for name, sev, rx, need_lic in RULES:
            if need_lic and not in_lic:
                continue
            m = rx.search(sent)
            if not m or negated(sent, m.start()):
                continue
            extra = {"scope": "winners"} if win and need_lic else {}
            if name == "commercial_use" and AGREEMENT.search(sent):
                add(name, down[sev] if extra else "medium", sent, qualified="needs a separate agreement", **extra)
                continue
            add(name, down[sev] if extra else sev, sent, **extra)
        if in_lic and not win:
            tm = TERM.search(sent)
            if tm:
                n = tm.group(1) or tm.group(2)
                n = int(n) if n.isdigit() else NUMBERS.get(n.lower())
                if n:
                    add("term_years", "info", sent, years=n)
        if AUTOMATION.search(sent) and AUTO_BAN.search(sent) and re.search(r"\b(enter|entry|entries|submit|submission|register)", sent, re.I):
            add("automated_entry_banned", "info", sent)
        if AI_WORDS.search(sent):
            add("ai_rules", "info", sent)
    if not licence_seen:
        add("licence_not_found", "high", "No licence or grant wording was found in the rules text. Read the terms.")
    elif "licence_all_entries" in flags and limit_elsewhere:
        flags["licence_all_entries"]["note"] = "check scope: another clause limits some uses to winners or finalists"
    elif "licence_all_entries" not in flags and "licence_not_found" not in flags:
        flags["licence_winners_only"] = {"flag": "licence_winners_only", "severity": "info",
                                         "sentence": "The grant wording found is limited to winners, finalists or shortlisted entries."}
    elig = eligibility(text)
    return {"flags": sorted(flags.values(), key=lambda f: (-SEVERITY[f["severity"]], f["flag"])),
            "fee_usd": parse_fee(text), "us_eligible": elig["us_eligible"], "eligibility": elig["sentence"],
            "chars": len(text or ""), "terms_hash": terms_hash(units_lic)}


def terms_hash(units: list) -> str:
    """A hash of the sentences that matter (licence, fee, deadline and eligibility wording), so a changed cookie
    banner or a 'days left' counter does not show as a change in the terms."""
    keep = [s for s, lic in units if lic or re.search(r"\b(fee|deadline|close|eligib|open to|resident|licen)", s, re.I)]
    return hashlib.sha256("\n".join(keep).encode()).hexdigest()[:16]


FX = {"$": 1.0, "usd": 1.0, "us$": 1.0, "£": 1.27, "gbp": 1.27, "€": 1.08, "eur": 1.08, "aed": 0.27, "cad": 0.73,
      "ca$": 0.73, "aud": 0.66, "a$": 0.66}
MONEY = re.compile(r"(us\$|ca\$|a\$|\$|£|€)\s?(\d[\d,]*(?:\.\d\d)?)|(\d[\d,]*(?:\.\d\d)?)\s?(usd|gbp|eur|aed|cad|aud)\b", re.I)


def money(text: str) -> list:
    out = []
    for m in MONEY.finditer(text or ""):
        cur = (m.group(1) or m.group(4)).lower()
        val = float((m.group(2) or m.group(3)).replace(",", ""))
        out.append((round(val * FX.get(cur, 1.0), 2), m.start()))
    return out


def parse_fee(text: str):
    """The cheapest entry fee in USD: 0.0 for a free contest, None when the text does not say."""
    sents = split_sentences(text)
    for sent in sents:
        if re.search(r"\b(free to enter|free entry|no entry fee|no fee to enter|entry is free|there is no (entry )?fee)\b", sent, re.I):
            return 0.0
    fees = []
    for sent in sents:
        if re.search(r"\b(entry fee|fee|per image|per entry|per photo|per submission|to enter)\b", sent, re.I):
            fees += [v for v, _ in money(sent) if v > 0]
    return min(fees) if fees else None


COUNTRY_US = re.compile(r"\b(united states|u\.s\.a?\.?|usa|us residents|america)\b", re.I)


def eligibility(text: str) -> dict:
    """us_eligible: False when the US is excluded, or when the rules open the contest to named countries without the
    US ('open to residents of the UK'); True when it is open worldwide or names the US; None when unsaid."""
    verdict, why = None, ""
    for sent in split_sentences(text):
        low = sent.lower()
        if not re.search(r"\b(open to|eligible|residents? of|excluding|exclude|except|not open|void in|citizens? of)\b", low):
            continue
        why = why or " ".join(sent.split()[:25])
        if re.search(r"\b(excluding|except|not open to|void in|excluded)\b", low) and COUNTRY_US.search(sent):
            return {"us_eligible": False, "sentence": " ".join(sent.split()[:25])}
        if re.search(r"\b(worldwide|all countries|anyone|any country|all members of the public|international)\b", low):
            verdict = True if verdict is None else verdict
        elif COUNTRY_US.search(sent) and re.search(r"\b(open to|residents? of|citizens? of)\b", low):
            verdict = True
        elif re.search(r"\bopen to\b[^.]{0,60}\b(residents?|citizens?) of\b", low):
            verdict, why = False, " ".join(sent.split()[:25])
    return {"us_eligible": verdict, "sentence": why}


# ---------------------------------------------------------------- rights gate, rights cost, score
def blocked(rec: dict, profile: dict) -> bool:
    """Anything run by or involving Georgia State University is dropped silently (word-boundary patterns in
    profile.json)."""
    hay = " ".join(str(rec.get(k, "")) for k in ("name", "organizer", "url", "notes", "eligibility_text"))
    return any(re.search(p, hay, re.I) for p in profile.get("blocked", []))


def worst(flags: list) -> str:
    return max((f["severity"] for f in flags), key=lambda s: SEVERITY[s], default="info")


def rights_gate(flags: list, rec: dict) -> str:
    """'' when the licence may be picked; otherwise why not. Default hard rule (design review): an all-entries licence
    that is also perpetual, a copyright transfer or an exclusive licence keeps a contest out of the picks. Ben can lift
    it for one contest with "allow_rights": true in its registry entry."""
    if rec.get("allow_rights"):
        return ""
    names = {f["flag"] for f in flags if not f.get("scope")}
    if names & {"copyright_transfer", "exclusive"}:
        return "copyright transfer or exclusive licence"
    if {"licence_all_entries", "perpetual"} <= names:
        return "perpetual licence on every entry"
    return ""


def rights_cost(flags: list, images: int, value: float, mult: dict, cap: float) -> float:
    """images x value per image x uses, capped. Uses start at `base_use` for any licence (promotion, judging) and add a
    weight for each broadening flag (perpetual, commercial, sub-licensable, irrevocable). A flag that applies to every
    entry counts in full; one that applies to winners or finalists only counts at `winners_only_factor`. Terms with no
    licence wording found cost `licence_not_found` uses on every entry: unknown is not free."""
    names = {f["flag"]: f for f in flags}
    if "licence_not_found" in names:
        return round(images * value * min(mult.get("licence_not_found", 0.5), cap), 2)
    k = mult.get("winners_only_factor", 0.1)
    every = "licence_all_entries" in names
    uses = mult.get("base_use", 0.25) * (1.0 if every else k)
    for name in ("perpetual", "commercial_use", "sublicensable", "irrevocable"):
        f = names.get(name)
        if not f:
            continue
        w = mult.get("commercial_use_qualified", 0.5) if name == "commercial_use" and f.get("qualified") else mult.get(name, 0)
        uses += w * (1.0 if every and not f.get("scope") else k)
    return round(images * value * min(uses, cap), 2)


def fit_of(themes: list, profile: dict, material: int, min_material: int) -> float:
    covered = set(profile.get("covered_themes", []))
    th = [t for t in themes or [] if t]
    if not th:
        return 0.0
    f = len([t for t in th if t in covered]) / len(th)
    return round(f * (0.5 if material < min_material else 1.0), 3)


def score(rec: dict, flags: list, profile: dict, material: int) -> dict:
    """ev = prize x odds x tickets x fit; score = ev - fee - rights cost. Exposure is shown beside the score, not
    added, so a guessed exposure value cannot outrank a real prize. An unknown fee leaves the contest unscored:
    unknown is not free."""
    s = profile["score"]
    group = rec.get("group", "photo")
    images = int(rec.get("images") or (s["default_images"] if group == "photo" else 1))
    prize = float(rec.get("prize_usd") or 0) + s["category_factor"] * float(rec.get("category_prize_usd") or 0) \
        + s["goods_factor"] * float(rec.get("prize_goods_usd") or 0)
    odds = float(s["odds"].get(f"{group}-{rec.get('size', 'large')}", s["odds"].get(group, 0.001)))
    tickets = min(images, s["ticket_cap"]) if group == "photo" else 1
    fit = fit_of(rec.get("themes"), profile, material, s["min_material"])
    ev = round(prize * odds * tickets * fit, 2)
    kind = "photo" if group == "photo" else "product"
    rc = rights_cost(flags, images if kind == "photo" else 1, s["value_per_image"][kind], s["rights_multipliers"], s["multiplier_cap"])
    fee = rec.get("fee_usd")
    total = None if fee is None else round(ev - float(fee) - rc, 2)
    return {"prize_usd": round(prize, 2), "odds": odds, "tickets": tickets, "fit": fit, "ev": ev, "fee_usd": fee,
            "rights_cost": rc, "exposure_usd": float(rec.get("exposure_usd") or 0), "score": total, "images": images}


# ---------------------------------------------------------------- fetching
UA = "Mozilla/5.0 (Macintosh) PurplelinkContestFinder/1.0 (+https://purplelink.llc; reads public rules pages weekly)"
MAX_BYTES = 3_000_000
_last_hit: dict = {}


def site_of(url: str) -> str:
    return ".".join(host_of(url).split(".")[-2:])


class NoCrossSiteRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith("https://") or site_of(req.full_url) != site_of(newurl):
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer)\b.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</(p|li|div|h\d|tr|section|article|td)>", "\n", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    text = html.unescape(raw)
    # Control and zero-width characters are dropped: fetched text is data that later sessions read.
    text = re.sub(r"[\u0000-\u0008\u000b-\u001f\u200b-\u200f\u2028-\u202e\u2060-\u206f]", " ", text)
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", text)).strip()


BLOCK_MARKERS = re.compile(r"(just a moment|checking your browser|enable javascript and cookies|access denied|attention required|captcha)", re.I)
ACTION_URL = re.compile(r"(unsubscribe|confirm|verify|token=|login|signin|sign-in|/account|checkout|/cart)", re.I)


def fetch(url: str, timeout: int = 20, opener=None) -> dict:
    """{status: ok|blocked|error|skipped, text, code, why}. https only, no cross-site redirects, one request per host
    per second, one retry. URLs that act (unsubscribe, confirm, sign-in, checkout) are never fetched."""
    if not url.startswith("https://"):
        return {"status": "skipped", "text": "", "code": 0, "why": "not https"}
    if ACTION_URL.search(url):
        return {"status": "skipped", "text": "", "code": 0, "why": "action url"}
    opener = opener or urllib.request.build_opener(NoCrossSiteRedirect)
    host = host_of(url)
    last = {"status": "error", "text": "", "code": 0, "why": "not fetched"}
    for _ in range(2):
        wait = 1.0 - (time.time() - _last_hit.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        _last_hit[host] = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"})
            with opener.open(req, timeout=timeout) as r:
                ctype = r.headers.get("Content-Type", "")
                body = r.read(MAX_BYTES + 1)
                if "pdf" in ctype:
                    return {"status": "error", "text": "", "code": r.status, "why": "pdf (not read; open it by hand)"}
                if len(body) > MAX_BYTES:
                    return {"status": "error", "text": "", "code": r.status, "why": "page too large"}
                text = html_to_text(body.decode("utf-8", errors="replace"))
                if len(text) < 1500 and BLOCK_MARKERS.search(text):
                    return {"status": "blocked", "text": "", "code": r.status, "why": "bot check"}
                return {"status": "ok", "text": text, "code": r.status}
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 429, 503):
                return {"status": "blocked", "text": "", "code": e.code, "why": f"http {e.code}"}
            last = {"status": "error", "text": "", "code": e.code, "why": f"http {e.code}"}
        except Exception as e:  # network, TLS, timeout
            last = {"status": "error", "text": "", "code": 0, "why": type(e).__name__}
    return last


# ---------------------------------------------------------------- ledger and statuses
STATUSES = ["open", "excluded", "closed", "picked", "prefilled", "queued", "entered", "shortlisted", "won", "lost",
            "skipped", "rejected"]
WORKFLOW = {"picked", "prefilled", "queued"}    # set by weekly / prefill / queue
DONE = {"entered", "shortlisted", "won", "lost", "skipped", "rejected"}  # set by Ben with `mark`; scan never changes them
ALLOWED = {
    "entered": {"open", "excluded", "closed", "picked", "prefilled", "queued"},
    "skipped": {"open", "excluded", "closed", "picked", "prefilled", "queued"},
    "rejected": set(STATUSES) - {"entered", "shortlisted", "won", "lost"},
    "shortlisted": {"entered"},
    "won": {"entered", "shortlisted"},
    "lost": {"entered", "shortlisted"},
}


def load_ledger(p: dict) -> dict:
    led = load_json(p["ledger"], {}) or {}
    led.setdefault("schema", SCHEMA_VERSION)
    led.setdefault("contests", {})
    return led


def history(rec: dict, event: str, **extra) -> None:
    rec.setdefault("history", []).append({"at": dt.datetime.now().astimezone().isoformat(timespec="minutes"),
                                          "event": event, **{k: v for k, v in extra.items() if v not in ("", None)}})


REGISTRY_FIELDS = ["name", "organizer", "url", "rules_urls", "entry_url", "group", "size", "themes", "photo_themes",
                   "cadence", "edition", "opens", "deadline", "deadline_note", "deadline_status", "fee_usd", "fee_text",
                   "prize_usd", "category_prize_usd", "prize_goods_usd", "prize_text", "us_eligible", "llc_eligible",
                   "eligibility_text", "ai_text", "licence_text", "automation_text", "images", "entry_limit",
                   "taken_from", "taken_to", "max_long_edge", "convert_bw", "wild_only", "people_ok", "product", "exposure_usd", "allow_rights",
                   "read", "notes", "ben_status", "ben_entered"]
EDITION_KEYS = ("queue_id", "queue_folder", "queue_problems", "entry_dir", "result", "entry_url_done", "utm_link",
                "terms_matched", "statement", "picks", "entered")


def merge_registry(led: dict, sources: dict, profile: dict, today: dt.date) -> dict:
    """Registry entries into the ledger, one record per contest. A new edition archives the old one into `past` and
    reopens the record, except a contest Ben rejected, which stays rejected across editions. A registry entry may
    carry `ben_status` (for example "entered" for an entry made before the finder existed)."""
    recs = led["contests"]
    stats = {"new": [], "editions": [], "blocked": 0, "possible_duplicates": []}
    for src in sources.get("contests", []):
        if blocked(src, profile):
            stats["blocked"] += 1
            continue
        rid, how = match_record(src, recs)
        if rid and rid != src["id"]:
            stats["possible_duplicates"].append((rid, src["id"]))
            continue
        rid = src["id"]
        rec = recs.get(rid)
        if rec is None:
            rec = recs[rid] = {"id": rid, "status": "open", "first_seen": today.isoformat(), "past": []}
            stats["new"].append(rid)
            history(rec, "added", source="registry")
        elif str(src.get("edition") or "") and str(src.get("edition")) != str(rec.get("edition") or ""):
            rec.setdefault("past", []).append({k: rec.get(k) for k in ("edition", "status", "deadline") + EDITION_KEYS if rec.get(k)})
            stats["editions"].append(rid)
            history(rec, "new-edition", old=rec.get("edition"), new=src.get("edition"))
            rec["status"] = "rejected" if rec.get("status") == "rejected" else "open"
            for k in EDITION_KEYS:
                rec.pop(k, None)
        for k in REGISTRY_FIELDS:
            if k in src:
                rec[k] = src[k]
        if src.get("ben_status") in DONE and rec.get("status") not in DONE:
            rec["status"] = src["ben_status"]
            history(rec, f"status:{src['ben_status']}", note="from the registry")
        if src.get("ben_entered") and not rec.get("entered"):
            rec["entered"] = src["ben_entered"]
        rec["key"] = norm_key(rec.get("name", ""))
        rec["source"] = "registry"
    stats["possible_duplicates"] += possible_duplicates(recs)
    return stats


def proposals(p: dict) -> list:
    """Research finds waiting for a registry entry (JSON arrays in proposals/). Shown in the digest, never picked."""
    out = []
    if p["proposals"].is_dir():
        for f in sorted(p["proposals"].glob("*.json")):
            for item in load_json(f, []) or []:
                if isinstance(item, dict) and item.get("name") and item.get("url"):
                    out.append({**item, "_file": f.name})
    return out


def evaluate(rec: dict, page, profile: dict, material: int, today: dt.date) -> None:
    """Terms flags, deadline, eligibility and score for one record. The page text is used when it was read; the
    registry's own summary (a person's dated read) is always added to it, so a page that hides its rules behind a
    script still gets the read facts checked. The record says which source the flags came from."""
    reg_text = " ".join(str(rec.get(k) or "") for k in ("licence_text", "eligibility_text", "ai_text", "automation_text", "fee_text"))
    if page and page.get("status") == "ok" and len(page["text"]) >= 400:
        terms = check_terms(page["text"] + "\n" + reg_text)
        rec["terms_source"] = "page+registry" if reg_text.strip() else "page"
        dl = parse_deadline(page["text"], today)
    else:
        terms = check_terms(reg_text)
        rec["terms_source"] = "registry" if reg_text.strip() else "unknown"
        dl = None
    rec["flags"] = terms["flags"]
    rec["terms_hash"] = terms["terms_hash"]
    rec["wild_only_detected"] = bool(WILD_ONLY_RULE.search((page or {}).get("text", "") + " " + reg_text))
    rec["ai_denoise_banned"] = ai_denoise_banned((page or {}).get("text", "") + " " + reg_text)
    if rec.get("fee_usd") is None and terms["fee_usd"] is not None:
        rec["fee_usd"], rec["fee_source"] = terms["fee_usd"], "page"
    if rec.get("us_eligible") is None and terms["us_eligible"] is not None:
        rec["us_eligible"] = terms["us_eligible"]
    # The registry deadline is authoritative. A different page date is a warning; when the registry date has passed
    # and the page shows a later one (a new edition), the page date is used and the registry needs a re-read.
    rec["deadline_page"] = (dl or {}).get("date")
    rec["early_bird"] = (dl or {}).get("early_bird") or rec.get("early_bird")
    warn = ""
    if dl and dl.get("date") and rec.get("deadline") and dl["date"] != rec["deadline"]:
        warn = f"page says {dl['date']}, registry says {rec['deadline']}"
        if dl["date"] > rec["deadline"] and rec["deadline"] < today.isoformat():
            rec["deadline"], rec["deadline_status"] = dl["date"], "page"
            warn += " (registry date passed; page date used, re-read the rules)"
    elif dl and dl.get("date") and not rec.get("deadline"):
        rec["deadline"], rec["deadline_status"] = dl["date"], "page"
    rec["deadline_warning"] = warn
    rec["material"] = material
    rec["score_inputs"] = score(rec, rec["flags"], profile, material)
    rec["gate"] = rights_gate(rec["flags"], rec)


def exclusion(rec: dict) -> str:
    if rec.get("us_eligible") is False:
        return "not open to US entrants"
    if rec.get("llc_eligible") is False:
        return "not open to a US LLC or its owner"
    if rec.get("cadence") == "ended":
        return "programme ended"
    return ""


def refresh_status(rec: dict, today: dt.date) -> None:
    """open, excluded or closed, from the facts; Ben's statuses are never changed here, and a picked, prefilled or
    queued contest stays so until its deadline passes."""
    if rec.get("status") in DONE:
        return
    why = exclusion(rec)
    dl = rec.get("deadline")
    if dl and dl < today.isoformat():
        new = "closed"
    elif why:
        new = "excluded"
    elif rec.get("status") in WORKFLOW:
        return
    else:
        new = "open"
    if new != rec.get("status"):
        history(rec, f"status:{new}", why=why)
    rec["status"], rec["excluded_why"] = new, why


def days_left(rec: dict, today: dt.date):
    try:
        return (dt.date.fromisoformat(rec["deadline"]) - today).days
    except (KeyError, TypeError, ValueError):
        return None


def pickable(rec: dict, profile: dict, today: dt.date) -> str:
    """'' when the record may be picked for prefill; otherwise the reason it is not."""
    s = profile["score"]
    if rec.get("status") != "open":
        return rec.get("status", "")
    if rec.get("source") != "registry":
        return "not in the registry"
    if rec.get("deadline_status") in (None, "expected", "unknown", "rolling") or not rec.get("deadline"):
        return "deadline unknown or expected"
    left = days_left(rec, today)
    if left is not None and left < s["min_days_left"]:
        return f"{left} days left: too close to review"
    if rec.get("opens") and rec["opens"] > today.isoformat():
        return f"opens {rec['opens']}"
    if rec.get("gate"):
        return "rights gate: " + rec["gate"]
    if rec.get("us_eligible") is None:
        return "US eligibility not confirmed"
    sc = (rec.get("score_inputs") or {}).get("score")
    if sc is None:
        return "fee unknown: unscored"
    cap = s.get("max_fee_usd")
    if cap is not None and float(rec.get("fee_usd") or 0) > cap:
        return f"entry fee {rec.get('fee_usd')} USD above the {cap} USD cap"
    if sc <= s["min_score"]:
        return f"score {sc} at or below {s['min_score']}"
    return ""


def ranked(led: dict) -> list:
    def k(r):
        sc = (r.get("score_inputs") or {}).get("score")
        return (sc is None, -(sc if sc is not None else 0), r.get("deadline") or "9999")
    return sorted(led["contests"].values(), key=k)


# ---------------------------------------------------------------- photos
PEOPLE_TAGS = {"people", "person", "man", "woman", "men", "women", "crowd", "portrait", "child", "children", "fans",
               "spectators", "tourists", "visitors", "pedestrians", "couple", "family"}


def load_photos(p: dict) -> list:
    """Ben's licensed photos with their metadata: alamy-metadata.csv (caption, tags, editorial) joined by filename to
    the newest Alamy export (location, date taken, exclusivity). Read only. A missing workspace or library gives []."""
    ws, lib = p["photo_ws"], p["photo_lib"]
    meta = ws / "alamy-metadata.csv"
    if not meta.exists() or not lib.is_dir():
        return []
    export = {}
    exports = sorted((ws / "exports").glob("BenjaminAmpel_*.csv")) if (ws / "exports").is_dir() else []
    if exports:
        with open(exports[-1], encoding="utf-8-sig", newline="") as fh:
            export = {row.get("Filename", ""): row for row in csv.DictReader(fh)}
    out = []
    with open(meta, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            fn = row.get("Filename", "")
            path = lib / fn
            if not fn or not path.is_file():
                continue
            ex = export.get(fn, {})
            m = re.match(r"(\d\d)/(\d\d)/(\d{4})", ex.get("Date taken", ""))
            taken = _mk(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else None
            tags = {t.strip().lower() for t in re.split(r"[;,]", row.get("Tags", "")) if t.strip()}
            out.append({
                "file": fn, "path": str(path), "title": row.get("Title", ""), "caption": row.get("Caption", ""),
                "tags": tags, "editorial": row.get("Editorial", "").strip().lower() == "yes",
                "location": ex.get("Location", ""), "taken": taken.isoformat() if taken else None,
                "exclusive": (ex.get("Exclusive to Alamy", "") or "").strip().lower() == "yes",
                "people": bool(tags & PEOPLE_TAGS),
            })
    return out


def exif_dates(paths_: list) -> dict:
    """DateTimeOriginal per file. exiftool only reads here. {} without exiftool."""
    if not paths_ or not shutil.which("exiftool"):
        return {}
    try:
        r = subprocess.run(["exiftool", "-q", "-q", "-T", "-FilePath", "-DateTimeOriginal", *paths_],
                           capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.TimeoutExpired):
        return {}
    out = {}
    for line in r.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 2 and re.match(r"\d{4}:\d\d:\d\d", parts[1]):
            out[parts[0]] = parts[1][:10].replace(":", "-")
    return out


def theme_words(rec: dict, profile: dict) -> set:
    words = set()
    for t in (rec.get("photo_themes") or rec.get("themes") or []):
        words |= set(profile.get("theme_keywords", {}).get(t, [t]))
    return {w.lower() for w in words}


def photo_eligible(ph: dict, rec: dict) -> str:
    """'' when the photo may be entered; otherwise why not."""
    if ph["editorial"]:
        return "editorial"
    if ph["people"] and not rec.get("people_ok"):
        return "people"
    if ph["exclusive"]:
        return "exclusive to Alamy"
    if (rec.get("wild_only") or rec.get("wild_only_detected")) and CAPTIVE.search(ph["caption"] + " " + ph["title"] + " " + " ".join(ph["tags"])):
        return "captive animal or cultivated plant"
    if rec.get("ai_denoise_banned") and AI_ENHANCED_FILE.search(ph["file"]):
        return "AI denoise or upscale (Lightroom Enhanced file)"
    if rec.get("taken_from") or rec.get("taken_to"):
        if not ph.get("taken"):
            return "capture date unknown"
        if rec.get("taken_from") and ph["taken"] < rec["taken_from"]:
            return "taken too early"
        if rec.get("taken_to") and ph["taken"] > rec["taken_to"]:
            return "taken too late"
    return ""


# Signs a photo shows a captive animal or a cultivated plant, which nature contests such as Wildlife Photographer of
# the Year bar (its rule 5: "non-captive wild animals"; no farm animals, pets or cultivated plants).
CAPTIVE = re.compile(r"\b(zoo|aquarium|exhibit|enclosure|captive|captivity|sanctuary|botanical|botanic|garden|cultivated|"
                     r"farm|pet|pets|domestic|petting|terrarium|vivarium|conservatory|greenhouse|nursery)\b", re.I)
WILD_ONLY_RULE = re.compile(r"\b(non-captive|must not portray captive|no captive|captive animals are not|not (be )?of captive)\b", re.I)
# Lightroom names its AI Denoise and Super Resolution output "<name>-Enhanced-NR" / "-Enhanced-SR"; some contests
# (35AWARDS) ban AI noise reduction and upscaling.
AI_ENHANCED_FILE = re.compile(r"-Enhanced(-NR|-SR)?\b|-Denoise", re.I)


def ai_denoise_banned(text: str) -> bool:
    """True when a sentence names AI noise reduction or upscaling and bans it."""
    for sent in re.split(r"(?<=[.;])\s+", text):
        if re.search(r"\b(noise reduction|denois\w*|upscal\w*|super.resolution)\b", sent, re.I) and \
                re.search(r"\bAI\b|artificial intelligence|neural", sent, re.I) and \
                re.search(r"\b(banned|ban|prohibited|not (permitted|allowed)|forbidden)\b", sent, re.I):
            return True
    return False


GOOD_LIGHT = {"golden hour", "sunset", "sunrise", "dusk", "dawn", "reflection", "night", "blue hour", "fog", "mist"}


def pick_photos(photos: list, rec: dict, profile: dict, n: int) -> list:
    """The best-fitting eligible photos by overlap between their tags and the contest's theme words, at most two per
    place (location, or the caption's first phrase when the location is blank) so the set is varied."""
    words = theme_words(rec, profile)
    scored = []
    for ph in photos:
        if photo_eligible(ph, rec):
            continue
        hits = sorted(ph["tags"] & words)
        if not hits:
            continue
        scored.append((len(hits) + 0.5 * len(ph["tags"] & GOOD_LIGHT), ph["file"], ph, hits))
    scored.sort(key=lambda t: (-t[0], t[1]))
    out, per_place = [], {}
    for sc, _, ph, hits in scored:
        place = (ph["location"] or re.split(r"[,.]", ph["caption"])[0] or "?").lower()[:40]
        if per_place.get(place, 0) >= 2:
            continue
        per_place[place] = per_place.get(place, 0) + 1
        out.append({**ph, "tags": sorted(ph["tags"])[:12], "fit": round(sc, 1), "why": hits[:6]})
        if len(out) >= n:
            break
    return out


def count_material(rec: dict, photos: list, profile: dict) -> int:
    if rec.get("group") == "photo":
        words = theme_words(rec, profile)
        return sum(1 for ph in photos if not photo_eligible(ph, rec) and ph["tags"] & words)
    return 1 if rec.get("product") else 0


def inside(path: Path, root: Path) -> bool:
    path, root = path.resolve(), root.resolve()
    return path == root or root in path.parents


def safe_copy(src: Path, dest_dir: Path, lib: Path) -> Path:
    """Copy one original into the entry folder. The destination must resolve outside the library, so no original can
    be overwritten; shutil opens the source for reading only."""
    if inside(dest_dir, lib):
        raise SystemExit(f"refusing to write inside the photo library: {dest_dir}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    shutil.copy2(src, dest)
    os.chmod(dest, 0o644)
    return dest


GRAY_PROFILE = "/System/Library/ColorSync/Profiles/Generic Gray Profile.icc"


def resize_copy(dest: Path, long_edge, lib: Path, grey: bool = False) -> None:
    """sips resizes (or turns grey, for a black-and-white contest) the copy, never a library file, and GPS is removed
    from the copy."""
    if inside(dest, lib):
        raise SystemExit("refusing to edit a file inside the photo library")
    if long_edge and shutil.which("sips"):
        subprocess.run(["sips", "-Z", str(long_edge), str(dest), "--out", str(dest)], capture_output=True)
    if grey and shutil.which("sips") and Path(GRAY_PROFILE).exists():
        subprocess.run(["sips", "-m", GRAY_PROFILE, str(dest), "--out", str(dest)], capture_output=True)
    if shutil.which("exiftool"):
        subprocess.run(["exiftool", "-q", "-overwrite_original", "-gps:all=", str(dest)], capture_output=True)


# ---------------------------------------------------------------- product materials
PRODUCT_PAGES = {"outbound-veil": "outbound-veil", "batterymeter": "batterymeter"}


def product_section(site: Path, product: str) -> tuple:
    """(heading, paragraph text) for a product from site/llms.txt."""
    txt = (site / "llms.txt").read_text() if (site / "llms.txt").exists() else ""
    want = product.replace("-", " ").lower()
    for m in re.finditer(r"^### (.+?)\n(.*?)(?=^###? |\Z)", txt, re.M | re.S):
        if m.group(1).lower().startswith(want):
            return m.group(1).strip(), m.group(2).strip()
    return product, ""


def product_images(site: Path, product: str) -> list:
    """Screenshots for a product: images under site/<product>/ and site/img/ files named after it."""
    slug = PRODUCT_PAGES.get(product, product)
    found = []
    for d in (site / slug, site / "img", site / "images"):
        if d.is_dir():
            for f in d.rglob("*"):
                if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") and (d == site / slug or slug in f.name.lower()):
                    found.append(str(f.relative_to(site)))
    return sorted(set(found))[:10]


def hub_module(p: dict):
    spec = importlib.util.spec_from_file_location("hub", p["hub_script"])
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def tagged_link(p: dict, rec: dict, today: dt.date) -> str:
    """The product link with a utm_content no placement uses, made once per edition and kept in the ledger so
    re-running prefill never mints a second tag."""
    if rec.get("utm_link"):
        return rec["utm_link"]
    hub = hub_module(p)
    url = f"https://purplelink.llc/{PRODUCT_PAGES.get(rec['product'], rec['product'])}/"
    rec["utm_link"] = hub.make_utm(hub.paths(), url, rec["product"], "contest", source=rec["id"][:30],
                                   campaign=f"contest-{rec['id']}"[:40], medium="referral", today=today)
    return rec["utm_link"]


# ---------------------------------------------------------------- statements and checklist
def plain(text: str) -> str:
    text = text.replace("—", ",").replace("–", "-")
    return re.sub(r"\s+", " ", text).strip()


def photo_statement(ph: dict) -> str:
    cap = plain(ph["caption"]).rstrip(".")
    place = f" Location: {ph['location']}." if ph.get("location") else ""
    when = f" Taken {ph['taken']}." if ph.get("taken") else ""
    proc = (" Processing: exposure, contrast and colour adjustments, noise reduction and sharpening;"
            " nothing added or removed.")
    return f"{cap}.{place}{when}{proc}"


def product_statement(heading: str, para: str, link: str) -> str:
    text = plain(re.sub(r"\[(.*?)\]\(.*?\)", r"\1", para))
    text = re.sub(r"^[-*]\s*", "", text)
    sents = [s for s in re.split(r"(?<=\.)\s+", text) if s and not s.startswith("- ")][:3]
    body = " ".join(sents).rstrip(".")
    name = re.sub(r"\s*\(.*?\)", "", heading)
    return (f"{name} is made by Purplelink, a one-person software company in Georgia, USA. {body}. "
            f"More detail, screenshots and a free trial: {link}")


def checklist(rec: dict) -> list:
    flags = {f["flag"]: f for f in rec.get("flags") or []}
    items = [f"Re-read the rules at {rec['url']} (flags from: {rec.get('terms_source')}; registry read {rec.get('read') or 'undated'})."]
    items.append(f"Sign in or create the entry account yourself at {rec.get('entry_url') or 'the organiser site'}.")
    fee = rec.get("fee_usd")
    items.append("Fee: free." if fee == 0 else f"Fee: {rec.get('fee_text') or fee}. You pay it; the finder never does.")
    for name in ("licence_all_entries", "perpetual", "commercial_use", "irrevocable", "sublicensable", "licence_not_found",
                 "copyright_transfer", "exclusive"):
        if name in flags:
            items.append(f"Red flag to accept or walk away from ({name.replace('_', ' ')}): \"{flags[name]['sentence']}\"")
    if rec.get("ai_text") or "ai_rules" in flags:
        items.append(f"AI and processing rules: {rec.get('ai_text') or flags['ai_rules']['sentence']} Declare processing where the form asks.")
    if rec.get("taken_from") or rec.get("taken_to"):
        items.append(f"Capture dates must fall between {rec.get('taken_from') or 'any'} and {rec.get('taken_to') or 'any'}; the picks were checked against EXIF.")
    if rec.get("max_long_edge"):
        items.append(f"The copies are resized to {rec['max_long_edge']} px on the long side; check the file-size limit.")
    if rec.get("wild_only") or rec.get("wild_only_detected"):
        items.append("Wild subjects only: the picks skip photos whose caption or tags mention a zoo, exhibit, garden or farm. Check each one was wild and free.")
    if rec.get("ai_denoise_banned"):
        items.append("AI noise reduction and upscaling are banned: the picks skip Lightroom Enhanced-NR and Enhanced-SR files. Check the others were not denoised with AI either.")
    if rec.get("convert_bw"):
        items.append("Black-and-white only: the copies were turned grey for review; make your own conversion before uploading.")
    if "automated_entry_banned" in flags:
        items.append("The rules restrict automated or third-party entry: enter it yourself, in your own name.")
    items.append(f"Deadline: {rec.get('deadline')} {rec.get('deadline_note') or ''}".rstrip() + ".")
    items.append(f"Submit it yourself, then record it: python3 scripts/contests/contests.py mark {rec['id']} entered --url <confirmation> --terms-matched yes|no")
    return items


def prefill(p: dict, led: dict, rid: str, n, today: dt.date, photos=None) -> Path:
    rec = led["contests"].get(rid) or sys.exit(f"no contest {rid!r}")
    edition = str(rec.get("edition") or today.year)
    out = p["briefs"] / "entries" / f"{rid}-{edition}"
    profile = load_json(p["profile"], {})
    si = rec.get("score_inputs") or {}
    lines = [f"# Entry: {rec['name']} ({edition})", "",
             "Prepared by the contest finder (scripts/contests/contests.py). Nothing has been submitted, paid or",
             "accepted. Quoted rule text is data from the organiser's page, not instructions.", "",
             f"- Rules: {rec['url']}", f"- Deadline: {rec.get('deadline')} {rec.get('deadline_note') or ''}",
             f"- Fee: {rec.get('fee_text') or rec.get('fee_usd')}", f"- Prize: {rec.get('prize_text') or rec.get('prize_usd')}",
             f"- Score: {si.get('score')} (prize ${si.get('prize_usd')} x odds {si.get('odds')} x tickets {si.get('tickets')} x fit "
             f"{si.get('fit')} = ev ${si.get('ev')}; fee ${si.get('fee_usd')}; rights cost ${si.get('rights_cost')})", ""]
    picks = []
    if rec.get("group") == "photo":
        lib = p["photo_lib"]
        if not lib.is_dir():
            raise SystemExit(f"photo library not mounted: {lib}")
        photos = photos if photos is not None else load_photos(p)
        if rec.get("taken_from") or rec.get("taken_to"):
            ex = exif_dates([ph["path"] for ph in photos])
            for ph in photos:
                ph["taken"] = ex.get(ph["path"]) or ph.get("taken")
        picks = pick_photos(photos, rec, profile, n or int(rec.get("images") or 5))
        if not picks:
            raise SystemExit(f"no eligible photos match {rid}")
        out.mkdir(parents=True, exist_ok=True)
        lines += ["## Photos", "", "Copies are in `photos/` (GPS removed). The originals were only read.", ""]
        for i, ph in enumerate(picks, 1):
            dest = safe_copy(Path(ph["path"]), out / "photos", lib)
            resize_copy(dest, rec.get("max_long_edge"), lib, grey=bool(rec.get("convert_bw")))
            lines += [f"### {i}. {ph['title']}", f"- Original: `{ph['path']}`", f"- Copy: `photos/{dest.name}`",
                      f"- Taken: {ph.get('taken') or 'unknown'}; location: {ph.get('location') or 'not recorded'}",
                      f"- Why it fits: {', '.join(ph['why'])}", f"- Title for the form: {ph['title']}",
                      f"- Description for the form: {photo_statement(ph)}", ""]
        statement = f"{len(picks)} photos for {rec['name']}: " + "; ".join(ph["title"] for ph in picks) + "."
    else:
        out.mkdir(parents=True, exist_ok=True)
        heading, para = product_section(p["site"], rec["product"])
        link = tagged_link(p, rec, today)
        statement = product_statement(heading, para, link)
        lines += ["## Product", "", f"- Product: {heading}", f"- Link (tagged for the hub): {link}", "- Screenshots (in site/):"]
        lines += [f"  - `site/{x}`" for x in product_images(p["site"], rec["product"])] or ["  - none found"]
        lines += ["", "### Description for the form", "", statement, ""]
    lines += ["## Terms flags", ""] + [f"- **{f['severity']}** {f['flag']}: \"{f['sentence']}\"" + (f" ({f['note']})" if f.get("note") else "")
                                      for f in rec.get("flags") or []] + [""]
    lines += ["## Checklist (Ben)", ""] + [f"- [ ] {c}" for c in checklist(rec)] + [""]
    (out / "entry.md").write_text("\n".join(lines))
    rec.update(entry_dir=str(out), statement=statement, picks=[ph["file"] for ph in picks])
    if rec["status"] in ("open", "picked"):
        rec["status"] = "prefilled"
        history(rec, "status:prefilled", dir=str(out))
    return out


# ---------------------------------------------------------------- queue
def fm_value(v) -> str:
    s = str(v)
    return json.dumps(s) if re.search(r"[:#{}\[\],&*!|>%@`\"']", s) else s


def queue_item(rec: dict, today: dt.date) -> str:
    """An approval-queue item (scripts/queue/approval_queue.py): kind submission, executor ben. Approving it means
    only that Ben will enter; the entry itself stays his click."""
    sev = worst(rec.get("flags") or [])
    risk = {"severe": "high", "high": "high", "medium": "medium"}.get(sev, "low")
    fee = rec.get("fee_usd") or 0
    si = rec.get("score_inputs") or {}
    flags_line = ", ".join(f["flag"].replace("_", " ") for f in rec.get("flags") or [] if SEVERITY[f["severity"]] >= 2) or "none above low"
    expires = rec.get("deadline") or (today + dt.timedelta(days=30)).isoformat()
    fm = {
        "job": "contest-finder", "model": "rules (contests.py)", "kind": "submission",
        "target": f"{rec['name']} {rec.get('edition') or ''}".strip(), "executor": "ben", "risk": risk,
        "effort_minutes": 20 if rec.get("group") == "photo" else 30, "expires": expires,
        "expected_effect": f"one contest entry; expected value about {si.get('ev', 0)} USD before fees",
        "ledger": f"~/.purplelink/contests/ledger.json {rec['id']}", "channel": "contest", "contest": rec["id"],
        "assets": rec.get("product") or "photo-licensing",
    }
    fee_s = "free" if not fee else (rec.get("fee_text") or f"{fee} USD")
    body = f"""## Ask
Enter {rec['name']} yourself before {expires} with the prepared entry. Fee: {fee_s}.

## Why now
Deadline {rec.get('deadline')} {rec.get('deadline_note') or ''}. Score {si.get('score')}. Flags at medium or above: {flags_line}.{(' ' + rec['note_for_ben']) if rec.get('note_for_ben') else ''}

## Draft
{rec.get('statement') or ''}

## Verify
Terms flags from {rec.get('terms_source')}, registry read {rec.get('read') or 'undated'}; picks, statements and checklist in {rec.get('entry_dir')}/entry.md. The rules link is under Evidence (organiser pages often refuse automated link checks).

## If approved
Ben signs in, checks the picks and statements, accepts the terms, pays any fee and submits, all himself. Then: contests.py mark {rec['id']} entered --url <confirmation>.

## If rejected
contests.py mark {rec['id']} rejected (kept across editions) or skipped (this edition only).

## Evidence
Rules: {rec['url']}
Entry: {rec.get('entry_dir')}/entry.md; ledger record {rec['id']}.
"""
    return "\n".join(["---"] + [f"{k}: {fm_value(v)}" for k, v in fm.items()] + ["---", "", body])


def queue(p: dict, led: dict, rid: str, today: dt.date, offline: bool = False) -> str:
    """Files the item with approval_queue.py new, so the normal lint decides pending or needs-work. Never twice for one
    edition."""
    rec = led["contests"].get(rid) or sys.exit(f"no contest {rid!r}")
    if rec.get("queue_id"):
        return rec["queue_id"]
    if not rec.get("entry_dir"):
        raise SystemExit(f"prefill {rid} first")
    item = p["state"] / "queue-drafts" / f"{rid}-{rec.get('edition') or today.year}.md"
    item.parent.mkdir(parents=True, exist_ok=True)
    item.write_text(queue_item(rec, today))
    args = [sys.executable, str(p["queue_script"]), "new", str(item)] + (["--offline"] if offline else [])
    r = subprocess.run(args, capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    m = re.match(r"(\S+) -> (pending|needs-work)", out)
    if not m:
        raise SystemExit(f"queue failed: {out[:400]}")
    rec["queue_id"], rec["queue_folder"] = m.group(1), m.group(2)
    rec["queue_problems"] = [ln.strip().lstrip("- ") for ln in out.splitlines()[1:]]
    if rec["status"] in ("prefilled", "picked", "open"):
        rec["status"] = "queued"
        history(rec, "status:queued", queue=m.group(1), folder=m.group(2))
    return rec["queue_id"]


# ---------------------------------------------------------------- mark
def mark(led: dict, rid: str, status: str, note: str = "", url: str = "", terms_matched: str = "", today=None) -> dict:
    rec = led["contests"].get(rid) or sys.exit(f"no contest {rid!r}")
    if status not in ALLOWED:
        raise SystemExit(f"status must be one of {sorted(ALLOWED)}")
    if rec.get("status") not in ALLOWED[status]:
        raise SystemExit(f"cannot go from {rec.get('status')} to {status}")
    rec["status"] = status
    day = (today or dt.date.today()).isoformat()
    if status == "entered":
        rec["entered"], rec["entry_url_done"] = day, url
        if terms_matched:
            rec["terms_matched"] = terms_matched
    if status in ("shortlisted", "won", "lost"):
        rec["result"] = {"status": status, "date": day, "note": note}
    history(rec, f"status:{status}", note=note, url=url, terms_matched=terms_matched)
    return rec


# ---------------------------------------------------------------- scan and weekly
def scan(p: dict, today: dt.date, offline: bool = False, only=None, fetcher=fetch) -> dict:
    profile = load_json(p["profile"], {})
    led = load_ledger(p)
    st = merge_registry(led, load_json(p["sources"], {}), profile, today)
    photos = load_photos(p)
    st.update(photos=len(photos), changed=[], blocked_pages=[])
    p["pages"].mkdir(parents=True, exist_ok=True)
    for rid, rec in led["contests"].items():
        if (only and rid != only) or rec.get("source") != "registry":
            continue
        cache = p["pages"] / f"{rid}.txt"
        page = None
        if not offline and rec.get("status") != "rejected":
            texts, why = [], ""
            for u in [rec["url"]] + [x for x in rec.get("rules_urls") or [] if x != rec["url"]]:
                r = fetcher(u)
                if r["status"] == "ok":
                    texts.append(r["text"])
                else:
                    why = f"{r['status']}: {r.get('why', '')}"
            if texts:
                page = {"status": "ok", "text": "\n".join(texts)}
                cache.write_text(page["text"])
                rec["fetched"], rec["fetch"], rec["fetch_why"] = today.isoformat(), "ok", why
            else:
                rec["fetch"], rec["fetch_why"] = "blocked" if why.startswith("blocked") else "error", why
                st["blocked_pages"].append(rid)
        elif offline and cache.exists():
            page = {"status": "ok", "text": cache.read_text()}
        before = rec.get("terms_hash")
        evaluate(rec, page, profile, count_material(rec, photos, profile), today)
        if before and rec["terms_hash"] != before and rec["terms_source"].startswith("page"):
            st["changed"].append(rid)
            rec["terms_changed"] = today.isoformat()
            history(rec, "terms-changed", old=before, new=rec["terms_hash"])
        refresh_status(rec, today)
    led["scanned"] = today.isoformat()
    led["last_scan"] = st
    save_json(p["ledger"], led)
    return st


def weekly(p: dict, today: dt.date, offline: bool = False, fetcher=fetch) -> dict:
    """The launchd job: scan, pick up to `picks_per_week` contests, prefill and queue them, write the digest. Safe to
    run twice: picked contests are no longer open, and queue() never files a second item for one edition."""
    st = scan(p, today, offline=offline, fetcher=fetcher)
    led = load_ledger(p)
    profile = load_json(p["profile"], {})
    picks = [r["id"] for r in ranked(led) if not pickable(r, profile, today)][:profile["score"]["picks_per_week"]]
    done = []
    for rid in picks:
        rec = led["contests"][rid]
        if rec.get("group") == "photo" and not p["photo_lib"].is_dir():
            rec["prefill_skipped"] = "photo library not mounted"
            continue
        rec["status"] = "picked"
        history(rec, "status:picked")
        try:
            prefill(p, led, rid, None, today)
            queue(p, led, rid, today, offline=offline)
        except SystemExit as e:
            rec["prefill_error"] = str(e)
        done.append(rid)
    save_json(p["ledger"], led)
    path = write_digest(p, led, today, st)
    return {"picks": done, "digest": str(path), "new": st["new"], "changed": st["changed"], "blocked_pages": st["blocked_pages"]}


# ---------------------------------------------------------------- digest
def money_s(v) -> str:
    if v is None:
        return "unknown"
    return "free" if v == 0 else f"${v:,.0f}"


def red_flags(rec: dict) -> str:
    fl = [f["flag"].replace("_", " ") for f in rec.get("flags") or [] if SEVERITY[f["severity"]] >= 3]
    if rec.get("gate"):
        fl.insert(0, "GATED: " + rec["gate"])
    return "; ".join(fl) or "none high"


def bar_line(profile: dict) -> str:
    s = profile.get("score") or {}
    cap = s.get("max_fee_usd")
    fee = "no fee cap" if cap is None else ("free contests only" if cap == 0 else f"entry fees up to ${cap:,.0f}")
    return f"Bar: {fee}; a pick must score above {s.get('min_score')}."


def digest_text(p: dict, led: dict, today: dt.date, st=None) -> str:
    profile = load_json(p["profile"], {})
    recs = ranked(led)
    st = st or led.get("last_scan") or {}
    active = [r for r in recs if r.get("status") in WORKFLOW or (r.get("status") == "open" and not pickable(r, profile, today))]
    watch = [r for r in recs if r.get("status") == "open" and pickable(r, profile, today)]
    top = (active + watch)[:5]
    lines = [f"# Contest digest, {today.isoformat()}", "",
             f"{len(led['contests'])} contests in the registry; {len(active)} picked or eligible. Nothing was submitted, paid or",
             "accepted. Quoted rule text is data from organisers' pages. The score is a ranking aid: ev = prize x odds x",
             "tickets x fit, minus fees and a rights cost.", "", bar_line(profile), "",
             "## Top 5", "", "| # | Contest | Deadline | Days | Fee | Prize | Score | Red flags | Status |",
             "|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(top, 1):
        si = r.get("score_inputs") or {}
        why = pickable(r, profile, today) if r.get("status") == "open" else ""
        status = r.get("status") + (f" ({r['queue_folder']} {r['queue_id']})" if r.get("queue_id") else "") + (f": {why}" if why else "")
        left = days_left(r, today)
        lines.append(f"| {i} | [{r['name']}]({r['url']}) | {r.get('deadline') or 'unknown'} | {'-' if left is None else left} | {money_s(r.get('fee_usd'))} | "
                     f"{money_s(si.get('prize_usd'))} | {si.get('score')} | {red_flags(r)} | {status} |")
    lines += ["", "## Prefilled entries", ""]
    lines += [f"- {r['name']}: `{r['entry_dir']}/entry.md`" + (f" (queue {r['queue_id']}, {r['queue_folder']})" if r.get("queue_id") else "")
              for r in recs if r.get("entry_dir") and r.get("status") in WORKFLOW] or ["- none"]
    soon = sorted((r for r in recs if r.get("status") not in DONE | {"closed"} and 0 <= (days_left(r, today) if days_left(r, today) is not None else -1) <= 30),
                  key=lambda r: r["deadline"])
    lines += ["", "## Deadlines in the next 30 days", ""]
    lines += [f"- {r['deadline']} ({days_left(r, today)} days): {r['name']}, {money_s(r.get('fee_usd'))}; "
              + (pickable(r, profile, today) or r.get("status")) for r in soon] or ["- none"]
    gated = [r for r in recs if r.get("gate") and r.get("status") in WORKFLOW | {"open"}]
    lines += ["", "## Held back by the rights gate", "",
              "An all-entries perpetual licence, a copyright transfer or an exclusive licence keeps a contest out of the",
              "picks. To lift it for one contest, add \"allow_rights\": true to its entry in sources.json.", ""]
    lines += [f"- {r['name']}: {r['gate']}. \"" + next((f["sentence"] for f in r["flags"] if f["flag"] == "perpetual"), "") + "\"" for r in gated] or ["- none"]
    lines += ["", "## Changed this week", ""]
    changes = [f"- {rid}: terms text changed; re-read before entering" for rid in st.get("changed", [])]
    changes += [f"- {r['id']}: {r['deadline_warning']}" for r in recs if r.get("deadline_warning")]
    changes += [f"- {rid}: new edition" for rid in st.get("editions", [])]
    lines += changes or ["- nothing"]
    lines += ["", "## Pages not read this week", ""]
    lines += [f"- {rid}: {led['contests'][rid].get('fetch_why')}; flags come from the registry read of {led['contests'][rid].get('read')}"
              for rid in st.get("blocked_pages", []) if rid in led["contests"]] or ["- all read"]
    declined = [r for r in recs if r.get("status") == "rejected"]
    if declined:
        lines += ["", "## Declined by Ben", ""]
        lines += [f"- {r['name']}: " + next((h.get("note") for h in reversed(r.get("history") or [])
                                             if h.get("event") == "status:rejected" and h.get("note")), "no reason recorded")
                  for r in declined]
    lines += ["", "## Entered, waiting on results", ""]
    lines += [f"- {r['name']} (entered {r.get('entered') or 'before the finder'}; flags: {red_flags(r)}): record the result with `mark {r['id']} won|lost|shortlisted`"
              for r in recs if r.get("status") in ("entered", "shortlisted")] or ["- none"]
    props = proposals(p)
    if props:
        lines += ["", "## Found by research, not in the registry yet", "",
                  "Never picked until someone reads the rules and adds a registry entry.", ""]
        lines += [f"- {x['name']}: {x['url']} (deadline {x.get('deadline')}, fee {x.get('fee')})" for x in props[:15]]
    rest = [r for r in recs if r not in top and r.get("status") not in DONE]
    lines += ["", "## Not picked, and why", ""]
    lines += [f"- {r['name']}: {pickable(r, profile, today) or r.get('status')}" + (f" ({r['excluded_why']})" if r.get("excluded_why") else "")
              for r in rest][:40] or ["- none"]
    if st.get("possible_duplicates"):
        lines += ["", "## Possible duplicates (not merged)", ""] + [f"- {a} and {b}" for a, b in st["possible_duplicates"]]
    return "\n".join(lines) + "\n"


def write_digest(p: dict, led: dict, today: dt.date, st=None) -> Path:
    p["briefs"].mkdir(parents=True, exist_ok=True)
    path = p["briefs"] / f"digest-{today.isoformat()}.md"
    path.write_text(digest_text(p, led, today, st))
    return path


# ---------------------------------------------------------------- cli
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan"); s.add_argument("--offline", action="store_true"); s.add_argument("--only")
    s = sub.add_parser("list"); s.add_argument("--all", action="store_true")
    s = sub.add_parser("show"); s.add_argument("id")
    s = sub.add_parser("digest"); s.add_argument("--write", action="store_true")
    s = sub.add_parser("prefill"); s.add_argument("id"); s.add_argument("--n", type=int)
    s = sub.add_parser("queue"); s.add_argument("id"); s.add_argument("--offline", action="store_true")
    s = sub.add_parser("mark"); s.add_argument("id"); s.add_argument("status"); s.add_argument("--note", default="")
    s.add_argument("--url", default=""); s.add_argument("--terms-matched", default="", choices=["", "yes", "no"])
    s = sub.add_parser("weekly"); s.add_argument("--offline", action="store_true")
    a = ap.parse_args(argv)
    p, today = paths(), dt.date.today()
    if a.cmd == "scan":
        print(json.dumps(scan(p, today, offline=a.offline, only=a.only), default=str))
        return 0
    if a.cmd == "weekly":
        print(json.dumps(weekly(p, today, offline=a.offline)))
        return 0
    led = load_ledger(p)
    profile = load_json(p["profile"], {})
    if a.cmd == "list":
        for r in ranked(led):
            if not a.all and r.get("status") in ("closed", "excluded"):
                continue
            why = pickable(r, profile, today)
            print(f"{str((r.get('score_inputs') or {}).get('score')):>8}  {r.get('status'):<10} {r.get('deadline') or '?':<10} "
                  f"{r['id']:<34} {red_flags(r)[:50]}{'  [' + why + ']' if why else ''}")
    elif a.cmd == "show":
        print(json.dumps(led["contests"].get(a.id) or {}, indent=1, default=str))
    elif a.cmd == "digest":
        print(write_digest(p, led, today) if a.write else digest_text(p, led, today))
    elif a.cmd == "prefill":
        print(prefill(p, led, a.id, a.n, today))
        save_json(p["ledger"], led)
    elif a.cmd == "queue":
        print(queue(p, led, a.id, today, offline=a.offline))
        save_json(p["ledger"], led)
    elif a.cmd == "mark":
        rec = mark(led, a.id, a.status, a.note, a.url, a.terms_matched)
        save_json(p["ledger"], led)
        print(f"{rec['id']} -> {rec['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
