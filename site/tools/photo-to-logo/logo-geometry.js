/* Photo to logo: outline, construction and scoring (LogoForge stages 2 to 5, ported from Python).
 *
 * Pure functions, no DOM. Runs in the page, in logo-worker.js and under Node for tests
 * (netlify/tests/photo-to-logo.test.mjs). Points are [x, y] in image coordinates (y down). Angles are line directions
 * in degrees modulo 180. Design: docs/designs/photo-to-logo.md; the Python original is LogoForge's
 * logoforge/{outline,geometry,construct,score}.py.
 */
(function (root) {
  "use strict";

  const DEG = 180 / Math.PI;
  const TAU = 2 * Math.PI;

  // ---------------------------------------------------------------- small vector helpers

  const sub = (a, b) => [a[0] - b[0], a[1] - b[1]];
  const add = (a, b) => [a[0] + b[0], a[1] + b[1]];
  const mul = (a, s) => [a[0] * s, a[1] * s];
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1];
  // Math.hypot is several times slower than sqrt in V8, and dist runs in RANSAC's inner loop
  const norm = (a) => Math.sqrt(a[0] * a[0] + a[1] * a[1]);
  const dist = (a, b) => { const x = a[0] - b[0], y = a[1] - b[1]; return Math.sqrt(x * x + y * y); };
  const mod = (a, m) => ((a % m) + m) % m;

  function mean(pts) {
    let x = 0, y = 0;
    for (const p of pts) { x += p[0]; y += p[1]; }
    return [x / pts.length, y / pts.length];
  }

  function bounds(pts) {
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const p of pts) {
      if (p[0] < x0) x0 = p[0]; if (p[0] > x1) x1 = p[0];
      if (p[1] < y0) y0 = p[1]; if (p[1] > y1) y1 = p[1];
    }
    return [x0, y0, x1, y1];
  }

  // ---------------------------------------------------------------- seeded random numbers

  /** FNV-1a 32-bit hash of a byte array (seeds RANSAC from the mask, so one mask gives one result). */
  function fnv1a(bytes) {
    let h = 0x811c9dc5;
    for (let i = 0; i < bytes.length; i++) {
      h ^= bytes[i];
      h = Math.imul(h, 0x01000193);
    }
    return h >>> 0;
  }

  /** sfc32 generator (integer arithmetic only, so every engine gives the same sequence). */
  function makeRng(a, b = 0x9e3779b9, c = 0x243f6a88, d = 0xb7e15162) {
    a >>>= 0; b >>>= 0; c >>>= 0; d >>>= 0;
    const next = () => {
      const t = (((a + b) | 0) + d) | 0;
      d = (d + 1) | 0;
      a = b ^ (b >>> 9);
      b = (c + (c << 3)) | 0;
      c = (c << 21) | (c >>> 11);
      c = (c + t) | 0;
      return (t >>> 0) / 4294967296;
    };
    for (let i = 0; i < 12; i++) next();
    return { float: next, int: (n) => Math.floor(next() * n) };
  }

  // ---------------------------------------------------------------- angles

  /** Distance between two line directions in degrees, modulo 180. */
  function angDist(a, b) {
    const d = mod(Math.abs(a - b), 180);
    return Math.min(d, 180 - d);
  }

  /** Nearest allowed direction (mod 180); an exact tie goes to the smaller angle. An empty set means free. */
  function snapAngle(theta, allowed) {
    theta = mod(theta, 180);
    if (!allowed || !allowed.length) return theta;
    let best = null;
    for (const a of allowed) {
      if (best === null) { best = a; continue; }
      const da = angDist(theta, a), db = angDist(theta, best);
      if (da < db || (da === db && mod(a, 180) < mod(best, 180))) best = a;
    }
    return mod(best, 180);
  }

  /** Weighted mean of directions using doubled angles, so 178 and 2 average to 0. */
  function axialMean(thetas, weights) {
    let s = 0, c = 0;
    thetas.forEach((t, i) => {
      const w = weights ? weights[i] : 1;
      s += w * Math.sin((2 * t) / DEG);
      c += w * Math.cos((2 * t) / DEG);
    });
    const m = mod((Math.atan2(s, c) * DEG) / 2, 180);
    return mod(Math.round(m * 1e9) / 1e9, 180);
  }

  /** Single-link groups: union-find over every pair for which close(i, j) holds. */
  function groups(n, close) {
    const parent = Array.from({ length: n }, (_, i) => i);
    const find = (i) => {
      while (parent[i] !== i) { parent[i] = parent[parent[i]]; i = parent[i]; }
      return i;
    };
    for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) if (close(i, j)) parent[find(i)] = find(j);
    const out = new Map();
    for (let i = 0; i < n; i++) {
      const r = find(i);
      if (!out.has(r)) out.set(r, []);
      out.get(r).push(i);
    }
    return [...out.values()];
  }

  /** Cluster directions within tol degrees (mod 180); returns each input's cluster mean. */
  function clusterAngles(thetas, weights, tol = 6) {
    const th = thetas.map((t) => mod(t, 180));
    const w = weights || th.map(() => 1);
    const out = new Array(th.length).fill(0);
    for (const idx of groups(th.length, (i, j) => angDist(th[i], th[j]) <= tol)) {
      const m = axialMean(idx.map((i) => th[i]), idx.map((i) => w[i]));
      for (const i of idx) out[i] = m;
    }
    return out;
  }

  // ---------------------------------------------------------------- fits

  /** Total least squares line: { theta (degrees mod 180), c (centroid) }. */
  function fitLineTLS(pts) {
    const c = mean(pts);
    if (pts.length < 2) return { theta: 0, c };
    let sxx = 0, syy = 0, sxy = 0;
    for (const p of pts) {
      const dx = p[0] - c[0], dy = p[1] - c[1];
      sxx += dx * dx; syy += dy * dy; sxy += dx * dy;
    }
    return { theta: mod(0.5 * Math.atan2(2 * sxy, sxx - syy) * DEG, 180), c };
  }

  function solve3(A, b) {
    const M = A.map((row, i) => [...row, b[i]]);
    for (let col = 0; col < 3; col++) {
      let piv = col;
      for (let r = col + 1; r < 3; r++) if (Math.abs(M[r][col]) > Math.abs(M[piv][col])) piv = r;
      if (Math.abs(M[piv][col]) < 1e-12) return null;
      [M[col], M[piv]] = [M[piv], M[col]];
      for (let r = 0; r < 3; r++) {
        if (r === col) continue;
        const f = M[r][col] / M[col][col];
        for (let k = col; k < 4; k++) M[r][k] -= f * M[col][k];
      }
    }
    return [M[0][3] / M[0][0], M[1][3] / M[1][1], M[2][3] / M[2][2]];
  }

  /** Algebraic least-squares circle (Kasa), data centred for stability: { center, r } or null. */
  function fitCircleKasa(pts) {
    const m = mean(pts);
    let a11 = 0, a12 = 0, a13 = 0, a22 = 0, a23 = 0, a33 = 0, b1 = 0, b2 = 0, b3 = 0;
    for (const p of pts) {
      const x = p[0] - m[0], y = p[1] - m[1], z = -(x * x + y * y);
      a11 += x * x; a12 += x * y; a13 += x; a22 += y * y; a23 += y; a33 += 1;
      b1 += x * z; b2 += y * z; b3 += z;
    }
    const sol = solve3([[a11, a12, a13], [a12, a22, a23], [a13, a23, a33]], [b1, b2, b3]);
    if (!sol) return null;
    const [D, E, F] = sol;
    const cx = -D / 2, cy = -E / 2;
    return { center: [cx + m[0], cy + m[1]], r: Math.sqrt(Math.max(cx * cx + cy * cy - F, 0)) };
  }

  function circleFrom3(a, b, c) {
    const [ax, ay] = a, [bx, by] = b, [cx, cy] = c;
    const d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by));
    if (Math.abs(d) < 1e-9) return null;
    const A = ax * ax + ay * ay, B = bx * bx + by * by, C = cx * cx + cy * cy;
    const center = [(A * (by - cy) + B * (cy - ay) + C * (ay - by)) / d, (A * (cx - bx) + B * (ax - cx) + C * (bx - ax)) / d];
    return { center, r: dist(a, center) };
  }

  /** Points inside the ring r - tol < |p - center| < r + tol, on a flat [x0, y0, x1, y1, ...] array. Squared
   * distances, no square root: this is RANSAC's inner loop and most of the run time. */
  function countInliers(xy, cx, cy, r, tol) {
    const lo = r > tol ? (r - tol) * (r - tol) : 0, hi = (r + tol) * (r + tol);
    let n = 0;
    for (let i = 0; i < xy.length; i += 2) {
      const x = xy[i] - cx, y = xy[i + 1] - cy, d = x * x + y * y;
      if (d > lo && d < hi) n++;
    }
    return n;
  }

  /** RANSAC circle (three distinct points per sample), then a Kasa refit on the inliers: { center, r } or null. */
  function fitCircleRansac(pts, tol, rng, iters = 200) {
    const n = pts.length;
    if (n < 3) return null;
    const xy = new Float64Array(2 * n);
    for (let i = 0; i < n; i++) { xy[2 * i] = pts[i][0]; xy[2 * i + 1] = pts[i][1]; }
    let best = null, bestCount = -1;
    for (let it = 0; it < iters; it++) {
      const i = rng.int(n);
      let j = rng.int(n - 1); if (j >= i) j++;
      let k = rng.int(n - 2);
      const lo = Math.min(i, j), hi = Math.max(i, j);
      if (k >= lo) k++;
      if (k >= hi) k++;
      const c = circleFrom3(pts[i], pts[j], pts[k]);
      if (!c) continue;
      const cnt = countInliers(xy, c.center[0], c.center[1], c.r, tol);
      if (cnt > bestCount) { bestCount = cnt; best = c; }
    }
    if (!best || bestCount < 3) return null;
    return fitCircleKasa(pts.filter((p) => Math.abs(dist(p, best.center) - best.r) < tol));
  }

  function circleRms(pts, center, r) {
    let s = 0;
    for (const p of pts) { const d = dist(p, center) - r; s += d * d; }
    return Math.sqrt(s / pts.length);
  }

  /** Unwrapped angles of points around a centre (numpy.unwrap of atan2). */
  function unwrapAngles(pts, center) {
    const out = [];
    let prev = null;
    for (const p of pts) {
      let a = Math.atan2(p[1] - center[1], p[0] - center[0]);
      if (prev !== null) {
        while (a - prev > Math.PI) a -= TAU;
        while (a - prev < -Math.PI) a += TAU;
      }
      out.push(a);
      prev = a;
    }
    return out;
  }

  /** Total angle swept by a polyline around a centre, in degrees (absolute). */
  function sweepDeg(pts, center) {
    const a = unwrapAngles(pts, center);
    return Math.abs((a[a.length - 1] - a[0]) * DEG);
  }

  /** True when the polyline turns one way for at least minFrac of its sampled steps (no S-bend). */
  function turningConsistent(pts, minFrac = 0.85) {
    if (pts.length < 5) return true;
    const step = Math.max(1, Math.floor(pts.length / 12));
    const q = [];
    for (let i = 0; i < pts.length; i += step) q.push(pts[i]);
    if (q.length < 4) return true;
    let pos = 0, cnt = 0;
    for (let i = 0; i + 2 < q.length; i++) {
      const d0 = sub(q[i + 1], q[i]), d1 = sub(q[i + 2], q[i + 1]);
      const cr = d0[0] * d1[1] - d0[1] * d1[0];
      if (Math.abs(cr) > 1e-9) { cnt++; if (cr > 0) pos++; }
    }
    if (!cnt) return false;
    const f = pos / cnt;
    return f >= minFrac || f <= 1 - minFrac;
  }

  // ---------------------------------------------------------------- primitives

  const makeLine = (theta, c, run) => ({ kind: "line", theta, c, run: run || [0, 0], weight: 1 });
  const makeArc = (center, r, run) => ({ kind: "arc", center, r, run: run || [0, 0], weight: 1 });
  const lineU = (l) => [Math.cos(l.theta / DEG), Math.sin(l.theta / DEG)];
  const lineN = (l) => { const u = lineU(l); return [-u[1], u[0]]; };

  /** Merge arc centres closer than tol to their radius-weighted mean. With ptsOf(arc), radii are refitted as the mean
   * distance of the arc's points from the shared centre, and with maxRms a group whose refit exceeds it stays apart. */
  function mergeConcentric(arcs, tol, ptsOf, maxRms) {
    for (const idx of groups(arcs.length, (i, j) => dist(arcs[i].center, arcs[j].center) < tol)) {
      if (idx.length < 2) continue;
      let ws = 0, cx = 0, cy = 0;
      for (const i of idx) { const w = arcs[i].r; ws += w; cx += arcs[i].center[0] * w; cy += arcs[i].center[1] * w; }
      const ctr = [cx / ws, cy / ws];
      const newR = new Map();
      let ok = true;
      for (const i of idx) {
        let r = arcs[i].r;
        if (ptsOf) {
          const p = ptsOf(arcs[i]);
          if (p.length) {
            r = p.reduce((s, q) => s + dist(q, ctr), 0) / p.length;
            if (maxRms != null && circleRms(p, ctr, r) > maxRms) ok = false;
          }
        }
        newR.set(i, r);
      }
      if (!ok) continue;
      for (const i of idx) { arcs[i].center = ctr.slice(); arcs[i].r = newR.get(i); }
    }
    return arcs;
  }

  /** Shift a line parallel until exactly tangent to the arc's circle, when within tol of it. True when it moved. */
  function makeTangent(line, arc, tol) {
    const n = lineN(line);
    const d = dot(n, sub(arc.center, line.c));
    if (Math.abs(Math.abs(d) - arc.r) > tol) return false;
    const target = d !== 0 ? Math.sign(d) * arc.r : arc.r;
    line.c = add(line.c, mul(n, d - target));
    return true;
  }

  /** Where two circles (nearly) touch, externally or internally, or null. */
  function circleTouchPoint(c0, r0, c1, r1, tol) {
    const v = sub(c1, c0), d = norm(v);
    if (d < 1e-9) return null;
    const u = mul(v, 1 / d);
    if (Math.abs(d - (r0 + r1)) < tol) return add(c0, mul(u, r0));
    if (Math.abs(d - Math.abs(r0 - r1)) < tol) return add(c0, mul(u, r0 >= r1 ? r0 : -r0));
    return null;
  }

  /** Foot of the perpendicular from a point onto the line. */
  function tangentPoint(line, p) {
    const u = lineU(line);
    return add(line.c, mul(u, dot(u, sub(p, line.c))));
  }

  function intersectLines(a, b) {
    const ua = lineU(a), ub = lineU(b);
    const den = ua[0] * ub[1] - ua[1] * ub[0];
    if (Math.abs(den) < 1e-9) return null;
    const w = sub(b.c, a.c);
    return add(a.c, mul(ua, (w[0] * ub[1] - w[1] * ub[0]) / den));
  }

  function intersectLineCircle(line, ctr, r) {
    const u = lineU(line), f = sub(line.c, ctr);
    const b = dot(u, f), c = dot(f, f) - r * r;
    const disc = b * b - c;
    if (disc < 0) return [];
    const s = Math.sqrt(disc);
    return [add(line.c, mul(u, -b - s)), add(line.c, mul(u, -b + s))];
  }

  function intersectCircles(c0, r0, c1, r1) {
    const d = dist(c0, c1);
    if (d < 1e-9 || d > r0 + r1 || d < Math.abs(r0 - r1)) return [];
    const a = (r0 * r0 - r1 * r1 + d * d) / (2 * d);
    const h = Math.sqrt(Math.max(r0 * r0 - a * a, 0));
    const v = sub(c1, c0);
    const m = add(c0, mul(v, a / d));
    const perp = [-v[1] / d, v[0] / d];
    return [add(m, mul(perp, h)), sub(m, mul(perp, h))];
  }

  function nearest(cands, ref) {
    if (!cands.length) return null;
    let best = cands[0];
    for (const p of cands) if (dist(p, ref) < dist(best, ref)) best = p;
    return best;
  }

  // ---------------------------------------------------------------- stage 2: outline

  /** Points evenly spaced `step` apart along a closed polyline. */
  function resample(c, step = 2) {
    const n0 = c.length;
    const s = [0];
    for (let i = 0; i < n0; i++) s.push(s[i] + dist(c[i], c[(i + 1) % n0]));
    const total = s[n0];
    const n = Math.max(8, Math.floor(total / step));
    const out = [];
    let k = 0;
    for (let i = 0; i < n; i++) {
      const t = (total * i) / n;
      while (k < n0 - 1 && s[k + 1] <= t) k++;
      const a = c[k], b = c[(k + 1) % n0];
      const len = s[k + 1] - s[k];
      const f = len > 0 ? (t - s[k]) / len : 0;
      out.push([a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f]);
    }
    return out;
  }

  /** Circular moving average over k points. */
  function smooth(c, k = 3) {
    if (k <= 1) return c.map((p) => p.slice());
    const n = c.length, pad = Math.floor(k / 2);
    return c.map((_, i) => {
      let x = 0, y = 0;
      for (let j = -pad; j <= pad; j++) { const p = c[mod(i + j, n)]; x += p[0]; y += p[1]; }
      return [x / k, y / k];
    });
  }

  const denseContour = (contour, step = 2, k = 3) => smooth(resample(contour, step), k);

  /** Indices kept by open-curve RDP (iterative; both ends always kept). */
  function rdpOpen(p, eps) {
    const keep = new Set([0, p.length - 1]);
    const stack = [[0, p.length - 1]];
    while (stack.length) {
      const [a, b] = stack.pop();
      if (b <= a + 1) continue;
      const seg = sub(p[b], p[a]), L = norm(seg);
      let best = -1, bestD = -1;
      for (let i = a + 1; i < b; i++) {
        const q = sub(p[i], p[a]);
        const d = L < 1e-9 ? norm(q) : Math.abs(q[0] * seg[1] - q[1] * seg[0]) / L;
        if (d > bestD) { bestD = d; best = i; }
      }
      if (bestD > eps) { keep.add(best); stack.push([a, best], [best, b]); }
    }
    return [...keep].sort((x, y) => x - y);
  }

  /** Closed-curve RDP: split at point 0 and the point farthest from it, simplify both halves. */
  function rdpClosed(c, eps) {
    const n = c.length;
    let far = 0;
    for (let i = 1; i < n; i++) if (dist(c[i], c[0]) > dist(c[far], c[0])) far = i;
    const a = rdpOpen(c.slice(0, far + 1), eps);
    const b = rdpOpen([...c.slice(far), c[0]], eps);
    const idx = new Set(a);
    for (const i of b) if (far + i < n) idx.add(far + i);
    return [...idx].sort((x, y) => x - y);
  }

  // ---------------------------------------------------------------- stage 3: construction

  const ANGLE_SETS = { "45": [0, 45, 90, 135], "30": [0, 30, 60, 90, 120, 150],
    "15": Array.from({ length: 12 }, (_, i) => i * 15), free: [] };

  /** LogoForge's starting parameters; lengths are fractions of the subject's bounding-box diagonal D. */
  const PARAMS = { eps: 0.01, angles: "45", arcTol: 0.006, rMin: 0.02, rMax: 0.6, minSweep: 35, maxK: 12,
    ransacIters: 120, snapTol: 12, parTol: 6, concTol: 0.015, tanTol: 0.012, minLen: 0.01, joinFar: 3 };

  const slice = (dense, i0, i1) => (i1 >= i0 ? dense.slice(i0, i1 + 1) : [...dense.slice(i0), ...dense.slice(0, i1 + 1)]);

  function runLen(dense, i0, i1) {
    const p = slice(dense, i0, i1);
    let s = 0;
    for (let i = 1; i < p.length; i++) s += dist(p[i], p[i - 1]);
    return s;
  }

  /** Position in brk of the break point with the smallest interior angle. */
  function sharpest(dense, brk) {
    let best = 1e9, bestPos = 0;
    const m = brk.length;
    for (let j = 0; j < m; j++) {
      const a = dense[brk[mod(j - 1, m)]], b = dense[brk[j]], c = dense[brk[(j + 1) % m]];
      const v1 = sub(a, b), v2 = sub(c, b), n1 = norm(v1), n2 = norm(v2);
      if (n1 < 1e-9 || n2 < 1e-9) continue;
      const ang = Math.acos(Math.max(-1, Math.min(1, dot(v1, v2) / (n1 * n2))));
      if (ang < best) { best = ang; bestPos = j; }
    }
    return bestPos;
  }

  function lineRms(pts, line) {
    const n = lineN(line);
    let s = 0;
    for (const p of pts) { const d = dot(sub(p, line.c), n); s += d * d; }
    return Math.sqrt(s / pts.length);
  }

  function project(prim, ref) {
    if (prim.kind === "line") return tangentPoint(prim, ref);
    const v = sub(ref, prim.center), n = norm(v);
    return add(prim.center, mul(n > 1e-9 ? mul(v, 1 / n) : [1, 0], prim.r));
  }

  /** Signed sweep (radians) of an arc segment from p0 to p1 in its travel direction. */
  function arcSweep(s) {
    const a0 = Math.atan2(s.p0[1] - s.center[1], s.p0[0] - s.center[0]);
    const a1 = Math.atan2(s.p1[1] - s.center[1], s.p1[0] - s.center[0]);
    const d = mod(a1 - a0, TAU);
    if (s.sweepPos) return d > 1e-9 ? d : TAU;
    return d > 1e-9 ? d - TAU : -TAU;
  }

  /** Stages 3a to 3g: a closed list of line, arc and connector segments from a dense contour and its break points. */
  function construct(dense, brkIn, params, rng) {
    const P = Object.assign({}, PARAMS, params);
    const bb = bounds(dense);
    const D = Math.hypot(bb[2] - bb[0], bb[3] - bb[1]);
    const m = brkIn.length;
    if (m < 3) throw new Error("too few break points");
    const s0 = sharpest(dense, brkIn);
    const brk = [...brkIn.slice(s0), ...brkIn.slice(0, s0)];
    const allowed = typeof P.angles === "string" ? ANGLE_SETS[P.angles] : P.angles;

    // 3a + 3b: from each break point keep the longest span that fits a line or (k >= 2) a circle
    const tol = P.arcTol * D;
    const prims = [];
    let i = 0;
    while (i < m) {
      let best = null;
      for (let k = 1; k <= Math.min(P.maxK, m - i, m - 1); k++) {
        const run = [brk[i], brk[(i + k) % m]];
        const pts = slice(dense, run[0], run[1]);
        const fl = fitLineTLS(pts);
        const ln = makeLine(fl.theta, fl.c, run);
        if (k === 1 || lineRms(pts, ln) < tol) { best = [k, ln]; continue; }
        const fit = fitCircleRansac(pts, tol, rng, P.ransacIters);
        if (!fit) continue;
        if (!(P.rMin * D <= fit.r && fit.r <= P.rMax * D) || circleRms(pts, fit.center, fit.r) >= tol) continue;
        if (sweepDeg(pts, fit.center) < P.minSweep || !turningConsistent(pts)) continue;
        best = [k, makeArc(fit.center, fit.r, run)];
      }
      const [k, prim] = best;
      prim.weight = runLen(dense, prim.run[0], prim.run[1]);
      prims.push(prim);
      i += k;
    }

    // 3c absorb short lines into the longer line neighbour (never into an arc)
    let changed = true;
    while (changed && prims.length > 3) {
      changed = false;
      for (let j = 0; j < prims.length; j++) {
        const p = prims[j];
        if (!(p.kind === "line" && p.weight < P.minLen * D)) continue;
        const nbs = [[prims[mod(j - 1, prims.length)], "prev"], [prims[(j + 1) % prims.length], "next"]]
          .filter(([q]) => q.kind === "line");
        if (!nbs.length) continue;
        const [q, side] = nbs.length === 2 && nbs[1][0].weight > nbs[0][0].weight ? nbs[1] : nbs[0];
        q.run = side === "prev" ? [q.run[0], p.run[1]] : [p.run[0], q.run[1]];
        q.weight = runLen(dense, q.run[0], q.run[1]);
        const fl = fitLineTLS(slice(dense, q.run[0], q.run[1]));
        q.theta = fl.theta; q.c = fl.c;
        prims.splice(j, 1);
        changed = true;
        break;
      }
    }

    let lines = prims.filter((p) => p.kind === "line");
    // 3d snap within snapTol; a line further from every allowed angle keeps its direction (off angle)
    const off = new Set();
    for (const l of lines) {
      const s = snapAngle(l.theta, allowed);
      if (allowed.length && angDist(s, l.theta) > P.snapTol) off.add(l);
      else l.theta = s;
    }
    // 3e parallels: cluster, re-snap the snapped ones, re-centre, merge same-direction neighbours
    if (lines.length) {
      const cl = clusterAngles(lines.map((l) => l.theta), lines.map((l) => l.weight), P.parTol);
      lines.forEach((l, k) => { l.theta = off.has(l) || !allowed.length ? cl[k] : snapAngle(cl[k], allowed); });
    }
    for (const l of lines) l.c = mean(slice(dense, l.run[0], l.run[1]));
    let j = 0;
    while (j < prims.length && prims.length > 3) {
      const nxt = (j + 1) % prims.length;
      const a = prims[j], b = prims[nxt];
      if (a.kind === "line" && b.kind === "line" && angDist(a.theta, b.theta) < 1e-6) {
        a.run = [a.run[0], b.run[1]];
        a.weight = runLen(dense, a.run[0], a.run[1]);
        a.c = mean(slice(dense, a.run[0], a.run[1]));
        off.delete(b);
        prims.splice(nxt, 1);
        if (nxt < j) j--;
        continue;
      }
      j++;
    }

    // 3f concentric centres (kept only when each refit stays close to its run), then same-circle neighbours
    let arcs = prims.filter((p) => p.kind === "arc");
    mergeConcentric(arcs, P.concTol * D, (a) => slice(dense, a.run[0], a.run[1]), 1.5 * tol);
    j = 0;
    while (j < prims.length && prims.length > 3) {
      const nxt = (j + 1) % prims.length;
      const a = prims[j], b = prims[nxt];
      if (a.kind === "arc" && b.kind === "arc" && dist(a.center, b.center) < 1e-6 && Math.abs(a.r - b.r) < tol) {
        a.run = [a.run[0], b.run[1]];
        a.r = (a.r * a.weight + b.r * b.weight) / (a.weight + b.weight);
        a.weight = runLen(dense, a.run[0], a.run[1]);
        prims.splice(nxt, 1);
        if (nxt < j) j--;
        continue;
      }
      j++;
    }
    arcs = prims.filter((p) => p.kind === "arc");
    lines = prims.filter((p) => p.kind === "line");

    // direction of travel for each arc, from its dense run
    const arcDir = new Map();
    for (const a of arcs) {
      const ang = unwrapAngles(slice(dense, a.run[0], a.run[1]), a.center);
      arcDir.set(a, ang[ang.length - 1] > ang[0]);
    }

    // tangency
    const n = prims.length;
    const tangent = new Set();
    for (let q = 0; q < n; q++) {
      const a = prims[q], b = prims[(q + 1) % n];
      if (a.kind === "line" && b.kind === "arc" && makeTangent(a, b, P.tanTol * D)) tangent.add(q);
      else if (a.kind === "arc" && b.kind === "line" && makeTangent(b, a, P.tanTol * D)) tangent.add(q);
    }

    // 3g joins: ends[q] is the join between prim q and prim q+1, measured against their shared break point
    const far = P.joinFar * P.eps * D;
    const ends = [];
    for (let q = 0; q < n; q++) {
      const a = prims[q], b = prims[(q + 1) % n];
      const ref = dense[a.run[1]];
      let X = null;
      if (a.kind === "line" && b.kind === "line") X = intersectLines(a, b);
      else if (tangent.has(q)) {
        const [ln, ar] = a.kind === "line" ? [a, b] : [b, a];
        X = tangentPoint(ln, ar.center);
      } else if (a.kind === "line" || b.kind === "line") {
        const [ln, ar] = a.kind === "line" ? [a, b] : [b, a];
        X = nearest(intersectLineCircle(ln, ar.center, ar.r), ref);
      } else {
        X = circleTouchPoint(a.center, a.r, b.center, b.r, P.tanTol * D);
        if (!X) X = nearest(intersectCircles(a.center, a.r, b.center, b.r), ref);
      }
      if (X && dist(X, ref) <= far) ends.push([X, X, false]);
      else ends.push([project(a, ref), project(b, ref), true]);
    }

    let segs = [];
    for (let q = 0; q < n; q++) {
      const p = prims[q];
      const start = ends[mod(q - 1, n)][1], end = ends[q][0];
      p.p0 = start; p.p1 = end;
      if (p.kind === "line") segs.push({ kind: "line", p0: start, p1: end, theta: p.theta });
      else segs.push({ kind: "arc", p0: start, p1: end, center: p.center, r: p.r, sweepPos: arcDir.get(p) });
      if (ends[q][2] && dist(ends[q][1], ends[q][0]) > 1e-6) segs.push({ kind: "connector", p0: ends[q][0], p1: ends[q][1] });
    }
    segs = segs.filter((s) => s.kind === "arc" || dist(s.p1, s.p0) > 1e-6);
    const stats = {
      offAngle: lines.filter((l) => off.has(l)).length,
      distinctAngles: new Set(lines.map((l) => Math.round(l.theta * 1e6))).size,
      arcs: arcs.length, lines: lines.length,
    };
    return { segments: segs, lines, arcs, params: P, D, stats };
  }

  // ---------------------------------------------------------------- geometry out

  /** Closed polygon approximating the outline (arcs sampled every degStep degrees). */
  function samplePolygon(con, degStep = 3) {
    const out = [];
    for (const s of con.segments) {
      if (s.kind === "arc") {
        const a0 = Math.atan2(s.p0[1] - s.center[1], s.p0[0] - s.center[0]);
        const sw = arcSweep(s);
        const n = Math.max(2, Math.floor(Math.abs(sw * DEG) / degStep) + 1);
        for (let k = 0; k < n; k++) {
          const a = a0 + (sw * k) / n;
          out.push([s.center[0] + s.r * Math.cos(a), s.center[1] + s.r * Math.sin(a)]);
        }
      } else out.push(s.p0);
    }
    return out;
  }

  /** A number rounded half away from zero to nd decimals, in its shortest form, never "-0". */
  function fmt(v, nd = 1) {
    const f = 10 ** nd;
    const r = Math.sign(v) * Math.round(Math.abs(v) * f) / f;
    return String(r === 0 ? 0 : r);
  }

  /** "M L A Z" path. xf maps a point (for viewBox fitting); radii scale by xf's scale factor. */
  function svgPath(con, xf = (p) => p, nd = 1) {
    const segs = con.segments;
    if (!segs.length) return "";
    const scale = dist(xf([1, 0]), xf([0, 0]));
    const P = (p) => { const q = xf(p); return `${fmt(q[0], nd)} ${fmt(q[1], nd)}`; };
    const parts = [`M${P(segs[0].p0)}`];
    for (const s of segs) {
      if (s.kind === "arc") {
        const sw = arcSweep(s);
        const r = fmt(s.r * scale, nd);
        parts.push(`A${r} ${r} 0 ${Math.abs(sw) > Math.PI ? 1 : 0} ${sw > 0 ? 1 : 0} ${P(s.p1)}`);
      } else parts.push(`L${P(s.p1)}`);
    }
    parts.push("Z");
    return parts.join("");
  }

  /** Construction guides in drawing order: one line guide per collinear group (extended 15% D both ways), grouped by
   * angle; circles largest first, without duplicates. */
  function guides(con) {
    const grs = [];
    for (const s of con.segments) {
      if (s.kind !== "line") continue;
      const u = [Math.cos(s.theta / DEG), Math.sin(s.theta / DEG)], n = [-u[1], u[0]];
      const o = dot(n, s.p0);
      const g = grs.find((gr) => Math.abs(gr.theta - s.theta) < 1e-6 && Math.abs(gr.off - o) < 0.01 * con.D);
      if (g) g.t.push(dot(u, s.p0), dot(u, s.p1));
      else grs.push({ theta: s.theta, off: o, u, n, t: [dot(u, s.p0), dot(u, s.p1)] });
    }
    const ext = 0.15 * con.D;
    const r1 = (v) => Math.round(v * 10) / 10;
    const lines = grs.map((g) => {
      const t0 = Math.min(...g.t) - ext, t1 = Math.max(...g.t) + ext;
      const a = add(mul(g.n, g.off), mul(g.u, t0)), b = add(mul(g.n, g.off), mul(g.u, t1));
      return { theta: Math.round(g.theta * 1000) / 1000, x0: r1(a[0]), y0: r1(a[1]), x1: r1(b[0]), y1: r1(b[1]) };
    });
    lines.sort((a, b) => a.theta - b.theta || a.y0 - b.y0 || a.x0 - b.x0);
    const seen = new Set(), circles = [];
    for (const a of [...con.arcs].sort((x, y) => y.r - x.r)) {
      const c = { cx: r1(a.center[0]), cy: r1(a.center[1]), r: r1(a.r) };
      const key = `${c.cx},${c.cy},${c.r}`;
      if (!seen.has(key)) { seen.add(key); circles.push(c); }
    }
    return { lines, circles };
  }

  /** Transform that fits a bounding box [x0, y0, x1, y1] into a size x size square with pad (fraction) per side. */
  function fitTransform(bbox, size, pad = 0.08) {
    const [x0, y0, x1, y1] = bbox;
    const s = (size * (1 - 2 * pad)) / Math.max(x1 - x0, y1 - y0, 1e-9);
    const ox = (size - (x1 - x0) * s) / 2 - x0 * s, oy = (size - (y1 - y0) * s) / 2 - y0 * s;
    return { xf: (p) => [p[0] * s + ox, p[1] * s + oy], scale: s, ox, oy };
  }

  // ---------------------------------------------------------------- stage 5: rasterise and score

  /** Fill a closed polygon into a w x h Uint8Array (1 inside), nonzero rule, sampling pixel centres. One rasteriser
   * for every score, so Node and the browser agree. */
  function fillPolygon(poly, w, h) {
    const out = new Uint8Array(w * h);
    const n = poly.length;
    if (n < 3) return out;
    let ymin = Infinity, ymax = -Infinity;
    for (const p of poly) { if (p[1] < ymin) ymin = p[1]; if (p[1] > ymax) ymax = p[1]; }
    const r0 = Math.max(0, Math.ceil(ymin - 0.5)), r1 = Math.min(h - 1, Math.floor(ymax - 0.5));
    const xs = [];
    for (let y = r0; y <= r1; y++) {
      const yc = y + 0.5;
      xs.length = 0;
      for (let i = 0; i < n; i++) {
        const a = poly[i], b = poly[(i + 1) % n];
        if ((a[1] <= yc && b[1] > yc) || (b[1] <= yc && a[1] > yc)) {
          xs.push([a[0] + ((yc - a[1]) * (b[0] - a[0])) / (b[1] - a[1]), b[1] > a[1] ? 1 : -1]);
        }
      }
      xs.sort((p, q) => p[0] - q[0]);
      let wind = 0;
      for (let k = 0; k < xs.length; k++) {
        if (wind !== 0) {
          const xa = Math.max(0, Math.ceil(xs[k - 1][0] - 0.5)), xb = Math.min(w - 1, Math.floor(xs[k][0] - 0.5));
          if (xb >= xa) out.fill(1, y * w + xa, y * w + xb + 1);
        }
        wind += xs[k][1];
      }
    }
    return out;
  }

  function iou(a, b) {
    let inter = 0, uni = 0;
    for (let i = 0; i < a.length; i++) {
      const x = a[i] > 0, y = b[i] > 0;
      if (x && y) inter++;
      if (x || y) uni++;
    }
    return uni ? inter / uni : 0;
  }

  /** Summed-area table (side+1)^2 of the side x side window at (ox, oy); outside the image counts as 0. */
  function integral(m, w, h, ox, oy, side) {
    const S = side + 1;
    const I = new Float64Array(S * S);
    for (let y = 0; y < side; y++) {
      let row = 0;
      const sy = y + oy;
      for (let x = 0; x < side; x++) {
        const sx = x + ox;
        if (sy >= 0 && sy < h && sx >= 0 && sx < w && m[sy * w + sx]) row++;
        I[(y + 1) * S + x + 1] = I[y * S + x + 1] + row;
      }
    }
    return I;
  }

  /** Area downsample to s x s from an integral image (fractional box edges by bilinear lookup), threshold 0.5. */
  function areaDown(I, side, s) {
    const S = side + 1;
    const at = (x, y) => {
      const xi = Math.min(Math.floor(x), side - 1), yi = Math.min(Math.floor(y), side - 1);
      const fx = x - xi, fy = y - yi;
      const a = I[yi * S + xi], b = I[yi * S + xi + 1], c = I[(yi + 1) * S + xi], d = I[(yi + 1) * S + xi + 1];
      return a * (1 - fx) * (1 - fy) + b * fx * (1 - fy) + c * (1 - fx) * fy + d * fx * fy;
    };
    const out = new Uint8Array(s * s), f = side / s;
    for (let y = 0; y < s; y++) for (let x = 0; x < s; x++) {
      const xa = x * f, xb = (x + 1) * f, ya = y * f, yb = (y + 1) * f;
      out[y * s + x] = (at(xb, yb) - at(xa, yb) - at(xb, ya) + at(xa, ya)) / (f * f) >= 0.5 ? 1 : 0;
    }
    return out;
  }

  /** Mean IoU of mark and mask after both are area-downsampled to each size and thresholded at 50%. The window is
   * a square around the mask with 10% padding per side, as in LogoForge's score.legibility. */
  function legibility(mark, mask, w, h, sizes = [16, 32]) {
    let x0 = w, x1 = -1, y0 = h, y1 = -1;
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) if (mask[y * w + x]) {
      if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y;
    }
    if (x1 < 0) return 0;
    const side = Math.floor(Math.max(x1 - x0, y1 - y0) * 1.2) + 1;
    const ox = Math.floor((x0 + x1) / 2) - Math.floor(side / 2), oy = Math.floor((y0 + y1) / 2) - Math.floor(side / 2);
    const A = integral(mark, w, h, ox, oy, side), B = integral(mask, w, h, ox, oy, side);
    let total = 0;
    for (const s of sizes) total += iou(areaDown(A, side, s), areaDown(B, side, s));
    return total / sizes.length;
  }

  const WEIGHTS = { legibility: 0.5, nodes: 0.006, connectors: 0.02, distinctAngles: 0.02, offAngle: 0.01, arcs: 0.02 };

  function scoreOf(v) {
    const w = WEIGHTS;
    return v.iou + w.legibility * v.legibility - w.nodes * v.nodes - w.connectors * v.connectors
      - w.distinctAngles * v.distinctAngles - w.offAngle * v.offAngle + w.arcs * Math.min(v.arcs || 0, 3);
  }

  /** The 3h guard: IoU at least 0.5, at most 40 segments, connectors at most 20% of them. */
  const guardOk = (v) => v.iou >= 0.5 && v.nodes <= 40 && v.connectors <= 0.2 * v.nodes;

  function paretoFront(vs) {
    const dominates = (b, a) =>
      b.iou >= a.iou && b.legibility >= a.legibility && b.nodes <= a.nodes &&
      (b.iou > a.iou || b.legibility > a.legibility || b.nodes < a.nodes);
    return vs.filter((a) => !vs.some((b) => b !== a && dominates(b, a)));
  }

  /** Three picks: the best Pareto-front members that differ from every earlier pick in angle set or eps, then the
   * rest by the same rule, then repeats as a last resort. Ordered by score, then eps, then angle set. */
  function pickTop3(vs) {
    const ok = vs.filter(guardOk);
    if (!ok.length) return [];
    const order = (a, b) => scoreOf(b) - scoreOf(a) || a.eps - b.eps || String(a.angles).localeCompare(String(b.angles));
    const front = paretoFront(ok).sort(order);
    const rest = ok.filter((v) => !front.includes(v)).sort(order);
    const picks = [];
    for (const pool of [front, rest]) for (const v of pool) {
      if (picks.length === 3) break;
      if (picks.every((p) => v.angles !== p.angles || v.eps !== p.eps)) picks.push(v);
    }
    for (const v of [...front, ...rest]) {
      if (picks.length === 3) break;
      if (!picks.includes(v)) picks.push(v);
    }
    return picks;
  }

  // ---------------------------------------------------------------- the whole grid

  const EPS_LIST = [0.006, 0.01, 0.015, 0.022, 0.03];
  const ANGLE_LIST = ["45", "30", "15", "free"];
  const round4 = (x) => Math.round(x * 1e4) / 1e4;

  /** Every variant of the grid (5 eps x 4 angle sets) for one mask, and the indices of the three picks.
   * contour: the traced outer contour (LogoMask.traceContour). mask: w x h Uint8Array of 0 and 1, also the RANSAC
   * seed. onProgress(done, total) is called after each variant. */
  function buildVariants(contour, mask, w, h, opts = {}) {
    const epsList = opts.eps || EPS_LIST, angleList = opts.angles || ANGLE_LIST;
    const dense = denseContour(contour);
    const bb = bounds(dense);
    const D = Math.hypot(bb[2] - bb[0], bb[3] - bb[1]);
    const seed = fnv1a(mask);
    const out = [];
    const total = epsList.length * angleList.length;
    epsList.forEach((eps, ei) => angleList.forEach((angles, ai) => {
      const v = { variant: `e${eps}-a${angles}`, eps, angles };
      try {
        const brk = rdpClosed(dense, eps * D);
        const con = construct(dense, brk, { eps, angles }, makeRng(seed, ei + 1, ai + 1));
        const mk = fillPolygon(samplePolygon(con), w, h);
        Object.assign(v, {
          iou: round4(iou(mk, mask)), legibility: round4(legibility(mk, mask, w, h)),
          nodes: con.segments.length, connectors: con.segments.filter((s) => s.kind === "connector").length,
          offAngle: con.stats.offAngle, distinctAngles: con.stats.distinctAngles, arcs: con.stats.arcs, con,
        });
      } catch (e) {
        Object.assign(v, { iou: 0, legibility: 0, nodes: 999, connectors: 0, offAngle: 0, distinctAngles: 0, arcs: 0,
          error: String((e && e.message) || e).slice(0, 80) });
      }
      v.score = round4(scoreOf(v));
      out.push(v);
      if (opts.onProgress) opts.onProgress(out.length, total);
    }));
    return { variants: out, picks: pickTop3(out).map((p) => out.indexOf(p)), D };
  }

  /** Plain, cloneable summary of one variant for the page: scores, SVG path, bounding box and guides. */
  function summarise(v) {
    const s = { variant: v.variant, eps: v.eps, angles: v.angles, iou: v.iou, legibility: v.legibility,
      nodes: v.nodes, connectors: v.connectors, arcs: v.arcs, score: v.score, ok: guardOk(v) };
    if (v.con) {
      s.path = svgPath(v.con);
      s.bbox = bounds(samplePolygon(v.con));
      s.guides = guides(v.con);
    }
    return s;
  }

  root.LogoGeometry = {
    fnv1a, makeRng, angDist, snapAngle, axialMean, clusterAngles, fitLineTLS, fitCircleKasa, circleFrom3,
    fitCircleRansac, circleRms, sweepDeg, turningConsistent, makeLine, makeArc, lineN, mergeConcentric, makeTangent,
    circleTouchPoint, tangentPoint, intersectLines, intersectLineCircle, intersectCircles, resample, smooth,
    denseContour, rdpClosed, construct, arcSweep, samplePolygon, fmt, svgPath, guides, fitTransform, bounds,
    fillPolygon, iou, legibility, scoreOf, guardOk, paretoFront, pickTop3, buildVariants, summarise,
    ANGLE_SETS, PARAMS, EPS_LIST, ANGLE_LIST,
  };
})(typeof self !== "undefined" ? self : globalThis);
