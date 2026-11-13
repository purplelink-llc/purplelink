// Publication-workflow hero: a manuscript passes five stations (review, coherence,
// citations, revision, response). three.js is self-hosted and loaded by dynamic import
// only after the capability checks pass. The poster image stays until the first frame.
// Stills: ?wf-still=<review|coherence|citations|revision|response|hero> or renderStill().

const THREE_URL = '/assets/vendor/three/three.module.min.js';
const NAMES = ['review', 'coherence', 'citations', 'revision', 'response'];
const SP = 2.45;
const ST_X = [-2 * SP, -SP, 0, SP, 2 * SP];
const PERIOD = 14;
const X0 = -7.2;
const X1 = 7.2;
const PW = 1.2;
const PH = 1.65;

const sm = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
const lerp = (a, b, t) => a + (b - a) * t;

// ---------- colour: read CSS custom properties (OKLCH) ----------
function oklchToLinear(L, C, h) {
  const a = C * Math.cos(h * Math.PI / 180), b = C * Math.sin(h * Math.PI / 180);
  const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3;
  const c = (v) => Math.min(1, Math.max(0, v));
  return [c(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
    c(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
    c(-0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)];
}
const srgbToLinear = (v) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
function parseCssColor(str, fallback) {
  str = (str || '').trim();
  let m = str.match(/oklch\(\s*([\d.]+)(%?)\s+([\d.]+)\s+([\d.]+)/i);
  if (m) return oklchToLinear(m[2] ? +m[1] / 100 : +m[1], +m[3], +m[4]);
  m = str.match(/rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)/i);
  if (m) return [srgbToLinear(m[1] / 255), srgbToLinear(m[2] / 255), srgbToLinear(m[3] / 255)];
  m = str.match(/^#([0-9a-f]{6})$/i);
  if (m) { const n = parseInt(m[1], 16); return [srgbToLinear((n >> 16) / 255), srgbToLinear(((n >> 8) & 255) / 255), srgbToLinear((n & 255) / 255)]; }
  return fallback;
}
function readPalette() {
  const cs = getComputedStyle(document.documentElement);
  const v = (n) => cs.getPropertyValue(n);
  const light = document.documentElement.getAttribute('data-theme') === 'light';
  const bg = parseCssColor(v('--bg'), light ? [0.95, 0.94, 0.96] : [0.012, 0.008, 0.016]);
  const ink = parseCssColor(v('--ink'), light ? [0.005, 0.002, 0.012] : [0.85, 0.83, 0.87]);
  const purple = parseCssColor(v('--purple'), light ? [0.35, 0.05, 0.6] : [0.55, 0.3, 0.75]);
  const line = parseCssColor(v('--line'), light ? [0.7, 0.65, 0.75] : [0.04, 0.03, 0.06]);
  const muted = parseCssColor(v('--muted'), [0.3, 0.28, 0.33]);
  return { bg, ink, purple, line, muted, light };
}
const mix = (a, b, t) => [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];

function roleColor(role, p) {
  const white = [1, 1, 1];
  const paper = p.light ? mix(p.bg, white, 0.8) : mix(p.bg, p.ink, 0.1);
  switch (role) {
    case 'paper': return paper;
    case 'paper2': return mix(paper, p.bg, 0.3);
    case 'paper3': return mix(paper, p.bg, 0.5);
    case 'edge': return mix(p.bg, p.ink, p.light ? 0.55 : 0.4);
    case 'text': return mix(paper, p.ink, p.light ? 0.34 : 0.3);
    case 'accent': return p.purple;
    case 'accent2': return mix(p.purple, p.bg, 0.35);
    case 'muted': return mix(p.bg, p.muted, 0.8);
    case 'rail': return mix(p.bg, p.ink, p.light ? 0.16 : 0.2);
    default: return p.ink;
  }
}

// ---------- scene ----------
function buildScene(THREE) {
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(26, 16 / 9, 0.1, 100);
  const reg = [];
  const geos = [];
  const pageRot = new THREE.Euler(0.05, -0.5, 0);

  const unit = new THREE.PlaneGeometry(1, 1);
  const circ = new THREE.CircleGeometry(1, 20);
  const torus = new THREE.TorusGeometry(1, 0.14, 6, 36);
  const sheetGeo = new THREE.PlaneGeometry(PW, PH);
  geos.push(unit, circ, torus, sheetGeo);

  const fill = (role, op, fade, order) => {
    const m = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: op, depthWrite: false, side: THREE.DoubleSide });
    reg.push({ m, role, base: op, fade, k: 1 });
    return { m, e: reg[reg.length - 1], order };
  };
  const lineMat = (role, op, fade) => {
    const m = new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: op, depthWrite: false });
    reg.push({ m, role, base: op, fade, k: 1 });
    return reg[reg.length - 1];
  };
  const mesh = (geo, mm, order, parent) => {
    const o = new THREE.Mesh(geo, mm.m);
    o.renderOrder = order;
    (parent || scene).add(o);
    return o;
  };
  const rectLine = (w, h, me, order, parent) => {
    const g = new THREE.BufferGeometry().setFromPoints([[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]].map(([x, y]) => new THREE.Vector3(x, y, 0)));
    geos.push(g);
    const l = new THREE.LineLoop(g, me.m);
    l.renderOrder = order;
    (parent || scene).add(l);
    return l;
  };

  // page text lines: x from left margin, widths as fraction of block
  const LINE_W = [0.9, 1, 0.82, 1, 0.95, 0.6, 1, 0.7];
  const lineY = (i) => PH * (0.3 - i * 0.1);
  const L0 = -PW * 0.38;
  const BW = PW * 0.76;
  function addLines(parent, base, tm, am) {
    const head = mesh(unit, am, base + 1, parent);
    head.scale.set(BW * 0.5, 0.042, 1); head.position.set(L0 + BW * 0.25, PH * 0.4, 0.004);
    LINE_W.forEach((w, i) => {
      const o = mesh(unit, tm, base + 1, parent);
      o.scale.set(BW * w, 0.022, 1);
      o.position.set(L0 + (BW * w) / 2, lineY(i), 0.004);
    });
  }

  // --- manuscript ---
  const page = new THREE.Group();
  scene.add(page);
  const sheetPaper = fill('paper', 0.96, true);
  const sheetEdge = lineMat('edge', 0.8, true);
  const txt = fill('text', 0.55, true);
  const acc = fill('accent', 0.7, true);
  [[0.06, -0.05, -0.1, 0.035], [-0.035, -0.025, -0.05, -0.02]].forEach(([x, y, z, r], i) => {
    const g = new THREE.Group();
    g.position.set(x, y, z); g.rotation.z = r;
    page.add(g);
    mesh(sheetGeo, sheetPaper, 10 + i, g);
    rectLine(PW, PH, sheetEdge, 10 + i, g);
  });
  const front = new THREE.Group();
  page.add(front);
  mesh(sheetGeo, sheetPaper, 12, front);
  rectLine(PW, PH, sheetEdge, 12, front);
  addLines(front, 12, txt, acc);

  // coherence dots on the page (anchored to local points)
  const cohLocal = [[PW * 0.2, lineY(1)], [-PW * 0.15, lineY(4)], [PW * 0.18, lineY(6)]];
  const dotMat = fill('accent', 0.9, true);
  const cohDots = cohLocal.map(([x, y]) => { const d = mesh(circ, dotMat, 15, front); d.scale.setScalar(0.04); d.position.set(x, y, 0.01); return d; });

  // --- rail + pips ---
  const rail = fill('rail', 0.7, false);
  const railMesh = mesh(unit, rail, 1, scene);
  railMesh.scale.set(14.4, 0.012, 1); railMesh.position.set(0, -1.75, 0);
  const pipMats = [];
  ST_X.forEach((sx, i) => {
    const pm = fill('accent', 0.9, false);
    pipMats.push(pm.e);
    const group = [];
    for (let k = 0; k <= i; k++) {
      const d = mesh(circ, pm, 2, scene);
      d.scale.setScalar(0.045); d.position.set(sx + (k - i / 2) * 0.17, -2.0, 0);
      group.push(d);
    }
  });
  // station ticks on the rail
  const tickMat = fill('muted', 0.7, false);
  ST_X.forEach((sx) => { const t = mesh(unit, tickMat, 1, scene); t.scale.set(0.012, 0.16, 1); t.position.set(sx, -1.75, 0); });

  // --- 1 review: ring of seven lenses ---
  const ringG = new THREE.Group();
  ringG.position.set(ST_X[0], 0, 0); ringG.rotation.copy(pageRot);
  scene.add(ringG);
  const guide = new THREE.BufferGeometry().setFromPoints(Array.from({ length: 65 }, (_, i) => new THREE.Vector3(Math.cos(i / 64 * Math.PI * 2) * 1.2, Math.sin(i / 64 * Math.PI * 2) * 1.2, 0)));
  geos.push(guide);
  const guideMat = lineMat('rail', 0.5, false);
  const guideLine = new THREE.Line(guide, guideMat.m); guideLine.renderOrder = 2; ringG.add(guideLine);
  const lenses = [];
  for (let i = 0; i < 7; i++) {
    const lg = new THREE.Group(); ringG.add(lg);
    const rm = fill('accent', 1, false);
    const dm = fill('accent2', 1, false);
    const r = mesh(torus, rm, 3, lg); r.scale.setScalar(0.13);
    const d = mesh(circ, dm, 3, lg); d.scale.setScalar(0.04);
    lenses.push({ g: lg, rm: rm.e, dm: dm.e });
  }

  // idle slots: faint page outlines where the manuscript will stop
  const slotMat = lineMat('rail', 0.55, false);
  const slots = [0, 1, 2].map((i) => {
    const g = new THREE.Group(); g.rotation.copy(pageRot); scene.add(g);
    rectLine(PW, PH, slotMat, 1, g); return g;
  });

  // --- 2 coherence: arcs between page sections ---
  const NA = 24;
  const arcs = [[0, 1], [1, 2], [0, 2]].map(([a, b], i) => {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(NA * 3), 3));
    geos.push(g);
    const me = lineMat('accent', 0.85, false);
    const l = new THREE.Line(g, me.m); l.renderOrder = 14; l.frustumCulled = false; scene.add(l);
    return { a, b, g, me, bulge: 0.38 + i * 0.1 };
  });

  // --- 3 citations: reference cards ---
  const CARD = [[-0.92, 0.62, 0.0, 0.05], [-0.92, -0.5, 0.0, -0.04], [0.92, 0.3, 0, -0.03], [0.92, -0.72, 0, 0.05]];
  const CONN_ANCHOR = [[-PW * 0.38, lineY(1)], [-PW * 0.38, lineY(5)], [PW * 0.38, lineY(2)], [PW * 0.38, lineY(6)]];
  const cards = CARD.map(([x, y, , r], i) => {
    const g = new THREE.Group();
    g.position.set(ST_X[2] + x, y, 0.35); g.rotation.set(pageRot.x, pageRot.y, r);
    scene.add(g);
    const pm = fill('paper', 0.96, false), tm = fill('text', 0.55, false), am = fill('accent', 0.9, false), em = lineMat('edge', 0.8, false);
    mesh(unit, pm, 20, g).scale.set(0.46, 0.3, 1);
    rectLine(0.46, 0.3, em, 20, g);
    const l1 = mesh(unit, tm, 21, g); l1.scale.set(0.3, 0.02, 1); l1.position.set(0.02, 0.02, 0.003);
    const l2 = mesh(unit, tm, 21, g); l2.scale.set(0.22, 0.02, 1); l2.position.set(-0.02, -0.05, 0.003);
    const dot = mesh(circ, am, 21, g); dot.scale.setScalar(0.025); dot.position.set(-0.18, 0.09, 0.003);
    const cg = new THREE.BufferGeometry();
    cg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(6), 3));
    geos.push(cg);
    const cm = lineMat('accent', 0.8, false);
    const cl = new THREE.Line(cg, cm.m); cl.renderOrder = 19; cl.frustumCulled = false; scene.add(cl);
    return { g, pm: pm.e, tm: tm.e, am: am.e, em, cg, cm, i };
  });

  // --- 4 revision: second sheet slides over, marked changes ---
  const rev = new THREE.Group();
  page.add(rev);
  const revPaper = fill('paper', 0.97, true), revEdge = lineMat('accent', 0.9, true);
  mesh(sheetGeo, revPaper, 16, rev);
  rectLine(PW, PH, revEdge, 16, rev);
  const revTxt = fill('text', 0.55, true), revAcc = fill('accent', 0.75, true);
  addLines(rev, 16, revTxt, revAcc);
  [[1, 0.5, 0.0], [4, 0.45, 0.3], [5, 0.3, 0.1]].forEach(([li, w, off]) => {
    const o = mesh(unit, revAcc, 18, rev);
    o.scale.set(BW * w, 0.034, 1);
    o.position.set(L0 + BW * (off + w / 2), lineY(li), 0.006);
  });
  const strike = mesh(unit, revTxt, 18, rev);
  strike.scale.set(BW * 0.5, 0.008, 1); strike.position.set(L0 + BW * 0.5 + BW * 0.1, lineY(3), 0.006);
  // idle ghost of the incoming sheet at the station
  const ghostEdge = lineMat('accent', 0.25, false);
  const ghost = new THREE.Group(); ghost.position.set(ST_X[3] + 0.9, 0.05, 0.2); ghost.rotation.copy(pageRot); scene.add(ghost);
  rectLine(PW, PH, ghostEdge, 16, ghost);
  const ghostLines = fill('accent', 0.2, false);
  [0, 3, 5].forEach((li) => { const o = mesh(unit, ghostLines, 16, ghost); o.scale.set(BW * 0.4, 0.03, 1); o.position.set(L0 + BW * 0.2, lineY(li), 0.002); });

  // --- 5 response: accordion letter, behind the page ---
  const PWL = 0.42, PHL = PH * 0.84;
  const letter = new THREE.Group();
  letter.rotation.copy(pageRot);
  scene.add(letter);
    const lm = [fill('paper', 0.96, false), fill('paper2', 0.96, false), fill('paper', 0.96, false)];
  const le = lineMat('edge', 0.7, false);
  const lt = fill('text', 0.5, false), la = fill('accent', 0.7, false);
  const hinges = [];
  let parent = letter;
  for (let k = 0; k < 3; k++) {
    const h = new THREE.Group();
    if (k > 0) h.position.set(PWL, 0, 0);
    parent.add(h);
    const p = mesh(unit, lm[k], 5, h); p.scale.set(PWL, PHL, 1); p.position.set(PWL / 2, 0, 0);
    const eg = rectLine(PWL, PHL, le, 5, h); eg.position.set(PWL / 2, 0, 0);
    if (k === 0) { const g = mesh(unit, la, 6, h); g.scale.set(0.2, 0.034, 1); g.position.set(PWL * 0.5, PHL * 0.32, 0.003); }
    for (let i = 0; i < 6; i++) { const o = mesh(unit, lt, 6, h); const w = [0.3, 0.3, 0.24, 0.3, 0.3, 0.14][i]; o.scale.set(w, 0.02, 1); o.position.set(PWL * 0.5 + (w - 0.3) / -2 - 0.0, PHL * (0.2 - i * 0.11), 0.003); }
    hinges.push(h);
    parent = h;
  }

  // ---------- update ----------
  const v = new THREE.Vector3();
  const w1 = new THREE.Vector3();
  const anchorW = (lx, ly, lz, cx) => v.set(lx, ly, lz).applyEuler(pageRot).add(w1.set(cx, 0, 0));
  const A = new THREE.Vector3(), B = new THREE.Vector3(), C = new THREE.Vector3();

  function pose(mx, ts, cam) {
    const fade = 1 - sm(5.9, 7.2, Math.abs(mx));
    page.position.set(mx, Math.sin(ts * 0.6) * 0.04, 0);
    page.rotation.copy(pageRot);
    const dAll = ST_X.map((sx) => mx - sx);
    const act = dAll.map((d) => 1 - sm(0.6, 1.7, Math.abs(d)));
    const cen = dAll.map((d, i) => ST_X[i] + d * (1 - sm(1.2, 2.6, Math.abs(d))));

    // pips
    pipMats.forEach((e, i) => { e.k = 0.3 + 0.7 * act[i]; });
    // 1 review
    const a0 = act[0], spin = ts * 0.12;
    lenses.forEach((L, i) => {
      const ang = (i / 7) * Math.PI * 2 + spin + (1 - a0) * 0.6;
      L.g.position.set(Math.cos(ang) * 1.2, Math.sin(ang) * 1.2, 0);
      const k = sm(0, 1, a0 * 1.6 - i * 0.1);
      L.g.scale.setScalar(0.78 + 0.22 * k);
      L.rm.k = 0.3 + 0.7 * k; L.dm.k = 0.3 + 0.7 * k;
    });
    guideMat.k = 0.6 + 0.8 * a0;
    ringG.position.x = cen[0];
    slots.forEach((g, i) => g.position.set(ST_X[i], 0, 0));
    slotMat.k = 1 - Math.max(act[0], act[1], act[2]);
    // 2 coherence
    const a1 = act[1], c1 = cen[1];
    const pts = cohLocal.map(([x, y]) => anchorW(x, y, 0.01, c1).clone());
    arcs.forEach((r, i) => {
      A.copy(pts[r.a]); B.copy(pts[r.b]);
      const arr = r.g.attributes.position.array;
      const mid = C.copy(A).add(B).multiplyScalar(0.5);
      mid.z += r.bulge; mid.x += (i === 2 ? 0.45 : -0.15);
      for (let k = 0; k < NA; k++) {
        const t = k / (NA - 1), u = 1 - t;
        arr[k * 3] = u * u * A.x + 2 * u * t * mid.x + t * t * B.x;
        arr[k * 3 + 1] = u * u * A.y + 2 * u * t * mid.y + t * t * B.y;
        arr[k * 3 + 2] = u * u * A.z + 2 * u * t * mid.z + t * t * B.z;
      }
      r.g.attributes.position.needsUpdate = true;
      r.me.k = 0.22 + 0.78 * sm(0.1 + i * 0.15, 0.7 + i * 0.15, a1);
    });
    dotMat.e.k = sm(0.15, 0.7, a1);
    // 3 citations
    const a2 = act[2], c2 = cen[2];
    cards.forEach((cd, i) => {
      const k = sm(0, 1, a2 * 1.7 - i * 0.15);
      cd.g.position.set(c2 + CARD[i][0], CARD[i][1], lerp(0.2, 0.38, k));
      cd.pm.k = 0.36 + 0.64 * k; cd.tm.k = 0.35 + 0.65 * k; cd.am.k = 0.25 + 0.75 * k; cd.em.k = 0.45 + 0.55 * k;
      const arr = cd.cg.attributes.position.array;
      const ca = CONN_ANCHOR[i];
      anchorW(ca[0], ca[1], 0.01, c2);
      const tx = v.x, ty = v.y, tz = v.z;
      const sx = cd.g.position.x + (ca[0] < 0 ? 0.23 : -0.23) * Math.cos(pageRot.y);
      arr[0] = sx; arr[1] = cd.g.position.y; arr[2] = cd.g.position.z;
      arr[3] = lerp(sx, tx, k); arr[4] = lerp(cd.g.position.y, ty, k); arr[5] = lerp(cd.g.position.z, tz, k);
      cd.cg.attributes.position.needsUpdate = true;
      cd.cm.k = k;
    });
    // 4 revision
    const r4 = sm(-1.7, -0.45, dAll[3]);
    rev.position.set(lerp(1.05, 0.13, r4), lerp(0.1, -0.06, r4), 0.2);
    rev.rotation.z = lerp(0.05, -0.012, r4);
    const fadeRev = sm(0.0, 0.5, r4);
    revPaper.e.k = fadeRev; revEdge.k = fadeRev; revTxt.e.k = fadeRev; revAcc.e.k = fadeRev;
    ghostEdge.k = 1 - fadeRev; ghostLines.e.k = 1 - fadeRev;
    ghost.position.x = ST_X[3] + 0.9;
    // 5 response
    const f = sm(-1.5, -0.25, dAll[4]);
    const th = (1 - f) * 2.0;
    hinges[1].rotation.y = th; hinges[2].rotation.y = -2 * th;
    letter.position.set(ST_X[4] + 0.4, 0.05, -0.22);

    // fade + apply
    for (const e of reg) { e.m.opacity = e.base * e.k * (e.fade ? fade : 1); }

    // camera
    const asp = cam.aspect;
    const fitW = cam.fit || lerp(7.6, 12.8, sm(0.7, 1.5, asp));
    const D = (fitW / 2) / (Math.tan((camera.fov * Math.PI) / 360) * asp);
    const follow = cam.follow == null ? lerp(0.9, 0.18, sm(0.8, 1.5, asp)) : cam.follow;
    const cx = cam.cx != null ? cam.cx : mx * follow + Math.sin(ts * 0.17) * 0.25;
    const cy = cam.cy != null ? cam.cy : -0.1;
    camera.aspect = asp;
    camera.position.set(cx + Math.sin(ts * 0.21) * 0.35, cy + 1.1 + Math.cos(ts * 0.19) * 0.12, D);
    camera.lookAt(cx, cy, 0);
    camera.updateProjectionMatrix();
  }

  function setPalette(p) {
    for (const e of reg) e.m.color.setRGB(...roleColor(e.role, p), THREE.LinearSRGBColorSpace);
  }
  function dispose() {
    geos.forEach((g) => g.dispose());
    reg.forEach((e) => e.m.dispose());
  }
  return { scene, camera, pose, setPalette, dispose, reg, pipMats };
}

// ---------- renderer wrapper ----------
async function createStage(el, { still = false } = {}) {
  const THREE = await import(THREE_URL);
  const canvas = document.createElement('canvas');
  canvas.className = 'wf-hero-canvas';
  canvas.setAttribute('aria-hidden', 'true');
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: still, powerPreference: 'low-power' });
  renderer.setClearColor(0x000000, 0);
  const st = buildScene(THREE);
  let size = { w: 1, h: 1 };
  const resize = () => {
    const r = el.getBoundingClientRect();
    const w = Math.max(2, Math.round(r.width)), h = Math.max(2, Math.round(r.height));
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(w, h, false);
    size = { w, h };
  };
  const applyTheme = () => st.setPalette(readPalette());
  el.appendChild(canvas);
  resize(); applyTheme();
  return {
    THREE, canvas, renderer, st,
    resize, applyTheme,
    aspect: () => size.w / size.h,
    draw(mx, ts, cam) { st.pose(mx, ts, { aspect: size.w / size.h, ...cam }); renderer.render(st.scene, st.camera); },
    destroy() {
      st.dispose(); renderer.dispose();
      renderer.forceContextLoss && renderer.forceContextLoss();
      canvas.remove();
    },
  };
}

const progressToX = (t) => X0 + (X1 - X0) * ((t % PERIOD) / PERIOD);

// pose definition for stills
function stillPose(name) {
  const i = NAMES.indexOf(name);
  if (i < 0) return { mx: 0.2, ts: 1.0, cam: { cx: 0, cy: -0.1, fit: 12.8, follow: 0 } };
  return { mx: ST_X[i] - 0.05, ts: 1.0, cam: { cx: ST_X[i] + (i === 4 ? 0.45 : 0), cy: -0.4, fit: 6.4, follow: 0 } };
}

export async function renderStill(el, name, opts = {}) {
  if (opts.theme) document.documentElement.setAttribute('data-theme', opts.theme);
  const stage = await createStage(el, { still: true });
  const p = stillPose(name);
  stage.draw(p.mx, p.ts, p.cam);
  el.classList.add('is-live', 'is-still');
  el.dataset.wfState = 'still';
  el.dataset.wfReady = '1';
  return stage;
}

// ---------- gating + controller ----------
function hasWebGL() {
  try {
    const c = document.createElement('canvas');
    const gl = c.getContext('webgl2') || c.getContext('webgl');
    if (!gl) return false;
    const ext = gl.getExtension('WEBGL_lose_context'); ext && ext.loseContext();
    return true;
  } catch (e) { return false; }
}
function eligible(mql) {
  const n = navigator;
  if (mql.matches) return false;
  if (n.connection && n.connection.saveData) return false;
  if (n.deviceMemory && n.deviceMemory < 4) return false;
  if (n.hardwareConcurrency && n.hardwareConcurrency < 4) return false;
  return hasWebGL();
}

function swapPoster(el) {
  const img = el.querySelector('.wf-hero-poster');
  if (!img) return;
  const light = document.documentElement.getAttribute('data-theme') === 'light';
  const src = img.getAttribute('src') || '';
  const want = light ? src.replace(/(-light)?\.webp$/, '-light.webp') : src.replace(/-light\.webp$/, '.webp');
  if (want !== src) img.setAttribute('src', want);
}

function controller(el) {
  const params = new URLSearchParams(location.search);
  const forceFallback = params.get('wf-force-fallback') === '1';
  const skipFps = params.get('wf-skip-fps') === '1';
  const mql = matchMedia('(prefers-reduced-motion: reduce)');
  let stage = null, raf = 0, last = 0, t = 0, frames = 0, dts = [], starting = false, failed = false, visible = true, io, mo, ro;

  const stop = (restore = true) => {
    cancelAnimationFrame(raf); raf = 0;
    io && io.disconnect(); mo && mo.disconnect(); ro && ro.disconnect();
    io = mo = ro = null;
    if (stage) { stage.destroy(); stage = null; }
    if (restore) { el.classList.remove('is-live'); el.dataset.wfState = 'poster'; }
  };
  const loop = (now) => {
    raf = 0;
    if (!stage) return;
    if (!visible || document.hidden) { last = 0; return; }
    const dt = last ? Math.min((now - last) / 1000, 0.1) : 0.016;
    if (last) {
      frames++;
      if (frames > 3 && dts.length < 30) dts.push(dt);
      if (dts.length === 30 && !skipFps) {
        dts.push(0); // marker: checked once
        const avg = dts.slice(0, 30).reduce((a, b) => a + b, 0) / 30;
        if (avg > 0.025 || forceFallback) { failed = true; stop(); return; }
      }
    }
    last = now; t += dt;
    stage.draw(progressToX(t), t, {});
    if (frames === 1) { el.classList.add('is-live'); el.dataset.wfState = 'live'; }
    raf = requestAnimationFrame(loop);
  };
  const kick = () => { if (stage && !raf && visible && !document.hidden) { last = 0; raf = requestAnimationFrame(loop); } };

  async function start() {
    if (stage || starting || failed || !eligible(mql)) return;
    starting = true;
    try {
      const s = await createStage(el);
      starting = false;
      if (mql.matches) { s.destroy(); return; }
      stage = s; frames = 0; dts = []; t = 0; last = 0;
      io = new IntersectionObserver((es) => { visible = es[es.length - 1].isIntersecting; kick(); });
      io.observe(el);
      mo = new MutationObserver(() => { swapPoster(el); stage && stage.applyTheme(); });
      mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
      ro = new ResizeObserver(() => stage && stage.resize());
      ro.observe(el);
      kick();
    } catch (e) { starting = false; failed = true; stop(); }
  }
  mql.addEventListener('change', () => { if (mql.matches) stop(); else start(); });
  document.addEventListener('visibilitychange', kick);
  return { start, stop };
}

function init() {
  const el = document.querySelector('[data-wf-hero]');
  if (!el) return;
  swapPoster(el);
  const themeWatch = new MutationObserver(() => swapPoster(el));
  themeWatch.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  const still = new URLSearchParams(location.search).get('wf-still');
  if (still) { renderStill(el, still); return; }
  const c = controller(el);
  const go = () => ('requestIdleCallback' in window ? requestIdleCallback(c.start, { timeout: 2500 }) : setTimeout(c.start, 300));
  if (document.readyState === 'complete') go(); else addEventListener('load', go, { once: true });
}
init();
