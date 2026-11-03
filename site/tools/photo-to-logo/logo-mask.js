/* Photo to logo: the subject mask. Cutout alpha, plain-background photos, clean-up and contour tracing.
 *
 * Pure functions on typed arrays, no DOM. Runs in logo-worker.js and under Node for tests. Masks are w x h Uint8Arrays
 * of 0 and 1. Design: docs/designs/photo-to-logo.md (stage 1 replaces LogoForge's Apple Vision mask). Box GrabCut was
 * built and measured for opaque photos and left out: see the design's "Where the subject mask comes from".
 */
(function (root) {
  "use strict";

  // ---------------------------------------------------------------- cutouts

  /** A cutout has some see-through pixels (alpha < 16 on at least 0.5% of the image) and a solid subject (alpha >= 128
   * on at least 1%). Returns { cutout, mask } where mask is alpha >= 128. */
  function alphaMask(rgba, w, h) {
    const n = w * h, mask = new Uint8Array(n);
    let clear = 0, solid = 0;
    for (let i = 0; i < n; i++) {
      const a = rgba[4 * i + 3];
      if (a < 16) clear++;
      if (a >= 128) { solid++; mask[i] = 1; }
    }
    return { cutout: clear >= 0.005 * n && solid >= 0.01 * n, mask };
  }

  /** A photo on a plain background (a product shot on white, a drawing, a silhouette): at least 90% of the border
   * pixels lie within 30 (RGB distance) of the border's median colour. The background is everything 4-connected to the
   * border within 40 of that colour; the rest is the subject. Returns { plain, mask }. */
  function plainBackground(rgba, w, h) {
    const border = [];
    for (let x = 0; x < w; x++) border.push(x, (h - 1) * w + x);
    for (let y = 1; y < h - 1; y++) border.push(y * w, y * w + w - 1);
    const med = [0, 1, 2].map((c) => {
      const v = border.map((p) => rgba[4 * p + c]).sort((a, b) => a - b);
      return v[v.length >> 1];
    });
    const far = (p, t) => {
      const r = rgba[4 * p] - med[0], g = rgba[4 * p + 1] - med[1], b = rgba[4 * p + 2] - med[2];
      return r * r + g * g + b * b > t * t;
    };
    let near = 0;
    for (const p of border) if (!far(p, 30)) near++;
    const mask = new Uint8Array(w * h);
    if (near < 0.9 * border.length) return { plain: false, mask };
    const bg = new Uint8Array(w * h), stack = new Int32Array(w * h);
    let top = 0;
    const seed = (p) => { if (!bg[p] && !far(p, 40)) { bg[p] = 1; stack[top++] = p; } };
    for (const p of border) seed(p);
    while (top) {
      const p = stack[--top], x = p % w, y = (p - x) / w;
      if (x > 0) seed(p - 1);
      if (x < w - 1) seed(p + 1);
      if (y > 0) seed(p - w);
      if (y < h - 1) seed(p + w);
    }
    for (let i = 0; i < mask.length; i++) mask[i] = bg[i] ? 0 : 1;
    return { plain: true, mask };
  }

  // ---------------------------------------------------------------- components and holes

  /** Label 8-connected components of a mask. Returns { labels (Int32Array, 0 = background), areas (index = label) }. */
  function components(mask, w, h) {
    const labels = new Int32Array(w * h), areas = [0];
    const stack = new Int32Array(w * h);
    let next = 0;
    for (let s = 0; s < w * h; s++) {
      if (!mask[s] || labels[s]) continue;
      next++;
      let top = 0, area = 0;
      stack[top++] = s; labels[s] = next;
      while (top) {
        const p = stack[--top];
        area++;
        const x = p % w, y = (p - x) / w;
        for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
          const nx = x + dx, ny = y + dy;
          if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
          const q = ny * w + nx;
          if (mask[q] && !labels[q]) { labels[q] = next; stack[top++] = q; }
        }
      }
      areas.push(area);
    }
    return { labels, areas };
  }

  /** The largest 8-connected component, and the area of the next largest as a fraction of it. */
  function largestComponent(mask, w, h) {
    const { labels, areas } = components(mask, w, h);
    let best = 0;
    for (let i = 1; i < areas.length; i++) if (areas[i] > areas[best]) best = i;
    const out = new Uint8Array(w * h);
    if (!best) return { mask: out, area: 0, second: 0 };
    let second = 0;
    for (let i = 1; i < areas.length; i++) if (i !== best && areas[i] > second) second = areas[i];
    for (let i = 0; i < out.length; i++) out[i] = labels[i] === best ? 1 : 0;
    return { mask: out, area: areas[best], second: second / areas[best] };
  }

  /** Fill holes: every background pixel not 4-connected to the image border becomes subject. */
  function fillHoles(mask, w, h) {
    const outside = new Uint8Array(w * h), stack = new Int32Array(w * h);
    let top = 0;
    const seed = (p) => { if (!mask[p] && !outside[p]) { outside[p] = 1; stack[top++] = p; } };
    for (let x = 0; x < w; x++) { seed(x); seed((h - 1) * w + x); }
    for (let y = 0; y < h; y++) { seed(y * w); seed(y * w + w - 1); }
    while (top) {
      const p = stack[--top], x = p % w, y = (p - x) / w;
      if (x > 0) seed(p - 1);
      if (x < w - 1) seed(p + 1);
      if (y > 0) seed(p - w);
      if (y < h - 1) seed(p + w);
    }
    const out = new Uint8Array(w * h);
    for (let i = 0; i < out.length; i++) out[i] = outside[i] ? 0 : 1;
    return out;
  }

  // ---------------------------------------------------------------- morphology by distance transform

  /** Exact squared Euclidean distance from every pixel to the nearest pixel where src[i] === value
   * (Felzenszwalb and Huttenlocher). Pixels outside the image never count as a match. */
  function sqDistTo(src, w, h, value) {
    const INF = 1e20;
    const f = new Float64Array(Math.max(w, h)), d = new Float64Array(Math.max(w, h));
    const v = new Int32Array(Math.max(w, h)), z = new Float64Array(Math.max(w, h) + 1);
    const out = new Float64Array(w * h);
    const dt1 = (n) => {
      let k = 0;
      v[0] = 0; z[0] = -INF; z[1] = INF;
      for (let q = 1; q < n; q++) {
        let s = ((f[q] + q * q) - (f[v[k]] + v[k] * v[k])) / (2 * q - 2 * v[k]);
        while (s <= z[k]) { k--; s = ((f[q] + q * q) - (f[v[k]] + v[k] * v[k])) / (2 * q - 2 * v[k]); }
        k++; v[k] = q; z[k] = s; z[k + 1] = INF;
      }
      k = 0;
      for (let q = 0; q < n; q++) { while (z[k + 1] < q) k++; d[q] = (q - v[k]) * (q - v[k]) + f[v[k]]; }
    };
    for (let x = 0; x < w; x++) {
      for (let y = 0; y < h; y++) f[y] = src[y * w + x] === value ? 0 : INF;
      dt1(h);
      for (let y = 0; y < h; y++) out[y * w + x] = d[y];
    }
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) f[x] = out[y * w + x];
      dt1(w);
      for (let x = 0; x < w; x++) out[y * w + x] = d[x];
    }
    return out;
  }

  /** Dilate with a disc of radius r: every pixel within r of the subject. */
  function dilate(mask, w, h, r) {
    const d = sqDistTo(mask, w, h, 1), out = new Uint8Array(w * h);
    for (let i = 0; i < out.length; i++) out[i] = d[i] <= r * r ? 1 : 0;
    return out;
  }

  /** Erode with a disc of radius r: every subject pixel further than r from the background. */
  function erode(mask, w, h, r) {
    const d = sqDistTo(mask, w, h, 0), out = new Uint8Array(w * h);
    for (let i = 0; i < out.length; i++) out[i] = d[i] > r * r ? 1 : 0;
    return out;
  }

  /** LogoForge's clean_mask at working size: largest component, holes filled, closed then opened with a disc of
   * radius 0.4% of the image diagonal, then the largest component again. Returns { mask, area, dropped } where dropped
   * is the second-largest piece's area as a fraction of the kept one (0 when there was only one). */
  function cleanMask(raw, w, h) {
    const first = largestComponent(raw, w, h);
    if (!first.area) return { mask: first.mask, area: 0, dropped: 0 };
    const r = Math.max(1, Math.round(0.004 * Math.hypot(w, h)));
    let m = fillHoles(first.mask, w, h);
    m = erode(dilate(m, w, h, r), w, h, r);
    m = dilate(erode(m, w, h, r), w, h, r);
    const last = largestComponent(m, w, h);
    return { mask: fillHoles(last.mask, w, h), area: last.area, dropped: first.second };
  }

  // ---------------------------------------------------------------- contour

  // clockwise on screen (y down): E, SE, S, SW, W, NW, N, NE
  const DX = [1, 1, 0, -1, -1, -1, 0, 1], DY = [0, 1, 1, 1, 0, -1, -1, -1];

  /** Outer boundary of the component containing the first subject pixel in raster order, by Moore-neighbour tracing
   * with Jacob's stopping rule. Returns [[x, y], ...] pixel coordinates in drawing order (no repeated end point). */
  function traceContour(mask, w, h) {
    let s = -1;
    for (let i = 0; i < w * h; i++) if (mask[i]) { s = i; break; }
    if (s < 0) return [];
    const at = (x, y) => x >= 0 && y >= 0 && x < w && y < h && mask[y * w + x] === 1;
    const dirOf = (dx, dy) => { for (let k = 0; k < 8; k++) if (DX[k] === dx && DY[k] === dy) return k; return 4; };
    const sx = s % w, sy = (s - sx) / w;
    const pts = [[sx, sy]];
    // the backtrack is the last background pixel looked at; west of the start is background (raster order)
    let x = sx, y = sy, back = 4, firstDir = -1;
    for (let step = 0, limit = 4 * w * h + 8; step < limit; step++) {
      let found = -1;
      for (let k = 1; k <= 8; k++) {
        const d = (back + k) % 8;
        if (at(x + DX[d], y + DY[d])) { found = d; break; }
      }
      if (found < 0) return pts;                      // a single pixel
      if (x === sx && y === sy) {
        if (firstDir < 0) firstDir = found;
        else if (found === firstDir) { pts.pop(); break; }   // Jacob's rule: back at the start, leaving the same way
      }
      const pd = (found + 7) % 8;                     // the background pixel checked just before the one found
      const bx = x + DX[pd], by = y + DY[pd];
      x += DX[found]; y += DY[found];
      back = dirOf(bx - x, by - y);
      pts.push([x, y]);
    }
    return pts;
  }

  root.LogoMask = {
    alphaMask, components, largestComponent, fillHoles, sqDistTo, dilate, erode, cleanMask, traceContour,
    plainBackground,
  };
})(typeof self !== "undefined" ? self : globalThis);
