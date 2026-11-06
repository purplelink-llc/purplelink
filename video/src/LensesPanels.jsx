import React from "react";

// Rendered illustrations for the Lenses how-to (scene type "panel"). Nothing here is footage through the glasses:
// each is a drawing of one setting, labelled "Illustration" on screen. `a` runs 0 (before) to 1 (after).
const INK = "oklch(14% 0.07 310)";
const PURPLE = "oklch(50% 0.24 310)";
const SOFT = "oklch(92% 0.03 310)";
const LINE = "oklch(78% 0.05 310)";
const ROOM = "linear-gradient(160deg, oklch(80% 0.07 70), oklch(62% 0.08 40))";
const FONT = 'system-ui, -apple-system, "Plus Jakarta Sans", sans-serif';
const lerp = (x, y, t) => x + (y - x) * t;

function Bars({ x, y, w, rows = 5, color = LINE, h = 14, gap = 30 }) {
  return Array.from({ length: rows }, (_, i) => (
    <rect key={i} x={x} y={y + i * gap} width={w * (i % 3 === 2 ? 0.7 : 1)} height={h} rx="7" fill={color} />
  ));
}

function Tag({ x, y, children, anchor = "start", size = 28, fill = INK, weight = 700 }) {
  return <text x={x} y={y} textAnchor={anchor} fontFamily={FONT} fontSize={size} fontWeight={weight} fill={fill}>{children}</text>;
}

// 1. soft edges: a window running to the edge, with the outer band blurred
function Edges() {
  return (
    <svg viewBox="0 0 900 560" width="100%" height="100%">
      <defs>
        <linearGradient id="eL" x1="0" x2="1"><stop offset="0" stopColor="oklch(35% 0.05 310)" stopOpacity="0.95" /><stop offset="1" stopColor="oklch(35% 0.05 310)" stopOpacity="0" /></linearGradient>
        <linearGradient id="eR" x1="1" x2="0"><stop offset="0" stopColor="oklch(35% 0.05 310)" stopOpacity="0.95" /><stop offset="1" stopColor="oklch(35% 0.05 310)" stopOpacity="0" /></linearGradient>
        <linearGradient id="eT" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="oklch(35% 0.05 310)" stopOpacity="0.95" /><stop offset="1" stopColor="oklch(35% 0.05 310)" stopOpacity="0" /></linearGradient>
        <linearGradient id="eB" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stopColor="oklch(35% 0.05 310)" stopOpacity="0.95" /><stop offset="1" stopColor="oklch(35% 0.05 310)" stopOpacity="0" /></linearGradient>
      </defs>
      <rect x="40" y="40" width="820" height="440" rx="28" fill="white" stroke={INK} strokeWidth="6" />
      <rect x="40" y="40" width="820" height="44" rx="0" fill={SOFT} />
      <Bars x={80} y={120} w={740} rows={9} gap={38} />
      <rect x="40" y="40" width="110" height="440" fill="url(#eL)" />
      <rect x="750" y="40" width="110" height="440" fill="url(#eR)" />
      <rect x="40" y="40" width="820" height="90" fill="url(#eT)" />
      <rect x="40" y="390" width="820" height="90" fill="url(#eB)" />
      <Tag x={450} y={535} anchor="middle" size={30} fill={PURPLE}>The outer band is soft: the lens, not your eyes</Tag>
    </svg>
  );
}

// 2. HiDPI: drawn at 2x, shown at 1x
function Hidpi({ a }) {
  return (
    <svg viewBox="0 0 900 560" width="100%" height="100%">
      <rect x="30" y="90" width="400" height="260" rx="18" fill="white" stroke={INK} strokeWidth="6" />
      <Tag x={230} y={250} anchor="middle" size={120} weight={600}>Aa</Tag>
      <Tag x={230} y={400} anchor="middle" size={30}>Drawn at 3840 x 2160</Tag>
      <g opacity={0.35 + 0.65 * a}>
        <path d="M450 220 H 505" stroke={PURPLE} strokeWidth="8" strokeLinecap="round" />
        <path d="M490 200 L515 220 L490 240" fill="none" stroke={PURPLE} strokeWidth="8" strokeLinecap="round" strokeLinejoin="round" />
      </g>
      <rect x="530" y="130" width="340" height="190" rx="14" fill="white" stroke={INK} strokeWidth="6" />
      <Tag x={700} y={240} anchor="middle" size={84} weight={600}>Aa</Tag>
      <Tag x={700} y={400} anchor="middle" size={30}>Shown at 1920 x 1080</Tag>
      <Tag x={450} y={490} anchor="middle" size={30} fill={PURPLE}>Same size on the glasses, smoother text</Tag>
    </svg>
  );
}

// 3. refresh rate: ticks per same slice of time
function Hz({ a }) {
  const row = (n, y, label, on) => (
    <g>
      <Tag x={40} y={y - 30} size={34}>{label}</Tag>
      <rect x="40" y={y} width="820" height="26" rx="13" fill={SOFT} />
      {Array.from({ length: n }, (_, i) => (
        <circle key={i} cx={40 + 410 / n * 2 * (i + 0.5)} cy={y + 13} r={on ? 11 : 9} fill={on ? PURPLE : LINE} />
      ))}
    </g>
  );
  return (
    <svg viewBox="0 0 900 560" width="100%" height="100%">
      {row(8, 150, "60 Hz: 60 pictures a second", a < 0.5)}
      <g opacity={0.35 + 0.65 * a}>{row(16, 330, "120 Hz: 120 pictures a second", a >= 0.5)}</g>
      <Tag x={450} y={470} anchor="middle" size={30} fill={PURPLE}>Same stretch of time, twice the pictures</Tag>
    </svg>
  );
}

// 4. edge margin: the picture shrinks, the border shows black
function Edge({ a }) {
  const s = lerp(1, 0.9, a);
  const w = 760 * s, h = 400 * s;
  return (
    <svg viewBox="0 0 900 560" width="100%" height="100%">
      <rect x="40" y="40" width="820" height="440" rx="28" fill="black" />
      <rect x={450 - w / 2} y={260 - h / 2} width={w} height={h} rx="16" fill="white" />
      <Bars x={450 - w / 2 + 36} y={260 - h / 2 + 40} w={w - 72} rows={8} gap={40} />
      {["Off", "95%", "90%", "85%"].map((c, i) => (
        <g key={c}>
          <rect x={150 + i * 150} y="498" width="130" height="50" rx="25" fill={c === "90%" && a > 0.5 ? PURPLE : SOFT} />
          <Tag x={215 + i * 150} y="533" anchor="middle" size={26} fill={c === "90%" && a > 0.5 ? "white" : INK}>{c}</Tag>
        </g>
      ))}
    </svg>
  );
}

// 5. Dark Mode: black is see-through
function Dark({ a }) {
  const win = a < 0.5 ? "white" : "oklch(16% 0.02 300)";
  const bar = a < 0.5 ? LINE : "oklch(86% 0.04 300)";
  return (
    <svg viewBox="0 0 900 560" width="100%" height="100%">
      <foreignObject x="30" y="30" width="840" height="440"><div style={{ width: "100%", height: "100%", borderRadius: 28, background: ROOM }} /></foreignObject>
      <rect x="30" y="30" width="840" height="440" rx="28" fill="none" stroke={INK} strokeWidth="6" />
      {a >= 0.5 ? <rect x="110" y="90" width="680" height="320" rx="16" fill={win} opacity="0.92" /> : <rect x="30" y="30" width="840" height="440" rx="28" fill="white" />}
      {a >= 0.5 && <rect x="30" y="30" width="840" height="60" fill="none" />}
      <Bars x={150} y={130} w={600} rows={6} gap={44} color={bar} />
      <Tag x={450} y={525} anchor="middle" size={30} fill={PURPLE}>{a < 0.5 ? "Light: a bright sheet over the room" : "Dark: black pixels are off, the room shows"}</Tag>
    </svg>
  );
}

// 6. Night mode: warm tints for the glasses
function Night({ a }) {
  const chips = [["Off", "white"], ["Warm", "oklch(93% 0.07 80)"], ["Night", "oklch(86% 0.12 60)"], ["Candle", "oklch(78% 0.15 45)"]];
  return (
    <svg viewBox="0 0 900 560" width="100%" height="100%">
      {chips.map(([n, c], i) => (
        <g key={n} opacity={i === 0 ? 1 : 0.3 + 0.7 * a}>
          <rect x={30 + i * 215} y="100" width="195" height="250" rx="20" fill={c} stroke={INK} strokeWidth="5" />
          <Bars x={52 + i * 215} y="135" w="150" rows={4} gap={36} color="oklch(40% 0.03 60 / 0.35)" />
          <Tag x={127 + i * 215} y="405" anchor="middle" size={32}>{n}</Tag>
        </g>
      ))}
      <Tag x={450} y={490} anchor="middle" size={30} fill={PURPLE}>Tints the glasses, not the laptop screen</Tag>
    </svg>
  );
}

// 7. pointer size
function Pointer({ a }) {
  const sc = lerp(1, 2.4, a);
  return (
    <svg viewBox="0 0 900 560" width="100%" height="100%">
      <rect x="40" y="40" width="820" height="400" rx="28" fill="white" stroke={INK} strokeWidth="6" />
      <Bars x={90} y={90} w={720} rows={6} gap={46} />
      <g transform={`translate(430 190) scale(${sc})`}>
        <path d="M0 0 L0 30 L8 23 L14 36 L20 33 L14 20 L25 20 Z" fill="black" stroke="white" strokeWidth="2.5" strokeLinejoin="round" />
      </g>
      <rect x="130" y="478" width="640" height="14" rx="7" fill={SOFT} />
      <circle cx={130 + 640 * (0.15 + 0.7 * a)} cy="485" r="22" fill={PURPLE} />
      <Tag x={450} y={540} anchor="middle" size={28} fill={PURPLE}>Pointer size</Tag>
    </svg>
  );
}

// 8. the Lenses menu (real item titles from the app)
function Menu({ a, tick = 0 }) {
  const hi = Math.floor(tick) % 7;
  const items = ["Optimal", "Mirror", "Mirror, Big Text", "Big Text", "Side by Side", "Cinema", "Mirror, 70%"];
  return (
    <svg viewBox="0 0 900 560" width="100%" height="100%">
      <rect x="150" y="10" width="600" height="540" rx="26" fill="oklch(97% 0.01 310)" stroke={INK} strokeWidth="5" />
      {items.map((t, i) => (
        <g key={t}>
          {i === hi && <rect x="170" y={26 + i * 40} width="560" height="38" rx="9" fill={PURPLE} opacity={a} />}
          <Tag x="196" y={54 + i * 40} size={26} weight={600} fill={i === hi && a > 0.4 ? "white" : INK}>{t}</Tag>
          <Tag x="704" y={54 + i * 40} anchor="end" size={24} weight={500} fill={i === hi && a > 0.4 ? "white" : "oklch(46% 0.04 300)"}>{`⌘${i + 1}`}</Tag>
        </g>
      ))}
      <line x1="170" x2="730" y1="318" y2="318" stroke={LINE} strokeWidth="2" />
      {["Edge Margin", "Night Mode", "Use this display as my glasses"].map((t, i) => (
        <Tag key={t} x="196" y={356 + i * 40} size={26} weight={600}>{t}</Tag>
      ))}
      <line x1="170" x2="730" y1="448" y2="448" stroke={LINE} strokeWidth="2" />
      <Tag x="196" y="484" size={26} weight={600}>Apply on Connect</Tag>
      <Tag x="196" y="522" size={26} weight={600}>Quit Lenses</Tag>
    </svg>
  );
}

const KINDS = { edges: Edges, hidpi: Hidpi, hz: Hz, edge: Edge, dark: Dark, night: Night, pointer: Pointer, menu: Menu };
export function Diagram({ kind, a, tick = 0 }) {
  const K = KINDS[kind] || Edges;
  return <K a={a} tick={tick} />;
}
