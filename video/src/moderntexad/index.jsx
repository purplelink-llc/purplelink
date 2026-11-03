import React from "react";
import { Composition, registerRoot } from "remotion";
import { Ad } from "./Ad.jsx";
import { FORMATS, FPS } from "./layout.js";

const Root = () => (
  <Composition
    id="ModernTexAd"
    component={Ad}
    fps={FPS}
    width={1200}
    height={1200}
    durationInFrames={90}
    defaultProps={{ format: "1x1", plan: { total: 3, scenes: [] } }}
    calculateMetadata={({ props }) => ({
      width: FORMATS[props.format].W,
      height: FORMATS[props.format].H,
      durationInFrames: Math.max(1, Math.round(props.plan.total * FPS)),
    })}
  />
);

registerRoot(Root);
