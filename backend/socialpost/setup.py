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
    if platform == "instagram":
        return _setup_instagram(cfg)
    if platform == "facebook":
        return _setup_facebook(cfg)
    raise SystemExit(f"unknown platform {platform}")


def _scrub(text: str, *secrets: str) -> str:
    """Meta's error text, with any secret removed in case it is ever echoed back."""
    for sec in secrets:
        if sec:
            text = text.replace(sec, "[hidden]")
    return text[:300]


def _setup_threads(cfg: dict) -> int:
    tok = _ask_secret("Threads access token")
    app_secret = _ask_secret("Threads app secret, or Enter if the token is already long-lived", required=False)
    if app_secret:
        # Meta documents this exchange as a GET with query parameters; a POST gets HTTP 400.
        q = urlencode({"grant_type": "th_exchange_token", "client_secret": app_secret, "access_token": tok})
        r = Http().request("GET", f"https://graph.threads.net/access_token?{q}")
        new = (r.json() or {}).get("access_token")
        if r.status != 200 or not new:
            err = (r.json() or {}).get("error") or {}
            msg = err.get("message", "") if isinstance(err, dict) else ""
            print(f"The exchange failed (HTTP {r.status}). Nothing stored. {_scrub(msg, tok, app_secret)}".rstrip())
            return 1
        tok = new
    sysutil.keychain_set("threads", "access_token", tok)
    note_token_time("threads")
    a = build_adapter(cfg, "threads")
    return 0 if _confirm_identity("threads", a, {"user_id": "id", "username": "username"}) else 1


# Business Login for Instagram, for when the dashboard's Generate token popup will not finish (it loops on the login
# in Safari and Chrome when the browser keeps instagram.com cookies away from the facebook.com page). The consent is a
# full Instagram page, the code comes back on the redirect URI, and the code is exchanged for a token here.
IG_AUTHORIZE = "https://www.instagram.com/oauth/authorize"
IG_TOKEN = "https://api.instagram.com/oauth/access_token"
IG_REDIRECT = "https://purplelink.llc/instagram/"
IG_SCOPES = "instagram_business_basic,instagram_business_content_publish"


def ig_authorize_url(app_id: str, state: str) -> str:
    return IG_AUTHORIZE + "?" + urlencode({"client_id": app_id, "redirect_uri": IG_REDIRECT, "response_type": "code",
                                           "scope": IG_SCOPES, "state": state, "force_reauth": "true"})


def ig_code_from(pasted: str, state: str) -> str | None:
    """The authorization code from the address Instagram sent the browser to (or the bare code). None when the
    state does not match (the address came from some other sign-in)."""
    pasted = pasted.strip()
    if not pasted.startswith("http"):
        return pasted.split("#")[0] or None
    q = parse_qs(urlsplit(pasted).query)
    if (q.get("state") or [""])[0] != state:
        return None
    code = (q.get("code") or [""])[0].split("#")[0]
    return code or None


def ig_exchange_code(http, app_id: str, app_secret: str, code: str) -> tuple[str | None, str]:
    """(short-lived token, error text) for an authorization code."""
    r = http.request("POST", IG_TOKEN, form={"client_id": app_id, "client_secret": app_secret,
                                             "grant_type": "authorization_code", "redirect_uri": IG_REDIRECT,
                                             "code": code})
    j = r.json() or {}
    if r.status == 200 and j.get("access_token"):
        return j["access_token"], ""
    msg = j.get("error_message") or ""
    if not msg and isinstance(j.get("error"), dict):
        msg = j["error"].get("message", "")
    return None, f"HTTP {r.status} {_scrub(str(msg), app_secret, code)}".strip()


def _instagram_login(http=None) -> tuple[str | None, str]:
    http = http or Http()
    print(f"""
Sign in through Instagram instead of the Generate token button.
In the app dashboard (Instagram API -> API setup with Instagram login -> 3. Set up Instagram business login):
  - Business login settings -> OAuth redirect URIs: add  {IG_REDIRECT}  and save.
  - Copy the Instagram app ID and the Instagram app secret shown there (not the Facebook app ID).
""")
    app_id = input("Instagram app ID: ").strip()
    if not app_id.isdigit():
        print("The Instagram app ID is a number. Nothing stored.")
        return None, ""
    app_secret = _ask_secret("Instagram app secret")
    state = secrets.token_urlsafe(16)
    print("\nOpen this link in a browser where Instagram is signed in as purplelink.llc (never RubbleFront), and allow:\n")
    print(ig_authorize_url(app_id, state))
    print("\nInstagram then opens the purplelink.llc/instagram/ page. Copy that page's full address from the address bar.")
    code = ig_code_from(input("Paste the address here: "), state)
    if not code:
        print("No code for this sign-in in that address (a different or old link?). Nothing stored.")
        return None, ""
    tok, err = ig_exchange_code(http, app_id, app_secret, code)
    if not tok:
        print(f"Instagram did not give a token ({err}). The code works once and for about an hour; run setup again.")
        return None, ""
    return tok, app_secret


def _setup_instagram(cfg: dict) -> int:
    tok = _ask_secret("Instagram access token from the dashboard's Generate token, or Enter to sign in through "
                      "Instagram instead", required=False)
    if tok:
        if not tok.startswith("IG"):
            print(f"That is not an Instagram Login token (those start with IG; this has {len(tok)} characters). "
                  "Run setup again and press only Enter at the first prompt to sign in through Instagram.")
            return 1
        app_secret = _ask_secret("Instagram app secret, or Enter if the token is already long-lived", required=False)
    else:
        tok, app_secret = _instagram_login()
        if not tok:
            return 1
    if app_secret:
        # Meta documents the short-to-long exchange as a GET with query parameters.
        q = urlencode({"grant_type": "ig_exchange_token", "client_secret": app_secret, "access_token": tok})
        r = Http().request("GET", f"https://graph.instagram.com/access_token?{q}")
        new = (r.json() or {}).get("access_token")
        if r.status != 200 or not new:
            err = (r.json() or {}).get("error") or {}
            msg = err.get("message", "") if isinstance(err, dict) else ""
            print(f"The exchange failed (HTTP {r.status}). Nothing stored. {_scrub(msg, tok, app_secret)}".rstrip())
            return 1
        tok = new
    # Check the token with Instagram before anything is stored: a rejected or wrong-account token never reaches
    # the keychain.
    a = build_adapter(cfg, "instagram", secret=lambda platform, field: tok)
    try:
        got = a.whoami()
    except SocialError as e:
        print(f"Instagram did not accept that token ({e}). Nothing stored.")
        return 1
    if "rubblefront" in str(got.get("username") or "").lower():
        print("That token belongs to RubbleFront's account. Purplelink never posts there. Nothing stored.")
        return 1
    sysutil.keychain_set("instagram", "access_token", tok)
    note_token_time("instagram")
    ok = _confirm_identity("instagram", a, {"user_id": "user_id", "username": "username"})
    if ok:
        print("Next: social.py instagram preview --dry-run  (renders a Reel and an image post, posts nothing)")
    return 0 if ok else 1


FB_GRAPH = "https://graph.facebook.com/v23.0"
FB_PAGE_NAME = "Purplelink LLC"


def fb_long_user_token(http, app_id: str, app_secret: str, short: str) -> tuple[str | None, str]:
    """Exchange a short-lived user token for a long-lived one (about 60 days)."""
    q = urlencode({"grant_type": "fb_exchange_token", "client_id": app_id, "client_secret": app_secret,
                   "fb_exchange_token": short})
    r = http.request("GET", f"{FB_GRAPH}/oauth/access_token?{q}")
    tok = (r.json() or {}).get("access_token")
    if r.status == 200 and tok:
        return tok, ""
    err = (r.json() or {}).get("error") or {}
    return None, f"HTTP {r.status} {_scrub(str(err.get('message', '') if isinstance(err, dict) else ''), app_secret, short)}"


def fb_pick_page(http, user_token: str, page_name: str = FB_PAGE_NAME) -> tuple[dict | None, str]:
    """The Page named page_name among the user's Pages, with its token and connected Instagram account."""
    r = http.request("GET", f"{FB_GRAPH}/me/accounts?fields=id,name,access_token,"
                            "instagram_business_account%7Bid,username%7D&limit=100",
                     {"Authorization": f"Bearer {user_token}"})
    if r.status != 200:
        return None, f"listing Pages answered {r.status} (does the token have pages_show_list?)"
    pages = (r.json() or {}).get("data") or []
    hits = [pg for pg in pages if str(pg.get("name", "")).strip().lower() == page_name.lower()]
    if len(hits) != 1:
        names = ", ".join(pg.get("name", "?") for pg in pages) or "none"
        return None, f"expected exactly one Page named {page_name!r}; the token sees: {names}"
    return hits[0], ""


def _setup_facebook(cfg: dict, http=None) -> int:
    http = http or Http()
    tok = _ask_secret("User token from the Graph API Explorer")
    app_id = input("App ID (the app the token was made in): ").strip()
    app_secret = _ask_secret("App secret (to make the token long-lived), or Enter if you already extended it in "
                             "the Access Token Debugger", required=False)
    if app_secret:
        if not app_id.isdigit():
            print("The App ID is a number. Nothing stored.")
            return 1
        tok, err = fb_long_user_token(http, app_id, app_secret, tok)
        if not tok:
            print(f"The exchange failed ({err}). Nothing stored.")
            return 1
    page, err = fb_pick_page(http, tok)
    if not page:
        print(f"{err}. Nothing stored.")
        return 1
    ig = page.get("instagram_business_account") or {}
    print(f"\nPage: {page['name']} (id {page['id']})")
    print(f"Connected Instagram: @{ig.get('username')} (id {ig.get('id')})" if ig else
          "Connected Instagram: none (connect @purplelink.llc to the Page first for Instagram posts)")
    if "rubblefront" in str(ig.get("username") or "").lower():
        print("That Page is connected to RubbleFront's Instagram. Purplelink never posts there. Nothing stored.")
        return 1
    if input("Is this the Purplelink company Page? Type yes to store its token and pin it: ").strip().lower() != "yes":
        print("Not stored.")
        return 1
    sysutil.keychain_set("facebook", "page_token", page["access_token"])
    cfgmod.update_platform("facebook", enabled=True, expected={"page_id": str(page["id"]), "name": page["name"]})
    print(f"Facebook Page pinned in {paths.config_file()} and enabled.")
    if ig.get("id") and str(ig.get("username") or "").lower() == "purplelink.llc":
        cfgmod.update_platform("instagram", enabled=True, api="facebook",
                               expected={"user_id": str(ig["id"]), "username": ig["username"]})
        print("Instagram @purplelink.llc now publishes through the Page (api: facebook), pinned and enabled.")
    print("Next: social.py whoami, then social.py instagram preview (the dry run, posts nothing)")
    return 0


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
