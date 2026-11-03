/* File converters, page side: drop zone, queue, worker, network meter, zip. Shared by every /tools/<pair>/ page.
   The page's .cv-app[data-convert] names the pair; convert-core.js has the table. Files never leave the tab.
   Options are the controls marked data-opt="<key>" (radios share a key); data-show-when="key=a,b" shows a control
   only while that option has one of those values, and data-nostore keeps a control out of the remembered options.
   PDF pages and SVGs are drawn here on the page (pdf.js and <img> cannot run in the worker); the rest go to the worker. */
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
  var controls = Array.prototype.slice.call(app.querySelectorAll("[data-opt]"));
  var qualityOut = $("cv-quality-out");
  function raw() {
    var o = {};
    controls.forEach(function (n) {
      var k = n.getAttribute("data-opt");
      if (n.type === "radio") { if (n.checked) o[k] = n.value; }
      else if (n.type === "checkbox") o[k] = n.checked;
      else o[k] = n.value;
    });
    return o;
  }
  (function restore() {
    var s = {};
    try { s = JSON.parse(localStorage.getItem(KEY) || "{}") || {}; } catch (e) { s = {}; }
    controls.forEach(function (n) {
      var v = s[n.getAttribute("data-opt")];
      if (v === undefined || n.hasAttribute("data-nostore") || n.type === "hidden") return;
      if (n.type === "radio") { if (n.value === v) n.checked = true; }
      else if (n.type === "checkbox") { if (typeof v === "boolean") n.checked = v; }
      else if (n.tagName === "SELECT") { if (Array.prototype.some.call(n.options, function (o) { return o.value === v; })) n.value = v; }
      else if (typeof v === "string" && v) n.value = v;
    });
    // A radio marked data-default-locale="en-US,en-CA" is the default for those browser languages (US Letter paper).
    var lang = navigator.language || "";
    controls.forEach(function (n) {
      var loc = n.getAttribute("data-default-locale");
      if (loc && s[n.getAttribute("data-opt")] === undefined && loc.split(",").indexOf(lang) !== -1) n.checked = true;
    });
  })();
  function options() {
    var o = raw();
    o.mobile = MOBILE;
    return C.options(PAIR, o);
  }
  function syncOptions() {
    var r = raw();
    var q = $("cv-quality");
    if (qualityOut && q) qualityOut.textContent = q.value;
    Array.prototype.forEach.call(app.querySelectorAll("[data-show-when]"), function (n) {
      var w = n.getAttribute("data-show-when").split("=");
      n.hidden = w[1].split(",").indexOf(String(r[w[0]])) === -1;
    });
    controls.forEach(function (n) { if (n.hasAttribute("data-nostore")) delete r[n.getAttribute("data-opt")]; });
    try { localStorage.setItem(KEY, JSON.stringify(r)); } catch (e) { /* private mode */ }
  }
  controls.forEach(function (n) { n.addEventListener("change", syncOptions); n.addEventListener("input", syncOptions); });
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
  var CAN = typeof Worker !== "undefined" &&
    (!CONV.canvas || (typeof OffscreenCanvas !== "undefined" && typeof createImageBitmap !== "undefined"));
  // Stamped URLs of the libraries the worker may load, read from this page's own tags.
  var LIBS = {};
  (function () {
    var z = document.querySelector('script[src*="/assets/vendor/jszip/"]');
    if (z) LIBS.zip = new URL(z.src).pathname + new URL(z.src).search;
    Array.prototype.forEach.call(document.querySelectorAll("link[data-convert-lib]"), function (l) {
      var u = new URL(l.href);
      LIBS[l.getAttribute("data-convert-lib")] = u.pathname + u.search;
    });
  })();
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
      getWorker().postMessage({ id: id, pair: PAIR, name: item.file.name, buffer: buf, opts: options(), libs: LIBS }, [buf]);
    });
  }
  function combine(buffers, item) {
    return new Promise(function (resolve, reject) {
      var id = ++seq;
      pending[id] = { item: item, resolve: resolve, reject: reject };
      getWorker().postMessage({ id: id, op: "combine", pair: PAIR, buffers: buffers, libs: LIBS }, buffers);
    });
  }

  // ---------- drawn on the page: PDF pages (pdf.js) and SVG (<img>) ----------
  function setProgress(item, p, label) { item.p = p; item.label = label; paintProgress(item); }

  // canvas.toBlob runs the encoder off the main thread in Chrome and Firefox. Same check as the worker's encode().
  function canvasBlob(c, opts) {
    var type = C.MIME[opts.output];
    return new Promise(function (resolve, reject) {
      try {
        c.toBlob(function (b) {
          if (!b || b.size === 0 || b.type !== type) reject(new Error("This browser could not write a " + opts.output.toUpperCase() + " of that size."));
          else resolve(b);
        }, type, opts.output === "jpg" ? opts.quality : undefined);
      } catch (e) {
        reject(e && e.name === "SecurityError"
          ? new Error("This browser will not export this SVG because it contains HTML (a foreignObject). Try Chrome or Firefox.")
          : e);
      }
    });
  }

  var pdfjsLoad = null, pdfWorker = null;
  function loadPdfjs() {
    var u = LIBS.pdfjs, w = LIBS["pdfjs-worker"];
    if (!u || !w || u.indexOf("/assets/vendor/") !== 0 || w.indexOf("/assets/vendor/") !== 0) return Promise.reject(new Error("The page did not name its PDF reader."));
    if (!pdfjsLoad) {
      pdfjsLoad = import(u).then(function (lib) {
        lib.GlobalWorkerOptions.workerSrc = w;
        return lib;
      }).catch(function () {
        pdfjsLoad = null; // let the next file try again
        throw new Error("This browser could not load the PDF reader. Use a current version of Chrome, Edge, Firefox or Safari.");
      });
    }
    return pdfjsLoad;
  }

  function pdfError(e) {
    var name = e && e.name;
    if (name === "PasswordException") return "This PDF is locked with a password. Open it in a PDF reader, save a copy without the password, and add that.";
    if (name === "InvalidPDFException") return "This file could not be read as a PDF. It may be damaged or cut short.";
    return "This PDF could not be opened (the reader said: " + ((e && e.message) || e) + ").";
  }

  async function pdfPages(item, opts) {
    setProgress(item, 0.05, "Loading the PDF reader");
    var lib = await loadPdfjs();
    if (!pdfWorker) pdfWorker = new lib.PDFWorker();
    var base = LIBS.pdfjs.split("?")[0].replace(/[^/]*$/, "");
    var data = new Uint8Array(await item.file.arrayBuffer());
    setProgress(item, 0.08, "Opening the PDF");
    var task = lib.getDocument({
        data: data, worker: pdfWorker, wasmUrl: base + "wasm/", cMapUrl: base + "cmaps/", cMapPacked: true,
        standardFontDataUrl: base + "standard_fonts/", iccUrl: base + "iccs/", useWorkerFetch: false, verbosity: 0
    });
    var doc;
    try { doc = await task.promise; } catch (e) { task.destroy(); throw new Error(pdfError(e)); }
    var c = document.createElement("canvas");
    try {
      var count = doc.numPages;
      var sel = C.parsePages(opts.pages, count);
      if (sel.error) throw new Error(sel.error);
      if (sel.pages.length > C.MAX_PDF_PAGES) throw new Error("This PDF has " + count + " pages. This page draws up to " + C.MAX_PDF_PAGES + " at a time, so enter a range under Pages, such as 1-" + C.MAX_PDF_PAGES + ".");
      var ctx = c.getContext("2d");
      var one = sel.pages.length === 1, folder = C.outName(item.file.name, "x").replace(/\.x$/, "") + "-pages";
      var blobs = [], notes = [], failed = [], total = 0, shrunk = 0, stopped = 0;
      for (var i = 0; i < sel.pages.length; i++) {
        var n = sel.pages[i];
        setProgress(item, 0.1 + 0.88 * (i / sel.pages.length), "Drawing page " + n + " of " + count);
        var page = await doc.getPage(n);
        try {
          var size = page.getViewport({ scale: 1 });
          var r = C.pageRaster(size.width, size.height, opts.dpi, MOBILE);
          if (r.dpi < opts.dpi) shrunk = Math.min(shrunk || r.dpi, r.dpi);
          c.width = r.width; c.height = r.height;
          await page.render({ canvasContext: ctx, canvas: c, viewport: page.getViewport({ scale: r.scale }), background: "#ffffff" }).promise;
          var blob = await canvasBlob(c, opts);
          total += blob.size;
          blobs.push({ name: one ? C.outName(item.file.name, opts.output) : folder + "/" + C.pageName(item.file.name, n, count, opts.output), part: !one, blob: blob });
        } catch (e) {
          failed.push(n);
        } finally {
          page.cleanup();
        }
        if (total > C.MAX_ZIP_BYTES && i < sel.pages.length - 1) { stopped = n; break; }
      }
      if (!blobs.length) throw new Error("No page of this PDF could be drawn" + (failed.length ? " (pages " + failed.join(", ") + ")" : "") + ".");
      if (shrunk) notes.push("Some pages are too large to draw at " + opts.dpi + " dpi here, so they were drawn at " + shrunk + " dpi.");
      if (failed.length) notes.push((failed.length === 1 ? "Page " + failed[0] + " could not be drawn and was left out." : "Pages " + failed.join(", ") + " could not be drawn and were left out."));
      if (stopped) notes.push("Stopped after page " + stopped + ": the pages so far add up to 1 GB, the most this tab can zip. Enter a range under Pages for the rest.");
      var pages = blobs.length;
      return {
        blobs: blobs, notes: notes,
        summary: pages + " page" + (pages === 1 ? "" : "s") + " at " + (shrunk || opts.dpi) + " dpi, " + C.formatBytes(total),
        partsLabel: "Download the " + pages + " pages (.zip)", zipName: folder + ".zip"
      };
    } finally {
      c.width = c.height = 0; // Safari keeps canvas memory until the size is zeroed
      task.destroy(); // frees the document in pdf.js's worker; the worker itself is kept for the next file
    }
  }

  async function pdfText(item, opts) {
    setProgress(item, 0.05, "Loading the PDF reader");
    var lib = await loadPdfjs();
    if (!pdfWorker) pdfWorker = new lib.PDFWorker();
    var base = LIBS.pdfjs.split("?")[0].replace(/[^/]*$/, "");
    var data = new Uint8Array(await item.file.arrayBuffer());
    var task = lib.getDocument({
      data: data, worker: pdfWorker, wasmUrl: base + "wasm/", cMapUrl: base + "cmaps/", cMapPacked: true,
      standardFontDataUrl: base + "standard_fonts/", iccUrl: base + "iccs/", useWorkerFetch: false, verbosity: 0
    });
    var doc;
    try { doc = await task.promise; } catch (e) { task.destroy(); throw new Error(pdfError(e)); }
    try {
      var sel = C.parsePages(opts.pages, doc.numPages);
      if (sel.error) throw new Error(sel.error);
      var texts = [], empty = [];
      for (var i = 0; i < sel.pages.length; i++) {
        setProgress(item, 0.1 + 0.85 * (i / sel.pages.length), "Reading page " + sel.pages[i] + " of " + doc.numPages);
        var page = await doc.getPage(sel.pages[i]);
        try { texts.push(C.pdfPageText((await page.getTextContent()).items, opts.layout)); } finally { page.cleanup(); }
        if (!texts[i].trim()) empty.push(sel.pages[i]);
      }
      var text = texts.join(opts.pagebreaks ? "\n\f" : "\n\n") + "\n";
      if (!text.trim()) throw new Error("This PDF has no text layer, so it is probably a scan. Text from a scan needs OCR, which this page does not do.");
      var words = (text.match(/\S+/g) || []).length;
      var notes = empty.length ? [(empty.length === 1 ? "Page " + empty[0] + " has" : "Pages " + empty.join(", ") + " have") + " no text layer (scanned, most likely) and came out empty."] : [];
      return { blobs: [{ name: C.outName(item.file.name, "txt"), part: false, blob: new Blob([text], { type: "text/plain" }) }], notes: notes,
        summary: sel.pages.length + " page" + (sel.pages.length === 1 ? "" : "s") + ", " + words.toLocaleString("en-US") + " words" };
    } finally { task.destroy(); }
  }

  async function svgText(file) {
    var head = new Uint8Array(await file.slice(0, 2).arrayBuffer());
    var bytes;
    if (head[0] === 0x1f && head[1] === 0x8b) {
      if (typeof DecompressionStream === "undefined") throw new Error("This browser cannot unpack .svgz files. Save the drawing as .svg.");
      var reader = file.stream().pipeThrough(new DecompressionStream("gzip")).getReader(), parts = [], n = 0;
      for (;;) {
        var r = await reader.read();
        if (r.done) break;
        n += r.value.length;
        if (n > CONV.maxBytes) { reader.cancel(); throw new Error("Unpacked, this SVGZ is over " + (CONV.maxBytes / 1048576) + " MB, more than this page draws."); }
        parts.push(r.value);
      }
      bytes = new Uint8Array(await new Blob(parts).arrayBuffer());
    } else bytes = new Uint8Array(await file.arrayBuffer());
    return C.svgDecode(bytes);
  }

  function dataUrl(text) {
    return new Promise(function (resolve, reject) {
      var fr = new FileReader();
      fr.onload = function () { resolve(fr.result); };
      fr.onerror = function () { reject(new Error("The SVG could not be read.")); };
      fr.readAsDataURL(new Blob([text], { type: "image/svg+xml" }));
    });
  }

  async function svgDraw(item, opts) {
    setProgress(item, 0.1, "Reading the SVG");
    var text = await svgText(item.file);
    var size = C.svgSize(text);
    if (!size) throw new Error("No <svg> element was found in this file.");
    var out = C.svgOutSize(size.width, size.height, opts.scale, opts.width);
    var big = C.tooManyPixels(out.width, out.height, MOBILE, C.MAX_PIXELS_PAGE);
    if (big) throw new Error(big.replace("This picture", "At this size the picture"));
    setProgress(item, 0.3, "Drawing " + out.width + " by " + out.height + " pixels");
    var notes = C.svgNotes(text);
    if (size.from === "default") notes.unshift("This SVG gives no size or viewBox, so it was drawn at 300 by 150 pixels, the browser default, times the size you chose.");
    var img = new Image();
    img.src = await dataUrl(C.svgWithSize(text, out.width, out.height));
    text = null;
    try { await img.decode(); } catch (e) { throw new Error("This browser could not draw this SVG. The file may not be valid XML."); }
    var c = document.createElement("canvas");
    try {
      c.width = out.width; c.height = out.height;
      var ctx = c.getContext("2d");
      if (opts.output === "jpg") { ctx.fillStyle = opts.background; ctx.fillRect(0, 0, out.width, out.height); }
      ctx.drawImage(img, 0, 0, out.width, out.height);
      setProgress(item, 0.7, "Writing " + opts.output.toUpperCase());
      var blob = await canvasBlob(c, opts);
      return { blobs: [{ name: C.outName(item.file.name, opts.output), part: false, blob: blob }], notes: notes, width: out.width, height: out.height };
    } finally {
      c.width = c.height = 0;
      img.src = "";
    }
  }

  // ---------- queue ----------
  var items = [], running = false;
  var drop = $("cv-drop"), input = $("cv-file"), list = $("cv-list"), statusEl = $("cv-status"), bar = $("cv-bar");

  if (!CAN) {
    statusEl.textContent = CONV.canvas
      ? "This browser cannot convert pictures here. It needs background workers and off-screen drawing, which Chrome and Edge 69, Firefox 105 and Safari 16.4 and later have."
      : "This browser cannot convert files here. It needs background workers, which every current browser has.";
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
      var item = { file: file, name: file.name || "pasted file", state: "queued", p: 0, label: "", li: el("li", "cv-item") };
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
      syncBar();
      showNet();
      // Counted after the meter is off: one anonymous event per batch, pair and output format only.
      if (converted && window.plTrack) window.plTrack("tool_use", PAIR + ":" + options().output);
    }
  }

  async function convert(item) {
    try {
      var head = new Uint8Array(await item.file.slice(0, 4096).arrayBuffer());
      var why = C.refuse(PAIR, C.kindOf(head, item.file.name), item.file.size);
      if (why) throw new Error(why);
      var res;
      if (CONV.work === "pdfpages" || CONV.work === "svg" || CONV.work === "pdftext") {
        res = CONV.work === "pdfpages" ? await pdfPages(item, options()) : CONV.work === "pdftext" ? await pdfText(item, options()) : await svgDraw(item, options());
        item.blobs = res.blobs;
        res.blobs = null;
      } else {
        res = await run(item, await item.file.arrayBuffer());
        item.blobs = res.outputs.map(function (o) { return { name: o.name, part: !!o.part, blob: new Blob([o.bytes], { type: o.mime }) }; });
        res.outputs = null; // the blobs hold the bytes now
      }
      item.res = res;
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
    if (item.res.summary) li.appendChild(el("p", "cv-note", item.res.summary));
    else if (item.res.width) li.appendChild(el("p", "cv-note", item.res.width + " by " + item.res.height + " pixels"));
    (item.res.notes || []).forEach(function (n) { li.appendChild(el("p", "cv-warn", n)); });
    mains.forEach(function (b) {
      var a = el("a", "btn btn-primary cv-small", "Download " + b.name);
      a.href = url(item, b.blob); a.download = b.name;
      actions.appendChild(a);
    });
    var parts = item.blobs.filter(function (b) { return b.part; });
    if (parts.length) {
      var z = el("button", "btn btn-ghost cv-small", item.res.partsLabel || "Download the .iconset folder (.zip)"); z.type = "button";
      if (!mains.length) z.className = "btn btn-primary cv-small";
      z.addEventListener("click", function () { saveZip(parts, item.res.zipName || parts[0].name.split("/")[0] + ".zip", z); });
      actions.appendChild(z);
    }
    if (item.res.copyText) {
      var cp = el("button", "btn btn-ghost cv-small", "Copy"); cp.type = "button";
      cp.addEventListener("click", function () {
        var done = function (ok) { cp.textContent = ok ? "Copied" : "Copy failed: download the file instead"; setTimeout(function () { cp.textContent = "Copy"; }, 2500); };
        if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(item.res.copyText).then(function () { done(true); }, function () { done(false); });
        else done(false);
      });
      actions.appendChild(cp);
    }
    if (CONV.combine) moveButtons(item, actions);
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
    syncBar();
  }

  function syncBar() {
    var ok = items.filter(function (i) { return i.state === "done"; }).length;
    $("cv-all").hidden = ok < 2;
    // The Mac Suite line appears once a file has converted, and stays until the page is reloaded.
    if (ok && $("cv-suite")) $("cv-suite").hidden = false;
    if ($("cv-one")) $("cv-one").hidden = ok < 2 || running;
  }

  // Combined PDF: rows can be moved, and the pages follow the order of the finished rows in the list.
  function moveButtons(item, actions) {
    var at = items.indexOf(item);
    [["Move up", -1], ["Move down", 1]].forEach(function (d) {
      var b = el("button", "btn btn-ghost cv-small", d[0]); b.type = "button";
      b.disabled = d[1] < 0 ? at === 0 : at === items.length - 1;
      b.setAttribute("aria-label", d[0] + ": " + item.name);
      b.addEventListener("click", function () { move(item, d[1], d[0]); });
      actions.appendChild(b);
    });
  }
  function move(item, by, label) {
    var at = items.indexOf(item), to = at + by;
    if (to < 0 || to >= items.length) return;
    items.splice(at, 1); items.splice(to, 0, item);
    items.forEach(function (i) { list.appendChild(i.li); });
    items.forEach(function (i) { if (i.state === "done") paint(i); });
    var again = Array.prototype.filter.call(item.li.querySelectorAll("button"), function (b) { return b.textContent === label && !b.disabled; })[0];
    (again || item.li.querySelector("a, button")).focus();
    statusEl.textContent = item.name + " is now number " + (to + 1) + " of " + items.length + ".";
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
  if ($("cv-one")) $("cv-one").addEventListener("click", async function () {
    var button = $("cv-one");
    var done = items.filter(function (i) { return i.state === "done"; });
    var blobs = done.map(function (i) { return i.blobs.filter(function (b) { return !b.part; })[0].blob; });
    var total = blobs.reduce(function (s, b) { return s + b.size; }, 0);
    if (total > C.MAX_ZIP_BYTES) { statusEl.textContent = "Together the pages are over 1 GB, too large to join in a browser tab. Download them one by one."; return; }
    var label = button.textContent;
    button.disabled = true; button.textContent = "Joining " + done.length + " pages…";
    net.armed = true;
    try {
      var buffers = await Promise.all(blobs.map(function (b) { return b.arrayBuffer(); }));
      var res = await combine(buffers, { li: null });
      var o = res.outputs[0];
      var blob = new Blob([o.bytes], { type: o.mime });
      var a = document.createElement("a");
      var u = URL.createObjectURL(blob);
      a.href = u; a.download = o.name;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(u); }, 30000);
      statusEl.textContent = "Saved one PDF of " + done.length + " pages, " + C.formatBytes(blob.size) + ".";
    } catch (e) {
      statusEl.textContent = (e && e.message) || "The pages could not be joined. Download them one by one.";
    } finally {
      net.armed = false;
      showNet();
      button.disabled = false; button.textContent = label;
    }
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
