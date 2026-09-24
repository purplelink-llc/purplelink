// Abstract Checker: counts an abstract's words in the browser and compares
// them with a venue's limit from venues.json, which is generated from the
// Journal Pack's rule library (scripts/gen_venue_json.py). Nothing is sent.
(() => {
  const text = document.getElementById("ac-text");
  const venueSel = document.getElementById("ac-venue");
  const custom = document.getElementById("ac-custom");
  const customWrap = document.getElementById("ac-custom-wrap");
  const result = document.getElementById("ac-result");
  const details = document.getElementById("ac-venue-facts");
  if (!text || !venueSel) return;

  const GROUPS = {
    machine_learning: "Machine learning",
    biomedicine: "General science and medicine",
    psychology_social: "Psychology and management",
    chemistry_materials: "Chemistry and materials",
  };
  const SECTION_NAMES = {
    introduction: "Introduction", methods: "Methods", results: "Results", discussion: "Discussion",
    conclusion: "Conclusion", limitations: "Limitations", data_availability: "Data availability",
    ethics_statement: "Ethics statement", competing_interests: "Competing interests",
    author_contributions: "Author contributions", related_work: "Related work",
  };
  let venues = [];

  // Words as a reader counts them: LaTeX commands and comments are dropped,
  // the text inside braces is kept, and inline math counts as one word.
  function countWords(raw) {
    const t = raw
      .replace(/(^|[^\\])%.*$/gm, "$1")
      .replace(/\$[^$]*\$/g, " MATH ")
      .replace(/\\(cite[a-z]*|ref|eqref|label)\*?(\[[^\]]*\])?\{[^}]*\}/g, " ")
      .replace(/\\[a-zA-Z]+\*?(\[[^\]]*\])?/g, " ")
      .replace(/[{}~]/g, " ");
    const words = t.split(/\s+/).filter((w) => /[\p{L}\p{N}]/u.test(w));
    return words.length;
  }

  function sentences(raw) {
    return (raw.match(/[^.!?]+[.!?]+(\s|$)/g) || []).length || (raw.trim() ? 1 : 0);
  }

  function selected() {
    return venues.find((v) => v.key === venueSel.value) || null;
  }

  function limit() {
    if (venueSel.value === "custom") return parseInt(custom.value, 10) || 0;
    const v = selected();
    return v ? v.abstract_max_words || 0 : 0;
  }

  function render() {
    customWrap.hidden = venueSel.value !== "custom";
    const raw = text.value;
    const words = countWords(raw);
    const lim = limit();
    result.textContent = "";
    const line = document.createElement("p");
    line.className = "ac-count";
    const strong = document.createElement("strong");
    strong.textContent = words + (words === 1 ? " word" : " words");
    line.append(strong);
    if (lim) {
      const diff = lim - words;
      const verdict = document.createElement("span");
      verdict.className = diff < 0 ? "ac-over" : "ac-under";
      verdict.textContent = diff < 0
        ? " · " + (-diff) + " over the " + lim + "-word limit"
        : " · " + diff + " to spare under the " + lim + "-word limit";
      line.append(verdict);
    }
    line.append(" · " + raw.length + " characters · " + sentences(raw) + (sentences(raw) === 1 ? " sentence" : " sentences"));
    result.append(line);
    if (lim) {
      const bar = document.createElement("div");
      bar.className = "ac-bar";
      const fill = document.createElement("span");
      fill.className = words > lim ? "ac-bar-fill ac-bar-over" : "ac-bar-fill";
      fill.style.width = Math.min(100, Math.round((words / lim) * 100)) + "%";
      bar.append(fill);
      result.append(bar);
    }
    renderFacts();
  }

  function renderFacts() {
    const v = selected();
    details.textContent = "";
    details.hidden = !v;
    if (!v) return;
    const h = document.createElement("h2");
    h.textContent = v.name;
    details.append(h);
    const dl = document.createElement("dl");
    const add = (k, val) => {
      if (val === null || val === undefined || val === "" || (Array.isArray(val) && !val.length)) return;
      const div = document.createElement("div");
      const dt = document.createElement("dt");
      dt.textContent = k;
      const dd = document.createElement("dd");
      dd.textContent = Array.isArray(val) ? val.map((s) => SECTION_NAMES[s] || s).join(", ") : String(val);
      div.append(dt, dd);
      dl.append(div);
    };
    add("Abstract", v.abstract_max_words ? "Up to " + v.abstract_max_words + " words" : null);
    add("Main text", v.manuscript_max_words ? "Up to " + v.manuscript_max_words.toLocaleString() + " words" : (v.manuscript_max_pages ? "Up to " + v.manuscript_max_pages + " pages" : null));
    add("Sections expected", v.required_sections);
    add("Also recommended", v.recommended_sections);
    add("References", v.reference_style_hint);
    add("Review", v.anonymous_submission ? "Double-blind: remove author details" : "Not anonymous");
    add("Note", v.notes);
    details.append(dl);
    if (v.sources) {
      const p = document.createElement("p");
      p.className = "ac-source";
      p.append("Limits change between years and article types. Confirm in ");
      const a = document.createElement("a");
      a.href = v.sources;
      a.rel = "noopener";
      a.textContent = "the venue's own instructions";
      p.append(a, ".");
      details.append(p);
    }
  }

  fetch("/tools/abstract-checker/venues.json")
    .then((r) => r.json())
    .then((data) => {
      venues = data;
      Object.entries(GROUPS).forEach(([domain, label]) => {
        const group = document.createElement("optgroup");
        group.label = label;
        venues.filter((v) => v.domain === domain).forEach((v) => {
          const o = document.createElement("option");
          o.value = v.key;
          o.textContent = v.name;
          group.append(o);
        });
        if (group.children.length) venueSel.insertBefore(group, venueSel.querySelector('option[value="custom"]'));
      });
      // The saved choice (site.js data-remember) is restored here, because
      // the options only exist once venues.json has loaded.
      let saved = "";
      try { saved = (JSON.parse(localStorage.getItem("pl_prefs") || "{}") || {})["ac-venue"] || ""; } catch (e) { saved = ""; }
      const want = new URLSearchParams(location.search).get("venue") || saved;
      if (want && venues.some((v) => v.key === want)) venueSel.value = want;
      render();
    })
    .catch(() => render());

  text.addEventListener("input", render);
  venueSel.addEventListener("change", () => { render(); if (window.plTrack) window.plTrack("tool_use", "abstract-checker:" + venueSel.value); });
  custom.addEventListener("input", render);
})();
