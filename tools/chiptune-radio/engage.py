"""Live engagement for the laptop screen: "12 here", and a small toast when someone likes or subscribes.

What YouTube lets a stream see, and what this uses:
  * viewers now      concurrentViewers on the live video                    (videos.list, 1 quota unit)
  * new likes        the like count going up (who liked is not available)    (same call)
  * new subscribers  the channel's subscriber count going up                 (channels.list, 1 unit, less often)
Shares are not available in real time at all, and chat is deliberately left out: reading it costs several times the
daily quota when polled, and anything viewers type would need moderating before it could go on a public stream.

Cost at the defaults (a poll every 60 s, subscribers every 5th poll, the live video id re-read every 10th poll):
about 1,900 units a day against the project's 10,000 (checked 2026-10-07: 371 used at midday).

Only counts are shown, never names. The first reading is a baseline, so starting or restarting the stream never
announces what was already there, and a new broadcast re-baselines the likes (they are per video).
"""
from __future__ import annotations

import os
import threading
import time
from typing import Callable

import scene as sc

MIN_GAP = float(os.environ.get("ENGAGE_MIN_GAP", "20"))        # seconds of quiet between toasts
POLL_S = float(os.environ.get("ENGAGE_POLL_SECONDS", "60"))
SUBS_EVERY, ID_EVERY = 5, 10                                    # polls between subscriber reads, and between live-video lookups


def like_text(n: int) -> str:
    return "+1 LIKE" if n == 1 else (f"+{n} LIKES" if n < 10 else "LIKES!")


def sub_text(n: int) -> str:
    return "NEW SUB!" if n == 1 else (f"+{n} SUBS" if n < 10 else "NEW SUBS")


TEXT = {"like": like_text, "sub": sub_text}


class Engagement:
    def __init__(self, fetch: Callable[[], dict], log: Callable[[str], None] = print, min_gap: float = MIN_GAP):
        self.fetch, self.log, self.min_gap = fetch, log, min_gap
        self.lock = threading.Lock()
        self.viewers: int | None = None
        self._vid = self._likes = self._subs = None
        self._queue: list[list] = []                            # [kind, count]
        self._current: tuple | None = None                      # (kind, text, started_at)
        self._quiet_until = 0.0

    # ---- reading YouTube
    def poll_once(self) -> None:
        snap = self.fetch()
        vid = snap.get("video_id")
        with self.lock:
            self.viewers = snap.get("viewers") if vid else None
            likes = snap.get("likes")
            if likes is not None:
                if self._vid == vid and self._likes is not None and likes > self._likes:
                    self._enqueue("like", likes - self._likes)
                self._vid, self._likes = vid, likes             # a new broadcast re-baselines: likes belong to one video
            subs = snap.get("subs")
            if subs is not None:
                if self._subs is not None and subs > self._subs:
                    self._enqueue("sub", subs - self._subs)
                self._subs = subs

    def _enqueue(self, kind: str, n: int) -> None:
        for item in self._queue:
            if item[0] == kind:                                 # coalesce: three likes in a minute are one "+3 LIKES"
                item[1] += n
                return
        self._queue.append([kind, n])

    def run(self, cancel: threading.Event, poll_s: float = POLL_S) -> None:
        while not cancel.is_set():
            try:
                self.poll_once()
            except Exception as e:  # noqa: BLE001 - a missed reading is nothing; the stream must not care
                self.log(f"engagement poll failed: {type(e).__name__}: {str(e)[:120]}")
            if cancel.wait(poll_s):
                return

    # ---- what the video thread draws
    def view(self, now: float | None = None) -> dict:
        now = time.time() if now is None else now
        with self.lock:
            if self._current and now - self._current[2] >= sc.Scene.TOAST_SECONDS:
                self._current = None
                self._quiet_until = now + self.min_gap
            if self._current is None and self._queue and now >= self._quiet_until:
                kind, n = self._queue.pop(0)
                self._current = (kind, TEXT[kind](n), now)
            toast = None if self._current is None else (self._current[0], self._current[1], now - self._current[2])
            return {"toast": toast, "viewers": self.viewers or None}


def youtube_fetch(get_service: Callable[[], object]) -> Callable[[], dict]:
    """The real readings, through the stream's own YouTube login (the token already in stream.env)."""
    state = {"n": 0, "vid": None, "subs": None, "yt": None}

    def fetch() -> dict:
        if state["yt"] is None:
            state["yt"] = get_service()
        yt, n = state["yt"], state["n"]
        state["n"] += 1
        try:
            if state["vid"] is None or n % ID_EVERY == 0:
                items = yt.liveBroadcasts().list(part="id,status", mine=True, maxResults=10).execute().get("items", [])
                live = [b["id"] for b in items if b["status"]["lifeCycleStatus"] == "live"]
                state["vid"] = live[0] if live else None
            out = {"video_id": state["vid"], "likes": None, "viewers": None, "subs": state["subs"]}
            if state["vid"]:
                items = yt.videos().list(part="statistics,liveStreamingDetails", id=state["vid"]).execute().get("items", [])
                if items:
                    out["likes"] = int(items[0].get("statistics", {}).get("likeCount", 0))
                    out["viewers"] = int(items[0].get("liveStreamingDetails", {}).get("concurrentViewers", 0) or 0)
            if n % SUBS_EVERY == 0:
                stats = yt.channels().list(part="statistics", mine=True).execute()["items"][0]["statistics"]
                state["subs"] = out["subs"] = int(stats.get("subscriberCount", 0))
            return out
        except Exception:
            state["yt"] = None                                   # rebuild the client next time (an expired login, a dropped connection)
            raise

    return fetch


def demo_fetch() -> Callable[[], dict]:
    """Made-up readings, for a test render only (CHIPTUNE_ENGAGE_DEMO=1): likes and subscribers tick up, viewers wobble."""
    s = {"n": 0}

    def fetch() -> dict:
        s["n"] += 1
        n = s["n"]
        return {"video_id": "demo", "likes": 10 + n // 2, "subs": 100 + n // 3, "viewers": 3 + n % 5}

    return fetch
