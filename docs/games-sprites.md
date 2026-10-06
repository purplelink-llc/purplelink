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
