// Shared three.js kit for Remotion videos (Keyfeel pilot, daily how-to app scene).
// Rules learned in the pilot (2026-11-07):
//  - No @react-three/postprocessing: EffectComposer renders a blank canvas under Remotion's frame capture. Tone mapping
//    is done by the renderer (NeutralToneMapping, see GL) and the film look is a 2D layer on top (Grade).
//  - Imperative mesh updates (instance matrices) go in useLayoutEffect, or the frame is captured before they apply.
//  - Every motion is a pure function of the frame, so frames render the same in any tab and any order.
//  - Render with chromiumOptions { gl: "angle" } on macOS (GPU); the default swiftshader is CPU-only and slow.
import React, { useEffect, useLayoutEffect, useMemo, useState } from "react";
import * as THREE from "three";
import { AbsoluteFill, Easing, continueRender, delayRender, staticFile } from "remotion";
import { useThree } from "@react-three/fiber";
import { Environment, Lightformer, RoundedBox } from "@react-three/drei";
import { clamp01, expoOut } from "../theme.js";

export const ease = { out: expoOut, move: Easing.bezier(0.65, 0, 0.35, 1) };
export const span = (t, a, b, e = ease.out) => e(clamp01((t - a) / (b - a)));
export const GL = { antialias: true, preserveDrawingBuffer: true, toneMapping: THREE.NeutralToneMapping, toneMappingExposure: 1.0 };

// Canvas-drawn textures, built once after the named images load. `draw(imgs, make)` returns any object of textures;
// make(drawFn, w, h) paints a canvas and wraps it as an sRGB texture.
export function useCanvasTextures(srcs, draw) {
  const [handle] = useState(() => delayRender("three textures"));
  const [tex, setTex] = useState(null);
  const key = srcs.join("|");
  useEffect(() => {
    const make = (fn, w, h) => {
      const c = document.createElement("canvas");
      c.width = w; c.height = h;
      fn(c.getContext("2d"));
      const t = new THREE.CanvasTexture(c);
      t.colorSpace = THREE.SRGBColorSpace;
      t.anisotropy = 8;
      return t;
    };
    Promise.all(srcs.map((s) => new Promise((res) => {
      const img = new Image();
      img.onload = () => res(img);
      img.onerror = () => res(null);
      img.src = staticFile(s);
    }))).then((imgs) => { setTex(draw(imgs, make)); continueRender(handle); });
  }, [handle, key]); // eslint-disable-line react-hooks/exhaustive-deps
  return tex;
}

// Purple wallpaper drawn in code (no stock image).
export function paintWallpaper(g, w = 1600, h = 1000) {
  const gr = g.createLinearGradient(0, 0, w, h);
  gr.addColorStop(0, "#2a0f4a"); gr.addColorStop(0.55, "#5b21b6"); gr.addColorStop(1, "#c4a6f5");
  g.fillStyle = gr; g.fillRect(0, 0, w, h);
  const r = g.createRadialGradient(w * 0.72, h * 0.25, 0, w * 0.72, h * 0.25, w * 0.44);
  r.addColorStop(0, "rgba(255,255,255,0.35)"); r.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = r; g.fillRect(0, 0, w, h);
}

// Softbox studio: one top panel, two side strips, a lavender back fill. Lights only the reflections (no background).
export function Studio({ intensity = 0.9 }) {
  return (
    <Environment resolution={256} frames={1} environmentIntensity={intensity}>
      <color attach="background" args={["#8f8a99"]} />
      <Lightformer form="rect" intensity={2.6} position={[0, 6, 1]} rotation-x={Math.PI / 2} scale={[8, 4, 1]} />
      <Lightformer form="rect" intensity={3.4} position={[-6, 2, 2]} rotation-y={Math.PI / 2} scale={[1.2, 6, 1]} />
      <Lightformer form="rect" intensity={2.2} position={[6, 2.5, -1]} rotation-y={-Math.PI / 2} scale={[1.2, 6, 1]} />
      <Lightformer form="rect" intensity={0.8} color="#d9c8ff" position={[0, 2, -7]} scale={[10, 3, 1]} />
    </Environment>
  );
}

// Camera through keyframes { t, p: position, q: target }: centripetal Catmull-Rom, eased per segment
// (first segment eases out, the rest ease in and out).
export function makeCameraPath(keys) {
  const pos = new THREE.CatmullRomCurve3(keys.map((k) => new THREE.Vector3(...k.p)), false, "centripetal");
  const tgt = new THREE.CatmullRomCurve3(keys.map((k) => new THREE.Vector3(...k.q)), false, "centripetal");
  const u = (t) => {
    for (let i = 0; i < keys.length - 1; i++) {
      const a = keys[i], b = keys[i + 1];
      if (t <= b.t) {
        const f = clamp01((t - a.t) / (b.t - a.t));
        return (i + (i === 0 ? ease.out(f) : ease.move(f))) / (keys.length - 1);
      }
    }
    return 1;
  };
  return (t) => ({ p: pos.getPoint(u(t)), q: tgt.getPoint(u(t)) });
}
export function Rig({ at }) {
  const { camera } = useThree();
  camera.position.copy(at.p);
  camera.lookAt(at.q);
  camera.updateProjectionMatrix();
  return null;
}

// ---------- the laptop (code-built, no model file) ----------
export const BASE = { w: 3.4, h: 0.11, d: 2.35 };
export const HINGE = new THREE.Vector3(0, BASE.h, -BASE.d / 2 + 0.02);
export const LID = { h: 2.22, d: 0.065 };
export const SCREEN = { w: 3.12, h: 1.95, y: LID.h / 2 + 0.03 }; // display area, in lid space
export const ALU = { color: "#d4d6dc", metalness: 0.75, roughness: 0.32, clearcoat: 0.35, clearcoatRoughness: 0.25 };
export const COLS = 14, ROWS = 5;

function Keyboard({ depth }) {
  const ref = React.useRef();
  const key = 0.19, gap = 0.032;
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const width = COLS * key + (COLS - 1) * gap;
  useLayoutEffect(() => {
    const m = ref.current;
    if (!m) return;
    let i = 0;
    for (let r = 0; r < ROWS; r++) {
      for (let c = 0; c < COLS; c++) {
        const d = depth ? depth(r, c) : 0;
        dummy.position.set(-width / 2 + key / 2 + c * (key + gap), BASE.h + 0.012 - d * 0.009, -0.62 + r * (key + gap));
        dummy.updateMatrix();
        m.setMatrixAt(i++, dummy.matrix);
      }
    }
    m.instanceMatrix.needsUpdate = true;
  });
  return (
    <group>
      <mesh position={[0, BASE.h + 0.001, -0.62 + 2 * (key + gap)]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[width + 0.08, ROWS * (key + gap) + 0.06]} />
        <meshStandardMaterial color="#0c0b0f" roughness={0.9} />
      </mesh>
      <instancedMesh ref={ref} args={[null, null, COLS * ROWS]} frustumCulled={false}>
        <boxGeometry args={[key, 0.022, key]} />
        <meshPhysicalMaterial color="#45434d" roughness={0.42} metalness={0.15} clearcoat={0.4} clearcoatRoughness={0.3} />
      </instancedMesh>
    </group>
  );
}

// `angle`: lid rotation about the hinge (PI/2 closed, about -0.2 open). `wall`: wallpaper texture. `depth(r, c)`:
// key press depth 0..1. Children are drawn on the display, centred, in lid space (z just in front of the glass).
export function Laptop({ angle, wall, depth, children }) {
  return (
    <group>
      <RoundedBox args={[BASE.w, BASE.h, BASE.d]} radius={0.05} smoothness={4} position={[0, BASE.h / 2, 0]}>
        <meshPhysicalMaterial {...ALU} />
      </RoundedBox>
      <mesh position={[0, BASE.h + 0.0012, 0.79]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[1.3, 0.62]} />
        <meshPhysicalMaterial color="#b9bbc2" metalness={0.7} roughness={0.42} />
      </mesh>
      <Keyboard depth={depth} />
      <group position={HINGE} rotation={[angle, 0, 0]}>
        <RoundedBox args={[BASE.w, LID.h, LID.d]} radius={0.04} smoothness={4} position={[0, LID.h / 2, -LID.d / 2]}>
          <meshPhysicalMaterial {...ALU} />
        </RoundedBox>
        <mesh position={[0, LID.h / 2, 0.0015]}>
          <planeGeometry args={[BASE.w - 0.08, LID.h - 0.08]} />
          <meshPhysicalMaterial color="#060608" roughness={0.12} clearcoat={1} />
        </mesh>
        <group position={[0, SCREEN.y, 0.004]}>
          {wall && (
            <mesh>
              <planeGeometry args={[SCREEN.w, SCREEN.h]} />
              <meshBasicMaterial map={wall} toneMapped={false} />
            </mesh>
          )}
          {children}
        </group>
      </group>
    </group>
  );
}

// Film look as a 2D layer: soft vignette plus monochrome grain re-seeded 24 times a second (deterministic).
export function Grade({ t, grain = 0.09, vignette = 0.22 }) {
  const seed = Math.floor(t * 24) % 97;
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <AbsoluteFill style={{ background: `radial-gradient(ellipse 75% 70% at 50% 46%, rgba(0,0,0,0) 55%, rgba(34,12,52,${vignette}) 100%)` }} />
      <svg width="100%" height="100%" style={{ position: "absolute", inset: 0, mixBlendMode: "overlay", opacity: grain }}>
        <filter id="grade-grain"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed={seed} stitchTiles="stitch" /><feColorMatrix type="saturate" values="0" /></filter>
        <rect width="100%" height="100%" filter="url(#grade-grain)" />
      </svg>
    </AbsoluteFill>
  );
}
