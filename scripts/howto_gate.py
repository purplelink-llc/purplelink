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
"""
from __future__ import annotations
import json, os, re, subprocess, sys, urllib.request, ssl
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VIDEO = REPO / "video"
ROTATION = VIDEO / "howto" / "rotation.json"
LEDGER = VIDEO / "howto" / "ledger.json"
TYPES = {"hook", "symptom", "cause", "steps", "check", "app"}
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
        for f in ("msg", "line", "sub"):
            if v.get(f):
                out.append((f"thumb {k} {f}", v[f]))
    return out


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
    for k in ("id", "app", "title", "short_title", "url", "page", "sources", "verify", "scenes", "thumbs"):
        if not sb.get(k):
            E(f"missing field: {k}")
    if not str(sb.get("id", "")).startswith("howto-"):
        E("id must start with 'howto-'")
    rot = json.loads(ROTATION.read_text()) if ROTATION.exists() else {"apps": []}
    apps = {a["app"]: a for a in rot.get("apps", [])}
    if sb.get("app") not in apps:
        E(f"app {sb.get('app')!r} is not in the rotation ({', '.join(apps)})")
    elif not sb.get("page", "").startswith(apps[sb["app"]]["page"]):
        E(f"page must be the app's page {apps[sb['app']]['page']}")
    ledger = json.loads(LEDGER.read_text()) if LEDGER.exists() else []
    if not rebuild and any(x.get("slug") == sb.get("id") for x in ledger):
        E(f"{sb.get('id')} is already published (ledger)")
    scenes = sb.get("scenes", [])
    kinds = [s.get("type") for s in scenes]
    if any(k not in TYPES for k in kinds):
        E(f"unknown scene type in {kinds}")
    for need in ("hook", "steps", "app"):
        if need not in kinds:
            E(f"needs a {need} scene")
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
    if not srcs or not all(u.startswith("https://") and "purplelink.llc" not in u for u in srcs):
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


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
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
