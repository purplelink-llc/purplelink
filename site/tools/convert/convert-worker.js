/* Runs the converters off the main thread so large files do not freeze the page. One file at a time.
   Loads the same core file as the page, and libheif, pdf-lib or JSZip only when the first file that needs it arrives.
   Every fetch and XHR this worker makes is counted and reported back, so the page's meter covers it too. Library loads
   (importScripts) are not counted: they are GET requests for this site's own files and send nothing. */
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

// Libraries the page names, with their ?v= stamps. Only this site's own vendor folder is accepted.
var libs = {};
function loadLib(key, global) {
  if (self[global]) return self[global];
  var u = libs[key];
  if (!u || u.indexOf("/assets/vendor/") !== 0) throw new Error("The page did not name its " + key + " library.");
  try { importScripts(u); } catch (e) { throw new Error("A library this page needs did not load. Check your connection and try again."); }
  if (!self[global]) throw new Error("A library this page needs did not load. Reload the page and try again.");
  return self[global];
}

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
  if (typeof OffscreenCanvas === "undefined") throw new Error("This browser cannot draw pictures in the background. Use a current version of Chrome, Edge, Firefox or Safari.");
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

async function decodeNative(bytes, kind, opts, maxPixels) {
  var bmp;
  try {
    bmp = await createImageBitmap(new Blob([bytes], { type: "image/" + kind }));
  } catch (e) {
    if (kind === "avif") throw new Error("This browser could not read the AVIF file. Chrome and Edge 85, Firefox 93 and Safari 16.4 on macOS 13 or iOS 16 and later read AVIF. If yours does, the file may be damaged.");
    throw new Error("This browser could not read the picture. It may be damaged, or use a variant this browser does not support.");
  }
  var big = Convert.tooManyPixels(bmp.width, bmp.height, opts.mobile, maxPixels);
  if (big) { bmp.close(); throw new Error(big); }
  var notes = [];
  // An animated WebP has an ANIM chunk, an animated AVIF the avis brand; the browser hands over the first frame only.
  if (kind === "webp" && hasChunk(bytes, "ANIM")) notes.push("This WebP is animated. Only the first frame was converted.");
  if (kind === "avif" && isAvis(bytes)) notes.push("This AVIF is animated. Only the first frame was converted.");
  return { bitmap: bmp, width: bmp.width, height: bmp.height, notes: notes };
}

function isAvis(b) {
  for (var i = 8; i + 4 <= Math.min(b.length, 64); i += 4) if (String.fromCharCode(b[i], b[i + 1], b[i + 2], b[i + 3]) === "avis") return true;
  return false;
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

async function drawSizes(pic, sizes, progress) {
  var pngs = {};
  for (var i = 0; i < sizes.length; i++) {
    progress(0.3 + 0.6 * (i / sizes.length), "Drawing " + sizes[i] + " px");
    pngs[sizes[i]] = await resized(pic.bitmap, pic.width, pic.height, sizes[i]);
  }
  return pngs;
}

function iconNotes(pic, largest) {
  var notes = pic.notes.slice();
  if (Math.max(pic.width, pic.height) < largest) notes.push("The picture is " + pic.width + " by " + pic.height + " pixels, so the larger sizes are enlarged and will look soft. Start from " + largest + " by " + largest + " for a sharp icon.");
  if (pic.width !== pic.height) notes.push("The picture is not square, so it was centered with transparent edges.");
  return notes;
}

async function toIcns(pic, name, opts, progress) {
  var pngs = await drawSizes(pic, Convert.ICNS_SIZES, progress);
  var icns = Convert.buildIcns(pngs);
  Convert.parseIcns(icns); // throws if the container is not self-consistent
  var outputs = [{ name: Convert.outName(name, "icns"), mime: Convert.MIME.icns, bytes: icns }];
  if (opts.iconset) {
    var base = Convert.outName(name, "iconset");
    Convert.ICONSET.forEach(function (e) { outputs.push({ name: base + "/" + e[0], mime: Convert.MIME.png, bytes: pngs[e[1]], part: true }); });
  }
  return { outputs: outputs, notes: iconNotes(pic, 1024) };
}

async function toIco(pic, name, opts, progress) {
  var sizes = Convert.ICO_SETS[opts.sizes];
  var pngs = await drawSizes(pic, sizes, progress);
  var ico = Convert.buildIco(pngs, sizes);
  Convert.parseIco(ico);
  var out = { outputs: [{ name: Convert.outName(name, "ico"), mime: Convert.MIME.ico, bytes: ico }], notes: iconNotes(pic, sizes[sizes.length - 1]) };
  out.summary = "Sizes " + sizes.join(", ") + " pixels";
  return out;
}

// ---------- JPG to PDF ----------
async function reencodeJpeg(bytes, kind, opts, maxPixels) {
  // createImageBitmap applies the EXIF orientation, so the result is upright and needs no matrix.
  var pic = await decodeNative(bytes, kind, opts, maxPixels);
  var s = canvas(pic.width, pic.height);
  if (kind === "jpeg") { s.ctx.fillStyle = "#ffffff"; s.ctx.fillRect(0, 0, pic.width, pic.height); }
  s.ctx.drawImage(pic.bitmap, 0, 0);
  pic.bitmap.close && pic.bitmap.close();
  var type = kind === "jpeg" ? "image/jpeg" : "image/png";
  var blob = await s.c.convertToBlob(kind === "jpeg" ? { type: type, quality: 0.95 } : { type: type });
  if (!blob || blob.size === 0 || blob.type !== type) throw new Error("This browser could not redraw that picture.");
  return { bytes: new Uint8Array(await blob.arrayBuffer()), width: pic.width, height: pic.height, notes: pic.notes };
}

function newPdf(P) {
  return P.PDFDocument.create().then(function (doc) {
    doc.setProducer("Purplelink JPG to PDF");
    doc.setCreator("purplelink.llc/tools/jpg-to-pdf/");
    return doc;
  });
}

async function toPdf(bytes, kind, name, opts, maxPixels, progress) {
  progress(0.1, "Loading the PDF writer");
  var P = loadLib("pdf", "PDFLib");
  var doc = await newPdf(P);
  var notes = [], img, w, h, orientation = 1, dpi = 0;
  progress(0.3, "Reading the picture");
  if (kind === "jpeg") {
    var info = Convert.jpegInfo(bytes);
    if (!info) throw new Error("The JPEG header could not be read. The file may be damaged.");
    if (info.embeddable) {
      img = await doc.embedJpg(bytes);
      w = info.width; h = info.height; orientation = info.orientation; dpi = info.dpi;
    } else {
      // Arithmetic-coded, 12-bit, lossless, or CMYK without Adobe's marker: not every PDF reader shows these right.
      var re = await reencodeJpeg(bytes, "jpeg", opts, maxPixels);
      img = await doc.embedJpg(re.bytes);
      w = re.width; h = re.height;
      notes.push("This JPEG uses an encoding some PDF readers do not show correctly, so it was redrawn at quality 95.");
    }
  } else {
    // PNGs are redrawn by the browser first: that applies their color profile and turns 16-bit, interlaced and
    // palette files into the plain 8-bit PNG pdf-lib embeds reliably.
    var png = await reencodeJpeg(bytes, "png", opts, maxPixels);
    notes = notes.concat(png.notes);
    img = await doc.embedPng(png.bytes);
    w = png.width; h = png.height;
  }
  bytes = null;
  progress(0.7, "Writing the page");
  var disp = Convert.displaySize(w, h, orientation);
  var lay = Convert.pageLayout(opts.page, opts.margin, disp.width, disp.height, dpi);
  var page = doc.addPage([lay.width, lay.height]);
  var key = page.node.newXObject("Image", img.ref);
  var m = Convert.pdfMatrix(orientation, lay.w, lay.h, lay.x, lay.y);
  page.pushOperators(P.pushGraphicsState(), P.concatTransformationMatrix(m[0], m[1], m[2], m[3], m[4], m[5]), P.drawObject(key), P.popGraphicsState());
  var out = await doc.save();
  var res = { outputs: [{ name: Convert.outName(name, "pdf"), mime: Convert.MIME.pdf, bytes: out }], notes: notes };
  res.width = disp.width; res.height = disp.height;
  res.summary = disp.width + " by " + disp.height + " pixels, one " + pageName(opts.page, lay) + " page";
  return res;
}

function pageName(page, lay) {
  var turn = lay.width > lay.height ? " landscape" : "";
  return page === "a4" ? "A4" + turn : page === "letter" ? "Letter" + turn : Math.round(lay.width / 72 * 25.4) + " by " + Math.round(lay.height / 72 * 25.4) + " mm";
}

async function combinePdfs(buffers, progress) {
  var P = loadLib("pdf", "PDFLib");
  var doc = await newPdf(P);
  for (var i = 0; i < buffers.length; i++) {
    progress(i / buffers.length, "Adding page " + (i + 1) + " of " + buffers.length);
    var src = await P.PDFDocument.load(buffers[i]);
    var pages = await doc.copyPages(src, src.getPageIndices());
    pages.forEach(function (pg) { doc.addPage(pg); });
    buffers[i] = null;
  }
  progress(0.95, "Saving");
  return await doc.save();
}

// ---------- CSV to XLSX ----------
async function toXlsx(bytes, name, opts, progress) {
  progress(0.1, "Reading the text");
  var Z = loadLib("zip", "JSZip");
  var dec = Convert.decodeText(bytes, opts.encoding === "auto" ? "" : opts.encoding);
  bytes = null;
  var d = opts.delimiter === "auto" ? Convert.detectDelimiter(dec.text, name) : Convert.DELIMS[opts.delimiter];
  progress(0.25, "Splitting into cells");
  var rows = Convert.parseCsv(dec.text, d);
  var unclosed = rows.unclosed;
  dec.text = null;
  if (!rows.length) throw new Error("This file has no rows.");
  progress(0.45, "Building the sheet");
  var built = Convert.buildXlsxParts(rows, name, { header: opts.header, text: opts.text, delimiter: d });
  rows = null;
  var zip = new Z();
  Object.keys(built.parts).forEach(function (k) {
    var v = built.parts[k];
    zip.file(k, Array.isArray(v) ? new Blob(v, { type: "application/xml" }) : v);
  });
  built.parts = null;
  var out = await zip.generateAsync({ type: "uint8array", compression: "DEFLATE", compressionOptions: { level: 6 } }, function (meta) {
    progress(0.55 + 0.4 * (meta.percent / 100), "Compressing");
  });
  var notes = built.notes.slice();
  if (unclosed) notes.push("A quoted value is never closed, so everything after it ended up in one cell. Check the last row.");
  var names = { ",": "comma", ";": "semicolon", "\t": "tab", "|": "pipe" };
  return {
    outputs: [{ name: Convert.outName(name, "xlsx"), mime: Convert.MIME.xlsx, bytes: out }], notes: notes,
    summary: built.rows.toLocaleString("en-US") + " row" + (built.rows === 1 ? "" : "s") + " and " + built.cols + " column" + (built.cols === 1 ? "" : "s") +
      ", read as " + dec.encoding + ", " + names[d] + "-separated"
  };
}

self.onmessage = async function (e) {
  var m = e.data;
  var before = { requests: net.requests, bytes: net.bytes };
  function progress(p, label) { self.postMessage({ id: m.id, type: "progress", p: p, label: label }); }
  function used() { return { requests: net.requests - before.requests, bytes: net.bytes - before.bytes }; }
  try {
    if (m.libs) libs = m.libs;
    var res;
    if (m.op === "combine") {
      var pdf = await combinePdfs(m.buffers, progress);
      res = { outputs: [{ name: "combined.pdf", mime: Convert.MIME.pdf, bytes: pdf }], notes: [] };
    } else {
      var bytes = new Uint8Array(m.buffer);
      var pair = Convert.CONVERSIONS[m.pair];
      var opts = Convert.options(m.pair, m.opts);
      var kind = Convert.kindOf(bytes.subarray(0, 4096), m.name);
      var why = Convert.refuse(m.pair, kind, bytes.length);
      if (why) throw new Error(why);
      if (pair.canvas && (typeof OffscreenCanvas === "undefined" || typeof createImageBitmap === "undefined")) throw new Error("This browser cannot convert pictures in the background. Use a current version of Chrome, Edge, Firefox or Safari.");
      progress(0.04, "Reading");
      m.buffer = null;
      if (pair.work === "pdf") res = await toPdf(bytes, kind, m.name, opts, pair.maxPixels, progress);
      else if (pair.work === "sheet") res = await toXlsx(bytes, m.name, opts, progress);
      else {
        var pic = kind === "heic" ? await decodeHeif(bytes, opts, progress) : await decodeNative(bytes, kind, opts, pair.maxPixels);
        bytes = null; // the source is no longer needed; let it go before encoding
        if (pair.output === "icns") res = await toIcns(pic, m.name, opts, progress);
        else if (pair.output === "ico") res = await toIco(pic, m.name, opts, progress);
        else {
          progress(0.75, "Writing " + opts.output.toUpperCase());
          var out = await encode(pic.bitmap, pic.width, pic.height, opts);
          res = { outputs: [{ name: Convert.outName(m.name, opts.output), mime: Convert.MIME[opts.output], bytes: out }], notes: pic.notes };
        }
        pic.bitmap.close && pic.bitmap.close();
        res.width = pic.width; res.height = pic.height;
      }
    }
    res.net = used();
    var transfer = [];
    res.outputs.forEach(function (o) { if (transfer.indexOf(o.bytes.buffer) === -1) transfer.push(o.bytes.buffer); });
    self.postMessage({ id: m.id, type: "done", res: res }, transfer);
  } catch (err) {
    self.postMessage({ id: m.id, type: "error", message: String((err && err.message) || err), net: used() });
  }
};
