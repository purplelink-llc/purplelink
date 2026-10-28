#!/usr/bin/env python3
"""Publish a built problem-and-fix video: the 16:9 tutorial (public, Test & Compare A/B/C) and the 9:16 Short
(public, thumbnail A, linking to the tutorial). Records the ledger, advances the rotation, logs the change.

    python3 scripts/howto-publish.py <slug> [--dry-run]

Refuses unless scripts/howto_gate.py passes and video/out/howto/<slug>/ holds both cuts and all three thumbnails.
A kill switch file at ~/.purplelink/howto/PAUSE stops every publish. Links are tagged utm_source=youtube, utm_medium=video|short,
utm_campaign=howto-link-test, utm_content=<slug> (the Short adds -short) for the link placement test.
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


LINK_TEST_START = dt.date(2026, 10, 20)  # switchback test howto-link-placement, 28 days, review 2026-11-17


def eastern_today() -> dt.date:
    """The test's day boundary is US Eastern, whatever timezone this Mac is in."""
    from zoneinfo import ZoneInfo
    return dt.datetime.now(ZoneInfo("America/New_York")).date()


def link_arm(day: dt.date) -> str:
    """Switchback by day-of-month: odd days are arm B (tracked link as the description's first line),
    even days are arm A (link stays after the app paragraph). Pinned comments are not possible: uploads go
    through the Studio browser (yt-upload.py) and there is no Purplelink API token, so arm B means
    "first line only"."""
    if day < LINK_TEST_START:
        return "A"
    return "B" if day.day % 2 == 1 else "A"


def tagged(page: str, medium: str, slug: str) -> str:
    """Tracked link. utm_content is the video's slug (the video id is not known before upload); the ledger maps
    slug to long_id and short_id. The Short's slug carries a -short suffix."""
    return (f"{page}?utm_source=youtube&utm_medium={medium}&utm_campaign=howto-link-test"
            f"&utm_content={slug}")


def hub_links(sb: dict, hub=None) -> dict:
    """Each cut gets its own utm_content from the marketing hub (scripts/hub/hub.py make_utm), checked against every
    tag already in use: the long video <slug>, the Short <slug>-short (the link test's names, kept until it ends on
    2026-11-17) and the Instagram Reel <slug>-reel. A taken name gets -2, -3 ... Returns {"long", "short"} (links) and
    {"long_tag", "short_tag", "reel_tag"}."""
    if hub is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("hub", REPO / "scripts" / "hub" / "hub.py")
        hub = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hub)
    p = hub.paths()
    page, app = sb["page"], str(sb.get("app") or "")
    common = {"source": "youtube", "campaign": "howto-link-test"}
    long_url = hub.make_utm(p, page, app, "youtube", medium="video", content=sb["id"], **common)
    long_tag = re.search(r"utm_content=([\w.\-]+)", long_url).group(1)
    short_url = hub.make_utm(p, page, app, "youtube-short", medium="short", content=f"{long_tag}-short", **common)
    short_tag = re.search(r"utm_content=([\w.\-]+)", short_url).group(1)
    reel = hub.make_utm(p, page, app, "instagram", source="instagram", medium="social", campaign="ig-reel",
                        content=f"{long_tag}-reel")
    reel_tag = re.search(r"utm_content=([\w.\-]+)", reel).group(1)
    tags = {long_tag, short_tag, reel_tag}
    if len(tags) != 3:
        raise SystemExit(f"tracking tags collide ({long_tag}, {short_tag}, {reel_tag}); not publishing")
    return {"long": long_url, "short": short_url, "long_tag": long_tag, "short_tag": short_tag, "reel_tag": reel_tag}


TRENDS_ROOT = Path(os.environ.get("TRENDS_ROOT", "/Volumes/Extreme SSD/TikTokPipeline"))
FALLBACK_TAGS = ["macos", "mactips", "techtips"]


# Content tag per app: what this video is about, after the two core tags (mac, macos).
APP_TAGS = {
    "moderntex": ["latex"], "legroom": ["macstorage"], "outbound-veil": ["dataprivacy"],
    "panely": ["windowmanagement"], "summonly": ["spotlight"], "tapefolio": ["transcription"],
    "keyfeel": ["typingsounds"], "batterymeter": ["macbattery"], "vitae": ["academiclife"],
    "paper-review": ["academicwriting"], "scholar-utility-belt": ["googlescholar"],
}


def content_tags(sb: dict) -> list[str]:
    """Per-video content tags: the app's tag, plus #overleaf when the storyboard mentions it."""
    tags = list(APP_TAGS.get(str(sb.get("app", "")).lower(), []))
    if "overleaf" in json.dumps(sb).lower() and "overleaf" not in tags:
        tags.append("overleaf")
    return tags[:2]


def trend_tags(sb: dict, short: bool) -> str:
    """Hashtags for the description from the shared trends system (topic mac_howto, YouTube list):
    2 core, the video's content tags, then trending. YouTube shows the first three above the title,
    so core + content come first; the Short gets 3 and then #shorts, the long video 4."""
    tags = list(FALLBACK_TAGS)
    try:
        r = subprocess.run([PY, "-m", "shared_media.trends.cli", "assemble", "--topic", "mac_howto",
                            "--platform", "youtube", "--content", ",".join(content_tags(sb))],
                           cwd=TRENDS_ROOT, capture_output=True, text=True, timeout=60)
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


def yt_safe(cmd: str) -> str:
    """Studio refuses a description with < or > ("Angled brackets aren't allowed"), which left the 2026-10-18 upload
    a draft. A trailing "> file" redirect becomes a note in words; any other bracket is dropped."""
    m = re.match(r"^(.*?)\s*>\s*(\S+)$", cmd)
    if m:
        cmd = f"{m.group(1)}   (save the output as {m.group(2)}, as in the video)"
    return cmd.replace("<", "").replace(">", "")


def descriptions(sb: dict, long_url: str | None, arm: str = "A", links: dict | None = None) -> tuple[str, str]:
    """links: hub_links(sb) (the publish path); without it the link test's default tags are used (dry runs, tests)."""
    links = links or {"long": tagged(sb["page"], "video", sb["id"]),
                      "short": tagged(sb["page"], "short", sb["id"] + "-short")}
    scenes = sb["scenes"]
    hook = next(s for s in scenes if s["type"] == "hook")
    cause = next((s for s in scenes if s["type"] == "cause"), None)
    cmds = [yt_safe(l[2:]) for s in scenes if s["type"] == "steps" for l in s.get("lines", []) if l.startswith("$ ")]
    app = next(s for s in scenes if s["type"] == "app")
    lead = hook["title"] if hook["title"].rstrip()[-1:] in ".?!" else hook["title"] + "."  # no "?." after a question
    opener = f"{lead} {hook.get('sub', '')}".strip()
    parts = [opener]
    if cause:
        parts.append(cause["text"])
    if cmds:
        parts.append("The fix, in Terminal:\n" + "\n".join(cmds))
    link = links["long"]
    if arm == "B":
        parts.append(f"{app['name']}: {app['line']}")
    else:
        parts.append(f"{app['name']}: {app['line']}\n{link}")
    if sb.get("sources"):
        parts.append("Where this comes up:\n" + "\n".join(sb["sources"]))
    parts.append(trend_tags(sb, short=False))
    if arm == "B":
        parts.insert(0, f"{app['name']}: {link}")
    long_d = "\n\n".join(parts)
    short_parts = [opener]
    if cmds:
        short_parts.append("\n".join(cmds))
    if long_url:
        short_parts.append(f"Full walkthrough: {long_url}")
    short_parts.append(f"{app['name']}: {links['short']}")
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


def add_captions(video_id: str, srt: Path) -> dict:
    """Caption track from the build's .srt (video/src/howto/srt.js) via scripts/yt-captions.py (channel-guarded).
    Never fails the publish: a missing file, refusal or API error is reported and recorded, the video stays up."""
    if not srt.exists():
        print(f"captions: {srt.name} missing (built before captions existed?); skipped")
        return {"skipped": "no srt"}
    r = subprocess.run([PY, str(REPO / "scripts" / "yt-captions.py"), video_id, str(srt), "--channel", "purplelink"],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        print(f"captions: not added to {video_id} (exit {r.returncode}): {(r.stderr or r.stdout).strip()[-300:]}")
        return {"error": f"exit {r.returncode}"}
    try:
        res = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        res = {"raw": r.stdout.strip()[-200:]}
    print(f"captions: {video_id}: {res}")
    return res


def add_reel(short_file: Path, short_id: str, title: str, desc: str, page: str, long_id: str, utm_content: str = "") -> dict:
    """Hand the Short to the Instagram Reel inbox (backend/socialpost/instagram, Ben's 2026-10-23 request): the 9:16
    cut becomes the Purplelink Instagram Reel, queued and vetted by the social pipeline. Never fails the publish."""
    import tempfile
    social = REPO / "backend" / "scripts" / "social.py"
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
        fh.write(desc)
    try:
        r = subprocess.run([PY, str(social), "instagram", "reel-add", "--video", str(short_file), "--youtube-id", short_id,
                            "--title", title, "--description-file", fh.name, "--link", page, "--also", long_id,
                            *(["--utm-content", utm_content] if utm_content else [])],
                           capture_output=True, text=True, timeout=1800)
    except Exception as e:
        print(f"instagram: Reel not added ({type(e).__name__}); the channel scan will flag it")
        return {"error": type(e).__name__}
    finally:
        Path(fh.name).unlink(missing_ok=True)
    out = (r.stdout or r.stderr).strip()[-300:]
    print(f"instagram: {out}")
    return {"ok": r.returncode == 0, "utm_content": utm_content}


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
    arm = link_arm(eastern_today())
    links = hub_links(sb)
    long_d, _ = descriptions(sb, None, arm, links)
    if not dry:   # the rendered-video check (pops, freezes, contrast) must pass for both cuts before anything uploads
        vq = [PY, str(REPO / "scripts" / "howto_gate.py"), str(sbp)]
        for k in ("16x9.mp4", "9x16.mp4"):
            vq += ["--video", str(files[k])]
        if subprocess.run(vq).returncode != 0:
            raise SystemExit("video check failed: not publishing")
    if dry:
        print(f"--- link placement arm {arm} (Eastern date {eastern_today()})")
        print("--- long title\n" + sb["title"] + "\n--- long description\n" + long_d)
        print("--- short title\n" + sb["short_title"] + "\n--- short description\n"
              + descriptions(sb, "https://youtu.be/XXXXXXXXXXX", arm, links)[1])
        print(f"--- tags: long {links['long_tag']}, Short {links['short_tag']}, Reel {links['reel_tag']}")
        return 0
    long_id = upload(files["16x9.mp4"], sb["title"], long_d,
                     ["--ab-thumbnails", str(files["thumb-A.jpg"]), str(files["thumb-B.jpg"]), str(files["thumb-C.jpg"])])
    _, short_d = descriptions(sb, f"https://youtu.be/{long_id}", arm, links)
    short_id = upload(files["9x16.mp4"], sb["short_title"], short_d, ["--thumbnail", str(files["thumb-A.jpg"])])
    captions = {"long": add_captions(long_id, out / f"{slug}-16x9.srt"),
                "short": add_captions(short_id, out / f"{slug}-9x16.srt")}
    instagram = add_reel(files["9x16.mp4"], short_id, sb["short_title"], short_d, sb["page"], long_id, links["reel_tag"])
    today = eastern_today().isoformat()
    ledger = json.loads(LEDGER.read_text()) if LEDGER.exists() else []
    ledger.append({"slug": sb["id"], "app": sb["app"], "date": today, "title": sb["title"],
                   "long_id": long_id, "short_id": short_id, "link_arm": arm,
                   "link_utm_content": links["long_tag"], "short_utm_content": links["short_tag"], "sources": sb.get("sources", []), "captions": captions,
                   "instagram": instagram})
    LEDGER.write_text(json.dumps(ledger, indent=1) + "\n")
    rot = json.loads(ROTATION.read_text())
    if rot["cycle"][rot["next"] % len(rot["cycle"])] == sb["app"]:
        rot["next"] = (rot["next"] + 1) % len(rot["cycle"])
        ROTATION.write_text(json.dumps(rot, indent=1) + "\n")
    if CHANGELOG.exists():
        subprocess.run([PY, str(CHANGELOG), "add", "--date", today, "--area", "content",
                        "--what", f"Daily how-to video published: {sb['title']} (long {long_id}, Short {short_id})",
                        "--affected", f"youtube visits (utm_campaign=howto-link-test) to {sb['page']}; views of {long_id} and {short_id}",
                        "--comparison", "other apps' pages and earlier how-to videos",
                        "--metric", "views, utm_campaign=howto-link-test sessions and trials"], check=False)
    print(f"published: https://youtu.be/{long_id} (A/B/C test) and https://youtube.com/shorts/{short_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
