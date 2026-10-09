#!/usr/bin/env python3
"""Permanently delete videos from the Purplelink channel through Studio in the automation Chrome (port 9340).

  python3 scripts/yt-delete.py --dry-run VIDEO_ID "expected title" [VIDEO_ID "expected title" ...]
  python3 scripts/yt-delete.py VIDEO_ID "expected title" ...

Only run for videos Ben has said to delete. A delete is permanent. Each video's title in Studio must equal the expected
title you pass, or that video is skipped. --dry-run opens the delete dialog and prints it without confirming.
Afterwards the public watch page is checked: a deleted video no longer answers oEmbed (404).
"""
import os, subprocess, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_tab import Tab  # noqa: E402

args = sys.argv[1:]
dry = "--dry-run" in args
args = [a for a in args if a != "--dry-run"]
pairs = list(zip(args[0::2], args[1::2]))
JS_ALL = """const all=[];(function walk(r){for(const e of r.querySelectorAll('*')){all.push(e);if(e.shadowRoot)walk(e.shadowRoot);}})(document);"""


def oembed(vid):
    return subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "20",
                           f"https://www.youtube.com/oembed?format=json&url=https://youtu.be/{vid}"], capture_output=True, text=True).stdout.strip()


for vid, expect in pairs:
    t = Tab.new(f"https://studio.youtube.com/video/{vid}/edit")
    try:
        urllib.request.urlopen(f"http://127.0.0.1:9340/json/activate/{t.info['id']}").read()
        t.wait_idle(8); time.sleep(6)
        title = t.eval("(()=>{" + JS_ALL + """const e=all.find(x=>x.id==='textbox'&&/title/i.test(x.getAttribute('aria-label')||''));return e?e.innerText.trim():''})()""")
        if title != expect:
            print(vid, "SKIPPED: title is", repr(title), "not", repr(expect)); continue
        t.click("ytcp-icon-button#overflow-menu-button"); time.sleep(1.5)
        t.click_text("Delete", exact=True); time.sleep(2)
        dlg = t.eval("(()=>{" + JS_ALL + """const ok=all.some(x=>/Permanently delete this video\\?/.test(x.textContent||'')&&/^ytcp-dialog$/i.test(x.tagName));
          const cb=all.find(x=>/^ytcp-checkbox-lit$/i.test(x.tagName)&&x.offsetParent!==null); const btn=all.find(x=>x.id==='confirm-button'&&x.offsetParent!==null);
          const views=(all.find(x=>/\\d+ views?/.test(x.innerText||'')&&x.children.length===0)||{}).innerText||'';
          return ok&&cb&&btn?'DIALOG OK '+views:'NO DIALOG'})()""")
        print(vid, "dialog:", dlg)
        if dry or dlg == "NO DIALOG":
            continue
        t.eval("(()=>{" + JS_ALL + """const c=all.find(x=>/^ytcp-checkbox-lit$/i.test(x.tagName)&&x.offsetParent!==null);if(c)c.click()})()""")
        time.sleep(1)
        t.eval("(()=>{" + JS_ALL + """const b=all.find(x=>x.id==='confirm-button'&&x.offsetParent!==null);if(b)b.click()})()""")
        time.sleep(6)
    finally:
        t.close()
    time.sleep(3)
    if not dry:
        print(vid, "oEmbed after delete:", oembed(vid), "(404 means gone)")
