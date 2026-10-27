# backend/tests/test_research_digest_evergreen.py
"""Coverage for routing weekly papers into the evergreen /learn/ articles.

The updater auto-publishes into ranking articles, so the guarantees that matter
are structural: the model cannot invent an article or a paper, a rerun changes
nothing, an article without the expected anchor is left alone, and the page's
own date format survives.
"""
import asyncio
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from research_digest import evergreen  # noqa: E402
from research_digest.harvester import Paper  # noqa: E402
from research_digest.models import DigestItem, WeeklyDigest  # noqa: E402
from research_digest.publisher import noindex_posts  # noqa: E402
from research_digest.renderer import POST_ROBOTS, render_post_html  # noqa: E402
from research_digest.topics import TOPICS  # noqa: E402


def _item(n: int, relevance: int = 3, preprint: bool = False) -> DigestItem:
    paper = Paper(title=f"Paper {n} on lean mass", authors=["Doe J"], source="PubMed",
                  is_preprint=preprint, venue="Obesity" if not preprint else "Preprint",
                  pub_date="2026-10-20", url=f"https://doi.org/10.1000/p{n}", abstract="...")
    return DigestItem(paper=paper, relevance=relevance, summary=f"Summary {n} <b>&</b>.",
                      why_it_matters=f"Why {n}.")


def _digest(*items) -> WeeklyDigest:
    return WeeklyDigest(date="2026-11-02", week_label="Oct 27-Nov 2, 2026", slug="2026-11-02",
                        intro="", items=list(items))


ARTICLE = """<!DOCTYPE html><html><head>
<script type="application/ld+json">{"@type": "Article", "datePublished": "2026-07-10", "dateModified": "2026-07-10"}</script>
</head><body>
      <h1>Does Ozempic cause muscle loss?</h1>
        <span>Updated July 10, 2026</span>
      <p>Body.</p>
      <nav class="related-reading" aria-label="Related reading">
        <h2>Related reading</h2>
      </nav>
      <div class="references" id="references"><ol><li id="ref-1">Ref.</li></ol></div>
</body></html>
"""


def _site(tmp_path, page=ARTICLE, slug="ozempic-muscle-loss"):
    (tmp_path / "learn" / slug).mkdir(parents=True)
    (tmp_path / "learn" / slug / "index.html").write_text(page)
    (tmp_path / "sitemap.xml").write_text(
        f"<urlset>\n  <url>\n    <loc>https://getmuscleonglp.com/learn/{slug}/</loc>\n"
        "    <lastmod>2026-07-10</lastmod>\n  </url>\n</urlset>\n")
    return tmp_path


# --------------------------------------------------------------- topic map ----

def test_every_topic_is_a_real_article_slug_with_queries():
    site_learn = Path(__file__).resolve().parents[3] / "muscleonglp" / "learn"
    for slug, t in TOPICS.items():
        assert slug == slug.lower() and " " not in slug
        assert t["headline"] and t["scope"] and t["queries"]
        if site_learn.is_dir():  # only when the site repo sits next to this one
            assert (site_learn / slug / "index.html").exists(), slug


def test_dose_schedule_article_is_never_a_target():
    # The site gives no dosing guidance; new papers must not be written into it.
    assert "glp1-dose-schedules" not in TOPICS


# ----------------------------------------------------------------- routing ----

def test_assignments_reject_unknown_slugs_bad_indexes_and_duplicates():
    d = _digest(_item(0), _item(1), _item(2))
    routed = evergreen.assignments_from({"assignments": [
        {"index": 0, "slug": "ozempic-muscle-loss"},
        {"index": 0, "slug": "creatine-and-ozempic"},   # same paper twice: first wins
        {"index": 1, "slug": "made-up-article"},
        {"index": 2, "slug": "none"},
        {"index": 9, "slug": "protein-on-glp1"},         # no such paper
        {"index": "1", "slug": "protein-on-glp1"},       # not an int
    ]}, d)
    assert list(routed) == ["ozempic-muscle-loss"]
    assert [it.paper.url for it in routed["ozempic-muscle-loss"]] == ["https://doi.org/10.1000/p0"]


def test_assignments_cap_new_papers_per_article_by_relevance():
    d = _digest(_item(0, relevance=2), _item(1, relevance=3), _item(2, relevance=3))
    routed = evergreen.assignments_from(
        {"assignments": [{"index": i, "slug": "ozempic-muscle-loss"} for i in range(3)]}, d)
    assert len(routed["ozempic-muscle-loss"]) == evergreen.MAX_NEW_PER_ARTICLE
    assert all(it.relevance == 3 for it in routed["ozempic-muscle-loss"])


def test_route_sends_the_catalog_and_validates_the_reply(monkeypatch):
    seen = {}

    async def fake_message(client, *, system, user_content, max_tokens, temperature=0.1, model=None):
        seen["text"] = user_content[0]["text"]
        return '```json\n{"assignments": [{"index": 0, "slug": "creatine-and-ozempic", "reason": "x"}]}\n```'

    monkeypatch.setattr(evergreen, "anthropic_message", fake_message)
    routed = asyncio.run(evergreen.route(None, _digest(_item(0))))
    assert "creatine-and-ozempic" in routed
    assert "can you take creatine on glp 1" in seen["text"]  # real queries reach the model


# ---------------------------------------------------------------- updating ----

def test_apply_inserts_section_bumps_dates_and_sitemap(tmp_path):
    site = _site(tmp_path)
    urls = evergreen.apply_updates(str(site), {"ozempic-muscle-loss": [_item(0, preprint=True)]}, "2026-11-02")
    assert urls == ["https://getmuscleonglp.com/learn/ozempic-muscle-loss/"]
    page = (site / "learn/ozempic-muscle-loss/index.html").read_text()
    assert page.index(evergreen.SECTION_START) < page.index('<nav class="related-reading"')
    assert '"dateModified": "2026-11-02"' in page and '"datePublished": "2026-07-10"' in page
    assert "<span>Updated November 2, 2026</span>" in page
    assert "Summary 0 &lt;b&gt;&amp;&lt;/b&gt;." in page          # escaped, never raw HTML
    assert '<span class="rr-preprint">Preprint</span>' in page and "Read the preprint" in page
    assert "<lastmod>2026-11-02</lastmod>" in (site / "sitemap.xml").read_text()
    store = json.loads((site / evergreen.STORE_REL).read_text())
    assert store["ozempic-muscle-loss"][0]["url"] == "https://doi.org/10.1000/p0"


def test_iso_updated_date_keeps_its_format(tmp_path):
    site = _site(tmp_path, ARTICLE.replace("Updated July 10, 2026", "Updated 2026-07-17"))
    evergreen.apply_updates(str(site), {"ozempic-muscle-loss": [_item(0)]}, "2026-11-02")
    assert "<span>Updated 2026-11-02</span>" in (site / "learn/ozempic-muscle-loss/index.html").read_text()


def test_rerun_is_idempotent_and_known_papers_are_not_repeated(tmp_path):
    site = _site(tmp_path)
    routed = {"ozempic-muscle-loss": [_item(0)]}
    evergreen.apply_updates(str(site), routed, "2026-11-02")
    first = (site / "learn/ozempic-muscle-loss/index.html").read_text()
    assert evergreen.apply_updates(str(site), routed, "2026-11-09") == []   # nothing new
    assert (site / "learn/ozempic-muscle-loss/index.html").read_text() == first
    # A genuinely new paper replaces the section in place: still exactly one.
    evergreen.apply_updates(str(site), {"ozempic-muscle-loss": [_item(1)]}, "2026-11-09")
    page = (site / "learn/ozempic-muscle-loss/index.html").read_text()
    assert page.count(evergreen.SECTION_START) == 1 and page.count(evergreen.SECTION_END) == 1
    assert page.index("Paper 1 on lean mass") < page.index("Paper 0 on lean mass")   # newest first
    assert '      <nav class="related-reading"' in page                              # indentation kept


def test_section_keeps_only_the_newest_entries(tmp_path):
    site = _site(tmp_path)
    for n in range(evergreen.MAX_ENTRIES + 2):
        evergreen.apply_updates(str(site), {"ozempic-muscle-loss": [_item(n)]}, f"2026-11-{n + 1:02d}")
    store = json.loads((site / evergreen.STORE_REL).read_text())["ozempic-muscle-loss"]
    assert len(store) == evergreen.MAX_ENTRIES
    assert store[0]["url"].endswith(f"p{evergreen.MAX_ENTRIES + 1}")


def test_article_without_anchor_or_missing_is_left_alone(tmp_path):
    no_anchor = ARTICLE.replace('<nav class="related-reading"', '<nav class="other"')
    site = _site(tmp_path, no_anchor)
    routed = {"ozempic-muscle-loss": [_item(0)], "protein-on-glp1": [_item(1)]}
    assert evergreen.apply_updates(str(site), routed, "2026-11-02") == []
    assert (site / "learn/ozempic-muscle-loss/index.html").read_text() == no_anchor
    assert not (site / evergreen.STORE_REL).exists()


# ------------------------------------------------------------ roundup noindex ----

def test_new_posts_render_noindex_follow():
    html_out = render_post_html(_digest(_item(0), _item(1)))
    assert f'<meta name="robots" content="{POST_ROBOTS}">' in html_out
    assert POST_ROBOTS == "noindex, follow"


def test_existing_posts_are_switched_to_noindex_and_the_hub_is_not(tmp_path):
    (tmp_path / "research" / "2026-10-19").mkdir(parents=True)
    old = '<meta name="robots" content="index, follow, max-image-preview:large">'
    (tmp_path / "research" / "2026-10-19" / "index.html").write_text(f"<head>{old}</head>")
    (tmp_path / "research" / "index.html").write_text(f"<head>{old}</head>")
    assert noindex_posts(str(tmp_path)) == 1
    assert POST_ROBOTS in (tmp_path / "research/2026-10-19/index.html").read_text()
    assert old in (tmp_path / "research/index.html").read_text()
    assert noindex_posts(str(tmp_path)) == 0   # idempotent
