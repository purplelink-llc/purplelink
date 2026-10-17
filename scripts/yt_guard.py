"""Channel guard for YouTube Data API uploads: content must never land on the wrong channel.

Every upload goes through guarded_upload(). All of these are mandatory and raise ChannelGuardError:

  0. confirmed the registry entry must say "confirmed": true (Ben has verified the channel id)
  a. kind      the content kind must be listed for the channel in scripts/yt-channels.json (checked before any API call)
  b. identity  the channel's own token is loaded and channels.list(mine=True) must return exactly one channel whose
               id equals the registry id (checked before any insert)
  c. duplicate a video with exactly this title uploaded to the channel in the last 24 h is returned instead of re-uploaded
  d. upload    resumable, chunked videos.insert (+ optional thumbnails.set)
  e. verify    videos.list on the new id must report the registry channel id; otherwise the video is set Private at once,
               a macOS notification is shown, and the guard raises
  f. lock      one upload at a time across processes (fcntl lock on ~/.purplelink/yt-upload.lock)

Tokens live in ~/.config/purplelink/ and are refused if the registry points inside this (public) repo.
Standard library only at import time; the Google client libraries are imported lazily, so the tests run without them.
Services, the notifier, the lock path and the registry are injectable so tests never touch the network.
"""
import datetime
import fcntl
import json
import os
import re
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = Path(__file__).resolve().parent / "yt-channels.json"
LOCK_PATH = Path.home() / ".purplelink" / "yt-upload.lock"
CLIENT_SECRET_PATH = Path.home() / ".tiktok_pipeline" / "youtube_client_secret.json"

# upload scope publishes; force-ssl is needed for channels.list(mine), videos.list/update and thumbnails.set.
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

UPLOAD_CHUNK_BYTES = 16 * 1024 * 1024
UPLOAD_CHUNK_RETRIES = 5
DUPLICATE_WINDOW_HOURS = 24
LOOKUP_RETRIES = 2
LOOKUP_WAIT_SECONDS = 6
VERIFY_RETRIES = 4
VERIFY_WAIT_SECONDS = 5
LOCK_TIMEOUT_SECONDS = 3 * 3600
SYNTHETIC_KINDS = {"ambient", "photo-quiz"}
PRIVACY = ("public", "unlisted", "private")


class ChannelGuardError(Exception):
    """A guard check failed. Nothing wrong was uploaded (or the wrong upload was set Private). CLI exit code 3."""


class UploadArgsError(ValueError):
    """The request itself is malformed (bad title, privacy, publish time...). CLI exit code 2."""


class UploadCapError(Exception):
    """YouTube refused for quota or the daily upload cap. CLI exit code 4."""


# ---------------------------------------------------------------- registry

def load_registry(path=None):
    path = Path(path) if path else REGISTRY_PATH
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        channels = data["channels"]
    except (OSError, ValueError, KeyError) as e:
        raise ChannelGuardError(f"cannot read the channel registry {path}: {e}")
    seen = {}
    for key, ch in channels.items():
        for field in ("id", "title", "token", "kinds", "default_category"):
            if field not in ch:
                raise ChannelGuardError(f"registry channel {key!r} has no {field!r}")
        if not re.fullmatch(r"UC[\w-]{22}", ch["id"]):
            raise ChannelGuardError(f"registry channel {key!r} has a malformed id {ch['id']!r}")
        if ch["id"] in seen:
            raise ChannelGuardError(f"channels {seen[ch['id']]!r} and {key!r} share the id {ch['id']}")
        seen[ch["id"]] = key
        tp = token_path(ch)
        if _inside(tp, REPO_ROOT):
            raise ChannelGuardError(f"token path for {key!r} is inside the repo ({tp}); tokens must live in ~/.config/purplelink/")
    return channels


def _inside(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def token_path(ch):
    return Path(os.path.expanduser(ch["token"]))


def get_channel(key, registry=None):
    channels = registry if registry is not None else load_registry()
    if key not in channels:
        raise ChannelGuardError(f"unknown channel {key!r}; known: {', '.join(sorted(channels))}. Add new channels to scripts/yt-channels.json")
    return channels[key]


# ---------------------------------------------------------------- checks

def check_confirmed(ch, key):
    """Refuse a channel whose registry entry Ben has not confirmed. Pure: no API call."""
    if ch.get("confirmed") is not True:
        raise ChannelGuardError(f"channel not confirmed by Ben in yt-channels.json ({key!r}, {ch['id']}); not uploading")


def check_kind(ch, key, kind):
    """Check a. Pure: no API call."""
    if kind not in ch["kinds"]:
        raise ChannelGuardError(
            f"kind {kind!r} is not allowed on channel {key!r} ({ch['title']}); its kinds are: {', '.join(ch['kinds'])}")


def build_service(tpath, scopes=None):
    """Load the token, refresh it if needed, and return a youtube v3 client."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    tpath = Path(tpath)
    if not tpath.exists():
        raise ChannelGuardError(f"no token at {tpath}; run scripts/yt-login.py --channel <key> first")
    creds = Credentials.from_authorized_user_file(str(tpath), scopes)
    if not creds.valid:
        if not creds.refresh_token:
            raise ChannelGuardError(f"token {tpath} has no refresh token; run scripts/yt-login.py again")
        try:
            creds.refresh(Request())
        except Exception as e:
            raise ChannelGuardError(f"token {tpath} could not be refreshed ({e}); run scripts/yt-login.py again")
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def mine(service):
    """The channels the token owns, as [{id, title}]."""
    items = service.channels().list(part="id,snippet", mine=True).execute().get("items", [])
    return [{"id": i.get("id"), "title": (i.get("snippet") or {}).get("title", "")} for i in items]


def verify_identity(service, ch, key):
    """Check b. Exactly one channel, and it is the registry's. Returns its title."""
    found = mine(service)
    if len(found) != 1:
        names = ", ".join(f"{c['id']} ({c['title']})" for c in found) or "none"
        raise ChannelGuardError(f"token for {key!r} returned {len(found)} channels ({names}); expected exactly one: {ch['id']}")
    got = found[0]
    if got["id"] != ch["id"]:
        raise ChannelGuardError(
            f"token for {key!r} belongs to {got['id']} ({got['title']}), not {ch['id']} ({ch['title']}); not uploading")
    return got["title"]


def recent_upload_with_title(service, title, hours=DUPLICATE_WINDOW_HOURS, now=None):
    """Video id of an upload on this channel with exactly this title in the last `hours`, else None. Never raises."""
    try:
        chan = service.channels().list(part="contentDetails", mine=True).execute()
        uploads = chan["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        items = service.playlistItems().list(part="snippet", playlistId=uploads, maxResults=25).execute().get("items", [])
    except Exception:
        return None
    now = now or datetime.datetime.now(datetime.timezone.utc)
    want = (title or "").strip()
    for it in items:
        sn = it.get("snippet", {})
        if (sn.get("title") or "").strip() != want:
            continue
        try:
            when = datetime.datetime.fromisoformat(sn["publishedAt"].replace("Z", "+00:00"))
        except Exception:
            continue
        if now - when <= datetime.timedelta(hours=hours):
            return (sn.get("resourceId") or {}).get("videoId")
    return None


def _already_up(service, title, retries=0, sleep=time.sleep):
    for attempt in range(retries + 1):
        vid = recent_upload_with_title(service, title)
        if vid or attempt == retries:
            return vid
        sleep(LOOKUP_WAIT_SECONDS)


# ---------------------------------------------------------------- lock

class UploadLock:
    """Cross-process lock: two uploads never overlap. Blocks (polling) up to `timeout`, then raises."""

    def __init__(self, path=None, timeout=LOCK_TIMEOUT_SECONDS, sleep=time.sleep):
        self.path = Path(path) if path else LOCK_PATH
        self.timeout = timeout
        self.sleep = sleep
        self.fd = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(str(self.path), os.O_RDWR | os.O_CREAT, 0o600)
        waited = 0.0
        while True:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except OSError:
                if waited >= self.timeout:
                    os.close(self.fd)
                    self.fd = None
                    raise ChannelGuardError(f"another YouTube upload held {self.path} for over {int(self.timeout)} s; not uploading")
                self.sleep(5)
                waited += 5

    def __exit__(self, *exc):
        if self.fd is not None:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
            finally:
                os.close(self.fd)
                self.fd = None
        return False


# ---------------------------------------------------------------- notify

def macos_notify(message, title="YouTube guard"):
    esc = lambda s: str(s).replace("\\", "\\\\").replace('"', '\\"')
    try:
        subprocess.run(["osascript", "-e", f'display notification "{esc(message)}" with title "{esc(title)}"'],
                       check=False, timeout=15)
    except Exception:
        pass


# ---------------------------------------------------------------- upload

def normalize_publish_at(value):
    """ISO 8601 with an explicit offset (or Z) -> RFC 3339 UTC, which is what the API wants."""
    try:
        when = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise UploadArgsError(f"--publish-at is not an ISO 8601 time: {value!r}")
    if when.tzinfo is None:
        raise UploadArgsError("--publish-at needs a UTC offset (for example 2026-10-20T15:00:00-04:00 or ...Z)")
    return when.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def build_body(ch, kind, title, description="", tags=None, category=None, privacy="unlisted",
               publish_at=None, synthetic=None):
    title = (title or "").strip()
    if not title or len(title) > 100 or "<" in title or ">" in title:
        raise UploadArgsError("title must be 1 to 100 characters and contain no < or >")
    if len(description.encode("utf-8")) > 5000:
        raise UploadArgsError("description is over 5000 bytes")
    if privacy not in PRIVACY:
        raise UploadArgsError(f"privacy must be one of {', '.join(PRIVACY)}")
    status = {"privacyStatus": privacy, "selfDeclaredMadeForKids": False,
              "containsSyntheticMedia": (kind in SYNTHETIC_KINDS) if synthetic is None else bool(synthetic)}
    if publish_at:
        if privacy != "private":
            raise UploadArgsError("--publish-at requires --privacy private (YouTube publishes it at that time)")
        status["publishAt"] = normalize_publish_at(publish_at)
    tags = [t.strip() for t in (tags or []) if t.strip()]
    if sum(len(t) + 1 for t in tags) > 480:
        raise UploadArgsError("tags are over 500 characters in total")
    return {"snippet": {"title": title, "description": description, "tags": tags,
                        "categoryId": str(category or ch["default_category"])},
            "status": status}


def _status_of(exc):
    return getattr(getattr(exc, "resp", None), "status", None)


def _is_cap(exc):
    low = str(exc).lower()
    return (_status_of(exc) == 429 or "quotaexceeded" in low or "uploadlimitexceeded" in low
            or "exceeded the number of videos" in low or "upload limit" in low)


def upload_in_chunks(request):
    response = None
    while response is None:
        _status, response = request.next_chunk(num_retries=UPLOAD_CHUNK_RETRIES)
    return response


def _media(path, mimetype, chunk=UPLOAD_CHUNK_BYTES, resumable=True):
    from googleapiclient.http import MediaFileUpload
    return MediaFileUpload(str(path), mimetype=mimetype, resumable=resumable,
                           chunksize=chunk if resumable else -1)


def verify_landed(service, video_id, ch, key, notify=macos_notify, sleep=time.sleep):
    """Check e. Returns the videos.list item. On a wrong channel: Private at once, notify, raise."""
    item = None
    for attempt in range(VERIFY_RETRIES):
        items = service.videos().list(part="snippet,status", id=video_id).execute().get("items", [])
        if items:
            item = items[0]
            break
        if attempt < VERIFY_RETRIES - 1:
            sleep(VERIFY_WAIT_SECONDS)
    if item is None:
        raise ChannelGuardError(f"video {video_id} was uploaded but videos.list does not return it, so its channel is unverified; check Studio")
    landed = (item.get("snippet") or {}).get("channelId")
    if landed != ch["id"]:
        st = item.get("status") or {}
        keep = {k: v for k, v in st.items() if k in
                ("embeddable", "license", "publicStatsViewable", "selfDeclaredMadeForKids", "containsSyntheticMedia")}
        keep["privacyStatus"] = "private"
        problem = ""
        try:
            service.videos().update(part="status", body={"id": video_id, "status": keep}).execute()
        except Exception as e:
            problem = f" AND setting it Private failed ({e}); set it Private in Studio now"
        notify(f"YouTube guard: {video_id} landed on the wrong channel, set Private")
        raise ChannelGuardError(
            f"video {video_id} landed on channel {landed}, not {ch['id']} ({ch['title']}) for {key!r}; set Private{problem}")
    return item


def guarded_upload(channel_key, kind, path, title, description="", tags=None, category=None, privacy="unlisted",
                   publish_at=None, thumbnail=None, synthetic=None, *, registry=None, service=None,
                   notify=macos_notify, lock_path=None, media_factory=None, sleep=time.sleep,
                   lock_timeout=LOCK_TIMEOUT_SECONDS):
    """Upload `path` to the channel `channel_key` with every guard. Returns
    {id, url, channel_id, channel_title, privacy, duplicate, thumbnail}."""
    channels = registry if registry is not None else load_registry()
    ch = get_channel(channel_key, channels)
    check_confirmed(ch, channel_key)
    check_kind(ch, channel_key, kind)                                    # a. before any API call
    path = Path(path)
    if not path.is_file():
        raise UploadArgsError(f"no such file: {path}")
    if thumbnail and not Path(thumbnail).is_file():
        raise UploadArgsError(f"no such thumbnail: {thumbnail}")
    body = build_body(ch, kind, title, description, tags, category, privacy, publish_at, synthetic)
    media_factory = media_factory or _media

    with UploadLock(lock_path, timeout=lock_timeout, sleep=sleep):       # f.
        if service is None:
            service = build_service(token_path(ch))
        channel_title = verify_identity(service, ch, channel_key)        # b. before any insert
        vid = _already_up(service, body["snippet"]["title"])             # c.
        duplicate = bool(vid)
        if not vid:
            vid = _insert(service, body, path, media_factory, sleep)     # d.
        item = verify_landed(service, vid, ch, channel_key, notify, sleep)   # e.
        thumb_ok = None
        if thumbnail and not duplicate:
            try:
                service.thumbnails().set(videoId=vid, media_body=media_factory(thumbnail, "image/jpeg", resumable=False)).execute()
                thumb_ok = True
            except Exception as e:
                thumb_ok = False
                notify(f"YouTube guard: uploaded {vid} but the thumbnail failed ({str(e)[:80]})", title="YouTube upload")
        return {"id": vid, "url": f"https://youtu.be/{vid}", "channel_id": item["snippet"]["channelId"],
                "channel_title": item["snippet"].get("channelTitle") or channel_title,
                "privacy": (item.get("status") or {}).get("privacyStatus"),
                "duplicate": duplicate, "thumbnail": thumb_ok}


def _insert(service, body, path, media_factory, sleep):
    title = body["snippet"]["title"]
    try:
        media = media_factory(path, "video/*")
        request = service.videos().insert(part="snippet,status", body=body, media_body=media)
        return upload_in_chunks(request)["id"]
    except Exception as e:
        if _is_cap(e):
            raise UploadCapError(str(e))
        status = _status_of(e)
        # 410, 5xx and dropped connections can arrive after YouTube stored the video: look before failing.
        if status is None or status == 410 or status >= 500:
            vid = _already_up(service, title, retries=LOOKUP_RETRIES, sleep=sleep)
            if vid:
                return vid
        raise


def dry_run(channel_key, kind, *, registry=None, service=None, **_unused):
    """Checks a and b only. Returns (channel dict, channel title)."""
    channels = registry if registry is not None else load_registry()
    ch = get_channel(channel_key, channels)
    check_confirmed(ch, channel_key)
    check_kind(ch, channel_key, kind)
    if service is None:
        service = build_service(token_path(ch))
    return ch, verify_identity(service, ch, channel_key)
