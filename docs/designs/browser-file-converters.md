# Browser file converters: one shell, one page per conversion

Status: reviewed (EGM Goldfish review, three Sonnet reviewers: design, implementation readiness, zoom-out,
2026-11-02), findings resolved, and the first three pages built in the same change. Owner: Ben. Ben approved building
it ("add to our web tools"). The review log is at the end.

## Concepts brief

**Problem.** People who search for a single conversion ("heic to jpg", "webp to png") land on converter sites that
upload the file, show ads around a progress bar and keep the file for an hour or a day. Purplelink's audiences care
about where their files go: researchers with unpublished figures, Mac users who chose apps that do not track them.
The site already has the pieces for a converter that never uploads anything: a background-worker pattern and a
"bytes sent" meter in `/tools/metadata-cleaner/`, JSZip and pdf-lib in `site/assets/vendor/`.

**Idea.** A small set of converter pages under `/tools/`, each answering one search ("HEIC to JPG"), all driven by one
shared shell: drop zone, queue, per-file progress, download one or all as a zip. Conversion runs in a Web Worker in
the visitor's tab. The page says so and shows it, with the same network meter the Metadata Cleaner uses.

**Why now.** Filee (KnifeLemon/Filee, an offline converter, 20.6k GitHub stars) shows the demand for private,
local conversion. Ben approved a native Mac converter app (session `filee-mac-app`); these pages are its front door
later, through internal links, and a GEO/SEO guide follows once the app ships.

**Success measure.** Read 90 days after the first scheduled build publishes the pages (new pages on a low-authority
site take weeks to be indexed, so a shorter window would judge pages Google has not ranked yet):
- Search Console impressions and clicks per converter page (the dashboard's GSC card lists landing pages);
- `tool_use` runs per page from `netlify/lib/tool-counts.mjs` (the dashboard's per-tool table);
- runs per pageview, by page.

Target queries, so the read tests something specific: HEIC to JPG, "heic to jpg without uploading", "convert heic to
jpg on windows", "heic to jpg mac"; WebP to PNG, "webp to png for latex", "webp to png transparent"; PNG to ICNS,
"png to icns", "make icns from png", "png to icns online".

**Gate for the next pages.** The second set (below) is a candidate list, not a commitment. It is built when at least
one of the first three pages has 100 Search Console impressions, or 20 runs, by day 28. A page with fewer than 50
impressions and no runs by day 90 is a candidate for removal or for merging into a sibling page; that is a manual
decision (the existing thin-page prune covers photography places and kits, not tools).

## Demand and choice

**What Search Console says.** The dashboard's latest GSC snapshot (`~/.purplelink/traffic/history.json`,
2026-10-04 to 2026-10-31: 13,110 impressions, 330 clicks) has no converter query at all. That is expected (no page
targets one), and it says something about difficulty: the site's authority is in "LaTeX editor for Mac" and academic
guides. Head terms where the top ten are CloudConvert, Convertio, iLovePDF and Adobe are out of reach for now. The
choice favors pairs with large volume and a plain reason for the site's audiences to prefer a local tool, plus one
low-volume, low-competition Mac pair.

**Volume estimates.** No keyword tool is connected to this repo, so these are public Semrush figures found by web
search (US, monthly, 2025), rounded, and treated as an order of magnitude. Difficulty is a judgement from who ranks.

| Pair | Est. volume | Difficulty | Fit | Browser fit | Rank |
|---|---|---|---|---|---|
| HEIC to JPG (and PNG) | 246k, plus "convert heic to jpg" 60k, "heic to jpg converter" 27k | High, long tail ("on Mac", "without uploading") reachable | iPhone and Mac users, highest | libheif WASM, 1.5 MB | 1 |
| WebP to PNG (and JPG) | about 165k, "webp to jpg" about 110k | High | Saving web figures for papers and slides | Native decode, no library | 2 |
| PNG to ICNS | low thousands | Low: few dedicated pages, mostly CLI man pages | Mac developers, exact fit | Pure JS container | 3 |
| PNG to ICO | tens of thousands | Medium | Favicons for lab and personal sites | Pure JS container | 4 |
| JPG/PNG to PDF | very high | Very high (iLovePDF, Adobe, Smallpdf) | Scanned forms and receipts for grants | pdf-lib, already vendored | 5 |
| AVIF to JPG | tens of thousands, rising | Medium | Saving web images | Native decode | 6 |
| CSV to XLSX | tens of thousands | Medium | Research data | JSZip, already vendored | 7 |
| MP4 to MP3, video to GIF | very high | Very high | Weak | See below | Not built |
| Markdown to PDF, PDF merge and split | | | | Already on the site | Linked, not rebuilt |

**First PR: the top three.** HEIC to JPG, WebP to PNG, PNG to ICNS. HEIC and WebP are bets on their long tail (the
target queries above, where "without uploading" and the Mac or LaTeX angle are the site's own reason to rank), not on
the head terms. PNG to ICNS is the pair the site can rank for soon. The brief asked for the top three in one PR; the
zoom-out review's suggestion to ship HEIC alone first was weighed and declined, since WebP and ICNS add little risk on
a shell HEIC already proves.

**Second set, gated.** PNG to ICO, JPG to PDF, AVIF to JPG, CSV to XLSX, on the same shell, when the gate above is
met.

**Not built: video.** ffmpeg.wasm's core is about 31 MB. Its fast multi-threaded build needs
`SharedArrayBuffer`, which needs cross-origin isolation (`Cross-Origin-Embedder-Policy: require-corp`), and that
header breaks the AdSense iframes the site carries by Ben's decision. The single-threaded build turns a two-minute
MP4 into an MP3 in tens of seconds at best on a laptop and much longer on a phone, after a 31 MB download. A later
option is WebCodecs plus a small MP3 encoder, without ffmpeg; it is out of scope here.

**Not rebuilt.** `/tools/markdown-to-pdf/` and `/tools/pdf-tools/` (merge, split) exist. The converter pages link to
them; they are not duplicated.

**One page per pair, not per output.** The HEIC page converts to JPG or PNG with a format switch, and its canonical
URL is `/tools/heic-to-jpg/`, the larger query. A separate `/tools/heic-to-png/` page would repeat the same text with
one word changed, which is the thin programmatic pattern the brief rules out. It gets its own page only if Search
Console later shows "heic to png" impressions landing on the JPG page. The same holds for WebP to JPG.

## What the visitor sees

Each page follows the existing tool-page layout (`back-link`, `tools-hero`, `tool-app`, `tool-howto`, `tool-faq`,
`tool-related`), with dark as the default and the light theme from the footer toggle, like every page.

1. **Answer first.** The hero paragraph says what happens in one or two sentences: "Convert HEIC photos from an iPhone
   to JPG or PNG. The conversion runs in your browser, so the photos are never uploaded." No marketing lines.
2. **The converter.** A drop zone (click, keyboard, drag, paste), an output switch where the pair has one (JPG or PNG;
   JPEG quality; background color for transparent images saved as JPG), the network meter, a queue with one row per
   file (name, size, a progress bar, then the result size and a Download button, or the error in words), and a bar with
   "Download all as .zip" (two or more results) and "Clear".
3. **How it works.** Three or four plain sentences: what reads the file, what writes the result, what happens to
   metadata, where the files go.
4. **Steps** (`tool-howto`, matched by HowTo schema).
5. **Limits.** File size, what the decoder cannot read, what is lost (metadata, HDR, Live Photo motion).
6. **Questions** (`tool-faq`, matched by FAQPage schema).
7. **Related.** The other converters, the Metadata Cleaner and PDF Tools, and the Mac converter app once it exists.

The PNG to ICNS page has one option, "Include an .iconset folder of PNGs" (named for `iconutil`), and notes on the row
when the source is smaller than 1024 px (upscaled icons look soft) or not square (it is centered on a transparent
square).

## Architecture

```
site/tools/convert/                      shared, not a page (no index.html)
  convert-core.js       pure functions, no DOM: format sniffing, output names, ICNS writer, ZIP naming,
                        size limits. Runs in the page, the worker and under node for tests.
  convert-worker.js     the worker: decode, resize, encode; posts progress
  convert-shell.js      the page side: drop zone, queue, worker pool of one, meter, zip, analytics
  convert.css           the shell's styles
site/tools/heic-to-jpg/index.html        one page per pair; data-convert="heic-to-jpg" selects the pipeline
site/tools/webp-to-png/index.html
site/tools/png-to-icns/index.html
site/assets/vendor/libheif-1.23.5/       libheif.js (91 KB), libheif.wasm (1.46 MB), LICENSE, README.txt
```

**Why `/tools/convert/` holds no page.** `site-tests` and `netlify/lib/tool-counts.mjs` treat every directory under
`site/tools/` that holds an `index.html` as a tool page. The shared folder has none, so it is not counted, offered or
indexed.

**Pipeline per pair** (`CONVERSIONS` in `convert-core.js`, keyed by the page's `data-convert`):

| Pair | Accepts | Decode | Encode | Outputs |
|---|---|---|---|---|
| `heic-to-jpg` | .heic, .heif (sniffed by `ftyp` brand) | libheif in the worker, to RGBA | `OffscreenCanvas.convertToBlob` | JPG (quality 0.92 default) or PNG |
| `webp-to-png` | .webp (sniffed `RIFF....WEBP`) | `createImageBitmap(blob)` in the worker | same | PNG or JPG |
| `png-to-icns` | PNG, JPG, WebP | `createImageBitmap` | resize to each size with stepwise halving and `imageSmoothingQuality: "high"`, PNG-encode each, write the ICNS container in `convert-core.js` | .icns |

**Sniffing, not extensions.** Files are identified by their first bytes. A `.jpg` that is really a HEIC (common when
an iPhone photo is renamed) is converted as HEIC; a file that matches nothing gets "This is not a HEIC file" instead of
a decoder error.

**HEIC details.** libheif applies the rotation and mirroring stored in the file (`irot`, `imir`), so portrait photos
come out upright. Only the primary image is converted; a HEIC with several images (a burst) gets a note saying so.
Depth maps, HDR gain maps and Live Photo motion are not carried over. The decoder is loaded once per worker, on the
first HEIC file, never on page load.

**ICNS details.** The container is the four bytes `icns`, a big-endian total length, then one entry per size: a
four-byte type, a big-endian entry length, and a PNG. Ten types, one per file of an `.iconset`: `icp4` 16, `icp5` 32,
`ic07` 128, `ic08` 256, `ic09` 512, `ic10` 1024 (512 at 2x), `ic11` 32 (16 at 2x), `ic12` 64 (32 at 2x), `ic13` 256
(128 at 2x), `ic14` 512 (256 at 2x). `icp6` was in the draft as 64 px and is left out: `iconutil -c iconset` reads it
as 48 px, and Apple's own files do not use it. Each pixel size is drawn once and reused for both types that share it.
macOS 10.8 and later read all ten. A `TOC ` entry is not written; `iconutil` reads files without one. Verified by
running `iconutil -c iconset` on a file the page built: ten PNGs at the expected sizes. A source that is not square is
fitted and centered on a transparent square; JPG sources have no alpha and stay opaque.

**Worker protocol.** Same shape as the Metadata Cleaner, copied rather than extracted (extracting would refactor a
live tool in the same PR): the page sends `{id, pair, name, buffer, opts}` with the buffer transferred, the worker
answers `progress {p, label}` events and one `done {outputs: [{name, mime, bytes}], notes, width, height, net}` or
`error {message, net}`. `net` is the requests and request-body bytes the worker itself made for that file (it wraps its
own `fetch` and `XMLHttpRequest`), which the page adds to its meter. One worker, one file at a time, so a 40-photo batch does not hold 40 decoded images in
memory at once. The worker URL comes from a `<link rel="prefetch" data-convert-worker>` tag so
`scripts/fingerprint_assets.py` stamps it; the page reads the core file's stamp from its `<script src=".../convert-core.js?v=">`
tag and passes it to the worker as `?c=`, which the worker uses in `importScripts`. libheif's two files are not
stamped: they live in a versioned folder under `/assets/vendor/`, which `netlify.toml` caches as immutable. A failed
decoder load is reported on the row and retried on the next HEIC file.

**No worker.** If `Worker`, `OffscreenCanvas` or `createImageBitmap` is missing, the page says so and names the
minimum versions: Chrome and Edge 69, Firefox 105, Safari 16.4 (the first releases with `OffscreenCanvas` 2D, per MDN's
compatibility tables). A main-thread fallback would double the code for browsers from before 2023.

**Limits.** 100 MB per file, 200 files per batch. The pixel count is checked before decoding, from the HEIC image
header or the decoded bitmap's size: 100 MP on a computer, 16.7 MP (iOS Safari's canvas limit) on a phone or tablet,
each with a message that says what to do. A tab killed for memory cannot be caught from inside it; the worker's
`onerror` turns a dead worker into a row error ("needs more memory than this tab has") and the next file gets a fresh
worker. Each result is kept as a Blob (browsers may page Blobs to disk) and the source buffer is released before
encoding. libheif's own security limits stay at their defaults.

**Zip.** "Download all as .zip" builds the archive with JSZip (already vendored) in the page from the result blobs,
`STORE` compression (JPG and PNG do not shrink further), names de-duplicated (`photo.jpg`, `photo (2).jpg`). Above 1 GB
of results the page declines to zip and asks for single downloads.

## CSP: one added keyword

`netlify.toml`'s `script-src` gets `'wasm-unsafe-eval'`, and nothing else changes. No origin is added.

- **Why it is needed.** Browsers treat compiling WebAssembly as a script-src decision. Without `'wasm-unsafe-eval'`
  (or the far broader `'unsafe-eval'`), `WebAssembly.instantiate` throws under the site's CSP. Netlify sends the same
  header on the worker script, so the worker is bound by it too.
- **What it allows.** Compiling and running WebAssembly modules, for every script the policy already allows to run,
  on every page. It does not allow `eval()`, `new Function()` or string timers; those still need `'unsafe-eval'`,
  which the site does not have. (The draft said a module "could not be fetched from elsewhere"; that was wrong:
  `script-src` and `connect-src` list third-party ad and analytics origins, and there is no `worker-src`.)
- **Why sitewide, and why that is acceptable.** Scoping it to the converter paths would need the `/*` policy to skip
  them, and a more specific Netlify header block adds headers rather than replacing the `/*` ones (two CSP headers are
  both enforced). The added exposure is small: `script-src` already has `'unsafe-inline'`, so any script that can run
  on the page can already run arbitrary JavaScript; WebAssembly gives it no capability JavaScript lacks. The converter
  pages themselves carry no ad scripts.
- **Alternatives considered.** libheif's asm.js build (3.2 MB of plain JavaScript) needs no CSP change, but it is twice
  the download and several times slower to decode. Safari 17 and later decode HEIC natively, which covers only Safari;
  most people searching for this are on Windows or Chrome. A server-side conversion would contradict the point of the
  pages.

## Vendored library and license

libheif-js 1.23.5 (`npm view libheif-js` on 2026-11-02: latest 1.23.5, modified 2026-10-04; libheif with the libde265
HEVC decoder, compiled with Emscripten). Both libheif and libde265 are LGPL-3.0. The site ships the unmodified
`libheif-wasm/libheif.js` and `libheif.wasm` with the package's LICENSE and a README giving the source repositories,
the SHA-256 of both files, and the fact that they are replaceable files: the converter calls the library only through
them, so a modified build of the same version can be dropped in under the same names. Hosting a source tarball is not
done in this PR; the README points at the tagged sources. HEVC patents: decoding runs on the visitor's device. This is
an accepted risk, owned by Ben, recorded here; it is not legal advice and no sign-off was sought.

## Privacy and copy

- The hero says the files are not uploaded. The tool area carries the meter: "Bytes of your files sent anywhere: 0",
  then "Bytes sent while converting: 0. Your files stayed on this device." It counts request bodies sent by the
  page's `fetch`, `sendBeacon` and `XMLHttpRequest` and by the worker's own requests, while a batch runs. The usage
  beacon is sent after the meter is switched off. The converter pages load no ad scripts; a third-party script that
  bypassed those functions would not be counted, which is why the copy talks about the files, not about all traffic.
- The FAQ says what the converted file loses: re-encoding through a canvas writes a fresh file, so EXIF (camera, date
  taken, GPS) is not carried over. That is stated as a fact, with a pointer to the Metadata Cleaner for people who want
  to strip metadata from files they keep in their original format.
- Copy rules from `PRODUCT.md`: plain verbs, no emoji, no buzzwords, no em-dash tics, no exclamation marks.

## SEO and GEO

- Title: "HEIC to JPG Converter, in Your Browser | Purplelink", description under 160 characters stating the no-upload
  fact.
- JSON-LD `@graph`: `WebApplication` (free offer, `featureList`), `HowTo` whose steps equal the visible steps,
  `FAQPage` whose questions equal the visible `<details>`, `BreadcrumbList`.
- Answer-first hero paragraph, then a "How it works" section written to be quotable on its own.
- Social card: `scripts/gen_og_cards.py` gains a `tools` section (kicker "Tool", footer "Tools for researchers and Mac
  users", the apps background for the converters). The plan picks tool pages whose card is one of the two generic
  ones, which included `/tools/retraction-check/` and `/tools/resume-review/`; both got their own card in this PR so
  `test_social_cards` stays green. New converter pages are generated with the generic card and then rendered.
- Internal links: the `/tools/` index gets a "Convert images and icons" group; each converter links to its siblings,
  the Metadata Cleaner (HEIC FAQ there currently says "Not yet"; it gains a link to the HEIC page) and PDF Tools.
  Mac app links: none of the four apps allowed in tool-offer cards (`scripts/tool_offers.py`) fits an image
  converter, and Lenscrib's page is `noindex` until it launches, so the first PR carries no offer card. When the
  converter app from `filee-mac-app` has a page, it gets an offer card on all converter pages (the allowlist in
  `site-tests/test_tool_offers.py` grows by one) with internal `utm_source=tool-<slug>` tags, the convention those
  cards already use. `scripts/hub/hub.py utm` is for links that leave the site and is not needed for these pages.
- Sitemap, search index and `llms-full.txt` pick the pages up through their generators; the last two are build output
  and are not committed.

## Analytics

`window.plTrack("tool_use", "<pair>:<output>")` once per batch when at least one file converts, for example
`heic-to-jpg:png`. The beacon's page path makes `track.mjs` bump that tool's daily runs, provided the slug is in
`TOOL_SLUGS` in `netlify/lib/tool-counts.mjs`; the three slugs are added there. No file names, sizes or counts go in
the meta.

## Tests

- `netlify/tests/convert-core.test.mjs` (run by CI's Node step): sniffing on synthetic headers (HEIC brands
  `heic`/`heix`/`mif1`, WebP, PNG, JPEG, junk); output naming and de-duplication; the ICNS writer against a hand-built
  expected byte layout, including total length and every entry's type and length; option validation.
- Same file, HEIC decode: a 502-byte 64x48 HEIC fixture made with `sips` (left half red, right half blue) is decoded
  with the vendored `libheif.js`/`libheif.wasm` under Node, checking dimensions and the two colors. This proves the
  vendored files are the working build, not only that the wrapper code is correct.
- `site-tests/test_converters.py`: each page exists, has a canonical URL, one H1, the three JSON-LD types plus
  breadcrumbs, HowTo steps equal to the visible steps, FAQ entries equal to the visible ones, an own og:image file that
  exists, no inline `style=`, no ads, no emoji, the worker prefetch link and stamped scripts, the slug in `TOOL_SLUGS`,
  a `tool-card` and an ItemList entry on `/tools/`, the vendored decoder with its license, and `'wasm-unsafe-eval'` in
  `script-src` with no `'unsafe-eval'` anywhere.
- The Node test loads `convert-core.js` with `vm.runInNewContext` (the repo is `"type": "module"`), and loads libheif
  from a `.cjs` copy of the vendored file with `wasmBinary` read from disk. The fixture is
  `netlify/tests/fixtures/convert-64x48-red-blue.heic`.
- Pages are written by `scripts/gen_converter_pages.py` (data in `PAGES`, template head and footer from
  `/tools/metadata-cleaner/`), then `apply_layout.py`, as for any page (the build adds the `?v=` stamps).
- Browser check before the PR, served by a local server that sends the production CSP from `netlify.toml` (a plain
  static server sends none, which would not exercise `'wasm-unsafe-eval'`): a 12 MP HEIC and a small one converted
  in 0.4 s including the decoder load, pixel colors checked on the JPG and PNG outputs, WebP transparency kept in PNG
  and filled in JPG, a renamed WebP refused by name, an ICNS checked with `iconutil`, the zip with de-duplicated names,
  the meter, the usage beacon, keyboard focus on the drop zone, 375 px width without horizontal scroll, light and dark.

## Rollout

Branch `tools-converters` from `origin/main` in `/Volumes/Extreme SSD/_worktrees/Purplelink LLC/converters`; one PR
with the first three pages; CI green; squash merge; published by the next scheduled build (no `[deploy now]`: new pages
are not urgent). The second PR (branch `tools-converters-2`, worktree `converters-2`) adds the next four, below.

## Second set: PNG to ICO, JPG to PDF, AVIF to JPG, CSV to XLSX

Ben, 2026-11-02, after the first PR merged: "build the next four now". This replaces the day-28 gate for these four.
The 90-day read stays as the check on all seven. Same shell, same worker, one page per pair, a second PR.

| Pair | Accepts | Work | Outputs |
|---|---|---|---|
| `png-to-ico` | PNG, JPG, WebP | Same resize path as ICNS; the ICO container is written in `convert-core.js` | .ico |
| `jpg-to-pdf` | JPEG, PNG | pdf-lib (the copy PDF Tools already uses, `/assets/vendor/pdf-lib.min.js`, 525 KB, MIT), loaded in the worker on the first file. JPEG bytes go into the PDF unchanged | .pdf, one per picture, plus "Download as one PDF" |
| `avif-to-jpg` | AVIF (sniffed `ftyp` with `avif`/`avis`) | `createImageBitmap`, as WebP | JPG or PNG |
| `csv-to-xlsx` | CSV, TSV, TXT (text, sniffed by extension plus "no NUL byte in the first 4 KB") | Parser and sheet XML in `convert-core.js`; zipped by JSZip in the worker | .xlsx |

**ICO.** Header `00 00 01 00`, count; one 16-byte directory entry per size (width and height bytes, 0 meaning 256;
colors 0; planes 1; 32 bits; data length; offset), then the images. Every entry is a PNG, which Windows Vista and
later, every current browser and macOS read. Windows XP needed BMP entries; it is not supported and the limits say so.
Two size sets: **All sizes** (16, 24, 32, 48, 64, 128, 256; the default, for Windows icons) and **Favicon** (16, 32,
48; a smaller file for a site's `/favicon.ico`). Same notes as ICNS for small and non-square sources. The test parses
the directory back and checks every offset and length, as `parseIcns` does.

**PDF.**
- **Page size**: Fit to picture (the page is the picture at 96 pixels per inch), A4, or US Letter. The default is
  Letter when the browser language is `en-US` or `en-CA`, A4 otherwise. A4 and Letter turn landscape for a landscape
  picture, and the picture is scaled to fit inside a margin.
- **Margin**: None or 12 mm, for A4 and Letter only.
- **JPEG**: embedded as is (DCTDecode), so there is no second round of compression. `jpegInfo` in the core walks the
  markers up to the first scan. It returns `sof`, `precision`, `width`, `height`, `components`, `orientation` (EXIF
  0x0112, default 1), `adobe` (APP14 present), `dpi` (JFIF density, 72 to 2400, else 0) and `embeddable`. It returns
  null for a truncated header.
- **Orientation**: applied with the page's transformation matrix. `pdfMatrix(orientation, W, H, x, y)` maps the
  stored image's unit square into the displayed box, for all eight orientations. For 5 to 8 the displayed width is the
  stored height (`displaySize`). A Node test checks where each orientation puts the stored corners, and a browser check
  renders an orientation-6 file upright. Drawing uses pdf-lib's `newXObject` and `concatTransformationMatrix`, because
  `drawImage` has no matrix.
- **What is embedded as is**: baseline or progressive (SOF0 to SOF2), 8-bit, and gray, RGB, or CMYK with Adobe's
  marker. pdf-lib gives every CMYK JPEG the inverted Decode array (read in the vendored source), which is right for
  Adobe-written files. Other JPEGs (arithmetic-coded, 12-bit, lossless, CMYK without the marker) are drawn by the browser
  and re-encoded at quality 95, with a note on the row. The CMYK fixture renders red, not cyan, in Apple's PDF renderer.
- **PNG**: drawn by the browser first and re-encoded as a plain 8-bit PNG, then embedded by pdf-lib with transparency
  as a soft mask. This applies the PNG's color profile and avoids pdf-lib's own handling of 16-bit, interlaced and
  palette files. PNG pages have a 25 MP cap (`maxPixels`), since pdf-lib holds the decoded pixels in memory.
- **Metadata**: Producer and Creator are set to the tool, so files do not advertise pdf-lib.
- **Combining**: each picture becomes a one-page PDF in its row. With two or more, "Download as one PDF" reads the
  finished rows' PDFs from their Blobs, in list order (errored rows are skipped), and sends them, transferred, to the
  worker as `{id, op: "combine", buffers, libs}`. The worker copies the pages into a single `combined.pdf`
  (`copyPages`, no re-encoding) and answers like any file. The join is refused above 1 GB in total, the same cap as
  the zip. Rows on this page get Move up and Move down buttons, labelled with the file name, so the order can be set
  first; focus stays on the moved row's button and the status line says its new position.
- **Size limits**: JPEGs are not decoded, so only the file size caps them.

**AVIF.** Decoded by the browser: Chrome 85, Firefox 93, Safari 16.4 on macOS 13 or iOS 16 and later. When the
browser cannot decode it, the row names those requirements instead of the generic message. The page does not probe
for support in advance. An animated AVIF (an `avis` brand in `ftyp`) gets the first-frame note. 10-bit and HDR AVIF
are drawn to an 8-bit sRGB canvas, which the limits state.

**CSV.**
- **What counts as a CSV**: `kindOf(head, name)`. Image magic wins. Otherwise a UTF-16 BOM, or a name ending in
  `.csv`, `.tsv`, `.txt` or `.tab` with no NUL byte in the first 4 KB, makes it `csv`. The BOM is checked before the NUL
  check, and short files count, below `sniff`'s 12-byte minimum. The page and the worker both call it.
- **Text decoding**: a UTF-8, UTF-16 LE or UTF-16 BE BOM picks the encoding. Without a BOM the whole file is read as
  strict UTF-8, and as Windows-1252 if that fails (the usual Excel-on-Windows export). A Text encoding option forces
  UTF-8, Windows-1252, ISO-8859-2, Shift JIS, GB18030 or UTF-16. The row says which encoding and which separator were
  used, so a wrong guess is visible.
- **Parsing**: RFC 4180. Quoted fields, `""` escapes, newlines inside quotes, CRLF, LF or CR line ends, ragged rows.
  Lenient: a quote inside an unquoted field is kept as a character. A trailing line break adds no row; blank lines in
  the middle stay as empty rows. A quote that never closes is flagged with a note on the row.
- **Separator**: detected from the first 50 lines outside quotes (comma, semicolon, tab, pipe). The candidate whose
  per-line count is most often the same and above zero wins; ties go to comma, then semicolon, tab and pipe, and tab
  first for `.tsv`. A one-column file comes out as comma. A Separator option sets it by hand.
- **Cells**:
  - A value becomes a number only in plain decimal notation (`^-?(0|[1-9]\d*)(\.\d+)?$`). Scientific notation counts
    only with a decimal point or a signed exponent (`1.5e-3`, `2E+5`), so part numbers and gene names like `12E3`
    stay text.
  - These stay text:
    - A leading zero (`02134`).
    - A leading `+` (phone numbers).
    - A whole number of 12 digits or more. Excel shows those as `1.23457E+11` under General.
    - Anything past 15 significant digits.
    - `.5`, `5.`, `Infinity`, `NaN`, hex, and values with surrounding spaces.
  - `1.10` is stored as 1.1, as Excel would show it; Keep every value as text avoids that.
  - In a semicolon file, `3,14` is read as a decimal comma; `1.234,5` stays text.
  - Everything else is an inline string (`t="inlineStr"`).
  - Dates stay text. Excel's own guessing of dates is the complaint people have, and the FAQ says how to convert a
    column.
  - Nothing is written as a formula, so `=HYPERLINK(...)` in a CSV shows as text: no formula injection.
  - XML-illegal control characters are dropped.
  - Cells over 32,767 characters are cut there, with a note.
  - "Keep every value as text" turns off number detection.
- **Sheet**:
  - One sheet, named from the file (31 characters, no `[]:*?/\`).
  - "First row is a header" (on by default) makes row 1 bold and freezes it.
  - Column widths come from the longest value in the first 1,000 rows, capped at 60 characters.
- **Limits**: 1,048,576 rows and 16,384 columns (Excel's) refuse with a message, and so do more than 5 million cells.
  The parsed rows and the XML both sit in worker memory, and short cells carry about 40 bytes of XML each. The file
  cap is 50 MB for this pair (`maxBytes` in `CONVERSIONS`). The sheet XML is kept as an array of chunks of 1,000 rows
  and handed to JSZip as a Blob, so it never has to be one giant string.
- **Package**: `[Content_Types].xml` (first in the zip), `_rels/.rels`, `docProps/app.xml`, `xl/workbook.xml`,
  `xl/_rels/workbook.xml.rels`, `xl/styles.xml`, `xl/worksheets/sheet1.xml`.
  - `buildXlsxParts(rows, fileName, {header, text, delimiter})` returns them; the worker zips with DEFLATE.
  - The worksheet's elements are in schema order: `dimension`, `sheetViews` (frozen pane), `cols` with `customWidth`,
    then `sheetData`.
  - Styles: 0 normal, 1 bold header, 2 wrapped. Cells with a line break get 2, so they show on several lines.
  - Every `<t>` carries `xml:space="preserve"`.
  - Sheet names: no apostrophe at either end; History, which Excel reserves, becomes "History 1".
  - The Node test zips the parts with the vendored JSZip and reads them back. The browser check opened a converted
    file with `openpyxl` with warnings as errors. Excel and Numbers were not run in this session.

**Shell changes.**
- Options become generic. Each control carries `data-opt="<key>"`, saved per pair under the same localStorage key.
  - Radios and selects store their value, checkboxes a boolean, and the quality slider its raw string. The old keys
    (`output`, `quality`, `background`, `iconset`) keep their names and shapes, so remembered choices survive; a
    browser check restored an old record on the HEIC page.
  - A stored value that matches no control is ignored.
  - `data-show-when="key=a,b"` replaces `data-for-output` (the margin shows only for A4 and Letter).
  - `data-default-locale` gives US Letter to `en-US` and `en-CA`.
  - `Convert.options()` validates every key, with fixed defaults (`page: "a4"`), so tests do not depend on the
    browser.
- The first 4 KB are read for sniffing, not 64 bytes, and `kindOf(head, name)` adds the text check.
- Pairs marked `canvas` in `CONVERSIONS` need `OffscreenCanvas` and `createImageBitmap`; CSV and JPG to PDF need only
  `Worker`. PNGs and odd JPEGs on the PDF page fail on their own row if the canvas is missing. The worker checks the
  same flag.
- Pairs with `combine` get row reordering and the one-PDF button.
- Events: `tool_use` once per batch as before (`jpg-to-pdf:pdf`, `csv-to-xlsx:xlsx`). No separate event for a combined
  PDF, because `tool-counts.mjs` counts every `tool_use` as a run and it would count the batch twice.

**Worker changes.**
- Work is routed by `CONVERSIONS[pair].work` (`image`, `icon`, `pdf`, `sheet`). The ICNS and ICO paths share
  `drawSizes` and `resized`.
- pdf-lib and JSZip are loaded with `importScripts` the first time their pair needs them, from stamped URLs the page
  sends with every message (`libs`).
  - JSZip's URL comes from the page's own `<script src="/assets/vendor/jszip/jszip.min.js?v=">`.
  - pdf-lib's comes from `<link rel="prefetch" as="script" data-convert-lib="pdf" href="/assets/vendor/pdf-lib.min.js">`,
    which only the JPG to PDF page carries and which `fingerprint_assets.py` stamps.
  - The worker accepts only paths under `/assets/vendor/`.
  - The prefetch fetches pdf-lib at idle into the cache. It is the site's own file and sends nothing.
- `importScripts` is not counted by the worker's `fetch`/XHR meter. Neither was libheif's load; they are GET requests
  for this site's files with no body.
- The browser check ran both libraries in the worker under the production CSP, with no CSP errors. A site test checks
  that the link is stamped.

**Pages and links.**
- Each page links to its siblings.
- JPG to PDF links to PDF Tools, for merging existing PDFs.
- The `/tools/` index group is renamed "Convert files": seven cards, `ItemList` positions 25 to 28.
- Each new page gets its own social card.

**Not in this set.**
- **Several CSVs as sheets of one workbook.** Easy to add later with the combine path.
- **XLSX to CSV.** The reverse needs a zip reader and shared-strings parsing; a separate pair if asked.
- **Picking which PNG sizes go into an ICO.** Not offered.
- **BMP entries in ICO** for Windows XP, older resource compilers and some installers. The limits say so.

## Third set: PDF to JPG, SVG to PNG, PNG to JPG

Ben, 2026-11-03: "ship the top 3 first, the rest after". All seven ranked pairs above are live, and the examples in
the request (images to PDF, PDF merge and split, CSV to XLSX, Markdown to PDF) already exist on the site, so the next
three were ranked again on who ranks, fit and browser fit. No volume figures were looked up for this set; the volume
column is relative, from the size of the sites that hold the head terms:

| Pair | Est. volume | Difficulty | Fit | Browser fit | Rank |
|---|---|---|---|---|---|
| PDF to JPG (and PNG) | Very high | Very high head, long tail ("without uploading", "on Mac", "high resolution") reachable | Figures and pages for slides, forms to upload as images | pdf.js, already used by two site tools | 1 |
| SVG to PNG (and JPG) | Medium | Medium | Researchers: pdfLaTeX, Word and many slide tools do not take SVG figures | Native SVG drawing | 2 |
| PNG to JPG | Very high | Very high head; tail "keep quality", "transparent background" | Smaller files for upload limits | Native, existing image path | 3 |
| JPG to PNG | high | Very high | Weak (a JPG gains nothing as PNG) | Native | Not now |
| XLSX to CSV | Medium | Medium | Research data | Needs a zip reader and shared strings | Next |
| TIFF to JPG | Medium | Medium | Microscopy and scans | Needs a TIFF decoder (only Safari reads TIFF) | Next |

| Pair | Accepts | Where the work runs | Outputs |
|---|---|---|---|
| `pdf-to-jpg` | PDF (`%PDF-` in the first 1 KB) | pdf.js draws each page on a canvas on the page; pdf.js parses in its own worker | JPG or PNG per page; one file for a one-page PDF, a zip of the pages otherwise |
| `svg-to-png` | SVG, SVGZ (`<svg` root in the first 4 KB of text, or gzip with a .svgz name) | The browser draws the SVG on a canvas on the page | PNG or JPG |
| `png-to-jpg` | PNG, GIF, BMP | The existing worker image path | JPG |

**Why two pairs draw on the page.** pdf.js's canvas and font loading use `document`, so drawing pages in a worker
would need a custom canvas factory and font handling; pdf.js already parses and decodes in its own worker, and only
the drawing runs on the page. Browsers do not decode an SVG from a Blob in a worker (`createImageBitmap` rejects it
in Chrome and Firefox), and a worker has no `Image`. So the page draws: pdf.js renders a page into a canvas, and the
SVG is drawn from an `<img>` whose source is a `data:` URL (the CSP allows `img-src data:`, not `blob:`, so no CSP
change). The canvas is encoded with `canvas.toBlob`, which Chrome and Firefox run off the main thread, with the same
check `encode()` makes (empty blob or wrong type is an error). There is no new worker message. In `convert()` the
shell branches on `CONV.work`: `"pdfpages"` and `"svg"` return `{ blobs, notes, summary, partsLabel }` and fill
`item.blobs` directly; everything else goes to the worker as before. Progress is set on the item page-side
(`paintProgress`), and `pump()` counts the run for `tool_use` as for every pair.

**Single-output pages.** `options_html` drops the Save as radio when there is one output, which left the quality
and fill controls (`data-show-when="output=jpg"`) hidden for good. Every page with one output now carries
`<input type="hidden" data-opt="output" value="...">`.

**PDF to JPG.**
- pdf.js 6.4.299, copied from the pdfjs-dist package already installed in the ScholarReader repo (no new download):
  `pdf.min.mjs`, `pdf.worker.min.mjs`, and `wasm/jbig2.wasm`, `wasm/openjpeg.wasm`, `wasm/qcms_bg.wasm` with their
  licenses, in `site/assets/vendor/pdfjs-6.4.299/`. Without the wasm decoders, JBIG2 (black-and-white office scans)
  and JPEG 2000 images come out blank. A versioned folder because pdf.js fetches the wasm files by name without a
  `?v=` stamp, and `/assets/vendor/*` is cached as immutable for a year.
- The Thesis Format Checker and the Camera-Ready Checker moved to this folder in the same PR, and the old
  `/assets/vendor/pdfjs/` (6.3.289) was removed. pdf.js 6.4 no longer sends a font's name to the page unless
  `getDocument` is given `fontExtraProperties: true`, so both checkers now pass it; without it their font lists showed
  internal ids (`g_d0_f1`). Their reports were compared on six PDFs (two real papers, 7 and 36 pages) under 6.3.289
  and 6.4.299, in WebKit and Firefox: all 24 identical.
- Also vendored from the same package, loaded only when a PDF needs them: `cmaps/` (packed CMaps for CJK and other
  non-embedded Type0 fonts), `standard_fonts/` (Foxit and Liberation fonts for the 14 standard PDF fonts, so text in
  non-embedded Helvetica or Times looks the same on every system) and `iccs/`. 4.6 MB on the server in all.
- The URLs come from `<link rel="prefetch" as="script" data-convert-lib="pdfjs" href=".../pdf.min.mjs">` and
  `data-convert-lib="pdfjs-worker"` (prefetch, as for pdf-lib, so nothing loads at full priority before a PDF is
  added; `modulepreload` would). `fingerprint_assets.py`
  stamps only `.css` and `.js`, so these stay bare; the versioned folder makes that safe, as for libheif. The shell
  reads them page-side; the site test checks the key and the bare versioned path.
- `GlobalWorkerOptions.workerSrc` is set once; one `PDFWorker` is reused across files. Per file:
  `getDocument({ data, worker, wasmUrl, cMapUrl, cMapPacked: true, standardFontDataUrl, iccUrl, useWorkerFetch: false,
  verbosity: 0 })`, every URL derived from the folder of the module link. `useWorkerFetch: false` keeps those loads
  on the page, where the meter counts them (GETs of this site's files with no body). Per page: `getPage`,
  `render({ canvasContext, canvas, viewport, background: "#ffffff" })`, `page.cleanup()`; after the row,
  `doc.destroy()`. Scripting and XFA stay off (the defaults for `getDocument`), and links in the PDF are never
  opened: the output is pixels. Embedded fonts load through `FontFace` from bytes, which `font-src 'self'` does not
  block; the browser run checks a PDF with embedded fonts for CSP errors.
- If `import()` fails (a browser too old for pdf.js 6), the row says "This browser could not load the PDF reader.
  Use a current version of Chrome, Edge, Firefox or Safari."
- Options, as `data-opt` keys validated in `Convert.options`: `output` "jpg" (default) or "png"; `dpi` "72", "150"
  (default) or "300"; `pages`, text, trimmed, at most 200 characters, default "" (all pages). The Pages field has a
  visible label and a hint linked with `aria-describedby`, and carries `data-nostore` so a range is not remembered
  for the next visit. Pages are always opaque white (`background`), so there is no fill option.
- `Convert.parsePages(text, count)` returns `{ pages }` (sorted, without duplicates) or `{ error }`. Grammar: numbers
  and ranges separated by commas or semicolons; `4-` means 4 to the end; an en dash works as a hyphen. Errors:
  "Pages should look like 1-3, 8. "x" is not a page or a range.", ""5-2" is not a range of pages.", "This PDF has 3
  pages, so there is no page 9." A range running past the end stops at the last page.
- `Convert.pageRaster(w, h, dpi, mobile)` gives the canvas size: dpi/72 times the page in points, shrunk to 40 MP
  (16.7 MP on phones) when larger, since the canvas lives in the page. When any page was shrunk, one row note: "Some
  pages are too large to draw at N dpi here, so they were drawn at M dpi."
- At most 500 pages per run, checked after the document opens: "This PDF has N pages. This page draws up to 500 at
  a time, so enter a range under Pages, such as 1-500."
- Results stop at 1 GB in all (the zip cap): the pages done so far are kept and the row says "Stopped after page N:
  the pages so far add up to 1 GB, the most this tab can zip. Enter a range under Pages for the rest." A page that
  fails to draw is skipped with a note naming it; the rest go on.
- Output names: `report.jpg` for a one-page selection (a normal download button); otherwise `report-pages/report-p001.jpg`
  and so on (digits enough for the page count, at least three), shown as one button "Download the 12 pages (.zip)"
  (`partsLabel`), zipped as `report-pages.zip` with the folder inside. Download all as .zip takes every row's files
  flat, as for ICNS. The row text: "12 pages at 150 dpi, 9.8 MB".
- Errors from pdf.js: `PasswordException` gives "This PDF is locked with a password. Open it in a PDF reader, save a
  copy without the password, and add that." (a PDF with only owner restrictions opens without one and converts);
  `InvalidPDFException` gives "This file could not be read as a PDF. It may be damaged or cut short."; anything else
  gives "This PDF could not be opened (the reader said: ...)."

**SVG to PNG.**
- The text is decoded as UTF-8, or with the encoding its XML declaration names. `Convert.svgRoot` finds the root
  start tag with a regex that skips the XML declaration, comments and a doctype, and takes `svg` or `svg:svg`;
  attributes may come in any order. The `<img>` still parses the whole file, so malformed XML is caught there.
- `Convert.svgSize(text)` reads the root `<svg>`: `width` and `height` in px (1), pt (4/3), pc (16), mm, cm, in (96
  per inch) or unitless; a percentage or a missing value falls back to the `viewBox`, then to 300 by 150 (the browser
  default, with a row note).
  `Convert.svgWithSize(text, w, h)` rewrites the root's width and height to the output pixels and adds a `viewBox`
  from the old size when there is none, so the drawing scales as a vector instead of being enlarged as pixels, and
  Firefox, which will not draw an SVG without a size, gets one. Both are tested in Node.
- Options: `output` "png" (default) or "jpg" (with quality and fill color, as the other image pages); `scale` "1",
  "2" (default), "4" or "width", and `width`, a number from 16 to 16384 shown only for "width" (default 1920). The
  output size is checked against the 40 MP page-side cap (16.7 MP on phones) before the canvas is made. PNG keeps
  transparency.
- An SVG drawn as an image cannot run scripts or load anything, which is also why external images and web fonts do
  not appear. The row says so when the file references `http` images or `@import`s fonts. Safari refuses to export a
  canvas with an SVG `<foreignObject>` (a tainted canvas): `toBlob` throws a `SecurityError`, and the row says "This
  browser will not export this SVG because it contains HTML (a foreignObject). Try Chrome or Firefox." An `<img>`
  that fails to load says "This browser could not draw this SVG. The file may not be valid XML."
- Up to 10 MB of SVG, because the drawing goes through a `data:` URL that some browsers cap. An SVGZ (gzip, named
  .svgz) is unpacked with `DecompressionStream` and stopped once the text passes 10 MB, so a small file cannot unpack
  to gigabytes. Without `DecompressionStream`: "This browser cannot unpack .svgz files. Save the drawing as .svg."

**PNG to JPG.** `work: "image"`, JPG only, the quality slider and fill color (shown through the hidden `output`). GIF and BMP are accepted (sniffed `GIF8`,
and `BM` with a known header size) because the question is the same: a lossless picture made smaller. An animated
PNG (`acTL` chunk) or GIF (a `NETSCAPE2.0` block) gets the first-frame note.

**Pages and links.**
- `/tools/` group "Convert files": ten cards and a count of 10; `ItemList` positions 29 to 31 after CSV to XLSX, and
  Photo to Logo moves to 32.
- PDF to JPG and PNG to JPG name Née in their How it works text and list it under More free tools ("Née, a Mac
  converter"): it does both from Finder (its PDF pages come out as PNG).
- The three slugs go into `TOOL_SLUGS` (`netlify/lib/tool-counts.mjs`, sorted) and the "apps" background tuple in
  `gen_og_cards.py`; each card is rendered with `--only tools/<slug>`. Buddy's links come from the sitemap.
- The page-side pairs override the privacy line and the "Are my files uploaded?" answer, which otherwise say "in a
  background worker".

**Build and tests.** Branch `tools-converters-3`, worktree `converters-3`, one PR, squash-merged when green, no
`[deploy now]`. Node tests: `parsePages`, `pageRaster`, `pageName`, `svgSize`, `svgWithSize` (units, percentage,
viewBox fallback, default, existing viewBox, `svg:svg`, comments and doctype first), `isSvgText` and `kindOf` for
pdf, svg, svgz, bmp, the new `options()` keys, and the new refusals. Site test: the pdfjs links and vendor folder
(files, licenses, README hashes), the hidden `output` on single-output pages, `data-nostore` on Pages. Browser runs in
WebKit and Firefox under the production CSP, with every output opened: a multi-page PDF with embedded fonts, a JBIG2
scan, a password PDF, SVGs with mm sizes and with only a viewBox, an SVGZ, an animated GIF, a BMP.

**Not in this set.** JPG to PNG, XLSX to CSV and TIFF to JPG (above). Extracting the images embedded in a PDF
unchanged (a different job from drawing pages). Choosing a background for SVG PNGs (they keep transparency).

## Open questions

0. **Safari 16.4 and Firefox.** The browser check ran in Chromium. Worker plus Emscripten plus `OffscreenCanvas` is
   standard in Safari 16.4+ and Firefox 105+, but it has not been run there; worth a manual pass on Ben's Mac in Safari
   after the build publishes.

1. **Wide-gamut color.** iPhone HEICs are Display P3. libheif returns the pixel values without converting them, and
   they are written to an sRGB canvas, so very saturated colors come out slightly duller. A P3 canvas
   (`colorSpace: "display-p3"`) would keep them in Chrome and Safari, but whether `convertToBlob` embeds the P3
   profile in the JPEG differs by browser. The first PR keeps sRGB and says so in the limits; worth a follow-up.
2. **Keeping the date taken.** Some people converting a photo library want EXIF dates kept. Copying the EXIF block
   from HEIC into the JPEG is possible (libheif exposes it) but would also carry GPS, which conflicts with the
   privacy posture. Left out; revisit if people ask.

## Review log

Three Goldfish reviewers on Sonnet, zero context, 2026-11-02. What changed:

- **Design: CSP reasoning was wrong** ("a module could not be fetched from elsewhere"). Corrected; sitewide scope
  justified by `'unsafe-inline'` already being present and by Netlify's header merging. Test asserts no `'unsafe-eval'`.
- **Design: memory.** Pixel caps checked before decoding (desktop and phone), source released before encoding, a dead
  worker becomes a row error, zip capped at 1 GB.
- **Design: LGPL.** libde265 named; README with hashes and the replaceable-file statement; patent risk recorded as
  accepted, owner Ben. A hosted source tarball was not added (noted).
- **Design: `mif1` ambiguity.** Sniffing checks AVIF brands before HEIF ones; tests cover `mif1`+`avif`.
- **Design: ICNS.** Non-square sources fitted and centered; 10.8 stated. Building it surfaced a draft error the
  reviewers did not catch: `icp6` is read as 48 px by `iconutil`, so it was dropped.
- **Design: animated WebP** gets a note on the row; P3 color stays an open question.
- **Readiness: OG cards** would have failed `test_social_cards` through two existing tool pages; both rendered.
- **Readiness: the meter** did not see the worker's requests; the worker now reports its own.
- **Readiness: build order, `vm` loading, the stamp handoff, index ItemList** spelled out above.
- **Readiness: thin-page prune** does not cover tools; the gate is now a manual decision.
- **Zoom-out: success gate and window.** 90-day read, a day-28 gate for the next set, target queries named.
- **Zoom-out: HEIC alone first.** Declined, because the brief asked for three and WebP and ICNS add little risk.
- **Zoom-out: altitude.** The ICNS layout and worker protocol stay, because they are what the tests check against.

Second set, two Goldfish reviewers on Sonnet (design, implementation readiness), zero context, 2026-11-02. What
changed:

- **Number rule** was too loose. These now stay text: 12-digit and longer integers, scientific notation without a
  decimal point or a signed exponent, `.5` and `5.`. A Node table of 25 cases pins the rule.
- **AVIF support**: iOS 16 named; the row message names the browsers. A pre-drop probe was declined: the row message
  covers it without an extra decode on page load.
- **PDF orientation**: page box swap and matrix signature specified and tested for all eight orientations.
  Non-embeddable JPEGs (SOF other than 0 to 2, 12-bit, CMYK without Adobe's marker) are redrawn instead of refused.
- **CMYK**: checked in the vendored pdf-lib source (it writes the inverted Decode array for every CMYK JPEG), so CMYK
  without Adobe's marker is redrawn. Rendered red in a browser check.
- **PNG memory and fidelity**: 25 MP cap for PNG pages; PNGs normalized through the browser before pdf-lib.
- **Encoding**: BOM before the NUL check, the whole file tested as UTF-8, an encoding option, and the encoding and
  separator shown on the row. A data preview was declined; the row summary says what was read.
- **XLSX package**: content types first, schema order, wrap style, reserved and apostrophe sheet names. Checked by
  openpyxl, not by Excel.
- **Memory**: a 5 million cell cap, and the sheet XML kept in chunks.
- **Library stamping** (blocker): stamped `data-convert-lib` link, `libs` in each message, a vendor-path check, a site
  test.
- **OffscreenCanvas gate** (blocker): a per-pair `canvas` flag in both shell and worker.
- **`kindOf`** (blocker): defined; the worker calls it instead of `sniff`.
- **`options()` dropped new keys** (blocker): every key validated, fixed defaults, tests.
- **Options storage**: types and compatibility defined, `data-show-when`.
- **Node loading**: `.cjs` copies of pdf-lib and JSZip; pdf-lib and JSZip run in the main realm, the core in `vm`
  with `TextDecoder` passed in.
- **Combine protocol** defined; the separate combined event dropped, since it would double-count runs.
- **Open: a hash check of the vendored copies in tests.** Not added. pdf-lib and JSZip were already live, and a swap
  breaks the Node tests that run them.

Third set, two Goldfish reviewers on Sonnet (design, implementation readiness), zero context, 2026-11-03. What
changed:

- **pdf.js `.mjs` links** would not have been stamped, and the site test would have rejected them. Now bare,
  versioned, and tested as such.
- **PNG to JPG's quality and fill** would have stayed hidden on a page with one output. A hidden `output` field fixes
  every single-output page.
- **Encoding** moved from a new worker message to `canvas.toBlob` on the page, which drops a second full-size copy of
  every page.
- **Memory**: page-side canvases capped at 40 MP, one canvas reused, `page.cleanup()` and `doc.destroy()`, a 1 GB
  stop that keeps the pages done, one failed page skipped instead of failing the file.
- **Fonts**: CMaps and standard fonts vendored, and `useWorkerFetch: false` so the meter sees their loads.
- **SVG**: a 10 MB limit (the `data:` route), the SVGZ limit applied while unpacking, the pixel cap before drawing,
  messages for a failed load and a tainted canvas.
- **Specified**: option keys and defaults, the `parsePages` grammar and messages, the pdf.js error map, the row text
  and zip naming, the ItemList positions, the copy overrides, tests and build order.
- **Kept**: the regex root edit for SVG instead of `DOMParser`, so the size rules run in the Node tests; the `<img>`
  still parses the whole file. A Cancel button is not added (no converter has one; Clear removes waiting rows).
