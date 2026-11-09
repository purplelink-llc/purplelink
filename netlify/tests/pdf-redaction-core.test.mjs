import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const src = readFileSync(new URL("../../site/tools/pdf-redaction-checker/pdf-redaction-core.js", import.meta.url), "utf8");
const mod = { exports: {} };
new Function("module", "exports", src)(mod, mod.exports);
const core = mod.exports;

function canvas(w, h, fn) {
  const d = new Uint8ClampedArray(w * h * 4);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const v = fn(x, y), i = (y * w + x) * 4;
    d[i] = d[i + 1] = d[i + 2] = v; d[i + 3] = 255;
  }
  return d;
}
const rect = { x0: 2, y0: 2, x1: 18, y1: 10 };

test("a solid dark area is covered", () => {
  const d = canvas(20, 12, () => 0);
  assert.equal(core.isCovered(core.regionStats(d, 20, 12, rect)), true);
});

test("black text on white is not covered", () => {
  const d = canvas(20, 12, (x) => (x % 3 === 0 ? 0 : 255));
  assert.equal(core.isCovered(core.regionStats(d, 20, 12, rect)), false);
});

test("white text on a dark band is not covered", () => {
  const d = canvas(20, 12, (x) => (x % 3 === 0 ? 255 : 0));
  assert.equal(core.isCovered(core.regionStats(d, 20, 12, rect)), false);
});

test("a blank page is not covered", () => {
  const d = canvas(20, 12, () => 255);
  assert.equal(core.isCovered(core.regionStats(d, 20, 12, rect)), false);
});

test("a rect outside the canvas does not throw or count as covered", () => {
  const d = canvas(20, 12, () => 0);
  assert.equal(core.isCovered(core.regionStats(d, 20, 12, { x0: 50, y0: 50, x1: 60, y1: 60 })), false);
});

test("splitWords returns offsets", () => {
  assert.deepEqual(core.splitWords(" ab  cde"), [{ text: "ab", start: 1, end: 3 }, { text: "cde", start: 5, end: 8 }]);
});

test("maskSnippet keeps the start and hides the middle and end", () => {
  const m = core.maskSnippet("Account number 4417 1234 5678 9010");
  assert.ok(m.startsWith("Account number"));
  assert.ok(!m.includes("4417"));
  assert.ok(!core.maskSnippet("secretpassword").includes("secretpassword"));
  assert.equal(core.maskSnippet(""), "");
});

test("groupPlaces joins neighbouring hidden words on a line", () => {
  const w = (text, hidden, y) => ({ text, hidden, y, size: 12 });
  const places = core.groupPlaces([w("a", true, 100), w("b", true, 100), w("c", false, 100), w("d", true, 100), w("e", true, 130)]);
  assert.equal(places.length, 3);
  assert.equal(places[0].words, 2);
  assert.equal(places[1].words, 1);
});

test("classifyPage tells scans from text", () => {
  assert.equal(core.classifyPage({ images: true, textItems: 0, invisibleText: false }), "scan-no-text");
  assert.equal(core.classifyPage({ images: true, textItems: 5, invisibleText: true }), "scan-ocr");
  assert.equal(core.classifyPage({ images: true, textItems: 5, invisibleText: false }), "text");
  assert.equal(core.classifyPage({ images: false, textItems: 0, invisibleText: false }), "empty");
});
