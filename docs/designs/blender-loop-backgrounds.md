# Blender loop backgrounds for Hearthside Pixels long-form videos

Status: approved by Ben 2026-11-04 (full 3D skyway, all four asset sets, 320x180 at 6x); built the same day. Owner: Ben. First theme: `racer` ("Music to Run To").
Review notes: `blender-loop-backgrounds-review.md` next to this file.

## Background

Hearthside Pixels is Purplelink's ambient YouTube channel. Its long-form videos (2 h and up) come from
`tools/chiptune-radio`. Each theme in `themes/*.py` draws a 320x180 picture in numpy for time `t`; `longform.py`
enlarges it exactly 6x to 1920x1080 and pipes it to x264. The racer theme draws a flat road scaled row by row to look
3D (the old console "Mode 7" trick), a sky with two skyline strips, a hover craft, and three kinds of event: boosts,
rival overtakes and shooting stars.

On 2026-11-04 Ben asked for more intricate backgrounds: "full 30 second looping renders from blender using high quality
open-source assets". He chose "Pixel-styled Blender" over a clean 3D look, so the channel keeps its pixel identity. The
first racer video (`music-to-run-to-2h`, seed 313) will not be published until it can be re-rendered with this
background. (A render of it is running in the night render queue now as a test of the new music; it will be replaced.)

## Goals

1. A 30 s background loop for the racer, rendered in Blender from CC0 assets and turned into 320x180 pixel art, the
   same art grid as the rest of the channel. Ben approves its look from a 20 s preview.
2. The loop joins end to start with no visible jump: frame 900 rendered by Blender matches frame 0.
3. `render_batch.sh music-to-run-to-2h racer 2 --seed 313` uses it with no new flags.
4. The music does not loop. Only the picture repeats.
5. The racer keeps its events (boosts, rivals, shooting stars) and a craft that reacts to them.
6. Every other theme renders exactly as before.

## Non-goals

- Loops for campfire, study, winter and halloween. The design allows them; this work does not build them.
- A clean, unpixelated 3D look.
- Rendering Blender per video. One loop is rendered once and reused by every racer video until a new version replaces it.
- 4K-native art. `--uhd` keeps doubling the 1080p picture, as today.
- A loop longer than 30 s. A 30 s loop repeats 240 times in 2 h; a 60 s version is a possible v2 if the repeat shows.

## Pipeline at a glance

Blender renders 1280x720 frames -> each 4x4 block is averaged to one pixel (320x180) -> the theme draws the craft and
events on top -> the whole frame is mapped to the theme palette -> `longform.py` enlarges it 6x to 1920x1080.

## Scene concept (racer)

An original elevated night skyway over a harbour city. Nothing from F-Zero or any other game: no existing vehicles,
track shapes, logos or colour schemes.

The loop covers one stretch of road of length L (defined under "How the loop joins") in three parts:

| Part | Share of L | What is seen |
| :--- | :--- | :--- |
| Causeway | 0 to 40 % | Open water on both sides reflecting the city; the skyline and a banded ringed planet low in the sky. |
| Gantry run | 40 to 60 % | Overhead light arches with magenta and cyan strips; signs carry abstract glyphs, never words or brands. |
| Tower canyon | 60 to 100 % | Tall lit towers close on both sides, window lights, antenna beacons, then the road opens back to the causeway. |

Four lanes, magenta and white rumble strips, a centre line and guard-rail light posts, in today's racer colours (violet
ground, magenta, cyan, warm yellow). The camera sits where today's view is: horizon about half way up, road filling the
lower half. Gantry legs and light posts stand outside the road edge, so nothing stands in a lane.

The player's craft stays the numpy craft drawn by `Racer._craft` today (the review found a Blender sprite sheet was more
work than it earns for v1; see "Later").

## Assets and licences

Only CC0 assets are used. CC0 needs no credit and allows monetised video.

At 320x180 most texture detail averages away, so the assets earn their place through silhouettes (building outlines,
gantry shapes), window light patterns and props. Geometry and lights carry the detail.

Sources, each pack's licence page read before it is listed:

| Source | What | Licence | Approx. size |
| :--- | :--- | :--- | :--- |
| Kenney, City Kit (Commercial) and City Kit (Roads) | Buildings and road pieces | CC0 | 10 to 20 MB |
| Quaternius, one or two sci-fi modular packs | Gantries, railings, light posts, props | CC0 | 20 to 80 MB |
| Poly Haven | One night HDRI (2K) for reflections on the water | CC0 | about 10 MB |
| ambientCG | Two or three window, concrete and metal textures (1K) | CC0 | about 20 MB |

Total under 150 MB. Order: Ben approves the sources; each licence page is read; `fetch_assets.py` downloads the files
into `$AMBIENT_LOOPS/_assets/` (outside the repo, which is public), records each file's sha256 on first fetch, and
writes the entry to `tools/chiptune-radio/blender/assets.json` (name, page URL, download URL, author, licence
`CC0-1.0`, date, files, sha256). Later fetches check against the recorded hash. The loop's manifest copies the asset
list, so provenance travels with the loop.

`$AMBIENT_LOOPS` defaults to `/Volumes/Extreme SSD/PurplelinkVideos/ambient/_loops`.

## How the loop joins

The scene is a periodic world: everything along the road repeats with period L.

- **Distance.** L is measured as arc length along the road centre. The camera moves at constant speed along that arc,
  60 m/s, so L = 1800 m and the camera covers exactly L in 900 frames (30 s at 30 fps). Frame 900 is then the same
  picture as frame 0, and the loop is frames 0 to 899.
- **Road shape.** The road's sideways offset is x(u) = A sin(2 pi u / L) + B sin(4 pi u / L + phi), sampled densely and
  re-parameterised by arc length, so the bends at the end lead into the bends at the start. The camera follows the road
  centre, turned to its direction, with a small bank in bends.
- **Scenery.** One period of content is built and copied to cover one period behind the camera to two ahead. View
  distance and fog end at 0.8 L, so the far edge of the copies is never seen.
- **Far background.** Planet, far skyline and sky follow the camera's position but not its rotation, so they drift
  sideways only as the camera turns.
- **Animated light.** Blinking beacons, sign flicker, water ripples and star twinkle are driven by the frame number.
  Every period divides 900 (30, 45, 60, 90, 150, 180, 300 or 450 frames). Nothing uses random time.
- **No history effects.** No particles, no physics, no motion blur. EEVEE renders each frame from scratch with a fixed
  sample count, so frame 0 does not depend on a previous frame.
- **Checks.** `racer_highway.py --check` compares the camera matrix at frames 0 and 900 and lists every driver period,
  failing if one does not divide 900. The build also renders frame 900 and fails if it differs from frame 0 by more
  than a small tolerance (RMS under 0.5 % of full scale, before averaging), and records the measured value in the
  manifest.

## Playback, the craft and the events

The background plays at a constant rate: video frame n shows loop frame n mod 900, where n = round(t x 30). A boost
does not speed the loop up. Skipping frames at a non-integer rate would make the evenly spaced gantries and posts
judder, and it would make the loop's phase depend on the event schedule. Boosts are shown by what the racer already
draws: white speed lines, a blue thruster glow, and the craft's boost pose.

| Today | With the loop |
| :--- | :--- |
| Road and bends | From the loop. |
| Boost | Kept: speed lines, thruster glow; the loop rate does not change. |
| Rival overtake | Kept. Drawn with the per-frame road data (below) so it stays in its lane through bends, and hidden where the occluder mask says a gantry arch is in front. |
| Shooting star | Kept, drawn only on pixels the sky mask marks as open sky. If less than a fifth of the sky band is open at the event's start (in the tower canyon), the star is skipped. |
| Twinkling stars | Baked into the loop. |
| Lean | The craft leans by the loop's bend value, smoothed over 0.5 s, instead of `_curve(t)`. The camera bank is not added again. |
| Craft | The existing numpy craft, unchanged. |

### Per-frame road data

The scene script computes it from the camera and the road curve and stores it with the frames, in 320x180 pixel
coordinates sampled at pixel centres:

- `road_cx[900, 180]` and `road_hw[900, 180]`: road centre x and half-width in pixels for each screen row (NaN above
  the horizon);
- `horizon[900]`: the first row of road;
- `bend[900]`: camera yaw rate scaled to -1..1;
- `sky[900, 180, 320]` (bit-packed): pixels where only the sky is seen, from a Blender render pass;
- `occluder[900, 180, 320]` (bit-packed): pixels where a gantry arch or sign is in front of the road.

A rival z metres ahead is placed on the screen row the camera projects it to, at the lane's x on that row.

## Palette and the pixel step

1. Blender writes each 1280x720 frame as 16-bit PNG with the compositor glow already applied, so neon halos survive.
2. Each 4x4 block is averaged in linear light to get 320x180. Thin lights become one partly lit pixel instead of blinking.
3. The palette is fixed once per loop version: today's racer colours (sky, road, magenta, cyan, yellow, craft and
   overlay colours) plus colours chosen by k-means over 60 sampled loop frames, 40 colours in all, sorted and stored
   with the loop.
4. Each background pixel is mapped to the nearest palette colour in OKLab (so dark violets stay apart), with a 4x4
   ordered (Bayer) dither at a quarter of a palette step. The background is stored as palette indices.
5. At video time the theme draws the rival, speed lines, shooting star and craft on the background, and every
   overlay colour is snapped to the nearest palette colour (no dither). So every on-screen art pixel comes from the same
   palette.

Flicker check (build step): in the 60 sampled frames, the share of pixels that change palette index between
neighbouring frames in regions the camera motion leaves still (the far sky) must be under 2 %. If not, the dither
strength is lowered and the step re-run.

Two other ways were considered. Rendering at full 1080p and reducing colours there reads as posterised 3D, not pixel
art. Rendering straight at 320x180 makes thin lights flicker on and off between frames.

## File formats

`$AMBIENT_LOOPS/racer-highway-v1/`:

- `loop.npz`: `frames` uint8 [900, 180, 320] (palette indices), `palette` uint8 [40, 3] (sRGB), `road_cx` and
  `road_hw` float32 [900, 180], `horizon` int16 [900], `bend` float32 [900], `sky` and `occluder` uint8 bit-packed
  [900, 180, 40]. About 60 MB uncompressed, a few MB compressed.
- `manifest.json`: `name`, `version`, `fps` (30), `frames` (900), `size` ([320, 180]), `blender` (version string),
  `script_sha256`, `assets` (copied from assets.json), `npz_sha256`, `seam_rms`, `flicker`, `rendered` (date).
- `preview.mp4`: the 20 s review clip.

`bgloop.load(name)` returns a small dataclass holding those arrays and the manifest.

## How it fits into `longform.py` and the theme

Opt-in per theme. `Theme` gets one class attribute, `bg_loop = None`; the racer sets `bg_loop = "racer-highway-v1"`.
`frame(t)` still returns a 320x180 picture, so audio, the video stage, mux, fades, `--dark`, `--uhd`, thumbnails and
verify are unchanged.

- `bgloop.py` (new): `load(name)` reads `manifest.json`, checks `loop.npz` against `npz_sha256`, and returns the data.
  Results are cached per process. The video stage runs workers in separate processes (spawn), each building its own
  theme, so each worker loads the loop once: about 60 MB of memory per worker, plus well under a second to hash and
  decompress. The same module holds the build-time step (`pixelate`, palette, flicker check).
- `themes/racer.py`: when `bg_loop` is in use, `frame(t)` takes loop frame n mod 900, draws rival, shooting star, speed
  lines and craft on top, and snaps overlay colours to the palette. The existing numpy road stays in the file.
- Choosing the background: the environment variable `AMBIENT_BG` set to `code` selects the old numpy road. It is read
  once in `longform.main` and passed to the theme through `options` (which already reaches every worker), so the choice
  is part of the render spec. The background used (`racer-highway-v1` plus its sha256, or `code`) is written to the
  render's `video.json`.
- Missing loop: the render stops at start-up, before any audio work, with an error that names the expected folder. It
  never falls back to the old road on its own, so a video cannot silently ship the old look.
- No new command-line flags: `render_batch.sh` passes the same options on to `longform_pub.py`, whose parser would
  reject them.
- `--loop-min` with the racer is refused with a message: it loops the music too, which this theme must not do.
- Thumbnails come from `theme.frame()` in `longform_pub.py`, so they show the loop with no change there.

## Building a loop (the Blender side)

New folder `tools/chiptune-radio/blender/`:

- `assets.json` and `fetch_assets.py` (above).
- `racer_highway.py`: the scene script, run as `Blender -b --factory-startup -P racer_highway.py -- --out DIR`. Written
  and tested against Blender 5.2.3 (the installed version, recorded in the manifest). It builds the scene, renders
  frames 0 to 900, the sky and occluder passes, writes the road data, and has `--check`. Frames already on disk are
  skipped, so a crashed run resumes.
- `build_loop.sh` (starts with `set -u`): fetch, Blender, `bgloop.py pixelate`, the seam and flicker checks, the
  manifest, then the preview through `longform.py --theme racer --seconds 20 --no-music`. It waits while another
  Blender is running, and stops the run if no new frame appears for 5 minutes. Raw 16-bit frames (about 4 GB) are
  deleted after a successful build.

Render engine: EEVEE (fast, and no sampling noise that changes from frame to frame). First step of the build is a
20-frame timing run.

## Render cost and scheduling

- One loop: 901 frames at 1280x720 in EEVEE. Estimate 0.3 to 0.6 s a frame on the Mac mini, so 5 to 9 minutes, plus
  the passes and about a minute for the pixel step. The 20-frame timing run replaces this estimate before the full run.
- It runs once per loop version, as a night render queue (nightq) job or from a session shell.
- A 2 h racer video gets cheaper to draw: a palette lookup and a few shapes per frame instead of the numpy road.

## Determinism

- A finished video depends on the seed, the theme code, the background choice and the loop files. `frame(t)` is a pure
  function of those and `t`, so the parallel chunked video stage works as before.
- The loop is a pinned file, identified by the sha256 in its manifest. A re-render, even with the same script, gets a
  new version name (`racer-highway-v2`). Bit-exact Blender output across machines or versions is not promised, which is
  why the rendered result is pinned.
- The pixel step is plain numpy with no randomness (k-means uses a fixed seed and fixed sampled frames).

## Tests

CI has neither Blender nor the loop. A `conftest.py` in `tools/chiptune-radio` sets `AMBIENT_BG=code` for every test
(autouse fixture), so the existing racer tests (`test_theme_draws_crisp_distinct_frames[racer]`,
`test_events_are_inside_the_video...[racer]`) keep running on the numpy road. `test_bgloop.py` removes it and builds a
small synthetic loop in a temporary folder.

1. `load` reads a synthetic loop and refuses a `loop.npz` whose sha256 does not match.
2. `pixelate` returns only palette colours, gives the same result on two runs, and keeps a flat palette-colour input flat.
3. Racer with a loop: `frame(t)` is deterministic; video frame n shows loop frame n mod 900, including frames 899, 900
   and 901 and through a boost.
4. Every pixel of a racer frame with a loop is a palette colour (overlays included).
5. The rival is drawn inside the road on its lane, and not on occluder pixels; the shooting star only on sky pixels.
6. Missing loop: start-up fails with an error naming the folder; with `AMBIENT_BG=code` the numpy road is drawn.
7. `--loop-min` with the racer is refused.
8. Only the racer sets `bg_loop`; the other themes pass the existing tests unchanged.
9. `longform_pub` makes a racer thumbnail from a synthetic loop.
10. `assets.json`: every entry has a page URL, a sha256 and licence `CC0-1.0`.
11. With the real loop present (skipped elsewhere): the manifest's `seam_rms` and `flicker` are under their limits, and
    the road data's lane lines lie on the rendered road within 1 pixel on 10 sampled frames.

## As built (2026-11-04)

Where the build differs from the plan above:

- **Depth is a second render.** EEVEE has no reliable depth pass with a transparent film, so `racer_highway.py` renders each frame
  twice: colour, then a `material_override` that writes view Z. Depth is stored as a log uint8 code, 255 for sky (`skyway_geom.depth_code`).
- **Fog and bloom are done in numpy, not in Blender.** Fog mixes each 1280x720 pixel towards the scene-linear haze by depth before the 4x4
  mean; bloom (threshold 0.9, gain 0.35, blurs of 1.5 and 5 px) runs on the 320x180 frame in `bgloop.finish`.
- **Tone map, then sky.** Geometry is tone-mapped with 1 - exp(-x); the sky (gradient, 150 twinkling stars, the planet) is drawn by
  `bgloop.Sky` in display space and composited behind it through the alpha. The haze the fog aims at is the inverse-tone-mapped sky, so
  distant geometry melts into the sky with no seam. Star twinkles use whole cycles per loop, so the sky repeats too.
- **Checks at pack time.** `bgloop build` refuses a loop whose last frame differs from the first by more than 0.5 % RMS, or whose sky
  flickers more than 2 % of pixels a frame. The manifest records both, the palette step, the Blender version and each asset's sha256.
- **Size and speed.** About 0.45 s a frame on the Mac mini (0.4 to 1.0 s depending on section), so a 901-frame loop takes under 10 minutes.
  The packed loop is about 104 MB in memory per render worker.
- **The switch.** `longform.build_theme` reads `AMBIENT_BG` once and passes it as `options["bg"]`; a theme built without options (the
  thumbnail tool) falls back to the environment variable. `--loop-min` is refused for loop themes, since the background already loops.
  `video.json` records the background as `racer-highway-v1@<sha256 prefix>` or `code`.
- **Build command.** `bash tools/chiptune-radio/blender/build_loop.sh [render|pack|preview|all]`.

## Later

- Craft rendered in Blender as a sprite sheet, if the numpy craft looks out of place on the new background.
- 60 s loops, or two loops alternated, if the 30 s repeat shows.
- Loops for the other themes.

## Detailed Implementation Plan

Gated on Ben's approval of this design and the asset list.

1. Read the licence pages; write `fetch_assets.py`; fetch; commit `assets.json`.
2. Scene script, in order: road curve and camera (with `--check`); one period of scenery and its copies; sky, planet
   and animated light; compositor glow; sky and occluder passes; road data; frame resume. Time 20 frames.
3. `bgloop.py`: pixel step, palette, flicker check, `load`, dataclass, CLI.
4. `build_loop.sh`; build `racer-highway-v1`; send Ben the 20 s preview; adjust until he approves.
5. Theme: `Theme.bg_loop`, racer loop path, overlay snapping, rival and star masks, lean smoothing; `longform.main`
   reads `AMBIENT_BG`, refuses racer with `--loop-min`, fails fast on a missing loop, writes the background to
   `video.json`.
6. Tests (above), `conftest.py`.
7. PR off `origin/main`, files added by path, CI green, squash-merge; then tell the coordinator session to re-queue the
   racer video.
