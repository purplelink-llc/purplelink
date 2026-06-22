# backend/digest/sources.py
"""Source registry for the daily digest pipeline.

Each SourceDef describes one upstream content source. The `type` field
determines which fetcher in harvester.py handles it. `params` carries
per-source overrides (e.g. api_key_env for sources that need auth).
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from enum import Enum


class SourceType(Enum):
    RSS = "rss"                 # feedparser (RSS + Atom)
    HN_ALGOLIA = "hn_algolia"   # HN Algolia search API
    ARXIV_OAI = "arxiv_oai"     # arXiv OAI-PMH protocol
    SEMANTIC_SCHOLAR = "s2"     # Semantic Scholar bulk search API
    OPENALEX = "openalex"       # OpenAlex works API
    HF_PAPERS = "hf_papers"     # HuggingFace daily papers API


@dataclass
class SourceDef:
    name: str
    type: SourceType
    url: str
    category: str  # papers / ai_tech / cybersecurity / finance / entrepreneurship / general_tech
    params: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


SOURCES: list[SourceDef] = [
    # ── Papers & Research ────────────────────────────────────────────────
    SourceDef(
        name="arXiv",
        type=SourceType.ARXIV_OAI,
        url="https://oaipmh.arxiv.org/oai",
        category="papers",
        params={"sets": ["cs:AI", "cs:LG", "cs:CR", "stat:ML", "q-fin"]},
    ),
    SourceDef(
        name="Semantic Scholar",
        type=SourceType.SEMANTIC_SCHOLAR,
        url="https://api.semanticscholar.org/graph/v1/paper/search/bulk",
        category="papers",
        params={
            "queries": ["cybersecurity LLM", "adversarial machine learning",
                        "information systems AI", "large language models"],
            "api_key_env": "SEMANTIC_SCHOLAR_API_KEY",
        },
    ),
    SourceDef(
        name="OpenAlex",
        type=SourceType.OPENALEX,
        url="https://api.openalex.org/works",
        category="papers",
        params={"topics": ["cybersecurity", "artificial intelligence", "information systems"]},
    ),
    SourceDef(
        name="HuggingFace Daily Papers",
        type=SourceType.HF_PAPERS,
        url="https://huggingface.co/api/daily_papers",
        category="papers",
    ),
    # ── AI & Technology ──────────────────────────────────────────────────
    SourceDef(
        name="HuggingFace Blog",
        type=SourceType.RSS,
        url="https://huggingface.co/blog/feed.xml",
        category="ai_tech",
    ),
    SourceDef(
        name="OpenAI",
        type=SourceType.RSS,
        url="https://openai.com/news/rss.xml",
        category="ai_tech",
    ),
    SourceDef(
        name="Google DeepMind",
        type=SourceType.RSS,
        url="https://deepmind.google/blog/rss.xml",
        category="ai_tech",
    ),
    SourceDef(
        name="Anthropic",
        type=SourceType.RSS,
        url="https://raw.githubusercontent.com/taobojlen/anthropic-rss-feed/main/anthropic_news_rss.xml",
        category="ai_tech",
    ),
    SourceDef(
        name="Mistral AI",
        type=SourceType.RSS,
        url="https://mistral.ai/rss.xml",
        category="ai_tech",
    ),
    SourceDef(
        name="Cohere",
        type=SourceType.RSS,
        url="https://raw.githubusercontent.com/alan-turing-institute/ai-rss-feeds/main/feeds/cohere-blog.xml",
        category="ai_tech",
    ),
    SourceDef(
        name="TLDR AI",
        type=SourceType.RSS,
        url="https://tldr.tech/api/rss/ai",
        category="ai_tech",
    ),
    SourceDef(
        name="Import AI",
        type=SourceType.RSS,
        url="https://importai.substack.com/feed",
        category="ai_tech",
        params={"user_agent": "Mozilla/5.0 (compatible; RSS reader)"},
    ),
    SourceDef(
        name="The Gradient",
        type=SourceType.RSS,
        url="https://thegradient.pub/feed/",
        category="ai_tech",
    ),
    SourceDef(
        name="Hacker News",
        type=SourceType.HN_ALGOLIA,
        url="https://hn.algolia.com/api/v1/search_by_date",
        category="ai_tech",
        params={"min_points": 100},
    ),
    # ── Cybersecurity ────────────────────────────────────────────────────
    SourceDef(
        name="Krebs on Security",
        type=SourceType.RSS,
        url="https://krebsonsecurity.com/feed/",
        category="cybersecurity",
    ),
    SourceDef(
        name="Schneier on Security",
        type=SourceType.RSS,
        url="https://www.schneier.com/blog/atom.xml",
        category="cybersecurity",
    ),
    SourceDef(
        name="Bleeping Computer",
        type=SourceType.RSS,
        url="https://www.bleepingcomputer.com/feed/",
        category="cybersecurity",
    ),
    SourceDef(
        name="SANS ISC",
        type=SourceType.RSS,
        url="https://isc.sans.edu/rssfeed_full.xml",
        category="cybersecurity",
    ),
    SourceDef(
        name="The Hacker News",
        type=SourceType.RSS,
        url="https://thehackernews.com/feeds/posts/default",
        category="cybersecurity",
    ),
    SourceDef(
        name="Dark Reading",
        type=SourceType.RSS,
        url="https://www.darkreading.com/rss.xml",
        category="cybersecurity",
    ),
    SourceDef(
        name="GreyNoise Blog",
        type=SourceType.RSS,
        url="https://www.greynoise.io/blog/rss.xml",
        category="cybersecurity",
    ),
    SourceDef(
        name="Google Project Zero",
        type=SourceType.RSS,
        url="https://googleprojectzero.blogspot.com/feeds/posts/default",
        category="cybersecurity",
    ),
    SourceDef(
        name="Trail of Bits",
        type=SourceType.RSS,
        url="https://blog.trailofbits.com/feed/",
        category="cybersecurity",
    ),
    SourceDef(
        name="PortSwigger Research",
        type=SourceType.RSS,
        url="https://portswigger.net/research/rss",
        category="cybersecurity",
    ),
    SourceDef(
        name="CVE.org",
        type=SourceType.RSS,
        url="https://www.cve.org/new-cves.rss",
        category="cybersecurity",
    ),
    # ── Finance & Business ───────────────────────────────────────────────
    SourceDef(
        name="Bloomberg Technology",
        type=SourceType.RSS,
        url="https://feeds.bloomberg.com/technology/news.rss",
        category="finance",
    ),
    SourceDef(
        name="MarketWatch",
        type=SourceType.RSS,
        url="https://feeds.marketwatch.com/marketwatch/topstories/",
        category="finance",
    ),
    SourceDef(
        name="Yahoo Finance",
        type=SourceType.RSS,
        url="https://finance.yahoo.com/news/rssindex",
        category="finance",
    ),
    SourceDef(
        name="CoinDesk",
        type=SourceType.RSS,
        url="https://www.coindesk.com/arc/outboundfeeds/rss/",
        category="finance",
    ),
    # ── Entrepreneurship & Startups ──────────────────────────────────────
    SourceDef(
        name="First Round Review",
        type=SourceType.RSS,
        url="https://review.firstround.com/feed",
        category="entrepreneurship",
    ),
    SourceDef(
        name="Paul Graham",
        type=SourceType.RSS,
        url="https://www.paulgraham.com/rss.html",
        category="entrepreneurship",
    ),
    SourceDef(
        name="Y Combinator Blog",
        type=SourceType.RSS,
        url="https://www.ycombinator.com/blog/rss.xml",
        category="entrepreneurship",
    ),
    SourceDef(
        name="Indie Hackers",
        type=SourceType.RSS,
        url="https://www.indiehackers.com/feed.xml",
        category="entrepreneurship",
    ),
    SourceDef(
        name="SaaStr",
        type=SourceType.RSS,
        url="https://www.saastr.com/feed/",
        category="entrepreneurship",
    ),
    # ── General Tech ─────────────────────────────────────────────────────
    SourceDef(
        name="Ars Technica",
        type=SourceType.RSS,
        url="https://feeds.arstechnica.com/arstechnica/index",
        category="general_tech",
    ),
    SourceDef(
        name="MIT Technology Review",
        type=SourceType.RSS,
        url="https://www.technologyreview.com/feed/",
        category="general_tech",
    ),
    SourceDef(
        name="IEEE Spectrum",
        type=SourceType.RSS,
        url="https://spectrum.ieee.org/feeds/feed.rss",
        category="general_tech",
    ),
    SourceDef(
        name="Wired",
        type=SourceType.RSS,
        url="https://www.wired.com/feed/category/security/latest/rss",
        category="general_tech",
    ),
]
