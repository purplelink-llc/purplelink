#!/usr/bin/env python3
"""Start and read YouTube Test & Compare thumbnail tests through the automation Chrome (port 9340, signed in).

  python3 scripts/yt-abtest.py start VIDEO_ID A.jpg B.jpg C.jpg   # A becomes the current thumbnail, B and C the others
  python3 scripts/yt-abtest.py status [VIDEO_ID ...]               # read results of open tests from Studio

Test & Compare works on long-form public videos only (not Shorts). Studio splits impressions evenly and picks by
share of watch time; results read Winner, Preferred, or None. Every start is recorded in video/thumbs/ab-tests.json
and in the change log (~/.purplelink/insights/changelog/log_change.py). See video/README.md, "A/B testing".
"""
import datetime as dt, importlib.util, json, os, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cdp_tab import Tab  # noqa: E402

def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

ytu = _load("ytu", "yt-upload.py")
ytt = _load("ytt", "yt-thumbnail.py")
# the weekly job (llc.purplelink.ytabtest) runs local copies and keeps its own log: YT_ABTEST_LOG overrides the path
LOG = os.environ.get("YT_ABTEST_LOG") or os.path.join(HERE, "..", "video", "thumbs", "ab-tests.json")
CHANGELOG = os.path.expanduser("~/.purplelink/insights/changelog/log_change.py")
WALK = "const all=[];(function w(r){for(const e of r.querySelectorAll('*')){all.push(e);if(e.shadowRoot)w(e.shadowRoot);}})(document);"


def ensure_chrome():
    """Start the automation Chrome (its own signed-in profile) when nothing answers on port 9340."""
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
    raise SystemExit("automation Chrome did not start on port 9340")


def _open(vid):
    ensure_chrome()
    tab = Tab.new(f"https://studio.youtube.com/video/{vid}/edit")
    urllib.request.urlopen(f"http://127.0.0.1:9340/json/activate/{tab.info['id']}").read()
    tab.wait_idle(10)
    ytu.wait_for(tab, "document.querySelectorAll('#textbox').length >= 2", 60)
    time.sleep(3)
    return tab


def _tap(tab, find_js, what):
    pos = tab.eval("(()=>{" + WALK + find_js + "if(!e) return null; e.scrollIntoView({block:'center'}); "
                   "const r=e.getBoundingClientRect(); return [r.x+r.width/2, r.y+r.height/2]})()")
    if not pos:
        raise LookupError(f"could not find {what}")
    tab.tap(pos[0], pos[1], pause=2)


def _editor_text(tab):
    return tab.eval("(()=>{" + WALK + "const e=all.find(x=>x.tagName==='YTCP-VIDEO-THUMBNAIL-EDITOR');"
                    "return e? e.innerText.trim() : ''})()") or ""


def _file_inputs(tab):
    """backendNodeIds of every thumbnail <input type=file id=file-loader>, in document order."""
    tab.send("DOM.enable")
    root = tab.send("DOM.getDocument", depth=-1, pierce=True)["root"]
    out = []
    def walk(n):
        a = n.get("attributes", [])
        if n.get("nodeName") == "INPUT" and "file-loader" in a:
            out.append(n["backendNodeId"])
        for c in n.get("children", []) + n.get("shadowRoots", []) + ([n["contentDocument"]] if "contentDocument" in n else []):
            walk(c)
    walk(root)
    return out


def _record(entry):
    log = json.load(open(LOG)) if os.path.exists(LOG) else []
    log = [x for x in log if not (x["video"] == entry["video"] and x["started"] == entry["started"])] + [entry]
    with open(LOG, "w") as f:
        json.dump(log, f, indent=1)
        f.write("\n")


def start(vid, a, b, c):
    paths = [os.path.abspath(p) for p in (a, b, c)]
    for p in paths:
        if not os.path.isfile(p) or os.path.getsize(p) >= 2_000_000:
            raise SystemExit(f"thumbnail missing or 2 MB or more: {p}")
    # A is the control: make it the video's current thumbnail first (no-op when it already is)
    if not ytt.public_matches(vid, paths[0]) and not ytt.apply(vid, paths[0]):
        raise SystemExit(f"{vid}: could not make A the current thumbnail; not starting a test")
    tab = _open(vid)
    try:
        before = len(_file_inputs(tab))
        _tap(tab, "const e=all.find(x=>x.tagName==='BUTTON'&&x.getAttribute('aria-label')==='A/B Testing');", "the A/B Testing button")
        ytu.wait_for(tab, "(()=>{" + WALK + "return all.some(x=>x.tagName==='TP-YT-PAPER-DIALOG'&&/Test and compare/.test(x.innerText||'')&&x.getBoundingClientRect().width>0)})()", 20)
        tab.click_text("Thumbnail only")
        time.sleep(2)
        inputs = _file_inputs(tab)[before:]
        if len(inputs) < 3:
            raise RuntimeError(f"expected 3 thumbnail slots in the dialog, found {len(inputs)}")
        for node, p in zip(inputs[1:3], paths[1:]):  # slot 1 is the current thumbnail (A)
            tab.send("DOM.setFileInputFiles", files=[p], backendNodeId=node)
            time.sleep(6)
        ytu.wait_for(tab, "(()=>{" + WALK + "const b=all.find(x=>x.id==='set-test-button'&&x.getBoundingClientRect().width>0);"
                     "return !!b && b.getAttribute('aria-disabled')!=='true'})()", 90, 1)
        _tap(tab, "const e=all.find(x=>x.id==='set-test-button'&&x.getBoundingClientRect().width>0);", "Set test")
        time.sleep(3)
        # the dialog closes into the edit page, which needs a Save to keep the test
        try:
            ytu.wait_for(tab, """(()=>{const b=document.querySelector('ytcp-button#save');
                return !!b && !b.hasAttribute('disabled') && b.getAttribute('aria-disabled')!=='true'})()""", 20, 0.5)
            tab.click("ytcp-button#save")
            time.sleep(5)
        except TimeoutError:
            pass  # some Studio builds save the test directly from the dialog
    finally:
        tab.close()
    state = status_of(vid)
    # a running test shows "Running..." in the thumbnail panel and three custom_N images; check slot 3 is C
    if not any(w in state.lower() for w in ("running", "test")):
        raise SystemExit(f"{vid}: Studio does not show a running test; thumbnail panel says: {state[:200]!r}")
    slots = slot_match(vid, paths)
    if slots.get(3) != "C":
        print(f"WARNING {vid}: slot images look like {slots}; check the test in Studio", file=sys.stderr)
    today = dt.date.today().isoformat()
    _record({"video": vid, "variants": dict(zip("ABC", [os.path.relpath(p, os.path.join(HERE, "..")) for p in paths])),
             "started": today, "status": state, "checked": today})
    if os.path.exists(CHANGELOG):
        subprocess.run([sys.executable, CHANGELOG, "add", "--date", today, "--area", "content",
                        "--what", f"YouTube Test & Compare thumbnail test started on {vid} (A/B/C)",
                        "--affected", f"impressions split evenly across 3 thumbnails on {vid}",
                        "--comparison", "the variants against each other (YouTube randomizes); titles unchanged",
                        "--metric", "Studio result by share of watch time: Winner, Preferred or None"], check=False)
    print(f"{vid}: test running. Studio says: {state[:160]}")


def slot_match(vid, paths):
    """Screenshot each test slot inside Studio (the i9.ytimg images need the signed-in session) and name the
    closest local variant. Small dark cards can sit close together, so only a clear match is trusted."""
    import base64, tempfile
    loc = {k: ytt.tiny(p) for k, p in zip("ABC", paths)}
    tab = _open(vid)
    out = {}
    try:
        rects = json.loads(tab.eval("(()=>{" + WALK + """const ed=all.find(x=>x.tagName==='YTCP-VIDEO-THUMBNAIL-EDITOR');
            ed.scrollIntoView({block:'center'});
            const inner=[];(function w(r){for(const e of r.querySelectorAll('*')){inner.push(e);if(e.shadowRoot)w(e.shadowRoot);}})(ed);
            return JSON.stringify(inner.filter(e=>e.tagName==='IMG'&&/custom_/.test(e.src)).map(e=>{const b=e.getBoundingClientRect();
            return [+e.src.match(/custom_(\\d)/)[1],b.x,b.y,b.width,b.height]}))})()"""))
        time.sleep(1.5)
        for n, x, y, w, h in rects:
            png = tab.send("Page.captureScreenshot", format="png", clip={"x": x, "y": y, "width": w, "height": h, "scale": 1})["data"]
            with tempfile.NamedTemporaryFile(suffix=".png") as f:
                f.write(base64.b64decode(png)); f.flush()
                g = ytt.tiny(f.name)
            d = {k: sum(abs(a - b) for a, b in zip(v, g)) / len(v) for k, v in loc.items()}
            out[n] = min(d, key=d.get)
    finally:
        tab.close()
    return out


def status_of(vid):
    tab = _open(vid)
    try:
        return _editor_text(tab)
    finally:
        tab.close()


def status(vids):
    """Read open tests from Studio. Prints RESULT lines for tests that reached Winner, Preferred or None."""
    log = json.load(open(LOG)) if os.path.exists(LOG) else []
    todo = vids or [x["video"] for x in log if not any(w in x.get("status", "") for w in ("Winner", "Preferred", "None", "ended"))]
    today = dt.date.today().isoformat()
    for vid in todo:
        state = status_of(vid)
        for x in log:
            if x["video"] == vid:
                x["status"], x["checked"] = state, today
        done = next((w for w in ("Winner", "Preferred", "None") if w in state), None)
        print(f"{'RESULT' if done else 'open'} {vid}: {' '.join(state.split())[:200]}")
    with open(LOG, "w") as f:
        json.dump(log, f, indent=1)
        f.write("\n")


if __name__ == "__main__":
    if len(sys.argv) >= 6 and sys.argv[1] == "start":
        start(*sys.argv[2:6])
    elif len(sys.argv) >= 2 and sys.argv[1] == "status":
        status(sys.argv[2:])
    else:
        sys.exit(__doc__)
