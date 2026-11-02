libheif-js 1.23.5 (npm package libheif-js, files libheif-wasm/libheif.js and libheif-wasm/libheif.wasm), unmodified.
libheif with the libde265 HEVC decoder, compiled to WebAssembly with Emscripten. LGPL-3.0, see LICENSE.

Source: https://github.com/catdad-experiments/libheif-js (build scripts) and https://github.com/strukturag/libheif
(the library). Used by the HEIC to JPG converter (/tools/heic-to-jpg/), loaded in its Web Worker with importScripts.

The converter calls the library only through these two files, so you can replace them with your own build of the same
version (same file names, same folder) and the page will use it.

sha256
376c0bb483c23ac458cd22d718074693748ea75eddc3e4929353d4153e365a2e  libheif.js
184d3d20f8323877f13e9f5254f9c6a0ce272c9a3a2f823b0b2bcd2ee9f73f80  libheif.wasm
