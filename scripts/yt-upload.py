#!/usr/bin/env python3
"""Upload a video to the Purplelink YouTube channel through the automation
Chrome (port 9340) with the DevTools protocol.

WHY THIS EXISTS
The Claude in Chrome extension caps file uploads at 10 MB, which forces a
soft 1000 kbps encode of every promo. CDP's DOM.setFileInputFiles has no size
limit and needs no file dialog, so the full-quality master goes up as-is.
The automation Chrome must be signed in to a Google account that can manage
the channel (Ben does that sign-in; this script never touches credentials).

  python3 scripts/yt-upload.py FILE --title "..." --description "..." [--public]
  python3 scripts/yt-upload.py FILE --title ... --dry-run   # stops before choosing the file

Visibility defaults to unlisted so a bad render never goes public by accident;
pass --public only after Ben has approved that specific video in chat.
Prints the video URL on success. Exit 2 means the channel was not reachable
(wrong account in the automation Chrome).
"""
import argparse, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_tab import Tab  # noqa: E402

CHANNEL = "UCUv28P5SUzT4RLQOmi3EK8w"
UPLOAD_URL = f"https://studio.youtube.com/channel/{CHANNEL}/videos/upload?d=ud"


def wait_for(tab, js, timeout=60, every=0.5):
    end = time.time() + timeout
    while time.time() < end:
        v = tab.eval(js)
        if v:
            return v
        time.sleep(every)
    raise TimeoutError(js)


def type_into(tab, selector_js, text):
    """Focus a Studio textbox (contenteditable) through a real click, select
    everything, then insert text with Input.insertText so Polymer sees it."""
    box = tab.eval(f"""(()=>{{const e={selector_js}; if(!e) return null;
        e.scrollIntoView({{block:'center'}}); const b=e.getBoundingClientRect();
        return [b.x+b.width/2, b.y+b.height/2]}})()""")
    if not box:
        raise LookupError(selector_js)
    for t in ("mousePressed", "mouseReleased"):
        tab.send("Input.dispatchMouseEvent", type=t, x=box[0], y=box[1], button="left", clickCount=1)
    time.sleep(0.3)
    tab.send("Input.dispatchKeyEvent", type="keyDown", key="a", code="KeyA", modifiers=4,
             windowsVirtualKeyCode=65, commands=["selectAll"])
    tab.send("Input.dispatchKeyEvent", type="keyUp", key="a", code="KeyA", modifiers=4, windowsVirtualKeyCode=65)
    tab.send("Input.insertText", text=text)
    time.sleep(0.5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--title", required=True)
    ap.add_argument("--description", default="")
    ap.add_argument("--public", action="store_true", help="publish public (default unlisted)")
    ap.add_argument("--dry-run", action="store_true", help="open the dialog, find the input, stop")
    a = ap.parse_args()
    path = os.path.abspath(a.file)
    if not os.path.isfile(path):
        sys.exit(f"no such file: {path}")
    if len(a.title) > 100:
        sys.exit("title over 100 characters")

    tab = Tab.new(UPLOAD_URL, background=True)
    try:
        tab.wait_idle(8)
        if "permission" in tab.text().lower() and "Oops" in (tab.eval("document.title") or ""):
            print("automation Chrome is not signed in to an account that manages the channel", file=sys.stderr)
            sys.exit(2)
        tab.send("DOM.enable")
        doc = tab.send("DOM.getDocument", depth=0)["root"]["nodeId"]
        wait_for(tab, "!!document.querySelector('input[type=file]')", 30)
        node = tab.send("DOM.querySelector", nodeId=doc, selector="input[type=file]")["nodeId"]
        if a.dry_run:
            print("dry run: upload dialog open and file input found; not uploading")
            return
        tab.send("DOM.setFileInputFiles", files=[path], nodeId=node)

        # Details step: title and description are contenteditable textboxes.
        wait_for(tab, "document.querySelectorAll('#textbox').length >= 2", 60)
        time.sleep(1.5)
        type_into(tab, "document.querySelectorAll('#textbox')[0]", a.title)
        if a.description:
            type_into(tab, "document.querySelectorAll('#textbox')[1]", a.description)

        # Audience: not made for kids.
        tab.eval("""(()=>{const r=[...document.querySelectorAll('tp-yt-paper-radio-button')]
            .find(e=>/not made for kids/i.test(e.innerText)); if(r){r.scrollIntoView({block:'center'});} return !!r})()""")
        time.sleep(0.5)
        tab.click_text("No, it's not made for kids", tag="tp-yt-paper-radio-button", exact=False)

        for _ in range(3):
            tab.click_text("Next", tag="ytcp-button, button", exact=False)
            time.sleep(1.5)

        label = "Public" if a.public else "Unlisted"
        tab.click_text(label, tag="tp-yt-paper-radio-button", exact=False)
        time.sleep(0.8)

        # The upload itself must finish before Publish/Save is enabled.
        wait_for(tab, """(()=>{const b=[...document.querySelectorAll('ytcp-button, button')]
            .find(e=>/^(Publish|Save|Done)$/.test((e.innerText||'').trim()));
            return !!b && !b.hasAttribute('disabled') && b.getAttribute('aria-disabled')!=='true'})()""", 900, 2)
        for name in ("Publish", "Save", "Done"):
            try:
                tab.click_text(name, tag="ytcp-button, button")
                break
            except LookupError:
                continue
        link = wait_for(tab, """(()=>{const a=[...document.querySelectorAll('a')]
            .find(x=>/youtu\\.be\\//.test(x.href)); return a? a.href : null})()""", 120)
        print(link)
    finally:
        tab.close()


if __name__ == "__main__":
    main()
