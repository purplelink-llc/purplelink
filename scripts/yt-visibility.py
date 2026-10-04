#!/usr/bin/env python3
"""Set the visibility of existing Studio videos through the automation Chrome (port 9340).

  python3 scripts/yt-visibility.py unlisted VIDEO_ID [VIDEO_ID ...]

Only run for videos Ben has said to change. Confirms with the public oEmbed
endpoint (200 = public, 401/403/404 = not public).
"""
import os, subprocess, sys, time, urllib.request, importlib.util
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_tab import Tab  # noqa: E402
spec = importlib.util.spec_from_file_location("ytu", os.path.join(os.path.dirname(os.path.abspath(__file__)), "yt-upload.py"))
ytu = importlib.util.module_from_spec(spec); spec.loader.exec_module(ytu)

mode, ids = sys.argv[1].upper(), sys.argv[2:]
assert mode in ("PRIVATE", "UNLISTED", "PUBLIC")


def oembed(vid):
    return subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "20",
                           f"https://www.youtube.com/oembed?format=json&url=https://youtu.be/{vid}"],
                          capture_output=True, text=True).stdout.strip()


for vid in ids:
    tab = Tab.new(f"https://studio.youtube.com/video/{vid}/edit")
    try:
        urllib.request.urlopen(f"http://127.0.0.1:9340/json/activate/{tab.info['id']}").read()
        tab.wait_idle(8)
        ytu.wait_for(tab, "document.querySelectorAll('#textbox').length >= 2", 60)
        time.sleep(1.5)
        # open the visibility dialog: the dropdown shows the current state (Public/Unlisted/Private)
        pos = tab.eval("""(()=>{const all=[];(function walk(r){for(const e of r.querySelectorAll('*')){all.push(e);if(e.shadowRoot)walk(e.shadowRoot);}})(document);
          const e=all.find(x=>x.id==='visibility-text'); if(!e) return null;
          const b=e.getBoundingClientRect(); return [b.x+b.width/2,b.y+b.height/2]})()""")
        if not pos:
            print(vid, "visibility control not found"); continue
        tab.tap(pos[0], pos[1], pause=1.5)
        ytu.choose_visibility(tab, mode)
        time.sleep(0.8)
        tab.click("ytcp-button#save-button")   # the dialog's Done button
        ytu.wait_for(tab, """(()=>{const b=document.querySelector('ytcp-button#save');
            return !!b && !b.hasAttribute('disabled') && b.getAttribute('aria-disabled')!=='true'})()""", 20, 0.5)
        tab.click("ytcp-button#save")          # the page Save
        time.sleep(5)
    finally:
        tab.close()
    time.sleep(3)
    # oEmbed answers 200 for unlisted too, so read the state back from Studio instead.
    t2 = Tab.new(f"https://studio.youtube.com/video/{vid}/edit")
    try:
        urllib.request.urlopen(f"http://127.0.0.1:9340/json/activate/{t2.info['id']}").read()
        t2.wait_idle(10); time.sleep(4)
        got = t2.eval("""(()=>{const all=[];(function walk(r){for(const e of r.querySelectorAll('*')){all.push(e);if(e.shadowRoot)walk(e.shadowRoot);}})(document);
          const e=all.find(x=>x.id==='visibility-text'); return e&&e.innerText.trim()})()""")
    finally:
        t2.close()
    print(vid, "wanted", mode, "Studio says", got)
