# Game sprites

Some daily games draw their art as vectors and can swap in generated bitmap art later without a code change.
Each game has its own section below.

## Frontlink

Current art: the unit, effect and flag sprites are cut from `docs/art-source/frontlink-sheet.webp` by `python3 scripts/build_sprites.py frontlink`, which also writes `pack.json`. The isometric terrain tiles on that sheet do not fit the square board, so terrain stays vector.

Frontlink draws every tile, unit and effect as inline SVG built by `site/games/frontlink.js`. The sprite layer lets
WebP art replace any single piece of that drawing.

### How it is wired

- Files live in `site/assets/games/frontlink/`, served as `/assets/games/frontlink/<name>.webp`.
- `site/assets/games/frontlink/pack.json` lists the sprite names that exist, for example
  `{"sprites": ["tile-plains", "unit-tank-player"]}`. The page reads this one file first and only requests the names
  it lists, so a missing file never produces a failed request. It ships with an empty list (vector art only).
- A listed sprite is loaded the first time something needs it. When the image loads, the vector drawing for that
  piece is hidden and the image is shown. If the image fails to load, nothing changes and nothing is logged.
- To add art: put the WebP files in the folder and add their names to `pack.json`. No JavaScript or CSS change.
- The manifest (`SPRITES` in `frontlink.js`) holds name, url, frame size, anchor and frame count for each name.
  CSP already allows same-origin images.

### Sizes and requirements

One frame is 128 x 128 px. A frame is drawn the size of one tile, so 128 px = 1 tile at any screen size. Export
as WebP; lossless or high quality, with alpha where the table says transparent.

| Name | File size | Background | Anchor (px in frame) | Lands at (tile) |
| --- | --- | --- | --- | --- |
| `tile-plains` | 128 x 128 | opaque | 0, 0 | top left |
| `tile-forest` | 128 x 128 | opaque | 0, 0 | top left |
| `tile-mountain` | 128 x 128 | opaque | 0, 0 | top left |
| `tile-water` | 128 x 128 | opaque | 0, 0 | top left |
| `tile-road` | 128 x 128 | opaque | 0, 0 | top left |
| `tile-hq-player` | 128 x 128 | opaque | 0, 0 | top left |
| `tile-hq-enemy` | 128 x 128 | opaque | 0, 0 | top left |
| `unit-infantry-player` | 128 x 128 | transparent | 64, 108 | 50%, 84% |
| `unit-infantry-enemy` | 128 x 128 | transparent | 64, 108 | 50%, 84% |
| `unit-tank-player` | 128 x 128 | transparent | 64, 108 | 50%, 84% |
| `unit-tank-enemy` | 128 x 128 | transparent | 64, 108 | 50%, 84% |
| `unit-artillery-player` | 128 x 128 | transparent | 64, 108 | 50%, 84% |
| `unit-artillery-enemy` | 128 x 128 | transparent | 64, 108 | 50%, 84% |
| `fx-hit` | 384 x 128 (3 frames) | transparent | 64, 64 per frame | tile centre |
| `fx-explosion` | 384 x 128 (3 frames) | transparent | 64, 64 per frame | tile centre |
| `fx-flag` | 128 x 128 | transparent | 30, 118 | 24%, 90% |

Notes for the artist or the prompt:

- Tiles fill the whole frame edge to edge with no border, bevel or grid line; the game adds a soft top-left light
  overlay and a thin edge. Light comes from the top left. Keep the middle of every tile calm enough for a unit to
  read on top of it, in both a light and a dark page theme.
- `tile-road` is a single straight east-west track; it is used for every road tile. The two HQ tiles include their
  own ground and show a small fort with a flag in the team colour (purple for the player, orange for the enemy).
- Units are the figure only. The game draws the team base (round for the player, diamond for the enemy), the ground
  shadow, the HP bar and number, and the "has acted" marker. Keep the figure inside roughly 100 x 90 px of the
  frame so it clears the HP bar at the bottom. Player units face right and enemy units face left, drawn that way in
  the file: the game does not mirror sprites.
- Team colours are purple for the player and orange for the enemy, and must differ by more than hue (the game
  also relies on the base shape and facing direction).
- `fx-hit` and `fx-explosion` are horizontal strips: frame 1 at x 0, frame 2 at x 128, frame 3 at x 256, played in
  order over about 0.3 s and 0.45 s. Both are skipped when the visitor prefers reduced motion.
- `fx-flag` is a flag on a short pole, shown on a base while a unit is capturing it.

## Tanklink

Current art: tanks, barrel, shells, explosion and grass strip are cut from `docs/art-source/tanklink-sheet.webp` by `python3 scripts/build_sprites.py tanklink`, which also writes `pack.json`; the page reads that list and requests only the sprites it names. The backgrounds and the dirt tile are built from the sheet's strips: `build_sprites.py` scales each strip to the full width, continues its own sky gradient upward and its ground downward to reach the 1648 x 848 picture, keys the sky out of the nearer-hills strip, and makes the dirt tile seamless by pasting soft-edged patches with wrap-around. There is a dusk pair (`bg-far`, `bg-near`) for the dark theme and a daytime pair (`bg-far-day`, `bg-near-day`) for the light theme. The barrel is one neutral steel sprite shared by both teams.

Code: `site/games/tanklink.js` (the `SPRITES` manifest and `drawSprite`). Files go in `site/assets/games/tanklink/` and are
served from `/assets/games/tanklink/<name>.webp`. They load lazily, about 400 ms after the page is ready, and each one is
used as soon as it arrives. A file that fails to load is remembered for the rest of the browser session so it is not
requested again on the next page. Until real art exists, the browser console shows one 404 per slot on a fresh visit; that
is expected.

### File rules

- Format: WebP with an alpha channel (lossless or high quality), 8 bits per channel, saved with the exact file names below.
- Cutouts: the background of every sprite except `bg-far` and `terrain-tile` must be fully transparent. If the art is
  made on a magenta (#ff00ff) key background, remove the magenta to transparent before saving. Do not leave a magenta
  fringe: erode the matte one pixel and check the edges on both a light and a dark background (the game has both themes).
- Scale: **3 source pixels per field unit** (`PPU = 3`). A tank is about 30 field units wide, so a tank sprite is about
  108 px wide. The file may be any whole multiple of the size below (2x, 3x), with the same aspect ratio; it is scaled
  to the nominal size when drawn.
- Facing: everything points to the **right** (angle 0). The code rotates and mirrors it.
- Light: paint the light from the upper left. Sprites are shown on both a dark and a light sky.
- No baked-in text, armor bars, labels or ground shadow. The code draws those.

### Slots

| Name | File | Size in px (w x h) | Anchor (px from top-left) | Frames | Notes |
|---|---|---|---|---|---|
| `tank-player` | `tank-player.webp` | 108 x 72 | 54, 69 | 1 | Whole tank without the barrel: tracks, hull and turret, facing right. Anchor is the ground contact point, bottom centre, 3 px inside the tracks so it sits into the ground. The barrel pivot is 9 field units (27 px) above the ground, so keep the turret mount at x = 54, y = 42. |
| `tank-enemy` | `tank-enemy.webp` | 108 x 72 | 54, 69 | 1 | Same layout as the player tank. It is drawn **mirrored** so the enemy faces left. Use a different silhouette marking (not only a different colour). |
| `barrel` | `barrel.webp` | 72 x 24 | 12, 12 | 1 | Pointing right. Anchor is the pivot (a 12 px stub behind it, 60 px in front, so about 20 field units reach the muzzle). Drawn **under** the tank so the turret covers its base. The code slides it back for recoil. |
| `shell-normal` | `shell-normal.webp` | 36 x 18 | 18, 9 | 1 | Pointing right, centred. Turned to follow the flight. |
| `shell-heavy` | `shell-heavy.webp` | 54 x 27 | 27, 13.5 | 1 | Bigger and visibly heavier. |
| `shell-cluster` | `shell-cluster.webp` | 45 x 30 | 22.5, 15 | 1 | The cluster carrier. The three bomblets reuse this art at 60 percent size. |
| `explosion` | `explosion.webp` | 1536 x 256 (6 frames of 256 x 256, left to right) | 128, 128 (centre of each frame) | 6 | The frame is centred on the blast and drawn 2.6 crater radii wide (about 68 units for a normal shell, 114 for a heavy). Frame 1 is the flash, frame 6 is thin smoke. Played over half a second. |
| `bg-far` | `bg-far.webp` | 1648 x 848, opaque | none (stretched over the field) | 1 | Sky and distant hills in one picture. Covers the field plus a 12 unit margin on every side (824 x 424 units at 2 px per unit), because the layer moves a little when the screen shakes. Keep important detail away from the edges. It replaces the code sky, sun or moon, stars, clouds and far hills. |
| `bg-near` | `bg-near.webp` | 1648 x 848, transparent above its hills | none | 1 | Nearer hills only, same size and margin as `bg-far`, with the sky part transparent. Keep the hills below roughly the top third so tanks stay readable. Both themes use it, so paint it in mid tones. |
| `terrain-tile` | `terrain-tile.webp` | 384 x 384, opaque | none | 1 | Seamless in both directions, shown at 128 x 128 field units. Soil and rock texture. The game still lays a light-to-dark gradient, wavy strata, the shadow under the surface, the grass line and the scorch around craters over it, so keep it mid-tone and low contrast. |
| `grass-strip` | `grass-strip.webp` | 192 x 36 | 0, 12 | 1 | Seamless along x, shown 64 units long. The surface line of the ground sits at y = 12 px: blades above it, a few pixels of turf below it. It is cut into 4 unit slices that follow the height of the ground, so keep it free of large features. |

### How to check a new sprite

1. Put the file in `site/assets/games/tanklink/` and serve `site/` (`node scripts/dev-games-server.mjs 8766`).
2. Open `/games/tanklink/` in both themes, fire a shell, a heavy and a cluster, and look at the tank edges against the sky.
3. Check a narrow viewport (375 px): tanks are drawn up to 1.45 times larger there.
4. With `prefers-reduced-motion` on, the sprites still show; only the movement is removed.

### What stays in code

Armor bars and labels, the wind pennants and streaks, smoke and fire on damaged and destroyed tanks (a destroyed tank is
always the code-drawn wreck), the muzzle flash, the shock ring, debris and dust, the shell trail and the scorched craters.
