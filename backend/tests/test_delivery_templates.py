"""Tests for HTML escaping of user-controlled data in email templates.

manuscript_title is derived from text extracted from a customer-uploaded
PDF (see papercheck.extract_paper / app.py), so it is attacker-controlled.
html_review_ready() must escape it before interpolating into the HTML email
body sent from the trusted reviews@mail.purplelink.llc address.
"""
from latextools import delivery


def test_html_review_ready_escapes_html_metacharacters():
    malicious_title = (
        'Foo</strong><a href="http://evil.example/verify">'
        "Click to verify your account</a><strong>Bar"
    )
    out = delivery.html_review_ready(
        status_url="https://purplelink.llc/tools/paper-review/status/?token=abc",
        manuscript_title=malicious_title,
    )
    assert "<a href=\"http://evil.example/verify\">" not in out
    assert "</strong><a" not in out
    assert "&lt;/strong&gt;&lt;a href=" in out


def test_html_review_ready_escapes_quotes_and_ampersands():
    out = delivery.html_review_ready(
        status_url="https://purplelink.llc/x",
        manuscript_title='Title with "quotes" & <tags>',
    )
    assert "&quot;quotes&quot;" in out
    assert "&amp;" in out
    assert "&lt;tags&gt;" in out
    assert '"quotes"' not in out
    assert "<tags>" not in out


def test_html_review_ready_caps_title_length():
    long_title = "A" * 5000
    out = delivery.html_review_ready(
        status_url="https://purplelink.llc/x",
        manuscript_title=long_title,
    )
    assert out.count("A") <= 200


def test_html_review_ready_default_title_when_empty():
    out = delivery.html_review_ready(status_url="https://purplelink.llc/x")
    assert "(your manuscript)" in out


def test_html_review_ready_status_url_still_interpolated():
    out = delivery.html_review_ready(
        status_url="https://purplelink.llc/tools/paper-review/status/?token=abc123",
        manuscript_title="Normal Title",
    )
    assert 'href="https://purplelink.llc/tools/paper-review/status/?token=abc123"' in out
    assert "Normal Title" in out


def test_html_review_ready_refund_amount_defaults_to_standard_price():
    out = delivery.html_review_ready(status_url="https://purplelink.llc/x")
    assert "refund the $9" in out
    assert "$5" not in out


def test_html_review_ready_refund_amount_is_tier_aware():
    journal_out = delivery.html_review_ready(
        status_url="https://purplelink.llc/x", amount_cents=1100,
    )
    assert "refund the $11" in journal_out

    deep_out = delivery.html_review_ready(
        status_url="https://purplelink.llc/x", amount_cents=1500,
    )
    assert "refund the $15" in deep_out
