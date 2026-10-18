#!/usr/bin/env python3
"""Upload one long ambient video to Pixel Hearth and schedule it, through the guarded API path (scripts/yt-api-upload.py).

  python3 scripts/yt-schedule-upload.py --video FILE.mp4 --meta FILE.json --thumbnail THUMB.jpg --publish-at 2026-10-26T15:00:00-04:00 [--dry-run]

Everything comes from the meta JSON that tools/chiptune-radio/longform_pub.py writes: title, description (plus the link footer),
tags, and the altered-or-synthetic-content answer; the category is Music. The upload goes in Private and YouTube makes it public at
--publish-at. Channel choice, token identity, the post-upload channel check and duplicate protection are yt-api-upload.py's job;
this script never drives Studio or switches the shared Chrome's channel (Ben, 2026-10-17: "I never want a channel getting the
wrong content").
"""
import argparse, json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
MUSIC = "10"   # YouTube category id


def build_args(meta: dict, video: str, thumbnail: str | None, publish_at: str, desc_file: str, dry_run: bool) -> list[str]:
    cmd = [sys.executable, os.path.join(HERE, "yt-api-upload.py"), "--channel", "pixelhearth", "--kind", "ambient", os.path.abspath(video),
           "--title", meta["title"], "--description-file", desc_file, "--category", MUSIC, "--privacy", "private", "--publish-at", publish_at]
    if meta.get("tags"):
        cmd += ["--tags", ",".join(meta["tags"])]
    if thumbnail:
        cmd += ["--thumbnail", os.path.abspath(thumbnail)]
    if meta.get("altered_or_synthetic_content", {}).get("answer") == "No":
        cmd.append("--not-synthetic")
    if dry_run:
        cmd.append("--dry-run")
    return cmd


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--meta", required=True)
    ap.add_argument("--thumbnail")
    ap.add_argument("--publish-at", required=True, help="ISO 8601 with offset, for example 2026-10-26T15:00:00-04:00")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    meta = json.load(open(a.meta))
    desc = meta["description"] + (("\n\n" + meta["optional_footer"]) if meta.get("optional_footer") else "")
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(desc)
        desc_file = f.name
    try:
        return subprocess.run(build_args(meta, a.video, a.thumbnail, a.publish_at, desc_file, a.dry_run)).returncode
    finally:
        os.unlink(desc_file)


if __name__ == "__main__":
    sys.exit(main())
