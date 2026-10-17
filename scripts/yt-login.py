#!/usr/bin/env python3
"""Create the OAuth token for one registered YouTube channel, and refuse to save it for the wrong one.

  python3 scripts/yt-login.py --channel pixelhearth

Opens a browser (InstalledAppFlow, local server on a free port). In the browser, choose the channel that is named
on screen when Google asks which account or channel. Afterwards channels.list(mine=True) is called with the new
credentials: only when its single channel id equals the registry id is the token written to the registry path
(chmod 600, atomic). Otherwise nothing is written and the exit code is 3.

The OAuth client secret is read from ~/.tiktok_pipeline/youtube_client_secret.json (or $YOUTUBE_CLIENT_SECRET).
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yt_guard as g  # noqa: E402


def run_flow(secret_path, scopes):
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_secrets_file(str(secret_path), scopes)
    return flow.run_local_server(port=0)


def service_for(creds):
    from googleapiclient.discovery import build
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def write_token_atomic(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main(argv=None, *, registry=None, flow=run_flow, build=service_for, secret=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--channel", required=True, help="registry key in scripts/yt-channels.json")
    a = ap.parse_args(argv)
    try:
        ch = g.get_channel(a.channel, registry if registry is not None else g.load_registry())
    except g.ChannelGuardError as e:
        print(f"CHANNEL GUARD: {e}", file=sys.stderr)
        return 3
    client_file = Path(secret or os.environ.get("YOUTUBE_CLIENT_SECRET") or g.CLIENT_SECRET_PATH)
    if not client_file.exists():
        # no path in the message: it can come from the environment, and CodeQL treats it as sensitive
        print("no OAuth client file found: create ~/.tiktok_pipeline/youtube_client_secret.json or set YOUTUBE_CLIENT_SECRET",
              file=sys.stderr)
        return 2
    print(f"In the browser, choose the {ch['title']} channel ({ch['id']}) when Google asks which account or channel.")
    creds = flow(client_file, g.SCOPES)
    found = g.mine(build(creds))
    if len(found) != 1 or found[0]["id"] != ch["id"]:
        chosen = ", ".join(f"{c['id']} ({c['title']})" for c in found) or "no channel"
        print(f"WRONG CHANNEL: you signed in as {chosen}, but {a.channel!r} must be {ch['id']} ({ch['title']}). "
              f"No token was written. Run this again and pick {ch['title']}.", file=sys.stderr)
        return 3
    tp = g.token_path(ch)
    write_token_atomic(tp, creds.to_json())
    print(f"success: token for {ch['title']} ({ch['id']}) saved to {tp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
