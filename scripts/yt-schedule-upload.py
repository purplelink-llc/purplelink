#!/usr/bin/env python3
"""Upload one long ambient video to a YouTube channel through the automation Chrome (port 9340) and schedule it to go public.

  python3 scripts/yt-schedule-upload.py --channel UC... --video FILE.mp4 --meta FILE.json --date 2026-10-22 --time "12:00 PM"

The date and time are in the Studio's local time zone (the Mac's, GMT-7 in Phoenix: 12:00 PM is 15:00 US Eastern in October).
Everything comes from the meta JSON that tools/chiptune-radio/longform_pub.py writes: title, description, tags, category, and the
altered-or-synthetic-content answer. Made for kids is always No. The thumbnail is set in the dialog when the channel allows custom
thumbnails (a new channel needs phone verification first); otherwise it is skipped and reported, and yt-thumbnail.py sets it later.
The external link footer is left out unless --links, because an unverified channel refuses a description with a link.
Only run for videos Ben has approved for upload; it never chooses Publish anyway while checks are running.
"""
import argparse, datetime as dt, importlib.util, json, os, re, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cdp_tab import Tab  # noqa: E402


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


ytu = _load("ytu", "yt-upload.py")
ytt = _load("ytt", "yt-thumbnail.py")
WALK = "const all=[];(function w(r){for(const e of r.querySelectorAll('*')){all.push(e);if(e.shadowRoot)w(e.shadowRoot);}})(document);"


def tap_js(tab, find_js, what, pause=1.5):
    pos = tab.eval("(()=>{" + WALK + find_js + "if(!e) return null; e.scrollIntoView({block:'center'}); const r=e.getBoundingClientRect();"
                   "return [r.x+r.width/2, r.y+r.height/2]})()")
    if not pos:
        raise LookupError(f"could not find {what}")
    tab.tap(pos[0], pos[1], pause=pause)


def value(tab, js):
    return tab.eval("(()=>{" + WALK + js + "})()")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", required=True)
    ap.add_argument("--video", required=True)
    ap.add_argument("--meta", required=True)
    ap.add_argument("--thumbnail")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD, local time zone")
    ap.add_argument("--time", required=True, help='as Studio lists it, for example "12:00 PM" (15-minute steps)')
    ap.add_argument("--links", action="store_true", help="keep the link footer (channel must be verified)")
    a = ap.parse_args()
    meta = json.load(open(a.meta))
    when = dt.date.fromisoformat(a.date)
    want_date = f"{when.strftime('%b')} {when.day}, {when.year}"
    desc = meta["description"] + (("\n\n" + meta["optional_footer"]) if a.links and meta.get("optional_footer") else "")

    ytu.ensure_chrome()
    tab = Tab.new(f"https://studio.youtube.com/channel/{a.channel}/videos/upload?d=ud")
    urllib.request.urlopen(f"http://127.0.0.1:9340/json/activate/{tab.info['id']}").read()
    tab.wait_idle(8)
    if f"/channel/{a.channel}/" not in (tab.eval("location.pathname") or ""):
        sys.exit(f"Studio did not open channel {a.channel}; not uploading")
    tab.send("DOM.enable")
    doc = tab.send("DOM.getDocument", depth=0)["root"]["nodeId"]
    ytu.wait_for(tab, "!!document.querySelector('input[type=file]')", 30)
    node = tab.send("DOM.querySelector", nodeId=doc, selector="input[type=file]")["nodeId"]
    tab.send("DOM.setFileInputFiles", files=[os.path.abspath(a.video)], nodeId=node)
    ytu.wait_for(tab, "document.querySelectorAll('#textbox').length >= 2", 120)
    time.sleep(3)
    for _ in range(3):                       # a first-visit welcome dialog can sit over the form
        if not value(tab, "return all.some(x=>x.id==='dismiss-button'&&x.getBoundingClientRect().width>0)"):
            break
        tap_js(tab, "const e=all.find(x=>x.id==='dismiss-button'&&x.getBoundingClientRect().width>0);", "welcome Continue")

    ytu.type_into(tab, "document.querySelectorAll('#textbox')[0]", meta["title"])
    ytu.type_into(tab, "document.querySelectorAll('#textbox')[1]", desc)
    time.sleep(1.5)
    if value(tab, "return all.filter(x=>x.tagName==='YTCP-SOCIAL-SUGGESTIONS-TEXTBOX').some(x=>x.hasAttribute('invalid'))"):
        sys.exit("Studio marks the title or description invalid; the draft is saved as private, fix it in Studio")

    thumb_set = False
    if a.thumbnail:
        try:
            ytt.set_file(tab, os.path.abspath(a.thumbnail))
            time.sleep(6)
            thumb_set = bool(value(tab, "const e=all.find(x=>x.tagName==='YTCP-THUMBNAIL-UPLOADER');"
                                        "return !!e && !/Upload file/.test((e.innerText||''))"))
        except LookupError:
            thumb_set = False

    tab.click_text("No, it's not made for kids")
    time.sleep(1)
    tab.click_text("Show more")
    time.sleep(2)
    alt = "VIDEO_HAS_ALTERED_CONTENT_YES" if meta.get("altered_or_synthetic_content", {}).get("answer") == "Yes" else "VIDEO_HAS_ALTERED_CONTENT_NO"
    tap_js(tab, f"const e=all.find(x=>x.getAttribute('name')==='{alt}');", "the altered content answer")
    if meta.get("tags"):
        ytu.type_into(tab, "(()=>{" + WALK + "return all.find(x=>x.tagName==='INPUT'&&x.getAttribute('aria-label')==='Tags')})()",
                      ",".join(meta["tags"]) + ",")
        time.sleep(1)
    if meta.get("category"):
        tap_js(tab, "const e=all.find(x=>x.id==='category');", "the category menu")
        tap_js(tab, f"const e=all.find(x=>x.tagName==='TP-YT-PAPER-ITEM'&&(x.innerText||'').trim()==={json.dumps(meta['category'])}"
                    "&&x.getBoundingClientRect().width>0);", "the category " + meta["category"])
    state = json.loads(value(tab, "return JSON.stringify({alt:!!(all.find(x=>x.getAttribute('name')==='" + alt + "')||{hasAttribute:()=>0}).hasAttribute('checked'),"
                                  "kids:!!(all.find(x=>x.getAttribute('name')==='VIDEO_MADE_FOR_KIDS_NOT_MFK')||{hasAttribute:()=>0}).hasAttribute('checked'),"
                                  "cat:(all.find(x=>x.id==='category')||{}).innerText||''})"))
    if not (state["alt"] and state["kids"]):
        sys.exit(f"the audience or altered content answer did not take: {state}")

    for _ in range(3):
        tab.click_text("Next")
        time.sleep(2)
    tap_js(tab, "const e=all.find(x=>(x.id==='second-container-expand-button'||x.id==='schedule-expand-button')&&x.getBoundingClientRect().width>0)"
                "||all.find(x=>(x.innerText||'').trim()==='Schedule'&&x.getBoundingClientRect().width>0&&x.children.length<3);", "Schedule")
    # date: open the picker, type the date into its field, press Enter
    tap_js(tab, "const e=all.find(x=>x.id==='datepicker-trigger'&&x.getBoundingClientRect().width>0);", "the date picker")
    ytu.type_into(tab, "(()=>{" + WALK + "return all.find(x=>x.tagName==='INPUT'&&/\\d{4}$/.test(x.value)&&x.getBoundingClientRect().width>0)})()", want_date)
    for t_ in ("keyDown", "keyUp"):
        tab.send("Input.dispatchKeyEvent", type=t_, key="Enter", code="Enter", windowsVirtualKeyCode=13)
    time.sleep(1.5)
    # time: open the list and pick the entry
    tap_js(tab, "const e=all.find(x=>x.tagName==='INPUT'&&/AM|PM/.test(x.value)&&x.getBoundingClientRect().width>0);", "the time field")
    pat = re.escape(a.time).replace("\\ ", "\\s*").replace(" ", "\\s*")
    tap_js(tab, "const c=all.filter(x=>x.tagName==='TP-YT-PAPER-ITEM'&&/^" + pat + "$/.test((x.innerText||'').replace(/\\u202f/g,' ').trim()));"
                "const e=c[c.length-1];", "the time " + a.time)
    got = value(tab, "const d=all.find(x=>x.id==='datepicker-trigger');const tm=all.find(x=>x.tagName==='INPUT'&&/AM|PM/.test(x.value));"
                     "return (d?d.innerText.trim():'')+' | '+(tm?tm.value.replace(/\\u202f/g,' '):'')")
    if got != f"{want_date} | {a.time}":
        sys.exit(f"schedule fields read {got!r}, wanted {want_date} | {a.time}; the draft stays private")

    # wait for the upload, then the content check; stop at once if Studio abandons processing (an unverified channel refuses
    # anything over 15 minutes: "Processing abandoned. Video is too long")
    end = time.time() + 5400
    while True:
        status = value(tab, "const f=all.find(x=>/Processing abandoned|Checks complete|No issues found|issues? found/i.test(x.innerText||'')"
                            "&&(x.innerText||'').length<160&&x.getBoundingClientRect().width>0);return f?f.innerText.trim():''") or ""
        if "abandoned" in status.lower():
            sys.exit("Studio abandoned processing: " + status.replace("\n", " ")[:160])
        if "issue" in status.lower() and "no issues" not in status.lower():
            sys.exit("Studio reports a content check issue: " + status[:160] + "; the video stays a private draft")
        ready = value(tab, "const b=all.find(x=>/^Schedule$/.test((x.innerText||'').trim())&&/BUTTON/.test(x.tagName)&&x.getBoundingClientRect().width>0);"
                           "return !!b && !b.hasAttribute('disabled') && b.getAttribute('aria-disabled')!=='true'")
        if ready and re.search(r"complete|no issues", status, re.I):
            break
        if time.time() > end:
            sys.exit("upload or check did not finish in 90 minutes; last status: " + status[:160])
        time.sleep(20)
    link = value(tab, "const x=all.find(x=>x.tagName==='A'&&/youtu\\.be\\//.test(x.href));return x?x.href:''")
    tab.click_text("Schedule")
    time.sleep(4)
    if value(tab, "return all.some(x=>/still checking your content/i.test(x.innerText||'')&&x.offsetParent!==null&&(x.innerText||'').length<400)"):
        try:
            tab.click_text("Go back")
        except LookupError:
            pass
        sys.exit("Studio is still checking the content; the video is a private draft. Schedule it in Studio after the check")
    print(json.dumps({"video": link, "scheduled": f"{want_date} {a.time} local", "thumbnail_set": thumb_set, "category": state["cat"]}))
    tab.close()


if __name__ == "__main__":
    main()
