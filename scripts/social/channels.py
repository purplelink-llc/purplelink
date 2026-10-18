"""Channel adapters. Each one posts only as the pinned company account and checks that identity twice: before it
creates anything and again right before it publishes. Any mismatch raises Refused (the poster exits 4, notifies,
logs, and does not retry that channel for the rest of the day). No adapter replies, likes, follows or sends DMs.

A channel is enabled only when its pin in core.PINS is filled in AND ~/.config/purplelink/social/<channel>.json
exists with mode 600. Tokens are never printed.
"""
from __future__ import annotations

import datetime as dt
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import quote, urlsplit

from core import URL_RE, Refused, Skip, load_config, now, pin, pinned, save_config

ROOT = Path(__file__).resolve().parents[2]


class Channel:
    name = ""

    def __init__(self, http, cfg: dict, sleep=time.sleep):
        self.http, self.cfg, self.sleep = http, cfg, sleep
        self.pin = pin(self.name)

    # -- identity
    def whoami(self) -> tuple[str, str]:
        raise NotImplementedError

    def check_identity(self, stage: str) -> None:
        try:
            got_id, got_handle = self.whoami()
        except Refused:
            raise
        except Exception as e:  # an unreadable identity is a refusal, never a pass
            raise Refused(f"{self.name}: identity check failed at {stage}: {type(e).__name__}")
        want_id, want_handle = str(self.pin.get("id")), str(self.pin.get("handle"))
        cfg_id, cfg_handle = str(self.cfg.get("id", "")), str(self.cfg.get("handle", ""))
        if str(got_id) != want_id or str(got_handle).lower() != want_handle.lower():
            raise Refused(f"{self.name}: {stage} identity is {got_handle!r} ({got_id}), not the pinned company "
                          f"account {want_handle!r} ({want_id})")
        if cfg_id != want_id or cfg_handle.lower() != want_handle.lower():
            raise Refused(f"{self.name}: the config names {cfg_handle!r} ({cfg_id}), not the pinned account")

    # -- posting
    def preflight(self) -> None:
        """Quota and other checks that need no identity (raise Skip)."""

    def prepare(self, text: str, extra: dict):
        return None

    def publish(self, text: str, extra: dict, prepared) -> str:
        raise NotImplementedError

    def post(self, text: str, extra: dict) -> str:
        self.check_identity("before create")
        self.preflight()
        prepared = self.prepare(text, extra)
        self.check_identity("before publish")
        return self.publish(text, extra, prepared)

    def _ok(self, r, what: str):
        if r.status in (429,):
            raise Skip(f"{self.name}: rate limited at {what}")
        if r.status >= 400 or r.status == 0:
            raise RuntimeError(f"{self.name}: {what} answered {r.status}")
        return r.json()


# ---------------------------------------------------------------- Threads
class Threads(Channel):
    """Threads Graph API. Ben's own Meta app with the company profile as a Threads Tester (no app review)."""
    name = "threads"

    @property
    def base(self):
        return self.cfg.get("api_base", "https://graph.threads.net/v1.0").rstrip("/")

    def _get(self, path: str, **params):
        params["access_token"] = self.cfg["access_token"]
        q = "&".join(f"{k}={quote(str(v), safe=',')}" for k, v in params.items())
        return self.http.request("GET", f"{self.base}/{path}?{q}")

    def whoami(self):
        d = self._ok(self._get("me", fields="id,username"), "GET /me")
        return str(d["id"]), d["username"]

    def preflight(self):
        exp = self.cfg.get("expires_at")
        if exp and dt.datetime.fromisoformat(exp) <= now():
            raise Skip("threads: token expired; run poster.py refresh threads after a new login")
        d = self._ok(self._get(f"{self.pin['id']}/threads_publishing_limit", fields="quota_usage,config"), "quota")
        row = (d.get("data") or [{}])[0]
        used, total = row.get("quota_usage", 0), (row.get("config") or {}).get("quota_total", 250)
        if used >= total:
            raise Skip(f"threads: publishing quota used up ({used} of {total} in 24 h)")

    def prepare(self, text, extra):
        if len(URL_RE.findall(text)) > 5:
            raise Skip("threads: more than 5 links")
        r = self.http.request("POST", f"{self.base}/{self.pin['id']}/threads",
                              form={"media_type": "TEXT", "text": text, "access_token": self.cfg["access_token"]})
        cid = self._ok(r, "create container").get("id")
        if not cid:
            raise RuntimeError("threads: no container id")
        self.sleep(30)  # Meta: wait about 30 s before publishing a container
        return cid

    def publish(self, text, extra, cid):
        r = self.http.request("POST", f"{self.base}/{self.pin['id']}/threads_publish",
                              form={"creation_id": cid, "access_token": self.cfg["access_token"]})
        mid = self._ok(r, "publish").get("id")
        d = self._ok(self._get(str(mid), fields="id,permalink,username"), "read back")
        if str(d.get("username", "")).lower() != str(self.pin["handle"]).lower():
            raise Refused(f"threads: published post reads back as {d.get('username')!r}")
        return d.get("permalink") or f"https://www.threads.com/@{self.pin['handle']}"

    def refresh(self) -> str:
        """Long-lived tokens last 60 days; a token at least 24 h old can be refreshed for another 60."""
        r = self.http.request("GET", "https://graph.threads.net/refresh_access_token?grant_type=th_refresh_token"
                              f"&access_token={quote(self.cfg['access_token'])}")
        d = self._ok(r, "refresh")
        self.cfg["access_token"] = d["access_token"]
        self.cfg["expires_at"] = (now() + dt.timedelta(seconds=int(d.get("expires_in", 5184000)))).isoformat()
        save_config(self.name, self.cfg)
        return self.cfg["expires_at"]


# ---------------------------------------------------------------- Bluesky
class Bluesky(Channel):
    """AT Protocol with an app password (never the account password). Link-card embed."""
    name = "bluesky"

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.jwt = None

    @property
    def pds(self):
        return self.cfg.get("pds", "https://bsky.social").rstrip("/")

    def _session(self):
        r = self.http.request("POST", f"{self.pds}/xrpc/com.atproto.server.createSession",
                              json_body={"identifier": self.pin["handle"], "password": self.cfg["app_password"]})
        d = self._ok(r, "createSession")
        if str(d.get("did")) != str(self.pin["id"]):
            raise Refused(f"bluesky: session DID {d.get('did')!r} is not the pinned company DID")
        self.jwt = d["accessJwt"]

    def whoami(self):
        if not self.jwt:
            self._session()
        r = self.http.request("GET", f"{self.pds}/xrpc/com.atproto.server.getSession",
                              headers={"Authorization": f"Bearer {self.jwt}"})
        d = self._ok(r, "getSession")
        return d["did"], d["handle"]

    @staticmethod
    def facets(text: str) -> list:
        out, raw = [], text.encode("utf-8")
        for m in URL_RE.finditer(text):
            start = len(text[:m.start()].encode("utf-8"))
            end = start + len(m.group(0).encode("utf-8"))
            assert raw[start:end].decode() == m.group(0)
            out.append({"index": {"byteStart": start, "byteEnd": end},
                        "features": [{"$type": "app.bsky.richtext.facet#link", "uri": m.group(0)}]})
        return out

    def prepare(self, text, extra):
        links = URL_RE.findall(text)
        if not links:
            return None
        card = {"uri": links[-1], "title": extra.get("title", "")[:300], "description": extra.get("description", "")[:300]}
        img = extra.get("og_image")
        if img:
            try:
                r = self.http.request("GET", img)
                ctype = r.headers.get("content-type", "image/png").split(";")[0]
                if r.status == 200 and ctype.startswith("image/") and len(r.body) < 950_000:
                    up = self.http.request("POST", f"{self.pds}/xrpc/com.atproto.repo.uploadBlob", data=r.body,
                                           headers={"Authorization": f"Bearer {self.jwt}", "Content-Type": ctype})
                    if up.status == 200:
                        card["thumb"] = up.json()["blob"]
            except Exception:
                pass  # a card without a picture is fine
        return {"$type": "app.bsky.embed.external", "external": card}

    def publish(self, text, extra, embed):
        record = {"$type": "app.bsky.feed.post", "text": text, "createdAt": dt.datetime.now(dt.timezone.utc)
                  .isoformat().replace("+00:00", "Z"), "langs": ["en"], "facets": self.facets(text)}
        if embed:
            record["embed"] = embed
        r = self.http.request("POST", f"{self.pds}/xrpc/com.atproto.repo.createRecord",
                              headers={"Authorization": f"Bearer {self.jwt}"},
                              json_body={"repo": self.pin["id"], "collection": "app.bsky.feed.post", "record": record})
        uri = self._ok(r, "createRecord")["uri"]
        return f"https://bsky.app/profile/{self.pin['handle']}/post/{uri.rsplit('/', 1)[-1]}"


# ---------------------------------------------------------------- X
class X(Channel):
    """X API v2. Pay-per-use since 2026: a post with a link costs $0.20 and each identity read about $0.01
    (docs.x.com/x-api/getting-started/pricing, read 2026-10-18). Disabled unless the config sets
    "paid_posting_ok": true after Ben buys credits."""
    name = "x"
    API = "https://api.x.com/2"

    def _auth(self):
        return {"Authorization": f"Bearer {self.cfg['access_token']}"}

    def _maybe_refresh(self):
        exp = self.cfg.get("expires_at")
        if exp and dt.datetime.fromisoformat(exp) <= now() + dt.timedelta(minutes=5):
            self.refresh()

    def refresh(self) -> str:
        """OAuth 2.0 user tokens last 2 hours; the refresh token (scope offline.access) renews them."""
        r = self.http.request("POST", f"{self.API}/oauth2/token", form={
            "grant_type": "refresh_token", "refresh_token": self.cfg["refresh_token"], "client_id": self.cfg["client_id"]})
        d = self._ok(r, "refresh")
        self.cfg["access_token"], self.cfg["refresh_token"] = d["access_token"], d.get("refresh_token", self.cfg["refresh_token"])
        self.cfg["expires_at"] = (now() + dt.timedelta(seconds=int(d.get("expires_in", 7200)))).isoformat()
        save_config(self.name, self.cfg)
        return self.cfg["expires_at"]

    def whoami(self):
        self._maybe_refresh()
        d = self._ok(self.http.request("GET", f"{self.API}/users/me", headers=self._auth()), "users/me")["data"]
        return str(d["id"]), d["username"]

    def preflight(self):
        if self.cfg.get("paid_posting_ok") is not True:
            raise Skip("x: posting is paid per use; set paid_posting_ok in the config to enable")

    def publish(self, text, extra, prepared):
        r = self.http.request("POST", f"{self.API}/tweets", headers=self._auth(), json_body={"text": text})
        tid = self._ok(r, "POST /2/tweets")["data"]["id"]
        return f"https://x.com/{self.pin['handle']}/status/{tid}"


# ---------------------------------------------------------------- Mastodon
class Mastodon(Channel):
    name = "mastodon"

    @property
    def instance(self):
        return str(self.pin.get("instance") or "").rstrip("/")

    def _auth(self):
        return {"Authorization": f"Bearer {self.cfg['access_token']}"}

    def whoami(self):
        if str(self.cfg.get("instance", "")).rstrip("/") != self.instance or not self.instance.startswith("https://"):
            raise Refused("mastodon: the config's server is not the pinned server")
        d = self._ok(self.http.request("GET", f"{self.instance}/api/v1/accounts/verify_credentials",
                                       headers=self._auth()), "verify_credentials")
        return str(d["id"]), d["acct"]

    def publish(self, text, extra, prepared):
        r = self.http.request("POST", f"{self.instance}/api/v1/statuses",
                              headers={**self._auth(), "Idempotency-Key": extra["idempotency_key"]},
                              json_body={"status": text, "visibility": "public", "language": "en"})
        return self._ok(r, "POST statuses")["url"]


# ---------------------------------------------------------------- dev.to
class Devto(Channel):
    name = "devto"
    API = "https://dev.to/api"

    def _auth(self):
        return {"api-key": self.cfg["api_key"], "Accept": "application/vnd.forem.api-v1+json"}

    def whoami(self):
        d = self._ok(self.http.request("GET", f"{self.API}/users/me", headers=self._auth()), "users/me")
        return str(d["id"]), d["username"]

    def publish(self, text, extra, prepared):
        a = extra["article"]
        if not str(a.get("canonical_url", "")).startswith("https://purplelink.llc/"):
            raise Skip("devto: canonical_url must be the purplelink.llc page")
        r = self.http.request("POST", f"{self.API}/articles", headers=self._auth(), json_body={"article": {
            "title": a["title"], "body_markdown": a["body_markdown"], "published": True,
            "canonical_url": a["canonical_url"], "description": a.get("description", ""), "tags": a.get("tags", [])}})
        return self._ok(r, "POST articles")["url"]


# ---------------------------------------------------------------- email (Resend broadcast)
class Email(Channel):
    """Release notes to a double opt-in list, as a Resend broadcast to one segment. Stays disabled until a list
    exists: the segment id and name must be pinned and the config written. Resend adds the unsubscribe link."""
    name = "email"
    API = "https://api.resend.com"
    FROM_DOMAIN = "purplelink.llc"

    def _auth(self):
        return {"Authorization": f"Bearer {self.cfg['api_key']}"}

    def whoami(self):
        d = self._ok(self.http.request("GET", f"{self.API}/segments/{self.pin['id']}", headers=self._auth()), "segment")
        return str(d["id"]), d["name"]

    def preflight(self):
        sender = str(self.cfg.get("from", ""))
        if not re.search(rf"@{re.escape(self.FROM_DOMAIN)}>?$", sender):
            raise Refused(f"email: sender must be an @{self.FROM_DOMAIN} address")
        if self.cfg.get("double_opt_in") is not True:
            raise Skip("email: the list is not marked double opt-in in the config")

    def publish(self, text, extra, prepared):
        from html import escape
        from variants import POSTAL_ADDRESS
        unsub = "{{{RESEND_UNSUBSCRIBE_URL}}}"
        def linked(m):
            return '<a href="' + m.group(0) + '">' + m.group(0) + "</a>"

        paras = [p for p in text.split("\n\n") if p.strip()]
        html = "".join("<p>" + URL_RE.sub(linked, escape(p, quote=False)) + "</p>" for p in paras)
        html += f'<p style="font-size:13px;color:#666">You signed up for Purplelink release notes. ' \
                f'<a href="{unsub}">Unsubscribe</a>.<br>{POSTAL_ADDRESS}</p>'
        body_text = f"{text}\n\n--\nYou signed up for Purplelink release notes. Unsubscribe: {unsub}\n{POSTAL_ADDRESS}"
        r = self.http.request("POST", f"{self.API}/broadcasts", headers=self._auth(), json_body={
            "segment_id": self.pin["id"], "from": self.cfg["from"], "subject": extra["subject"], "html": html,
            "text": body_text, "name": extra["idempotency_key"], "send": True})
        return f"resend:broadcast:{self._ok(r, 'POST broadcasts')['id']}"


# ---------------------------------------------------------------- LinkedIn (existing company-only poster)
class Linkedin(Channel):
    """Runs backend/scripts/linkedin_post.py unchanged. That script checks, twice, that the page is the company admin
    page (company 120183926) and that the composer posts as "Purplelink LLC"; it exits 4 when either is wrong."""
    name = "linkedin"

    def __init__(self, http, cfg, sleep=time.sleep, runner=subprocess.run):
        super().__init__(http, cfg, sleep)
        self.runner = runner

    def whoami(self):
        return self.pin["id"], self.pin["handle"]  # read from the live composer inside linkedin_post.py

    def check_identity(self, stage):
        if self.cfg.get("enabled") is not True:
            raise Skip("linkedin: not enabled in the config")

    def publish(self, text, extra, prepared):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write(text)
            path = fh.name
        try:
            r = self.runner([sys.executable, str(ROOT / "backend" / "scripts" / "linkedin_post.py"), "--text-file", path,
                             "--headless"], capture_output=True, text=True, timeout=600)
        finally:
            Path(path).unlink(missing_ok=True)
        if r.returncode == 4:
            raise Refused("linkedin: linkedin_post.py refused (not the company page or composer)")
        if r.returncode == 2:
            raise Skip("linkedin: session expired; run backend/scripts/linkedin_login.py")
        if r.returncode != 0:
            raise RuntimeError(f"linkedin: linkedin_post.py exited {r.returncode}")
        return "https://www.linkedin.com/company/120183926/admin/page-posts/published/"


ADAPTERS = {"threads": Threads, "bluesky": Bluesky, "x": X, "mastodon": Mastodon, "devto": Devto, "email": Email,
            "linkedin": Linkedin}


def adapter(channel: str, http, **kw) -> Channel | None:
    """The adapter, or None when the channel is disabled (no pin, no config, or "enabled": false)."""
    if not pinned(channel):
        return None
    cfg = load_config(channel)
    if cfg is None or cfg.get("enabled") is False:
        return None
    return ADAPTERS[channel](http, cfg, **kw)


def status(channel: str) -> str:
    if not pinned(channel):
        return "disabled: company account not pinned in code yet"
    try:
        cfg = load_config(channel)
    except Refused as e:
        return f"disabled: {e}"
    if cfg is None:
        return "disabled: no config file"
    if cfg.get("enabled") is False:
        return "disabled in config"
    if channel == "x" and cfg.get("paid_posting_ok") is not True:
        return "disabled: X posting is paid per use (paid_posting_ok not set)"
    if channel == "linkedin" and cfg.get("enabled") is not True:
        return "disabled: set enabled true in linkedin.json"
    host = urlsplit(str(pin(channel).get("instance") or "")).netloc
    return "enabled" + (f" ({host})" if host else "")
