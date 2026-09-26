"""Drive one tab of the automation Chrome over raw CDP, without Playwright.

WHY THIS EXISTS
Playwright's connect_over_cdp attaches to every target in the browser. Once
the automation profile picked up synced extensions (2026-09-24, ~10 service
workers), that attach hung past 180s and nothing could connect. Talking to a
single page's own websocket sidesteps the extensions entirely.

  from cdp_tab import Tab
  t = Tab.new("https://my.pixsy.com/matches")   # opens a fresh tab
  t.wait_idle(8)
  print(t.eval("document.body.innerText"))
  t.close()
"""
import itertools, json, time, urllib.parse, urllib.request
import websocket

BASE = "http://127.0.0.1:9340"


class Tab:
    def __init__(self, info):
        self.info = info
        self.ws = websocket.create_connection(info["webSocketDebuggerUrl"], timeout=60,
                                              suppress_origin=True)
        self._ids = itertools.count(1)
        self.send("Page.enable")   # needed to see (and auto-accept) beforeunload dialogs

    @classmethod
    def new(cls, url="about:blank", background=False):
        # background=True keeps whatever tab is in front there: Chrome pauses
        # rAF in background tabs, so stealing focus from a running job (e.g.
        # etsy-list.py) stops its dropdowns from ever rendering.
        if background:
            bws = json.load(urllib.request.urlopen(f"{BASE}/json/version", timeout=30))["webSocketDebuggerUrl"]
            b = websocket.create_connection(bws, timeout=30, suppress_origin=True)
            b.send(json.dumps({"id": 1, "method": "Target.createTarget",
                               "params": {"url": url, "background": True}}))
            while True:
                m = json.loads(b.recv())
                if m.get("id") == 1:
                    break
            b.close()
            tid = m["result"]["targetId"]
            for t in json.load(urllib.request.urlopen(f"{BASE}/json/list", timeout=30)):
                if t["id"] == tid:
                    return cls(t)
            raise LookupError(tid)
        req = urllib.request.Request(f"{BASE}/json/new?{urllib.parse.quote(url, safe='')}", method="PUT")
        return cls(json.load(urllib.request.urlopen(req, timeout=30)))

    @classmethod
    def find(cls, substr):
        for t in json.load(urllib.request.urlopen(f"{BASE}/json/list", timeout=30)):
            if t["type"] == "page" and substr in t["url"]:
                return cls(t)
        raise LookupError(substr)

    def send(self, method, **params):
        i = next(self._ids)
        self.ws.send(json.dumps({"id": i, "method": method, "params": params}))
        while True:
            m = json.loads(self.ws.recv())
            # A half-filled editor raises "Leave site?" on navigation, and the
            # navigate call then never answers. Accept it so nothing hangs.
            if m.get("method") == "Page.javascriptDialogOpening" and m["params"].get("type") == "beforeunload":
                self.ws.send(json.dumps({"id": next(self._ids), "method": "Page.handleJavaScriptDialog",
                                         "params": {"accept": True}}))
                continue
            if m.get("id") == i:
                if "error" in m:
                    raise RuntimeError(m["error"])
                return m.get("result", {})

    def eval(self, js, await_promise=True):
        r = self.send("Runtime.evaluate", expression=js, returnByValue=True, awaitPromise=await_promise)
        if "exceptionDetails" in r:
            raise RuntimeError(r["exceptionDetails"].get("text"))
        return r.get("result", {}).get("value")

    def goto(self, url, settle=6):
        self.send("Page.navigate", url=url)
        self.wait_idle(settle)

    def wait_idle(self, settle=6, timeout=60):
        end = time.time() + timeout
        while time.time() < end and self.eval("document.readyState") != "complete":
            time.sleep(0.5)
        time.sleep(settle)

    def text(self):
        return self.eval("document.body ? document.body.innerText : ''") or ""

    def url(self):
        return self.eval("location.href")

    # --- real input, for React forms that ignore programmatic .value= ---
    def _box(self, selector, index=0):
        r = self.eval(f"""(()=>{{const e=[...document.querySelectorAll({selector!r})][{index}];
            if(!e) return null; e.scrollIntoView({{block:'center'}});
            const b=e.getBoundingClientRect(); return [b.x+b.width/2,b.y+b.height/2,b.width,b.height]}})()""")
        if not r:
            raise LookupError(selector)
        return r

    def click(self, selector, index=0):
        x, y, *_ = self._box(selector, index)
        time.sleep(0.3)
        for t in ("mousePressed", "mouseReleased"):
            self.send("Input.dispatchMouseEvent", type=t, x=x, y=y, button="left", clickCount=1)
        time.sleep(0.6)

    def click_text(self, text, tag="*", exact=True):
        """Click the smallest visible element whose text matches."""
        cond = f"t===({text!r})" if exact else f"t.includes({text!r})"
        # walk shadow roots too: Etsy's modal buttons are web components
        r = self.eval(f"""(()=>{{const all=[];(function walk(root){{for(const e of root.querySelectorAll('*')){{
            if(e.matches({tag!r}))all.push(e); if(e.shadowRoot)walk(e.shadowRoot);}}}})(document);
            const els=all.filter(e=>{{
            const t=(e.innerText||'').trim(); const b=e.getBoundingClientRect();
            return {cond} && b.width>0 && b.height>0}});
            els.sort((a,b)=>a.innerText.length-b.innerText.length||a.getBoundingClientRect().width-b.getBoundingClientRect().width);
            const e=els[0]; if(!e) return null; e.scrollIntoView({{block:'center'}});
            const b=e.getBoundingClientRect(); return [b.x+b.width/2,b.y+b.height/2]}})()""")
        if not r:
            raise LookupError(text)
        time.sleep(0.3)
        for t in ("mousePressed", "mouseReleased"):
            self.send("Input.dispatchMouseEvent", type=t, x=r[0], y=r[1], button="left", clickCount=1)
        time.sleep(0.6)

    def click_topmost(self, text):
        """Click the visible element with this exact text that is actually on top
        at its own centre (i.e. inside the open modal, not behind it)."""
        r = self.eval(f"""(()=>{{const all=[];(function walk(root){{for(const e of root.querySelectorAll('*')){{
            all.push(e); if(e.shadowRoot)walk(e.shadowRoot);}}}})(document);
            for(const e of all.reverse()){{ if((e.innerText||'').trim()!=={text!r}) continue;
              const b=e.getBoundingClientRect(); if(!b.width||!b.height) continue;
              const x=b.x+b.width/2,y=b.y+b.height/2; const top=document.elementFromPoint(x,y);
              if(top && (e===top||e.contains(top)||top.contains(e)||(top.shadowRoot&&top.shadowRoot.contains(e))||e.getRootNode().host===top))
                return [x,y]; }} return null}})()""")
        if not r:
            raise LookupError(text)
        self.tap(*r)

    def type(self, selector, text, clear=True, index=0):
        self.click(selector, index)
        if clear:
            self.eval(f"(()=>{{const e=[...document.querySelectorAll({selector!r})][{index}]; e.select&&e.select();}})()")
            self.send("Input.dispatchKeyEvent", type="keyDown", key="Backspace", code="Backspace", windowsVirtualKeyCode=8)
            self.send("Input.dispatchKeyEvent", type="keyUp", key="Backspace", code="Backspace", windowsVirtualKeyCode=8)
        self.send("Input.insertText", text=text)
        time.sleep(0.4)

    def key(self, key, code=None, vk=None):
        code = code or key
        vk = vk or {"Enter": 13, "Tab": 9, "Escape": 27, "ArrowDown": 40}.get(key, 0)
        for t in ("keyDown", "keyUp"):
            self.send("Input.dispatchKeyEvent", type=t, key=key, code=code, windowsVirtualKeyCode=vk,
                      **({"text": "\r"} if key == "Enter" and t == "keyDown" else {}))
        time.sleep(0.3)

    def set_files(self, selector, paths, index=0):
        # Chrome resolves these against ITS cwd, not ours: a relative path
        # attaches a phantom file and the site's upload stalls at 0%.
        import os
        doc = self.send("DOM.getDocument", depth=-1, pierce=True)["root"]["nodeId"]
        ids = self.send("DOM.querySelectorAll", nodeId=doc, selector=selector)["nodeIds"]
        self.send("DOM.setFileInputFiles", files=[os.path.abspath(p) for p in paths], nodeId=ids[index])

    def tap(self, x, y, pause=1.5):
        """Click at CSS-pixel coordinates."""
        for t in ("mousePressed", "mouseReleased"):
            self.send("Input.dispatchMouseEvent", type=t, x=x, y=y, button="left", clickCount=1)
        time.sleep(pause)

    def upload_by_click(self, x, y, paths, wait=8):
        """Click something that opens a native file chooser and answer it."""
        self.send("Page.enable")
        self.send("Page.setInterceptFileChooserDialog", enabled=True)
        try:
            self.tap(x, y, pause=0)
            end, ev = time.time() + 10, None
            self.ws.settimeout(2)
            while time.time() < end and not ev:
                try:
                    m = json.loads(self.ws.recv())
                except Exception:
                    continue
                if m.get("method") == "Page.fileChooserOpened":
                    ev = m["params"]
            if not ev:
                raise RuntimeError("no file chooser opened")
            self.send("DOM.setFileInputFiles", files=[__import__("os").path.abspath(p) for p in paths], backendNodeId=ev["backendNodeId"])
            time.sleep(wait)
        finally:
            self.ws.settimeout(60)
            self.send("Page.setInterceptFileChooserDialog", enabled=False)

    def shot(self, path):
        import base64
        data = self.send("Page.captureScreenshot", format="jpeg", quality=70)["data"]
        open(path, "wb").write(base64.b64decode(data))

    def front(self):
        urllib.request.urlopen(f"{BASE}/json/activate/{self.info['id']}", timeout=10)

    def close(self):
        try:
            self.ws.close()
        finally:
            urllib.request.urlopen(f"{BASE}/json/close/{self.info['id']}", timeout=10)
