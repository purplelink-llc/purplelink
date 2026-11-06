/* PDF Redaction Checker: runs in the browser with the self-hosted pdf.js. The file is never sent anywhere. */
(function () {
  "use strict";
  var core = window.PLRedactCore;
  var PDFJS = "/assets/vendor/pdfjs-6.4.299/pdf.min.mjs";
  var WORKER = "/assets/vendor/pdfjs-6.4.299/pdf.worker.min.mjs";
  var MAX_BYTES = 200 * 1024 * 1024;
  var MAX_PAGES = 150;
  var BOX_SUBTYPES = { Square: 1, Ink: 1, Polygon: 1, FreeText: 1, Redact: 1, Highlight: 1 };

  var drop = document.getElementById("rc-drop");
  var input = document.getElementById("rc-file");
  var statusEl = document.getElementById("rc-status");
  var results = document.getElementById("rc-results");
  if (!drop || !input || !results || !core) return;

  var pdfjsPromise = null;
  function loadPdfjs() {
    if (!pdfjsPromise) {
      pdfjsPromise = import(PDFJS).then(function (m) {
        m.GlobalWorkerOptions.workerSrc = WORKER;
        return m;
      });
    }
    return pdfjsPromise;
  }

  function setStatus(msg, busy) {
    statusEl.textContent = msg;
    statusEl.classList.toggle("is-busy", !!busy);
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function plural(n, one, many) { return n + " " + (n === 1 ? one : many); }

  async function pageHasInvisibleText(pdfjs, page) {
    var info = { images: false, invisible: false };
    try {
      var ops = await page.getOperatorList();
      var OPS = pdfjs.OPS;
      var imageOps = [OPS.paintImageXObject, OPS.paintInlineImageXObject, OPS.paintImageMaskXObject, OPS.paintImageXObjectRepeat, OPS.paintJpegXObject].filter(function (v) { return v != null; });
      for (var i = 0; i < ops.fnArray.length; i++) {
        var fn = ops.fnArray[i];
        if (imageOps.indexOf(fn) !== -1) info.images = true;
        else if (fn === OPS.setTextRenderingMode && ops.argsArray[i] && ops.argsArray[i][0] === 3) info.invisible = true;
      }
    } catch (e) { /* operator scan is best effort */ }
    return info;
  }

  /* Fonts are proportional, so a word's position is estimated from the width of the text before it. */
  var measureCtx = document.createElement("canvas").getContext("2d");
  measureCtx.font = "100px sans-serif";
  function measure(str) { return str ? measureCtx.measureText(str).width : 0; }

  async function checkPage(pdfjs, pdf, n) {
    var page = await pdf.getPage(n);
    var base = page.getViewport({ scale: 1 });
    var scale = Math.min(2, 3200 / Math.max(base.width, base.height));
    var vp = page.getViewport({ scale: scale });
    var canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.floor(vp.width));
    canvas.height = Math.max(1, Math.floor(vp.height));
    var ctx = canvas.getContext("2d", { willReadFrequently: true });
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    await page.render({ canvasContext: ctx, canvas: canvas, viewport: vp }).promise;
    var pixels = ctx.getImageData(0, 0, canvas.width, canvas.height).data;

    var tc = await page.getTextContent();
    var words = [];
    var textItems = 0;
    tc.items.forEach(function (it) {
      if (typeof it.str !== "string" || !it.str.trim()) return;
      textItems++;
      var tx = pdfjs.Util.transform(vp.transform, it.transform);
      var size = Math.hypot(tx[2], tx[3]);
      var along = Math.hypot(tx[0], tx[1]) || 1;
      var w = Math.abs(it.width) * vp.scale;
      if (!(size > 0) || !(w > 0)) return;
      var ux = tx[0] / along, uy = tx[1] / along;
      var vx = tx[2] / size, vy = tx[3] / size;
      var whole = measure(it.str) || 1;
      core.splitWords(it.str).forEach(function (wd) {
        var a = (measure(it.str.slice(0, wd.start)) / whole) * w, b = (measure(it.str.slice(0, wd.end)) / whole) * w;
        var pad = (b - a) * 0.08;
        a += pad; b -= pad;
        var pts = [[a, 0.12], [b, 0.12], [a, 0.7], [b, 0.7]].map(function (p) {
          return [tx[4] + ux * p[0] + vx * size * p[1], tx[5] + uy * p[0] + vy * size * p[1]];
        });
        var rect = {
          x0: Math.min(pts[0][0], pts[1][0], pts[2][0], pts[3][0]), x1: Math.max(pts[0][0], pts[1][0], pts[2][0], pts[3][0]),
          y0: Math.min(pts[0][1], pts[1][1], pts[2][1], pts[3][1]), y1: Math.max(pts[0][1], pts[1][1], pts[2][1], pts[3][1])
        };
        var hidden = core.isCovered(core.regionStats(pixels, canvas.width, canvas.height, rect));
        words.push({ text: wd.text, hidden: hidden, y: tx[5], size: size, rect: rect });
      });
    });

    var places = core.groupPlaces(words);
    var hiddenRects = words.filter(function (x) { return x.hidden; }).map(function (x) { return x.rect; });

    var annots = [];
    try {
      var list = await page.getAnnotations();
      list.forEach(function (a) {
        if (!a.rect || !BOX_SUBTYPES[a.subtype]) return;
        var r = vp.convertToViewportRectangle(a.rect);
        annots.push({ subtype: a.subtype, rect: { x0: Math.min(r[0], r[2]), x1: Math.max(r[0], r[2]), y0: Math.min(r[1], r[3]), y1: Math.max(r[1], r[3]) } });
      });
    } catch (e) { /* annotations are optional */ }
    var overAnnot = annots.filter(function (a) {
      return a.subtype !== "Redact" && hiddenRects.some(function (r) { return core.rectsOverlap(a.rect, r); });
    }).length;
    var pendingRedact = annots.filter(function (a) { return a.subtype === "Redact"; }).length;

    var ops = await pageHasInvisibleText(pdfjs, page);
    var kind = core.classifyPage({ images: ops.images, textItems: textItems, invisibleText: ops.invisible });
    canvas.width = 1; canvas.height = 1;
    page.cleanup();
    return { n: n, places: places, kind: kind, overAnnot: overAnnot, pendingRedact: pendingRedact };
  }

  function fieldRow(label, value) {
    var li = el("li");
    li.appendChild(el("strong", null, label + ": "));
    li.appendChild(document.createTextNode(value ? value : "empty"));
    return li;
  }

  function render(name, pages, meta, truncated) {
    results.textContent = "";
    var total = pages.reduce(function (s, p) { return s + p.places.length; }, 0);
    var h = el("h2", null, name);
    results.appendChild(h);

    var verdict = el("div", total ? "rc-card rc-found" : "rc-card rc-clear");
    var vh = el("h3");
    vh.appendChild(el("span", "rc-tag", total ? "Found" : "None found"));
    vh.appendChild(document.createTextNode(total ? plural(total, "place where text is still readable", "places where text is still readable") : "No readable text under dark boxes"));
    verdict.appendChild(vh);
    verdict.appendChild(el("p", null, total
      ? "Text under a dark box can still be selected, copied and searched. Anyone who opens this file can read it."
      : "This does not prove the file is safe. It only means this check found nothing. Check the limits above, and look at the metadata below."));
    if (truncated) verdict.appendChild(el("p", "rc-note", "Only the first " + MAX_PAGES + " pages were checked."));
    results.appendChild(verdict);

    pages.forEach(function (p) {
      if (!p.places.length && p.kind === "text" && !p.overAnnot && !p.pendingRedact) return;
      var card = el("div", "rc-card");
      var ch = el("h3");
      ch.appendChild(el("span", "rc-tag", p.places.length ? "Found" : "Note"));
      ch.appendChild(document.createTextNode("Page " + p.n));
      card.appendChild(ch);
      if (p.places.length) {
        card.appendChild(el("p", null, "Still readable: " + plural(p.places.length, "place", "places")));
        var ul = el("ul", "rc-places");
        p.places.forEach(function (pl) {
          var li = el("li", null, pl.masked);
          li.appendChild(el("span", "rc-words", " (" + plural(pl.words, "word", "words") + ")"));
          ul.appendChild(li);
        });
        card.appendChild(ul);
      }
      if (p.overAnnot) card.appendChild(el("p", "rc-note", plural(p.overAnnot, "drawn shape or markup sits", "drawn shapes or markups sit") + " over this text. Shapes added in Preview or a PDF editor are separate objects and hide nothing."));
      if (p.pendingRedact) card.appendChild(el("p", "rc-note", plural(p.pendingRedact, "area is", "areas are") + " marked for redaction but not yet applied. Apply the redaction and save."));
      if (p.kind === "scan-ocr") card.appendChild(el("p", "rc-note", "This page is a scan with a hidden OCR text layer (text that sits invisibly over the picture)."));
      if (p.kind === "scan-no-text") card.appendChild(el("p", "rc-note", "This page is a scan with no text layer, so there is no text to find. Images under boxes are not checked."));
      if (p.kind === "empty") card.appendChild(el("p", "rc-note", "No text and no image found on this page."));
      results.appendChild(card);
    });

    var scanPages = pages.filter(function (p) { return p.kind === "scan-ocr" || p.kind === "scan-no-text"; });
    var ocr = el("div", "rc-card rc-info");
    var oh = el("h3");
    oh.appendChild(el("span", "rc-tag", "Info"));
    oh.appendChild(document.createTextNode("Scanned pages"));
    ocr.appendChild(oh);
    if (!scanPages.length) {
      ocr.appendChild(el("p", null, "No scanned pages found."));
    } else {
      var withOcr = scanPages.filter(function (p) { return p.kind === "scan-ocr"; }).map(function (p) { return p.n; });
      var noOcr = scanPages.filter(function (p) { return p.kind === "scan-no-text"; }).map(function (p) { return p.n; });
      if (withOcr.length) ocr.appendChild(el("p", null, "OCR text layer present on page " + withOcr.join(", ") + ". The recognised text can be copied."));
      if (noOcr.length) ocr.appendChild(el("p", null, "No text layer on page " + noOcr.join(", ") + ". These pages are pictures only."));
    }
    results.appendChild(ocr);

    var md = el("div", "rc-card rc-info");
    var mh = el("h3");
    mh.appendChild(el("span", "rc-tag", "Info"));
    mh.appendChild(document.createTextNode("Document fields"));
    md.appendChild(mh);
    var mu = el("ul");
    mu.appendChild(fieldRow("Title", meta.title));
    mu.appendChild(fieldRow("Author", meta.author));
    mu.appendChild(fieldRow("Creator", meta.creator));
    md.appendChild(mu);
    md.appendChild(el("p", "rc-note", "Redacting the page does not clear these fields. Remove them if they identify anyone."));
    results.appendChild(md);

    results.hidden = false;
    results.focus();
  }

  async function run(file) {
    results.hidden = true;
    if (!file) return;
    if (file.size > MAX_BYTES) { setStatus("That file is over 200 MB. Choose a smaller PDF.", false); return; }
    setStatus("Reading " + file.name + "...", true);
    try {
      var pdfjs = await loadPdfjs();
      var data = new Uint8Array(await file.arrayBuffer());
      var task = pdfjs.getDocument({ data: data, verbosity: 0 });
      var pdf = await task.promise;
      var md = { title: "", author: "", creator: "" };
      try {
        var m = await pdf.getMetadata();
        var info = m.info || {};
        md.title = info.Title || (m.metadata && m.metadata.get("dc:title")) || "";
        md.author = info.Author || (m.metadata && m.metadata.get("dc:creator")) || "";
        md.creator = info.Creator || "";
      } catch (e) { /* no metadata */ }
      var count = Math.min(pdf.numPages, MAX_PAGES);
      var pages = [];
      for (var n = 1; n <= count; n++) {
        setStatus("Checking page " + n + " of " + count + "...", true);
        pages.push(await checkPage(pdfjs, pdf, n));
      }
      render(file.name, pages, md, pdf.numPages > count);
      setStatus("Done. " + plural(count, "page", "pages") + " checked.", false);
      try { if (window.plTrack) window.plTrack("tool_use", "slug:pdf-redaction-checker"); } catch (e) { /* tracking is optional */ }
      try { pdf.destroy(); } catch (e) { /* ignore */ }
    } catch (err) {
      if (window.console) console.error(err);
      setStatus("This file could not be read. It may be damaged or password protected.", false);
    }
  }

  input.addEventListener("change", function () { run(input.files && input.files[0]); });
  ["dragenter", "dragover"].forEach(function (ev) { drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.add("is-over"); }); });
  ["dragleave", "drop"].forEach(function (ev) { drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.remove("is-over"); }); });
  drop.addEventListener("drop", function (e) {
    var f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) run(f);
  });
})();
