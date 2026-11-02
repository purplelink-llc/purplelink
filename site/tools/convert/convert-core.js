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
  // "Download all" stops above this; past it a zip built in memory can take the tab down.
  const MAX_ZIP_BYTES = 1024 * 1024 * 1024;

  // One entry per page. The page's data-convert picks it. accepts are sniffed kinds, not extensions.
  const CONVERSIONS = {
    "heic-to-jpg": { label: "HEIC", accepts: ["heic"], outputs: ["jpg", "png"], output: "jpg", decoder: "heif" },
    "webp-to-png": { label: "WebP", accepts: ["webp"], outputs: ["png", "jpg"], output: "png", decoder: "native" },
    "png-to-icns": { label: "PNG", accepts: ["png", "jpeg", "webp"], outputs: ["icns"], output: "icns", decoder: "native" }
  };

  const MIME = { jpg: "image/jpeg", png: "image/png", icns: "image/icns", zip: "application/zip" };
  const KIND_NAMES = { heic: "HEIC", avif: "AVIF", webp: "WebP", png: "PNG", jpeg: "JPEG", gif: "GIF" };

  function ascii(b, s, e) {
    let out = "";
    for (let i = s; i < e && i < b.length; i++) out += String.fromCharCode(b[i]);
    return out;
  }

  // mif1/msf1 are generic HEIF brands that AVIF files carry too, so AVIF brands are checked first.
  const HEIF_BRANDS = ["heic", "heix", "heim", "heis", "hevc", "hevx", "hevm", "hevs", "mif1", "msf1", "mif2"];
  const AVIF_BRANDS = ["avif", "avis"];

  /** What a file is, from its first bytes: "heic", "avif", "webp", "png", "jpeg", "gif" or "". */
  function sniff(b) {
    if (!b || b.length < 12) return "";
    if (b[0] === 0x89 && ascii(b, 1, 4) === "PNG") return "png";
    if (b[0] === 0xff && b[1] === 0xd8 && b[2] === 0xff) return "jpeg";
    if (ascii(b, 0, 4) === "RIFF" && ascii(b, 8, 12) === "WEBP") return "webp";
    if (ascii(b, 0, 4) === "GIF8") return "gif";
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

  /** The message for a file this page cannot take, or "" when it can. */
  function refuse(pair, kind, size) {
    const c = CONVERSIONS[pair];
    if (!c) return "This page does not know that conversion.";
    if (size === 0) return "That file is empty.";
    if (size > MAX_BYTES) return "That file is over " + (MAX_BYTES / 1048576) + " MB.";
    if (c.accepts.indexOf(kind) !== -1) return "";
    const want = c.accepts.map(function (k) { return KIND_NAMES[k]; }).join(", ").replace(/, ([^,]*)$/, " or $1");
    return kind ? "This is a " + KIND_NAMES[kind] + " file, not " + want + "." : "This is not a " + want + " file, or it is damaged.";
  }

  /** The message for a picture too large to decode here, or "". */
  function tooManyPixels(width, height, mobile) {
    const cap = mobile ? MAX_PIXELS_MOBILE : MAX_PIXELS;
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

  /** Options as the page sends them, cleaned. */
  function options(pair, raw) {
    const c = CONVERSIONS[pair];
    raw = raw || {};
    const output = c && c.outputs.indexOf(raw.output) !== -1 ? raw.output : (c ? c.output : "");
    let quality = Number(raw.quality);
    if (!(quality >= 0.5 && quality <= 1)) quality = 0.92;
    const background = /^#[0-9a-f]{6}$/i.test(raw.background || "") ? raw.background.toLowerCase() : "#ffffff";
    return { output: output, quality: quality, background: background, iconset: !!raw.iconset, mobile: !!raw.mobile };
  }

  const api = {
    MAX_BYTES: MAX_BYTES, MAX_FILES: MAX_FILES, MAX_PIXELS: MAX_PIXELS, MAX_PIXELS_MOBILE: MAX_PIXELS_MOBILE,
    MAX_ZIP_BYTES: MAX_ZIP_BYTES, CONVERSIONS: CONVERSIONS, MIME: MIME, KIND_NAMES: KIND_NAMES,
    ICNS_TYPES: ICNS_TYPES, ICNS_SIZES: ICNS_SIZES, ICONSET: ICONSET,
    sniff: sniff, refuse: refuse, tooManyPixels: tooManyPixels, outName: outName, uniqueNames: uniqueNames,
    formatBytes: formatBytes, buildIcns: buildIcns, parseIcns: parseIcns, pngSize: pngSize,
    downscaleSteps: downscaleSteps, fitSquare: fitSquare, options: options
  };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.Convert = api;
})(typeof self !== "undefined" ? self : this);
