// Keyfeel 3D pilot: a code-built MacBook opens, the Settings window lifts off the screen and its layers
// separate (teardown-style), keys are typed with the app's own recorded samples, then it reassembles for the title.
// Every value is a pure function of the frame, so any frame renders the same in any tab, in any order.
import React, { useEffect, useState } from "react";
import * as THREE from "three";
import { AbsoluteFill, Audio, Img, Sequence, continueRender, delayRender, staticFile, useCurrentFrame } from "remotion";
import { ThreeCanvas } from "@remotion/three";
import { useThree } from "@react-three/fiber";
import { ContactShadows } from "@react-three/drei";
import { ease, span, GL, Studio, Laptop, Grade, Rig, makeCameraPath, paintWallpaper, COLS } from "./kit.jsx";
import { brand, C, FONT_DISPLAY, FONT_BODY, lerp } from "../theme.js";

export const PILOT = { W: 1920, H: 1080, FPS: 30, T: 12 };

// ---------- window layers (source px in sounds.webp, 1208x660) ----------
const SRC = { w: 1208, h: 660 };
const WIN_W = 2.5; // world width of the Settings window
const S = WIN_W / SRC.w;
const BG = "rgb(247,247,247)";
const LAYERS = [
  { key: "tabs", rect: [124, 84, 962, 50], lift: 0.42 },
  { key: "tactile", rect: [70, 322, 1068, 104], lift: 0.95, hero: true },
  { key: "cherry", rect: [70, 436, 1068, 88], lift: 0.7 },
  { key: "dome", rect: [70, 534, 1068, 104], lift: 0.55 },
];
const layerPos = ([x, y, w, h]) => [(x + w / 2 - SRC.w / 2) * S, -(y + h / 2 - SRC.h / 2) * S];

function useWindowTextures() {
  const [handle] = useState(() => delayRender("window textures"));
  const [tex, setTex] = useState(null);
  useEffect(() => {
    const img = new Image();
    img.onload = () => {
      const make = (draw, w, h) => {
        const c = document.createElement("canvas");
        c.width = w; c.height = h;
        draw(c.getContext("2d"));
        const t = new THREE.CanvasTexture(c);
        t.colorSpace = THREE.SRGBColorSpace;
        t.anisotropy = 8;
        return t;
      };
      // back plate: the whole window with the lifted pieces painted out
      const back = make((g) => {
        g.drawImage(img, 0, 0);
        g.fillStyle = BG;
        for (const l of LAYERS.slice(1)) g.fillRect(...l.rect);
        g.fillStyle = "rgb(236,236,236)";
        g.fillRect(124, 84, 962, 50);
      }, SRC.w, SRC.h);
      const parts = Object.fromEntries(LAYERS.map((l) => [l.key, make((g) => {
        const [x, y, w, h] = l.rect;
        g.drawImage(img, x, y, w, h, 0, 0, w * 2, h * 2);
      }, l.rect[2] * 2, l.rect[3] * 2)]));
      // wallpaper: brand purple field, drawn in code
      const wall = make((g) => paintWallpaper(g), 1600, 1000);
      const bgTex = make((g) => {
        const gr = g.createLinearGradient(0, 0, 0, 1080);
        gr.addColorStop(0, "#f6f3fa"); gr.addColorStop(0.62, "#ebe6f1"); gr.addColorStop(1, "#ddd6e6");
        g.fillStyle = gr; g.fillRect(0, 0, 16, 1080);
      }, 16, 1080);
      setTex({ back, parts, wall, bgTex });
      continueRender(handle);
    };
    img.onerror = () => continueRender(handle);
    img.src = staticFile("media/sounds.webp");
  }, [handle]);
  return tex;
}

// ---------- typing: deterministic presses with the app's own samples ----------
function rng(seed) { let s = seed >>> 0; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 2 ** 32); }
const PRESSES = (() => {
  const r = rng(20261007);
  const out = [];
  let t = 4.9;
  while (t < 8.1) {
    out.push({ t, col: 1 + Math.floor(r() * (COLS - 2)), row: Math.floor(r() * 4), n: 1 + Math.floor(r() * 15) });
    t += 0.085 + r() * 0.11 + (r() < 0.12 ? 0.22 : 0);
  }
  out.push({ t: t + 0.15, col: 6, row: 4, n: 1, space: true });
  return out;
})();
const pressDepth = (t, p) => {
  const d = t - p.t;
  if (d < 0 || d > 0.16) return 0;
  return d < 0.035 ? d / 0.035 : 1 - ease.out((d - 0.035) / 0.125);
};

// ---------- camera ----------
const KEYS = [
  { t: 0.0, p: [6.24, 4.44, 9.88], q: [0, 0.8, 0] },
  { t: 2.8, p: [2.86, 2.12, 6.6], q: [0, 1.15, 0.1] },
  { t: 4.8, p: [5.25, 1.83, 3.73], q: [0.45, 1.2, 0.45] },
  { t: 8.3, p: [4.58, 1.61, 4.3], q: [0.45, 1.15, 0.45] },
  { t: 10.0, p: [-1.35, 1.91, 7.25], q: [-1.5, 1.0, 0.1] },
  { t: 12.0, p: [-1.25, 1.81, 6.79], q: [-1.45, 1.0, 0.1] },
];
const cam = makeCameraPath(KEYS);
const lidAngle = (t) => lerp(Math.PI / 2 - 0.02, -0.2, span(t, 0.25, 2.0, ease.move));
const keyDepth = (t) => (r, c) => {
  let d = 0;
  for (const p of PRESSES) {
    const hit = p.space ? r === 4 && c >= 4 && c <= 9 : p.row === r && p.col === c;
    if (hit) d = Math.max(d, pressDepth(t, p));
  }
  return d;
};

function SettingsWindow({ t, tex }) {
  const appear = span(t, 1.55, 2.3);
  const out = (i) => span(t, 3.0 + i * 0.09, 4.5 + i * 0.09) * (1 - span(t, 8.35 + (3 - i) * 0.06, 9.55 + (3 - i) * 0.06, ease.move));
  const lift = span(t, 2.8, 4.2) * (1 - span(t, 8.3, 9.5, ease.move));
  const winH = WIN_W * SRC.h / SRC.w;
  const glow = span(t, 4.2, 4.9) * (1 - span(t, 8.2, 8.8));
  return (
    <group position={[0, 0, 0.012 + lift * 0.14]} scale={lerp(0.94, 1, appear)} visible={appear > 0.001}>
      <mesh>
        <planeGeometry args={[WIN_W, winH]} />
        <meshBasicMaterial map={tex.back} alphaTest={0.5} toneMapped={false} transparent opacity={appear} />
      </mesh>
      {LAYERS.map((l, i) => {
        const [x, y] = layerPos(l.rect);
        const [w, h] = [l.rect[2] * S, l.rect[3] * S];
        const e = out(i);
        return (
          <group key={l.key} position={[x + e * 0.05 * i, y, 0.003 + e * l.lift]}>
            {l.hero && (
              <mesh position={[0, 0, -0.004]}>
                <planeGeometry args={[w + 0.028, h + 0.028]} />
                <meshBasicMaterial color={"#9b5cff"} transparent opacity={0.32 * glow} toneMapped={false} depthWrite={false} />
              </mesh>
            )}
            <mesh>
              <planeGeometry args={[w, h]} />
              <meshBasicMaterial map={tex.parts[l.key]} toneMapped={false} transparent opacity={appear} />
            </mesh>
          </group>
        );
      })}
    </group>
  );
}

function Scene({ t, tex }) {
  const { scene } = useThree();
  scene.background = tex.bgTex;
  return (
    <>
      <Rig at={cam(t)} />
      <Studio />
      <Laptop angle={lidAngle(t)} wall={tex.wall} depth={keyDepth(t)}>
        <group position={[0, -0.02, 0]}>
          <SettingsWindow t={t} tex={tex} />
        </group>
      </Laptop>
      <ContactShadows position={[0, 0, 0]} opacity={0.55} scale={12} blur={2.6} far={3.5} resolution={1024} color="#2a1840" />
    </>
  );
}

// ---------- 2D layers ----------
function useFonts() {
  const [handle] = useState(() => delayRender("fonts"));
  useEffect(() => {
    const faces = Object.values(brand.fonts).map((f) => {
      const face = new FontFace(f.family, `url(${staticFile("fonts/" + f.file.split("/").pop())})`, { weight: f.weight });
      document.fonts.add(face);
      return face.load();
    });
    Promise.all(faces).then(() => continueRender(handle), () => continueRender(handle));
  }, [handle]);
}

function Title({ t }) {
  const a = span(t, 9.7, 10.5), b = span(t, 9.85, 10.65), c = span(t, 10.05, 10.85);
  const rise = (k) => ({ opacity: k, transform: `translateY(${(1 - k) * 26}px)` });
  return (
    <AbsoluteFill style={{ justifyContent: "center", paddingLeft: 150 }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 18, maxWidth: 620 }}>
        <Img src={staticFile("media/icon.png")} style={{ width: 104, height: 104, ...rise(a) }} />
        <div style={{ fontFamily: FONT_DISPLAY, fontSize: 132, fontWeight: 560, letterSpacing: "-0.02em", color: C.ink, lineHeight: 1, ...rise(b) }}>Keyfeel</div>
        <div style={{ fontFamily: FONT_BODY, fontSize: 40, fontWeight: 500, color: C.ink, opacity: 0.78 * c, lineHeight: 1.25, transform: `translateY(${(1 - c) * 26}px)` }}>
          Real keyboard-switch sounds as you type.
        </div>
      </div>
    </AbsoluteFill>
  );
}

function Clicks() {
  return PRESSES.map((p, i) => {
    const kind = p.space ? "space-press-01" : `press-${String(p.n).padStart(2, "0")}`;
    const rel = p.space ? "space-release-01" : `release-${String(p.n).padStart(2, "0")}`;
    return (
      <React.Fragment key={i}>
        <Sequence from={Math.round(p.t * PILOT.FPS)} layout="none"><Audio src={staticFile(`audio/tactile/${kind}.wav`)} volume={0.9} /></Sequence>
        <Sequence from={Math.round((p.t + 0.075) * PILOT.FPS)} layout="none"><Audio src={staticFile(`audio/tactile/${rel}.wav`)} volume={0.6} /></Sequence>
      </React.Fragment>
    );
  });
}

export function KeyfeelPilot() {
  useFonts();
  const frame = useCurrentFrame();
  const t = frame / PILOT.FPS;
  const tex = useWindowTextures();
  return (
    <AbsoluteFill style={{ background: "#efeaf4" }}>
      {tex && (
        <ThreeCanvas width={PILOT.W} height={PILOT.H} camera={{ fov: 26, near: 0.1, far: 60, position: KEYS[0].p }}
          gl={GL} dpr={1.5}>
          <Scene t={t} tex={tex} />
        </ThreeCanvas>
      )}
      <Title t={t} />
      <Grade t={t} />
      <Clicks />
    </AbsoluteFill>
  );
}
