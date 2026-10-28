"""Link placement switchback on the daily how-to videos (experiment howto-link-placement)."""
import datetime as dt
import importlib.util
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("howto_publish", ROOT / "scripts" / "howto-publish.py")
H = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(H)

SB = {
    "id": "howto-demo-slug", "app": "legroom", "page": "https://purplelink.llc/legroom/",
    "scenes": [
        {"type": "hook", "title": "Disk full on Mac?", "sub": "Here is why."},
        {"type": "cause", "text": "Caches pile up."},
        {"type": "steps", "lines": ["$ du -sh ~/Library/Caches"]},
        {"type": "app", "name": "Legroom", "line": "Shows what takes the space."},
    ],
    "sources": ["https://example.org/a"],
}


def _desc(arm, monkeypatch):
    monkeypatch.setattr(H, "trend_tags", lambda sb, short: "#macos")
    return H.descriptions(SB, "https://youtu.be/abcdefghijk", arm)


def test_arm_by_date():
    assert H.link_arm(dt.date(2026, 10, 20)) == "A"
    assert H.link_arm(dt.date(2026, 10, 21)) == "B"
    assert H.link_arm(dt.date(2026, 10, 22)) == "A"
    assert H.link_arm(dt.date(2026, 10, 31)) == "B"
    assert H.link_arm(dt.date(2026, 11, 1)) == "B"  # day 1 is odd, so two B days in a row at month end
    assert H.link_arm(dt.date(2026, 11, 2)) == "A"
    assert H.link_arm(dt.date(2026, 10, 19)) == "A"  # before the start date, nothing changes


def test_utm():
    q = parse_qs(urlparse(H.tagged(SB["page"], "video", SB["id"])).query)
    assert q == {"utm_source": ["youtube"], "utm_medium": ["video"], "utm_campaign": ["howto-link-test"],
                 "utm_content": ["howto-demo-slug"]}


def test_arm_a_keeps_link_after_app_paragraph(monkeypatch):
    long_d, short_d = _desc("A", monkeypatch)
    link = H.tagged(SB["page"], "video", SB["id"])
    assert not long_d.startswith("Legroom:") and not long_d.splitlines()[0].startswith("http")
    assert long_d.count(link) == 1
    assert "Shows what takes the space.\n" + link in long_d


def test_arm_b_first_line_is_link_and_not_duplicated(monkeypatch):
    long_d, short_d = _desc("B", monkeypatch)
    link = H.tagged(SB["page"], "video", SB["id"])
    assert long_d.splitlines()[0] == f"Legroom: {link}"
    assert long_d.count(link) == 1
    assert "Shows what takes the space." in long_d
    assert "<" not in long_d and ">" not in long_d


def test_short_link_tagged_and_same_in_both_arms(monkeypatch):
    a = _desc("A", monkeypatch)[1]
    b = _desc("B", monkeypatch)[1]
    assert a == b
    assert "utm_content=howto-demo-slug-short" in a and "utm_medium=short" in a


def _hub_in(tmp_path, monkeypatch, ledger=None):
    """The real marketing hub, with every source redirected into tmp_path (no real queue or ledger)."""
    repo = tmp_path / "repo"
    (repo / "video" / "howto").mkdir(parents=True)
    (repo / "video" / "howto" / "ledger.json").write_text(__import__("json").dumps(ledger or []))
    for k, sub in (("PURPLELINK_REPO", "repo"), ("PURPLELINK_HUB", "hub"), ("PURPLELINK_QUEUE", "queue"),
                   ("PURPLELINK_SOCIAL_QUEUE", "social")):
        monkeypatch.setenv(k, str(tmp_path / sub))
    spec = importlib.util.spec_from_file_location("hub_t", ROOT / "scripts" / "hub" / "hub.py")
    hub = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hub)
    return hub


def test_long_short_and_reel_get_their_own_tags(tmp_path, monkeypatch):
    """Fails if the long video and its Short (or the Instagram Reel) come out with the same utm_content."""
    links = H.hub_links(SB, _hub_in(tmp_path, monkeypatch))
    tags = [links["long_tag"], links["short_tag"], links["reel_tag"]]
    assert len(set(tags)) == 3, tags
    assert tags == ["howto-demo-slug", "howto-demo-slug-short", "howto-demo-slug-reel"]   # the link test's names
    lq, sq = parse_qs(urlparse(links["long"]).query), parse_qs(urlparse(links["short"]).query)
    assert lq["utm_medium"] == ["video"] and sq["utm_medium"] == ["short"]
    assert lq["utm_campaign"] == sq["utm_campaign"] == ["howto-link-test"] and lq["utm_source"] == ["youtube"]
    monkeypatch.setattr(H, "trend_tags", lambda sb, short: "#macos")
    long_d, short_d = H.descriptions(SB, "https://youtu.be/abcdefghijk", "A", links)
    assert links["long"] in long_d and links["short"] in short_d and links["long"] not in short_d


def test_a_taken_tag_is_not_reused(tmp_path, monkeypatch):
    hub = _hub_in(tmp_path, monkeypatch, [{"slug": "howto-demo-slug", "long_id": "a" * 11, "short_id": "b" * 11,
                                           "link_utm_content": "howto-demo-slug",
                                           "short_utm_content": "howto-demo-slug-short"}])
    links = H.hub_links(SB, hub)
    assert links["long_tag"] == "howto-demo-slug-2" and links["short_tag"] == "howto-demo-slug-2-short"
