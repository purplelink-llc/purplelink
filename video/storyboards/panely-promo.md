# Panely promo: storyboard

Target: about 28 seconds including the Purplelink bumpers (product cut about 24 s). 16:9 for the site and YouTube, 9:16 for Shorts, Reels and TikTok. An 8 second silent hero loop and a poster for the Panely page, plus a 15 second cut. Facts come only from `site/panely/index.html` and `site/llms.txt` in the new-apps worktree. No statistics, ratings, testimonials or user counts.

Footage: no screen recording and no screenshot of anyone's screen. Two kinds of picture.
1. The real Settings window, drawn by Panely's own SwiftUI code rendered offscreen with a fake home folder and invented sample data (`video/panely-shots/render.sh`, then `compose_settings.py`). Nothing was launched, no window was shown, no real folder or preference was read.
2. A drawn desktop (`src/PanelyDesk.jsx`, geometry from `src/panely/desk.js`) with invented windows (Draft, Sources, Notes, Chat, Photos, Plan, Callroom), the Panely menu-bar icon and its drop-down, key caps, a cursor and the drag preview. Tile sizes use the same arithmetic as the app (columns and rows, a 10 px margin and gap on a 1280 px desk). It illustrates the idea; it is not a recording of the app, and the page's own hero caption says the same ("An illustration of the idea, not a screenshot of the app").

Voice: en-GB-SoniaNeural at +4% (edge-tts, `narrate.py`, which points edge-tts at Microsoft's new host since the old one answers 403 from 2026-10-10; `EDGE_TTS_HOST=legacy` reverts), as Legroom and Keyfeel. No sound bed.

## 0. Title card (about 1.2 s)
- **Sees:** app icon, "Panely", "Window snapping for Mac."
- **Connects to next:** the drawn desktop rises in with three windows floating loose.

## 1. Hook (about 3 s)
- **Sees:** the desktop, three windows loose, the menu-bar icon.
- **Narration:** "Panely snaps windows into place on your Mac."
- **On-screen copy:** "1  Snapping / Windows snap into place."

## 2. Shortcut and drag (about 4.5 s)
- **Sees:** key caps "control option left" and the Draft window slides to the left half. Then the Sources window is dragged to the top-right corner, a translucent preview shows the quarter, it snaps. Then Notes goes to the bottom-right corner.
- **Understands:** a shortcut or a drag to an edge or corner, with a preview before release.
- **Narration:** "Press a shortcut, or drag a window to a screen edge or corner."
- **On-screen copy:** "2  Shortcut or drag / A preview shows where it will land."

## 3. Layouts and areas (about 4.5 s)
- **Sees:** six windows tile as halves, thirds, quarters, sixths on the name of each. On "area" the picture crossfades to Settings, Custom areas: a ring on the Reading column row and its four percentages.
- **Narration:** "Halves, thirds, quarters, sixths, or an area you draw yourself."
- **On-screen copy:** "3  Layouts / Halves, thirds, quarters, sixths." then "4  Custom areas / Left, top, width and height as percentages."

## 4. Your own shortcuts (about 3.8 s)
- **Sees:** Settings, Shortcuts. The Left third button reads "Press keys...". A ring follows it.
- **Narration:** "Click any shortcut in Settings and press the keys you want."
- **On-screen copy:** "5  Shortcuts / Click a shortcut, press the keys you want."

## 5. Ignored apps (about 3.3 s)
- **Sees:** the menu-bar drop-down with "Never move windows of Callroom" checked. After it closes, two shortcuts tile Draft and Sources; Callroom stays where it was.
- **Narration:** "Choose apps it should never move."
- **On-screen copy:** "6  Ignored apps / Chosen apps are never moved."

## 6. End card (about 4.5 s, settles)
- **Sees:** icon, "Panely", pill "$9.99 once. 7-day free trial.", "purplelink.llc/panely", then the Purplelink bumper.
- **Narration:** "It works offline. Nine ninety-nine once, with a seven day free trial."

## 15 second cut (`panely-promo-15`)
Title, scenes 1 and 2 (hook, shortcut and drag), 3 up to the layouts (no Settings), end card. Same assets, own narration file.

## Media for the site
`site/panely/media/panely-poster.webp` (1920x1080, from the 16:9 cut), `panely-hero.mp4`, `panely-hero.webm` (1280x720, silent, under 1.5 MB each), `panely-promo-720.mp4` (full cut).
