import React from "react";
import { Composition } from "remotion";
import { Promo, Hero } from "./Promo.jsx";
import { FORMATS, brand } from "./theme.js";
import { buildTimeline, totalFrames } from "./timeline.js";

const empty = { id: "empty", scenes: [] };

export const Root = () => (
  <>
    <Composition
      id="Promo"
      component={Promo}
      fps={brand.fps}
      width={1920}
      height={1080}
      durationInFrames={90}
      defaultProps={{ format: "16x9", storyboard: empty, timing: { scenes: [] } }}
      calculateMetadata={({ props }) => {
        const fmt = FORMATS[props.format];
        const tl = buildTimeline(props.storyboard, props.timing, brand.fps);
        return { width: fmt.W, height: fmt.H, durationInFrames: Math.max(1, totalFrames(tl)) };
      }}
    />
    <Composition
      id="Hero"
      component={Hero}
      fps={brand.fps}
      width={1920}
      height={1080}
      durationInFrames={180}
      defaultProps={{ storyboard: empty }}
      calculateMetadata={({ props }) => {
        const secs = (props.storyboard.hero && props.storyboard.hero.seconds) || 6;
        return { durationInFrames: Math.round(secs * brand.fps) };
      }}
    />
  </>
);
