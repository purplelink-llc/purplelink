# Product video framework

Turns a storyboard JSON, narration text and real screen captures into a 15 to 40 second promo in two formats (16:9 1920x1080, 9:16 1080x1920) with synthesized narration and burned-in captions, plus a poster PNG and a silent hero loop for the website. Renderer: Remotion (React), run with Node from `~/.nvm/versions/node/v26.2.0/bin`. Narration: `edge-tts` (free, needs network).

```
cd video
npm install                     # first time; Remotion downloads a headless Chrome into node_modules
node render.mjs storyboards/moderntex-promo.json --format both      # or 16x9 | 9x16
# flags: --skip-narrate (reuse cached audio)  --no-hero  --frames (dump one PNG per scene to .cache/frames)
```

Output goes to `video/out/<id>/` (gitignored, never committed): `<id>-16x9.mp4`, `<id>-9x16.mp4`, `<id>-poster.png`, `<id>-hero.mp4`, `<id>-hero.webm` (1280x720, silent, under 1.5 MB each, seamless loop), and `run-log.txt`. Remotion is free for individuals and companies of up to three people; check its license if the studio grows.

## Files

- `storyboards/<id>.json`: the content. `storyboards/<id>.md`: the written storyboard, written first.
- `brand.json`: colors (OKLCH, from `site/styles.css`), font files, logo, fps. Change colors and fonts here only.
- `narrate.py`: per-scene mp3 and word timings into `.cache/<id>/` (cached by text, voice and rate).
- `src/`: presentation. `timeline.js` (scene timing), `scenes.jsx` (title, media, callout, end card), `parts.jsx` (camera, highlight ring, word reveal), `Captions.jsx`, `theme.js` (easing and per-format safe areas).
- `render.mjs`: the CLI.

## Storyboard schema

```
{ "id", "title", "voice": "en-US-AndrewNeural", "rate": "+4%",
  "hero": { "scene": 1, "seconds": 6 },
  "scenes": [ { "type": "title|clip|still|callout|endcard",
    "src": "path from video/", "text": "on-screen headline", "narration": "spoken text, written as spoken",
    "layout": "side|bleed", "fit": "contain|cover",
    "zoom": { "from": 1, "to": 1.1, "x": 0.5, "y": 0.45 },
    "highlight": { "x": 0.5, "y": 0.1, "w": 0.4, "h": 0.8, "cue": "word" },
    "items": [ { "title", "detail", "cue" } ],        // callout rows
    "lines": [], "url": "",                           // end card
    "vertical": { "zoom": {}, "highlight": {} },      // overrides applied only in 9:16
    "seconds": 5, "tail": 0.3, "captions": true } ] }
```

Coordinates are fractions of the media (0 to 1). `cue` is a spoken word: the ring or row appears as that word starts. `seconds` is a minimum; scenes last as long as the narration plus 0.3 s lead and `tail` (default 0.3 s). `clip` accepts `.mp4/.mov/.webm` (`trim` = frames to skip); `still` is an image.

## Change copy, assets, colors, duration

- Copy: edit `text`, `narration`, `items`, `lines` in the storyboard, then re-run (narration re-synthesizes only for changed scenes).
- Assets: change `src`. Media keeps its true proportions; it is never stretched. Zoom is cropped inside the window frame.
- Colors and fonts: `brand.json`. Fonts are read from `site/assets/fonts/` (self-hosted woff2, latin subset); to use another file, copy it there and point `brand.json` at it.
- Duration: shorten narration, or raise `seconds` or `tail` for a longer hold. Keep the total between 15 and 25 seconds; go to 30 to 40 only when the story needs it. Do not add scenes to fill time.
- Voice: `voice` and `rate`. Andrew (warm, confident) is default; `en-US-AriaNeural` reads more like a news announcer.

## Add a product

1. Write `storyboards/<id>.md` first: per scene, what the viewer sees, what they should understand, on-screen copy, duration, link to next scene. Order: hook (problem or benefit), product in a window, two or three feature moments each with one benefit, closing line with logo and URL that holds long enough to read.
2. Copy `moderntex-promo.json`, replace copy and `src`. Use only facts from `site/llms.txt` and the product page. No statistics, ratings, testimonials or user counts.
3. Render, then check frames with `--frames` (text overflow, safe margins, one focal point per scene, nothing clipped) before sharing.

## Recording clips

- Record the app window only, not the desktop. No menu bar, Dock, notifications or other windows.
- Use an invented sample manuscript. No real names, unpublished work, emails, file paths with your username, or license keys on screen.
- Record at 2x (Retina), 30 or 60 fps, at least 1440 px wide; hold each action for two seconds before and after. Move slowly; the renderer adds the zoom and highlight, so do not add cursor effects.
- Stills: export the window at 2x. Anything above 1.6x zoom needs a source at least 1400 px wide; the renderer warns otherwise.

## Safe zones

16:9 keeps 120 px side and 90 px top margins, captions 70 px from the bottom. 9:16 keeps the top 210 px and bottom 410 px clear of Shorts, Reels and TikTok interface overlays; captions sit above that band. Captions are 48 px (16:9) and 58 px (9:16) semi-bold white on near-black.

## Approval rule

Nothing is uploaded or posted without the owner's explicit yes. Rendering only writes to `video/out/`. To publish, queue the file through the approval queue (`scripts/queue/approval_queue.py`); this framework never calls it.
