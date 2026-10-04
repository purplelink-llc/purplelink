/* Sudoku. The daily page: puzzles get harder every week for ten weeks, then a new season starts.
   The Sudoku Unlimited page (it has #sd-rated) uses the same board with rated puzzles from a pool, one after another. */
(function () {
  "use strict";
  var G = window.PLGames, R = window.PLRating, RATED = !!document.getElementById("sd-rated");
  var NAME = RATED ? "sudoku-unlimited" : "sudoku", URL_ = "https://purplelink.llc/games/sudoku/";
  if (!G || (RATED && !R)) return;
  var LEVELS = ["", "Beginner", "Easy", "Medium", "Hard", "Expert"];
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
    if (RATED) {
      if (!st.done && st.rid) R.current("sudoku", { id: st.rid, level: st.levelN, n: st.poolN, seed: st.seed, cells: st.cells.join("").replace(/0/g, "."), notes: st.notes.map(function (n) { return n || 0; }), elapsed: st.elapsed, checks: st.checks, hints: st.hints, t0: st.t0 });
      return;
    }
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
    persist(); paint(); fx(i, d); checkDone();
  }

  // Sound and motion for a digit: a clack, a shake for a clash, and a ripple when a row, column or box is complete.
  function fx(i, d) {
    var FX = window.PLFX; if (!FX) return;
    if (st.noteMode) { FX.play("key"); return; }
    if (!d) { FX.play("back"); return; }
    var cells = $("sd-grid").children;
    FX.kick(cells[i], "fx-pop", 200);
    if (conflicts()[i] || st.wrong[i]) { FX.play("bad"); FX.vibrate(25); FX.kick(cells[i], "fx-shake", 420); return; }
    FX.play("place");
    var r = Math.floor(i / 9), c = i % 9, b0 = Math.floor(r / 3) * 27 + Math.floor(c / 3) * 3, row = [], col = [], box = [], k;
    for (k = 0; k < 9; k++) { row.push(r * 9 + k); col.push(k * 9 + c); box.push(b0 + Math.floor(k / 3) * 9 + (k % 3)); }
    var any = false;
    [row, col, box].forEach(function (u) {
      var seen = {};
      if (u.every(function (x) { seen[st.cells[x]] = 1; return st.cells[x]; }) && Object.keys(seen).length === 9) {
        any = true;
        FX.wave(u.map(function (x) { return cells[x]; }), "fx-flash", 45, 600);
      }
    });
    if (any) window.setTimeout(function () { FX.play("unit"); }, 140);
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
    if (window.PLFX && filled) { window.PLFX.play(bad ? "bad" : "good"); if (bad) window.PLFX.vibrate(25); }
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
    if (RATED) return finishRated();
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
  function shareText() {
    var clean = !st.checks && !st.hints;
    if (RATED) { var d = st.delta || 0; return "Sudoku Unlimited: solved a " + st.pz.level + " puzzle in " + fmt(st.elapsed) + (clean ? ", no help" : ", with help") + ". My rating is " + (st.rec ? st.rec.r : "") + " (" + (d >= 0 ? "+" : "\u2212") + Math.abs(d) + ").\n\nhttps://purplelink.llc/games/sudoku-unlimited/"; }
    return "Sudoku " + (st.idx + 1) + " (" + st.pz.level + ") solved in " + fmt(st.elapsed) + (clean ? ", no help" : ", with help") + "\n\n" + URL_; }

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
    if ($("sd-skip")) $("sd-skip").addEventListener("click", function () {
      var b = $("sd-skip");
      if (!b.hasAttribute("data-armed")) { b.setAttribute("data-armed", "1"); b.textContent = "Press again: counts as a miss"; window.setTimeout(function () { b.removeAttribute("data-armed"); b.textContent = "New puzzle"; }, 4000); return; }
      skipRated();
    });
    window.PLShareText = shareText;   // the share row (share.js) reads this when the player taps a button
    window.setInterval(tickClock, 1000); window.setInterval(tick, 30000);
    document.addEventListener("visibilitychange", function () { st.last = Date.now(); persist(); });
  }

  // Common to both pages: set the board up from a puzzle string, its solution and an optional saved state.
  function begin(p, sol, meta, saved) {
    st.pz = { level: meta.level, week: meta.week };
    st.sol = sol.split("").map(Number);
    st.given = p.split("").map(function (ch) { return ch !== "."; });
    st.cells = p.split("").map(function (ch) { return ch === "." ? 0 : Number(ch); });
    st.notes = new Array(81).fill(0);
    if (saved) {
      var c = saved.cells || ""; for (var i = 0; i < 81; i++) if (!st.given[i] && c[i] && c[i] !== ".") st.cells[i] = Number(c[i]);
      st.notes = (saved.notes || []).concat(new Array(81).fill(0)).slice(0, 81);
      st.elapsed = saved.elapsed || 0; st.checks = saved.checks || 0; st.hints = saved.reveals !== undefined ? saved.reveals : (saved.hints || 0); st.done = !!saved.done;
      if (st.elapsed > 0 && !st.done) { st.ticking = true; st.last = Date.now(); }
    }
    $("sd-number").textContent = meta.label;
    $("sd-level").textContent = st.pz.level;
    if ($("sd-week")) $("sd-week").textContent = String(st.pz.week);
    st.sel = st.cells.findIndex(function (v, i) { return !v && !st.given[i]; }); if (st.sel < 0) st.sel = 0;
    build(); wire();
    if (G.getGame(NAME).auto) { st.auto = true; $("sd-auto").setAttribute("aria-pressed", "true"); $("sd-auto").textContent = "Auto-check: on"; for (var j = 0; j < 81; j++) if (st.cells[j] && !st.given[j] && st.cells[j] !== st.sol[j]) st.wrong[j] = 1; }
    $("sd-loading").hidden = true; $("sd-game").hidden = false; $("sd-timer").textContent = fmt(st.elapsed);
    paint();
    if (st.done && !RATED) finish(false);
  }

  function start(data) {
    st.idx = G.dayIndex(new Date(), data.epoch);
    var raw = G.pick(data.days, st.idx), saved = G.getGame(NAME).today;
    begin(raw.p, G.decodeText(raw.s), { level: raw.l, week: raw.w, label: raw.l + ", week " + raw.w + " of 10" }, saved && saved.idx === st.idx ? saved : null);
  }

  // ---- Sudoku Unlimited ----
  // A pool puzzle is relabelled and reshuffled (digits, rows and columns within their bands, the bands themselves, and a
  // transpose), which keeps it valid and as hard as it was but makes it a different-looking puzzle each time.
  function rng(seed) { var a = seed >>> 0; return function () { a = (a + 0x6D2B79F5) >>> 0; var t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
  function shuffle(list, r) { for (var i = list.length - 1; i > 0; i--) { var j = Math.floor(r() * (i + 1)), t = list[i]; list[i] = list[j]; list[j] = t; } return list; }
  function axis(r) { var bands = shuffle([0, 1, 2], r), out = []; bands.forEach(function (b) { shuffle([0, 1, 2], r).forEach(function (k) { out.push(b * 3 + k); }); }); return out; }
  function transform(p, s, seed) {
    var r = rng(seed), rows = axis(r), cols = axis(r), perm = shuffle([1, 2, 3, 4, 5, 6, 7, 8, 9], r), flip = r() < 0.5, np = "", ns = "";
    for (var i = 0; i < 81; i++) {
      var tr = Math.floor(i / 9), tc = i % 9, sr = rows[tr], sc = cols[tc], from = flip ? sc * 9 + sr : sr * 9 + sc;
      np += p[from] === "." ? "." : String(perm[Number(p[from]) - 1]);
      ns += String(perm[Number(s[from]) - 1]);
    }
    return { p: np, s: ns };
  }

  function loadLevel(n) { return fetch("/games/data/sudoku-pool/level-" + n + ".json").then(function (r) { if (!r.ok) throw 0; return r.json(); }); }

  function levelFor(rating) {
    var target = rating + (Math.random() - 0.5) * 300, best = 1;
    for (var l = 1; l <= 5; l++) if (Math.abs(R.LEVEL_RATING[l] - target) < Math.abs(R.LEVEL_RATING[best] - target)) best = l;
    return best;
  }

  function beginRated(level, n, entry, seed, saved) {
    var t = transform(entry[0], G.decodeText(entry[1]), seed);
    st.rid = level + "-" + n; st.levelN = level; st.poolN = n; st.seed = seed;
    st.t0 = saved ? saved.t0 : Date.now();
    var rating = R.LEVEL_RATING[level];
    begin(t.p, t.s, { level: LEVELS[level], week: "", label: LEVELS[level] + ", rated " + rating }, saved);
    persist();
  }

  function startRated() {
    R.load("sudoku").then(function (info) {
      st.rec = info.rec; st.isPublic = !!info.public;
      $("sr-rating").textContent = String(info.rec.r); $("sr-tier-top").textContent = R.tierFor(info.rec.r); $("sr-streak-top").textContent = String(info.rec.streak);
      var saved = R.current("sudoku");
      if (saved && saved.id) {
        return loadLevel(saved.level).then(function (d) {
          var entry = d.p[saved.n];
          if (entry) return beginRated(saved.level, saved.n, entry, saved.seed, saved);
          R.current("sudoku", null); return freshRated(info.rec.r);
        }, function () { R.current("sudoku", null); return freshRated(info.rec.r); });
      }
      return freshRated(info.rec.r);
    });
  }
  function freshRated(rating) {
    var level = levelFor(rating), seen = R.recentIds("sudoku");
    return loadLevel(level).then(function (d) {
      if (!d.p.length && level > 1) return freshRated(R.LEVEL_RATING[level - 1]);      // a level with no puzzles yet: step down
      var open = []; d.p.forEach(function (e, i) { if (seen.indexOf(level + "-" + i) < 0) open.push(i); });
      if (!open.length) open = d.p.map(function (_, i) { return i; });
      var n = open[Math.floor(Math.random() * open.length)];
      beginRated(level, n, d.p[n], Math.floor(Math.random() * 4294967295), null);
    }).catch(function () { $("sd-loading").textContent = "The puzzles could not be loaded. Check your connection and reload the page."; });
  }

  function reportRated(result) {
    var ms = result === "skip" ? 0 : Math.max(1000, st.elapsed * 1000);
    return R.report("sudoku", { id: st.rid, puzzleRating: R.LEVEL_RATING[st.levelN], level: st.levelN, result: result, ms: ms });
  }
  function skipRated() {
    if (st.done) return;
    st.done = true;
    reportRated("skip").then(function () { R.current("sudoku", null); R.recentIds("sudoku", st.rid); window.location.assign(window.location.pathname); });
  }
  function finishRated() {
    var clean = !st.checks && !st.hints, result = clean ? "clean" : "help";
    reportRated(result).then(function (out) {
      var rec = out.rec, delta = out.delta, up = delta >= 0;
      st.rec = rec; st.delta = delta;
      R.current("sudoku", null); R.recentIds("sudoku", st.rid);
      $("sr-head").textContent = "Solved in " + fmt(st.elapsed) + (clean ? "" : " with help");
      $("sr-delta").textContent = (up ? "+" : "\u2212") + Math.abs(delta); $("sr-delta").setAttribute("data-up", up ? "1" : "0");
      $("sr-new").textContent = String(rec.r); $("sr-tier").textContent = R.tierFor(rec.r);
      $("sr-streak").textContent = String(rec.streak); $("sr-streak-top").textContent = String(rec.streak); $("sr-peak").textContent = String(rec.peak);
      $("sr-rating").textContent = String(rec.r); $("sr-tier-top").textContent = R.tierFor(rec.r);
      $("sr-note").textContent = clean ? "" : "Checks and reveals count as help, so this solve moved your rating less.";
      $("sd-result").hidden = false; $("sd-status").textContent = "";
      var FX = window.PLFX;
      if (FX) { FX.play(clean ? "big" : "win"); FX.vibrate([20, 40, 20]); FX.kick($("sr-delta"), "fx-pop", 300); }
      if (window.PLConfetti && clean) window.PLConfetti.small();
      joinPrompt(out);
      if (window.PLAch) window.PLAch.check({ game: NAME, rated: true, idx: G.dayIndex(new Date(), "2026-10-04"), won: true, clean: clean, rating: rec.r, level: LEVELS[st.levelN], streak: rec.streak, n: rec.n, seconds: st.elapsed });
      G.track("game_end", NAME + ":" + (clean ? "clean" : "assisted"));
      $("sr-next").focus({ preventScroll: true });
      $("sd-result").scrollIntoView({ block: "nearest", behavior: "smooth" });
    });
  }
  function joinPrompt(out) {
    var box = $("sr-join"), s = G.session && G.session.get();
    box.textContent = "";
    function p(text) { var e = document.createElement("p"); e.textContent = text; box.appendChild(e); }
    if (!s) {
      p("Your rating is saved on this device. Sign in with an email link to keep it across devices and appear on the leaderboard.");
      var a = document.createElement("a"); a.className = "gbtn gbtn--ghost"; a.href = "/games/account/"; a.textContent = "Sign in"; box.appendChild(a);
    } else if (!out.public && !st.isPublic) {
      p(s.name ? "You are not on the leaderboard. Show " + s.name + " there?" : "Pick a display name on your account page to appear on the leaderboard.");
      if (s.name) { var b = document.createElement("button"); b.type = "button"; b.className = "gbtn gbtn--ghost"; b.textContent = "Show me on the leaderboard"; box.appendChild(b);
        b.addEventListener("click", function () { R.setPublic(true).then(function (res) { box.textContent = ""; p(res.status === 200 ? "You are on the leaderboard." : "That name cannot be shown. Choose another on your account page."); if (res.status === 200) st.isPublic = true; }); }); }
    } else p("You are on the leaderboard.");
  }

  if (RATED) {
    G.ready.then(startRated);
  } else {
    fetch("/games/data/sudoku.json").then(function (r) { if (!r.ok) throw 0; return r.json(); }).then(function (d) { return G.ready.then(function () { start(d); }); }, function () {
    $("sd-loading").textContent = "Today's puzzle could not be loaded. Check your connection and reload the page.";
  });
  }
})();
