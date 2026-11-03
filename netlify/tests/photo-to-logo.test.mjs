// Photo to logo (site/tools/photo-to-logo/): the LogoForge pytest suite ported case for case (geometry, construction,
// scoring), plus the parts that replace Apple Vision and OpenCV in the browser: cutout and plain-background masks,
// clean-up, the distance transform, contour tracing and the rasteriser. Design: docs/designs/photo-to-logo.md.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import vm from "node:vm";

const HERE = dirname(fileURLToPath(import.meta.url));
const DIR = join(HERE, "..", "..", "site", "tools", "photo-to-logo");
const ctx = { self: {} };
vm.createContext(ctx);
for (const f of ["logo-geometry.js", "logo-mask.js"]) vm.runInContext(readFileSync(join(DIR, f), "utf8"), ctx);
const G = ctx.self.LogoGeometry, M = ctx.self.LogoMask;

const close = (a, b, tol, msg) => assert.ok(Math.abs(a - b) <= tol, `${msg || ""} ${a} vs ${b}`);

/** A w x h 0/1 mask with fill(x, y) deciding each pixel. */
function maskOf(w, h, fill) {
  const m = new Uint8Array(w * h);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) m[y * w + x] = fill(x, y) ? 1 : 0;
  return m;
}

/** LogoForge's synthetic subject: a rectangle body with a disc head on the right (cv2 fills both ends inclusive). */
const SW = 900, SH = 600;
const synthetic = () => maskOf(SW, SH, (x, y) =>
  (x >= 150 && x <= 600 && y >= 200 && y <= 400) || (x - 600) ** 2 + (y - 300) ** 2 <= 100 * 100);

function build(mask, w, h, eps = 0.01, angles = "45") {
  const dense = G.denseContour(M.traceContour(mask, w, h));
  const b = G.bounds(dense);
  const D = Math.hypot(b[2] - b[0], b[3] - b[1]);
  return G.construct(dense, G.rdpClosed(dense, eps * D), { eps, angles }, G.makeRng(0));
}

// ---------------------------------------------------------------- angles (test_geometry.py)

test("snapAngle: nearest allowed direction, wrap at 180, ties to the smaller angle", () => {
  close(G.snapAngle(43, [0, 45, 90, 135]), 45, 1e-9);
  close(G.snapAngle(179, [0, 45, 90, 135]), 0, 1e-9);
  close(G.snapAngle(100, [0, 30, 60, 90, 120, 150]), 90, 1e-9);
  close(G.snapAngle(-30, [0, 45, 90, 135]), 135, 1e-9);
  close(G.snapAngle(67.5, [0, 45, 90, 135]), 45, 1e-9);
  close(G.snapAngle(37.2, []), 37.2, 1e-9);
});

test("angDist wraps at 180", () => {
  close(G.angDist(178, 2), 4, 1e-9);
  close(G.angDist(10, 100), 90, 1e-9);
});

test("clusterAngles: two groups, length-weighted mean, and across the wrap", () => {
  const out = G.clusterAngles([44, 47, 89], [1, 2, 1], 6);
  close(out[0], out[1], 1e-9);
  close(out[0], 46, 0.05);
  close(out[2], 89, 1e-9);
  const w = G.clusterAngles([178, 2], null, 6);
  close(w[0], w[1], 1e-9);
  assert.ok(G.angDist(w[0], 0) < 1e-6);
});

// ---------------------------------------------------------------- fits

function noisyCircle(rng, n = 200) {
  const gauss = () => Math.sqrt(-2 * Math.log(1 - rng.float())) * Math.cos(2 * Math.PI * rng.float());
  const pts = [];
  for (let i = 0; i < n; i++) {
    const t = 0.2 + 2.4 * rng.float();
    pts.push([200 + 80 * Math.cos(t) + 0.5 * gauss(), 150 + 80 * Math.sin(t) + 0.5 * gauss()]);
  }
  for (let i = 0; i < n * 0.2; i++) pts[i] = [50 + 300 * rng.float(), 50 + 300 * rng.float()];
  return pts;
}

test("RANSAC recovers a circle from noisy points with 20% outliers, and repeats for the same seed", () => {
  const pts = noisyCircle(G.makeRng(7));
  const fit = G.fitCircleRansac(pts, 2, G.makeRng(1), 200);
  assert.ok(Math.hypot(fit.center[0] - 200, fit.center[1] - 150) < 1);
  close(fit.r, 80, 1);
  const a = G.fitCircleRansac(pts, 2, G.makeRng(42), 200), b = G.fitCircleRansac(pts, 2, G.makeRng(42), 200);
  assert.deepEqual([...a.center, a.r], [...b.center, b.r]);
});

test("Kasa is exact on clean points; TLS finds the direction", () => {
  const pts = [];
  for (let i = 0; i < 30; i++) { const t = (1.5 * i) / 29; pts.push([10 + 5 * Math.cos(t), -3 + 5 * Math.sin(t)]); }
  const c = G.fitCircleKasa(pts);
  close(c.center[0], 10, 1e-9); close(c.center[1], -3, 1e-9); close(c.r, 5, 1e-9);
  const line = [];
  for (let i = 0; i < 50; i++) { const x = (100 * i) / 49; line.push([x, 0.5 * x + 3]); }
  close(G.fitLineTLS(line).theta, (Math.atan(0.5) * 180) / Math.PI, 1e-9);
});

// ---------------------------------------------------------------- tangency, concentric, intersections

test("makeTangent shifts a near line to exact tangency and leaves a far one", () => {
  const arc = G.makeArc([0, 0], 10);
  const line = G.makeLine(0, [5, 9]);
  assert.equal(G.makeTangent(line, arc, 1.5), true);
  const n = G.lineN(line);
  close(Math.abs(n[0] * (0 - line.c[0]) + n[1] * (0 - line.c[1])), 10, 1e-6);
  assert.equal(line.theta, 0);
  const tp = G.tangentPoint(line, [0, 0]);
  close(tp[0], 0, 1e-9); close(tp[1], 10, 1e-9);
  assert.equal(G.makeTangent(G.makeLine(0, [0, 20]), arc, 1.5), false);
});

test("mergeConcentric merges near centres only", () => {
  const a = G.makeArc([100, 100], 40), b = G.makeArc([103, 100], 20), c = G.makeArc([300, 100], 20);
  G.mergeConcentric([a, b, c], 10);
  assert.deepEqual([...a.center], [...b.center]);
  assert.deepEqual([...c.center], [300, 100]);
});

test("circle touch point and intersections", () => {
  const p = G.circleTouchPoint([0, 0], 5, [10.2, 0], 5, 0.5);
  close(p[0], 5, 1e-9); close(p[1], 0, 1e-9);
  const a = G.makeLine(0, [0, 2]), b = G.makeLine(90, [3, 0]);
  const x = G.intersectLines(a, b);
  close(x[0], 3, 1e-9); close(x[1], 2, 1e-9);
  assert.equal(G.intersectLines(a, G.makeLine(0, [0, 5])), null);
  const pts = G.intersectLineCircle(a, [0, 0], 2);
  assert.equal(pts.length, 2);
  close(pts[0][0], pts[1][0], 1e-6);
});

// ---------------------------------------------------------------- outline and construction (test_construct.py)

test("closed RDP keeps a rectangle's corners", () => {
  const m = maskOf(200, 200, (x, y) => x >= 50 && x <= 150 && y >= 50 && y <= 150);
  const brk = G.rdpClosed(G.denseContour(M.traceContour(m, 200, 200)), 2);
  assert.ok(brk.length >= 4 && brk.length <= 6, `${brk.length} break points`);
});

test("synthetic subject: simple, faithful, with an arc", () => {
  const m = synthetic();
  const con = build(m, SW, SH);
  assert.ok(con.segments.length <= 8, `${con.segments.length} segments`);
  assert.ok(con.segments.some((s) => s.kind === "arc"));
  assert.ok(G.iou(G.fillPolygon(G.samplePolygon(con), SW, SH), m) > 0.95);
});

test("synthetic subject: lines use the allowed angles", () => {
  for (const s of build(synthetic(), SW, SH, 0.01, "45").segments) {
    if (s.kind === "line") assert.ok([0, 45, 90, 135, 180].some((a) => Math.abs(s.theta - a) < 1e-6), String(s.theta));
  }
});

test("the SVG path is deterministic", () => {
  assert.equal(G.svgPath(build(synthetic(), SW, SH)), G.svgPath(build(synthetic(), SW, SH)));
  assert.match(G.svgPath(build(synthetic(), SW, SH)), /^M[\d. -]+(?:[LA][\d. -]+)+Z$/);
});

test("buildVariants runs the 20-variant grid and returns three differing picks", () => {
  const m = synthetic();
  const r = G.buildVariants(M.traceContour(m, SW, SH), m, SW, SH);
  assert.equal(r.variants.length, 20);
  assert.equal(r.picks.length, 3);
  const picks = r.picks.map((i) => r.variants[i]);
  assert.ok(picks.every((p) => G.guardOk(p)));
  const s = G.summarise(picks[0]);
  for (const k of ["path", "bbox", "guides", "iou", "nodes"]) assert.ok(k in s, k);
  assert.equal(JSON.stringify(G.buildVariants(M.traceContour(m, SW, SH), m, SW, SH).picks), JSON.stringify(r.picks));
});

// ---------------------------------------------------------------- scoring (test_score_render.py)

const v = (name, iou, leg, nodes, angles = "45", eps = 0.01, conn = 0) =>
  ({ variant: name, iou, legibility: leg, nodes, connectors: conn, offAngle: 0, distinctAngles: 2, arcs: 0, eps, angles });

test("Pareto front drops dominated variants", () => {
  const a = v("a", 0.9, 0.9, 10), b = v("b", 0.8, 0.8, 12), c = v("c", 0.95, 0.85, 20);
  const front = G.paretoFront([a, b, c]);
  assert.ok(front.includes(a) && front.includes(c) && !front.includes(b));
});

test("guard rules", () => {
  assert.equal(G.guardOk(v("x", 0.49, 0.9, 10)), false);
  assert.equal(G.guardOk(v("x", 0.9, 0.9, 41)), false);
  assert.equal(G.guardOk(v("x", 0.9, 0.9, 10, "45", 0.01, 3)), false);
  assert.equal(G.guardOk(v("x", 0.9, 0.9, 10, "45", 0.01, 2)), true);
});

test("picks differ in setting and the best comes first", () => {
  const vs = [v("a", 0.95, 0.9, 10, "45", 0.01), v("b", 0.94, 0.9, 10, "45", 0.01), v("c", 0.9, 0.88, 12, "30", 0.02)];
  const names = G.pickTop3(vs).map((p) => p.variant);
  assert.equal(names[0], "a");
  assert.equal(names.length, 3);
  assert.equal(G.pickTop3([v("x", 0.4, 0.9, 10)]).length, 0);
});

// ---------------------------------------------------------------- rasteriser and numbers

test("fillPolygon fills a known area with the nonzero rule", () => {
  const sq = G.fillPolygon([[10, 10], [30, 10], [30, 30], [10, 30]], 40, 40);
  assert.equal(sq.reduce((s, x) => s + x, 0), 400);
  const tri = G.fillPolygon([[0, 0], [40, 0], [0, 40]], 40, 40).reduce((s, x) => s + x, 0);
  close(tri, 800, 25);
  // a square traced twice the same way stays filled (nonzero), not emptied (even-odd)
  const twice = G.fillPolygon([[10, 10], [30, 10], [30, 30], [10, 30], [10, 10], [30, 10], [30, 30], [10, 30]], 40, 40);
  assert.equal(twice.reduce((s, x) => s + x, 0), 400);
});

test("fmt rounds half away from zero and never writes -0", () => {
  assert.equal(G.fmt(1.25), "1.3");
  assert.equal(G.fmt(-1.25), "-1.3");
  assert.equal(G.fmt(-0.04), "0");
  assert.equal(G.fmt(12), "12");
});

// ---------------------------------------------------------------- masks (replacing Apple Vision)

function rgbaOf(w, h, px) {
  const a = new Uint8ClampedArray(w * h * 4);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) a.set(px(x, y), 4 * (y * w + x));
  return a;
}

test("alphaMask: a cutout, an opaque photo, and a tight cutout with few clear pixels", () => {
  const disc = (x, y) => (x - 50) ** 2 + (y - 50) ** 2 < 40 * 40;
  const cut = M.alphaMask(rgbaOf(100, 100, (x, y) => [20, 20, 20, disc(x, y) ? 255 : 0]), 100, 100);
  assert.equal(cut.cutout, true);
  assert.equal(cut.mask[50 * 100 + 50], 1);
  assert.equal(cut.mask[0], 0);
  assert.equal(M.alphaMask(rgbaOf(100, 100, () => [20, 20, 20, 255]), 100, 100).cutout, false);
  // only one corner clear: 1% of the image
  const tight = M.alphaMask(rgbaOf(100, 100, (x, y) => [0, 0, 0, x < 10 && y < 10 ? 0 : 255]), 100, 100);
  assert.equal(tight.cutout, true);
});

test("plainBackground: a dark disc on white is plain, a noisy photo is not", () => {
  const rng = G.makeRng(3);
  const inDisc = (x, y) => (x - 60) ** 2 + (y - 50) ** 2 < 30 * 30;
  const px = (x, y) => (inDisc(x, y) ? [40, 30, 50, 255] : [245 + rng.int(8), 245 + rng.int(8), 245 + rng.int(8), 255]);
  const r = M.plainBackground(rgbaOf(120, 100, px), 120, 100);
  assert.equal(r.plain, true);
  assert.ok(G.iou(r.mask, maskOf(120, 100, inDisc)) > 0.98);
  const noisy = M.plainBackground(rgbaOf(120, 100, () => [rng.int(256), rng.int(256), rng.int(256), 255]), 120, 100);
  assert.equal(noisy.plain, false);
});

test("cleanMask keeps the largest piece, fills a hole and reports the dropped piece", () => {
  const m = maskOf(200, 120, (x, y) => (x >= 20 && x < 120 && y >= 20 && y < 100 && !(x >= 60 && x < 70 && y >= 50 && y < 60)) ||
    (x >= 150 && x < 170 && y >= 40 && y < 60));
  const r = M.cleanMask(m, 200, 120);
  assert.equal(r.mask[55 * 200 + 65], 1, "hole filled");
  assert.equal(r.mask[50 * 200 + 160], 0, "small piece dropped");
  close(r.dropped, 400 / (100 * 80 - 100), 1e-9);
  assert.equal(M.cleanMask(new Uint8Array(100), 10, 10).area, 0);
});

test("distance-transform dilation equals a brute-force disc", () => {
  const w = 41, h = 33, r = 5;
  const m = maskOf(w, h, (x, y) => (x === 20 && y === 16) || (x === 3 && y === 30));
  const fast = M.dilate(m, w, h, r);
  const slow = maskOf(w, h, (x, y) => (x - 20) ** 2 + (y - 16) ** 2 <= r * r || (x - 3) ** 2 + (y - 30) ** 2 <= r * r);
  assert.deepEqual([...fast], [...slow]);
});

/** Trace a mask and fill the traced polygon back (through pixel centres, so it is half a pixel short on every side). */
function traceBack(m, w, h) {
  const c = M.traceContour(m, w, h);
  const fill = G.fillPolygon(c.map(([x, y]) => [x + 0.5, y + 0.5]), w, h);
  const grown = M.dilate(fill, w, h, 1.5);
  let inside = 0, total = 0;
  for (let i = 0; i < m.length; i++) if (m[i]) { total++; if (grown[i]) inside++; }
  return { c, cover: inside / total, iou: G.iou(fill, m) };
}

test("traceContour: a rectangle, a one-pixel neck, and a shape touching the frame edge", () => {
  const rect = maskOf(60, 40, (x, y) => x >= 10 && x < 50 && y >= 10 && y < 30);
  const r = traceBack(rect, 60, 40);
  assert.equal(r.c.length, 2 * (40 + 20) - 4);
  assert.deepEqual([...r.c[0]], [10, 10]);
  assert.ok(r.iou > 0.9);
  const neck = maskOf(80, 40, (x, y) => (x >= 5 && x < 35 && y >= 5 && y < 35) || (y === 20 && x >= 35 && x < 45) ||
    (x >= 45 && x < 75 && y >= 5 && y < 35));
  const n = traceBack(neck, 80, 40);
  assert.ok(n.cover > 0.99, `neck covered ${n.cover}`);
  assert.ok(n.c.some(([x]) => x > 60), "the trace crosses the neck to the second square");
  const edge = maskOf(50, 50, (x, y) => x ** 2 + (y - 25) ** 2 < 20 * 20);
  assert.ok(traceBack(edge, 50, 50).iou > 0.9);
  assert.equal(M.traceContour(new Uint8Array(25), 5, 5).length, 0);
});
