"""Keep every dashboard test away from the real archive in ~/.purplelink/traffic.

traffic_dashboard reads PURPLELINK_TRAFFIC_DIR once, at import. Test modules that did not set it
(test_app_funnels, test_outbound_veil) could be imported first in a combined run, and then
test_marketplaces wrote its invented orders into the real marketplaces.json (2026-10-06).
"""
import os
import tempfile

os.environ.setdefault("PURPLELINK_TRAFFIC_DIR", tempfile.mkdtemp(prefix="traffic-test-"))


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _no_real_tiktok_daily_income(monkeypatch, tmp_path):
    """TikTok's own daily figures live in TikTokPipeline/analytics; a test that does not pass its own file must see none."""
    import traffic_dashboard as td
    monkeypatch.setattr(td, "TIKTOK_DAILY_INCOME_CSV", tmp_path / "no-daily-income.csv")
