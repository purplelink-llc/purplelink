# Photo to logo: a construction-geometry mark from a photo, in the browser

Status: reviewed (EGM Goldfish review, three Sonnet reviewers: design, implementation readiness, zoom-out,
2026-11-02), findings resolved, built in the same change. **Waiting for Ben's approval before merge.** Owner: Ben.
Port of the LogoForge prototype (`/Volumes/Extreme SSD/LogoForge`, commit 224cb57, design `docs/designs/logoforge.md`
in that repo). Ben asked for this as idea 3 of four uses of LogoForge on 2026-11-02 ("try all four"). The review log
is at the end.

## Concepts brief

**Problem.** A designer on TikTok (@quigsart) showed a way to make a logo from an animal photo: draw concentric circles
for every curve and straight guides at a few repeated angles over the photo, trace the outline only along that
geometry, fill it flat. It takes a designer about an hour. LogoForge, a local Python tool Ben built the same day,
automates it: on the cow photo it gives a 21-segment mark with IoU 0.94 against the subject in 7 seconds. People who
search "turn a photo into a logo" today get AI image generators (a different picture every time, unclear rights) or
vectorisers, which give smooth blobs and usually upload the photo.

**Idea.** A free page, `/tools/photo-to-logo/`, that runs the LogoForge pipeline in the visitor's browser: add a
cutout of a subject, get three marks made of lines and circular arcs, see the construction drawn over the photo,
download an SVG or PNG. The photo never leaves the device, and the page shows that with the converters' byte meter.

**Why it fits.** Free tools are the site's traffic source (`/tools/` lists 40). This one makes a visual result people
share, and the construction overlay is the picture the construction videos (use 2) are built from. It is the first
tool for makers and small businesses rather than researchers; that is a test of a new audience.

**Success measure.** Read 90 days after the first scheduled build publishes the page (record the date here when it
does: *published: not yet*):
- downloads: `tool_outcome` `ok` for the slug, the clearest "a mark someone wanted" signal. Target: 30 by day 90;
- runs: `tool_use` (photos that reached the marks) and runs per pageview;
- turned away: `tool_outcome` `limit`, opaque photos the page could not use (the evidence for a segmentation model);
- Search Console impressions and clicks for the page.

Target queries (no keyword tool is connected to this repo, so no volume estimate): "photo to logo", "turn a photo
into a logo", "logo from a picture", "geometric logo maker", "silhouette logo maker", "animal logo from photo". Fewer
than 10 downloads and 50 impressions by day 90 makes the page a candidate for removal (a manual decision).

## Where the subject mask comes from

LogoForge gets its mask from Apple Vision, which a web page cannot call. Everything after the mask ports directly.

| Option | Result | Chosen |
|---|---|---|
| A. A cutout the visitor already has (PNG or WebP with transparency) | The alpha channel is the mask. Often it *is* Vision: iPhone, iPad and Mac "Copy Subject", macOS Preview "Remove Background" | Yes |
| A2. A photo on a plain background (product shot on white, drawing, silhouette) | Background found from the border colour; no interaction | Yes |
| B. Box plus GrabCut | Built and measured, see below: usable on half of real photos, 1 to 8 s | No |
| C. Click and flood fill by colour | Poor on fur, patterns and shadows | No |
| D. Segmentation model (U2-Netp 4.7 MB, Apache-2.0) in onnxruntime-web | Good on salient subjects; about 15 MB on first use, a second vendored runtime, and the popular background models (RMBG-1.4, 2.0) are non-commercial | Next step if the `limit` count is high |

**B was measured, not guessed.** A JS GrabCut (Gaussian mixture colour models, Boykov-Kolmogorov max-flow) was built
during this review and run on 19 of Ben's photos that LogoForge has Vision masks for, with the box set to the Vision
mask's bounds plus 4%. It reached IoU 0.85 against Vision on 9 of 19 photos; OpenCV's own `grabCut` on the same boxes
reached 8 of 19, so the port was not the limit. The worst cases (0.47, 0.58, 0.61) would make marks of the background.
It took 0.8 to 7.7 s per photo in Node on a Mac. A tool that fails on half its inputs teaches visitors that the tool
is bad, so v1 does not ship it. The implementation and the per-photo numbers are kept outside the repo for a later
attempt (`side-session-notes/.../photo-to-logo-grabcut-gate.md`).

**Opaque photos** get a clear message instead of a mark: how to make a cutout on iPhone or iPad (touch and hold the
subject in Photos, Copy), Mac (Photos: right-click, Copy Subject; or Preview: Tools, Remove Background), Windows 11
(Photos: Edit, Background, Remove), Android (Samsung Gallery and Google Photos on Pixel: touch and hold the subject),
then paste or drop it here. Each one is counted as `tool_outcome` `limit`.

## What the visitor sees

The page follows the tool layout (`back-link`, `tools-hero`, `tool-app`, `tool-prose`, `tool-howto`, `tool-faq`,
`tool-related`), dark by default with the footer's light toggle.

1. **Hero.** One answer-first sentence, then an example figure: the raven photo with its construction drawn over it
   and the finished mark beside it (`example-raven.jpg`, from LogoForge's output for `DSC_6709`, Ben's photo by its
   EXIF creator field).
2. **Input.** A drop zone (click, keyboard, drag, paste) for PNG, WebP, JPG or AVIF, a "Try the sample" button (a
   cutout of the same raven, `sample-raven.webp`, loaded only on click), and the tip: "Best results: a cutout of one
   subject seen from the side."
3. **Progress.** A status line ("Reading the photo", "Finding the outline", "Fitting lines and arcs 12 of 20"),
   `role="status"`.
4. **Marks.** Three picks as a radio group, each a small filled mark. The selected one is shown large, beside the
   construction view: the photo (dimmed) on a canvas with every guide line, every construction circle and the
   outline drawn over it. Pick 1 is selected first.
5. **Colour.** Purple (the site's purple for the current theme), Black, White, as a radio group. The preview tile
   switches to a dark tile for White and a light tile for Black, so the mark stays visible in either theme.
6. **Downloads.** "Download SVG" and "Download PNG" (1024 px, transparent). A line under them: "For a favicon, open the
   PNG in PNG to ICO."
7. **Refusals** (opaque photo, no subject found, more than one large piece, unreadable file) replace the marks with a
   message saying what to do; the drop zone stays usable.

State: `idle` → `working` → `marks` or `refused`. A new photo at any point terminates the worker (which cancels the
run), starts a new one and returns to `working`.

## Architecture

The page is hand-written, not generated by `scripts/gen_converter_pages.py`: its head, topbar and footer are copied
from `/tools/png-to-ico/index.html`, then `scripts/apply_layout.py` and `scripts/fingerprint_assets.py` run as for any
page.

```
site/tools/photo-to-logo/
  index.html            the page
  photo-to-logo.css     page styles
  photo-to-logo.js      page side: input, worker calls, marks, canvas overlay, downloads, meter, analytics
  logo-worker.js        worker: decode, mask, outline, the 20 variants, picks
  logo-geometry.js      pure: geometry, outline, construction, scoring, SVG path (LogoForge stages 2 to 5)
  logo-mask.js          pure: cutout alpha, plain background, clean-up, contour tracing (replaces stage 1)
  sample-raven.webp     the sample cutout (about 900 px, alpha)
  example-raven.jpg     the hero example (construction over the photo)
```

`logo-geometry.js` and `logo-mask.js` are classic scripts that each attach one object (`LogoGeometry`, `LogoMask`) to
`self`; the Node tests load them with `vm.runInContext`, as `convert-core.js` is loaded.

**Script tags and stamps.** `netlify.toml` caches `/tools/*` scripts as immutable, so every script URL carries a
`?v=` stamp from `fingerprint_assets.py`, which stamps any `src` or `href` ending in `.js`. The page carries:

```html
<link rel="prefetch" as="script" data-logo-worker href="/tools/photo-to-logo/logo-worker.js">
<link rel="prefetch" as="script" data-logo-mask href="/tools/photo-to-logo/logo-mask.js">
<script src="/tools/photo-to-logo/logo-geometry.js" defer></script>
<script src="/tools/photo-to-logo/photo-to-logo.js" defer></script>
```

The page reads the stamps of `logo-geometry.js` (its script tag) and `logo-mask.js` (its prefetch link) and starts the
worker as `logo-worker.js?v=…&g=<stamp>&m=<stamp>`; the worker calls
`importScripts("/tools/photo-to-logo/logo-geometry.js?v=" + g, "/tools/photo-to-logo/logo-mask.js?v=" + m)`.

**Worker protocol.** Page to worker, one message per photo, the buffer transferred:
`{id, op: "make", buffer, type}`. Worker to page:
- `{id, type: "progress", label, p}` (p from 0 to 1);
- `{id, type: "done", kind: "cutout" | "plain", width, height, photo, picks, dropped, net}` where `photo` is an
  `ImageBitmap` of the working image (transferred), `picks` is up to three `summarise()` objects
  (`variant, eps, angles, iou, legibility, nodes, connectors, arcs, score, ok, path, bbox, guides`), `dropped` is the
  second-largest piece's area as a fraction of the kept one;
- `{id, type: "refused", reason: "opaque" | "empty" | "tiny" | "huge" | "pieces" | "nomark", net}`;
- `{id, type: "error", message, net}` (unreadable file, out of memory).

`net` is `{requests, bytes}` the worker itself sent (it wraps its own `fetch` and `XMLHttpRequest` the way
`convert-worker.js` does). A worker that dies (`onerror`) becomes an error state ("This photo needs more memory than
this tab has. Try a smaller one.").

**Pipeline in the worker.**

1. *Decode.* Files over 50 MB are refused before reading. `createImageBitmap(blob)` decodes (EXIF orientation applied
   by the browser); over 100 MP (16.7 MP on iOS) is refused. The bitmap is drawn onto an `OffscreenCanvas` whose long
   side is at most 1024 px (LogoForge's working size), then closed. A decode failure says which formats work and, for a
   HEIC file, links `/tools/heic-to-jpg/`.
2. *Mask.* `alphaMask`: a cutout when at least 0.5% of pixels have alpha below 16 and at least 1% have alpha 128 or
   more; the mask is alpha at or above 128. Else `plainBackground`: at least 90% of border pixels within RGB distance
   30 of the border's median colour; background is everything 4-connected to the border within distance 40. Else
   refused as `opaque`.
3. *Clean-up* (`cleanMask`, LogoForge's `clean_mask`): largest 8-connected piece, holes filled, closed then opened
   with a disc of radius 0.4% of the image diagonal (exact, by Euclidean distance transform), largest piece again.
   Refused when the kept piece covers under 1% of the frame (`tiny`: nothing to trace at 16 px) or over 97%
   (`huge`: the cutout is the whole frame). When the second piece is over 25% of the kept one (two animals, a gap
   between body and tail), refused as `pieces`, since the mark would silently lose one; between 5% and 25% the marks
   are shown with a note that a smaller piece was left out.
4. *Outline.* Moore-neighbour contour tracing (replacing `cv2.findContours`), resampled every 2 px, 3-point circular
   smoothing, closed-curve RDP per `eps`.
5. *Construction and scoring.* LogoForge stages 3a to 3h and 5 with its parameters and weights (table below), on the
   grid of 5 `eps` values by 4 angle sets. RANSAC uses an sfc32 generator seeded with the FNV-1a hash of the 0/1 mask
   bytes plus the variant's grid position, integer arithmetic only, so a mask gives the same marks in every engine.
   Polygons are filled by a scanline rasteriser (nonzero rule, pixel centres) in `logo-geometry.js`. The optional
   Qwen3-VL feature check is not ported. No pick passing the guard: refused as `nomark`.
6. *Result.* The three picks, summarised.

**LogoForge parameters, as ported** (lengths are fractions of the subject's bounding-box diagonal D):

| Name | Value | | Name | Value |
|---|---|---|---|---|
| `eps` grid | 0.006, 0.01, 0.015, 0.022, 0.03 | | angle sets | 45: 0/45/90/135; 30: every 30; 15: every 15; free: none |
| `arcTol` | 0.006 | | `snapTol` | 12 degrees |
| `rMin`, `rMax` | 0.02, 0.6 | | `parTol` | 6 degrees |
| `minSweep` | 35 degrees | | `concTol` | 0.015 |
| `maxK` | 12 | | `tanTol` | 0.012 |
| `ransacIters` | 120 | | `minLen` | 0.01 |
| join limit | 3 x `eps` | | guard | IoU >= 0.5, nodes <= 40, connectors <= 20% |

Score: `iou + 0.5 legibility - 0.006 nodes - 0.02 connectors - 0.02 distinct_angles - 0.01 off_angle + 0.02 min(arcs, 3)`;
legibility is the mean IoU at 16 and 32 px (area downsampling, threshold 0.5) in a square window 20% wider than the
mask. Picks: Pareto front on (iou, legibility, nodes), then the rest, each new pick differing from earlier ones in
angle set or `eps`.

**Output files** (built in the page from the selected pick):
- SVG: `<svg xmlns viewBox="0 0 1000 1000">` with a `<title>Logo mark</title>` and one `<path fill-rule="nonzero">`
  in the chosen colour, the mark fitted with 8% padding, coordinates rounded half away from zero to 0.1.
- PNG: the same path drawn with `Path2D` on a 1024 px canvas, transparent.
- Name: `<stem>-logo.svg` and `.png`, the stem being the file name without extension, reduced to letters, digits,
  `.`, `-`, `_`, cut to 60 characters, `logo` when empty (a pasted image has no name).

**Compatibility.** `Worker`, `OffscreenCanvas` 2D and `createImageBitmap`: Chrome and Edge 69, Firefox 105, Safari
16.4, the converters' floor. Older browsers get that sentence instead of the tool.

## Privacy

- The meter under the drop zone reads "Bytes of your photo sent anywhere: 0". It counts request bodies sent by the
  page's `fetch`, `sendBeacon` and `XMLHttpRequest` while it is armed, plus what the worker reports in `net`. It is
  armed from the moment a photo is read until the worker answers; analytics beacons are sent after it is disarmed.
  Same code and wording as the converters' shell.
- Beacons carry the slug, the mask route (`cutout` or `plain`) and an outcome word; never names, sizes or pixels.
- The page loads no ad scripts (it carries no `adsbygoogle` or EthicalAds tag, like the converter pages).

## CSP

No change. The worker is `'self'` under `script-src` (there is no `worker-src`). `img-src` allows `'self'` and `data:`
but not `blob:`, so nothing is shown through an object URL: the photo and overlay are drawn on a `<canvas>` from the
worker's `ImageBitmap`, marks are inline SVG elements, and the example and sample are files on the site. Downloads use
an object URL on an `<a download>`, which is a navigation, not an image load. No inline `style=`: SVG `fill` and
`stroke` are presentation attributes, and colour changes swap classes.

## SEO and GEO

- Title "Photo to Logo: a Geometric Mark From Your Photo | Purplelink" (under 65 characters); description under 160
  characters with the no-upload fact.
- JSON-LD `@graph`: `WebApplication` (free offer, `featureList`), `HowTo` equal to the visible steps (markup
  `<li><strong>Name.</strong> Text</li>` in `.tool-howto`), `FAQPage` equal to the visible
  `<details><summary>…</summary><div class="faq-body">…</div></details>`, `BreadcrumbList`.
- Social card: `scripts/gen_og_cards.py` gets the slug in its "apps" background list (image tools), the page's og:image
  points at `/assets/og/cards/tools-photo-to-logo.jpg`, and `python3 scripts/gen_og_cards.py --only tools/photo-to-logo`
  renders it.
- `/tools/` gets a card in the image-tools group and an `ItemList` entry. Related links go to PNG to ICO, PNG to ICNS
  and Metadata Cleaner. PNG to ICO links back through its `related` list in `gen_converter_pages.py`, regenerated.
- FAQ: are photos uploaded; which photo works best; how to make a cutout on each platform; can I use the logo
  commercially (the mark is drawn from your photo; you need the rights to the photo, and should search trademarks
  before relying on a mark; the page claims nothing about the result); how it differs from an AI logo generator; why
  it gives three marks.
- Sitemap and search index come from `scripts/gen_sitemap.py` and the build (`site/search-index.json` and
  `llms-full.txt` are build output and not committed).

## Analytics

The beacon's page path selects the tool; `netlify/lib/tool-counts.mjs` counts `tool_use` as a run whatever its meta,
and counts `tool_outcome` only for `ok`, `error` and `limit`. So:
- `plTrack("tool_use", "photo-to-logo:cutout" | "photo-to-logo:plain")` once per photo that reaches the marks (the meta
  is kept in the event record, which is where the route split is read);
- `plTrack("tool_outcome", "ok")` on the first download per photo;
- `plTrack("tool_outcome", "limit")` when a photo is refused (any `refused` reason);
- `plTrack("tool_outcome", "error")` on a decode or worker error.

The slug goes into `TOOL_SLUGS` in alphabetical order (between `pdf-tools` and `pii-checker`);
`site-tests/test_tool_offers.py` fails until it is there.

## Tests

- `netlify/tests/photo-to-logo.test.mjs` (CI's Node step) ports LogoForge's pytest suite: angle snapping and wrap,
  `angDist`, parallel clustering (weighted mean, wrap at 180), RANSAC circle on noisy points with 20% outliers
  (centre and radius within 1 px, same seed same result), Kasa exact, TLS direction, tangency to 1e-6 and a far line
  left alone, concentric merge, circle touch point, intersections, closed RDP keeps a rectangle's corners, the
  synthetic mask end to end (rectangle body plus disc head: at most 8 segments, an arc, IoU above 0.95, lines on
  allowed angles, same SVG twice), Pareto front, guard, picks differ. New for the browser parts: cutout detection
  (cutout, opaque, tight cutout with 1% clear pixels), plain-background detection (disc on white with noise; a noisy
  photo is not plain), clean-up keeps the largest piece, fills a hole and reports the dropped fraction, the distance
  transform dilation equals a brute-force disc, contour tracing of a rectangle, of a shape with a one-pixel neck and of
  a shape touching the frame edge (the traced polygon filled back covers the mask with IoU above 0.97), the rasteriser's
  area for a known polygon, `fmt` rounding, and `buildVariants` returning three picks for the synthetic mask.
- `site-tests/test_photo_to_logo.py`: canonical URL, one H1, title and description lengths, the four JSON-LD types,
  HowTo and FAQ equal to the visible text, og:image file exists, no `style=` attribute, no emoji, no `adsbygoogle` or
  EthicalAds, the two prefetch links and stamped scripts, slug in `TOOL_SLUGS`, card and `ItemList` entry on
  `/tools/`, sample and example files exist.
- **Parity (recorded, not in CI; Ben's masks stay out of the public repo).** All 19 Vision masks in LogoForge's `out/`
  through the JS pipeline under Node: the best pick's IoU is within 0.012 of Python's on every photo (largest gap:
  cow, 0.930 against 0.942), node counts within 4. Pick order differs on near-ties, as expected from a different
  random generator. The full grid takes 0.4 to 1.3 s per photo in Node on a Mac (it took 1 s per variant until the
  RANSAC inner loop moved to a flat `Float64Array`).
- **Browser check before the PR**, with a local server sending the production CSP: the sample, a cutout PNG, a
  plain-background photo, an opaque photo (refusal and its message), both downloads opened, the meter at 0, no CSP
  errors in the console, keyboard-only use, 375 px width with no horizontal scroll, light and dark.
  *Done 2026-11-02 in Chrome (the app's browser pane) against a server sending `netlify.toml`'s CSP:* the sample gave
  three marks in about 2 s; the opaque example photo was refused with the cutout steps; a dark shape on white went
  through the plain-background route; the SVG had the chosen fill and a cleaned file name; the PNG was 1024 px with a
  transparent corner and every solid pixel #8c16c5; the meter read 0 after each run; no CSP violation in the console
  (only the analytics POSTs a static server rejects); Enter on the sample button and arrow keys across the marks
  worked; no horizontal scroll at 375 px; light theme checked. Not covered: Safari and Firefox, a real phone, and a
  pasted "Copy Subject" from Photos (the paste handler takes any image file on the clipboard; untested with Apple's).

## Rollout

Branch `tools-photo-to-logo` from `origin/main` in `/Volumes/Extreme SSD/_worktrees/Purplelink LLC/photo-to-logo`.
Before the PR: `python3 scripts/gen_converter_pages.py`, `python3 scripts/gen_og_cards.py --only tools/photo-to-logo`,
`python3 scripts/apply_layout.py`, `python3 scripts/fingerprint_assets.py`, `python3 scripts/gen_sitemap.py`, then
`python3 -m pytest -q site-tests` and `node --experimental-test-module-mocks --test netlify/tests/*.test.mjs`. One PR;
CI green; merge after Ben approves this design; published by the next scheduled build (no `[deploy now]`).

## Later

- Segmentation model (option D) if `limit` is a large share of attempts.
- Angles and Detail controls over all 20 variants, a construction replay animation, a construction SVG download: cut
  from v1 by the review; worth adding only if visitors ask or downloads are high.

## Alternatives considered

| Option | Why not chosen |
|---|---|
| Run LogoForge on a server (Modal) | Uploads the photo, which the page's pitch rules out; costs per run |
| Pyodide running the Python code | About 20 MB plus numpy and OpenCV builds |
| Box GrabCut (B) | Measured: half of real photos give a wrong mask |
| A potrace-style smooth vectoriser | Not the look; no circles or guides to show |

## Risks

| Risk | Mitigation |
|---|---|
| Few visitors have a cutout | Sample button; per-platform instructions; `limit` count shows the size of the gap |
| The mark does not look like the animal even at high IoU (a sibling session found this with the iguana) | Three picks, the construction view, and the copy calls it a starting draft |
| A wrong cutout (the subject lift took a leaf or a second animal) | The construction view shows the outline over the photo; the `pieces` refusal catches two large pieces |
| JS port drifts from Python | Ported test suite plus the recorded parity run |
| Slow phones | The grid took 0.4 to 1.3 s in Node on a Mac; the status line counts variants; a phone at a few times slower is still seconds |
| People use someone else's photo or a trademark | FAQ says they need the rights to the photo and should check marks before use |

## Review log (2026-11-02)

Three zero-context Sonnet reviewers read the draft: design critic, implementation readiness, zoom-out.

- **Analytics would double-count runs** (design, readiness; high). `tool_use` with meta `download` counts as a run.
  Fixed: downloads are `tool_outcome ok`, refusals `limit`, errors `error`.
- **Box GrabCut is the main scope risk and unproven on real photos** (zoom-out, design; high). Resolved by measuring:
  built, run on 19 photos against Vision masks, 9 of 19 usable (OpenCV 8 of 19). Cut from v1; plain-background
  detection added as the cheap path for product shots and drawings.
- **Keep/remove brush has no keyboard path** (design, zoom-out). Gone with B.
- **`img-src` has no `blob:`** (design, readiness). Fixed: canvas and inline SVG only; CSP unchanged.
- **Angles/Detail controls, replay, construction SVG, custom colour** (zoom-out). Cut; listed under Later.
- **No example before input** (zoom-out). Added the raven example figure and a sample button.
- **Page production, stamps, worker protocol, generated files, test markup unspecified** (readiness). Specified above.
- **Cutout rule misses tight cutouts** (design). Thresholds lowered to 0.5% clear and 1% solid.
- **Largest piece silently drops parts** (design). `pieces` refusal over 25%, a note from 5%.
- **Meter claim and worker instrumentation** (design). Worker wraps its requests and reports `net`; beacons after
  disarm.
- **White mark invisible on the light theme** (zoom-out, readiness). Preview tile switches with the colour.
- **Success measure cannot separate failure modes** (zoom-out). Downloads, runs, refusals and impressions read
  separately, with targets.
- Not adopted: renaming the meter to "request bodies sent by this page" (design). The converters use the files
  wording, the count covers the page and its worker, and the FAQ explains what is counted.
