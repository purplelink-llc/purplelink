/* File converters core. Pure functions on Uint8Array and strings, no DOM, so the same file runs in the page, in
   convert-worker.js and under node for tests (netlify/tests/convert-core.test.mjs).
   Design: docs/designs/browser-file-converters.md. */
(function (root) {
  "use strict";

  const MAX_BYTES = 100 * 1024 * 1024;
  const MAX_FILES = 200;
  // Decoded size caps, checked before a picture is decoded. RGBA is 4 bytes a pixel, so 100 MP is 400 MB before the
  // canvas and the encoded copy. Phones get the iOS Safari canvas limit (4096 x 4096).
  const MAX_PIXELS = 100e6;
  const MAX_PIXELS_MOBILE = 16777216;
  // PDF pages and SVGs are drawn on a canvas in the page itself, not in the worker, so they get a lower cap.
  const MAX_PIXELS_PAGE = 40e6;
  // "Download all" stops above this; past it a zip built in memory can take the tab down.
  const MAX_ZIP_BYTES = 1024 * 1024 * 1024;

  // One entry per page. The page's data-convert picks it. accepts are sniffed kinds, not extensions. work routes the
  // file in the worker: image (decode and re-encode), icon (resize into a container), pdf, sheet. canvas: the pair
  // draws pixels, so it needs OffscreenCanvas and createImageBitmap (JPG to PDF needs them only for PNG and odd JPEGs).
  const CONVERSIONS = {
    "heic-to-jpg": { label: "HEIC", accepts: ["heic"], outputs: ["jpg", "png"], output: "jpg", work: "image", canvas: true },
    "webp-to-png": { label: "WebP", accepts: ["webp"], outputs: ["png", "jpg"], output: "png", work: "image", canvas: true },
    "png-to-icns": { label: "PNG", accepts: ["png", "jpeg", "webp"], outputs: ["icns"], output: "icns", work: "icon", canvas: true },
    "png-to-ico": { label: "PNG", accepts: ["png", "jpeg", "webp"], outputs: ["ico"], output: "ico", work: "icon", canvas: true },
    // pdf-lib decodes a PNG again in JavaScript memory, so PNG pages get a lower pixel cap.
    "jpg-to-pdf": { label: "JPG", accepts: ["jpeg", "png"], outputs: ["pdf"], output: "pdf", work: "pdf", combine: true, maxPixels: 25e6 },
    "avif-to-jpg": { label: "AVIF", accepts: ["avif"], outputs: ["jpg", "png"], output: "jpg", work: "image", canvas: true },
    // The sheet is built in worker memory as XML several times the size of the CSV, hence the lower cap.
    "csv-to-xlsx": { label: "CSV", accepts: ["csv"], outputs: ["xlsx"], output: "xlsx", work: "sheet", maxBytes: 50 * 1024 * 1024 },
    // pdfpages and svg are drawn by the page (pdf.js and <img> cannot run in this worker); the worker encodes the pixels.
    "pdf-to-jpg": { label: "PDF", accepts: ["pdf"], outputs: ["jpg", "png"], output: "jpg", work: "pdfpages" },
    "svg-to-png": { label: "SVG", accepts: ["svg"], outputs: ["png", "jpg"], output: "png", work: "svg", maxBytes: 10 * 1024 * 1024 },
    "png-to-jpg": { label: "PNG", accepts: ["png", "gif", "bmp"], outputs: ["jpg"], output: "jpg", work: "image", canvas: true }
  };
  // A PDF with more pages than this is refused rather than drawn for minutes.
  const MAX_PDF_PAGES = 500;

  const MIME = {
    jpg: "image/jpeg", png: "image/png", icns: "image/icns", ico: "image/x-icon", pdf: "application/pdf",
    xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", zip: "application/zip"
  };
  const KIND_NAMES = { heic: "HEIC", avif: "AVIF", webp: "WebP", png: "PNG", jpeg: "JPEG", gif: "GIF", csv: "CSV", pdf: "PDF", bmp: "BMP", svg: "SVG" };

  function ascii(b, s, e) {
    let out = "";
    for (let i = s; i < e && i < b.length; i++) out += String.fromCharCode(b[i]);
    return out;
  }

  // mif1/msf1 are generic HEIF brands that AVIF files carry too, so AVIF brands are checked first.
  const HEIF_BRANDS = ["heic", "heix", "heim", "heis", "hevc", "hevx", "hevm", "hevs", "mif1", "msf1", "mif2"];
  const AVIF_BRANDS = ["avif", "avis"];

  /** What a file is, from its first bytes: "heic", "avif", "webp", "png", "jpeg", "gif", "bmp", "pdf" or "". */
  function sniff(b) {
    if (!b || b.length < 12) return "";
    if (b[0] === 0x89 && ascii(b, 1, 4) === "PNG") return "png";
    if (b[0] === 0xff && b[1] === 0xd8 && b[2] === 0xff) return "jpeg";
    if (ascii(b, 0, 4) === "RIFF" && ascii(b, 8, 12) === "WEBP") return "webp";
    if (ascii(b, 0, 4) === "GIF8") return "gif";
    // BMP: "BM", then a DIB header whose size is one of the known versions (OS/2 1, Windows 3 to 5, and the two v2/v3).
    if (b[0] === 0x42 && b[1] === 0x4d && b.length >= 18 && [12, 40, 52, 56, 64, 108, 124].indexOf(b[14] | (b[15] << 8) | (b[16] << 16) | (b[17] << 24)) !== -1) return "bmp";
    // PDF readers accept the header anywhere in the first 1 KB (some files start with junk from a mail gateway).
    if (ascii(b, 0, Math.min(b.length, 1024)).indexOf("%PDF-") !== -1) return "pdf";
    if (ascii(b, 4, 8) === "ftyp") {
      const size = ((b[0] << 24) | (b[1] << 16) | (b[2] << 8) | b[3]) >>> 0;
      const end = Math.min(size >= 16 ? size : 16, b.length, 256);
      const brands = [ascii(b, 8, 12)];
      for (let i = 16; i + 4 <= end; i += 4) brands.push(ascii(b, i, i + 4));
      if (brands.some(function (x) { return AVIF_BRANDS.indexOf(x) !== -1; })) return "avif";
      if (brands.some(function (x) { return HEIF_BRANDS.indexOf(x) !== -1; })) return "heic";
    }
    return "";
  }

  /** Like sniff, plus "svg" for SVG text (or gzip named .svgz) and "csv" for a text file named .csv, .tsv or .txt:
      no NUL byte in the head, or a UTF-16 BOM. */
  function kindOf(b, name) {
    const k = sniff(b);
    if (k) return k;
    if (b && b.length > 2 && b[0] === 0x1f && b[1] === 0x8b && /\.svgz$/i.test(String(name || ""))) return "svg";
    if (isSvgText(b)) return "svg";
    if (!/\.(csv|tsv|txt|tab)$/i.test(String(name || ""))) return k;
    if (b && b.length >= 2 && ((b[0] === 0xff && b[1] === 0xfe) || (b[0] === 0xfe && b[1] === 0xff))) return "csv";
    for (let i = 0; b && i < b.length && i < 4096; i++) if (b[i] === 0) return "";
    return b && b.length ? "csv" : "";
  }

  /** True when the head of a file is SVG text: an <svg element before any other element, after an optional BOM,
      XML declaration, comments and doctype. */
  function isSvgText(b) {
    if (!b || b.length < 5) return false;
    let t = "";
    for (let i = 0; i < b.length && i < 4096; i++) { if (b[i] === 0) return false; t += String.fromCharCode(b[i]); }
    t = t.replace(/^\xef\xbb\xbf/, "").replace(/<\?xml[\s\S]*?\?>|<!--[\s\S]*?-->|<!DOCTYPE[^>[]*(\[[\s\S]*?\])?\s*>/gi, "").replace(/^\s+/, "");
    return /^<(svg:)?svg[\s>/]/i.test(t);
  }

  // "an SVG", "an AVIF", "a PNG": by how the name is said, not how it is spelled.
  function article(name) { return (/^(AVIF|SVG)\b/.test(name) ? "an " : "a ") + name; }

  /** The message for a file this page cannot take, or "" when it can. */
  function refuse(pair, kind, size) {
    const c = CONVERSIONS[pair];
    if (!c) return "This page does not know that conversion.";
    const max = c.maxBytes || MAX_BYTES;
    if (size === 0) return "That file is empty.";
    if (size > max) return "That file is over " + (max / 1048576) + " MB.";
    if (c.accepts.indexOf(kind) !== -1) return "";
    const want = c.accepts.map(function (k) { return KIND_NAMES[k]; }).join(", ").replace(/, ([^,]*)$/, " or $1");
    return kind ? "This is " + article(KIND_NAMES[kind]) + " file, not " + want + "." : "This is not " + article(want) + " file, or it is damaged.";
  }

  /** The message for a picture too large to decode here, or "". */
  function tooManyPixels(width, height, mobile, max) {
    const cap = Math.min(mobile ? MAX_PIXELS_MOBILE : MAX_PIXELS, max || Infinity);
    if (width * height <= cap) return "";
    const mp = Math.round(width * height / 1e6);
    return mobile
      ? "This picture is " + mp + " megapixels, more than a phone browser can draw. Convert it on a computer."
      : "This picture is " + mp + " megapixels, more than this page converts (" + (cap / 1e6) + " MP).";
  }

  /** photo.HEIC -> photo.jpg. Drops any folder part and the characters some file systems refuse. */
  function outName(name, ext) {
    let base = String(name || "file").split(/[\\/]/).pop();
    base = base.replace(/\.[^.]{1,5}$/, "").replace(/[\u0000-\u001f<>:"|?*]+/g, "_").trim() || "file";
    return base + "." + ext;
  }

  /** De-duplicate names in order: photo.jpg, photo (2).jpg, photo (3).jpg. Case-insensitive, as on macOS. */
  function uniqueNames(names) {
    const seen = {};
    return names.map(function (n) {
      const key = n.toLowerCase();
      if (!seen[key]) { seen[key] = 1; return n; }
      let i = seen[key];
      let candidate, ck;
      do {
        i++;
        const dot = n.lastIndexOf(".");
        candidate = dot > 0 ? n.slice(0, dot) + " (" + i + ")" + n.slice(dot) : n + " (" + i + ")";
        ck = candidate.toLowerCase();
      } while (seen[ck]);
      seen[key] = i;
      seen[ck] = 1;
      return candidate;
    });
  }

  function formatBytes(n) {
    if (n < 1024) return n + " B";
    if (n < 1048576) return (n / 1024).toFixed(n < 10240 ? 1 : 0) + " KB";
    return (n / 1048576).toFixed(1) + " MB";
  }

  // ---------- ICNS ----------
  // Each type holds a PNG. The ten types match the ten files of an .iconset, which is what Apple's iconutil writes
  // (it uses ic04/ic05 for 16 and 32 px; icp4/icp5 are their PNG forms). icp6 is left out: iconutil reads it as
  // 48 px, and 64 px is already ic12, 32 at 2x. Pixel sizes repeat (32 is icp5 and ic11), so each is drawn once.
  const ICNS_TYPES = [
    ["icp4", 16], ["icp5", 32], ["ic07", 128], ["ic08", 256], ["ic09", 512], ["ic10", 1024],
    ["ic11", 32], ["ic12", 64], ["ic13", 256], ["ic14", 512]
  ];
  const ICNS_SIZES = [16, 32, 64, 128, 256, 512, 1024];
  // The names iconutil expects inside a .iconset folder.
  const ICONSET = [
    ["icon_16x16.png", 16], ["icon_16x16@2x.png", 32], ["icon_32x32.png", 32], ["icon_32x32@2x.png", 64],
    ["icon_128x128.png", 128], ["icon_128x128@2x.png", 256], ["icon_256x256.png", 256], ["icon_256x256@2x.png", 512],
    ["icon_512x512.png", 512], ["icon_512x512@2x.png", 1024]
  ];

  function u32be(out, at, v) {
    out[at] = (v >>> 24) & 255; out[at + 1] = (v >>> 16) & 255; out[at + 2] = (v >>> 8) & 255; out[at + 3] = v & 255;
  }
  function readU32be(b, at) { return ((b[at] << 24) | (b[at + 1] << 16) | (b[at + 2] << 8) | b[at + 3]) >>> 0; }

  /** pngs: { 16: Uint8Array, 32: ..., 1024: ... }. Writes every type whose size is present. */
  function buildIcns(pngs) {
    const entries = ICNS_TYPES.filter(function (t) { return pngs[t[1]]; });
    if (!entries.length) throw new Error("No icon sizes to write.");
    let total = 8;
    entries.forEach(function (t) { total += 8 + pngs[t[1]].length; });
    const out = new Uint8Array(total);
    out.set([0x69, 0x63, 0x6e, 0x73], 0); // "icns"
    u32be(out, 4, total);
    let at = 8;
    entries.forEach(function (t) {
      const data = pngs[t[1]];
      for (let i = 0; i < 4; i++) out[at + i] = t[0].charCodeAt(i);
      u32be(out, at + 4, 8 + data.length);
      out.set(data, at + 8);
      at += 8 + data.length;
    });
    return out;
  }

  /** [{ type, length, offset }] for an ICNS file; throws if the container is inconsistent. */
  function parseIcns(b) {
    if (ascii(b, 0, 4) !== "icns") throw new Error("Not an ICNS file.");
    const total = readU32be(b, 4);
    if (total !== b.length) throw new Error("ICNS length mismatch.");
    const out = [];
    let at = 8;
    while (at < total) {
      if (at + 8 > total) throw new Error("ICNS entry header truncated.");
      const len = readU32be(b, at + 4);
      if (len < 8 || at + len > total) throw new Error("ICNS entry length out of range.");
      out.push({ type: ascii(b, at, at + 4), length: len, offset: at + 8 });
      at += len;
    }
    return out;
  }

  /** Width and height from a PNG's IHDR, or null. */
  function pngSize(b) {
    if (sniff(b) !== "png" || b.length < 24 || ascii(b, 12, 16) !== "IHDR") return null;
    return { width: readU32be(b, 16), height: readU32be(b, 20) };
  }

  /** Sizes to pass through on the way down from `from` to `to`. One large step through a canvas skips source pixels
      and aliases; halving each time keeps a 4096 px source clean at 16 px. */
  function downscaleSteps(from, to) {
    const steps = [];
    let cur = from;
    while (cur / 2 >= to) { cur = Math.round(cur / 2); steps.push(cur); }
    if (cur !== to) steps.push(to);
    return steps;
  }

  /** Where a w x h picture sits inside a square icon: scaled to fit, centered, transparent around it. */
  function fitSquare(w, h, size) {
    const s = size / Math.max(w, h);
    const dw = Math.max(1, Math.round(w * s)), dh = Math.max(1, Math.round(h * s));
    return { x: Math.floor((size - dw) / 2), y: Math.floor((size - dh) / 2), width: dw, height: dh };
  }

  // ---------- ICO ----------
  // A 6-byte header, one 16-byte directory entry per size, then the images. Every entry is a PNG, which Windows Vista
  // and later, browsers and macOS read. Width and height are one byte each, so 256 is written as 0.
  const ICO_SETS = { all: [16, 24, 32, 48, 64, 128, 256], favicon: [16, 32, 48] };

  function u16le(out, at, v) { out[at] = v & 255; out[at + 1] = (v >>> 8) & 255; }
  function u32le(out, at, v) { out[at] = v & 255; out[at + 1] = (v >>> 8) & 255; out[at + 2] = (v >>> 16) & 255; out[at + 3] = (v >>> 24) & 255; }
  function readU16le(b, at) { return b[at] | (b[at + 1] << 8); }
  function readU32le(b, at) { return (b[at] | (b[at + 1] << 8) | (b[at + 2] << 16) | (b[at + 3] << 24)) >>> 0; }

  /** pngs: { 16: Uint8Array, ... }; sizes: the sizes to write, in order. */
  function buildIco(pngs, sizes) {
    const list = sizes.filter(function (s) { return pngs[s]; });
    if (!list.length) throw new Error("No icon sizes to write.");
    let total = 6 + 16 * list.length;
    list.forEach(function (s) { total += pngs[s].length; });
    const out = new Uint8Array(total);
    u16le(out, 2, 1); // type 1: icon
    u16le(out, 4, list.length);
    let off = 6 + 16 * list.length;
    list.forEach(function (s, i) {
      const at = 6 + 16 * i, data = pngs[s];
      out[at] = s >= 256 ? 0 : s; out[at + 1] = s >= 256 ? 0 : s;
      u16le(out, at + 4, 1); // planes
      u16le(out, at + 6, 32); // bits per pixel
      u32le(out, at + 8, data.length);
      u32le(out, at + 12, off);
      out.set(data, off);
      off += data.length;
    });
    return out;
  }

  /** [{ width, height, length, offset }] for an ICO file; throws if the directory is inconsistent. */
  function parseIco(b) {
    if (b.length < 6 || readU16le(b, 0) !== 0 || readU16le(b, 2) !== 1) throw new Error("Not an ICO file.");
    const n = readU16le(b, 4);
    if (!n || 6 + 16 * n > b.length) throw new Error("ICO directory truncated.");
    const out = [];
    let expect = 6 + 16 * n;
    for (let i = 0; i < n; i++) {
      const at = 6 + 16 * i, len = readU32le(b, at + 8), off = readU32le(b, at + 12);
      if (off !== expect || off + len > b.length) throw new Error("ICO entry out of range.");
      out.push({ width: b[at] || 256, height: b[at + 1] || 256, length: len, offset: off });
      expect = off + len;
    }
    if (expect !== b.length) throw new Error("ICO length mismatch.");
    return out;
  }

  // ---------- JPEG and PDF ----------
  const SOF = [0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf];

  /** { width, height, components, orientation } from a JPEG's markers, without decoding it; null if unreadable. */
  function jpegInfo(b) {
    if (sniff(b) !== "jpeg") return null;
    let at = 2, orientation = 1, info = null, adobe = false, dpi = 0;
    while (at + 4 <= b.length) {
      if (b[at] !== 0xff) { at++; continue; }
      const m = b[at + 1];
      if (m === 0xff) { at++; continue; }
      if (m === 0xd8 || (m >= 0xd0 && m <= 0xd7) || m === 0x01) { at += 2; continue; }
      if (m === 0xd9 || m === 0xda) break; // end of image, start of scan: the header is over
      const len = (b[at + 2] << 8) | b[at + 3];
      if (len < 2) return null;
      const seg = at + 4;
      if (m === 0xe1 && ascii(b, seg, seg + 4) === "Exif" && !info) orientation = exifOrientation(b, seg + 6, seg + len - 2) || orientation;
      if (m === 0xee && ascii(b, seg, seg + 5) === "Adobe") adobe = true;
      // JFIF density in dots per inch (units 1), used to size a scanned page; dots per cm (units 2) converted.
      if (m === 0xe0 && ascii(b, seg, seg + 5) === "JFIF\u0000" && seg + 12 <= b.length) {
        const units = b[seg + 7], x = (b[seg + 8] << 8) | b[seg + 9];
        dpi = units === 1 ? x : units === 2 ? Math.round(x * 2.54) : 0;
      }
      if (SOF.indexOf(m) !== -1 && seg + 6 <= b.length && !info) {
        info = { sof: m, precision: b[seg], height: (b[seg + 1] << 8) | b[seg + 2], width: (b[seg + 3] << 8) | b[seg + 4], components: b[seg + 5] };
      }
      at = seg + len - 2;
    }
    if (!info || !info.width || !info.height) return null;
    info.orientation = orientation;
    info.adobe = adobe;
    info.dpi = dpi >= 72 && dpi <= 2400 ? dpi : 0;
    // PDF readers take baseline and progressive 8-bit JPEGs in gray, RGB, or CMYK as Adobe writes it (pdf-lib sets the
    // inverted Decode array every CMYK JPEG gets). Anything else is drawn by the browser and re-encoded instead.
    info.embeddable = [0xc0, 0xc1, 0xc2].indexOf(info.sof) !== -1 && info.precision === 8 &&
      (info.components === 1 || info.components === 3 || (info.components === 4 && adobe));
    return info;
  }

  function exifOrientation(b, tiff, end) {
    if (tiff + 8 > end) return 0;
    const le = b[tiff] === 0x49;
    const r16 = function (at) { return le ? b[at] | (b[at + 1] << 8) : (b[at] << 8) | b[at + 1]; };
    const r32 = function (at) { return le ? readU32le(b, at) : readU32be(b, at); };
    const ifd = tiff + r32(tiff + 4);
    if (ifd + 2 > end) return 0;
    const n = r16(ifd);
    for (let i = 0; i < n; i++) {
      const e = ifd + 2 + 12 * i;
      if (e + 12 > end) return 0;
      if (r16(e) === 0x0112) { const v = r16(e + 8); return v >= 1 && v <= 8 ? v : 0; }
    }
    return 0;
  }

  /** Orientations 5 to 8 turn the picture a quarter, so its displayed width is its stored height. */
  function displaySize(w, h, orientation) { return orientation >= 5 ? { width: h, height: w } : { width: w, height: h }; }

  /** The PDF matrix [a b c d e f] that draws a stored image (the unit square) upright into a box of the displayed
      width W and height H at x, y, for EXIF orientation 1 to 8. */
  function pdfMatrix(orientation, W, H, x, y) {
    const m = {
      1: [W, 0, 0, H, 0, 0], 2: [-W, 0, 0, H, W, 0], 3: [-W, 0, 0, -H, W, H], 4: [W, 0, 0, -H, 0, H],
      5: [0, -H, -W, 0, W, H], 6: [0, -H, W, 0, 0, H], 7: [0, H, W, 0, 0, 0], 8: [0, H, -W, 0, W, 0]
    }[orientation] || [W, 0, 0, H, 0, 0];
    return [m[0], m[1], m[2], m[3], m[4] + (x || 0), m[5] + (y || 0)];
  }

  const PAGES = { a4: [595.28, 841.89], letter: [612, 792] };
  const MARGIN = 34.02; // 12 mm in points
  const MAX_PAGE = 14400; // PDF's page size limit, 200 inches

  /** Page size and where the picture sits on it, in points. dw, dh: the displayed size in pixels; dpi: the density
      stored in the file, or 0. */
  function pageLayout(page, margin, dw, dh, dpi) {
    if (!PAGES[page]) {
      // Fit to picture: the stored density if there is one (a 300 dpi scan of A4 gives an A4 page), else 96 pixels to
      // the inch, shrunk to PDF's size limit if needed.
      const k = Math.min(72 / (dpi || 96), MAX_PAGE / Math.max(dw, dh));
      const pw = Math.max(1, dw * k), ph = Math.max(1, dh * k);
      return { width: pw, height: ph, x: 0, y: 0, w: pw, h: ph };
    }
    let pw = PAGES[page][0], ph = PAGES[page][1];
    if (dw > dh) { const t = pw; pw = ph; ph = t; }
    const m = margin ? MARGIN : 0;
    const s = Math.min((pw - 2 * m) / dw, (ph - 2 * m) / dh);
    const w = dw * s, h = dh * s;
    return { width: pw, height: ph, x: (pw - w) / 2, y: (ph - h) / 2, w: w, h: h };
  }

  // ---------- CSV and XLSX ----------
  const XLSX_ROWS = 1048576, XLSX_COLS = 16384, XLSX_CELL = 32767;
  // Parsed rows and the sheet XML both sit in worker memory; past this many cells a tab runs out on a laptop.
  const MAX_CELLS = 5e6;

  const ENCODINGS = { "utf-8": "UTF-8", "windows-1252": "Windows-1252", "iso-8859-2": "ISO-8859-2", "shift_jis": "Shift JIS",
    "gb18030": "GB18030", "utf-16le": "UTF-16" };

  /** { text, encoding } from a text file's bytes: BOM first, then strict UTF-8, then Windows-1252. forced: a key of
      ENCODINGS, used as is. */
  function decodeText(b, forced) {
    if (ENCODINGS[forced]) {
      const t = new TextDecoder(forced).decode(b);
      return { text: t.charCodeAt(0) === 0xfeff ? t.slice(1) : t, encoding: ENCODINGS[forced] };
    }
    if (b.length >= 3 && b[0] === 0xef && b[1] === 0xbb && b[2] === 0xbf) return { text: new TextDecoder("utf-8").decode(b.subarray(3)), encoding: "UTF-8" };
    if (b.length >= 2 && b[0] === 0xff && b[1] === 0xfe) return { text: new TextDecoder("utf-16le").decode(b.subarray(2)), encoding: "UTF-16" };
    if (b.length >= 2 && b[0] === 0xfe && b[1] === 0xff) return { text: new TextDecoder("utf-16be").decode(b.subarray(2)), encoding: "UTF-16" };
    try { return { text: new TextDecoder("utf-8", { fatal: true }).decode(b), encoding: "UTF-8" }; } catch (e) { /* not UTF-8 */ }
    return { text: new TextDecoder("windows-1252").decode(b), encoding: "Windows-1252" };
  }

  const DELIMS = { comma: ",", semicolon: ";", tab: "\t", pipe: "|" };

  /** The delimiter whose count per line, outside quotes, is most often the same and above zero, in the first 50 lines. */
  function detectDelimiter(text, name) {
    const lines = [];
    let cur = "", q = false;
    for (let i = 0; i < text.length && lines.length < 50; i++) {
      const ch = text[i];
      if (ch === '"') q = !q;
      if (!q && (ch === "\n" || ch === "\r")) { if (cur) lines.push(cur); cur = ""; continue; }
      if (!q) cur += ch; else if (ch !== '"') cur += " "; // quoted content cannot hold a delimiter
    }
    if (cur && lines.length < 50) lines.push(cur);
    let best = ",", bestScore = -1;
    const order = /\.(tsv|tab)$/i.test(String(name || "")) ? ["\t", ",", ";", "|"] : [",", ";", "\t", "|"];
    order.forEach(function (d) {
      const counts = {};
      lines.forEach(function (l) { const c = l.split(d).length - 1; if (c) counts[c] = (counts[c] || 0) + 1; });
      const score = Math.max.apply(null, [0].concat(Object.keys(counts).map(function (k) { return counts[k]; })));
      if (score > bestScore) { best = d; bestScore = score; }
    });
    return best;
  }

  /** RFC 4180 rows: quoted fields, "" escapes, newlines in quotes, CRLF, LF or CR line ends. */
  function parseCsv(text, d) {
    const rows = [];
    let row = [], field = "", i = 0, q = false, quoted = false;
    const n = text.length;
    while (i < n) {
      const ch = text[i];
      if (q) {
        if (ch === '"') {
          if (text[i + 1] === '"') { field += '"'; i += 2; continue; }
          q = false; i++; continue;
        }
        field += ch; i++; continue;
      }
      if (ch === '"' && field === "" && !quoted) { q = true; quoted = true; i++; continue; }
      if (ch === d) { row.push(field); field = ""; quoted = false; i++; continue; }
      if (ch === "\n" || ch === "\r") {
        row.push(field); rows.push(row); row = []; field = ""; quoted = false;
        i += ch === "\r" && text[i + 1] === "\n" ? 2 : 1;
        continue;
      }
      field += ch; i++;
    }
    if (field !== "" || quoted || row.length) { row.push(field); rows.push(row); }
    rows.unclosed = q; // a quote opened and never closed swallowed the rest of the file
    return rows;
  }

  const NUMBER = /^-?(?:0|[1-9]\d*)(?:\.\d+)?$/;
  // Scientific notation only with a decimal point or a signed exponent (1.5e-3, 2E+5), so part numbers and gene names
  // such as 12E3 or 2E5 stay text.
  const SCIENTIFIC = /^-?(?:0|[1-9]\d*)(?:\.\d+[eE][+-]?\d{1,3}|[eE][+-]\d{1,3})$/;
  const DECIMAL_COMMA = /^-?(?:0|[1-9]\d*),\d+$/;

  /** A number for a value in plain decimal notation, else null. Leading zeros (02134), a leading +, thousands
      separators and dates stay text, and so do integers of 12 digits or more (IDs and card numbers, which Excel would
      show as 1.23457E+11) and anything past Excel's 15 significant digits. */
  function cellNumber(s, delim) {
    let t = s;
    if (delim === ";" && DECIMAL_COMMA.test(t)) t = t.replace(",", ".");
    if (!NUMBER.test(t) && !SCIENTIFIC.test(t)) return null;
    const mantissa = t.replace(/[eE].*$/, "");
    if (mantissa.indexOf(".") === -1 && mantissa.replace("-", "").length >= 12) return null;
    const digits = mantissa.replace(/[-.]/g, "").replace(/^0+/, "");
    if (digits.length > 15) return null;
    const v = Number(t);
    return isFinite(v) ? v : null;
  }

  function colName(i) {
    let s = "";
    for (i++; i > 0; i = Math.floor((i - 1) / 26)) s = String.fromCharCode(65 + ((i - 1) % 26)) + s;
    return s;
  }

  function xml(s) {
    return String(s).replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f￾￿]/g, "")
      .replace(/[\ud800-\udbff](?![\udc00-\udfff])|(^|[^\ud800-\udbff])[\udc00-\udfff]/g, "$1")
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  /** A sheet name Excel accepts: 31 characters at most, none of []:*?/\, no apostrophe at either end, not empty,
      and not History, which Excel reserves. */
  function sheetName(name) {
    const base = String(name || "").split(/[\\/]/).pop().replace(/\.[^.]{1,5}$/, "").replace(/[\[\]:*?\/\\]/g, " ").trim();
    const out = base.slice(0, 31).replace(/^['\s]+|['\s]+$/g, "") || "Sheet1";
    return out.toLowerCase() === "history" ? "History 1" : out;
  }

  /** { parts: { path: xml }, notes, rows, cols } for an .xlsx of one sheet. The sheet part is an array of chunks (a
      Blob is made from it in the worker, so the whole sheet never has to be one string); the rest are strings. In
      [Content_Types].xml order, first, which some readers expect. opts: header, text, delimiter (the character). */
  function buildXlsxParts(rows, fileName, opts) {
    opts = opts || {};
    if (rows.length > XLSX_ROWS) throw new Error("This file has " + rows.length.toLocaleString("en-US") + " rows. Excel holds at most 1,048,576.");
    let cols = 0, cut = 0, cells = 0;
    rows.forEach(function (r) { if (r.length > cols) cols = r.length; cells += r.length; });
    if (cols > XLSX_COLS) throw new Error("This file has " + cols.toLocaleString("en-US") + " columns. Excel holds at most 16,384.");
    if (cells > MAX_CELLS) throw new Error("This file has " + cells.toLocaleString("en-US") + " cells, more than this page builds in a browser tab (" + (MAX_CELLS / 1e6) + " million). Split it, or open it in Excel directly.");
    const widths = [];
    const body = [];
    let chunk = [];
    for (let r = 0; r < rows.length; r++) {
      const row = rows[r], out = [];
      for (let c = 0; c < row.length; c++) {
        let v = row[c];
        if (v === "") continue;
        if (v.length > XLSX_CELL) { v = v.slice(0, XLSX_CELL); cut++; }
        if (r < 1000) widths[c] = Math.max(widths[c] || 0, v.length);
        const ref = colName(c) + (r + 1);
        const head = opts.header && r === 0;
        const num = head || opts.text ? null : cellNumber(v, opts.delimiter);
        const style = head ? ' s="1"' : /[\r\n]/.test(v) ? ' s="2"' : "";
        out.push(num !== null
          ? '<c r="' + ref + '"><v>' + num + "</v></c>"
          : '<c r="' + ref + '"' + style + ' t="inlineStr"><is><t xml:space="preserve">' + xml(v) + "</t></is></c>");
      }
      chunk.push('<row r="' + (r + 1) + '">' + out.join("") + "</row>");
      if (chunk.length === 1000) { body.push(chunk.join("")); chunk = []; }
    }
    if (chunk.length) body.push(chunk.join(""));
    const colsXml = widths.length ? "<cols>" + widths.map(function (w, i) {
      return '<col min="' + (i + 1) + '" max="' + (i + 1) + '" width="' + Math.min(60, Math.max(8, (w || 0) + 2)) + '" customWidth="1"/>';
    }).join("") + "</cols>" : "";
    const pane = opts.header && rows.length > 1
      ? '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
      : '<sheetViews><sheetView workbookViewId="0"/></sheetViews>';
    const dim = rows.length && cols ? "A1:" + colName(cols - 1) + rows.length : "A1";
    const NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"';
    const R = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"';
    const head = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n';
    const parts = {
      "[Content_Types].xml": head + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">' +
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>' +
        '<Default Extension="xml" ContentType="application/xml"/>' +
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>' +
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' +
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>' +
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>' +
        "</Types>",
      "_rels/.rels": head + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>' +
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>' +
        "</Relationships>",
      "docProps/app.xml": head + '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>Purplelink CSV to XLSX</Application></Properties>',
      "xl/workbook.xml": head + "<workbook " + NS + " " + R + '><sheets><sheet name="' + xml(sheetName(fileName)) + '" sheetId="1" r:id="rId1"/></sheets></workbook>',
      "xl/_rels/workbook.xml.rels": head + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>' +
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>' +
        "</Relationships>",
      "xl/styles.xml": head + "<styleSheet " + NS + ">" +
        '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>' +
        '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>' +
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>' +
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>' +
        // 0 normal, 1 bold header, 2 wrapped (a cell with a line break)
        '<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>' +
        '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>' +
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf></cellXfs>' +
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>' +
        "</styleSheet>",
      "xl/worksheets/sheet1.xml": [head + "<worksheet " + NS + " " + R + '><dimension ref="' + dim + '"/>' + pane + colsXml + "<sheetData>"]
        .concat(body, ["</sheetData></worksheet>"])
    };
    const notes = [];
    if (cut) notes.push(cut + " cell" + (cut > 1 ? "s were" : " was") + " longer than Excel's 32,767 characters and " + (cut > 1 ? "were" : "was") + " cut there.");
    return { parts: parts, notes: notes, rows: rows.length, cols: cols };
  }

  /** Options as the page sends them, cleaned. */
  // ---------- PDF to JPG ----------
  const DPIS = { "72": 72, "150": 150, "300": 300 };

  /** "1-3, 8" -> [1, 2, 3, 8] for a PDF of count pages. Empty means every page. Returns { pages } or { error }. */
  function parsePages(text, count) {
    const t = String(text == null ? "" : text).trim();
    const all = [];
    if (!t) { for (let i = 1; i <= count; i++) all.push(i); return { pages: all }; }
    const seen = {};
    const parts = t.split(/\s*[,;]\s*/).filter(Boolean);
    for (let i = 0; i < parts.length; i++) {
      const m = /^(\d+)(?:\s*[-\u2013]\s*(\d*))?$/.exec(parts[i]);
      if (!m) return { error: "Pages should look like 1-3, 8. \u201c" + parts[i] + "\u201d is not a page or a range." };
      const a = Number(m[1]);
      const b = m[2] === undefined ? a : m[2] === "" ? count : Number(m[2]);
      if (a < 1 || b < a) return { error: "\u201c" + parts[i] + "\u201d is not a range of pages." };
      if (a > count) return { error: "This PDF has " + count + " page" + (count === 1 ? "" : "s") + ", so there is no page " + a + "." };
      for (let p = a; p <= Math.min(b, count); p++) if (!seen[p]) { seen[p] = 1; all.push(p); }
    }
    all.sort(function (x, y) { return x - y; });
    return { pages: all };
  }

  /** Pixel size of a page of w by h points drawn at dpi, shrunk to fit the page-side cap. dpi is what was used. */
  function pageRaster(w, h, dpi, mobile) {
    const cap = mobile ? MAX_PIXELS_MOBILE : MAX_PIXELS_PAGE;
    let k = dpi / 72;
    if (w * k * h * k > cap) k = Math.sqrt(cap / (w * h));
    return { width: Math.max(1, Math.floor(w * k)), height: Math.max(1, Math.floor(h * k)), scale: k, dpi: Math.round(k * 72) };
  }

  /** report.pdf, page 3 of 12 -> report-p003.jpg (digits enough for the page count, at least 3). */
  function pageName(name, page, count, ext) {
    const base = outName(name, ext).replace(/\.[^.]+$/, "");
    const digits = Math.max(3, String(count).length);
    return base + "-p" + String(page).padStart(digits, "0") + "." + ext;
  }

  // ---------- SVG to PNG ----------
  // CSS absolute units in px (96 per inch).
  const SVG_UNITS = { "": 1, px: 1, pt: 96 / 72, pc: 16, mm: 96 / 25.4, cm: 96 / 2.54, in: 96 };

  /** The root <svg ...> start tag, with where it starts and ends in text, or null. Skips comments and the prolog. */
  function svgRoot(text) {
    const re = /<!--[\s\S]*?-->|<\?[\s\S]*?\?>|<!DOCTYPE[^>[]*(\[[\s\S]*?\])?\s*>|<((?:svg:)?svg)(\s[^>]*?)?(\/?)>/gi;
    let m;
    while ((m = re.exec(text))) {
      if (m[2]) return { start: m.index, end: re.lastIndex, name: m[2], attrs: m[3] || "", selfClose: m[4] === "/" };
    }
    return null;
  }

  function svgAttr(attrs, name) {
    const m = new RegExp("(?:^|\\s)" + name + "\\s*=\\s*(\"([^\"]*)\"|'([^']*)')", "i").exec(attrs);
    return m ? (m[2] !== undefined ? m[2] : m[3]) : null;
  }

  function svgLength(v) {
    if (v == null) return 0;
    const m = /^\s*([0-9]*\.?[0-9]+(?:e[-+]?\d+)?)\s*(px|pt|pc|mm|cm|in)?\s*$/i.exec(v);
    if (!m) return 0; // percentages, em and the like fall back to the viewBox
    return Number(m[1]) * SVG_UNITS[(m[2] || "").toLowerCase()];
  }

  /** SVG bytes to text: a BOM wins, then the encoding the XML declaration names, then UTF-8. */
  function svgDecode(b) {
    let label = "utf-8";
    if (b.length >= 2 && b[0] === 0xff && b[1] === 0xfe) label = "utf-16le";
    else if (b.length >= 2 && b[0] === 0xfe && b[1] === 0xff) label = "utf-16be";
    else if (!(b.length >= 3 && b[0] === 0xef && b[1] === 0xbb && b[2] === 0xbf)) {
      const m = /^\s*<\?xml[^>]*?encoding\s*=\s*["']([A-Za-z0-9._-]+)["']/.exec(ascii(b, 0, 200));
      if (m) label = m[1].toLowerCase();
    }
    try { return new TextDecoder(label).decode(b); } catch (e) { return new TextDecoder("utf-8").decode(b); }
  }

  /** The size an SVG asks to be drawn at, in CSS px: { width, height, viewBox, from } or null when there is no root. */
  function svgSize(text) {
    const r = svgRoot(text);
    if (!r) return null;
    const vbRaw = svgAttr(r.attrs, "viewBox");
    let vb = null;
    if (vbRaw) {
      const n = vbRaw.trim().split(/[\s,]+/).map(Number);
      if (n.length === 4 && n.every(isFinite) && n[2] > 0 && n[3] > 0) vb = n;
    }
    let w = svgLength(svgAttr(r.attrs, "width")), h = svgLength(svgAttr(r.attrs, "height"));
    let from = "size";
    if (w && !h) h = vb ? w * vb[3] / vb[2] : 150;
    else if (h && !w) w = vb ? h * vb[2] / vb[3] : 300;
    else if (!w && !h) {
      if (vb) { w = vb[2]; h = vb[3]; from = "viewBox"; } else { w = 300; h = 150; from = "default"; }
    }
    return { width: w, height: h, viewBox: vb, from: from };
  }

  /** The SVG text with its root width and height set to w by h pixels and a viewBox kept or added, so the drawing
      scales as a vector. */
  function svgWithSize(text, w, h) {
    const r = svgRoot(text);
    if (!r) return text;
    const size = svgSize(text);
    let attrs = r.attrs.replace(/(^|\s)(width|height)\s*=\s*("[^"]*"|'[^']*')/gi, "");
    if (!size.viewBox) attrs += ' viewBox="0 0 ' + round4(size.width) + " " + round4(size.height) + '"';
    attrs += ' width="' + w + '" height="' + h + '"';
    const tag = "<" + r.name + " " + attrs.replace(/^\s+/, "") + (r.selfClose ? "/>" : ">");
    return text.slice(0, r.start) + tag + text.slice(r.end);
  }
  function round4(n) { return Math.round(n * 1e4) / 1e4; }

  /** Notes for things an SVG drawn as an image cannot show: images from the web and web fonts. */
  function svgNotes(text) {
    const notes = [];
    if (/[\s:]href\s*=\s*["']\s*(https?:)?\/\//i.test(text)) notes.push("This SVG links to images on the web. A browser does not load those when it draws an SVG as a picture, so they are missing.");
    if (/@import|@font-face[^}]*url\(\s*["']?\s*(https?:)?\/\//i.test(text)) notes.push("This SVG asks for web fonts, which are not loaded when it is drawn as a picture. Its text uses fonts installed on this device.");
    return notes;
  }

  /** Output pixel size for an SVG of w by h CSS px: scale "1", "2", "4", or "width" with a width in pixels. */
  function svgOutSize(w, h, scale, width) {
    if (scale === "width") {
      const W = Math.round(width);
      return { width: W, height: Math.max(1, Math.round(h * W / w)) };
    }
    const k = Number(scale) || 2;
    return { width: Math.max(1, Math.round(w * k)), height: Math.max(1, Math.round(h * k)) };
  }

  function options(pair, raw) {
    const c = CONVERSIONS[pair];
    raw = raw || {};
    const output = c && c.outputs.indexOf(raw.output) !== -1 ? raw.output : (c ? c.output : "");
    let quality = Number(raw.quality);
    if (quality > 1) quality = quality / 100; // the slider sends 50 to 100
    if (!(quality >= 0.5 && quality <= 1)) quality = 0.92;
    const background = /^#[0-9a-f]{6}$/i.test(raw.background || "") ? raw.background.toLowerCase() : "#ffffff";
    return {
      output: output, quality: quality, background: background, iconset: bool(raw.iconset), mobile: bool(raw.mobile),
      sizes: ICO_SETS[raw.sizes] ? raw.sizes : "all",
      page: raw.page === "fit" || PAGES[raw.page] ? raw.page : "a4",
      margin: bool(raw.margin),
      delimiter: DELIMS[raw.delimiter] ? raw.delimiter : "auto",
      encoding: ENCODINGS[raw.encoding] ? raw.encoding : "auto",
      header: raw.header === undefined ? true : bool(raw.header),
      text: bool(raw.text),
      dpi: DPIS[raw.dpi] || 150,
      pages: String(raw.pages == null ? "" : raw.pages).slice(0, 200),
      scale: ["1", "2", "4", "width"].indexOf(String(raw.scale)) !== -1 ? String(raw.scale) : "2",
      width: Math.min(16384, Math.max(16, Math.round(Number(raw.width)) || 1920))
    };
  }

  function bool(v) { return v === true || v === "true" || v === "on" || v === 1; }

  const api = {
    MAX_BYTES: MAX_BYTES, MAX_FILES: MAX_FILES, MAX_PIXELS: MAX_PIXELS, MAX_PIXELS_MOBILE: MAX_PIXELS_MOBILE,
    MAX_ZIP_BYTES: MAX_ZIP_BYTES, CONVERSIONS: CONVERSIONS, MIME: MIME, KIND_NAMES: KIND_NAMES,
    ICNS_TYPES: ICNS_TYPES, ICNS_SIZES: ICNS_SIZES, ICONSET: ICONSET,
    sniff: sniff, refuse: refuse, tooManyPixels: tooManyPixels, outName: outName, uniqueNames: uniqueNames,
    formatBytes: formatBytes, buildIcns: buildIcns, parseIcns: parseIcns, pngSize: pngSize,
    downscaleSteps: downscaleSteps, fitSquare: fitSquare, options: options,
    kindOf: kindOf, ICO_SETS: ICO_SETS, buildIco: buildIco, parseIco: parseIco,
    jpegInfo: jpegInfo, displaySize: displaySize, pdfMatrix: pdfMatrix, pageLayout: pageLayout, PAGES: PAGES,
    decodeText: decodeText, ENCODINGS: ENCODINGS, DELIMS: DELIMS, MAX_CELLS: MAX_CELLS, detectDelimiter: detectDelimiter, parseCsv: parseCsv, cellNumber: cellNumber,
    colName: colName, sheetName: sheetName, buildXlsxParts: buildXlsxParts,
    MAX_PDF_PAGES: MAX_PDF_PAGES, MAX_PIXELS_PAGE: MAX_PIXELS_PAGE, svgRoot: svgRoot, DPIS: DPIS, parsePages: parsePages, pageRaster: pageRaster, pageName: pageName,
    isSvgText: isSvgText, svgDecode: svgDecode, svgSize: svgSize, svgWithSize: svgWithSize, svgNotes: svgNotes, svgOutSize: svgOutSize
  };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.Convert = api;
})(typeof self !== "undefined" ? self : this);
