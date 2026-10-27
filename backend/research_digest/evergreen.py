"""Route each week's curated papers into the evergreen /learn/ articles they update.

Two steps, kept apart on purpose:

1. route(): one model call assigns each curated paper to at most one article in
   topics.TOPICS, or to none. The code accepts only known slugs and real item
   indexes, so the model cannot invent an article or a paper.
2. apply_updates(): no model prose at all. It writes the curator's existing
   abstract-only summary and "why it matters" (the same text the roundup already
   auto-publishes) into a marked "What newer research adds" section, keeps the
   newest MAX_ENTRIES, and refreshes the article's dateModified, its visible
   "Updated" date and its sitemap lastmod.

The section's entries live in research/evergreen.json in the site repo, and the
section is re-rendered from that store each run, so a rerun is idempotent and a
hand edit to the store (to pull an entry) sticks.
"""
from __future__ import annotations

import html
import json
import logging
import os
import re
from datetime import date as _date

from ._http import anthropic_message, parse_json
from .models import WeeklyDigest
from .publisher import bump_lastmod
from .topics import TOPICS, catalog_text

logger = logging.getLogger(__name__)

STORE_REL = "research/evergreen.json"
SITE = "https://getmuscleonglp.com"
MAX_ENTRIES = 5            # per article, newest first; older ones roll off
MAX_NEW_PER_ARTICLE = 2    # per week, so one busy topic cannot flood a page
SECTION_START = "<!-- research-updates:start -->"
SECTION_END = "<!-- research-updates:end -->"
ANCHOR = '<nav class="related-reading"'

ROUTER_SYSTEM = """You match new research papers to existing evergreen articles on a site about keeping muscle while on GLP-1 drugs.

For each paper, pick the ONE article whose reader question the paper directly answers or updates, judged by the article's scope and by what its readers search. If no article is a clear fit, answer "none". Most weeks several papers fit nothing; that is expected.

Strict rules:
- Assign only when a reader of that article would see the paper as new evidence on their exact question. Topical overlap ("both mention GLP-1") is not enough.
- Never assign a paper about dosing, titration, compounding or sourcing a drug.
- Use only slugs from the list. One article per paper at most.

Reply with JSON only: {"assignments": [{"index": <paper index>, "slug": "<slug or none>", "reason": "<one short clause>"}]}"""


# ----------------------------------------------------------------- routing ----

async def route(client, digest: WeeklyDigest) -> dict[str, list]:
    """Return {slug: [DigestItem, ...]} for the papers that fit an article."""
    if not digest.items:
        return {}
    papers = "\n\n".join(
        f"[{i}] {it.paper.title}\nSUMMARY: {it.summary}\nWHY: {it.why_it_matters}"
        for i, it in enumerate(digest.items)
    )
    raw = await anthropic_message(
        client, system=ROUTER_SYSTEM,
        user_content=[{"type": "text", "text": f"ARTICLES:\n{catalog_text()}\n\nPAPERS:\n{papers}"}],
        max_tokens=2000, temperature=0.0,
    )
    return assignments_from(parse_json(raw), digest)


def assignments_from(data: dict, digest: WeeklyDigest) -> dict[str, list]:
    """Validate the model's answer: known slugs, real indexes, one article per paper."""
    routed: dict[str, list] = {}
    seen: set[int] = set()
    for a in (data or {}).get("assignments", []):
        idx, slug = a.get("index"), a.get("slug")
        if not isinstance(idx, int) or not 0 <= idx < len(digest.items) or idx in seen:
            continue
        if slug not in TOPICS:
            continue  # "none", or a slug the model made up
        seen.add(idx)
        routed.setdefault(slug, []).append(digest.items[idx])
    for slug, items in routed.items():
        items.sort(key=lambda it: it.relevance, reverse=True)
        del items[MAX_NEW_PER_ARTICLE:]
    return routed


# ---------------------------------------------------------------- updating ----

def _entry(item, week_date: str) -> dict:
    p = item.paper
    return {"date": week_date, "title": p.title, "venue": p.venue, "is_preprint": bool(p.is_preprint),
            "pub_date": p.pub_date, "url": p.url, "summary": item.summary, "why": item.why_it_matters}


def _month_year(iso: str) -> str:
    try:
        return _date.fromisoformat(iso[:10]).strftime("%B %Y")
    except ValueError:
        return ""


def render_section(entries: list[dict]) -> str:
    """The section, built from the roundup's own rr-* card classes so it needs no new CSS."""
    e = html.escape
    items = []
    for x in entries:
        badge = ' <span class="rr-preprint">Preprint</span>' if x.get("is_preprint") else ""
        meta = " &middot; ".join(filter(None, [e(x.get("venue", "")), e(_month_year(x.get("pub_date", "")))]))
        why = f'\n          <p class="rr-why"><strong>Why it matters:</strong> {e(x["why"])}</p>' if x.get("why") else ""
        kind = "preprint" if x.get("is_preprint") else "paper"
        # h3 (the section's own heading is the h2), sized inline to match the
        # site's ".rr-item h2" rule so no stylesheet change is needed.
        items.append(f"""        <article class="rr-item">
          <h3 style="font-size:1.15rem;line-height:1.3;margin:0 0 6px"><a href="{e(x['url'])}" target="_blank" rel="noopener" style="color:var(--ink);text-decoration:none">{e(x['title'])}</a>{badge}</h3>
          <p class="rr-meta">{meta}</p>
          <p>{e(x['summary'])}</p>{why}
          <p class="rr-source"><a href="{e(x['url'])}" target="_blank" rel="noopener">Read the {kind} &rarr;</a></p>
        </article>""")
    return f"""{SECTION_START}
      <section class="research-updates" id="newer-research" aria-labelledby="newer-research-h">
        <h2 id="newer-research-h">What newer research adds</h2>
        <p>Studies published since this guide was written, summarized from their abstracts. Not medical advice; one study rarely settles a question.</p>
        <div class="rr-list">
{chr(10).join(items)}
        </div>
        <p>Every paper we track is in the <a href="/research/">weekly research roundups</a>.</p>
      </section>
      {SECTION_END}
"""


def upsert_section(page: str, section: str) -> str | None:
    """Replace the marked section, or insert it before Related reading. None if no anchor."""
    if SECTION_START in page and SECTION_END in page:
        start = page.index(SECTION_START)
        end = page.index(SECTION_END) + len(SECTION_END)
        # The rendered section ends with a newline; swallow the old one too.
        if page[end:end + 1] == "\n":
            end += 1
        return page[:start] + section + page[end:]
    pos = page.find(ANCHOR)
    if pos == -1:
        return None
    line_start = page.rfind("\n", 0, pos) + 1
    return page[:line_start] + "      " + section + page[line_start:]


_LONG_DATE = re.compile(r"(<span>Updated )([A-Z][a-z]+ \d{1,2}, \d{4})(</span>)")
_ISO_DATE = re.compile(r"(<span>Updated )(\d{4}-\d{2}-\d{2})(</span>)")
_DATE_MODIFIED = re.compile(r'("dateModified":\s*")[^"]*(")')


def bump_dates(page: str, iso: str) -> str:
    """Set dateModified and the visible "Updated" date, keeping the page's own date format."""
    d = _date.fromisoformat(iso)
    page = _DATE_MODIFIED.sub(lambda m: m.group(1) + iso + m.group(2), page, count=1)
    page = _LONG_DATE.sub(lambda m: m.group(1) + f"{d.strftime('%B')} {d.day}, {d.year}" + m.group(3), page, count=1)
    return _ISO_DATE.sub(lambda m: m.group(1) + iso + m.group(3), page, count=1)


def _load_store(site_dir: str) -> dict:
    path = os.path.join(site_dir, STORE_REL)
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def apply_updates(site_dir: str, routed: dict[str, list], week_date: str) -> list[str]:
    """Write routed papers into their articles. Returns the URLs of articles that changed."""
    store = _load_store(site_dir)
    smp = os.path.join(site_dir, "sitemap.xml")
    sitemap = open(smp).read() if os.path.exists(smp) else None
    updated: list[str] = []

    for slug, items in routed.items():
        page_path = os.path.join(site_dir, "learn", slug, "index.html")
        if not os.path.exists(page_path):
            logger.warning("evergreen: no article at learn/%s/; skipped", slug)
            continue
        existing = store.get(slug, [])
        known = {x["url"] for x in existing}
        fresh = [_entry(it, week_date) for it in items if it.paper.url not in known]
        if not fresh:
            continue
        entries = (fresh + existing)[:MAX_ENTRIES]

        with open(page_path) as f:
            page = f.read()
        new_page = upsert_section(page, render_section(entries))
        if new_page is None:
            logger.warning("evergreen: learn/%s/ has no Related reading anchor; skipped", slug)
            continue
        with open(page_path, "w") as f:
            f.write(bump_dates(new_page, week_date))

        store[slug] = entries
        url = f"{SITE}/learn/{slug}/"
        if sitemap is not None:
            sitemap = bump_lastmod(sitemap, url, week_date)
        updated.append(url)
        logger.info("evergreen: %s +%d paper(s)", slug, len(fresh))

    if updated:
        os.makedirs(os.path.dirname(os.path.join(site_dir, STORE_REL)), exist_ok=True)
        with open(os.path.join(site_dir, STORE_REL), "w") as f:
            json.dump(store, f, indent=2)
        if sitemap is not None:
            with open(smp, "w") as f:
                f.write(sitemap)
    return updated
