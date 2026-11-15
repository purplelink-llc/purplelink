// Waiting scene for the status page: manuscript pages leave an unread stack, get
// three lines highlighted and marked in the margin, then settle on a read stack.
// Optional and cheap: three.js (self-hosted) is imported only when WebGL works,
// motion is allowed and the visitor has not turned it off. Frame rate is capped,
// the loop stops while the tab or the band is hidden, and the renderer is torn
// down for good once the progress panel goes away (result or error).

const THREE_URL = '/assets/vendor/three/three.module.min.js';
const STORE_KEY = 'pl-pr-scene';
const FPS = 30;
const FRAME_MS = 1000 / FPS;
const MAX_DPR = 1.5;

const PERIOD = 8;      // seconds between pages
const MOVE = 1.6;      // seconds a page takes to travel between slots
const PW = 1.25;
const PH = 1.7;
const VIEW_H = 2.3;    // world units visible vertically
const FOV = 28;
const LINE_W = [0.92, 1, 0.84, 1, 0.97, 0.62, 1, 0.88, 0.7];
const MARKS = [[1, 4, 7], [0, 3, 6], [2, 5, 8], [1, 3, 6], [0, 4, 8]];

const clamp01 = (x) => Math.min(1, Math.max(0, x));
const ease = (x) => { const t = clamp01(x); return t * t * (3 - 2 * t); };
const lerp = (a, b, t) => a + (b - a) * t;
const mix = (a, b, t) => [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];

// ---------- colour from the site's CSS custom properties ----------
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
function palette() {
  const cs = getComputedStyle(document.documentElement);
  const v = (n) => cs.getPropertyValue(n);
  const light = document.documentElement.getAttribute('data-theme') === 'light';
  const bg = parseCssColor(v('--bg'), light ? [0.95, 0.94, 0.96] : [0.012, 0.008, 0.016]);
  const ink = parseCssColor(v('--ink'), light ? [0.005, 0.002, 0.012] : [0.85, 0.83, 0.87]);
  const purple = parseCssColor(v('--purple'), light ? [0.35, 0.05, 0.6] : [0.55, 0.3, 0.75]);
  const paper = light ? mix(bg, [1, 1, 1], 0.8) : mix(bg, ink, 0.075);
  const stack = mix(paper, bg, light ? 0.35 : 0.4);
  return {
    paper,
    stack,
    stack2: mix(stack, bg, 0.3),
    stack3: mix(stack, bg, 0.55),
    edge: mix(bg, ink, light ? 0.45 : 0.32),
    text: mix(paper, ink, light ? 0.3 : 0.28),
    head: mix(paper, ink, light ? 0.55 : 0.5),
    accent: purple,
  };
}

// ---------- scene ----------
function buildScene(THREE) {
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(FOV, 4, 0.1, 50);
  camera.position.set(0, 0, (VIEW_H / 2) / Math.tan((FOV / 2) * Math.PI / 180));
  const mats = [];   // { m, role }
  const geos = [];

  const unit = new THREE.PlaneGeometry(1, 1);
  const leftUnit = new THREE.PlaneGeometry(1, 1).translate(0.5, 0, 0); // grows from its left edge
  const dot = new THREE.CircleGeometry(1, 18);
  const sheet = new THREE.PlaneGeometry(PW, PH);
  const outline = new THREE.EdgesGeometry(sheet);
  geos.push(unit, leftUnit, dot, sheet, outline);

  const mat = (role, opts) => {
    const m = opts.line ? new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, depthWrite: false })
      : new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: !!opts.transparent, depthWrite: !opts.transparent, side: THREE.DoubleSide });
    if (opts.opacity != null) m.opacity = opts.opacity;
    mats.push({ m, role });
    return m;
  };
  const add = (parent, obj, order) => { obj.renderOrder = order; parent.add(obj); return obj; };

  // Stacks: three plain sheets each. The top sheet sits exactly where a moving
  // page starts (left) or lands (right), so pages hand off without a pop.
  const stackPaper = [mat('stack', {}), mat('stack2', {}), mat('stack3', {})];
  const stackEdge = mat('edge', { line: true, opacity: 0.7 });
  const stacks = [-1, 1].map((side) => {
    const g = new THREE.Group();
    for (let i = 2; i >= 0; i--) {
      const s = add(g, new THREE.Mesh(sheet, stackPaper[i]), 0);
      s.position.set(side * -i * 0.05, -i * 0.05, -i * 0.06);
      add(s, new THREE.LineSegments(outline, stackEdge), 1);
    }
    scene.add(g);
    return g;
  });

  // Text block geometry inside a page.
  const L0 = -PW * 0.4;
  const BW = PW * 0.72;
  const lineY = (i) => PH * (0.27 - i * 0.075);
  const MARGIN_X = L0 + BW + PW * 0.06;

  // Two recycled pages: page k uses slot k % 2.
  const pages = [0, 1].map(() => {
    const g = new THREE.Group();
    const paper = mat(null, {});
    const edge = mat('edge', { line: true, opacity: 0.7 });
    const text = mat('text', { transparent: true });
    const head = mat('head', { transparent: true });
    const hi = mat('accent', { transparent: true });
    const dotM = mat('accent', { transparent: true });
    add(g, new THREE.Mesh(sheet, paper), 0);
    add(g, new THREE.LineSegments(outline, edge), 1);
    const title = add(g, new THREE.Mesh(unit, head), 3);
    title.scale.set(BW * 0.55, 0.05, 1);
    title.position.set(L0 + BW * 0.275, PH * 0.38, 0.004);
    LINE_W.forEach((w, i) => {
      const l = add(g, new THREE.Mesh(unit, text), 3);
      l.scale.set(BW * w, 0.026, 1);
      l.position.set(L0 + BW * w / 2, lineY(i), 0.004);
    });
    const his = [0, 1, 2].map(() => {
      const h = add(g, new THREE.Mesh(leftUnit, hi), 2);
      h.position.set(L0 - 0.02, 0, 0.002);
      return h;
    });
    const dots = [0, 1, 2].map(() => add(g, new THREE.Mesh(dot, dotM), 3));
    scene.add(g);
    return { g, paper, text, head, hi, dotM, his, dots };
  });

  let slots = null;
  function layout(aspect) {
    camera.aspect = aspect;
    camera.updateProjectionMatrix();
    const halfW = (VIEW_H * aspect) / 2;
    const S = Math.max(1.2, Math.min(2.4, halfW - PW * 0.62));
    const side = { y: -0.08, z: -0.15, s: 0.78, ry: 0.3 };
    slots = {
      L: { x: -S, ...side, ry: side.ry },
      C: { x: 0, y: 0, z: 0, s: 1, ry: 0 },
      R: { x: S, ...side, ry: -side.ry },
    };
    stacks[0].position.set(-S, side.y, side.z); stacks[0].scale.setScalar(side.s); stacks[0].rotation.y = side.ry;
    stacks[1].position.set(S, side.y, side.z); stacks[1].scale.setScalar(side.s); stacks[1].rotation.y = -side.ry;
  }

  function place(g, a, from, to, t) {
    const k = ease(a);
    const centred = (from === slots.C ? 1 - k : 0) + (to === slots.C ? k : 0);
    g.position.set(lerp(from.x, to.x, k), lerp(from.y, to.y, k) + Math.sin(t * 0.7) * 0.025 * centred,
      lerp(from.z, to.z, k) + Math.sin(Math.PI * k) * 0.45);
    g.scale.setScalar(lerp(from.s, to.s, k));
    g.rotation.set(0, lerp(from.ry, to.ry, k) + Math.sin(Math.PI * k) * 0.12 * Math.sign(to.x - from.x), Math.sin(t * 0.5) * 0.008 * centred);
  }

  function posePage(p, k, u, t) {
    if (u < 0 || u >= PERIOD + MOVE) { p.g.visible = false; return; }
    p.g.visible = true;
    let ink;  // opacity of everything printed on the page
    if (u < MOVE) { place(p.g, u / MOVE, slots.L, slots.C, t); ink = ease((u / MOVE - 0.2) / 0.6); }
    else if (u < PERIOD) { place(p.g, 1, slots.L, slots.C, t); ink = 1; }
    else { const a = (u - PERIOD) / MOVE; place(p.g, a, slots.C, slots.R, t); ink = 1 - ease((a - 0.4) / 0.55); }
    // Paper blends toward the stack colour while it travels, so it matches the
    // stack's top sheet at both hand-offs.
    const c = mix(pal.stack, pal.paper, ink);
    p.paper.color.setRGB(c[0], c[1], c[2]);
    p.text.opacity = 0.9 * ink;
    p.head.opacity = 0.95 * ink;
    p.hi.opacity = 0.34 * ink;
    p.dotM.opacity = 0.95 * ink;
    const lines = MARKS[((k % MARKS.length) + MARKS.length) % MARKS.length];
    lines.forEach((li, j) => {
      const start = MOVE + 0.6 + j * 1.7;
      const sweep = ease((u - start) / 1.0);
      const w = (BW * LINE_W[li] + 0.04) * sweep;
      const h = p.his[j];
      h.visible = sweep > 0;
      h.scale.set(Math.max(w, 1e-4), 0.07, 1);
      h.position.y = lineY(li);
      const d = p.dots[j];
      const pop = ease((u - start - 0.85) / 0.35);
      d.visible = pop > 0;
      d.scale.setScalar(0.034 * Math.max(pop, 1e-4));
      d.position.set(MARGIN_X, lineY(li), 0.004);
    });
  }

  function pose(t) {
    const k = Math.floor(t / PERIOD);
    posePage(pages[((k % 2) + 2) % 2], k, t - k * PERIOD, t);
    posePage(pages[(((k - 1) % 2) + 2) % 2], k - 1, t - (k - 1) * PERIOD, t);
  }

  let pal = null;
  function setPalette(next) {
    pal = next;
    mats.forEach(({ m, role }) => { if (!role) return; const c = pal[role]; m.color.setRGB(c[0], c[1], c[2]); });
  }
  function dispose() {
    geos.forEach((g) => g.dispose());
    mats.forEach(({ m }) => m.dispose());
  }
  return { scene, camera, layout, pose, setPalette, dispose };
}

// ---------- renderer ----------
async function createStage(host) {
  const THREE = await import(THREE_URL);
  const canvas = document.createElement('canvas');
  canvas.className = 'pr-scene-canvas';
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'low-power' });
  renderer.setClearColor(0x000000, 0);
  const st = buildScene(THREE);
  const resize = () => {
    const r = host.getBoundingClientRect();
    const w = Math.max(2, Math.round(r.width)), h = Math.max(2, Math.round(r.height));
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, MAX_DPR));
    renderer.setSize(w, h, false);   // false: no inline styles on the canvas
    st.layout(w / h);
  };
  host.appendChild(canvas);
  resize();
  st.setPalette(palette());
  return {
    canvas, resize,
    applyTheme: () => st.setPalette(palette()),
    draw(t) { st.pose(t); renderer.render(st.scene, st.camera); },
    destroy() {
      st.dispose(); renderer.dispose();
      if (renderer.forceContextLoss) renderer.forceContextLoss();
      canvas.remove();
    },
  };
}

// ---------- gating ----------
function hasWebGL() {
  try {
    const c = document.createElement('canvas');
    const gl = c.getContext('webgl2') || c.getContext('webgl');
    if (!gl) return false;
    const ext = gl.getExtension('WEBGL_lose_context');
    if (ext) ext.loseContext();
    return true;
  } catch (e) { return false; }
}
const readPref = () => { try { return localStorage.getItem(STORE_KEY); } catch (e) { return null; } };
const writePref = (v) => { try { localStorage.setItem(STORE_KEY, v); } catch (e) { /* storage blocked */ } };

// ---------- controller ----------
function init() {
  const root = document.getElementById('pr-scene');
  const host = root && root.querySelector('.pr-scene-stage');
  const btn = root && root.querySelector('.pr-scene-toggle');
  const wrap = document.getElementById('progress-wrap');
  if (!root || !host || !btn || !wrap) return;
  const n = navigator;
  const mql = matchMedia('(prefers-reduced-motion: reduce)');
  if ((n.connection && n.connection.saveData) || !hasWebGL()) return;

  let stage = null, starting = false, finished = false;
  let raf = 0, lastDraw = 0, t = 0, onScreen = true;
  let io = null, mo = null, ro = null;
  root.prSceneFrames = 0;

  const setState = (s) => { root.dataset.state = s; };
  const userOff = () => readPref() === 'off';

  function teardown() {
    cancelAnimationFrame(raf); raf = 0;
    if (io) io.disconnect(); if (mo) mo.disconnect(); if (ro) ro.disconnect();
    io = mo = ro = null;
    if (stage) { stage.destroy(); stage = null; }
  }
  function sync() {
    // The band is offered only while motion is allowed and the review is running.
    root.hidden = finished || mql.matches;
    const off = userOff();
    host.hidden = off;
    btn.textContent = off ? 'Show animation' : 'Hide animation';
    if (root.hidden || off) { teardown(); setState(root.hidden ? 'off' : 'hidden-by-user'); return; }
    start();
  }

  function loop(now) {
    raf = 0;
    if (!stage) return;
    if (!onScreen || document.hidden) { setState('paused'); return; }
    if (!lastDraw || now - lastDraw >= FRAME_MS - 2) {
      t += lastDraw ? Math.min((now - lastDraw) / 1000, 0.1) : 0;
      lastDraw = now;
      stage.draw(t);
      root.prSceneFrames++;
      if (root.dataset.state !== 'live') setState('live');
    }
    raf = requestAnimationFrame(loop);
  }
  function kick() {
    if (stage && !raf && onScreen && !document.hidden) { lastDraw = 0; raf = requestAnimationFrame(loop); }
  }

  async function start() {
    if (stage || starting || finished) return;
    starting = true;
    setState('loading');
    let s;
    try { s = await createStage(host); } catch (e) { starting = false; finished = true; sync(); return; }
    starting = false;
    if (finished || mql.matches || userOff()) { s.destroy(); return; }
    stage = s;
    s.canvas.addEventListener('webglcontextlost', () => { if (stage === s) { finished = true; sync(); } });
    io = new IntersectionObserver((es) => { onScreen = es[es.length - 1].isIntersecting; kick(); });
    io.observe(host);
    mo = new MutationObserver(() => { if (stage) stage.applyTheme(); });
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    ro = new ResizeObserver(() => { if (stage) stage.resize(); });
    ro.observe(host);
    kick();
  }

  btn.addEventListener('click', () => { writePref(userOff() ? 'on' : 'off'); sync(); });
  mql.addEventListener('change', sync);
  document.addEventListener('visibilitychange', kick);
  // status.js hides #progress-wrap when the result or an error arrives.
  new MutationObserver(() => {
    if (!finished && getComputedStyle(wrap).display === 'none') { finished = true; sync(); }
  }).observe(wrap, { attributes: true, attributeFilter: ['style', 'hidden', 'class'] });

  const go = () => sync();
  if (document.readyState === 'complete') go(); else addEventListener('load', go, { once: true });
}
init();
