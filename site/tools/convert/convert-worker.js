/* Runs the converters off the main thread so large photos do not freeze the page. One file at a time.
   Loads the same core file as the page, and libheif only when the first HEIC file arrives.
   Every request this worker makes is counted and reported back, so the page's meter covers it too. */
"use strict";
var q = new URL(self.location.href).searchParams;
var cv = q.get("c") ? "?v=" + q.get("c") : "";
importScripts("/tools/convert/convert-core.js" + cv);

var LIBHEIF = "/assets/vendor/libheif-1.23.5/";
var net = { requests: 0, bytes: 0 };
(function () {
  function size(b) { return b == null ? 0 : typeof b === "string" ? b.length : b.byteLength || b.size || 0; }
  var f0 = self.fetch;
  if (f0) self.fetch = function (input, init) { net.requests++; net.bytes += size(init && init.body); return f0.apply(this, arguments); };
  var xs = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send = function (body) { net.requests++; net.bytes += size(body); return xs.apply(this, arguments); };
})();

var heifPromise = null;
function loadHeif() {
  if (!heifPromise) {
    heifPromise = new Promise(function (resolve, reject) {
      try {
        importScripts(LIBHEIF + "libheif.js");
        Promise.resolve(self.libheif({ locateFile: function (f) { return LIBHEIF + f; } })).then(resolve, reject);
      } catch (e) { reject(e); }
    }).catch(function (e) {
      heifPromise = null; // let the next file try again
      throw new Error("The HEIC decoder failed to load (" + ((e && e.message) || e) + "). Check your connection and try again.");
    });
  }
  return heifPromise;
}

function canvas(w, h) {
  var c = new OffscreenCanvas(w, h);
  var ctx = c.getContext("2d");
  if (!ctx) throw new Error("This browser could not make a drawing surface of " + w + " by " + h + " pixels.");
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  return { c: c, ctx: ctx };
}

async function encode(src, w, h, opts) {
  var s = canvas(w, h);
  if (opts.output === "jpg") { s.ctx.fillStyle = opts.background; s.ctx.fillRect(0, 0, w, h); }
  s.ctx.drawImage(src, 0, 0);
  var type = Convert.MIME[opts.output];
  var blob = await s.c.convertToBlob(opts.output === "jpg" ? { type: type, quality: opts.quality } : { type: type });
  // Safari returns an empty or PNG blob when it cannot encode; never hand that out under a .jpg name.
  if (!blob || blob.size === 0 || blob.type !== type) throw new Error("This browser could not write a " + opts.output.toUpperCase() + " of that size.");
  return new Uint8Array(await blob.arrayBuffer());
}

async function decodeHeif(bytes, opts, progress) {
  progress(0.08, "Loading the HEIC decoder");
  var lib = await loadHeif();
  progress(0.2, "Reading the photo");
  var decoder = new lib.HeifDecoder();
  var images = decoder.decode(bytes);
  if (!images || !images.length) throw new Error("No picture could be read from this HEIC file. It may be damaged.");
  var notes = [];
  // decode() lists the top-level images; the first is the primary one in every file Apple writes.
  var img = images[0];
  if (images.length > 1) notes.push("This file holds " + images.length + " pictures. The first one was converted.");
  var w = img.get_width(), h = img.get_height();
  var big = Convert.tooManyPixels(w, h, opts.mobile);
  if (big) { images.forEach(function (i) { i.free && i.free(); }); throw new Error(big); }
  progress(0.35, "Decoding " + w + " by " + h + " pixels");
  var data = new ImageData(w, h);
  await new Promise(function (resolve, reject) {
    img.display({ data: data.data, width: w, height: h }, function (r) { r ? resolve() : reject(new Error("The photo could not be decoded. It may use a HEIC feature this decoder does not support.")); });
  });
  images.forEach(function (i) { i.free && i.free(); });
  var bmp = await createImageBitmap(data);
  return { bitmap: bmp, width: w, height: h, notes: notes };
}

async function decodeNative(bytes, kind, opts) {
  var bmp;
  try {
    bmp = await createImageBitmap(new Blob([bytes], { type: "image/" + kind }));
  } catch (e) {
    throw new Error("This browser could not read the picture. It may be damaged, or use a variant this browser does not support.");
  }
  var big = Convert.tooManyPixels(bmp.width, bmp.height, opts.mobile);
  if (big) { bmp.close(); throw new Error(big); }
  var notes = [];
  // An animated WebP has an ANIM chunk; the browser hands over the first frame only.
  if (kind === "webp" && hasChunk(bytes, "ANIM")) notes.push("This WebP is animated. Only the first frame was converted.");
  return { bitmap: bmp, width: bmp.width, height: bmp.height, notes: notes };
}

function hasChunk(b, id) {
  for (var at = 12; at + 8 <= b.length && at < 4096;) {
    var name = String.fromCharCode(b[at], b[at + 1], b[at + 2], b[at + 3]);
    if (name === id) return true;
    var len = b[at + 4] | (b[at + 5] << 8) | (b[at + 6] << 16) | (b[at + 7] << 24);
    at += 8 + len + (len & 1);
  }
  return false;
}

async function resized(bitmap, w, h, size) {
  // Halve step by step, then draw the last step into the square with the picture centered.
  var src = bitmap, sw = w, sh = h;
  var fit = Convert.fitSquare(w, h, size);
  var steps = Convert.downscaleSteps(Math.max(w, h), Math.max(fit.width, fit.height));
  for (var i = 0; i < steps.length - 1; i++) {
    var k = steps[i] / Math.max(sw, sh);
    var nw = Math.max(1, Math.round(sw * k)), nh = Math.max(1, Math.round(sh * k));
    var s = canvas(nw, nh);
    s.ctx.drawImage(src, 0, 0, nw, nh);
    src = s.c; sw = nw; sh = nh;
  }
  var out = canvas(size, size);
  out.ctx.drawImage(src, fit.x, fit.y, fit.width, fit.height);
  var blob = await out.c.convertToBlob({ type: "image/png" });
  if (!blob || blob.type !== "image/png") throw new Error("This browser could not write a PNG.");
  return new Uint8Array(await blob.arrayBuffer());
}

async function toIcns(pic, name, opts, progress) {
  var pngs = {};
  var sizes = Convert.ICNS_SIZES;
  for (var i = 0; i < sizes.length; i++) {
    progress(0.3 + 0.6 * (i / sizes.length), "Drawing " + sizes[i] + " px");
    pngs[sizes[i]] = await resized(pic.bitmap, pic.width, pic.height, sizes[i]);
  }
  var icns = Convert.buildIcns(pngs);
  Convert.parseIcns(icns); // throws if the container is not self-consistent
  var outputs = [{ name: Convert.outName(name, "icns"), mime: Convert.MIME.icns, bytes: icns }];
  if (opts.iconset) {
    var base = Convert.outName(name, "iconset");
    Convert.ICONSET.forEach(function (e) { outputs.push({ name: base + "/" + e[0], mime: Convert.MIME.png, bytes: pngs[e[1]], part: true }); });
  }
  var notes = pic.notes.slice();
  if (Math.max(pic.width, pic.height) < 1024) notes.push("The picture is " + pic.width + " by " + pic.height + " pixels, so the larger sizes are enlarged and will look soft. Start from 1024 by 1024 for a sharp icon.");
  if (pic.width !== pic.height) notes.push("The picture is not square, so it was centered with transparent edges.");
  return { outputs: outputs, notes: notes };
}

self.onmessage = async function (e) {
  var m = e.data;
  var before = { requests: net.requests, bytes: net.bytes };
  function progress(p, label) { self.postMessage({ id: m.id, type: "progress", p: p, label: label }); }
  try {
    if (typeof OffscreenCanvas === "undefined") throw new Error("This browser cannot convert pictures in the background. Use a current version of Chrome, Edge, Firefox or Safari.");
    var bytes = new Uint8Array(m.buffer);
    var pair = Convert.CONVERSIONS[m.pair];
    var opts = Convert.options(m.pair, m.opts);
    var kind = Convert.sniff(bytes);
    var why = Convert.refuse(m.pair, kind, bytes.length);
    if (why) throw new Error(why);
    progress(0.04, "Reading");
    var pic = kind === "heic" ? await decodeHeif(bytes, opts, progress) : await decodeNative(bytes, kind, opts);
    m.buffer = bytes = null; // the source is no longer needed; let it go before encoding
    var res;
    if (pair.output === "icns") res = await toIcns(pic, m.name, opts, progress);
    else {
      progress(0.75, "Writing " + opts.output.toUpperCase());
      var out = await encode(pic.bitmap, pic.width, pic.height, opts);
      res = { outputs: [{ name: Convert.outName(m.name, opts.output), mime: Convert.MIME[opts.output], bytes: out }], notes: pic.notes };
    }
    pic.bitmap.close && pic.bitmap.close();
    res.width = pic.width; res.height = pic.height;
    res.net = { requests: net.requests - before.requests, bytes: net.bytes - before.bytes };
    var transfer = [];
    res.outputs.forEach(function (o) { if (transfer.indexOf(o.bytes.buffer) === -1) transfer.push(o.bytes.buffer); });
    self.postMessage({ id: m.id, type: "done", res: res }, transfer);
  } catch (err) {
    self.postMessage({ id: m.id, type: "error", message: String((err && err.message) || err),
      net: { requests: net.requests - before.requests, bytes: net.bytes - before.bytes } });
  }
};
