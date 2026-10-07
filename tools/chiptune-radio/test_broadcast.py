"""broadcast.ensure / keep against a fake YouTube service (no network, no credentials)."""
import threading

import broadcast


class _Call:
    def __init__(self, fn): self.fn = fn
    def execute(self): return self.fn()


class FakeYT:
    def __init__(self, broadcasts):
        self.items = broadcasts
        self.created, self.bound, self.updated = [], [], []
        self.thumbs, self.chats, self.thumb_error = [], [], None
        self.transitions = []
        self.snippet = {"description": "old", "categoryId": "10", "tags": ["a"], "title": "old"}

    def liveBroadcasts(self):
        yt = self
        class LB:
            def list(self, **kw): return _Call(lambda: {"items": yt.items})
            def insert(self, part, body):
                def go():
                    yt.created.append(body)
                    return {"id": "NEW1"}
                return _Call(go)
            def bind(self, id, part, streamId):
                yt.bound.append((id, streamId)); return _Call(lambda: {})
            def transition(self, broadcastStatus, id, part):
                yt.transitions.append((id, broadcastStatus)); return _Call(lambda: {})
        return LB()

    def liveStreams(self):
        class LS:
            def list(self, **kw): return _Call(lambda: {"items": [{"id": "STREAM"}]})
        return LS()

    def thumbnails(self):
        yt = self
        class T:
            def set(self, videoId, media_body):
                if yt.thumb_error: raise RuntimeError(yt.thumb_error)
                yt.thumbs.append(videoId); return _Call(lambda: {})
        return T()

    def liveChatMessages(self):
        yt = self
        class C:
            def insert(self, part, body): yt.chats.append(body["snippet"]); return _Call(lambda: {})
        return C()

    def videos(self):
        yt = self
        class V:
            def list(self, **kw):
                return _Call(lambda: {"items": [{"snippet": yt.snippet}]})
            def update(self, part, body): yt.updated.append(body); return _Call(lambda: {})
        return V()


def _b(i, state, stream="STREAM"):
    return {"id": i, "status": {"lifeCycleStatus": state}, "snippet": {"description": "desc"},
            "contentDetails": {"boundStreamId": stream, "enableDvr": True, "latencyPreference": "low"}}


def test_creates_and_binds_when_the_last_broadcast_is_complete():
    yt = FakeYT([_b("OLD", "complete")])
    out = broadcast.ensure("synth", yt=yt)
    assert out.startswith("created NEW1")
    assert yt.bound == [("NEW1", "STREAM")]
    body = yt.created[0]
    assert body["snippet"]["title"] == broadcast.title_for("synth")
    assert body["snippet"]["description"] == broadcast.description_for("synth")
    assert body["contentDetails"]["enableAutoStart"] is True and body["status"]["privacyStatus"] == "public"
    sn = yt.updated[0]["snippet"]
    assert sn["categoryId"] == "10" and sn["tags"] == broadcast.TAGS and sn["defaultLanguage"] == "en"


def test_does_nothing_when_one_is_already_open():
    for state in ("live", "ready", "created", "testing", "liveStarting"):
        yt = FakeYT([_b("CUR", state), _b("OLD", "complete")])
        assert broadcast.ensure(None, yt=yt).startswith("already open: CUR")
        assert not yt.created and not yt.bound


def test_first_ever_run_falls_back_to_the_channels_stream_key():
    yt = FakeYT([])
    assert broadcast.ensure("8bit", yt=yt).startswith("created NEW1")
    assert yt.bound == [("NEW1", "STREAM")]


def test_titles_fit_and_cover_every_era():
    for era in ("16bit", "8bit", "synth", "hybrid", None, "unknown"):
        assert 0 < len(broadcast.title_for(era)) <= 100


def test_keep_survives_errors_and_stops_when_cancelled():
    cancel, seen = threading.Event(), []
    def boom(era):
        seen.append(era)
        if len(seen) == 2: cancel.set()
        raise RuntimeError("quota")
    broadcast.CHECKS_AFTER_START = (0, 0, 0)
    broadcast.keep("8bit", cancel, log=lambda m: None, hourly=0.01, ensure_fn=boom)
    assert seen == ["8bit", "8bit"]


def test_search_metadata_fits_youtubes_limits_and_says_the_important_things():
    assert broadcast.tags_total() <= 480                    # the limit is 500 characters for the whole list
    assert len(set(broadcast.TAGS)) == len(broadcast.TAGS)
    for era in ("16bit", "8bit", "synth", "hybrid", None):
        title, desc = broadcast.title_for(era), broadcast.description_for(era)
        assert len(title) <= 100 and "Study Music" in title and "Pomodoro" in title
        assert len(desc) < 5000
        head = "\n".join(desc.splitlines()[:2])
        assert "Like" in head and "Subscribe" in head and "Share" in head        # the ask is above the fold
        assert "chiptune study music" in head.lower() and "utm_campaign=chiptune-radio" in desc
        assert desc.count("#") <= 15                                              # YouTube ignores all hashtags past 15


def test_open_broadcast_gets_current_metadata_only_when_it_differs():
    yt = FakeYT([_b("CUR", "live")])
    assert "metadata refreshed" in broadcast.ensure("8bit", yt=yt)
    sent = yt.updated[-1]["snippet"]
    assert sent["title"] == broadcast.title_for("8bit") and sent["tags"] == broadcast.TAGS and sent["categoryId"] == "10"
    # once YouTube shows the current text (trailing whitespace is ignored), nothing more is written
    yt.snippet = {"title": broadcast.title_for("8bit"), "description": broadcast.description_for("8bit") + "  \n",
                  "tags": list(reversed(broadcast.TAGS)), "categoryId": "10"}     # YouTube hands tags back reordered
    n = len(yt.updated)
    assert "metadata current" in broadcast.ensure("8bit", yt=yt)
    assert len(yt.updated) == n and not yt.created


def test_new_title_leads_with_the_red_dot_and_the_search_terms():
    for era in ("16bit", "8bit", "synth", None):
        title = broadcast.title_for(era)
        assert title.startswith("\U0001F534 24/7 ") and "Study Music" in title and "Lofi Beats to Focus to" in title and len(title) <= 100


def test_thumbnail_is_set_once_per_broadcast_and_a_refusal_never_raises():
    broadcast._thumb_done.clear()
    yt = FakeYT([_b("OLD", "complete")])
    assert broadcast.ensure("8bit", yt=yt).endswith("thumbnail set")
    assert yt.thumbs == ["NEW1"]
    assert broadcast.set_thumbnail(yt, "NEW1") == "already set" and yt.thumbs == ["NEW1"]
    yt2 = FakeYT([_b("CUR", "live")]); yt2.thumb_error = "channel not verified"
    assert broadcast.set_thumbnail(yt2, "CUR", log=lambda m: None) == "refused"
    assert broadcast.set_thumbnail(yt2, "CUR", log=lambda m: None) == "already set"      # no retry every hour


def test_chat_posts_only_into_a_live_broadcasts_chat():
    live = _b("CUR", "live"); live["snippet"]["liveChatId"] = "CHAT1"
    yt = FakeYT([live])
    assert broadcast.post_chat(yt, "hello") == "posted"
    assert yt.chats == [{"liveChatId": "CHAT1", "type": "textMessageEvent", "textMessageDetails": {"messageText": "hello"}}]
    assert broadcast.post_chat(FakeYT([_b("OLD", "complete")]), "hello") == "no live chat open"
    assert all(len(line) <= 200 for line in broadcast.CHAT_LINES) and len(set(broadcast.CHAT_LINES)) == len(broadcast.CHAT_LINES)


def test_chat_loop_fires_five_seconds_past_each_hour_and_survives_errors():
    clock = {"t": 1_000_000 * 3600 + 1800.0}                     # half past an hour
    waits, said = [], []
    cancel = threading.Event()
    def fake_wait(s):
        waits.append(round(s)); clock["t"] += s
        return len(waits) > 3                                    # let three hours go by, then cancel
    cancel.wait = fake_wait
    def post(text):
        said.append(text)
        if len(said) == 2: raise RuntimeError("quota")
        return "posted"
    broadcast.chat_loop(cancel, log=lambda m: None, now=lambda: clock["t"], post_fn=post)
    assert waits[0] == 1805 and waits[1:3] == [3600, 3600]       # 25 min to the hour plus 5 s, then hourly
    assert len(said) == 3 and len(set(said)) == 3                # errors do not stop it, and the wording rotates


def test_end_current_ends_only_the_live_broadcast():
    yt = FakeYT([_b("OLD", "complete"), _b("CUR", "live"), _b("NEXT", "ready")])
    assert broadcast.end_current(yt, log=lambda m: None) is True
    assert yt.transitions == [("CUR", "complete")]


def test_end_current_reports_false_when_nothing_is_live_or_the_api_fails():
    yt = FakeYT([_b("OLD", "complete")])
    assert broadcast.end_current(yt, log=lambda m: None) is False and yt.transitions == []
    class Broken:
        def liveBroadcasts(self): raise RuntimeError("quota")
    said = []
    assert broadcast.end_current(Broken(), log=said.append) is False and "falling back" in said[0]
