// The how-to "app" scene's picture: the product screenshot on a code-built laptop (src/three/kit.jsx). The lid opens,
// the app window lifts off the screen toward the camera, and the camera keeps drifting until the scene ends, so the
// hold never freezes (scripts/howto_gate.py fails freezes over 6 s). Transparent canvas over the scene's Backdrop.
import React from "react";
import { ThreeCanvas } from "@remotion/three";
import { ContactShadows } from "@react-three/drei";
import { ease, span, GL, Studio, Laptop, Rig, makeCameraPath, paintWallpaper, SCREEN } from "../three/kit.jsx";
import { useCanvasTextures } from "../three/kit.jsx";
import { lerp } from "../theme.js";

function windowTexture(img, make) {
  // the screenshot with rounded corners, at its own size (at most 2400 px wide)
  const k = Math.min(1, 2400 / img.width);
  const w = Math.round(img.width * k), h = Math.round(img.height * k);
  const r = Math.round(w * 0.012);
  return { tex: make((g) => {
    g.beginPath();
    g.roundRect(0, 0, w, h, r);
    g.clip();
    g.drawImage(img, 0, 0, w, h);
  }, w, h), aspect: w / h };
}

function AppWindow({ t, win }) {
  const appear = span(t, 0.95, 1.6);
  const lift = span(t, 1.9, 3.1);
  const maxW = SCREEN.w * 0.95, maxH = SCREEN.h * 0.92;
  const w = Math.min(maxW, maxH * win.aspect), h = w / win.aspect;
  return (
    <group position={[0, 0, 0.01 + lift * 0.24]} scale={lerp(0.94, 1, appear)} visible={appear > 0.001}>
      <mesh position={[0.02, -0.035 - lift * 0.03, -0.006]}>
        <planeGeometry args={[w + 0.04, h + 0.04]} />
        <meshBasicMaterial color="#14051f" transparent opacity={(0.22 + lift * 0.18) * appear} toneMapped={false} depthWrite={false} />
      </mesh>
      <mesh position={[0, 0, -0.003]}>
        <planeGeometry args={[w + 0.03, h + 0.03]} />
        <meshBasicMaterial color="#9b5cff" transparent opacity={0.3 * lift * appear} toneMapped={false} depthWrite={false} />
      </mesh>
      <mesh>
        <planeGeometry args={[w, h]} />
        <meshBasicMaterial map={win.tex} toneMapped={false} transparent opacity={appear} />
      </mesh>
    </group>
  );
}

// Camera: settles in from high right over the first 1.8 s, then a slow move across to the left until the scene ends.
const pathFor = (dur, v) => makeCameraPath(v ? [
  { t: 0, p: [4.4, 4.2, 12.6], q: [0, 0.95, 0] },
  { t: 1.8, p: [1.0, 2.6, 12.4], q: [0, 1.12, 0.1] },
  { t: Math.max(2.5, dur), p: [-0.5, 2.5, 12.0], q: [0, 1.12, 0.1] },
] : [
  { t: 0, p: [4.6, 3.4, 7.8], q: [0, 0.9, 0] },
  { t: 1.8, p: [2.1, 1.95, 6.2], q: [0, 1.12, 0.1] },
  { t: Math.max(2.5, dur), p: [-0.85, 1.8, 6.0], q: [0, 1.12, 0.1] },
]);

export function AppLaptop({ img, t, dur, v, width, height }) {
  const tex = useCanvasTextures([img], ([im], make) => ({
    wall: make((g) => paintWallpaper(g), 1600, 1000),
    win: im ? windowTexture(im, make) : null,
  }));
  const cam = React.useMemo(() => pathFor(dur, v), [dur, v]);
  if (!tex) return null;
  const angle = lerp(Math.PI / 2 - 0.02, -0.2, span(t, 0.1, 1.45, ease.move));
  const rise = span(t, 0, 0.9);
  return (
    <ThreeCanvas width={width} height={height} camera={{ fov: 30, near: 0.1, far: 60, position: cam(0).p.toArray() }}
      gl={{ ...GL, alpha: true }} dpr={1.5}>
      <Rig at={cam(t)} />
      <Studio />
      <group position={[v ? 0.0 : 1.1, (rise - 1) * 0.35 + (v ? -1.35 : 0), 0]}>
        <Laptop angle={angle} wall={tex.wall}>
          {tex.win && <AppWindow t={t} win={tex.win} />}
        </Laptop>
      </group>
      <ContactShadows position={[0, 0, 0]} opacity={0.5 * rise} scale={12} blur={2.6} far={3.5} resolution={1024} color="#2a1840" />
    </ThreeCanvas>
  );
}
