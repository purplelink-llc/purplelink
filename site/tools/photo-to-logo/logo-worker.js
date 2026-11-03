/* Photo to logo, worker side: decode the photo, find the subject, run LogoForge's grid of 20 variants, return the
   three picks. One message per photo; the page terminates the worker to cancel. Design: docs/designs/photo-to-logo.md.
   Every fetch and XHR this worker makes is counted and reported back as `net`, so the page's meter covers it too.
   The two importScripts below are GET requests for this site's own files and send nothing. */
"use strict";

var q = new URL(self.location.href).searchParams;
importScripts("/tools/photo-to-logo/logo-geometry.js?v=" + (q.get("g") || ""),
  "/tools/photo-to-logo/logo-mask.js?v=" + (q.get("m") || ""));

var net = { requests: 0, bytes: 0 };
(function () {
  function size(b) { try { return b == null ? 0 : (b.byteLength || b.size || String(b).length || 0); } catch (e) { return 0; } }
  var f0 = self.fetch;
  if (f0) self.fetch = function (input, init) { net.requests++; net.bytes += size(init && init.body); return f0.apply(this, arguments); };
  if (self.XMLHttpRequest) {
    var xs = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function (body) { net.requests++; net.bytes += size(body); return xs.apply(this, arguments); };
  }
})();

var WORK = 1024;                       // LogoForge's working size (long side)
var MAX_BYTES = 50 * 1024 * 1024;
var IOS = /iP(hone|ad|od)/.test(self.navigator.userAgent) ||
  (/Macintosh/.test(self.navigator.userAgent) && self.navigator.maxTouchPoints > 1);
var MAX_PIXELS = IOS ? 16.7e6 : 100e6;

function fail(message) { var e = new Error(message); e.user = true; return e; }

async function decode(buffer, type) {
  if (buffer.byteLength > MAX_BYTES) throw fail("This file is over 50 MB. Export a smaller copy and try again.");
  var bmp;
  try {
    bmp = await createImageBitmap(new Blob([buffer], { type: type || "" }));
  } catch (e) {
    if (/hei[cf]/i.test(type || "")) throw fail("heic");
    throw fail("This browser could not read the file. Use a PNG, WebP, JPG or AVIF image.");
  }
  if (bmp.width * bmp.height > MAX_PIXELS) {
    bmp.close();
    throw fail("This photo has more pixels than this device can work with here. Export a copy under 16 megapixels.");
  }
  var s = Math.min(1, WORK / Math.max(bmp.width, bmp.height));
  var w = Math.max(1, Math.round(bmp.width * s)), h = Math.max(1, Math.round(bmp.height * s));
  var canvas = new OffscreenCanvas(w, h);
  var ctx = canvas.getContext("2d", { willReadFrequently: true });
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(bmp, 0, 0, w, h);
  bmp.close();
  return { canvas: canvas, w: w, h: h, rgba: ctx.getImageData(0, 0, w, h).data };
}

async function make(m) {
  var before = { requests: net.requests, bytes: net.bytes };
  function used() { return { requests: net.requests - before.requests, bytes: net.bytes - before.bytes }; }
  function progress(label, p) { self.postMessage({ id: m.id, type: "progress", label: label, p: p }); }
  function refuse(reason) { self.postMessage({ id: m.id, type: "refused", reason: reason, net: used() }); }
  try {
    progress("Reading the photo", 0);
    var img = await decode(m.buffer, m.type);
    m.buffer = null;
    var w = img.w, h = img.h;

    progress("Finding the subject", 0.05);
    var kind = "cutout", raw = LogoMask.alphaMask(img.rgba, w, h);
    if (!raw.cutout) {
      kind = "plain";
      raw = LogoMask.plainBackground(img.rgba, w, h);
      if (!raw.plain) return refuse("opaque");
    }
    var clean = LogoMask.cleanMask(raw.mask, w, h);
    if (!clean.area) return refuse("empty");
    var frac = clean.area / (w * h);
    if (frac < 0.01) return refuse("tiny");
    if (frac > 0.97) return refuse("huge");
    if (clean.dropped > 0.25) return refuse("pieces");

    progress("Finding the outline", 0.1);
    var contour = LogoMask.traceContour(clean.mask, w, h);
    var res = LogoGeometry.buildVariants(contour, clean.mask, w, h, {
      onProgress: function (done, total) {
        progress("Fitting lines and arcs " + done + " of " + total, 0.1 + 0.9 * done / total);
      },
    });
    if (!res.picks.length) return refuse("nomark");

    var photo = img.canvas.transferToImageBitmap();
    self.postMessage({
      id: m.id, type: "done", kind: kind, width: w, height: h, photo: photo,
      picks: res.picks.map(function (i) { return LogoGeometry.summarise(res.variants[i]); }),
      dropped: clean.dropped, net: used(),
    }, [photo]);
  } catch (err) {
    self.postMessage({ id: m.id, type: "error", message: String((err && err.message) || err), user: !!(err && err.user), net: used() });
  }
}

self.onmessage = function (e) {
  if (e.data && e.data.op === "make") make(e.data);
};
