/* Transcript Cleaner page. Files are read with the browser and cleaned by TranscriptClean
   (transcript-cleaner-core.js) in a Web Worker. Nothing from a file is sent anywhere. Text from
   a file is untrusted, so it is only ever written with textContent or a textarea value. */
(function () {
  "use strict";
  var TC = window.TranscriptClean;
  var MAX = 50 * 1024 * 1024;
  var PREVIEW_CHARS = 200000;
  var EXT_OK = /\.(vtt|srt|txt|text)$/i;
  var $ = function (id) { return document.getElementById(id); };

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function fmtSize(n) {
    if (n < 1024) return n + " B";
    if (n < 1048576) return (n / 1024).toFixed(n < 10240 ? 1 : 0) + " KB";
    return (n / 1048576).toFixed(n < 10485760 ? 1 : 0) + " MB";
  }
  function plural(n, one, many) { return n.toLocaleString("en-US") + " " + (n === 1 ? one : many); }
  function baseName(name) { var i = name.lastIndexOf("."); return i > 0 ? name.slice(0, i) : name; }
  function download(text, name, type) {
    var url = URL.createObjectURL(new Blob([text], { type: type + ";charset=utf-8" }));
    var a = el("a");
    a.href = url; a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 30000);
  }

  // ---------- saved options ----------
  var KEY = "tc-options";
  var IDS = { speakers: "tc-opt-speakers", timestamps: "tc-opt-times", paragraphs: "tc-opt-para", tags: "tc-opt-tags" };
  var OUTPUTS = { text: 1, qda: 1, "nvivo-tsv": 1 };
  var outputRadios = document.querySelectorAll('input[name="tc-output"]');
  function outputChoice() {
    for (var i = 0; i < outputRadios.length; i++) if (outputRadios[i].checked) return outputRadios[i].value;
    return "text";
  }
  function options() {
    return { speakers: $(IDS.speakers).checked, timestamps: $(IDS.timestamps).checked, paragraphs: $(IDS.paragraphs).checked, tags: $(IDS.tags).checked, output: outputChoice() };
  }
  // The "[00:01:35]" time before each turn belongs to readable text only.
  function syncOutput() { $(IDS.timestamps).disabled = outputChoice() !== "text"; }
  function saveOptions() { try { localStorage.setItem(KEY, JSON.stringify(options())); } catch (e) { /* storage can be blocked; the page works without it */ } }
  (function restore() {
    var s = {};
    try { s = JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { s = {}; }
    Object.keys(IDS).forEach(function (k) { if (typeof s[k] === "boolean") $(IDS[k]).checked = s[k]; });
    if (typeof s.output === "string" && OUTPUTS[s.output]) {
      Array.prototype.forEach.call(outputRadios, function (r) { r.checked = r.value === s.output; });
    }
    syncOutput();
  })();

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
  function showNet() {
    var t = $("tc-net-text");
    t.textContent = net.requests === 0
      ? "Requests made while cleaning: 0. Nothing was sent."
      : "While cleaning, this page made " + plural(net.requests, "request", "requests") + " and sent " + net.bytes + " bytes: the anonymous usage count (file type only, no names or text).";
    $("tc-net").classList.add("is-live");
  }

  // ---------- worker, with the same code on the page as a fallback ----------
  var worker = null, workerBroken = false, seq = 0, pending = {}, inlineDocs = {};
  function getWorker() {
    if (workerBroken || typeof Worker === "undefined") return null;
    if (worker) return worker;
    try {
      var link = document.querySelector("link[data-tc-worker]");
      var core = document.querySelector('script[src*="transcript-cleaner-core"]');
      var u = new URL(link.href);
      u.searchParams.set("c", new URL(core.src).searchParams.get("v") || "");
      worker = new Worker(u.href);
      worker.onmessage = function (e) {
        // The worker answers in the order it was asked, so each reply belongs to the oldest open request for that file.
        var m = e.data, q = pending[m.id], p = q && q.shift();
        if (!p) return;
        if (!q.length) delete pending[m.id];
        if (m.ok) p.resolve(m.res); else p.reject(new Error(m.message));
      };
      worker.onerror = function () {
        workerBroken = true; worker = null;
        Object.keys(pending).forEach(function (id) { var q = pending[id]; delete pending[id]; q.forEach(function (p) { p.reject(Object.assign(new Error("worker"), { workerFailed: true })); }); });
      };
      return worker;
    } catch (e) { workerBroken = true; return null; }
  }
  // Sends text (first time) or just new options (after that). Resolves to {txt, md, stats}.
  function process(item, withText) {
    var msg = { id: item.id, opts: options() };
    if (withText) { msg.text = item.text; msg.name = item.name; }
    var w = getWorker();
    if (w) {
      return new Promise(function (resolve, reject) {
        (pending[item.id] = pending[item.id] || []).push({ resolve: resolve, reject: reject });
        w.postMessage(msg);
      }).catch(function (err) {
        if (!err.workerFailed) throw err;
        item.inline = true;
        return process(item, true);
      });
    }
    item.inline = true;
    return new Promise(function (resolve, reject) {
      setTimeout(function () {
        try {
          if (withText || !inlineDocs[item.id]) inlineDocs[item.id] = TC.parse(item.text, item.name);
          resolve(TC.render(inlineDocs[item.id], msg.opts));
        } catch (err) { reject(err); }
      }, 0);
    });
  }
  function drop(item) {
    if (worker) worker.postMessage({ id: item.id, drop: true });
    delete inlineDocs[item.id];
  }

  // ---------- results ----------
  var items = [], running = false, view = "txt", extraNote = "";
  var list = $("tc-list"), statusEl = $("tc-status"), bar = $("tc-bar");

  var FORMAT = { vtt: "WebVTT file", srt: "SubRip file", text: "Text file" };
  var HOW = { voice: "speaker names read from voice tags", label: "speaker names read from name labels", header: "speaker names read from header lines", none: "no speaker names found" };
  function describe(st) {
    var parts = [FORMAT[st.format] + ", " + HOW[st.source] + "."];
    var counts = [];
    if (st.format !== "text" || st.source === "header") counts.push(plural(st.cues, "cue", "cues"));
    counts.push(st.source === "none" ? plural(st.turns, "paragraph", "paragraphs") : plural(st.turns, "turn", "turns"));
    if (st.speakers.length) {
      var shown = st.speakers.slice(0, 8).map(function (s) { return s.name; });
      var more = st.speakers.length - shown.length;
      counts.push(plural(st.speakers.length, "speaker", "speakers") + ": " + shown.join(", ") + (more > 0 ? " and " + more + " more" : ""));
    }
    parts.push(counts.join(", ") + ".");
    return parts.join(" ");
  }
  function notesFor(item) {
    var st = item.res.stats, o = item.optsUsed, notes = [];
    var timed = o.output === "qda" || o.output === "nvivo-tsv";
    if (o.timestamps && !timed && !st.hasTimes) notes.push({ warn: false, text: "This file has no timestamps, so none were added." });
    if (timed && !st.hasTimes) notes.push({ warn: true, text: "This file has no timestamps, so the output has none. NVivo and MAXQDA need times to link the text to the recording." });
    else if (timed && st.untimedRows) {
      notes.push({ warn: true, text: o.output === "qda"
        ? plural(st.untimedRows, "turn has", "turns have") + " no end time in the file, so no timestamp was written after " + (st.untimedRows === 1 ? "it." : "them.")
        : plural(st.untimedRows, "line comes", "lines come") + " before the first time in the file and " + (st.untimedRows === 1 ? "has" : "have") + " no time. NVivo needs a time on every line." });
    }
    if (st.sameTimeRows) notes.push({ warn: true, text: plural(st.sameTimeRows, "turn ends", "turns end") + " at or before the end of the turn above, usually because people talk over each other. MAXQDA needs times that never go backwards, so " + (st.sameTimeRows === 1 ? "it gets" : "they get") + " the same time as the turn above and play no audio of " + (st.sameTimeRows === 1 ? "its" : "their") + " own. Check " + (st.sameTimeRows === 1 ? "that turn" : "those turns") + " after importing." });
    if (st.startOnlyRows) notes.push({ warn: true, text: plural(st.startOnlyRows, "line has", "lines have") + " a start time but no end time after it. The NVivo help shows a start and an end on every line, so check " + (st.startOnlyRows === 1 ? "that line" : "those lines") + " after importing." });
    if (st.backwardsTimes) notes.push({ warn: true, text: plural(st.backwardsTimes, "time in the file is", "times in the file are") + " earlier than the time above. Check the times in the original file, since the output keeps them in the order they appear." });
    if (st.colonRows) notes.push({ warn: true, text: plural(st.colonRows, "turn has", "turns have") + " a colon followed by a space in the text. NVivo for Mac reads text before a colon and a space as a speaker name, so check " + (st.colonRows === 1 ? "that turn" : "those turns") + " after importing." });
    if (o.tags && st.tagsRemoved) notes.push({ warn: false, text: plural(st.tagsRemoved, "bracketed sound tag", "bracketed sound tags") + " removed." });
    if (st.emptyDropped) notes.push({ warn: false, text: plural(st.emptyDropped, "empty cue", "empty cues") + " skipped." });
    st.warnings.forEach(function (w) { notes.push({ warn: true, text: w }); });
    return notes;
  }

  function paint(item) {
    var li = item.li;
    li.textContent = "";
    li.setAttribute("data-state", item.state);
    var head = el("div", "tc-item-head");
    head.appendChild(el("span", "tc-name", item.name));
    head.appendChild(el("span", "tc-size", fmtSize(item.size)));
    li.appendChild(head);
    if (item.state === "error") { li.appendChild(el("p", "tc-error", item.error)); return; }
    if (item.state !== "done") { li.appendChild(el("p", "tc-note-plain", item.state === "queued" ? "Waiting." : "Cleaning.")); return; }
    li.appendChild(el("p", "tc-summary", describe(item.res.stats)));
    var notes = notesFor(item);
    if (notes.length) {
      var ul = el("ul", "tc-notes");
      notes.forEach(function (n) { ul.appendChild(el("li", n.warn ? "tc-warn" : "tc-note", n.text)); });
      li.appendChild(ul);
    }
    var det = el("details", "tc-preview");
    det.open = true;
    det.appendChild(el("summary", null, "Preview"));
    var ta = el("textarea", "tc-out");
    ta.readOnly = true;
    ta.spellcheck = false;
    ta.rows = 12;
    ta.setAttribute("aria-label", "Cleaned text of " + item.name);
    item.ta = ta;
    det.appendChild(ta);
    var cut = el("p", "tc-note", "");
    cut.hidden = true;
    item.cut = cut;
    det.appendChild(cut);
    li.appendChild(det);
    var act = el("div", "tc-actions");
    var copy = el("button", "btn btn-primary tc-small", "Copy text");
    copy.type = "button";
    copy.addEventListener("click", function () { copyText(item, copy); });
    var dtxt = el("button", "btn btn-ghost tc-small", "Download .txt");
    dtxt.type = "button";
    var suffix = item.optsUsed.output === "qda" ? "-nvivo-maxqda.txt" : item.optsUsed.output === "nvivo-tsv" ? "-nvivo-windows.txt" : "-clean.txt";
    dtxt.addEventListener("click", function () { download(item.res.txt, baseName(item.name) + suffix, "text/plain"); });
    var dmd = el("button", "btn btn-ghost tc-small", "Download .md");
    dmd.type = "button";
    dmd.addEventListener("click", function () { download(item.res.md, baseName(item.name) + "-clean.md", "text/markdown"); });
    act.appendChild(copy); act.appendChild(dtxt);
    if (item.optsUsed.output === "text") act.appendChild(dmd);
    li.appendChild(act);
    paintPreview(item);
  }
  function paintPreview(item) {
    if (!item.ta) return;
    var full = item.res[view];
    item.ta.value = full.length > PREVIEW_CHARS ? full.slice(0, PREVIEW_CHARS) : full;
    item.cut.hidden = full.length <= PREVIEW_CHARS;
    if (full.length > PREVIEW_CHARS) item.cut.textContent = "The preview shows the first " + PREVIEW_CHARS.toLocaleString("en-US") + " characters. Copy and the downloads include everything.";
  }
  function copyText(item, btn) {
    var text = item.res[view];
    function done(ok) {
      var old = btn.textContent;
      btn.textContent = ok ? "Copied" : "Copy failed";
      statusEl.textContent = ok ? "Copied the cleaned text of " + item.name + "." : "The browser blocked copying. Select the text in the preview and copy it.";
      setTimeout(function () { btn.textContent = old; }, 1800);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { done(true); }, function () { done(legacyCopy(item, text)); });
    } else done(legacyCopy(item, text));
  }
  function legacyCopy(item, text) {
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

  function updateBar() {
    bar.hidden = items.length === 0;
    // Markdown is a readable-text format; the NVivo and MAXQDA layouts are plain text only.
    $("tc-view").hidden = outputChoice() !== "text" || !items.some(function (i) { return i.state === "done"; });
  }

  function add(entries, skipNote) {
    var added = 0;
    entries.forEach(function (e) {
      var item = { id: ++seq, name: e.name, size: e.size, text: null, state: "queued", li: el("li", "tc-item tc-reveal"), file: e.file, pasted: e.pasted };
      items.push(item);
      list.appendChild(item.li);
      paint(item);
      added++;
    });
    extraNote = skipNote || "";
    if (!added) { statusEl.textContent = extraNote; return; }
    updateBar();
    net.armed = true;
    pump();
  }

  async function readItem(item) {
    if (item.pasted != null) return item.pasted;
    var buf = await item.file.arrayBuffer();
    return TC.decodeBytes(new Uint8Array(buf));
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
        statusEl.textContent = "Cleaning " + (done + 1) + " of " + total;
        statusEl.classList.add("is-busy");
        next.state = "working";
        paint(next);
        try {
          next.text = await readItem(next);
          next.optsUsed = options();
          next.res = await process(next, true);
          next.state = "done";
          if (window.plTrack) window.plTrack("tool_use", "transcript-cleaner:" + next.res.stats.format);
        } catch (err) {
          next.state = "error";
          next.error = "This file could not be cleaned (" + ((err && err.message) || "unknown error") + "). It was not changed.";
        }
        paint(next);
      }
    } finally {
      running = false;
      net.armed = false;
      statusEl.classList.remove("is-busy");
      var ok = items.filter(function (i) { return i.state === "done"; }).length;
      statusEl.textContent = ok ? "Done. " + plural(ok, "file", "files") + " cleaned." + (extraNote ? " " + extraNote : "") : extraNote;
      if (ok) showNet();
      updateBar();
    }
  }

  // Each option change starts a new pass; a pass that a newer one has replaced stops and keeps none of its late results,
  // so a file's text, notes and download name always come from the same options.
  var renderPass = 0;
  async function rerender() {
    var pass = ++renderPass;
    var done = items.filter(function (i) { return i.state === "done"; });
    if (!done.length) return;
    statusEl.classList.add("is-busy");
    statusEl.textContent = "Updating";
    for (var i = 0; i < done.length; i++) {
      var item = done[i];
      try {
        var opts = options();
        var res = await process(item, false);
        if (pass !== renderPass) return;
        item.optsUsed = opts;
        item.res = res;
      } catch (err) {
        if (pass !== renderPass) return;
        item.state = "error";
        item.error = "This file could not be updated (" + ((err && err.message) || "unknown error") + ").";
      }
      paint(item);
    }
    statusEl.classList.remove("is-busy");
    statusEl.textContent = "Updated.";
  }

  // ---------- input ----------
  function takeFiles(fileList) {
    var entries = [], skipped = [];
    Array.prototype.forEach.call(fileList, function (f) {
      if (!EXT_OK.test(f.name)) { skipped.push(f.name + " (not a .vtt, .srt or .txt file)"); return; }
      if (f.size > MAX) { skipped.push(f.name + " (over " + fmtSize(MAX) + ")"); return; }
      if (f.size === 0) { skipped.push(f.name + " (empty)"); return; }
      entries.push({ name: f.name, size: f.size, file: f });
    });
    add(entries, skipped.length ? "Skipped: " + skipped.join("; ") + "." : "");
  }

  var drop_ = $("tc-drop"), input = $("tc-file");
  $("tc-choose").addEventListener("click", function () { input.click(); });
  input.addEventListener("change", function () { if (input.files && input.files.length) takeFiles(input.files); input.value = ""; });
  ["dragenter", "dragover"].forEach(function (t) {
    drop_.addEventListener(t, function (e) { e.preventDefault(); drop_.classList.add("is-over"); });
  });
  drop_.addEventListener("dragleave", function (e) { if (!drop_.contains(e.relatedTarget)) drop_.classList.remove("is-over"); });
  drop_.addEventListener("drop", function (e) {
    e.preventDefault();
    drop_.classList.remove("is-over");
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) takeFiles(e.dataTransfer.files);
  });

  $("tc-paste-go").addEventListener("click", function () {
    var v = $("tc-paste-in").value;
    if (v.trim() === "") { statusEl.textContent = "Paste some text first."; return; }
    add([{ name: "pasted text", size: new Blob([v]).size, pasted: v }], "");
    $("tc-paste-in").value = "";
  });

  Object.keys(IDS).forEach(function (k) { $(IDS[k]).addEventListener("change", function () { saveOptions(); rerender(); }); });
  Array.prototype.forEach.call(outputRadios, function (r) {
    r.addEventListener("change", function () { syncOutput(); saveOptions(); updateBar(); rerender(); });
  });
  Array.prototype.forEach.call(document.querySelectorAll('input[name="tc-view"]'), function (r) {
    r.addEventListener("change", function () {
      view = r.value;
      items.forEach(function (i) { if (i.state === "done") paintPreview(i); });
    });
  });

  $("tc-clear").addEventListener("click", function () {
    items.forEach(drop);
    items = [];
    list.textContent = "";
    statusEl.textContent = "";
    $("tc-net-text").textContent = "Bytes of your text sent anywhere: 0";
    updateBar();
  });
  updateBar();
})();
