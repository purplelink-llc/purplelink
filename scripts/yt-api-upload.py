#!/usr/bin/env python3
"""Upload a video to a registered YouTube channel through the Data API, with the channel guard.

  python3 scripts/yt-api-upload.py --channel pixelhearth --kind ambient FILE --title "..." [--description "..."]
      [--description-file F] [--tags a,b] [--category N] [--privacy public|unlisted|private] [--publish-at ISO]
      [--thumbnail F] [--not-synthetic] [--dry-run]

Channels and the kinds each may carry are in scripts/yt-channels.json; tokens are made by scripts/yt-login.py.
Privacy defaults to unlisted; pass --privacy public only for a video Ben approved. --dry-run runs the kind and
identity checks and prints the plan without inserting. Success prints the URL and `verified channel: <id> (<title>)`.

Exit codes: 0 ok, 1 upload failed, 2 bad arguments, 3 a guard check failed, 4 YouTube quota or upload cap.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yt_guard as g  # noqa: E402


def main(argv=None, **injected):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--channel", required=True, help="registry key in scripts/yt-channels.json")
    ap.add_argument("--kind", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--description", default=None)
    ap.add_argument("--description-file")
    ap.add_argument("--tags", default="")
    ap.add_argument("--category")
    ap.add_argument("--privacy", choices=g.PRIVACY, default="unlisted")
    ap.add_argument("--publish-at")
    ap.add_argument("--thumbnail")
    ap.add_argument("--not-synthetic", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.description is not None and a.description_file:
        print("use --description or --description-file, not both", file=sys.stderr)
        return 2
    try:
        desc = a.description or ""
        if a.description_file:
            with open(a.description_file, encoding="utf-8") as f:
                desc = f.read()
        tags = [t for t in a.tags.split(",") if t.strip()]
        synthetic = False if a.not_synthetic else None
        if a.dry_run:
            ch, title = g.dry_run(a.channel, a.kind, **injected)
            body = g.build_body(ch, a.kind, a.title, desc, tags, a.category, a.privacy, a.publish_at, synthetic)
            print(f"dry run: checks passed for {a.channel!r}, kind {a.kind!r}")
            print(f"verified channel: {ch['id']} ({title})")
            print(f"would upload {os.path.abspath(a.file)} with snippet {body['snippet']} and status {body['status']}")
            if a.thumbnail:
                print(f"would set thumbnail {a.thumbnail}")
            return 0
        r = g.guarded_upload(a.channel, a.kind, a.file, a.title, desc, tags, a.category, a.privacy,
                             a.publish_at, a.thumbnail, synthetic, **injected)
    except g.ChannelGuardError as e:
        print(f"CHANNEL GUARD: {e}", file=sys.stderr)
        return 3
    except g.UploadArgsError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except g.UploadCapError as e:
        print(f"YouTube quota or upload cap: {e}", file=sys.stderr)
        return 4
    except Exception as e:  # network, HttpError, anything else
        print(f"upload failed: {e}", file=sys.stderr)
        return 1
    if r["duplicate"]:
        print("a video with this exact title was uploaded in the last 24 h; returning it instead of uploading again")
    if r["thumbnail"] is False:
        print("warning: the thumbnail could not be set", file=sys.stderr)
    print(r["url"])
    print(f"privacy: {r['privacy']}")
    print(f"verified channel: {r['channel_id']} ({r['channel_title']})")
    if a.channel == "purplelink" and r["privacy"] == "public" and not r["duplicate"] and not injected:
        add_reel(a.file, r["id"], a.title, desc)
    return 0


def add_reel(path, video_id, title, desc):
    """Every public Purplelink video also becomes an Instagram Reel (Ben, 2026-10-23): hand the file to the social
    pipeline's Reel inbox, which pads a 16:9 video to 9:16, vets and queues it. Never fails the upload."""
    import subprocess
    import tempfile
    social = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", "scripts", "social.py")
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
        fh.write(desc or "")
    try:
        p = subprocess.run([sys.executable, social, "instagram", "reel-add", "--video", os.path.abspath(path),
                            "--youtube-id", video_id, "--title", title, "--description-file", fh.name],
                           capture_output=True, text=True, timeout=1800)
        print(f"instagram: {(p.stdout or p.stderr).strip()[-300:]}")
    except Exception as e:
        print(f"instagram: Reel not added ({type(e).__name__}); the channel scan will flag it", file=sys.stderr)
    finally:
        os.unlink(fh.name)


if __name__ == "__main__":
    sys.exit(main())
