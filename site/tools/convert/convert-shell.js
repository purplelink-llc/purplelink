/* File converters, page side: drop zone, queue, worker, network meter, zip. Shared by every /tools/<pair>/ page.
   The page's .cv-app[data-convert] names the pair; convert-core.js has the table. Files never leave the tab. */
(function () {
  "use strict";
  var C = window.Convert;
  var app = document.querySelector(".cv-app[data-convert]");
  if (!C || !app) return;
  var PAIR = app.getAttribute("data-convert");
  var CONV = C.CONVERSIONS[PAIR];
  if (!CONV) return;

  function $(id) { return document.getElementById(id); }
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  var MOBILE = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent) || (navigator.maxTouchPoints > 1 && /Mac/.test(navigator.platform || ""));

  // ---------- options, remembered per pair ----------
  var KEY = "pl-convert-" + PAIR;
  var outputs = Array.prototype.slice.call(document.querySelectorAll('input[name="cv-output"]'));
  var quality = $("cv-quality"), qualityOut = $("cv-quality-out"), bg = $("cv-bg"), iconset = $("cv-iconset");
  (function restore() {
    var s = {};
    try { s = JSON.parse(localStorage.getItem(KEY) || "{}") || {}; } catch (e) { s = {}; }
    outputs.forEach(function (r) { if (r.value === s.output) r.checked = true; });
    if (quality && s.quality) quality.value = s.quality;
    if (bg && s.background) bg.value = s.background;
    if (iconset && typeof s.iconset === "boolean") iconset.checked = s.iconset;
  })();
  function options() {
    var chosen = outputs.filter(function (r) { return r.checked; })[0];
    return C.options(PAIR, {
      output: chosen ? chosen.value : CONV.output,
      quality: quality ? Number(quality.value) / 100 : undefined,
      background: bg ? bg.value : undefined,
      iconset: iconset ? iconset.checked : false,
      mobile: MOBILE
    });
  }
  function syncOptions() {
    var o = options();
    if (qualityOut && quality) qualityOut.textContent = quality.value;
    // JPEG-only controls are shown only while JPG is chosen.
    Array.prototype.forEach.call(document.querySelectorAll("[data-for-output]"), function (n) {
      n.hidden = n.getAttribute("data-for-output") !== o.output;
    });
    try { localStorage.setItem(KEY, JSON.stringify({ output: o.output, quality: quality ? quality.value : "", background: o.background, iconset: o.iconset })); } catch (e) { /* private mode */ }
  }
  outputs.concat([quality, bg, iconset]).forEach(function (n) { if (n) { n.addEventListener("change", syncOptions); n.addEventListener("input", syncOptions); } });
  syncOptions();

  // ---------- network meter: what this page and its worker send while converting ----------
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
    if (f0) window.fetch = function (input, init) { if (net.armed) { net.requests++; net.bytes += bodySize(init && init.body); } return f0.apply(this, arguments); };
    if (navigator.sendBeacon) {
      var b0 = navigator.sendBeacon.bind(navigator);
      navigator.sendBeacon = function (url, data) { if (net.armed) { net.requests++; net.bytes += bodySize(data); } return b0(url, data); };
    }
    var xs = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function (body) { if (net.armed) { net.requests++; net.bytes += bodySize(body); } return xs.apply(this, arguments); };
  } catch (e) { /* the meter is a convenience; never block the tool */ }
  function showNet() {
    var t = $("cv-net-text");
    if (!t) return;
    t.textContent = net.bytes === 0
      ? "Bytes sent while converting: 0. Your files stayed on this device."
      : "While converting, " + net.bytes + " bytes were sent in " + net.requests + " request" + (net.requests > 1 ? "s" : "") + ". The converter never sends files, so please tell ben@purplelink.llc what you saw.";
    $("cv-net").classList.add("is-live");
  }

  // ---------- worker ----------
  var worker = null, seq = 0, pending = {};
  var CAN = typeof Worker !== "undefined" && typeof OffscreenCanvas !== "undefined" && typeof createImageBitmap !== "undefined";
  function getWorker() {
    if (worker) return worker;
    var link = document.querySelector("link[data-convert-worker]");
    var core = document.querySelector('script[src*="convert-core"]');
    var u = new URL(link.href);
    u.searchParams.set("c", new URL(core.src).searchParams.get("v") || "");
    worker = new Worker(u.href);
    worker.onmessage = function (e) {
      var m = e.data, p = pending[m.id];
      if (!p) return;
      if (m.type === "progress") { p.item.p = m.p; p.item.label = m.label; paintProgress(p.item); return; }
      delete pending[m.id];
      var w = (m.res && m.res.net) || m.net;
      if (w && net.armed) { net.requests += w.requests; net.bytes += w.bytes; }
      if (m.type === "done") p.resolve(m.res); else p.reject(new Error(m.message));
    };
    worker.onerror = function (ev) {
      if (ev && ev.preventDefault) ev.preventDefault();
      worker = null;
      Object.keys(pending).forEach(function (id) {
        var p = pending[id]; delete pending[id];
        p.reject(new Error("The converter stopped, most likely because the picture needs more memory than this tab has. Try it on its own, or on a computer."));
      });
    };
    return worker;
  }
  function run(item, buf) {
    return new Promise(function (resolve, reject) {
      var id = ++seq;
      pending[id] = { item: item, resolve: resolve, reject: reject };
      getWorker().postMessage({ id: id, pair: PAIR, name: item.file.name, buffer: buf, opts: options() }, [buf]);
    });
  }

  // ---------- queue ----------
  var items = [], running = false;
  var drop = $("cv-drop"), input = $("cv-file"), list = $("cv-list"), statusEl = $("cv-status"), bar = $("cv-bar");

  if (!CAN) {
    statusEl.textContent = "This browser cannot convert pictures here. It needs background workers and off-screen drawing, which Chrome and Edge 69, Firefox 105 and Safari 16.4 and later have.";
    statusEl.classList.add("is-error");
    drop.classList.add("is-disabled");
    input.disabled = true;
    return;
  }

  function addFiles(files) {
    var room = C.MAX_FILES - items.length;
    var arr = Array.prototype.slice.call(files || []);
    if (!arr.length) return;
    if (arr.length > room) { statusEl.textContent = "Up to " + C.MAX_FILES + " files at a time. The first " + Math.max(0, room) + " were added."; arr = arr.slice(0, Math.max(0, room)); }
    arr.forEach(function (file) {
      var item = { file: file, name: file.name || "pasted picture", state: "queued", p: 0, label: "", li: el("li", "cv-item") };
      items.push(item);
      list.appendChild(item.li);
      paint(item);
    });
    bar.hidden = false;
    pump();
  }

  async function pump() {
    if (running) return;
    running = true;
    net.armed = true;
    var converted = 0;
    try {
      for (;;) {
        var next = items.find(function (i) { return i.state === "queued"; });
        if (!next) break;
        var done = items.filter(function (i) { return i.state === "done" || i.state === "error"; }).length;
        statusEl.textContent = "Converting " + (done + 1) + " of " + items.length + "…";
        statusEl.classList.add("is-busy");
        next.state = "working"; next.p = 0.02; next.label = "Reading";
        paint(next);
        if (await convert(next)) converted++;
        paint(next);
      }
    } finally {
      running = false;
      net.armed = false;
      statusEl.classList.remove("is-busy");
      var ok = items.filter(function (i) { return i.state === "done"; }).length;
      var bad = items.filter(function (i) { return i.state === "error"; }).length;
      statusEl.textContent = ok ? "Done. " + ok + " file" + (ok > 1 ? "s" : "") + " converted" + (bad ? ", " + bad + " could not be." : ".") : (bad ? "Nothing could be converted. The reasons are below." : "");
      $("cv-all").hidden = ok < 2;
      showNet();
      // Counted after the meter is off: one anonymous event per batch, pair and output format only.
      if (converted && window.plTrack) window.plTrack("tool_use", PAIR + ":" + options().output);
    }
  }

  async function convert(item) {
    try {
      var head = new Uint8Array(await item.file.slice(0, 64).arrayBuffer());
      var why = C.refuse(PAIR, C.sniff(head), item.file.size);
      if (why) throw new Error(why);
      var res = await run(item, await item.file.arrayBuffer());
      item.res = res;
      item.blobs = res.outputs.map(function (o) { return { name: o.name, part: !!o.part, blob: new Blob([o.bytes], { type: o.mime }) }; });
      res.outputs = null; // the blobs hold the bytes now
      item.state = "done";
      return true;
    } catch (e) {
      item.state = "error";
      item.error = e && e.message ? e.message : "Could not convert this file.";
      return false;
    }
  }

  function revoke(item) { (item.urls || []).forEach(function (u) { URL.revokeObjectURL(u); }); item.urls = []; }
  function url(item, blob) { var u = URL.createObjectURL(blob); (item.urls = item.urls || []).push(u); return u; }

  function paintProgress(item) {
    if (!item.li) return;
    var pr = item.li.querySelector("progress");
    if (pr) pr.value = Math.round(item.p * 100);
    var lab = item.li.querySelector(".cv-prog-label");
    if (lab) lab.textContent = item.label || "Working…";
  }

  function paint(item) {
    var li = item.li;
    revoke(item);
    li.textContent = "";
    li.dataset.state = item.state;
    var head = el("div", "cv-item-head");
    head.appendChild(el("span", "cv-name", item.name));
    var mains = item.blobs ? item.blobs.filter(function (b) { return !b.part; }) : [];
    head.appendChild(el("span", "cv-size", item.state === "done" && mains.length
      ? C.formatBytes(item.file.size) + " to " + C.formatBytes(mains[0].blob.size)
      : C.formatBytes(item.file.size)));
    li.appendChild(head);

    if (item.state === "queued") { li.appendChild(el("p", "cv-note", "Waiting")); return; }
    if (item.state === "working") {
      var lab = el("p", "cv-prog-label", item.label || "Working…");
      lab.id = "cv-l-" + items.indexOf(item);
      li.appendChild(lab);
      var pr = el("progress", "cv-prog");
      pr.max = 100; pr.value = Math.round(item.p * 100);
      pr.setAttribute("aria-labelledby", lab.id);
      li.appendChild(pr);
      return;
    }
    var actions = el("div", "cv-actions");
    if (item.state === "error") {
      var err = el("p", "cv-error", item.error); err.setAttribute("role", "alert"); li.appendChild(err);
      var rm = el("button", "btn btn-ghost cv-small", "Remove"); rm.type = "button";
      rm.addEventListener("click", function () { removeItem(item); });
      actions.appendChild(rm);
      li.appendChild(actions);
      return;
    }
    if (item.res.width) li.appendChild(el("p", "cv-note", item.res.width + " by " + item.res.height + " pixels"));
    (item.res.notes || []).forEach(function (n) { li.appendChild(el("p", "cv-warn", n)); });
    mains.forEach(function (b) {
      var a = el("a", "btn btn-primary cv-small", "Download " + b.name);
      a.href = url(item, b.blob); a.download = b.name;
      actions.appendChild(a);
    });
    var parts = item.blobs.filter(function (b) { return b.part; });
    if (parts.length) {
      var z = el("button", "btn btn-ghost cv-small", "Download the .iconset folder (.zip)"); z.type = "button";
      z.addEventListener("click", function () { saveZip(parts, parts[0].name.split("/")[0] + ".zip", z); });
      actions.appendChild(z);
    }
    var rm2 = el("button", "btn btn-ghost cv-small", "Remove"); rm2.type = "button";
    rm2.addEventListener("click", function () { removeItem(item); });
    actions.appendChild(rm2);
    li.appendChild(actions);
  }

  function removeItem(item) {
    if (item.state === "working") return;
    revoke(item);
    items = items.filter(function (i) { return i !== item; });
    item.li.remove();
    if (!items.length) { bar.hidden = true; statusEl.textContent = ""; }
    $("cv-all").hidden = items.filter(function (i) { return i.state === "done"; }).length < 2;
  }

  function saveZip(entries, zipName, button) {
    var total = entries.reduce(function (s, e) { return s + e.blob.size; }, 0);
    if (total > C.MAX_ZIP_BYTES) { statusEl.textContent = "Together the results are over 1 GB, too large to zip in a browser tab. Download them one by one."; return; }
    if (!window.JSZip) { statusEl.textContent = "The zip library did not load. Download the files one by one, or reload the page."; return; }
    var zip = new window.JSZip();
    var names = C.uniqueNames(entries.map(function (e) { return e.name; }));
    entries.forEach(function (e, i) { zip.file(names[i], e.blob, { binary: true }); });
    var label = button.textContent;
    button.disabled = true; button.textContent = "Zipping…";
    zip.generateAsync({ type: "blob", compression: "STORE" }).then(function (blob) {
      var a = document.createElement("a");
      var u = URL.createObjectURL(blob);
      a.href = u; a.download = zipName;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(u); }, 30000);
    }).catch(function () {
      statusEl.textContent = "The zip could not be made. Download the files one by one.";
    }).then(function () { button.disabled = false; button.textContent = label; });
  }

  $("cv-all").addEventListener("click", function () {
    var entries = [];
    items.forEach(function (i) {
      if (i.state === "done") i.blobs.forEach(function (b) { entries.push(b); });
    });
    saveZip(entries, PAIR + ".zip", $("cv-all"));
  });
  $("cv-clear").addEventListener("click", function () {
    items.filter(function (i) { return i.state !== "working"; }).forEach(removeItem);
  });

  // ---------- input: click, keyboard, drag, paste ----------
  input.addEventListener("change", function () { addFiles(input.files); input.value = ""; });
  drop.addEventListener("dragover", function (e) { e.preventDefault(); drop.classList.add("is-over"); });
  drop.addEventListener("dragleave", function (e) { if (!drop.contains(e.relatedTarget)) drop.classList.remove("is-over"); });
  drop.addEventListener("drop", function (e) {
    e.preventDefault();
    drop.classList.remove("is-over");
    if (e.dataTransfer && e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
  });
  document.addEventListener("paste", function (e) {
    if (e.target && /^(INPUT|TEXTAREA)$/.test(e.target.tagName)) return;
    var files = e.clipboardData ? Array.prototype.filter.call(e.clipboardData.files || [], Boolean) : [];
    if (files.length) { e.preventDefault(); addFiles(files); }
  });
})();
