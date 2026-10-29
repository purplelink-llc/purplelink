import React from "react";
import { Composition, registerRoot } from "remotion";
import { Ad } from "./Ad.jsx";
import { FORMATS, FPS } from "./layout.js";

const Root = () => (
  <Composition
    id="CircledHoopsAd"
    component={Ad}
    fps={FPS}
    width={1080}
    height={1920}
    durationInFrames={90}
    defaultProps={{ format: "9x16", plan: { total: 3, shots: [], caps: [] } }}
    calculateMetadata={({ props }) => ({
      width: FORMATS[props.format].W,
      height: FORMATS[props.format].H,
      durationInFrames: Math.max(1, Math.round(props.plan.total * FPS)),
    })}
  />
);

registerRoot(Root);
