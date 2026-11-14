// Response Review hero: a reviewer comment on one sheet, the author's reply on another, a thread
// between them and a verdict chip at the end of each. The sheets drift in, the threads draw once,
// then the scene rests. three.js is self-hosted and loaded by dynamic import only after the
// capability checks pass; the poster image stays until the canvas is ready.
// Same conventions as workflow-hero.js (poster swap by theme, lazy import, destroy on ineligible).
// Still for the poster images: ?rt-still=1 (final state, preserveDrawingBuffer).

const THREE_URL = '/assets/vendor/three/three.module.min.js';
const PW = 1;
const PH = 1.3;
const TW = 1024;
const TH = 1331;
const END = 4.4; // seconds until the scene is at rest
const PITCH = 340;
const ROW0 = 240;
const MARGIN = 84;

// Content is the sample report on the page: the same comments and the same verdicts.
const ROWS = [
  { id: 'R1.2', quote: 'Sample size seems small for the claimed effect.', reply: 'We added a power analysis to Section 3.2.', verdict: 'addressed', label: 'Addressed' },
  { id: 'R1.4', quote: 'Figure 3 axis labels are unreadable.', reply: 'We enlarged the labels in Figure 3.', verdict: 'partial', label: 'Partially addressed' },
  { id: 'R2.1', quote: 'The related-work section ignores prior work by Chen et al.', reply: 'We are aware of this work.', verdict: 'waved', label: 'Hand-waved' },
];

const sm = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
const lerp = (a, b, t) => a + (b - a) * t;
const easeOut = (x) => 1 - (1 - Math.min(1, Math.max(0, x))) ** 3;

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
const linearToSrgb = (v) => (v <= 0.0031308 ? v * 12.92 : 1.055 * v ** (1 / 2.4) - 0.055);
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
const mix = (a, b, t) => [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];
const hex = (c) => '#' + c.map((v) => Math.round(Math.min(1, Math.max(0, linearToSrgb(v))) * 255).toString(16).padStart(2, '0')).join('');
const rgba = (c, a) => `rgba(${c.map((v) => Math.round(Math.min(1, Math.max(0, linearToSrgb(v))) * 255)).join(',')},${a})`;

function readPalette() {
  const cs = getComputedStyle(document.documentElement);
  const v = (n) => cs.getPropertyValue(n);
  const light = document.documentElement.getAttribute('data-theme') === 'light';
  const bg = parseCssColor(v('--bg'), light ? [0.95, 0.94, 0.96] : [0.012, 0.008, 0.016]);
  const ink = parseCssColor(v('--ink'), light ? [0.005, 0.002, 0.012] : [0.85, 0.83, 0.87]);
  const purple = parseCssColor(v('--purple'), light ? [0.35, 0.05, 0.6] : [0.55, 0.3, 0.75]);
  const purpleDim = parseCssColor(v('--purple-dim'), purple);
  const muted = parseCssColor(v('--muted'), [0.3, 0.28, 0.33]);
  const warm = [1, 0.9, 0.76];
  // Paper is the page's lightest tone nudged warm. Dark theme: a sheet under a desk lamp. Light theme: near white.
  const paper = light ? mix(mix(bg, [1, 1, 1], 0.7), warm, 0.2) : mix(mix(ink, warm, 0.4), [1, 1, 1], 0.3);
  const text = light ? ink : bg; // text on paper is always the dark end of the ramp
  const sub = mix(text, paper, light ? 0.42 : 0.38); // secondary text on paper, still above 4.5:1
  return { bg, ink, purple, purpleDim, muted, paper, text, sub, light };
}

// ---------- canvas textures ----------
function wrap(ctx, text, maxW) {
  const words = text.split(' ');
  const lines = [];
  let cur = '';
  for (const w of words) {
    const t = cur ? cur + ' ' + w : w;
    if (ctx.measureText(t).width > maxW && cur) { lines.push(cur); cur = w; } else cur = t;
  }
  if (cur) lines.push(cur);
  return lines;
}
const SERIF = '"Fraunces", Georgia, serif';
const SANS = '"Plus Jakarta Sans", system-ui, sans-serif';

function drawSheet(title, kind, P) {
  const c = document.createElement('canvas');
  c.width = TW; c.height = TH;
  const x = c.getContext('2d');
  const g = x.createLinearGradient(0, 0, 0, TH);
  g.addColorStop(0, hex(mix(P.paper, [1, 1, 1], P.light ? 0.15 : 0.06)));
  g.addColorStop(1, hex(mix(P.paper, P.bg, P.light ? 0.06 : 0.09)));
  x.fillStyle = g; x.fillRect(0, 0, TW, TH);
  x.strokeStyle = rgba(mix(P.bg, P.ink, 0.4), P.light ? 0.35 : 0.2); x.lineWidth = 3; x.strokeRect(1.5, 1.5, TW - 3, TH - 3);

  x.fillStyle = hex(P.text);
  x.font = `600 64px ${SERIF}`; x.textBaseline = 'alphabetic';
  x.fillText(title, MARGIN, 150);
  x.fillStyle = rgba(P.text, 0.28); x.fillRect(MARGIN, 190, TW - MARGIN * 2, 3);

  const anchors = [];
  ROWS.forEach((r, i) => {
    const top = ROW0 + i * PITCH;
    x.fillStyle = rgba(P.purple, P.light ? 0.1 : 0.16);
    x.fillRect(MARGIN - 24, top - 14, TW - (MARGIN - 24) * 2, PITCH - 24);
    x.fillStyle = hex(P.light ? P.purple : mix(P.purple, P.bg, 0.45));
    x.font = `700 38px ${SANS}`;
    x.fillText(r.id, MARGIN, top + 40);
    x.fillStyle = hex(P.text);
    x.font = `${kind === 'quote' ? 'italic 500' : '500'} 52px ${SANS}`;
    wrap(x, kind === 'quote' ? '“' + r.quote + '”' : r.reply, TW - MARGIN * 2).forEach((ln, k) => x.fillText(ln, MARGIN, top + 112 + k * 68));
    anchors.push((top + 34) / TH);
  });
  return { canvas: c, anchors };
}

function drawChip(row, P) {
  const w = 520, h = 120;
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  const x = c.getContext('2d');
  const r = h / 2 - 3;
  let fill, stroke, ink;
  if (row.verdict === 'addressed') { fill = P.purple; stroke = P.purple; ink = P.light ? [1, 1, 1] : P.bg; }
  else if (row.verdict === 'partial') { fill = mix(P.paper, P.purple, 0.22); stroke = P.purpleDim; ink = P.text; }
  else { fill = mix(P.paper, P.text, 0.1); stroke = mix(P.paper, P.text, 0.55); ink = P.text; }
  x.beginPath();
  x.roundRect(3, 3, w - 6, h - 6, r);
  x.fillStyle = hex(fill); x.fill();
  x.lineWidth = 4; x.strokeStyle = hex(stroke); x.stroke();
  x.fillStyle = hex(ink); x.font = `700 50px ${SANS}`; x.textAlign = 'center'; x.textBaseline = 'middle';
  x.fillText(row.label, w / 2, h / 2 + 3);
  return c;
}

function drawGlow(P) {
  const c = document.createElement('canvas');
  c.width = c.height = 256;
  const x = c.getContext('2d');
  const g = x.createRadialGradient(128, 128, 0, 128, 128, 128);
  g.addColorStop(0, rgba(P.purple, P.light ? 0.12 : 0.2));
  g.addColorStop(1, rgba(P.purple, 0));
  x.fillStyle = g; x.fillRect(0, 0, 256, 256);
  return c;
}
function drawShadow(P) {
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const x = c.getContext('2d');
  const g = x.createRadialGradient(64, 64, 8, 64, 64, 64);
  const s = P.light ? mix(P.purple, P.bg, 0.5) : [0, 0, 0];
  g.addColorStop(0, rgba(s, P.light ? 0.4 : 0.6));
  g.addColorStop(1, rgba(s, 0));
  x.fillStyle = g; x.fillRect(0, 0, 128, 128);
  return c;
}

// ---------- scene ----------
function buildScene(THREE, renderer) {
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(24, 5 / 4, 0.1, 50);
  const disposables = [];
  const textures = [];
  const track = (o) => { disposables.push(o); return o; };

  const tex = (canvas) => {
    const t = new THREE.CanvasTexture(canvas);
    t.colorSpace = THREE.SRGBColorSpace;
    t.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
    textures.push(t);
    return t;
  };
  const mat = (map, order, extra) => {
    const m = track(new THREE.MeshBasicMaterial({ map, transparent: true, depthWrite: false, depthTest: false, toneMapped: false, side: THREE.DoubleSide, ...extra }));
    return m;
  };
  const planeGeo = track(new THREE.PlaneGeometry(PW, PH));
  const chipGeo = track(new THREE.PlaneGeometry(0.42, 0.42 * 120 / 520));
  const unitGeo = track(new THREE.PlaneGeometry(1, 1));
  const dotGeo = track(new THREE.CircleGeometry(0.014, 16));

  const glow = new THREE.Mesh(unitGeo, mat(null)); glow.position.set(-0.13, 0, -0.8); glow.scale.set(5.4, 4.4, 1); glow.renderOrder = 0;
  scene.add(glow);

  const sheets = ['A', 'B'].map((k, i) => {
    const g = new THREE.Group();
    const shadow = new THREE.Mesh(unitGeo, mat(null)); shadow.scale.set(1.18, 1.5, 1); shadow.position.set(0.02, -0.07, -0.02); shadow.renderOrder = 1;
    const paper = new THREE.Mesh(planeGeo, mat(null)); paper.renderOrder = 2;
    g.add(shadow, paper);
    scene.add(g);
    return { g, shadow, paper, home: i === 0 ? { x: -0.8, y: 0.04, z: 0.06, ry: 0.24, rz: -0.016 } : { x: 0.54, y: -0.04, z: -0.04, ry: -0.17, rz: 0.012 } };
  });
  sheets[0].g.rotation.x = sheets[1].g.rotation.x = 0.05;

  const chips = ROWS.map(() => {
    const m = new THREE.Mesh(chipGeo, mat(null)); m.renderOrder = 4;
    sheets[1].g.add(m);
    return m;
  });

  const threadMat = track(new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.95, depthTest: false, depthWrite: false, toneMapped: false }));
  const dotMat = track(new THREE.MeshBasicMaterial({ transparent: true, depthTest: false, depthWrite: false, toneMapped: false, side: THREE.DoubleSide }));
  let threads = [];
  let anchorsA = [], anchorsB = [];

  const local = (u, v) => new THREE.Vector3((u - 0.5) * PW, (0.5 - v) * PH, 0.004);
  function buildThreads() {
    threads.forEach((t) => { scene.remove(t.mesh, t.dotA, t.dotB); t.geo.dispose(); });
    threads = ROWS.map((_, i) => {
      sheets.forEach((s) => s.g.updateMatrixWorld(true));
      const a = sheets[0].g.localToWorld(local(1, anchorsA[i]));
      const b = sheets[1].g.localToWorld(local(0, anchorsB[i]));
      const c1 = a.clone().add(new THREE.Vector3(0.14, 0.08 - i * 0.02, 0.24 + i * 0.04));
      const c2 = b.clone().add(new THREE.Vector3(-0.14, 0.05, 0.19 + i * 0.03));
      const curve = new THREE.CubicBezierCurve3(a, c1, c2, b);
      const geo = new THREE.TubeGeometry(curve, 48, 0.005, 5, false);
      const mesh = new THREE.Mesh(geo, threadMat); mesh.renderOrder = 5; mesh.frustumCulled = false;
      const dotA = new THREE.Mesh(dotGeo, dotMat); dotA.position.copy(a); dotA.renderOrder = 6;
      const dotB = new THREE.Mesh(dotGeo, dotMat); dotB.position.copy(b); dotB.renderOrder = 6;
      scene.add(mesh, dotA, dotB);
      return { mesh, dotA, dotB, geo, count: geo.index.count };
    });
  }

  function setPalette(P) {
    textures.splice(0).forEach((t) => t.dispose());
    const A = drawSheet('Reviewer comments', 'quote', P);
    const B = drawSheet('Your response letter', 'reply', P);
    anchorsA = A.anchors; anchorsB = B.anchors;
    sheets[0].paper.material.map = tex(A.canvas);
    sheets[1].paper.material.map = tex(B.canvas);
    const sh = tex(drawShadow(P));
    sheets.forEach((s) => { s.shadow.material.map = sh; });
    glow.material.map = tex(drawGlow(P));
    chips.forEach((m, i) => { m.material.map = tex(drawChip(ROWS[i], P)); });
    // chip sits under the reply text, left-aligned with it
    chips.forEach((m, i) => m.position.set((MARGIN / TW - 0.5) * PW + 0.21, (0.5 - (ROW0 + i * PITCH + 246) / TH) * PH, 0.008));
    [glow.material, ...sheets.flatMap((s) => [s.paper.material, s.shadow.material]), ...chips.map((m) => m.material)].forEach((m) => { m.needsUpdate = true; });
    const col = (c) => new THREE.Color().setRGB(c[0], c[1], c[2], THREE.LinearSRGBColorSpace);
    threadMat.color.copy(col(P.light ? P.purple : mix(P.purple, [1, 1, 1], 0.1)));
    dotMat.color.copy(col(P.purple));
    pose(lastT, lastCam);
    buildThreads();
    pose(lastT, lastCam);
  }

  let lastT = END, lastCam = { px: 0, py: 0, aspect: 5 / 4 };
  function pose(t, cam) {
    lastT = t; lastCam = cam;
    sheets.forEach((s, i) => {
      const k = easeOut((t - i * 0.25) / 1.7);
      const h = s.home;
      s.g.position.set(h.x + (i === 0 ? -0.22 : 0.22) * (1 - k), h.y - 0.1 * (1 - k), h.z - 0.5 * (1 - k));
      s.g.rotation.y = h.ry + (i === 0 ? 0.28 : -0.28) * (1 - k);
      s.g.rotation.z = h.rz;
      const o = 0.5 + 0.5 * sm(0, 1, (t - i * 0.25) / 1.0);
      s.paper.material.opacity = o; s.shadow.material.opacity = o * 0.9;
    });
    glow.material.opacity = 0.35 + 0.65 * sm(0, 2.2, t);
    ROWS.forEach((_, i) => {
      const th = threads[i];
      const t0 = 1.5 + i * 0.5;
      const f = easeOut((t - t0) / 1.1);
      if (th) {
        th.mesh.geometry.setDrawRange(0, Math.floor(f * 48) * 30);
        th.mesh.visible = f > 0.01;
        th.dotA.visible = f > 0.01; th.dotB.visible = f > 0.98;
      }
      const c = sm(t0 + 0.9, t0 + 1.35, t);
      chips[i].material.opacity = c;
      chips[i].scale.setScalar(0.92 + 0.08 * c);
    });
    // camera: fit width and height, small pointer parallax. A panel that is not wider than tall (phones)
    // gets a close-up of the response letter, with the threads coming in from the comment sheet.
    const asp = cam.aspect;
    const close = asp < 1.05;
    const cx = close ? 0.36 : -0.13;
    const fitW = close ? 1.66 : 2.62, fitH = close ? 1.58 : 1.7;
    const tn = Math.tan((camera.fov * Math.PI) / 360);
    const D = Math.max((fitW / 2) / (tn * asp), (fitH / 2) / tn);
    camera.aspect = asp;
    camera.position.set(cx + cam.px * 0.09, 0.3 + cam.py * -0.05, D);
    camera.lookAt(cx, 0.06, 0);
    camera.updateProjectionMatrix();
  }

  function dispose() {
    textures.forEach((t) => t.dispose());
    threads.forEach((t) => t.geo.dispose());
    disposables.forEach((d) => d.dispose());
  }
  return { scene, camera, pose, setPalette, dispose };
}

// ---------- stage ----------
async function createStage(el, { still = false } = {}) {
  const THREE = await import(THREE_URL);
  if (document.fonts && document.fonts.load) {
    try {
      await Promise.all([document.fonts.load(`600 64px "Fraunces"`), document.fonts.load(`500 52px "Plus Jakarta Sans"`), document.fonts.load(`italic 500 52px "Plus Jakarta Sans"`), document.fonts.load(`700 50px "Plus Jakarta Sans"`)]);
    } catch (e) { /* draw with the fallback faces */ }
  }
  const canvas = document.createElement('canvas');
  canvas.className = 'rt-hero-canvas';
  canvas.setAttribute('aria-hidden', 'true');
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: still, powerPreference: 'low-power' });
  renderer.setClearColor(0x000000, 0);
  const st = buildScene(THREE, renderer);
  let size = { w: 1, h: 1 };
  const resize = () => {
    const r = el.getBoundingClientRect();
    const w = Math.max(2, Math.round(r.width)), h = Math.max(2, Math.round(r.height));
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(w, h, false);
    size = { w, h };
  };
  el.appendChild(canvas);
  resize();
  st.setPalette(readPalette());
  return {
    canvas, renderer, st, resize,
    applyTheme: () => st.setPalette(readPalette()),
    draw(t, cam) { st.pose(t, { px: 0, py: 0, ...cam, aspect: size.w / size.h }); renderer.render(st.scene, st.camera); },
    destroy() {
      st.dispose(); renderer.dispose();
      renderer.forceContextLoss && renderer.forceContextLoss();
      canvas.remove();
    },
  };
}

// ---------- gating + controller ----------
let webglOK = null;
function hasWebGL() {
  if (webglOK === null) webglOK = probeWebGL();
  return webglOK;
}
function probeWebGL() {
  try {
    const c = document.createElement('canvas');
    const gl = c.getContext('webgl2') || c.getContext('webgl');
    if (!gl) return false;
    const ext = gl.getExtension('WEBGL_lose_context'); ext && ext.loseContext();
    return true;
  } catch (e) { return false; }
}
function eligible(mqls) {
  const n = navigator;
  if (mqls.some((m) => m.matches)) return false; // reduced motion, narrow viewport, coarse pointer
  if (n.connection && n.connection.saveData) return false;
  if (n.deviceMemory && n.deviceMemory < 4) return false; // a missing value passes
  return hasWebGL();
}

function swapPoster(el) {
  const light = document.documentElement.getAttribute('data-theme') === 'light';
  const themed = (u) => (light ? u.replace(/(-light)?\.webp$/, '-light.webp') : u.replace(/-light\.webp$/, '.webp'));
  el.querySelectorAll('.rt-hero-poster, source').forEach((n) => {
    const attr = n.tagName === 'SOURCE' ? 'srcset' : 'src';
    const cur = n.getAttribute(attr) || '';
    const want = themed(cur);
    if (want !== cur) n.setAttribute(attr, want);
  });
}

function controller(el) {
  const reduce = matchMedia('(prefers-reduced-motion: reduce)');
  const narrow = matchMedia('(max-width: 759px)');
  const coarse = matchMedia('(pointer: coarse)');
  const mqls = [reduce, narrow, coarse];
  let stage = null, raf = 0, last = 0, t = 0, started = false, starting = false, failed = false, visible = false;
  let io, mo, ro;
  const ptr = { x: 0, y: 0, tx: 0, ty: 0 };

  const stop = (restore = true) => {
    cancelAnimationFrame(raf); raf = 0;
    io && io.disconnect(); mo && mo.disconnect(); ro && ro.disconnect();
    el.removeEventListener('pointermove', onMove); el.removeEventListener('pointerleave', onLeave);
    io = mo = ro = null;
    if (stage) { stage.destroy(); stage = null; }
    started = false; t = 0; last = 0;
    if (restore) { el.classList.remove('is-live'); el.dataset.rtState = 'poster'; }
  };
  const settled = () => t >= END && Math.abs(ptr.tx - ptr.x) < 0.001 && Math.abs(ptr.ty - ptr.y) < 0.001;
  const draw = () => stage && stage.draw(Math.min(t, END), { px: ptr.x, py: ptr.y });
  const loop = (now) => {
    raf = 0;
    if (!stage || !visible || document.hidden) { last = 0; return; }
    const dt = last ? Math.min((now - last) / 1000, 0.1) : 0.016;
    last = now;
    if (started) t = Math.min(END, t + dt);
    ptr.x += (ptr.tx - ptr.x) * Math.min(1, dt * 6);
    ptr.y += (ptr.ty - ptr.y) * Math.min(1, dt * 6);
    if (Math.abs(ptr.tx - ptr.x) < 0.001) ptr.x = ptr.tx;
    if (Math.abs(ptr.ty - ptr.y) < 0.001) ptr.y = ptr.ty;
    draw();
    if (!el.classList.contains('is-live')) { el.classList.add('is-live'); el.dataset.rtState = 'live'; }
    if (settled()) { last = 0; return; } // at rest: no more frames until the pointer moves
    raf = requestAnimationFrame(loop);
  };
  const kick = () => { if (stage && !raf && visible && !document.hidden) { last = 0; raf = requestAnimationFrame(loop); } };
  function onMove(e) {
    const r = el.getBoundingClientRect();
    ptr.tx = ((e.clientX - r.left) / r.width - 0.5) * 2;
    ptr.ty = ((e.clientY - r.top) / r.height - 0.5) * 2;
    kick();
  }
  function onLeave() { ptr.tx = 0; ptr.ty = 0; kick(); }

  async function start() {
    if (stage || starting || failed || !eligible(mqls)) return;
    starting = true;
    try {
      const s = await createStage(el);
      starting = false;
      if (!eligible(mqls)) { s.destroy(); return; }
      stage = s; t = 0; last = 0;
      s.draw(0, {});
      s.renderer.domElement.addEventListener('webglcontextlost', (e) => { e.preventDefault(); failed = true; stop(); });
      io = new IntersectionObserver((es) => {
        visible = es[es.length - 1].isIntersecting;
        if (visible) started = true; // the settle-in begins when the figure is on screen
        kick();
      }, { threshold: 0.35 });
      io.observe(el);
      mo = new MutationObserver(() => { swapPoster(el); if (stage) { stage.applyTheme(); draw(); } });
      mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
      ro = new ResizeObserver(() => { if (stage) { stage.resize(); draw(); } });
      ro.observe(el);
      el.addEventListener('pointermove', onMove, { passive: true });
      el.addEventListener('pointerleave', onLeave);
    } catch (e) { starting = false; failed = true; stop(); }
  }
  const recheck = () => { if (mqls.some((m) => m.matches)) stop(); else start(); };
  mqls.forEach((m) => m.addEventListener('change', recheck));
  document.addEventListener('visibilitychange', kick);
  return { start };
}

async function renderStill(el) {
  const stage = await createStage(el, { still: true });
  stage.draw(END, {});
  el.classList.add('is-live', 'is-still');
  el.dataset.rtState = 'still';
  el.dataset.rtReady = '1';
}

function init() {
  const el = document.querySelector('[data-rt-hero]');
  if (!el) return;
  swapPoster(el);
  new MutationObserver(() => swapPoster(el)).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  if (new URLSearchParams(location.search).get('rt-still')) { renderStill(el); return; }
  const c = controller(el);
  const go = () => ('requestIdleCallback' in window ? requestIdleCallback(c.start, { timeout: 2500 }) : setTimeout(c.start, 300));
  if (document.readyState === 'complete') go(); else addEventListener('load', go, { once: true });
}
init();
