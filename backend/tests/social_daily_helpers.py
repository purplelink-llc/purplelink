"""Fakes for the daily pipeline tests: a scripted HTTP that fails on any unscripted URL (no network, ever), a site
fixture, and an environment with every private path redirected into tmp_path."""
from __future__ import annotations

import json
import re

import pytest

from social_helpers import PNG, env  # noqa: F401
from socialpost import config as cfgmod
from socialpost.daily import lib219

Response = lib219.Response

SITEMAP = """<urlset>
<url><loc>https://purplelink.llc/guides/new-guide/</loc><lastmod>2026-10-17</lastmod></url>
<url><loc>https://purplelink.llc/guides/old-guide/</loc><lastmod>2026-10-17</lastmod></url>
<url><loc>https://purplelink.llc/tools/word-counter/</loc><lastmod>2026-10-17</lastmod></url>
<url><loc>https://purplelink.llc/blog/digest/</loc><lastmod>2026-10-17</lastmod></url>
</urlset>"""


def page(title, desc, image="https://purplelink.llc/assets/og/cards/x.png", alt=""):
    alt_tag = f'<meta property="og:image:alt" content="{alt}">' if alt else ""
    return (f'<html><head><meta property="og:title" content="{title} | Purplelink LLC">'
            f'<meta name="description" content="{desc}"><meta property="og:image" content="{image}">{alt_tag}'
            f'</head><body><h1>{title}</h1></body></html>')


def product(app, name, version):
    ld = json.dumps({"@type": "SoftwareApplication", "name": name, "softwareVersion": version,
                     "offers": {"@type": "Offer", "price": "9.99"}})
    return f'<script type="application/ld+json">{ld}</script><meta property="og:image" content="https://purplelink.llc/assets/og/{app}.png">'


CHANGELOG = """<div class="changelog-entry">
        <span class="changelog-date">October 19, 2026</span>
        <div class="changelog-content">
          <h2>Panely 1.1.0</h2>
          <p>The list of open windows can show a picture of each one, so two windows of one app are easy to tell apart. Snapped windows now resize together.</p>
        </div>
      </div>
<div class="changelog-entry">
        <span class="changelog-date">September 2, 2026</span>
        <div class="changelog-content">
          <h2>Legroom 1.0.0</h2>
          <p>The first release of Legroom, which lists what is using the space on a startup disk in plain words.</p>
        </div>
      </div>
</main>"""


class FakeHttp:
    """routes: [(method, regex, reply)]. reply is a Response, a dict (JSON 200), bytes (200) or callable(call)."""

    def __init__(self):
        self.routes, self.calls = [], []

    def on(self, method, pattern, reply):
        self.routes.insert(0, (method, re.compile(pattern), reply))
        return self

    def request(self, method, url, headers=None, follow=True, **kw):
        call = {"method": method, "url": url, "headers": headers or {}}
        self.calls.append(call)
        for m, pat, reply in self.routes:
            if m == method and pat.search(url):
                if callable(reply):
                    reply = reply(call)
                if isinstance(reply, dict):
                    return Response(200, json.dumps(reply).encode(), url=url)
                if isinstance(reply, (bytes, str)):
                    return Response(200, reply.encode() if isinstance(reply, str) else reply, url=url)
                return reply
        raise AssertionError(f"unexpected request {method} {url}: tests never touch the network")

    def posted(self):
        return [c for c in self.calls if c["method"] not in ("GET", "HEAD")]


def site(h: FakeHttp | None = None, panely="1.1.0") -> FakeHttp:
    """A live site with one fresh release (Panely), one new guide, an old guide and a tool."""
    h = h or FakeHttp()
    h.on("GET", r"/sitemap\.xml$", SITEMAP)
    h.on("GET", r"/changelog/$", CHANGELOG)
    from socialpost.daily.lib219 import events
    for app, path in events.PRODUCTS.items():
        name = app.replace("-", " ").title()
        v = panely if app == "panely" else "1.0.0"
        h.on("GET", rf"^https://purplelink\.llc{re.escape(path)}$", product(app, name, v))
    h.on("GET", r"/guides/new-guide/$", page("Check a manuscript before you submit it",
         "A step by step walkthrough of checking a manuscript for leaks before submission. It takes about ten minutes."))
    h.on("GET", r"/guides/old-guide/$", page("An older guide", "A plain guide that has been live for a long while now."))
    h.on("GET", r"/tools/word-counter/$", page("Word counter", "Counts the words in a manuscript without leaving the page."))
    h.on("GET", r"/assets/og/", PNG + b"\x01" * 200)
    h.on("GET", r"/social-media/0{40}\.png$", Response(404, b"Not found", {"Content-Type": "text/plain; charset=utf-8"}))
    return h


@pytest.fixture
def denv(env, tmp_path, monkeypatch):
    """The social env plus the daily pipeline's private paths, all inside tmp_path. Config enables all four platforms
    with the real expected identities so the pipeline's platform filter works."""
    monkeypatch.setenv("PL_SOCIAL_DAILY_CONFIG", str(tmp_path / "social-daily.json"))
    monkeypatch.setenv("PL_SOCIAL_METRICS", str(tmp_path / "metrics.json"))
    tenv = tmp_path / "traffic.env"
    tenv.write_text("PURPLELINK_STATS_TOKEN=test-token-123\n")
    monkeypatch.setenv("PL_TRAFFIC_ENV", str(tenv))
    briefs = tmp_path / "briefs"
    briefs.mkdir()
    monkeypatch.setenv("PL_GROWTH_BRIEFS", str(briefs))
    cfg = cfgmod.load()
    for p in ("linkedin", "bluesky", "threads", "mastodon"):
        cfg["platforms"][p]["enabled"] = True
    cfg["platforms"]["mastodon"]["instance"] = "https://mastodon.example"
    cfg["platforms"]["mastodon"]["expected"] = {"acct": "purplelink_llc@mastodon.example"}
    env.cfg = cfg
    env.briefs = briefs
    return env
