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

## Fourth set: XLSX to CSV, JSON to CSV, TIFF to JPG

Ben, 2026-11-03: "build the next three converters". XLSX to CSV and TIFF to JPG were ranked "Next" in the third set.
The third slot goes to JSON to CSV (research data from APIs and survey tools, the same readers as CSV to XLSX, pure
JavaScript) rather than JPG to PNG, which ranked weak on fit, or a WebP encoder, which Safari's canvas cannot do.

| Pair | Accepts | Work (worker) | Outputs |
|---|---|---|---|
| `xlsx-to-csv` | XLSX and XLSM (`PK\x03\x04` and the name); a legacy .xls (`D0 CF 11 E0`) is refused with its own message | JSZip reads the parts; a cell reader in `convert-core.js` | .csv for the first sheet, or one per sheet in a zip |
| `json-to-csv` | .json, .jsonl, .ndjson, or text whose first character is `[` or `{` | `JSON.parse`, flatten, the CSV writer; XLSX through `buildXlsxParts` | .csv or .xlsx |
| `tiff-to-jpg` | TIFF (`II*\0` or `MM\0*`); BigTIFF (`II+\0`) is refused | UTIF.js decodes, `toRGBA8`, then the existing `encode()` | JPG or PNG, one per page; a zip for several |

**XLSX to CSV.**
- The worker has no `DOMParser`, so the XML is read with small regex readers in the core, tested in Node:
  `parseWorkbook` (sheet names, order, hidden state, `date1904`), `parseRels`, `parseSharedStrings` (every `<t>` of
  an `<si>`, rich-text runs joined, phonetic `<rPh>` left out, `_x000D_` escapes decoded), `parseStyles` (which
  `cellXfs` index is a date or time format), and `sheetRows` (cells by their `r` reference, so skipped cells and
  rows stay empty; types `s`, `str`, `inlineStr`, `b`, `e`, `n`).
- Values: the cached result of each formula (a formula with none is empty, and the row counts them); `TRUE` and
  `FALSE`; error text such as `#N/A`; numbers as stored, through `String(Number(v))`. Date and time formats
  (built-in ids 14 to 22, 27 to 36, 45 to 47, 50 to 58, and custom codes with d, m, y, h or s outside quotes and
  brackets) become ISO 8601: `2026-11-03`, `2026-11-03 14:05:00`, or `14:05:00`. Serials use the 1900 system with
  Excel's leap-year bug (serial 60 and later minus one day) or the 1904 system when the workbook says so. Other
  formats (currency, percent) give the plain number, so `12%` is `0.12`; the limits say so.
- `Convert.toCsv(rows, delimiter)`: RFC 4180 quoting (fields with the separator, a quote, CR or LF), CRLF line ends,
  trailing empty columns trimmed per sheet. Options: `delimiter` comma (default), semicolon or tab; `sheets` "first"
  (default) or "all"; `bom`, a checkbox, default off ("Add a byte-order mark for Excel on Windows"), because R and
  some scripts read the mark into the first column name.
- "All sheets" writes `book-sheets/<sheet name>.csv` in `book-sheets.zip`; hidden sheets are included and named in
  a note; chart sheets have no cells and are skipped. Caps: 50 MB file, 300 MB of sheet XML unpacked (checked from
  the zip's directory before inflating), 5 million cells (the CSV to XLSX cap).

**JSON to CSV.**
- `Convert.jsonRecords(text)`: a top-level array is the rows; an object whose largest array holds objects uses that
  array (the row note names the key, for API replies such as `{"data": [...]}`); any other object is one row; if the
  whole text does not parse but every non-empty line does, it is JSON Lines.
- `Convert.flattenRecords(records, nested)`: columns are the union of keys in first-seen order. `nested` "columns"
  (default) turns `{"a": {"b": 1}}` into a column `a.b`; arrays, and everything under "json", are written as JSON
  text. `null` is empty, booleans are `true` and `false`. An array of plain values gives one column, `value`.
- Large integers: `JSON.parse` rounds integers past 2^53 (tweet and order IDs). Where the browser passes the source
  text to a reviver (`context.source`; Chrome 114 and Firefox 135 have it, and the page tests for it at run time), those numbers are kept exactly as
  written; elsewhere the row notes how many were rounded.
- Options: `output` csv (default) or xlsx; `delimiter` and `bom` as above, CSV only; `nested` "columns" or "json".
  XLSX goes through `buildXlsxParts`, so leading zeros and long IDs stay text there as well. Cap: 50 MB.

**TIFF to JPG.**
- UTIF.js 3.1.0 (Photopea, MIT), downloaded with Ben's approval on 2026-11-03 from the npm registry and checked
  against its sha512, and pako 1.0.11's `pako_inflate.min.js` (MIT and Zlib), copied from a local npm install, in
  `site/assets/vendor/utif-3.1.0/`. UTIF decodes uncompressed, PackBits, LZW, Deflate (through pako), CCITT G3 and
  G4, and JPEG-compressed TIFF, at 1 to 16 bits per channel, gray, RGB, palette and CMYK. Its `<img>`-replacing
  helpers, the only code using `document` or XHR, are never called. UTIF reads `self.pako` when it loads, so the
  worker loads pako first. Both are stamped `.js` prefetch links, like pdf-lib.
- The worker reads the directory (`UTIF.decode`), skips reduced-resolution subfiles (bit 0 of tag 254, the
  thumbnails scanners add), checks each page's size against the pixel cap before decoding, then `decodeImage`,
  `toRGBA8`, `ImageData`, and the existing `encode()`.
- Options: `output` jpg (default, with quality and fill) or png; `pages` "first" (default) or "all". Several pages
  are named like PDF to JPG's (`scan-pages/scan-p001.jpg`, `Download the 4 pages (.zip)`).
- Notes: 16 bits per channel reduced to 8 (dim scientific images can stay dark; nothing is stretched); an
  orientation tag that is not upright is not applied; layers and alpha in other channels are left out.

**Shared.** The three pages use the worker, so the privacy line and the first FAQ are the standard ones. Index: 13
cards in "Convert files", ItemList positions 32 to 34, Photo to Logo to 35. Social cards, `TOOL_SLUGS`, sitemap and
Buddy as before. CSV to XLSX links to XLSX to CSV and JSON to CSV; PNG to JPG and PDF to JPG to TIFF to JPG. Branch
`tools-converters-4`, worktree `converters-4`, one PR, squash-merged when green, no `[deploy now]`. Browser runs in
WebKit and Firefox under the production CSP, every output opened: a workbook with shared and inline strings, dates
in both systems, a formula, a hidden sheet and a Japanese sheet name; JSON as an array, an object holding an array,
JSON Lines, nested objects and a 19-digit ID; TIFFs in LZW, Deflate, PackBits, G4, JPEG, 16-bit gray, CMYK,
palette, and a multi-page scan with a thumbnail.

**Resolved after review (two Goldfish reviewers on Sonnet, 2026-11-03).** These replace the text above where they
differ.

- **TIFF reading is ours; only UTIF's decompressors are used.** Running UTIF on Pillow-made and hand-made fixtures in
  Node showed `UTIF.decode` looping without end on a TIFF whose next-directory pointer points back (out of memory),
  PackBits strips copied raw when their compressed length happens to equal the raw length, and `toRGBA8` wrong for
  gray with alpha, 1, 2 and 4-bit palettes, planar files and JPEG-in-TIFF. So the core reads the TIFF itself:
  `Convert.readTiff(bytes)` walks the directory chain with a visited set and a cap of 1,000 directories, checks
  every strip and tile against the file length, and returns the pages with their tags. The worker decompresses each
  strip or tile with the core's PackBits, pako (8 and 32946, which is the same zlib stream), or UTIF's
  `_decodeLZW`, `_decodeG3` and `_decodeG4`; `Convert.tiffUnpredict` undoes predictor 2 for 8 and 16 bits; and
  `Convert.tiffRGBA` converts gray and WhiteIsZero (1, 2, 4, 8, 16 bits, with or without alpha), RGB and RGBA (8
  and 16, associated alpha un-premultiplied), palette (1, 2, 4, 8) and CMYK (8 and 16), reading 16-bit samples in the
  file's byte order. JPEG-in-TIFF (compression 7) is decoded by the browser: each strip or tile becomes a JPEG
  (`JPEGTables` spliced in after SOI) for `createImageBitmap`, drawn at its place. When the TIFF says the JPEG data is RGB (photometric 2), an Adobe APP14 segment with transform 0 goes in too: the browser run showed WebKit reading such strips as YCbCr (red came out green), while Chrome goes by the component ids. Anything else (planar
  configuration 2, floating point, CIELab, old-style JPEG, other compressions) is refused with "This TIFF uses
  <what> that this page cannot read." Every decoder is checked against Pillow's pixels for the same file in Node.
- **TIFF memory and pages.** `maxPixels` 40 MP per page (checked from tags 256 and 257 before anything is
  allocated); one page decoded, encoded and released at a time; 500 pages a run; the 1 GB stop of PDF to JPG; a page
  that fails is skipped with a note. "First page" is the first full-resolution page (thumbnails skipped); when there
  are more, the row says "This TIFF has N pages. The first was converted; choose All pages for the rest." The
  orientation tag is applied (`Convert.orientTransform`), and `ImageData` goes through `createImageBitmap` before
  `encode()`.
- **Formula protection.** A text value that starts with `=`, `+`, `-`, `@`, a tab or a carriage return can run as a
  formula when a CSV opens in Excel, even though it was harmless text in the workbook or the JSON. Option `safe`,
  default on, labelled "Keep text that starts with = + - @ from running as a formula in Excel", puts a `'` in front
  of such text cells only: numbers, dates and booleans are never touched, so `-5` stays `-5`. The limits say so.
- **Long integers in JSON.** `Convert.protectBigInts(text)` runs before `JSON.parse` in every browser: a scanner that
  skips strings marks integer literals of 16 digits or more, which then reach the CSV exactly as written. The
  reviver and its feature test are dropped.
- **Kinds, in order.** `sniff` gains `tiff`, `bigtiff` and `xls` (OLE). `kindOf` then: svgz and svg as before; a zip
  is `xlsx` only when named .xlsx or .xlsm (a .docx stays ""); .json, .jsonl, .ndjson and .geojson are `json`, and so
  is a .txt whose first character after a BOM and spaces is `[` or `{`; the CSV-family names as before. The OLE
  refusal says "This is an older Excel workbook (.xls), or an .xlsx protected with a password. Save it as an
  unprotected .xlsx and add that."
- **Option keys.** `delimiter` reuses the CSV to XLSX key; for the writers "auto" means comma. New keys: `sheets`
  ("first" or "all"), `bom` (false), `nested` ("columns" or "json"), `safe` (true), `tiffpages` ("first" or "all"),
  so the PDF page range keeps `pages`. On JSON to CSV, `delimiter` and `bom` show only for `output=csv`.
- **Numbers from a workbook** are written as stored (the cell's own text), not as Excel shows them: `12%` is `0.12`,
  and a 17-digit ID typed as a number has already lost digits inside the workbook. The limits say so.
- **XLSX memory.** Each sheet's XML is read through JSZip's `internalStream`, counting bytes as they inflate, and
  stopped past 100 MB ("This sheet is over 100 MB of data, more than this page reads in a browser tab"), so a size
  field that lies does not matter. Cells stop at 5 million, in `sheetRows` and in `flattenRecords`.
- **Names.** Sheet file names have `\ / : * ? " < > |` and control characters replaced, leading and trailing dots and
  spaces trimmed, and duplicates numbered; JSON Lines and GeoJSON names lose their whole extension.
- **JSON shapes.** The largest array of objects wins, and the note names it and any other candidates. A literal key
  `a.b` next to a nested `a.b` gets the column `a.b (2)`. Column bookkeeping uses `Object.create(null)`, so a key
  named `__proto__` is an ordinary column. XLSX output goes through `buildXlsxParts` with the CSV to XLSX number
  rule, so a JSON string "42" becomes a number cell there; the limits say so.
- **Messages** for every failure named by the review are in the code and its tests; the Node tests cover the kinds,
  refusals, options, every reader and writer, date rules (serial 60, 1904, rounding to the second), the TIFF
  decoders against Pillow, a looping directory chain and an oversized page.
- **Not done:** a Safari-native TIFF path (UTIF plus the core decode works in every browser, one path is simpler).

## Fifth set: CSV to JSON, ICNS to PNG, ICO to PNG

The parent session, 2026-11-03, after the fourth set merged: "pick the next converter set from the demand ranking in
your design doc and start it, with the same tests against reference outputs." Every ranked pair is now built except
JPG to PNG (weak fit), so the set was ranked again on fit, browser fit, and whether a trusted tool on this Mac can
produce the reference output each test compares against. No new library is needed.

| Pair | Volume (relative) | Fit | Browser fit | Reference for the tests | Rank |
|---|---|---|---|---|---|
| CSV to JSON | Medium to high | The reverse of JSON to CSV, for the same data readers | The CSV to XLSX reader, a JSON writer | Python's `csv` and `json` with the same rules | 1 |
| ICNS to PNG | Low, little competition | Mac developers, the reverse of PNG to ICNS | PNG entries are copied out unchanged; old RLE entries decoded | Apple's `iconutil -c iconset` | 2 |
| ICO to PNG | Medium | Favicons and Windows icons | PNG entries copied out; BMP entries decoded in the core | Pillow's ICO reader | 3 |
| JPG to PNG | Very high | Weak (a JPG gains nothing as PNG) | Native | | Not now |

| Pair | Accepts | Work (worker) | Outputs |
|---|---|---|---|
| `csv-to-json` | CSV, TSV, TXT (the CSV to XLSX kinds) | `decodeText`, `detectDelimiter`, `parseCsv`, then `Convert.csvToJson` | .json, or .jsonl |
| `icns-to-png` | ICNS (`icns` and a length that matches the file) | `Convert.readIcns`, then PNG entries as they are and the rest drawn | .png, the largest; or every size in a zip |
| `ico-to-png` | ICO and CUR (`00 00 01 00` or `00 00 02 00`, a sane count and directory) | `Convert.readIco`, then PNG entries as they are and BMP entries decoded | .png, the largest; or every size in a zip |

**CSV to JSON.**
- Options: `output` "json" (default, an array, indented two spaces) or "jsonl" (one object per line); `header`
  (default on: the first row gives the keys, otherwise each row is an array); `types` (default on: numbers by the
  CSV to XLSX rule, so ZIP codes, phone numbers and long IDs stay strings, `true` and `false` as booleans, empty cells
  as `null`; off: every value a string, empty cells `""`); `nest` (default off: `a.b` headers become nested objects,
  the reverse of JSON to CSV); `delimiter` and `encoding` as on CSV to XLSX.
- Keys: an empty header becomes `column N`; a repeated header gets ` (2)`; a row longer than the header gets
  `column N` keys; a shorter one leaves the missing keys out (JSON Lines) or `null` (array), so every object has
  the same keys in the array output. With `nest`, a header that is both a value and a parent (`a` and `a.b`) keeps
  the flat key for the value and the row note says so.
- Numbers are written by JSON.stringify of the parsed value, so `3.50` becomes `3.5`; a value the number rule keeps
  as a string stays exactly as typed. Decimal commas (`3,50`) are read only for semicolon files, as on CSV to XLSX.
- Caps: 50 MB and 5 million cells. The JSON is built as an array of chunks, as the XLSX sheet XML is.

**ICNS to PNG.**
- `Convert.readIcns(bytes)`: the header length must equal the file length (or be no longer); entries are walked
  with a cap of 200 and every length checked. Each entry is classified by its type and first bytes: PNG
  (`\x89PNG`), JPEG 2000 (`\0\0\0\x0cjP`), ARGB RLE (`ARGB`, ic04 and ic05), legacy 24-bit RLE (is32, il32, ih32,
  it32, the last with four zero bytes first) with its 8-bit mask (s8mk, l8mk, h8mk, t8mk), and the rest (TOC,
  icnV, name, info, and the old 1 and 4-bit types) ignored.
- Size and scale come from the type: ic07 128, ic08 256, ic09 512, ic10 1024 (512@2x), ic11 32 (16@2x), ic12 64
  (32@2x), ic13 256 (128@2x), ic14 512 (256@2x), icp4 16, icp5 32, icp6 48 (as `iconutil` reads it), ic04 16,
  ic05 32, is32 16, il32 32, ih32 48, it32 128. The PNG's own IHDR size wins when it differs.
- PNG entries are written out byte for byte. RLE entries are unpacked in the core (`Convert.icnsRle`, the PackBits
  variant Apple uses: 0 to 127 means copy n+1, 128 and up means repeat n-125), combined with their mask, and drawn
  to PNG by the worker. JPEG 2000 entries (icons from Mac OS X 10.5 to 10.6) are left out with a note, since only
  Safari decodes JPEG 2000.
- Options: `icons` "largest" (default) or "all". All gives `name.iconset/icon_16x16.png` and the other `iconutil`
  names in `name-icons.zip` (an `.iconset` folder `iconutil -c icns` can turn back into an ICNS); duplicate sizes
  keep the first.

**ICO to PNG.**
- `Convert.readIco(bytes)`: the 6-byte header (reserved 0, type 1 or 2, a count of 1 to 255), 16-byte directory
  entries, each offset and length checked against the file. A width or height byte of 0 means 256. The entry's
  own data decides its size: a PNG's IHDR, or a BMP header's width and half its height.
- BMP entries (`Convert.icoBmp`): BITMAPINFOHEADER, 1, 4 and 8-bit with their palette, 24-bit, and 32-bit with
  alpha; rows bottom-up and padded to four bytes; then the 1-bit AND mask, applied when the image has no alpha of its
  own (a 32-bit entry with every alpha 0 uses the mask too). Compressed BMP entries are refused with a note.
- Options: `icons` as for ICNS. All gives `name-16x16.png`, `name-32x32.png` and so on in `name-icons.zip`; two
  entries of one size at different color depths keep the deepest.
- A cursor (.cur) is read the same way; its hotspot is not kept.

**Shared.** Worker pages with the standard privacy line and first FAQ. Index: 16 cards, `ItemList` 35 to 37, Photo
to Logo to 38; social cards, `TOOL_SLUGS`, sitemap, Buddy. Sibling links: JSON to CSV and CSV to XLSX to CSV to JSON;
PNG to ICNS to ICNS to PNG; PNG to ICO to ICO to PNG. Branch `tools-converters-5`, one PR, squash-merged when green,
no `[deploy now]`.

**Tests against reference outputs.**
- CSV to JSON: fixtures (quoted fields, embedded newlines, a BOM, Windows-1252, semicolons with decimal commas, ZIP
  codes, long IDs, empty and repeated headers, ragged rows) are converted by a Python script that applies the same
  rules with `csv` and `json`; the page's output must parse to the same value in Node and in both browsers.
- ICNS to PNG: real ICNS files from `/System/Applications` and `/System/Library/CoreServices` (PNG, ARGB and legacy
  RLE entries), plus the page's own PNG to ICNS output; `iconutil -c iconset` gives the reference PNGs, compared
  pixel for pixel.
- ICO to PNG: ICOs written by Pillow (PNG entries) and by hand (1, 4, 8, 24 and 32-bit BMP entries, with and without
  an AND mask), plus real favicons on disk; Pillow's decode of each entry is the reference, compared pixel for pixel.
- Node tests for every reader and the refusals, as in the earlier sets; browser runs in WebKit and Firefox under the
  production CSP, every output opened.

**Resolved after review (two Goldfish reviewers on Sonnet, 2026-11-03).** These replace the text above where they
differ.

- **Kinds.** `sniff` gains `icns` (`icns`, a header length of at least 16, and a first entry of at least 8 bytes that
  fits inside it) and `ico` (`00 00 01 00` or `00 00 02 00`, a count of 1 to 255, and not `ftyp` at bytes 4 to 8,
  since a HEIC or AVIF `ftyp` box of 256 or 512 bytes starts the same way), checked after the `ftyp` branch. A .cur
  file is kind `ico`. `KIND_NAMES` and `article` ("an ICNS", "an ICO") learn both. The length check against the whole
  file lives in `readIcns`, since `kindOf` sees only 4 KB.
- **Table rows.** `csv-to-json`: accepts `csv`, outputs json (default) and jsonl, `work: "csvjson"`, 50 MB.
  `icns-to-png`: accepts `icns`, output png, `work: "icns"`, 50 MB. `ico-to-png`: accepts `ico`, output png,
  `work: "ico"`, 20 MB. No `canvas` flag on the icon pairs: PNG entries need no drawing, so the worker checks for
  `OffscreenCanvas` only when an entry has to be drawn. `MIME` gains `json` and `jsonl`.
- **Option keys.** `header` (existing, default on), `types` (new, default on), `unflatten` (new, default off; named
  apart from JSON to CSV's `nested`), `icons` ("largest", the default, or "all"), plus `delimiter` and `encoding`.
- **Types are inferred per column, and only when they round-trip.** A column is numbers only if every non-empty cell
  passes the CSV to XLSX rule and `String(Number(t)) === t` (after a decimal comma becomes a point in semicolon
  files), so `3.50`, `10.00`, `-0`, `1.5e-400`, `90210` beside `02134`, and versions like `1.10` all stay strings
  as typed. A column is booleans only if every non-empty cell is `true` or `false` in any case. Empty cells are
  `null` with types on and `""` with them off; a cell of spaces is text. The page no longer claims ZIP codes or phone
  numbers stay text in general: the rule is per column, and the limits say so.
- **JSON is written by hand, in header order.** JavaScript orders integer-like keys first (`2023` before `name`), so
  no objects are built: each row is written as text, keys in header order, and the text goes into Blob parts every
  2 MB. The output size is estimated first (keys times rows plus cell text) and refused past 200 MB with "The JSON
  would be about N MB, more than this page writes in a browser tab. Choose JSON Lines, or split the CSV."
- **Keys.** Empty headers become `column N`, extra cells in long rows `column N`, and every key is then made unique
  in one pass (` (2)`, ` (3)`, until free), so a real header named `column 3` or `a (2)` cannot collide. Blank lines
  are skipped. Missing cells in short rows are empty cells in both outputs. An unclosed quote gives the CSV to XLSX
  note. With `unflatten`, `a.b` becomes `{"a": {"b": ...}}`; a key with an empty part (`a..b`, `.a`, `a.`) stays
  flat; a prefix that is also a value (`a` and `a.b`) keeps both flat, with a note. Arrays written by JSON to CSV as
  JSON text stay text; the page does not claim a perfect round trip. With `header` off, each row is an array, in
  both outputs.
- **ICNS names by type.** Each type has one iconset slot, the names `iconutil` writes:

  | Type | Slot | | Type | Slot |
  |---|---|---|---|---|
  | icp4, ic04, is32 | icon_16x16 | | ic11 | icon_16x16@2x |
  | icp5, ic05, il32 | icon_32x32 | | ic12 | icon_32x32@2x |
  | icp6, ih32 | icon_48x48 | | ic13 | icon_128x128@2x |
  | ic07, it32 | icon_128x128 | | ic14 | icon_256x256@2x |
  | ic08 | icon_256x256 | | ic10 | icon_512x512@2x |
  | ic09 | icon_512x512 | | icsb / icsB | icon_18x18 / @2x |
  | sb24 / SB24 | icon_24x24 / @2x | | | |

  When two entries share a slot, a PNG wins over ARGB, and ARGB over legacy RLE. `icp6` is 48 px: `iconutil` writes
  an icp6 entry to icon_48x48 and scales a 64 px PNG in it down to 48 (checked 2026-11-03; it also wrote a plain
  48 px icp6 PNG as a transparent image, so `iconutil` is not the reference for icp6, and the PNG is copied as it is). Real icons also carry
  `icsb`, `icsB`, `sb24` and `SB24` (sidebar sizes), found in a survey of 393 system ICNS files.
- **ICNS decoding.** ARGB (ic04, ic05, icsb): after `ARGB`, one RLE stream that unpacks to 4 x w x h bytes, the A,
  R, G and B planes in turn. The color planes are premultiplied by alpha, so they are divided back out (found by comparing
  Siri's 16 px icon with `iconutil`'s output: pixels at alpha 3 to 30 differed until then). Legacy (is32, il32, ih32, it32, the last after four zero bytes): RLE to 3 x w x h, the R,
  G and B planes; the mask (s8mk, l8mk, h8mk, t8mk) is w x h raw bytes, and without one the icon is opaque. An entry
  that unpacks short is skipped with a note. JPEG 2000 entries are skipped, and "largest" means largest readable: the
  row says "This icon also holds a 512 by 512 size in JPEG 2000, which only Safari reads, so 128 by 128 was saved."
  With nothing readable: "This ICNS holds no size this page can read." The header length may be shorter than the
  file (trailing bytes are ignored) but not longer.
- **ICO decoding.** `readIco` is lenient, unlike `parseIco`, which stays strict for checking PNG to ICO's own output:
  entries may have gaps, trailing bytes or any order; each must lie inside the file. PNG entries are copied out.
  BMP entries: header size 40 or more (V4 and V5 too), width up to 1024 and height up to 2048 (doubled for the mask),
  checked before anything is allocated; 1, 4 and 8-bit with `biClrUsed` colors (0 meaning 2^bits), 24 and 32-bit;
  rows bottom-up (a negative height is top-down) padded to 4 bytes; then the AND mask, 1 bit a pixel, rows padded to 4
  bytes, applied when the entry has no alpha of its own, including a 32-bit entry whose alpha is all 0 (what Windows
  does; Pillow leaves such an entry transparent, so that fixture is checked against its known pixels, not Pillow). A
  short or missing mask means opaque. 16-bit, BI_BITFIELDS and other compressions are skipped with a note. Depth for
  "keep the deepest" comes from the BMP header or the PNG's IHDR, never from the directory (a .cur keeps its hotspot
  there).
- **Names and summaries.** Largest: `name.png`, with "512 by 512 pixels, the largest of 10 sizes". All: ICNS as
  `name.iconset/icon_16x16.png` and so on in `name-icons.zip`; ICO as `name-icons/name-16x16.png` (real width and
  height); both with "Download the 10 sizes (.zip)". CSV to JSON: "N rows and M columns".
- **Fixtures and references, committed.** System icons are Apple's and are not committed. The committed ICNS
  fixtures are synthesized by a Python script with an independent RLE encoder over known pixels: legacy is32 with
  s8mk, ARGB ic04, a PNG ic07, and a JPEG 2000 placeholder; their expected pixels are asserted in Node. Real icons
  (393 surveyed; Siri, Music, Mail sidebar, NetAuthAgent's it32 and ih32, a JPEG 2000 iPhone icon) are compared in
  the session with `iconutil -c iconset` as the reference and Pillow as a second one for RLE. ICO fixtures (1, 4, 8,
  24 and 32-bit BMP entries, with and without masks, the zero-alpha case, and a Pillow ICO with PNG entries) are
  committed with their expected pixels; Pillow's decode was the reference when they were made, and real ICOs from
  disk (Lightroom's installer icon, Apache's favicon) are compared in the session. CSV fixtures are committed next
  to the JSON a Python reference script wrote for them.
- **Build order:** core kinds, table, options and tests; readers with fixture tests; worker routes; generator pages;
  index, slugs, cards, sitemap, Buddy; site tests; browser runs.
- **Decoded icon sizes are written by the core's own PNG writer** (`Convert.pngEncode`: filter 0 rows, zlib from
  `CompressionStream`, CRC-checked chunks), not a canvas. The first browser run drew them through a canvas, which
  stores premultiplied alpha and moved the color of faint pixels by up to 20 against `iconutil` and Pillow; with the
  writer, all 29 compared images match their references exactly in WebKit and Firefox. "Every size" for an icon with a
  single size gives the plain PNG, not a one-file zip.

## Sixth set: XLSX to JSON, SRT to VTT, VTT to SRT

Ben, 2026-11-03: "build the next three converters". Ranked as the fifth set was: fit, browser fit, no new library, and
a trusted tool on this Mac for the reference outputs.

| Pair | Volume (relative) | Fit | Browser fit | Reference | Rank |
|---|---|---|---|---|---|
| XLSX to JSON | Medium | Research and survey data into scripts | The XLSX readers of the fourth set, the JSON writer of the fifth | openpyxl (`data_only=True`) with the same rules | 1 |
| VTT to SRT | Medium to high | Captions downloaded from YouTube, Zoom and lecture platforms, for editors that want SRT | Text only | `ffmpeg -i x.vtt x.srt` | 2 |
| SRT to VTT | Medium | Captions for HTML5 video and course sites | Text only | `ffmpeg -i x.srt x.vtt` | 3 |
| JPG to PNG | Very high | Weak | Native | | Not now |

| Pair | Accepts | Work (worker) | Outputs |
|---|---|---|---|
| `xlsx-to-json` | `xlsx` (the fourth set's kind) | `xlsxread`: the same parts as XLSX to CSV, then `Convert.sheetJson` | .json or .jsonl; all sheets as one JSON object, or a zip of .jsonl |
| `vtt-to-srt` | `vtt`: `WEBVTT` at the start, after a BOM | `Convert.parseVtt`, `Convert.writeSrt` | .srt |
| `srt-to-vtt` | `srt`: a .srt name, or a head that opens with a cue number and an SRT timing line | `Convert.parseSrt`, `Convert.writeVtt` | .vtt |

**XLSX to JSON.**
- Excel cells have types, so nothing is guessed: `sheetRows` gains a parallel matrix of cell kinds (`n` number, `b`
  boolean, `d` date or time, `s` text, `e` error). Numbers are written as the workbook stores them (valid JSON
  number text, so `0.1` stays `0.1`); booleans as `true` and `false`; dates and times as the ISO strings XLSX to CSV
  writes; errors and text as strings; empty cells as `null`.
- Options: `output` "json" (default) or "jsonl"; `header` (default on: the first row gives the keys, with the fifth
  set's key rules; off: rows as arrays); `sheets` "first" (default) or "all". All with JSON gives one object keyed by
  sheet name in tab order (`{"Results": [...], "Notes": [...]}`); all with JSON Lines gives one .jsonl per sheet in a
  zip. `unflatten` as on CSV to JSON.
- Formula protection does not apply (JSON is not opened by Excel). The XLSX caps and the 200 MB JSON cap apply.

**VTT to SRT.**
- `parseVtt`: the `WEBVTT` line and its header; NOTE, STYLE and REGION blocks skipped; an optional cue identifier;
  the timing line in `mm:ss.ttt` or `hh:mm:ss.ttt`, with cue settings after it dropped; the cue text up to a blank
  line.
- Text: `<b>`, `<i>` and `<u>` kept (SRT players read them); voice tags `<v Ana>` become the text alone, or
  `Ana: text` with the "Keep speaker names" option (default on, since lecture and meeting captions use them); class
  tags (`<c.yellow>`), `<lang>`, `<ruby>` and inline timestamps (`<00:00:01.200>`, used by auto-captions) removed;
  `&amp;`, `&lt;`, `&gt;`, `&nbsp;` and numeric entities decoded.
- Auto-captions from YouTube repeat each line in the next cue as it scrolls up. The "Merge repeated caption lines"
  option (default on) drops a cue's first line when it equals the previous cue's last line and the file has inline
  timestamps, the mark of those captions. A cue left empty by that is dropped.
- `writeSrt`: cues numbered from 1, `hh:mm:ss,ttt --> hh:mm:ss,ttt`, CRLF line ends, a blank line between cues.

**SRT to VTT.**
- `parseSrt`: BOM, CRLF, missing or wrong cue numbers, extra blank lines, a `.` instead of `,` in times, and the
  `X1:` position coordinates some files carry after the timing are all tolerated. A block without a timing line is
  skipped with a note.
- Text: `<b>`, `<i>`, `<u>` kept; `<font>` tags removed and their text kept (VTT has no font tag); `{\an8}`-style ASS
  tags removed; a literal `<` or `&` escaped.
- `writeVtt`: `WEBVTT`, a blank line, then each cue as `hh:mm:ss.ttt --> hh:mm:ss.ttt`; cue numbers kept as
  identifiers, since some players and editors use them.

**Shared.** Kinds `vtt` and `srt` in `kindOf`, before the CSV branch, so a .txt holding SRT is not called CSV. The two
subtitle pairs use the worker (small files, but one path). Index: 19 cards, positions 38 to 40, Photo to Logo to 41.
Sibling links between the two subtitle pages, from Transcript Cleaner to both, and from XLSX to CSV and CSV to JSON to
XLSX to JSON. Branch `tools-converters-6`, one PR, squash-merged when green.

**Tests against reference outputs.**
- XLSX to JSON: workbooks written with openpyxl (numbers, booleans, dates in both date systems, a formula with a
  cached value written by LibreOffice-style XML, text, errors, empty cells, a hidden sheet) and the real ABDC list;
  openpyxl reads each with `data_only=True` and a Python script applies the same rules; the page's JSON must parse to
  the same values.
- Subtitles: fixtures with the edge cases above, each converted by ffmpeg; cue starts, ends and text (after the same
  tag rules, where ffmpeg's differ, as documented) must match. YouTube-style auto-captions are checked against a
  hand-written expected file, since ffmpeg does not merge repeated lines.
- Node tests for every reader and writer; browser runs in WebKit and Firefox under the production CSP.

**Resolved after review (two Goldfish reviewers on Sonnet, 2026-11-03).** These replace the text above where they
differ.

- **Kinds**, checked after the SVG test and before XLSX, JSON and CSV: `vtt` when the head (after a UTF-8 BOM) starts
  `WEBVTT` followed by a space, tab, line break or the end; `srt` for a .srt name, or a head that is a number line and an
  SRT timing line. A UTF-16 file (its BOM) named .srt or .vtt takes that kind. `KIND_NAMES` "SRT" and "WebVTT";
  `article` learns SRT. A .txt holding SRT is now `srt`, so the CSV pages refuse it by name.
- **Table rows.** `xlsx-to-json`: xlsx, json (default) or jsonl, `work: "xlsxread"`, 50 MB. `vtt-to-srt`: vtt, srt,
  `work: "subs"`, 5 MB. `srt-to-vtt`: srt, vtt, `work: "subs"`, 5 MB. `MIME` gains `srt` (application/x-subrip) and
  `vtt` (text/vtt).
- **Options.** New `speakers` and `merge`, default on; `bom` (SRT output, default off) and `encoding` (subtitle
  input, Detect by default, through `decodeText`) are reused. VTT output is UTF-8 without a BOM.
- **The merge rule** acts only in files with inline timestamps (auto-captions), and only in two shapes: a cue whose
  single line repeats the previous cue's last line and that lasts 50 ms or less (the flash cue YouTube puts between
  rolls) is dropped; in a cue of two or more lines whose later line carries inline timestamps, a first line that repeats
  the previous cue's last line is dropped. Lines are compared after tags are removed. Two genuine identical captions
  ("No." then "No.") fit neither shape. The row says how many lines were merged.
- **Subtitle text.** Voice tags give "Name: " when the speaker changes, not on every cue; `<rt>` readings are dropped
  with their tags; `&lrm;` and `&rlm;` are decoded with the rest, once. SRT to VTT keeps `b`, `i` and `u` in any case,
  removes every other tag (font, s, span and the like) and ASS overrides such as `{\an8}` with a note that positioning
  was not kept, and escapes every other `<`, `>` and `&`, so `-->` in text cannot end a cue. Cue numbers are not kept
  as identifiers. A fraction with fewer than three digits is read as a decimal (`,5` is 500 ms; ffmpeg reads 5 ms, a
  documented difference). In a VTT block, a later line with `-->` starts a new cue, so a missing blank line does not
  merge two cues. Output names keep the base (`lecture.en.vtt` gives `lecture.en.srt`); the summary is "N cues, the
  last ending at hh:mm:ss"; no cues gives "This file has no captions."
- **XLSX to JSON.** `sheetRows(xml, shared, styles, date1904, maxCells, safe, withKinds)`: with `withKinds`, it also
  returns one string per row with a character per cell (`n` number, `b` boolean, `d` date or time, `s` text, `e`
  error, space for a gap); XLSX to CSV does not pass it and is unchanged. The worker passes `safe` false. Numbers are
  written as stored when the text fits the JSON number grammar, else as `String(Number(t))` when finite, else `null`
  with a note; date-times use `T` (`2026-11-03T14:05:00`), not the CSV space. Leading and trailing empty rows are
  trimmed and empty rows inside skipped; the header is the first row left. "First sheet" is the first visible sheet.
  All sheets with JSON give one object keyed by sheet name, written by hand in tab order; with JSON Lines, a zip of
  `name-sheets/<sheet>.jsonl`. The JSON writer of CSV to JSON is shared (`jsonWrite`), not copied, and its 200 MB
  estimate covers all sheets together. Workbook opening (zip, index, rels, shared strings, styles, sheet list) moves
  into one worker helper both XLSX pages use.
- **Found in passing.** `parseSharedStrings` read a self-closing `<si/>` (and `<t/>`) as the start of a string that
  swallowed the next one, shifting every later shared string in XLSX to CSV by one cell. Fixed with a test.
- **Index:** 19 cards, positions 38 to 40, Photo to Logo to 41. Transcript Cleaner's related list links both subtitle
  pages. **Build order:** core, readers and writers with tests, worker, pages, registration, site tests, browser runs.

## Seventh set: ranking from data, then PDF to Text, Excel to LaTeX, Image to Base64

The parent session, 2026-11-03: before a seventh set, check search volume or Search Console data for conversions not
built yet, which live pages get impressions, and what the leading converter sites rank for that this site lacks.

**What the data says (Search Console, purplelink.llc, 2026-08-04 to 2026-11-01, read 2026-11-03).**
- None of the 19 converter pages has an impression yet. The first set went out with the 2026-11-02 build, after the
  window closes, so the site's own data cannot rank converters yet. The 90-day read in the Concepts brief stands.
- The conversion queries the site already gets are academic formats: "latex to word" (68 impressions, position 51.6),
  "word to latex" (51, 35.8, plus variants), "pdf to markdown for scientific equations" (25, 27.7), "docx to tex",
  "latex table to word", "doi to citation", "bibtex to citation", "latex zip to pdf". Each already has a tool (LaTeX to
  Word, Word to LaTeX, File to Markdown, LaTeX Table Generator, Citation Generator, Reference Converter, LaTeX to
  PDF), several of them server-side. An in-browser twin of a server tool would compete with it for the same query, so
  those are not rebuilt.
- Tool pages with impressions in the window: Citation Generator 577, LaTeX Diff 549, BibTeX Validator 418, Word to
  LaTeX 398, LaTeX to Word 372, /tools/ 252, LaTeX to PDF 227; the rest under 100.

**Rerank on 2026-11-24.** Search Console holds no converter data yet (the window above ends 2026-11-01, before the first
converter build). On 2026-11-24 the converter pages will have about three weeks of impressions: rerank the candidates
below with real per-page impressions and queries before an eighth set, and drop or merge any page the 90-day rule in
the Concepts brief would flag.

**Volume.** No keyword tool is connected (no Semrush, Ahrefs or DataForSEO account), and web searches for public
figures on the candidate phrases returned none, so the volume column below is relative, judged from how many dedicated
converter sites hold each head term. That is weaker than measured volume, and the 90-day read is the real test.

**What the leading converter sites carry that this site lacks.** CloudConvert, FreeConvert and Convertio list
document (PDF, DOCX, XLSX), image (PNG, JPG, SVG, WEBP), audio, video and ebook conversions. Against the 19 pages here,
the gaps that run in a browser without a new library are: PDF to text, image to Base64 and back, JPG to PNG, and the
spreadsheet-to-code family (Excel to LaTeX, Excel to Markdown or HTML tables). Audio, video, ebook and OCR need a
library this site does not carry (an MP3 encoder, ffmpeg, an EPUB renderer, an OCR engine) and stay out.

| Candidate | Volume (relative) | Fit | Browser fit | Reference | Rank |
|---|---|---|---|---|---|
| PDF to Text | High (every converter site has it) | Researchers pulling text from papers without uploading them | pdf.js, already vendored | Known text, and pypdf's `extract_text` | 2 |
| Excel to LaTeX | Medium (a handful of table generators hold it) | Papers: the LaTeX Table Generator takes pasted CSV, not a workbook | The XLSX readers of the fourth set | pandoc reads the LaTeX back into cells | 1 |
| Image to Base64 | High (developer tool sites) | Web pages, email templates, CSS and JSON payloads | Native | the `base64` command | 3 |
| Base64 to Image | Medium | The reverse | Native | the `base64` command | Next |
| JPG to PNG | Very high | Weak | Native | | Not now |
| Excel to Markdown or HTML table | Medium | Docs and READMEs | XLSX readers | pandoc | Next |
| Server-tool twins (Markdown to Word, PDF to Markdown, LaTeX to Word) | | | | | Not built: they would compete with the server tools |

| Pair | Accepts | Where | Outputs |
|---|---|---|---|
| `pdf-to-text` | `pdf` | On the page, through pdf.js, as PDF to JPG does (`work: "pdftext"`) | .txt, UTF-8 |
| `xlsx-to-latex` | `xlsx` | The worker: `openWorkbook`, `sheetRows` with kinds, `Convert.latexTable` | .tex |
| `image-to-base64` | png, jpeg, gif, webp, avif, bmp, svg, ico | The worker: bytes to Base64 in the core (`Convert.base64`) | .txt, plus a Copy button on the row |

**PDF to Text.** `getTextContent` per page; items are joined into lines by `hasEOL` and by a change in baseline, and
lines into paragraphs where the gap between baselines is larger than the line height (option `layout`: "paragraphs",
the default, or "lines" to keep the PDF's own line breaks). A hyphen at the end of a line joins the word when the next
line starts with a lowercase letter. Pages are separated by a blank line, or by a form feed (`\f`, as pdftotext
writes) with the "Mark page breaks" option. `pages` (the PDF to JPG range, not remembered) picks pages. A PDF with no
text on any page gets "This PDF has no text layer, so it is probably a scan. Text from a scan needs OCR, which this page
does not do." Reference: pypdf's `extract_text` on the same files; after whitespace is collapsed and line-end hyphens
joined in both, the word sequence must match at 98% or more (pdf.js and pypdf order some items differently).

**Excel to LaTeX.** One `tabular` per sheet: booktabs rules (`\toprule`, `\midrule` after the header, `\bottomrule`)
or `\hline` with booktabs off; a column is right-aligned when every non-empty cell in it is a number, else
left-aligned; LaTeX specials (`& % $ # _ { } ~ ^ \`) escaped; numbers as stored, dates as ISO. Options: `sheets`
"first" (first visible) or "all" (one table each, in one .tex); `header` (default on); `booktabs` (default on, the
row notes `\usepackage{booktabs}`); `float` (default on: a `table` environment with `\caption{<sheet name>}` and
`\label{tab:<slug>}`). Reference: pandoc reads the .tex back (`-f latex -t json`), and its table cells must equal
openpyxl's values for the same cells.

**Image to Base64.** The file's bytes, unchanged, as Base64 (no line breaks), with the MIME type from the sniffed
kind. Option `format`: "dataurl" (`data:image/png;base64,...`, the default), "base64" (the bare string), "css"
(`background-image: url("data:...")`) or "html" (`<img src="data:..." alt="">`). Up to 10 MB; over 100 KB the row
notes that a data URL that large slows a page down. The row has a Copy button (the shell's new `copyText` result
field, through `navigator.clipboard.writeText`) and the .txt download. Reference: `base64` on macOS gives the same
string.

**Shared.** Index: 22 cards, positions 41 to 43, Photo to Logo to 44. Sitemap, Buddy, social cards and slugs as
before; PDF to Text links to PDF to JPG and File to Markdown; Excel to LaTeX to the LaTeX Table Generator, XLSX to CSV
and XLSX to JSON (and the LaTeX Table Generator links back); Image to Base64 to SVG to PNG and PNG to JPG.

**Resolved after review (one Goldfish reviewer on Sonnet, design and readiness together, 2026-11-03).**
- The ranking is by fit to this site's audience, which is the only evidence the data gives: Excel to LaTeX first (the
  academic queries above), PDF to Text second (a different query from File to Markdown's "pdf to markdown", which
  stays the server tool for structure and equations; each page links the other), Image to Base64 third, on fit to the
  developers who use the site's other in-browser tools, the weakest of the three. The 2026-11-24 rerank decides
  whether it stays.
- PDF to Text: a space goes in where the gap between items is wider than a fifth of the font size; ligatures are folded
  (NFKC) and soft hyphens removed; the line-end hyphen rule is a heuristic, said so in the limits; text runs in content
  order, and two-column pages can interleave (a limit). Option keys `layout` ("paragraphs" or "lines") and
  `pagebreaks` (form feeds); `pages` is reused and not remembered. A page without text is named in a note.
- Excel to LaTeX: a row whose first cell starts with `[` is wrapped in braces so `\\` cannot take it as an optional
  argument; line breaks inside cells become spaces; captions are escaped and labels unique; the worker passes `safe`
  false; the output is a fragment with a booktabs note. Keys `booktabs` and `float` (default on); `sheets` "all" here
  is one .tex with a table per sheet.
- Image to Base64: `IMAGE_MIME` maps kinds to types (jpeg to image/jpeg, svg to image/svg+xml, ico to image/x-icon);
  every output is .txt; the Copy button appears up to 2 MB of text, and past that the row says to download.
- Reference tests: PDF to Text is compared with the known text of fixtures made for it (one column, two columns, a
  ligature, a hyphenated line break), as a token LCS ratio over the known token count: 100% on one column, at least
  95% on two; pypdf is a second, looser check. Excel to LaTeX is read back by pandoc (`-f latex-smart`) and its cells
  compared with openpyxl's after whitespace is collapsed. Every Base64 format is decoded back to the original bytes.

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

Fourth set, two Goldfish reviewers on Sonnet (design, implementation readiness), zero context, 2026-11-03. What
changed: the TIFF reader became the core's own after the reviewers' UTIF findings were confirmed on fixtures
(looping directory chain, PackBits copied raw, `toRGBA8` gaps); formula protection added, on by default for text
cells; the long-integer reviver replaced by a pre-pass that works in every browser; option keys, kind order,
caps, names and messages specified; tests named. The browser runs then found two more: formulas saved with an empty
`<v>` were not counted, and RGB JPEG-in-TIFF needed the Adobe marker in WebKit. Both fixed with tests.


Fifth set, two Goldfish reviewers on Sonnet (design, implementation readiness), zero context, 2026-11-03. What
changed: types inferred per column with a round-trip test (the first draft would have typed 90210 but not 02134 in
one column, and turned 3.50 into 3.5); JSON written by hand in header order; an output-size cap; one key
uniquifier; ICNS names by type, with ARGB, mask and JPEG 2000 rules; a lenient ICO reader with bounds checked before
allocation and the Windows mask rule; kinds placed after the ftyp branch; option names kept apart from the existing
ones; committed fixtures with independent references. The reference runs then found ARGB colors stored
premultiplied, and the canvas rounding that the PNG writer removed.

Sixth set, two Goldfish reviewers on Sonnet (design, implementation readiness), zero context, 2026-11-03. What
changed: the auto-caption merge narrowed to two shapes so genuine repeats survive; subtitle encodings read through
`decodeText`; cell kinds opt-in so XLSX to CSV is unchanged; no formula guard in JSON; number text checked against the
JSON grammar; date-times with T; row and column bounds and a slot cap before padding; kinds, table rows, options,
messages and names specified. Found while testing against the references: a self-closing `<si/>` shifted every later
shared string (fixed, affects XLSX to CSV); literal CR LF inside workbook XML was not normalized to LF as XML requires
(fixed, affects XLSX to CSV). Against openpyxl, the 116,200 cells of the ABDC workbook differ only where empty text
cells become null (documented) and where openpyxl leaves `_xHHHH_` escapes undecoded (it does not follow the spec).


**2026-11-03, seventh set (Excel to LaTeX, PDF to Text, Image to Base64).** Ranked from Search Console fit (no converter
impressions yet) and the competitor gap; rerank on 2026-11-24. One Goldfish reviewer on Sonnet; findings resolved
above. Tested in WebKit and Firefox, headless, under the production CSP, with 0 CSP violations and 0 bytes sent while
converting. Excel to LaTeX: each `.tex` read back with `pandoc -f latex-smart` matches openpyxl on every cell of the
edge, book and ABDC (2,653 rows) workbooks, apart from three expected differences. Numbers are written as stored (`.5`,
`1.234567890123457e+19`), a hidden sheet is skipped, and TeX typesets `'` as a right quote. PDF to Text: the two-column
fixture matches its known text token for token. The one-column fixture differs in one word, because reportlab's
base-14 Helvetica cannot encode the ffi ligature, so pypdf cannot recover it either. Paragraphs and the hyphen join
come out right. Image to Base64: PNG, SVG and ICO outputs in every format decode back to the original bytes. Found
while testing: refusals said "a XLSX"; `article()` now covers XLSX.
