import React from "react";
import { Composition, registerRoot } from "remotion";
import { Trailer } from "./Trailer.jsx";

const Root = () => (
  <Composition
    id="Trailer"
    component={Trailer}
    fps={30}
    width={1920}
    height={1080}
    durationInFrames={90}
    defaultProps={{ format: "16x9", plan: { fps: 30, total: 3, shots: [], captions: [], end: null } }}
    calculateMetadata={({ props }) => ({
      width: props.format === "9x16" ? 1080 : 1920,
      height: props.format === "9x16" ? 1920 : 1080,
      durationInFrames: Math.max(1, Math.round(props.plan.total * 30)),
    })}
  />
);

registerRoot(Root);
