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
  function add(found, group, field, value) {
    found.push({ group: group, field: field, value: value == null ? "" : trunc(value) });
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
      if (list && list.size() > 0) add(found, "Other", "Attached files", list.size() / 2 + " (left in place, they are content)");
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

  async function processPdf(PDFLib, bytes, opts) {
    opts = opts || {};
    const { PDFName, PDFDict, PDFStream, PDFRawStream, PDFHexString } = PDFLib;
    const doc = await loadPdf(PDFLib, bytes);
    const ctx = doc.context;
    const found = pdfScan(PDFLib, doc), kept = [];
    // 1. Info dictionary and file ID.
    ctx.trailerInfo.Info = undefined;
    ctx.trailerInfo.ID = undefined;
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
    const live = reachable(PDFLib, ctx, [ctx.trailerInfo.Root]);
    for (const [ref] of ctx.enumerateIndirectObjects()) if (!live.has(ref.tag)) ctx.delete(ref);
    const out = await doc.save();
    kept.push("Page content is not touched: text, figures and fonts are exactly as they were.");
    return { kind: "pdf", found: found, out: out, kept: kept };
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
      } else if (/^xl\/comments[^/]*\.xml$/.test(n)) {
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
    if (cx.length) add(found, "Other", "Custom XML parts", cx.length + " (SharePoint or add-in data, left in place)");
  }

  async function processOffice(JSZip, bytes, opts) {
    opts = opts || {};
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

    if (zip.file("docProps/core.xml")) zip.file("docProps/core.xml", CORE_EMPTY);
    if (zip.file("docProps/custom.xml")) zip.file("docProps/custom.xml", CUSTOM_EMPTY);
    if (zip.file("docProps/app.xml")) {
      let x = await read("docProps/app.xml");
      x = x.replace(new RegExp("<(" + APP_FIELDS.join("|") + ")\\b[^>]*?(?:/>|>[\\s\\S]*?</\\1>)", "g"), "");
      zip.file("docProps/app.xml", x);
    }
    for (const n of names.filter((x) => /^docProps\/thumbnail\./.test(x))) await removePart(zip, n);
    if (names.includes("word/people.xml")) await removePart(zip, "word/people.xml");

    for (const n of names) {
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
        if (y !== x) zip.file(n, y);
      } else if (n === "word/_rels/settings.xml.rels") {
        const x = await read(n), y = dropRel(x, "/attachedTemplate");
        if (y !== x) zip.file(n, y);
      } else if (anonymize && /^xl\/comments[^/]*\.xml$/.test(n)) {
        const x = await read(n);
        zip.file(n, x.replace(/<author>[^<]*<\/author>/g, "<author>Author</author>"));
      } else if (anonymize && /^xl\/persons\/[^/]+\.xml$/.test(n)) {
        const x = await read(n);
        zip.file(n, x.replace(/\sdisplayName="[^"]*"/g, ' displayName="Author"').replace(/\suserId="[^"]*"/g, ' userId="Author"').replace(/\sproviderId="[^"]*"/g, ' providerId="None"'));
      } else if (anonymize && /^xl\/threadedComments\/[^/]+\.xml$/.test(n)) {
        const x = await read(n);
        zip.file(n, x.replace(/\sdT="[^"]*"/g, ""));
      } else if (anonymize && (n === "ppt/commentAuthors.xml" || n === "ppt/authors.xml")) {
        const x = await read(n);
        zip.file(n, x.replace(/\sname="[^"]*"/g, ' name="Author"').replace(/\sinitials="[^"]*"/g, ' initials="A"')
          .replace(/\suserId="[^"]*"/g, ' userId="Author"').replace(/\sproviderId="[^"]*"/g, ' providerId="None"'));
      } else if (n === "xl/workbook.xml") {
        const x = await read(n);
        zip.file(n, x.replace(/<mc:AlternateContent\b[^>]*>\s*<mc:Choice\b[^>]*>\s*<x15ac:absPath\b[^>]*\/>\s*<\/mc:Choice>\s*<\/mc:AlternateContent>/g, ""));
      } else if (/\/media\/[^/]+\.(jpe?g|png|webp)$/i.test(n)) {
        try {
          const r = processImage(await zip.file(n).async("uint8array"), { keepOrientation: true });
          if (r.found.length) zip.file(n, r.out);
        } catch (e) { /* leave unreadable images as they are */ }
      }
    }
    zip.forEach((p, f) => { f.date = FIXED_DATE; });
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

  // ---------- dispatch ----------

  function kindOf(name, bytes) {
    if (detectImage(bytes)) return detectImage(bytes);
    const lower = String(name).toLowerCase();
    if (startsWith(bytes, 0, "%PDF")) return "pdf";
    if (bytes[0] === 0x50 && bytes[1] === 0x4b && /\.(docx|xlsx|pptx|docm|xlsm|pptm)$/.test(lower)) return "office";
    if (/\.(doc|xls|ppt)$/.test(lower)) return "legacy";
    return null;
  }

  async function run(name, bytes, libs, opts) {
    const k = kindOf(name, bytes);
    if (k === "legacy") throw new Error("Old .doc, .xls and .ppt files are not supported. Save as .docx, .xlsx or .pptx first.");
    if (!k) throw new Error("Not supported. Use a JPG, PNG, WebP, PDF, DOCX, XLSX or PPTX file.");
    let res;
    if (k === "pdf") res = await processPdf(libs.PDFLib, bytes, opts);
    else if (k === "office") res = await processOffice(libs.JSZip, bytes, opts);
    else res = processImage(bytes, opts);
    return res;
  }

  // Re-read a cleaned file with the same readers. Anything it still finds is shown to the user.
  async function verify(kindName, out, libs) {
    if (kindName === "pdf") return pdfScan(libs.PDFLib, await loadPdf(libs.PDFLib, out));
    if (kindName === "docx" || kindName === "xlsx" || kindName === "pptx") {
      const zip = await libs.JSZip.loadAsync(out), found = [];
      await officeScan(zip, found);
      return found;
    }
    return processImage(out, { keepOrientation: true }).found;
  }

  const api = { run, verify, kindOf, processJpeg, processPng, processWebp, processImage, processPdf, processOffice, cleanText, parseTiff, minimalTiff, crc32 };
  if (typeof module === "object" && module.exports) module.exports = api;
  root.MetaClean = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
