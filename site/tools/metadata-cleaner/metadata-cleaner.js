/* Metadata Cleaner page. Reads files with the browser, cleans them with
   MetaClean (metadata-cleaner-core.js) and offers downloads. No network calls.
   Metadata values come from untrusted files, so they are only ever written with
   textContent. */
(function () {
  "use strict";
  var MC = window.MetaClean;
  var MAX = 200 * 1024 * 1024;
  var $ = function (id) { return document.getElementById(id); };

  var items = [];
  var running = false;
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

  function fmtSize(n) {
    if (n < 1024) return n + " B";
    if (n < 1048576) return (n / 1024).toFixed(n < 10240 ? 1 : 0) + " KB";
    return (n / 1048576).toFixed(n < 10485760 ? 1 : 0) + " MB";
  }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function cleanName(name) {
    var i = name.lastIndexOf(".");
    return i > 0 ? name.slice(0, i) + "-clean" + name.slice(i) : name + "-clean";
  }
  var MIME = {
    jpeg: "image/jpeg", png: "image/png", webp: "image/webp", pdf: "application/pdf",
    docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation"
  };

  // ---------- tabs ----------
  var tabs = [["mc-tab-files", "mc-panel-files"], ["mc-tab-text", "mc-panel-text"]];
  tabs.forEach(function (t) {
    $(t[0]).addEventListener("click", function () {
      tabs.forEach(function (o) {
        var on = o[0] === t[0];
        $(o[0]).setAttribute("aria-selected", String(on));
        $(o[1]).hidden = !on;
      });
    });
  });

  // ---------- files ----------
  var drop = $("mc-drop"), input = $("mc-file"), list = $("mc-list"), statusEl = $("mc-status"), bar = $("mc-bar");

  drop.addEventListener("dragover", function (e) { e.preventDefault(); drop.classList.add("is-over"); });
  drop.addEventListener("dragleave", function (e) { if (!drop.contains(e.relatedTarget)) drop.classList.remove("is-over"); });
  drop.addEventListener("drop", function (e) {
    e.preventDefault();
    drop.classList.remove("is-over");
    if (e.dataTransfer && e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
  });
  input.addEventListener("change", function () { if (input.files.length) addFiles(input.files); input.value = ""; });

  function addFiles(fileList) {
    Array.prototype.forEach.call(fileList, function (file) {
      var item = { file: file, state: "queued", li: el("li", "mc-item") };
      items.push(item);
      list.appendChild(item.li);
      paint(item);
    });
    bar.hidden = false;
    pump();
  }

  function options() {
    return { keepOrientation: $("mc-opt-rotate").checked, anonymize: $("mc-opt-anon").checked };
  }

  async function pump() {
    if (running) return;
    running = true;
    try {
      for (;;) {
        var next = items.find(function (i) { return i.state === "queued"; });
        if (!next) break;
        var total = items.length, done = items.filter(function (i) { return i.state === "done" || i.state === "error"; }).length;
        statusEl.textContent = "Cleaning " + (done + 1) + " of " + total + "…";
        statusEl.classList.add("is-busy");
        next.state = "working";
        paint(next);
        await clean(next);
        paint(next);
      }
    } finally {
      running = false;
      statusEl.classList.remove("is-busy");
      var ok = items.filter(function (i) { return i.state === "done"; }).length;
      statusEl.textContent = ok ? "Done. " + ok + " file" + (ok > 1 ? "s" : "") + " cleaned. Nothing left your device." : "";
      $("mc-all").hidden = ok < 2;
    }
  }

  async function clean(item) {
    var file = item.file;
    try {
      if (file.size === 0) throw new Error("That file is empty.");
      if (file.size > MAX) throw new Error("That file is over 200 MB.");
      var bytes = new Uint8Array(await file.arrayBuffer());
      var kind = MC.kindOf(file.name, bytes);
      if (kind === "pdf") await loadPdfLib();
      var libs = { PDFLib: window.PDFLib, JSZip: window.JSZip };
      var res = await MC.run(file.name, bytes, libs, options());
      var after = await MC.verify(res.kind, res.out, libs);
      item.result = res;
      item.after = after;
      item.blobUrl = URL.createObjectURL(new Blob([res.out], { type: MIME[res.kind] || "application/octet-stream" }));
      item.outName = cleanName(file.name);
      item.state = "done";
      if (window.plTrack) window.plTrack("tool_use", "metadata-cleaner:" + res.kind);
    } catch (e) {
      item.state = "error";
      item.error = e && e.message ? e.message : "Could not clean this file.";
    }
  }

  function groupFields(found) {
    var groups = [], map = {};
    found.forEach(function (f) {
      if (!map[f.group]) { map[f.group] = []; groups.push(f.group); }
      map[f.group].push(f);
    });
    return groups.map(function (g) { return { name: g, rows: map[g] }; });
  }

  function paint(item) {
    var li = item.li;
    li.textContent = "";
    li.dataset.state = item.state;
    var head = el("div", "mc-item-head");
    head.appendChild(el("span", "mc-name", item.file.name));
    if (item.state === "done") head.appendChild(el("span", "mc-size", fmtSize(item.file.size) + " → " + fmtSize(item.result.out.length)));
    else head.appendChild(el("span", "mc-size", fmtSize(item.file.size)));
    li.appendChild(head);

    if (item.state === "queued") { li.appendChild(el("p", "mc-note", "Waiting")); return; }
    if (item.state === "working") { li.appendChild(el("p", "mc-note", "Cleaning…")); return; }
    if (item.state === "error") { var err = el("p", "mc-error", item.error); err.setAttribute("role", "alert"); li.appendChild(err); return; }

    var n = item.result.found.length;
    var summary = n
      ? "Removed " + n + " item" + (n > 1 ? "s" : "") + "."
      : "No metadata found. The copy below is the same content.";
    li.appendChild(el("p", "mc-summary", summary));
    if (n) {
      var det = el("details", "mc-found");
      det.appendChild(el("summary", null, "What was in the file"));
      groupFields(item.result.found).forEach(function (g) {
        det.appendChild(el("h3", "mc-group", g.name));
        var dl = el("dl", "mc-rows");
        g.rows.forEach(function (r) {
          dl.appendChild(el("dt", null, r.field));
          dl.appendChild(el("dd", null, r.value || "present"));
        });
        det.appendChild(dl);
      });
      li.appendChild(det);
    }
    if (item.after.length) {
      var warn = el("p", "mc-warn", "Still found after cleaning: " + item.after.map(function (f) { return f.field; }).join(", ") + ".");
      warn.setAttribute("role", "alert");
      li.appendChild(warn);
    } else {
      li.appendChild(el("p", "mc-verified", "Read again after cleaning: nothing found."));
    }
    item.result.kept.forEach(function (k) { li.appendChild(el("p", "mc-kept", k)); });
    var a = el("a", "btn btn-primary mc-dl", "Download " + item.outName);
    a.href = item.blobUrl;
    a.download = item.outName;
    li.appendChild(a);
  }

  $("mc-clear").addEventListener("click", function () {
    items.forEach(function (i) { if (i.blobUrl) URL.revokeObjectURL(i.blobUrl); });
    items = [];
    list.textContent = "";
    bar.hidden = true;
    statusEl.textContent = "";
  });

  $("mc-all").addEventListener("click", async function () {
    var zip = new window.JSZip(), used = {};
    items.filter(function (i) { return i.state === "done"; }).forEach(function (i) {
      var name = i.outName, k = 1;
      while (used[name]) { var d = i.outName.lastIndexOf("."); name = (d > 0 ? i.outName.slice(0, d) : i.outName) + "-" + (++k) + (d > 0 ? i.outName.slice(d) : ""); }
      used[name] = true;
      zip.file(name, i.result.out);
    });
    var blob = await zip.generateAsync({ type: "blob" });
    var url = URL.createObjectURL(blob);
    var a = el("a");
    a.href = url; a.download = "cleaned-files.zip";
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 30000);
  });

  // ---------- text ----------
  var tin = $("mc-in"), tout = $("mc-out"), tstatus = $("mc-t-status"), counts = $("mc-counts"), copy = $("mc-copy");

  function runText() {
    var res = MC.cleanText(tin.value, {
      spaces: $("mc-t-spaces").checked, typography: $("mc-t-typo").checked, trim: $("mc-t-trim").checked
    });
    tout.value = res.text;
    counts.textContent = "";
    Object.keys(res.counts).forEach(function (k) {
      counts.appendChild(el("li", null, k + ": " + res.counts[k]));
    });
    copy.disabled = !tin.value;
    tstatus.textContent = !tin.value ? "" : res.total ? "Removed or replaced " + res.total + " character" + (res.total > 1 ? "s" : "") + "." : "No hidden characters found.";
  }
  ["input", "change"].forEach(function (ev) { $("mc-panel-text").addEventListener(ev, runText); });

  copy.addEventListener("click", function () {
    var done = function () { tstatus.textContent = "Copied."; };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(tout.value).then(done, fallback);
    else fallback();
    function fallback() { tout.select(); try { document.execCommand("copy"); done(); } catch (e) { tstatus.textContent = "Select the text and copy it."; } }
  });
})();
