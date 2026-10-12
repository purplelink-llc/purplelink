// Desk specs for the Panely promo and its stills. Geometry follows PanelyCore: GridRegion.frame (outer margin, gap,
// columns x rows) and CustomArea (fractions of the usable area). All coordinates are desk px in the 1280 x 800 desk.
import { DESK, ignoreRowRect } from "./geom.js";

export const AREA = [0, DESK.BAR, DESK.W, DESK.H - DESK.BAR]; // usable area under the menu bar (no Dock drawn)
export const OUTER = 10;
export const GAP = 10;

// GridRegion.frame(in: area, outer, gap)
export function grid(columns, rows, col, row, colSpan = 1, rowSpan = 1) {
  const [ax, ay, aw, ah] = AREA;
  const ix = ax + OUTER, iy = ay + OUTER, iw = aw - 2 * OUTER, ih = ah - 2 * OUTER;
  const cw = (iw - GAP * (columns - 1)) / columns, rh = (ih - GAP * (rows - 1)) / rows;
  return [ix + col * (cw + GAP), iy + row * (rh + GAP), cw * colSpan + GAP * (colSpan - 1), rh * rowSpan + GAP * (rowSpan - 1)].map(Math.round);
}
// CustomArea.rect.rect(in: inner)
export function frac(x, y, w, h) {
  const [ax, ay, aw, ah] = AREA;
  const ix = ax + OUTER, iy = ay + OUTER, iw = aw - 2 * OUTER, ih = ah - 2 * OUTER;
  return [ix + x * iw, iy + y * ih, w * iw, h * ih].map(Math.round);
}

const NAMES = [
  { id: "draft", title: "Draft", tone: "violet", kind: "text" },
  { id: "sources", title: "Sources", tone: "blue", kind: "list" },
  { id: "notes", title: "Notes", tone: "sand", kind: "blocks" },
  { id: "chat", title: "Chat", tone: "rose", kind: "text" },
  { id: "photos", title: "Photos", tone: "teal", kind: "blocks" },
  { id: "plan", title: "Plan", tone: "violet", kind: "list" },
];
export const FLOAT = {
  draft: [90, 110, 640, 460],
  sources: [420, 190, 600, 420],
  notes: [700, 84, 420, 320],
  chat: [160, 330, 480, 340],
  photos: [560, 380, 520, 330],
  plan: [300, 60, 460, 360],
};

// windows from per-window key lists: keys[id] = [[t, rect, d?], ...]
function make(ids, keysById, zById = {}) {
  return ids.map((id) => {
    const n = NAMES.find((x) => x.id === id);
    return { ...n, z: zById[id] ?? 1, keys: keysById[id].map(([t, r, d]) => (d == null ? [t, ...r] : [t, ...r, d])) };
  });
}

// ---- 1. a shortcut, then two drags ---------------------------------------------------------------
// c: { shortcut, drag1, drag2 } seconds (local)
export function deskDrag(c) {
  const left = grid(2, 1, 0, 0);
  const tr = grid(2, 2, 1, 0), br = grid(2, 2, 1, 1);
  const dur = 0.8;
  const grab = (r) => [r[0] + r[2] * 0.5, r[1] + 17]; // title bar centre
  const gs = grab(FLOAT.sources), gn = grab(FLOAT.notes);
  const [W, H] = [DESK.W, DESK.H];
  const e1 = [W - 26, DESK.BAR + 18], e2 = [W - 26, H - 40]; // cursor end points, just inside the corner
  const winKeys = (r0, to, tDrag, snap) => {
    const g = grab(r0);
    const moved = [to[0] + (r0[0] - g[0]), to[1] + (r0[1] - g[1]), r0[2], r0[3]];
    return [[0, r0], [tDrag, moved, dur], [tDrag + dur + 0.35, snap, 0.5]];
  };
  return {
    windows: make(["draft", "sources", "notes"], {
      draft: [[0, FLOAT.draft], [c.shortcut + 0.25, left, 0.6]],
      sources: winKeys(FLOAT.sources, e1, c.drag1, tr),
      notes: winKeys(FLOAT.notes, e2, c.drag2, br),
    }, { draft: 1, sources: 2, notes: 3 }),
    caps: [{ t0: c.shortcut, t1: c.shortcut + 1.1, text: "⌃ ⌥ ←" }],
    previews: [
      { t0: c.drag1 + dur - 0.25, t1: c.drag1 + dur + 0.35, r: tr },
      { t0: c.drag2 + dur - 0.25, t1: c.drag2 + dur + 0.35, r: br },
    ],
    cursor: [
      [0, gs[0] + 120, gs[1] + 330, 0.01],
      [c.drag1 - 0.6, gs[0], gs[1], 0.6],
      [c.drag1, e1[0], e1[1], dur],
      [c.drag1 + dur + 0.4, gn[0], gn[1], 0.6],
      [c.drag2, e2[0], e2[1], dur],
      [c.drag2 + dur + 0.5, W - 260, H - 200, 0.6],
    ],
  };
}

// the state deskDrag ends in (left half, two right quarters), with the other three windows waiting behind
export function afterDrag() {
  const left = grid(2, 1, 0, 0), tr = grid(2, 2, 1, 0), br = grid(2, 2, 1, 1);
  return { rects: { draft: left, sources: tr, notes: br, chat: left, photos: br, plan: left }, z: { draft: 5, sources: 5, notes: 5, chat: 2, photos: 2, plan: 2 } };
}

// ---- 2. layouts: halves, thirds, quarters, sixths, one custom area ----------------------------
// Windows a layout does not use wait behind another window.
export function layoutSets() {
  const L = {};
  L.halves = { draft: grid(2, 1, 0, 0), sources: grid(2, 1, 1, 0), notes: grid(2, 1, 1, 0), chat: grid(2, 1, 0, 0), photos: grid(2, 1, 1, 0), plan: grid(2, 1, 0, 0) };
  L.thirds = { draft: grid(3, 1, 0, 0), sources: grid(3, 1, 1, 0), notes: grid(3, 1, 2, 0), chat: grid(3, 1, 0, 0), photos: grid(3, 1, 1, 0), plan: grid(3, 1, 2, 0) };
  L.quarters = { draft: grid(2, 2, 0, 0), sources: grid(2, 2, 1, 0), chat: grid(2, 2, 0, 1), notes: grid(2, 2, 1, 1), photos: grid(2, 2, 1, 1), plan: grid(2, 2, 0, 1) };
  L.sixths = { draft: grid(3, 2, 0, 0), sources: grid(3, 2, 1, 0), notes: grid(3, 2, 2, 0), chat: grid(3, 2, 0, 1), photos: grid(3, 2, 1, 1), plan: grid(3, 2, 2, 1) };
  const col = frac(0.2, 0, 0.6, 1);
  L.area = { draft: col, sources: col, notes: col, chat: col, photos: col, plan: col };
  return L;
}
const Z = {
  halves: { draft: 5, sources: 5, notes: 2, chat: 2, photos: 2, plan: 2 },
  thirds: { draft: 5, sources: 5, notes: 5, chat: 2, photos: 2, plan: 2 },
  quarters: { draft: 5, sources: 5, chat: 5, notes: 5, photos: 2, plan: 2 },
  sixths: { draft: 5, sources: 5, notes: 5, chat: 5, photos: 5, plan: 5 },
  area: { draft: 6, sources: 2, notes: 2, chat: 2, photos: 2, plan: 2 },
};
export const IDS6 = ["draft", "sources", "notes", "chat", "photos", "plan"];

// order: [[layoutName, time], ...]; loopBack: { name, t } returns to a layout at the end (hero loop)
// start: undefined = windows float loose; a layout name; or { rects, z } (explicit start state)
export function deskLayouts(order, { loopBack = null, floatStart = true, start = null } = {}) {
  const sets = layoutSets();
  const seq = loopBack ? [...order, [loopBack.name, loopBack.t]] : order;
  const keys = {};
  let z0;
  const init = (id) => {
    if (start && start.rects) return start.rects[id];
    if (typeof start === "string") return sets[start][id];
    return floatStart ? FLOAT[id] : sets[order[0][0]][id];
  };
  if (start && start.z) z0 = start.z;
  else if (typeof start === "string") z0 = Z[start];
  else z0 = floatStart ? { draft: 1, sources: 2, notes: 3, chat: 1, photos: 2, plan: 1 } : Z[order[0][0]];
  IDS6.forEach((id) => (keys[id] = [[0, init(id)]]));
  seq.forEach(([name, t]) => IDS6.forEach((id) => keys[id].push([t, sets[name][id], 0.75])));
  const wins = make(IDS6, keys, z0);
  wins.forEach((w) => (w.zSteps = [[-1, z0[w.id]], ...seq.map(([name, t]) => [t, Z[name][w.id]])]));
  const areaLabels = [];
  seq.forEach(([name, t], i) => {
    if (name === "area" && !(loopBack && i === seq.length - 1)) {
      const next = i + 1 < seq.length ? seq[i + 1][1] : t + 3;
      areaLabels.push({ t0: t + 0.7, t1: next - 0.2, r: sets.area.draft, text: "Custom area: left 20%, width 60%" });
    }
  });
  return { windows: wins, areaLabels, caps: [], previews: [], cursor: [] };
}

// ---- 3. ignored apps -------------------------------------------------------------------------------
// c: { open, hover, check, close, k1, k2 }
export function deskIgnore(c) {
  const left = grid(2, 1, 0, 0), right = grid(2, 1, 1, 0);
  const call = [400, 250, 520, 380];
  const row = ignoreRowRect();
  return {
    windows: make(["draft", "sources", "chat"], {
      draft: [[0, [60, 120, 600, 440]], [c.k1 + 0.25, left, 0.6]],
      sources: [[0, [610, 150, 580, 420]], [c.k2 + 0.25, right, 0.6]],
      chat: [[0, call]],
    }, { draft: 1, sources: 2, chat: 4 }).map((w) => (w.id === "chat" ? { ...w, title: "Callroom", kind: "blocks" } : w)),
    menu: { t0: c.open, t1: c.close, hoverAt: c.hover, checkAt: c.check },
    caps: [{ t0: c.k1, t1: c.k1 + 0.95, text: "⌃ ⌥ ←", bottom: 100 }, { t0: c.k2, t1: c.k2 + 0.95, text: "⌃ ⌥ →", bottom: 100 }],
    previews: [],
    cursor: [
      [0, DESK.W - 150, 400, 0.01],
      [c.open - 0.5, DESK.W - 36, 18, 0.5],
      [c.hover - 0.55, row[0] + 120, row[1] + 14, 0.5],
      [c.close + 0.1, DESK.W - 160, 700, 0.9],
    ],
  };
}
