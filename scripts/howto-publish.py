#!/usr/bin/env python3
"""Publish a built problem-and-fix video: the 16:9 tutorial (public, Test & Compare A/B/C) and the 9:16 Short
(public, thumbnail A, linking to the tutorial). Records the ledger, advances the rotation, logs the change.

    python3 scripts/howto-publish.py <slug> [--dry-run]

Refuses unless scripts/howto_gate.py passes and video/out/howto/<slug>/ holds both cuts and all three thumbnails.
A kill switch file at ~/.purplelink/howto/PAUSE stops every publish. Links are tagged utm_source=youtube-howto,
utm_medium=video|short, utm_campaign=<slug> so the series is measured on its own.
"""
from __future__ import annotations
import datetime as dt, json, os, re, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VIDEO = REPO / "video"
PY = "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
PAUSE = Path.home() / ".purplelink" / "howto" / "PAUSE"
LEDGER = VIDEO / "howto" / "ledger.json"
ROTATION = VIDEO / "howto" / "rotation.json"
CHANGELOG = Path.home() / ".purplelink" / "insights" / "changelog" / "log_change.py"


def tagged(page: str, medium: str, slug: str) -> str:
    return f"{page}?utm_source=youtube-howto&utm_medium={medium}&utm_campaign={slug.removeprefix('howto-')}"


TRENDS_ROOT = Path(os.environ.get("TRENDS_ROOT", "/Volumes/Extreme SSD/TikTokPipeline"))
FALLBACK_TAGS = ["macos", "mactips", "techtips"]


def trend_tags(sb: dict, short: bool) -> str:
    """Relevant hashtags for the description (shared trends system, topic mac_howto, YouTube list).
    YouTube shows the first three hashtags above the title, so the order matters: topic tags first, and
    #shorts only on the Short (last). latex/overleaf tags only when the storyboard is about LaTeX."""
    tags = list(FALLBACK_TAGS)
    try:
        r = subprocess.run([PY, "-m", "shared_media.trends.cli", "hashtags", "--topic", "mac_howto",
                            "--platform", "youtube", "--k", "6"], cwd=TRENDS_ROOT, capture_output=True,
                           text=True, timeout=60)
        got = r.stdout.split()
        if r.returncode == 0 and got:
            tags = got
    except Exception:
        pass
    if "latex" not in json.dumps(sb).lower():
        tags = [t for t in tags if t not in ("latex", "overleaf")]
    tags = [t for t in tags if t != "shorts"][:3 if short else 4]
    if short:
        tags.append("shorts")
    return " ".join(f"#{t}" for t in tags)


def descriptions(sb: dict, long_url: str | None) -> tuple[str, str]:
    scenes = sb["scenes"]
    hook = next(s for s in scenes if s["type"] == "hook")
    cause = next((s for s in scenes if s["type"] == "cause"), None)
    cmds = [l[2:] for s in scenes if s["type"] == "steps" for l in s.get("lines", []) if l.startswith("$ ")]
    app = next(s for s in scenes if s["type"] == "app")
    parts = [f"{hook['title']}. {hook.get('sub', '')}".strip()]
    if cause:
        parts.append(cause["text"])
    if cmds:
        parts.append("The fix, in Terminal:\n" + "\n".join(cmds))
    parts.append(f"{app['name']}: {app['line']}\n{tagged(sb['page'], 'video', sb['id'])}")
    if sb.get("sources"):
        parts.append("Where this comes up:\n" + "\n".join(sb["sources"]))
    parts.append(trend_tags(sb, short=False))
    long_d = "\n\n".join(parts)
    short_parts = [f"{hook['title']}. {hook.get('sub', '')}".strip()]
    if cmds:
        short_parts.append("\n".join(cmds))
    if long_url:
        short_parts.append(f"Full walkthrough: {long_url}")
    short_parts.append(f"{app['name']}: {tagged(sb['page'], 'short', sb['id'])}")
    short_parts.append(trend_tags(sb, short=True))
    return long_d, "\n\n".join(short_parts)


def upload(file: Path, title: str, desc: str, extra: list[str]) -> str:
    r = subprocess.run([PY, str(REPO / "scripts" / "yt-upload.py"), str(file), "--title", title, "--description", desc,
                        "--public", *extra], capture_output=True, text=True, timeout=3600)
    out = r.stdout + r.stderr
    print(out.strip()[-800:])
    m = re.search(r"https://youtu\.be/([\w-]{11})", r.stdout)
    if r.returncode != 0 or not m or "verified in Studio: Public" not in r.stdout:
        raise SystemExit(f"upload failed for {file.name} (exit {r.returncode})")
    return m.group(1)


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    slug = args[0]
    dry = "--dry-run" in sys.argv
    if PAUSE.exists():
        print(f"paused: {PAUSE} exists; nothing published")
        return 3
    sbp = VIDEO / "storyboards" / "howto" / f"{slug}.json"
    sb = json.loads(sbp.read_text())
    if subprocess.run([PY, str(REPO / "scripts" / "howto_gate.py"), str(sbp)]).returncode != 0:
        raise SystemExit("gate failed: not publishing")
    out = VIDEO / "out" / "howto" / slug
    files = {k: out / f"{slug}-{k}" for k in ("16x9.mp4", "9x16.mp4", "thumb-A.jpg", "thumb-B.jpg", "thumb-C.jpg")}
    missing = [str(p) for p in files.values() if not p.exists()]
    if missing:
        raise SystemExit(f"missing build output: {missing}")
    long_d, _ = descriptions(sb, None)
    if dry:
        print("--- long title\n" + sb["title"] + "\n--- long description\n" + long_d)
        print("--- short title\n" + sb["short_title"] + "\n--- short description\n" + descriptions(sb, "https://youtu.be/XXXXXXXXXXX")[1])
        return 0
    long_id = upload(files["16x9.mp4"], sb["title"], long_d,
                     ["--ab-thumbnails", str(files["thumb-A.jpg"]), str(files["thumb-B.jpg"]), str(files["thumb-C.jpg"])])
    _, short_d = descriptions(sb, f"https://youtu.be/{long_id}")
    short_id = upload(files["9x16.mp4"], sb["short_title"], short_d, ["--thumbnail", str(files["thumb-A.jpg"])])
    today = dt.date.today().isoformat()
    ledger = json.loads(LEDGER.read_text()) if LEDGER.exists() else []
    ledger.append({"slug": sb["id"], "app": sb["app"], "date": today, "title": sb["title"],
                   "long_id": long_id, "short_id": short_id, "sources": sb.get("sources", [])})
    LEDGER.write_text(json.dumps(ledger, indent=1) + "\n")
    rot = json.loads(ROTATION.read_text())
    if rot["cycle"][rot["next"] % len(rot["cycle"])] == sb["app"]:
        rot["next"] = (rot["next"] + 1) % len(rot["cycle"])
        ROTATION.write_text(json.dumps(rot, indent=1) + "\n")
    if CHANGELOG.exists():
        subprocess.run([PY, str(CHANGELOG), "add", "--date", today, "--area", "content",
                        "--what", f"Daily how-to video published: {sb['title']} (long {long_id}, Short {short_id})",
                        "--affected", f"youtube-howto visits to {sb['page']}; views of {long_id} and {short_id}",
                        "--comparison", "other apps' pages and earlier how-to videos",
                        "--metric", "views, utm_source=youtube-howto sessions and trials"], check=False)
    print(f"published: https://youtu.be/{long_id} (A/B/C test) and https://youtube.com/shorts/{short_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
