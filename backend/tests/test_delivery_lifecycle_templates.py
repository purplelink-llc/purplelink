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
