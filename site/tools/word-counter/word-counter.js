// Word Counter & Document Insights — UI controller.
//
// Wires the paste/upload tabs, live basic counts, the Analyse button, the
// deep-report cards, section toggles, and CSV export to the pure WordStats
// engine (wordstats.js). Upload path posts to the backend /word-stats
// endpoint for text extraction only; all stats run client-side.
(function () {
  "use strict";

  var WS = window.WordStats;

  // --- elements ---
  var input = document.getElementById("wc-input");
  var limitInput = document.getElementById("wc-limit");
  var limitReadout = document.getElementById("wc-limit-readout");
  var analyseBtn = document.getElementById("wc-analyse");
  var clearBtn = document.getElementById("wc-clear");
  var csvBtn = document.getElementById("wc-csv");
  var statusEl = document.getElementById("wc-status");
  var reportEl = document.getElementById("wc-report");
  var tabPaste = document.getElementById("wc-tab-paste");
  var tabUpload = document.getElementById("wc-tab-upload");
  var panePaste = document.getElementById("wc-pane-paste");
  var paneUpload = document.getElementById("wc-pane-upload");
  var fileNameEl = document.getElementById("wc-filename");

  var elWords = document.getElementById("s-words");
  var elChars = document.getElementById("s-chars");
  var elCharsNoSpace = document.getElementById("s-chars-nospace");
  var elSentences = document.getElementById("s-sentences");
  var elParagraphs = document.getElementById("s-paragraphs");
  var elReading = document.getElementById("s-reading");
  var elSpeaking = document.getElementById("s-speaking");

  var mode = "paste";              // "paste" | "upload"
  var uploadedText = "";           // text extracted from an uploaded file
  var uploadedSections = null;     // section dict from backend, if academic
  var lastStats = null;            // most recent full analysis (for CSV)

  function fmt(n) { return (n || 0).toLocaleString(); }

  // ---------------- Tabs ----------------
  function setMode(next) {
    mode = next;
    var isPaste = next === "paste";
    tabPaste.setAttribute("aria-selected", isPaste ? "true" : "false");
    tabUpload.setAttribute("aria-selected", isPaste ? "false" : "true");
    panePaste.hidden = !isPaste;
    paneUpload.hidden = isPaste;
    liveUpdate();
  }
  tabPaste.addEventListener("click", function () { setMode("paste"); });
  tabUpload.addEventListener("click", function () { setMode("upload"); });

  // ---------------- Active text source ----------------
  function activeText() {
    return mode === "paste" ? input.value : uploadedText;
  }

  // ---------------- Live basic counts ----------------
  function liveUpdate() {
    var b = WS.basicCounts(activeText());
    elWords.textContent = fmt(b.words);
    elChars.textContent = fmt(b.characters);
    elCharsNoSpace.textContent = fmt(b.charactersNoSpaces);
    elSentences.textContent = fmt(b.sentences);
    elParagraphs.textContent = fmt(b.paragraphs);
    elReading.textContent = b.readingMinutes + " min";
    elSpeaking.textContent = b.speakingMinutes + " min";
    updateLimit(b.words);
  }

  function updateLimit(words) {
    var raw = (limitInput.value || "").trim();
    var limit = parseInt(raw, 10);
    if (!raw || isNaN(limit) || limit <= 0) {
      limitReadout.textContent = "";
      limitReadout.classList.remove("over");
      return;
    }
    if (words > limit) {
      limitReadout.textContent = fmt(words) + " / " + fmt(limit) + " — " + fmt(words - limit) + " over";
      limitReadout.classList.add("over");
    } else {
      limitReadout.textContent = fmt(words) + " / " + fmt(limit) + " — " + fmt(limit - words) + " left";
      limitReadout.classList.remove("over");
    }
  }

  input.addEventListener("input", function () { if (mode === "paste") liveUpdate(); });
  limitInput.addEventListener("input", function () { liveUpdate(); });

  clearBtn.addEventListener("click", function () {
    input.value = "";
    uploadedText = "";
    uploadedSections = null;
    lastStats = null;
    fileNameEl.textContent = "";
    reportEl.innerHTML = "";
    statusEl.textContent = "";
    csvBtn.hidden = true;
    liveUpdate();
    if (mode === "paste") input.focus();
  });

  // ---------------- Upload ----------------
  if (typeof wireDropzone === "function") {
    wireDropzone("wc-dropzone", "wc-file", function (file) {
      if (file.size > 20 * 1024 * 1024) {
        statusEl.innerHTML = '<span class="wc-err">File is too large (max 20 MB).</span>';
        return;
      }
      fileNameEl.textContent = file.name + " (" + Math.round(file.size / 1024) + " KB)";
      statusEl.innerHTML = '<span class="tool-spinner" aria-hidden="true"></span>Extracting text…';
      reportEl.innerHTML = "";
      csvBtn.hidden = true;
      var fd = new FormData();
      fd.append("file", file, file.name);
      fetch(API_BASE + "/word-stats", { method: "POST", body: fd })
        .then(function (resp) {
          if (!resp.ok) return resp.json().then(function (p) { throw p; });
          return resp.json();
        })
        .then(function (data) {
          uploadedText = data.text || "";
          uploadedSections = data.sections || null;
          statusEl.textContent = "Extracted " + fmt(WS.words(uploadedText).length) + " words. Analysing…";
          liveUpdate();
          runAnalysis();         // auto-analyse right after upload
        })
        .catch(function (err) {
          statusEl.innerHTML = '<span class="wc-err">' +
            escapeHtml((err && err.detail) || "Couldn't read that file.") + "</span>";
        });
    });
  }

  // ---------------- Deep analysis ----------------
  analyseBtn.addEventListener("click", runAnalysis);

  function runAnalysis() {
    var text = activeText();
    if (!text || !text.trim()) {
      statusEl.innerHTML = '<span class="wc-err">Nothing to analyse yet — paste text or upload a file.</span>';
      return;
    }
    statusEl.textContent = "Analysing…";
    // Defer so the status paint happens before the (synchronous) crunch.
    setTimeout(function () {
      var stats = WS.analyze(text, mode === "upload" ? uploadedSections : null);
      lastStats = stats;
      renderReport(stats);
      statusEl.textContent = "Done.";
      csvBtn.hidden = false;
    }, 10);
  }

  // ---------------- CSV ----------------
  csvBtn.addEventListener("click", function () {
    if (!lastStats) return;
    var csv = WS.toCSV(lastStats);
    var blob = new Blob([csv], { type: "text/csv" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url; a.download = "document-stats.csv"; a.click();
    URL.revokeObjectURL(url);
  });

  // ---------------- Report rendering ----------------
  function card(title, bodyHtml, note) {
    return '<details class="wc-card" open><summary>' + escapeHtml(title) + "</summary>" +
      '<div class="wc-card-body">' + bodyHtml +
      (note ? '<p class="wc-card-note">' + note + "</p>" : "") +
      "</div></details>";
  }

  function metricGrid(pairs) {
    return '<div class="wc-metric-grid">' + pairs.map(function (p) {
      return '<div class="wc-metric"><span class="wc-metric-num">' + escapeHtml(String(p[1])) +
        '</span><span class="wc-metric-lbl">' + escapeHtml(p[0]) + "</span></div>";
    }).join("") + "</div>";
  }

  function renderReport(s) {
    var html = "";

    // Readability
    if (s.readability) {
      var r = s.readability;
      html += card("Readability", metricGrid([
        ["Flesch-Kincaid grade", r.fleschKincaidGrade],
        ["Flesch Reading Ease", r.fleschReadingEase],
        ["Gunning Fog", r.gunningFog],
        ["SMOG", r.smog + (r.smogReliable ? "" : "*")],
        ["Coleman-Liau", r.colemanLiau],
        ["ARI", r.automatedReadabilityIndex],
        ["Avg words/sentence", r.avgWordsPerSentence],
        ["Avg syllables/word", r.avgSyllablesPerWord],
      ]) + '<p class="wc-interp">' + escapeHtml(r.interpretation) + "</p>",
        r.smogReliable ? null : "*SMOG is most accurate on texts of 30+ sentences.");
    }

    // Vocabulary
    if (s.vocabulary) {
      var v = s.vocabulary;
      var topWords = v.topWords.map(function (w) {
        return '<span class="wc-chip">' + escapeHtml(w.term) + ' <em>' + w.count + "</em></span>";
      }).join("");
      var topBigrams = v.topBigrams.map(function (w) {
        return '<span class="wc-chip">' + escapeHtml(w.term) + ' <em>' + w.count + "</em></span>";
      }).join("");
      html += card("Vocabulary", metricGrid([
        ["Unique words", fmt(v.uniqueWords)],
        ["Type-token ratio", v.typeTokenRatio],
        ["Hapax legomena", fmt(v.hapaxCount)],
        ["Hapax ratio", v.hapaxRatio],
      ]) +
        (topWords ? '<h4>Top words</h4><div class="wc-chips">' + topWords + "</div>" : "") +
        (topBigrams ? '<h4>Top phrases</h4><div class="wc-chips">' + topBigrams + "</div>" : ""));
    }

    // Sentence stats
    if (s.sentences) {
      var ss = s.sentences;
      var maxBucket = Math.max.apply(null, ss.histogram.map(function (b) { return b.n; })) || 1;
      var bars = ss.histogram.map(function (b) {
        var pct = Math.round((b.n / maxBucket) * 100);
        return '<div class="wc-bar-row"><span class="wc-bar-lbl">' + b.label +
          '</span><span class="wc-bar"><span class="wc-bar-fill" style="width:' + pct + '%"></span></span>' +
          '<span class="wc-bar-n">' + b.n + "</span></div>";
      }).join("");
      html += card("Sentence length", metricGrid([
        ["Average", ss.avg],
        ["Median", ss.median],
        ["95th percentile", ss.p95],
        ["Longest", ss.longest],
      ]) + '<div class="wc-hist">' + bars + "</div>");
    }

    // Style flags
    if (s.style) {
      var st = s.style;
      html += card("Style flags", metricGrid([
        ["Passive voice", st.passive.count + " (" + st.passive.densityPer100 + "/100w)"],
        ["Adverbs", st.adverbs.count + " (" + st.adverbs.densityPer100 + "/100w)"],
        ["Weasel words", st.weasel.count],
        ["Hedge words", st.hedge.count],
        ["Academic clichés", st.cliche.count],
      ]),
      "Style flags are descriptive, not prescriptive — some passive voice and hedging is correct in academic writing.");
    }

    // Citations
    if (s.citations && s.citations.total > 0) {
      html += card("Citation density", metricGrid([
        ["Total citations", s.citations.total],
        ["Numeric [N]", s.citations.numericCitations],
        ["Author-year", s.citations.authorYearCitations],
        ["Per 1000 words", s.citations.perThousandWords],
      ]));
    }

    // AI-writing-pattern audit
    if (s.aiPatterns) {
      var ai = s.aiPatterns;
      var phraseList = ai.matches.length
        ? '<div class="wc-chips">' + ai.matches.slice(0, 30).map(function (m) {
            return '<span class="wc-chip wc-chip-flag">' + escapeHtml(m.text) + "</span>";
          }).join("") + "</div>"
        : '<p class="wc-none">No common AI-writing phrases flagged.</p>';
      html += card("AI-writing-pattern audit",
        metricGrid([
          ["Flagged phrases", ai.flaggedPhraseCount],
          ["Per 1000 words", ai.densityPer1000Words],
          ["Em-dashes", ai.emDashCount],
        ]) + phraseList,
        "<strong>This is not an AI detector.</strong> It flags phrasing common in AI-generated text so you can review it. Presence of these patterns is NOT proof of AI authorship — human writers use them too, and automated AI detectors are unreliable and disproportionately misflag non-native English writers. Use this as a style mirror, never as evidence.");
    }

    // Character anomalies
    if (s.anomalies && s.anomalies.anyAnomaly) {
      var a = s.anomalies;
      var items = [];
      if (a.invisibleChars) items.push(a.invisibleChars + " invisible/zero-width character(s)");
      if (a.controlChars) items.push(a.controlChars + " control character(s)");
      if (a.mixedScript) items.push("mixed scripts detected (e.g. Latin + Cyrillic look-alikes)");
      html += card("Character anomalies",
        '<ul class="wc-anom">' + items.map(function (i) { return "<li>" + escapeHtml(i) + "</li>"; }).join("") + "</ul>",
        "These can indicate copy-paste artifacts, hidden characters, or look-alike-character spoofing. Often harmless, but worth a glance before submission.");
    }

    // Section splice (upload + academic only)
    if (s.sections && Object.keys(s.sections).length) {
      html += renderSectionCard(s.sections);
    }

    reportEl.innerHTML = html;
    wireSectionToggles(s.sections);
  }

  // ---------------- Section splice card ----------------
  // Builds a checkbox list of detected sections and a live "selected total".
  var SECTION_ORDER = ["abstract", "body", "introduction", "methods", "results",
    "discussion", "conclusion", "references", "appendix", "acknowledgements", "figure_captions"];
  var SECTION_LABELS = {
    abstract: "Abstract", body: "Main text (intro→conclusion)", introduction: "Introduction",
    methods: "Methods", results: "Results", discussion: "Discussion", conclusion: "Conclusion",
    references: "References", appendix: "Appendix", acknowledgements: "Acknowledgements",
    figure_captions: "Figure captions",
  };

  function renderSectionCard(sections) {
    var keys = SECTION_ORDER.filter(function (k) { return sections[k]; });
    Object.keys(sections).forEach(function (k) { if (keys.indexOf(k) === -1) keys.push(k); });

    // By default, count everything EXCEPT references + appendix (the most
    // common "what's my main-text word count" question).
    var rows = keys.map(function (k) {
      var defaultOn = (k !== "references" && k !== "appendix" && k !== "abstract" && k !== "body");
      // Prefer the narrative sub-sections over "body" to avoid double count;
      // if "body" exists alongside intro/methods/etc., default body OFF.
      var label = SECTION_LABELS[k] || k;
      return '<label class="wc-sec-row">' +
        '<input type="checkbox" class="wc-sec-cb" data-sec="' + escapeHtml(k) + '"' +
        (defaultOn ? " checked" : "") + ">" +
        '<span class="wc-sec-name">' + escapeHtml(label) + "</span>" +
        '<span class="wc-sec-words">' + fmt(sections[k].words) + " words</span>" +
        "</label>";
    }).join("");

    return card("Section breakdown",
      '<p class="wc-sec-intro">Detected academic sections. Tick the sections to include in the combined total below.</p>' +
      rows +
      '<div class="wc-sec-total">Selected total: <strong id="wc-sec-sum">0</strong> words</div>',
      "Section detection is heuristic — verify against your manuscript. Counts use the same word definition as the main counter.");
  }

  function wireSectionToggles(sections) {
    if (!sections) return;
    var cbs = reportEl.querySelectorAll(".wc-sec-cb");
    var sumEl = document.getElementById("wc-sec-sum");
    if (!sumEl) return;
    function recompute() {
      var total = 0;
      cbs.forEach(function (cb) {
        if (cb.checked && sections[cb.dataset.sec]) {
          total += sections[cb.dataset.sec].words;
        }
      });
      sumEl.textContent = fmt(total);
    }
    cbs.forEach(function (cb) { cb.addEventListener("change", recompute); });
    recompute();
  }

  // ---------------- boot ----------------
  liveUpdate();
})();
