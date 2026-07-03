(function () {
  "use strict";

  var inputEl = document.getElementById("rc-input");
  var fromEl = document.getElementById("rc-from");
  var toEl = document.getElementById("rc-to");
  var runBtn = document.getElementById("rc-run");
  var copyBtn = document.getElementById("rc-copy");
  var statusEl = document.getElementById("rc-status");
  var resultEl = document.getElementById("rc-result");
  var outEl = document.getElementById("rc-out");
  var detectedEl = document.getElementById("rc-detected");

  if (!inputEl || !fromEl || !toEl || !runBtn) return;

  // A host page (e.g. a /format/references-for-*/ venue page) can preset
  // which output format is selected on load via data-default-to on the
  // tool container, so the widget opens already pointed at what that
  // venue's submission system wants.
  var container = document.querySelector("[data-default-to]");
  if (container) {
    var defaultTo = container.getAttribute("data-default-to");
    if (defaultTo && toEl.querySelector('option[value="' + defaultTo + '"]')) {
      toEl.value = defaultTo;
    }
  }

  // ---- Neutral model ----------------------------------------------
  // { type, title, authors:[...], year, container, volume, issue,
  //   pages, publisher, doi, url, abstract, keywords:[...] }

  // ---- Type maps ---------------------------------------------------
  // canonical neutral types: article, book, inproceedings, incollection,
  // techreport, phdthesis, mastersthesis, webpage, misc

  var BIBTEX_TYPE = {
    article: "article", book: "book", inproceedings: "inproceedings",
    conference: "inproceedings", incollection: "incollection",
    inbook: "incollection", techreport: "techreport",
    phdthesis: "phdthesis", mastersthesis: "mastersthesis",
    misc: "misc", online: "webpage", electronic: "webpage",
    booklet: "misc", manual: "misc", unpublished: "misc",
    proceedings: "inproceedings"
  };
  var NEUTRAL_TO_BIBTEX = {
    article: "article", book: "book", inproceedings: "inproceedings",
    incollection: "incollection", techreport: "techreport",
    phdthesis: "phdthesis", mastersthesis: "mastersthesis",
    webpage: "online", misc: "misc"
  };

  var RIS_TO_NEUTRAL = {
    JOUR: "article", BOOK: "book", CONF: "inproceedings",
    CPAPER: "inproceedings", CHAP: "incollection", RPRT: "techreport",
    THES: "phdthesis", ELEC: "webpage", GEN: "misc", ADVS: "misc",
    MGZN: "article", NEWS: "article"
  };
  var NEUTRAL_TO_RIS = {
    article: "JOUR", book: "BOOK", inproceedings: "CONF",
    incollection: "CHAP", techreport: "RPRT", phdthesis: "THES",
    mastersthesis: "THES", webpage: "ELEC", misc: "GEN"
  };

  // EndNote %0 reference types
  var ENDNOTE_TO_NEUTRAL = {
    "Journal Article": "article", "Book": "book",
    "Conference Proceedings": "inproceedings", "Conference Paper": "inproceedings",
    "Book Section": "incollection", "Report": "techreport",
    "Thesis": "phdthesis", "Web Page": "webpage", "Generic": "misc"
  };
  var NEUTRAL_TO_ENDNOTE = {
    article: "Journal Article", book: "Book",
    inproceedings: "Conference Proceedings", incollection: "Book Section",
    techreport: "Report", phdthesis: "Thesis", mastersthesis: "Thesis",
    webpage: "Web Page", misc: "Generic"
  };

  // ---- Helpers -----------------------------------------------------
  function emptyEntry() {
    return { type: "misc", title: "", authors: [], year: "", container: "",
      volume: "", issue: "", pages: "", publisher: "", doi: "",
      url: "", abstract: "", keywords: [] };
  }

  // Normalize a single author token to "Last, First".
  function normAuthor(raw) {
    var a = raw.trim().replace(/\s+/g, " ");
    if (!a) return "";
    if (a.indexOf(",") !== -1) return a; // already Last, First
    // "First Middle Last" -> "Last, First Middle"
    var parts = a.split(" ");
    if (parts.length === 1) return parts[0];
    var last = parts.pop();
    return last + ", " + parts.join(" ");
  }

  function makeKey(e) {
    var first = (e.authors[0] || "anon").replace(/,.*/, "").replace(/[^A-Za-z]/g, "").toLowerCase();
    if (!first) first = "anon";
    return first + (e.year || "");
  }

  function stripBraces(s) {
    return s.replace(/^[{"]+/, "").replace(/[}"]+$/, "").trim();
  }

  // ---- Detection ---------------------------------------------------
  function detect(text) {
    var t = text.trim();
    if (/^@\s*[A-Za-z]+\s*[{(]/.test(t)) return "bibtex";
    if (/^TY\s{2}-\s/m.test(text) || /^ER\s{2}-/m.test(text)) return "ris";
    if (/^%[0ATDJVNPIUKXR]\b/m.test(text) || /^%0\s/m.test(text)) return "endnote";
    // looser fallbacks
    if (/\bTY\s{2}-/.test(text)) return "ris";
    if (/^@[A-Za-z]/.test(t)) return "bibtex";
    return null;
  }

  // ---- Parsers -----------------------------------------------------
  function parseBibtex(text) {
    var entries = [];
    var re = /@\s*([A-Za-z]+)\s*\{\s*([^,\s]*)\s*,/g;
    var m;
    while ((m = re.exec(text)) !== null) {
      var typeRaw = m[1].toLowerCase();
      // find matching closing brace from the opening one
      var start = text.indexOf("{", m.index);
      var depth = 0, i = start, end = -1;
      for (; i < text.length; i++) {
        var c = text[i];
        if (c === "{") depth++;
        else if (c === "}") { depth--; if (depth === 0) { end = i; break; } }
      }
      if (end === -1) end = text.length;
      var body = text.slice(re.lastIndex, end);
      var e = emptyEntry();
      e.type = BIBTEX_TYPE[typeRaw] || "misc";
      parseBibtexFields(body, e);
      entries.push(e);
      re.lastIndex = end + 1;
    }
    return entries;
  }

  function parseBibtexFields(body, e) {
    // tokenize key = value pairs, respecting brace/quote balance
    var i = 0, n = body.length;
    while (i < n) {
      // read field name
      while (i < n && /[\s,]/.test(body[i])) i++;
      var ks = i;
      while (i < n && /[A-Za-z0-9_-]/.test(body[i])) i++;
      var key = body.slice(ks, i).trim().toLowerCase();
      while (i < n && /\s/.test(body[i])) i++;
      if (body[i] !== "=") { // skip stray content
        while (i < n && body[i] !== ",") i++;
        i++;
        continue;
      }
      i++; // skip =
      while (i < n && /\s/.test(body[i])) i++;
      var val = "";
      if (body[i] === "{") {
        var depth = 0;
        for (; i < n; i++) {
          var c = body[i];
          if (c === "{") { depth++; if (depth === 1) continue; }
          else if (c === "}") { depth--; if (depth === 0) { i++; break; } }
          val += c;
        }
      } else if (body[i] === '"') {
        i++;
        while (i < n && body[i] !== '"') { val += body[i]; i++; }
        i++;
      } else {
        while (i < n && body[i] !== "," ) { val += body[i]; i++; }
      }
      val = val.replace(/\s+/g, " ").trim();
      assignBibtexField(key, val, e);
      while (i < n && body[i] !== ",") i++;
      i++; // skip comma
    }
  }

  function assignBibtexField(key, val, e) {
    switch (key) {
      case "title": e.title = val; break;
      case "author": case "editor":
        e.authors = val.split(/\s+and\s+/i).map(normAuthor).filter(Boolean); break;
      case "year": e.year = (val.match(/\d{4}/) || [val])[0]; break;
      case "date": e.year = e.year || (val.match(/\d{4}/) || [""])[0]; break;
      case "journal": case "journaltitle": case "booktitle":
        e.container = e.container || val; break;
      case "volume": e.volume = val; break;
      case "number": case "issue": e.issue = val; break;
      case "pages": e.pages = val.replace(/--/g, "-"); break;
      case "publisher": case "school": case "institution":
        e.publisher = e.publisher || val; break;
      case "doi": e.doi = val.replace(/^https?:\/\/(dx\.)?doi\.org\//i, ""); break;
      case "url": e.url = val; break;
      case "abstract": e.abstract = val; break;
      case "keywords": e.keywords = val.split(/[;,]/).map(function (k) { return k.trim(); }).filter(Boolean); break;
    }
  }

  function splitTagged(text, tagRe, startTag) {
    // generic splitter for RIS/EndNote line-tagged formats
    var lines = text.split(/\r?\n/);
    var blocks = [];
    var cur = null;
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      if (startTag.test(line)) {
        if (cur && cur.length) blocks.push(cur);
        cur = [line];
      } else if (cur) {
        cur.push(line);
      }
    }
    if (cur && cur.length) blocks.push(cur);
    return blocks;
  }

  function parseRis(text) {
    var entries = [];
    // each entry starts at a TY line
    var blocks = splitTagged(text, null, /^TY\s{2}-/);
    blocks.forEach(function (block) {
      var e = emptyEntry();
      var lastTag = null;
      block.forEach(function (line) {
        var m = line.match(/^([A-Z][A-Z0-9])\s{2}-\s?(.*)$/);
        if (!m) {
          // continuation of previous value
          if (lastTag) appendRis(e, lastTag, line.trim());
          return;
        }
        var tag = m[1], val = m[2].trim();
        lastTag = tag;
        applyRis(e, tag, val);
      });
      entries.push(e);
    });
    return entries;
  }

  function applyRis(e, tag, val) {
    switch (tag) {
      case "TY": e.type = RIS_TO_NEUTRAL[val] || "misc"; break;
      case "TI": case "T1": e.title = val; break;
      case "AU": case "A1": case "A2":
        if (val) e.authors.push(normAuthor(val)); break;
      case "PY": case "Y1": e.year = e.year || (val.match(/\d{4}/) || [""])[0]; break;
      case "DA": e.year = e.year || (val.match(/\d{4}/) || [""])[0]; break;
      case "JO": case "JF": case "J2": case "T2":
        e.container = e.container || val; break;
      case "VL": e.volume = val; break;
      case "IS": e.issue = val; break;
      case "SP": e.pages = e.pages ? e.pages : val; e._sp = val; break;
      case "EP": e._ep = val; break;
      case "PB": e.publisher = e.publisher || val; break;
      case "DO": e.doi = val.replace(/^https?:\/\/(dx\.)?doi\.org\//i, ""); break;
      case "UR": case "L1": case "L2": e.url = e.url || val; break;
      case "AB": case "N2": e.abstract = e.abstract ? e.abstract + " " + val : val; break;
      case "KW": if (val) e.keywords.push(val); break;
    }
  }
  function appendRis(e, tag, extra) {
    if (!extra) return;
    if (tag === "AB" || tag === "N2") e.abstract += " " + extra;
    else if (tag === "TI" || tag === "T1") e.title += " " + extra;
  }

  function parseEndnote(text) {
    var entries = [];
    var blocks = splitTagged(text, null, /^%0\s/);
    // fall back: if no %0, treat blank-line separated chunks
    if (!blocks.length) {
      text.split(/\n\s*\n/).forEach(function (chunk) {
        if (/%[A-Z0-9]/.test(chunk)) blocks.push(chunk.split(/\r?\n/));
      });
    }
    blocks.forEach(function (block) {
      var e = emptyEntry();
      block.forEach(function (line) {
        var m = line.match(/^%([A-Z0-9])\s?(.*)$/);
        if (!m) return;
        applyEndnote(e, m[1], m[2].trim());
      });
      entries.push(e);
    });
    return entries;
  }

  function applyEndnote(e, tag, val) {
    switch (tag) {
      case "0": e.type = ENDNOTE_TO_NEUTRAL[val] || "misc"; break;
      case "T": e.title = val; break;
      case "A": if (val) e.authors.push(normAuthor(val)); break;
      case "D": e.year = e.year || (val.match(/\d{4}/) || [val])[0]; break;
      case "J": case "B": e.container = e.container || val; break;
      case "V": e.volume = val; break;
      case "N": e.issue = val; break;
      case "P": e.pages = val.replace(/--/g, "-"); break;
      case "I": e.publisher = e.publisher || val; break;
      case "R": e.doi = val.replace(/^https?:\/\/(dx\.)?doi\.org\//i, ""); break;
      case "U": e.url = e.url || val; break;
      case "X": e.abstract = val; break;
      case "K": if (val) e.keywords.push(val); break;
    }
  }

  // resolve RIS SP/EP into a page range after parsing
  function finalizePages(e) {
    if (e._sp && e._ep) e.pages = e._sp + "-" + e._ep;
    else if (e._sp && !e.pages) e.pages = e._sp;
    delete e._sp; delete e._ep;
  }

  // ---- Serializers -------------------------------------------------
  function serBibtex(e, idx) {
    var t = NEUTRAL_TO_BIBTEX[e.type] || "misc";
    var lines = ["@" + t + "{" + makeKey(e) + "," ];
    function f(k, v) { if (v) lines.push("  " + k + " = {" + v + "},"); }
    f("title", e.title);
    if (e.authors.length) f("author", e.authors.join(" and "));
    f("year", e.year);
    if (e.type === "article") f("journal", e.container);
    else if (e.type === "inproceedings" || e.type === "incollection") f("booktitle", e.container);
    else f("journal", e.container);
    f("volume", e.volume);
    f("number", e.issue);
    if (e.pages) lines.push("  pages = {" + e.pages.replace(/-/g, "--") + "},");
    f("publisher", e.publisher);
    f("doi", e.doi);
    f("url", e.url);
    f("abstract", e.abstract);
    if (e.keywords.length) f("keywords", e.keywords.join(", "));
    // drop trailing comma on last field
    var last = lines[lines.length - 1];
    lines[lines.length - 1] = last.replace(/,$/, "");
    lines.push("}");
    return lines.join("\n");
  }

  function serRis(e) {
    var lines = [];
    lines.push("TY  - " + (NEUTRAL_TO_RIS[e.type] || "GEN"));
    if (e.title) lines.push("TI  - " + e.title);
    e.authors.forEach(function (a) { lines.push("AU  - " + a); });
    if (e.year) lines.push("PY  - " + e.year);
    if (e.container) lines.push("JO  - " + e.container);
    if (e.volume) lines.push("VL  - " + e.volume);
    if (e.issue) lines.push("IS  - " + e.issue);
    if (e.pages) {
      var p = e.pages.split(/[-–]/);
      lines.push("SP  - " + p[0].trim());
      if (p[1]) lines.push("EP  - " + p[1].trim());
    }
    if (e.publisher) lines.push("PB  - " + e.publisher);
    if (e.doi) lines.push("DO  - " + e.doi);
    if (e.url) lines.push("UR  - " + e.url);
    if (e.abstract) lines.push("AB  - " + e.abstract);
    e.keywords.forEach(function (k) { lines.push("KW  - " + k); });
    lines.push("ER  - ");
    return lines.join("\n");
  }

  function serEndnote(e) {
    var lines = [];
    lines.push("%0 " + (NEUTRAL_TO_ENDNOTE[e.type] || "Generic"));
    e.authors.forEach(function (a) { lines.push("%A " + a); });
    if (e.title) lines.push("%T " + e.title);
    if (e.year) lines.push("%D " + e.year);
    if (e.container) lines.push((e.type === "incollection" || e.type === "inproceedings" ? "%B " : "%J ") + e.container);
    if (e.volume) lines.push("%V " + e.volume);
    if (e.issue) lines.push("%N " + e.issue);
    if (e.pages) lines.push("%P " + e.pages);
    if (e.publisher) lines.push("%I " + e.publisher);
    if (e.doi) lines.push("%R " + e.doi);
    if (e.url) lines.push("%U " + e.url);
    if (e.abstract) lines.push("%X " + e.abstract);
    e.keywords.forEach(function (k) { lines.push("%K " + k); });
    return lines.join("\n");
  }

  var PARSERS = { bibtex: parseBibtex, ris: parseRis, endnote: parseEndnote };
  var SERIALIZERS = { bibtex: serBibtex, ris: serRis, endnote: serEndnote };
  var LABELS = { bibtex: "BibTeX", ris: "RIS", endnote: "EndNote" };

  // ---- Wiring ------------------------------------------------------
  function showError(msg) {
    resultEl.hidden = true;
    statusEl.textContent = msg;
    statusEl.classList.add("rc-error");
  }
  function clearError() {
    statusEl.textContent = "";
    statusEl.classList.remove("rc-error");
  }

  runBtn.addEventListener("click", function () {
    clearError();
    var text = inputEl.value;
    if (!text || !text.trim()) {
      showError("Paste one or more references first.");
      return;
    }
    var from = fromEl.value;
    var detectedNote = "";
    if (from === "auto") {
      var d = detect(text);
      if (!d) {
        showError("Couldn't auto-detect the format. Please pick the “From” format manually.");
        return;
      }
      from = d;
      detectedNote = "Detected input format: " + LABELS[from] + ".";
    }
    var to = toEl.value;

    var entries;
    try {
      entries = PARSERS[from](text);
    } catch (err) {
      showError("Sorry - that input couldn't be parsed as " + LABELS[from] + ".");
      return;
    }
    if (!entries || !entries.length) {
      showError("No " + LABELS[from] + " entries found in the input. Check the format and try again.");
      return;
    }
    entries.forEach(finalizePages);

    var ser = SERIALIZERS[to];
    var out = entries.map(function (e, i) { return ser(e, i); }).join("\n\n");

    outEl.textContent = out;
    detectedEl.textContent = (detectedNote ? detectedNote + " " : "") +
      "Converted " + entries.length + " " + (entries.length === 1 ? "entry" : "entries") +
      " to " + LABELS[to] + ".";
    resultEl.hidden = false;
    copyBtn.textContent = "Copy";
  });

  copyBtn.addEventListener("click", function () {
    var text = outEl.textContent;
    if (!text) return;
    function done() { copyBtn.textContent = "Copied!"; setTimeout(function () { copyBtn.textContent = "Copy"; }, 1500); }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, function () {
        copyBtn.textContent = "Press Ctrl+C";
      });
    } else {
      var r = document.createRange();
      r.selectNodeContents(outEl);
      var sel = window.getSelection();
      sel.removeAllRanges(); sel.addRange(r);
      try { document.execCommand("copy"); done(); } catch (e) { copyBtn.textContent = "Press Ctrl+C"; }
    }
  });
})();
