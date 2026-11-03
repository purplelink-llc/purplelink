UTIF.js 3.1.0 (Photopea, MIT, https://github.com/photopea/UTIF.js), a TIFF decoder, self-hosted for TIFF to JPG
(/tools/tiff-to-jpg/). Downloaded 2026-11-03 with Ben's approval from https://registry.npmjs.org/utif/-/utif-3.1.0.tgz,
integrity sha512-WEo4D/xOvFW53K5f5QTaTbbiORcm2/pCL9P6qmJnup+17eYfKaEhDeX9PeQkuyEoIxlbGklDuGl8xwuXYMrrXQ==, and copied unchanged.
pako_inflate.min.js is pako 1.0.11 (MIT and Zlib, https://github.com/nodeca/pako), the version UTIF names, copied
unchanged from an npm install (https://registry.npmjs.org/pako/-/pako-1.0.11.tgz). UTIF uses it for Deflate TIFFs and
reads self.pako when it loads, so the worker loads pako first. UTIF's replaceIMG and _imgLoaded helpers, the only
code that touches document or XHR, are never called.

SHA-256:
e3e76115f49571e39624c3316a76b3c4c5b2c5ca518dfec4b66a9f7af8c6d059  UTIF.js
2ca27e9a8dae569cdeac42752ed1aed1afeff7f19282d3cc12c0aaa54a08bc04  pako_inflate.min.js
