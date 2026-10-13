"""Affiliate program registry and link rewriting.

One source of truth for every affiliate program, shared by the daily digest (Modal) and by
scripts/affiliates.py, which rewrites links in the static guides and blog posts.

A program only changes a link once its status is "approved" and it has a tracked link, a deep-link template or
a tag. Candidates and pending applications are listed so the work is visible, but they rewrite nothing.

Lifecycle: candidate -> applied -> approved (or rejected). Moving a program to "approved" is a manual edit made
after the network confirms it, with the tracked link copied from the network's dashboard. This file is public:
never put a password, API key or payout detail in it.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional
from urllib.parse import quote, urlparse

REL = "sponsored noopener"
DISCLOSURE = (
    "Some links on this page are affiliate links. If you buy through one, Purplelink may earn a commission "
    "at no extra cost to you. It does not change which products we mention or what we say about them."
)
AMAZON_DISCLOSURE = "As an Amazon Associate I earn from qualifying purchases"
DISCLOSURE_MARK = 'class="aff-disclosure"'
DISCLOSURE_HTML = f"<p {DISCLOSURE_MARK}>{html.escape(DISCLOSURE)}</p>"
LABEL_TEXT = "(paid link)"
LABEL_HTML = f'<span class="aff-label">{LABEL_TEXT}</span>'
_LABEL_AFTER = re.compile(r'\s*<span class="aff-label">')


@dataclass(frozen=True)
class Program:
    id: str
    name: str
    domains: tuple          # hosts whose links may be rewritten, without "www."
    network: str
    status: str             # candidate | applied | approved | rejected
    commission: str         # as stated by the program, with the date it was read
    terms_checked: str      # ISO date the terms were last read on the program's own page
    source_url: str
    link: str = ""          # fixed tracked link (used when there is no template)
    deep_link: str = ""     # template containing {url}, which gets the percent-encoded destination
    tag: str = ""           # Amazon-style tracking id appended as ?tag=
    only_paths: str = ""    # regex; when set, only URL paths matching it are rewritten
    notes: str = ""
    topics: tuple = field(default_factory=tuple)

    @property
    def live(self) -> bool:
        return self.status == "approved" and bool(self.link or self.deep_link or self.tag)


REGISTRY: tuple = (
    Program(
        id="amazon",
        name="Amazon Associates",
        domains=("amazon.com",),
        network="Amazon Associates",
        status="approved",
        commission="Category rates set by Amazon",
        terms_checked="2026-10-12",
        source_url="https://affiliate-program.amazon.com/help/operating/agreement",
        tag="purplelinkpl-20",
        only_paths=r"^/(?:dp/|s\?|gp/product/|[^/]+/dp/)",
        notes="Live before this registry existed. Amazon requires its own disclosure sentence, not the generic one.",
        topics=("desk", "equipment"),
    ),
    Program(
        id="setapp",
        name="Setapp",
        domains=("setapp.com",),
        network="Impact",
        status="candidate",
        commission="$25 flat per new paid user, 45-day cookie, $10 minimum payout (Setapp page, read 2026-10-12)",
        terms_checked="2026-10-12",
        source_url="https://setapp.com/affiliate-program",
        notes="Free to join, no traffic minimum, applications reviewed.",
        topics=("mac-apps", "window-managers", "disk-space", "latex-editors"),
    ),
    Program(
        id="1password",
        name="1Password",
        domains=("1password.com",),
        network="CJ Affiliate",
        status="candidate",
        commission="Reported between $2 plus 25% of the first payment and 40% of sales; sources disagree. "
                   "Read the official page before applying.",
        terms_checked="2026-10-12",
        source_url="https://1password.com/affiliate",
        notes="Only where a guide really discusses password managers. Official page not read yet.",
        topics=("privacy", "security"),
    ),
    Program(
        id="wordvice",
        name="Wordvice",
        domains=("wordvice.com",),
        network="In-house",
        status="candidate",
        commission="15% of a new client's first order, after the client's 10% discount; 90-day cookie; no minimum order or payout minimum (program page, read 2026-10-12)",
        terms_checked="2026-10-12",
        source_url="https://wordvice.com/affiliate/home/",
        notes="Self-serve. Terms last amended 2020-12-21.",
        topics=("academic-editing",),
    ),
    Program(
        id="raycast",
        name="Raycast",
        domains=("raycast.com",),
        network="Rewardful",
        status="candidate",
        commission="30% of all payments from referred Pro users, recurring; referred user gets 10% off; cookie length not stated (Raycast blog, read 2026-10-12)",
        terms_checked="2026-10-12",
        source_url="https://raycast.com/blog/affiliate-program",
        notes="Open to any Raycast account holder.",
        topics=("mac-apps","launchers"),
    ),
    Program(
        id="paperpal",
        name="Paperpal",
        domains=("paperpal.com",),
        network="TrackDesk",
        status="candidate",
        commission="30% one-time on each Paperpal Prime purchase; 60-day cookie (program page, read 2026-10-12)",
        terms_checked="2026-10-12",
        source_url="https://paperpal.com/affiliate-program",
        notes="Self-serve. Aimed at students, researchers and academic influencers.",
        topics=("academic-writing",),
    ),
    Program(
        id="scrivener",
        name="Scrivener",
        domains=("literatureandlatte.com",),
        network="FirstPromoter",
        status="candidate",
        commission="20% on licences sold through the link; cookie length not stated (Literature and Latte page, read 2026-10-12)",
        terms_checked="2026-10-12",
        source_url="https://www.literatureandlatte.com/becoming-a-sales-affiliate",
        notes="Self-serve.",
        topics=("writing-apps",),
    ),
    Program(
        id="ulysses",
        name="Ulysses",
        domains=("ulysses.app",),
        network="In-house",
        status="candidate",
        commission="25% per subscriber; readers get 25% off the first year; cookie length not stated (program page, read 2026-10-12)",
        terms_checked="2026-10-12",
        source_url="https://ulysses.app/affiliate/",
        notes="Application form, reviewed.",
        topics=("writing-apps","mac-apps"),
    ),
    Program(
        id="proton",
        name="Proton",
        domains=("proton.me",),
        network="In-house",
        status="candidate",
        commission="30% on new subscriptions and renewals for most products; one product group differs; $100 minimum payout; cookie length not stated (Proton partner page, read 2026-10-12)",
        terms_checked="2026-10-12",
        source_url="https://proton.me/partners/affiliates",
        notes="Partners must disclose the relationship. Paid search on brand terms and cookie stuffing are banned.",
        topics=("privacy","security"),
    ),
    Program(
        id="pcloud",
        name="pCloud",
        domains=("pcloud.com",),
        network="In-house",
        status="candidate",
        commission="20% of every payment, or of a Lifetime purchase; 45-day cookie; PayPal payout from $10 (pCloud help page, read 2026-10-12)",
        terms_checked="2026-10-12",
        source_url="https://help.pcloud.com/article/affiliate-program",
        notes="Open to adults (18+).",
        topics=("cloud-storage","disk-space"),
    ),
    Program(
        id="readwise",
        name="Readwise",
        domains=("readwise.io",),
        network="In-house",
        status="candidate",
        commission="33% per paying subscriber; cookie length not stated (Readwise docs, read 2026-10-12)",
        terms_checked="2026-10-12",
        source_url="https://docs.readwise.io/affiliates",
        notes="Application form, reviewed. Approved affiliates receive custom links.",
        topics=("reading","research"),
    ),
    Program(
        id="logitech",
        name="Logitech",
        domains=("logitech.com",),
        network="Impact",
        status="candidate",
        commission="4% to 10% depending on brand and season; 30-day cookie (Logitech affiliate page, read 2026-10-12)",
        terms_checked="2026-10-12",
        source_url="https://www.logitech.com/en-us/programs/affiliate-program",
        notes="Reviewed on Impact. Free to join.",
        topics=("keyboards","equipment"),
    ),
)

# Not eligible, kept so nobody researches them twice.
CLOSED = {
    "backblaze": "Closed to new affiliates since 2025-08-30 (backblaze.com/affiliate.html).",
    "overleaf": "No cash affiliate program found, only a referral scheme that gives users premium features.",
    "paddle": "No blogger affiliate program found, only tooling to run your own.",
    "ezoic": "Reportedly 250,000 monthly users minimum since Feb 2026.",
    "raptive": "Reportedly 25,000 monthly pageviews minimum since Oct 2025; site is about 4,000.",
}


def _host(url: str) -> str:
    h = (urlparse(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def _path_query(url: str) -> str:
    u = urlparse(url)
    return u.path + (("?" + u.query) if u.query else "")


def program_for(url: str, registry=None) -> Optional[Program]:
    """The live program whose domain (and path rule) matches this URL, if any."""
    host = _host(url)
    if not host:
        return None
    for p in (registry if registry is not None else REGISTRY):
        if not p.live or not any(host == d or host.endswith("." + d) for d in p.domains):
            continue
        if p.only_paths and not re.search(p.only_paths, _path_query(url)):
            continue
        return p
    return None


def tracked_owner(url: str, registry=None) -> Optional[Program]:
    """The live program whose tracked link this URL already is, if any."""
    for p in (registry if registry is not None else REGISTRY):
        if not p.live:
            continue
        if p.tag:
            if program_for(url, [p]) and re.search(r"[?&]tag=" + re.escape(p.tag) + r"(?:&|$)", url):
                return p
            continue
        fixed = (p.link or p.deep_link.split("{url}")[0]).split("?")[0]
        if fixed and url.startswith(fixed):
            return p
    return None


def is_tracked(url: str, registry=None) -> bool:
    return tracked_owner(url, registry) is not None


def tracked_url(url: str, p: Program) -> str:
    if p.tag:
        base = re.sub(r"([?&])tag=[^&]*&?", r"\1", url).rstrip("?&")
        return base + ("&" if "?" in base else "?") + "tag=" + p.tag
    if p.deep_link:
        return p.deep_link.replace("{url}", quote(url, safe=""))
    return p.link


def rewrite_url(url: str, registry=None) -> tuple:
    """(new_url, program) for a link that should change, else (url, None)."""
    if is_tracked(url, registry):
        return url, None
    p = program_for(url, registry)
    if not p:
        return url, None
    return tracked_url(url, p), p


_A_TAG = re.compile(r'<a\b([^>]*?)\bhref="([^"]+)"([^>]*)>', re.I)


def _uses(url: str, registry=None) -> Optional[Program]:
    """The program a link belongs to, whether or not it is already tracked."""
    return tracked_owner(url, registry) or program_for(url, registry)


def rewrite_html(page: str, registry=None) -> tuple:
    """Rewrite links to live programs in one page. Returns (new_page, number_changed).

    Idempotent. Every link to a live program gets rel="sponsored noopener". When any non-Amazon program is used,
    the generic disclosure is inserted once, right after the page's </h1>, and every such link is followed by a
    small "(paid link)" label, because a notice at the top alone is not close enough to the link. Amazon links keep
    their existing markup and sentence, which scripts/check_content.py already enforces.
    """
    changed = 0
    used_generic = False
    out, pos = [], 0
    for m in _A_TAG.finditer(page):
        href = html.unescape(m.group(2))
        p = _uses(href, registry)
        if p is None:
            continue
        new = tracked_url(href, p) if not is_tracked(href, registry) else href
        tag = m.group(0)
        if new != href:
            tag = tag.replace(f'href="{m.group(2)}"', f'href="{html.escape(new, quote=True)}"', 1)
        rel = re.search(r'\brel="([^"]*)"', tag)
        if rel:
            vals = rel.group(1).split()
            for v in REL.split():
                if v not in vals:
                    vals.append(v)
            tag = tag[:rel.start()] + 'rel="' + " ".join(vals) + '"' + tag[rel.end():]
        else:
            tag = tag[:-1] + f' rel="{REL}">'
        if tag != m.group(0):
            changed += 1
        if p.id != "amazon":
            used_generic = True
        out.append(page[pos:m.start()])
        out.append(tag)
        pos = m.end()
        if p.id != "amazon":
            close = page.find("</a>", m.end())
            if close != -1:
                close += len("</a>")
                out.append(page[pos:close])
                pos = close
                if not _LABEL_AFTER.match(page, close):
                    out.append(LABEL_HTML)
                    changed += 1
    out.append(page[pos:])
    result = "".join(out)
    if used_generic and DISCLOSURE_MARK not in result:
        result, n = re.subn(r"</h1>", lambda m: m.group(0) + "\n        " + DISCLOSURE_HTML, result, count=1)
        if n == 0:
            raise ValueError("page has affiliate links but no </h1> to place the disclosure after")
        changed += 1
    return result, changed


def lint_html(page: str, registry=None) -> list:
    """Problems with affiliate links on one page."""
    problems, generic, amazon = [], False, False
    for m in _A_TAG.finditer(page):
        href = html.unescape(m.group(2))
        p = _uses(href, registry)
        if p is None:
            continue
        if not is_tracked(href, registry):
            problems.append(f"{p.id} link not tracked: {href[:80]}")
        rel = re.search(r'\brel="([^"]*)"', m.group(1) + m.group(3))
        if not rel or "sponsored" not in rel.group(1).split():
            problems.append(f"{p.id} link without rel=sponsored: {href[:80]}")
        amazon |= p.id == "amazon"
        generic |= p.id != "amazon"
        if p.id != "amazon":
            close = page.find("</a>", m.end())
            if close == -1 or not _LABEL_AFTER.match(page, close + len("</a>")):
                problems.append(f"{p.id} link without a (paid link) label: {href[:80]}")
    if generic and DISCLOSURE_MARK not in page:
        problems.append("affiliate links but no disclosure paragraph")
    if amazon and AMAZON_DISCLOSURE not in page:
        problems.append("Amazon links but no Amazon Associate statement")
    return problems


def check_registry(registry=None, today: Optional[date] = None, max_age_days: int = 180) -> list:
    """Problems with the registry itself."""
    today = today or date.today()
    problems, seen = [], set()
    for p in (registry if registry is not None else REGISTRY):
        if p.id in seen:
            problems.append(f"{p.id}: duplicate id")
        seen.add(p.id)
        if p.status not in ("candidate", "applied", "approved", "rejected"):
            problems.append(f"{p.id}: unknown status {p.status!r}")
        has_link = bool(p.link or p.deep_link or p.tag)
        if p.status == "approved" and not has_link:
            problems.append(f"{p.id}: approved but no tracked link")
        if p.status != "approved" and has_link:
            problems.append(f"{p.id}: has a tracking link but is not approved")
        for link in (p.link, p.deep_link):
            if link and not link.startswith("https://"):
                problems.append(f"{p.id}: tracked link must be https")
        if p.deep_link and "{url}" not in p.deep_link:
            problems.append(f"{p.id}: deep_link needs a {{url}} placeholder")
        age = (today - date.fromisoformat(p.terms_checked)).days
        if p.status == "approved" and age > max_age_days:
            problems.append(f"{p.id}: terms last read {age} days ago, re-read {p.source_url}")
    return problems


def live_programs(registry=None) -> list:
    return [p for p in (registry if registry is not None else REGISTRY) if p.live]
