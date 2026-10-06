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
        return LB()

    def liveStreams(self):
        class LS:
            def list(self, **kw): return _Call(lambda: {"items": [{"id": "STREAM"}]})
        return LS()

    def videos(self):
        yt = self
        class V:
            def list(self, **kw):
                return _Call(lambda: {"items": [{"snippet": {"description": "d", "categoryId": "10", "tags": ["a"]}}]})
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
    assert body["snippet"]["description"] == "desc"
    assert body["contentDetails"]["enableAutoStart"] is True and body["status"]["privacyStatus"] == "public"
    assert yt.updated and yt.updated[0]["snippet"]["categoryId"] == "10"


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
