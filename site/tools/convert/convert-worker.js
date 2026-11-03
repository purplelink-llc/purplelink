/* Runs the converters off the main thread so large files do not freeze the page. One file at a time.
   Loads the same core file as the page, and libheif, pdf-lib, JSZip or UTIF only when the first file that needs it
   arrives.
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
  // An animated PNG has an acTL chunk before its image data; an animated GIF a NETSCAPE2.0 looping block.
  if (kind === "png" && hasPngChunk(bytes, "acTL")) notes.push("This PNG is animated. Only the first frame was converted.");
  if (kind === "gif" && hasAscii(bytes, "NETSCAPE2.0", 65536)) notes.push("This GIF is animated. Only the first frame was converted.");
  return { bitmap: bmp, width: bmp.width, height: bmp.height, notes: notes };
}

function isAvis(b) {
  for (var i = 8; i + 4 <= Math.min(b.length, 64); i += 4) if (String.fromCharCode(b[i], b[i + 1], b[i + 2], b[i + 3]) === "avis") return true;
  return false;
}

function hasPngChunk(b, id) {
  for (var at = 8; at + 8 <= b.length;) {
    var len = ((b[at] << 24) | (b[at + 1] << 16) | (b[at + 2] << 8) | b[at + 3]) >>> 0;
    var name = String.fromCharCode(b[at + 4], b[at + 5], b[at + 6], b[at + 7]);
    if (name === id) return true;
    if (name === "IDAT" || name === "IEND") return false;
    at += 12 + len;
  }
  return false;
}

function hasAscii(b, text, limit) {
  var end = Math.min(b.length, limit) - text.length;
  outer: for (var i = 0; i <= end; i++) {
    for (var j = 0; j < text.length; j++) if (b[i + j] !== text.charCodeAt(j)) continue outer;
    return true;
  }
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

// ---------- XLSX to CSV and JSON to CSV ----------
var SHEET_XML_CAP = 100 * 1024 * 1024;
function separator(opts) { return opts.delimiter === "auto" ? "," : Convert.DELIMS[opts.delimiter] || ","; }
function csvBytes(text, bom) {
  var b = new TextEncoder().encode(text);
  if (!bom) return b;
  var out = new Uint8Array(b.length + 3);
  out.set([0xef, 0xbb, 0xbf], 0); out.set(b, 3);
  return out;
}

// A part of the workbook as text, counting bytes as they inflate, so a size field that lies cannot run the tab out
// of memory.
function partText(zip, path, what) {
  var f = zip.file(path);
  if (!f) return Promise.resolve(null);
  return new Promise(function (resolve, reject) {
    var parts = [], n = 0, stopped = false;
    var s = f.internalStream("uint8array");
    s.on("data", function (c) {
      if (stopped) return;
      n += c.length;
      if (n > SHEET_XML_CAP) { stopped = true; s.pause(); reject(new Error(what + " is over 100 MB of data, more than this page reads in a browser tab.")); return; }
      parts.push(c);
    }).on("error", function (e) { if (!stopped) { stopped = true; reject(new Error("The workbook could not be read (" + ((e && e.message) || e) + ").")); } })
      .on("end", function () {
        if (stopped) return;
        var all = new Uint8Array(n), at = 0;
        parts.forEach(function (c) { all.set(c, at); at += c.length; });
        resolve(new TextDecoder("utf-8").decode(all));
      }).resume();
  });
}

async function xlsxToCsv(bytes, name, opts, progress) {
  progress(0.1, "Opening the workbook");
  var Z = loadLib("zip", "JSZip");
  var zip;
  try { zip = await Z.loadAsync(bytes); } catch (e) { throw new Error("This file could not be opened as a workbook. It may be damaged, or not really an .xlsx."); }
  bytes = null;
  var wbXml = await partText(zip, "xl/workbook.xml", "The workbook index");
  if (!wbXml) throw new Error("This zip has no xl/workbook.xml, so it is not an Excel workbook.");
  var wb = Convert.parseWorkbook(wbXml);
  var rels = Convert.parseRels((await partText(zip, "xl/_rels/workbook.xml.rels", "The workbook index")) || "", "xl/");
  progress(0.2, "Reading the shared text");
  var shared = Convert.parseSharedStrings((await partText(zip, "xl/sharedStrings.xml", "The shared text of this workbook")) || "");
  var styles = Convert.parseStyles((await partText(zip, "xl/styles.xml", "The styles of this workbook")) || "");
  var sheets = wb.sheets.map(function (s) {
    var r = rels[s.rid] || {};
    return { name: s.name, state: s.state, path: r.target, type: r.type };
  }).filter(function (s) { return s.type === "worksheet" && s.path && zip.file(s.path); });
  if (!sheets.length) throw new Error("This workbook has no sheets with cells. Chart sheets have none.");
  var pick = opts.sheets === "all" ? sheets : [sheets[0]];
  var d = separator(opts), outputs = [], notes = [], rows = 0, lost = 0;
  var base = Convert.outName(name, "x").replace(/\.x$/, ""), folder = base + "-sheets";
  var names = Convert.uniqueNames(pick.map(function (s) { return Convert.sheetFileName(s.name) + ".csv"; }));
  for (var i = 0; i < pick.length; i++) {
    progress(0.3 + 0.65 * (i / pick.length), "Reading " + pick[i].name);
    var xml = await partText(zip, pick[i].path, "The sheet “" + pick[i].name + "”");
    var r = Convert.sheetRows(xml, shared, styles, wb.date1904, Convert.MAX_CELLS, opts.safe);
    xml = null;
    rows += r.rows.length; lost += r.formulasWithoutValue;
    var csv = csvBytes(Convert.toCsv(r.rows, d), opts.bom);
    outputs.push(pick.length === 1
      ? { name: Convert.outName(name, "csv"), mime: Convert.MIME.csv, bytes: csv }
      : { name: folder + "/" + names[i], mime: Convert.MIME.csv, bytes: csv, part: true });
  }
  var hidden = pick.filter(function (s) { return s.state !== "visible"; }).map(function (s) { return "“" + s.name + "”"; });
  if (hidden.length) notes.push("Hidden sheets were included: " + hidden.join(", ") + ".");
  if (opts.sheets !== "all" && sheets.length > 1) notes.push("This workbook has " + sheets.length + " sheets. The first, “" + sheets[0].name + "”, was converted; choose All sheets for the rest.");
  if (lost) notes.push(lost + " formula" + (lost === 1 ? " has" : "s have") + " no saved result in the file, so " + (lost === 1 ? "its cell is" : "their cells are") + " empty. Open the workbook in Excel and save it once to store the results.");
  var res = { outputs: outputs, notes: notes };
  res.summary = pick.length === 1
    ? rows.toLocaleString("en-US") + " row" + (rows === 1 ? "" : "s") + " from “" + pick[0].name + "”"
    : pick.length + " sheets, " + rows.toLocaleString("en-US") + " rows";
  if (pick.length > 1) { res.partsLabel = "Download the " + pick.length + " sheets (.zip)"; res.zipName = folder + ".zip"; }
  return res;
}

async function zipXlsx(Z, built, progress) {
  var zip = new Z();
  Object.keys(built.parts).forEach(function (k) {
    var v = built.parts[k];
    zip.file(k, Array.isArray(v) ? new Blob(v, { type: "application/xml" }) : v);
  });
  built.parts = null;
  return await zip.generateAsync({ type: "uint8array", compression: "DEFLATE", compressionOptions: { level: 6 } }, function (meta) {
    progress(0.55 + 0.4 * (meta.percent / 100), "Compressing");
  });
}

async function jsonToTable(bytes, name, opts, progress) {
  progress(0.1, "Reading the JSON");
  var dec = Convert.decodeText(bytes, "");
  bytes = null;
  var r = Convert.jsonRecords(dec.text);
  dec.text = null;
  if (!r.records.length) throw new Error("This JSON holds an empty list, so there are no rows to write.");
  progress(0.35, "Making columns");
  var csv = opts.output !== "xlsx";
  var f = Convert.flattenRecords(r.records, opts.nested, csv && opts.safe);
  r.records = null;
  var plain = name.replace(/\.(ndjson|geojson|jsonl)$/i, ".json");
  var notes = [];
  if (r.from) notes.push("The rows are the list under “" + r.from + "”" + (r.others.length ? "; other lists, " + r.others.map(function (k) { return "“" + k + "”"; }).join(", ") + ", were left out" : "") + ".");
  if (r.lines) notes.push("Read as JSON Lines: one record per line.");
  var out;
  if (csv) out = { name: Convert.outName(plain, "csv"), mime: Convert.MIME.csv, bytes: csvBytes(Convert.toCsv(f.rows, separator(opts)), opts.bom) };
  else {
    progress(0.45, "Building the sheet");
    var built = Convert.buildXlsxParts(f.rows, plain, { header: true, text: false, delimiter: ",", app: "Purplelink JSON to CSV" });
    notes = notes.concat(built.notes);
    out = { name: Convert.outName(plain, "xlsx"), mime: Convert.MIME.xlsx, bytes: await zipXlsx(loadLib("zip", "JSZip"), built, progress) };
  }
  var n = f.rows.length - 1;
  return { outputs: [out], notes: notes, summary: n.toLocaleString("en-US") + " row" + (n === 1 ? "" : "s") + " and " + f.columns + " column" + (f.columns === 1 ? "" : "s") };
}

// ---------- TIFF to JPG ----------
// The core reads the directories; UTIF supplies the LZW and CCITT decoders, pako the Deflate one.
async function tiffPageBitmap(bytes, p, libs) {
  if (p.compression === 7) {
    var c = canvas(p.width, p.height);
    var tw = p.tiled ? p.tileWidth : p.width, th = p.tiled ? p.tileHeight : p.rowsPerStrip;
    var across = p.tiled ? Math.ceil(p.width / tw) : 1;
    for (var i = 0; i < p.offsets.length; i++) {
      var jpg = Convert.tiffJpeg(bytes.subarray(p.offsets[i], p.offsets[i] + p.counts[i]), p.jpegTables, p.photometric === 2);
      var bmp = await createImageBitmap(new Blob([jpg], { type: "image/jpeg" }));
      c.ctx.drawImage(bmp, (i % across) * tw, Math.floor(i / across) * th);
      bmp.close && bmp.close();
    }
    return c.c.transferToImageBitmap();
  }
  var raw = Convert.tiffDecodeRaw(bytes, p, libs);
  var rgba = Convert.tiffRGBA(raw, p);
  raw = null;
  return await createImageBitmap(new ImageData(rgba, p.width, p.height));
}

async function tiffToImages(bytes, name, opts, maxPixels, progress) {
  progress(0.08, "Reading the TIFF");
  var t = Convert.readTiff(bytes);
  var full = t.pages.filter(function (p) { return !p.thumbnail; });
  if (!full.length) full = t.pages;
  var pick = opts.tiffpages === "all" ? full : [full[0]];
  if (pick.length > Convert.MAX_TIFF_PAGES) throw new Error("This TIFF has " + pick.length + " pages, more than this page converts at a time (" + Convert.MAX_TIFF_PAGES + ").");
  if (pick.length === 1 && pick[0].problem) throw new Error(pick[0].problem);
  var libs = {};
  if (pick.some(function (p) { return [3, 4, 5, 8, 32946].indexOf(p.compression) !== -1; })) {
    progress(0.12, "Loading the TIFF decoder");
    libs.pako = loadLib("pako", "pako"); // UTIF reads self.pako when it loads, so pako goes first
    libs.UTIF = loadLib("utif", "UTIF");
  }
  var one = pick.length === 1, base = Convert.outName(name, "x").replace(/\.x$/, ""), folder = base + "-pages";
  var outputs = [], notes = [], failed = [], total = 0, stopped = 0, deep = false, last = null;
  for (var i = 0; i < pick.length; i++) {
    var p = pick[i], n = t.pages.indexOf(p) + 1;
    progress(0.15 + 0.8 * (i / pick.length), one ? "Decoding " + p.width + " by " + p.height + " pixels" : "Page " + (i + 1) + " of " + pick.length);
    try {
      if (p.problem) throw new Error(p.problem);
      var big = Convert.tooManyPixels(p.width, p.height, opts.mobile, maxPixels);
      if (big) throw new Error(big);
      var bmp = await tiffPageBitmap(bytes, p, libs);
      var o = Convert.orientTransform(p.orientation, p.width, p.height), src = bmp;
      if (p.orientation > 1 && p.orientation <= 8) {
        var turned = canvas(o.width, o.height);
        turned.ctx.setTransform(o.m[0], o.m[1], o.m[2], o.m[3], o.m[4], o.m[5]);
        turned.ctx.drawImage(bmp, 0, 0);
        src = turned.c;
      }
      var out = await encode(src, o.width, o.height, opts);
      bmp.close && bmp.close();
      if (p.bps[0] === 16) deep = true;
      total += out.length;
      last = o;
      outputs.push(one ? { name: Convert.outName(name, opts.output), mime: Convert.MIME[opts.output], bytes: out }
        : { name: folder + "/" + Convert.pageName(name, i + 1, pick.length, opts.output), mime: Convert.MIME[opts.output], bytes: out, part: true });
    } catch (e) {
      if (one) throw e.message ? e : new Error("This TIFF page could not be decoded. It may be damaged.");
      failed.push(i + 1);
    }
    if (total > Convert.MAX_ZIP_BYTES && i < pick.length - 1) { stopped = i + 1; break; }
  }
  if (!outputs.length) throw new Error("No page of this TIFF could be converted.");
  if (deep) notes.push("This TIFF stores 16 bits per sample. It was reduced to 8 bits; nothing is brightened, so a dim scientific image stays dim.");
  if (!one && failed.length) notes.push((failed.length === 1 ? "Page " + failed[0] + " could not be converted and was left out." : "Pages " + failed.join(", ") + " could not be converted and were left out."));
  if (stopped) notes.push("Stopped after page " + stopped + ": the pages so far add up to 1 GB, the most this tab can zip.");
  if (opts.tiffpages !== "all" && full.length > 1) notes.push("This TIFF has " + full.length + " pages. The first was converted; choose All pages for the rest.");
  var res = { outputs: outputs, notes: notes };
  if (one) { res.width = last.width; res.height = last.height; }
  else { res.summary = outputs.length + " pages"; res.partsLabel = "Download the " + outputs.length + " pages (.zip)"; res.zipName = folder + ".zip"; }
  return res;
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
      else if (pair.work === "unsheet") res = await xlsxToCsv(bytes, m.name, opts, progress);
      else if (pair.work === "json") res = await jsonToTable(bytes, m.name, opts, progress);
      else if (pair.work === "tiff") res = await tiffToImages(bytes, m.name, opts, pair.maxPixels, progress);
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
