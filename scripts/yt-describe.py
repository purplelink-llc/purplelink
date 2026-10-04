#!/usr/bin/env python3
"""Rewrite "$10" to the current ModernTex price in the description of existing
Studio videos, through the automation Chrome (port 9340, signed in to the channel).

  python3 scripts/yt-describe.py VIDEO_ID [VIDEO_ID ...]

Reads each description from the public watch page, replaces the old price text,
types the result into Studio's description box and saves. Prints before/after.
"""
import json, re, subprocess, sys, time, os, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_tab import Tab  # noqa: E402
import importlib.util
spec = importlib.util.spec_from_file_location("ytu", os.path.join(os.path.dirname(os.path.abspath(__file__)), "yt-upload.py"))
ytu = importlib.util.module_from_spec(spec); spec.loader.exec_module(ytu)

CHANNEL = ytu.CHANNEL


def current(vid):
    html = subprocess.run(["curl", "-s", "-A", "Mozilla/5.0", f"https://www.youtube.com/watch?v={vid}"],
                          capture_output=True, text=True).stdout
    m = re.search(r'"shortDescription":("(?:[^"\\]|\\.)*")', html)
    return json.loads(m.group(1)) if m else None


def fix(s):
    s = s.replace("$10, one purchase.", "$19.99, one purchase, all updates included.")
    s = s.replace("$10, one purchase", "$19.99, one purchase, all updates included")
    s = s.replace("a $10 LaTeX editor", "a $19.99 LaTeX editor")
    s = s.replace("$10 once", "$19.99 once")
    return s


for vid in sys.argv[1:]:
    old = current(vid)
    if old is None:
        print(vid, "could not read description"); continue
    new = fix(old)
    if new == old:
        print(vid, "no change needed"); continue
    tab = Tab.new(f"https://studio.youtube.com/video/{vid}/edit")
    try:
        urllib.request.urlopen(f"http://127.0.0.1:9340/json/activate/{tab.info['id']}").read()
        tab.wait_idle(8)
        ytu.wait_for(tab, "document.querySelectorAll('#textbox').length >= 2", 60)
        time.sleep(1.5)
        ytu.type_into(tab, "document.querySelectorAll('#textbox')[1]", new)
        time.sleep(1)
        ytu.wait_for(tab, """(()=>{const b=document.querySelector('ytcp-button#save');
            return !!b && !b.hasAttribute('disabled') && b.getAttribute('aria-disabled')!=='true'})()""", 20, 0.5)
        tab.click("ytcp-button#save")
        time.sleep(4)
    finally:
        tab.close()
    time.sleep(6)
    chk = current(vid)
    print(vid, "OK" if chk == new else "MISMATCH", "\n  was:", old[-120:], "\n  now:", (chk or "")[-140:])
