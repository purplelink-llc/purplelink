import sys
from pathlib import Path
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import asyncio
import datetime

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
