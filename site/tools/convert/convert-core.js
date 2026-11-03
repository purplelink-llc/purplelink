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
    "png-to-jpg": { label: "PNG", accepts: ["png", "gif", "bmp"], outputs: ["jpg"], output: "jpg", work: "image", canvas: true },
    // A workbook's sheet XML unpacks to many times the file, and JSON.parse holds the whole tree, hence 50 MB.
    "xlsx-to-csv": { label: "XLSX", accepts: ["xlsx"], outputs: ["csv"], output: "csv", work: "unsheet", maxBytes: 50 * 1024 * 1024 },
    "json-to-csv": { label: "JSON", accepts: ["json"], outputs: ["csv", "xlsx"], output: "csv", work: "json", maxBytes: 50 * 1024 * 1024 },
    "tiff-to-jpg": { label: "TIFF", accepts: ["tiff"], outputs: ["jpg", "png"], output: "jpg", work: "tiff", canvas: true, maxPixels: 40e6 },
    "csv-to-json": { label: "CSV", accepts: ["csv"], outputs: ["json", "jsonl"], output: "json", work: "csvjson", maxBytes: 50 * 1024 * 1024 },
    // No canvas flag: PNG entries are copied out, so the worker checks for OffscreenCanvas only when it must draw.
    "icns-to-png": { label: "ICNS", accepts: ["icns"], outputs: ["png"], output: "png", work: "icns", maxBytes: 50 * 1024 * 1024 },
    "ico-to-png": { label: "ICO", accepts: ["ico"], outputs: ["png"], output: "png", work: "ico", maxBytes: 20 * 1024 * 1024 },
    "xlsx-to-json": { label: "XLSX", accepts: ["xlsx"], outputs: ["json", "jsonl"], output: "json", work: "xlsxread", maxBytes: 50 * 1024 * 1024 },
    "vtt-to-srt": { label: "WebVTT", accepts: ["vtt"], outputs: ["srt"], output: "srt", work: "subs", maxBytes: 5 * 1024 * 1024 },
    "srt-to-vtt": { label: "SRT", accepts: ["srt"], outputs: ["vtt"], output: "vtt", work: "subs", maxBytes: 5 * 1024 * 1024 }
  };
  // A PDF with more pages than this is refused rather than drawn for minutes.
  const MAX_PDF_PAGES = 500;

  const MIME = {
    jpg: "image/jpeg", png: "image/png", icns: "image/icns", ico: "image/x-icon", pdf: "application/pdf",
    xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", zip: "application/zip", csv: "text/csv",
    json: "application/json", jsonl: "application/x-ndjson",
    srt: "application/x-subrip", vtt: "text/vtt"
  };
  const KIND_NAMES = { heic: "HEIC", avif: "AVIF", webp: "WebP", png: "PNG", jpeg: "JPEG", gif: "GIF", csv: "CSV", pdf: "PDF", bmp: "BMP", svg: "SVG",
    xlsx: "XLSX", xls: "XLS", json: "JSON", tiff: "TIFF", bigtiff: "BigTIFF", icns: "ICNS", ico: "ICO", srt: "SRT", vtt: "WebVTT" };

  function ascii(b, s, e) {
    let out = "";
    for (let i = s; i < e && i < b.length; i++) out += String.fromCharCode(b[i]);
    return out;
  }

  // mif1/msf1 are generic HEIF brands that AVIF files carry too, so AVIF brands are checked first.
  const HEIF_BRANDS = ["heic", "heix", "heim", "heis", "hevc", "hevx", "hevm", "hevs", "mif1", "msf1", "mif2"];
  const AVIF_BRANDS = ["avif", "avis"];

  /** What a file is, from its first bytes: "heic", "avif", "webp", "png", "jpeg", "gif", "bmp", "pdf", "tiff",
      "bigtiff", "xls" or "". */
  function sniff(b) {
    if (!b || b.length < 12) return "";
    if (b[0] === 0x89 && ascii(b, 1, 4) === "PNG") return "png";
    if (b[0] === 0xff && b[1] === 0xd8 && b[2] === 0xff) return "jpeg";
    if (ascii(b, 0, 4) === "RIFF" && ascii(b, 8, 12) === "WEBP") return "webp";
    if (ascii(b, 0, 4) === "GIF8") return "gif";
    if ((b[0] === 0x49 && b[1] === 0x49 && b[2] === 0x2a && b[3] === 0) || (b[0] === 0x4d && b[1] === 0x4d && b[2] === 0 && b[3] === 0x2a)) return "tiff";
    if ((b[0] === 0x49 && b[1] === 0x49 && b[2] === 0x2b && b[3] === 0) || (b[0] === 0x4d && b[1] === 0x4d && b[2] === 0 && b[3] === 0x2b)) return "bigtiff";
    // An OLE compound file: the legacy .xls (and .doc) format.
    if (b[0] === 0xd0 && b[1] === 0xcf && b[2] === 0x11 && b[3] === 0xe0 && b[4] === 0xa1 && b[5] === 0xb1 && b[6] === 0x1a && b[7] === 0xe1) return "xls";
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
    // ICNS: the magic, a total of at least 16, and a first entry that fits inside it.
    if (ascii(b, 0, 4) === "icns") {
      const total = ((b[4] << 24) | (b[5] << 16) | (b[6] << 8) | b[7]) >>> 0, first = ((b[12] << 24) | (b[13] << 16) | (b[14] << 8) | b[15]) >>> 0;
      if (total >= 16 && first >= 8 && first <= total - 8) return "icns";
    }
    // ICO and CUR: 0 0 1 0 or 0 0 2 0 and a count of 1 to 255. Checked after the ftyp branch, since a HEIC or AVIF
    // ftyp box of 256 or 512 bytes starts with the same four bytes.
    if (b[0] === 0 && b[1] === 0 && (b[2] === 1 || b[2] === 2) && b[3] === 0 && ascii(b, 4, 8) !== "ftyp") {
      const n = b[4] | (b[5] << 8);
      if (n >= 1 && n <= 255 && b[6 + 12] !== undefined) return "ico";
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
    const n = String(name || "");
    const sub = subtitleKind(b, n);
    if (sub) return sub;
    // A workbook is a zip; its first entry name varies, so the extension decides between XLSX and other zips.
    if (b && b.length >= 4 && b[0] === 0x50 && b[1] === 0x4b && b[2] === 3 && b[3] === 4) return /\.xls[xm]$/i.test(n) ? "xlsx" : "";
    if (/\.(json|jsonl|ndjson|geojson)$/i.test(n) || (/\.txt$/i.test(n) && /^(\ufeff|\xef\xbb\xbf)?\s*[[{]/.test(ascii(b || [], 0, 64)))) {
      for (let i = 0; b && i < b.length && i < 4096; i++) if (b[i] === 0) return "";
      return b && b.length ? "json" : "";
    }
    if (!/\.(csv|tsv|txt|tab)$/i.test(n)) return k;
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
    // Step over the prolog (whitespace, comments, processing instructions, doctype) without rewriting the text; an
    // item cut off by the 4 KB head runs to the end, so nothing is mistaken for the root.
    const skip = /\s+|<!--[\s\S]*?(?:-->|$)|<\?[\s\S]*?(?:\?>|$)|<!DOCTYPE[^>[]*(?:\[[\s\S]*?\])?[^>]*(?:>|$)/iy;
    let at = t.startsWith("\xef\xbb\xbf") ? 3 : 0;
    for (;;) {
      skip.lastIndex = at;
      const m = skip.exec(t);
      if (!m || !m[0]) break;
      at = skip.lastIndex;
    }
    return /^<(svg:)?svg[\s>/]/i.test(t.slice(at));
  }

  // "an SVG", "an AVIF", "a PNG": by how the name is said, not how it is spelled.
  function article(name) { return (/^(AVIF|SVG|XLS|ICNS|ICO|SRT)\b/.test(name) ? "an " : "a ") + name; }

  /** "vtt" for text that starts WEBVTT (then a space, tab, line break or the end), "srt" for a .srt name or a head
      that is a cue number and an SRT timing line, or "". A UTF-16 file named .srt or .vtt takes that kind. */
  function subtitleKind(b, n) {
    if (!b || !b.length) return "";
    const utf16 = b.length >= 2 && ((b[0] === 0xff && b[1] === 0xfe) || (b[0] === 0xfe && b[1] === 0xff));
    if (utf16) return /\.vtt$/i.test(n) ? "vtt" : /\.srt$/i.test(n) ? "srt" : "";
    for (let i = 0; i < b.length && i < 4096; i++) if (b[i] === 0) return "";
    const head = ascii(b, b[0] === 0xef && b[1] === 0xbb && b[2] === 0xbf ? 3 : 0, 400);
    if (/^WEBVTT(?:[ \t\r\n]|$)/.test(head)) return "vtt";
    if (/\.srt$/i.test(n) || /^\s*\d+[ \t]*\r?\n[ \t]*(?:\d+:)?\d{1,2}:\d{2}[,.]\d{1,3}[ \t]*-->/.test(head)) return "srt";
    return "";
  }

  /** The message for a file this page cannot take, or "" when it can. */
  function refuse(pair, kind, size) {
    const c = CONVERSIONS[pair];
    if (!c) return "This page does not know that conversion.";
    if (kind === "xls" && c.accepts.indexOf("xlsx") !== -1) return "This is an older Excel workbook (.xls), or an .xlsx protected with a password. Save it as an unprotected .xlsx in Excel, Numbers or LibreOffice, and add that.";
    if (kind === "bigtiff" && c.accepts.indexOf("tiff") !== -1) return "This is a BigTIFF, a variant for files over 4 GB that this page cannot read.";
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
      "docProps/app.xml": head + '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>' + xml(opts.app || "Purplelink CSV to XLSX") + '</Application></Properties>',
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
  // ---------- XLSX to CSV: readers for the parts of a workbook (a worker has no DOMParser) ----------
  const XML_ENT = { lt: "<", gt: ">", amp: "&", quot: '"', apos: "'" };
  /** XML text to a string: entities, character references, and Excel's _xHHHH_ escapes for control characters. */
  function xmlText(t) {
    // XML turns a literal CR LF, or a lone CR, into LF before anything else; an escaped _x000D_ or &#13; stays a CR.
    return String(t).replace(/\r\n?/g, "\n")
      .replace(/&(#x[0-9a-f]+|#\d+|lt|gt|amp|quot|apos);/gi, function (m, e) {
        if (e[0] !== "#") return XML_ENT[e.toLowerCase()];
        const n = e[1] === "x" || e[1] === "X" ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10);
        return n > 0 && n <= 0x10ffff ? String.fromCodePoint(n) : m;
      })
      .replace(/_x([0-9A-Fa-f]{4})_/g, function (m, h) { return String.fromCharCode(parseInt(h, 16)); });
  }
  function xmlAttr(tag, name) {
    const m = new RegExp("\\s" + name + "\\s*=\\s*(?:\"([^\"]*)\"|'([^']*)')").exec(tag);
    return m ? xmlText(m[1] !== undefined ? m[1] : m[2]) : null;
  }

  /** xl/workbook.xml: the sheets in tab order and whether dates count from 1904. */
  function parseWorkbook(xml) {
    const sheets = [];
    const re = /<(?:\w+:)?sheet\b[^>]*\/?>/g;
    let m;
    while ((m = re.exec(xml))) {
      const t = m[0];
      sheets.push({ name: xmlAttr(t, "name") || "Sheet" + (sheets.length + 1), rid: xmlAttr(t, "r:id") || xmlAttr(t, "[\\w]+:id"), state: xmlAttr(t, "state") || "visible" });
    }
    const pr = /<(?:\w+:)?workbookPr\b[^>]*>/.exec(xml);
    const d = pr ? xmlAttr(pr[0], "date1904") : null;
    return { sheets: sheets, date1904: d === "1" || d === "true" };
  }

  /** A .rels part: id -> { target, type }. Targets are resolved against base ("xl/"). */
  function parseRels(xml, base) {
    const out = {};
    const re = /<Relationship\b[^>]*\/?>/g;
    let m;
    while ((m = re.exec(xml))) {
      const id = xmlAttr(m[0], "Id"), target = xmlAttr(m[0], "Target") || "";
      if (!id) continue;
      out[id] = { target: target[0] === "/" ? target.slice(1) : normPath((base || "") + target), type: (xmlAttr(m[0], "Type") || "").split("/").pop() };
    }
    return out;
  }
  function normPath(p) {
    const out = [];
    p.split("/").forEach(function (seg) { if (seg === "..") out.pop(); else if (seg && seg !== ".") out.push(seg); });
    return out.join("/");
  }

  /** xl/sharedStrings.xml: the strings in order. Rich-text runs are joined; phonetic guides (rPh) are left out. */
  function parseSharedStrings(xml) {
    const out = [];
    // The self-closing form goes first: otherwise "<si/>" opens a match that swallows the next string.
    const re = /<(?:\w+:)?si\b[^>]*?\/>|<(?:\w+:)?si\b[^>]*>([\s\S]*?)<\/(?:\w+:)?si>/g;
    let m;
    while ((m = re.exec(xml))) out.push(m[1] ? siText(m[1]) : "");
    return out;
  }
  function siText(inner) {
    const body = inner.replace(/<(?:\w+:)?rPh\b[\s\S]*?<\/(?:\w+:)?rPh>/g, "");
    let t = "";
    const re = /<(?:\w+:)?t\b[^>]*?\/>|<(?:\w+:)?t\b[^>]*>([\s\S]*?)<\/(?:\w+:)?t>/g;
    let m;
    while ((m = re.exec(body))) t += m[1] ? xmlText(m[1]) : "";
    return t;
  }

  // Built-in number formats that show a date or a time (ECMA-376 18.8.30, plus the East Asian date ids).
  const DATE_FMT_IDS = [14, 15, 16, 17, 18, 19, 20, 21, 22, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 45, 46, 47, 50, 51, 52, 53, 54, 55, 56, 57, 58];
  const TIME_ONLY_IDS = [18, 19, 20, 21, 45, 46, 47];
  /** What a number format code shows: "date", "datetime", "time" or "" (a plain number). */
  function fmtKind(code) {
    // Leave out quoted text, escaped characters and bracketed parts ([Red], [$-409]); elapsed [h] stays a duration.
    if (/\[[hms]+\]/i.test(code)) return "";
    const c = String(code).replace(/"[^"]*"|\\.|\[[^\]]*\]|_.|\*./g, "").split(";")[0];
    const date = /[dy]/i.test(c) || /m/i.test(c.replace(/h[^dy]*?m|m[^dy]*?s/gi, "")) && /[dy]/i.test(c);
    const time = /[hs]/i.test(c) || /AM\/PM|A\/P/i.test(c);
    return date && time ? "datetime" : date ? "date" : time ? "time" : "";
  }
  /** xl/styles.xml: for each cell style index (the s attribute), "date", "datetime", "time" or "". */
  function parseStyles(xml) {
    const custom = {};
    let m;
    const fre = /<(?:\w+:)?numFmt\b[^>]*\/?>/g;
    while ((m = fre.exec(xml))) custom[xmlAttr(m[0], "numFmtId")] = xmlAttr(m[0], "formatCode") || "";
    const xfs = /<(?:\w+:)?cellXfs\b[^>]*>([\s\S]*?)<\/(?:\w+:)?cellXfs>/.exec(xml);
    const out = [];
    if (!xfs) return out;
    const xre = /<(?:\w+:)?xf\b[^>]*>/g;
    while ((m = xre.exec(xfs[1]))) {
      const id = Number(xmlAttr(m[0], "numFmtId") || 0);
      if (custom[id] !== undefined) out.push(fmtKind(custom[id]));
      else out.push(DATE_FMT_IDS.indexOf(id) === -1 ? "" : TIME_ONLY_IDS.indexOf(id) !== -1 ? "time" : id === 22 ? "datetime" : "date");
    }
    return out;
  }

  /** An Excel date serial as ISO 8601. kind is "date", "datetime" or "time". */
  function excelDate(serial, kind, date1904) {
    if (!isFinite(serial)) return String(serial);
    let days = Math.floor(serial);
    let secs = Math.round((serial - days) * 86400);
    if (secs >= 86400) { days += 1; secs -= 86400; }
    const hms = pad2(Math.floor(secs / 3600)) + ":" + pad2(Math.floor(secs / 60) % 60) + ":" + pad2(secs % 60);
    if (kind === "time") return hms;
    // 1900 system: serial 1 is 1900-01-01, and Excel counts a 29 February 1900 that never was (serial 60).
    let ms;
    if (date1904) ms = Date.UTC(1904, 0, 1) + days * 864e5;
    else {
      if (days === 60) return kind === "datetime" ? "1900-02-29 " + hms : "1900-02-29";
      ms = Date.UTC(1899, 11, 31) + (days > 60 ? days - 1 : days) * 864e5;
    }
    const d = new Date(ms);
    if (isNaN(d.getTime())) return String(serial);
    const iso = d.getUTCFullYear() + "-" + pad2(d.getUTCMonth() + 1) + "-" + pad2(d.getUTCDate());
    return kind === "datetime" ? iso + " " + hms : iso;
  }
  function pad2(n) { return (n < 10 ? "0" : "") + n; }

  /** "C7" -> 2 (zero-based column), or -1. */
  function colIndex(ref) {
    const m = /^([A-Z]+)/i.exec(ref || "");
    if (!m) return -1;
    let n = 0;
    for (let i = 0; i < m[1].length; i++) n = n * 26 + (m[1].toUpperCase().charCodeAt(i) - 64);
    return n - 1;
  }

  /** A worksheet's XML to rows of strings. Cells and rows are placed by their references, so gaps stay empty.
      Returns { rows, formulasWithoutValue, cells }. Stops with an error past maxCells. */
  function sheetRows(xml, shared, styles, date1904, maxCells, safe, withKinds) {
    const rows = [], kinds = [];
    let lostFormulas = 0, cells = 0, nextRow = 0, slots = 0;
    const cap = maxCells || MAX_CELLS;
    const data = /<(?:\w+:)?sheetData\b[^>]*>([\s\S]*)<\/(?:\w+:)?sheetData>/.exec(xml);
    if (!data) return { rows: rows, formulasWithoutValue: 0, cells: 0 };
    const rre = /<(?:\w+:)?row\b([^>]*?)(?:\/>|>([\s\S]*?)<\/(?:\w+:)?row>)/g;
    let rm;
    while ((rm = rre.exec(data[1]))) {
      const rAttr = xmlAttr(rm[1] || "", "r");
      const ri = rAttr ? Number(rAttr) - 1 : nextRow;
      if (!(ri >= 0 && ri < 1048576)) throw new Error("This sheet names a row past Excel's last row, so it is likely damaged.");
      nextRow = ri + 1;
      const row = [];
      let krow = "";
      let nextCol = 0;
      const cre = /<(?:\w+:)?c\b([^>]*?)(?:\/>|>([\s\S]*?)<\/(?:\w+:)?c>)/g;
      let cm;
      while ((cm = cre.exec(rm[2] || ""))) {
        const attrs = cm[1] || "", inner = cm[2] || "";
        const ref = xmlAttr(attrs, "r");
        const ci = ref ? colIndex(ref) : nextCol;
        if (!(ci >= 0 && ci < 16384)) throw new Error("This sheet names a column past Excel's last column, so it is likely damaged.");
        nextCol = ci + 1;
        const type = xmlAttr(attrs, "t") || "n";
        const v = /<(?:\w+:)?v\b[^>]*>([\s\S]*?)<\/(?:\w+:)?v>/.exec(inner);
        let out = "";
        if (type === "inlineStr") {
          const is = /<(?:\w+:)?is\b[^>]*>([\s\S]*?)<\/(?:\w+:)?is>/.exec(inner);
          out = is ? siText(is[1]) : "";
        } else if (!v || (v[1].trim() === "" && type !== "str" && type !== "s")) {
          // No cached result: either no <v>, or an empty one, as openpyxl and some exporters write.
          if (/<(?:\w+:)?f\b/.test(inner)) lostFormulas++;
        } else if (type === "s") out = safeText(shared[Number(v[1])] || "", safe);
        else if (type === "b") out = v[1].trim() === "1" ? "TRUE" : "FALSE";
        else if (type === "str") out = safeText(xmlText(v[1]), safe);
        else if (type === "e") out = xmlText(v[1]);
        else if (type === "d") out = xmlText(v[1]).replace("T", " ").replace(/Z$/, "");
        else {
          // A number is written as the workbook stores it, not as Excel would display it.
          const raw = v[1].trim(), num = Number(raw);
          const kind = styles[Number(xmlAttr(attrs, "s") || 0)] || "";
          out = kind && isFinite(num) && raw !== "" ? excelDate(num, kind, date1904) : raw;
        }
        if (type === "inlineStr") out = safeText(out, safe);
        if (out === "") continue;
        if (++cells > cap) throw new Error("This sheet has more than " + (cap / 1e6) + " million cells, more than this page reads in a browser tab.");
        // Empty slots before a far-away cell cost memory too, so they count against a looser cap.
        slots += Math.max(0, ci - row.length) + 1;
        if (slots > cap * 4) throw new Error("This sheet spreads its cells over too many empty columns for this page to read in a browser tab.");
        while (row.length < ci) row.push("");
        row[ci] = out;
        if (withKinds) {
          const k = type === "s" || type === "str" || type === "inlineStr" ? "s" : type === "b" ? "b" : type === "e" ? "e"
            : type === "d" || (styles[Number(xmlAttr(attrs, "s") || 0)] || "") ? "d" : "n";
          krow = krow.padEnd(ci, " ") + k;
        }
      }
      while (rows.length < ri) { rows.push([]); if (withKinds) kinds.push(""); }
      rows[ri] = row;
      if (withKinds) kinds[ri] = krow;
    }
    const res = { rows: rows, formulasWithoutValue: lostFormulas, cells: cells };
    if (withKinds) res.kinds = kinds;
    return res;
  }

  /** Text that Excel would run as a formula when it opens a CSV gets a leading apostrophe (when safe is on). */
  function safeText(v, safe) { return safe && /^[=+\-@\t\r]/.test(v) ? "'" + v : v; }

  /** A sheet name as a file name: characters file systems refuse replaced, dots and spaces trimmed at the ends. */
  function sheetFileName(name) {
    const t = String(name || "").replace(/[\\/:*?"<>|\u0000-\u001f]+/g, "_").replace(/^[\s.]+|[\s.]+$/g, "");
    return (t || "Sheet").slice(0, 120);
  }

  /** Rows of strings to CSV text: RFC 4180 quoting, CRLF line ends, empty trailing rows and columns dropped. */
  function toCsv(rows, delimiter) {
    const d = delimiter || ",";
    let end = rows.length;
    while (end > 0 && !rows[end - 1].some(function (x) { return x !== "" && x != null; })) end--;
    let cols = 0;
    for (let r = 0; r < end; r++) for (let c = rows[r].length - 1; c >= cols; c--) if (rows[r][c] !== "" && rows[r][c] != null) { cols = c + 1; break; }
    const lines = new Array(end);
    for (let r = 0; r < end; r++) {
      const row = rows[r], out = new Array(cols);
      for (let c = 0; c < cols; c++) out[c] = csvField(row[c] == null ? "" : String(row[c]), d);
      lines[r] = out.join(d);
    }
    return end ? lines.join("\r\n") + "\r\n" : "";
  }
  function csvField(v, d) {
    return v.indexOf(d) !== -1 || v.indexOf('"') !== -1 || v.indexOf("\n") !== -1 || v.indexOf("\r") !== -1 ? '"' + v.replace(/"/g, '""') + '"' : v;
  }

  // ---------- JSON to CSV ----------
  /** JSON text with every integer literal of 16 digits or more turned into a marked string, outside strings only.
      JSON.parse rounds integers past 2^53 (tweet and order IDs); a string that starts with a NUL, which JSON text
      cannot otherwise produce unescaped here, carries the digits through and is written back as the number. */
  function protectBigInts(text) {
    const t = String(text);
    let out = null, last = 0, i = 0;
    const n = t.length;
    while (i < n) {
      const ch = t.charCodeAt(i);
      if (ch === 34) { // a string: skip to its closing quote
        i++;
        while (i < n) { const c = t.charCodeAt(i); if (c === 92) i += 2; else if (c === 34) break; else i++; }
        i++;
        continue;
      }
      if (ch === 45 || (ch >= 48 && ch <= 57)) {
        let k = i + (ch === 45 ? 1 : 0);
        const d0 = k;
        while (k < n && t.charCodeAt(k) >= 48 && t.charCodeAt(k) <= 57) k++;
        const c = k < n ? t.charCodeAt(k) : 0;
        if (c !== 46 && c !== 101 && c !== 69 && k - d0 >= 16) { // an integer: no fraction, no exponent
          (out = out || []).push(t.slice(last, i), '"\\u0000' + t.slice(i, k) + '"');
          last = k;
        }
        i = k;
        while (i < n && /[0-9.eE+\-]/.test(t[i])) i++;
        continue;
      }
      i++;
    }
    return out ? out.join("") + t.slice(last) : t;
  }
  function isBig(v) { return typeof v === "string" && v.charCodeAt(0) === 0; }

  /** The rows in a JSON file: { records, from, others, lines }. from names the key an array was found under, others
      any other keys that held arrays of objects. */
  function jsonRecords(text) {
    const t = protectBigInts(String(text).replace(/^\ufeff/, ""));
    let data, lines = false;
    try { data = JSON.parse(t); } catch (e) {
      const parts = t.split(/\r?\n/).filter(function (l) { return l.trim(); });
      if (parts.length < 2) throw new Error("This is not valid JSON (" + e.message + ").");
      data = [];
      for (let i = 0; i < parts.length; i++) {
        try { data.push(JSON.parse(parts[i])); } catch (e2) {
          if (i === 0) throw new Error("This is not valid JSON (" + e.message + ").");
          throw new Error("This is not valid JSON, and line " + (i + 1) + " is not a JSON value either, so it is not JSON Lines.");
        }
      }
      lines = true;
    }
    let from = "", others = [];
    if (!Array.isArray(data) && data && typeof data === "object") {
      const keys = Object.keys(data).filter(function (k) {
        const v = data[k];
        return Array.isArray(v) && v.some(function (x) { return x && typeof x === "object" && !Array.isArray(x); });
      }).sort(function (a, b) { return data[b].length - data[a].length; });
      if (keys.length) { from = keys[0]; others = keys.slice(1); data = data[from]; } else data = [data];
    } else if (!Array.isArray(data)) data = [data];
    return { records: data, from: from, others: others, lines: lines };
  }

  /** Records to rows: a header of every key in first-seen order, then one row per record. nested is "columns"
      (objects become a.b columns; arrays stay JSON text) or "json" (every object or array is JSON text). A literal
      key that clashes with a flattened one gets " (2)". safe guards text cells as in safeText. */
  function flattenRecords(records, nested, safe, maxCells) {
    const cols = [], index = Object.create(null);
    const cap = maxCells || MAX_CELLS;
    const flat = records.map(function (rec) {
      const out = Object.create(null);
      if (rec === null || typeof rec !== "object" || Array.isArray(rec)) out.value = cellValue(rec, safe);
      else walk(rec, "", out, nested !== "json", safe);
      for (const k in out) if (index[k] === undefined) { index[k] = cols.length; cols.push(k); }
      return out;
    });
    if (cols.length * flat.length > cap) {
      throw new Error("This file makes " + (cols.length * flat.length).toLocaleString("en-US") + " cells (" + flat.length.toLocaleString("en-US") +
        " rows by " + cols.length.toLocaleString("en-US") + " columns), more than this page builds in a browser tab (" + (cap / 1e6) + " million).");
    }
    const rows = [cols.slice()];
    flat.forEach(function (o) { rows.push(cols.map(function (k) { return o[k] === undefined ? "" : o[k]; })); });
    return { rows: rows, columns: cols.length };
  }
  function walk(obj, prefix, out, deep, safe) {
    Object.keys(obj).forEach(function (k) {
      const v = obj[k];
      let key = prefix + k;
      if (deep && v && typeof v === "object" && !Array.isArray(v) && Object.keys(v).length) { walk(v, key + ".", out, deep, safe); return; }
      if (out[key] !== undefined) { let n = 2; while (out[key + " (" + n + ")"] !== undefined) n++; key = key + " (" + n + ")"; }
      out[key] = cellValue(v, safe);
    });
  }
  function cellValue(v, safe) {
    if (v === null || v === undefined) return "";
    if (isBig(v)) return v.slice(1);
    if (typeof v === "string") return safeText(v, safe);
    if (typeof v === "object") return safeText(JSON.stringify(v).replace(/"\\u0000(-?\d+)"/g, "$1"), safe);
    return String(v);
  }

  // ---------- TIFF to JPG: the file is read here, so it can be bounded and tested ----------
  const TIFF_TYPE_SIZE = [0, 1, 1, 2, 4, 8, 1, 1, 2, 4, 8, 4, 8];
  const TIFF_MAX_IFDS = 1000;
  const MAX_TIFF_PAGES = 500;
  const TIFF_COMPRESSIONS = { 1: "none", 3: "CCITT Group 3", 4: "CCITT Group 4", 5: "LZW", 7: "JPEG", 8: "Deflate", 32773: "PackBits", 32946: "Deflate" };

  /** The pages of a TIFF: { pages, le }. Walks the directory chain once, stopping where it points back on itself,
      with a cap, and checks every strip and tile against the file length. Throws a message it cannot read. */
  function readTiff(b) {
    if (!b || b.length < 8) throw new Error("This TIFF is empty or cut short.");
    const le = b[0] === 0x49;
    const u16 = function (o) { return le ? b[o] | (b[o + 1] << 8) : (b[o] << 8) | b[o + 1]; };
    const u32 = function (o) { return (le ? (b[o] | (b[o + 1] << 8) | (b[o + 2] << 16) | (b[o + 3] << 24)) : ((b[o] << 24) | (b[o + 1] << 16) | (b[o + 2] << 8) | b[o + 3])) >>> 0; };
    if (u16(2) === 43) throw new Error("This is a BigTIFF, a variant for files over 4 GB that this page cannot read.");
    if (u16(2) !== 42) throw new Error("This is not a TIFF file, or it is damaged.");
    const seen = Object.create(null);
    const pages = [];
    let off = u32(4);
    while (off) {
      if (seen[off]) break;
      seen[off] = 1;
      if (pages.length >= TIFF_MAX_IFDS) throw new Error("This TIFF has more than " + TIFF_MAX_IFDS + " directories, so it is likely damaged.");
      if (off + 2 > b.length) throw new Error("This TIFF is damaged or cut short.");
      const n = u16(off);
      if (off + 2 + n * 12 + 4 > b.length) throw new Error("This TIFF is damaged or cut short.");
      const tags = {};
      for (let i = 0; i < n; i++) {
        const e = off + 2 + i * 12;
        const tag = u16(e), type = u16(e + 2), count = u32(e + 4);
        const size = TIFF_TYPE_SIZE[type] || 0;
        if (!size || count > 1e7) continue;
        const bytes = size * count;
        const at = bytes <= 4 ? e + 8 : u32(e + 8);
        if (at + bytes > b.length) continue;
        if (size === 1) { tags[tag] = b.subarray(at, at + count); continue; }
        const vals = new Array(count);
        for (let k = 0; k < count; k++) {
          const o = at + k * size;
          vals[k] = size === 2 ? u16(o) : size === 4 ? u32(o) : u32(o) / (u32(o + 4) || 1);
        }
        tags[tag] = vals;
      }
      pages.push(tiffPage(tags, b.length, le));
      off = u32(off + 2 + n * 12);
    }
    if (!pages.length) throw new Error("This TIFF has no pages.");
    return { pages: pages, le: le };
  }
  function tag0(t, k, d) { const v = t[k]; return v && v.length ? v[0] : d; }
  function tiffPage(t, length, le) {
    const p = {
      width: tag0(t, 256, 0), height: tag0(t, 257, 0), bps: t[258] ? Array.from(t[258]) : [1],
      spp: tag0(t, 277, t[258] ? t[258].length : 1), compression: tag0(t, 259, 1), photometric: tag0(t, 262, -1),
      fillOrder: tag0(t, 266, 1), orientation: tag0(t, 274, 1), planar: tag0(t, 284, 1), predictor: tag0(t, 317, 1),
      subfile: tag0(t, 254, 0), extra: t[338] ? Array.from(t[338]) : [], sampleFormat: tag0(t, 339, 1),
      colorMap: t[320] || null, jpegTables: t[347] || null, le: le, tiled: !!t[322],
      tileWidth: tag0(t, 322, 0), tileHeight: tag0(t, 323, 0), rowsPerStrip: tag0(t, 278, 0)
    };
    p.offsets = (p.tiled ? t[324] : t[273]) || [];
    p.counts = (p.tiled ? t[325] : t[279]) || [];
    if (!p.rowsPerStrip || p.rowsPerStrip > p.height) p.rowsPerStrip = p.height;
    p.thumbnail = (p.subfile & 1) === 1;
    p.problem = tiffProblem(p, length);
    return p;
  }
  /** What makes a page unreadable here, or "". */
  function tiffProblem(p, length) {
    if (!p.width || !p.height) return "This TIFF page has no size, so it is likely damaged.";
    if (!TIFF_COMPRESSIONS[p.compression]) return "This TIFF uses a compression (number " + p.compression + ") that this page cannot read.";
    if (p.planar !== 1 && p.spp > 1) return "This TIFF stores each color as a separate plane, which this page cannot read.";
    if (p.sampleFormat === 3) return "This TIFF stores floating-point samples, which this page cannot read.";
    if ([0, 1, 2, 3, 5, 6].indexOf(p.photometric) === -1) return "This TIFF uses a color model (number " + p.photometric + ") that this page cannot read.";
    if (p.photometric === 6 && p.compression !== 7) return "This TIFF stores YCbCr without JPEG compression, which this page cannot read.";
    const bits = p.bps[0];
    if (p.compression !== 7) {
      const ok = p.photometric === 3 ? [1, 2, 4, 8].indexOf(bits) !== -1 : p.photometric <= 1 ? [1, 2, 4, 8, 16].indexOf(bits) !== -1 : [8, 16].indexOf(bits) !== -1;
      if (!ok || p.bps.some(function (x) { return x !== bits; })) return "This TIFF uses " + p.bps.join("/") + " bits per sample, which this page cannot read.";
      if (p.photometric === 2 && p.spp < 3) return "This TIFF is marked as color but has fewer than three samples per pixel.";
      if (p.photometric === 5 && p.spp < 4) return "This TIFF is marked as CMYK but has fewer than four samples per pixel.";
      if (p.photometric === 3 && (!p.colorMap || p.colorMap.length < 3 * (1 << bits))) return "This TIFF has a palette that is missing or too short.";
      if (p.predictor !== 1 && p.predictor !== 2) return "This TIFF uses a predictor this page cannot undo.";
    }
    if (p.tiled && (!p.tileWidth || !p.tileHeight)) return "This TIFF has tiles without a size, so it is likely damaged.";
    if (!p.offsets.length || p.offsets.length !== p.counts.length) return "This TIFF page has no image data, so it is likely damaged.";
    for (let i = 0; i < p.offsets.length; i++) if (p.offsets[i] + p.counts[i] > length) return "This TIFF is damaged or cut short.";
    return "";
  }

  /** Bytes per row of width pixels, chunky samples, padded to a byte. */
  function tiffRowBytes(p, width) { return Math.ceil(width * p.bps[0] * p.spp / 8); }

  /** PackBits (compression 32773) into out. Returns the bytes written. */
  function unpackBits(src, out) {
    let i = 0, o = 0;
    while (i < src.length && o < out.length) {
      const n = src[i++];
      if (n < 128) { const end = Math.min(i + n + 1, src.length); while (i < end && o < out.length) out[o++] = src[i++]; }
      else if (n > 128) { const v = src[i++], c = 257 - n; for (let k = 0; k < c && o < out.length; k++) out[o++] = v; }
    }
    return o;
  }

  /** Undo predictor 2 (horizontal differencing) in place, for 8 or 16-bit samples, row by row. */
  function tiffUnpredict(buf, p, width, rows) {
    const spp = p.spp, rb = tiffRowBytes(p, width);
    if (p.bps[0] === 8) {
      for (let r = 0; r < rows; r++) { const o = r * rb; for (let i = spp; i < width * spp; i++) buf[o + i] = (buf[o + i] + buf[o + i - spp]) & 255; }
    } else if (p.bps[0] === 16) {
      const le = p.le;
      const get = function (o) { return le ? buf[o] | (buf[o + 1] << 8) : (buf[o] << 8) | buf[o + 1]; };
      const put = function (o, v) { if (le) { buf[o] = v & 255; buf[o + 1] = v >>> 8; } else { buf[o] = v >>> 8; buf[o + 1] = v & 255; } };
      for (let r = 0; r < rows; r++) { const o = r * rb; for (let i = spp; i < width * spp; i++) put(o + 2 * i, (get(o + 2 * i) + get(o + 2 * (i - spp))) & 65535); }
    }
  }

  /** Decoded samples (chunky, rows padded to a byte) to RGBA, for every layout tiffProblem lets through. 16-bit
      samples keep their high byte, in the file's byte order. */
  function tiffRGBA(raw, p) {
    const w = p.width, h = p.height, spp = p.spp, bits = p.bps[0], le = p.le, rb = tiffRowBytes(p, w);
    const out = new Uint8ClampedArray(w * h * 4);
    const sample = bits === 8 ? function (r, s) { return raw[r + s]; }
      : bits === 16 ? function (r, s) { const o = r + 2 * s; return le ? raw[o + 1] : raw[o]; }
      : function (r, s) { const bit = s * bits; return (raw[r + (bit >> 3)] >> (8 - bits - (bit & 7))) & ((1 << bits) - 1); };
    const scale = bits >= 8 || p.photometric === 3 ? 1 : 255 / ((1 << bits) - 1);
    const alphaAt = p.photometric === 2 ? 3 : p.photometric === 5 ? 4 : p.photometric <= 1 ? 1 : -1;
    const hasAlpha = alphaAt > 0 && spp > alphaAt;
    const premultiplied = hasAlpha && p.extra[0] === 1;
    const map = p.colorMap, mapN = 1 << bits;
    for (let y = 0; y < h; y++) {
      const row = y * rb;
      for (let x = 0; x < w; x++) {
        const s0 = x * spp, q = (y * w + x) * 4;
        let r, g, bl;
        if (p.photometric <= 1) { let v = sample(row, s0) * scale; if (p.photometric === 0) v = 255 - v; r = g = bl = v; }
        else if (p.photometric === 2) { r = sample(row, s0); g = sample(row, s0 + 1); bl = sample(row, s0 + 2); }
        else if (p.photometric === 3) { const i = sample(row, s0); r = map[i] >> 8; g = map[mapN + i] >> 8; bl = map[2 * mapN + i] >> 8; }
        else {
          const c = sample(row, s0), m = sample(row, s0 + 1), yy = sample(row, s0 + 2), k = sample(row, s0 + 3);
          r = (255 - c) * (255 - k) / 255; g = (255 - m) * (255 - k) / 255; bl = (255 - yy) * (255 - k) / 255;
        }
        const a = hasAlpha ? sample(row, s0 + alphaAt) * (bits >= 8 ? 1 : scale) : 255;
        if (premultiplied && a > 0 && a < 255) { r = r * 255 / a; g = g * 255 / a; bl = bl * 255 / a; }
        out[q] = r; out[q + 1] = g; out[q + 2] = bl; out[q + 3] = a;
      }
    }
    return out;
  }

  /** A page's samples as one buffer (chunky, rows padded to a byte), for every compression but JPEG. libs carries
      pako (Deflate) and UTIF (LZW and CCITT); the rest is done here. */
  function tiffDecodeRaw(bytes, p, libs) {
    const rb = tiffRowBytes(p, p.width), raw = new Uint8Array(rb * p.height);
    const cw = p.tiled ? p.tileWidth : p.width, ch = p.tiled ? p.tileHeight : p.rowsPerStrip;
    const crb = tiffRowBytes(p, cw), across = p.tiled ? Math.ceil(p.width / cw) : 1;
    for (let k = 0; k < p.offsets.length; k++) {
      const rows = p.tiled ? ch : Math.min(ch, p.height - k * ch);
      if (rows <= 0) break;
      const chunk = new Uint8Array(crb * rows);
      const src = bytes.subarray(p.offsets[k], p.offsets[k] + p.counts[k]);
      if (p.compression === 1) chunk.set(src.subarray(0, Math.min(src.length, chunk.length)));
      else if (p.compression === 32773) unpackBits(src, chunk);
      else if (p.compression === 8 || p.compression === 32946) { const inf = libs.pako.inflate(src); chunk.set(inf.subarray(0, Math.min(inf.length, chunk.length))); }
      else if (p.compression === 5) libs.UTIF.decode._decodeLZW(bytes, p.offsets[k], chunk, 0);
      else if (p.compression === 3) libs.UTIF.decode._decodeG3(bytes, p.offsets[k], p.counts[k], chunk, 0, cw, p.fillOrder);
      else if (p.compression === 4) libs.UTIF.decode._decodeG4(bytes, p.offsets[k], p.counts[k], chunk, 0, cw, p.fillOrder);
      if (p.predictor === 2) tiffUnpredict(chunk, p, cw, rows);
      if (!p.tiled) raw.set(chunk.subarray(0, Math.min(chunk.length, raw.length - k * ch * rb)), k * ch * rb);
      else {
        const x0 = (k % across) * cw, y0 = Math.floor(k / across) * ch;
        const xb = tiffRowBytes(p, x0), copy = Math.min(crb, rb - xb);
        for (let y = 0; y < ch && y0 + y < p.height; y++) raw.set(chunk.subarray(y * crb, y * crb + copy), (y0 + y) * rb + xb);
      }
    }
    return raw;
  }

  /** Canvas size and transform (for setTransform) that show a w by h picture upright, for orientation tags 1 to 8. */
  function orientTransform(o, w, h) {
    switch (o) {
      case 2: return { width: w, height: h, m: [-1, 0, 0, 1, w, 0] };
      case 3: return { width: w, height: h, m: [-1, 0, 0, -1, w, h] };
      case 4: return { width: w, height: h, m: [1, 0, 0, -1, 0, h] };
      case 5: return { width: h, height: w, m: [0, 1, 1, 0, 0, 0] };
      case 6: return { width: h, height: w, m: [0, 1, -1, 0, h, 0] };
      case 7: return { width: h, height: w, m: [0, -1, -1, 0, h, w] };
      case 8: return { width: h, height: w, m: [0, -1, 1, 0, 0, w] };
      default: return { width: w, height: h, m: [1, 0, 0, 1, 0, 0] };
    }
  }

  // Adobe's APP14 segment with transform 0: "these three components are RGB, do not convert from YCbCr".
  const ADOBE_RGB = [0xff, 0xee, 0, 14, 0x41, 0x64, 0x6f, 0x62, 0x65, 0, 100, 0, 0, 0, 0, 0];
  /** A JPEG-compressed strip or tile as a standalone JPEG: the JPEGTables (without their SOI and EOI) go in right
      after the strip's own SOI. When the TIFF says the JPEG data is RGB (photometric 2), an Adobe marker says so
      too, since decoders otherwise read three components as YCbCr (WebKit does; Chrome goes by component ids). */
  function tiffJpeg(strip, tables, rgb) {
    let t = new Uint8Array(0);
    if (tables && tables.length >= 4) {
      const end = tables[tables.length - 2] === 0xff && tables[tables.length - 1] === 0xd9 ? tables.length - 2 : tables.length;
      t = tables.subarray(2, end);
    }
    const mark = rgb ? ADOBE_RGB : [];
    if (!t.length && !mark.length) return strip;
    const out = new Uint8Array(strip.length + mark.length + t.length);
    out.set(strip.subarray(0, 2), 0); out.set(mark, 2); out.set(t, 2 + mark.length); out.set(strip.subarray(2), 2 + mark.length + t.length);
    return out;
  }


  // ---------- CSV to JSON ----------
  const JSON_CAP = 200 * 1024 * 1024;
  /** Keys for n columns: the header cells, "column N" where one is empty or missing, every key made unique in one
      pass (" (2)", " (3)", until free). */
  function jsonKeys(header, n) {
    const seen = Object.create(null), out = [];
    for (let i = 0; i < n; i++) {
      const raw = header && i < header.length && header[i] !== "" ? header[i] : "column " + (i + 1);
      let k = raw, c = 2;
      while (seen[k]) k = raw + " (" + c++ + ")";
      seen[k] = 1;
      out.push(k);
    }
    return out;
  }
  /** What each column holds: "number" when every non-empty cell is a number that writes back exactly as typed,
      "boolean" when every non-empty cell is true or false (any case), else "string". */
  function columnTypes(rows, n, delim) {
    const types = [];
    for (let c = 0; c < n; c++) {
      let num = true, bool = true, any = false;
      for (let r = 0; r < rows.length && (num || bool); r++) {
        const t = rows[r][c];
        if (t === undefined || t === "") continue;
        any = true;
        if (bool && !/^(true|false)$/i.test(t)) bool = false;
        if (num) {
          const norm = delim === ";" && DECIMAL_COMMA.test(t) ? t.replace(",", ".") : t;
          const v = cellNumber(t, delim);
          if (v === null || String(v) !== norm) num = false;
        }
      }
      types.push(!any ? "string" : num ? "number" : bool ? "boolean" : "string");
    }
    return types;
  }
  function jsonValue(t, type, typed, delim) {
    if (t === undefined || t === "") return typed ? "null" : '""';
    if (typed && type === "number") return delim === ";" && DECIMAL_COMMA.test(t) ? t.replace(",", ".") : t;
    if (typed && type === "boolean") return t.toLowerCase();
    return JSON.stringify(t);
  }
  /** With unflatten, an ordered tree of key paths: [[name, child or column]]. Keys with an empty part stay flat, and
      so does a key that is also the parent of another (a and a.b), so nothing is lost. */
  function keyTree(keys) {
    const paths = keys.map(function (k) { const p = k.split("."); return p.length > 1 && p.every(Boolean) ? p : null; });
    const whole = Object.create(null);
    keys.forEach(function (k) { whole[k] = 1; });
    const flat = keys.map(function () { return false; });
    let clash = false;
    paths.forEach(function (p, i) {
      if (!p) return;
      for (let j = 1; j < p.length; j++) {
        const pre = p.slice(0, j).join(".");
        if (whole[pre]) { flat[i] = true; flat[keys.indexOf(pre)] = true; clash = true; }
      }
    });
    const root = [];
    keys.forEach(function (k, i) {
      const p = !flat[i] && paths[i] ? paths[i] : [k];
      let node = root;
      for (let j = 0; j < p.length - 1; j++) {
        let next = null;
        for (let e = 0; e < node.length; e++) if (node[e][0] === p[j] && Array.isArray(node[e][1])) { next = node[e][1]; break; }
        if (!next) { next = []; node.push([p[j], next]); }
        node = next;
      }
      node.push([p[p.length - 1], i]);
    });
    return { tree: root, clash: clash };
  }
  /** The JSON text for rows, in parts of about 2 MB, written by hand so keys keep header order. value(row, c) gives a
      cell's JSON text. keys null means arrays. Shared by CSV to JSON and XLSX to JSON. Returns { parts, notes, est }. */
  function jsonWrite(rows, n, keys, opts, value) {
    const notes = [];
    let tree = null;
    if (keys && opts.unflatten) {
      const t = keyTree(keys);
      tree = t.tree;
      if (t.clash) notes.push("Some headers are both a value and the parent of others (such as a and a.b), so those stay as flat keys.");
    } else if (keys) tree = keys.map(function (k, i) { return [k, i]; });
    let est = 2;
    const keyLen = keys ? keys.reduce(function (s, k) { return s + k.length + 4; }, 0) : 0;
    rows.forEach(function (r) { est += keyLen + 4 + n * 4; for (let c = 0; c < r.length; c++) est += String(r[c] == null ? "" : r[c]).length; });
    if (!opts.lines) est += rows.length * (n * 6 + 6);
    if (est + (opts.already || 0) > JSON_CAP) throw new Error("The JSON would be about " + Math.round((est + (opts.already || 0)) / 1048576) + " MB, more than this page writes in a browser tab. Choose JSON Lines, or split the file.");
    const parts = [];
    let cur = [], curLen = 0;
    const put = function (s) { cur.push(s); curLen += s.length; if (curLen > 2e6) { parts.push(cur.join("")); cur = []; curLen = 0; } };
    const pretty = !opts.lines, base = opts.depth || 0;
    const ind = function (d) { return "  ".repeat(d); };
    const emit = function (node, row, depth) {
      let s = "{";
      node.forEach(function (e, i) {
        s += (i ? "," : "") + (pretty ? "\n" + ind(depth + 1) : "") + JSON.stringify(e[0]) + (pretty ? ": " : ":");
        s += Array.isArray(e[1]) ? emit(e[1], row, depth + 1) : value(row, e[1]);
      });
      return s + (pretty && node.length ? "\n" + ind(depth) : "") + "}";
    };
    const arr = function (row) {
      let s = "[";
      for (let c = 0; c < n; c++) s += (c ? (pretty ? ", " : ",") : "") + value(row, c);
      return s + "]";
    };
    if (pretty) put("[");
    rows.forEach(function (row, i) {
      const one = tree ? emit(tree, row, pretty ? base + 1 : 0) : arr(row);
      if (pretty) put((i ? "," : "") + "\n" + ind(base + 1) + one);
      else put(one + "\n");
    });
    if (pretty) put(rows.length ? "\n" + ind(base) + "]" : "]");
    if (pretty && !base) put("\n");
    if (cur.length) parts.push(cur.join(""));
    return { parts: parts, notes: notes, est: est };
  }

  /** CSV rows (from parseCsv) to JSON text in parts of about 2 MB: { parts, rows, cols, notes }. opts: header,
      types, unflatten, lines (JSON Lines), delimiter. Objects are written as text in header order, since JavaScript
      would put integer-like keys such as "2024" first. */
  function csvToJson(allRows, opts) {
    const d = opts.delimiter || ",";
    const rows = allRows.filter(function (r) { return !(r.length === 1 && r[0] === ""); }); // blank lines
    const header = opts.header ? rows.shift() || [] : null;
    let n = header ? header.length : 0;
    rows.forEach(function (r) { if (r.length > n) n = r.length; });
    if (rows.length * n > MAX_CELLS) throw new Error("This file has " + (rows.length * n).toLocaleString("en-US") + " cells, more than this page builds in a browser tab (" + (MAX_CELLS / 1e6) + " million).");
    const keys = header ? jsonKeys(header, n) : null;
    const types = columnTypes(rows, n, d);
    const typed = opts.types !== false;
    const w = jsonWrite(rows, n, keys, opts, function (row, c) { return jsonValue(row[c], types[c], typed, d); });
    return { parts: w.parts, rows: rows.length, cols: n, notes: w.notes };
  }

  // ---------- XLSX to JSON ----------
  const JSON_NUMBER = /^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?$/;
  /** One sheet's rows (from sheetRows with kinds) as JSON: { parts, rows, cols, notes, est }. Leading and trailing
      empty rows are trimmed and empty rows inside skipped; with header, the first row left gives the keys. Cells keep
      the workbook's types: numbers as stored when that text is valid JSON, booleans, dates as ISO strings with T,
      text and errors as strings, empty cells as null. */
  function sheetJson(rows, kinds, opts) {
    const keep = [], kk = [];
    rows.forEach(function (r, i) { if (r && r.some(function (x) { return x !== "" && x != null; })) { keep.push(r); kk.push(kinds[i] || ""); } });
    let header = null;
    if (opts.header && keep.length) { header = keep.shift(); kk.shift(); }
    let n = header ? header.length : 0;
    keep.forEach(function (r) { if (r.length > n) n = r.length; });
    const keys = header ? jsonKeys(header.map(function (h) { return h == null ? "" : String(h); }), n) : null;
    const at = new Map(keep.map(function (r, i) { return [r, i]; }));
    let badNumbers = 0;
    const value = function (row, c) {
      const t = row[c], k = (kk[at.get(row)] || "")[c] || "s";
      if (t === undefined || t === "") return "null";
      if (k === "n") {
        if (JSON_NUMBER.test(t)) return t;
        const v = Number(t);
        if (isFinite(v)) return String(v);
        badNumbers++;
        return "null";
      }
      if (k === "b") return t === "TRUE" ? "true" : "false";
      if (k === "d") return JSON.stringify(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(t) ? t.replace(" ", "T") : t);
      return JSON.stringify(t);
    };
    const w = jsonWrite(keep, n, keys, opts, value);
    if (badNumbers) w.notes.push(badNumbers + " number cell" + (badNumbers === 1 ? " holds" : "s hold") + " text that is not a number, written as null.");
    return { parts: w.parts, rows: keep.length, cols: n, notes: w.notes, est: w.est };
  }

  // ---------- ICNS to PNG ----------
  // Each type's iconset slot (the names iconutil writes), its pixel size, and how it is stored. When two entries share
  // a slot, a PNG wins over ARGB, and ARGB over legacy RLE.
  const ICNS_SLOTS = {
    icp4: ["icon_16x16", 16, "png"], icp5: ["icon_32x32", 32, "png"], icp6: ["icon_48x48", 48, "png"],
    ic07: ["icon_128x128", 128, "png"], ic08: ["icon_256x256", 256, "png"], ic09: ["icon_512x512", 512, "png"],
    ic10: ["icon_512x512@2x", 1024, "png"], ic11: ["icon_16x16@2x", 32, "png"], ic12: ["icon_32x32@2x", 64, "png"],
    ic13: ["icon_128x128@2x", 256, "png"], ic14: ["icon_256x256@2x", 512, "png"],
    icsB: ["icon_18x18@2x", 36, "png"], sb24: ["icon_24x24", 24, "png"], SB24: ["icon_24x24@2x", 48, "png"],
    ic04: ["icon_16x16", 16, "argb"], ic05: ["icon_32x32", 32, "argb"], icsb: ["icon_18x18", 18, "argb"],
    is32: ["icon_16x16", 16, "rle"], il32: ["icon_32x32", 32, "rle"], ih32: ["icon_48x48", 48, "rle"], it32: ["icon_128x128", 128, "rle"]
  };
  const ICNS_MASKS = { is32: "s8mk", il32: "l8mk", ih32: "h8mk", it32: "t8mk" };
  const ICNS_RANK = { png: 0, argb: 1, rle: 2 };

  /** The images in an ICNS, one per iconset slot, largest first: { images, skipped }. images[i] is { type, slot,
      width, height, format: "png" | "argb" | "rle", data, mask }; skipped lists the sizes held as JPEG 2000. */
  function readIcns(b) {
    if (!b || b.length < 16 || ascii(b, 0, 4) !== "icns") throw new Error("This is not an ICNS file, or it is damaged.");
    const u32 = function (o) { return ((b[o] << 24) | (b[o + 1] << 16) | (b[o + 2] << 8) | b[o + 3]) >>> 0; };
    const total = u32(4);
    if (total > b.length) throw new Error("This ICNS is cut short: its header says " + total + " bytes, and the file has " + b.length + ".");
    const entries = Object.create(null);
    for (let at = 8, count = 0; at + 8 <= total; count++) {
      if (count >= 200) throw new Error("This ICNS has more than 200 entries, so it is likely damaged.");
      const type = ascii(b, at, at + 4), len = u32(at + 4);
      if (len < 8 || at + len > total) throw new Error("This ICNS is damaged: an entry runs past the end of the file.");
      if (!entries[type]) entries[type] = b.subarray(at + 8, at + len);
      at += len;
    }
    const best = Object.create(null), skipped = [];
    Object.keys(entries).forEach(function (type) {
      const slot = ICNS_SLOTS[type];
      if (!slot) return;
      const data = entries[type];
      let format = slot[2], w = slot[1], h = slot[1];
      const isPng = data.length > 8 && data[0] === 0x89 && ascii(data, 1, 4) === "PNG";
      const isJp2 = data.length > 12 && ((ascii(data, 4, 8) === "jP  ") || (data[0] === 0xff && data[1] === 0x4f && data[2] === 0xff && data[3] === 0x51));
      if (isJp2) { skipped.push(slot[1]); return; }
      if (format === "png") {
        if (!isPng) return;
        const s = pngSize(data);
        if (s) { w = s.width; h = s.height; }
      } else if (format === "argb" && ascii(data, 0, 4) !== "ARGB") {
        if (!isPng) return; // an icsb or ic04 can hold a PNG too
        format = "png";
      }
      const cand = { type: type, slot: slot[0], width: w, height: h, format: format, data: data, mask: ICNS_MASKS[type] ? entries[ICNS_MASKS[type]] || null : null };
      const was = best[slot[0]];
      if (!was || ICNS_RANK[format] < ICNS_RANK[was.format]) best[slot[0]] = cand;
    });
    const images = Object.keys(best).map(function (k) { return best[k]; }).sort(function (a, z) { return z.width * z.height - a.width * a.height; });
    return { images: images, skipped: skipped.filter(function (s, i, a) { return a.indexOf(s) === i; }).sort(function (a, z) { return z - a; }) };
  }

  /** Apple's icon RLE (a PackBits variant): a byte under 128 copies the next n+1 bytes, 128 and up repeats the next
      byte n-125 times. Unpacks to exactly need bytes, or returns null when the data runs out first. */
  function icnsRle(src, need) {
    const out = new Uint8Array(need);
    let i = 0, o = 0;
    while (o < need && i < src.length) {
      const n = src[i++];
      if (n < 128) { for (let k = 0; k <= n && o < need && i < src.length; k++) out[o++] = src[i++]; }
      else { const v = src[i++], c = n - 125; for (let k = 0; k < c && o < need; k++) out[o++] = v; }
    }
    return o === need ? out : null;
  }

  /** An ARGB or legacy RLE image as RGBA, or null when its data is short. ARGB colors are stored premultiplied. */
  function icnsRGBA(img) {
    const w = img.width, area = w * img.height, out = new Uint8ClampedArray(area * 4);
    if (img.format === "argb") {
      const planes = icnsRle(img.data.subarray(4), area * 4);
      if (!planes) return null;
      // The color planes are premultiplied by alpha (iconutil's output confirms it), so they are divided back out.
      for (let i = 0; i < area; i++) {
        const al = planes[i], k = al ? 255 / al : 0;
        out[i * 4] = Math.round(planes[area + i] * k); out[i * 4 + 1] = Math.round(planes[2 * area + i] * k);
        out[i * 4 + 2] = Math.round(planes[3 * area + i] * k); out[i * 4 + 3] = al;
      }
      return out;
    }
    const src = img.type === "it32" ? img.data.subarray(4) : img.data;
    const planes = icnsRle(src, area * 3);
    if (!planes) return null;
    const mask = img.mask && img.mask.length >= area ? img.mask : null;
    for (let i = 0; i < area; i++) { out[i * 4] = planes[i]; out[i * 4 + 1] = planes[area + i]; out[i * 4 + 2] = planes[2 * area + i]; out[i * 4 + 3] = mask ? mask[i] : 255; }
    return out;
  }

  // ---------- ICO to PNG ----------
  /** The images in an ICO or CUR: { images, problems }. images[i] is { width, height, depth, format: "png" | "bmp",
      data }; one per size, the deepest kept, largest first. Lenient about gaps and order, unlike parseIco. */
  function readIco(b) {
    if (!b || b.length < 6 || b[0] || b[1] || (b[2] !== 1 && b[2] !== 2) || b[3]) throw new Error("This is not an ICO file, or it is damaged.");
    const u16 = function (o) { return b[o] | (b[o + 1] << 8); };
    const u32 = function (o) { return (b[o] | (b[o + 1] << 8) | (b[o + 2] << 16) | (b[o + 3] << 24)) >>> 0; };
    const i32 = function (o) { return b[o] | (b[o + 1] << 8) | (b[o + 2] << 16) | (b[o + 3] << 24); };
    const count = u16(4);
    if (!count || count > 255 || 6 + count * 16 > b.length) throw new Error("This ICO is damaged: its list of sizes does not fit in the file.");
    const best = Object.create(null), problems = [];
    for (let i = 0; i < count; i++) {
      const e = 6 + i * 16, size = u32(e + 8), off = u32(e + 12);
      if (!size || off + size > b.length) { problems.push("One size runs past the end of the file and was left out."); continue; }
      const data = b.subarray(off, off + size);
      let img;
      if (data.length > 8 && data[0] === 0x89 && ascii(data, 1, 4) === "PNG") {
        const s = pngSize(data);
        if (!s) { problems.push("One PNG size is damaged and was left out."); continue; }
        const ct = data[25], bitDepth = data[24];
        img = { width: s.width, height: s.height, depth: bitDepth * ({ 0: 1, 2: 3, 3: 1, 4: 2, 6: 4 }[ct] || 1), format: "png", data: data };
      } else {
        if (data.length < 40 || u32(off) < 40) { problems.push("One size is not a PNG or a bitmap this page reads and was left out."); continue; }
        const w = i32(off + 4), hh = i32(off + 8), bpp = u16(off + 14), comp = u32(off + 16);
        const h = Math.abs(hh) / 2;
        if (w < 1 || w > 1024 || h < 1 || h > 1024 || h !== Math.floor(h)) { problems.push("One bitmap size has an impossible width or height and was left out."); continue; }
        if (comp !== 0 || [1, 4, 8, 24, 32].indexOf(bpp) === -1) { problems.push("One " + w + " by " + h + " size uses " + (comp ? "a compressed bitmap" : bpp + "-bit color") + ", which this page cannot read, and was left out."); continue; }
        const colors = bpp <= 8 ? (u32(off + 32) || (1 << bpp)) : 0;
        const stride = Math.ceil(w * bpp / 32) * 4;
        const need = u32(off) + colors * 4 + stride * h;
        if (need > data.length) { problems.push("One " + w + " by " + h + " bitmap is cut short and was left out."); continue; }
        img = { width: w, height: h, depth: bpp, format: "bmp", data: data, topDown: hh < 0, colors: colors, header: u32(off) };
      }
      const key = img.width + "x" + img.height;
      if (!best[key] || img.depth > best[key].depth) best[key] = img;
    }
    const images = Object.keys(best).map(function (k) { return best[k]; }).sort(function (a, z) { return z.width * z.height - a.width * a.height || z.depth - a.depth; });
    return { images: images, problems: problems.filter(function (p, i, a) { return a.indexOf(p) === i; }) };
  }

  /** A BMP entry of an ICO as RGBA. The AND mask (1 bit a pixel, rows padded to 4 bytes, bottom-up) makes pixels
      transparent when the image has no alpha of its own, as for a 32-bit entry whose alpha is all 0 (Windows does
      this; Pillow does not). A missing or short mask means opaque. */
  function icoBmp(img) {
    const d = img.data, w = img.width, h = img.height, bpp = img.depth;
    const pal = img.header, px = pal + img.colors * 4;
    const stride = Math.ceil(w * bpp / 32) * 4, mstride = Math.ceil(w / 32) * 4, moff = px + stride * h;
    const out = new Uint8ClampedArray(w * h * 4);
    let anyAlpha = false;
    for (let y = 0; y < h; y++) {
      const row = px + (img.topDown ? y : h - 1 - y) * stride;
      for (let x = 0; x < w; x++) {
        const q = (y * w + x) * 4;
        if (bpp === 32) { const o = row + x * 4; out[q] = d[o + 2]; out[q + 1] = d[o + 1]; out[q + 2] = d[o]; out[q + 3] = d[o + 3]; if (d[o + 3]) anyAlpha = true; }
        else if (bpp === 24) { const o = row + x * 3; out[q] = d[o + 2]; out[q + 1] = d[o + 1]; out[q + 2] = d[o]; out[q + 3] = 255; }
        else {
          const bit = x * bpp, v = (d[row + (bit >> 3)] >> (8 - bpp - (bit & 7))) & ((1 << bpp) - 1);
          const p = pal + Math.min(v, img.colors - 1) * 4;
          out[q] = d[p + 2]; out[q + 1] = d[p + 1]; out[q + 2] = d[p]; out[q + 3] = 255;
        }
      }
    }
    if ((bpp < 32 || !anyAlpha) && moff + mstride * h <= d.length) {
      for (let y = 0; y < h; y++) {
        const row = moff + (img.topDown ? y : h - 1 - y) * mstride;
        for (let x = 0; x < w; x++) {
          const q = (y * w + x) * 4;
          if ((d[row + (x >> 3)] >> (7 - (x & 7))) & 1) out[q + 3] = 0;
          else if (bpp === 32) out[q + 3] = 255;
        }
      }
    } else if (bpp === 32 && !anyAlpha) for (let q = 3; q < out.length; q += 4) out[q] = 255;
    return out;
  }

  // ---------- PNG writer, for pixels that must come out exactly (icon sizes decoded here) ----------
  // A canvas stores premultiplied alpha, which changes the color of faint pixels; this writes RGBA as it is. deflate
  // is the caller's zlib compressor (CompressionStream in the worker, zlib in Node).
  let CRC_TABLE = null;
  function crc32(b) {
    if (!CRC_TABLE) { CRC_TABLE = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; CRC_TABLE[n] = c >>> 0; } }
    let c = 0xffffffff;
    for (let i = 0; i < b.length; i++) c = CRC_TABLE[(c ^ b[i]) & 255] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  }
  async function pngEncode(rgba, w, h, deflate) {
    const raw = new Uint8Array((w * 4 + 1) * h);
    for (let y = 0; y < h; y++) raw.set(rgba.subarray(y * w * 4, (y + 1) * w * 4), y * (w * 4 + 1) + 1); // filter 0
    const z = await deflate(raw);
    const chunk = function (type, data) {
      const out = new Uint8Array(12 + data.length), dv = new DataView(out.buffer);
      dv.setUint32(0, data.length);
      for (let i = 0; i < 4; i++) out[4 + i] = type.charCodeAt(i);
      out.set(data, 8);
      dv.setUint32(8 + data.length, crc32(out.subarray(4, 8 + data.length)));
      return out;
    };
    const ihdr = new Uint8Array(13), dv = new DataView(ihdr.buffer);
    dv.setUint32(0, w); dv.setUint32(4, h); ihdr[8] = 8; ihdr[9] = 6; // 8-bit RGBA
    const parts = [new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), chunk("IHDR", ihdr), chunk("IDAT", z), chunk("IEND", new Uint8Array(0))];
    const out = new Uint8Array(parts.reduce(function (n, x) { return n + x.length; }, 0));
    let at = 0;
    parts.forEach(function (x) { out.set(x, at); at += x.length; });
    return out;
  }

  // ---------- SRT to VTT and VTT to SRT ----------
  const SUB_TIME = /^\s*((?:\d+:)?\d{1,2}:\d{2}[.,]\d{1,3})\s*-->\s*((?:\d+:)?\d{1,2}:\d{2}[.,]\d{1,3})(.*)$/;
  /** "01:02:03,4" or "02:03.456" to milliseconds, or NaN. */
  function subMs(t) {
    const m = /^(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})$/.exec(t.trim());
    if (!m) return NaN;
    return ((Number(m[1] || 0) * 60 + Number(m[2])) * 60 + Number(m[3])) * 1000 + Number((m[4] + "00").slice(0, 3));
  }
  function subTime(ms, sep) {
    const h = Math.floor(ms / 3600000), m = Math.floor(ms / 60000) % 60, s = Math.floor(ms / 1000) % 60, t = ms % 1000;
    return pad2(h) + ":" + pad2(m) + ":" + pad2(s) + sep + String(t).padStart(3, "0");
  }
  function subBlocks(text) {
    return String(text).replace(/^﻿/, "").replace(/\r\n?/g, "\n").split(/\n[ \t]*\n/);
  }
  // Entities WebVTT text may use, decoded for SRT, where they are not markup.
  function subEntities(t) {
    return t.replace(/&(amp|lt|gt|nbsp|lrm|rlm|quot|apos|#x[0-9a-f]+|#\d+);/gi, function (m, e) {
      const k = e.toLowerCase();
      if (k === "amp") return "&"; if (k === "lt") return "<"; if (k === "gt") return ">"; if (k === "nbsp") return " ";
      if (k === "lrm") return "‎"; if (k === "rlm") return "‏"; if (k === "quot") return '"'; if (k === "apos") return "'";
      const n = k[1] === "x" ? parseInt(k.slice(2), 16) : parseInt(k.slice(1), 10);
      return n > 0 && n <= 0x10ffff ? String.fromCodePoint(n) : m;
    });
  }

  /** SRT text to cues: [{ id, start, end, text }]. Tolerates a BOM, CRLF, missing or wrong numbers, extra blank lines,
      "." for ",", and coordinates after the timing. Returns { cues, skipped }. */
  function parseSrt(text) {
    const cues = [];
    let skipped = 0;
    subBlocks(text).forEach(function (block) {
      const lines = block.split("\n");
      let i = 0;
      while (i < lines.length && lines[i].trim() === "") i++;
      if (i >= lines.length) return;
      let id = "";
      if (!SUB_TIME.test(lines[i]) && i + 1 < lines.length && SUB_TIME.test(lines[i + 1])) { id = lines[i].trim(); i++; }
      const m = SUB_TIME.exec(lines[i] || "");
      if (!m) { skipped++; return; }
      const start = subMs(m[1]), end = subMs(m[2]);
      if (isNaN(start) || isNaN(end)) { skipped++; return; }
      cues.push({ id: id, start: start, end: end, text: lines.slice(i + 1).join("\n").replace(/\s+$/, "") });
    });
    return { cues: cues, skipped: skipped };
  }

  /** Remove matches of re until none are left, so a tag split by another (<<b>x>) cannot survive one pass. */
  function stripTags(s, re) {
    let prev;
    do { prev = s; s = s.replace(re, ""); } while (s !== prev);
    return s;
  }

  /** SRT cue text as WebVTT cue text: b, i and u kept; font tags and ASS overrides ({\an8}) removed; any other <, and
      every &, escaped, since a WebVTT parser would read them as markup. */
  function srtTextToVtt(t) {
    const keep = [];
    let s = t.replace(/\{\\[^}]*\}/g, "");
    s = s.replace(/<(\/?)([biu])>/gi, function (m, slash, tag) { keep.push("<" + slash + tag.toLowerCase() + ">"); return "\u0000" + (keep.length - 1) + "\u0000"; });
    s = stripTags(s, /<\/?[a-z][a-z0-9]*(?:\s[^<>]*)?>/gi); // font, s, span and other markup: the text stays
    s = s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return s.replace(/\u0000(\d+)\u0000/g, function (m, n) { return keep[Number(n)]; });
  }

  /** Cues to a WebVTT file. Cues are sorted by start time (stable), which WebVTT requires; numbers stay as ids. */
  function writeVtt(cues) {
    const sorted = cues.map(function (c, i) { return [c, i]; }).sort(function (a, b) { return a[0].start - b[0].start || a[1] - b[1]; }).map(function (x) { return x[0]; });
    let out = "WEBVTT\n";
    sorted.forEach(function (c) {
      const text = srtTextToVtt(c.text).split("\n").filter(function (l) { return l.trim() !== ""; }).join("\n");
      out += "\n" + subTime(c.start, ".") + " --> " + subTime(c.end, ".") + "\n" + text + "\n";
    });
    return { text: out, reordered: sorted.some(function (c, i) { return c !== cues[i]; }) };
  }

  /** WebVTT text to cues. Skips the header, NOTE, STYLE and REGION blocks; drops cue settings. Returns
      { cues, skipped, autoCaptions } where autoCaptions is true when cue text carries inline timestamps. */
  function parseVtt(text) {
    const blocks = subBlocks(text);
    if (!/^WEBVTT(?:[ \t].*)?$/.test((blocks[0] || "").split("\n")[0])) throw new Error("This file does not start with WEBVTT, so it is not a WebVTT file.");
    const cues = [];
    let skipped = 0, auto = false;
    // A line with --> inside a block starts a new cue, so a missing blank line does not merge two cues.
    const split = [];
    blocks.slice(1).forEach(function (block) {
      let cur = [];
      block.split("\n").forEach(function (l) {
        const timing = l.indexOf("-->") !== -1;
        if (timing && cur.some(function (x) { return x.indexOf("-->") !== -1; })) { split.push(cur); cur = []; }
        cur.push(l);
      });
      split.push(cur);
    });
    split.forEach(function (lines) {
      let i = 0;
      while (i < lines.length && lines[i].trim() === "") i++;
      if (i >= lines.length) return;
      if (/^(NOTE|STYLE|REGION)(?:[ \t]|$)/.test(lines[i])) return;
      let id = "";
      if (lines[i].indexOf("-->") === -1) { id = lines[i].trim(); i++; }
      const m = SUB_TIME.exec(lines[i] || "");
      if (!m) { skipped++; return; }
      const start = subMs(m[1]), end = subMs(m[2]);
      if (isNaN(start) || isNaN(end)) { skipped++; return; }
      const body = lines.slice(i + 1).join("\n");
      if (/<\d+:\d{2}(?::\d{2})?\.\d{3}>/.test(body)) auto = true;
      cues.push({ id: id, start: start, end: end, text: body });
    });
    return { cues: cues, skipped: skipped, autoCaptions: auto };
  }

  /** WebVTT cue text as SRT text: b, i and u kept; voice tags become "Name: " (speakers on) or nothing; class, lang,
      ruby and inline timestamps removed; entities decoded; blank lines dropped. */
  function vttTextToSrt(t, speakers, state) {
    state = state || {};
    let s = t.replace(/<v(?:\.[^\s>]*)?\s+([^>]*)>/g, function (m, name) {
      const who = subEntities(name.trim());
      if (!speakers || !who || who === state.speaker) return "";
      state.speaker = who;
      return "\u0001" + who + ": ";
    });
    s = s.replace(/<\/v>/g, "").replace(/<\d+:\d{2}(?::\d{2})?\.\d{3}>/g, "").replace(/<rt>[\s\S]*?<\/rt>/g, "");
    s = s.replace(/<(\/?)([biu])(?:\.[^>]*)?>/g, "\u0002$1$2\u0003");
    s = stripTags(stripTags(s, /<\/?(?:c|lang|ruby|rt)(?:[.\s][^>]*)?>/g), /<[^>]*>/g);
    s = subEntities(s).replace(/\u0002(\/?)([biu])\u0003/g, "<$1$2>").replace(/\u0001/g, "");
    return s.split("\n").map(function (l) { return l.replace(/\s+$/, ""); }).filter(function (l) { return l.trim() !== ""; }).join("\n");
  }

  /** Cues to an SRT file, numbered from 1, CRLF line ends. merge drops a first line that repeats the previous cue's
      last line (the roll-up of auto-captions) and the cues it leaves empty. Returns { text, merged, cues }. */
  function writeSrt(cues, opts) {
    opts = opts || {};
    const out = [];
    let prevLast = null, merged = 0;
    const state = {};
    const STAMP = /<\d+:\d{2}(?::\d{2})?\.\d{3}>/;
    let prevEnd = -1;
    cues.forEach(function (c) {
      let lines = vttTextToSrt(c.text, opts.speakers !== false, state).split("\n").filter(Boolean);
      if (opts.merge && prevLast !== null && lines.length && lines[0] === prevLast) {
        const raw = c.text.split("\n").filter(function (l) { return l.trim() !== ""; });
        // The flash cue between rolls: one repeated line, 50 ms or less. Or a roll: the repeated line on top, the new
        // line below it carrying inline timestamps. Two genuine identical captions fit neither.
        if (lines.length === 1 && c.end - c.start <= 50) { lines = []; merged++; }
        else if (lines.length >= 2 && raw.slice(1).some(function (l) { return STAMP.test(l); }) && c.start - prevEnd <= 50) { lines = lines.slice(1); merged++; }
      }
      if (!lines.length) return;
      prevLast = lines[lines.length - 1];
      prevEnd = c.end;
      out.push({ start: c.start, end: c.end, text: lines.join("\r\n") });
    });
    const text = out.map(function (c, i) { return (i + 1) + "\r\n" + subTime(c.start, ",") + " --> " + subTime(c.end, ",") + "\r\n" + c.text + "\r\n"; }).join("\r\n");
    return { text: text, merged: merged, cues: out.length };
  }

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
      width: Math.min(16384, Math.max(16, Math.round(Number(raw.width)) || 1920)),
      sheets: raw.sheets === "all" ? "all" : "first",
      bom: bool(raw.bom),
      nested: raw.nested === "json" ? "json" : "columns",
      safe: raw.safe === undefined ? true : bool(raw.safe),
      tiffpages: raw.tiffpages === "all" ? "all" : "first",
      types: raw.types === undefined ? true : bool(raw.types),
      unflatten: bool(raw.unflatten),
      icons: raw.icons === "all" ? "all" : "largest",
      speakers: raw.speakers === undefined ? true : bool(raw.speakers),
      merge: raw.merge === undefined ? true : bool(raw.merge)
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
    isSvgText: isSvgText, svgDecode: svgDecode, xmlText: xmlText, parseWorkbook: parseWorkbook, parseRels: parseRels,
    parseSharedStrings: parseSharedStrings, fmtKind: fmtKind, parseStyles: parseStyles, excelDate: excelDate,
    colIndex: colIndex, sheetRows: sheetRows, toCsv: toCsv, jsonRecords: jsonRecords, flattenRecords: flattenRecords,
    safeText: safeText, sheetFileName: sheetFileName, protectBigInts: protectBigInts, readTiff: readTiff,
    unpackBits: unpackBits, tiffUnpredict: tiffUnpredict, tiffRGBA: tiffRGBA, tiffRowBytes: tiffRowBytes,
    orientTransform: orientTransform, tiffJpeg: tiffJpeg, tiffDecodeRaw: tiffDecodeRaw, tiffProblem: tiffProblem, csvToJson: csvToJson, jsonKeys: jsonKeys, columnTypes: columnTypes,
    readIcns: readIcns, icnsRle: icnsRle, icnsRGBA: icnsRGBA, readIco: readIco, icoBmp: icoBmp, jsonWrite: jsonWrite, sheetJson: sheetJson,
    parseSrt: parseSrt, writeVtt: writeVtt, parseVtt: parseVtt, writeSrt: writeSrt, subtitleKind: subtitleKind, subMs: subMs, pngEncode: pngEncode, crc32: crc32, ICNS_SLOTS: ICNS_SLOTS, MAX_TIFF_PAGES: MAX_TIFF_PAGES, TIFF_COMPRESSIONS: TIFF_COMPRESSIONS, svgSize: svgSize, svgWithSize: svgWithSize, svgNotes: svgNotes, svgOutSize: svgOutSize
  };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.Convert = api;
})(typeof self !== "undefined" ? self : this);
