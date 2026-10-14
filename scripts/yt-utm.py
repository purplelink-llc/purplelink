#!/usr/bin/env python3
"""Tag the purplelink.llc links in existing video descriptions so the site can tell a YouTube visit from a
direct one (site/analytics.js records utm_source / utm_medium / utm_campaign as the first-touch channel),
and give each LaTeX error Short a direct ModernTex line. Studio is driven through the automation Chrome
(port 9340, signed in to the channel), the same way yt-describe.py does it.

  python3 scripts/yt-utm.py                    # dry run: print the plan for every video, change nothing
  python3 scripts/yt-utm.py --apply VIDEO_ID [VIDEO_ID ...]

Which videos and which tags:
  LaTeX error Shorts  (description links to /latex-errors/<slug>/)
      error-page link  -> ?utm_source=youtube-latex&utm_medium=short&utm_campaign=latex-errors
      appended line    -> ModernTex link, same tags
  ModernTex promos    (description links to /moderntex/)
      link             -> ?utm_source=youtube-latex&utm_medium=video&utm_campaign=moderntex-promo
The source is "youtube-latex", not "youtube": the site records only utm_source as the channel label and the live
stream already uses "youtube", so a separate source keeps these videos measurable on their own.
A description that already carries utm_source=youtube (or youtube-latex) is left alone, so re-running is safe. Every change is
read back from the public watch page and compared with what was typed.
"""
import argparse, json, os, re, subprocess, sys, time, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BASE = "https://purplelink.llc"
SHORT_TAGS = "?utm_source=youtube-latex&utm_medium=short&utm_campaign=latex-errors"
PROMO_TAGS = "?utm_source=youtube-latex&utm_medium=video&utm_campaign=moderntex-promo"
MT_LINE = "ModernTex, a LaTeX editor for Mac that shows build errors in plain language: "
ERROR_URL = re.compile(r"https://purplelink\.llc/latex-errors/[a-z0-9-]+/(?![\w?])")
MT_URL = re.compile(r"https://purplelink\.llc/moderntex/(?![\w?])")


def plan(desc: str) -> str | None:
    """The description with tags applied, or None when there is nothing to do."""
    if "utm_source=youtube" in desc:
        return None
    if ERROR_URL.search(desc):
        out = ERROR_URL.sub(lambda m: m.group(0) + SHORT_TAGS, desc)
        if "/moderntex/" not in out:
            out = out.rstrip() + f"\n\n{MT_LINE}{BASE}/moderntex/{SHORT_TAGS}"
        return out
    if MT_URL.search(desc):
        return MT_URL.sub(lambda m: m.group(0) + PROMO_TAGS, desc)
    return None


def current(vid: str) -> str | None:
    html = subprocess.run(["curl", "-s", "-A", "Mozilla/5.0", f"https://www.youtube.com/watch?v={vid}"],
                          capture_output=True, text=True).stdout
    m = re.search(r'"shortDescription":("(?:[^"\\]|\\.)*")', html)
    return json.loads(m.group(1)) if m else None


def apply(vid: str, new: str) -> None:
    from cdp_tab import Tab
    import importlib.util
    spec = importlib.util.spec_from_file_location("ytu", os.path.join(os.path.dirname(os.path.abspath(__file__)), "yt-upload.py"))
    ytu = importlib.util.module_from_spec(spec); spec.loader.exec_module(ytu)
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", nargs="+", metavar="VIDEO_ID", help="write the change for these videos")
    ap.add_argument("--ids", nargs="+", help="dry-run only these videos (default: the ids in the plan file)")
    ap.add_argument("--plan-file", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "yt-utm-videos.json"))
    a = ap.parse_args()
    ids = a.apply or a.ids or json.load(open(a.plan_file))
    rc = 0
    for vid in ids:
        old = current(vid)
        if old is None:
            print(vid, "could not read the description"); rc = 1; continue
        new = plan(old)
        if new is None:
            print(vid, "nothing to do"); continue
        if not a.apply:
            print(f"{vid} would become:\n{new}\n"); continue
        apply(vid, new)
        time.sleep(6)
        chk = current(vid)
        ok = (chk or "").strip() == new.strip()
        print(vid, "OK" if ok else "MISMATCH", "\n  now:", (chk or "")[-170:])
        rc = rc or (0 if ok else 1)
    return rc


if __name__ == "__main__":
    sys.exit(main())
