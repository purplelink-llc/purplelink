"""The room's events and the sharp full-size frame: when things happen is a pure function of the clock, every event draws, and the
world clocks tell the true time in each city."""
import collections
import datetime as dt

import numpy as np
import pytest

import critters
import pixfont
import scene as sc


def test_events_are_a_function_of_the_clock():
    a = [critters.active(1_700_000_000 + i * 7.0, 14.0, False) for i in range(400)]
    b = [critters.active(1_700_000_000 + i * 7.0, 14.0, False) for i in range(400)]
    assert a == b                                                         # same minute, same event, on every restart


def test_every_event_happens_and_only_at_the_right_time():
    seen = collections.defaultdict(set)
    for slot in range(4000):
        for hour, rain in ((14.0, False), (23.0, False), (23.0, True), (14.0, True)):
            ev = critters.active(slot * critters.SLOT + 120.0, hour, rain)       # the middle of the slot
            if ev:
                seen[(hour, rain)].add(ev[0])
    everything = set().union(*seen.values())
    assert everything == {"cat", "dog", "bird", "vacuum", "star", "balloon", "storm", "friend", "plane"}
    assert "star" not in seen[(14.0, False)] and "balloon" not in seen[(23.0, False)]        # stars at night, balloons by day
    assert "storm" not in seen[(14.0, False)] and "storm" in seen[(23.0, True)]              # lightning only while it rains
    assert "bird" not in seen[(14.0, True)] and "balloon" not in seen[(14.0, True)]          # no robin or balloon in the rain


def test_an_event_runs_for_its_whole_length_inside_one_slot():
    hits = {}
    for slot in range(300):
        base = slot * critters.SLOT
        runs = [critters.active(base + s, 14.0, False) for s in range(0, int(critters.SLOT), 2)]
        names = {r[0] for r in runs if r}
        assert len(names) <= 1                                                  # one event per slot, never two at once
        for r in runs:
            if r:
                assert 0 <= r[1] < r[2] <= critters.SLOT
                hits[r[0]] = max(hits.get(r[0], 0), r[1])
    assert hits["dog"] > 100                                                      # a dog visit really lasts a couple of minutes


def test_the_cat_goes_through_its_routine_and_ends_asleep():
    order = [critters.cat_pose(("cat", age, 48)) for age in (0, 3, 8, 18, 26, 32, 40, 47)]
    assert order == ["sleep", "wake", "stretch", "wash", "yawn", "look", "curl", "sleep"]
    assert critters.cat_pose(None) == "sleep" and critters.cat_pose(("dog", 5, 130)) == "sleep"


@pytest.mark.parametrize("name,age,dur,hour,rain", [
    ("cat", 8, 48, 14, False), ("dog", 22, 130, 14, False), ("dog", 3, 130, 14, False), ("dog", 125, 130, 14, False),
    ("bird", 9, 30, 14, False), ("bird", 3, 30, 14, False), ("vacuum", 25, 58, 14, False), ("star", 1.0, 9, 23, False),
    ("balloon", 35, 80, 14, False), ("storm", 2.05, 9, 23, True)])
def test_each_event_changes_the_picture(monkeypatch, name, age, dur, hour, rain):
    s = sc.Scene()
    monkeypatch.setattr(critters, "active", lambda *a: None)
    quiet = np.array(s.frame(1.0, hour, rain, 84, "x", 600.0)).astype(int)
    monkeypatch.setattr(critters, "active", lambda *a: (name, age, dur))
    busy = np.array(s.frame(1.0, hour, rain, 84, "x", 600.0)).astype(int)
    assert (np.abs(quiet - busy).sum(axis=2) > 0).sum() > 15                      # something was drawn


def test_the_full_size_frame_is_exactly_six_times_the_scene():
    s = sc.Scene()
    hd = s.frame_hd(1.0, 14, False, 84, "D major, 80 BPM", 600.0)
    assert hd.size == (1920, 1080) and 1920 == sc.W * sc.Scene.HD_SCALE
    a = s.frame(1.0, 14, False, 84, "x", 600.0, hud=False, lights_dy=10).resize((1920, 1080), 0)
    diff = np.abs(np.array(hd).astype(int) - np.array(a).astype(int)).sum(axis=2) > 0
    assert diff[:64].any() and diff[790:].any() and not diff[300:500].any()      # text only at the top and bottom: the room is untouched


def test_the_break_is_a_different_colour_and_the_timer_counts_down():
    s = sc.Scene()
    focus = np.array(s.frame_hd(1.0, 14, False, 84, "x", 60.0))
    brk = np.array(s.frame_hd(1.0, 14, False, 84, "x", sc.FOCUS + 60.0))
    assert not np.array_equal(focus[796:970, 24:584], brk[796:970, 24:584])
    assert not np.array_equal(focus[800:970, 24:584], np.array(s.frame_hd(1.0, 14, False, 84, "x", 62.0))[800:970, 24:584])


def test_the_nudge_shows_for_fifteen_seconds_of_every_four_minutes():
    s = sc.Scene()
    on = np.array(s.frame_hd(1.0, 14, False, 84, "x", 240.0 * 10 + 5.0))[896:972, 700:1200]
    off = np.array(s.frame_hd(1.0, 14, False, 84, "x", 240.0 * 10 + 100.0))[896:972, 700:1200]
    assert not np.array_equal(on, off)


def test_world_clocks_tell_the_true_time_in_each_city():
    s = sc.Scene()
    wall = dt.datetime(2026, 10, 7, 18, 0, tzinfo=dt.timezone.utc).timestamp()
    got = {label: hhmm for label, hhmm, _ in s.world_clocks(wall)}
    assert got == {"LA": "11:00", "NYC": "14:00", "LON": "19:00", "DEL": "23:30", "TYO": "03:00", "SYD": "05:00"}      # British and Sydney summer time
    winter = dt.datetime(2026, 1, 15, 12, 0, tzinfo=dt.timezone.utc).timestamp()
    got = {label: hhmm for label, hhmm, _ in s.world_clocks(winter)}
    assert got["LA"] == "04:00" and got["LON"] == "12:00" and got["SYD"] == "23:00"
    day = {label: d for label, _, d in s.world_clocks(wall)}
    assert day["LA"] and day["NYC"] and not day["DEL"] and not day["TYO"]


def test_the_pixel_font_covers_what_the_stream_prints():
    for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 :.,-+!/'?#":
        assert ch in pixfont.GLYPHS
    assert pixfont.width("AB", 4) == (5 + 1 + 5) * 4 and pixfont.width("", 4) == 0
    im = pixfont.text_image("24:13", 8, (255, 255, 255))
    assert im.mode == "RGBA" and im.height >= 7 * 8
    assert pixfont.text_image("PURPLELINK.LLC", 5, (255, 255, 255)) is pixfont.text_image("PURPLELINK.LLC", 5, (255, 255, 255))   # cached
    assert pixfont.text_image("é~", 3, (255, 255, 255)).size[0] > 0                            # an unknown letter is a '?', never an error


def test_the_person_leaves_for_the_break_and_comes_back_with_headphones_on():
    ps = sc.Scene.person_state
    assert ps(None)["mode"] == "sit" and ps(None)["phones_on"]                                 # focusing: seated, headphones on
    assert ps(2)["arms_up"] and ps(2)["mode"] == "sit"                                         # first the stretch
    assert ps(7)["mode"] == "stand" and not ps(7)["phones_on"] and ps(7)["desk_phones"]        # they stand and the headphones are on the desk
    assert ps(12)["mode"] == "walk" and ps(12)["x"] > 160                                      # walking out to the right
    assert all(ps(b)["mode"] == "away" for b in (17, 100, 200, 281))                           # gone for most of the five minutes
    assert ps(286)["mode"] == "walk" and ps(286)["x"] < 350                                    # walking back in
    assert ps(291)["mode"] in ("stand", "sit") and not ps(291)["phones_on"]
    assert ps(293)["putting_on"] is not None and not ps(293)["phones_on"]                      # hands raising the headphones
    assert ps(297)["mode"] == "sit" and ps(297)["phones_on"] and not ps(297)["desk_phones"]    # on, before the break is over
    assert ps(299.9)["phones_on"] and ps(299.9)["mode"] == "sit"


def test_the_scene_has_nobody_in_the_chair_while_they_are_away():
    s = sc.Scene()
    away = np.array(s.frame(1.0, 14, False, 84, "x", sc.FOCUS + 100.0, events=False)).astype(int)
    focus = np.array(s.frame(1.0, 14, False, 84, "x", 60.0, events=False)).astype(int)
    hoodie = np.array(sc.C["hoodie"])
    assert (np.abs(focus[100:128, 136:184] - hoodie).sum(axis=2) == 0).sum() > 500           # someone in the hoodie at the desk
    assert (np.abs(away[100:128, 136:184] - hoodie).sum(axis=2) == 0).sum() == 0              # the seat is empty


def test_the_person_walks_in_front_of_the_cat_not_behind_it():
    s = sc.Scene()
    bt = 11.0                                                                  # mid walk out; find where they are
    st = sc.Scene.person_state(bt)
    walking = np.array(s.frame(1.0, 14, False, 84, "x", sc.FOCUS + bt, events=False)).astype(int)
    cat = np.array(sc.C["cat"])
    x = st["x"]
    # where the cat's body would be (sleeping on the sill, x 214-244, y 96-108), the person's hoodie covers it wherever they overlap
    lo, hi = max(214, x - 24), min(245, x + 25)
    if lo < hi:
        region = walking[98:108, lo:hi]
        assert (np.abs(region - cat).sum(axis=2) == 0).sum() == 0


# ---------------------------------------------------------------------------------------------- goldfish, friend, plane
def test_the_goldfish_swims(monkeypatch):
    monkeypatch.setattr(critters, "active", lambda *a: None)
    s = sc.Scene()
    a = np.array(s.frame(1.0, 14, False, 84, "x", 600.0, season=None)).astype(int)
    b = np.array(s.frame(3.0, 14, False, 84, "x", 600.0, season=None)).astype(int)
    x0, y0, x1, y1 = critters.BOWL
    assert (np.abs(a - b)[y0:y1 + 1, x0:x1 + 1].sum(axis=2) > 0).sum() > 3                    # the fish moved inside the bowl


def test_the_friend_walks_in_pours_and_leaves_the_mug_steaming():
    assert critters.friend_state(0, 90)[0] > 300 and critters.friend_state(10, 90)[0] == critters.FRIEND_X
    assert critters.friend_state(10, 90)[1] and not critters.friend_state(17, 90)[1]               # pours for a few seconds
    assert critters.friend_state(40, 90)[0] is None and critters.friend_state(40, 90)[2]           # gone, steam stays up


def test_the_season_follows_the_real_date(monkeypatch):
    monkeypatch.delenv("STREAM_SEASON", raising=False)
    import datetime as dt
    ny = seasons_tz()
    at = lambda *a: dt.datetime(*a, tzinfo=ny).timestamp()
    import seasons
    assert seasons.season(at(2026, 10, 7, 12)) is None and seasons.season(at(2026, 10, 25, 12)) == "halloween"
    assert seasons.season(at(2026, 11, 2, 12)) is None and seasons.season(at(2026, 12, 20, 12)) == "christmas"
    assert seasons.season(at(2026, 12, 31, 16)) is None and seasons.season(at(2026, 12, 31, 20)) == "newyear"
    assert seasons.season(at(2027, 1, 1, 1)) == "newyear" and seasons.season(at(2027, 1, 1, 4)) is None
    assert seasons.season(at(2026, 10, 7, 12), forced="christmas") == "christmas" and seasons.season(at(2026, 10, 25, 12), forced="off") is None


def seasons_tz():
    import seasons
    return seasons._tz()


@pytest.mark.parametrize("name", ["halloween", "christmas", "newyear"])
def test_each_season_changes_the_room_and_the_lights(monkeypatch, name):
    import seasons
    monkeypatch.setattr(critters, "active", lambda *a: None)
    s = sc.Scene()
    plain = np.array(s.frame(3.0, 23, False, 84, "x", 600.0, season=None)).astype(int)
    decorated = np.array(s.frame(3.0, 23, False, 84, "x", 600.0, season=name)).astype(int)
    assert (np.abs(plain - decorated).sum(axis=2) > 0).sum() > 100
    assert seasons.light_colours(name, 0, True) != seasons.light_colours(None, 0, True)


def test_the_pomodoro_tally_counts_finished_focus_blocks_since_local_midnight():
    import datetime as dt, seasons
    ny = seasons._tz()
    mid = dt.datetime(2026, 3, 3, 0, 0, tzinfo=ny).timestamp()
    f = sc.Scene.pomodoros_today
    assert f(mid + 60) == 0 and f(mid + 24 * 60) == 0 and f(mid + 25 * 60 + 1) == 1               # the first block ends at 00:25
    assert f(mid + 55 * 60 + 1) == 2 and f(mid + 12 * 3600 + 10 * 60) == 24
    spring = dt.datetime(2026, 3, 8, 12, 0, tzinfo=ny).timestamp()                                   # the clocks went forward that night
    assert f(spring) == 22                                                                           # only 11 real hours had passed by noon


def test_the_goal_bar_and_confetti_only_appear_when_there_are_subscribers():
    s = sc.Scene()
    none = np.array(s.frame_hd(1.0, 14, False, 84, "x", 60.0, fx={"toast": None, "viewers": None, "subs": None}, season=None))
    some = np.array(s.frame_hd(1.0, 14, False, 84, "x", 60.0, fx={"toast": None, "viewers": None, "subs": 143}, season=None))
    assert not np.array_equal(none[880:975, 1400:1900], some[880:975, 1400:1900])                   # the bar is bottom right
    pop = np.array(s.frame_hd(1.0, 14, False, 84, "x", 60.0, fx={"toast": ("sub", "NEW SUB!", 1.0), "viewers": None, "subs": 144}, season=None))
    assert (np.abs(pop.astype(int) - some.astype(int)).sum(axis=2) > 0)[100:700].sum() > 2000       # confetti over the window
    assert sc.Scene.GOALS == sorted(sc.Scene.GOALS)
