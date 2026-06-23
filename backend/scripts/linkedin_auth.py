#!/usr/bin/env python3
"""One-time LinkedIn OAuth flow to obtain an access token for the digest cron.

Usage:
  1. Create a LinkedIn Developer App at https://developer.linkedin.com/
     - Add products: "Share on LinkedIn" (for personal) or
       "Marketing Developer Platform" (for company pages)
     - Set OAuth 2.0 redirect URL to: http://localhost:8080/callback
     - Note your Client ID and Client Secret

  2. Set env vars and run:
       LINKEDIN_CLIENT_ID=xxx LINKEDIN_CLIENT_SECRET=yyy python linkedin_auth.py

  3. Copy the Modal commands printed at the end and run them.

Token lifetime: 60 days. Re-run this script ~every 50 days.
"""
from __future__ import annotations

import http.server
import os
import threading
import urllib.parse
import urllib.request
import json
import webbrowser

CLIENT_ID = os.environ.get("LINKEDIN_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("LINKEDIN_CLIENT_SECRET", "")
REDIRECT_URI = "http://localhost:8080/callback"

# For personal profile posting: w_member_social
# For company page posting: w_organization_social (requires Marketing Developer Platform)
SCOPE = "openid profile w_member_social"


def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("ERROR: Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET env vars.")
        raise SystemExit(1)

    auth_url = (
        "https://www.linkedin.com/oauth/v2/authorization"
        f"?response_type=code"
        f"&client_id={CLIENT_ID}"
        f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
        f"&scope={urllib.parse.quote(SCOPE)}"
    )

    code_holder: list[str] = []
    server_ready = threading.Event()
    server_done = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            params = dict(urllib.parse.parse_qsl(parsed.query))
            code = params.get("code", "")
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            if code:
                self.wfile.write(b"<h2>Authorized. You can close this window.</h2>")
                code_holder.append(code)
            else:
                self.wfile.write(b"<h2>No code received. Try again.</h2>")
            server_done.set()

        def log_message(self, *args):
            pass

    httpd = http.server.HTTPServer(("localhost", 8080), Handler)
    t = threading.Thread(target=httpd.serve_forever)
    t.daemon = True
    t.start()

    print(f"\nOpening browser for LinkedIn authorization...")
    print(f"If it doesn't open, visit:\n  {auth_url}\n")
    webbrowser.open(auth_url)
    server_done.wait(timeout=120)
    httpd.shutdown()

    if not code_holder:
        print("ERROR: No authorization code received.")
        raise SystemExit(1)

    code = code_holder[0]
    print("Authorization code received. Exchanging for access token...")

    token_data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }).encode()

    req = urllib.request.Request(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data=token_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req) as resp:
        token_resp = json.loads(resp.read())

    access_token = token_resp.get("access_token", "")
    expires_in = token_resp.get("expires_in", 0)
    if not access_token:
        print(f"ERROR: {token_resp}")
        raise SystemExit(1)

    print(f"\nAccess token obtained (expires in {expires_in // 86400} days).\n")

    # Fetch the person URN via userinfo endpoint
    person_urn = ""
    try:
        req2 = urllib.request.Request(
            "https://api.linkedin.com/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        with urllib.request.urlopen(req2) as resp2:
            info = json.loads(resp2.read())
        sub = info.get("sub", "")
        person_urn = f"urn:li:person:{sub}" if sub else ""
        print(f"Person URN: {person_urn}")
    except Exception as e:
        print(f"Could not fetch person URN automatically: {e}")
        person_urn = "urn:li:person:YOUR_ID_HERE"

    print("\n--- Run these commands to store credentials in Modal ---\n")
    print(f"modal secret create linkedin \\")
    print(f"  LINKEDIN_ACCESS_TOKEN='{access_token}' \\")
    print(f"  LINKEDIN_AUTHOR_URN='{person_urn}'")
    print("\n--- For a company page, replace LINKEDIN_AUTHOR_URN with: ---")
    print("  LINKEDIN_AUTHOR_URN='urn:li:organization:YOUR_ORG_ID'")
    print("(find your org ID in the company page URL on LinkedIn)\n")
    print("--- Then redeploy the Modal app: ---")
    print("bash scripts/deploy.sh --backend\n")


if __name__ == "__main__":
    main()
