// Replication Package Checker. Everything runs in the browser: the zip is read
// with a self-hosted copy of JSZip and never uploaded. Nothing is executed; the
// checks are pattern matches on file names and on the text of code files.
(() => {
  "use strict";

  const MAX_ZIP = 500 * 1024 * 1024;
  const MAX_READ = 5 * 1024 * 1024;
  const BIG_FILE = 100 * 1024 * 1024;
  const NB_OUTPUT_MAX = 1024 * 1024;
  const MAX_CSV_READ = 200;

  const $ = (id) => document.getElementById(id);
  const drop = $("rp-drop");
  const fileInput = $("rp-file");
  const status = $("rp-status");
  const out = $("rp-results");
  const dl = $("rp-download");
  let lastReport = "";

  const setStatus = (msg, busy) => {
    status.textContent = msg;
    status.classList.toggle("is-busy", !!busy);
  };

  // ---------- helpers ----------
  const LANG_BY_EXT = {
    r: "R", rmd: "R", qmd: "R", py: "Python", ipynb: "Python", do: "Stata", ado: "Stata",
    jl: "Julia", m: "MATLAB", sas: "SAS", sh: "Shell",
  };
  const TEXT_EXT = new Set(["r", "rmd", "qmd", "py", "ipynb", "do", "ado", "jl", "m", "sas", "sh", "md", "txt",
    "yml", "yaml", "toml", "lock", "csv", "env", "renviron", "ini", "cfg", "rst"]);
  const TEXT_NAMES = /^(makefile|gnumakefile|snakefile|description|pipfile|license|licence|copying|readme|\.env|\.renviron)$/i;
  const DATA_EXT = ["csv", "tsv", "dta", "rds", "rdata", "rda", "xlsx", "xls", "parquet", "feather", "sav", "por",
    "sas7bdat", "xpt", "dat", "pkl", "pickle", "h5", "hdf5", "mat", "npy", "npz", "jld2", "arrow", "fst", "shp", "geojson"];
  const DATA_RE = new RegExp("\\.(" + DATA_EXT.join("|") + ")$", "i");
  const COMMENT = {
    R: /^\s*#/, Python: /^\s*#/, Julia: /^\s*#/, Shell: /^\s*#/, Stata: /^\s*(\*|\/\/)/, MATLAB: /^\s*%/, SAS: /^\s*(\*|\/\*)/,
  };

  const ext = (p) => { const b = base(p); const i = b.lastIndexOf("."); return i > 0 ? b.slice(i + 1).toLowerCase() : (i === 0 ? b.slice(1).toLowerCase() : ""); };
  const base = (p) => p.slice(p.lastIndexOf("/") + 1);
  const dirOf = (p) => (p.includes("/") ? p.slice(0, p.lastIndexOf("/")) : "");
  const depth = (p) => p.split("/").length - 1;
  const fmtSize = (b) => b >= 1073741824 ? (b / 1073741824).toFixed(2) + " GB" : b >= 1048576 ? (b / 1048576).toFixed(1) + " MB" : b >= 1024 ? Math.round(b / 1024) + " KB" : b + " bytes";
  const clip = (s, n = 110) => { const t = s.trim().replace(/\s+/g, " "); return t.length > n ? t.slice(0, n) + "..." : t; };
  const some = (arr, max = 12) => arr.length <= max ? arr : arr.slice(0, max).concat(["and " + (arr.length - max) + " more"]);
  const at = (f, ln) => f.path + (f.nb ? " (" + ln.n + ")" : ":" + ln.n);
  const plural = (n, w) => n + " " + w + (n === 1 ? "" : "s");

  // ---------- reading the zip ----------
  async function readZip(file) {
    setStatus("Opening the zip.", true);
    const zip = await window.JSZip.loadAsync(file);
    let entries = [];
    const dirs = new Set();
    zip.forEach((path, e) => {
      const p = path.replace(/\\/g, "/").replace(/^\.?\//, "");
      if (e.dir) { dirs.add(p.replace(/\/$/, "")); return; }
      entries.push({ raw: p, entry: e, size: (e._data && e._data.uncompressedSize) || 0 });
    });
    // A zip made by right-clicking a folder holds everything under one folder.
    const real = entries.filter((x) => !x.raw.startsWith("__MACOSX/"));
    const tops = new Set(real.map((x) => x.raw.split("/")[0]));
    let root = "";
    if (tops.size === 1 && real.length && real.every((x) => x.raw.includes("/"))) root = [...tops][0] + "/";
    const strip = (p) => (root && p.startsWith(root) ? p.slice(root.length) : p);
    entries = entries.map((x) => ({ ...x, path: strip(x.raw) }));
    const allDirs = new Set();
    dirs.forEach((d) => { const s = strip(d + "/").replace(/\/$/, ""); if (s) allDirs.add(s); });
    entries.forEach((x) => { let d = dirOf(x.path); while (d) { allDirs.add(d); d = dirOf(d); } });

    const files = [];
    let csvRead = 0, n = 0;
    for (const x of entries) {
      n++;
      if (n % 25 === 1) setStatus("Reading file " + n + " of " + entries.length + ".", true);
      const f = { path: x.path, size: x.size, ext: ext(x.path), name: base(x.path), text: null, lines: [], lang: null, skipped: false };
      const isText = TEXT_EXT.has(f.ext) || TEXT_NAMES.test(f.name);
      const debris = /(^|\/)(__MACOSX|__pycache__|\.ipynb_checkpoints|\.git|\.Rproj\.user)\//.test(f.path);
      if (isText && !debris) {
        if (f.size > MAX_READ) f.skipped = true;
        else if (f.ext === "csv") {
          if (csvRead < MAX_CSV_READ) { csvRead++; const t = await x.entry.async("string"); f.header = (t.split(/\r?\n/, 1)[0] || ""); }
        } else {
          f.text = await x.entry.async("string");
        }
      }
      if (f.text !== null) prepare(f);
      else if (LANG_BY_EXT[f.ext]) f.lang = LANG_BY_EXT[f.ext];
      files.push(f);
    }
    return { files, dirs: allDirs, root: root.replace(/\/$/, ""), zipSize: file.size };
  }

  function prepare(f) {
    f.lang = LANG_BY_EXT[f.ext] || null;
    if (/^(makefile|gnumakefile)$/i.test(f.name)) f.lang = "Shell";
    if (f.ext === "ipynb") {
      f.nb = true;
      f.nbOutput = 0;
      try {
        const nb = JSON.parse(f.text);
        const l = ((nb.metadata || {}).kernelspec || {}).language || ((nb.metadata || {}).language_info || {}).name || "python";
        f.lang = /^r$/i.test(l) ? "R" : /julia/i.test(l) ? "Julia" : /stata/i.test(l) ? "Stata" : "Python";
        (nb.cells || []).forEach((c, ci) => {
          if (c.outputs && c.outputs.length) f.nbOutput += JSON.stringify(c.outputs).length;
          if (c.cell_type !== "code") return;
          const src = Array.isArray(c.source) ? c.source.join("") : String(c.source || "");
          src.split(/\r?\n/).forEach((t, li) => f.lines.push({ t, n: "cell " + (ci + 1) + ", line " + (li + 1) }));
        });
      } catch (e) { f.lines = []; }
    } else {
      if (f.ext === "qmd" && /```\{python/.test(f.text) && !/```\{r/.test(f.text)) f.lang = "Python";
      f.lines = f.text.split(/\r?\n/).map((t, i) => ({ t, n: i + 1 }));
    }
    const cre = COMMENT[f.lang];
    f.code = f.lang ? f.lines.filter((l) => l.t.trim() && !(cre && cre.test(l.t))) : [];
  }

  // ---------- checks ----------
  const README_SECTIONS = [
    ["Data Availability and Provenance Statements", /data\s+availability/i],
    ["Dataset list", /data\s?sets?\s+list|list\s+of\s+data\s?sets/i],
    ["Computational requirements", /computational\s+requirements/i],
    ["Description of programs/code", /description\s+of\s+(the\s+)?(programs?|code)/i],
    ["Instructions to replicators", /instructions\s+(to|for)\s+(the\s+)?replicators?/i],
    ["List of tables and programs", /list\s+of\s+(tables|figures|exhibits)/i],
    ["References", /^\W*(references|bibliography)\W*$/i],
  ];

  function headings(lines) {
    const hs = [];
    lines.forEach((l, i) => {
      const t = l.t.trim();
      if (!t) return;
      const next = (lines[i + 1] || { t: "" }).t.trim();
      const prev = i ? lines[i - 1].t.trim() : "";
      let h = null;
      let m;
      if ((m = /^#{1,6}\s+(.*?)\s*#*$/.exec(t))) h = m[1];
      else if (/^(={3,}|-{3,})$/.test(next) && !/^(={3,}|-{3,})$/.test(t)) h = t;
      else if ((m = /^\*\*(.+?)\*\*:?$/.exec(t))) h = m[1];
      else if (t.length <= 70 && !/[.,;]$/.test(t) && t.split(/\s+/).length <= 9 && !prev && !next && /^[A-Z0-9]/.test(t)) h = t;
      if (h) hs.push({ t: h.replace(/^\d+[.)]\s*/, ""), n: l.n });
    });
    return hs;
  }

  function evaluate(pkg) {
    const { files, dirs } = pkg;
    const results = [];
    const add = (st, title, summary, details) => results.push({ status: st, title, summary, details: (details || []).filter(Boolean) });
    const live = files.filter((f) => !/(^|\/)(__MACOSX|__pycache__|\.ipynb_checkpoints|\.git|\.Rproj\.user)\//.test(f.path));
    const codeFiles = live.filter((f) => f.lang && LANG_BY_EXT[f.ext]);
    const readCode = codeFiles.filter((f) => f.text !== null);
    const langs = {};
    codeFiles.forEach((f) => { langs[f.lang] = (langs[f.lang] || 0) + 1; });
    const has = (l) => !!langs[l];
    const byName = (re, maxDepth = 99) => live.filter((f) => re.test(f.name) && depth(f.path) <= maxDepth);

    // 1. README
    const readmes = live.filter((f) => /^readme(\.[a-z0-9]+)?$/i.test(f.name));
    const topReadme = readmes.filter((f) => depth(f.path) === 0);
    const textReadme = topReadme.find((f) => f.text !== null) || readmes.find((f) => f.text !== null) || null;
    const readmeText = textReadme ? textReadme.text : "";
    const readmeLines = textReadme ? textReadme.lines : [];
    let hs = [];
    {
      const d = [];
      let st = "Pass", sum;
      if (!readmes.length) {
        st = "Review";
        sum = "No README file was found in the package.";
      } else if (!topReadme.length) {
        st = "Review";
        sum = "A README exists, but not at the top level of the package.";
        d.push("Found: " + readmes.map((f) => f.path).join(", "));
      } else {
        sum = "README found at the top level: " + topReadme.map((f) => f.path).join(", ") + ".";
      }
      if (textReadme) {
        hs = headings(readmeLines);
        const missing = [];
        README_SECTIONS.forEach(([name, re]) => {
          const h = hs.find((x) => re.test(x.t));
          if (h) d.push("Section found: " + name + " (" + textReadme.path + ":" + h.n + ")");
          else { missing.push(name); d.push("Section not found by heading: " + name); }
        });
        const rt = readmeLines.find((l) => /\b\d+(\.\d+)?\s*(-|to)?\s*\d*\s*(hours?|hrs?|minutes?|mins?|seconds?|days?|weeks?|core-hours)\b|\brun\s?time\b/i.test(l.t) && !/^#/.test(l.t.trim()) && /\d/.test(l.t));
        const hw = readmeLines.find((l) => /\b(\d+\s*(GB|TB|MB)\b|\d+[- ]core|RAM\b|cores?\b|CPU|GPU|laptop|desktop machine|cluster|server\b)/i.test(l.t) && !/^#/.test(l.t.trim()));
        d.push(rt ? "Runtime statement: " + textReadme.path + ":" + rt.n + " \"" + clip(rt.t, 80) + "\"" : "No runtime statement found (a time such as \"about 2 hours\").");
        d.push(hw ? "Hardware statement: " + textReadme.path + ":" + hw.n + " \"" + clip(hw.t, 80) + "\"" : "No hardware statement found (machine, cores, memory or storage).");
        if (missing.length || !rt || !hw) {
          st = "Review";
          sum += " " + (missing.length ? plural(missing.length, "template section") + " not found by heading." : "") + (!rt || !hw ? " Runtime or hardware statement missing." : "");
        } else if (st === "Pass") sum += " All seven template sections, a runtime and a hardware statement were found.";
        d.push("Sections are matched on heading text only. A section under a different heading is reported as not found.");
      } else if (readmes.length) {
        if (st === "Pass") st = "Info";
        d.push("The README is not a text file (or is over 5 MB), so its sections were not read. Check it against the template by hand.");
      }
      add(st, "README", sum.replace(/\s+/g, " ").trim(), d);
    }

    // 2. License
    {
      const lic = byName(/^(licen[sc]e|copying)(\.(txt|md|markdown|rst))?$/i);
      const line = readmeLines.find((l) => /\blicen[sc]ed?\b/i.test(l.t) && /\b(MIT|BSD|GPL|Apache|Creative Commons|CC[- ]?BY|CC0|public domain|LICENSE\.txt)\b/i.test(l.t));
      const head = hs.find((h) => /licen[sc]e/i.test(h.t));
      const d = [];
      lic.forEach((f) => d.push("License file: " + f.path));
      if (line) d.push("License statement: " + textReadme.path + ":" + line.n + " \"" + clip(line.t, 90) + "\"");
      else if (head) d.push("License heading: " + textReadme.path + ":" + head.n);
      const ok = lic.length || line || head;
      add(ok ? "Pass" : "Review", "License",
        ok ? (lic.length ? "A license file is in the package." : "The README states a license. No separate license file was found.")
          : "No LICENSE file and no license statement in the README.", d);
    }

    // 3. Environment
    {
      const d = [];
      let review = false;
      const find = (re) => byName(re).map((f) => f);
      const note = (l, msg) => d.push(l + ": " + msg);
      if (has("Python")) {
        const req = find(/^requirements.*\.txt$/i), env = find(/^environment.*\.ya?ml$/i);
        const locks = find(/^(pipfile\.lock|poetry\.lock|uv\.lock|conda-lock\.ya?ml|pixi\.lock)$/i);
        const loose = find(/^(pyproject\.toml|pipfile|setup\.py)$/i);
        if (!req.length && !env.length && !locks.length && !loose.length) { review = true; note("Python", "no requirements.txt, environment.yml, pyproject.toml or Pipfile.lock found."); }
        req.filter((f) => f.text !== null).forEach((f) => {
          const pk = f.lines.filter((l) => l.t.trim() && !/^\s*(#|-)/.test(l.t));
          const un = pk.filter((l) => !/===?|@\s*(https?|git|file)/.test(l.t));
          if (un.length) { review = true; note("Python", f.path + " has " + plural(un.length, "package") + " without an exact version: " + some(un.map((l) => clip(l.t, 40) + " (line " + l.n + ")"), 8).join(", ")); }
          else note("Python", f.path + " pins all " + plural(pk.length, "package") + " with ==.");
        });
        env.filter((f) => f.text !== null).forEach((f) => {
          let sec = "";
          const un = [], all = [];
          f.lines.forEach((l) => {
            const m = /^([A-Za-z_]+):/.exec(l.t);
            if (m) { sec = m[1]; return; }
            const it = /^\s*-\s+([^\s#:]+)\s*$/.exec(l.t);
            if (sec !== "dependencies" || !it) return;
            all.push(l);
            if (!/[=<>~]=?\s*\d/.test(it[1]) || /[<>~]/.test(it[1])) un.push(l);
          });
          if (un.length) { review = true; note("Python", f.path + " has " + (un.length === 1 ? "1 dependency" : un.length + " dependencies") + " without an exact version: " + some(un.map((l) => clip(l.t.replace(/^\s*-\s*/, ""), 40) + " (line " + l.n + ")"), 8).join(", ")); }
          else note("Python", f.path + " gives a version for all " + all.length + " dependencies.");
        });
        locks.forEach((f) => note("Python", "lock file " + f.path + " records exact versions."));
        if (loose.length && !locks.length && !req.length && !env.length) { review = true; note("Python", loose.map((f) => f.path).join(", ") + " found without a lock file, so exact versions are not recorded."); }
      }
      if (has("R")) {
        const lock = find(/^(renv\.lock|packrat\.lock)$/i), desc = find(/^DESCRIPTION$/);
        const inst = readCode.filter((f) => f.lang === "R").flatMap((f) => f.code.filter((l) => /\b(install\.packages|install_version|install_github|pak::pkg_install|groundhog\.library|renv::restore)\s*\(/.test(l.t)).map((l) => at(f, l)));
        lock.forEach((f) => note("R", "lock file " + f.path + " records exact versions."));
        if (!lock.length && desc.length) { review = true; note("R", desc[0].path + " lists packages but usually not the exact versions used. renv.lock does."); }
        if (!lock.length && !desc.length && inst.length) { review = true; note("R", "packages are installed by a script (" + some(inst, 4).join(", ") + "). install.packages() installs the current version, so list the versions you used in the README."); }
        if (!lock.length && !desc.length && !inst.length) { review = true; note("R", "no renv.lock, DESCRIPTION or install script found."); }
      }
      if (has("Julia")) {
        const proj = find(/^Project\.toml$/), man = find(/^Manifest\.toml$/);
        if (man.length) note("Julia", man[0].path + " records exact versions.");
        else if (proj.length) { review = true; note("Julia", proj[0].path + " found without Manifest.toml, so exact versions are not recorded."); }
        else { review = true; note("Julia", "no Project.toml or Manifest.toml found."); }
      }
      if (has("Stata")) {
        const ssc = readCode.filter((f) => f.lang === "Stata").flatMap((f) => f.code.filter((l) => /^\s*(cap(ture)?\s+)?(ssc\s+install|net\s+install)\b/i.test(l.t)).map((l) => at(f, l)));
        const ados = live.filter((f) => f.ext === "ado");
        if (ados.length) note("Stata", plural(ados.length, "ado file") + " shipped in the package (" + dirOf(ados[0].path) + "/).");
        if (ssc.length) { if (!ados.length) review = true; note("Stata", "packages installed at " + some(ssc, 5).join(", ") + ". ssc install fetches the current version."); }
        note("Stata", "Stata has no dependency manifest. Note the Stata version and the version or install date of each ado package in the README.");
      }
      ["MATLAB", "SAS"].forEach((l) => { if (has(l)) note(l, "no manifest format is checked. State the version and any toolboxes in the README."); });
      const VER = {
        Stata: /\bStata\b[^\n]{0,60}?\b\d{1,2}(\.\d+)?\b/i, R: /\bR\s*(\(|version|v\.?)?\s*\d\.\d+(\.\d+)?/, Python: /\bPython\b[^\n]{0,30}?\d(\.\d+)+/i,
        Julia: /\bJulia\b[^\n]{0,30}?\d(\.\d+)+/i, MATLAB: /\bMatlab\b[^\n]{0,40}?(R?20\d\d[ab]?|\d+\.\d+)/i, SAS: /\bSAS\b[^\n]{0,30}?\d+(\.\d+)?/,
      };
      Object.keys(VER).filter(has).forEach((l) => {
        const ln = readmeLines.find((x) => VER[l].test(x.t));
        if (ln) d.push(l + " version stated in the README: " + textReadme.path + ":" + ln.n + " \"" + clip(ln.t, 70) + "\"");
        else { review = true; d.push(l + " version not found in the README" + (textReadme ? "." : " (no text README to read).")); }
      });
      const any = Object.keys(langs).some((l) => l !== "Shell");
      add(!any ? "Info" : review ? "Review" : "Pass", "Environment",
        !any ? "No code files in a checked language were found."
          : review ? "Some dependencies or software versions are not recorded exactly."
            : "Each language found has a dependency file with exact versions, and the README states the software version.", d);
    }

    // 4. Entry point
    const ENTRY_RE = /^((main|master|run_?all|run|runme|00?_[\w.-]*|0_[\w.-]*)\.(r|rmd|qmd|py|do|jl|m|sas|sh|ipynb)|makefile|gnumakefile|snakefile)$/i;
    const entries = live.filter((f) => ENTRY_RE.test(f.name));
    const topEntries = entries.filter((f) => depth(f.path) === 0);
    {
      const numbered = {};
      codeFiles.filter((f) => /^\d{1,3}[_-]/.test(f.name)).forEach((f) => { (numbered[dirOf(f.path)] = numbered[dirOf(f.path)] || []).push(f.name); });
      const numDirs = Object.keys(numbered).filter((k) => numbered[k].length >= 2);
      const d = [];
      let st = "Pass", sum;
      if (topEntries.length) sum = "Entry point at the top level: " + topEntries.map((f) => f.path).join(", ") + ".";
      else if (entries.length) { sum = "Entry point found below the top level: " + some(entries.map((f) => f.path), 4).join(", ") + "."; d.push("Name it in the README instructions so a replicator does not have to look for it."); }
      else if (numDirs.length) sum = "No main script, but numbered scripts give the order.";
      else { st = "Review"; sum = "No main, master or run script, no Makefile and no numbered scripts were found."; }
      numDirs.forEach((k) => d.push("Numbered scripts in " + (k || "the top level") + "/: " + some(numbered[k].sort(), 8).join(", ")));
      if (!codeFiles.length) { st = "Info"; sum = "No code files were found."; }
      add(st, "Entry point", sum, d);
    }

    // 5. Absolute paths
    {
      const PATHS = [
        [/(^|[^A-Za-z0-9])[A-Za-z]:[\\/](?![\\/])[^\s"']/, "Windows drive path"],
        [/(^|["'`\s(=,])\/(Users|home|Volumes|mnt|media)\/[^\s]/, "absolute path"],
        [/(^|["'`\s(=,])~[\\/]/, "home-directory path"],
      ];
      const hits = [];
      readCode.forEach((f) => f.code.forEach((l) => {
        if (/https?:\/\//.test(l.t) && !/[A-Za-z]:\\/.test(l.t) && !/\/(Users|home)\//.test(l.t)) return;
        const p = PATHS.find(([re]) => re.test(l.t));
        if (!p) return;
        const kind = /\bsetwd\s*\(/.test(l.t) ? "setwd with an " + (p[1] === "absolute path" ? p[1] : "absolute path") : /^\s*cd\s/.test(l.t) ? "cd to an absolute path" : p[1];
        hits.push({ f: f.path, s: at(f, l) + " " + kind + ": " + clip(l.t, 90) });
      }));
      const inFiles = new Set(hits.map((h) => h.f));
      const d = some(hits.map((h) => h.s), 25);
      if (hits.length && inFiles.size === 1) d.push("All of them are in one file. A single top-level configuration file that sets the base directory is the one change a replicator can be asked to make.");
      add(hits.length ? "Review" : readCode.length ? "Pass" : "Info", "Paths",
        hits.length ? plural(hits.length, "line") + " in " + plural(inFiles.size, "file") + " point to a location on one machine."
          : readCode.length ? "No absolute paths were found in " + plural(readCode.length, "code file") + "." : "No code files were read.", d);
    }

    // 6. Randomness
    {
      const RNG = {
        R: [/\b(sample|rnorm|runif|rbinom|rpois|rexp|rgamma|rbeta|rt|rchisq|rlogis|rmultinom|sample_n|sample_frac|slice_sample|mvrnorm|rmvnorm|bootstraps|createDataPartition|vfold_cv|initial_split)\s*\(/, /\bset\.seed\s*\(/],
        Python: [/\b(np|numpy)\.random\.(?!seed\b|default_rng\b|RandomState\b|Generator\b|SeedSequence\b)\w+\s*\(|\bdefault_rng\s*\(\s*\)|\brandom\.(random|randint|choice|choices|shuffle|sample|uniform|gauss|normalvariate|randrange)\s*\(|\btorch\.(rand|randn|randint|randperm|normal|bernoulli|multinomial)\w*\s*\(|\btrain_test_split\s*\(|\brng\.\w+\s*\(/,
          /\b(np|numpy)\.random\.seed\s*\(|\brandom\.seed\s*\(|\bdefault_rng\s*\(\s*\w+|\bRandomState\s*\(\s*\d+|\btorch\.manual_seed\s*\(|\brandom_state\s*=\s*\d+|\bset_seed\s*\(|\bseed_everything\s*\(/],
        Stata: [/\b(runiform|runiformint|rnormal|rbinomial|rpoisson|rbeta|rgamma|rchi2|rt|rlogistic|rexponential)\s*\(|^\s*(cap(ture)?\s+|qui(etly)?\s+)*(bootstrap|simulate|permute|bsample|sample)\b|\bvce\s*\(\s*boot/i, /^\s*set\s+seed\b|\bseed\s*\(\s*\d+/i],
        Julia: [/\b(rand|randn|randperm|randexp|shuffle!?|sample)\s*\(/, /\bRandom\.seed!\s*\(|\bseed!\s*\(|\b(MersenneTwister|Xoshiro|StableRNG)\s*\(\s*\d+/],
        MATLAB: [/\b(rand|randn|randi|randperm|normrnd|unifrnd|mvnrnd|datasample|bootstrp|randsample)\s*\(/, /\brng\s*\(|^\s*rng\s+\w+|\bRandStream\b/],
        SAS: [/\b(ranuni|rannor|ranbin|rand)\s*\(|proc\s+surveyselect/i, /call\s+streaminit|\bseed\s*=\s*\d+/i],
      };
      const seedOf = (f) => (RNG[f.lang] ? f.code.filter((l) => RNG[f.lang][1].test(l.t)) : []);
      const central = readCode.filter((f) => ENTRY_RE.test(f.name) || /^config\./i.test(f.name));
      const centralSeeds = central.flatMap((f) => seedOf(f).map((l) => at(f, l)));
      const d = [];
      let unseeded = 0, drawing = 0;
      readCode.forEach((f) => {
        if (!RNG[f.lang]) return;
        const draws = f.code.filter((l) => RNG[f.lang][0].test(l.t));
        const seeds = seedOf(f);
        if (!draws.length) { if (seeds.length) d.push("Random seed is set at " + seeds.map((l) => at(f, l)).join(", ") + "."); return; }
        drawing++;
        const where = some(draws.map((l) => at(f, l) + " " + clip(l.t, 60)), 4).join("; ");
        if (seeds.length) d.push(f.path + ": seed set at " + seeds.map((l) => "line " + l.n).join(", ").replace(/line cell/g, "cell") + ". Draws at " + where);
        else if (centralSeeds.length) d.push(f.path + ": no seed in this file, but one is set at " + centralSeeds.join(", ") + ". Draws at " + where);
        else { unseeded++; d.push(f.path + ": random numbers drawn with no seed set in this file or in the entry script. Draws at " + where); }
      });
      add(unseeded ? "Review" : readCode.length ? "Pass" : "Info", "Randomness",
        unseeded ? plural(unseeded, "file") + (unseeded === 1 ? " draws" : " draw") + " random numbers without a seed."
          : drawing ? "Every file that draws random numbers has a seed set, in the file or in the entry script."
            : readCode.length ? "No calls that draw random numbers were found." : "No code files were read.", d);
    }

    // 7 and 8 share one pass over string literals in code.
    const WRITE_RE = /\b(write[._]\w+|saveRDS|save|fwrite|ggsave|to_(csv|latex|excel|stata|parquet|pickle|html|feather|json)|savefig|np\.save\w*|dump|export|outsheet|esttab|outreg2?|estout|graph\s+export|CSV\.write|writetable|writematrix|saveas|exportgraphics|texsave|putexcel|log\s+using|pdf|png|jpeg|stargazer)\b|open\s*\([^)]*,\s*["'][wa]/i;
    const OUTDIR_RE = /(^|\/)(output|outputs|out|results?|tables?|figures?|figs?|plots?|exhibits?|temp|tmp|intermediate|derived|processed)(\/|$)/i;
    const refs = [];
    readCode.forEach((f) => f.code.forEach((l) => {
      const lits = [];
      l.t.replace(/"([^"\n]{1,240})"|'([^'\n]{1,240})'/g, (m, a, b) => { lits.push(a || b); return m; });
      if (f.lang === "Stata") {
        const m = /^\s*(?:cap(?:ture)?\s+|qui(?:etly)?\s+)*(use|save|append\s+using|merge\s+.*?\busing|joinby\s+.*?\busing|import\s+\w+(?:\s+using)?|insheet\s+using|export\s+\w+(?:\s+using)?|outsheet\s+using)\s+"?([^\s,"]+)/i.exec(l.t);
        if (m && !/^(using|if|in)$/i.test(m[2])) {
          let p = m[2];
          if (/^(use|save|append|merge|joinby)/i.test(m[1]) && !/\.\w{2,8}$/.test(p)) p += ".dta";
          if (!lits.includes(m[2])) lits.push(p); else lits[lits.indexOf(m[2])] = p;
        }
      }
      const writes = WRITE_RE.test(l.t) && !/\b(read[._]\w+|readRDS|pd\.read_\w+|^\s*use\b|import\s+delimited|import\s+excel)\b/i.test(l.t.replace(WRITE_RE, ""));
      lits.forEach((s) => {
        if (/^(https?|ftp|s3):/i.test(s) || !DATA_RE.test(s)) return;
        let p = s.replace(/\\\\?/g, "/");
        const cut = Math.max(p.lastIndexOf("$"), p.lastIndexOf("}"), p.lastIndexOf("'"), p.lastIndexOf("`"));
        if (cut >= 0) p = p.slice(p.indexOf("/", cut) + 1 || cut + 1);
        const abs = /^([A-Za-z]:\/|\/|~\/)/.test(p);
        p = p.replace(/^([A-Za-z]:)?\/+/, "").replace(/^~\//, "").replace(/^(\.\.?\/)+/, "");
        if (!p) return;
        refs.push({ p, shown: abs ? s : p, abs, writes, where: at(f, l) });
      });
    }));

    // 7. Data
    {
      const data = live.filter((f) => DATA_RE.test(f.name));
      const lower = live.map((f) => f.path.toLowerCase());
      const names = new Set(lower.map(base));
      const inPkg = (r) => {
        const p = r.p.toLowerCase();
        if (!r.abs && lower.some((x) => x === p || x.endsWith("/" + p))) return true;
        return names.has(base(p));
      };
      const written = new Set(refs.filter((r) => r.writes).map((r) => base(r.p).toLowerCase()));
      const missing = new Map();
      refs.filter((r) => !r.writes && !inPkg(r) && !written.has(base(r.p).toLowerCase()) && !OUTDIR_RE.test(dirOf(r.p)))
        .forEach((r) => { if (!missing.has(r.shown)) missing.set(r.shown, []); missing.get(r.shown).push(r.where); });
      const allCode = readCode.map((f) => f.code.map((l) => l.t).join("\n")).join("\n").toLowerCase();
      const unref = data.filter((f) => {
        const b = f.name.toLowerCase();
        if (allCode.includes(b)) return false;
        const stem = b.replace(/\.[^.]+$/, "");
        if (/^(dta|rds|rdata|rda)$/.test(f.ext) && stem.length > 2 && new RegExp("(^|[^a-z0-9_])" + stem.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "([^a-z0-9_.]|$)").test(allCode)) return false;
        return true;
      });
      const d = [];
      missing.forEach((w, p) => d.push("Referenced but not in the package: " + p + " (read at " + some(w, 3).join(", ") + ")"));
      some(unref.map((f) => "In the package but not named in any code file: " + f.path + " (" + fmtSize(f.size) + ")"), 15).forEach((x) => d.push(x));
      const folder = {};
      live.forEach((f) => { const k = f.path.includes("/") ? f.path.split("/")[0] + "/" : "(top level)"; folder[k] = (folder[k] || 0) + f.size; });
      d.push("Size by folder: " + Object.entries(folder).sort((a, b) => b[1] - a[1]).slice(0, 10).map(([k, v]) => k + " " + fmtSize(v)).join(", ") + ".");
      const big = live.filter((f) => f.size > BIG_FILE);
      big.forEach((f) => d.push("Over 100 MB: " + f.path + " (" + fmtSize(f.size) + ")"));
      const heads = data.filter((f) => f.header !== undefined).slice(0, 5).map((f) => f.path + " (" + plural(f.header.split(/[,;\t]/).length, "column") + ")");
      if (heads.length) d.push("CSV header rows read: " + heads.join(", ") + ".");
      if (missing.size) d.push("A file that an earlier script creates, or that the README tells the replicator to download, is expected to be absent. Say so in the Data Availability Statement.");
      if (unref.length) d.push("Files read through a loop or a pattern (list.files, glob, a Stata macro) can appear here although they are used.");
      const dataRefs = refs.filter((r) => !r.writes).length;
      add(missing.size || unref.length ? "Review" : data.length || dataRefs ? "Pass" : "Info", "Data",
        missing.size || unref.length
          ? [missing.size ? plural(missing.size, "data file") + " named in code " + (missing.size === 1 ? "is" : "are") + " not in the package" : "", unref.length ? plural(unref.length, "data file") + " in the package " + (unref.length === 1 ? "is" : "are") + " not named in any code" : ""].filter(Boolean).join("; ") + "."
          : data.length || dataRefs ? "Every data file named in code is in the package, and every data file in the package is named in code (" + plural(data.length, "data file") + ")."
            : "No data files in the package and none named in code.", d);
    }

    // 8. Outputs
    {
      const OUT_CALL = /\b(ggsave|write\.csv|write_csv|write\.table|write_xlsx|stargazer|modelsummary|etable|kable|xtable|savefig|to_latex|to_csv|to_excel|esttab|estout|outreg2?|graph\s+export|putexcel|texsave|export\s+(delimited|excel)|CSV\.write|writetable|exportgraphics|saveas)\b|^\s*(pdf|png|jpeg|tiff|svg)\s*\(/i;
      const calls = readCode.flatMap((f) => f.code.filter((l) => OUT_CALL.test(l.t) && !/\b(install|library|require|import|using\s+[A-Z]\w*\s*$)\b/.test(l.t.split(/["']/)[0])).map((l) => at(f, l) + " " + clip(l.t, 60)));
      const outDirs = [...dirs].filter((x) => /^(output|outputs|out|results?|tables?|figures?|figs?|plots?|exhibits?)$/i.test(base(x)) && depth(x) <= 2);
      const mk = readCode.some((f) => f.code.some((l) => /\b(dir\.create|makedirs|mkdir|mkpath)\b/i.test(l.t)));
      const listHead = hs.find((h) => /list\s+of\s+(tables|figures|exhibits)/i.test(h.t));
      const mapLines = readmeLines.filter((l) => /\b(table|figure|fig\.?)\s*[A-Z]?\d+/i.test(l.t) && /\b[\w.-]+\.(R|Rmd|qmd|py|do|jl|m|sas|ipynb|sh)\b/i.test(l.t));
      const d = [];
      if (calls.length) d.push("Code that writes tables or figures: " + some(calls, 6).join("; "));
      d.push(outDirs.length ? "Output folder: " + outDirs.map((x) => x + "/").join(", ")
        : mk ? "No output folder in the package, but the code creates folders when it runs." : "No output folder (output, results, tables, figures) in the package and no code that creates one.");
      d.push(mapLines.length ? "README lines that tie a table or figure to a program: " + mapLines.length + " (first at " + textReadme.path + ":" + mapLines[0].n + ")"
        : listHead ? "The README has a list of tables heading, but no line names both a table or figure number and a program file."
          : "The README does not map tables and figures to programs.");
      const ok = calls.length && (outDirs.length || mk) && mapLines.length;
      add(!readCode.length ? "Info" : ok ? "Pass" : "Review", "Outputs",
        !readCode.length ? "No code files were read."
          : ok ? "The code writes tables or figures, an output folder exists, and the README maps outputs to programs."
            : !calls.length ? "No calls that write tables or figures were found."
              : !(outDirs.length || mk) ? "The code writes outputs, but there is no output folder." : "The README does not say which program makes which table or figure.", d);
    }

    // 9. Hygiene
    {
      const d = [];
      const single = files.filter((f) => /^(\.DS_Store|Thumbs\.db|desktop\.ini|\.Rhistory|\.RData|\.Rapp\.history)$/i.test(f.name) || /\.(pyc|swp|bak)$|^~\$|~$/i.test(f.name))
        .filter((f) => !/(^|\/)(__MACOSX|__pycache__|\.ipynb_checkpoints|\.git|\.Rproj\.user)\//.test(f.path));
      const group = {};
      files.forEach((f) => { const m = /(^|\/)(__MACOSX|__pycache__|\.ipynb_checkpoints|\.git|\.Rproj\.user)\//.exec(f.path); if (m) { const k = f.path.slice(0, m.index + m[0].length); group[k] = (group[k] || 0) + 1; } });
      some(single.map((f) => "Debris: " + f.path), 15).forEach((x) => d.push(x));
      some(Object.entries(group).map(([k, v]) => "Debris: " + k + " (" + plural(v, "file") + ")"), 10).forEach((x) => d.push(x));
      const CRED = /([A-Za-z0-9_.-]*(api[_-]?key|secret|token|passw(or)?d|pwd|access[_-]?key|auth)[A-Za-z0-9_-]*)["']?\s*(=|:|<-)\s*(["'])([^"'\s]{4,})\5/i;
      const ENVCRED = /^\s*(export\s+)?([A-Za-z0-9_]*(API_?KEY|SECRET|TOKEN|PASSWORD|PASSWD)[A-Za-z0-9_]*)\s*[=:]\s*([^\s"'#]{6,})\s*$/i;
      const KNOWN = /\b(AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|sk-[A-Za-z0-9_-]{20,}|xox[bp]-[A-Za-z0-9-]{10,})\b/;
      const PLACE = /^(x{3,}|\*+|your|<|\$|%|changeme|none|null|true|false|todo|os\.|env|getenv|sys\.)/i;
      const creds = [];
      live.filter((f) => f.text !== null && f.ext !== "lock").forEach((f) => f.lines.forEach((l) => {
        let m = CRED.exec(l.t), name, val;
        if (m) { name = m[1]; val = m[6]; }
        else if (/^(env|renviron|yml|yaml|ini|cfg|toml|sh)$/.test(f.ext) || /^\.env/.test(f.name)) { m = ENVCRED.exec(l.t); if (m) { name = m[2]; val = m[4]; } }
        if (!m) { m = KNOWN.exec(l.t); if (m) { name = "key"; val = m[1]; } }
        if (!m || PLACE.test(val)) return;
        creds.push("Looks like a credential: " + at(f, l) + " " + name + " = \"" + "*".repeat(Math.min(val.length, 8)) + "\" (" + val.length + " characters, hidden)");
      }));
      some(creds, 15).forEach((x) => d.push(x));
      const nbs = live.filter((f) => f.ext === "ipynb" && ((f.nbOutput || 0) > NB_OUTPUT_MAX || f.skipped));
      nbs.forEach((f) => d.push("Notebook with large stored outputs: " + f.path + (f.skipped ? " (file is " + fmtSize(f.size) + ", not read)" : " (" + fmtSize(f.nbOutput) + " of outputs)")));
      const debrisN = single.length + Object.keys(group).length;
      const bad = debrisN || creds.length || nbs.length;
      add(bad ? "Review" : "Pass", "Hygiene",
        bad ? [debrisN ? plural(debrisN, "piece") + " of system or editor debris" : "", creds.length ? plural(creds.length, "line") + " that " + (creds.length === 1 ? "looks" : "look") + " like a credential" : "", nbs.length ? plural(nbs.length, "notebook") + " with large stored outputs" : ""].filter(Boolean).join(", ") + "."
          : "No system debris, no credential-looking strings and no oversized notebook outputs.", d);
    }

    // 10. Summary
    {
      const total = live.reduce((a, f) => a + f.size, 0);
      const skipped = files.filter((f) => f.skipped);
      const zips = live.filter((f) => /\.(zip|7z|tar|gz|tgz|rar)$/i.test(f.name));
      const d = [];
      d.push("Languages: " + (Object.keys(langs).length ? Object.entries(langs).sort((a, b) => b[1] - a[1]).map(([k, v]) => k + " (" + plural(v, "file") + ")").join(", ") : "none found") + ".");
      d.push(plural(files.length, "file") + ", " + fmtSize(total) + " unpacked." + (pkg.root ? " Everything sits in one folder, " + pkg.root + "/, which was treated as the top level." : ""));
      if (skipped.length) d.push("Not read because they are over 5 MB: " + some(skipped.map((f) => f.path + " (" + fmtSize(f.size) + ")"), 8).join(", "));
      if (zips.length) d.push("Archives inside the package were not opened: " + some(zips.map((f) => f.path), 6).join(", "));
      if (files.length > 1000) d.push("The package has more than 1,000 files. The AEA guidance says ICPSR cannot accept deposits with more than 1,000 files and describes zipping large directories.");
      d.push("What a person still has to do: download the package to a clean machine, follow the README from the first line, and run the code from start to finish. This tool does not execute anything. It cannot tell whether the code runs, whether it finishes in the stated time, or whether the tables and figures it writes match the ones in the paper.");
      add("Info", "Summary", Object.keys(langs).length ? "Code in " + Object.keys(langs).join(", ") + ". The checks above read file names and text; none of the code was run." : "No code files were found in the package.", d);
    }
    return results;
  }

  // ---------- rendering ----------
  function render(results, fileName, pkg) {
    out.textContent = "";
    const counts = { Pass: 0, Review: 0, Info: 0 };
    results.forEach((r) => { counts[r.status] = (counts[r.status] || 0) + 1; });
    const h = document.createElement("h2");
    h.textContent = "Results for " + fileName;
    out.appendChild(h);
    const sum = document.createElement("p");
    sum.className = "rp-summary";
    sum.textContent = plural(pkg.files.length, "file") + ". " + counts.Pass + " checks passed, " + counts.Review + " to review, " + counts.Info + " for information.";
    out.appendChild(sum);
    const txt = ["Replication Package Checker report for " + fileName, sum.textContent, ""];
    results.forEach((r) => {
      const card = document.createElement("section");
      card.className = "rp-card rp-" + r.status.toLowerCase();
      const head = document.createElement("h3");
      const tag = document.createElement("span");
      tag.className = "rp-tag";
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
    txt.push("Checked in the browser at purplelink.llc/tools/reproducibility-checker/. The file was not uploaded and no code was run.");
    lastReport = txt.join("\n");
    dl.hidden = false;
    out.hidden = false;
    out.focus({ preventScroll: false });
  }

  async function run(file) {
    if (!file) return;
    out.hidden = true;
    dl.hidden = true;
    if (!/\.zip$/i.test(file.name) && !/zip/.test(file.type)) { setStatus("Choose a .zip file.", false); return; }
    if (file.size > MAX_ZIP) { setStatus("That zip is over 500 MB. Leave the largest data files out and check the rest.", false); return; }
    if (!window.JSZip) { setStatus("The zip reader did not load. Reload the page and try again.", false); return; }
    try {
      const pkg = await readZip(file);
      if (!pkg.files.length) { setStatus("That zip is empty.", false); return; }
      render(evaluate(pkg), file.name, pkg);
      setStatus("Done. Nothing left your browser.", false);
    } catch (e) {
      console.error("reproducibility-checker:", e);
      setStatus("This zip could not be read" + (e && /encrypt/i.test(e.message || "") ? " because it is password protected." : ". It may be damaged or not a zip file."), false);
    }
  }

  fileInput.addEventListener("change", () => run(fileInput.files[0]));
  ["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("is-over"); }));
  ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("is-over"); }));
  drop.addEventListener("drop", (e) => { const f = e.dataTransfer.files[0]; if (f) run(f); });
  dl.addEventListener("click", () => {
    const url = URL.createObjectURL(new Blob([lastReport], { type: "text/plain" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "reproducibility-report.txt";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  });
})();
