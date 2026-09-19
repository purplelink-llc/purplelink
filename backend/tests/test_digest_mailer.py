import sys
from pathlib import Path
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import asyncio
import datetime

import digest.mailer as mailer
from digest.mailer import split_by_send_group


def test_split_by_send_group_paid_and_legacy_get_same_day():
    subscribers = [
        {"email": "a@x.com", "tier": "paid"},
        {"email": "b@x.com", "tier": "legacy"},
        {"email": "c@x.com", "tier": "free", "last_sent_slug": None},
    ]
    same_day, delayed = split_by_send_group(subscribers, delayed_slug="2026-09-17")
    assert {s["email"] for s in same_day} == {"a@x.com", "b@x.com"}
    assert {s["email"] for s in delayed} == {"c@x.com"}


def test_split_by_send_group_skips_free_subscriber_already_caught_up():
    subscribers = [
        {"email": "c@x.com", "tier": "free", "last_sent_slug": "2026-09-17"},
    ]
    same_day, delayed = split_by_send_group(subscribers, delayed_slug="2026-09-17")
    assert same_day == []
    assert delayed == []


def test_split_by_send_group_treats_missing_tier_as_legacy():
    # A record that predates this feature and hasn't been touched by the
    # subscribe.mjs backfill (that backfill only fires on re-submission).
    # Must not be silently dropped from every send.
    subscribers = [{"email": "old@x.com"}]
    same_day, delayed = split_by_send_group(subscribers, delayed_slug="2026-09-17")
    assert {s["email"] for s in same_day} == {"old@x.com"}


class _FakeDigest:
    def __init__(self, number, date):
        self.number = number
        self.date = date


def test_mail_digest_does_not_mark_sent_when_delayed_send_fails(monkeypatch):
    """Regression test for the bug fixed alongside this test: a failed
    _send_one used to be followed unconditionally by _mark_sent, which
    would permanently drop a free-tier subscriber from ever receiving
    that issue (split_by_send_group's idempotency check would treat them
    as already caught up on the next cron run).
    """
    subscribers = [
        {"email": "ok@x.com", "tier": "free", "last_sent_slug": None},
        {"email": "fails@x.com", "tier": "free", "last_sent_slug": None},
    ]

    async def fake_get_subscribers(client, secret):
        return subscribers

    send_calls = []

    async def fake_send_one(client, email, subject, html, resend_key):
        send_calls.append(email)
        # Simulate a transient Resend failure (5xx / network blip) for one
        # subscriber only -- exactly the failure mode _send_one's own
        # try/except is meant to convert into a bool rather than swallow.
        return email != "fails@x.com"

    mark_sent_calls = []

    async def fake_mark_sent(client, email, slug, secret):
        mark_sent_calls.append((email, slug))

    monkeypatch.setattr(mailer, "_get_subscribers", fake_get_subscribers)
    monkeypatch.setattr(mailer, "_send_one", fake_send_one)
    monkeypatch.setattr(mailer, "_mark_sent", fake_mark_sent)

    def render_email_html(digest, unsubscribe_url, tier):
        return "<html></html>"

    digest = _FakeDigest(number=1, date=datetime.date(2026, 9, 17))
    delayed_digest = _FakeDigest(number=1, date=datetime.date(2026, 9, 16))

    sent = asyncio.run(
        mailer.mail_digest(
            digest,
            render_email_html,
            subscribe_secret="secret",
            resend_key="key",
            delayed_digest=delayed_digest,
            delayed_slug="2026-09-17",
        )
    )

    # Both subscribers were attempted...
    assert send_calls == ["ok@x.com", "fails@x.com"]
    # ...but only the one whose send actually succeeded got marked sent,
    # and only successful sends count toward the returned total.
    assert mark_sent_calls == [("ok@x.com", "2026-09-17")]
    assert sent == 1


def test_mail_digest_same_day_sent_count_reflects_confirmed_sends_only(monkeypatch):
    subscribers = [
        {"email": "paid-ok@x.com", "tier": "paid"},
        {"email": "paid-fails@x.com", "tier": "paid"},
    ]

    async def fake_get_subscribers(client, secret):
        return subscribers

    async def fake_send_one(client, email, subject, html, resend_key):
        return email != "paid-fails@x.com"

    async def fake_mark_sent(client, email, slug, secret):
        raise AssertionError("_mark_sent should not be called for the same-day group")

    monkeypatch.setattr(mailer, "_get_subscribers", fake_get_subscribers)
    monkeypatch.setattr(mailer, "_send_one", fake_send_one)
    monkeypatch.setattr(mailer, "_mark_sent", fake_mark_sent)

    def render_email_html(digest, unsubscribe_url, tier, manage_url=""):
        return "<html></html>"

    digest = _FakeDigest(number=1, date=datetime.date(2026, 9, 17))

    sent = asyncio.run(
        mailer.mail_digest(
            digest,
            render_email_html,
            subscribe_secret="secret",
            resend_key="key",
        )
    )

    assert sent == 1
