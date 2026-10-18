"""Queue file format, text limits, images and alt text, link and UTM building, approval."""
import datetime as dt

import pytest

from social_helpers import env, make_png  # noqa: F401
from socialpost import config as cfgmod
from socialpost import fmt, items
from socialpost.text import graphemes, link_errors, measure, utm_link


def mk(env, **over):
    it = items.create("t", ["bluesky", "linkedin"], "https://purplelink.llc/vitae/", "vitae-140")
    it.sections["default"] = "Hello from Purplelink. {link}"
    it.meta.update(over)
    it.save()
    return it


def test_front_matter_round_trip_and_sections():
    meta = {"id": "a-b-c", "platforms": ["x"], "images": [{"path": "p.png", "alt": 'say "hi"'}], "n": None}
    text = fmt.dump(meta, {"default": "line one\nline two", "x": "short"}, "notes here")
    m2, sections, pre = fmt.parse(text)
    assert m2 == meta
    assert sections == {"default": "line one\nline two", "x": "short"}
    assert pre == "notes here"


def test_front_matter_rejects_garbage():
    with pytest.raises(ValueError):
        fmt.parse("no fence here")
    with pytest.raises(ValueError):
        fmt.parse("---\nkey value\n---\n")


def test_utm_link_adds_the_three_tags_and_keeps_other_params():
    u = utm_link("https://purplelink.llc/vitae/?ref=a#top", "threads", "vitae-140")
    assert u == "https://purplelink.llc/vitae/?ref=a&utm_source=threads&utm_medium=social&utm_campaign=vitae-140#top"
    assert "utm_source=x&utm_medium=social&utm_campaign=c" in utm_link("https://purplelink.llc/", "x", "c")


def test_utm_replaces_existing_utm_instead_of_doubling():
    u = utm_link("https://purplelink.llc/?utm_source=old", "bluesky", "c")
    assert u.count("utm_source") == 1 and "utm_source=bluesky" in u


def test_link_errors():
    ok = ["purplelink.llc"]
    assert link_errors("https://purplelink.llc/a/", "vitae-140", ok) == []
    assert link_errors("http://purplelink.llc/a/", "vitae-140", ok)
    assert link_errors("https://evil.example/a/", "vitae-140", ok)
    assert link_errors("https://purplelink.llc/a/?utm_source=x", "vitae-140", ok)
    assert link_errors("https://purplelink.llc/a/", "Bad Campaign!", ok)


def test_render_puts_the_platform_utm_in_each_text(env):
    it = mk(env)
    assert "utm_source=bluesky" in it.render("bluesky") and "utm_source=linkedin" in it.render("linkedin")
    it.sections["default"] = "no placeholder"
    assert it.render("bluesky").endswith("utm_campaign=vitae-140")
    it.sections["bluesky"] = "only bluesky {link}"
    assert it.render("bluesky").startswith("only bluesky") and it.render("linkedin").startswith("no placeholder")


def test_grapheme_counting():
    assert graphemes("abc") == 3
    assert graphemes("é") == 1            # combining accent
    assert graphemes("\U0001F468‍\U0001F469‍\U0001F467") == 1  # ZWJ family
    assert graphemes("\U0001F1FA\U0001F1F8") == 1  # flag


def test_x_and_mastodon_count_links_as_23():
    t = "hi https://purplelink.llc/vitae/?utm_source=x&utm_medium=social&utm_campaign=vitae-140"
    assert measure(t, "x") == 3 + 23 and measure(t, "mastodon") == 3 + 23
    assert measure(t, "chars") == len(t)


def test_validate_clean_item(env):
    cfg = cfgmod.load()
    errors, warnings = items.validate(mk(env), cfg)
    assert errors == []


@pytest.mark.parametrize("platform,limit", [("bluesky", 300), ("threads", 500), ("mastodon", 500), ("x", 280), ("linkedin", 3000)])
def test_validate_text_limits(env, platform, limit):
    cfg = cfgmod.load()
    it = mk(env, platforms=[platform])
    it.sections["default"] = "a" * (limit + 1)
    it.meta["link"] = ""
    errors, _ = items.validate(it, cfg)
    assert any("limit" in e and platform in e for e in errors), errors
    it.sections["default"] = "a" * limit
    errors, _ = items.validate(it, cfg)
    assert not any("limit" in e for e in errors), errors


def test_validate_bluesky_limit_counts_the_utm_link(env):
    cfg = cfgmod.load()
    it = mk(env, platforms=["bluesky"])
    it.sections["default"] = "a" * 250 + " {link}"
    errors, _ = items.validate(it, cfg)
    assert any("bluesky" in e and "limit 300" in e for e in errors)


def test_validate_images_alt_count_size_format(env):
    cfg = cfgmod.load()
    base = env.tmp
    good = make_png(base / "a.png")
    it = mk(env, platforms=["bluesky"], images=[{"path": str(good), "alt": "a card"}])
    assert items.validate(it, cfg)[0] == []
    it.meta["images"] = [{"path": str(good), "alt": ""}]
    assert any("no alt text" in e for e in items.validate(it, cfg)[0])
    it.meta["images"] = [{"path": str(good), "alt": "x" * 2001}]
    assert any("alt text is 2001" in e for e in items.validate(it, cfg)[0])
    it.meta["images"] = [{"path": str(good), "alt": "ok"}] * 5
    assert any("5 images, limit 4" in e for e in items.validate(it, cfg)[0])
    it.meta["images"] = [{"path": str(base / "missing.png"), "alt": "ok"}]
    assert any("does not exist" in e for e in items.validate(it, cfg)[0])
    fake = base / "fake.png"
    fake.write_bytes(b"not a png at all")
    it.meta["images"] = [{"path": str(fake), "alt": "ok"}]
    assert any("not really a .png" in e for e in items.validate(it, cfg)[0])
    gif = base / "a.gif"
    gif.write_bytes(b"GIF89a" + b"\0" * 10)
    it.meta.update(platforms=["threads"], images=[{"path": str(gif), "alt": "ok"}])
    assert any("takes .png, .jpg, .jpeg" in e for e in items.validate(it, cfg)[0])
    big = base / "big.png"
    big.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * (9 * 1024 * 1024))
    it.meta.update(platforms=["threads"], images=[{"path": str(big), "alt": "ok"}])
    assert any("limit 8192 KB" in e for e in items.validate(it, cfg)[0])


def test_threads_allows_a_carousel_up_to_20(env):
    cfg = cfgmod.load()
    p = make_png(env.tmp / "a.png")
    it = mk(env, platforms=["threads"], images=[{"path": str(p), "alt": "a"}] * 20)
    assert items.validate(it, cfg)[0] == []
    it.meta["images"] = [{"path": str(p), "alt": "a"}] * 21
    assert any("limit 20" in e for e in items.validate(it, cfg)[0])


def test_linkedin_images_need_text_only_or_a_document(env):
    cfg = cfgmod.load()
    p = make_png(env.tmp / "a.png")
    it = mk(env, platforms=["linkedin"], images=[{"path": str(p), "alt": "a"}])
    assert any("cannot attach images" in e for e in items.validate(it, cfg)[0])
    it.meta["text_only"] = ["linkedin"]
    assert items.validate(it, cfg)[0] == []


def test_per_image_platform_filter(env):
    p = make_png(env.tmp / "a.png")
    q = make_png(env.tmp / "b.png", 3)
    it = mk(env, platforms=["bluesky", "x"], images=[{"path": str(p), "alt": "a", "platforms": ["x"]}, {"path": str(q), "alt": "b"}])
    assert [i["alt"] for i in it.images_for("bluesky")] == ["b"]
    assert [i["alt"] for i in it.images_for("x")] == ["a", "b"]


def test_validate_flags_unknown_platform_missing_schedule_and_text(env):
    cfg = cfgmod.load()
    it = mk(env, platforms=["myspace"])
    assert any("unknown platform" in e for e in items.validate(it, cfg)[0])
    it = mk(env)
    del it.meta["scheduled_at"]
    assert any("scheduled_at" in e for e in items.validate(it, cfg)[0])
    it = mk(env, scheduled_at="2026-10-27T08:30:00")
    assert any("no timezone" in e for e in items.validate(it, cfg)[0])
    it = mk(env)
    it.sections.clear()
    assert any("no text" in e for e in items.validate(it, cfg)[0])


def test_disabled_platform_is_a_warning_not_an_error(env):
    cfg = cfgmod.load()
    it = mk(env, platforms=["bluesky", "threads"])
    errors, warnings = items.validate(it, cfg)
    assert errors == [] and any("threads: disabled" in w for w in warnings)


def test_approve_sets_fields_and_edit_voids_it(env):
    cfg = cfgmod.load()
    it = mk(env, scheduled_at=items.iso(items.now() + dt.timedelta(hours=2)))
    items.approve(it, cfg)
    again = items.Item.load(it.path)
    assert again.status == "approved" and again.meta["approved_by"] == "ben" and again.meta["approved_at"]
    assert again.approval_valid() == (True, "")
    again.sections["default"] = "Changed after approval. {link}"
    ok, why = again.approval_valid()
    assert not ok and "changed after approval" in why


def test_approve_refuses_invalid_and_stale_items(env):
    cfg = cfgmod.load()
    it = mk(env, scheduled_at=items.iso(items.now() + dt.timedelta(hours=2)))
    it.sections["default"] = "a" * 400 + " {link}"
    it.save()
    with pytest.raises(ValueError, match="fix these first"):
        items.approve(it, cfg)
    it = mk(env, scheduled_at=items.iso(items.now() - dt.timedelta(hours=49)))
    with pytest.raises(ValueError, match="more than 48 hours"):
        items.approve(it, cfg)


def test_a_draft_with_forged_approval_fields_is_not_approved(env):
    it = mk(env, status="approved", approved_by="ben", approved_at="2026-10-18T00:00:00+00:00")
    ok, why = it.approval_valid()
    assert not ok  # no approved_hash: only the approve command can produce a valid approval


def test_wrong_approver_is_not_valid(env):
    cfg = cfgmod.load()
    it = mk(env, scheduled_at=items.iso(items.now() + dt.timedelta(hours=2)))
    items.approve(it, cfg)
    it.meta["approved_by"] = "claude"
    assert not it.approval_valid()[0]


def test_cancel_and_find(env):
    it = mk(env)
    items.cancel(it)
    assert items.find(it.id).status == "cancelled"
    assert items.find(it.id[:12]).id == it.id
    with pytest.raises(KeyError):
        items.find("nope")


def test_posting_window(env):
    cfg = cfgmod.load()
    cfg["windows"] = {"days": [0, 1, 2, 3, 4], "start": "08:00", "end": "20:00"}
    cfg["timezone"] = "America/New_York"
    mon_noon = dt.datetime(2026, 10, 19, 16, 0, tzinfo=dt.timezone.utc)   # Monday 12:00 Eastern
    mon_night = dt.datetime(2026, 10, 20, 3, 0, tzinfo=dt.timezone.utc)   # Monday 23:00 Eastern
    sat_noon = dt.datetime(2026, 10, 24, 16, 0, tzinfo=dt.timezone.utc)
    assert items.due_local_window(mon_noon, cfg)
    assert not items.due_local_window(mon_night, cfg)
    assert not items.due_local_window(sat_noon, cfg)
