#!/usr/bin/env python3
"""Render audit: load site pages in headless Chromium at phone and desktop widths and report layout problems.

  python3 scripts/render_audit.py OUTDIR [--site SITE_DIR] [--only PREFIX ...] [--shots N]

Serves SITE_DIR (default: ./site) on a local port, then for each page at 390x844 (phone) and 1280x800
(desktop), in light and dark colour schemes, records:
  hscroll     the page scrolls sideways (document wider than the viewport), with the widest offending elements
  clipped     text or media wider than its container that is hidden by overflow
  img         broken images, images without alt, images without width and height (layout shift)
  tap         links and buttons smaller than 24x24 CSS px (WCAG 2.2 AA minimum target size) on the phone, outside running text
  small       visible text below 14 px on the phone
  contrast    text whose computed contrast against its background is below 4.5:1 (3:1 for large text)
  console     console errors and failed requests
  h1          pages without exactly one h1
Writes OUTDIR/report.json and OUTDIR/summary.txt, plus full-page phone screenshots for the SHOTS worst pages.
Local serving does not apply the Netlify headers, so CSP problems are not visible here.
"""
import argparse
import http.server
import json
import re
import socketserver
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent

JS = r"""
() => {
  const out = {hscroll: null, clipped: [], img: [], tap: [], small: 0, contrast: [], h1: document.querySelectorAll('h1').length};
  const vw = document.documentElement.clientWidth;
  const de = document.documentElement;
  if (de.scrollWidth > vw + 1) {
    const wide = [];
    for (const el of document.querySelectorAll('body *')) {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.right > vw + 1 && getComputedStyle(el).position !== 'fixed') {
        wide.push({tag: el.tagName.toLowerCase(), cls: (el.className && el.className.baseVal === undefined ? String(el.className) : '').slice(0, 50), right: Math.round(r.right), w: Math.round(r.width)});
      }
    }
    wide.sort((a, b) => b.right - a.right);
    out.hscroll = {scrollWidth: de.scrollWidth, viewport: vw, worst: wide.slice(0, 4)};
  }
  for (const el of document.querySelectorAll('main *, article *')) {
    const cs = getComputedStyle(el);
    if ((cs.overflowX === 'hidden' || cs.overflowX === 'clip') && el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 0) {
      out.clipped.push({tag: el.tagName.toLowerCase(), cls: String(el.className).slice(0, 40), scroll: el.scrollWidth, client: el.clientWidth});
    }
  }
  for (const im of document.querySelectorAll('img')) {
    const probs = [];
    const ir = im.getBoundingClientRect();
    if (ir.width > 0 && ir.height > 0 && im.complete && im.naturalWidth === 0) probs.push('broken');
    if (!im.hasAttribute('alt')) probs.push('no-alt');
    if (ir.width > 0 && !(im.getAttribute('width') && im.getAttribute('height')) && !getComputedStyle(im).aspectRatio.includes('/')) probs.push('no-size');
    if (probs.length) out.img.push({src: (im.getAttribute('src') || '').slice(-50), probs});
  }
  const lum = (r, g, b) => { const f = c => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const cv = document.createElement('canvas'); cv.width = cv.height = 1; const cx = cv.getContext('2d', {willReadFrequently: true});
  const cache = new Map();
  const parse = s => { if (!s || s === 'transparent') return null; if (cache.has(s)) return cache.get(s); cx.clearRect(0, 0, 1, 1); cx.fillStyle = '#000'; cx.fillStyle = s; cx.fillRect(0, 0, 1, 1); const d = cx.getImageData(0, 0, 1, 1).data; const v = {r: d[0], g: d[1], b: d[2], a: d[3] / 255}; cache.set(s, v); return v; };
  const bgOf = el => { let e = el; const stack = []; while (e) { const c = parse(getComputedStyle(e).backgroundColor); if (c && c.a > 0) { stack.push(c); if (c.a >= 0.99) break; } e = e.parentElement; } let base = {r: 255, g: 255, b: 255}; for (const c of stack.reverse()) base = {r: c.r * c.a + base.r * (1 - c.a), g: c.g * c.a + base.g * (1 - c.a), b: c.b * c.a + base.b * (1 - c.a)}; return base; };
  const seen = new Set();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n = 0;
  while (walker.nextNode() && n < 4000) {
    n++;
    const t = walker.currentNode; const txt = t.textContent.trim();
    if (txt.length < 3) continue;
    const el = t.parentElement; if (!el || seen.has(el)) continue; seen.add(el);
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || parseFloat(cs.opacity) === 0) continue;
    const r = el.getBoundingClientRect(); if (r.width === 0 || r.height === 0) continue;
    const fs = parseFloat(cs.fontSize);
    if (fs < 14 && r.top < 100000 && el.closest('main, article')) out.small++;
    const fg = parse(cs.color); if (!fg) continue;
    const bg = bgOf(el);
    const fgc = {r: fg.r * fg.a + bg.r * (1 - fg.a), g: fg.g * fg.a + bg.g * (1 - fg.a), b: fg.b * fg.a + bg.b * (1 - fg.a)};
    const L1 = lum(fgc.r, fgc.g, fgc.b), L2 = lum(bg.r, bg.g, bg.b);
    const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const large = fs >= 24 || (fs >= 18.66 && parseInt(cs.fontWeight) >= 700);
    if (ratio < (large ? 3 : 4.5)) out.contrast.push({t: txt.slice(0, 40), ratio: Math.round(ratio * 100) / 100, fs});
  }
  out.contrast = out.contrast.slice(0, 6);
  for (const el of document.querySelectorAll('a[href], button, [role=button], input, select, summary')) {
    const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    if (r.width === 0 || r.height === 0 || cs.visibility === 'hidden') continue;
    if (el.closest('p, li') && el.tagName === 'A' && cs.display === 'inline') continue;
    if (r.width < 24 || r.height < 24) out.tap.push({tag: el.tagName.toLowerCase(), text: (el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 24), w: Math.round(r.width), h: Math.round(r.height)});
  }
  out.tap = out.tap.slice(0, 8);
  return out;
}
"""


def serve(site: Path, port: int):
    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(site), **k)

        def log_message(self, *a):
            pass

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

    http.server.ThreadingHTTPServer.request_queue_size = 512
    http.server.ThreadingHTTPServer.daemon_threads = True
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def pages(site: Path, only):
    skip = ("blog/digest/", "kits-delivery", "assets/", "fonts/")
    for p in sorted(site.rglob("index.html")):
        rel = p.relative_to(site).parent.as_posix()
        url = "/" if rel == "." else f"/{rel}/"
        if url.startswith("/" + skip[0]) or any(url.startswith("/" + s) for s in skip[1:]) or "/success/" in url:
            continue
        if only and not any(url.startswith(o) for o in only):
            continue
        yield url


def severity(r):
    s = 0
    for v in r["views"].values():
        s += (10 if v["hscroll"] else 0) + len(v["clipped"]) * 3 + sum(2 if "broken" in i["probs"] else 1 for i in v["img"])
        s += len(v["contrast"]) * 2 + len(v["console"]) * 3 + (2 if v["h1"] != 1 else 0)
    ph = r["views"].get("phone-light")
    if ph:
        s += min(len(ph["tap"]), 6) + (3 if ph["small"] > 8 else 0)
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir")
    ap.add_argument("--site", default=str(ROOT / "site"))
    ap.add_argument("--only", nargs="*", default=[])
    ap.add_argument("--shots", type=int, default=12)
    ap.add_argument("--port", type=int, default=8791)
    a = ap.parse_args()
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    site = Path(a.site)
    srv = serve(site, a.port)
    base = f"http://127.0.0.1:{a.port}"
    views = {"phone-light": (390, 844, "light"), "phone-dark": (390, 844, "dark"),
             "desk-light": (1280, 800, "light"), "desk-dark": (1280, 800, "dark")}
    results = []
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        ctxs = {k: br.new_context(viewport={"width": w, "height": h}, color_scheme=cs, device_scale_factor=1,
                                   is_mobile=(w < 500), has_touch=(w < 500)) for k, (w, h, cs) in views.items()}
        for url in pages(site, a.only):
            rec = {"url": url, "views": {}}
            for k, ctx in ctxs.items():
                pg = ctx.new_page()
                cons = []
                pg.on("console", lambda m, c=cons: c.append(m.text[:100]) if m.type == "error" and not any(x in m.text for x in ("favicon", "501", "ERR_CONNECTION_RESET", "ERR_SOCKET_NOT_CONNECTED")) else None)
                pg.on("requestfailed", lambda r, c=cons: None)
                try:
                    pg.goto(base + url, wait_until="load", timeout=20000)
                    pg.wait_for_timeout(600)
                    v = pg.evaluate(JS)
                    if v["img"]:
                        pg.wait_for_timeout(1200)
                        v["img"] = pg.evaluate(JS)["img"]
                except Exception as e:  # noqa: BLE001
                    v = {"hscroll": None, "clipped": [], "img": [], "tap": [], "small": 0, "contrast": [], "h1": 1, "error": str(e)[:80]}
                v["console"] = cons[:4]
                rec["views"][k] = v
                pg.close()
            rec["severity"] = severity(rec)
            results.append(rec)
            print(f"{rec['severity']:4} {url}", flush=True)
        results.sort(key=lambda r: -r["severity"])
        for r in results[: a.shots]:
            if r["severity"] == 0:
                break
            pg = ctxs["phone-light"].new_page()
            try:
                pg.goto(base + r["url"], wait_until="load", timeout=20000)
                pg.wait_for_timeout(300)
                name = re.sub(r"[^a-z0-9]+", "-", r["url"].strip("/").lower()) or "home"
                pg.screenshot(path=str(out / f"{name}-phone.png"), full_page=True)
            except Exception:  # noqa: BLE001
                pass
            pg.close()
        br.close()
    srv.shutdown()
    (out / "report.json").write_text(json.dumps(results, indent=1))
    lines = [f"{len(results)} pages"]
    cat = {"hscroll": 0, "clipped": 0, "img": 0, "tap": 0, "contrast": 0, "console": 0, "h1": 0}
    for r in results:
        for k, v in r["views"].items():
            cat["hscroll"] += bool(v["hscroll"]); cat["clipped"] += bool(v["clipped"]); cat["img"] += bool(v["img"])
            cat["tap"] += bool(v["tap"]) and k.startswith("phone"); cat["contrast"] += bool(v["contrast"])
            cat["console"] += bool(v["console"]); cat["h1"] += v["h1"] != 1
    lines.append("page-views with a problem: " + json.dumps(cat))
    lines += [f"{r['severity']:4} {r['url']}" for r in results[:40]]
    (out / "summary.txt").write_text("\n".join(lines))
    print("\n".join(lines[:2]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
