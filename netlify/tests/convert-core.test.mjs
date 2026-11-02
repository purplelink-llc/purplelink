// The in-browser converters (site/tools/convert/): sniffing, naming, options, the ICNS writer, and a real decode of a
// HEIC fixture with the vendored libheif, so a broken or swapped decoder build fails here rather than on the live page.
// The fixture is 64 x 48, left half red and right half blue, written by macOS `sips -s format heic` (502 bytes).
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
const ctx = { self: {} };
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
  assert.deepEqual(plain(C.options("heic-to-jpg", {})), { output: "jpg", quality: 0.92, background: "#ffffff", iconset: false, mobile: false });
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
