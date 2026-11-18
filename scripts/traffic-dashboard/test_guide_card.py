"""guide_card_block: the exact guide app-card click counts stored next to adFunnel in history.json."""
import sys
import os, tempfile
os.environ.setdefault("PURPLELINK_TRAFFIC_DIR", tempfile.mkdtemp(prefix="traffic-test-"))   # never touch the real archive
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import traffic_dashboard as td


def test_block_carries_both_fields_with_window_and_date():
    week = {"guideCardClicksByPath": {"/moderntex/": 3}, "guidePageviewsByPath": {"/guides/a/": 120, "/guides/b/": 80},
            "funnelByChannel": {}}
    assert td.guide_card_block(week, 7, "2026-11-18") == {
        "asOf": "2026-11-18", "days": 7,
        "clicksByPath": {"/moderntex/": 3}, "guideViewsByPath": {"/guides/a/": 120, "/guides/b/": 80}}


def test_zero_clicks_is_a_real_block():
    b = td.guide_card_block({"guideCardClicksByPath": {}, "guidePageviewsByPath": {"/guides/a/": 5}}, 7, "2026-11-18")
    assert b is not None and b["clicksByPath"] == {}


def test_absent_or_malformed_fields_give_none():
    assert td.guide_card_block({}, 7, "2026-11-18") is None
    assert td.guide_card_block({"guideCardClicksByPath": {"/x/": 1}}, 7, "2026-11-18") is None
    assert td.guide_card_block({"guideCardClicksByPath": [], "guidePageviewsByPath": {}}, 7, "2026-11-18") is None
