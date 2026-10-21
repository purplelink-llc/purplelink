/* PII Checker page. Text is checked by PiiCheck (pii-checker-core.js) in a Web Worker. Nothing you paste or open
   is sent anywhere. Text from the box or a file is untrusted, so it is only ever written with textContent,
   createTextNode or a textarea value. */
(function () {
  "use strict";
  var PC = window.PiiCheck;
  var MAX = 5 * 1024 * 1024;
  var PREVIEW_CHARS = 100000;
  var EXT_OK = /\.(txt|text)$/i;
  var $ = function (id) { return document.getElementById(id); };

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function plural(n, one, many) { return n.toLocaleString("en-US") + " " + (n === 1 ? one : many); }
  function fmtSize(n) {
    if (n < 1024) return n + " B";
    if (n < 1048576) return (n / 1024).toFixed(n < 10240 ? 1 : 0) + " KB";
    return (n / 1048576).toFixed(n < 10485760 ? 1 : 0) + " MB";
  }

  var SAMPLE = [
    "Client note, 14 October. Jordan Sample (born in Atlanta) called about the lease.",
    "Date of birth: 03/14/1981. Social Security number 472-81-0094, again 472 81 0094 on the form.",
    "Reach Jordan at jordan.sample@example.com or (404) 555-0182. Card on file 4111 1111 1111 1111.",
    "Patient ID 77-1290. IBAN GB82 WEST 1234 5698 7654 32. Portal link: https://portal.example.com/reset?token=a1b2c3.",
    "Order #84-2291 shipped 2026-10-21, version 2.4.1, ISBN 978-3-16-148410-0."
  ].join("\n");

  var input = $("pc-input"), statusEl = $("pc-status"), results = $("pc-results"), preview = $("pc-preview");
  var summary = $("pc-summary"), groupsEl = $("pc-groups"), copyBtn = $("pc-copy"), clearBtn = $("pc-clear");

  // ---------- network meter: counts what the page itself sends while it works ----------
  var net = { armed: false, requests: 0, bytes: 0 };
  function bodySize(b) {
    if (b == null) return 0;
    if (typeof b === "string") return b.length;
    if (typeof Blob !== "undefined" && b instanceof Blob) return b.size;
    if (typeof b.byteLength === "number") return b.byteLength;
    return String(b).length;
  }
  try {
    var f0 = window.fetch;
    if (f0) window.fetch = function (i, init) { if (net.armed) { net.requests++; net.bytes += bodySize(init && init.body); } return f0.apply(this, arguments); };
    if (navigator.sendBeacon) {
      var b0 = navigator.sendBeacon.bind(navigator);
      navigator.sendBeacon = function (url, data) { if (net.armed) { net.requests++; net.bytes += bodySize(data); } return b0(url, data); };
    }
    var xs = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function (body) { if (net.armed) { net.requests++; net.bytes += bodySize(body); } return xs.apply(this, arguments); };
  } catch (e) { /* the meter is a convenience; never block the tool */ }
  function showNet() {
    $("pc-net-text").textContent = net.requests === 0
      ? "Requests made while checking: 0. Nothing was sent."
      : "While checking, this page made " + plural(net.requests, "request", "requests") + " and sent " + net.bytes + " bytes: the anonymous usage count (how the text got here, never the text).";
    $("pc-net").classList.add("is-live");
  }

  // ---------- worker, with the same code on the page as a fallback ----------
  var worker = null, workerBroken = false, seq = 0, pending = {};
  function getWorker() {
    if (workerBroken || typeof Worker === "undefined") return null;
    if (worker) return worker;
    try {
      var link = document.querySelector("link[data-pc-worker]");
      var core = document.querySelector('script[src*="pii-checker-core"]');
      var u = new URL(link.href);
      u.searchParams.set("c", new URL(core.src).searchParams.get("v") || "");
      worker = new Worker(u.href);
      worker.onmessage = function (e) {
        var m = e.data, p = pending[m.id];
        if (!p) return;
        delete pending[m.id];
        if (m.ok) p.resolve(m); else p.reject(new Error(m.message));
      };
      worker.onerror = function () {
        workerBroken = true; worker = null;
        Object.keys(pending).forEach(function (id) { var p = pending[id]; delete pending[id]; p.reject(Object.assign(new Error("worker"), { workerFailed: true })); });
      };
      return worker;
    } catch (e) { workerBroken = true; return null; }
  }
  function check(text) {
    var id = ++seq, w = getWorker();
    if (w) {
      return new Promise(function (resolve, reject) {
        pending[id] = { resolve: resolve, reject: reject };
        w.postMessage({ id: id, text: text });
      }).catch(function (err) {
        if (!err.workerFailed) throw err;
        return inline(id, text);
      });
    }
    return inline(id, text);
  }
  function inline(id, text) {
    return new Promise(function (resolve, reject) {
      setTimeout(function () {
        try {
          var r = PC.check(text);
          resolve({ id: id, ok: true, total: r.total, groups: r.groups, redacted: r.redacted, spans: r.spans.map(function (s) { return { s: s.start, e: s.end, l: s.label }; }) });
        } catch (err) { reject(err); }
      }, 0);
    });
  }

  // ---------- results ----------
  var current = null, counted = false, source = "typed", pass = 0, timer = 0;

  function paintPreview(text, res) {
    preview.textContent = "";
    var shown = text.length > PREVIEW_CHARS ? text.slice(0, PREVIEW_CHARS) : text;
    var cursor = 0;
    for (var i = 0; i < res.spans.length; i++) {
      var s = res.spans[i];
      if (s.s >= shown.length) break;
      var end = Math.min(s.e, shown.length);
      if (s.s > cursor) preview.appendChild(document.createTextNode(shown.slice(cursor, s.s)));
      var mk = el("mark", "pc-mark", shown.slice(s.s, end));
      mk.setAttribute("data-label", PC.DISPLAY[s.l]);
      mk.title = PC.DISPLAY[s.l];
      preview.appendChild(mk);
      cursor = end;
    }
    if (cursor < shown.length) preview.appendChild(document.createTextNode(shown.slice(cursor)));
    $("pc-cut").hidden = text.length <= PREVIEW_CHARS;
  }

  function paintGroups(res) {
    groupsEl.textContent = "";
    res.groups.forEach(function (g) {
      var li = el("li", "pc-group");
      li.appendChild(el("span", "pc-group-name", g.name));
      li.appendChild(el("span", "pc-group-count", g.count.toLocaleString("en-US")));
      li.appendChild(el("span", "pc-group-ph", g.placeholders.length > 6 ? g.placeholders.slice(0, 6).join(" ") + " and " + (g.placeholders.length - 6) + " more" : g.placeholders.join(" ")));
      groupsEl.appendChild(li);
    });
  }

  function render(text, res) {
    current = { text: text, res: res };
    var empty = text.trim() === "";
    results.setAttribute("data-state", empty ? "empty" : res.total ? "found" : "none");
    $("pc-preview-wrap").hidden = empty;
    copyBtn.disabled = empty;
    clearBtn.hidden = empty;
    if (empty) {
      summary.textContent = "Paste text above to see what it finds.";
      groupsEl.textContent = "";
      preview.textContent = "";
      return;
    }
    summary.textContent = res.total
      ? plural(res.total, "item", "items") + " found, in " + plural(res.groups.length, "type", "types") + "."
      : "No numbers or addresses in the formats this check knows were found.";
    paintGroups(res);
    paintPreview(text, res);
  }

  async function run(text) {
    var mine = ++pass;
    statusEl.classList.add("is-busy");
    net.armed = true;
    try {
      var res = await check(text);
      if (mine !== pass) return;
      render(text, res);
      if (text.trim() !== "" && !counted && window.plTrack) {
        counted = true;
        window.plTrack("tool_use", "pii-checker:" + source);
      }
      statusEl.textContent = text.trim() === "" ? "" : "Checked " + plural(text.length, "character", "characters") + ".";
    } catch (err) {
      if (mine !== pass) return;
      statusEl.textContent = "The check failed (" + ((err && err.message) || "unknown error") + "). Your text was not changed.";
    } finally {
      if (mine === pass) {
        net.armed = false;
        statusEl.classList.remove("is-busy");
        showNet();
      }
    }
  }

  function schedule(delay) {
    clearTimeout(timer);
    timer = setTimeout(function () { run(input.value); }, delay);
  }

  // ---------- input ----------
  input.addEventListener("paste", function () { source = "paste"; });
  input.addEventListener("input", function (e) {
    if (e.inputType && /^insertFrom(Paste|Drop)/.test(e.inputType)) source = "paste";
    else if (!counted && source !== "paste") source = "typed";
    schedule(250);
  });

  function takeFile(f) {
    if (!f) return;
    if (!EXT_OK.test(f.name)) { statusEl.textContent = f.name + " was not opened. This tool reads .txt files."; return; }
    if (f.size > MAX) { statusEl.textContent = f.name + " was not opened. It is over " + fmtSize(MAX) + "."; return; }
    if (f.size === 0) { statusEl.textContent = f.name + " was not opened. It is empty."; return; }
    f.arrayBuffer().then(function (buf) {
      source = "file";
      counted = false;
      input.value = PC.decodeBytes(new Uint8Array(buf)).replace(/^﻿/, "");
      $("pc-file-name").textContent = f.name + " (" + fmtSize(f.size) + ")";
      schedule(0);
    }, function () { statusEl.textContent = f.name + " could not be read."; });
  }
  var box = $("pc-box"), fileInput = $("pc-file");
  $("pc-choose").addEventListener("click", function () { fileInput.click(); });
  fileInput.addEventListener("change", function () { if (fileInput.files && fileInput.files.length) takeFile(fileInput.files[0]); fileInput.value = ""; });
  ["dragenter", "dragover"].forEach(function (t) {
    box.addEventListener(t, function (e) { e.preventDefault(); box.classList.add("is-over"); });
  });
  box.addEventListener("dragleave", function (e) { if (!box.contains(e.relatedTarget)) box.classList.remove("is-over"); });
  box.addEventListener("drop", function (e) {
    e.preventDefault();
    box.classList.remove("is-over");
    var files = e.dataTransfer && e.dataTransfer.files;
    if (files && files.length) takeFile(files[0]);
    else if (e.dataTransfer && e.dataTransfer.getData("text")) { source = "paste"; input.value += e.dataTransfer.getData("text"); schedule(0); }
  });

  $("pc-sample").addEventListener("click", function () {
    source = "sample";
    counted = false;
    $("pc-file-name").textContent = "";
    input.value = SAMPLE;
    schedule(0);
    input.focus();
  });

  function legacyCopy(text) {
    var ta = el("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.className = "sr-only";
    document.body.appendChild(ta);
    ta.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    ta.remove();
    return ok;
  }
  copyBtn.addEventListener("click", function () {
    if (!current) return;
    var text = current.res.redacted, old = copyBtn.textContent;
    function done(ok) {
      copyBtn.textContent = ok ? "Copied" : "Copy failed";
      statusEl.textContent = ok ? "Copied the redacted text." : "The browser blocked copying. Select the text in the box and copy it yourself.";
      setTimeout(function () { copyBtn.textContent = old; }, 1800);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(function () { done(true); }, function () { done(legacyCopy(text)); });
    else done(legacyCopy(text));
  });

  clearBtn.addEventListener("click", function () {
    input.value = "";
    $("pc-file-name").textContent = "";
    counted = false;
    clearTimeout(timer);
    ++pass;
    render("", { total: 0, groups: [], redacted: "", spans: [] });
    statusEl.textContent = "Cleared.";
    input.focus();
  });

  render("", { total: 0, groups: [], redacted: "", spans: [] });
})();
