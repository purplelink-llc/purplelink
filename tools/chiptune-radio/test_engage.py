"""Live engagement on the laptop screen: what gets queued, when it shows, that it stays on the screen, and what it costs."""
import threading

import numpy as np

import engage
import scene as sc


class Feed:
    """A scripted YouTube: each call returns the next reading."""
    def __init__(self, *readings): self.r = list(readings)
    def __call__(self): return self.r.pop(0) if len(self.r) > 1 else self.r[0]


def snap(likes=10, subs=100, viewers=3, vid="v1"):
    return {"video_id": vid, "likes": likes, "subs": subs, "viewers": viewers}


def test_the_first_reading_is_a_baseline_so_a_restart_announces_nothing():
    e = engage.Engagement(Feed(snap(likes=500, subs=2000)), log=lambda m: None)
    e.poll_once()
    assert e.view(1000.0)["toast"] is None


def test_new_likes_and_subscribers_become_toasts_with_counts_only():
    e = engage.Engagement(Feed(snap(), snap(likes=11), snap(likes=11, subs=101)), log=lambda m: None, min_gap=0)
    e.poll_once(); e.poll_once()
    assert e.view(0.0)["toast"][:2] == ("like", "+1 LIKE")
    e.view(10.0)                                           # that toast has expired
    e.poll_once()
    t = e.view(10.0)["toast"]
    assert t[:2] == ("sub", "NEW SUB!")


def test_several_new_likes_before_the_next_toast_are_one_message():
    e = engage.Engagement(Feed(snap(), snap(likes=11), snap(likes=13)), log=lambda m: None)
    for _ in range(3): e.poll_once()
    assert e.view(0.0)["toast"][1] == "+3 LIKES"


def test_a_burst_never_floods_the_screen():
    e = engage.Engagement(Feed(snap(subs=100), snap(subs=1100)), log=lambda m: None)
    e.poll_once(); e.poll_once()
    assert e.view(0.0)["toast"][1] == "NEW SUBS"           # no number, no list of names


def test_toasts_expire_and_respect_the_quiet_gap():
    e = engage.Engagement(Feed(snap(), snap(likes=11), snap(likes=11, subs=101)), log=lambda m: None, min_gap=20)
    e.poll_once(); e.poll_once(); e.poll_once()             # a like and then a subscriber are waiting
    assert e.view(0.0)["toast"][0] == "like"
    assert e.view(sc.Scene.TOAST_SECONDS - 0.1)["toast"][0] == "like"
    assert e.view(sc.Scene.TOAST_SECONDS + 1)["toast"] is None            # shown for its time, then gone
    assert e.view(sc.Scene.TOAST_SECONDS + 10)["toast"] is None           # the quiet gap
    assert e.view(sc.Scene.TOAST_SECONDS + 21)["toast"][0] == "sub"       # then the next one


def test_a_new_broadcast_rebaselines_likes_but_not_subscribers():
    e = engage.Engagement(Feed(snap(likes=40, vid="old"), snap(likes=2, vid="new")), log=lambda m: None)
    e.poll_once(); e.poll_once()
    assert e.view(0.0)["toast"] is None                    # fewer likes on a new video is not an event, nor is it a decrease to announce


def test_viewers_show_only_while_live_and_non_zero():
    e = engage.Engagement(Feed(snap(viewers=7)), log=lambda m: None); e.poll_once()
    assert e.view(0.0)["viewers"] == 7
    e = engage.Engagement(Feed({"video_id": None, "likes": None, "subs": None, "viewers": 4}), log=lambda m: None); e.poll_once()
    assert e.view(0.0)["viewers"] is None
    e = engage.Engagement(Feed(snap(viewers=0)), log=lambda m: None); e.poll_once()
    assert e.view(0.0)["viewers"] is None


def test_a_failing_poll_is_logged_and_never_stops_the_loop():
    calls, said = [], []
    def boom():
        calls.append(1)
        raise RuntimeError("quota")
    cancel = threading.Event()
    cancel.wait = lambda s: len(calls) >= 3
    engage.Engagement(boom, log=said.append).run(cancel, poll_s=0)
    assert len(calls) == 3 and said and "RuntimeError" in said[0]


def test_every_message_fits_on_the_laptop_screen():
    sx0, sy0, sx1, sy1 = sc.Scene.SCREEN
    room = (sx1 - sx0 - 4) - 14                              # banner width minus where the text starts
    for n in range(1, 40):
        for text in (engage.like_text(n), engage.sub_text(n)):
            assert sc.Scene.tiny_width(text) <= room, text
    assert sc.Scene.tiny_width("999 HERE") <= (sx1 - sx0) - 7  # the viewer count, even at three digits


def test_notifications_are_drawn_only_inside_the_laptop_screen():
    s = sc.Scene()
    base = np.array(s.frame(10.0, 21.0, True, 80, "", wall=60.0, fx={"toast": None, "viewers": None}))
    for age in (0.1, 0.35, 2.0, 5.3):
        with_fx = np.array(s.frame(10.0, 21.0, True, 80, "", wall=60.0,
                                   fx={"toast": ("sub", "NEW SUB!", age), "viewers": 12}))
        ys, xs = np.nonzero(np.abs(with_fx.astype(int) - base.astype(int)).sum(axis=2))
        sx0, sy0, sx1, sy1 = sc.Scene.SCREEN
        assert xs.min() >= sx0 and xs.max() <= sx1 and ys.min() >= sy0 and ys.max() <= sy1, (age, xs.min(), xs.max(), ys.min(), ys.max())


def test_with_no_engagement_the_frame_is_unchanged():
    s = sc.Scene()
    a = s.frame(10.0, 21.0, True, 80, "x", wall=60.0)
    b = s.frame(10.0, 21.0, True, 80, "x", wall=60.0, fx=None)
    assert np.array_equal(np.array(a), np.array(b))


def test_polling_costs_what_the_docstring_says():
    class Call:
        def __init__(self, n, out): self.n, self.out = n, out
        def execute(self): self.n["calls"] += 1; return self.out
    n = {"calls": 0, "b": 0, "v": 0, "c": 0}
    class YT:
        def liveBroadcasts(self):
            class LB:
                def list(s, **kw): n["b"] += 1; return Call(n, {"items": [{"id": "V", "status": {"lifeCycleStatus": "live"}}]})
            return LB()
        def videos(self):
            class V:
                def list(s, **kw): n["v"] += 1; return Call(n, {"items": [{"statistics": {"likeCount": "5"}, "liveStreamingDetails": {"concurrentViewers": "2"}}]})
            return V()
        def channels(self):
            class C:
                def list(s, **kw): n["c"] += 1; return Call(n, {"items": [{"statistics": {"subscriberCount": "30"}}]})
            return C()
    fetch = engage.youtube_fetch(lambda: YT())
    for _ in range(10): out = fetch()
    assert (n["b"], n["v"], n["c"]) == (1, 10, 2)            # one broadcast lookup, ten video reads, two channel reads per ten minutes
    assert out["likes"] == 5 and out["viewers"] == 2 and out["subs"] == 30 and out["video_id"] == "V"
    per_day = 24 * 60 * (1 + 2 / 10 + 1 / 10)                # units a day at one poll a minute
    assert per_day < 2000
