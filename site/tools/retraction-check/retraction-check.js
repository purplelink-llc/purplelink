// Retraction Checker: paste a reference list, BibTeX or DOIs; the browser asks Crossref
// (which carries Retraction Watch data) whether any item has been retracted or carries an
// expression of concern. Nothing is sent to Purplelink. Everything written to the page is set as
// plain text, never parsed as markup, because the pasted text and Crossref's titles are untrusted.
(function () {
  "use strict";

  var API = "https://api.crossref.org/works";
  var MAILTO = "ben@purplelink.llc";
  var MAX_DOIS = 300;
  var MAX_TITLE_LOOKUPS = 25;
  var CHUNK = 20;
  var RETRACTED_TYPES = { retraction: 1, withdrawal: 1, removal: 1 };
  var CONCERN_TYPES = { expression_of_concern: 1, partial_retraction: 1 };
  var TITLE_FLAG = /^\s*(?:retracted|withdrawn)\s*[:\-–—]/i;
  // Includes < and > because early Wiley DOIs contain them, for example 10.1002/(SICI)1097-0258(19980430)17:8<873::AID-SIM779>3.0.CO;2-I.
  var DOI_RE = /\b10\.\d{4,9}\/[-._;()<>\/:A-Za-z0-9]+/g;

  // ---- pure logic (also exported for tests) ----------------------------------------------------

  function trimDoi(raw) {
    var d = String(raw).replace(/[.,;:\]}"'’”]+$/, "");
    // A trailing ">" is a wrapper (<doi>) unless a "<" earlier in the DOI is still open.
    while (d.charAt(d.length - 1) === ">" && (d.match(/>/g) || []).length > (d.match(/</g) || []).length) {
      d = d.slice(0, -1).replace(/[.,;:]+$/, "");
    }
    // A trailing ")" belongs to the DOI only when it closes a "(" inside it.
    while (d.charAt(d.length - 1) === ")" && (d.match(/\)/g) || []).length > (d.match(/\(/g) || []).length) {
      d = d.slice(0, -1).replace(/[.,;:]+$/, "");
    }
    return d;
  }

  function extractDois(text) {
    var seen = {};
    var out = [];
    var m;
    DOI_RE.lastIndex = 0;
    while ((m = DOI_RE.exec(String(text || ""))) !== null) {
      var d = trimDoi(m[0]);
      if (d.length < 8) continue;
      var key = d.toLowerCase();
      if (!seen[key]) { seen[key] = 1; out.push(d); }
    }
    return out;
  }

  // References that carry no DOI: one per BibTeX entry (its title field), or one per line or blank-line
  // separated paragraph that looks like a reference (long enough, has a year). Returns [{raw, title}].
  // End index of a BibTeX entry that starts at its "@": the brace that closes the first "{".
  function bibEntryEnd(part) {
    var depth = 0, started = false;
    for (var i = 0; i < part.length; i++) {
      var ch = part.charAt(i);
      if (ch === "{") { depth++; started = true; }
      else if (ch === "}") { depth--; if (started && depth <= 0) return i + 1; }
    }
    return part.length;
  }

  function extractUndoiedReferences(text) {
    var t = String(text || "");
    var refs = [];
    var rest = "";
    var parts = t.split(/(?=@\w+\s*\{)/);
    parts.forEach(function (part) {
      if (!/^@\w+\s*\{/.test(part)) { rest += part + "\n"; return; }
      var end = bibEntryEnd(part);
      var entry = part.slice(0, end);
      rest += part.slice(end) + "\n";
      DOI_RE.lastIndex = 0;
      if (DOI_RE.test(entry)) return;
      var tm = /title\s*=\s*\{((?:[^{}]|\{[^{}]*\})*)\}/i.exec(entry) || /title\s*=\s*"([^"]*)"/i.exec(entry);
      if (tm) {
        var title = tm[1].replace(/[{}]/g, "").replace(/\s+/g, " ").trim();
        if (title.length >= 15) refs.push({ raw: title, title: title });
      }
    });
    var blocks = /\n\s*\n/.test(rest) ? rest.split(/\n\s*\n/) : rest.split(/\n/);
    blocks.forEach(function (blk) {
      var line = blk.replace(/\s+/g, " ").trim();
      DOI_RE.lastIndex = 0;
      if (line.length < 40 || DOI_RE.test(line) || !/\b(19|20)\d{2}\b/.test(line)) return;
      line = line.replace(/^\s*(?:\[\d{1,3}\]|\d{1,3}[.)])\s*/, "");
      refs.push({ raw: line, title: guessTitle(line) });
    });
    return refs;
  }

  // Brittle by design, like the backend's: the segment after the year up to the next sentence.
  function guessTitle(line) {
    var y = /\b(?:19|20)\d{2}[a-z]?\b/.exec(line);
    var rest = y ? line.slice(y.index + y[0].length) : line;
    rest = rest.replace(/^[\s.,;:)\]]+/, "");
    var m = /^([^.]{12,}?)\.\s+[A-Z]/.exec(rest + ". X");
    return (m ? m[1] : rest).slice(0, 200).trim();
  }

  function updateDate(u) {
    try {
      var p = (((u || {}).updated || {})["date-parts"] || [[]])[0] || [];
      var n = p.slice(0, 3).map(function (x) { return parseInt(x, 10); });
      if (!n.length || !(n[0] >= 1000 && n[0] <= 9999)) return "";
      return n.map(function (x, i) { return i === 0 ? String(x) : (x < 10 ? "0" + x : String(x)); }).join("-");
    } catch (e) { return ""; }
  }

  // Retraction status of one Crossref work record, or null. Mirrors the backend's crossref_retraction().
  function retractionOf(message) {
    if (!message || typeof message !== "object") return null;
    var updates = Array.isArray(message["updated-by"]) ? message["updated-by"] : [];
    var found = [];
    updates.forEach(function (u) {
      if (!u || typeof u !== "object") return;
      var type = String(u.type || "").trim().toLowerCase();
      if (RETRACTED_TYPES[type] || CONCERN_TYPES[type]) {
        found.push({ type: type, doi: String(u.DOI || "").slice(0, 120), date: updateDate(u) });
      }
    });
    if (found.length) {
      var hard = found.filter(function (f) { return RETRACTED_TYPES[f.type]; });
      var chosen = (hard.length ? hard : found)[0];
      var types = [];
      found.forEach(function (f) { if (types.indexOf(f.type) < 0) types.push(f.type); });
      return { kind: hard.length ? "retracted" : "concern", types: types.sort(), noticeDoi: chosen.doi, date: chosen.date };
    }
    // The record itself is a retraction notice (it points at the work it retracts): citing it is citing a retraction.
    var targets = Array.isArray(message["update-to"]) ? message["update-to"] : [];
    for (var i = 0; i < targets.length; i++) {
      var tt = targets[i] && String(targets[i].type || "").trim().toLowerCase();
      if (RETRACTED_TYPES[tt]) {
        return { kind: "retracted", types: ["notice_itself"], noticeDoi: String(message.DOI || "").slice(0, 120), date: updateDate(targets[i]) };
      }
    }
    var titles = message.title;
    var title = Array.isArray(titles) && titles.length ? titles[0] : "";
    if (typeof title === "string" && TITLE_FLAG.test(title)) {
      return { kind: "retracted", types: ["title_flag"], noticeDoi: "", date: "" };
    }
    return null;
  }

  function overlap(a, b) {
    var ta = {}, tb = {}, inter = 0, union = 0, k;
    (a.toLowerCase().match(/\w+/g) || []).forEach(function (w) { ta[w] = 1; });
    (b.toLowerCase().match(/\w+/g) || []).forEach(function (w) { tb[w] = 1; });
    for (k in ta) { union++; if (tb[k]) inter++; }
    for (k in tb) { if (!ta[k]) union++; }
    return union ? inter / union : 0;
  }

  var core = {
    trimDoi: trimDoi, extractDois: extractDois, extractUndoiedReferences: extractUndoiedReferences,
    retractionOf: retractionOf, overlap: overlap, guessTitle: guessTitle,
    limits: { MAX_DOIS: MAX_DOIS, MAX_TITLE_LOOKUPS: MAX_TITLE_LOOKUPS, CHUNK: CHUNK }
  };
  if (typeof module !== "undefined" && module.exports) module.exports = core;
  if (typeof window !== "undefined") window.RetractionCheckCore = core;

  // ---- page --------------------------------------------------------------------------------------

  var form = typeof document !== "undefined" && document.getElementById("rc-form");
  if (!form) return;
  var textEl = document.getElementById("rc-text");
  var runBtn = document.getElementById("rc-run");
  var exampleBtn = document.getElementById("rc-example");
  var statusEl = document.getElementById("rc-status");
  var results = document.getElementById("rc-results");
  var busy = false;

  var EXAMPLE = [
    "10.1016/S0140-6736(97)11096-0",
    "10.1038/nature14539",
    "10.1126/science.1059487"
  ].join("\n");

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = String(text);
    return n;
  }

  function setStatus(msg, kind) {
    statusEl.textContent = msg || "";
    statusEl.classList.toggle("is-error", kind === "error");
  }

  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  function getJson(url, signal, tries) {
    tries = tries || 3;
    return fetch(url, { headers: { Accept: "application/json" }, signal: signal }).then(function (r) {
      if ((r.status === 429 || r.status === 503) && tries > 1) {
        var wait = parseFloat(r.headers.get("retry-after")) || 2;
        return sleep(Math.min(wait, 8) * 1000).then(function () { return getJson(url, signal, tries - 1); });
      }
      if (r.status === 404) return { notFound: true };
      if (!r.ok) throw new Error("Crossref answered " + r.status);
      return r.json();
    });
  }

  function doiUrl(doi) {
    return API + "/" + encodeURIComponent(doi).replace(/%2F/gi, "/") + "?mailto=" + encodeURIComponent(MAILTO);
  }

  // DOI -> {title, retraction} or {missing:true} or {failed:true}
  function lookupDois(dois, signal, onProgress) {
    var out = {};
    var batchable = dois.filter(function (d) { return d.indexOf(",") < 0; });
    var single = dois.filter(function (d) { return d.indexOf(",") >= 0; });
    var chunks = [];
    for (var i = 0; i < batchable.length; i += CHUNK) chunks.push(batchable.slice(i, i + CHUNK));
    var done = 0;
    var chain = Promise.resolve();
    chunks.forEach(function (chunk) {
      chain = chain.then(function () {
        var url = API + "?filter=" + chunk.map(function (d) { return "doi:" + encodeURIComponent(d); }).join(",") +
          "&select=DOI,title,updated-by,update-to&rows=" + chunk.length + "&mailto=" + encodeURIComponent(MAILTO);
        return getJson(url, signal).then(function (data) {
          var items = ((data || {}).message || {}).items || [];
          items.forEach(function (it) {
            out[String(it.DOI || "").toLowerCase()] = { title: (it.title || [""])[0] || "", retraction: retractionOf(it) };
          });
        }).catch(function (e) {
          if (e && e.name === "AbortError") throw e;
          chunk.forEach(function (d) { out[d.toLowerCase()] = { failed: true }; });
        }).then(function () { done += chunk.length; onProgress(done); });
      });
    });
    single.forEach(function (d) {
      chain = chain.then(function () {
        return getJson(doiUrl(d), signal).then(function (data) {
          if (data && data.message) out[d.toLowerCase()] = { title: (data.message.title || [""])[0] || "", retraction: retractionOf(data.message) };
        }).catch(function (e) {
          if (e && e.name === "AbortError") throw e;
          out[d.toLowerCase()] = { failed: true };
        }).then(function () { done += 1; onProgress(done); });
      });
    });
    return chain.then(function () { return out; });
  }

  // Searches with the whole reference (authors and year sharpen the ranking of a generic title), takes the
  // top three, and accepts the one whose title is closest to the cited title, if it is close enough.
  function lookupTitle(ref, signal) {
    var url = API + "?query.bibliographic=" + encodeURIComponent(ref.raw.slice(0, 300)) +
      "&rows=3&select=DOI,title,updated-by,update-to&mailto=" + encodeURIComponent(MAILTO);
    return getJson(url, signal).then(function (data) {
      var items = (((data || {}).message || {}).items || []);
      var best = null, bestScore = 0, bestFlagged = null, bestFlaggedScore = 0;
      items.forEach(function (it) {
        var found = (it.title || [""])[0] || "";
        // A retracted work's own title is often prefixed ("RETRACTED: ..."), and the retraction notice shares the
        // title, so a close match that carries a retraction wins over a slightly closer one that does not.
        var score = overlap(ref.title, found.replace(/^\s*(?:retracted|retraction|withdrawn)\s*[:\-\u2013\u2014]\s*/i, ""));
        if (score > bestScore) { best = it; bestScore = score; }
        if (score >= 0.7 && retractionOf(it) && score > bestFlaggedScore) { bestFlagged = it; bestFlaggedScore = score; }
      });
      if (bestFlagged) { best = bestFlagged; bestScore = bestFlaggedScore; }
      if (!best || bestScore < 0.7) return { status: "not_found" };
      return { status: "matched", doi: best.DOI || "", title: (best.title || [""])[0] || "", retraction: retractionOf(best) };
    }).catch(function (e) {
      if (e && e.name === "AbortError") throw e;
      return { status: "failed" };
    });
  }

  function lookupTitles(refs, signal, onProgress) {
    var results = new Array(refs.length);
    var next = 0, done = 0;
    function worker() {
      if (next >= refs.length) return Promise.resolve();
      var i = next++;
      return lookupTitle(refs[i], signal).then(function (r) {
        results[i] = r; done++; onProgress(done);
        return sleep(150);
      }).then(worker);
    }
    return Promise.all([worker(), worker(), worker()]).then(function () { return results; });
  }

  var GUIDANCE = {
    retracted: "Crossref records this work as retracted. Read the notice, and do not cite the work as support for a claim unless you say it was retracted.",
    concern: "Crossref records a notice against this work, such as an expression of concern or a partial retraction. Read it before you rely on the result."
  };

  function render(summary) {
    results.textContent = "";
    var f = summary.findings;
    var retracted = f.filter(function (x) { return x.kind === "retracted"; }).length;
    var concerns = f.length - retracted;

    var head = el("p", "rc-summary");
    head.appendChild(el("strong", "", retracted + " retracted"));
    head.appendChild(document.createTextNode(", "));
    head.appendChild(el("strong", "", concerns + " with a notice of concern"));
    head.appendChild(document.createTextNode(" among " + summary.checked + " item" + (summary.checked === 1 ? "" : "s") +
      " Crossref could look up (" + summary.entered + " entered)."));
    results.appendChild(head);

    if (f.length) {
      var list = el("ol", "rc-findings");
      f.sort(function (a, b) { return (a.kind === "retracted" ? 0 : 1) - (b.kind === "retracted" ? 0 : 1); });
      f.forEach(function (x) {
        var li = el("li", "rc-finding rc-" + x.kind);
        li.appendChild(el("h3", "", x.kind === "retracted" ? "Retracted" : "Expression of concern or partial retraction"));
        li.appendChild(el("p", "rc-ref", x.reference));
        if (x.doi && x.doi !== x.reference) li.appendChild(el("p", "rc-meta", "DOI: " + x.doi));
        if (x.title) li.appendChild(el("p", "rc-meta", "Crossref lists this under: " + x.title));
        var when = x.date ? " on " + x.date : "";
        var meta = el("p", "rc-meta", "Notice" + when + ". ");
        if (x.noticeDoi) {
          var a = el("a", "", "Open the notice");
          a.href = "https://doi.org/" + encodeURI(x.noticeDoi);
          a.rel = "noopener";
          a.target = "_blank";
          meta.appendChild(a);
        }
        li.appendChild(meta);
        li.appendChild(el("p", "rc-advice", GUIDANCE[x.kind]));
        list.appendChild(li);
      });
      results.appendChild(list);
    } else if (summary.checked > 0) {
      results.appendChild(el("p", "rc-clear", "No retractions or expressions of concern were found among the items Crossref could look up. That is not a guarantee: a very recent retraction may not be in Crossref yet."));
    }

    if (summary.unchecked.length) {
      var d = el("details", "rc-unchecked");
      d.appendChild(el("summary", "", summary.unchecked.length + " item" + (summary.unchecked.length === 1 ? "" : "s") + " could not be checked"));
      var ul = el("ul");
      summary.unchecked.slice(0, 30).forEach(function (u) { ul.appendChild(el("li", "", u.reference + " (" + u.reason + ")")); });
      d.appendChild(ul);
      results.appendChild(d);
    }
    summary.notes.forEach(function (n) { results.appendChild(el("p", "rc-note", n)); });

    var next = document.querySelector("[data-tool-next='#rc-results']");
    if (next) next.hidden = false;
    results.hidden = false;
  }

  function run() {
    if (busy) return;
    var text = textEl.value || "";
    if (text.length > 400000) { setStatus("That is too much text. Paste the reference list only.", "error"); return; }
    var dois = extractDois(text);
    var refs = extractUndoiedReferences(text);
    if (!dois.length && !refs.length) {
      setStatus("Paste a reference list, BibTeX or a list of DOIs first.", "error");
      textEl.focus();
      return;
    }
    var notes = [];
    if (dois.length > MAX_DOIS) { notes.push("Only the first " + MAX_DOIS + " DOIs were checked."); dois = dois.slice(0, MAX_DOIS); }
    if (refs.length > MAX_TITLE_LOOKUPS) {
      notes.push((refs.length - MAX_TITLE_LOOKUPS) + " references without a DOI were not looked up: only " + MAX_TITLE_LOOKUPS + " title lookups run at a time.");
      refs = refs.slice(0, MAX_TITLE_LOOKUPS);
    }
    busy = true;
    runBtn.disabled = true;
    results.hidden = true;
    var ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
    var timer = setTimeout(function () { if (ctrl) ctrl.abort(); }, 90000);
    var signal = ctrl ? ctrl.signal : undefined;
    var total = dois.length + refs.length;
    function progress(n) { setStatus("Checking with Crossref: " + n + " of " + total + "."); }
    setStatus("Checking with Crossref.");
    if (window.plTrack) window.plTrack("tool_use", "retraction-check");

    lookupDois(dois, signal, progress).then(function (byDoi) {
      return lookupTitles(refs, signal, function (n) { progress(dois.length + n); }).then(function (byTitle) {
        var summary = { entered: total, checked: 0, findings: [], unchecked: [], notes: notes };
        dois.forEach(function (d) {
          var r = byDoi[d.toLowerCase()];
          if (!r) { summary.unchecked.push({ reference: d, reason: "not in Crossref; it may be registered with another agency" }); return; }
          if (r.failed) { summary.unchecked.push({ reference: d, reason: "the lookup failed" }); return; }
          summary.checked++;
          if (r.retraction) summary.findings.push({ kind: r.retraction.kind, reference: d, doi: d, title: r.title, noticeDoi: r.retraction.noticeDoi, date: r.retraction.date });
        });
        refs.forEach(function (ref, i) {
          var r = byTitle[i] || { status: "failed" };
          if (r.status !== "matched") { summary.unchecked.push({ reference: ref.raw.slice(0, 140), reason: r.status === "failed" ? "the lookup failed" : "no close title match in Crossref" }); return; }
          summary.checked++;
          if (r.retraction) summary.findings.push({ kind: r.retraction.kind, reference: ref.raw.slice(0, 220), doi: r.doi, title: r.title, noticeDoi: r.retraction.noticeDoi, date: r.retraction.date });
        });
        render(summary);
        setStatus("");
      });
    }).catch(function (e) {
      setStatus(e && e.name === "AbortError" ? "That took too long. Try a shorter list." : "Crossref could not be reached. Try again in a moment.", "error");
    }).then(function () {
      clearTimeout(timer);
      busy = false;
      runBtn.disabled = false;
    });
  }

  form.addEventListener("submit", function (ev) { ev.preventDefault(); run(); });
  if (exampleBtn) exampleBtn.addEventListener("click", function () { textEl.value = EXAMPLE; textEl.focus(); });
})();
