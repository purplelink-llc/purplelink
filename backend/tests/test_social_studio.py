"""Weekly studio note: the gate rejects what the house voice and Ben's voice forbid, the items it writes are drafts that
only Ben can approve, and the approval-queue copy is marked needs_ben."""
import pytest

from social_helpers import env  # noqa: F401
from socialpost import items, studio

LINK = "https://purplelink.llc/research/citation-gaps-in-new-arxiv-papers/"
GOOD = f"""---
slug: citation-count
asset: citation-gap
link: {LINK}
cta: none
---

## linkedin
From the studio: we counted something, then counted it again. The first count said 95 of 99 papers. After removing works already cited it was 86. Details: {{link}}

## bluesky
We first counted 95 of 99 papers. After removing works already cited, 86. {{link}}

## mastodon
Our checker flagged a missing citation in 95 of 99 papers. Some were already cited. With those removed, 86 still had a gap. Method and data: {{link}}
"""


def test_good_note_has_no_problems():
    meta, sec = studio.parse_note(GOOD)
    assert studio.problems(meta, sec) == []


@pytest.mark.parametrize("bad,needle", [
    ("We did it — and it worked.", "em dash"),
    ("Buy now at the link.", "hard call to action"),
    ("Ben wrote this one.", "unnamed"),
])
def test_linkedin_rejects(bad, needle):
    meta, sec = studio.parse_note(GOOD)
    sec["linkedin"] = bad
    assert any(needle in p for p in studio.problems(meta, sec))


def test_mastodon_uses_bens_rules():
    meta, sec = studio.parse_note(GOOD)
    sec["mastodon"] = "Furthermore, it works; is that notable?"
    probs = studio.problems(meta, sec)
    assert any("Ben's voice" in p for p in probs)


def test_hard_cta_only_when_front_matter_allows():
    meta, sec = studio.parse_note(GOOD)
    sec["linkedin"] = "Start your free trial today."
    assert studio.problems(meta, sec)
    meta["cta"] = "hard"
    assert not any("hard call" in p for p in studio.problems(meta, sec))


def test_missing_platform_and_off_site_link():
    meta, sec = studio.parse_note(GOOD)
    del sec["bluesky"]
    meta["link"] = "https://example.com/x"
    probs = studio.problems(meta, sec)
    assert any("missing a ## bluesky" in p for p in probs)
    assert any("purplelink.llc" in p for p in probs)


def test_make_items_writes_an_unapproved_draft_with_tags(env):
    meta, sec = studio.parse_note(GOOD)
    it = studio.make_items(meta, sec)
    saved = items.find(it.id)
    assert saved.status == "draft" and saved.meta["approved_by"] is None
    assert saved.meta["needs_ben"] is True
    assert set(saved.meta["utm_contents"]) == {"linkedin", "bluesky", "mastodon"}
    assert saved.approval_valid()[0] is False          # nothing posts until Ben runs `social.py approve`
    assert "utm_campaign=studio-note" in saved.render("bluesky")


def test_queue_markdown_is_needs_ben_and_keeps_the_tag_off_the_draft(env):
    meta, sec = studio.parse_note(GOOD)
    it = studio.make_items(meta, sec)
    md = studio.queue_markdown(it, meta, ["a reason"])
    assert "needs_ben: true" in md and "executor: ben" in md and "kind: post" in md
    assert "utm_content" not in md and "{link}" in md   # one tag lives in one place only
    assert "approve" in md and "--by-ben" in md


def test_standing_approval_covers_only_studio_notes_on_three_platforms(env):
    meta, sec = studio.parse_note(GOOD)
    it = studio.make_items(meta, sec, auto=True)
    assert "needs_ben" not in it.meta and it.meta["source"] == "studio-note"
    studio.auto_approve(it, {**meta, "link": ""}, http=None)   # no link check without a link
    saved = items.find(it.id)
    assert saved.status == "approved" and saved.meta["approved_by"] == items.STUDIO_STANDING_BY
    assert saved.approval_valid()[0] is True
    # editing after approval voids it
    saved.sections["bluesky"] += " edited"
    assert saved.approval_valid()[0] is False


def test_standing_approval_refuses_other_platforms_and_sources(env):
    meta, sec = studio.parse_note(GOOD)
    it = studio.make_items(meta, sec, auto=True)
    it.meta["platforms"] = ["linkedin", "threads"]
    with pytest.raises(ValueError):
        items.approve_studio_standing(it, {})
    it.meta["platforms"] = ["linkedin", "bluesky", "mastodon"]
    it.meta["source"] = "social-daily"
    with pytest.raises(ValueError):
        items.approve_studio_standing(it, {})


def test_auto_approve_needs_a_live_link(env):
    from social_helpers import FakeHttp
    from socialpost.http import Resp
    meta, sec = studio.parse_note(GOOD)
    it = studio.make_items(meta, sec, auto=True)
    with pytest.raises(studio.NoteError):
        studio.auto_approve(it, meta, http=FakeHttp([("GET", "citation-gaps", Resp(404, b""))]))
    assert items.find(it.id).status == "draft"
    studio.auto_approve(it, meta, http=FakeHttp([("GET", "citation-gaps", Resp(200, b"ok"))]))
    assert items.find(it.id).status == "approved"
