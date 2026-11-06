#!/usr/bin/env python3
"""Publish gate for the daily problem-and-fix videos (video/storyboards/howto/<slug>.json).

    python3 scripts/howto_gate.py video/storyboards/howto/<slug>.json [--offline] [--rebuild]

The daily pipeline publishes without a human look (Ben's choice, 2026-10-15), so this gate is the review. It exits 1
and lists every problem when any check fails; build-howto.mjs refuses to render and howto-publish.py refuses to
upload. Checks:
  structure   required fields, scene types, an app from video/howto/rotation.json, a slug not already in the ledger
  text        no prices, emoji, em dashes or hype words in titles, narration or on-screen text
  commands    no destructive commands; sudo only for allowlisted tools (tlmgr), and only with tug.org/ctan.org docs
  honesty     every output line on screen appears in a recorded verification run, and the gate re-runs those
              commands itself (with TeX Live on PATH) to confirm the recorded output is real
  sources     at least one https demand source; every documentation link answers 200; images exist
  thumbnails  (storyboards not yet in the ledger) A is the "diff" design: a short hook plus the real before and after
              strings, each copied verbatim from the storyboard's on-screen lines; a face variant needs a real image

Rendered-video step (run after the full build, before publishing; build-howto.mjs leaves <slug>-<format>.qa.json
next to each mp4 with the measured text boxes):

    python3 scripts/howto_gate.py video/storyboards/howto/<slug>.json --video video/out/howto/<slug>/<slug>-16x9.mp4 \
        [--video .../<slug>-9x16.mp4]

For each mp4 it uses TikTokPipeline/shared_media/video_qa.py (HOWTO_VIDEO_QA overrides the path) and fails on any
one-frame pop, any frozen stretch over 6 s outside the closing bumper, and any text under 4.5:1 contrast. It writes a
contact sheet next to the render (<name>-contact-sheet.jpg) and prints its path; the daily task Reads it.
"""
from __future__ import annotations
import json, os, re, subprocess, sys, urllib.request, ssl
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VIDEO = REPO / "video"
ROTATION = VIDEO / "howto" / "rotation.json"
LEDGER = VIDEO / "howto" / "ledger.json"
TYPES = {"hook", "symptom", "cause", "steps", "panel", "check", "app"}
TEX_BIN = Path.home() / "Library" / "TinyTeX" / "bin" / "universal-darwin"

DENY = [r"\brm\s+-[a-z]*r", r"\bcurl\b[^|]*\|\s*(ba|z)?sh", r"\bwget\b[^|]*\|\s*(ba|z)?sh", r"\bdd\s+if=", r"\bmkfs\b",
        r"diskutil\s+(erase|zero|secureErase|partition)", r"csrutil\s+disable", r"spctl\s+--master-disable",
        r"chmod\s+(-R\s+)?777", r"\bsudo\s+rm\b", r">\s*/dev/disk", r"defaults\s+delete\b", r"killall\s+-9\s+(Finder|Dock|loginwindow)"]
SUDO_OK = {"tlmgr": ("tug.org", "ctan.org")}   # tool -> doc domains that must back it
HYPE = re.compile(r"\b(revolutionary|game[- ]chang\w*|seamless\w*|supercharg\w*|unleash\w*|effortless\w*|ultimate|"
                  r"blazing\w*|insane\w*|mind[- ]blow\w*|you won'?t believe|secret trick|hack your)\b", re.I)
EMOJI = re.compile(r"[\U0001F300-\U0001FAFF☀-➿⭐✅]")
PRICE = re.compile(r"[$€£]\s?\d")


def norm(s: str) -> str:
    """Shells print 'zsh:1:' when run with -c and 'zsh:' interactively; treat them as the same line."""
    return re.sub(r"\b(zsh|bash|sh):\d+:", r"\1:", s).strip()


def texts(sb: dict) -> list[tuple[str, str]]:
    out = [("title", sb.get("title", "")), ("short_title", sb.get("short_title", ""))]
    for i, sc in enumerate(sb.get("scenes", [])):
        for k in ("narration", "title", "sub", "text", "line", "ui", "ok", "kicker"):
            if sc.get(k):
                out.append((f"scene {i} {k}", sc[k]))
        for ln in sc.get("lines", []):
            out.append((f"scene {i} line", ln))
    for k, v in (sb.get("thumbs") or {}).items():
        for f in ("msg", "line", "sub", "hook"):
            if v.get(f):
                out.append((f"thumb {k} {f}", v[f]))
    return out


NUMBER_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]


def on_screen(sb: dict) -> str:
    """Every on-screen line of the storyboard, whitespace folded and the shell prompt dropped."""
    out = []
    for sc in sb.get("scenes", []):
        for ln in sc.get("lines", []):
            out.append(re.sub(r"\s+", " ", ln[2:] if ln.startswith("$ ") else ln).strip())
    return "\n".join(out)


def thumb_checks(sb: dict) -> list[str]:
    """Ben's rule (2026-11-06): the default thumbnail (A, the control Test & Compare starts from) is the diff design,
    built from strings the video really shows; the hook may only claim what the video delivers."""
    errs: list[str] = []
    th = sb.get("thumbs") or {}
    a = th.get("A") or {}
    if a.get("kind") != "diff":
        return ["thumbs.A must be kind 'diff' (hook, before, after) for a new video"]
    hook = (a.get("hook") or "").strip()
    if not hook or len(hook) > 24:
        errs.append("thumbs.A.hook is required and at most 24 characters")
    if not a.get("after"):
        errs.append("thumbs.A.after is required (the fix line the video shows)")
    screen = on_screen(sb)
    for f in ("before", "after"):
        v = re.sub(r"\s+", " ", a.get(f) or "").strip()
        if v and v not in screen:
            errs.append(f"thumbs.A.{f} {v!r} is not copied verbatim from an on-screen line of the video")
    m = re.match(r"(?i)(\d+|" + "|".join(NUMBER_WORDS) + r")\s+(\w+)", hook)
    if m:
        word, unit = m.group(1).lower(), m.group(2).lower()
        if unit in ("click", "clicks", "tap", "taps"):
            errs.append("thumbs.A.hook counts clicks, which the gate cannot verify: drop the number")
        elif unit in ("command", "commands"):
            n = int(word) if word.isdigit() else NUMBER_WORDS.index(word)
            cmds = sum(1 for sc in sb.get("scenes", []) if sc.get("type") == "steps"
                       for ln in sc.get("lines", []) if ln.startswith("$ "))
            if n != cmds:
                errs.append(f"thumbs.A.hook says {n} commands but the steps scene shows {cmds}")
    for k, v in th.items():
        if v.get("kind") == "face":
            f = v.get("face")
            if not f or not (REPO / f).is_file():
                errs.append(f"thumbs.{k} is a face variant without a real image (set face to an existing file); "
                            "use a non-face variant until the face exists. Placeholders are never uploaded")
    return errs


def head_ok(url: str) -> bool:
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = ssl.create_default_context()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh) purplelink-howto-gate"})
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            return r.status == 200
    except Exception:
        return False


def rerun(cmd: str) -> str:
    env = {"PATH": f"{TEX_BIN}:/usr/bin:/bin:/usr/sbin:/sbin", "HOME": str(Path.home()), "LANG": "en_US.UTF-8"}
    r = subprocess.run(["/bin/zsh", "-c", cmd], capture_output=True, text=True, timeout=120, env=env,
                       cwd=str(Path(os.environ.get("TMPDIR", "/tmp"))))
    return r.stdout + r.stderr


def check(sb_path: Path, offline: bool, rebuild: bool) -> list[str]:
    errs: list[str] = []
    sb = json.loads(sb_path.read_text())
    E = errs.append
    # structure
    # "standalone": a one-off launch video for a product outside the daily rotation (Lenses). It skips the rotation,
    # ledger and demand-source checks; every text, command, link and visual check still applies.
    standalone = bool(sb.get("standalone"))
    for k in ("id", "app", "title", "short_title", "url", "page", "verify", "scenes", "thumbs") + (() if standalone else ("sources",)):
        if not sb.get(k):
            E(f"missing field: {k}")
    if not str(sb.get("id", "")).startswith("howto-"):
        E("id must start with 'howto-'")
    rot = json.loads(ROTATION.read_text()) if ROTATION.exists() else {"apps": []}
    apps = {a["app"]: a for a in rot.get("apps", [])}
    if standalone:
        pass
    elif sb.get("app") not in apps:
        E(f"app {sb.get('app')!r} is not in the rotation ({', '.join(apps)})")
    elif not sb.get("page", "").startswith(apps[sb["app"]]["page"]):
        E(f"page must be the app's page {apps[sb['app']]['page']}")
    ledger = json.loads(LEDGER.read_text()) if LEDGER.exists() else []
    if not rebuild and not standalone and any(x.get("slug") == sb.get("id") for x in ledger):
        E(f"{sb.get('id')} is already published (ledger)")
    scenes = sb.get("scenes", [])
    kinds = [s.get("type") for s in scenes]
    if any(k not in TYPES for k in kinds):
        E(f"unknown scene type in {kinds}")
    for need in ("hook", "app"):
        if need not in kinds:
            E(f"needs a {need} scene")
    if "steps" not in kinds and "panel" not in kinds:
        E("needs a steps or panel scene")
    if not any(s.get("short") for s in scenes):
        E("no scene is marked short (the vertical cut would be empty)")
    for i, s in enumerate(scenes):
        if not (s.get("narration") or "").strip():
            E(f"scene {i} has no narration")
    for k in ("title", "short_title"):
        if len(sb.get(k, "")) > 100:
            E(f"{k} is over 100 characters")
    if set((sb.get("thumbs") or {}).keys()) != {"A", "B", "C"}:
        E("thumbs must hold variants A, B and C")
    elif len({v.get("kind") for v in sb["thumbs"].values()}) < 2:
        E("thumbs must use at least two templates")
    # thumbnails: a published storyboard keeps the thumbnails it shipped with
    if not any(x.get("slug") == sb.get("id") for x in ledger) and sb.get("thumbs"):
        for e in thumb_checks(sb):
            E(e)
    # text
    for where, t in texts(sb):
        if PRICE.search(t):
            E(f"{where}: a price ({t[:60]!r}); prices go stale, link the page instead")
        if EMOJI.search(t):
            E(f"{where}: emoji")
        if "—" in t:
            E(f"{where}: em dash")
        if HYPE.search(t):
            E(f"{where}: hype word {HYPE.search(t).group(0)!r}")
    # commands
    docs = (sb.get("verify") or {}).get("docs", [])
    for i, s in enumerate(scenes):
        for ln in s.get("lines", []):
            if not ln.startswith("$ "):
                continue
            cmd = ln[2:]
            for pat in DENY:
                if re.search(pat, cmd):
                    E(f"scene {i}: destructive command not allowed: {cmd}")
            m = re.match(r"sudo\s+(\S+)", cmd)
            if m:
                tool = m.group(1)
                if tool not in SUDO_OK:
                    E(f"scene {i}: sudo {tool} is not allowlisted")
                elif not any(any(d in u for d in SUDO_OK[tool]) for u in docs):
                    E(f"scene {i}: sudo {tool} needs documentation from {SUDO_OK[tool]}")
    # honesty
    runs = (sb.get("verify") or {}).get("runs", [])
    recorded = "\n".join(norm(l) for r in runs for l in r.get("output", "").splitlines())
    for i, s in enumerate(scenes):
        if s.get("type") not in ("symptom", "check"):
            continue
        for ln in s.get("lines", []):
            if ln.startswith("$ "):
                continue
            if norm(ln) not in recorded:
                E(f"scene {i}: on-screen output {ln!r} is not in any recorded verification run")
    if not offline:
        for r in runs:
            if r.get("rerun") is False:
                continue
            if re.search(r"\bsudo\b", r["cmd"]) or any(re.search(p, r["cmd"]) for p in DENY):
                E(f"verification command may not use sudo or destructive commands: {r['cmd']}")
                continue
            got = "\n".join(norm(l) for l in rerun(r["cmd"]).splitlines())
            for want in r.get("output", "").splitlines():
                if norm(want) and norm(want) not in got:
                    E(f"re-run of {r['cmd']!r} did not print {want!r}")
    # sources and assets
    srcs = sb.get("sources", [])
    if (not srcs and not standalone) or not all(u.startswith("https://") and "purplelink.llc" not in u for u in srcs):
        E("sources must be at least one https demand source outside purplelink.llc")
    if not offline:
        for u in docs + srcs:
            if not head_ok(u):
                E(f"link does not answer 200: {u}")
    for i, s in enumerate(scenes):
        for k in ("img", "icon"):
            if s.get(k) and not (REPO / s[k]).is_file():
                E(f"scene {i}: missing {k} {s[k]}")
    for k, v in (sb.get("thumbs") or {}).items():
        for f in ("img", "icon"):
            if isinstance(v.get(f), str) and not (REPO / v[f]).is_file():
                E(f"thumb {k}: missing {f} {v[f]}")
    return errs


VIDEO_QA = Path(os.environ.get("HOWTO_VIDEO_QA", "/Volumes/Extreme SSD/TikTokPipeline/shared_media/video_qa.py"))
MAX_STILL = 6.0
MIN_CONTRAST = 4.5


def load_video_qa():
    """video_qa by path from the TikTokPipeline checkout; a clear error when it is missing."""
    import importlib.util
    if not VIDEO_QA.is_file():
        raise RuntimeError(f"video_qa not found at {VIDEO_QA} (pull /Volumes/Extreme SSD/TikTokPipeline, or set HOWTO_VIDEO_QA)")
    spec = importlib.util.spec_from_file_location("video_qa", VIDEO_QA)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check_video(video: Path, sheet: Path | None = None) -> list[str]:
    """Problems in one rendered how-to video. Needs <video stem>.qa.json beside it (written by build-howto.mjs)."""
    errs: list[str] = []
    video = Path(video)
    if not video.is_file():
        return [f"{video}: rendered video not found"]
    try:
        qa = load_video_qa()
    except Exception as e:  # noqa: BLE001
        return [f"{video.name}: cannot run the visual check: {e}"]
    meta_path = video.with_suffix(".qa.json")
    if not meta_path.is_file():
        return [f"{video.name}: {meta_path.name} is missing (rebuild with build-howto.mjs so text boxes are measured)"]
    meta = json.loads(meta_path.read_text())
    regions = [{"name": r["name"], "rect": r["rect"], "t": r["t"]} for r in meta.get("regions", [])]
    if not regions:
        errs.append(f"{video.name}: no measured text boxes in {meta_path.name}")
    try:
        pops = qa.pop_scan(video)
        freezes = qa.frozen_scan(video, max_still=MAX_STILL, final_hold=float(meta.get("final_hold", 0)))
        contrast = qa.contrast_check(video, regions, minimum=MIN_CONTRAST) if regions else []
        sheet = sheet or video.with_name(video.stem + "-contact-sheet.jpg")
        res = qa.contact_sheet(video, sheet, n=30, cols=6)
    except Exception as e:  # noqa: BLE001
        return errs + [f"{video.name}: visual check crashed: {e}"]
    print(f"contact sheet: {res['path']}")
    for p in pops:
        errs.append(f"{video.name}: one-frame pop at {p['time']}s (frame {p['frame']})")
    for f in freezes:
        errs.append(f"{video.name}: nothing changes for {f['duration']}s ({f['start']}s to {f['end']}s)")
    for c in contrast:
        if c["status"] == "low":
            errs.append(f"{video.name}: {c['name']} at {c['time']}s has contrast {c['ratio']}:1, under {MIN_CONTRAST}:1")
        else:
            print(f"warning: {video.name}: no text found in {c['name']} at {c['time']}s (box {c['rect']})")
    return errs


def main() -> int:
    argv = sys.argv[1:]
    videos = [argv[i + 1] for i, a in enumerate(argv) if a == "--video" and i + 1 < len(argv)]
    if videos:
        errs = []
        for v in videos:
            errs += check_video(Path(v))
        if errs:
            print(f"VIDEO CHECK FAILED ({len(errs)}):")
            for e in errs:
                print(f"  - {e}")
            return 1
        print("video check passed")
        return 0
    args = [a for i, a in enumerate(argv) if not a.startswith("--") and not (i and argv[i - 1] == "--video")]
    if not args:
        sys.exit(__doc__)
    errs = check(Path(args[0]).resolve(), "--offline" in sys.argv, "--rebuild" in sys.argv)
    if errs:
        print(f"GATE FAILED ({len(errs)}):")
        for e in errs:
            print(f"  - {e}")
        return 1
    print("gate passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
