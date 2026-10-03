/* Metadata Cleaner core. Pure functions on Uint8Array / string, no DOM, so the
   same file runs in the page and under node for tests.

   Every cleaner returns { kind, found, out, kept, notes }.
     found  fields that were present in the input: [{ group, field, value }]
     out    the cleaned bytes
     kept   things deliberately left alone, as sentences
   scan(out) runs the same reader over the result, which is how the page can say
   "re-read the cleaned file, nothing found" instead of just claiming it. */
(function (root) {
  "use strict";

  const FIXED_DATE = new Date(Date.UTC(1980, 0, 1, 0, 0, 0));
  const MAX_VALUE = 160;

  // ---------- small helpers ----------

  function trunc(s) {
    s = String(s).replace(/[\u0000-\u001f]+/g, " ").trim();
    return s.length > MAX_VALUE ? s.slice(0, MAX_VALUE - 1) + "\u2026" : s;
  }
  function add(found, group, field, value, info) {
    const f = { group: group, field: field, value: value == null ? "" : trunc(value) };
    if (info) f.info = true; // reported but deliberately left in place
    found.push(f);
  }
  function ascii(b, s, e) {
    let out = "";
    for (let i = s; i < e && i < b.length; i++) out += String.fromCharCode(b[i]);
    return out;
  }
  function startsWith(b, off, str) {
    for (let i = 0; i < str.length; i++) if (b[off + i] !== str.charCodeAt(i)) return false;
    return true;
  }
  function utf8(b, s, e) {
    return new TextDecoder("utf-8", { fatal: false }).decode(b.subarray(s, e));
  }
  function concat(parts) {
    let n = 0;
    for (const p of parts) n += p.length;
    const out = new Uint8Array(n);
    let o = 0;
    for (const p of parts) { out.set(p, o); o += p.length; }
    return out;
  }
  function be32(n) { return Uint8Array.of((n >>> 24) & 255, (n >>> 16) & 255, (n >>> 8) & 255, n & 255); }
  function le32(n) { return Uint8Array.of(n & 255, (n >>> 8) & 255, (n >>> 16) & 255, (n >>> 24) & 255); }
  function strBytes(s) { const o = new Uint8Array(s.length); for (let i = 0; i < s.length; i++) o[i] = s.charCodeAt(i) & 255; return o; }

  let crcTable = null;
  function crc32(b) {
    if (!crcTable) {
      crcTable = new Uint32Array(256);
      for (let n = 0; n < 256; n++) {
        let c = n;
        for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
        crcTable[n] = c >>> 0;
      }
    }
    let c = 0xffffffff;
    for (let i = 0; i < b.length; i++) c = crcTable[(c ^ b[i]) & 255] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  }

  function decodeEntities(s) {
    return s
      .replace(/&#x([0-9a-fA-F]+);/g, (_, h) => String.fromCodePoint(parseInt(h, 16)))
      .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(parseInt(d, 10)))
      .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&amp;/g, "&");
  }

  // ---------- EXIF (TIFF) ----------

  const TYPE_SIZE = { 1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8, 12: 8 };
  const IFD0_NAMES = {
    0x010e: "Image description", 0x010f: "Camera make", 0x0110: "Camera model", 0x0131: "Software",
    0x0132: "Date and time", 0x013b: "Artist", 0x013c: "Host computer", 0x8298: "Copyright",
  };
  const EXIF_NAMES = {
    0x9003: "Date taken", 0x9004: "Date digitized", 0xa430: "Camera owner", 0xa431: "Camera serial number",
    0xa433: "Lens make", 0xa434: "Lens model", 0xa435: "Lens serial number", 0xa420: "Image unique ID",
  };

  function parseTiff(b, base, end) {
    const res = { found: [], orientation: 1 };
    if (end - base < 8) return res;
    const le = b[base] === 0x49 && b[base + 1] === 0x49;
    if (!le && !(b[base] === 0x4d && b[base + 1] === 0x4d)) return res;
    const r16 = (o) => (o + 2 > end ? 0 : le ? b[o] | (b[o + 1] << 8) : (b[o] << 8) | b[o + 1]);
    const r32 = (o) => (o + 4 > end ? 0 : (le
      ? b[o] | (b[o + 1] << 8) | (b[o + 2] << 16) | (b[o + 3] << 24)
      : (b[o] << 24) | (b[o + 1] << 16) | (b[o + 2] << 8) | b[o + 3]) >>> 0);

    function valueOf(entry) {
      const type = r16(entry + 2), count = r32(entry + 4), sz = (TYPE_SIZE[type] || 1) * count;
      if (count > 65536 || sz > end - base) return null;
      const off = sz <= 4 ? entry + 8 : base + r32(entry + 8);
      if (off < base || off + sz > end) return null;
      if (type === 2) return ascii(b, off, off + count).replace(/\u0000+$/, "");
      const nums = [];
      for (let i = 0; i < Math.min(count, 8); i++) {
        if (type === 3) nums.push(r16(off + i * 2));
        else if (type === 4) nums.push(r32(off + i * 4));
        else if (type === 5) { const d = r32(off + i * 8 + 4); nums.push(d ? r32(off + i * 8) / d : 0); }
        else if (type === 1 || type === 7) nums.push(b[off + i]);
      }
      return nums;
    }

    const seen = new Set();
    const gps = {};
    function ifd(off, kind, depth) {
      if (depth > 4 || off <= 0 || base + off + 2 > end || seen.has(off)) return 0;
      seen.add(off);
      const n = Math.min(r16(base + off), 512);
      for (let i = 0; i < n; i++) {
        const e = base + off + 2 + i * 12;
        if (e + 12 > end) break;
        const tag = r16(e);
        if (kind === 0) {
          if (tag === 0x0112) { const v = valueOf(e); if (v && v[0]) res.orientation = v[0]; }
          else if (tag === 0x8769) ifd(r32(e + 8), 1, depth + 1);
          else if (tag === 0x8825) ifd(r32(e + 8), 2, depth + 1);
          else if (IFD0_NAMES[tag]) { const v = valueOf(e); if (typeof v === "string" && v.trim()) add(res.found, "Camera and software", IFD0_NAMES[tag], v); }
        } else if (kind === 1) {
          if (EXIF_NAMES[tag]) { const v = valueOf(e); if (typeof v === "string" && v.trim()) add(res.found, "Camera and software", EXIF_NAMES[tag], v); }
          else if (tag === 0x927c) add(res.found, "Camera and software", "Maker note", "manufacturer data, " + r32(e + 4) + " bytes");
          else if (tag === 0x9286) add(res.found, "Camera and software", "User comment", r32(e + 4) + " bytes");
        } else if (kind === 2) {
          const v = valueOf(e);
          if (tag === 1) gps.latRef = v; else if (tag === 2) gps.lat = v;
          else if (tag === 3) gps.lonRef = v; else if (tag === 4) gps.lon = v;
          else if (tag === 6) gps.alt = v;
        }
      }
      return r32(base + off + 2 + n * 12);
    }
    const next = ifd(r32(base + 4), 0, 0);
    if (next) {
      const before = seen.size;
      ifd(next, 3, 0);
      if (seen.size > before) add(res.found, "Camera and software", "Embedded thumbnail", "a second copy of the picture");
    }
    if (gps.lat && gps.lon && gps.lat.length >= 3 && gps.lon.length >= 3) {
      const dec = (a) => a[0] + a[1] / 60 + a[2] / 3600;
      const la = (dec(gps.lat) * (gps.latRef === "S" ? -1 : 1)).toFixed(5);
      const lo = (dec(gps.lon) * (gps.lonRef === "W" ? -1 : 1)).toFixed(5);
      add(res.found, "Location", "GPS position", la + ", " + lo);
      if (gps.alt && gps.alt.length) add(res.found, "Location", "GPS altitude", gps.alt[0].toFixed(1) + " m");
    } else if (Object.keys(gps).length) {
      add(res.found, "Location", "GPS block", "present");
    }
    return res;
  }

  // Smallest valid Exif payload: one Orientation tag, nothing else.
  function minimalTiff(orientation) {
    return Uint8Array.of(
      0x49, 0x49, 0x2a, 0x00, 0x08, 0x00, 0x00, 0x00,
      0x01, 0x00,
      0x12, 0x01, 0x03, 0x00, 0x01, 0x00, 0x00, 0x00, orientation & 255, 0x00, 0x00, 0x00,
      0x00, 0x00, 0x00, 0x00
    );
  }

  // ---------- XMP ----------

  const XMP_TAGS = [
    ["dc:creator", "Author"], ["dc:title", "Title"], ["dc:rights", "Rights"], ["dc:description", "Description"],
    ["dc:subject", "Keywords"], ["xmp:CreatorTool", "Created with"], ["pdf:Producer", "PDF producer"],
    ["pdf:Author", "Author"], ["pdf:Keywords", "Keywords"], ["xmp:Author", "Author"],
    ["photoshop:Credit", "Credit"], ["xmpMM:DocumentID", "Document ID"], ["xmpMM:InstanceID", "Instance ID"],
    ["xmp:CreateDate", "Created"], ["xmp:ModifyDate", "Modified"], ["xmp:MetadataDate", "Metadata date"],
  ];
  function xmpFindings(text, found, size) {
    let n = 0;
    for (const [tag, label] of XMP_TAGS) {
      let val = null;
      const esc = tag.replace(":", "\\:");
      let m = new RegExp("<" + esc + "[^>]*>([\\s\\S]*?)</" + esc + ">").exec(text);
      if (m) {
        const lis = [...m[1].matchAll(/<rdf:li[^>]*>([\s\S]*?)<\/rdf:li>/g)].map((x) => x[1]);
        val = lis.length ? lis.join(", ") : m[1].replace(/<[^>]+>/g, "");
      } else {
        m = new RegExp("\\s" + esc + '="([^"]*)"').exec(text);
        if (m) val = m[1];
      }
      if (val && decodeEntities(val).trim()) { add(found, "XMP packet", label, decodeEntities(val)); n++; }
    }
    if (!n) add(found, "XMP packet", "XMP metadata", size + " bytes");
  }

  // ---------- IPTC (JPEG Photoshop resource) ----------

  const IPTC_NAMES = { 5: "Object name", 25: "Keywords", 80: "By-line", 90: "City", 101: "Country", 116: "Copyright", 120: "Caption" };
  function iptcFindings(b, s, e, found) {
    let p = s + 14; // after "Photoshop 3.0\0"
    let any = false;
    while (p + 12 <= e && startsWith(b, p, "8BIM")) {
      const id = (b[p + 4] << 8) | b[p + 5];
      let q = p + 6;
      const nameLen = b[q];
      q += 1 + nameLen;
      if ((1 + nameLen) % 2) q++;
      const size = ((b[q] << 24) | (b[q + 1] << 16) | (b[q + 2] << 8) | b[q + 3]) >>> 0;
      q += 4;
      if (id === 0x0404) {
        let r = q;
        const stop = Math.min(q + size, e);
        while (r + 5 <= stop && b[r] === 0x1c) {
          const rec = b[r + 1], ds = b[r + 2], len = (b[r + 3] << 8) | b[r + 4];
          if (rec === 2 && IPTC_NAMES[ds] && len) add(found, "IPTC caption data", IPTC_NAMES[ds], utf8(b, r + 5, r + 5 + len));
          any = true;
          r += 5 + len;
        }
      }
      p = q + size + (size % 2);
    }
    if (!any) add(found, "IPTC caption data", "Photoshop resource block", "present");
  }

  // ---------- JPEG ----------

  function jpegOrientation(b) {
    let i = 2;
    while (i + 4 < b.length && b[i] === 0xff) {
      const m = b[i + 1];
      if (m === 0xda || m === 0xd9) break;
      const len = (b[i + 2] << 8) | b[i + 3];
      if (m === 0xe1 && startsWith(b, i + 4, "Exif\u0000\u0000")) return parseTiff(b, i + 10, Math.min(i + 2 + len, b.length)).orientation;
      i += 2 + len;
    }
    return 1;
  }

  function processJpeg(b, opts) {
    opts = opts || {};
    if (!(b[0] === 0xff && b[1] === 0xd8)) throw new Error("This does not look like a JPEG file.");
    const n = b.length, found = [], kept = [], parts = [];
    const orient = opts.keepOrientation === false ? 1 : jpegOrientation(b);
    let i = 2, copyStart = 0, end = n, afterJfif = -1, exifSeg = null;
    if (orient > 1) {
      const tiff = minimalTiff(orient);
      exifSeg = concat([Uint8Array.of(0xff, 0xe1, 0, 2 + 6 + tiff.length), strBytes("Exif\u0000\u0000"), tiff]);
    }
    let sawIccKept = false;
    while (i < n) {
      if (b[i] !== 0xff) { i++; continue; }
      const m = b[i + 1];
      if (m === 0xff) { i++; continue; }
      if (m === 0x00 || m === 0x01 || (m >= 0xd0 && m <= 0xd7) || m === 0xd8) { i += 2; continue; }
      if (m === 0xd9) { end = i + 2; break; }
      const len = (b[i + 2] << 8) | b[i + 3];
      const segEnd = i + 2 + len;
      if (segEnd > n || len < 2) { end = n; break; }
      const p = i + 4;
      let drop = false, replace = null;
      if (m === 0xfe) { drop = true; add(found, "Comments", "JPEG comment", utf8(b, p, segEnd)); }
      else if (m >= 0xe0 && m <= 0xef) {
        if (m === 0xe0) {
          if (startsWith(b, p, "JFIF\u0000")) {
            if (len >= 16 && (b[p + 12] || b[p + 13])) {
              replace = Uint8Array.from(b.subarray(i, i + 18));
              replace[2] = 0; replace[3] = 16; replace[16] = 0; replace[17] = 0;
              add(found, "Camera and software", "Embedded thumbnail", "a small copy of the picture");
            }
          } else { drop = true; add(found, "Camera and software", "JFIF extension", "thumbnail data"); }
        } else if (m === 0xe1) {
          drop = true;
          if (startsWith(b, p, "Exif\u0000\u0000")) { parseTiff(b, p + 6, segEnd).found.forEach((f) => found.push(f)); }
          else if (startsWith(b, p, "http://ns.adobe.com/xap/1.0/\u0000")) xmpFindings(utf8(b, p + 29, segEnd), found, len);
          else if (startsWith(b, p, "http://ns.adobe.com/xmp/extension/")) add(found, "XMP packet", "Extended XMP", len + " bytes");
          else add(found, "Other", "APP1 data", len + " bytes");
        } else if (m === 0xe2) {
          if (startsWith(b, p, "ICC_PROFILE\u0000")) { if (!sawIccKept) kept.push("Color profile kept, so colors look the same."); sawIccKept = true; }
          else { drop = true; add(found, "Other", startsWith(b, p, "MPF") ? "Multi-picture data" : "APP2 data", len + " bytes"); }
        } else if (m === 0xed) {
          drop = true;
          if (startsWith(b, p, "Photoshop 3.0")) iptcFindings(b, p, segEnd, found);
          else add(found, "Other", "APP13 data", len + " bytes");
        } else if (m === 0xee) {
          if (!startsWith(b, p, "Adobe")) { drop = true; add(found, "Other", "APP14 data", len + " bytes"); }
        } else if (m === 0xeb && b[p] === 0x4a && b[p + 1] === 0x50) {
          drop = true; add(found, "Other", "Content Credentials (C2PA)", len + " bytes");
        } else { drop = true; add(found, "Other", "Application data (APP" + (m - 0xe0) + ")", len + " bytes"); }
      }
      if (drop || replace) {
        parts.push(b.subarray(copyStart, i));
        if (replace) parts.push(replace);
        copyStart = segEnd;
      }
      if (m === 0xe0 && i === 2 && !drop) afterJfif = segEnd;
      i = segEnd;
    }
    if (end < n) add(found, "Other", "Data after the end of the image", n - end + " bytes");
    parts.push(b.subarray(copyStart, end));
    let out = concat(parts);
    if (exifSeg) {
      // Insert after a leading JFIF segment if there was one, otherwise right after SOI.
      let at = 2;
      if (afterJfif > 0) {
        // Find where the (possibly patched) JFIF segment ends in the output.
        const l = (out[4] << 8) | out[5];
        at = 2 + 2 + l;
      }
      out = concat([out.subarray(0, at), exifSeg, out.subarray(at)]);
      kept.push("Rotation (orientation " + orient + ") kept so the picture still displays upright.");
    }
    return { kind: "jpeg", found: found, out: out, kept: kept, orientation: orient };
  }

  // ---------- PNG ----------

  const PNG_KEEP = new Set(["IHDR", "PLTE", "IDAT", "IEND", "tRNS", "gAMA", "cHRM", "sRGB", "iCCP", "sBIT", "pHYs", "bKGD", "hIST", "sPLT", "acTL", "fcTL", "fdAT", "cICP", "mDCV", "cLLI"]);
  function processPng(b, opts) {
    opts = opts || {};
    const sig = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
    for (let k = 0; k < 8; k++) if (b[k] !== sig[k]) throw new Error("This does not look like a PNG file.");
    const found = [], kept = [], parts = [b.subarray(0, 8)];
    let i = 8, orient = 1, sawEnd = false, iccKept = false, ihdrEnd = -1;
    while (i + 12 <= b.length) {
      const len = ((b[i] << 24) | (b[i + 1] << 16) | (b[i + 2] << 8) | b[i + 3]) >>> 0;
      const type = ascii(b, i + 4, i + 8);
      const dataS = i + 8, dataE = i + 8 + len, next = dataE + 4;
      if (next > b.length) break;
      const critical = type.charCodeAt(0) < 0x61;
      if (PNG_KEEP.has(type) || critical) {
        parts.push(b.subarray(i, next));
        if (type === "IHDR") ihdrEnd = parts.length;
        if (type === "iCCP" && !iccKept) { kept.push("Color profile kept, so colors look the same."); iccKept = true; }
      } else if (type === "tEXt") {
        let z = dataS; while (z < dataE && b[z] !== 0) z++;
        add(found, "Text chunks", ascii(b, dataS, z), ascii(b, z + 1, dataE));
      } else if (type === "zTXt") {
        let z = dataS; while (z < dataE && b[z] !== 0) z++;
        add(found, "Text chunks", ascii(b, dataS, z), "compressed text");
      } else if (type === "iTXt") {
        let z = dataS; while (z < dataE && b[z] !== 0) z++;
        const key = ascii(b, dataS, z);
        if (key === "XML:com.adobe.xmp" && b[z + 1] === 0) {
          let q = z + 3; for (let nul = 0; q < dataE && nul < 2; q++) if (b[q] === 0) nul++;
          xmpFindings(utf8(b, q, dataE), found, len);
        } else add(found, "Text chunks", key, b[z + 1] === 0 ? utf8(b, z + 3, dataE).replace(/^[^\u0000]*\u0000[^\u0000]*\u0000/, "") : "compressed text");
      } else if (type === "eXIf") {
        const r = parseTiff(b, dataS, dataE);
        r.found.forEach((f) => found.push(f));
        orient = r.orientation;
      } else if (type === "tIME") {
        add(found, "Other", "Last modified time", ((b[dataS] << 8) | b[dataS + 1]) + "-" + b[dataS + 2] + "-" + b[dataS + 3]);
      } else if (type === "caBX") {
        add(found, "Other", "Content Credentials (C2PA)", len + " bytes");
      } else {
        add(found, "Other", "Chunk " + type, len + " bytes");
      }
      i = next;
      if (type === "IEND") { sawEnd = true; break; }
    }
    if (sawEnd && i < b.length) add(found, "Other", "Data after the end of the image", b.length - i + " bytes");
    if (opts.keepOrientation !== false && orient > 1 && ihdrEnd > 0) {
      const tiff = minimalTiff(orient);
      const crcIn = concat([strBytes("eXIf"), tiff]);
      parts.splice(ihdrEnd, 0, concat([be32(tiff.length), crcIn, be32(crc32(crcIn))]));
      kept.push("Rotation (orientation " + orient + ") kept so the picture still displays upright.");
    }
    return { kind: "png", found: found, out: concat(parts), kept: kept, orientation: orient };
  }

  // ---------- WebP ----------

  function processWebp(b, opts) {
    opts = opts || {};
    if (!(startsWith(b, 0, "RIFF") && startsWith(b, 8, "WEBP"))) throw new Error("This does not look like a WebP file.");
    const found = [], kept = [], chunks = [];
    const riffEnd = Math.min(b.length, 8 + ((b[4] | (b[5] << 8) | (b[6] << 16) | (b[7] << 24)) >>> 0));
    let i = 12, orient = 1, hasVp8x = false;
    while (i + 8 <= riffEnd) {
      const type = ascii(b, i, i + 4);
      const len = (b[i + 4] | (b[i + 5] << 8) | (b[i + 6] << 16) | (b[i + 7] << 24)) >>> 0;
      const dataS = i + 8, dataE = Math.min(dataS + len, riffEnd), next = dataS + len + (len % 2);
      if (type === "EXIF") {
        const off = startsWith(b, dataS, "Exif\u0000\u0000") ? dataS + 6 : dataS;
        const r = parseTiff(b, off, dataE);
        r.found.forEach((f) => found.push(f));
        orient = r.orientation;
      } else if (type === "XMP ") {
        xmpFindings(utf8(b, dataS, dataE), found, len);
      } else {
        if (type === "VP8X") hasVp8x = true;
        chunks.push({ type: type, data: Uint8Array.from(b.subarray(dataS, dataE)) });
      }
      i = next;
    }
    if (riffEnd < b.length) add(found, "Other", "Data after the end of the image", b.length - riffEnd + " bytes");
    const keepRot = opts.keepOrientation !== false && orient > 1 && hasVp8x;
    if (hasVp8x) {
      const v = chunks.find((c) => c.type === "VP8X");
      v.data[0] &= ~(0x08 | 0x04);
      if (keepRot) {
        v.data[0] |= 0x08;
        const tiff = minimalTiff(orient);
        chunks.push({ type: "EXIF", data: tiff });
        kept.push("Rotation (orientation " + orient + ") kept so the picture still displays upright.");
      }
    }
    const body = [strBytes("WEBP")];
    for (const c of chunks) {
      body.push(strBytes(c.type), le32(c.data.length), c.data);
      if (c.data.length % 2) body.push(Uint8Array.of(0));
    }
    const payload = concat(body);
    return { kind: "webp", found: found, out: concat([strBytes("RIFF"), le32(payload.length), payload]), kept: kept, orientation: orient };
  }

  function detectImage(b) {
    if (b[0] === 0xff && b[1] === 0xd8) return "jpeg";
    if (b[0] === 0x89 && b[1] === 0x50 && b[2] === 0x4e && b[3] === 0x47) return "png";
    if (startsWith(b, 0, "RIFF") && startsWith(b, 8, "WEBP")) return "webp";
    return null;
  }
  function processImage(b, opts) {
    const k = detectImage(b);
    if (k === "jpeg") return processJpeg(b, opts);
    if (k === "png") return processPng(b, opts);
    if (k === "webp") return processWebp(b, opts);
    throw new Error("Not a JPEG, PNG or WebP image.");
  }

  // ---------- PDF (pdf-lib passed in) ----------

  const INFO_LABELS = {
    Title: "Title", Author: "Author", Subject: "Subject", Keywords: "Keywords", Creator: "Created with",
    Producer: "PDF producer", CreationDate: "Created", ModDate: "Modified", Trapped: "Trapped",
  };
  function pdfText(o) {
    if (!o) return "";
    if (typeof o.decodeText === "function") return o.decodeText();
    if (typeof o.asString === "function") return o.asString();
    if (typeof o.toString === "function") return String(o.toString());
    return "";
  }
  function pdfDate(s) {
    const m = /^D:(\d{4})(\d\d)?(\d\d)?(\d\d)?(\d\d)?(\d\d)?/.exec(s);
    if (!m) return s;
    return m[1] + "-" + (m[2] || "01") + "-" + (m[3] || "01") + (m[4] ? " " + m[4] + ":" + (m[5] || "00") : "");
  }

  function reachable(PDFLib, ctx, roots) {
    const { PDFRef, PDFDict, PDFArray, PDFStream } = PDFLib;
    const seen = new Set();
    const stack = roots.slice();
    while (stack.length) {
      const o = stack.pop();
      if (!o) continue;
      if (o instanceof PDFRef) {
        if (seen.has(o.tag)) continue;
        seen.add(o.tag);
        const t = ctx.lookup(o);
        if (t) stack.push(t);
      } else if (o instanceof PDFStream) stack.push(o.dict);
      else if (o instanceof PDFDict) { for (const [, v] of o.entries()) stack.push(v); }
      else if (o instanceof PDFArray) { for (let i = 0; i < o.size(); i++) stack.push(o.get(i)); }
    }
    return seen;
  }

  async function loadPdf(PDFLib, bytes) {
    try {
      const doc = await PDFLib.PDFDocument.load(bytes, { updateMetadata: false, ignoreEncryption: false, throwOnInvalidObject: false });
      if (!doc.context.trailerInfo.Root || !doc.catalog) throw new Error("no document catalog");
      return doc;
    } catch (e) {
      if (/encrypt/i.test(String(e && e.message))) throw new Error("This PDF is password-protected. Remove the password first, then clean it.");
      throw new Error("This PDF could not be read" + (e && e.message ? " (" + String(e.message).slice(0, 80) + ")" : "") + ".");
    }
  }

  function pdfScan(PDFLib, doc) {
    const { PDFName, PDFDict, PDFArray, PDFStream, PDFRawStream } = PDFLib;
    const ctx = doc.context, found = [];
    const infoRef = ctx.trailerInfo.Info;
    const info = infoRef ? ctx.lookupMaybe(infoRef, PDFDict) : null;
    if (info) {
      for (const [k, v] of info.entries()) {
        const key = k.decodeText();
        let val = pdfText(v);
        if (!val) continue;
        if (key === "CreationDate" || key === "ModDate") val = pdfDate(val);
        if (/^(Trapped)$/.test(key)) continue;
        add(found, "Document properties", INFO_LABELS[key] || key, val);
      }
    }
    const meta = doc.catalog.get(PDFName.of("Metadata"));
    const metaObj = meta && ctx.lookup(meta);
    if (metaObj instanceof PDFStream) {
      let text = "";
      try {
        const bytes = metaObj instanceof PDFRawStream ? PDFLib.decodePDFRawStream(metaObj).decode() : metaObj.getContents();
        text = utf8(bytes, 0, bytes.length);
      } catch (e) { /* fall through with empty text */ }
      xmpFindings(text, found, text.length);
    }
    // Comment and markup authors.
    const authors = new Set();
    let annots = 0;
    for (const page of doc.getPages()) {
      const arr = page.node.Annots();
      if (!arr) continue;
      for (let i = 0; i < arr.size(); i++) {
        const a = ctx.lookupMaybe(arr.get(i), PDFDict);
        if (!a) continue;
        const st = a.get(PDFName.of("Subtype"));
        if (st && /^\/(Widget|Link)$/.test(String(st))) continue;
        const t = a.get(PDFName.of("T"));
        if (t) { const txt = pdfText(t); if (txt && txt !== "Author") { authors.add(txt); annots++; } }
      }
    }
    if (annots) add(found, "Comments", "Comment and markup authors", [...authors].join(", ") + " (" + annots + " annotation" + (annots > 1 ? "s" : "") + ")");
    // Attachments.
    try {
      const names = doc.catalog.lookupMaybe(PDFName.of("Names"), PDFDict);
      const ef = names && names.lookupMaybe(PDFName.of("EmbeddedFiles"), PDFDict);
      const list = ef && ef.lookupMaybe(PDFName.of("Names"), PDFArray);
      if (list && list.size() > 0) add(found, "Left in place", "Attached files", list.size() / 2 + " (they are content)", true);
    } catch (e) { /* ignore */ }
    // Leftover objects from earlier saves.
    const roots = [ctx.trailerInfo.Root];
    if (infoRef) roots.push(infoRef);
    const live = reachable(PDFLib, ctx, roots);
    let orphans = 0;
    for (const [ref, obj] of ctx.enumerateIndirectObjects()) {
      if (live.has(ref.tag)) continue;
      const d = obj instanceof PDFStream ? obj.dict : obj instanceof PDFDict ? obj : null;
      const t = d && d.get(PDFName.of("Type"));
      if (t && /^\/(XRef|ObjStm)$/.test(String(t))) continue;
      orphans++;
    }
    if (orphans) add(found, "Other", "Leftover objects from earlier saves", orphans + " (old versions of edited content)");
    return found;
  }

  async function processPdf(PDFLib, bytes, opts, progress) {
    opts = opts || {}; progress = progress || function () {};
    progress(0.1, "Reading the PDF");
    const { PDFName, PDFDict, PDFStream, PDFRawStream, PDFHexString } = PDFLib;
    const doc = await loadPdf(PDFLib, bytes);
    const ctx = doc.context;
    const found = pdfScan(PDFLib, doc), kept = [];
    // 1. Info dictionary and file ID. Optionally keep the title or set an author.
    const oldInfoRef = ctx.trailerInfo.Info;
    const oldInfo = oldInfoRef ? ctx.lookupMaybe(oldInfoRef, PDFDict) : null;
    const keepTitle = opts.keepTitle && oldInfo ? pdfText(oldInfo.get(PDFName.of("Title"))) : "";
    ctx.trailerInfo.Info = undefined;
    ctx.trailerInfo.ID = undefined;
    if (keepTitle || opts.author) {
      const d = ctx.obj({});
      if (keepTitle) d.set(PDFName.of("Title"), PDFHexString.fromText(keepTitle));
      if (opts.author) d.set(PDFName.of("Author"), PDFHexString.fromText(String(opts.author)));
      ctx.trailerInfo.Info = ctx.register(d);
    }
    progress(0.3, "Removing hidden data");
    // 2. XMP and private application data, anywhere they hang.
    const METADATA = PDFName.of("Metadata"), PIECE = PDFName.of("PieceInfo");
    let jpegs = 0;
    for (const [ref, obj] of ctx.enumerateIndirectObjects()) {
      const d = obj instanceof PDFStream ? obj.dict : obj instanceof PDFDict ? obj : null;
      if (!d) continue;
      if (d.has(METADATA)) d.delete(METADATA);
      if (d.has(PIECE)) d.delete(PIECE);
      if (obj instanceof PDFRawStream) {
        const f = d.get(PDFName.of("Filter"));
        let isDct = f && String(f) === "/DCTDecode";
        if (f && !isDct && f.size && f.size() === 1) isDct = String(f.get(0)) === "/DCTDecode";
        if (isDct && obj.contents[0] === 0xff && obj.contents[1] === 0xd8) {
          try {
            const r = processJpeg(obj.contents, { keepOrientation: false });
            if (r.out.length !== obj.contents.length) { ctx.assign(ref, PDFRawStream.of(d, r.out)); jpegs++; }
          } catch (e) { /* leave this image alone */ }
        }
      }
    }
    if (jpegs) found.push({ group: "Embedded images", field: "Photo metadata inside embedded images", value: jpegs + " image" + (jpegs > 1 ? "s" : "") });
    // 3. Annotation authors.
    if (opts.anonymize !== false) {
      for (const page of doc.getPages()) {
        const arr = page.node.Annots();
        if (!arr) continue;
        for (let i = 0; i < arr.size(); i++) {
          const a = ctx.lookupMaybe(arr.get(i), PDFDict);
          if (!a || !a.has(PDFName.of("T"))) continue;
          const st = a.get(PDFName.of("Subtype"));
          if (st && /^\/(Widget|Link)$/.test(String(st))) continue;
          a.set(PDFName.of("T"), PDFHexString.fromText("Author"));
        }
      }
    }
    // 4. Drop everything no longer reachable (old revisions, the old Info dictionary).
    progress(0.6, "Dropping leftovers");
    const rootsLive = [ctx.trailerInfo.Root];
    if (ctx.trailerInfo.Info) rootsLive.push(ctx.trailerInfo.Info);
    const live = reachable(PDFLib, ctx, rootsLive);
    for (const [ref] of ctx.enumerateIndirectObjects()) if (!live.has(ref.tag)) ctx.delete(ref);
    const pages = doc.getPageCount();
    progress(0.75, "Writing the PDF");
    const out = await doc.save();
    kept.push("Page content is not touched: text, figures and fonts are exactly as they were.");
    return { kind: "pdf", found: found, out: out, kept: kept, pages: pages };
  }

  // ---------- Office files (JSZip passed in) ----------

  const CORE_EMPTY = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"/>';
  const CUSTOM_EMPTY = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"/>';
  const CORE_FIELDS = [
    ["dc:creator", "Author"], ["cp:lastModifiedBy", "Last saved by"], ["dc:title", "Title"], ["dc:subject", "Subject"],
    ["cp:keywords", "Keywords"], ["dc:description", "Comments"], ["cp:category", "Category"],
    ["dcterms:created", "Created"], ["dcterms:modified", "Modified"], ["cp:lastPrinted", "Last printed"],
  ];
  const APP_FIELDS = ["Company", "Manager", "Template", "TotalTime", "Application", "AppVersion", "HyperlinkBase"];
  const REL_LOCAL = /Target="((?:file:\/\/|[A-Za-z]:\\|\\\\|\/Users\/|\/home\/)[^"]*)"/g;

  function xmlTag(xml, tag) {
    const esc = tag.replace(":", "\\:");
    const m = new RegExp("<" + esc + "(?:\\s[^>]*)?>([\\s\\S]*?)</" + esc + ">").exec(xml);
    return m ? decodeEntities(m[1]).trim() : "";
  }
  function dropRel(xml, typeSuffix) {
    return xml.replace(new RegExp('<Relationship\\b[^>]*Type="[^"]*' + typeSuffix + '"[^>]*/>', "g"), "");
  }

  async function removePart(zip, name) {
    zip.remove(name);
    const base = name.split("/").pop();
    for (const relName of Object.keys(zip.files)) {
      if (!relName.endsWith(".rels")) continue;
      const xml = await zip.file(relName).async("string");
      const next = xml.replace(/<Relationship\b[^>]*\/>/g, (rel) => {
        const t = /Target="([^"]*)"/.exec(rel);
        return t && (t[1] === base || t[1].endsWith("/" + base)) ? "" : rel;
      });
      if (next !== xml) zip.file(relName, next);
    }
    const ct = zip.file("[Content_Types].xml");
    if (ct) {
      const xml = await ct.async("string");
      zip.file("[Content_Types].xml", xml.replace(new RegExp('<Override\\b[^>]*PartName="/' + name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + '"[^>]*/>', "g"), ""));
    }
  }

  async function officeScan(zip, found) {
    const names = Object.keys(zip.files).filter((n) => !zip.files[n].dir);
    const read = async (n) => (zip.file(n) ? zip.file(n).async("string") : "");
    const core = await read("docProps/core.xml");
    for (const [tag, label] of CORE_FIELDS) { const v = xmlTag(core, tag); if (v) add(found, "Document properties", label, v); }
    const app = await read("docProps/app.xml");
    for (const tag of APP_FIELDS) { const v = xmlTag(app, tag); if (v && !(tag === "TotalTime" && v === "0")) add(found, "Document properties", tag === "Application" ? "Created with" : tag === "AppVersion" ? "Application version" : tag === "TotalTime" ? "Editing time (minutes)" : tag, v); }
    const custom = await read("docProps/custom.xml");
    const props = [...custom.matchAll(/<property\b[^>]*\sname="([^"]*)"/g)].map((m) => decodeEntities(m[1]));
    if (props.length) add(found, "Document properties", "Custom properties", props.join(", "));
    const thumb = names.find((n) => /^docProps\/thumbnail\./.test(n));
    if (thumb) add(found, "Document properties", "Preview thumbnail", "a small picture of the first page or sheet");
    // Revision authors, comment authors, people lists.
    const authors = new Set();
    let revisions = 0, rsid = 0;
    for (const n of names) {
      if (/^word\/[^/]+\.xml$/.test(n)) {
        const x = await read(n);
        for (const m of x.matchAll(/\bw:author="([^"]*)"/g)) { if (m[1] !== "Author") { authors.add(decodeEntities(m[1])); revisions++; } }
        rsid += (x.match(/\sw:rsid[A-Za-z]*="[0-9A-Fa-f]+"/g) || []).length;
      } else if (/^xl\/comments(?:[^/]*|\/[^/]+)\.xml$/.test(n)) {
        const x = await read(n);
        for (const m of x.matchAll(/<author>([^<]*)<\/author>/g)) { if (m[1] !== "Author") { authors.add(decodeEntities(m[1])); revisions++; } }
      } else if (/^xl\/persons\/[^/]+\.xml$/.test(n)) {
        const x = await read(n);
        for (const m of x.matchAll(/\sdisplayName="([^"]*)"/g)) { if (m[1] !== "Author") authors.add(decodeEntities(m[1])); }
      } else if (n === "ppt/commentAuthors.xml" || /^ppt\/authors\.xml$/.test(n)) {
        const x = await read(n);
        for (const m of x.matchAll(/\sname="([^"]*)"/g)) { if (m[1] !== "Author") authors.add(decodeEntities(m[1])); }
      }
    }
    if (authors.size) add(found, "Comments and revisions", "Names on comments, tracked changes and reviewers", [...authors].join(", "));
    if (names.includes("word/people.xml")) add(found, "Comments and revisions", "People list", "names and account ids of everyone who edited");
    if (rsid) add(found, "Comments and revisions", "Editing-session ids", rsid + " markers (show which edits happened in the same sitting)");
    // Local paths.
    for (const n of names.filter((x) => x.endsWith(".rels"))) {
      const x = await read(n);
      for (const m of x.matchAll(REL_LOCAL)) add(found, "Paths", "Link to a file on a computer", decodeEntities(m[1]));
    }
    const wb = await read("xl/workbook.xml");
    const ap = /x15ac:absPath[^>]*\surl="([^"]*)"/.exec(wb);
    if (ap) add(found, "Paths", "Folder the workbook was saved in", decodeEntities(ap[1]));
    // Embedded photos.
    let withMeta = 0, gps = 0;
    for (const n of names.filter((x) => /\/media\/[^/]+\.(jpe?g|png|webp)$/i.test(x))) {
      try {
        const r = processImage(await zip.file(n).async("uint8array"), { keepOrientation: true });
        if (r.found.length) withMeta++;
        if (r.found.some((f) => f.group === "Location")) gps++;
      } catch (e) { /* skip unreadable image */ }
    }
    if (withMeta) add(found, "Embedded images", "Photo metadata inside embedded images", withMeta + " image" + (withMeta > 1 ? "s" : "") + (gps ? ", " + gps + " with a GPS position" : ""));
    const cx = names.filter((n) => n.startsWith("customXml/") && /\.xml$/.test(n) && !/Props\d*\.xml$/.test(n) && !/_rels/.test(n));
    if (cx.length) add(found, "Left in place", "Custom XML parts", cx.length + " (SharePoint or add-in data)", true);
  }

  async function processOffice(JSZip, bytes, opts, progress) {
    opts = opts || {}; progress = progress || function () {};
    progress(0.1, "Opening the file");
    const zip = await JSZip.loadAsync(bytes);
    const names = Object.keys(zip.files).filter((n) => !zip.files[n].dir);
    let kind = null;
    if (names.some((n) => n.startsWith("word/"))) kind = "docx";
    else if (names.some((n) => n.startsWith("xl/"))) kind = "xlsx";
    else if (names.some((n) => n.startsWith("ppt/"))) kind = "pptx";
    if (!kind) throw new Error("This zip is not a Word, Excel or PowerPoint file.");
    const found = [], kept = [];
    await officeScan(zip, found);
    const anonymize = opts.anonymize !== false;
    const read = async (n) => zip.file(n).async("string");
    // Every XML part we rewrite must still be well-formed, or the whole clean is refused.
    const put = (n, x) => { if (/\.(xml|rels)$/.test(n)) mustBeWellFormed(n, x); zip.file(n, x); };

    if (zip.file("docProps/core.xml")) {
      const oldCore = await read("docProps/core.xml");
      const t = opts.keepTitle ? xmlTag(oldCore, "dc:title") : "";
      const au = opts.author ? String(opts.author) : "";
      put("docProps/core.xml", t || au
        ? CORE_EMPTY.replace(/\/>$/, ">" + (t ? "<dc:title>" + xmlEsc(t) + "</dc:title>" : "") + (au ? "<dc:creator>" + xmlEsc(au) + "</dc:creator>" : "") + "</cp:coreProperties>")
        : CORE_EMPTY);
    }
    if (zip.file("docProps/custom.xml")) put("docProps/custom.xml", CUSTOM_EMPTY);
    if (zip.file("docProps/app.xml")) {
      let x = await read("docProps/app.xml");
      x = x.replace(new RegExp("<(" + APP_FIELDS.join("|") + ")\\b[^>]*?(?:/>|>[\\s\\S]*?</\\1>)", "g"), "");
      put("docProps/app.xml", x);
    }
    for (const n of names.filter((x) => /^docProps\/thumbnail\./.test(x))) await removePart(zip, n);
    if (names.includes("word/people.xml")) await removePart(zip, "word/people.xml");

    let doneParts = 0;
    for (const n of names) {
      progress(0.15 + 0.65 * (doneParts++ / names.length), "Cleaning " + n.split("/").pop());
      if (!zip.file(n)) continue;
      if (/^word\/[^/]+\.xml$/.test(n)) {
        let x = await read(n), y = x;
        y = y.replace(/\sw:rsid[A-Za-z]*="[0-9A-Fa-f]+"/g, "");
        if (n === "word/settings.xml") {
          y = y.replace(/<w:rsids>[\s\S]*?<\/w:rsids>/g, "").replace(/<w:rsidRoot\b[^>]*\/>/g, "");
          y = y.replace(/<w:attachedTemplate\b[^>]*\/>/g, "");
        }
        if (anonymize) {
          y = y.replace(/\bw:author="[^"]*"/g, 'w:author="Author"').replace(/\sw:initials="[^"]*"/g, "")
            .replace(/\sw:date="[^"]*"/g, "").replace(/\sw16du:dateUtc="[^"]*"/g, "").replace(/\sw16cex:dateUtc="[^"]*"/g, "");
        }
        if (y !== x) put(n, y);
      } else if (n === "word/_rels/settings.xml.rels") {
        const x = await read(n), y = dropRel(x, "/attachedTemplate");
        if (y !== x) put(n, y);
      } else if (anonymize && /^xl\/comments(?:[^/]*|\/[^/]+)\.xml$/.test(n)) {
        const x = await read(n);
        put(n, x.replace(/<author>[^<]*<\/author>/g, "<author>Author</author>"));
      } else if (anonymize && /^xl\/persons\/[^/]+\.xml$/.test(n)) {
        const x = await read(n);
        put(n, x.replace(/\sdisplayName="[^"]*"/g, ' displayName="Author"').replace(/\suserId="[^"]*"/g, ' userId="Author"').replace(/\sproviderId="[^"]*"/g, ' providerId="None"'));
      } else if (anonymize && /^xl\/threadedComments\/[^/]+\.xml$/.test(n)) {
        const x = await read(n);
        put(n, x.replace(/\sdT="[^"]*"/g, ""));
      } else if (anonymize && (n === "ppt/commentAuthors.xml" || n === "ppt/authors.xml")) {
        const x = await read(n);
        put(n, x.replace(/\sname="[^"]*"/g, ' name="Author"').replace(/\sinitials="[^"]*"/g, ' initials="A"')
          .replace(/\suserId="[^"]*"/g, ' userId="Author"').replace(/\sproviderId="[^"]*"/g, ' providerId="None"'));
      } else if (n === "xl/workbook.xml") {
        const x = await read(n);
        put(n, x.replace(/<mc:AlternateContent\b[^>]*>\s*<mc:Choice\b[^>]*>\s*<x15ac:absPath\b[^>]*\/>\s*<\/mc:Choice>\s*<\/mc:AlternateContent>/g, ""));
      } else if (/\/media\/[^/]+\.(jpe?g|png|webp)$/i.test(n)) {
        try {
          const r = processImage(await zip.file(n).async("uint8array"), { keepOrientation: true });
          if (r.found.length) zip.file(n, r.out);
        } catch (e) { /* leave unreadable images as they are */ }
      }
    }
    zip.forEach((p, f) => { f.date = FIXED_DATE; });
    progress(0.85, "Writing the file");
    const out = await zip.generateAsync({ type: "uint8array", compression: "DEFLATE", compressionOptions: { level: 6 } });
    kept.push("Text, tables, slides and pictures are not touched. Names typed into the body are content, not metadata.");
    return { kind: kind, found: found, out: out, kept: kept };
  }

  // ---------- Text ----------

  function cleanText(s, opts) {
    opts = opts || {};
    const counts = {};
    const bump = (label, n) => { counts[label] = (counts[label] || 0) + n; };
    let t = String(s);
    // Tag characters (U+E0000-E007F) hide text from a reader. Keep the flag-emoji sequences that use them.
    t = t.replace(/(\u{1F3F4})?([\u{E0020}-\u{E007E}]+\u{E007F})|[\u{E0000}-\u{E007F}]/gu, (m, flag, tail) => {
      if (flag && tail) return m;
      bump("Hidden tag characters (can carry invisible instructions)", [...m].length);
      return "";
    });
    t = t.replace(/[\u{E0100}-\u{E01EF}]/gu, (m) => { bump("Variation selectors used to hide data", 1); return ""; });
    t = t.replace(/[\u200B\u2060\uFEFF]/g, (m) => { bump("Zero-width characters", 1); return ""; });
    t = t.replace(/(?<![^\u0000-\u007f])[\u200C\u200D](?![^\u0000-\u007f])/g, () => { bump("Zero-width joiners between plain letters", 1); return ""; });
    t = t.replace(/[\u200E\u200F\u061C\u202A-\u202E\u2066-\u2069]/g, () => { bump("Text-direction controls", 1); return ""; });
    t = t.replace(/[\u00AD\u180E\u2061-\u2064\u115F\u1160\u3164\uFFA0]/g, () => { bump("Soft hyphens and invisible operators", 1); return ""; });
    t = t.replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F-\u009F]/g, () => { bump("Control characters", 1); return ""; });
    if (opts.spaces !== false) {
      t = t.replace(/[\u00A0\u1680\u2000-\u200A\u202F\u205F\u3000]/g, () => { bump("Non-breaking and wide spaces", 1); return " "; });
      t = t.replace(/[\u2028\u2029]/g, () => { bump("Line and paragraph separators", 1); return "\n"; });
    }
    if (opts.typography) {
      t = t.replace(/[\u2018\u2019\u201A\u201B]/g, () => { bump("Curly single quotes", 1); return "'"; })
        .replace(/[\u201C\u201D\u201E\u201F]/g, () => { bump("Curly double quotes", 1); return '"'; })
        .replace(/[\u2013\u2014\u2212]/g, () => { bump("Dashes", 1); return "-"; })
        .replace(/\u2026/g, () => { bump("Ellipsis characters", 1); return "..."; });
    }
    if (opts.trim) {
      const before = t;
      t = t.replace(/[ \t]+$/gm, "");
      const d = before.length - t.length;
      if (d) bump("Trailing spaces", d);
    }
    return { text: t, counts: counts, total: Object.values(counts).reduce((a, b) => a + b, 0) };
  }

  // ---------- XML helpers ----------

  // Light well-formedness check: tags balance and nothing stray sits between them.
  // Used on every XML part this file rewrites, so a bad edit is caught before download.
  function wellFormed(xml) {
    const re = /<!--[\s\S]*?-->|<!\[CDATA\[[\s\S]*?\]\]>|<\?[\s\S]*?\?>|<!DOCTYPE[^>\[]*(?:\[[\s\S]*?\])?\s*>|<\/([^\s>]+)\s*>|<([^\s\/>!?]+)((?:[^>"']|"[^"]*"|'[^']*')*?)(\/?)>/g;
    const stack = [];
    let m, last = 0;
    while ((m = re.exec(xml))) {
      if (xml.slice(last, m.index).indexOf("<") !== -1) return false;
      last = re.lastIndex;
      if (m[1] !== undefined) { if (stack.pop() !== m[1]) return false; }
      else if (m[2] !== undefined && m[4] !== "/") stack.push(m[2]);
    }
    if (xml.slice(last).indexOf("<") !== -1) return false;
    return stack.length === 0;
  }
  function xmlEsc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
  function mustBeWellFormed(name, xml) {
    if (!wellFormed(xml)) throw new Error("Cleaning would have broken " + name + ", so nothing was changed. Your original is untouched.");
  }

  // ---------- GIF ----------

  function processGif(b) {
    if (!(startsWith(b, 0, "GIF87a") || startsWith(b, 0, "GIF89a"))) throw new Error("This does not look like a GIF file.");
    const found = [], parts = [];
    let i = 13, copyStart = 0;
    if (b[10] & 0x80) i += 3 * (1 << ((b[10] & 7) + 1));
    function skipSub(p) { while (p < b.length && b[p] !== 0) p += b[p] + 1; return p + 1; }
    let end = b.length;
    while (i < b.length) {
      const t = b[i];
      if (t === 0x3b) { end = i + 1; break; }
      if (t === 0x21) {
        const label = b[i + 1];
        const next = label === 0xff ? skipSub(i + 3 + b[i + 2]) : skipSub(i + 2);
        // Application extension: id is 8 bytes + 3 byte auth code, announced by block size 11.
        let drop = false;
        if (label === 0xfe) { drop = true; add(found, "Comments", "GIF comment", utf8(b, i + 2, next).replace(/[\u0000-\u001f]/g, "")); }
        else if (label === 0xff) {
          const id = ascii(b, i + 3, i + 3 + 11);
          if (/^XMP Data/.test(id)) { drop = true; add(found, "XMP packet", "XMP metadata", (next - i) + " bytes"); }
          else if (!/^(NETSCAPE2\.0|ANIMEXTS1\.0|ICCRGBG1012)/.test(id)) { drop = true; add(found, "Other", "Application block", id.slice(0, 8).trim()); }
        }
        if (drop) { parts.push(b.subarray(copyStart, i)); copyStart = next; }
        i = next;
      } else if (t === 0x2c) {
        let p = i + 10;
        if (b[i + 9] & 0x80) p += 3 * (1 << ((b[i + 9] & 7) + 1));
        p += 1;
        i = skipSub(p);
      } else { i++; }
    }
    if (end < b.length) add(found, "Other", "Data after the end of the image", (b.length - end) + " bytes");
    parts.push(b.subarray(copyStart, end));
    return { kind: "gif", found: found, out: concat(parts), kept: [] };
  }

  // ---------- SVG ----------

  function processSvg(b) {
    const text = utf8(b, 0, b.length);
    if (!/<svg[\s>]/.test(text)) throw new Error("This does not look like an SVG file.");
    mustBeWellFormed("the SVG", text);
    const found = [];
    let t = text;
    const meta = [...t.matchAll(/<metadata\b[\s\S]*?<\/metadata>/g)];
    meta.forEach((m) => xmpFindings(m[0], found, m[0].length));
    t = t.replace(/<metadata\b[\s\S]*?<\/metadata>/g, "");
    const comments = [...t.matchAll(/<!--([\s\S]*?)-->/g)].filter((m) => m[1].trim());
    comments.slice(0, 3).forEach((m) => add(found, "Comments", "XML comment", m[1]));
    if (comments.length > 3) add(found, "Comments", "More comments", (comments.length - 3) + " more");
    t = t.replace(/<!--[\s\S]*?-->/g, "");
    const attr = (name) => { const m = new RegExp("\\s" + name + '="([^"]*)"').exec(t); return m ? decodeEntities(m[1]) : ""; };
    if (attr("sodipodi:docname")) add(found, "Paths", "Document name", attr("sodipodi:docname"));
    if (attr("inkscape:export-filename")) add(found, "Paths", "Export path", attr("inkscape:export-filename"));
    if (attr("inkscape:version")) add(found, "Camera and software", "Created with", "Inkscape " + attr("inkscape:version"));
    if (/<sodipodi:namedview\b/.test(t) || /\sinkscape:[\w-]+=/.test(t)) {
      t = t.replace(/<sodipodi:namedview\b[\s\S]*?(?:\/>|<\/sodipodi:namedview>)/g, "");
      t = t.replace(/\s(?:inkscape|sodipodi):[\w-]+="[^"]*"/g, "");
      add(found, "Other", "Editor settings", "window, grid and layer data from Inkscape");
    }
    if (/<i:pgf\b/.test(t)) {
      t = t.replace(/<i:pgf\b[\s\S]*?<\/i:pgf>/g, "");
      add(found, "Other", "Illustrator private data", "embedded editing data");
    }
    t = t.replace(/<\?xpacket[\s\S]*?\?>/g, "");
    // Drop namespace declarations no longer used.
    for (const p of ["inkscape", "sodipodi", "dc", "cc", "rdf", "i", "x", "a", "xmpGImg", "xmp", "xmpMM", "stRef", "stEvt", "illustrator", "pdf", "pdfx", "xapGImg"]) {
      const decl = new RegExp('\\sxmlns:' + p + '="[^"]*"', "g");
      if (decl.test(t) && !new RegExp("[<\\s/]" + p + ":", "g").test(t.replace(decl, ""))) t = t.replace(decl, "");
    }
    t = t.replace(/\n\s*\n+/g, "\n");
    mustBeWellFormed("the SVG", t);
    return { kind: "svg", found: found, out: new TextEncoder().encode(t), kept: ["Drawing, text and styling are not touched."] };
  }

  // ---------- TIFF (byte-level, in place) ----------

  const TIFF_DROP = new Set([269, 270, 271, 272, 285, 305, 306, 315, 316, 33432, 700, 33723, 34377, 34665, 34853, 50341, 37724, 40091, 40092, 40093, 40094, 40095, 18246, 18247, 18248, 18249]);
  const TIFF_TYPE = { 1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8, 13: 4 };

  function processTiff(b0, opts) {
    opts = opts || {};
    const b = Uint8Array.from(b0);
    const le = b[0] === 0x49 && b[1] === 0x49;
    if (!(le || (b[0] === 0x4d && b[1] === 0x4d)) || (le ? b[2] | (b[3] << 8) : (b[2] << 8) | b[3]) !== 42) {
      throw new Error(b[2] === 43 || b[3] === 43 ? "BigTIFF files are not supported." : "This does not look like a TIFF file.");
    }
    const n = b.length, touched = [];
    const r16 = (o) => (le ? b[o] | (b[o + 1] << 8) : (b[o] << 8) | b[o + 1]);
    const r32 = (o) => (le ? (b[o] | (b[o + 1] << 8) | (b[o + 2] << 16) | (b[o + 3] << 24)) >>> 0 : ((b[o] << 24) | (b[o + 1] << 16) | (b[o + 2] << 8) | b[o + 3]) >>> 0);
    const w32 = (o, v) => { if (le) { b[o] = v & 255; b[o + 1] = (v >>> 8) & 255; b[o + 2] = (v >>> 16) & 255; b[o + 3] = (v >>> 24) & 255; } else { b[o] = (v >>> 24) & 255; b[o + 1] = (v >>> 16) & 255; b[o + 2] = (v >>> 8) & 255; b[o + 3] = v & 255; } };
    const found = parseTiff(b, 0, n).found.filter((f) => f.field !== "Embedded thumbnail");
    const zero = (s, e) => { if (e > s) { b.fill(0, s, e); touched.push([s, e]); } };
    const seen = new Set();
    let dropped = 0;

    function extSize(e) { return (TIFF_TYPE[r16(e + 2)] || 1) * r32(e + 4); }
    function zeroValue(e) {
      const sz = extSize(e);
      if (sz > 4) { const off = r32(e + 8); if (off + sz <= n) zero(off, off + sz); }
    }
    function zeroIfd(off, depth) {
      if (depth > 3 || off < 8 || off + 2 > n || seen.has(off)) return;
      seen.add(off);
      const cnt = r16(off);
      for (let i = 0; i < cnt && off + 2 + i * 12 + 12 <= n; i++) {
        const e = off + 2 + i * 12, tag = r16(e);
        if (tag === 34665 || tag === 34853 || tag === 40965) zeroIfd(r32(e + 8), depth + 1);
        zeroValue(e);
      }
      zero(off, Math.min(n, off + 2 + cnt * 12 + 4));
    }
    function cleanIfd(off, depth) {
      if (depth > 64 || off < 8 || off + 2 > n || seen.has(off)) return 0;
      seen.add(off);
      const cnt = r16(off);
      if (off + 2 + cnt * 12 + 4 > n) throw new Error("This TIFF is damaged.");
      const keep = [];
      let subs = [];
      for (let i = 0; i < cnt; i++) {
        const e = off + 2 + i * 12, tag = r16(e);
        if (tag === 330) { const sz = extSize(e); const cntS = r32(e + 4); if (cntS === 1) subs.push(r32(e + 8)); else if (sz <= n) for (let k = 0; k < cntS && k < 16; k++) subs.push(r32(r32(e + 8) + 4 * k)); }
        if (TIFF_DROP.has(tag)) {
          if (tag === 34665 || tag === 34853) zeroIfd(r32(e + 8), 0);
          zeroValue(e);
          dropped++;
        } else keep.push(Uint8Array.from(b.subarray(e, e + 12)));
      }
      const next = r32(off + 2 + cnt * 12);
      const newCnt = keep.length;
      if (newCnt !== cnt) {
        b[off] = le ? newCnt & 255 : (newCnt >> 8) & 255; b[off + 1] = le ? (newCnt >> 8) & 255 : newCnt & 255;
        keep.forEach((k, i) => b.set(k, off + 2 + i * 12));
        w32(off + 2 + newCnt * 12, next);
        zero(off + 2 + newCnt * 12 + 4, off + 2 + cnt * 12 + 4);
        touched.push([off, off + 2 + newCnt * 12 + 4]);
      }
      subs.forEach((s) => cleanIfd(s, depth + 1));
      return next;
    }
    let ifd = r32(4), guard = 0;
    while (ifd && guard++ < 64) ifd = cleanIfd(ifd, 0);
    if (dropped && !found.length) add(found, "Other", "Metadata tags", dropped + " tag" + (dropped > 1 ? "s" : ""));
    return { kind: "tiff", found: found, out: b, kept: ["Color profile and rotation are kept; the image data is byte-for-byte the same."], touched: touched, original: b0 };
  }

  // ---------- MP4 / MOV (boxes blanked in place, so no offsets move) ----------

  const MP4_TEXT = { "xyz": "GPS position", "mak": "Camera make", "mod": "Camera model", "swr": "Software", "too": "Created with", "nam": "Title", "ART": "Artist", "alb": "Album", "day": "Date", "cmt": "Comment", "des": "Description", "cpy": "Copyright", "aut": "Author", "inf": "Information", "wrt": "Writer", "grp": "Group", "enc": "Encoded by", "dir": "Director", "prd": "Producer" };
  function iso6709(s) {
    const m = /^([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)/.exec(s);
    return m ? parseFloat(m[1]).toFixed(5) + ", " + parseFloat(m[2]).toFixed(5) : s;
  }

  function processMp4(b, opts) {
    opts = opts || {};
    const n = b.length, found = [], kept = [];
    const dv = new DataView(b.buffer, b.byteOffset, b.byteLength);
    const u32 = (o) => dv.getUint32(o);
    const view = (o, len) => b.subarray(o, o + len);
    function boxAt(o, end) {
      if (o + 8 > end) return null;
      let size = u32(o), hdr = 8;
      const type = ascii(b, o + 4, o + 8);
      if (size === 1) { if (o + 16 > end) return null; size = u32(o + 8) * 4294967296 + u32(o + 12); hdr = 16; }
      else if (size === 0) size = end - o;
      if (size < hdr || o + size > end) return null;
      return { o: o, size: size, hdr: hdr, type: type, end: o + size, p: o + hdr };
    }
    function children(box, skip) {
      const out = [];
      let o = box.p + (skip || 0);
      for (;;) { const c = boxAt(o, box.end); if (!c) break; out.push(c); o = c.end; }
      return out;
    }
    function blank(box) {
      if (!opts.scanOnly) { b.set(strBytes("free"), box.o + 4); b.fill(0, box.p, box.end); }
    }
    function typeLabel(t) { return t.charCodeAt(0) === 0xa9 ? MP4_TEXT[t.slice(1)] || t.slice(1) : t; }
    function textOf(c) {
      // c-symbol xyz style: 2 byte length, 2 byte language, text. 3GPP boxes start with version/flags + language.
      const len = (b[c.p] << 8) | b[c.p + 1];
      if (c.type.charCodeAt(0) === 0xa9 && len <= c.size - c.hdr - 4) return utf8(b, c.p + 4, c.p + 4 + len);
      return utf8(b, c.p, c.end).replace(/[\u0000-\u001f]/g, " ");
    }
    function readMeta(meta) {
      const kids = children(meta, 4);
      const keysBox = kids.find((k) => k.type === "keys");
      const keys = [];
      if (keysBox) { let o = keysBox.p + 8; for (let i = 0; i < u32(keysBox.p + 4) && o + 8 <= keysBox.end; i++) { const sz = u32(o); keys.push(ascii(b, o + 8, o + sz)); o += sz; } }
      const ilst = kids.find((k) => k.type === "ilst");
      if (!ilst) return;
      for (const item of children(ilst)) {
        const data = children(item).find((d) => d.type === "data");
        if (!data) continue;
        const flag = u32(data.p) & 0xffffff;
        let val = flag === 1 || flag === 0 ? utf8(b, data.p + 8, data.end) : "(" + (data.end - data.p - 8) + " bytes)";
        let label = item.type;
        const idx = u32(item.o + 4);
        if (item.type.charCodeAt(0) !== 0xa9 && keys[idx - 1]) label = keys[idx - 1].replace(/^com\.apple\.quicktime\./, "");
        else label = typeLabel(item.type);
        if (/location|xyz|iso6709/i.test(label)) { add(found, "Location", "GPS position", iso6709(val)); continue; }
        if (/creationdate|^day$/i.test(label)) { add(found, "Camera and software", "Recorded", val); continue; }
        label = label.replace(/_/g, " "); add(found, "Camera and software", /^[a-z]/.test(label) ? label.charAt(0).toUpperCase() + label.slice(1) : label, val);
      }
    }
    function readUdta(u) {
      for (const c of children(u)) {
        if (c.type === "meta") { readMeta(c); continue; }
        if (c.type.charCodeAt(0) === 0xa9) {
          const txt = textOf(c);
          if (!txt) continue;
          if (c.type.slice(1) === "xyz") add(found, "Location", "GPS position", iso6709(txt));
          else add(found, "Camera and software", typeLabel(c.type), txt);
        } else if (["titl", "auth", "dscp", "cprt", "perf", "yrrc", "name"].includes(c.type)) {
          add(found, "Camera and software", typeLabel(c.type), utf8(b, c.p + (c.type === "name" ? 0 : 6), c.end));
        } else if (c.type === "loci") {
          // 3GPP location: version/flags, language, null-terminated name, role, then longitude, latitude, altitude as 16.16 fixed point.
          let q = c.p + 6;
          while (q < c.end && b[q] !== 0) q++;
          q += 2;
          if (q + 8 <= c.end) { const fx = (o) => dv.getInt32(o) / 65536; add(found, "Location", "GPS position", fx(q + 4).toFixed(5) + ", " + fx(q).toFixed(5)); }
        } else if (c.type !== "free" && c.type !== "skip" && c.type !== "WLOC") {
          add(found, "Other", "User data: " + c.type, (c.size - c.hdr) + " bytes");
        }
      }
    }
    const MAC_EPOCH = 2082844800;
    function stampBox(box, fieldStart, label) {
      // version 0: 4 byte times; version 1: 8 byte times. creation and modification, back to back.
      const ver = b[box.p], w = ver === 1 ? 8 : 4, off = box.p + 4 + fieldStart;
      let secs = 0;
      for (let i = 0; i < w; i++) secs = secs * 256 + b[off + i];
      if (secs > MAC_EPOCH) { add(found, "Camera and software", label, new Date((secs - MAC_EPOCH) * 1000).toISOString().replace(/\.\d+Z$/, "Z")); }
      if (!opts.scanOnly) b.fill(0, off, off + 2 * w);
    }

    let moovSeen = false;
    for (let o = 0; o < n;) {
      const box = boxAt(o, n);
      if (!box) { if (o < n) add(found, "Other", "Unreadable data at the end", (n - o) + " bytes (left in place)"); break; }
      if (box.type === "moov") {
        moovSeen = true;
        for (const c of children(box)) {
          if (c.type === "mvhd") stampBox(c, 0, "Recorded (movie header)");
          else if (c.type === "udta") { readUdta(c); blank(c); }
          else if (c.type === "meta") { readMeta(c); blank(c); }
          else if (c.type === "Xtra") { add(found, "Other", "Windows media tags", (c.size - c.hdr) + " bytes"); blank(c); }
          else if (c.type === "uuid") { add(found, "Other", "Private data (uuid)", (c.size - c.hdr) + " bytes"); blank(c); }
          else if (c.type === "trak") {
            for (const t of children(c)) {
              if (t.type === "tkhd") stampBox(t, 0, "Track created");
              else if (t.type === "udta") { readUdta(t); blank(t); }
              else if (t.type === "meta") { readMeta(t); blank(t); }
              else if (t.type === "mdia") {
                for (const m of children(t)) {
                  if (m.type === "mdhd") stampBox(m, 0, "Track created");
                  else if (m.type === "hdlr") {
                    const h = ascii(b, m.p + 8, m.p + 12);
                    if (h === "meta" || h === "mett" || h === "camm" || h === "gpmd") add(found, "Left in place", "Timed metadata track", "GPS or motion data recorded alongside the video; removing it needs re-muxing", true);
                  }
                }
              }
            }
          }
        }
      } else if (box.type === "uuid") {
        add(found, "XMP packet", "Private data (uuid)", (box.size - box.hdr) + " bytes"); blank(box);
      } else if (box.type === "meta" || box.type === "udta") { readMeta(box); blank(box); }
      o = box.end;
    }
    if (!moovSeen) throw new Error("This does not look like an MP4 or MOV video.");
    // De-duplicate repeated findings (track and movie both carry a time).
    const seenKeys = new Set();
    const uniq = found.filter((f) => { const k = f.field + "|" + f.value; if (seenKeys.has(k)) return false; seenKeys.add(k); return true; });
    kept.push("Picture and sound are not re-encoded. Removed boxes are blanked in place, so nothing moves and playback is unchanged.");
    return { kind: "mp4", found: uniq, out: b, kept: kept };
  }

  // ---------- OpenDocument (JSZip passed in) ----------

  const ODF_META_FIELDS = [
    ["meta:initial-creator", "Author"], ["dc:creator", "Last saved by"], ["dc:title", "Title"], ["dc:subject", "Subject"],
    ["dc:description", "Comments"], ["meta:keyword", "Keywords"], ["meta:creation-date", "Created"], ["dc:date", "Modified"],
    ["meta:generator", "Created with"], ["meta:editing-duration", "Editing time"],
  ];
  async function odfScan(zip, found) {
    const names = Object.keys(zip.files).filter((n) => !zip.files[n].dir);
    const read = async (n) => (zip.file(n) ? zip.file(n).async("string") : "");
    const meta = await read("meta.xml");
    for (const [tag, label] of ODF_META_FIELDS) {
      if (tag === "meta:keyword") { const kws = [...meta.matchAll(/<meta:keyword>([^<]*)<\/meta:keyword>/g)].map((m) => decodeEntities(m[1])); if (kws.length) add(found, "Document properties", label, kws.join(", ")); continue; }
      const v = xmlTag(meta, tag); if (v) add(found, "Document properties", label, v);
    }
    const custom = [...meta.matchAll(/<meta:user-defined\b[^>]*meta:name="([^"]*)"/g)].map((m) => decodeEntities(m[1]));
    if (custom.length) add(found, "Document properties", "Custom properties", custom.join(", "));
    const tpl = /<meta:template\b[^>]*xlink:href="([^"]*)"/.exec(meta);
    if (tpl && tpl[1]) add(found, "Paths", "Template path", decodeEntities(tpl[1]));
    if (names.some((n) => /^Thumbnails\//.test(n))) add(found, "Document properties", "Preview thumbnail", "a small picture of the first page");
    const authors = new Set();
    for (const n of ["content.xml", "styles.xml"]) {
      const x = await read(n);
      for (const m of x.matchAll(/<dc:creator>([^<]*)<\/dc:creator>/g)) if (m[1] !== "Author") authors.add(decodeEntities(m[1]));
    }
    if (authors.size) add(found, "Comments and revisions", "Names on comments and tracked changes", [...authors].join(", "));
    const settings = await read("settings.xml");
    const pr = /config:name="PrinterName"[^>]*>([^<]+)</.exec(settings);
    if (pr) add(found, "Other", "Printer name", decodeEntities(pr[1]));
    let withMeta = 0;
    for (const n of names.filter((x) => /\.(jpe?g|png|webp)$/i.test(x))) {
      try { if (processImage(await zip.file(n).async("uint8array"), { keepOrientation: true }).found.length) withMeta++; } catch (e) { /* skip */ }
    }
    if (withMeta) add(found, "Embedded images", "Photo metadata inside embedded images", withMeta + " image" + (withMeta > 1 ? "s" : ""));
  }
  async function processOdf(JSZip, bytes, opts, progress) {
    opts = opts || {}; progress = progress || function () {};
    const zip = await JSZip.loadAsync(bytes);
    const mime = zip.file("mimetype") ? await zip.file("mimetype").async("string") : "";
    if (!/^application\/vnd\.oasis\.opendocument\./.test(mime)) throw new Error("This zip is not an OpenDocument file.");
    const found = [], kept = [];
    await odfScan(zip, found);
    const oldMeta = zip.file("meta.xml") ? await zip.file("meta.xml").async("string") : "";
    const ver = (/office:version="([^"]*)"/.exec(oldMeta) || [0, "1.2"])[1];
    const keepTitle = opts.keepTitle ? xmlTag(oldMeta, "dc:title") : "";
    const author = opts.author ? String(opts.author) : "";
    const metaOut = '<?xml version="1.0" encoding="UTF-8"?>\n<office:document-meta xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0" office:version="' + xmlEsc(ver) + '">' +
      (keepTitle || author ? "<office:meta>" + (keepTitle ? "<dc:title>" + xmlEsc(keepTitle) + "</dc:title>" : "") + (author ? "<meta:initial-creator>" + xmlEsc(author) + "</meta:initial-creator>" : "") + "</office:meta>" : "<office:meta/>") + "</office:document-meta>";
    mustBeWellFormed("meta.xml", metaOut);
    zip.file("meta.xml", metaOut);
    const names = Object.keys(zip.files).filter((n) => !zip.files[n].dir);
    let done = 0;
    for (const n of names) {
      progress(0.1 + 0.7 * (done++ / names.length), "Cleaning " + n.split("/").pop());
      if (/^Thumbnails\//.test(n)) {
        zip.remove(n);
        const man = zip.file("META-INF/manifest.xml");
        if (man) {
          const x = await man.async("string");
          const y = x.replace(new RegExp('<manifest:file-entry\\b[^>]*manifest:full-path="' + n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + '"[^>]*/>', "g"), "");
          mustBeWellFormed("the manifest", y);
          zip.file("META-INF/manifest.xml", y);
        }
      } else if (n === "content.xml" || n === "styles.xml") {
        if (opts.anonymize !== false) {
          const x = await zip.file(n).async("string");
          const y = x.replace(/<dc:creator>[^<]*<\/dc:creator>/g, "<dc:creator>Author</dc:creator>").replace(/<dc:date>[^<]*<\/dc:date>/g, "");
          if (y !== x) { mustBeWellFormed(n, y); zip.file(n, y); }
        }
      } else if (n === "settings.xml") {
        const x = await zip.file(n).async("string");
        const y = x.replace(/(<config:config-item\b[^>]*config:name="Printer(?:Name|Setup)"[^>]*>)[^<]*(<\/config:config-item>)/g, "$1$2");
        if (y !== x) { mustBeWellFormed(n, y); zip.file(n, y); }
      } else if (/\.(jpe?g|png|webp)$/i.test(n)) {
        try { const r = processImage(await zip.file(n).async("uint8array"), { keepOrientation: true }); if (r.found.length) zip.file(n, r.out); } catch (e) { /* leave as is */ }
      }
    }
    // The mimetype entry must stay first and stored, uncompressed.
    zip.file("mimetype", mime, { compression: "STORE" });
    zip.forEach((p, f) => { f.date = FIXED_DATE; });
    progress(0.85, "Writing the file");
    const out = await zip.generateAsync({ type: "uint8array", compression: "DEFLATE", compressionOptions: { level: 6 } });
    kept.push("Text, tables, slides and pictures are not touched. Names typed into the body are content, not metadata.");
    return { kind: "odf", found: found, out: out, kept: kept };
  }

  // ---------- checks ----------

  async function sha256(bytes) {
    try {
      const c = root.crypto && root.crypto.subtle;
      if (!c) return null;
      const d = new Uint8Array(await c.digest("SHA-256", bytes));
      let h = "";
      for (let i = 0; i < d.length; i++) h += (d[i] < 16 ? "0" : "") + d[i].toString(16);
      return h;
    } catch (e) { return null; }
  }

  function mp4Structure(b) {
    let o = 0, moov = false;
    const dv = new DataView(b.buffer, b.byteOffset, b.byteLength);
    while (o + 8 <= b.length) {
      let size = dv.getUint32(o);
      const type = ascii(b, o + 4, o + 8);
      if (size === 1) size = dv.getUint32(o + 8) * 4294967296 + dv.getUint32(o + 12);
      if (size === 0) size = b.length - o;
      if (size < 8 || o + size > b.length) return false;
      if (type === "moov") moov = true;
      o += size;
    }
    return moov && o === b.length;
  }

  // Confirms the cleaned file still opens. Returns { ok, note }.
  async function integrity(res, orig, libs, ctx) {
    const kind = res.kind;
    try {
      if (["jpeg", "png", "webp", "gif"].includes(kind)) {
        if (typeof root.createImageBitmap !== "function" || typeof root.Blob !== "function") return { ok: true, note: "Image decode check skipped on this browser." };
        const mime = { jpeg: "image/jpeg", png: "image/png", webp: "image/webp", gif: "image/gif" }[kind];
        let a = null;
        try { a = await root.createImageBitmap(new Blob([orig], { type: mime })); } catch (e) { return { ok: true, note: "Original could not be decoded here, so no comparison was made." }; }
        let o;
        try { o = await root.createImageBitmap(new Blob([res.out], { type: mime })); } catch (e) { a.close(); return { ok: false, note: "The cleaned picture would not open." }; }
        const same = a.width === o.width && a.height === o.height;
        a.close(); o.close();
        return same ? { ok: true, note: "Cleaned picture opens at the same size." } : { ok: false, note: "The cleaned picture came out a different size." };
      }
      if (kind === "tiff") {
        const touched = res.touched || [];
        const o = res.out, a = res.original;
        if (o.length !== a.length) return { ok: false, note: "File length changed." };
        let i = 0;
        const sorted = touched.slice().sort((x, y) => x[0] - y[0]);
        for (const [s, e] of sorted) { for (; i < s; i++) if (o[i] !== a[i]) return { ok: false, note: "Image data changed." }; i = Math.max(i, e); }
        for (; i < o.length; i++) if (o[i] !== a[i]) return { ok: false, note: "Image data changed." };
        return { ok: true, note: "Image data is byte-for-byte unchanged." };
      }
      if (kind === "mp4") return mp4Structure(res.out) ? { ok: true, note: "Video structure is intact." } : { ok: false, note: "Video structure check failed." };
      if (kind === "svg") return wellFormed(utf8(res.out, 0, res.out.length)) ? { ok: true, note: "SVG is well-formed." } : { ok: false, note: "SVG check failed." };
      if (kind === "pdf") {
        const d = await loadPdf(libs.PDFLib, res.out);
        return d.getPageCount() === res.pages ? { ok: true, note: "PDF reopens with " + res.pages + " page" + (res.pages === 1 ? "" : "s") + "." } : { ok: false, note: "Page count changed." };
      }
      if (["docx", "xlsx", "pptx", "odf"].includes(kind)) {
        const z = await libs.JSZip.loadAsync(res.out);
        const main = kind === "odf" ? "mimetype" : "[Content_Types].xml";
        if (!z.file(main)) return { ok: false, note: "Package is missing " + main + "." };
        const origZip = await libs.JSZip.loadAsync(orig);
        const lost = Object.keys(origZip.files).filter((n) => !origZip.files[n].dir && !z.files[n] && !/^docProps\/thumbnail\.|^Thumbnails\/|^word\/people\.xml$/.test(n));
        return lost.length ? { ok: false, note: "Parts went missing: " + lost.slice(0, 3).join(", ") } : { ok: true, note: "Package reopens with every part present." };
      }
    } catch (e) { return { ok: false, note: "Check failed: " + (e && e.message ? e.message : e) }; }
    return { ok: true, note: "" };
  }

  // ---------- dispatch ----------

  const ZIP_EXT = /\.(docx|xlsx|pptx|docm|xlsm|pptm)$/;
  const ODF_EXT = /\.(odt|ods|odp|odg|ott|ots|otp)$/;
  function kindOf(name, bytes) {
    const lower = String(name).toLowerCase();
    const img = detectImage(bytes);
    if (img) return img;
    if (startsWith(bytes, 0, "GIF87a") || startsWith(bytes, 0, "GIF89a")) return "gif";
    if (startsWith(bytes, 0, "%PDF")) return "pdf";
    if ((bytes[0] === 0x49 && bytes[1] === 0x49 && bytes[2] === 0x2a && bytes[3] === 0) || (bytes[0] === 0x4d && bytes[1] === 0x4d && bytes[2] === 0 && bytes[3] === 0x2a)) return "tiff";
    if (bytes[0] === 0x50 && bytes[1] === 0x4b) {
      if (ZIP_EXT.test(lower)) return "office";
      if (ODF_EXT.test(lower)) return "odf";
    }
    if (bytes.length > 12 && ascii(bytes, 4, 8) === "ftyp") return "mp4";
    if (/\.svg$/.test(lower) || (bytes[0] === 0x3c && /^\s*(<\?xml[^>]*>\s*)?(<!--[\s\S]*?-->\s*)*(<!DOCTYPE[^>]*>\s*)?<svg[\s>]/.test(utf8(bytes, 0, Math.min(bytes.length, 4096))))) return "svg";
    if (/\.(doc|xls|ppt)$/.test(lower)) return "legacy";
    return null;
  }
  const SUPPORTED = "JPG, PNG, WebP, GIF, TIFF, SVG, PDF, DOCX, XLSX, PPTX, ODT/ODS/ODP and MP4/MOV";

  async function run(name, bytes, libs, opts, progress) {
    progress = progress || function () {};
    const k = kindOf(name, bytes);
    if (k === "legacy") throw new Error("Old .doc, .xls and .ppt files are not supported. Save as .docx, .xlsx or .pptx first.");
    if (!k) throw new Error("Not supported. Use " + SUPPORTED + ".");
    if (k === "pdf") return processPdf(libs.PDFLib, bytes, opts, progress);
    if (k === "office") return processOffice(libs.JSZip, bytes, opts, progress);
    if (k === "odf") return processOdf(libs.JSZip, bytes, opts, progress);
    if (k === "gif") return processGif(bytes);
    if (k === "tiff") return processTiff(bytes, opts);
    if (k === "svg") return processSvg(bytes);
    if (k === "mp4") return processMp4(bytes, opts);
    return processImage(bytes, opts);
  }

  // Re-read a cleaned file with the same readers. Anything it still finds is shown to the user.
  async function verify(kindName, out, libs) {
    if (kindName === "pdf") return pdfScan(libs.PDFLib, await loadPdf(libs.PDFLib, out));
    if (kindName === "docx" || kindName === "xlsx" || kindName === "pptx") {
      const zip = await libs.JSZip.loadAsync(out), found = [];
      await officeScan(zip, found);
      return found;
    }
    if (kindName === "odf") { const zip = await libs.JSZip.loadAsync(out), found = []; await odfScan(zip, found); return found; }
    if (kindName === "gif") return processGif(out).found;
    if (kindName === "svg") return processSvg(out).found;
    if (kindName === "tiff") return processTiff(out, {}).found;
    if (kindName === "mp4") return processMp4(out, { scanOnly: true }).found;
    return processImage(out, { keepOrientation: true }).found;
  }

  // Full pipeline used by the page and its worker: clean, re-read, check, hash.
  async function clean(name, bytes, libs, opts, progress) {
    opts = opts || {}; progress = progress || function () {};
    progress(0.02, "Reading");
    const inHash = await sha256(bytes);
    const orig = bytes.length > 64 * 1048576 ? null : Uint8Array.from(bytes); // images and zips are not edited in place; MP4 is
    const inSize = bytes.length;
    const res = await run(name, bytes, libs, opts, progress);
    progress(0.88, "Reading the result again");
    let after = await verify(res.kind, res.out, libs);
    const keepFields = [];
    if (opts.keepTitle) keepFields.push("Title");
    if (opts.author) keepFields.push("Author");
    after = after.filter((f) => !f.info && !(f.group === "Document properties" && keepFields.indexOf(f.field) !== -1));
    progress(0.94, "Checking the file still opens");
    const check = res.kind === "mp4" ? await integrity(res, null, libs) : await integrity(res, orig || res.original || bytes, libs);
    const outHash = await sha256(res.out);
    progress(1, "Done");
    return { kind: res.kind, found: res.found.filter((f) => !f.info), left: res.found.filter((f) => f.info), kept: res.kept, after: after, check: check, inSize: inSize, outSize: res.out.length, inHash: inHash, outHash: outHash, out: res.out };
  }

  const api = { clean, run, verify, kindOf, SUPPORTED, wellFormed, processJpeg, processPng, processWebp, processImage, processGif, processSvg, processTiff, processMp4, processPdf, processOffice, processOdf, cleanText, parseTiff, minimalTiff, crc32, sha256, integrity };
  if (typeof module === "object" && module.exports) module.exports = api;
  root.MetaClean = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
