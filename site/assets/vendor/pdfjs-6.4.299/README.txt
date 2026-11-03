pdf.js 6.4.299 (pdfjs-dist), Apache-2.0, https://github.com/mozilla/pdf.js. Self-hosted for PDF to JPG (/tools/pdf-to-jpg/), the
Thesis Format Checker and the Camera-Ready Checker.
Copied unchanged from the npm package pdfjs-dist@6.4.299 (https://registry.npmjs.org/pdfjs-dist/-/pdfjs-dist-6.4.299.tgz,
integrity sha512-AVl138zALtfaAPvADulE0PZThbYzCBS79nL4pOSL/6Sm/4AH5A21BD9VHt97OlCuzJuCpmeZtAtkinisF4Vb1g==).
wasm/ holds the image decoders pdf.js fetches by name: jbig2.wasm (PDFium JBIG2, BSD-3-Clause), openjpeg.wasm
(OpenJPEG, BSD-2-Clause) and qcms_bg.wasm (qcms color management, MIT); their licenses are beside them.
The folder name carries the version because pdf.js requests wasm/ files without a ?v= stamp and /assets/vendor/*
is cached as immutable. To update: copy the same files from a newer pdfjs-dist into a new versioned folder.

SHA-256:
57456c8e0c81e46be31174b499ef77f2b9f5ee46d04412ba627320a36755d4c2  pdf.min.mjs
9536359f1b8367850d485731ca1d5e45c159a7b7a0912325e539937aa21ceb18  pdf.worker.min.mjs
466f45c2a61a698152fb5400c27e56ff2ceb73dcb71fde3fc366a502308eaab0  wasm/jbig2.wasm
95e5002597af0824004aa57b1900fe019715db389e37640b1e58395e42f00cc5  wasm/openjpeg.wasm
663d86126d5f5fcb1c61490f94353e2a8375660b8c5498ab3ebab5a34b08800e  wasm/qcms_bg.wasm
