// Thesis Format Checker. Everything runs in the browser: the PDF is read with a
// self-hosted copy of pdf.js and never uploaded. Checks are text-based, so a
// scanned thesis (images of pages) has nothing to measure.
(() => {
  "use strict";

  const PT = 72; // PDF points per inch
  const LETTER = [612, 792];
  const A4 = [595.28, 841.89];
  const MAX_BYTES = 200 * 1024 * 1024;
  const FONT_SAMPLE_PAGES = 30;

  const $ = (id) => document.getElementById(id);
  const drop = $("tf-drop");
  const fileInput = $("tf-file");
  const status = $("tf-status");
  const out = $("tf-results");
  const dl = $("tf-download");
  let lastReport = "";

  // ---------- settings ----------
  const PRESETS = {
    common: { left: 1, right: 1, top: 1, bottom: 1 },
    binding: { left: 1.5, right: 1, top: 1, bottom: 1 },
  };
  const preset = $("tf-preset");
  const m = { left: $("tf-ml"), right: $("tf-mr"), top: $("tf-mt"), bottom: $("tf-mb") };
  preset.addEventListener("change", () => {
    const p = PRESETS[preset.value];
    if (!p) return;
    Object.keys(m).forEach((k) => { m[k].value = p[k]; });
  });
  Object.values(m).forEach((el) => el.addEventListener("input", () => { preset.value = "custom"; }));

  const settings = () => ({
    paper: $("tf-paper").value,
    margins: Object.fromEntries(Object.keys(m).map((k) => [k, Math.max(0, parseFloat(m[k].value) || 0)])),
    minFont: Math.max(0, parseFloat($("tf-font").value) || 0),
    spacing: $("tf-spacing").value,
  });

  // ---------- small helpers ----------
  const median = (a) => {
    if (!a.length) return NaN;
    const s = [...a].sort((x, y) => x - y);
    const h = s.length >> 1;
    return s.length % 2 ? s[h] : (s[h - 1] + s[h]) / 2;
  };
  const inch = (pt) => (pt / PT).toFixed(2);
  const romanToInt = (r) => {
    const v = { i: 1, v: 5, x: 10, l: 50, c: 100, d: 500, m: 1000 };
    let t = 0;
    const s = r.toLowerCase();
    for (let i = 0; i < s.length; i++) {
      const a = v[s[i]], b = v[s[i + 1]] || 0;
      t += a < b ? -a : a;
    }
    return t;
  };
  const isRoman = (s) => /^[ivxlcdm]{1,7}$/i.test(s) && /^(m{0,3})(cm|cd|d?c{0,3})(xc|xl|l?x{0,3})(ix|iv|v?i{0,3})$/i.test(s);
  const pageList = (arr, max = 12) =>
    arr.length <= max ? arr.join(", ") : arr.slice(0, max).join(", ") + " and " + (arr.length - max) + " more";

  const setStatus = (msg, busy) => {
    status.textContent = msg;
    status.classList.toggle("is-busy", !!busy);
  };

  // ---------- analysis ----------
  async function analyze(file, opt) {
    setStatus("Loading the PDF reader.", true);
    const pdfjs = await import("/assets/vendor/pdfjs/pdf.min.mjs");
    pdfjs.GlobalWorkerOptions.workerSrc = "/assets/vendor/pdfjs/pdf.worker.min.mjs";
    const data = new Uint8Array(await file.arrayBuffer());
    const task = pdfjs.getDocument({ data });
    const pdf = await task.promise;
    const n = pdf.numPages;

    const pages = [];
    const sizeChars = new Map(); // font size (0.5 pt bins) -> characters
    const fontUse = new Map(); // fontName id -> { chars, name, embedded }
    const repeats = new Map(); // header/footer candidates
    const sampleEvery = Math.max(1, Math.ceil(n / FONT_SAMPLE_PAGES));

    for (let p = 1; p <= n; p++) {
      if (p % 5 === 1 || p === n) setStatus("Reading page " + p + " of " + n + ".", true);
      const page = await pdf.getPage(p);
      const vp = page.getViewport({ scale: 1 });
      const content = await page.getTextContent();
      const items = [];
      for (const it of content.items) {
        if (!it.str || !it.str.trim()) continue;
        const tx = pdfjs.Util.transform(vp.transform, it.transform);
        const size = Math.hypot(tx[2], tx[3]);
        if (!(size > 0)) continue;
        const left = tx[4];
        const right = left + Math.abs(it.width) * vp.scale;
        const base = tx[5];
        items.push({
          str: it.str, font: it.fontName, size, left, right,
          top: base - size * 0.78, bottom: base + size * 0.22, base,
        });
      }
      let fontInfo = null;
      if (p === 1 || p % sampleEvery === 0) {
        try { await page.getOperatorList(); fontInfo = page.commonObjs; } catch (e) { fontInfo = null; }
      }
      for (const it of items) {
        const bin = Math.round(it.size * 2) / 2;
        sizeChars.set(bin, (sizeChars.get(bin) || 0) + it.str.length);
        let f = fontUse.get(it.font);
        if (!f) { f = { chars: 0, name: null, embedded: null }; fontUse.set(it.font, f); }
        f.chars += it.str.length;
        if (fontInfo && f.name === null) {
          try {
            if (fontInfo.has(it.font)) {
              const o = fontInfo.get(it.font);
              f.name = String(o.name || o.loadedName || it.font).replace(/^[A-Z]{6}\+/, "");
              // pdf.js 6 reports missingFile as true for every font, so it cannot be
              // used. An embedded font program carries a mimetype; a base font left
              // out of the file does not. Type 3 fonts are always in the file.
              f.embedded = o.isType3Font ? true : !!o.mimetype && o.mimetype !== "null";
            }
          } catch (e) { /* font not resolved on this page */ }
        }
        const key = it.str + "|" + Math.round(it.left / 3) + "|" + Math.round(it.base / 3);
        repeats.set(key, (repeats.get(key) || 0) + 1);
      }
      pages.push({ n: p, w: vp.width, h: vp.height, items });
      page.cleanup();
    }
    await task.destroy();
    return { n, pages, sizeChars, fontUse, repeats };
  }

  function evaluate(raw, opt) {
    const { n, pages, sizeChars, fontUse, repeats } = raw;
    const results = [];
    const add = (status, title, summary, details) => results.push({ status, title, summary, details: details || [] });

    const totalChars = [...sizeChars.values()].reduce((a, b) => a + b, 0);
    if (totalChars < 200) {
      return [{
        status: "Review",
        title: "No readable text",
        summary: "This PDF has almost no text to measure. If it is a scan of printed pages, run OCR first or check the pages by hand.",
        details: [],
      }];
    }

    // Page size
    const dims = pages.map((p) => [Math.min(p.w, p.h), Math.max(p.w, p.h)]);
    const near = (d, ref) => Math.abs(d[0] - ref[0]) < 4 && Math.abs(d[1] - ref[1]) < 4;
    const wanted = opt.paper === "a4" ? [A4] : opt.paper === "letter" ? [LETTER] : [LETTER, A4];
    const label = opt.paper === "a4" ? "A4" : opt.paper === "letter" ? "US Letter (8.5 x 11 in)" : "US Letter or A4";
    const off = pages.filter((p, i) => !wanted.some((r) => near(dims[i], r))).map((p) => p.n);
    add(off.length ? "Review" : "Pass", "Page size",
      off.length ? off.length + " page(s) are not " + label + ": " + pageList(off) + "."
        : "All " + n + " pages are " + label + ".");

    // Detect running headers and footers (same text at the same place on 4+ pages).
    // Only text inside the top or bottom 1.25 in can be a running header or
    // footer; body text that happens to repeat (a template, a form) stays.
    const isRepeated = (it, pg) =>
      n >= 6 && (it.top < 1.25 * PT || it.bottom > pg.h - 1.25 * PT) &&
      (repeats.get(it.str + "|" + Math.round(it.left / 3) + "|" + Math.round(it.base / 3)) || 0) >= 4;

    // Page numbers and margins
    const labels = [];
    const bodyByPage = [];
    pages.forEach((pg) => {
      const bandBottom = pg.h - 1.0 * PT;
      const bandTop = 1.0 * PT;
      let num = null;
      for (const it of pg.items) {
        const s = it.str.trim();
        if (!/^(\d{1,4}|[ivxlcdm]{1,7})$/i.test(s)) continue;
        if (/^[ivxlcdm]+$/i.test(s) && !isRoman(s)) continue;
        const inBottom = it.top > bandBottom, inTop = it.bottom < bandTop;
        if (!inBottom && !inTop) continue;
        const cx = (it.left + it.right) / 2;
        const pos = (inBottom ? "bottom " : "top ") + (cx < pg.w * 0.35 ? "left" : cx > pg.w * 0.65 ? "right" : "center");
        const dist = inBottom ? pg.h - it.bottom : it.top;
        if (!num || dist < num.dist) num = { s, pos, dist, it };
      }
      labels.push(num ? { page: pg.n, label: num.s, pos: num.pos, roman: /^[ivxlcdm]+$/i.test(num.s) } : { page: pg.n, label: null });
      bodyByPage.push(pg.items.filter((it) => !(num && it === num.it) && !isRepeated(it, pg)));
    });

    // Margins
    const tol = 0.03 * PT;
    const mm = { left: opt.margins.left * PT, right: opt.margins.right * PT, top: opt.margins.top * PT, bottom: opt.margins.bottom * PT };
    const bad = { left: [], right: [], top: [], bottom: [] };
    const worst = { left: Infinity, right: Infinity, top: Infinity, bottom: Infinity };
    let checked = 0;
    pages.forEach((pg, i) => {
      const body = bodyByPage[i];
      if (body.length < 3) return;
      checked++;
      const L = Math.min(...body.map((x) => x.left));
      const R = pg.w - Math.max(...body.map((x) => x.right));
      const T = Math.min(...body.map((x) => x.top));
      const B = pg.h - Math.max(...body.map((x) => x.bottom));
      const v = { left: L, right: R, top: T, bottom: B };
      Object.keys(v).forEach((k) => {
        worst[k] = Math.min(worst[k], v[k]);
        if (v[k] < mm[k] - tol) bad[k].push(pg.n);
      });
    });
    const sides = ["left", "right", "top", "bottom"];
    const anyBad = sides.some((k) => bad[k].length);
    add(anyBad ? "Review" : "Pass", "Margins",
      anyBad
        ? "Text comes closer to the edge than your minimums on some pages."
        : "On " + checked + " pages with text, nothing comes closer to an edge than your minimums.",
      sides.map((k) => {
        const w = isFinite(worst[k]) ? inch(worst[k]) : "-";
        return k[0].toUpperCase() + k.slice(1) + ": minimum " + opt.margins[k].toFixed(2) + " in, closest text " + w + " in" +
          (bad[k].length ? ", too close on pages " + pageList(bad[k]) : "");
      }).concat(["Page numbers and lines repeated on four or more pages (running headers and footers) are left out of this measure."]));

    // Page numbers
    const withLabel = labels.filter((l) => l.label);
    const firstLabelIdx = labels.findIndex((l) => l.label);
    const seq = labels.slice(firstLabelIdx < 0 ? 0 : firstLabelIdx);
    const missing = seq.filter((l) => !l.label).map((l) => l.page);
    const arabic = withLabel.filter((l) => !l.roman);
    const roman = withLabel.filter((l) => l.roman);
    const breaks = [];
    for (let i = 1; i < withLabel.length; i++) {
      const a = withLabel[i - 1], b = withLabel[i];
      if (a.roman !== b.roman) continue;
      const av = a.roman ? romanToInt(a.label) : parseInt(a.label, 10);
      const bv = b.roman ? romanToInt(b.label) : parseInt(b.label, 10);
      if (bv !== av + 1 && b.page === a.page + 1) breaks.push("PDF page " + b.page + " is numbered " + b.label + " after " + a.label);
    }
    const positions = [...new Set(withLabel.map((l) => l.pos))];
    let pnStatus = "Pass";
    const pnDetails = [];
    if (!withLabel.length) {
      pnStatus = "Review";
      pnDetails.push("No page numbers were found within an inch of the top or bottom edge.");
    } else {
      pnDetails.push("Numbers found on " + withLabel.length + " of " + n + " pages. Position: " + positions.join(", ") + ".");
      if (roman.length) pnDetails.push("Roman numerals on " + roman.length + " pages (PDF pages " + roman[0].page + " to " + roman[roman.length - 1].page + ").");
      if (arabic.length) pnDetails.push("Arabic numbers begin on PDF page " + arabic[0].page + " with " + arabic[0].label + ".");
      if (missing.length) { pnStatus = "Review"; pnDetails.push("No number found on PDF pages " + pageList(missing) + ". Some programs omit numbers on chapter-opening pages; check yours."); }
      if (breaks.length) { pnStatus = "Review"; pnDetails.push("Sequence breaks: " + pageList(breaks, 5) + "."); }
      if (positions.length > 2) { pnStatus = "Review"; pnDetails.push("The number moves between several positions."); }
    }
    add(pnStatus, "Page numbers", pnStatus === "Pass" ? "Numbers run in sequence." : "Check the numbering.", pnDetails);

    // Font size
    const sizes = [...sizeChars.entries()].sort((a, b) => b[1] - a[1]);
    const body = sizes[0][0];
    const small = sizes.filter(([s]) => s < opt.minFont - 0.2).reduce((a, [, c]) => a + c, 0);
    const smallShare = small / totalChars;
    const fsStatus = opt.minFont && body < opt.minFont - 0.2 ? "Review" : "Pass";
    add(fsStatus, "Font size",
      "Body text is " + body + " pt (" + Math.round((sizes[0][1] / totalChars) * 100) + "% of characters)." +
        (opt.minFont ? (smallShare > 0.005 ? " " + (smallShare * 100).toFixed(1) + "% of characters are below " + opt.minFont + " pt, which is normal for footnotes, captions and page numbers." : "") : ""),
      sizes.slice(0, 6).map(([s, c]) => s + " pt: " + (c / totalChars * 100).toFixed(1) + "% of characters"));

    // Fonts
    const fonts = [...fontUse.values()].filter((f) => f.name).sort((a, b) => b.chars - a.chars);
    const notEmb = fonts.filter((f) => f.embedded === false);
    add(!fonts.length ? "Info" : notEmb.length ? "Review" : "Pass", "Fonts",
      !fonts.length ? "Font names could not be read."
        : notEmb.length ? notEmb.length + " font(s) are not embedded, which many repositories and publishers reject."
          : "All " + fonts.length + " fonts read from sampled pages are embedded.",
      fonts.slice(0, 8).map((f) => f.name + (f.embedded === false ? " (not embedded)" : "")).concat(["Fonts were read from up to " + FONT_SAMPLE_PAGES + " sampled pages."]));

    // Line spacing
    const ratios = [];
    pages.forEach((pg, i) => {
      const lines = new Map();
      bodyByPage[i].filter((it) => Math.abs(it.size - body) < 0.6).forEach((it) => {
        const k = Math.round(it.base * 2) / 2;
        lines.set(k, Math.min(lines.get(k) ?? Infinity, it.left));
      });
      const ys = [...lines.keys()].sort((a, b) => a - b);
      for (let j = 1; j < ys.length; j++) {
        const d = ys[j] - ys[j - 1];
        if (d > body * 0.95 && d < body * 3.2) ratios.push(d / body);
      }
    });
    if (ratios.length > 30) {
      const r = median(ratios);
      const kind = r < 1.35 ? "single" : r < 1.85 ? "about 1.5" : "double";
      const want = opt.spacing;
      let st = "Info";
      if (want === "double") st = r >= 1.85 ? "Pass" : "Review";
      else if (want === "onehalf") st = r >= 1.35 ? "Pass" : "Review";
      add(st, "Line spacing",
        "Typical distance between lines is " + r.toFixed(2) + " times the font size, which reads as " + kind + " spacing.",
        ["This is measured on body text and is approximate. Word double spacing is about 2.3 times the font size and LaTeX double spacing about 2.0, so the cut-offs here are 1.35 for 1.5 and 1.85 for double.",
          want === "any" ? "You chose not to require a spacing." : "You require " + (want === "double" ? "double" : "1.5") + " spacing."]);
    } else {
      add("Info", "Line spacing", "Too few lines of body text to measure spacing.");
    }

    // Front matter headings
    const heads = [
      ["Title or approval page", /^(approval|approved|signature page|committee)/i],
      ["Copyright", /^(copyright|©)/i],
      ["Dedication", /^dedication/i],
      ["Acknowledgments", /^acknowledg(e)?ments?$/i],
      ["Abstract", /^abstract$/i],
      ["Table of contents", /^(table of contents|contents)$/i],
      ["List of tables", /^list of tables$/i],
      ["List of figures", /^list of figures$/i],
      ["List of abbreviations", /^(list of (abbreviations|symbols|acronyms)|abbreviations|nomenclature)$/i],
      ["First chapter", /^(chapter\s+(1|one|i)\b|1\s+introduction|introduction$)/i],
    ];
    const found = [];
    const limit = Math.min(n, 40);
    heads.forEach(([name, re]) => {
      for (let i = 0; i < limit; i++) {
        const lines = new Map();
        pages[i].items.forEach((it) => {
          const k = Math.round(it.base);
          lines.set(k, (lines.get(k) || "") + (lines.get(k) ? " " : "") + it.str.trim());
        });
        // A heading is short, has no dot leaders and does not end in a page number (a contents entry does).
        if ([...lines.values()].some((t) => { const s = t.trim(); return s.length < 60 && !/\.{3,}|\s\d{1,4}$/.test(s) && re.test(s); })) { found.push([pages[i].n, name]); break; }
      }
    });
    found.sort((a, b) => a[0] - b[0]);
    add("Info", "Front matter found",
      found.length ? "Headings found in the first " + limit + " pages, in order." : "No standard front-matter headings were found in the first " + limit + " pages.",
      found.map(([pn, name]) => name + ": PDF page " + pn).concat(["Compare this order with your graduate school's checklist. Rules differ between universities."]));

    return results;
  }

  // ---------- rendering ----------
  function render(results, fileName, pagesN) {
    out.textContent = "";
    const counts = { Pass: 0, Review: 0, Info: 0 };
    results.forEach((r) => { counts[r.status] = (counts[r.status] || 0) + 1; });
    const h = document.createElement("h2");
    h.textContent = "Results for " + fileName;
    out.appendChild(h);
    const sum = document.createElement("p");
    sum.className = "tf-summary";
    sum.textContent = pagesN + " pages. " + counts.Pass + " checks passed, " + counts.Review + " to review, " + counts.Info + " for information.";
    out.appendChild(sum);
    const txt = ["Thesis Format Checker report for " + fileName, sum.textContent, ""];
    results.forEach((r) => {
      const card = document.createElement("section");
      card.className = "tf-card tf-" + r.status.toLowerCase();
      const head = document.createElement("h3");
      const tag = document.createElement("span");
      tag.className = "tf-tag";
      tag.textContent = r.status;
      head.appendChild(tag);
      head.appendChild(document.createTextNode(" " + r.title));
      card.appendChild(head);
      const p = document.createElement("p");
      p.textContent = r.summary;
      card.appendChild(p);
      if (r.details.length) {
        const ul = document.createElement("ul");
        r.details.forEach((d) => { const li = document.createElement("li"); li.textContent = d; ul.appendChild(li); });
        card.appendChild(ul);
      }
      out.appendChild(card);
      txt.push("[" + r.status + "] " + r.title, r.summary, ...r.details.map((d) => "  - " + d), "");
    });
    txt.push("Checked in the browser at purplelink.llc/tools/thesis-format-checker/. The file was not uploaded.");
    lastReport = txt.join("\n");
    dl.hidden = false;
    out.hidden = false;
    out.focus({ preventScroll: false });
  }

  async function run(file) {
    if (!file) return;
    out.hidden = true;
    dl.hidden = true;
    if (!/\.pdf$/i.test(file.name) && file.type !== "application/pdf") { setStatus("Choose a PDF file.", false); return; }
    if (file.size > MAX_BYTES) { setStatus("That file is over 200 MB. Compress it or check a part of it.", false); return; }
    try {
      const raw = await analyze(file, settings());
      lastRaw = { raw, name: file.name };
      render(evaluate(raw, settings()), file.name, raw.n);
      setStatus("Done. Nothing left your browser.", false);
    } catch (e) {
      console.error("thesis-format-checker:", e);
      setStatus("This PDF could not be read" + (e && e.name === "PasswordException" ? " because it is password protected." : ".") +
        (e && e.message && /import|module|MIME|fetch/i.test(e.message) ? " The PDF reader did not load; reload the page and try again." : ""), false);
    }
  }

  let lastRaw = null;
  const rerun = () => { if (lastRaw) render(evaluate(lastRaw.raw, settings()), lastRaw.name, lastRaw.raw.n); };
  ["tf-paper", "tf-font", "tf-spacing", "tf-preset", "tf-ml", "tf-mr", "tf-mt", "tf-mb"].forEach((id) => $(id).addEventListener("change", rerun));

  fileInput.addEventListener("change", () => run(fileInput.files[0]));
  ["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("is-over"); }));
  ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("is-over"); }));
  drop.addEventListener("drop", (e) => { const f = e.dataTransfer.files[0]; if (f) run(f); });
  dl.addEventListener("click", () => {
    const url = URL.createObjectURL(new Blob([lastReport], { type: "text/plain" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "thesis-format-report.txt";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  });
})();
