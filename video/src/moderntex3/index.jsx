import React from "react";
import { Composition, registerRoot } from "remotion";
import { Demo } from "./Demo.jsx";
import { buildPlan, planTotal } from "./plan.js";
import { brand } from "../theme.js";

// Own entry point: the shared src/Root.jsx stays untouched. build-moderntex3.mjs bundles this file.
const empty = { id: "empty", scenes: [{ id: "x", dur: 3, clip: "x", tag: "", cap: "" }] };
const dims = (format) => (format === "9x16" ? { width: 1080, height: 1920 } : { width: 1920, height: 1080 });

const Root = () => (
  <Composition id="ModernTex3" component={Demo} fps={brand.fps} width={1920} height={1080} durationInFrames={90}
    defaultProps={{ plan: buildPlan(empty), format: "16x9", clips: [] }}
    calculateMetadata={({ props }) => ({ ...dims(props.format), durationInFrames: Math.round(planTotal(props.plan) * brand.fps) })} />
);
registerRoot(Root);
