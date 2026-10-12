import React from "react";
import { AbsoluteFill } from "remotion";
import { Desk } from "./PanelyDesk.jsx";
import { SHOTS } from "./panely/shots.js";
import { useFonts } from "./V2.jsx";

// One still of the schematic desk, 1280 x 800 (rendered at 2x by panely-shots.mjs). Rounded corners stay transparent in the PNG.
export function PanelyShot({ shot }) {
  useFonts();
  const s = SHOTS[shot];
  return (
    <AbsoluteFill>
      <Desk spec={s.spec()} t={s.t} radius={24} />
    </AbsoluteFill>
  );
}
