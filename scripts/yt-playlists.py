#!/usr/bin/env python3
"""Create or update the ambient channel's playlists through the guarded YouTube API path (the same registry, token identity and lock as yt-api-upload.py).

  python3 scripts/yt-playlists.py --plan plan.json [--channel pixelhearth] [--kind ambient] [--privacy private|unlisted|public] [--apply]

The plan comes from tools/chiptune-radio/playlists.py (`--out plan.json`): {"playlists": [{"title", "description", "videos": [{"slug", "title", "video_id"?}]}]}.
It only reads YouTube unless --apply is given: without it the script runs the checks, looks up what exists and prints what it would do.

What it does, in order, and the guards:
  - the channel must be in scripts/yt-channels.json with "confirmed": true and the kind must be one the channel may carry (before any API call);
  - the channel's own token is loaded and channels.list(mine=True) must return exactly the registry id (before any write);
  - playlists are matched by exact title, so running it twice changes nothing; a playlist that is missing is created Private, its channel is read back (a
    playlist on any other channel is set Private and the run fails), and only then is it given the visibility asked for (--privacy, default private);
  - a video is found by its exact title among the channel's own uploads (or by "video_id" in the plan, which must belong to the channel), so a video from another
    channel can never be added; videos not uploaded yet are listed as missing and skipped; a playlist with no uploaded video is not created;
  - videos are only ever added, never removed or reordered; an existing playlist's visibility is changed only if --privacy is passed and differs.

Exit codes: 0 ok, 1 failed, 2 bad arguments, 3 a guard check failed, 4 YouTube quota or cap. Playlist inserts cost 50 quota units each (a day is 10,000).
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yt_guard as g  # noqa: E402

PAGES_MAX = 20


def _pages(call, **kw):
    """Every item of a paged list call (50 at a time), up to PAGES_MAX pages."""
    token = None
    for _ in range(PAGES_MAX):
        resp = call(**kw, **({"pageToken": token} if token else {})).execute()
        yield from resp.get("items", [])
        token = resp.get("nextPageToken")
        if not token:
            return


def uploads_by_title(service):
    """{exact title: video id} for the token's own channel, newest first (the first of two equal titles wins)."""
    chan = service.channels().list(part="contentDetails", mine=True).execute()
    uploads = chan["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    out = {}
    for it in _pages(service.playlistItems().list, part="snippet", playlistId=uploads, maxResults=50):
        sn = it.get("snippet", {})
        vid = (sn.get("resourceId") or {}).get("videoId")
        if vid:
            out.setdefault((sn.get("title") or "").strip(), vid)
    return out


def playlists_by_title(service, ch, key):
    """{exact title: {id, privacy, description}} for the channel's playlists. A playlist reported on another channel is a guard failure."""
    out = {}
    for it in _pages(service.playlists().list, part="snippet,status", mine=True, maxResults=50):
        sn = it.get("snippet", {})
        if sn.get("channelId") not in (None, ch["id"]):
            raise g.ChannelGuardError(f"playlists.list(mine) for {key!r} returned a playlist of channel {sn.get('channelId')}, not {ch['id']}")
        out.setdefault((sn.get("title") or "").strip(),
                       {"id": it["id"], "privacy": (it.get("status") or {}).get("privacyStatus"), "description": sn.get("description", "")})
    return out


def playlist_video_ids(service, playlist_id):
    return {(it.get("snippet", {}).get("resourceId") or {}).get("videoId")
            for it in _pages(service.playlistItems().list, part="snippet", playlistId=playlist_id, maxResults=50)}


def video_on_channel(service, video_id, ch):
    items = service.videos().list(part="snippet", id=video_id).execute().get("items", [])
    return bool(items) and (items[0].get("snippet") or {}).get("channelId") == ch["id"]


def _guard_call(fn):
    try:
        return fn()
    except g.ChannelGuardError:
        raise
    except Exception as e:
        if g._is_cap(e):
            raise g.UploadCapError(str(e))
        raise


def create_private(service, ch, key, title, description, notify):
    """Insert a Private playlist, then read its channel back. A playlist on any other channel is set Private again and the guard raises."""
    body = {"snippet": {"title": title, "description": description}, "status": {"privacyStatus": "private"}}
    pid = service.playlists().insert(part="snippet,status", body=body).execute()["id"]
    items = service.playlists().list(part="snippet,status", id=pid).execute().get("items", [])
    landed = ((items[0].get("snippet") or {}).get("channelId")) if items else None
    if landed != ch["id"]:
        problem = ""
        try:
            service.playlists().update(part="status", body={"id": pid, "status": {"privacyStatus": "private"}}).execute()
        except Exception as e:
            problem = f" AND setting it Private failed ({e}); set it Private in Studio now"
        notify(f"YouTube guard: playlist {pid} landed on the wrong channel, set Private")
        raise g.ChannelGuardError(f"playlist {pid} landed on channel {landed}, not {ch['id']} ({ch['title']}) for {key!r}; set Private{problem}")
    return pid


def run(plan, channel_key="pixelhearth", kind="ambient", privacy=None, apply=False, *, registry=None, service=None,
        notify=g.macos_notify, lock_path=None, lock_timeout=g.LOCK_TIMEOUT_SECONDS, sleep=time.sleep):
    """Returns {"channel", "actions": [{"playlist", "action", "detail"}], "missing": [{"playlist", "slug", "title"}]}. Without `apply` nothing is written."""
    if privacy is not None and privacy not in g.PRIVACY:
        raise g.UploadArgsError(f"privacy must be one of {', '.join(g.PRIVACY)}")
    lists = plan.get("playlists") if isinstance(plan, dict) else None
    if not isinstance(lists, list):
        raise g.UploadArgsError('the plan must be {"playlists": [...]}')
    for p in lists:
        if not (p.get("title") or "").strip() or len(p["title"]) > 150 or not isinstance(p.get("videos"), list):
            raise g.UploadArgsError(f"bad playlist entry: {p.get('title')!r}")
        if len(p.get("description", "")) > 5000 or "<" in p["title"] or ">" in p["title"]:
            raise g.UploadArgsError(f"bad playlist title or description: {p['title']!r}")
    channels = registry if registry is not None else g.load_registry()
    ch = g.get_channel(channel_key, channels)
    g.check_confirmed(ch, channel_key)
    g.check_kind(ch, channel_key, kind)                                    # before any API call
    report = {"channel": None, "actions": [], "missing": []}
    with g.UploadLock(lock_path, timeout=lock_timeout, sleep=sleep):       # one YouTube write job at a time, with the uploads
        if service is None:
            service = g.build_service(g.token_path(ch))
        report["channel"] = g.verify_identity(service, ch, channel_key)    # before any write
        titles = uploads_by_title(service)
        existing = playlists_by_title(service, ch, channel_key)
        for p in lists:
            title = p["title"].strip()
            desc = p.get("description", "")
            ids, seen = [], set()
            for v in p["videos"]:
                vid = v.get("video_id") or titles.get((v.get("title") or "").strip())
                if vid and v.get("video_id") and not _guard_call(lambda: video_on_channel(service, vid, ch)):
                    raise g.ChannelGuardError(f"video {vid} in playlist {title!r} is not on channel {ch['id']} ({ch['title']}); not adding it")
                if not vid:
                    report["missing"].append({"playlist": title, "slug": v.get("slug", ""), "title": v.get("title", "")})
                elif vid not in seen:
                    seen.add(vid)
                    ids.append(vid)
            cur = existing.get(title)
            if cur is None and not ids:
                report["actions"].append({"playlist": title, "action": "skip", "detail": "no uploaded video yet, not created"})
                continue
            if cur is None:
                want = privacy or "private"
                report["actions"].append({"playlist": title, "action": "create", "detail": f"{want}, {len(ids)} videos"})
                if not apply:
                    continue
                pid = _guard_call(lambda: create_private(service, ch, channel_key, title, desc, notify))
                if want != "private":                                      # only now, on the verified channel, the visibility asked for
                    service.playlists().update(part="snippet,status", body={"id": pid, "snippet": {"title": title, "description": desc},
                                                                           "status": {"privacyStatus": want}}).execute()
                have = set()
            else:
                pid = cur["id"]
                have = playlist_video_ids(service, pid)
                changes = []
                if desc and desc != cur["description"]:
                    changes.append("description")
                if privacy and privacy != cur["privacy"]:
                    changes.append(f"visibility {cur['privacy']} -> {privacy}")
                if changes:
                    report["actions"].append({"playlist": title, "action": "update", "detail": ", ".join(changes)})
                    if apply:
                        body = {"id": pid, "snippet": {"title": title, "description": desc or cur["description"]},
                                "status": {"privacyStatus": privacy or cur["privacy"]}}
                        _guard_call(lambda: service.playlists().update(part="snippet,status", body=body).execute())
            for vid in ids:
                if vid in have:
                    continue
                report["actions"].append({"playlist": title, "action": "add", "detail": vid})
                if apply:
                    body = {"snippet": {"playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": vid}}}
                    _guard_call(lambda: service.playlistItems().insert(part="snippet", body=body).execute())
    return report


def main(argv=None, **injected):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", required=True, help="the JSON written by tools/chiptune-radio/playlists.py --out")
    ap.add_argument("--channel", default="pixelhearth", help="registry key in scripts/yt-channels.json")
    ap.add_argument("--kind", default="ambient")
    ap.add_argument("--privacy", choices=g.PRIVACY, default=None, help="visibility for new playlists (default private); changes an existing playlist only if given")
    ap.add_argument("--apply", action="store_true", help="make the changes; without it the script only reads YouTube and prints the plan")
    a = ap.parse_args(argv)
    try:
        with open(a.plan, encoding="utf-8") as f:
            plan = json.load(f)
        rep = run(plan, a.channel, a.kind, a.privacy, a.apply, **injected)
    except g.UploadArgsError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as e:
        print(f"error: cannot read the plan: {e}", file=sys.stderr)
        return 2
    except g.ChannelGuardError as e:
        print(f"CHANNEL GUARD: {e}", file=sys.stderr)
        return 3
    except g.UploadCapError as e:
        print(f"YouTube quota or cap: {e}", file=sys.stderr)
        return 4
    except Exception as e:  # network, HttpError, anything else
        print(f"failed: {e}", file=sys.stderr)
        return 1
    print(f"verified channel: {rep['channel']}")
    print(("applied" if a.apply else "dry run (nothing written; pass --apply)") + f": {len(rep['actions'])} actions")
    for x in rep["actions"]:
        print(f"  {x['action']:6} {x['playlist']}: {x['detail']}")
    for m in rep["missing"]:
        print(f"  missing (not uploaded yet): {m['slug']} {m['title']!r} for {m['playlist']!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
