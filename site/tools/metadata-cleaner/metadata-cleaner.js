/* Metadata Cleaner page. Files are read with the browser, cleaned by MetaClean
   (metadata-cleaner-core.js) inside a Web Worker, and offered as downloads. No
   file bytes leave the device. Metadata values come from untrusted files, so
   they are only ever written with textContent. */
(function () {
  "use strict";
  var MC = window.MetaClean;
  var MAX = 200 * 1024 * 1024;
  var MAX_VIDEO = 600 * 1024 * 1024;
  var $ = function (id) { return document.getElementById(id); };
  var EXT_OK = /\.(jpe?g|png|webp|gif|tiff?|svg|pdf|docx|xlsx|pptx|docm|xlsm|pptm|odt|ods|odp|mp4|mov|m4v)$/i;
  var IMG_OK = /\.(jpe?g|png|webp|gif)$/i;

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function fmtSize(n) {
    if (n < 1024) return n + " B";
    if (n < 1048576) return (n / 1024).toFixed(n < 10240 ? 1 : 0) + " KB";
    if (n < 1073741824) return (n / 1048576).toFixed(n < 10485760 ? 1 : 0) + " MB";
    return (n / 1073741824).toFixed(2) + " GB";
  }
  function baseName(name) { var i = name.lastIndexOf("."); return i > 0 ? name.slice(0, i) : name; }
  function extOf(name) { var i = name.lastIndexOf("."); return i > 0 ? name.slice(i) : ""; }
  function cleanName(name) { return baseName(name) + "-clean" + extOf(name); }
  function download(blob, name) {
    var url = URL.createObjectURL(blob);
    var a = el("a");
    a.href = url; a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 30000);
  }
  var MIME = {
    jpeg: "image/jpeg", png: "image/png", webp: "image/webp", gif: "image/gif", tiff: "image/tiff", svg: "image/svg+xml",
    pdf: "application/pdf", mp4: "video/mp4", odf: "application/vnd.oasis.opendocument.text",
    docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation"
  };

  // ---------- saved options ----------
  var KEY = "mc-options";
  function loadSaved() { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { return {}; } }
  function save() {
    try {
      localStorage.setItem(KEY, JSON.stringify({
        rotate: $("mc-opt-rotate").checked, anon: $("mc-opt-anon").checked,
        title: $("mc-opt-title").checked, author: $("mc-opt-author").value
      }));
    } catch (e) { /* storage can be blocked; the page works without it */ }
  }
  (function restore() {
    var s = loadSaved();
    if (s.rotate === false) $("mc-opt-rotate").checked = false;
    if (s.anon === false) $("mc-opt-anon").checked = false;
    if (s.title) $("mc-opt-title").checked = true;
    if (typeof s.author === "string") $("mc-opt-author").value = s.author;
  })();
  ["mc-opt-rotate", "mc-opt-anon", "mc-opt-title", "mc-opt-author"].forEach(function (id) { $(id).addEventListener("change", save); });
  function options() {
    return {
      keepOrientation: $("mc-opt-rotate").checked, anonymize: $("mc-opt-anon").checked,
      keepTitle: $("mc-opt-title").checked, author: $("mc-opt-author").value.trim()
    };
  }

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
    if (f0) window.fetch = function (input, init) { if (net.armed) { net.requests++; net.bytes += bodySize(init && init.body); } return f0.apply(this, arguments); };
    if (navigator.sendBeacon) {
      var b0 = navigator.sendBeacon.bind(navigator);
      navigator.sendBeacon = function (url, data) { if (net.armed) { net.requests++; net.bytes += bodySize(data); } return b0(url, data); };
    }
    var xs = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function (body) { if (net.armed) { net.requests++; net.bytes += bodySize(body); } return xs.apply(this, arguments); };
  } catch (e) { /* the meter is a convenience; never block the tool */ }
  function showNet(done) {
    var t = $("mc-net-text");
    if (!done) { t.textContent = "Bytes of your files sent anywhere: 0"; return; }
    t.textContent = net.requests === 0
      ? "Network requests while cleaning: 0. Nothing was sent."
      : "While cleaning, this page made " + net.requests + " request" + (net.requests > 1 ? "s" : "") + " and sent " + net.bytes + " bytes: the anonymous usage count (file type only, no names or content).";
    $("mc-net").classList.add("is-live");
  }

  // ---------- tabs ----------
  var TABS = [["mc-tab-files", "mc-panel-files"], ["mc-tab-redact", "mc-panel-redact"], ["mc-tab-text", "mc-panel-text"]];
  function showTab(id) {
    TABS.forEach(function (o) {
      var on = o[0] === id;
      $(o[0]).setAttribute("aria-selected", String(on));
      $(o[1]).hidden = !on;
    });
  }
  function activeTab() { return (TABS.find(function (o) { return $(o[0]).getAttribute("aria-selected") === "true"; }) || TABS[0])[0]; }
  TABS.forEach(function (t) { $(t[0]).addEventListener("click", function () { showTab(t[0]); }); });

  // ---------- worker ----------
  var worker, workerBroken = false, seq = 0, pending = {};
  function getWorker() {
    if (workerBroken || typeof Worker === "undefined") return null;
    if (worker) return worker;
    try {
      var link = document.querySelector("link[data-mc-worker]");
      var core = document.querySelector('script[src*="metadata-cleaner-core"]');
      var u = new URL(link.href);
      u.searchParams.set("c", new URL(core.src).searchParams.get("v") || "");
      worker = new Worker(u.href);
      worker.onmessage = function (e) {
        var m = e.data, p = pending[m.id];
        if (!p) return;
        if (m.type === "progress") { p.item.p = m.p; p.item.label = m.label; paintProgress(p.item); return; }
        delete pending[m.id];
        if (m.type === "done") p.resolve(m.res); else p.reject(new Error(m.message));
      };
      worker.onerror = function () {
        workerBroken = true; worker = null;
        Object.keys(pending).forEach(function (id) { var p = pending[id]; delete pending[id]; p.reject(Object.assign(new Error("worker"), { workerFailed: true })); });
      };
      return worker;
    } catch (e) { workerBroken = true; return null; }
  }
  var pdfLibPromise = null;
  function loadPdfLib() {
    if (window.PDFLib) return Promise.resolve();
    if (pdfLibPromise) return pdfLibPromise;
    pdfLibPromise = new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      s.src = "/assets/vendor/pdf-lib.min.js?v=0f9a5cad07";
      s.onload = resolve;
      s.onerror = function () { pdfLibPromise = null; reject(new Error("The PDF library failed to load. Check your connection and try again.")); };
      document.head.appendChild(s);
    });
    return pdfLibPromise;
  }
  async function viaMain(item, buf) {
    var bytes = new Uint8Array(buf);
    if (MC.kindOf(item.file.name, bytes) === "pdf") await loadPdfLib();
    return MC.clean(item.file.name, bytes, { PDFLib: window.PDFLib, JSZip: window.JSZip }, options(), function (p, label) { item.p = p; item.label = label; paintProgress(item); });
  }
  async function process(item) {
    var buf = await item.file.arrayBuffer();
    var w = getWorker();
    if (w) {
      try {
        return await new Promise(function (resolve, reject) {
          var id = ++seq;
          pending[id] = { item: item, resolve: resolve, reject: reject };
          w.postMessage({ id: id, name: item.file.name, buffer: buf, opts: options() }, [buf]);
        });
      } catch (e) {
        if (!e.workerFailed) throw e;
        buf = await item.file.arrayBuffer(); // the worker could not start; do the work here
      }
    }
    return viaMain(item, buf);
  }

  // ---------- file list ----------
  var items = [];
  var running = false;
  var extraNote = "";
  var dropEl = $("mc-drop"), list = $("mc-list"), statusEl = $("mc-status"), bar = $("mc-bar");

  function addFiles(files, skipNote) {
    var added = 0;
    Array.prototype.forEach.call(files, function (file) {
      var item = { file: file, name: file.relPath || file.webkitRelativePath || file.name, state: "queued", p: 0, label: "", li: el("li", "mc-item") };
      items.push(item);
      list.appendChild(item.li);
      paint(item);
      added++;
    });
    if (!added) return;
    bar.hidden = false;
    net.armed = true;
    extraNote = skipNote || "";
    pump();
  }

  async function pump() {
    if (running) return;
    running = true;
    try {
      for (;;) {
        var next = items.find(function (i) { return i.state === "queued"; });
        if (!next) break;
        var total = items.length;
        var done = items.filter(function (i) { return i.state === "done" || i.state === "error"; }).length;
        statusEl.textContent = "Cleaning " + (done + 1) + " of " + total + "…";
        statusEl.classList.add("is-busy");
        next.state = "working"; next.p = 0.02;
        paint(next);
        await clean(next);
        paint(next);
      }
    } finally {
      running = false;
      net.armed = false;
      statusEl.classList.remove("is-busy");
      var ok = items.filter(function (i) { return i.state === "done"; }).length;
      statusEl.textContent = ok ? "Done. " + ok + " file" + (ok > 1 ? "s" : "") + " cleaned." + (extraNote ? " " + extraNote : "") : extraNote;
      $("mc-all").hidden = ok < 2;
      $("mc-report").hidden = ok < 1;
      showNet(true);
    }
  }

  async function clean(item) {
    var file = item.file;
    try {
      if (file.size === 0) throw new Error("That file is empty.");
      var limit = /\.(mp4|mov|m4v)$/i.test(file.name) ? MAX_VIDEO : MAX;
      if (file.size > limit) throw new Error("That file is over " + (limit / 1048576) + " MB.");
      var res = await process(item);
      item.res = res;
      item.blobUrl = null;
      if (res.check.ok) {
        item.blob = new Blob([res.out], { type: MIME[res.kind] || "application/octet-stream" });
        item.blobUrl = URL.createObjectURL(item.blob);
      }
      item.outName = cleanName(file.name);
      item.state = res.check.ok ? "done" : "error";
      if (!res.check.ok) item.error = "The cleaned file failed its safety check (" + res.check.note + "). It was not offered for download, and your original is untouched.";
      if (window.plTrack) window.plTrack("tool_use", "metadata-cleaner:" + res.kind);
    } catch (e) {
      item.state = "error";
      item.error = e && e.message ? e.message : "Could not clean this file.";
    }
  }

  function paintProgress(item) {
    if (!item.li) return;
    var bar_ = item.li.querySelector(".mc-prog");
    if (bar_) bar_.style.setProperty("--p", Math.round(item.p * 100) + "%");
    var lab = item.li.querySelector(".mc-prog-label");
    if (lab) lab.textContent = item.label || "Working…";
  }

  function paint(item) {
    var li = item.li;
    li.textContent = "";
    li.dataset.state = item.state;
    li.classList.remove("mc-reveal");
    var head = el("div", "mc-item-head");
    var nm = el("span", "mc-name", item.name);
    head.appendChild(nm);
    if (item.state === "done") head.appendChild(el("span", "mc-size", fmtSize(item.res.inSize) + " → " + fmtSize(item.res.outSize)));
    else head.appendChild(el("span", "mc-size", fmtSize(item.file.size)));
    li.appendChild(head);

    if (item.state === "queued") { li.appendChild(el("p", "mc-note", "Waiting")); return; }
    if (item.state === "working") {
      li.appendChild(el("p", "mc-prog-label", item.label || "Working…"));
      var pr = el("div", "mc-prog");
      pr.setAttribute("role", "progressbar"); pr.setAttribute("aria-label", "Cleaning " + item.name);
      pr.appendChild(el("span", "mc-prog-fill"));
      li.appendChild(pr);
      paintProgress(item);
      return;
    }
    var actions = el("div", "mc-actions");
    function btn(label, cls, fn) { var b = el("button", "btn " + cls + " mc-small", label); b.type = "button"; b.addEventListener("click", fn); actions.appendChild(b); return b; }
    if (item.state === "error") {
      var err = el("p", "mc-error", item.error); err.setAttribute("role", "alert"); li.appendChild(err);
      btn("Try again", "btn-ghost", function () { redo(item); });
      btn("Remove", "btn-ghost", function () { removeItem(item); });
      li.appendChild(actions);
      return;
    }
    var res = item.res, n = res.found.length;
    li.classList.add("mc-reveal");

    // size bar
    var pct = Math.max(3, Math.min(100, Math.round(100 * res.outSize / Math.max(1, res.inSize))));
    var sb = el("div", "mc-sizebar");
    sb.setAttribute("role", "img"); sb.setAttribute("aria-label", "Output is " + pct + " percent of the original size");
    var fill = el("span", "mc-sizebar-fill");
    fill.style.setProperty("--w", pct + "%");
    sb.appendChild(fill);
    li.appendChild(sb);

    var loc = res.found.filter(function (f) { return f.group === "Location"; });
    if (loc.length) li.appendChild(el("p", "mc-gps", "This file recorded where it was made: " + loc.map(function (f) { return f.value; }).join("; ") + "."));

    var sum = el("p", "mc-summary");
    sum.appendChild(checkIcon());
    sum.appendChild(document.createTextNode(n ? "Removed " + n + " item" + (n > 1 ? "s" : "") + "." : "No metadata found. The copy below has the same content."));
    li.appendChild(sum);

    if (n) {
      var ul = el("ul", "mc-fields");
      var restUl = null;
      res.found.forEach(function (f, i) {
        var row = el("li", "mc-row");
        row.style.setProperty("--i", String(Math.min(i, 14)));
        row.appendChild(el("span", "mc-row-g", f.group));
        row.appendChild(el("span", "mc-row-k", f.field));
        row.appendChild(el("span", "mc-row-v", f.value || "present"));
        if (i < 10) ul.appendChild(row);
        else { if (!restUl) restUl = el("ul", "mc-fields mc-fields-rest"); restUl.appendChild(row); }
      });
      li.appendChild(ul);
      if (restUl) {
        var more = el("details", "mc-more");
        more.appendChild(el("summary", null, "Show " + (n - 10) + " more"));
        more.appendChild(restUl);
        li.appendChild(more);
      }
    }
    if (res.left && res.left.length) li.appendChild(el("p", "mc-kept", "Left in place: " + res.left.map(function (f) { return f.field + " (" + f.value + ")"; }).join("; ") + "."));
    if (res.after.length) {
      var warn = el("p", "mc-warn", "Still found after cleaning: " + res.after.map(function (f) { return f.field; }).join(", ") + ".");
      warn.setAttribute("role", "alert");
      li.appendChild(warn);
    } else li.appendChild(el("p", "mc-verified", "Read again after cleaning: nothing found. " + (res.check.note || "")));
    res.kept.forEach(function (k) { li.appendChild(el("p", "mc-kept", k)); });
    if (res.inHash) {
      var hd = el("details", "mc-hash");
      hd.appendChild(el("summary", null, "Checksums (SHA-256)"));
      hd.appendChild(el("p", null, "Before: " + res.inHash));
      hd.appendChild(el("p", null, "After: " + res.outHash));
      li.appendChild(hd);
    }

    var a = el("a", "btn btn-primary mc-dl", "Download " + item.outName);
    a.href = item.blobUrl; a.download = item.outName;
    actions.appendChild(a);
    if (IMG_OK.test(item.file.name) && res.kind !== "gif") btn("Redact parts of this picture", "btn-ghost", function () { showTab("mc-tab-redact"); loadRedact(item.file); });
    btn("Clean again", "btn-ghost", function () { redo(item); });
    btn("Remove", "btn-ghost", function () { removeItem(item); });
    li.appendChild(actions);
  }

  function checkIcon() {
    var ns = "http://www.w3.org/2000/svg";
    var svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 24 24"); svg.setAttribute("class", "mc-check"); svg.setAttribute("aria-hidden", "true");
    var c = document.createElementNS(ns, "circle"); c.setAttribute("cx", "12"); c.setAttribute("cy", "12"); c.setAttribute("r", "10");
    var p = document.createElementNS(ns, "path"); p.setAttribute("d", "M7 12.5l3.2 3.2L17 9");
    svg.appendChild(c); svg.appendChild(p);
    return svg;
  }

  function revoke(item) { if (item.blobUrl) { URL.revokeObjectURL(item.blobUrl); item.blobUrl = null; } }
  function removeItem(item) {
    revoke(item);
    items = items.filter(function (i) { return i !== item; });
    item.li.remove();
    if (!items.length) { bar.hidden = true; statusEl.textContent = ""; }
    $("mc-all").hidden = items.filter(function (i) { return i.state === "done"; }).length < 2;
    $("mc-report").hidden = !items.some(function (i) { return i.state === "done"; });
  }
  function redo(item) {
    revoke(item);
    item.state = "queued"; item.res = null; item.error = null; item.p = 0;
    paint(item);
    net.armed = true;
    pump();
  }
  $("mc-clear").addEventListener("click", function () {
    items.forEach(revoke);
    items = [];
    list.textContent = "";
    bar.hidden = true;
    statusEl.textContent = "";
    showNet(false);
  });

  $("mc-all").addEventListener("click", async function () {
    var zip = new window.JSZip(), used = {};
    items.filter(function (i) { return i.state === "done"; }).forEach(function (i) {
      var rel = i.name.indexOf("/") > -1 ? i.name.slice(0, i.name.lastIndexOf("/") + 1) : "";
      var name = rel + i.outName.split("/").pop(), k = 1;
      while (used[name]) { var d = name.lastIndexOf("."); name = (d > 0 ? name.slice(0, d) : name) + "-" + (++k) + (d > 0 ? name.slice(d) : ""); }
      used[name] = true;
      zip.file(name, i.res.out);
    });
    download(await zip.generateAsync({ type: "blob" }), "cleaned-files.zip");
  });

  // ---------- report ----------
  $("mc-report").addEventListener("click", function () {
    var lines = [];
    lines.push("Metadata Cleaner report");
    lines.push("Made " + new Date().toISOString() + " by purplelink.llc/tools/metadata-cleaner, run in your browser. No file was uploaded.");
    lines.push("This report lists the values that were removed. Do not send it along with the cleaned files.");
    lines.push("");
    items.filter(function (i) { return i.state === "done"; }).forEach(function (i) {
      var r = i.res;
      lines.push("File: " + i.name);
      lines.push("Type: " + r.kind + "    Size: " + fmtSize(r.inSize) + " to " + fmtSize(r.outSize));
      if (r.inHash) { lines.push("SHA-256 before: " + r.inHash); lines.push("SHA-256 after:  " + r.outHash); }
      lines.push("Removed (" + r.found.length + "):");
      r.found.forEach(function (f) { lines.push("  " + f.group + ": " + f.field + " = " + (f.value || "present")); });
      if (r.left && r.left.length) { lines.push("Left in place:"); r.left.forEach(function (f) { lines.push("  " + f.field + " (" + f.value + ")"); }); }
      lines.push(r.after.length ? "Still found after cleaning: " + r.after.map(function (f) { return f.field; }).join(", ") : "Read again after cleaning: nothing found.");
      if (r.check.note) lines.push("Check: " + r.check.note);
      r.kept.forEach(function (k) { lines.push("Note: " + k); });
      lines.push("");
    });
    download(new Blob([lines.join("\n")], { type: "text/plain" }), "metadata-cleaner-report.txt");
  });

  // ---------- adding files: pick, drop, folder, paste ----------
  $("mc-file").addEventListener("change", function (e) { if (e.target.files.length) addFiles(e.target.files); e.target.value = ""; });
  $("mc-folder").addEventListener("change", function (e) {
    var files = Array.prototype.filter.call(e.target.files, function (f) { return EXT_OK.test(f.name); });
    var skipped = e.target.files.length - files.length;
    addFiles(files, skipped ? "Skipped " + skipped + " file" + (skipped > 1 ? "s" : "") + " that are not a supported type." : "");
    e.target.value = "";
  });
  dropEl.addEventListener("dragover", function (e) { e.preventDefault(); dropEl.classList.add("is-over"); });
  dropEl.addEventListener("dragleave", function (e) { if (!dropEl.contains(e.relatedTarget)) dropEl.classList.remove("is-over"); });
  dropEl.addEventListener("drop", async function (e) {
    e.preventDefault();
    dropEl.classList.remove("is-over");
    var out = [], skipped = 0;
    var entries = [];
    if (e.dataTransfer.items && e.dataTransfer.items.length && e.dataTransfer.items[0].webkitGetAsEntry) {
      for (var k = 0; k < e.dataTransfer.items.length; k++) { var en = e.dataTransfer.items[k].webkitGetAsEntry(); if (en) entries.push(en); }
    }
    if (entries.some(function (en) { return en.isDirectory; })) {
      statusEl.textContent = "Reading the folder…";
      for (var i = 0; i < entries.length; i++) await walk(entries[i], out, "");
      var keep = out.filter(function (f) { return EXT_OK.test(f.name); });
      skipped = out.length - keep.length;
      addFiles(keep, skipped ? "Skipped " + skipped + " file" + (skipped > 1 ? "s" : "") + " that are not a supported type." : "");
    } else if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
  });
  function walk(entry, out, prefix) {
    return new Promise(function (resolve) {
      if (entry.isFile) { entry.file(function (f) { f.relPath = prefix + f.name; out.push(f); resolve(); }, resolve); return; }
      var reader = entry.createReader(), all = [];
      (function readMore() {
        reader.readEntries(async function (batch) {
          if (!batch.length) { for (var j = 0; j < all.length; j++) await walk(all[j], out, prefix + entry.name + "/"); resolve(); return; }
          all = all.concat(Array.prototype.slice.call(batch));
          readMore();
        }, resolve);
      })();
    });
  }
  document.addEventListener("paste", function (e) {
    var t = e.target;
    if (t && (t.tagName === "TEXTAREA" || (t.tagName === "INPUT" && t.type === "text"))) return;
    var files = e.clipboardData && e.clipboardData.files;
    if (!files || !files.length) return;
    var tab = activeTab();
    if (tab === "mc-tab-text") return;
    e.preventDefault();
    if (tab === "mc-tab-redact") loadRedact(files[0]); else addFiles(files);
  });

  // ---------- sample photo ----------
  function ascii0(s) { var o = []; for (var i = 0; i < s.length; i++) o.push(s.charCodeAt(i)); o.push(0); return o; }
  function u16(n) { return [n & 255, (n >> 8) & 255]; }
  function u32(n) { return [n & 255, (n >> 8) & 255, (n >> 16) & 255, (n >>> 24) & 255]; }
  function rational(n, d) { return u32(n).concat(u32(d)); }
  // Little-endian TIFF with the given IFD entries; returns bytes and a way to patch pointers.
  function buildIfd(entries, base) {
    // entries: {tag, type, count, data:[bytes]}; data longer than 4 bytes goes after the table.
    entries.sort(function (a, b) { return a.tag - b.tag; });
    var tableLen = 2 + entries.length * 12 + 4, extra = [], out = u16(entries.length);
    entries.forEach(function (e) {
      out = out.concat(u16(e.tag), u16(e.type), u32(e.type === 2 ? e.data.length : e.count));
      if (e.data.length <= 4) { out = out.concat(e.data); for (var i = e.data.length; i < 4; i++) out.push(0); }
      else { out = out.concat(u32(base + tableLen + extra.length)); extra = extra.concat(e.data); if (extra.length % 2) extra.push(0); }
    });
    out = out.concat(u32(0), extra);
    return out;
  }
  function sampleExif() {
    // Lay out: header(8) + IFD0, then Exif IFD, then GPS IFD. Offsets depend on IFD0 length, so build twice.
    function ifd0(exifOff, gpsOff) {
      return buildIfd([
        { tag: 0x010f, type: 2, count: 11, data: ascii0("SampleCam") }, { tag: 0x0110, type: 2, count: 7, data: ascii0("SC-100") },
        { tag: 0x0131, type: 2, count: 16, data: ascii0("PhotoEditor 4.2") }, { tag: 0x0132, type: 2, count: 20, data: ascii0("2026:09:14 08:12:30") },
        { tag: 0x013b, type: 2, count: 12, data: ascii0("Alex Sample") }, { tag: 0x8298, type: 2, count: 12, data: ascii0("Alex Sample") },
        { tag: 0x8769, type: 4, count: 1, data: u32(exifOff) }, { tag: 0x8825, type: 4, count: 1, data: u32(gpsOff) }
      ], 8);
    }
    var probe = ifd0(0, 0).length;
    var exifOff = 8 + probe;
    var exifBytes = buildIfd([
      { tag: 0x9003, type: 2, count: 20, data: ascii0("2026:09:14 08:12:30") }, { tag: 0xa431, type: 2, count: 10, data: ascii0("SN-204815") },
      { tag: 0xa434, type: 2, count: 11, data: ascii0("50mm f/1.8") }
    ], exifOff);
    var gpsOff = exifOff + exifBytes.length;
    var gpsBytes = buildIfd([
      { tag: 1, type: 2, count: 2, data: ascii0("N") }, { tag: 2, type: 5, count: 3, data: rational(33, 1).concat(rational(44, 1), rational(564, 10)) },
      { tag: 3, type: 2, count: 2, data: ascii0("W") }, { tag: 4, type: 5, count: 3, data: rational(84, 1).concat(rational(23, 1), rational(168, 10)) }
    ], gpsOff);
    var tiff = [0x49, 0x49, 0x2a, 0, 8, 0, 0, 0].concat(ifd0(exifOff, gpsOff), exifBytes, gpsBytes);
    var body = ascii0("Exif").slice(0, 4).concat([0, 0], tiff);
    var len = body.length + 2;
    return new Uint8Array([0xff, 0xe1, len >> 8, len & 255].concat(body));
  }
  $("mc-sample").addEventListener("click", function () {
    var c = document.createElement("canvas");
    c.width = 960; c.height = 640;
    var g = c.getContext("2d");
    var sky = g.createLinearGradient(0, 0, 0, 640);
    sky.addColorStop(0, "#2a1a5e"); sky.addColorStop(0.55, "#c0568b"); sky.addColorStop(1, "#f2b27a");
    g.fillStyle = sky; g.fillRect(0, 0, 960, 640);
    g.fillStyle = "#ffe9b8"; g.beginPath(); g.arc(700, 330, 70, 0, 6.2832); g.fill();
    g.fillStyle = "#3a2570"; g.beginPath(); g.moveTo(0, 640); g.lineTo(0, 470); g.quadraticCurveTo(220, 360, 430, 470); g.quadraticCurveTo(640, 560, 960, 430); g.lineTo(960, 640); g.fill();
    g.fillStyle = "#1c1040"; g.beginPath(); g.moveTo(0, 640); g.lineTo(0, 540); g.quadraticCurveTo(300, 470, 560, 560); g.quadraticCurveTo(780, 620, 960, 520); g.lineTo(960, 640); g.fill();
    c.toBlob(async function (blob) {
      var jb = new Uint8Array(await blob.arrayBuffer());
      var ex = sampleExif();
      var bytes = new Uint8Array(2 + ex.length + jb.length - 2);
      bytes.set(jb.subarray(0, 2), 0); bytes.set(ex, 2); bytes.set(jb.subarray(2), 2 + ex.length);
      var f = new File([bytes], "sample-photo.jpg", { type: "image/jpeg" });
      showTab("mc-tab-files");
      addFiles([f]);
    }, "image/jpeg", 0.9);
  });

  // ---------- redaction ----------
  var rd = { bmp: null, file: null, boxes: [], sel: -1, undo: [], drag: null };
  var cv = $("mc-rd-canvas"), ctx = cv.getContext("2d"), rdDrop = $("mc-rd-drop");
  var rdStatus = $("mc-rd-status");

  rdDrop.addEventListener("dragover", function (e) { e.preventDefault(); rdDrop.classList.add("is-over"); });
  rdDrop.addEventListener("dragleave", function (e) { if (!rdDrop.contains(e.relatedTarget)) rdDrop.classList.remove("is-over"); });
  rdDrop.addEventListener("drop", function (e) { e.preventDefault(); rdDrop.classList.remove("is-over"); if (e.dataTransfer.files.length) loadRedact(e.dataTransfer.files[0]); });
  $("mc-rd-file").addEventListener("change", function (e) { if (e.target.files.length) loadRedact(e.target.files[0]); e.target.value = ""; });

  async function loadRedact(file) {
    if (!/^image\/(jpeg|png|webp|gif)$/.test(file.type) && !IMG_OK.test(file.name)) { rdStatus.textContent = "Use a JPG, PNG, WebP or GIF picture."; return; }
    try {
      var bmp;
      try { bmp = await createImageBitmap(file, { imageOrientation: "from-image" }); } catch (e) { bmp = await createImageBitmap(file); }
      var scale = 1, px = bmp.width * bmp.height;
      if (px > 60e6) {
        scale = Math.sqrt(60e6 / px);
        var small = await createImageBitmap(bmp, { resizeWidth: Math.round(bmp.width * scale), resizeHeight: Math.round(bmp.height * scale), resizeQuality: "high" });
        bmp.close(); bmp = small;
      }
      rd.bmp = bmp; rd.file = file; rd.boxes = []; rd.sel = -1; rd.undo = [];
      cv.width = bmp.width; cv.height = bmp.height;
      $("mc-rd-work").hidden = false;
      rdDrop.hidden = true;
      rdStatus.textContent = scale < 1 ? "Large picture: scaled down to fit. Drag on the picture to cover what should not be seen." : "Drag on the picture to cover what should not be seen.";
      drawRd(true);
    } catch (e) {
      rdStatus.textContent = "That picture could not be opened.";
    }
  }
  function snapshot() { rd.undo.push(JSON.stringify(rd.boxes)); if (rd.undo.length > 50) rd.undo.shift(); }
  function paintBox(g, b) {
    if (b.mode !== "pixel") { g.fillStyle = "#000"; g.fillRect(b.x, b.y, b.w, b.h); return; }
    // Pixelate: average into a few large cells, then draw them back without smoothing, clipped to the box.
    var cell = Math.max(10, Math.ceil(Math.max(b.w, b.h) / 8));
    var cw = Math.max(1, Math.ceil(b.w / cell)), ch = Math.max(1, Math.ceil(b.h / cell));
    var tmp = document.createElement("canvas");
    tmp.width = cw; tmp.height = ch;
    var tg = tmp.getContext("2d");
    tg.imageSmoothingEnabled = true; tg.imageSmoothingQuality = "high";
    tg.drawImage(rd.bmp, b.x, b.y, b.w, b.h, 0, 0, cw, ch);
    g.save();
    g.beginPath(); g.rect(b.x, b.y, b.w, b.h); g.clip();
    g.imageSmoothingEnabled = false;
    g.drawImage(tmp, 0, 0, cw, ch, b.x, b.y, cw * cell, ch * cell);
    g.restore();
  }
  function drawRd(withUi) {
    ctx.clearRect(0, 0, cv.width, cv.height);
    ctx.drawImage(rd.bmp, 0, 0);
    rd.boxes.forEach(function (b) { paintBox(ctx, b); });
    if (withUi) {
      var u = Math.max(2, cv.width / 400);
      rd.boxes.forEach(function (b, i) {
        ctx.lineWidth = u * (i === rd.sel ? 1.6 : 1);
        ctx.strokeStyle = i === rd.sel ? "#c4a1ff" : "#ffffff";
        ctx.setLineDash(i === rd.sel ? [] : [u * 3, u * 3]);
        ctx.strokeRect(b.x, b.y, b.w, b.h);
        if (i === rd.sel) { ctx.fillStyle = "#c4a1ff"; corners(b).forEach(function (c) { ctx.fillRect(c[0] - u * 3, c[1] - u * 3, u * 6, u * 6); }); }
      });
      ctx.setLineDash([]);
      if (rd.drag && rd.drag.kind === "new") { ctx.strokeStyle = "#c4a1ff"; ctx.lineWidth = u * 1.4; ctx.strokeRect(rd.drag.x, rd.drag.y, rd.drag.w, rd.drag.h); }
    }
    $("mc-rd-undo").disabled = !rd.undo.length;
    $("mc-rd-clear").disabled = !rd.boxes.length;
    $("mc-rd-save").disabled = !rd.boxes.length;
  }
  function corners(b) { return [[b.x, b.y], [b.x + b.w, b.y], [b.x, b.y + b.h], [b.x + b.w, b.y + b.h]]; }
  function pt(e) {
    var r = cv.getBoundingClientRect();
    return [Math.max(0, Math.min(cv.width, (e.clientX - r.left) * cv.width / r.width)), Math.max(0, Math.min(cv.height, (e.clientY - r.top) * cv.height / r.height))];
  }
  function hit(x, y) {
    var tol = Math.max(8, cv.width / 60);
    if (rd.sel >= 0) {
      var cs = corners(rd.boxes[rd.sel]);
      for (var k = 0; k < 4; k++) if (Math.abs(cs[k][0] - x) < tol && Math.abs(cs[k][1] - y) < tol) return { kind: "resize", corner: k };
    }
    for (var i = rd.boxes.length - 1; i >= 0; i--) {
      var b = rd.boxes[i];
      if (x >= b.x && x <= b.x + b.w && y >= b.y && y <= b.y + b.h) return { kind: "move", index: i };
    }
    return null;
  }
  cv.addEventListener("pointerdown", function (e) {
    if (!rd.bmp) return;
    try { cv.setPointerCapture(e.pointerId); } catch (err) { /* synthetic or ended pointer */ }
    var p = pt(e), h = hit(p[0], p[1]);
    if (h && h.kind === "resize") { snapshot(); var b = rd.boxes[rd.sel], c = corners(b)[3 - h.corner]; rd.drag = { kind: "resize", ax: c[0], ay: c[1] }; }
    else if (h) { rd.sel = h.index; snapshot(); rd.drag = { kind: "move", dx: p[0] - rd.boxes[h.index].x, dy: p[1] - rd.boxes[h.index].y }; }
    else { rd.sel = -1; rd.drag = { kind: "new", sx: p[0], sy: p[1], x: p[0], y: p[1], w: 0, h: 0 }; }
    drawRd(true);
  });
  cv.addEventListener("pointermove", function (e) {
    if (!rd.drag) return;
    var p = pt(e), d = rd.drag;
    if (d.kind === "new") { d.x = Math.min(d.sx, p[0]); d.y = Math.min(d.sy, p[1]); d.w = Math.abs(p[0] - d.sx); d.h = Math.abs(p[1] - d.sy); }
    else if (d.kind === "move") { var b = rd.boxes[rd.sel]; b.x = Math.max(0, Math.min(cv.width - b.w, p[0] - d.dx)); b.y = Math.max(0, Math.min(cv.height - b.h, p[1] - d.dy)); }
    else if (d.kind === "resize") { var r = rd.boxes[rd.sel]; r.x = Math.min(d.ax, p[0]); r.y = Math.min(d.ay, p[1]); r.w = Math.abs(p[0] - d.ax); r.h = Math.abs(p[1] - d.ay); }
    drawRd(true);
  });
  function endDrag() {
    var d = rd.drag;
    if (!d) return;
    rd.drag = null;
    if (d.kind === "new" && d.w > 6 && d.h > 6) { snapshot(); rd.boxes.push({ x: d.x, y: d.y, w: d.w, h: d.h, mode: $("mc-rd-mode").value }); rd.sel = rd.boxes.length - 1; }
    drawRd(true);
  }
  cv.addEventListener("pointerup", endDrag);
  cv.addEventListener("pointercancel", endDrag);
  cv.addEventListener("keydown", function (e) {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "z") { e.preventDefault(); undoRd(); return; }
    if (rd.sel < 0) return;
    var b = rd.boxes[rd.sel], s = Math.max(2, Math.round(cv.width / 100)) * (e.altKey ? 0.25 : 1);
    if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); snapshot(); rd.boxes.splice(rd.sel, 1); rd.sel = -1; }
    else if (/^Arrow/.test(e.key)) {
      e.preventDefault();
      var dx = e.key === "ArrowLeft" ? -s : e.key === "ArrowRight" ? s : 0, dy = e.key === "ArrowUp" ? -s : e.key === "ArrowDown" ? s : 0;
      if (e.shiftKey) { b.w = Math.max(6, Math.min(cv.width - b.x, b.w + dx)); b.h = Math.max(6, Math.min(cv.height - b.y, b.h + dy)); }
      else { b.x = Math.max(0, Math.min(cv.width - b.w, b.x + dx)); b.y = Math.max(0, Math.min(cv.height - b.h, b.y + dy)); }
    } else if (e.key === "Tab" && rd.boxes.length > 1) { e.preventDefault(); rd.sel = (rd.sel + (e.shiftKey ? -1 : 1) + rd.boxes.length) % rd.boxes.length; }
    else return;
    drawRd(true);
  });
  function undoRd() { if (!rd.undo.length) return; rd.boxes = JSON.parse(rd.undo.pop()); rd.sel = -1; drawRd(true); }
  $("mc-rd-undo").addEventListener("click", undoRd);
  $("mc-rd-clear").addEventListener("click", function () { snapshot(); rd.boxes = []; rd.sel = -1; drawRd(true); });
  $("mc-rd-add").addEventListener("click", function () {
    if (!rd.bmp) return;
    snapshot();
    var w = cv.width * 0.25, h = cv.height * 0.2;
    rd.boxes.push({ x: (cv.width - w) / 2, y: (cv.height - h) / 2, w: w, h: h, mode: $("mc-rd-mode").value });
    rd.sel = rd.boxes.length - 1;
    drawRd(true);
    cv.focus();
    rdStatus.textContent = "Box added. Arrow keys move it, Shift with arrows resizes it, Delete removes it.";
  });
  $("mc-rd-new").addEventListener("click", function () {
    if (rd.bmp) rd.bmp.close();
    rd.bmp = null; rd.boxes = []; rd.undo = []; rd.sel = -1;
    $("mc-rd-work").hidden = true; rdDrop.hidden = false; rdStatus.textContent = "";
  });
  $("mc-rd-save").addEventListener("click", function () {
    drawRd(false); // nothing but the picture and the covers
    var png = $("mc-rd-format").value === "png";
    cv.toBlob(function (blob) {
      drawRd(true);
      if (!blob) { rdStatus.textContent = "The picture could not be saved."; return; }
      download(blob, baseName(rd.file.name) + "-redacted" + (png ? ".png" : ".jpg"));
      rdStatus.textContent = "Saved. The covers are part of the pixels now, and the file carries no metadata.";
      if (window.plTrack) window.plTrack("tool_use", "metadata-cleaner:redact");
    }, png ? "image/png" : "image/jpeg", 0.93);
  });

  // ---------- text ----------
  var tin = $("mc-in"), tout = $("mc-out"), tstatus = $("mc-t-status"), counts = $("mc-counts"), copy = $("mc-copy");
  function runText() {
    var res = MC.cleanText(tin.value, { spaces: $("mc-t-spaces").checked, typography: $("mc-t-typo").checked, trim: $("mc-t-trim").checked });
    tout.value = res.text;
    counts.textContent = "";
    Object.keys(res.counts).forEach(function (k) { counts.appendChild(el("li", null, k + ": " + res.counts[k])); });
    copy.disabled = !tin.value;
    tstatus.textContent = !tin.value ? "" : res.total ? "Removed or replaced " + res.total + " character" + (res.total > 1 ? "s" : "") + "." : "No hidden characters found.";
  }
  ["input", "change"].forEach(function (ev) { $("mc-panel-text").addEventListener(ev, runText); });
  copy.addEventListener("click", function () {
    var done = function () { tstatus.textContent = "Copied."; };
    function fallback() { tout.select(); try { document.execCommand("copy"); done(); } catch (e) { tstatus.textContent = "Select the text and copy it."; } }
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(tout.value).then(done, fallback);
    else fallback();
  });

  showNet(false);
})();
