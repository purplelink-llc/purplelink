/* Daily Sudoku. Puzzles get harder every week for ten weeks, then a new season starts. */
(function () {
  "use strict";
  var G = window.PLGames, NAME = "sudoku", URL_ = "https://purplelink.llc/games/sudoku/";
  if (!G) return;
  var $ = function (id) { return document.getElementById(id); };
  function fmt(sec) { var m = Math.floor(sec / 60), s = sec % 60; return m + ":" + (s < 10 ? "0" : "") + s; }

  var st = { idx: 0, pz: null, given: [], sol: [], cells: [], notes: [], sel: 0, noteMode: false, auto: false, elapsed: 0, checks: 0, hints: 0, done: false, wrong: {}, ticking: false, last: 0 };

  function peers(i) {
    var r = Math.floor(i / 9), c = i % 9, b = Math.floor(r / 3) * 3 + Math.floor(c / 3), out = [];
    for (var k = 0; k < 81; k++) {
      if (k === i) continue;
      var kr = Math.floor(k / 9), kc = k % 9;
      if (kr === r || kc === c || Math.floor(kr / 3) * 3 + Math.floor(kc / 3) === b) out.push(k);
    }
    return out;
  }
  var PEERS = []; for (var q = 0; q < 81; q++) PEERS.push(peers(q));

  function build() {
    var g = $("sd-grid"); g.textContent = "";
    for (var i = 0; i < 81; i++) {
      var b = document.createElement("button");
      b.type = "button"; b.className = "sd-cell"; b.setAttribute("data-i", i); b.tabIndex = i === st.sel ? 0 : -1;
      var r = Math.floor(i / 9), c = i % 9;
      if (c % 3 === 2 && c !== 8) b.setAttribute("data-bx", "1");
      if (r % 3 === 2 && r !== 8) b.setAttribute("data-by", "1");
      var v = document.createElement("span"); v.className = "sd-val"; b.appendChild(v);
      var n = document.createElement("span"); n.className = "sd-notes"; n.setAttribute("aria-hidden", "true"); b.appendChild(n);
      g.appendChild(b);
    }
  }

  function conflicts() {
    var bad = {};
    for (var i = 0; i < 81; i++) {
      var v = st.cells[i]; if (!v) continue;
      for (var k = 0; k < PEERS[i].length; k++) if (st.cells[PEERS[i][k]] === v) { bad[i] = 1; break; }
    }
    return bad;
  }

  function paint() {
    var cells = $("sd-grid").children, bad = conflicts(), selV = st.cells[st.sel], peerSet = {};
    PEERS[st.sel].forEach(function (p) { peerSet[p] = 1; });
    for (var i = 0; i < 81; i++) {
      var el = cells[i], v = st.cells[i];
      el.firstChild.textContent = v ? String(v) : "";
      var notes = "";
      if (!v && st.notes[i]) for (var d = 1; d <= 9; d++) notes += (st.notes[i] & (1 << (d - 1))) ? d : " ";
      el.lastChild.textContent = notes;
      el.toggleAttribute("data-given", !!st.given[i]);
      el.toggleAttribute("data-sel", i === st.sel);
      el.toggleAttribute("data-peer", !!peerSet[i]);
      el.toggleAttribute("data-same", !!selV && v === selV && i !== st.sel);
      el.toggleAttribute("data-bad", !!bad[i] || !!st.wrong[i]);
      el.tabIndex = i === st.sel ? 0 : -1;
      el.setAttribute("aria-label", "Row " + (Math.floor(i / 9) + 1) + ", column " + (i % 9 + 1) + (v ? ", " + v + (st.given[i] ? ", given" : "") : ", empty") + (bad[i] ? ", conflicts" : "") + (st.wrong[i] ? ", wrong" : ""));
    }
    var counts = {}; st.cells.forEach(function (v) { if (v) counts[v] = (counts[v] || 0) + 1; });
    Array.prototype.forEach.call($("sd-pad").querySelectorAll("[data-d]"), function (b) {
      b.toggleAttribute("data-full", (counts[b.getAttribute("data-d")] || 0) >= 9);
    });
    $("sd-notes-btn").setAttribute("aria-pressed", st.noteMode ? "true" : "false");
    $("sd-notes-btn").textContent = st.noteMode ? "Notes: on" : "Notes: off";
  }

  function persist() {
    var s = G.getGame(NAME);
    s.today = { idx: st.idx, cells: st.cells.join("").replace(/0/g, "."), notes: st.notes.map(function (n) { return n || 0; }), elapsed: st.elapsed, checks: st.checks, reveals: st.hints, done: st.done };
    G.setGame(NAME, s);
  }

  function startClock() { if (st.ticking || st.done) return; st.ticking = true; st.last = Date.now(); G.track("game_start", NAME); }
  function tickClock() {
    if (st.ticking && !st.done && document.visibilityState === "visible") { var now = Date.now(); st.elapsed += Math.round((now - st.last) / 1000); st.last = now; } else st.last = Date.now();
    $("sd-timer").textContent = fmt(st.elapsed);
    if (st.ticking && st.elapsed % 5 === 0) persist();
  }

  function setValue(i, d) {
    if (st.done || st.given[i]) return;
    startClock();
    if (st.noteMode && d) {
      if (st.cells[i]) return;
      st.notes[i] = (st.notes[i] || 0) ^ (1 << (d - 1));
    } else {
      st.cells[i] = d; st.notes[i] = 0; delete st.wrong[i];
      if (d) {
        PEERS[i].forEach(function (p) { if (st.notes[p]) st.notes[p] &= ~(1 << (d - 1)); });   // keep pencil marks honest
        if (st.auto && d !== st.sol[i]) st.wrong[i] = 1;
      }
    }
    persist(); paint(); checkDone();
  }

  function checkDone() {
    if (st.done) return;
    for (var i = 0; i < 81; i++) if (!st.cells[i]) { $("sd-status").textContent = ""; return; }
    for (i = 0; i < 81; i++) if (st.cells[i] !== st.sol[i]) { $("sd-status").textContent = "Every square is filled, but something is not right yet. Duplicates are shown in red; Check puzzle finds the rest."; return; }
    st.done = true; persist(); finish(true);
  }

  function check(scope) {
    var list = scope === "cell" ? [st.sel] : Array.from({ length: 81 }, function (_, k) { return k; });
    st.checks += 1; var bad = 0, filled = 0;
    list.forEach(function (i) { delete st.wrong[i]; if (!st.cells[i] || st.given[i]) return; filled++; if (st.cells[i] !== st.sol[i]) { st.wrong[i] = 1; bad++; } });
    $("sd-status").textContent = !filled ? "Nothing entered to check yet." : bad ? bad + (bad === 1 ? " square is" : " squares are") + " wrong, shown in red." : (scope === "cell" ? "That square is correct." : "Everything entered so far is correct.");
    startClock(); persist(); paint();
  }
  function setAuto(on) {
    st.auto = on; var s = G.getGame(NAME); s.auto = on; G.setGame(NAME, s);
    $("sd-auto").setAttribute("aria-pressed", on ? "true" : "false"); $("sd-auto").textContent = on ? "Auto-check: on" : "Auto-check: off";
    if (on) { st.checks += 1; for (var i = 0; i < 81; i++) if (st.cells[i] && !st.given[i] && st.cells[i] !== st.sol[i]) st.wrong[i] = 1; $("sd-status").textContent = "Auto-check is on: wrong digits turn red as you type."; } else $("sd-status").textContent = "";
    persist(); paint();
  }
  function reveal() {
    if (st.done || st.given[st.sel]) return;
    st.hints += 1; st.cells[st.sel] = st.sol[st.sel]; st.notes[st.sel] = 0; delete st.wrong[st.sel];
    startClock(); persist(); paint(); checkDone();
  }

  function finish(fresh) {
    var saved = G.getGame(NAME), clean = !st.checks && !st.hints;
    if (fresh) {
      saved.stats = G.recordResult(saved.stats, st.idx, true, 1);
      saved.best = saved.best || {};
      if (clean) { saved.clean = (saved.clean || 0) + 1; if (!saved.best[st.pz.level] || st.elapsed < saved.best[st.pz.level]) saved.best[st.pz.level] = st.elapsed; }
      G.setGame(NAME, saved);
      G.track("game_end", NAME + ":" + (clean ? "clean" : "assisted"));
      var ctx = { game: NAME, idx: st.idx, won: true, clean: clean, seconds: st.elapsed, level: st.pz.level };
      if (window.PLAch) window.PLAch.check(ctx);
      if (window.PLConfetti) window.PLConfetti[clean ? "big" : "small"]();
      if (clean) G.submitScore(NAME, st.idx, Math.min(400, Math.floor(st.elapsed / 30))).then(function (res) {
        $("sd-pct").textContent = G.describePercentile(res);
        if (res && window.PLAch) window.PLAch.check({ game: NAME, idx: st.idx, won: true, clean: true, seconds: st.elapsed, level: st.pz.level, pct: res.percentile, total: res.total });
      });
    }
    var s = saved.stats || G.emptyStats();
    var sv = $("sd-saver"); if (sv) sv.textContent = G.saverNote(s, st.idx);
    $("sd-result").hidden = false;
    $("sd-result-head").textContent = "Solved in " + fmt(st.elapsed) + (clean ? "" : " with help");
    $("sd-played").textContent = s.played; $("sd-streak").textContent = s.streak; $("sd-max").textContent = s.max;
    var best = saved.best && saved.best[st.pz.level];
    $("sd-best").textContent = best ? fmt(best) : "none"; $("sd-best-label").textContent = "Best " + st.pz.level;
    $("sd-status").textContent = ""; $("sd-timer").textContent = fmt(st.elapsed);
    tick();
    if (fresh) $("sd-result").scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
  function tick() {
    var el = $("sd-next-in"); if (!el || $("sd-result").hidden) return;
    var now = new Date(), nx = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1), ms = nx - now, h = Math.floor(ms / 3600000), m = Math.floor((ms % 3600000) / 60000);
    el.textContent = h + " h " + (m < 10 ? "0" : "") + m + " min";
  }
  function shareText() { var clean = !st.checks && !st.hints; return "Sudoku " + (st.idx + 1) + " (" + st.pz.level + ") solved in " + fmt(st.elapsed) + (clean ? ", no help" : ", with help") + "\n\n" + URL_; }

  function move(d) {
    var r = Math.floor(st.sel / 9), c = st.sel % 9;
    if (d === "ArrowUp") r = Math.max(0, r - 1); else if (d === "ArrowDown") r = Math.min(8, r + 1); else if (d === "ArrowLeft") c = Math.max(0, c - 1); else c = Math.min(8, c + 1);
    st.sel = r * 9 + c; paint(); $("sd-grid").children[st.sel].focus();
  }

  function wire() {
    $("sd-grid").addEventListener("click", function (e) { var b = e.target.closest(".sd-cell"); if (!b) return; st.sel = Number(b.getAttribute("data-i")); paint(); b.focus(); });
    $("sd-grid").addEventListener("keydown", function (e) {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      var k = e.key;
      if (/^[1-9]$/.test(k)) setValue(st.sel, Number(k));
      else if (k === "Backspace" || k === "Delete" || k === "0") setValue(st.sel, 0);
      else if (k.indexOf("Arrow") === 0) move(k);
      else if (k === "n" || k === "N") { st.noteMode = !st.noteMode; paint(); }
      else return;
      e.preventDefault();
    });
    $("sd-pad").addEventListener("click", function (e) { var b = e.target.closest("[data-d]"); if (b) setValue(st.sel, Number(b.getAttribute("data-d"))); });
    $("sd-erase").addEventListener("click", function () { setValue(st.sel, 0); });
    $("sd-notes-btn").addEventListener("click", function () { st.noteMode = !st.noteMode; paint(); });
    $("sd-check-cell").addEventListener("click", function () { check("cell"); });
    $("sd-check").addEventListener("click", function () { check("puzzle"); });
    $("sd-auto").addEventListener("click", function () { setAuto(!st.auto); });
    $("sd-reveal").addEventListener("click", reveal);
    $("sd-share").addEventListener("click", function () {
      var text = shareText(); G.track("game_share", NAME);
      G.copyText(text).then(function (ok) { $("sd-share-note").textContent = ok ? "Copied to the clipboard." : "Copy failed. Select the text below and copy it."; var b = $("sd-share-text"); b.value = text; b.hidden = ok; });
    });
    window.setInterval(tickClock, 1000); window.setInterval(tick, 30000);
    document.addEventListener("visibilitychange", function () { st.last = Date.now(); persist(); });
  }

  function start(data) {
    st.idx = G.dayIndex(new Date(), data.epoch);
    var raw = G.pick(data.days, st.idx);
    st.pz = { level: raw.l, week: raw.w, clues: raw.n };
    st.sol = G.decodeText(raw.s).split("").map(Number);
    st.given = raw.p.split("").map(function (ch) { return ch !== "."; });
    st.cells = raw.p.split("").map(function (ch) { return ch === "." ? 0 : Number(ch); });
    st.notes = new Array(81).fill(0);
    var saved = G.getGame(NAME).today;
    if (saved && saved.idx === st.idx) {
      var c = saved.cells || ""; for (var i = 0; i < 81; i++) if (!st.given[i] && c[i] && c[i] !== ".") st.cells[i] = Number(c[i]);
      st.notes = (saved.notes || []).concat(new Array(81).fill(0)).slice(0, 81);
      st.elapsed = saved.elapsed || 0; st.checks = saved.checks || 0; st.hints = saved.reveals || 0; st.done = !!saved.done;
      if (st.elapsed > 0 && !st.done) { st.ticking = true; st.last = Date.now(); }
    }
    $("sd-number").textContent = st.pz.level + ", week " + st.pz.week + " of 10";
    $("sd-level").textContent = st.pz.level;
    $("sd-week").textContent = String(st.pz.week);
    st.sel = st.cells.findIndex(function (v, i) { return !v && !st.given[i]; }); if (st.sel < 0) st.sel = 0;
    build(); wire();
    if (G.getGame(NAME).auto) { st.auto = true; $("sd-auto").setAttribute("aria-pressed", "true"); $("sd-auto").textContent = "Auto-check: on"; for (var j = 0; j < 81; j++) if (st.cells[j] && !st.given[j] && st.cells[j] !== st.sol[j]) st.wrong[j] = 1; }
    $("sd-loading").hidden = true; $("sd-game").hidden = false; $("sd-timer").textContent = fmt(st.elapsed);
    paint();
    if (st.done) finish(false);
  }

  fetch("/games/data/sudoku.json").then(function (r) { if (!r.ok) throw 0; return r.json(); }).then(function (d) { return G.ready.then(function () { start(d); }); }, function () {
    $("sd-loading").textContent = "Today's puzzle could not be loaded. Check your connection and reload the page.";
  });
})();
