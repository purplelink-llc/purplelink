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
    sizes: "all", page: "a4", margin: false, delimiter: "auto", encoding: "auto", header: true, text: false
  });
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
