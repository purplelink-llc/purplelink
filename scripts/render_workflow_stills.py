#!/usr/bin/env python3
"""Render the publication-workflow hero poster and station card stills.

Serves site/ on a free local port, loads the same module the page uses
(site/assets/js/workflow-hero.js, renderStill) in headless Chromium, screenshots the
canvas and encodes WebP with Pillow. Writes to site/assets/img/workflow/:
  hero-poster.webp (1200x675), station-<name>.webp (800x500), each plus a -light variant.

Usage: python3 scripts/render_workflow_stills.py [--only hero|review|...] [--max-kb 60]
"""
import argparse, http.server, io, socketserver, sys, threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
OUT = SITE / "assets" / "img" / "workflow"
NAMES = ["review", "coherence", "citations", "revision", "response"]

HARNESS = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>wf</title>
<link rel="stylesheet" href="/styles.css"><link rel="stylesheet" href="/assets/css/workflow-hero.css">
<style>html,body{margin:0;padding:0;background:var(--bg)}#h{border-radius:0;max-width:none}
#h.hero{width:1200px;height:675px}#h.card{width:800px;height:500px}</style></head>
<body><div class="wf-hero hero" id="h"></div>
<script type="module">
import { renderStill } from '/assets/js/workflow-hero.js';
window.wfDraw = async (name, theme, cls) => {
  const el = document.getElementById('h'); el.className = 'wf-hero ' + cls;
  if (theme === 'light') document.documentElement.setAttribute('data-theme', 'light');
  else document.documentElement.removeAttribute('data-theme');
  const stage = await renderStill(el, name);
  window.__stage = stage; return true;
};
window.wfClear = () => { if (window.__stage) { window.__stage.destroy(); window.__stage = null; } document.getElementById('h').className = 'wf-hero'; };
</script></body></html>"""


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(SITE), **k)

    def do_GET(self):
        if self.path.split("?")[0] == "/__wf_harness.html":
            b = HARNESS.encode()
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
            return
        super().do_GET()

    def log_message(self, *a):
        pass


def encode_webp(png: bytes, max_kb: int) -> bytes:
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert("RGB")
    for q in (82, 78, 74, 70, 64, 58, 50):
        buf = io.BytesIO(); im.save(buf, "WEBP", quality=q, method=6)
        if len(buf.getvalue()) <= max_kb * 1024:
            break
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["hero"] + NAMES)
    ap.add_argument("--max-kb", type=int, default=60)
    args = ap.parse_args()
    from playwright.sync_api import sync_playwright

    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [("hero", "hero", "hero-poster")] + [(n, "card", f"station-{n}") for n in NAMES]
    if args.only:
        jobs = [j for j in jobs if j[0] == args.only]
    errors = []
    try:
        with sync_playwright() as p:
            kw = {"args": ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]}
            if not Path(p.chromium.executable_path).exists():  # pinned build missing: use any installed headless shell
                found = sorted(Path.home().glob("Library/Caches/ms-playwright/chromium_headless_shell-*/*/chrome-headless-shell"))
                if found:
                    kw["executable_path"] = str(found[-1])
            br = p.chromium.launch(**kw)
            ctx = br.new_context(viewport={"width": 1200, "height": 675}, device_scale_factor=1)
            page = ctx.new_page()
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"http://127.0.0.1:{port}/__wf_harness.html")
            page.wait_for_function("typeof window.wfDraw === 'function'")
            for theme in ("dark", "light"):
                for name, cls, stem in jobs:
                    page.evaluate("([n,t,c]) => window.wfDraw(n,t,c)", [name, theme, cls])
                    png = page.locator("#h").screenshot()
                    data = encode_webp(png, args.max_kb)
                    out = OUT / (stem + ("-light" if theme == "light" else "") + ".webp")
                    out.write_bytes(data)
                    print(f"{out.relative_to(ROOT)}  {len(data)/1024:.1f} KB")
                    page.evaluate("window.wfClear()")
            br.close()
    finally:
        srv.shutdown()
    if errors:
        print("console errors:", *errors, sep="\n  ", file=sys.stderr); sys.exit(1)


if __name__ == "__main__":
    main()
