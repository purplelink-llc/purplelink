// The in-browser converters (site/tools/convert/): sniffing, naming, options, the ICNS and ICO writers, JPEG headers
// and PDF placement, the CSV reader and XLSX parts, plus real runs of the vendored libheif, pdf-lib and JSZip, so a
// broken or swapped library fails here rather than on the live page.
// Fixtures: a 64 x 48 HEIC, left half red and right half blue, written by macOS `sips -s format heic` (502 bytes); a
// 40 x 20 JPEG in the same colors stored with EXIF orientation 6 at 300 dpi, and a 16 x 16 CMYK JPEG with Adobe's
// marker, both written by Pillow.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, mkdtempSync, copyFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";
import vm from "node:vm";

const HERE = dirname(fileURLToPath(import.meta.url));
const SITE = join(HERE, "..", "..", "site");
const ctx = { self: {}, TextDecoder };
vm.runInNewContext(readFileSync(join(SITE, "tools/convert/convert-core.js"), "utf8"), ctx);
const C = ctx.self.Convert;
// Values made inside the vm context have that context's Array and Object, which deepStrictEqual tells apart.
const plain = (v) => JSON.parse(JSON.stringify(v));

const bytes = (...parts) => {
  const out = [];
  for (const p of parts) typeof p === "string" ? out.push(...[...p].map((c) => c.charCodeAt(0))) : out.push(...p);
  return new Uint8Array(out);
};
const ftyp = (major, ...compat) => {
  const size = 16 + 4 * compat.length;
  return bytes([0, 0, 0, size], "ftyp", major, [0, 0, 0, 0], ...compat);
};

test("sniff: formats by their first bytes", () => {
  assert.equal(C.sniff(bytes([0x89], "PNG\r\n\x1a\n", [0, 0, 0, 0])), "png");
  assert.equal(C.sniff(bytes([0xff, 0xd8, 0xff, 0xe0], [0, 0, 0, 0, 0, 0, 0, 0])), "jpeg");
  assert.equal(C.sniff(bytes("RIFF", [0, 0, 0, 0], "WEBPVP8 ")), "webp");
  assert.equal(C.sniff(bytes("GIF89a", [0, 0, 0, 0, 0, 0])), "gif");
  assert.equal(C.sniff(ftyp("heic", "mif1", "heic")), "heic");
  assert.equal(C.sniff(ftyp("heix", "mif1")), "heic");
  assert.equal(C.sniff(ftyp("mif1", "heic")), "heic");
  // AVIF files carry mif1 as well; the avif brand decides.
  assert.equal(C.sniff(ftyp("avif", "mif1", "miaf")), "avif");
  assert.equal(C.sniff(ftyp("mif1", "avif", "miaf")), "avif");
  assert.equal(C.sniff(ftyp("isom", "mp41")), "");
  assert.equal(C.sniff(bytes("hello world, not a picture")), "");
  assert.equal(C.sniff(new Uint8Array(4)), "");
});

test("sniff: the fixture is HEIC", () => {
  assert.equal(C.sniff(readFileSync(join(HERE, "fixtures/convert-64x48-red-blue.heic"))), "heic");
});

test("refuse: says what a wrong file is", () => {
  assert.equal(C.refuse("heic-to-jpg", "heic", 1000), "");
  assert.equal(C.refuse("heic-to-jpg", "jpeg", 1000), "This is a JPEG file, not HEIC.");
  assert.equal(C.refuse("heic-to-jpg", "", 1000), "This is not a HEIC file, or it is damaged.");
  assert.equal(C.refuse("png-to-icns", "", 10), "This is not a PNG, JPEG or WebP file, or it is damaged.");
  assert.equal(C.refuse("png-to-icns", "webp", 10), "");
  assert.equal(C.refuse("webp-to-png", "webp", 0), "That file is empty.");
  assert.match(C.refuse("webp-to-png", "webp", C.MAX_BYTES + 1), /over 100 MB/);
  assert.match(C.refuse("nope", "png", 10), /does not know/);
});

test("tooManyPixels: desktop and phone caps", () => {
  assert.equal(C.tooManyPixels(8064, 6048, false), "");
  assert.match(C.tooManyPixels(8064, 6048, true), /49 megapixels.*computer/);
  assert.equal(C.tooManyPixels(4096, 4096, true), "");
  assert.match(C.tooManyPixels(20000, 20000, false), /400 megapixels/);
});

test("outName and uniqueNames", () => {
  assert.equal(C.outName("IMG_4821.HEIC", "jpg"), "IMG_4821.jpg");
  assert.equal(C.outName("folder/sub/shot.final.webp", "png"), "shot.final.png");
  assert.equal(C.outName("C:\\pics\\a:b?.heic", "jpg"), "a_b_.jpg");
  assert.equal(C.outName("", "png"), "file.png");
  assert.equal(C.outName("noext", "icns"), "noext.icns");
  assert.deepEqual(plain(C.uniqueNames(["a.jpg", "b.jpg", "A.jpg", "a.jpg", "a (2).jpg"])),
    ["a.jpg", "b.jpg", "A (2).jpg", "a (3).jpg", "a (2) (2).jpg"]);
  assert.deepEqual(plain(C.uniqueNames(["x/icon.png", "x/icon.png"])), ["x/icon.png", "x/icon (2).png"]);
});

test("options: clamps and defaults", () => {
  assert.deepEqual(plain(C.options("heic-to-jpg", {})), {
    output: "jpg", quality: 0.92, background: "#ffffff", iconset: false, mobile: false,
    sizes: "all", page: "a4", margin: false, delimiter: "auto", encoding: "auto", header: true, text: false,
    dpi: 150, pages: "", scale: "2", width: 1920, sheets: "first", bom: false, nested: "columns", safe: true, tiffpages: "first",
    types: true, unflatten: false, icons: "largest", speakers: true, merge: true
  });
  assert.equal(C.options("pdf-to-jpg", { dpi: "300" }).dpi, 300);
  assert.equal(C.options("pdf-to-jpg", { dpi: "600" }).dpi, 150);
  assert.equal(C.options("pdf-to-jpg", { pages: "x".repeat(500) }).pages.length, 200);
  assert.equal(C.options("svg-to-png", { scale: "4" }).scale, "4");
  assert.equal(C.options("svg-to-png", { scale: "3" }).scale, "2");
  assert.equal(C.options("svg-to-png", { width: "99999" }).width, 16384);
  assert.equal(C.options("svg-to-png", { width: "" }).width, 1920);
  assert.equal(C.options("svg-to-png", { width: "4" }).width, 16);
  assert.equal(C.options("png-to-jpg", { output: "png" }).output, "jpg");
  // The slider sends 50 to 100; remembered choices from the first pages store it as a string.
  assert.equal(C.options("heic-to-jpg", { quality: "80" }).quality, 0.8);
  assert.equal(C.options("png-to-ico", { sizes: "favicon" }).sizes, "favicon");
  assert.equal(C.options("png-to-ico", { sizes: "huge" }).sizes, "all");
  assert.equal(C.options("jpg-to-pdf", { page: "letter", margin: true }).page, "letter");
  assert.equal(C.options("jpg-to-pdf", { page: "a3" }).page, "a4");
  assert.equal(C.options("csv-to-xlsx", { delimiter: "semicolon", header: false, text: true, encoding: "shift_jis" }).header, false);
  assert.equal(C.options("csv-to-xlsx", { delimiter: "x" }).delimiter, "auto");
  assert.equal(C.options("csv-to-xlsx", { encoding: "ebcdic" }).encoding, "auto");
  assert.equal(C.options("heic-to-jpg", { output: "png" }).output, "png");
  assert.equal(C.options("heic-to-jpg", { output: "gif" }).output, "jpg");
  assert.equal(C.options("webp-to-png", {}).output, "png");
  assert.equal(C.options("webp-to-png", { quality: 3 }).quality, 0.92);
  assert.equal(C.options("webp-to-png", { quality: 0.7 }).quality, 0.7);
  assert.equal(C.options("webp-to-png", { background: "red" }).background, "#ffffff");
  assert.equal(C.options("webp-to-png", { background: "#00AA11" }).background, "#00aa11");
  assert.equal(C.options("png-to-icns", { iconset: 1, output: "jpg" }).output, "icns");
});

test("downscaleSteps and fitSquare", () => {
  assert.deepEqual(plain(C.downscaleSteps(4096, 16)), [2048, 1024, 512, 256, 128, 64, 32, 16]);
  assert.deepEqual(plain(C.downscaleSteps(1000, 16)), [500, 250, 125, 63, 32, 16]);
  assert.deepEqual(plain(C.downscaleSteps(512, 512)), []);
  assert.deepEqual(plain(C.downscaleSteps(300, 1024)), [1024]);
  assert.deepEqual(plain(C.fitSquare(200, 100, 64)), { x: 0, y: 16, width: 64, height: 32 });
  assert.deepEqual(plain(C.fitSquare(100, 300, 30)), { x: 10, y: 0, width: 10, height: 30 });
  assert.deepEqual(plain(C.fitSquare(512, 512, 16)), { x: 0, y: 0, width: 16, height: 16 });
});

test("buildIcns: header, every type, lengths, payloads", () => {
  const pngs = {};
  for (const s of C.ICNS_SIZES) pngs[s] = bytes([0x89], "PNG", [s & 255, s >> 8, 1, 2, 3]);
  const icns = C.buildIcns(pngs);
  assert.equal(String.fromCharCode(...icns.slice(0, 4)), "icns");
  const total = (icns[4] << 24) | (icns[5] << 16) | (icns[6] << 8) | icns[7];
  assert.equal(total, icns.length);
  // 8-byte header + 10 entries of (8 + 9 bytes)
  assert.equal(icns.length, 8 + 10 * 17);
  const entries = C.parseIcns(icns);
  assert.deepEqual(plain(entries.map((e) => e.type)), ["icp4", "icp5", "ic07", "ic08", "ic09", "ic10", "ic11", "ic12", "ic13", "ic14"]);
  const sizeOf = Object.fromEntries(C.ICNS_TYPES.map(([t, s]) => [t, s]));
  for (const e of entries) {
    assert.equal(e.length, 17);
    assert.deepEqual([...icns.slice(e.offset, e.offset + 9)], [...pngs[sizeOf[e.type]]], e.type);
  }
  // first entry starts right after the header: "icp4" then a big-endian 17
  assert.deepEqual([...icns.slice(8, 16)], [0x69, 0x63, 0x70, 0x34, 0, 0, 0, 17]);
});

test("buildIcns: only the sizes given; parseIcns rejects broken files", () => {
  const icns = C.buildIcns({ 16: bytes("abc"), 1024: bytes("defg") });
  assert.deepEqual(plain(C.parseIcns(icns).map((e) => e.type)), ["icp4", "ic10"]);
  assert.throws(() => C.buildIcns({}), /No icon sizes/);
  const bad = icns.slice(); bad[7] += 1;
  assert.throws(() => C.parseIcns(bad), /length mismatch/);
  const bad2 = icns.slice(); bad2[15] = 200;
  assert.throws(() => C.parseIcns(bad2), /out of range/);
  assert.throws(() => C.parseIcns(bytes("nope", [0, 0, 0, 8])), /Not an ICNS/);
});

test("ICONSET names cover every size iconutil wants, one per ICNS type", () => {
  assert.equal(C.ICONSET.length, 10);
  assert.equal(C.ICNS_TYPES.length, C.ICONSET.length);
  assert.deepEqual(plain(C.ICNS_TYPES.map((t) => t[1]).sort((a, b) => a - b)), plain(C.ICONSET.map((e) => e[1]).sort((a, b) => a - b)));
  for (const [name, size] of C.ICONSET) {
    const m = name.match(/^icon_(\d+)x\1(@2x)?\.png$/);
    assert.ok(m, name);
    assert.equal(size, Number(m[1]) * (m[2] ? 2 : 1), name);
  }
});

test("pngSize reads IHDR", () => {
  const png = bytes([0x89], "PNG\r\n\x1a\n", [0, 0, 0, 13], "IHDR", [0, 0, 4, 0], [0, 0, 2, 0], [8, 6, 0, 0, 0]);
  assert.deepEqual(plain(C.pngSize(png)), { width: 1024, height: 512 });
  assert.equal(C.pngSize(bytes("not a png at all, really")), null);
});

test("vendored libheif decodes the HEIC fixture", async () => {
  const dir = join(SITE, "assets/vendor/libheif-1.23.5");
  // The repo's package.json says "type": "module", so require() would read libheif.js as ESM. A .cjs copy keeps
  // Emscripten's CommonJS export; the bytes are the vendored file's.
  const tmp = join(mkdtempSync(join(tmpdir(), "libheif-")), "libheif.cjs");
  copyFileSync(join(dir, "libheif.js"), tmp);
  const factory = createRequire(import.meta.url)(tmp);
  const lib = await factory({ wasmBinary: readFileSync(join(dir, "libheif.wasm")) });
  const images = new lib.HeifDecoder().decode(readFileSync(join(HERE, "fixtures/convert-64x48-red-blue.heic")));
  assert.equal(images.length, 1);
  const img = images[0];
  const w = img.get_width(), h = img.get_height();
  assert.deepEqual([w, h], [64, 48]);
  const data = new Uint8ClampedArray(w * h * 4);
  const out = await new Promise((resolve) => img.display({ data, width: w, height: h }, resolve));
  assert.ok(out, "display() returned no pixels");
  const px = (x, y) => [...out.data.slice((y * w + x) * 4, (y * w + x) * 4 + 4)];
  const near = (a, b) => a.every((v, i) => Math.abs(v - b[i]) <= 6);
  assert.ok(near(px(8, 24), [255, 0, 0, 255]), "left half should be red: " + px(8, 24));
  assert.ok(near(px(56, 24), [0, 0, 255, 255]), "right half should be blue: " + px(56, 24));
});

// ---------- second set ----------
const req = createRequire(import.meta.url);
const fixture = (name) => new Uint8Array(readFileSync(join(HERE, "fixtures", name)));
// The vendored libraries are UMD builds; a .cjs copy keeps their CommonJS export under "type": "module".
function vendored(rel) {
  const tmp = join(mkdtempSync(join(tmpdir(), "vendor-")), rel.split("/").pop().replace(/\.js$/, ".cjs"));
  copyFileSync(join(SITE, "assets/vendor", rel), tmp);
  return req(tmp);
}
const enc = (s) => new TextEncoder().encode(s);

test("kindOf: text files by name and content, images by bytes", () => {
  assert.equal(C.kindOf(enc("a,b\n1,2"), "data.csv"), "csv", "short files count, below sniff's 12 bytes");
  assert.equal(C.kindOf(enc("a\tb\n"), "data.TSV"), "csv");
  assert.equal(C.kindOf(new Uint8Array([0xff, 0xfe, 0x61, 0, 0x2c, 0]), "utf16.csv"), "csv", "UTF-16 BOM before the NUL check");
  assert.equal(C.kindOf(new Uint8Array([0x61, 0, 0x62]), "binary.csv"), "");
  assert.equal(C.kindOf(enc("a,b"), "data.xlsx"), "");
  assert.equal(C.kindOf(bytes([0x89], "PNG\r\n\x1a\n", [0, 0, 0, 0]), "renamed.csv"), "png");
  assert.equal(C.refuse("csv-to-xlsx", "png", 10), "This is a PNG file, not CSV.");
  assert.equal(C.refuse("csv-to-xlsx", "csv", 51 * 1048576), "That file is over 50 MB.");
  assert.equal(C.refuse("jpg-to-pdf", "png", 10), "");
  assert.equal(C.refuse("avif-to-jpg", "heic", 10), "This is a HEIC file, not AVIF.");
  for (const pair of Object.keys(C.CONVERSIONS)) assert.ok(C.CONVERSIONS[pair].work, pair);
  assert.equal(C.CONVERSIONS["csv-to-xlsx"].canvas, undefined, "the CSV page needs no canvas");
  assert.equal(C.tooManyPixels(6000, 5000, false, 25e6), "This picture is 30 megapixels, more than this page converts (25 MP).");
});

test("buildIco: directory, 256 written as 0, offsets; parseIco reads it back", () => {
  const pngs = {};
  C.ICO_SETS.all.forEach((s, i) => { pngs[s] = new Uint8Array(10 + i).fill(s & 255); });
  const ico = C.buildIco(pngs, C.ICO_SETS.all);
  assert.deepEqual([...ico.slice(0, 6)], [0, 0, 1, 0, 7, 0]);
  const last = 6 + 16 * 6;
  assert.deepEqual([ico[last], ico[last + 1]], [0, 0], "256 px is stored as 0");
  assert.deepEqual([ico[last + 4], ico[last + 6]], [1, 32], "planes 1, 32 bits");
  const dir = plain(C.parseIco(ico));
  assert.deepEqual(dir.map((d) => d.width), [16, 24, 32, 48, 64, 128, 256]);
  assert.equal(dir[0].offset, 6 + 16 * 7);
  dir.forEach((d, i) => assert.deepEqual([...ico.slice(d.offset, d.offset + d.length)], [...pngs[C.ICO_SETS.all[i]]]));
  assert.equal(plain(C.parseIco(C.buildIco(pngs, C.ICO_SETS.favicon))).length, 3);
  assert.throws(() => C.parseIco(ico.slice(0, ico.length - 1)), /out of range|mismatch/);
  assert.throws(() => C.parseIco(bytes("icns", [0, 0, 0, 8])), /Not an ICO/);
});

test("jpegInfo: size, orientation, density, CMYK marker, refusals", () => {
  assert.deepEqual(plain(C.jpegInfo(fixture("convert-40x20-orient6.jpg"))),
    { sof: 0xc0, precision: 8, width: 40, height: 20, components: 3, orientation: 6, adobe: false, dpi: 300, embeddable: true });
  const cmyk = C.jpegInfo(fixture("convert-16x16-cmyk.jpg"));
  assert.equal(cmyk.components, 4);
  assert.equal(cmyk.adobe, true);
  assert.equal(cmyk.embeddable, true);
  // A CMYK JPEG without Adobe's marker, or an arithmetic-coded one, is redrawn instead of embedded.
  const sof = (m, comps) => bytes([0xff, 0xd8, 0xff, m, 0, 8 + 3 * comps, 8, 0, 10, 0, 12, comps], new Array(3 * comps).fill(1), [0xff, 0xd9]);
  assert.equal(C.jpegInfo(sof(0xc0, 4)).embeddable, false);
  assert.equal(C.jpegInfo(sof(0xc9, 3)).embeddable, false);
  assert.equal(C.jpegInfo(sof(0xc2, 3)).embeddable, true, "progressive is fine");
  assert.deepEqual([C.jpegInfo(sof(0xc0, 1)).width, C.jpegInfo(sof(0xc0, 1)).height], [12, 10]);
  assert.equal(C.jpegInfo(bytes([0xff, 0xd8, 0xff, 0xe0, 0, 16], "JFIF")), null, "truncated");
  assert.equal(C.jpegInfo(enc("not a jpeg at all")), null);
});

test("pdfMatrix: every EXIF orientation lands the stored corners where a viewer shows them", () => {
  // Stored corners in the unit square (u right, v up; v = 1 is the first stored row) and where each must appear in a
  // W x H box. Expected positions follow the EXIF definitions: 6 turns the picture a quarter clockwise, 8 counter-
  // clockwise, 3 a half turn; 2 and 4 mirror; 5 and 7 are the two transposes.
  const W = 30, H = 50;
  const TL = [0, 1], TR = [1, 1], BL = [0, 0];
  const want = {
    1: { TL: [0, H], TR: [W, H], BL: [0, 0] },
    2: { TL: [W, H], TR: [0, H], BL: [W, 0] },
    3: { TL: [W, 0], TR: [0, 0], BL: [W, H] },
    4: { TL: [0, 0], TR: [W, 0], BL: [0, H] },
    5: { TL: [0, H], TR: [0, 0], BL: [W, H] },
    6: { TL: [W, H], TR: [W, 0], BL: [0, H] },
    7: { TL: [W, 0], TR: [W, H], BL: [0, 0] },
    8: { TL: [0, 0], TR: [0, H], BL: [W, 0] },
  };
  for (let o = 1; o <= 8; o++) {
    const [a, b, c, d, e, f] = C.pdfMatrix(o, W, H, 5, 7);
    const at = ([u, v]) => [a * u + c * v + e - 5, b * u + d * v + f - 7];
    assert.deepEqual({ TL: at(TL), TR: at(TR), BL: at(BL) }, want[o], "orientation " + o);
  }
  assert.deepEqual(plain(C.displaySize(40, 20, 6)), { width: 20, height: 40 });
  assert.deepEqual(plain(C.displaySize(40, 20, 3)), { width: 40, height: 20 });
});

test("pageLayout: A4 and Letter turn for landscape and fit inside the margin; fit uses the stored dpi", () => {
  const a4 = C.pageLayout("a4", true, 1000, 500, 0);
  assert.deepEqual([a4.width, a4.height], [841.89, 595.28], "landscape picture, landscape page");
  assert.ok(Math.abs(a4.x - 34.02) < 0.01 && a4.y > 34);
  const letter = C.pageLayout("letter", false, 500, 1000, 0);
  assert.deepEqual([letter.width, letter.height, letter.y], [612, 792, 0]);
  assert.equal(letter.h, 792);
  const scan = C.pageLayout("fit", false, 2480, 3508, 300); // A4 at 300 dpi
  assert.ok(Math.abs(scan.width - 595.2) < 0.1 && Math.abs(scan.height - 841.9) < 0.1);
  assert.equal(C.pageLayout("fit", false, 800, 600, 0).width, 600, "96 pixels to the inch");
  assert.ok(C.pageLayout("fit", false, 40000, 1000, 0).width <= 14400, "PDF's page size limit");
});

test("vendored pdf-lib embeds a JPEG unchanged, turned by the matrix, and joins pages", async () => {
  const P = vendored("pdf-lib.min.js");
  const jpg = fixture("convert-40x20-orient6.jpg");
  const info = C.jpegInfo(jpg);
  const doc = await P.PDFDocument.create();
  const img = await doc.embedJpg(jpg);
  const disp = C.displaySize(info.width, info.height, info.orientation);
  const lay = C.pageLayout("fit", false, disp.width, disp.height, info.dpi);
  const page = doc.addPage([lay.width, lay.height]);
  const key = page.node.newXObject("Image", img.ref);
  page.pushOperators(P.pushGraphicsState(), P.concatTransformationMatrix(...C.pdfMatrix(info.orientation, lay.w, lay.h, lay.x, lay.y)),
    P.drawObject(key), P.popGraphicsState());
  const one = await doc.save();
  const back = await P.PDFDocument.load(one);
  const size = back.getPage(0).getSize();
  assert.ok(Math.abs(size.width - 20 * 72 / 300) < 0.01 && Math.abs(size.height - 40 * 72 / 300) < 0.01, JSON.stringify(size));
  // The JPEG's bytes are in the file as they were (DCTDecode, not re-encoded).
  const hay = Buffer.from(one), needle = Buffer.from(jpg.slice(0, 200));
  assert.ok(hay.includes(needle), "JPEG bytes copied into the PDF");
  const cmyk = await doc.embedJpg(fixture("convert-16x16-cmyk.jpg"));
  assert.ok(cmyk.ref);
  const joined = await P.PDFDocument.create();
  for (const src of [one, one, one]) {
    const d = await P.PDFDocument.load(src);
    (await joined.copyPages(d, d.getPageIndices())).forEach((pg) => joined.addPage(pg));
  }
  assert.equal((await P.PDFDocument.load(await joined.save())).getPageCount(), 3);
});

test("decodeText: BOMs, strict UTF-8, Windows-1252 fallback, forced encodings", () => {
  assert.deepEqual(plain(C.decodeText(new Uint8Array([0xef, 0xbb, 0xbf, 0x61]))), { text: "a", encoding: "UTF-8" });
  assert.deepEqual(plain(C.decodeText(new Uint8Array([0xff, 0xfe, 0x61, 0, 0xe9, 0]))), { text: "aé", encoding: "UTF-16" });
  assert.deepEqual(plain(C.decodeText(new Uint8Array([0x63, 0x61, 0x66, 0xe9]))), { text: "café", encoding: "Windows-1252" });
  assert.deepEqual(plain(C.decodeText(enc("café"))), { text: "café", encoding: "UTF-8" });
  assert.equal(C.decodeText(new Uint8Array([0xef, 0xbb, 0xbf, 0x62]), "utf-8").text, "b", "BOM dropped when forced");
  assert.equal(C.decodeText(new Uint8Array([0x82, 0xa0]), "shift_jis").text, "あ");
});

test("detectDelimiter and parseCsv", () => {
  assert.equal(C.detectDelimiter("name;price\nTea;3,50\nCake;4,20\n", "x.csv"), ";");
  assert.equal(C.detectDelimiter("a,b,c\n1,2,3\n", "x.csv"), ",");
  assert.equal(C.detectDelimiter("a\tb\n1\t2\n", "x.tsv"), "\t");
  assert.equal(C.detectDelimiter('"x;y",b\n"1;2",3\n', "x.csv"), ",", "delimiters inside quotes do not count");
  assert.equal(C.detectDelimiter("one column\nonly\n", "x.csv"), ",");
  assert.deepEqual(plain(C.parseCsv('a,"b ""q"", c"\r\n"multi\nline",2\n\n3,', ",")),
    [["a", 'b "q", c'], ["multi\nline", "2"], [""], ["3", ""]]);
  assert.deepEqual(plain(C.parseCsv("a,b\n", ",")), [["a", "b"]], "no empty last row");
  assert.deepEqual(plain(C.parseCsv('5" pipe,x\rnext', ",")), [['5" pipe', "x"], ["next"]], "stray quote, CR line end");
  const open = C.parseCsv('a,"never closed\nb,c', ",");
  assert.equal(open.unclosed, true);
  assert.equal(C.parseCsv("a,b", ",").unclosed, false);
});

test("cellNumber: plain numbers only; IDs, zips, phone numbers, dates stay text", () => {
  const cases = [
    ["42", 42], ["-3.5", -3.5], ["0.007", 0.007], ["1.5e-3", 0.0015], ["2E+5", 200000], ["1.10", 1.1], ["0", 0],
    ["12345678901", 12345678901], ["123456789012", null], ["4111111111111111", null], ["1.2345678901234567", null],
    ["02134", null], ["+15551234567", null], ["12E3", null], ["1,234", null], ["2024-05-01", null], ["3-4", null],
    ["MARCH1", null], [".5", null], ["5.", null], ["Infinity", null], ["NaN", null], ["0x1F", null], [" 4", null], ["", null],
  ];
  for (const [v, want] of cases) assert.equal(C.cellNumber(v, ","), want, JSON.stringify(v));
  assert.equal(C.cellNumber("3,14", ";"), 3.14, "decimal comma in a semicolon file");
  assert.equal(C.cellNumber("3,14", ","), null);
  assert.equal(C.cellNumber("1.234,5", ";"), null, "thousands dots stay text");
});

test("colName and sheetName", () => {
  assert.deepEqual([0, 25, 26, 51, 52, 701, 702, 16383].map(C.colName), ["A", "Z", "AA", "AZ", "BA", "ZZ", "AAA", "XFD"]);
  assert.equal(C.sheetName("results [final]: v2/run?.csv"), "run");
  assert.equal(C.sheetName("results [final]: v2.csv"), "results  final   v2");
  assert.equal(C.sheetName("a-very-long-file-name-that-goes-past-31.csv").length, 31);
  assert.equal(C.sheetName("'quoted'.csv"), "quoted");
  assert.equal(C.sheetName("History.csv"), "History 1");
  assert.equal(C.sheetName(".csv"), "Sheet1");
});

test("buildXlsxParts: cells, header, widths, limits; JSZip packs a readable workbook", async () => {
  const rows = [["id", "zip", "amount", "note"], ["1", "02134", "3.50", 'He said "hi" & <left>'], ["2", "10001", "-7", "two\nlines\u0001"]];
  const b = C.buildXlsxParts(rows, "orders.csv", { header: true, text: false, delimiter: "," });
  assert.deepEqual(Object.keys(b.parts)[0], "[Content_Types].xml", "content types first");
  const sheet = b.parts["xl/worksheets/sheet1.xml"].join("");
  assert.match(sheet, /<c r="A1" s="1" t="inlineStr"><is><t xml:space="preserve">id<\/t><\/is><\/c>/, "bold header as text");
  assert.match(sheet, /<c r="B2" t="inlineStr"><is><t xml:space="preserve">02134<\/t>/, "leading zero kept");
  assert.match(sheet, /<c r="C2"><v>3.5<\/v><\/c>/);
  assert.match(sheet, /<c r="A2"><v>1<\/v><\/c>/);
  assert.match(sheet, /He said &quot;hi&quot; &amp; &lt;left&gt;/);
  assert.match(sheet, /<c r="D3" s="2" t="inlineStr"><is><t xml:space="preserve">two\nlines<\/t>/, "wrapped, control character dropped");
  assert.match(sheet, /<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"\/>/);
  assert.match(sheet, /<dimension ref="A1:D3"\/><sheetViews>.*<\/sheetViews><cols>.*<\/cols><sheetData>/, "schema order");
  assert.doesNotMatch(sheet, /<f>/, "no formulas, ever");
  assert.match(b.parts["xl/workbook.xml"], /<sheet name="orders" sheetId="1" r:id="rId1"\/>/);
  const asText = C.buildXlsxParts(rows, "x.csv", { header: false, text: true }).parts["xl/worksheets/sheet1.xml"].join("");
  assert.doesNotMatch(asText, /<v>/);
  assert.doesNotMatch(asText, /pane/);
  const long = C.buildXlsxParts([["x".repeat(40000)]], "x.csv", {});
  assert.equal(long.notes.length, 1);
  assert.throws(() => C.buildXlsxParts([new Array(16385).fill("a")], "x.csv", {}), /16,384/);

  const JSZip = vendored("jszip/jszip.min.js");
  const zip = new JSZip();
  for (const [k, v] of Object.entries(b.parts)) zip.file(k, Array.isArray(v) ? v.join("") : v);
  const out = await zip.generateAsync({ type: "uint8array", compression: "DEFLATE" });
  const back = await JSZip.loadAsync(out);
  assert.deepEqual(Object.keys(back.files).filter((n) => !n.endsWith("/")),
    ["[Content_Types].xml", "_rels/.rels", "docProps/app.xml", "xl/workbook.xml", "xl/_rels/workbook.xml.rels", "xl/styles.xml", "xl/worksheets/sheet1.xml"]);
  assert.equal(await back.file("xl/worksheets/sheet1.xml").async("string"), sheet);
});

// ---------- third set: PDF to JPG, SVG to PNG, PNG to JPG ----------
const utf8 = (t) => new TextEncoder().encode(t);

test("sniff and kindOf: PDF, BMP, SVG and SVGZ", () => {
  assert.equal(C.sniff(utf8("%PDF-1.7\n%\xe2\xe3\n1 0 obj")), "pdf");
  assert.equal(C.sniff(utf8("junk from a gateway\r\n%PDF-1.4\n")), "pdf", "the header may sit anywhere in the first 1 KB");
  assert.equal(C.sniff(utf8(" ".repeat(1100) + "%PDF-1.4")), "");
  const bmp = new Uint8Array(54); bmp[0] = 0x42; bmp[1] = 0x4d; bmp[14] = 40;
  assert.equal(C.sniff(bmp), "bmp");
  bmp[14] = 41;
  assert.equal(C.sniff(bmp), "", "BM followed by an unknown header size is not a BMP");
  const svg = '<?xml version="1.0" encoding="UTF-8"?>\n<!-- made by hand -->\n<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "x">\n<svg xmlns="http://www.w3.org/2000/svg"/>';
  assert.equal(C.kindOf(utf8(svg), "drawing.svg"), "svg");
  assert.equal(C.kindOf(utf8(svg), "no-extension"), "svg", "SVG is known by its content");
  assert.equal(C.kindOf(utf8("\ufeff<svg:svg xmlns:svg='http://www.w3.org/2000/svg'/>"), "a.svg"), "svg");
  assert.equal(C.kindOf(utf8("<html><body><svg></svg></body></html>"), "page.svg"), "", "an HTML page is not an SVG");
  assert.equal(C.kindOf(utf8("<!-- <svg> in a comment that never closes"), "a.svg"), "", "a cut-off comment is not a root");
  assert.equal(C.kindOf(utf8("<!--a--><!--b-->\n  <?pi x?><svg/>"), "a.svg"), "svg");
  assert.equal(C.kindOf(new Uint8Array([0x1f, 0x8b, 8, 0, 0, 0]), "logo.svgz"), "svg");
  assert.equal(C.kindOf(new Uint8Array([0x1f, 0x8b, 8, 0, 0, 0]), "logo.gz"), "");
  assert.equal(C.kindOf(utf8("a,b\n1,2\n"), "data.csv"), "csv", "CSV detection is unchanged");
});

test("refuse: the new pairs name what they take", () => {
  assert.equal(C.refuse("pdf-to-jpg", "pdf", 1000), "");
  assert.equal(C.refuse("pdf-to-jpg", "png", 1000), "This is a PNG file, not PDF.");
  assert.equal(C.refuse("png-to-jpg", "jpeg", 1000), "This is a JPEG file, not PNG, GIF or BMP.");
  assert.equal(C.refuse("png-to-jpg", "bmp", 1000), "");
  assert.equal(C.refuse("svg-to-png", "svg", 11 * 1048576), "That file is over 10 MB.");
  assert.equal(C.refuse("svg-to-png", "", 100), "This is not an SVG file, or it is damaged.");
  assert.equal(C.refuse("png-to-jpg", "svg", 100), "This is an SVG file, not PNG, GIF or BMP.");
});

test("parsePages: ranges, open ends, duplicates and the messages", () => {
  assert.deepEqual(plain(C.parsePages("", 3)), { pages: [1, 2, 3] });
  assert.deepEqual(plain(C.parsePages("  ", 2)), { pages: [1, 2] });
  assert.deepEqual(plain(C.parsePages("8, 1-3, 2", 10)), { pages: [1, 2, 3, 8] });
  assert.deepEqual(plain(C.parsePages("4-", 6)), { pages: [4, 5, 6] });
  assert.deepEqual(plain(C.parsePages("2\u20134; 6", 9)), { pages: [2, 3, 4, 6] }, "en dash and semicolon");
  assert.deepEqual(plain(C.parsePages("5-99", 7)), { pages: [5, 6, 7] }, "a range past the end stops at the last page");
  assert.deepEqual(plain(C.parsePages("1,,3,", 3)), { pages: [1, 3] });
  assert.equal(C.parsePages("9", 3).error, "This PDF has 3 pages, so there is no page 9.");
  assert.equal(C.parsePages("2", 1).error, "This PDF has 1 page, so there is no page 2.");
  assert.equal(C.parsePages("5-2", 9).error, "\u201c5-2\u201d is not a range of pages.");
  assert.equal(C.parsePages("0", 9).error, "\u201c0\u201d is not a range of pages.");
  assert.match(C.parsePages("one", 9).error, /^Pages should look like 1-3, 8\. \u201cone\u201d is not a page or a range\.$/);
});

test("pageRaster and pageName", () => {
  assert.deepEqual(plain(C.pageRaster(612, 792, 150, false)), { width: 1275, height: 1650, scale: 150 / 72, dpi: 150 });
  assert.deepEqual(plain(C.pageRaster(612, 792, 300, false)).width, 2550);
  const poster = C.pageRaster(2384, 3370, 300, false); // A0 at 300 dpi is 93 MP
  assert.ok(poster.width * poster.height <= C.MAX_PIXELS_PAGE);
  assert.ok(poster.dpi < 300 && poster.dpi > 100, String(poster.dpi));
  const phone = C.pageRaster(612, 792, 300, true);
  assert.ok(phone.width * phone.height <= C.MAX_PIXELS_MOBILE);
  assert.equal(C.pageName("Report.PDF", 3, 12, "jpg"), "Report-p003.jpg");
  assert.equal(C.pageName("big.pdf", 7, 1200, "png"), "big-p0007.png");
});

test("svgSize: units, viewBox fallback and the browser default", () => {
  const size = (t) => plain(C.svgSize(t));
  assert.deepEqual(size('<svg width="24" height="12"/>'), { width: 24, height: 12, viewBox: null, from: "size" });
  assert.deepEqual(size("<svg height='2in' width='1in'></svg>"), { width: 96, height: 192, viewBox: null, from: "size" });
  assert.equal(C.svgSize('<svg width="72pt" height="6pc"/>').height, 96);
  assert.equal(Math.round(C.svgSize('<svg width="25.4mm" height="2.54cm"/>').width), 96);
  assert.deepEqual(size('<svg width="100%" height="100%" viewBox="0 0 40 20"/>'), { width: 40, height: 20, viewBox: [0, 0, 40, 20], from: "viewBox" });
  assert.deepEqual(size('<svg viewBox="-5,-5 10,30"/>').viewBox, [-5, -5, 10, 30]);
  assert.deepEqual(size('<svg width="80" viewBox="0 0 40 20"/>'), { width: 80, height: 40, viewBox: [0, 0, 40, 20], from: "size" });
  assert.deepEqual(size("<svg/>"), { width: 300, height: 150, viewBox: null, from: "default" });
  assert.equal(C.svgSize('<!-- <svg width="1" height="1"> -->\n<svg width="50" height="5"/>').width, 50, "a commented-out root is skipped");
  assert.equal(C.svgSize('<svg:svg xmlns:svg="x" width="7" height="3"/>').width, 7);
  assert.equal(C.svgSize("<html/>"), null);
});

test("svgWithSize: sets the pixel size and keeps or adds a viewBox, so the drawing scales as a vector", () => {
  assert.equal(C.svgWithSize('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="12"><path/></svg>', 96, 48),
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 12" width="96" height="48"><path/></svg>');
  assert.equal(C.svgWithSize('<svg viewBox="0 0 40 20"/>', 80, 40), '<svg viewBox="0 0 40 20" width="80" height="40"/>');
  assert.equal(C.svgWithSize("<svg height='5' viewBox='0 0 2 1' width='10'>", 20, 10), "<svg viewBox='0 0 2 1' width=\"20\" height=\"10\">");
  const pre = '<?xml version="1.0"?>\n<!-- <svg width="9"> -->\n';
  assert.equal(C.svgWithSize(pre + '<svg width="10mm" height="5mm"/>', 76, 38), pre + '<svg viewBox="0 0 37.7953 18.8976" width="76" height="38"/>');
  assert.equal(C.svgWithSize("not svg", 1, 1), "not svg");
});

test("svgOutSize, svgNotes and svgDecode", () => {
  assert.deepEqual(plain(C.svgOutSize(24, 12, "2")), { width: 48, height: 24 });
  assert.deepEqual(plain(C.svgOutSize(24, 12, "4")), { width: 96, height: 48 });
  assert.deepEqual(plain(C.svgOutSize(300, 150, "width", 1000)), { width: 1000, height: 500 });
  assert.equal(C.svgNotes('<svg><image href="https://example.org/a.png"/></svg>').length, 1);
  assert.equal(C.svgNotes('<svg><image xlink:href="data:image/png;base64,AAAA"/></svg>').length, 0, "embedded images are fine");
  assert.equal(C.svgNotes('<svg><image xlink:href="http://example.org/a.png"/></svg>').length, 1);
  assert.equal(C.svgNotes("<svg><style>@import url(https://fonts.example/x.css);</style></svg>").length, 1);
  assert.equal(C.svgDecode(utf8("<svg>\u00e9</svg>")), "<svg>\u00e9</svg>");
  assert.equal(C.svgDecode(new Uint8Array([...utf8('<?xml version="1.0" encoding="ISO-8859-1"?><svg>'), 0xe9, ...utf8("</svg>")])).slice(-7), "\u00e9</svg>");
  assert.equal(C.svgDecode(new Uint8Array([0xff, 0xfe, 0x3c, 0, 0x73, 0])), "<s");
});

test("vendored pdf.js is the version its folder names, with the module and worker from the same build", () => {
  // The browser build does not run under Node (it asks for pdf.js's legacy build), so drawing is checked in the
  // browser runs; here the module and its worker must agree, since pdf.js refuses a worker of another version.
  const dir = join(SITE, "assets/vendor/pdfjs-6.4.299");
  for (const f of ["pdf.min.mjs", "pdf.worker.min.mjs"]) {
    const src = readFileSync(join(dir, f), "utf8");
    assert.ok(src.includes('"6.4.299"'), f + " is 6.4.299");
  }
  const shell = readFileSync(join(SITE, "tools/convert/convert-shell.js"), "utf8");
  for (const k of ["wasmUrl", "cMapUrl", "standardFontDataUrl", "iccUrl", "useWorkerFetch: false"]) assert.ok(shell.includes(k), k);
});

// ---------- fourth set: XLSX to CSV, JSON to CSV, TIFF to JPG ----------
// TIFF fixtures (netlify/tests/fixtures/convert-tiff-*.tif) were written by Pillow or by hand, and every one was
// decoded to the same pixels as Pillow before it was added here: PackBits whose compressed length equals the raw
// length (UTIF copies that raw), WhiteIsZero CCITT G4, a 4-bit palette, gray with alpha, LZW with the horizontal
// predictor, 16 by 16 tiles, Adobe Deflate (32946), big-endian 16-bit gray, a multi-page file with a thumbnail, and
// a directory chain that points back on itself.
const tiffLibs = (() => {
  const c = { self: {}, console: { log() {} }, process: { env: {} } };
  vm.createContext(c);
  vm.runInContext(readFileSync(join(SITE, "assets/vendor/utif-3.1.0/pako_inflate.min.js"), "utf8"), c);
  vm.runInContext(readFileSync(join(SITE, "assets/vendor/utif-3.1.0/UTIF.js"), "utf8"), c);
  return { pako: c.self.pako, UTIF: c.self.UTIF };
})();
const tiff = (name) => new Uint8Array(readFileSync(join(HERE, "fixtures/convert-tiff-" + name + ".tif")));
const decodeTiff = (name, page = 0) => {
  const b = tiff(name), t = C.readTiff(b), p = t.pages[page];
  assert.equal(p.problem, "", name + ": " + p.problem);
  return { p, rgba: C.tiffRGBA(C.tiffDecodeRaw(b, p, tiffLibs), p) };
};
const pix = (d, x, y) => Array.from(d.rgba.slice((y * d.p.width + x) * 4, (y * d.p.width + x) * 4 + 4));

test("sniff and kindOf: TIFF, BigTIFF, XLS, XLSX and JSON", () => {
  assert.equal(C.sniff(utf8("II*\0\b\0\0\0\0\0\0\0")), "tiff");
  assert.equal(C.sniff(new Uint8Array([0x4d, 0x4d, 0, 0x2a, 0, 0, 0, 8, 0, 0, 0, 0])), "tiff");
  assert.equal(C.sniff(utf8("II+\0\b\0\0\0\0\0\0\0")), "bigtiff");
  assert.equal(C.sniff(new Uint8Array([0xd0, 0xcf, 0x11, 0xe0, 0xa1, 0xb1, 0x1a, 0xe1, 0, 0, 0, 0])), "xls");
  const zip = new Uint8Array([0x50, 0x4b, 3, 4, 20, 0, 0, 0, 8, 0, 0, 0]);
  assert.equal(C.kindOf(zip, "book.xlsx"), "xlsx");
  assert.equal(C.kindOf(zip, "macro.XLSM"), "xlsx");
  assert.equal(C.kindOf(zip, "letter.docx"), "", "a Word file is a zip too, but not a workbook");
  assert.equal(C.kindOf(utf8("a,b"), "data.xlsx"), "", "a text file named .xlsx is not a workbook");
  assert.equal(C.kindOf(utf8('[{"a":1}]'), "x.json"), "json");
  assert.equal(C.kindOf(utf8('{"a":1}\n{"a":2}\n'), "x.ndjson"), "json");
  assert.equal(C.kindOf(utf8('﻿  [1,2]'), "export.txt"), "json", "a .txt that starts like JSON");
  assert.equal(C.kindOf(utf8("a,b\n1,2"), "export.txt"), "csv", "a .txt that does not is still CSV");
  assert.equal(C.kindOf(utf8("[id],name\n1,a"), "list.csv"), "csv", "a .csv is CSV even when it starts with a bracket");
});

test("refuse: the fourth set's messages", () => {
  assert.match(C.refuse("xlsx-to-csv", "xls", 100), /^This is an older Excel workbook \(\.xls\), or an \.xlsx protected with a password\./);
  assert.equal(C.refuse("xlsx-to-csv", "csv", 100), "This is a CSV file, not XLSX.");
  assert.equal(C.refuse("tiff-to-jpg", "bigtiff", 100), "This is a BigTIFF, a variant for files over 4 GB that this page cannot read.");
  assert.equal(C.refuse("tiff-to-jpg", "png", 100), "This is a PNG file, not TIFF.");
  assert.equal(C.refuse("json-to-csv", "csv", 100), "This is a CSV file, not JSON.");
  assert.equal(C.refuse("json-to-csv", "json", 51 * 1048576), "That file is over 50 MB.");
});

test("options: the fourth set's keys and defaults", () => {
  const o = C.options("xlsx-to-csv", {});
  assert.deepEqual([o.output, o.sheets, o.bom, o.safe, o.delimiter], ["csv", "first", false, true, "auto"]);
  assert.equal(C.options("xlsx-to-csv", { sheets: "all", safe: false, bom: true }).sheets, "all");
  assert.equal(C.options("xlsx-to-csv", { safe: false }).safe, false);
  assert.equal(C.options("json-to-csv", { nested: "json", output: "xlsx" }).nested, "json");
  assert.equal(C.options("json-to-csv", { nested: "x" }).nested, "columns");
  assert.equal(C.options("tiff-to-jpg", { tiffpages: "all" }).tiffpages, "all");
  assert.equal(C.options("tiff-to-jpg", { tiffpages: "3" }).tiffpages, "first");
  assert.equal(C.options("pdf-to-jpg", { pages: "2-4" }).pages, "2-4", "the PDF page range keeps its own key");
});

test("XLSX readers: workbook, rels, shared strings, styles", () => {
  const wb = C.parseWorkbook('<workbook><workbookPr date1904="1"/><sheets><sheet name="Data &amp; notes" sheetId="1" r:id="rId1"/>' +
    '<sheet name="データ" sheetId="2" state="hidden" r:id="rId2"/></sheets></workbook>');
  assert.deepEqual(plain(wb), { sheets: [{ name: "Data & notes", rid: "rId1", state: "visible" }, { name: "データ", rid: "rId2", state: "hidden" }], date1904: true });
  assert.equal(C.parseWorkbook('<workbook><sheets/></workbook>').date1904, false);
  const rels = plain(C.parseRels('<Relationships><Relationship Id="rId1" Type="http://x/worksheet" Target="worksheets/sheet1.xml"/>' +
    '<Relationship Id="rId2" Type="http://x/worksheet" Target="/xl/worksheets/s2.xml"/><Relationship Id="rId3" Type="http://x/chartsheet" Target="../x/c.xml"/></Relationships>', "xl/"));
  assert.deepEqual(rels, { rId1: { target: "xl/worksheets/sheet1.xml", type: "worksheet" }, rId2: { target: "xl/worksheets/s2.xml", type: "worksheet" }, rId3: { target: "x/c.xml", type: "chartsheet" } });
  const sst = C.parseSharedStrings('<sst><si><t>plain</t></si><si><r><t>rich </t></r><r><rPr/><t xml:space="preserve">text</t></r></si>' +
    '<si><t>東京</t><rPh><t>トウキョウ</t></rPh></si><si><t>line_x000D_\nbreak &lt;b&gt; &#233;</t></si><si/></sst>');
  assert.deepEqual(plain(sst), ["plain", "rich text", "東京", "line\r\nbreak <b> é", ""]);
  const styles = C.parseStyles('<styleSheet><numFmts><numFmt numFmtId="164" formatCode="yyyy-mm-dd hh:mm"/><numFmt numFmtId="165" formatCode="0.00&quot; days&quot;"/>' +
    '<numFmt numFmtId="166" formatCode="[h]:mm"/><numFmt numFmtId="167" formatCode="[Red]0.00"/></numFmts><cellXfs><xf numFmtId="0"/><xf numFmtId="14"/>' +
    '<xf numFmtId="164"/><xf numFmtId="165"/><xf numFmtId="20"/><xf numFmtId="166"/><xf numFmtId="167"/><xf numFmtId="10"/><xf numFmtId="22"/></cellXfs></styleSheet>');
  assert.deepEqual(plain(styles), ["", "date", "datetime", "", "time", "", "", "", "datetime"]);
});

test("excelDate: both date systems, the 1900 leap-year bug, rounding to the second", () => {
  assert.equal(C.excelDate(46329, "date", false), "2026-11-03");
  assert.equal(C.excelDate(1, "date", false), "1900-01-01");
  assert.equal(C.excelDate(59, "date", false), "1900-02-28");
  assert.equal(C.excelDate(60, "date", false), "1900-02-29", "the day Excel counts that never was");
  assert.equal(C.excelDate(61, "date", false), "1900-03-01");
  assert.equal(C.excelDate(44867, "date", true), "2026-11-03", "the 1904 system is 1,462 days behind");
  assert.equal(C.excelDate(46329.5, "datetime", false), "2026-11-03 12:00:00");
  assert.equal(C.excelDate(0.6, "time", false), "14:24:00", "0.6 of a day is 14:24, not 14:23:59");
  assert.equal(C.excelDate(46329.9999999, "datetime", false), "2026-11-04 00:00:00", "rounding past midnight moves the day");
});

test("sheetRows: cell types, gaps, formulas, styles and formula protection", () => {
  const shared = ["name", "=HYPERLINK(\"x\")", "-5 items"];
  const styles = ["", "date"];
  const xml = '<worksheet><sheetData>' +
    '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="C1" t="inlineStr"><is><t>inline</t></is></c><c r="D1" s="1"><v>46329</v></c></row>' +
    '<row r="3"><c r="B3"><v>3.50</v></c><c r="C3"><f>1+1</f><v>2</v></c><c r="D3"><f>A1</f></c><c r="G3"><f>B3*2</f><v></v></c><c r="E3" t="b"><v>1</v></c><c r="F3" t="e"><v>#N/A</v></c></row>' +
    '<row r="4"><c r="A4" t="s"><v>1</v></c><c r="B4" t="s"><v>2</v></c><c r="C4"><v>-5</v></c><c r="D4" t="str"><v>@sum</v></c></row>' +
    '</sheetData></worksheet>';
  const r = C.sheetRows(xml, shared, styles, false, 1e6, true);
  assert.deepEqual(plain(r.rows), [["name", "", "inline", "2026-11-03"], [], ["", "3.50", "2", "", "TRUE", "#N/A"],
    ["'=HYPERLINK(\"x\")", "'-5 items", "-5", "'@sum"]]);
  assert.equal(r.formulasWithoutValue, 2, "no <v>, and an empty <v>");
  assert.equal(C.sheetRows(xml, shared, styles, false, 1e6, false).rows[3][0], "=HYPERLINK(\"x\")", "protection off");
  assert.throws(() => C.sheetRows(xml, shared, styles, false, 5, true), /more than 5e-06 million cells|more than/);
});

test("toCsv: quoting, CRLF, trimmed edges; sheetFileName", () => {
  assert.equal(C.toCsv([["a", "b,c", 'say "hi"'], ["line\nbreak", "", ""], [], []], ","), 'a,"b,c","say ""hi"""\r\n"line\nbreak",,\r\n');
  assert.equal(C.toCsv([["x", "", ""], ["y", "z", ""]], ";"), "x;\r\ny;z\r\n");
  assert.equal(C.toCsv([["a;b", "c"]], ";"), '"a;b";c\r\n');
  assert.equal(C.toCsv([], ","), "");
  assert.equal(C.sheetFileName("Q1/Q2: draft?"), "Q1_Q2_ draft_");
  assert.equal(C.sheetFileName("  .hidden. "), "hidden");
  assert.equal(C.sheetFileName(""), "Sheet");
});

test("protectBigInts and jsonRecords: shapes, JSON Lines, long IDs, errors", () => {
  assert.equal(C.protectBigInts('{"id": 1234567890123456789, "n": 12, "s": "1234567890123456789", "f": 1234567890123456.5}'),
    '{"id": "\\u00001234567890123456789", "n": 12, "s": "1234567890123456789", "f": 1234567890123456.5}');
  assert.equal(C.protectBigInts('[-12345678901234567890,1e30, "a\\"b 99999999999999999"]'), '["\\u0000-12345678901234567890",1e30, "a\\"b 99999999999999999"]');
  const api = C.jsonRecords('{"meta": {"count": 2}, "data": [{"id": 1}, {"id": 2}], "included": [{"x": 1}]}');
  assert.deepEqual([api.from, plain(api.others), api.records.length], ["data", ["included"], 2]);
  assert.equal(C.jsonRecords('﻿[{"a": 1}]').records.length, 1, "a BOM is fine");
  const lines = C.jsonRecords('{"a": 1}\n\n{"a": 2, "b": true}\n');
  assert.deepEqual([lines.lines, lines.records.length], [true, 2]);
  assert.deepEqual(plain(C.jsonRecords('{"only": "one"}').records), [{ only: "one" }]);
  assert.throws(() => C.jsonRecords("{nope"), /^Error: This is not valid JSON \(/);
  assert.throws(() => C.jsonRecords('{"a":1}\n{bad}\n'), /line 2 is not a JSON value either/);
});

test("flattenRecords: columns, nesting, collisions, long IDs, formula protection, cell cap", () => {
  const recs = C.jsonRecords('[{"id": 98765432109876543210, "user": {"name": "Ada", "tags": ["x", "y"]}, "user.name": "literal"},' +
    ' {"id": 2, "score": -5, "note": "=1+1", "ok": false, "none": null, "__proto__": "p"}]').records;
  const f = C.flattenRecords(recs, "columns", true);
  assert.deepEqual(plain(f.rows), [
    ["id", "user.name", "user.tags", "user.name (2)", "score", "note", "ok", "none", "__proto__"],
    ["98765432109876543210", "Ada", '["x","y"]', "literal", "", "", "", "", ""],
    ["2", "", "", "", "-5", "'=1+1", "false", "", "p"]]);
  const j = C.flattenRecords(C.jsonRecords('[{"id": 12345678901234567890, "user": {"id": 12345678901234567891}}]').records, "json", false);
  assert.deepEqual(plain(j.rows), [["id", "user"], ["12345678901234567890", '{"id":12345678901234567891}']], "long IDs stay exact inside JSON text too");
  assert.deepEqual(plain(C.flattenRecords([1, "a", null], "columns", false).rows), [["value"], ["1"], ["a"], [""]]);
  assert.throws(() => C.flattenRecords([{ a: 1, b: 2 }, { c: 3 }], "columns", false, 5), /makes 6 cells \(2 rows by 3 columns\)/);
});

test("readTiff: pages, thumbnails, a looping chain, damage, BigTIFF", () => {
  const multi = C.readTiff(tiff("multipage"));
  assert.deepEqual(plain(multi.pages.map((p) => [p.width, p.height, p.thumbnail])), [[40, 20, false], [10, 5, true], [30, 30, false]]);
  assert.equal(C.readTiff(tiff("loop")).pages.length, 1, "a directory that points back at itself ends the chain");
  assert.throws(() => C.readTiff(tiff("packbits").slice(0, 600)), /damaged or cut short/, "the directory itself is cut off");
  assert.equal(C.readTiff(tiff("be16").slice(0, 150)).pages[0].problem, "This TIFF is damaged or cut short.", "the strip runs past the end");
  assert.throws(() => C.readTiff(utf8("II+\0\b\0\0\0")), /BigTIFF/);
  assert.throws(() => C.readTiff(utf8("II\0\0\b\0\0\0")), /not a TIFF/);
  assert.throws(() => C.readTiff(new Uint8Array(4)), /empty or cut short/);
});

test("TIFF decoding matches Pillow for every layout the page takes", () => {
  const RED = [255, 0, 0, 255], BLUE = [0, 0, 255, 255];
  const pb = decodeTiff("packbits");
  assert.deepEqual([pix(pb, 1, 1), pix(pb, 38, 1)], [RED, BLUE], "PackBits that happens to be as long as the raw data");
  const z = decodeTiff("deflate32946");
  assert.deepEqual([z.p.compression, pix(z, 1, 1), pix(z, 38, 1)], [32946, RED, BLUE]);
  const g4 = decodeTiff("g4-whiteiszero");
  assert.deepEqual([pix(g4, 1, 1), pix(g4, 60, 1)], [[255, 255, 255, 255], [0, 0, 0, 255]]);
  const p4 = decodeTiff("palette4");
  assert.deepEqual([pix(p4, 0, 0), pix(p4, 1, 0), pix(p4, 4, 1), pix(p4, 5, 1)], [RED, [0, 255, 0, 255], BLUE, [255, 255, 0, 255]]);
  const ga = decodeTiff("gray-alpha");
  assert.deepEqual([pix(ga, 1, 1), pix(ga, 38, 1)], [[100, 100, 100, 255], [50, 50, 50, 0]]);
  for (const name of ["lzw-predictor", "tiled"]) {
    const g = decodeTiff(name);
    assert.deepEqual([pix(g, 0, 0), pix(g, 17, 17), pix(g, 39, 19)], [[0, 0, 128, 255], [102, 204, 128, 255], [234, 228, 128, 255]], name);
  }
  const be = decodeTiff("be16");
  assert.deepEqual(pix(be, 3, 2), [192, 192, 192, 255], "16-bit big-endian keeps its high byte");
  assert.deepEqual(pix(decodeTiff("multipage", 2), 5, 5), [0, 200, 0, 255]);
});

test("TIFF pieces: unpackBits, unpredict, refusals, orientation, JPEG tables", () => {
  const out = new Uint8Array(8);
  assert.equal(C.unpackBits(new Uint8Array([2, 1, 2, 3, 0xfd, 9]), out), 7);
  assert.deepEqual(Array.from(out), [1, 2, 3, 9, 9, 9, 9, 0]);
  const p = { spp: 1, bps: [16], le: true };
  const buf = new Uint8Array([0xff, 0xff, 2, 0]); // 65535 then +2 wraps to 1
  C.tiffUnpredict(buf, p, 2, 1);
  assert.deepEqual(Array.from(buf), [0xff, 0xff, 1, 0]);
  const f = tiff("palette4"), t = C.readTiff(f).pages[0];
  assert.equal(t.problem, "");
  for (const [k, v, msg] of [["compression", 6, /compression \(number 6\)/], ["planar", 2, /separate plane/], ["sampleFormat", 3, /floating-point/],
    ["photometric", 8, /color model \(number 8\)/], ["predictor", 3, /predictor/], ["colorMap", null, /palette that is missing/]]) {
    const copy = Object.assign({}, t, { [k]: v }, k === "planar" ? { spp: 3 } : {});
    assert.match(C.tiffProblem(copy, f.length), msg, k);
  }
  assert.match(C.tiffProblem(Object.assign({}, t, { photometric: 2, spp: 1, bps: [8] }), f.length), /fewer than three samples/);
  assert.match(C.tiffProblem(Object.assign({}, t, { photometric: 2, spp: 3, bps: [8, 8, 4] }), f.length), /8\/8\/4 bits per sample/);
  assert.deepEqual(plain(C.orientTransform(6, 40, 20)), { width: 20, height: 40, m: [0, 1, -1, 0, 20, 0] });
  // Each transform must land the four corners of the stored picture on the four corners of the upright canvas.
  for (let o = 1; o <= 8; o++) {
    const r = C.orientTransform(o, 40, 20), [a, b, c, d, e, g] = r.m;
    const corners = [[0, 0], [40, 0], [0, 20], [40, 20]].map(([x, y]) => [a * x + c * y + e, b * x + d * y + g].join(",")).sort();
    assert.deepEqual(corners, ["0,0", `0,${r.height}`, `${r.width},0`, `${r.width},${r.height}`].sort(), "orientation " + o);
  }
  const jpg = C.tiffJpeg(new Uint8Array([0xff, 0xd8, 0xff, 0xda, 1, 0xff, 0xd9]), new Uint8Array([0xff, 0xd8, 0xff, 0xdb, 7, 0xff, 0xd9]));
  assert.deepEqual(Array.from(jpg), [0xff, 0xd8, 0xff, 0xdb, 7, 0xff, 0xda, 1, 0xff, 0xd9]);
  const rgb = Array.from(C.tiffJpeg(new Uint8Array([0xff, 0xd8, 0xff, 0xda, 1]), null, true));
  assert.deepEqual(rgb.slice(0, 18), [0xff, 0xd8, 0xff, 0xee, 0, 14, 0x41, 0x64, 0x6f, 0x62, 0x65, 0, 100, 0, 0, 0, 0, 0], "Adobe APP14, transform 0");
  assert.deepEqual(rgb.slice(18), [0xff, 0xda, 1]);
});

// ---------- fifth set: CSV to JSON, ICNS to PNG, ICO to PNG ----------
// fixtures/csvjson/*.expected.json were written by a Python reference (csv and json, with the rules in the design
// doc) apart from this code; fixtures/convert-icns-synth.icns was written with an independent RLE encoder, and
// iconutil decodes it to the pixels asserted below; the convert-ico-*.ico BMP entries match Pillow's decode, except the
// 32-bit entry whose alpha is all 0, where the AND mask applies (as in Windows; Pillow leaves it transparent).
const csvDir = join(HERE, "fixtures/csvjson");
const pairs = (t) => JSON.parse(t, function (k, v) { return v; });

test("sniff: ICNS and ICO, and an ftyp box that starts like an ICO", () => {
  assert.equal(C.sniff(new Uint8Array(readFileSync(join(HERE, "fixtures/convert-icns-synth.icns")).subarray(0, 4096))), "icns");
  assert.equal(C.sniff(new Uint8Array(readFileSync(join(HERE, "fixtures/convert-ico-bmp24.ico")))), "ico");
  const cur = new Uint8Array(readFileSync(join(HERE, "fixtures/convert-ico-bmp24.ico"))); cur[2] = 2;
  assert.equal(C.sniff(cur), "ico", "a cursor");
  const heic = new Uint8Array([0, 0, 1, 0, 0x66, 0x74, 0x79, 0x70, 0x68, 0x65, 0x69, 0x63, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]);
  assert.notEqual(C.sniff(heic), "ico", "a 256-byte ftyp box is not an icon");
  assert.equal(C.sniff(utf8("icns,size\n1,2\n3,4\n")), "", "a CSV that starts with the word icns");
  assert.equal(C.refuse("ico-to-png", "icns", 10), "This is an ICNS file, not ICO.");
  assert.equal(C.refuse("icns-to-png", "png", 10), "This is a PNG file, not ICNS.");
  const o = C.options("csv-to-json", {});
  assert.deepEqual([o.output, o.header, o.types, o.unflatten], ["json", true, true, false]);
  assert.equal(C.options("ico-to-png", { icons: "all" }).icons, "all");
  assert.equal(C.options("ico-to-png", { icons: "x" }).icons, "largest");
});

test("csvToJson matches the Python reference on every fixture and option set", () => {
  const VARIANTS = { default: {}, strings: { types: false }, noheader: { header: false }, unflatten: { unflatten: true } };
  for (const f of ["basic", "semicolon", "cp1252", "years", "nest", "ragged", "column-clash"]) {
    const b = new Uint8Array(readFileSync(join(csvDir, f + ".csv")));
    const want = JSON.parse(readFileSync(join(csvDir, f + ".expected.json"), "utf8"));
    for (const [v, kw] of Object.entries(VARIANTS)) {
      const dec = C.decodeText(b, ""), d = C.detectDelimiter(dec.text, f + ".csv"), o = C.options("csv-to-json", kw);
      for (const lines of [false, true]) {
        const r = C.csvToJson(C.parseCsv(dec.text, d), { header: o.header, types: o.types, unflatten: o.unflatten, lines, delimiter: d });
        const text = r.parts.join("");
        const got = lines ? text.trim().split("\n").map(pairs) : pairs(text);
        assert.deepEqual(got, pairs(want[v]), f + " " + v + (lines ? " jsonl" : ""));
      }
    }
  }
});

test("csvToJson keeps header order, the round-trip number rule, and its caps", () => {
  const rows = (t) => C.parseCsv(t, ",");
  const text = C.csvToJson(rows("2024,2023,name\n5,4,x\n"), { header: true, types: true, delimiter: "," }).parts.join("");
  assert.equal(text, '[\n  {\n    "2024": 5,\n    "2023": 4,\n    "name": "x"\n  }\n]\n', "integer-like keys stay in header order");
  const types = plain(C.columnTypes(rows("3.50,90210,-0,1.5e-400,1.10,TRUE,7\n2,02134,0,1,1.2,false,8\n"), 7, ","));
  assert.deepEqual(types, ["string", "string", "string", "string", "string", "boolean", "number"]);
  assert.deepEqual(plain(C.jsonKeys(["", "column 1", "a", "a", "a (2)"], 6)), ["column 1", "column 1 (2)", "a", "a (2)", "a (2) (2)", "column 6"]);
  assert.equal(C.csvToJson(rows("a\n"), { header: true, delimiter: "," }).rows, 0);
});

test("readIcns and icnsRGBA: the synthesized icon decodes to what iconutil shows", () => {
  const t = C.readIcns(new Uint8Array(readFileSync(join(HERE, "fixtures/convert-icns-synth.icns"))));
  assert.deepEqual(plain(t.images.map((i) => [i.slot, i.type, i.format, i.width])), [["icon_128x128", "ic07", "png", 128], ["icon_32x32", "il32", "rle", 32], ["icon_16x16", "ic04", "argb", 16]]);
  assert.deepEqual(plain(t.skipped), [512], "the JPEG 2000 512 size is skipped");
  const at = (rgba, w, x, y) => Array.from(rgba.slice((y * w + x) * 4, (y * w + x) * 4 + 4));
  const il32 = C.icnsRGBA(t.images[1]);
  assert.deepEqual([at(il32, 32, 2, 2), at(il32, 32, 30, 2), at(il32, 32, 2, 30)], [[255, 0, 0, 255], [0, 0, 255, 255], [255, 0, 0, 128]]);
  const ic04 = C.icnsRGBA(t.images[2]);
  assert.deepEqual([at(ic04, 16, 2, 2), at(ic04, 16, 12, 2)], [[0, 255, 0, 255], [0, 255, 0, 64]], "ARGB colors are premultiplied");
  assert.equal(C.icnsRle(new Uint8Array([0x81, 7]), 5), null, "a run that stops short");
  assert.deepEqual(Array.from(C.icnsRle(new Uint8Array([1, 9, 8, 0x80, 5]), 5)), [9, 8, 5, 5, 5]);
  assert.throws(() => C.readIcns(utf8("icns\0\0\x10\0" + "x".repeat(8))), /cut short/);
  const bad = new Uint8Array(24); bad.set(utf8("icns"), 0); bad[7] = 24; bad.set(utf8("ic07"), 8); bad[15] = 200;
  assert.throws(() => C.readIcns(bad), /runs past the end/);
});

test("readIco and icoBmp: every bit depth, masks, and the lenient directory", () => {
  const read = (n) => C.readIco(new Uint8Array(readFileSync(join(HERE, "fixtures/convert-ico-" + n + ".ico"))));
  const px = (img, x, y) => Array.from(C.icoBmp(img).slice((y * img.width + x) * 4, (y * img.width + x) * 4 + 4));
  const b24 = read("bmp24").images[0];
  assert.deepEqual([b24.width, b24.height, b24.depth], [16, 16, 24]);
  assert.deepEqual([px(b24, 1, 0), px(b24, 0, 0), px(b24, 15, 15)], [[16, 0, 128, 255], [0, 0, 128, 0], [240, 240, 128, 0]], "mask bit set where (x + y) % 5 == 0");
  assert.deepEqual(px(read("bmp1").images[0], 1, 0), [0, 0, 0, 255]);
  assert.deepEqual(px(read("bmp1").images[0], 4, 0), [255, 255, 255, 255]);
  assert.deepEqual(px(read("bmp4").images[0], 1, 0), [17, 238, 40, 255], "palette index 1");
  assert.deepEqual(px(read("bmp8").images[0], 2, 1), [33, 99, 222, 255], "palette index 33");
  const b32 = read("bmp32").images[0];
  assert.deepEqual([px(b32, 1, 0), px(b32, 12, 0)], [[16, 0, 128, 255], [192, 0, 128, 64]], "a 32-bit entry keeps its own alpha");
  const z = read("bmp32-zero-alpha").images[0];
  assert.deepEqual([px(z, 1, 0), px(z, 0, 0)], [[200, 10, 10, 255], [200, 10, 10, 0]], "all-zero alpha: the AND mask decides, as in Windows");
  // A directory entry that points past the end is left out with a note; the rest is read.
  const f = new Uint8Array(readFileSync(join(HERE, "fixtures/convert-ico-bmp24.ico")));
  const two = new Uint8Array(f.length + 16); two.set(f.subarray(0, 6)); two[4] = 2; two.set(f.subarray(6, 22), 6);
  two.set([32, 32, 0, 0, 1, 0, 32, 0, 0, 0, 1, 0, 0, 0, 1, 0], 22); two.set(f.subarray(22), 38);
  two[6 + 12] += 16; // the first entry's data moved 16 bytes
  const r = C.readIco(two);
  assert.deepEqual([r.images.length, r.problems.length], [1, 1]);
  assert.throws(() => C.readIco(utf8("\0\0\x01\0\0\0")), /list of sizes/);
});

test("pngEncode writes RGBA exactly, faint pixels included, with valid CRCs", async () => {
  const zlib = createRequire(import.meta.url)("node:zlib");
  const rgba = new Uint8ClampedArray([255, 255, 255, 3, 162, 139, 139, 22, 0, 0, 0, 0, 10, 20, 30, 255]);
  const png = await C.pngEncode(rgba, 2, 2, async (d) => new Uint8Array(zlib.deflateSync(d)));
  assert.deepEqual(plain(C.pngSize(png)), { width: 2, height: 2 });
  const dv = new DataView(png.buffer, png.byteOffset), idatLen = dv.getUint32(33);
  assert.equal(String.fromCharCode(...png.subarray(37, 41)), "IDAT");
  assert.equal(dv.getUint32(41 + idatLen), C.crc32(png.subarray(37, 41 + idatLen)), "IDAT CRC");
  const raw = zlib.inflateSync(png.subarray(41, 41 + idatLen));
  assert.deepEqual(Array.from(raw), [0, 255, 255, 255, 3, 162, 139, 139, 22, 0, 0, 0, 0, 0, 10, 20, 30, 255]);
  assert.equal(C.crc32(new TextEncoder().encode("IEND")), 0xae426082, "the CRC every PNG's IEND carries");
});

test("parseSharedStrings: a self-closing <si/> or <t/> is an empty string and does not shift the rest", () => {
  assert.deepEqual(plain(C.parseSharedStrings("<sst><si><t>a</t></si><si/><si><t>c</t></si><si><r><t/></r><r><t>d</t></r></si></sst>")), ["a", "", "c", "d"]);
});

test("xmlText: literal line ends normalized as XML does, escaped carriage returns kept", () => {
  assert.equal(C.xmlText("a\r\nb\rc"), "a\nb\nc");
  assert.equal(C.xmlText("a_x000D_\nb&#13;"), "a\r\nb\r");
});

// ---------- sixth set: XLSX to JSON, VTT to SRT, SRT to VTT ----------
// fixtures/subs/*.expected.* are this code's output, checked against ffmpeg 9.0.2 on the same files: cue times match
// exactly, and text matches apart from the documented differences (speaker names, decoded numeric entities, the
// auto-caption merge, a cue whose blank line is missing split off instead of glued into the previous one).
const subs = join(HERE, "fixtures/subs");
test("subtitle kinds and refusals", () => {
  const k = (t, n) => C.kindOf(utf8(t), n);
  assert.equal(k("WEBVTT\n\n00:01.000 --> 00:02.000\nx\n", "a.vtt"), "vtt");
  assert.equal(k("﻿WEBVTT - title\n", "captions"), "vtt");
  assert.equal(k("WEBVTTX\n", "a.txt"), "csv", "WEBVTT must be followed by a space or line break");
  assert.equal(k("1\r\n00:00:01,000 --> 00:00:02,000\r\nhi\r\n", "captions.txt"), "srt", "a .txt holding SRT");
  assert.equal(k("anything", "a.srt"), "srt");
  assert.equal(C.kindOf(new Uint8Array([0xff, 0xfe, 0x31, 0]), "u16.srt"), "srt", "UTF-16 by name");
  assert.equal(C.refuse("csv-to-json", "srt", 10), "This is an SRT file, not CSV.");
  assert.equal(C.refuse("srt-to-vtt", "vtt", 10), "This is a WebVTT file, not SRT.");
});
test("SRT to VTT and VTT to SRT match the checked outputs", () => {
  for (const [src, out, fn] of [["basic.srt", "basic.srt.expected.vtt", "vtt"], ["cp1252.srt", "cp1252.srt.expected.vtt", "vtt"],
    ["basic.vtt", "basic.vtt.expected.srt", "srt"], ["youtube.vtt", "youtube.vtt.expected.srt", "srt"], ["repeat.vtt", "repeat.vtt.expected.srt", "srt"]]) {
    const text = C.decodeText(new Uint8Array(readFileSync(join(subs, src))), "").text;
    let got;
    if (fn === "vtt") got = C.writeVtt(C.parseSrt(text).cues).text;
    else { const v = C.parseVtt(text); got = C.writeSrt(v.cues, { speakers: true, merge: v.autoCaptions }).text; }
    assert.equal(got, readFileSync(join(subs, out), "utf8"), src);
  }
});
test("subtitle rules: times, escaping, voices, the two merge shapes", () => {
  assert.equal(C.subMs("01:02:03,4"), 3723400, "a short fraction is a decimal");
  assert.equal(C.subMs("123:00:00.000"), 442800000, "hours past 99");
  const vtt = C.writeVtt([{ start: 0, end: 1000, text: "a & b <x> --> c <I>i</I> {\\an8}top" }]).text;
  assert.equal(vtt, "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\na &amp; b  --&gt; c <i>i</i> top\n");
  const s = (cues, o) => C.writeSrt(cues, o).text.replace(/\r/g, "");
  const two = [{ start: 0, end: 1000, text: "<v Ana>Hi" }, { start: 1000, end: 2000, text: "<v Ana>Again" }, { start: 2000, end: 3000, text: "<v Bob>Yes" }];
  assert.equal(s(two, {}), "1\n00:00:00,000 --> 00:00:01,000\nAna: Hi\n\n2\n00:00:01,000 --> 00:00:02,000\nAgain\n\n3\n00:00:02,000 --> 00:00:03,000\nBob: Yes\n", "a name only when the speaker changes");
  assert.equal(s(two, { speakers: false }).split("\n")[2], "Hi");
  const same = [{ start: 0, end: 900, text: "No." }, { start: 1000, end: 1900, text: "No." }];
  assert.equal(C.writeSrt(same, { merge: true }).cues, 2, "two genuine identical captions both stay");
  assert.throws(() => C.parseVtt("1\n00:00:01,000 --> 00:00:02,000\nx"), /does not start with WEBVTT/);
});
test("XLSX to JSON: cell kinds, header rules, numbers as JSON, dates with T, no formula guard", async () => {
  const JSZip = vendored("jszip/jszip.min.js");
  const zip = await JSZip.loadAsync(readFileSync(join(HERE, "fixtures/convert-xlsx-edge.xlsx")));
  const txt = async (p) => (zip.file(p) ? await zip.file(p).async("string") : "");
  const wb = C.parseWorkbook(await txt("xl/workbook.xml")), rels = C.parseRels(await txt("xl/_rels/workbook.xml.rels"), "xl/");
  const shared = C.parseSharedStrings(await txt("xl/sharedStrings.xml")), styles = C.parseStyles(await txt("xl/styles.xml"));
  const data = wb.sheets.find((s) => s.name === "Data");
  const r = C.sheetRows(await txt(rels[data.rid].target), shared, styles, wb.date1904, 5e6, false, true);
  const j = JSON.parse(C.sheetJson(r.rows, r.kinds, { header: true }).parts.join(""));
  assert.deepEqual(j[0], { id: 1, name: "-text", score: 3.5, ok: true, when: "2026-11-03", at: "2026-11-03T14:05:00", err: "#N/A", note: null, "id (2)": 7 });
  assert.equal(j[1].score, 0.5, "a stored .5 becomes valid JSON");
  assert.equal(j[1].name, "=not a formula", "JSON gets no formula guard");
  assert.equal(j.length, 3, "the leading blank row and the empty row inside are skipped");
  const csv = C.sheetRows(await txt(rels[data.rid].target), shared, styles, wb.date1904, 5e6, true);
  assert.equal(csv.kinds, undefined, "XLSX to CSV gets no kinds");
  assert.throws(() => C.sheetRows('<sheetData><row r="2000000"><c r="A2000000"><v>1</v></c></row></sheetData>', [], [], false), /past Excel's last row/);
});
