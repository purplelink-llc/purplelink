#!/usr/bin/env python3
"""One-time LinkedIn OAuth flow to obtain an access token for the digest cron.

Usage:
  LINKEDIN_CLIENT_ID=xxx LINKEDIN_CLIENT_SECRET=yyy python3 backend/scripts/linkedin_auth.py

Token lifetime: 60 days. Re-run this script ~every 50 days.
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.parse
import webbrowser

CLIENT_ID = os.environ.get("LINKEDIN_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("LINKEDIN_CLIENT_SECRET", "")
REDIRECT_URI = "http://localhost:8080/callback"
SCOPE = "w_member_social"
STATE = "purplelink-digest-auth"


def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("ERROR: Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET env vars.")
        raise SystemExit(1)

    auth_url = (
        "https://www.linkedin.com/oauth/v2/authorization"
        f"?response_type=code"
        f"&client_id={CLIENT_ID}"
        f"&redirect_uri={urllib.parse.quote(REDIRECT_URI, safe='')}"
        f"&scope={urllib.parse.quote(SCOPE, safe='')}"
        f"&state={STATE}"
    )

    print("\n1. Opening LinkedIn authorization in your browser...")
    print("   If it doesn't open, visit this URL manually:\n")
    print(f"   {auth_url}\n")
    webbrowser.open(auth_url)

    print("2. Authorize the app in your browser.")
    print("   After authorizing, your browser will show a 'can't connect' error — that's expected.\n")
    print("3. Copy the FULL URL from your browser's address bar and paste it here:")
    print("   It will look like: http://localhost:8080/callback?code=AQT...&state=...\n")

    raw = input("Paste the full redirect URL: ").strip()

    parsed = urllib.parse.urlparse(raw)
    params = dict(urllib.parse.parse_qsl(parsed.query))

    if "error" in params:
        print(f"ERROR from LinkedIn: {params.get('error')}: {params.get('error_description')}")
        raise SystemExit(1)

    code = params.get("code", "")
    if not code:
        print("ERROR: No 'code' parameter found in the URL. Did you copy the full URL?")
        raise SystemExit(1)

    print("\nExchanging authorization code for access token...")

    def curl_post(url, data: dict, extra_headers: list[str] | None = None) -> dict:
        body = urllib.parse.urlencode(data)
        cmd = ["curl", "-s", "-X", "POST", url,
               "--data", body,
               "-H", "Content-Type: application/x-www-form-urlencoded",
               "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
               "-w", "\n%{http_code}"]
        if extra_headers:
            for h in extra_headers:
                cmd += ["-H", h]
        result = subprocess.run(cmd, capture_output=True, text=True)
        output = result.stdout.strip()
        # Last line is the HTTP status code
        lines = output.rsplit("\n", 1)
        body_text = lines[0] if len(lines) > 1 else ""
        status_code = int(lines[-1]) if lines[-1].isdigit() else 0
        return {"status": status_code, "body": body_text}

    def curl_get(url, headers: list[str]) -> dict:
        cmd = ["curl", "-s", "-X", "GET", url,
               "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
               "-w", "\n%{http_code}"]
        for h in headers:
            cmd += ["-H", h]
        result = subprocess.run(cmd, capture_output=True, text=True)
        output = result.stdout.strip()
        lines = output.rsplit("\n", 1)
        body_text = lines[0] if len(lines) > 1 else ""
        status_code = int(lines[-1]) if lines[-1].isdigit() else 0
        return {"status": status_code, "body": body_text}

    resp = curl_post("https://www.linkedin.com/oauth/v2/accessToken", {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    })

    if resp["status"] != 200:
        print(f"ERROR: Token exchange failed (HTTP {resp['status']})")
        print(f"Response body: {resp['body']}")
        raise SystemExit(1)

    token_data = json.loads(resp["body"])
    access_token = token_data.get("access_token", "")
    expires_in = token_data.get("expires_in", 0)
    if not access_token:
        print(f"ERROR: {token_data}")
        raise SystemExit(1)

    print(f"Access token obtained (expires in {expires_in // 86400} days).")

    # Fetch the person URN via the basic profile endpoint
    person_urn = ""
    try:
        profile_resp = curl_get(
            "https://api.linkedin.com/v2/me",
            headers=[
                f"Authorization: Bearer {access_token}",
                "X-Restli-Protocol-Version: 2.0.0",
            ],
        )
        if profile_resp["status"] != 200:
            raise RuntimeError(f"HTTP {profile_resp['status']}: {profile_resp['body']}")
        info = json.loads(profile_resp["body"])
        uid = info.get("id", "")
        first = info.get("localizedFirstName", "")
        last = info.get("localizedLastName", "")
        person_urn = f"urn:li:person:{uid}" if uid else ""
        print(f"Authenticated as: {first} {last}")
        print(f"Person URN: {person_urn}\n")
    except Exception as e:
        print(f"Could not fetch person URN automatically: {e}")
        person_urn = "urn:li:person:YOUR_ID_HERE"

    # NOTE: Organization/Page posting (w_organization_social) requires LinkedIn's
    # Community Management API product — a separate application with company
    # verification, not something granted through "Share on LinkedIn" alone.
    # Until that's approved, posts go out under the personal profile.
    author_urn = person_urn

    print("--- Run this command to store credentials in Modal ---\n")
    print(f"modal secret create linkedin \\")
    print(f"  LINKEDIN_ACCESS_TOKEN='{access_token}' \\")
    print(f"  LINKEDIN_AUTHOR_URN='{author_urn}'\n")
    print("--- Then redeploy the Modal app ---")
    print("bash scripts/deploy.sh --backend\n")


if __name__ == "__main__":
    main()
