import dataclasses
import datetime
import sys
from pathlib import Path
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from digest import affiliates as aff
from digest import publisher
from digest.curator import DigestData, DigestItem


def _digest(url):
    return DigestData(
        date=datetime.date(2026, 10, 12), number=9, intro="Intro.", sources_reviewed=10, items_selected=1,
        sections={"Tools": [DigestItem(title="A tool", url=url, source_name="Src", category="tools",
                                      editorial_note="Note.")]},
    )


def _live(monkeypatch):
    base = next(p for p in aff.REGISTRY if p.id == "setapp")
    live = dataclasses.replace(base, status="approved", link="https://setapp.sjv.io/abc123")
    monkeypatch.setattr(aff, "REGISTRY", (live,))


def test_ordinary_link_is_untouched_and_has_no_disclosure():
    html = publisher.render_html(_digest("https://example.org/post"))
    assert 'href="https://example.org/post"' in html
    assert "aff-disclosure" not in html
    assert "sponsored" not in html
    assert "affiliate links" not in publisher.render_email_html(_digest("https://example.org/post"))


def test_affiliate_link_is_tracked_sponsored_and_disclosed(monkeypatch):
    _live(monkeypatch)
    d = _digest("https://setapp.com/apps/foo")
    html = publisher.render_html(d)
    assert 'href="https://setapp.sjv.io/abc123"' in html
    assert 'rel="sponsored noopener"' in html
    assert html.count('class="aff-disclosure"') == 1
    assert "affiliate links" in publisher.render_email_html(d)


def test_digest_with_affiliate_link_in_another_issue_is_unaffected(monkeypatch):
    _live(monkeypatch)
    html = publisher.render_html(_digest("https://example.org/post"))
    assert "aff-disclosure" not in html
