#!/usr/bin/env python3
"""Set the custom thumbnail of existing videos on the Purplelink channel through the automation Chrome
(port 9340, signed in to the channel), the same way yt-describe.py and yt-utm.py edit descriptions.

  python3 scripts/yt-thumbnail.py VIDEO_ID=path/to/thumb.jpg [VIDEO_ID=...]
  python3 scripts/yt-thumbnail.py --dir video/out/thumbs VIDEO_ID [VIDEO_ID ...]   # <dir>/<id>.jpg

Thumbnails come from video/build-thumbs.mjs (1280x720 JPEG, under 2 MB). For each video the script opens
Studio's edit page, hands the file to the thumbnail input with DOM.setFileInputFiles (no file dialog), saves,
then confirms the public i.ytimg.com image matches the file (a video that already shows it is skipped).
"""
import argparse, importlib.util, os, subprocess, sys, tempfile, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cdp_tab import Tab  # noqa: E402
spec = importlib.util.spec_from_file_location("ytu", os.path.join(HERE, "yt-upload.py"))
ytu = importlib.util.module_from_spec(spec); spec.loader.exec_module(ytu)


def tiny(src):
    """32x18 grayscale pixels of an image file or URL (YouTube re-encodes uploads, so compare pictures, not bytes)."""
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", src, "-vf", "scale=32:18,format=gray", "-f", "rawvideo", "-"],
                       capture_output=True)
    return r.stdout if len(r.stdout) == 32 * 18 else None


def public_matches(vid, path):
    """True when the thumbnail YouTube serves looks like the local file (mean pixel difference under 12 of 255).
    curl fetches it (this ffmpeg cannot verify TLS); maxresdefault is the full 16:9 frame, hqdefault is letterboxed."""
    want = tiny(path)
    if not want:
        return False
    with tempfile.NamedTemporaryFile(suffix=".jpg") as f:
        if subprocess.run(["curl", "-s", "-f", "-o", f.name, f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg"]).returncode:
            return False
        got = tiny(f.name)
    return bool(got) and sum(abs(a - b) for a, b in zip(want, got)) / len(want) < 12


def set_file(tab, path):
    """Give Studio's thumbnail <input type=file id=file-loader> the file, found through shadow roots."""
    tab.send("DOM.enable")
    root = tab.send("DOM.getDocument", depth=-1, pierce=True)["root"]
    stack = [root]
    while stack:
        n = stack.pop()
        attrs = n.get("attributes", [])
        if n.get("nodeName") == "INPUT" and "file-loader" in attrs and "file" in attrs:
            tab.send("DOM.setFileInputFiles", files=[path], backendNodeId=n["backendNodeId"])
            return
        stack += n.get("children", []) + n.get("shadowRoots", []) + ([n["contentDocument"]] if "contentDocument" in n else [])
    raise LookupError("thumbnail file input not found (is the channel allowed custom thumbnails?)")


def apply(vid, path):
    if public_matches(vid, path):
        return True
    tab = Tab.new(f"https://studio.youtube.com/video/{vid}/edit")
    try:
        urllib.request.urlopen(f"http://127.0.0.1:9340/json/activate/{tab.info['id']}").read()
        tab.wait_idle(8)
        ytu.wait_for(tab, "document.querySelectorAll('#textbox').length >= 2", 60)
        time.sleep(1.5)
        set_file(tab, path)
        ytu.wait_for(tab, """(()=>{const b=document.querySelector('ytcp-button#save');
            return !!b && !b.hasAttribute('disabled') && b.getAttribute('aria-disabled')!=='true'})()""", 60, 0.5)
        time.sleep(2)  # let the preview finish processing before saving
        tab.click("ytcp-button#save")
        time.sleep(5)
    finally:
        tab.close()
    for _ in range(16):  # the CDN takes one to three minutes to serve a new thumbnail
        time.sleep(15)
        if public_matches(vid, path):
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("items", nargs="+", help="VIDEO_ID=file.jpg, or VIDEO_ID with --dir")
    ap.add_argument("--dir", help="folder holding <VIDEO_ID>.jpg")
    a = ap.parse_args()
    bad = 0
    for item in a.items:
        vid, _, path = item.partition("=")
        path = os.path.abspath(path or os.path.join(a.dir or ".", f"{vid}.jpg"))
        if not os.path.isfile(path):
            print(f"{vid}: no file {path}"); bad += 1; continue
        if os.path.getsize(path) >= 2_000_000:
            print(f"{vid}: {path} is 2 MB or more, YouTube refuses it"); bad += 1; continue
        ok = apply(vid, path)
        print(f"{vid}: {'thumbnail live (public image matches)' if ok else 'saved, but the public image does not match yet; recheck later'}")
        bad += 0 if ok else 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
