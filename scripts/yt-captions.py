#!/usr/bin/env python3
"""Upload a SubRip caption track to one of our YouTube videos, through the same channel guard as yt-api-upload.py.

    python3 scripts/yt-captions.py VIDEO_ID FILE.srt [--channel purplelink] [--lang en] [--name English] [--dry-run]

Ben, 2026-10-21: every how-to video and Short gets a caption track built from its narration's word timings
(video/src/howto/srt.js, written by video/build-howto.mjs), so viewers get selectable captions and YouTube gets the
exact transcript instead of its automatic guess. scripts/howto-publish.py calls this after each upload.

Checks, all of which must pass before anything is sent (ChannelGuardError otherwise):
  - the channel is in scripts/yt-channels.json and confirmed by Ben;
  - the token belongs to exactly that channel (yt_guard.verify_identity);
  - the video exists and is that channel's own;
  - the file is a non-empty SubRip file.
A video that already has a non-automatic track in this language is left alone (exit 0, "skipped"), so reruns
never duplicate a track. Quota: captions.insert costs 400 units, the checks about 150.
Exit codes: 0 uploaded or skipped, 2 bad arguments or file, 3 guard refused.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import yt_guard as g  # noqa: E402

SRT_RX = re.compile(r"^\d+\s*\n\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}", re.M)


def valid_srt(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return bool(text.strip()) and bool(SRT_RX.search(text))


def existing_track(service, video_id: str, lang: str):
    items = service.captions().list(part="snippet", videoId=video_id).execute().get("items", [])
    for it in items:
        sn = it.get("snippet") or {}
        if sn.get("language", "").split("-")[0] == lang.split("-")[0] and sn.get("trackKind") != "asr":
            return it.get("id")
    return None


def attach(video_id: str, srt: Path, channel_key: str = "purplelink", lang: str = "en", name: str = "English",
           dry_run: bool = False, service=None, registry=None) -> dict:
    """Guard, then upload. Returns {"video_id", "caption_id"} or {"video_id", "skipped": reason}."""
    srt = Path(srt)
    if not valid_srt(srt):
        raise ValueError(f"{srt} is not a non-empty SubRip file")
    ch = g.get_channel(channel_key, registry)
    g.check_confirmed(ch, channel_key)
    if service is None:
        service = g.build_service(g.token_path(ch))
    g.verify_identity(service, ch, channel_key)
    items = service.videos().list(part="snippet", id=video_id).execute().get("items", [])
    if not items:
        raise g.ChannelGuardError(f"video {video_id} not found")
    owner = (items[0].get("snippet") or {}).get("channelId")
    if owner != ch["id"]:
        raise g.ChannelGuardError(f"video {video_id} belongs to {owner}, not {ch['id']} ({ch['title']}); not adding captions")
    have = existing_track(service, video_id, lang)
    if have:
        return {"video_id": video_id, "skipped": f"already has a {lang} track ({have})"}
    if dry_run:
        return {"video_id": video_id, "skipped": "dry run"}
    body = {"snippet": {"videoId": video_id, "language": lang, "name": name, "isDraft": False}}
    res = service.captions().insert(part="snippet", body=body,
                                    media_body=g._media(srt, "application/octet-stream", resumable=False)).execute()
    return {"video_id": video_id, "caption_id": res.get("id")}


def main(argv=None, **injected) -> int:
    ap = argparse.ArgumentParser(description="Upload a caption track to one of our videos (channel-guarded).")
    ap.add_argument("video_id")
    ap.add_argument("srt")
    ap.add_argument("--channel", default="purplelink")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--name", default="English")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    try:
        r = attach(a.video_id, Path(a.srt), a.channel, a.lang, a.name, a.dry_run, **injected)
    except ValueError as e:
        print(f"yt-captions: {e}", file=sys.stderr)
        return 2
    except g.ChannelGuardError as e:
        print(f"yt-captions: refused: {e}", file=sys.stderr)
        return 3
    print(json.dumps(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
