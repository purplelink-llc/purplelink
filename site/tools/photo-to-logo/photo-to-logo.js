/* Photo to logo, page side: input (click, drop, paste, sample), the worker, the three marks, the construction view on a
   canvas, colours, downloads, the network meter and analytics. Design: docs/designs/photo-to-logo.md.
   No inline styles (CSP): colours are classes and SVG presentation attributes; images are drawn on canvases. */
(function () {
  "use strict";
  var app = document.querySelector(".pl-app");
  if (!app) return;
  var $ = function (id) { return document.getElementById(id); };
  var G = window.LogoGeometry;
  var SVGNS = "http://www.w3.org/2000/svg";
  var COLORS = { purple: "#8c16c5", black: "#111111", white: "#ffffff" };
  var GUIDE = "#c583f3", OUTLINE = "#b46ef0";

  var drop = $("pl-drop"), input = $("pl-file"), status = $("pl-status"), result = $("pl-result"),
    refusal = $("pl-refusal"), picksEl = $("pl-picks"), big = $("pl-big"), canvas = $("pl-construction");

  var CAN = typeof Worker !== "undefined" && typeof OffscreenCanvas !== "undefined" && typeof createImageBitmap !== "undefined";
  if (!CAN || !G) {
    $("pl-old").hidden = false;
    drop.classList.add("is-disabled");
    input.disabled = true;
    $("pl-sample").disabled = true;
    return;
  }

  // ---------- network meter: what this page and its worker send while a photo is worked on ----------
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
    $("pl-net-text").textContent = net.bytes === 0
      ? "Bytes sent while making the logo: 0. Your photo stayed on this device."
      : "While working, " + net.bytes + " bytes were sent in " + net.requests + " request" + (net.requests > 1 ? "s" : "") + ". The tool never sends photos, so please tell ben@purplelink.llc what you saw.";
    $("pl-net").classList.add("is-live");
  }

  function track(type, meta) { if (window.plTrack) window.plTrack(type, meta); }

  // ---------- worker ----------
  var worker = null, seq = 0;
  function stamp(sel, attr) {
    var n = document.querySelector(sel);
    return n ? new URL(n.getAttribute(attr), location.href).searchParams.get("v") || "" : "";
  }
  function startWorker() {
    if (worker) worker.terminate();               // a new photo cancels the one in progress
    var u = new URL(document.querySelector("link[data-logo-worker]").getAttribute("href"), location.href);
    u.searchParams.set("g", stamp('script[src*="logo-geometry"]', "src"));
    u.searchParams.set("m", stamp("link[data-logo-mask]", "href"));
    worker = new Worker(u.href);
    return worker;
  }

  // ---------- state ----------
  var current = null;          // { name, picks, photo, width, height, sel, downloaded }
  function setStatus(t) { status.textContent = t; }
  function show(which) {
    result.hidden = which !== "marks";
    refusal.hidden = which !== "refused";
    app.classList.toggle("is-working", which === "working");
  }

  var REFUSALS = {
    opaque: "This photo has a background, and the page needs the subject on its own. Make a cutout first (see below), then paste or drop it here.",
    empty: "No subject was found in this image. Use a cutout with a transparent background.",
    tiny: "The subject is too small in this image to trace. Crop closer to it, or use a cutout.",
    huge: "The subject fills the whole image, so there is no outline to trace. Use a cutout with a transparent background.",
    pieces: "This cutout has two large separate pieces (two animals, or a gap between body and tail). A mark has one outline, so cut out one subject.",
    nomark: "No clean mark came out of this outline. Try a cutout of the subject seen from the side.",
  };

  function run(file, name) {
    var id = ++seq;
    current = null;
    show("working");
    setStatus("Reading the photo");
    net.armed = true;
    var w = startWorker();
    var finish = function () {
      net.armed = false;
      showNet();
    };
    w.onmessage = function (e) {
      var m = e.data;
      if (m.id !== id) return;
      if (m.type === "progress") { setStatus(m.label); return; }
      if (m.net) { net.requests += m.net.requests; net.bytes += m.net.bytes; }
      if (m.type === "done") {
        finish();
        current = { name: name, picks: m.picks, photo: m.photo, width: m.width, height: m.height, sel: 0, downloaded: false };
        renderMarks();
        show("marks");
        setStatus("Three marks are ready." + (m.dropped > 0.05 ? " A smaller separate piece of the subject was left out." : ""));
        track("tool_use", "photo-to-logo:" + m.kind);
      } else if (m.type === "refused") {
        finish();
        refuse(REFUSALS[m.reason] || REFUSALS.nomark, m.reason === "opaque");
        track("tool_outcome", "limit");
      } else {
        finish();
        if (m.message === "heic") refuse("This browser cannot read HEIC photos. Convert it with HEIC to JPG first, or paste a cutout of the subject.", false, true);
        else refuse(m.user ? m.message : "Something went wrong reading this image. Try another one.", false);
        track("tool_outcome", "error");
      }
    };
    w.onerror = function (ev) {
      if (ev && ev.preventDefault) ev.preventDefault();
      if (id !== seq) return;
      finish();
      worker = null;
      refuse("This photo needs more memory than this tab has. Try a smaller one.", false);
      track("tool_outcome", "error");
    };
    file.arrayBuffer().then(function (buf) {
      w.postMessage({ id: id, op: "make", buffer: buf, type: file.type }, [buf]);
    }, function () {
      finish();
      refuse("This file could not be read.", false);
    });
  }

  function refuse(text, howto, heic) {
    $("pl-refusal-text").textContent = text;
    $("pl-refusal-howto").hidden = !howto;
    $("pl-refusal-heic").hidden = !heic;
    show("refused");
    setStatus(text);
  }

  // ---------- marks ----------
  function fitted(pick, size, pad) {
    var t = G.fitTransform(pick.bbox, size, pad);
    // the summary path is in photo pixels; refit it by re-scaling every coordinate pair through the transform
    return pathThrough(pick.path, t);
  }
  /** Apply a fit transform to an "M L A Z" path in photo coordinates (radii scale, flags stay). */
  function pathThrough(d, t) {
    var out = [], tok = d.match(/[MLAZ]|-?\d*\.?\d+(?:e-?\d+)?/g) || [], i = 0;
    var P = function () {
      var x = parseFloat(tok[i++]), y = parseFloat(tok[i++]);
      return G.fmt(x * t.scale + t.ox) + " " + G.fmt(y * t.scale + t.oy);
    };
    while (i < tok.length) {
      var c = tok[i++];
      if (c === "M" || c === "L") out.push(c + P());
      else if (c === "A") {
        var rx = G.fmt(parseFloat(tok[i++]) * t.scale), ry = G.fmt(parseFloat(tok[i++]) * t.scale);
        var rot = tok[i++], large = tok[i++], sweep = tok[i++];
        out.push("A" + rx + " " + ry + " " + rot + " " + large + " " + sweep + " " + P());
      } else if (c === "Z") out.push("Z");
    }
    return out.join("");
  }

  function svgEl(size, d, label) {
    var s = document.createElementNS(SVGNS, "svg");
    s.setAttribute("viewBox", "0 0 " + size + " " + size);
    s.setAttribute("role", "img");
    s.setAttribute("aria-label", label);
    var p = document.createElementNS(SVGNS, "path");
    p.setAttribute("d", d);
    p.setAttribute("fill-rule", "nonzero");
    p.setAttribute("class", "pl-ink");
    s.appendChild(p);
    return s;
  }

  function renderMarks() {
    picksEl.textContent = "";
    current.picks.forEach(function (pk, i) {
      var label = document.createElement("label");
      label.className = "pl-pick";
      var r = document.createElement("input");
      r.type = "radio"; r.name = "pl-pick"; r.value = String(i); r.checked = i === current.sel;
      r.className = "sr-only";
      r.addEventListener("change", function () { current.sel = i; renderBig(); });
      label.appendChild(r);
      label.appendChild(svgEl(1000, fitted(pk, 1000, 0.08), ""));
      var cap = document.createElement("span");
      cap.textContent = "Mark " + (i + 1) + ": " + pk.nodes + " pieces" + (pk.arcs ? ", " + pk.arcs + " arc" + (pk.arcs > 1 ? "s" : "") : "");
      label.appendChild(cap);
      picksEl.appendChild(label);
    });
    renderBig();
  }

  function renderBig() {
    var pk = current.picks[current.sel];
    big.textContent = "";
    big.appendChild(svgEl(1000, fitted(pk, 1000, 0.08), "Logo mark " + (current.sel + 1)));
    drawConstruction(pk);
  }

  function drawConstruction(pk) {
    // a margin round the photo, so guides (which run 15% past the outline) stay visible on a tight cutout
    var W = current.width, H = current.height, pad = Math.round(0.12 * Math.max(W, H));
    canvas.width = W + 2 * pad; canvas.height = H + 2 * pad;
    var ctx = canvas.getContext("2d");
    ctx.fillStyle = "#19141d";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.translate(pad, pad);
    ctx.globalAlpha = 0.55;
    ctx.drawImage(current.photo, 0, 0);
    ctx.globalAlpha = 1;
    var lw = Math.max(2, Math.max(W, H) / 400);
    ctx.lineWidth = lw;
    ctx.strokeStyle = GUIDE;
    ctx.setLineDash([lw * 5, lw * 4]);
    pk.guides.lines.forEach(function (l) { ctx.beginPath(); ctx.moveTo(l.x0, l.y0); ctx.lineTo(l.x1, l.y1); ctx.stroke(); });
    ctx.setLineDash([]);
    pk.guides.circles.forEach(function (c) { ctx.beginPath(); ctx.arc(c.cx, c.cy, c.r, 0, 2 * Math.PI); ctx.stroke(); });
    var path = new Path2D(pk.path);
    ctx.fillStyle = "rgba(140, 22, 197, 0.28)";
    ctx.fill(path, "nonzero");
    ctx.lineWidth = lw * 2;
    ctx.strokeStyle = OUTLINE;
    ctx.stroke(path);
  }

  // ---------- colour ----------
  function colour() {
    var c = app.querySelector('input[name="pl-colour"]:checked');
    return c ? c.value : "purple";
  }
  function syncColour() {
    app.setAttribute("data-colour", colour());
  }
  Array.prototype.forEach.call(app.querySelectorAll('input[name="pl-colour"]'), function (r) { r.addEventListener("change", syncColour); });
  syncColour();

  // ---------- downloads ----------
  function stem() {
    var s = (current.name || "").replace(/\.[^.]*$/, "").replace(/[^A-Za-z0-9._-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60);
    return s || "logo";
  }
  function save(blob, name) {
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
    if (!current.downloaded) { current.downloaded = true; track("tool_outcome", "ok"); }
  }
  $("pl-svg").addEventListener("click", function () {
    if (!current) return;
    var d = fitted(current.picks[current.sel], 1000, 0.08);
    var svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000" width="1000" height="1000">' +
      "<title>Logo mark</title>" + '<path fill="' + COLORS[colour()] + '" fill-rule="nonzero" d="' + d + '"/></svg>\n';
    save(new Blob([svg], { type: "image/svg+xml" }), stem() + "-logo.svg");
  });
  $("pl-png").addEventListener("click", function () {
    if (!current) return;
    var c = document.createElement("canvas");
    c.width = c.height = 1024;
    var ctx = c.getContext("2d");
    ctx.fillStyle = COLORS[colour()];
    ctx.fill(new Path2D(fitted(current.picks[current.sel], 1024, 0.08)), "nonzero");
    c.toBlob(function (b) { if (b) save(b, stem() + "-logo.png"); }, "image/png");
  });

  // ---------- input: click, keyboard, drag, paste, sample ----------
  function take(files) {
    var f = files && files[0];
    if (f) run(f, f.name || "");
  }
  input.addEventListener("change", function () { take(input.files); input.value = ""; });
  drop.addEventListener("dragover", function (e) { e.preventDefault(); drop.classList.add("is-over"); });
  drop.addEventListener("dragleave", function (e) { if (!drop.contains(e.relatedTarget)) drop.classList.remove("is-over"); });
  drop.addEventListener("drop", function (e) {
    e.preventDefault();
    drop.classList.remove("is-over");
    take(e.dataTransfer && e.dataTransfer.files);
  });
  document.addEventListener("paste", function (e) {
    var items = (e.clipboardData && e.clipboardData.items) || [];
    for (var i = 0; i < items.length; i++) {
      if (items[i].kind === "file" && /^image\//.test(items[i].type)) {
        var f = items[i].getAsFile();
        if (f) { e.preventDefault(); run(f, ""); return; }
      }
    }
  });
  $("pl-sample").addEventListener("click", function () {
    var btn = this;
    btn.disabled = true;
    fetch(btn.getAttribute("data-src")).then(function (r) {
      if (!r.ok) throw new Error("sample");
      return r.blob();
    }).then(function (b) {
      run(new File([b], "raven.webp", { type: "image/webp" }), "raven");
    }, function () {
      refuse("The sample did not load. Check your connection and try again.", false);
    }).then(function () { btn.disabled = false; });
  });
})();
