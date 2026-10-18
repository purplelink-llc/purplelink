"""Interactive setup helpers. Secrets are read with hidden input and go straight into the login keychain."""
from __future__ import annotations

import base64
import datetime as dt
import getpass
import hashlib
import json
import secrets
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from . import config as cfgmod
from . import paths, sysutil
from .engine import build_adapter
from .errors import SocialError
from .http import Http
from .setup_guides import GUIDES

X_AUTH = "https://x.com/i/oauth2/authorize"
X_TOKEN = "https://api.x.com/2/oauth2/token"
X_SCOPES = "tweet.read tweet.write users.read media.write offline.access"
REDIRECT = "http://127.0.0.1:8765/callback"


def tokens_file() -> Path:
    return paths.home() / "tokens.json"


def note_token_time(platform: str, when: dt.datetime | None = None) -> None:
    p = tokens_file()
    data = json.loads(p.read_text()) if p.exists() else {}
    data[platform] = {"refreshed_at": (when or dt.datetime.now(dt.timezone.utc)).isoformat(timespec="seconds")}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2))
    p.chmod(0o600)


def token_age_days(platform: str, now: dt.datetime | None = None) -> float | None:
    p = tokens_file()
    if not p.exists():
        return None
    t = json.loads(p.read_text()).get(platform, {}).get("refreshed_at")
    if not t:
        return None
    return ((now or dt.datetime.now(dt.timezone.utc)) - dt.datetime.fromisoformat(t)).total_seconds() / 86400


def pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def x_authorize_url(client_id: str, state: str, challenge: str) -> str:
    return X_AUTH + "?" + urlencode({"response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT,
                                      "scope": X_SCOPES, "state": state, "code_challenge": challenge,
                                      "code_challenge_method": "S256"})


def _ask_secret(label: str, required: bool = True) -> str:
    v = getpass.getpass(f"{label} (hidden): ").strip()
    if required and not v:
        raise SystemExit("nothing entered; nothing stored")
    return v


def _confirm_identity(platform: str, adapter, fields: dict[str, str]) -> bool:
    got = adapter.whoami()
    print("\nThe stored credential belongs to:")
    for k, v in got.items():
        if v not in (None, ""):
            print(f"  {k}: {v}")
    ans = input("Is this the Purplelink company account? Type yes to pin it as the expected identity: ").strip().lower()
    if ans != "yes":
        print("Not pinned. The platform stays disabled.")
        return False
    cfgmod.update_platform(platform, enabled=True, expected={k: str(got.get(v, "")) for k, v in fields.items()})
    print(f"Pinned in {paths.config_file()} and enabled.")
    return True


def setup(platform: str) -> int:
    print(GUIDES[platform])
    if platform == "bluesky":
        script = Path(__file__).resolve().parents[1] / "scripts" / "bluesky_login.py"
        return subprocess.call([sys.executable, str(script)])
    cfgmod.write_default()
    cfg = cfgmod.load()
    if platform == "threads":
        return _setup_threads(cfg)
    if platform == "mastodon":
        return _setup_mastodon(cfg)
    if platform == "x":
        return _setup_x(cfg)
    raise SystemExit(f"unknown platform {platform}")


def _setup_threads(cfg: dict) -> int:
    tok = _ask_secret("Threads access token")
    app_secret = _ask_secret("Threads app secret, or Enter if the token is already long-lived", required=False)
    if app_secret:
        r = Http().request("POST", "https://graph.threads.net/access_token",
                           form={"grant_type": "th_exchange_token", "client_secret": app_secret, "access_token": tok})
        new = (r.json() or {}).get("access_token")
        if r.status != 200 or not new:
            print(f"The exchange failed (HTTP {r.status}). Nothing stored.")
            return 1
        tok = new
    sysutil.keychain_set("threads", "access_token", tok)
    note_token_time("threads")
    a = build_adapter(cfg, "threads")
    return 0 if _confirm_identity("threads", a, {"user_id": "id", "username": "username"}) else 1


def _setup_mastodon(cfg: dict) -> int:
    inst = input("Server URL (for example https://mastodon.social): ").strip().rstrip("/")
    if not inst.startswith("https://") or len(urlsplit(inst).path) > 1:
        print("The server must be an https URL with no path.")
        return 1
    tok = _ask_secret("Mastodon access token")
    sysutil.keychain_set("mastodon", "access_token", tok)
    cfgmod.update_platform("mastodon", instance=inst)
    cfg = cfgmod.load()
    a = build_adapter(cfg, "mastodon")
    return 0 if _confirm_identity("mastodon", a, {"acct": "acct"}) else 1


def _setup_x(cfg: dict) -> int:
    client_id = _ask_secret("X OAuth 2.0 Client ID")
    client_secret = _ask_secret("X Client Secret, or Enter for a public (native) app", required=False)
    verifier, challenge = pkce_pair()
    state = secrets.token_urlsafe(16)
    got: dict = {}

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            q = parse_qs(urlsplit(self.path).query)
            got["code"], got["state"] = (q.get("code") or [""])[0], (q.get("state") or [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Authorized. You can close this tab and go back to the terminal.")

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 8765), H)
    threading.Thread(target=srv.handle_request, daemon=True).start()
    print("\nOpen this link in a browser signed in as the COMPANY X account, and authorize:\n")
    print(x_authorize_url(client_id, state, challenge))
    print("\nWaiting for the callback on 127.0.0.1:8765 ...")
    for _ in range(600):
        if got:
            break
        import time
        time.sleep(1)
    srv.server_close()
    if not got.get("code") or got.get("state") != state:
        print("No valid callback arrived. Nothing stored.")
        return 1
    form = {"grant_type": "authorization_code", "code": got["code"], "redirect_uri": REDIRECT,
            "client_id": client_id, "code_verifier": verifier}
    headers = {}
    if client_secret:
        headers["Authorization"] = "Basic " + base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    r = Http().request("POST", X_TOKEN, headers, form=form)
    j = r.json() or {}
    if r.status != 200 or not j.get("access_token"):
        print(f"The token exchange failed (HTTP {r.status}). Nothing stored.")
        return 1
    sysutil.keychain_set("x", "client_id", client_id)
    if client_secret:
        sysutil.keychain_set("x", "client_secret", client_secret)
    sysutil.keychain_set("x", "access_token", j["access_token"])
    if j.get("refresh_token"):
        sysutil.keychain_set("x", "refresh_token", j["refresh_token"])
    a = build_adapter(cfg, "x")
    ok = _confirm_identity("x", a, {"user_id": "id", "username": "username"})
    cfgmod.update_platform("x", enabled=False)  # stays off until paid_posting_ok is set by hand
    print("X stays disabled until you set enabled and paid_posting_ok to true in the config (see the guide above).")
    return 0 if ok else 1
