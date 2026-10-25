#!/usr/bin/env python3
"""Publish an iPhone app's prepared YouTube videos when the app goes live on the App Store.

Ben (2026-10-24/25): "release them when the apps release". Publishing these specific videos at release is approved;
the videos stay Private until then (project_watchlight-videos). launchd job com.purplelink.app-release-watch runs this
every hour at :20 through ~/.purplelink/bin/app-release-watch.sh, which uses repo-ro.sh (code from origin/main).

    python3 scripts/app-release-watch.py              run: publish every app that is live and not yet released
    python3 scripts/app-release-watch.py --check      list each app's App Store state and video privacy (read-only)
    python3 scripts/app-release-watch.py --dry-run    print what a run would do (read-only); --assume-live shows the
                                                      plan for an app that is not live yet
    options: --app NAME (one app), --videos-dir DIR, --state-dir DIR

Apps are the files video/out/*/release.json (git-ignored, so read from the shared checkout, not the jobs-ro worktree):
    {"app": "Watchlight", "ascAppId": "6824584515", "descriptionPlaceholder": "App Store link: ADD BEFORE PUBLISHING",
     "long":  {"id": "k_hT8fB5ykM", "thumbs": ["A.jpg", "B.jpg", "C.jpg"], "srt": "optional.srt"},
     "short": {"id": "7-dWXBUwCRw", "srt": "optional.srt"}}
A new app is one more file; nothing here names an app. Relative paths resolve against the file's folder, video/out,
then the repo root.

An app is live when App Store Connect lists an iOS appStoreVersions entry with appStoreState READY_FOR_SALE and
https://apps.apple.com/app/id<ascAppId> answers 200. Then, in this order (each step is remembered, so a retry resumes):
  1. descriptions: the placeholder becomes the App Store link; the Short also gets "Full video: <long video link>"
  2. both videos public (the long one first, so the Short's link works)
  3. Test & Compare thumbnail test on the long video: scripts/yt-abtest.py start <id> A B C (Studio through the
     automation Chrome on port 9340, CDP only; this script sends no keystrokes)
  4. best effort, three tries each: caption tracks (scripts/yt-captions.py), a change-log row, the marketing hub
  5. mark the app released in state.json, send one macOS notification. A released app is never touched again.
Steps 1 and 2 use the YouTube API with the Purplelink token, behind the same checks as scripts/yt_guard.py: the channel
is confirmed in scripts/yt-channels.json, the token's channel is exactly the registry id, and each video belongs to it.
Nothing is made public before App Store Connect says the app is live; no check, no change.

Safety: ~/.purplelink/app-release-watch/PAUSE stops every run (create it to pause, delete it to resume); a lock lets one
run happen at a time; a failure is retried at the next run and notifies after the 3rd in a row (then every 24th).
Exit 0 is a clean run (or paused or busy), 1 means something failed, 2 bad arguments.
State: ~/.purplelink/app-release-watch/state.json. Credentials: ~/.appstoreconnect/globepin.env (never printed).
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import fcntl
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import yt_guard as g  # noqa: E402

REPO_ROOT = HERE.parent
SHARED_REPO = Path("/Volumes/Extreme SSD/Purplelink LLC")
STATE_DIR_DEFAULT = Path.home() / ".purplelink" / "app-release-watch"
ASC_ENV = Path.home() / ".appstoreconnect" / "globepin.env"
CHANGELOG = Path.home() / ".purplelink" / "insights" / "changelog" / "log_change.py"
ASC_BASE = "https://api.appstoreconnect.apple.com"
CHANNEL_KEY = "purplelink"
LIVE_STATE = "READY_FOR_SALE"
NOTIFY_TITLE = "App release watch"
NET_TIMEOUT = 30
ABTEST_TIMEOUT = 20 * 60
BEST_EFFORT = ("captions:long", "captions:short", "changelog", "hub")
REQUIRED = ("desc:long", "desc:short", "public:long", "public:short", "abtest")
BEST_EFFORT_TRIES = 3
FAIL_NOTIFY_AT = 3
FAIL_NOTIFY_EVERY = 24
VIDEO_ID_RX = re.compile(r"[\w-]{11}")


class StepError(Exception):
    """One step failed in a way that a later run may fix. Counts as a failure for the app."""


class BadRelease(ValueError):
    """A release.json that is incomplete or inconsistent (it may still be being written)."""


def now_local() -> dt.datetime:
    return dt.datetime.now().astimezone()


# ------------------------------------------------------------------ release.json

def _resolve(rel, base: Path, videos_dir: Path) -> Path:
    p = Path(os.path.expanduser(str(rel)))
    if p.is_absolute():
        return p
    for root in (base, videos_dir, REPO_ROOT, SHARED_REPO):
        if (root / p).exists():
            return root / p
    return base / p


def load_release(path: Path, videos_dir: Path) -> dict:
    """Parse and validate one release.json. Raises BadRelease with the reason."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise BadRelease(f"cannot read: {e}")
    if not isinstance(raw, dict):
        raise BadRelease("not a JSON object")
    app = raw.get("app")
    if not isinstance(app, str) or not app.strip():
        raise BadRelease("no app name")
    asc = str(raw.get("ascAppId", "")).strip()
    if not asc.isdigit():
        raise BadRelease("ascAppId is missing or not numeric")
    ph = raw.get("descriptionPlaceholder")
    if not isinstance(ph, str) or not ph.strip():
        raise BadRelease("descriptionPlaceholder is missing")
    base = Path(path).parent
    out = {"app": app.strip(), "ascAppId": asc, "placeholder": ph, "file": str(path)}
    for key in ("long", "short"):
        v = raw.get(key)
        if not isinstance(v, dict) or not VIDEO_ID_RX.fullmatch(str(v.get("id", ""))):
            raise BadRelease(f"{key}.id is missing or not a YouTube video id")
        entry = {"id": v["id"], "srt": None}
        if v.get("srt"):
            entry["srt"] = _resolve(v["srt"], base, videos_dir)
        out[key] = entry
    thumbs = raw["long"].get("thumbs")
    if not isinstance(thumbs, list) or len(thumbs) != 3:
        raise BadRelease("long.thumbs must list exactly three images (A, B, C)")
    paths = [_resolve(t, base, videos_dir) for t in thumbs]
    for p in paths:
        if not p.is_file():
            raise BadRelease(f"thumbnail not found: {p}")
        if p.stat().st_size >= 2_000_000:
            raise BadRelease(f"thumbnail is 2 MB or more: {p}")
    out["long"]["thumbs"] = paths
    if out["long"]["id"] == out["short"]["id"]:
        raise BadRelease("long.id and short.id are the same video")
    return out


def find_releases(videos_dir: Path):
    """([valid releases], [(file, reason)]). A duplicated app or ascAppId is reported, not guessed at."""
    good, bad, seen_app, seen_asc = [], [], {}, {}
    for f in sorted(Path(videos_dir).glob("*/release.json")):
        try:
            r = load_release(f, videos_dir)
        except BadRelease as e:
            bad.append((str(f), str(e)))
            continue
        if r["app"] in seen_app or r["ascAppId"] in seen_asc:
            bad.append((str(f), f"duplicates {seen_app.get(r['app']) or seen_asc.get(r['ascAppId'])}"))
            continue
        seen_app[r["app"]] = seen_asc[r["ascAppId"]] = str(f)
        good.append(r)
    return good, bad


# ------------------------------------------------------------------ App Store Connect

def parse_env_file(path: Path) -> dict:
    env = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip().removeprefix("export ").strip()
        env[k] = v.strip().strip("\"'")
    return env


def expand_home(value: str) -> Path:
    home = str(Path.home())
    v = value.replace("${HOME}", home).replace("$HOME", home)
    if v.startswith("~"):
        v = home + v[1:]
    return Path(v)


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def es256_jwt(key_pem: bytes, kid: str, issuer: str, now: float, ttl: int = 600) -> str:
    """ES256 JWT for App Store Connect (aud appstoreconnect-v1, lifetime at most 20 minutes)."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    header = {"alg": "ES256", "kid": kid, "typ": "JWT"}
    payload = {"iss": issuer, "iat": int(now), "exp": int(now) + ttl, "aud": "appstoreconnect-v1"}
    signing = _b64(json.dumps(header, separators=(",", ":")).encode()) + "." + _b64(json.dumps(payload, separators=(",", ":")).encode())
    key = serialization.load_pem_private_key(key_pem, password=None)
    r, s = decode_dss_signature(key.sign(signing.encode(), ec.ECDSA(hashes.SHA256())))
    return signing + "." + _b64(r.to_bytes(32, "big") + s.to_bytes(32, "big"))


class AscClient:
    """Read-only App Store Connect client. The key and the token are never printed or put in an error message."""

    def __init__(self, env_file: Path = ASC_ENV, opener=urllib.request.urlopen, clock=time.time):
        self.env_file, self.opener, self.clock = Path(env_file), opener, clock
        self._token, self._exp = None, 0.0

    def token(self) -> str:
        if self._token and self.clock() < self._exp - 60:
            return self._token
        try:
            env = parse_env_file(self.env_file)
            key = expand_home(env["ASC_KEY_PATH"]).read_bytes()
            self._token = es256_jwt(key, env["ASC_KEY_ID"], env["ASC_ISSUER_ID"], self.clock())
        except (OSError, KeyError) as e:
            raise StepError(f"App Store Connect credentials unreadable ({type(e).__name__})")
        except Exception as e:
            raise StepError(f"could not sign the App Store Connect token ({type(e).__name__})")
        self._exp = self.clock() + 600
        return self._token

    def _get(self, url: str) -> dict:
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.token()}", "Accept": "application/json"})
        try:
            with self.opener(req, timeout=NET_TIMEOUT) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            title = ""
            try:
                title = (json.loads(e.read().decode("utf-8")).get("errors") or [{}])[0].get("title", "")
            except Exception:
                pass
            raise StepError(f"App Store Connect answered HTTP {e.code} {title}".strip())
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise StepError(f"App Store Connect unreachable ({type(e).__name__})")

    def versions(self, app_id: str) -> list:
        """appStoreVersions as [{version, platform, state}]."""
        url = f"{ASC_BASE}/v1/apps/{app_id}/appStoreVersions?limit=200"
        out = []
        for _ in range(5):
            data = self._get(url)
            for it in data.get("data", []):
                a = it.get("attributes") or {}
                out.append({"version": a.get("versionString"), "platform": a.get("platform"),
                            "state": a.get("appStoreState") or a.get("appVersionState")})
            url = (data.get("links") or {}).get("next")
            if not url:
                break
        return out


def live_version(versions: list):
    """The first iOS version whose appStoreState is READY_FOR_SALE, else None."""
    for v in versions:
        if v.get("state") == LIVE_STATE and v.get("platform") in (None, "IOS"):
            return v
    return None


def summarize_versions(versions: list) -> str:
    return ", ".join(f"{v['version']} {v['state']}" for v in versions if v.get("platform") in (None, "IOS")) or "no iOS versions"


def store_url(asc_id: str) -> str:
    return f"https://apps.apple.com/app/id{asc_id}"


def http_status(url: str) -> int:
    """GET and follow redirects; the final status code, or 0 when the request itself failed."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh) Purplelink-release-watch"})
    try:
        with urllib.request.urlopen(req, timeout=NET_TIMEOUT) as r:
            r.read(1)
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


# ------------------------------------------------------------------ YouTube (API, behind the guard's checks)

def get_items(service, ids: list) -> dict:
    items = service.videos().list(part="snippet,status", id=",".join(ids)).execute().get("items", [])
    return {i["id"]: i for i in items}


def new_description(old: str, placeholder: str, link: str, long_url: str = None, app: str = "the app") -> str:
    """Placeholder -> App Store link (idempotent). A description without the placeholder (the Short's real one has
    none) gets "<app> on the App Store: <link>" before its hashtag line. With long_url, the Short also names the
    full video: a "Full how-to"/"Full video" line without a link is rewritten, else a line follows the App Store link."""
    desc = old
    if link not in desc:
        if placeholder in desc:
            desc = desc.replace(placeholder, link)
        else:
            lines = desc.rstrip("\n").split("\n")
            last = len(lines) - 1
            if lines and lines[last].strip() and all(t.startswith("#") for t in lines[last].split()):
                lines[last:last] = [f"{app} on the App Store: {link}", ""]
            else:
                lines += ["", f"{app} on the App Store: {link}"]
            desc = "\n".join(lines)
    if long_url and long_url not in desc:
        m = re.search(r"(?m)^[ \t]*Full (?:video|how-to)\b[^\n]*$", desc)
        if m and not re.search(r"https?://", m.group(0)):
            desc = desc[:m.start()] + f"Full video: {long_url}" + desc[m.end():]
        else:
            lines = desc.split("\n")
            at = next((i for i, ln in enumerate(lines) if link in ln), len(lines) - 1)
            lines.insert(at + 1, f"Full video: {long_url}")
            desc = "\n".join(lines)
    if len(desc.encode("utf-8")) > 5000:
        raise StepError("the new description would be over 5000 bytes")
    if "<" in desc or ">" in desc:
        raise StepError("the new description contains < or >, which YouTube rejects")
    return desc


def _own(item: dict, ch: dict, vid: str):
    owner = ((item or {}).get("snippet") or {}).get("channelId")
    if owner != ch["id"]:
        raise g.ChannelGuardError(f"video {vid} belongs to {owner}, not {ch['id']} ({ch['title']}); not touching it")


def set_description(service, ch, vid, item, desc):
    _own(item, ch, vid)
    sn = item["snippet"]
    body = {"id": vid, "snippet": {"title": sn["title"], "description": desc, "categoryId": sn["categoryId"]}}
    for k in ("tags", "defaultLanguage"):
        if sn.get(k):
            body["snippet"][k] = sn[k]
    service.videos().update(part="snippet", body=body).execute()
    got = get_items(service, [vid]).get(vid) or {}
    if (got.get("snippet") or {}).get("description") != desc:
        raise StepError(f"{vid}: YouTube did not keep the new description")


def make_public(service, ch, vid, item, live_confirmed):
    """The only place a video becomes public. Refuses unless the caller has App Store proof that the app is live."""
    if live_confirmed is not True:
        raise g.ChannelGuardError("refusing to make a video public: the app is not confirmed live")
    _own(item, ch, vid)
    st = item.get("status") or {}
    if st.get("privacyStatus") == "public":
        return
    if st.get("uploadStatus") not in (None, "processed"):
        raise StepError(f"{vid}: YouTube upload status is {st.get('uploadStatus')!r}, not processed yet")
    keep = {k: v for k, v in st.items() if k in
            ("embeddable", "license", "publicStatsViewable", "selfDeclaredMadeForKids", "containsSyntheticMedia")}
    keep["privacyStatus"] = "public"
    service.videos().update(part="status", body={"id": vid, "status": keep}).execute()
    got = get_items(service, [vid]).get(vid) or {}
    if (got.get("status") or {}).get("privacyStatus") != "public":
        raise StepError(f"{vid}: YouTube does not report the video as public after the update")


def _load_module(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ------------------------------------------------------------------ state

def load_state(path: Path) -> dict:
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(d, dict) and isinstance(d.get("apps"), dict):
            return d
    except (OSError, ValueError):
        pass
    return {"version": 1, "apps": {}}


def save_state(path: Path, state: dict):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".state-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=1, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def app_state(state: dict, app: str, asc: str) -> dict:
    st = state["apps"].setdefault(app, {})
    st.setdefault("ascAppId", asc)
    st.setdefault("released", False)
    st.setdefault("failures", 0)
    st.setdefault("steps", {})
    return st


# ------------------------------------------------------------------ the watcher

class Ctx:
    """Everything a run needs, injectable so the tests never touch the network, YouTube or Chrome."""

    def __init__(self, a, *, asc=None, service_factory=None, status_fn=None, run_cmd=None, notify=None,
                 registry=None, out=print):
        self.state_dir = Path(a.state_dir)
        self.state_path = self.state_dir / "state.json"
        self.pause_path = self.state_dir / "PAUSE"
        self.lock_path = self.state_dir / "run.lock"
        self.videos_dir = Path(a.videos_dir)
        self.changelog = Path(a.changelog)
        self.asc = asc or AscClient(Path(a.asc_env))
        self.registry = registry
        self.service_factory = service_factory or self._real_service
        self.status_fn = status_fn or http_status
        self.run_cmd = run_cmd or self._real_run
        self.notify = notify or (lambda msg: g.macos_notify(msg, title=NOTIFY_TITLE))
        self.out = out
        self._service = None
        self._ch = None
        self.python = sys.executable

    def say(self, msg: str):
        self.out(msg)

    def channel(self) -> dict:
        if self._ch is None:
            ch = g.get_channel(CHANNEL_KEY, self.registry if self.registry is not None else g.load_registry())
            g.check_confirmed(ch, CHANNEL_KEY)
            self._ch = ch
        return self._ch

    def service(self):
        """YouTube client for the Purplelink token, after the guard's identity check (token channel == registry id)."""
        if self._service is None:
            ch = self.channel()
            svc = self.service_factory(ch)
            g.verify_identity(svc, ch, CHANNEL_KEY)
            self._service = svc
        return self._service

    @staticmethod
    def _real_service(ch):
        return g.build_service(g.token_path(ch))

    @staticmethod
    def _real_run(cmd, env=None, timeout=ABTEST_TIMEOUT):
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        except subprocess.TimeoutExpired:
            return 124, f"timed out after {timeout} s"
        return p.returncode, (p.stdout or "") + (p.stderr or "")

    @staticmethod
    def tool_env(**extra):
        env = dict(os.environ)
        env.update(extra)
        return env


def plan_steps(ctx: Ctx, rel: dict, st: dict, live_confirmed: bool, dry: bool):
    """Ordered (name, required, fn). Each fn does its work (or, when dry, returns what it would do)."""
    link = store_url(rel["ascAppId"])
    long_id, short_id = rel["long"]["id"], rel["short"]["id"]
    long_url = f"https://youtu.be/{long_id}"
    ids = {"long": long_id, "short": short_id}

    def fetch(key):
        vid = ids[key]
        svc = ctx.service()
        item = get_items(svc, [vid]).get(vid)
        if not item:
            raise StepError(f"{vid} is not on the Purplelink channel (videos.list does not return it)")
        _own(item, ctx.channel(), vid)
        return svc, vid, item

    def desc_step(key):
        def run():
            svc, vid, item = fetch(key)
            old = item["snippet"].get("description", "")
            new = new_description(old, rel["placeholder"], link, long_url if key == "short" else None, rel["app"])
            if new == old:
                return "description already has the link"
            if dry:
                return "would set the description to:\n" + "\n".join("      | " + ln for ln in new.split("\n"))
            set_description(svc, ctx.channel(), vid, item, new)
            return "description updated"
        return run

    def public_step(key):
        def run():
            svc, vid, item = fetch(key)
            now_priv = (item.get("status") or {}).get("privacyStatus")
            if now_priv == "public":
                return "already public"
            if dry:
                return f"would change {now_priv} to public (app confirmed live: {live_confirmed})"
            make_public(svc, ctx.channel(), vid, item, live_confirmed)
            return "made public"
        return run

    def abtest():
        yta = HERE / "yt-abtest.py"
        thumbs = [str(p) for p in rel["long"]["thumbs"]]
        env = ctx.tool_env(YT_ABTEST_LOG=str(ctx.state_dir / "ab-tests.json"))
        if dry:
            return "would run: " + " ".join(["yt-abtest.py", "start", long_id] + [Path(t).name for t in thumbs])
        # A retry may follow a run that pressed Set test but could not confirm it: look before starting a second test.
        if st["steps"].get("abtest", {}).get("attempts"):
            rc, text = ctx.run_cmd([ctx.python, str(yta), "status", long_id], env=env)
            if rc == 0 and re.search(r"running", text, re.I):
                return "a test is already running"
        rc, text = ctx.run_cmd([ctx.python, str(yta), "start", long_id] + thumbs, env=env)
        if rc != 0:
            raise StepError(f"yt-abtest.py start exited {rc}: {text.strip()[-300:]}")
        return "thumbnail test started"

    def captions(key):
        def run():
            srt = rel[key]["srt"]
            if not srt:
                return "no srt listed in release.json; skipped"
            ycap = _load_module("ytcap", "yt-captions.py")
            if dry:
                return f"would upload {srt} if the video has no English track" if ycap.valid_srt(Path(srt)) else f"{srt} is not a valid SubRip file"
            r = ycap.attach(ids[key], Path(srt), CHANNEL_KEY, service=ctx.service(),
                            registry=ctx.registry if ctx.registry is not None else g.load_registry())
            return "captions: " + (r.get("skipped") or f"uploaded {r.get('caption_id')}")
        return run

    def changelog():
        today = now_local().date().isoformat()
        what = f"{rel['app']} launch videos made public on the Purplelink channel (long {long_id}, Short {short_id}) when the app went live on the App Store"
        cmd = [ctx.python, str(ctx.changelog), "add", "--date", today, "--area", "content", "--what", what,
               "--affected", f"the two {rel['app']} launch videos; each description now links {link}",
               "--comparison", "other Purplelink videos that stayed as they were",
               "--metric", f"views and App Store page visits from YouTube for {rel['app']}"]
        if dry:
            return "would log: " + what
        if not ctx.changelog.exists():
            raise StepError(f"change-log tool not found at {ctx.changelog}")
        rc, text = ctx.run_cmd(cmd, env=None, timeout=60)
        if rc != 0:
            raise StepError(f"log_change.py exited {rc}: {text.strip()[-200:]}")
        return "change logged"

    def hub():
        if dry:
            return "would record both videos as placements (state.json) and run hub.py import"
        # the hub reads the git-ignored files (Outreach/, docs/growth-briefs/) from the shared checkout
        env = ctx.tool_env(PURPLELINK_REPO=os.environ.get("PURPLELINK_REPO") or str(SHARED_REPO),
                           PURPLELINK_APP_RELEASE_STATE=str(ctx.state_path))
        rc, text = ctx.run_cmd([ctx.python, str(HERE / "hub" / "hub.py"), "import"], env=env, timeout=600)
        if rc != 0:
            raise StepError(f"hub.py import exited {rc}: {text.strip()[-200:]}")
        return "marketing hub updated"

    return [("desc:long", True, desc_step("long")), ("desc:short", True, desc_step("short")),
            ("public:long", True, public_step("long")), ("public:short", True, public_step("short")),
            ("abtest", True, abtest),
            ("captions:long", False, captions("long")), ("captions:short", False, captions("short")),
            ("changelog", False, changelog), ("hub", False, hub)]


def record_placements(st: dict, rel: dict):
    """What the marketing hub reads (scripts/hub/hub.py, from_app_releases): one placement per public video."""
    st["storeUrl"] = store_url(rel["ascAppId"])
    st.setdefault("placements", [{"video": rel[k]["id"], "kind": k, "date": now_local().date().isoformat()}
                                 for k in ("long", "short")])


def process_app(ctx: Ctx, rel: dict, state: dict, *, dry: bool, assume_live: bool = False) -> bool:
    """One app. Returns True when nothing failed. Never raises for an app-level problem."""
    app = rel["app"]
    st = app_state(state, app, rel["ascAppId"])
    if st["released"]:
        ctx.say(f"{app}: already released ({st.get('releasedAt', '?')}); nothing to do")
        return True
    st["lastCheck"] = now_local().isoformat(timespec="seconds")
    ok = True
    try:
        versions = ctx.asc.versions(rel["ascAppId"])
        live = live_version(versions)
        if not live and not (dry and assume_live):
            ctx.say(f"{app}: not live (App Store Connect: {summarize_versions(versions)}); nothing to do")
            st["failures"], st["lastError"] = 0, ""
            return True
        if live:
            ctx.say(f"{app}: LIVE, version {live['version']} {LIVE_STATE}")
            code = ctx.status_fn(store_url(rel["ascAppId"]))
            if code != 200:
                raise StepError(f"{store_url(rel['ascAppId'])} answered {code or 'no response'}, not 200 yet")
            ctx.say(f"{app}: {store_url(rel['ascAppId'])} answers 200")
        else:
            ctx.say(f"{app}: NOT live (App Store Connect: {summarize_versions(versions)}); showing the plan as if it were (dry run, --assume-live)")
        required_ok = True
        for name, required, fn in plan_steps(ctx, rel, st, bool(live), dry):
            rec = st["steps"].setdefault(name, {"done": False, "attempts": 0})
            if rec.get("done"):
                continue
            if not required_ok:
                ctx.say(f"  {name}: waiting for an earlier step")
                continue
            try:
                msg = fn()
            except Exception as e:  # a failed step is retried by the next run
                if dry:
                    ctx.say(f"  {name}: would fail now: {e}")
                else:
                    rec["attempts"] = rec.get("attempts", 0) + 1
                    rec["error"] = str(e)[:300]
                    ctx.say(f"  {name}: FAILED (try {rec['attempts']}): {e}")
                    save_state(ctx.state_path, state)
                if required:
                    required_ok = False
                    ok = False
                continue
            ctx.say(f"  {name}: {msg}")
            if not dry:
                rec.update(done=True, at=now_local().isoformat(timespec="seconds"), result=msg[:200])
                rec.pop("error", None)
                if name == "public:short":
                    record_placements(st, rel)
                save_state(ctx.state_path, state)
        if dry:
            return ok
        if ok:
            st["failures"], st["lastError"] = 0, ""
        retrying = [n for n in BEST_EFFORT if not st["steps"][n].get("done") and st["steps"][n].get("attempts", 0) < BEST_EFFORT_TRIES]
        if all(st["steps"][n].get("done") for n in REQUIRED) and not retrying:
            gave_up = [n for n in BEST_EFFORT if not st["steps"][n].get("done")]
            st.update(released=True, releasedAt=now_local().isoformat(timespec="seconds"))
            record_placements(st, rel)
            save_state(ctx.state_path, state)
            extra = f" Not done after {BEST_EFFORT_TRIES} tries: {', '.join(gave_up)}." if gave_up else ""
            ctx.notify(f"{app} is live on the App Store. Its two YouTube videos are public and the thumbnail test is running.{extra}")
            ctx.say(f"{app}: released.{extra}")
        return ok
    except Exception as e:
        ok = False
        ctx.say(f"{app}: FAILED: {e}")
        if not dry:
            st["lastError"] = str(e)[:300]
        return False
    finally:
        if not dry:
            if not ok:
                st["failures"] = st.get("failures", 0) + 1
                if not st.get("lastError"):
                    st["lastError"] = "; ".join(f"{n}: {r['error']}" for n, r in st["steps"].items() if r.get("error"))[:300]
                n = st["failures"]
                if n == FAIL_NOTIFY_AT or (n > FAIL_NOTIFY_AT and n % FAIL_NOTIFY_EVERY == 0):
                    ctx.notify(f"{app} release watch has failed {n} runs in a row: {st['lastError'][:160]}")
            save_state(ctx.state_path, state)


# ------------------------------------------------------------------ --check

def do_check(ctx: Ctx, releases: list, bad: list) -> int:
    state = load_state(ctx.state_path)
    ctx.say(f"App release watch {now_local():%Y-%m-%d %H:%M %Z}   PAUSE: {'ON (runs are stopped)' if ctx.pause_path.exists() else 'off'}")
    for f, why in bad:
        ctx.say(f"  ignored {f}: {why}")
    if not releases:
        ctx.say(f"  no usable release.json under {ctx.videos_dir}/*/")
    for rel in releases:
        app = rel["app"]
        st = state["apps"].get(app, {})
        ctx.say(f"{app} (ascAppId {rel['ascAppId']})")
        live = None
        try:
            versions = ctx.asc.versions(rel["ascAppId"])
            live = live_version(versions)
            ctx.say(f"  App Store Connect: {summarize_versions(versions)} -> {'LIVE' if live else 'not live'}")
        except Exception as e:
            ctx.say(f"  App Store Connect: error: {e}")
        if live:
            ctx.say(f"  store page {store_url(rel['ascAppId'])}: HTTP {ctx.status_fn(store_url(rel['ascAppId'])) or 'no response'}")
        else:
            ctx.say("  store page: not checked (app not live)")
        try:
            items = get_items(ctx.service(), [rel["long"]["id"], rel["short"]["id"]])
            for key in ("long", "short"):
                vid = rel[key]["id"]
                it = items.get(vid)
                if not it:
                    ctx.say(f"  {key:5} {vid}: not found on the Purplelink channel")
                    continue
                pv = (it.get("status") or {}).get("privacyStatus")
                own = "" if (it.get("snippet") or {}).get("channelId") == ctx.channel()["id"] else "  WRONG CHANNEL"
                ph = "  placeholder still in description" if rel["placeholder"] in (it["snippet"].get("description") or "") else ""
                ctx.say(f"  {key:5} {vid}: {pv}{ph}{own}  \"{it['snippet'].get('title', '')[:60]}\"")
        except Exception as e:
            ctx.say(f"  videos: error: {e}")
        if st.get("released"):
            ctx.say(f"  watcher: released {st.get('releasedAt')}")
        else:
            done = [n for n, r in st.get("steps", {}).items() if r.get("done")]
            ctx.say(f"  watcher: waiting; {st.get('failures', 0)} failures in a row; steps done: {', '.join(done) or 'none'}"
                    + (f"; last error: {st['lastError']}" if st.get("lastError") else ""))
    return 0


# ------------------------------------------------------------------ run / main

def acquire_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except OSError:
        os.close(fd)
        return None


def parse_args(argv):
    ap = argparse.ArgumentParser(description="Publish an app's prepared YouTube videos when the app goes live on the App Store.")
    ap.add_argument("--check", action="store_true", help="list each app's App Store state and video privacy (read-only)")
    ap.add_argument("--dry-run", action="store_true", help="print what a run would do; changes nothing")
    ap.add_argument("--assume-live", action="store_true", help="with --dry-run: show the plan even if the app is not live")
    ap.add_argument("--app", help="only this app (name as in release.json)")
    ap.add_argument("--videos-dir", default=os.environ.get("PURPLELINK_VIDEO_OUT") or "")
    ap.add_argument("--state-dir", default=os.environ.get("APP_RELEASE_WATCH_DIR") or str(STATE_DIR_DEFAULT))
    ap.add_argument("--asc-env", default=str(ASC_ENV))
    ap.add_argument("--changelog", default=str(CHANGELOG))
    a = ap.parse_args(argv)
    if a.assume_live and not a.dry_run:
        ap.error("--assume-live only works with --dry-run")
    if a.check and a.dry_run:
        ap.error("use --check or --dry-run, not both")
    if not a.videos_dir:
        # video/out is git-ignored: it exists in the shared checkout, not in the jobs-ro worktree
        a.videos_dir = str(next((p for p in (SHARED_REPO / "video" / "out", REPO_ROOT / "video" / "out") if p.is_dir()),
                                SHARED_REPO / "video" / "out"))
    return a


def main(argv=None, **inject) -> int:
    a = parse_args(sys.argv[1:] if argv is None else argv)
    ctx = Ctx(a, **inject)
    raw_say = ctx.out
    ctx.out = raw_say if a.check else (lambda m: raw_say(f"[{now_local():%Y-%m-%d %H:%M:%S}] {m}"))
    releases, bad = find_releases(ctx.videos_dir)
    if a.app:
        releases = [r for r in releases if r["app"].lower() == a.app.lower()]
        if not releases:
            ctx.say(f"no usable release.json for app {a.app!r} under {ctx.videos_dir}")
            return 2
    if a.check:
        return do_check(ctx, releases, bad)
    for f, why in bad:
        ctx.say(f"ignored {f}: {why}")
    if a.dry_run:
        state = load_state(ctx.state_path)
        if ctx.pause_path.exists():
            ctx.say("note: PAUSE is on, so a real run would stop here; this dry run goes on")
        ok = True
        for rel in releases:
            ok = process_app(ctx, rel, state, dry=True, assume_live=a.assume_live) and ok
        ctx.say("dry run: nothing was changed")
        return 0 if ok else 1
    if ctx.pause_path.exists():
        ctx.say(f"paused ({ctx.pause_path} exists); not checking anything")
        return 0
    fd = acquire_lock(ctx.lock_path)
    if fd is None:
        ctx.say("another run holds the lock; skipping this one")
        return 0
    try:
        state = load_state(ctx.state_path)
        if not releases:
            ctx.say(f"no usable release.json under {ctx.videos_dir}; nothing to watch")
        ok = True
        for rel in releases:
            ok = process_app(ctx, rel, state, dry=False) and ok
        save_state(ctx.state_path, state)
        return 0 if ok else 1
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


if __name__ == "__main__":
    sys.exit(main())
