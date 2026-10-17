#!/usr/bin/env python3
"""Upload a video to the Purplelink YouTube channel through the automation
Chrome (port 9340) with the DevTools protocol.

WHY THIS EXISTS
The Claude in Chrome extension caps file uploads at 10 MB, which forces a
soft 1000 kbps encode of every promo. CDP's DOM.setFileInputFiles has no size
limit and needs no file dialog, so the full-quality master goes up as-is.
The automation Chrome must be signed in to a Google account that can manage
the channel (Ben does that sign-in; this script never touches credentials).

  python3 scripts/yt-upload.py FILE --title "..." --description "..." [--public] [--thumbnail THUMB.jpg | --ab-thumbnails A.jpg B.jpg C.jpg]
  python3 scripts/yt-upload.py FILE --title ... --dry-run   # stops before choosing the file

Visibility defaults to unlisted so a bad render never goes public by accident;
pass --public only after Ben has approved that specific video in chat.
Prints the video URL on success. Exit 2 means the channel was not reachable
(wrong account in the automation Chrome).
"""
import argparse, importlib.util, os, re, subprocess, sys, time, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_tab import Tab  # noqa: E402

CHANNEL = "UCUv28P5SUzT4RLQOmi3EK8w"
UPLOAD_URL = f"https://studio.youtube.com/channel/{CHANNEL}/videos/upload?d=ud"


def ensure_chrome():
    """Start the automation Chrome (its own signed-in profile) when nothing answers on port 9340, so scheduled
    uploads do not depend on someone having left it open."""
    try:
        urllib.request.urlopen("http://127.0.0.1:9340/json/version", timeout=3).read()
        return
    except Exception:
        pass
    subprocess.Popen(["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--remote-debugging-port=9340",
                      f"--user-data-dir={os.path.expanduser('~/.photo-automation-chrome')}", "--no-first-run",
                      "--no-default-browser-check"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(30):
        time.sleep(1)
        try:
            urllib.request.urlopen("http://127.0.0.1:9340/json/version", timeout=3).read()
            time.sleep(4)
            return
        except Exception:
            continue
    print("automation Chrome did not start on port 9340", file=sys.stderr)
    sys.exit(2)


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
    time.sleep(0.4)
    tab.send("Input.dispatchKeyEvent", type="keyDown", key="a", code="KeyA", modifiers=4,
             windowsVirtualKeyCode=65, commands=["selectAll"])
    tab.send("Input.dispatchKeyEvent", type="keyUp", key="a", code="KeyA", modifiers=4, windowsVirtualKeyCode=65)
    tab.send("Input.insertText", text=text)
    time.sleep(0.5)


def choose_visibility(tab, name):
    """Select Studio's PRIVATE / UNLISTED / PUBLIC radio and confirm it took.

    click_text("Public") printed a link but left three 2026-10-01 uploads as
    private drafts: the label text matched a non-radio element. This finds the
    <tp-yt-paper-radio-button name="PUBLIC"> itself (through shadow roots),
    taps its real position, and reads aria-checked back, retrying, so a missed
    click fails loudly here instead of surfacing as a draft later.
    """
    want = name.upper()
    find = f"""(()=>{{const all=[];(function walk(r){{for(const e of r.querySelectorAll('*')){{
        all.push(e); if(e.shadowRoot)walk(e.shadowRoot);}}}})(document);
        return all.find(x=>x.tagName==='TP-YT-PAPER-RADIO-BUTTON' && x.getAttribute('name')==={want!r})||null}})()"""
    pos = f"""(()=>{{const all=[];(function walk(r){{for(const e of r.querySelectorAll('*')){{
        all.push(e); if(e.shadowRoot)walk(e.shadowRoot);}}}})(document);
        const e=all.find(x=>x.tagName==='TP-YT-PAPER-RADIO-BUTTON' && x.getAttribute('name')==={want!r});
        if(!e) return null; e.scrollIntoView({{block:'center'}}); const b=e.getBoundingClientRect();
        return [b.x+Math.min(b.width/2,120), b.y+b.height/2]}})()"""
    state = f"""(()=>{{const all=[];(function walk(r){{for(const e of r.querySelectorAll('*')){{
        all.push(e); if(e.shadowRoot)walk(e.shadowRoot);}}}})(document);
        const e=all.find(x=>x.tagName==='TP-YT-PAPER-RADIO-BUTTON' && x.getAttribute('name')==={want!r});
        return !!e && (e.getAttribute('aria-checked')==='true' || e.hasAttribute('checked'))}})()"""
    for _ in range(4):
        pt = tab.eval(pos)
        if pt:
            time.sleep(0.4)
            tab.tap(pt[0], pt[1], pause=1.2)
            if tab.eval(state):
                return
        else:
            time.sleep(1.5)
    raise RuntimeError(f"could not select the {name} visibility option in Studio")


def studio_state(vid):
    """What Studio itself says the video's visibility is: Public, Unlisted, Private, or Draft/Scheduled.

    oEmbed cannot tell public from unlisted (it answers 200 for both), and the link shown in the upload dialog
    exists before anything is published, so neither proves the upload finished. Studio's own visibility text does.
    """
    t = Tab.new(f"https://studio.youtube.com/video/{vid}/edit")
    try:
        urllib.request.urlopen(f"http://127.0.0.1:9340/json/activate/{t.info['id']}").read()
        t.wait_idle(10); time.sleep(4)
        return t.eval("""(()=>{const all=[];(function walk(r){for(const e of r.querySelectorAll('*')){all.push(e);if(e.shadowRoot)walk(e.shadowRoot);}})(document);
            const e=all.find(x=>x.id==='visibility-text'); const d=all.some(x=>/^ytcp-video-metadata-editor$/i.test(x.tagName)&&/draft/i.test(x.getAttribute('draft')||''));
            return (e&&e.innerText.trim())||''})()""") or ""
    finally:
        t.close()


def wait_for_checks(tab, timeout=1500):
    """Block until Studio's automated content check reports it is complete.

    Pressing Publish while the footer still says "Checking N% ... M minutes
    left" does not publish: Studio raises "We're still checking your content"
    (Publish anyway / Go back) and the video stays a private draft. That, not
    the visibility radio, is what left three 2026-10-01 uploads as drafts.
    """
    js = """(()=>{const all=[];(function walk(r){for(const e of r.querySelectorAll('*')){all.push(e); if(e.shadowRoot)walk(e.shadowRoot);}})(document);
      const f=all.find(x=>/Checks complete|Checking|issues? found|No issues/i.test(x.innerText||'') && (x.innerText||'').length<120 && x.getBoundingClientRect().width>0);
      return f? f.innerText.trim():''})()"""
    end = time.time() + timeout
    last = ""
    while time.time() < end:
        last = tab.eval(js) or ""
        if "complete" in last.lower():
            return
        if "issue" in last.lower() and "no issues" not in last.lower():
            raise RuntimeError("Studio reports a content check issue: " + last[:100])
        time.sleep(15)
    raise TimeoutError("content check did not finish: " + last[:100])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--title", required=True)
    ap.add_argument("--description", default="")
    ap.add_argument("--public", action="store_true", help="publish public (default unlisted)")
    ap.add_argument("--channel", default=CHANNEL,
                    help="channel ID to upload to (default: the Purplelink channel). The automation Chrome's account must manage it.")
    ap.add_argument("--dry-run", action="store_true", help="open the dialog, find the input, stop")
    ap.add_argument("--thumbnail", help="custom thumbnail (1280x720 JPEG under 2 MB, from video/build-thumbs.mjs) set after publishing")
    ap.add_argument("--ab-thumbnails", nargs=3, metavar=("A", "B", "C"),
                    help="three thumbnails for a Test & Compare test started after publishing (long-form public videos; A is the control)")
    a = ap.parse_args()
    # Studio needs a browser-wide channel switch, which is how content could reach the wrong channel. It is kept for
    # Purplelink only; every other channel goes through the API with its own token (scripts/yt-api-upload.py).
    import yt_guard  # lazy: ~/.purplelink/yt-abtest holds a copy of this file that only imports its helpers
    try:
        purplelink_id = yt_guard.load_registry()["purplelink"]["id"]
    except (yt_guard.ChannelGuardError, KeyError) as e:
        print(f"CHANNEL GUARD: cannot read the Purplelink id from scripts/yt-channels.json ({e}); not uploading", file=sys.stderr)
        sys.exit(3)
    if a.channel != purplelink_id:
        print("Studio uploads are Purplelink-only; use yt-api-upload.py for other channels", file=sys.stderr)
        sys.exit(3)
    path = os.path.abspath(a.file)
    if not os.path.isfile(path):
        sys.exit(f"no such file: {path}")
    if len(a.title) > 100:
        sys.exit("title over 100 characters")
    if a.thumbnail and (not os.path.isfile(a.thumbnail) or os.path.getsize(a.thumbnail) >= 2_000_000):
        sys.exit(f"thumbnail missing or 2 MB or more: {a.thumbnail}")
    if a.ab_thumbnails and a.thumbnail:
        sys.exit("use --thumbnail or --ab-thumbnails, not both (A of the test is the thumbnail)")
    if a.ab_thumbnails and not a.public:
        sys.exit("Test & Compare runs only on public videos; add --public")
    for t in a.ab_thumbnails or []:
        if not os.path.isfile(t) or os.path.getsize(t) >= 2_000_000:
            sys.exit(f"thumbnail missing or 2 MB or more: {t}")

    # Foreground on purpose: Chrome gives a hidden tab no layout, so every
    # rect is 0x0 and Input events land nowhere. Studio's fields need real clicks.
    ensure_chrome()
    tab = Tab.new(f"https://studio.youtube.com/channel/{a.channel}/videos/upload?d=ud")
    try:
        urllib.request.urlopen(f"http://127.0.0.1:9340/json/activate/{tab.info['id']}").read()
        tab.wait_idle(8)
        if "permission" in tab.text().lower() and "Oops" in (tab.eval("document.title") or ""):
            print("automation Chrome is not signed in to an account that manages the channel", file=sys.stderr)
            sys.exit(2)
        # Studio can silently show a different channel than the URL asked for: refuse to upload anywhere else
        on = tab.eval("location.pathname")
        if f"/channel/{a.channel}/" not in (on or ""):
            print(f"Studio opened {on!r}, not channel {a.channel}; not uploading", file=sys.stderr)
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
        # Radios and buttons are Polymer web components; click their centre by
        # the text they show, walking shadow roots (click_text does that).
        # The audience radios sit in shadow DOM (body.innerText never sees
        # them); click_text walks shadow roots and scrolls the target itself.
        time.sleep(1)
        tab.click_text("No, it's not made for kids")

        for _ in range(3):
            tab.click_text("Next")
            time.sleep(1.5)

        choose_visibility(tab, "Public" if a.public else "Unlisted")
        time.sleep(0.8)

        # The upload itself must finish before Publish/Save is enabled.
        wait_for(tab, """(()=>{const b=[...document.querySelectorAll('ytcp-button, button')]
            .find(e=>/^(Publish|Save|Done)$/.test((e.innerText||'').trim()));
            return !!b && !b.hasAttribute('disabled') && b.getAttribute('aria-disabled')!=='true'})()""", 900, 2)
        # Always wait, whatever the visibility: Save/Publish pressed while the content check is still running raises
        # "We're still checking your content" (Publish anyway / Go back) and leaves the video a draft. That is what
        # left an unlisted upload as a draft on 2026-10-09; only --public used to wait.
        wait_for_checks(tab)
        clicked = None
        for name in ("Publish", "Save", "Done"):
            try:
                tab.click_text(name)
                clicked = name
                break
            except LookupError:
                continue
        if not clicked:
            raise RuntimeError("found no Publish, Save or Done button in the upload dialog; the video is still a draft")
        time.sleep(2)
        if tab.eval("""(()=>{const all=[];(function walk(r){for(const e of r.querySelectorAll('*')){all.push(e);if(e.shadowRoot)walk(e.shadowRoot);}})(document);
            return all.some(x=>/still checking your content/i.test(x.innerText||'')&&x.offsetParent!==null&&(x.innerText||'').length<400)})()"""):
            try:
                tab.click_text("Go back")      # never "Publish anyway": that risks a strike while checks are running
            except LookupError:
                pass
            raise RuntimeError("Studio said it is still checking the content; the video is a draft. Wait for the check, then save it in Studio")
        # Long videos show a youtu.be/<id> link in the dialog; Shorts show youtube.com/shorts/<id>.
        link = wait_for(tab, """(()=>{const a=[...document.querySelectorAll('a')]
            .find(x=>/youtu\\.be\\/|youtube\\.com\\/shorts\\//.test(x.href)); return a? a.href : null})()""", 120)
        m = re.search(r"(?:youtu\.be|youtube\.com/shorts)/([\w-]{11})", link)
        if not m:
            raise RuntimeError("could not read the video id from " + link)
        vid = m.group(1)
        time.sleep(5)
        # The link shows in the dialog before publishing, so it proves nothing, and oEmbed answers 200 for public AND
        # unlisted. Ask Studio what it thinks the visibility is, and refuse to report success unless it is what was
        # asked for. (2026-10-01: three uploads printed a link and stayed drafts; 2026-10-09: one that was asked to be
        # unlisted came out Public while the script said Unlisted.)
        want = "Public" if a.public else "Unlisted"
        got = ""
        for _ in range(8):
            got = studio_state(vid)
            if got.lower() == want.lower():
                break
            time.sleep(10)
        if got.lower() != want.lower():
            print(f"WRONG STATE: Studio says {got!r} for {link}, wanted {want!r}. Fix it with: "
                  f"python3 scripts/yt-visibility.py {want.lower()} {vid}", file=sys.stderr)
            sys.exit(3)
        print(f"https://youtu.be/{vid}")  # one stable form for long videos and Shorts
        print(f"verified in Studio: {got}")
        if a.thumbnail:
            # Set on the published video's edit page (scripts/yt-thumbnail.py), which confirms the public image matches;
            # the upload dialog's own thumbnail input shares markup with the video input, so it is not used.
            spec = importlib.util.spec_from_file_location("ytt", os.path.join(os.path.dirname(os.path.abspath(__file__)), "yt-thumbnail.py"))
            ytt = importlib.util.module_from_spec(spec); spec.loader.exec_module(ytt)
            ok = ytt.apply(vid, os.path.abspath(a.thumbnail))
            print("thumbnail live" if ok else f"thumbnail saved but not public yet; recheck with scripts/yt-thumbnail.py {vid}={a.thumbnail}")
        if a.ab_thumbnails:
            spec = importlib.util.spec_from_file_location("yab", os.path.join(os.path.dirname(os.path.abspath(__file__)), "yt-abtest.py"))
            yab = importlib.util.module_from_spec(spec); spec.loader.exec_module(yab)
            yab.start(vid, *a.ab_thumbnails)  # sets A as the thumbnail, starts the test, records it
    except Exception:
        print(f"left the Studio tab open for manual recovery: {tab.url()}", file=sys.stderr)
        raise
    else:
        tab.close()


if __name__ == "__main__":
    main()
