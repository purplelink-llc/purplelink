"""Tests for the lifecycle-email templates (tips / review-request / winback).

manuscript_title is attacker-controlled (same provenance as html_review_ready's
title — see test_delivery_templates.py), so these templates must escape it too.
Also verifies the unsubscribe link is present and unescaped so it stays clickable.
"""
from latextools import delivery


UNSUB_URL = "https://purplelink.llc/paper-review/lifecycle/unsubscribe?email=a%40b.com&token=abc123"


def test_html_lifecycle_tips_escapes_title():
    out = delivery.html_lifecycle_tips(
        manuscript_title='Foo</strong><a href="http://evil.example">x</a>Bar',
        unsubscribe_url=UNSUB_URL,
    )
    assert "</strong><a" not in out
    assert "&lt;/strong&gt;&lt;a href=" in out


def test_html_lifecycle_tips_default_title_when_empty():
    out = delivery.html_lifecycle_tips(unsubscribe_url=UNSUB_URL)
    assert "your manuscript" in out


def test_html_lifecycle_tips_includes_unsubscribe_link():
    out = delivery.html_lifecycle_tips(unsubscribe_url=UNSUB_URL)
    assert f'href="{UNSUB_URL}"' in out


def test_html_lifecycle_review_request_escapes_title():
    out = delivery.html_lifecycle_review_request(
        manuscript_title='<script>alert(1)</script>',
        unsubscribe_url=UNSUB_URL,
    )
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_html_lifecycle_review_request_includes_unsubscribe_link():
    out = delivery.html_lifecycle_review_request(unsubscribe_url=UNSUB_URL)
    assert f'href="{UNSUB_URL}"' in out


def test_html_lifecycle_winback_includes_unsubscribe_link():
    out = delivery.html_lifecycle_winback(unsubscribe_url=UNSUB_URL)
    assert f'href="{UNSUB_URL}"' in out
    assert "Still writing?" in out


def test_trial_day4_and_day6_copy():
    from latextools import delivery

    day4 = delivery.html_lifecycle_trial_features(unsubscribe_url="https://x/u")
    assert "The bar above the editor counts the days." in " ".join(day4.split())
    day6 = " ".join(delivery.html_lifecycle_trial_ending(unsubscribe_url="https://x/u").split())
    assert "In ModernTex choose Enter license key, paste it" in day6
    assert "the trial ends about now. The bar above the editor shows the exact days left." in day6
    assert "Have a license" not in day6
    assert "https://x/u" in day4 and "https://x/u" in day6
