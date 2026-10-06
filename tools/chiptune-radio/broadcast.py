"""Keep a YouTube broadcast bound to the stream key, so the radio never sits on air-but-unlisted.

stream.py ends the broadcast every 11 hours (YouTube only archives broadcasts under 12 hours) by
going silent for a few minutes, and used to rely on YouTube to open the next broadcast by itself when
the encoder came back. On 2026-10-06 it did not: the key reported `active` and `good` for hours while
the channel had no live video. This module creates the next broadcast through the Live API instead,
cloning the settings (description, DVR, latency, auto-start/stop) from the newest finished one.

It needs a token for the channel that owns the stream, with the `youtube.force-ssl` scope, passed as
the JSON text of an authorized-user file in YT_LIVE_TOKEN_JSON (put it in stream.env next to
STREAM_URL; both are secrets). Without it the keeper logs once and does nothing, and the stream runs
exactly as before.

Checks run right after a broadcast starts, again 2 and 10 minutes later, then every hour: the broadcast
that was live can take a moment to close, and YouTube can end one on its own.
"""
from __future__ import annotations

import datetime
import json
import os
import threading
from typing import Callable

CHECKS_AFTER_START = (0, 120, 600)          # seconds; then every `hourly` seconds
STILL_OPEN = {"created", "ready", "testing", "liveStarting", "live"}

TITLES = {
    "16bit": "24/7 16-Bit Study Music: Chiptune Focus Radio with Pomodoro Timer (25/5)",
    "8bit": "24/7 8-Bit Study Music: Chiptune Focus Radio with Pomodoro Timer (25/5)",
    "synth": "24/7 Synth Chiptune Study Music: Focus Radio with Pomodoro Timer (25/5)",
    "hybrid": "24/7 Chiptune Study Music Mix: Focus Radio with Pomodoro Timer (25/5)",
    None: "24/7 Chiptune Study Music Mix: Focus Radio with Pomodoro Timer (25/5)",
}


def title_for(era: str | None) -> str:
    return TITLES.get(era, TITLES[None])[:100]


def configured() -> bool:
    return bool(os.environ.get("YT_LIVE_TOKEN_JSON"))


def _service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    creds = Credentials.from_authorized_user_info(json.loads(os.environ["YT_LIVE_TOKEN_JSON"]))
    if not creds.valid:
        creds.refresh(Request())
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def ensure(era: str | None, yt=None, log: Callable[[str], None] = print) -> str:
    """Make sure one broadcast is open on the stream key. Returns what it did."""
    yt = yt or _service()
    items = yt.liveBroadcasts().list(part="snippet,contentDetails,status", mine=True,
                                     maxResults=25).execute().get("items", [])
    open_now = [b for b in items if b["status"]["lifeCycleStatus"] in STILL_OPEN]
    if open_now:
        return f"already open: {open_now[0]['id']} ({open_now[0]['status']['lifeCycleStatus']})"

    finished = [b for b in items if b["status"]["lifeCycleStatus"] == "complete"]
    tmpl = finished[0] if finished else (items[0] if items else None)
    stream_id = (tmpl or {}).get("contentDetails", {}).get("boundStreamId")
    if not stream_id:
        streams = yt.liveStreams().list(part="id", mine=True, maxResults=1).execute().get("items", [])
        if not streams:
            return "no stream key on the channel — nothing to bind to"
        stream_id = streams[0]["id"]

    cd = (tmpl or {}).get("contentDetails", {})
    start = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    created = yt.liveBroadcasts().insert(part="snippet,status,contentDetails", body={
        "snippet": {"title": title_for(era),
                    "description": (tmpl or {}).get("snippet", {}).get("description", ""),
                    "scheduledStartTime": start},
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
        "contentDetails": {
            "enableAutoStart": True, "enableAutoStop": True,
            "enableDvr": cd.get("enableDvr", True), "recordFromStart": cd.get("recordFromStart", True),
            "enableEmbed": cd.get("enableEmbed", True),
            "latencyPreference": cd.get("latencyPreference", "low"),
            "enableClosedCaptions": False,
            "monitorStream": {"enableMonitorStream": True},
        }}).execute()
    yt.liveBroadcasts().bind(id=created["id"], part="id,contentDetails", streamId=stream_id).execute()

    # The broadcast's video starts uncategorised; file it under Music like the first one.
    # Cosmetic, so a failure here must never undo or hide the broadcast that now exists.
    try:
        src = yt.videos().list(part="snippet", id=tmpl["id"]).execute()["items"][0]["snippet"] if tmpl else {}
        sn = {"title": title_for(era), "description": src.get("description", ""),
              "categoryId": src.get("categoryId", "10")}
        if src.get("tags"):
            sn["tags"] = src["tags"]
        yt.videos().update(part="snippet", body={"id": created["id"], "snippet": sn}).execute()
    except Exception as e:  # noqa: BLE001
        log(f"broadcast {created['id']}: category/tags not copied ({type(e).__name__})")
    return f"created {created['id']} \"{title_for(era)}\""


def keep(era: str | None, cancel: threading.Event, log: Callable[[str], None] = print,
         hourly: float = 3600.0, ensure_fn=ensure) -> None:
    """Run in a thread for the lifetime of one broadcast; `cancel` ends it."""
    waits = [CHECKS_AFTER_START[0]] + [b - a for a, b in zip(CHECKS_AFTER_START, CHECKS_AFTER_START[1:])]
    i = 0
    while not cancel.is_set():
        wait = waits[i] if i < len(waits) else hourly
        i += 1
        if cancel.wait(wait):
            return
        try:
            log(f"broadcast check: {ensure_fn(era)}")
        except Exception as e:  # noqa: BLE001 - the stream must keep running whatever YouTube says
            log(f"broadcast check failed: {type(e).__name__}: {str(e)[:160]}")
