// A schematic Mac desktop for the Panely promo: invented windows, a menu bar with the Panely icon, an optional
// drop-down, a drag preview, key caps and a cursor. Pure drawing, driven by time (no real window, no screenshot).
// Spec (see src/panely/desk.js): { windows:[{id,title,tone,kind,keys:[[t,x,y,w,h,d?]]}], previews, cursor, caps, menu }
// All coordinates are desk pixels in a 1280 x 800 desk; t is seconds since the spec started.
import React from "react";
import { brand, clamp01, expoOut, lerp, FONT_BODY } from "./theme.js";

import { DESK, MENU, MENU_ROW, MENU_W, menuHeight } from "./panely/geom.js";
export { DESK };
const INK = "oklch(14% 0.07 310)";
const PURPLE = "oklch(50% 0.24 310)";
const TONES = {
  violet: { bar: "oklch(93% 0.05 310)", line: "oklch(78% 0.09 310)", soft: "oklch(96.5% 0.02 310)", edge: "oklch(80% 0.07 310)" },
  blue: { bar: "oklch(93% 0.04 255)", line: "oklch(76% 0.09 255)", soft: "oklch(96.5% 0.018 255)", edge: "oklch(80% 0.06 255)" },
  teal: { bar: "oklch(93% 0.045 195)", line: "oklch(74% 0.08 195)", soft: "oklch(96.5% 0.018 195)", edge: "oklch(80% 0.06 195)" },
  rose: { bar: "oklch(93% 0.045 10)", line: "oklch(76% 0.09 10)", soft: "oklch(96.5% 0.02 10)", edge: "oklch(81% 0.06 10)" },
  sand: { bar: "oklch(93% 0.045 80)", line: "oklch(76% 0.09 80)", soft: "oklch(96.5% 0.02 80)", edge: "oklch(81% 0.06 80)" },
};

// rect of a window at time t: linear in key time order, eased with expoOut over each key's own duration d
export function rectAt(keys, t) {
  let i = 0;
  keys.forEach((k, j) => { if (t >= k[0]) i = j; });
  const k = keys[i];
  if (i === 0) return k.slice(1, 5);
  const p = expoOut(clamp01((t - k[0]) / (k[5] ?? 0.7)));
  const q = keys[i - 1];
  return [0, 1, 2, 3].map((n) => lerp(q[1 + n], k[1 + n], p));
}

function Lines({ kind, w, h, tone }) {
  const T = TONES[tone] || TONES.violet;
  const rows = [];
  const pad = 22;
  if (kind === "text") {
    const widths = [0.9, 0.78, 0.86, 0.62, 0.88, 0.7, 0.82, 0.5, 0.86, 0.74, 0.8, 0.58, 0.9, 0.66];
    const n = Math.max(1, Math.floor((h - 34 - 2 * pad) / 22));
    for (let i = 0; i < n; i++) rows.push(<div key={i} style={{ position: "absolute", left: pad, top: 34 + pad + i * 22, width: (w - 2 * pad) * widths[i % widths.length], height: 8, borderRadius: 4, background: T.line, opacity: 0.55 }} />);
  } else if (kind === "list") {
    const n = Math.max(1, Math.floor((h - 34 - 2 * pad) / 40));
    for (let i = 0; i < n; i++) {
      rows.push(<div key={"d" + i} style={{ position: "absolute", left: pad, top: 34 + pad + i * 40 + 2, width: 18, height: 18, borderRadius: 9, background: T.line, opacity: 0.8 }} />);
      rows.push(<div key={"l" + i} style={{ position: "absolute", left: pad + 32, top: 34 + pad + i * 40 + 6, width: (w - 2 * pad - 32) * (0.5 + 0.4 * ((i * 37) % 10) / 10), height: 9, borderRadius: 4.5, background: T.line, opacity: 0.55 }} />);
    }
  } else {
    // blocks: a picture area and a caption line
    rows.push(<div key="b" style={{ position: "absolute", left: pad, top: 34 + pad, right: pad, bottom: pad + 24, borderRadius: 10, background: `linear-gradient(135deg, ${T.line}, ${T.bar})`, opacity: 0.7 }} />);
    rows.push(<div key="c" style={{ position: "absolute", left: pad, bottom: pad, width: (w - 2 * pad) * 0.5, height: 9, borderRadius: 4.5, background: T.line, opacity: 0.55 }} />);
  }
  return <>{rows}</>;
}

function Win({ win, t }) {
  const [x, y, w, h] = rectAt(win.keys, t);
  let z = win.z || 1;
  (win.zSteps || []).forEach(([tz, v]) => { if (t >= tz + 0.35) z = v; });
  const T = TONES[win.tone] || TONES.violet;
  const dot = (c, i) => <div key={i} style={{ width: 11, height: 11, borderRadius: 6, background: c }} />;
  return (
    <div style={{ position: "absolute", left: x, top: y, width: w, height: h, borderRadius: 14, background: T.soft, boxShadow: `0 0 0 1.5px ${T.edge}, 0 14px 34px oklch(30% 0.12 310 / 0.22), 0 3px 8px oklch(30% 0.12 310 / 0.16)`, overflow: "hidden", zIndex: z }}>
      <div style={{ position: "absolute", left: 0, top: 0, right: 0, height: 34, background: T.bar, display: "flex", alignItems: "center", gap: 7, paddingLeft: 14 }}>
        {["oklch(70% 0.15 25)", "oklch(82% 0.14 85)", "oklch(74% 0.16 145)"].map(dot)}
        <div style={{ position: "absolute", left: 0, right: 0, textAlign: "center", fontFamily: FONT_BODY, fontWeight: 650, fontSize: 14, color: "oklch(34% 0.05 300)", letterSpacing: "0.01em" }}>{win.title}</div>
      </div>
      <Lines kind={win.kind || "text"} w={w} h={h} tone={win.tone} />
    </div>
  );
}

export function PanelyGlyph({ size = 20, color = INK }) {
  // the menu-bar image from the app: a tall pane on the left, two stacked panes on the right (18 x 18, y up)
  const r = 1.6;
  return (
    <svg width={size} height={size} viewBox="0 0 18 18">
      <g transform="translate(0 18) scale(1 -1)" fill={color}>
        <rect x="2" y="3" width="6.5" height="12" rx={r} />
        <rect x="9.5" y="9" width="6.5" height="6" rx={r} />
        <rect x="9.5" y="3" width="6.5" height="5" rx={r} />
      </g>
    </svg>
  );
}

function Menu({ m, t }) {
  const o = expoOut(clamp01((t - m.t0) / 0.28)) * (1 - expoOut(clamp01((t - m.t1) / 0.2)));
  if (o <= 0) return null;
  const right = 18;
  let y = 8;
  const hl = m.hoverAt != null && t >= m.hoverAt;
  const checked = m.checkAt != null && t >= m.checkAt;
  return (
    <div style={{ position: "absolute", right, top: DESK.BAR + 4, width: MENU_W, borderRadius: 12, background: "oklch(98.5% 0.006 310)", boxShadow: "0 0 0 1px oklch(70% 0.03 310 / 0.5), 0 24px 56px oklch(25% 0.1 310 / 0.38)", opacity: o, transform: `translateY(${(1 - o) * -8}px)`, padding: "8px 8px 8px", zIndex: 50, height: menuHeight() }}>
      {MENU.map((it, i) => {
        if (it.sep) return <div key={i} style={{ height: 1, margin: "5px 10px", background: "oklch(86% 0.02 310)" }} />;
        const isIgnore = it.id === "ignore";
        const on = isIgnore && hl;
        return (
          <div key={i} style={{ position: "relative", height: MENU_ROW, borderRadius: 7, display: "flex", alignItems: "center", paddingLeft: 26, paddingRight: 14, fontFamily: FONT_BODY, fontWeight: 500, fontSize: 16.5, color: on ? "oklch(99% 0.01 310)" : it.dim ? "oklch(52% 0.03 300)" : INK, background: on ? PURPLE : "transparent" }}>
            {isIgnore && checked && <span style={{ position: "absolute", left: 8, fontSize: 15, fontWeight: 700 }}>✓</span>}
            <span style={{ flex: 1 }}>{it.t}</span>
            {it.sub && <span style={{ opacity: 0.55, fontSize: 15 }}>›</span>}
          </div>
        );
      })}
    </div>
  );
}
function Cursor({ c, t }) {
  if (!c || !c.length) return null;
  let i = 0;
  c.forEach((p, j) => { if (t >= p[0]) i = j; });
  const p = c[i];
  let x = p[1], y = p[2];
  if (i > 0) {
    const q = c[i - 1];
    const k = expoOut(clamp01((t - p[0]) / (p[3] ?? 0.8)));
    x = lerp(q[1], p[1], k); y = lerp(q[2], p[2], k);
  }
  return (
    <svg viewBox="0 0 24 24" width={38} height={38} style={{ position: "absolute", left: x - 3, top: y - 3, zIndex: 60, filter: "drop-shadow(0 2px 3px oklch(20% 0.05 310 / 0.5))" }}>
      <path d="M5 3 L19 12.5 L12.6 13.6 L16.2 20.6 L13.7 21.8 L10.2 14.9 L5 19.4 Z" fill="oklch(99% 0.005 310)" stroke="oklch(18% 0.05 310)" strokeWidth="1.4" strokeLinejoin="round" />
    </svg>
  );
}

function Caps({ c, t }) {
  const dt = t - c.t0;
  if (dt < 0 || t > c.t1 + 0.4) return null;
  const o = expoOut(clamp01(dt / 0.3)) * (1 - clamp01((t - c.t1) / 0.3));
  const keys = c.text.split(" ");
  return (
    <div style={{ position: "absolute", left: 0, right: 0, bottom: c.bottom ?? 36, display: "flex", justifyContent: "center", gap: 10, opacity: o, transform: `translateY(${(1 - o) * 14}px)`, zIndex: 70 }}>
      {keys.map((k, i) => (
        <div key={i} style={{ minWidth: 64, height: 64, padding: "0 18px", borderRadius: 14, background: "oklch(99% 0.004 310)", boxShadow: "0 0 0 2px oklch(80% 0.05 310), 0 5px 0 oklch(80% 0.05 310), 0 14px 28px oklch(25% 0.1 310 / 0.3)", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: FONT_BODY, fontWeight: 650, fontSize: 30, color: INK }}>{k}</div>
      ))}
    </div>
  );
}

export function Desk({ spec, t, radius = 0 }) {
  const { W, H, BAR } = DESK;
  return (
    <div style={{ position: "relative", width: W, height: H, overflow: "hidden", borderRadius: radius, background: "linear-gradient(165deg, oklch(94% 0.035 300), oklch(88% 0.06 290) 60%, oklch(85% 0.07 280))" }}>
      <div style={{ position: "absolute", left: -260, top: 120, width: 900, height: 700, borderRadius: "50%", background: "radial-gradient(closest-side, oklch(97% 0.04 330 / 0.8), transparent)" }} />
      <div style={{ position: "absolute", left: 0, top: 0, right: 0, height: BAR, background: "oklch(98% 0.01 310 / 0.78)", boxShadow: "0 1px 0 oklch(80% 0.03 310 / 0.6)", zIndex: 40 }}>
        {[0, 1, 2, 3].map((i) => <div key={i} style={{ position: "absolute", left: 22 + i * 52, top: 12, width: i === 0 ? 14 : 34, height: 10, borderRadius: 5, background: "oklch(72% 0.03 300)", opacity: 0.55 }} />)}
        {[0, 1, 2].map((i) => <div key={i} style={{ position: "absolute", right: 120 + i * 40, top: 10, width: 20, height: 14, borderRadius: 4, background: "oklch(72% 0.03 300)", opacity: 0.5 }} />)}
        <div style={{ position: "absolute", right: 24, top: 7 }}><PanelyGlyph size={22} /></div>
      </div>
      {(spec.previews || []).map((p, i) => {
        const dt = t - p.t0;
        if (dt < 0 || t > p.t1 + 0.3) return null;
        const o = expoOut(clamp01(dt / 0.25)) * (1 - clamp01((t - p.t1) / 0.25));
        return <div key={i} style={{ position: "absolute", left: p.r[0], top: p.r[1], width: p.r[2], height: p.r[3], borderRadius: 14, background: "oklch(55% 0.22 310 / 0.2)", boxShadow: "inset 0 0 0 3px oklch(50% 0.24 310 / 0.7)", opacity: o, zIndex: 30 }} />;
      })}
      {spec.windows.map((w) => <Win key={w.id} win={w} t={t} />)}
      {spec.areaLabels && spec.areaLabels.map((a, i) => {
        const dt = t - a.t0;
        if (dt < 0 || t > a.t1 + 0.3) return null;
        const o = expoOut(clamp01(dt / 0.35)) * (1 - clamp01((t - a.t1) / 0.3));
        return <div key={i} style={{ position: "absolute", left: a.r[0], top: a.r[1], width: a.r[2], height: a.r[3], borderRadius: 14, boxShadow: `inset 0 0 0 3px oklch(50% 0.24 310 / 0.9)`, opacity: o, zIndex: 31 }}>
          <div style={{ position: "absolute", left: 12, top: 12, fontFamily: FONT_BODY, fontWeight: 650, fontSize: 18, color: "oklch(99% 0.01 310)", background: PURPLE, borderRadius: 999, padding: "6px 16px", whiteSpace: "nowrap" }}>{a.text}</div>
        </div>;
      })}
      {spec.menu && <Menu m={spec.menu} t={t} />}
      {(spec.caps || []).map((c, i) => <Caps key={i} c={c} t={t} />)}
      <Cursor c={spec.cursor} t={t} />
    </div>
  );
}
