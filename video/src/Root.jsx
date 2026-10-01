import React from "react";
import { Composition } from "remotion";
import { Promo, Hero } from "./Promo.jsx";
import { PromoV2, HeroV2, PromoLong } from "./V2.jsx";
import { StillPromo, StillHero } from "./Stills.jsx";
import { PRODUCTS } from "./products/index.js";
import { bumperTotal, BUMPER } from "./Bumper.jsx";
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
    <Composition id="PromoV2" component={PromoV2} fps={brand.fps} width={1920} height={1080} durationInFrames={90}
      defaultProps={{ format: "16x9", timing: { scenes: [] }, total: 3, bumper: null }}
      calculateMetadata={({ props }) => { const fmt = FORMATS[props.format]; const tot = props.bumper ? bumperTotal(props.total, props.bumper) : props.total; return { width: fmt.W, height: fmt.H, durationInFrames: Math.round(tot * brand.fps) }; }} />
    <Composition id="PromoLong" component={PromoLong} fps={brand.fps} width={1920} height={1080} durationInFrames={90}
      defaultProps={{ format: "16x9", timing: { scenes: [] }, total: 3, bumper: null }}
      calculateMetadata={({ props }) => { const fmt = FORMATS[props.format]; const tot = props.bumper ? bumperTotal(props.total, props.bumper) : props.total; return { width: fmt.W, height: fmt.H, durationInFrames: Math.round(tot * brand.fps) }; }} />
    <Composition id="StillPromo" component={StillPromo} fps={brand.fps} width={1920} height={1080} durationInFrames={90}
      defaultProps={{ id: "vitae-promo", format: "16x9", timing: { scenes: [] }, bumper: BUMPER }}
      calculateMetadata={({ props }) => { const fmt = FORMATS[props.format]; const total = props.timing.scenes.length ? bumperTotal(PRODUCTS[props.id].build(props.timing).total, props.bumper || BUMPER) : 3; return { width: fmt.W, height: fmt.H, durationInFrames: Math.round(total * brand.fps) }; }} />
    <Composition id="StillHero" component={StillHero} fps={brand.fps} width={1920} height={1080} durationInFrames={240}
      defaultProps={{ id: "vitae-promo", timing: { scenes: [] } }}
      calculateMetadata={({ props }) => ({ durationInFrames: Math.round((props.timing.scenes.length ? PRODUCTS[props.id].build(props.timing).hero.T : 8) * brand.fps) })} />
    <Composition id="HeroV2" component={HeroV2} fps={brand.fps} width={1920} height={1080} durationInFrames={240} defaultProps={{ timing: { scenes: [] } }} />
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
