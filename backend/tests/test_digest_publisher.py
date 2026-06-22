import datetime
import sys
from pathlib import Path
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from digest.curator import DigestData, DigestItem
from digest.publisher import render_html, render_email_html, render_index_entry


def _make_digest():
    return DigestData(
        date=datetime.date(2026, 6, 22),
        number=7,
        intro="Here is what caught my eye today in cybersecurity and AI.",
        sections={
            "Papers & Research": [
                DigestItem(
                    title="Adversarial Attacks on LLMs",
                    url="https://arxiv.org/abs/2606.12345",
                    source_name="arXiv",
                    category="papers",
                    editorial_note="This paper examines prompt injection at scale.",
                )
            ],
            "Cybersecurity": [
                DigestItem(
                    title="New Ransomware Variant",
                    url="https://bleepingcomputer.com/article",
                    source_name="Bleeping Computer",
                    category="cybersecurity",
                    editorial_note="Detailed breakdown of the attack chain.",
                )
            ],
        },
        sources_reviewed=45,
        items_selected=2,
    )


def test_render_html_contains_title():
    html = render_html(_make_digest())
    assert "Daily Digest #7" in html
    assert "June 22, 2026" in html


def test_render_html_contains_sections():
    html = render_html(_make_digest())
    assert "Papers &amp; Research" in html or "Papers & Research" in html
    assert "Cybersecurity" in html


def test_render_html_contains_items():
    html = render_html(_make_digest())
    assert "Adversarial Attacks on LLMs" in html
    assert "https://arxiv.org/abs/2606.12345" in html
    assert "prompt injection at scale" in html


def test_render_html_contains_subscribe_link():
    html = render_html(_make_digest())
    assert "subscribe" in html.lower() or "buttondown" in html.lower()


def test_render_html_no_inline_styles():
    html = render_html(_make_digest())
    assert ' style="' not in html


def test_render_index_entry_is_anchor():
    entry = render_index_entry(_make_digest())
    assert '<a ' in entry
    assert "digest/2026-06-22.html" in entry
    assert "Daily Digest #7" in entry
    assert "June 22, 2026" in entry


def test_render_email_html_has_no_nav():
    email = render_email_html(_make_digest())
    assert 'class="topbar"' not in email
    assert "Adversarial Attacks on LLMs" in email
