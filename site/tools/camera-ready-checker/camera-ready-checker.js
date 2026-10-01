// Camera-Ready PDF Checker. Everything runs in the browser: the PDF is read with
// a self-hosted copy of pdf.js and never uploaded. Checks read the text layer,
// the font table, annotations and the document information dictionary. Nothing
// here replaces the publisher's own validator.
(() => {
  "use strict";

  const PT = 72; // PDF points per inch
  const LETTER = [612, 792];
  const A4 = [595.28, 841.89];
  const MAX_BYTES = 200 * 1024 * 1024;
  const FONT_ALL_PAGES = 40; // read fonts on every page up to this many pages

  const $ = (id) => document.getElementById(id);
  const drop = $("cr-drop");
  const fileInput = $("cr-file");
  const status = $("cr-status");
  const out = $("cr-results");
  const dl = $("cr-download");
  let lastReport = "";
  let lastRaw = null;

  // ---------- venue presets ----------
  // Only values read from the publisher's own pages on 2026-10-01 are filled in.
  // A blank margin means the publisher's pages did not state it in a form that
  // could be checked, so the author fills it in from the template.
  const PRESETS = {
    ieee: {
      name: "IEEE conference",
      paper: "letter", m: { l: "", r: "", t: "", b: "" }, numbers: "report", heads: "report", links: "none",
      note: "IEEE publishes a US Letter and an A4 conference template, so set the page size your conference names. The margin fields are blank because IEEE's template page gives no margin numbers; fill them in from your template. IEEE Xplore asks for every font embedded or subset and for no bookmarks or links.",
      todo: [
        "If your conference uses IEEE PDF eXpress, run the file through it. It is the check IEEE Xplore accepts, and it also looks at PDF creation settings, security settings, attachments and crop marks, which are only partly visible here.",
        "If your conference does not use PDF eXpress, IEEE points authors to the IEEE PDF Checker.",
        "Remove all guidance text from the template. IEEE says a paper with template text left in may not be published.",
        "Check the title and every author name for accuracy. IEEE says no changes can be made once the paper is in IEEE Xplore.",
      ],
    },
    acm: {
      name: "ACM (acmart sigconf)",
      paper: "letter", m: { l: 0.75, r: 0.75, t: 0.79, b: 1.01 }, numbers: "none", heads: "report", links: "report",
      note: "Page size and margins are the acmart class settings for sigconf: 8.5 by 11 in, 54 pt at each side, 57 pt at the top and 73 pt at the bottom, measured to the header and footer. The sigconf format prints conference headers and no page numbers by default. ACM says margin adjustments are not allowed.",
      todo: [
        "For conferences that use TAPS, you upload a zip of your source, not this PDF. TAPS builds the PDF and HTML itself and reports validation errors. Use this check on the PDF proof TAPS sends back, or on your own build before you upload.",
        "The TAPS uploader takes a zip under 10 MB; larger zips go by the FTP link on the same page.",
        "Use only LaTeX packages on ACM's accepted list, and add the rights commands you were sent after completing the rights form. TAPS reports both as validation errors.",
        "Give every figure a \\Description, and check the CCS concepts and keywords.",
      ],
    },
    lncs: {
      name: "Springer LNCS",
      paper: "either", m: { l: "", r: "", t: "", b: "" }, numbers: "none", heads: "none", links: "report",
      note: "Springer's instructions for authors say there is no need for page numbers or running heads, because Springer adds them. They give no page size or margin numbers, so those fields are blank; the page size and text area come from the llncs class or the Word template. Springer's typesetters rebuild the paper from your source files.",
      todo: [
        "Send the source files (LaTeX with style files and figures, or Word) together with the PDF. Springer needs both.",
        "Send the signed license-to-publish form.",
        "Mark the corresponding author, and check how each author name should appear in the running heads and the author index.",
        "Read the proof Springer's typesetters send back. They insert the running heads, final page numbers and copyright line.",
      ],
    },
    neurips: {
      name: "NeurIPS",
      paper: "letter", m: { l: 1.5, r: 1.5, t: "", b: "" }, numbers: "report", heads: "report", links: "report",
      note: "The NeurIPS 2026 formatting instructions ask for US Letter, a text rectangle 5.5 in wide and 9 in long, and a left margin of 1.5 in, which leaves 1.5 in on the right. They give no top or bottom margin, so those fields are blank. They ask for Type 1 or embedded TrueType fonts only, and say files with Type 3 or non-embedded fonts will be sent back.",
      todo: [
        "Compile with the final option of the current year's style file. Without it the paper is anonymized and has line numbers.",
        "The 2026 instructions allow nine content pages; acknowledgments, references, the checklist and optional appendices do not count. Enter the limit that applies to you above.",
        "Include the paper checklist the instructions ask for.",
        "Check figure positions and overfull lines by eye. The instructions name hand-positioned figures as the usual cause of margin problems.",
      ],
    },
    custom: {
      name: "Custom",
      paper: "either", m: { l: "", r: "", t: "", b: "" }, numbers: "report", heads: "report", links: "report",
      note: "Type the page size, margins, page limit and file-size limit from your venue's author instructions. Any field left blank is measured and reported without a verdict.",
      todo: [
        "Run the publisher's own validator if there is one, and the venue's LaTeX or Word style check.",
        "Send the copyright or license form, which usually goes through a separate page.",
      ],
    },
  };

  const venue = $("cr-venue");
  const note = $("cr-venue-note");
  const mEl = { l: $("cr-ml"), r: $("cr-mr"), t: $("cr-mt"), b: $("cr-mb") };
  const applyPreset = () => {
    const p = PRESETS[venue.value] || PRESETS.custom;
    $("cr-paper").value = p.paper;
    Object.keys(mEl).forEach((k) => { mEl[k].value = p.m[k]; });
    $("cr-numbers").value = p.numbers;
    $("cr-heads").value = p.heads;
    $("cr-links").value = p.links;
    note.textContent = p.note;
  };
  venue.addEventListener("change", applyPreset);
  applyPreset();

  const num = (el) => { const v = parseFloat(el.value); return isFinite(v) && v > 0 ? v : null; };
  const settings = () => ({
    venue: venue.value,
    preset: PRESETS[venue.value] || PRESETS.custom,
    paper: $("cr-paper").value,
    margins: { left: num(mEl.l), right: num(mEl.r), top: num(mEl.t), bottom: num(mEl.b) },
    limit: num($("cr-limit")) ? Math.floor(num($("cr-limit"))) : null,
    maxMB: num($("cr-size")),
    numbers: $("cr-numbers").value,
    heads: $("cr-heads").value,
    links: $("cr-links").value,
  });

  // ---------- small helpers ----------
  const inch = (pt) => (pt / PT).toFixed(2);
  const plural = (n, w) => n + " " + w + (n === 1 ? "" : "s");
  const fmtSize = (b) => b >= 1048576 ? (b / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(b / 1024)) + " KB";
  // 1, 2, 3, 5 -> "1 to 3, 5"
  const pageRanges = (arr, max = 14) => {
    const s = [...new Set(arr)].sort((a, b) => a - b);
    const parts = [];
    for (let i = 0; i < s.length; i++) {
      let j = i;
      while (j + 1 < s.length && s[j + 1] === s[j] + 1) j++;
      parts.push(j > i + 1 ? s[i] + " to " + s[j] : j === i + 1 ? s[i] + ", " + s[j] : String(s[i]));
      i = j;
    }
    return parts.length <= max ? parts.join(", ") : parts.slice(0, max).join(", ") + " and more";
  };
  const pagesWord = (arr) => (new Set(arr).size === 1 ? "page " : "pages ") + pageRanges(arr);
  const clip = (s, n = 90) => { const t = String(s).trim().replace(/\s+/g, " "); return t.length > n ? t.slice(0, n) + "..." : t; };
  const sizeName = (w, h) => {
    const d = [Math.min(w, h), Math.max(w, h)];
    const near = (ref) => Math.abs(d[0] - ref[0]) < 4 && Math.abs(d[1] - ref[1]) < 4;
    return near(LETTER) ? "US Letter" : near(A4) ? "A4" : inch(w) + " x " + inch(h) + " in";
  };

  const setStatus = (msg, busy) => {
    status.textContent = msg;
    status.classList.toggle("is-busy", !!busy);
  };

  // Wait for a font object pdf.js is still binding, but never hang on one.
  const fontObj = (page, id) => new Promise((resolve) => {
    let done = false;
    const finish = (o) => { if (!done) { done = true; resolve(o || null); } };
    try {
      if (page.commonObjs.has(id)) { finish(page.commonObjs.get(id)); return; }
      page.commonObjs.get(id, finish);
    } catch (e) { finish(null); }
    setTimeout(() => finish(null), 1500);
  });

  // ---------- reading the PDF ----------
  async function analyze(file) {
    setStatus("Loading the PDF reader.", true);
    const pdfjs = await import("/assets/vendor/pdfjs/pdf.min.mjs");
    pdfjs.GlobalWorkerOptions.workerSrc = "/assets/vendor/pdfjs/pdf.worker.min.mjs";
    const data = new Uint8Array(await file.arrayBuffer());
    const task = pdfjs.getDocument({ data, verbosity: 0 });
    const pdf = await task.promise;
    const n = pdf.numPages;
    const OPS = pdfjs.OPS;
    const imageOps = new Set([OPS.paintImageXObject, OPS.paintInlineImageXObject, OPS.paintImageXObjectRepeat].filter((x) => x !== undefined));

    // Fonts: every page up to FONT_ALL_PAGES, then an even sample.
    const fontPages = new Set();
    if (n <= FONT_ALL_PAGES) for (let p = 1; p <= n; p++) fontPages.add(p);
    else {
      const step = n / FONT_ALL_PAGES;
      for (let i = 0; i < FONT_ALL_PAGES; i++) fontPages.add(Math.min(n, 1 + Math.floor(i * step)));
      fontPages.add(n);
    }

    const pages = [];
    const fonts = new Map(); // font id -> { name, embedded, type3, pages }
    let linksExternal = 0, linksInternal = 0, otherAnnots = 0, fontsUnread = 0;
    const linkPages = [];
    const imagePages = [];
    let imageCount = 0;

    for (let p = 1; p <= n; p++) {
      if (p % 3 === 1 || p === n) setStatus("Reading page " + p + " of " + n + ".", true);
      const page = await pdf.getPage(p);
      const vp = page.getViewport({ scale: 1 });
      const content = await page.getTextContent();
      const items = [];
      const ids = new Set();
      for (const it of content.items) {
        if (!it.str || !it.str.trim()) continue;
        const tx = pdfjs.Util.transform(vp.transform, it.transform);
        const size = Math.hypot(tx[2], tx[3]);
        if (!(size > 0)) continue;
        ids.add(it.fontName);
        const w = Math.abs(it.width) * vp.scale;
        const rotated = Math.abs(tx[1]) > Math.abs(tx[0]);
        const o = rotated
          ? { left: tx[4] - size * 0.78, right: tx[4] + size * 0.22, top: Math.min(tx[5], tx[5] - Math.sign(tx[1]) * w), bottom: Math.max(tx[5], tx[5] - Math.sign(tx[1]) * w), base: tx[5] }
          : { left: tx[4], right: tx[4] + w, top: tx[5] - size * 0.78, bottom: tx[5] + size * 0.22, base: tx[5] };
        items.push({ str: it.str, size, rotated, ...o });
      }

      if (fontPages.has(p)) {
        try {
          const ops = await page.getOperatorList();
          let imgs = 0;
          for (let i = 0; i < ops.fnArray.length; i++) {
            const fn = ops.fnArray[i];
            if (fn === OPS.setFont && ops.argsArray[i] && typeof ops.argsArray[i][0] === "string") ids.add(ops.argsArray[i][0]);
            else if (imageOps.has(fn)) imgs++;
          }
          if (imgs) { imagePages.push(p); imageCount += imgs; }
          for (const id of ids) {
            let f = fonts.get(id);
            if (!f) {
              const o = await fontObj(page, id);
              if (!o) { fontsUnread++; continue; }
              f = {
                name: String(o.name || (o.isType3Font ? "unnamed Type 3 font" : id)).replace(/^[A-Z]{6}\+/, ""),
                type3: !!o.isType3Font,
                // pdf.js 6 reports missingFile as true for every font on the main thread,
                // so the converted font's mimetype is the signal: it is only set when the
                // PDF carried a font program.
                embedded: o.isType3Font ? true : !!o.mimetype && o.mimetype !== "null",
                pages: [],
              };
              fonts.set(id, f);
            }
            f.pages.push(p);
          }
        } catch (e) { fontsUnread++; }
      }

      try {
        const annots = await page.getAnnotations();
        let here = 0;
        for (const a of annots) {
          if (a.subtype === "Link") { here++; if (a.url || a.unsafeUrl) linksExternal++; else linksInternal++; }
          else if (a.subtype !== "Popup") otherAnnots++;
        }
        if (here) linkPages.push(p);
      } catch (e) { /* annotations unreadable on this page */ }

      pages.push({ n: p, w: vp.width, h: vp.height, items });
      page.cleanup();
    }

    let info = {}, xmpTitle = null, outlineCount = 0, attachments = 0;
    try {
      const md = await pdf.getMetadata();
      info = md.info || {};
      try { xmpTitle = md.metadata ? md.metadata.get("dc:title") : null; } catch (e) { xmpTitle = null; }
    } catch (e) { info = {}; }
    try { const o = await pdf.getOutline(); outlineCount = o ? o.length : 0; } catch (e) { outlineCount = 0; }
    try { const a = await pdf.getAttachments(); attachments = a ? Object.keys(a).length : 0; } catch (e) { attachments = 0; }
    await task.destroy();

    return {
      n, pages, fonts: [...fonts.values()], fontPages: [...fontPages], fontsUnread,
      linksExternal, linksInternal, otherAnnots, linkPages, imagePages, imageCount,
      info, xmpTitle, outlineCount, attachments, bytes: file.size, fileName: file.name,
    };
  }

  // Join the glyph runs of one line into segments, so "R" + "EFERENCES" in small
  // caps reads as one heading and a two-column line stays two segments.
  function segments(pg) {
    const its = pg.items.filter((it) => !it.rotated).sort((a, b) => (Math.abs(a.base - b.base) < 2 ? a.left - b.left : a.base - b.base));
    const segs = [];
    let cur = null;
    for (const it of its) {
      const gap = cur ? it.left - cur.right : 0;
      if (cur && Math.abs(it.base - cur.base) < 2 && gap < Math.max(it.size, cur.size) * 0.6 && gap > -Math.max(it.size, cur.size)) {
        cur.str += (gap > Math.max(it.size, cur.size) * 0.18 ? " " : "") + it.str;
        cur.right = Math.max(cur.right, it.right);
        cur.top = Math.min(cur.top, it.top);
        cur.bottom = Math.max(cur.bottom, it.bottom);
        cur.items.push(it);
      } else {
        cur = { str: it.str, left: it.left, right: it.right, top: it.top, bottom: it.bottom, base: it.base, items: [it] };
        segs.push(cur);
      }
    }
    segs.forEach((s) => { s.text = s.str.trim().replace(/\s+/g, " "); });
    return segs;
  }

  // ---------- evaluation ----------
  function evaluate(raw, opt) {
    const { n, pages } = raw;
    const results = [];
    const add = (status, title, summary, details) => results.push({ status, title, summary, details: (details || []).filter(Boolean) });
    const totalChars = pages.reduce((a, pg) => a + pg.items.reduce((b, it) => b + it.str.length, 0), 0);
    const hasText = totalChars >= 200;
    const segsByPage = pages.map(segments);
    const band = 1.0 * PT;

    // Page numbers: a short numeric label alone in the top or bottom inch.
    const NUM_RE = /^(?:page\s*)?(\d{1,4})(?:\s*(?:of|\/)\s*\d{1,4})?$|^[-–]\s*(\d{1,4})\s*[-–]$/i;
    const cands = [];
    pages.forEach((pg, i) => {
      let best = null;
      const segs = segsByPage[i];
      const lowest = Math.max(...segs.map((x) => x.base)), highest = Math.min(...segs.map((x) => x.base));
      for (const s of segs) {
        // Inside the outer inch, or the last or first line of the page when the margin is wider than that.
        const inBottom = s.top > pg.h - band || (s.base >= lowest - 2 && s.top > pg.h * 0.8);
        const inTop = s.bottom < band || (s.base <= highest + 2 && s.bottom < pg.h * 0.15);
        if (!inBottom && !inTop) continue;
        const m = NUM_RE.exec(s.text);
        if (!m) continue;
        const cx = (s.left + s.right) / 2;
        const dist = inBottom ? pg.h - s.bottom : s.top;
        const c = {
          page: pg.n, value: parseInt(m[1] || m[2], 10), seg: s, dist,
          pos: (inBottom ? "bottom " : "top ") + (cx < pg.w * 0.35 ? "left" : cx > pg.w * 0.65 ? "right" : "center"),
        };
        if (!best || dist < best.dist) best = c;
      }
      if (best) cands.push(best);
    });
    // Accept as page numbers when two labels step with the page, or a single-page file has one.
    let numbered = [];
    if (cands.length >= 2) {
      const ok = new Set();
      for (let i = 1; i < cands.length; i++) {
        const a = cands[i - 1], b = cands[i];
        if (b.value - a.value === b.page - a.page) { ok.add(a); ok.add(b); }
      }
      numbered = cands.filter((c) => ok.has(c));
    } else if (cands.length === 1 && n === 1) numbered = cands;
    const possible = cands.filter((c) => !numbered.includes(c));
    const numSegs = new Set(numbered.map((c) => c.seg));

    // Running heads and feet: the same text at the same height on several pages.
    const need = n <= 3 ? 2 : 3;
    const groups = new Map();
    pages.forEach((pg, i) => {
      for (const s of segsByPage[i]) {
        if (numSegs.has(s)) continue;
        const inBottom = s.top > pg.h - band, inTop = s.bottom < band;
        if (!inBottom && !inTop) continue;
        if (s.text.replace(/[\d\s\W]/g, "").length < 3) continue;
        const key = (inTop ? "t" : "b") + "|" + s.text.toLowerCase().replace(/\d+/g, "#") + "|" + Math.round((inTop ? s.base : pg.h - s.base) / 4);
        let g = groups.get(key);
        if (!g) { g = { text: s.text, where: inTop ? "top" : "bottom", pages: [], segs: [] }; groups.set(key, g); }
        if (!g.pages.includes(pg.n)) g.pages.push(pg.n);
        g.segs.push(s);
      }
    });
    const heads = n >= 2 ? [...groups.values()].filter((g) => g.pages.length >= need) : [];
    const headSegs = new Set(heads.flatMap((g) => g.segs));

    // 1. Fonts
    // Subsets of one typeface arrive as separate font objects; list each name once.
    const byName = new Map();
    raw.fonts.forEach((f) => {
      const k = f.name + "|" + f.embedded + "|" + f.type3;
      if (!byName.has(k)) byName.set(k, { ...f, pages: [] });
      byName.get(k).pages.push(...f.pages);
    });
    const fonts = [...byName.values()];
    const notEmb = fonts.filter((f) => !f.embedded);
    const type3 = fonts.filter((f) => f.type3);
    const sampled = raw.fontPages.length < n;
    const fontNote = sampled
      ? "This file has " + n + " pages, so fonts were read on " + raw.fontPages.length + " pages spread through it, not all of them."
      : "Fonts were read on every page.";
    if (!fonts.length) {
      add(hasText ? "Review" : "Info", "Fonts", hasText ? "The font table could not be read." : "No fonts were found, which is what a scanned or image-only PDF looks like.",
        [fontNote, "Check with pdffonts, or in Acrobat under File, Document Properties, Fonts."]);
    } else {
      const bad = notEmb.length || type3.length;
      const bits = [];
      if (notEmb.length) bits.push(plural(notEmb.length, "font") + (notEmb.length === 1 ? " is" : " are") + " not embedded");
      if (type3.length) bits.push(plural(type3.length, "Type 3 font") + " found");
      add(bad ? "Review" : "Pass", "Fonts",
        bad ? bits.join(", and ") + "." : (fonts.length === 1 ? "The one font is embedded and is not Type 3." : "All " + fonts.length + " fonts are embedded, and none is Type 3."),
        notEmb.map((f) => f.name + ": not embedded, " + pagesWord(f.pages))
          .concat(type3.map((f) => f.name + ": Type 3, " + pagesWord(f.pages)))
          .concat(notEmb.length ? ["IEEE Xplore asks for all fonts embedded or subset, and NeurIPS for Type 1 or embedded TrueType only. Rebuild the PDF with font embedding on; the base fonts (Times, Helvetica, Courier) are the usual ones left out, often inside a figure. You can confirm with pdffonts, or in Acrobat under File, Document Properties, Fonts."] : [])
          .concat(type3.length ? ["A Type 3 font is usually a bitmap font from an old TeX setup or from a figure made by a plotting library. NeurIPS says files with Type 3 fonts are sent back. Other publishers' validators may warn; this tool could not confirm what each one does, so run theirs. Look at the pages listed: if the font is inside a figure, export the figure again with Type 1 or TrueType text."] : [])
          .concat(fonts.filter((f) => f.embedded && !f.type3).slice(0, 10).map((f) => f.name + ": embedded, " + pagesWord(f.pages)))
          .concat([fontNote, raw.fontsUnread ? plural(raw.fontsUnread, "font reference") + " could not be read and " + (raw.fontsUnread === 1 ? "is" : "are") + " not in this list." : ""]));
    }

    // 2. Page size
    const want = opt.paper;
    const wantLabel = want === "a4" ? "A4" : want === "letter" ? "US Letter" : "US Letter or A4";
    const names = pages.map((pg) => sizeName(pg.w, pg.h));
    const bySize = new Map();
    names.forEach((nm, i) => { if (!bySize.has(nm)) bySize.set(nm, []); bySize.get(nm).push(pages[i].n); });
    const okName = (nm) => (want === "letter" ? nm === "US Letter" : want === "a4" ? nm === "A4" : nm === "US Letter" || nm === "A4");
    const wrong = names.map((nm, i) => (okName(nm) ? null : pages[i].n)).filter(Boolean);
    const mixed = bySize.size > 1;
    const landscape = pages.filter((pg) => pg.w > pg.h + 1).map((pg) => pg.n);
    add(wrong.length || mixed ? "Review" : "Pass", "Page size",
      mixed ? "The pages are not all one size."
        : wrong.length ? "The pages are " + names[0] + ", not " + wantLabel + "."
          : "All " + plural(n, "page") + " are " + names[0] + ".",
      (mixed || wrong.length ? [...bySize.entries()].map(([nm, ps]) => nm + ": " + pagesWord(ps)) : [])
        .concat(wrong.length && mixed ? ["Not " + wantLabel + ": " + pagesWord(wrong) + "."] : [])
        .concat(landscape.length ? ["Landscape: " + pagesWord(landscape) + "."] : [])
        .concat(want === "either" ? ["No single size is set for this venue here, so either US Letter or A4 passes as long as every page matches."] : [])
        .concat(mixed ? ["A page of another size usually comes from an included PDF figure or a page inserted from another file."] : []));

    // 3. Page count and where the references start
    const REF_RE = /^(?:(?:\d{1,2}|[ivx]{1,5})\.?\s+)?(references|bibliography|references and notes|literature cited)$/i;
    let refPage = null;
    for (let i = 0; i < pages.length && refPage === null; i++) {
      if (segsByPage[i].some((s) => s.text.length < 40 && REF_RE.test(s.text))) refPage = pages[i].n;
    }
    const refLine = refPage === null
      ? "No References or Bibliography heading was found, so the start of the references could not be placed."
      : "The References heading is on page " + refPage + ".";
    if (opt.limit) {
      const over = n > opt.limit;
      add(over ? "Review" : "Pass", "Page count",
        over ? "The file has " + plural(n, "page") + " against a limit of " + opt.limit + ", so it is " + plural(n - opt.limit, "page") + " over."
          : "The file has " + plural(n, "page") + ", within the limit of " + opt.limit + ".",
        [refLine,
          refPage !== null ? (refPage <= opt.limit ? "The references start within the limit of " + opt.limit + " pages." : "The references start after the limit, on page " + refPage + ", so the body alone runs past page " + opt.limit + ".") : "",
          over && refPage !== null && refPage <= opt.limit + 1 ? "If your venue does not count references toward the limit, the pages before the references may still fit. Check the call for papers." : "",
          "Limits differ between conferences and between paper types, and some exclude references or appendices. The number here is the one you typed."]);
    } else {
      add("Info", "Page count", "The file has " + plural(n, "page") + ". Type your venue's page limit above to compare.", [refLine]);
    }

    // 4. Margins
    const mm = opt.margins;
    const sides = ["left", "right", "top", "bottom"];
    const tol = 0.03 * PT;
    const worst = { left: null, right: null, top: null, bottom: null };
    const bad = { left: [], right: [], top: [], bottom: [] };
    let measured = 0;
    pages.forEach((pg, i) => {
      const skip = new Set();
      segsByPage[i].forEach((s) => { if (numSegs.has(s) || headSegs.has(s)) s.items.forEach((it) => skip.add(it)); });
      const body = pg.items.filter((it) => !skip.has(it));
      if (!body.length) return;
      measured++;
      const v = {
        left: Math.min(...body.map((x) => x.left)),
        right: pg.w - Math.max(...body.map((x) => x.right)),
        top: Math.min(...body.map((x) => x.top)),
        bottom: pg.h - Math.max(...body.map((x) => x.bottom)),
      };
      sides.forEach((k) => {
        if (!worst[k] || v[k] < worst[k].v) worst[k] = { v: v[k], page: pg.n };
        if (mm[k] !== null && v[k] < mm[k] * PT - tol) bad[k].push(pg.n);
      });
    });
    if (!measured) {
      add("Info", "Margins", "There is no text to measure.", ["Figures and rules are not measured, only text."]);
    } else {
      const anyMin = sides.some((k) => mm[k] !== null);
      const anyBad = sides.some((k) => bad[k].length);
      const blank = sides.filter((k) => mm[k] === null);
      add(anyBad ? "Review" : anyMin ? "Pass" : "Info", "Margins",
        anyBad ? "Text comes closer to the edge than the minimum on " + pagesWord([].concat(...sides.map((k) => bad[k]))) + "."
          : anyMin ? "On " + plural(measured, "page") + " with text, nothing comes closer to an edge than the minimums set."
            : "No minimums are set, so the closest text to each edge is reported without a verdict.",
        sides.map((k) => {
          const w = worst[k];
          return k[0].toUpperCase() + k.slice(1) + ": closest text " + inch(w.v) + " in (page " + w.page + ")" +
            (mm[k] !== null ? ", minimum " + mm[k].toFixed(2) + " in" + (bad[k].length ? ", too close on " + pagesWord(bad[k]) : "") : ", no minimum set");
        }).concat([
          blank.length && anyMin ? "No minimum is set for: " + blank.join(", ") + ". Fill it in from your template to have it checked." : "",
          "Only text is measured. Figures, rules and table borders that run into the margin are not seen, so look at wide figures yourself. Detected page numbers and running heads are left out and reported below.",
        ]));
    }

    // 5. Page numbers, headers and footers
    const pnDetails = [];
    let pnStatus = "Pass";
    if (numbered.length) {
      const pos = [...new Set(numbered.map((c) => c.pos))];
      pnDetails.push("Page numbers found on " + pagesWord(numbered.map((c) => c.page)) + " (" + pos.join(", ") + "), reading " + numbered[0].value + " to " + numbered[numbered.length - 1].value + ".");
      pnStatus = opt.numbers === "none" ? "Review" : "Info";
    }
    if (possible.length) {
      pnDetails.push("A lone number near the edge that may or may not be a page number: " + possible.map((c) => "\"" + c.seg.text + "\" on page " + c.page).slice(0, 6).join(", ") + ".");
      if (pnStatus === "Pass") pnStatus = "Info";
    }
    heads.forEach((g) => {
      pnDetails.push("Repeated at the " + g.where + " of " + pagesWord(g.pages) + ": \"" + clip(g.text, 70) + "\"");
    });
    if (heads.length) pnStatus = opt.heads === "none" ? "Review" : pnStatus === "Review" ? "Review" : "Info";
    if (!numbered.length && !possible.length && !heads.length) pnDetails.push("Nothing that looks like a page number or a repeated header or footer was found near the top or bottom edge.");
    pnDetails.push(opt.numbers === "none" ? "This venue is set to want no page numbers in the file you send." : "Page numbers are set to be reported only.");
    pnDetails.push(opt.heads === "none" ? "This venue is set to want no running heads." : "Running heads are set to be reported only. Some templates print conference headers on purpose.");
    add(pnStatus, "Page numbers, headers and footers",
      pnStatus === "Review" ? "The file has " + [numbered.length ? "page numbers" : "", heads.length ? "running heads" : ""].filter(Boolean).join(" and ") + " that this venue is set not to want."
        : numbered.length || heads.length ? "Found " + [numbered.length ? "page numbers" : "", heads.length ? "repeated headers or footers" : ""].filter(Boolean).join(" and ") + ". Check them against your template."
          : possible.length ? "No page numbers in sequence were found."
            : "No page numbers or running heads were found.",
      pnDetails);

    // 6. Metadata
    const info = raw.info || {};
    const str = (v) => (typeof v === "string" ? v.trim() : "");
    const title = str(info.Title), author = str(info.Author);
    const stem = raw.fileName.replace(/\.pdf$/i, "").toLowerCase();
    const titleIsFile = !!title && (/\.(tex|dvi|docx?|pdf|rtf|odt|ps)$/i.test(title) || /^microsoft word\s*-/i.test(title) || title.toLowerCase() === stem || /^(untitled|title|titel|paper|main|manuscript|template)$/i.test(title));
    const version = str(info.PDFFormatVersion);
    const oldVersion = version && parseFloat(version) < 1.4;
    const mdBad = !title || titleIsFile || !author || oldVersion || info.EncryptFilterName;
    add(mdBad ? "Review" : "Pass", "Metadata",
      !title ? "The PDF Title field is empty." : titleIsFile ? "The PDF Title field looks like a file name or a placeholder, not the paper's title."
        : !author ? "The PDF Author field is empty." : oldVersion ? "The PDF version is older than 1.4." : info.EncryptFilterName ? "The PDF has security settings." : "Title and Author fields are filled in.",
      ["Title: " + (title ? "\"" + clip(title, 120) + "\"" : "(empty)"),
        "Author: " + (author ? "\"" + clip(author, 120) + "\"" : "(empty)"),
        "PDF version: " + (version || "not stated") + ". Producer: " + (str(info.Producer) || "not stated") + ". Creator: " + (str(info.Creator) || "not stated") + ".",
        oldVersion ? "IEEE Xplore asks for PDF version 1.4 or later." : "",
        info.EncryptFilterName ? "The file is encrypted (" + info.EncryptFilterName + "). IEEE Xplore asks for no password or other security settings." : "",
        raw.attachments ? plural(raw.attachments, "file attachment") + " found inside the PDF. IEEE Xplore asks for none." : "",
        "Search engines and digital libraries read these fields. The Title should be the paper's title and the Author field should match the author list on the first page, in the same order.",
        "With LaTeX, set them with hypersetup{pdftitle=..., pdfauthor=...} unless your class does it for you (acmart does). In Word, use File, Info, Properties."]);

    // 7. Anonymity leftovers
    const anon = [];
    ["Author", "Title", "Subject", "Keywords", "Creator"].forEach((k) => {
      if (/anonym/i.test(str(info[k]))) anon.push("The PDF " + k + " field says \"" + clip(str(info[k]), 80) + "\".");
    });
    if (raw.xmpTitle && /anonym/i.test(String(raw.xmpTitle))) anon.push("The XMP title says \"" + clip(String(raw.xmpTitle), 80) + "\".");
    const LEFT = [
      [/anonymous\s+(author|submission)|anonymized\s+author|author\(s\)\s+anonymous/i, "Anonymous author text"],
      [/\bunder\s+(double[- ]blind\s+|blind\s+)?review\b/i, "\"Under review\""],
      [/\bdo\s+not\s+distribute\b/i, "\"Do not distribute\""],
      [/\bsubmitted\s+to\b.{0,80}\b(conference|workshop|symposium|journal)\b/i, "\"Submitted to\" line"],
      [/\bpaper\s+(id|#)\s*:?\s*\d+|\bsubmission\s+(id|#|number)\s*:?\s*\d+/i, "Submission number"],
    ];
    pages.forEach((pg, i) => {
      const segs = i === 0 ? segsByPage[i] : segsByPage[i].filter((s) => s.top > pg.h - band || s.bottom < band);
      LEFT.forEach(([re, label]) => {
        const hit = segs.find((s) => re.test(s.text));
        if (hit) anon.push(label + " on page " + pg.n + ": \"" + clip(hit.text, 80) + "\"");
      });
    });
    // Review-mode line numbers: a column of bare numbers sharing one right edge.
    const lineNumPages = [];
    pages.forEach((pg, i) => {
      const cols = new Map();
      segsByPage[i].forEach((s) => {
        if (!/^\d{1,4}$/.test(s.text)) return;
        const k = Math.round(s.right / 3);
        cols.set(k, (cols.get(k) || 0) + 1);
      });
      if ([...cols.values()].some((c) => c >= 15)) lineNumPages.push(pg.n);
    });
    if (lineNumPages.length) anon.push("Line numbers in the margin on " + pagesWord(lineNumPages) + ", which is what a review build looks like.");
    add(anon.length ? "Review" : "Pass", "Anonymity leftovers",
      anon.length ? "This file still carries " + plural(anon.length, "trace") + " of a blind submission." : "No blind-submission leftovers were found in the metadata, on the first page, or in the headers and footers.",
      anon.concat(["Looked for: \"Anonymous\" in the document information fields; and on the first page and in every header and footer, anonymous-author text, \"under review\", \"do not distribute\", a \"submitted to\" line, a submission number and review-mode line numbers in the margin.",
        anon.length ? "Rebuild from the camera-ready or final option of your template and set the real author names." : ""]));

    // 8. Links, bookmarks and images
    const links = raw.linksExternal + raw.linksInternal;
    const linkBad = opt.links === "none" && (links > 0 || raw.outlineCount > 0);
    add(linkBad ? "Review" : "Info", "Links, bookmarks and images",
      linkBad ? "The file has " + [links ? plural(links, "link") : "", raw.outlineCount ? "bookmarks" : ""].filter(Boolean).join(" and ") + ", and this venue is set to want none."
        : plural(links, "link") + ", " + (raw.outlineCount ? "bookmarks present" : "no bookmarks") + ", " + plural(raw.imageCount, "image") + ".",
      [links ? plural(raw.linksExternal, "web link") + " and " + plural(raw.linksInternal, "link") + " inside the document (citations, cross-references), on " + pagesWord(raw.linkPages) + "." : "No link annotations.",
        raw.outlineCount ? "The file has a bookmark outline with " + plural(raw.outlineCount, "top-level entry").replace("entrys", "entries") + "." : "No bookmark outline.",
        raw.otherAnnots ? plural(raw.otherAnnots, "other annotation") + " (comments, highlights or form fields). Remove review comments before you send the file." : "",
        opt.links === "none" ? "IEEE Xplore's requirements say no bookmarks or links. With LaTeX, loading hyperref with the draft option, or leaving it out, removes both." : "Links and bookmarks are set to be reported only.",
        raw.imageCount ? plural(raw.imageCount, "image") + " drawn on " + pagesWord(raw.imagePages) + (sampled ? " (among the pages read)." : ".") : "No raster images are drawn; any figures are vector graphics.",
        "Not checked: image resolution, color space (RGB or CMYK), transparency, and whether color figures stay readable in gray. A PDF has no linked images, so there is nothing missing to detect; open the pages listed and zoom to 400% to judge sharpness."]);

    // 9. File size
    if (opt.maxMB) {
      const over = raw.bytes > opt.maxMB * 1048576;
      add(over ? "Review" : "Pass", "File size",
        "The file is " + fmtSize(raw.bytes) + ", " + (over ? "over" : "within") + " the limit of " + opt.maxMB + " MB you typed.",
        over && raw.imageCount ? ["Large files usually come from uncompressed or very high resolution images. " + plural(raw.imageCount, "image") + " drawn on " + pagesWord(raw.imagePages) + "."] : []);
    } else {
      add("Info", "File size", "The file is " + fmtSize(raw.bytes) + ". Type your venue's limit above to compare.",
        ["None of the presets carries a PDF size limit, because none could be confirmed from the publishers' pages. Submission systems set their own."]);
    }

    // 10. What is left
    add("Info", "Still to do", "This check does not replace the publisher's validator or a person reading the PDF.",
      opt.preset.todo.concat([
        "Open the exact file you are about to send and read it once through: unresolved citations show as [?], and a figure that did not update shows only in the output.",
        hasText ? "" : "This PDF has almost no text layer. If it is a scan, none of the text checks above mean anything; build the PDF from the source instead.",
      ]));

    return results;
  }

  // ---------- rendering ----------
  function render(results, raw, opt) {
    out.textContent = "";
    const counts = { Pass: 0, Review: 0, Info: 0 };
    results.forEach((r) => { counts[r.status] = (counts[r.status] || 0) + 1; });
    const h = document.createElement("h2");
    h.textContent = "Results for " + raw.fileName;
    out.appendChild(h);
    const sum = document.createElement("p");
    sum.className = "cr-summary";
    sum.textContent = plural(raw.n, "page") + ", " + fmtSize(raw.bytes) + ", checked as " + opt.preset.name + ". " +
      plural(counts.Pass, "check") + " passed, " + counts.Review + " to review, " + counts.Info + " for information.";
    out.appendChild(sum);
    const txt = ["Camera-Ready PDF Checker report for " + raw.fileName, sum.textContent, ""];
    results.forEach((r) => {
      const card = document.createElement("section");
      card.className = "cr-card cr-" + r.status.toLowerCase();
      const head = document.createElement("h3");
      const tag = document.createElement("span");
      tag.className = "cr-tag";
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
    txt.push("Checked in the browser at purplelink.llc/tools/camera-ready-checker/. The file was not uploaded.");
    lastReport = txt.join("\n");
    dl.hidden = false;
    out.hidden = false;
  }

  async function run(file) {
    if (!file) return;
    out.hidden = true;
    dl.hidden = true;
    lastRaw = null;
    if (!/\.pdf$/i.test(file.name) && file.type !== "application/pdf") { setStatus("Choose a PDF file.", false); return; }
    if (file.size > MAX_BYTES) { setStatus("That file is over 200 MB, which is more than this page can read.", false); return; }
    try {
      const raw = await analyze(file);
      lastRaw = raw;
      const opt = settings();
      render(evaluate(raw, opt), raw, opt);
      out.focus({ preventScroll: false });
      setStatus("Done. Nothing left your browser.", false);
    } catch (e) {
      console.error("camera-ready-checker:", e);
      setStatus("This PDF could not be read" + (e && e.name === "PasswordException" ? " because it is password protected. Publishers do not accept protected files either." : ".") +
        (e && e.message && /import|module|MIME|fetch/i.test(e.message) ? " The PDF reader did not load; reload the page and try again." : ""), false);
    }
  }

  const rerun = () => { if (lastRaw) { const opt = settings(); render(evaluate(lastRaw, opt), lastRaw, opt); } };
  ["cr-venue", "cr-paper", "cr-ml", "cr-mr", "cr-mt", "cr-mb", "cr-limit", "cr-size", "cr-numbers", "cr-heads", "cr-links"]
    .forEach((id) => $(id).addEventListener("change", rerun));

  fileInput.addEventListener("change", () => run(fileInput.files[0]));
  ["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("is-over"); }));
  ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("is-over"); }));
  drop.addEventListener("drop", (e) => { const f = e.dataTransfer.files[0]; if (f) run(f); });
  dl.addEventListener("click", () => {
    const url = URL.createObjectURL(new Blob([lastReport], { type: "text/plain" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "camera-ready-report.txt";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  });
})();
