# Review notes: Blender loop backgrounds

Four zero-context reviewers (Sonnet) read the first draft on 2026-11-04: scope (zoom-out), architecture (design),
implementation readiness against the code, and comprehension/style. This file records what they found and what changed.

## Resolved in the design

| Finding | Reviewer | Change |
| :--- | :--- | :--- |
| Boost playback at 1.9x by skipping frames judders on evenly spaced gantries and posts, and makes the loop phase depend on events; the "frame 0 at t = 30 s" test contradicts it | design, zoom-out, readiness, comprehension | Loop plays at constant rate (frame n mod 900); boosts shown by speed lines, thruster glow, craft pose. |
| Existing racer tests would fail in CI once a loop is required | readiness (blocker) | Autouse `conftest.py` sets `AMBIENT_BG=code`; the two tests named. |
| Blender craft sprite sheet is over-built for v1; lean pops between 7 sprites; underglow lost to alpha threshold | zoom-out, design | Keep the numpy craft; sprite sheet moved to "Later". Lean smoothed over 0.5 s, camera bank not added twice. |
| Overlays drawn in free RGB look pasted on over a dithered palette background | design | Overlay colours snapped to the palette; test that every pixel is a palette colour. |
| Ordered dither shimmers on slow gradients (fog, glow, water) at half a palette step | design | Quarter step, plus a measured flicker check (< 2 % index changes in still regions). |
| Palette source undefined | design, zoom-out, comprehension | Today's racer colours plus k-means over 60 loop frames, 40 colours, fixed per loop version. |
| One "highest skyline row" fails in the tower canyon; the rival has no occlusion | design | Per-pixel sky mask and occluder mask from Blender passes; star skipped when too little sky is open. Gantry legs placed outside the road. |
| Seam check too weak (1.5x median change); temporal effects can break the seam; arc length vs forward coordinate | design, zoom-out | Render frame 900 and require RMS < 0.5 % against frame 0; no motion blur, particles or physics; road parameterised by arc length; build fails and records `seam_rms`. |
| File formats unspecified | readiness | "File formats" section: npz keys, shapes, dtypes; manifest fields. |
| Per-worker loading and memory not described | readiness, design, zoom-out | Cached per process; about 60 MB per worker; spawn behaviour stated. |
| `AMBIENT_BG` is hidden state | readiness, design | Read once in `longform.main`, passed through `options`, recorded in `video.json`. |
| Missing loop found late | design | Fails at start-up, before audio work. |
| `--loop-min` interaction | readiness | Refused for the racer. |
| Thumbnails | readiness | Unchanged path; test that `longform_pub` makes a racer thumbnail from a synthetic loop. |
| Blender version not pinned; render estimate unvalidated; no resume | design, readiness | Blender 5.2.3 recorded; 20-frame timing run first; existing frames skipped on restart. |
| Asset order and first-hash trust | comprehension, design | Order stated; sha256 recorded on first fetch after reading the licence page. |
| Undefined terms (Mode 7, nightq, `$AMBIENT_LOOPS`, `code` background), three scale factors, duplicated plan | comprehension | Terms explained; "Pipeline at a glance"; plan shortened to ordered steps. |

## Not adopted

- **Drop the per-frame road data and draw the rival with today's flat perspective** (zoom-out). The 3D road bends and
  banks, so a flat-perspective rival would leave its lane. The road data comes straight from the camera projection the
  scene script already has, and a test checks it against the rendered road.
- **Drop the downloader** (zoom-out). Kept, small: it records hashes on first fetch, so a later rebuild can prove it
  used the same files.

## Put to Ben

- The zoom-out reviewer's simpler alternative: render only a static background in Blender (sky, water, skyline, no road)
  and keep today's numpy road, rival and craft over it. Much less work and risk, but no 3D road, bends or tower canyon.
- Asset downloads (sources and sizes in the design).
- Art grid: 320x180 (recommended, matches the channel) or 480x270.
- A 30 s loop repeats 240 times in 2 h; noted as a v2 option, not a question.
