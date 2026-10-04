/* Daily crossword. Grid, clues and solution come from /games/data/crossword.json for today's date. */
(function () {
  "use strict";
  var G = window.PLGames, NAME = "crossword", URL_ = "https://purplelink.llc/games/crossword/", EPOCH = "2026-10-04";
  if (!G) return;
  var $ = function (id) { return document.getElementById(id); };
  var KEYS = ["qwertyuiop", "asdfghjkl", "zxcvbnm-"];

  var st = {
    key: "", idx: 0, p: null, n: 0, sol: [], cells: [], black: [], entries: [], map: [], // map[r][c] = {a: entryIndex, d: entryIndex}
    r: 0, c: 0, dir: "across", auto: false, elapsed: 0, checks: 0, reveals: 0, done: false, wrong: {}, ticking: false, last: 0
  };

  function todayKey() {
    // ?date=YYYY-MM-DD works only on a local test server, never on the live site
    if (location.hostname === "127.0.0.1" && /^\d{4}-\d{2}-\d{2}$/.test((location.search.match(/date=([^&]+)/) || [])[1] || "")) return location.search.match(/date=([^&]+)/)[1];
    var d = new Date(), p = function (x) { return (x < 10 ? "0" : "") + x; };
    return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate());
  }
  function fmt(sec) { var m = Math.floor(sec / 60), s = sec % 60; return m + ":" + (s < 10 ? "0" : "") + s; }

  // ---- model ----
  function build(p) {
    st.p = p; st.n = p.size;
    var txt = G.decodeText(p.solution).split("/");
    st.sol = txt.map(function (row) { return row.toUpperCase().split(""); });
    st.black = st.sol.map(function (row) { return row.map(function (ch) { return ch === "#"; }); });
    st.cells = st.sol.map(function (row) { return row.map(function () { return ""; }); });
    st.map = st.sol.map(function (row) { return row.map(function () { return { a: -1, d: -1 }; }); });
    st.entries = p.entries.map(function (e, i) {
      var cells = [];
      for (var k = 0; k < e.len; k++) {
        var r = e.dir === "across" ? e.row : e.row + k, c = e.dir === "across" ? e.col + k : e.col;
        cells.push([r, c]);
        st.map[r][c][e.dir === "across" ? "a" : "d"] = i;
      }
      return { n: e.n, dir: e.dir, clue: e.clue, cells: cells };
    });
  }

  function entryAt(r, c, dir) {
    var m = st.map[r][c], i = dir === "across" ? m.a : m.d;
    return i >= 0 ? st.entries[i] : null;
  }
  function currentEntry() { return entryAt(st.r, st.c, st.dir); }

  // ---- drawing ----
  function drawGrid() {
    var g = $("cw-grid");
    g.textContent = "";
    g.setAttribute("data-size", String(st.n));
    var nums = {};
    st.entries.forEach(function (e) { nums[e.cells[0][0] + "," + e.cells[0][1]] = e.n; });
    for (var r = 0; r < st.n; r++) {
      var row = document.createElement("div");
      row.className = "cw-row";
      row.setAttribute("role", "row");
      for (var c = 0; c < st.n; c++) {
        var cell = document.createElement("div");
        cell.className = "cw-cell";
        cell.setAttribute("role", "gridcell");
        cell.setAttribute("data-r", r);
        cell.setAttribute("data-c", c);
        if (st.black[r][c]) {
          cell.setAttribute("data-black", "1");
          cell.setAttribute("aria-hidden", "true");
        } else {
          var key = r + "," + c;
          if (nums[key]) cell.setAttribute("data-n", nums[key]);
          var letter = document.createElement("span");
          letter.className = "cw-letter";
          cell.appendChild(letter);
        }
        row.appendChild(cell);
      }
      g.appendChild(row);
    }
  }

  function cellEl(r, c) { return $("cw-grid").children[r].children[c]; }

  function paint() {
    var ent = currentEntry(), inEntry = {};
    if (ent) ent.cells.forEach(function (x) { inEntry[x[0] + "," + x[1]] = 1; });
    for (var r = 0; r < st.n; r++) for (var c = 0; c < st.n; c++) {
      if (st.black[r][c]) continue;
      var el = cellEl(r, c), key = r + "," + c;
      el.firstChild.textContent = st.cells[r][c];
      el.toggleAttribute("data-active", r === st.r && c === st.c);
      el.toggleAttribute("data-entry", !!inEntry[key] && !(r === st.r && c === st.c));
      el.toggleAttribute("data-wrong", !!st.wrong[key]);
      el.setAttribute("aria-label", (el.getAttribute("data-n") ? el.getAttribute("data-n") + ", " : "") + (st.cells[r][c] ? st.cells[r][c] : "blank"));
      el.setAttribute("tabindex", r === st.r && c === st.c ? "0" : "-1");
    }
    if (window.innerWidth < 900) cellEl(st.r, st.c).scrollIntoView({ block: "nearest" });   // keep the active square clear of the sticky keyboard
    var cur = $("cw-current");
    cur.textContent = ent ? ent.n + " " + (ent.dir === "across" ? "Across" : "Down") + ": " + ent.clue : "";
    document.querySelectorAll(".cw-clue").forEach(function (li) {
      var i = Number(li.getAttribute("data-i"));
      li.toggleAttribute("data-current", st.entries[i] === ent);
      li.setAttribute("data-filled", st.entries[i].cells.every(function (x) { return st.cells[x[0]][x[1]]; }) ? "1" : "0");
    });
  }

  function drawClues() {
    ["across", "down"].forEach(function (dir) {
      var ol = $("cw-" + dir);
      ol.textContent = "";
      st.entries.forEach(function (e, i) {
        if (e.dir !== dir) return;
        var li = document.createElement("li");
        li.className = "cw-clue";
        li.setAttribute("data-i", i);
        var b = document.createElement("button");
        b.type = "button";
        b.className = "cw-clue-btn";
        b.textContent = e.n + ". " + e.clue;
        b.addEventListener("click", function () { goto(e); });
        li.appendChild(b);
        ol.appendChild(li);
      });
    });
  }

  function drawKeys() {
    var kb = $("cw-keys");
    kb.textContent = "";
    KEYS.forEach(function (letters) {
      var row = document.createElement("div");
      row.className = "wg-keyrow";
      letters.split("").forEach(function (ch) {
        var k = document.createElement("button");
        k.type = "button";
        k.className = "wg-key";
        if (ch === "-") { k.textContent = "Delete"; k.setAttribute("data-key", "back"); k.classList.add("wg-wide"); }
        else { k.textContent = ch; k.setAttribute("data-key", ch); }
        row.appendChild(k);
      });
      kb.appendChild(row);
    });
  }

  // ---- movement ----
  function goto(e) {
    st.dir = e.dir;
    var target = e.cells.find(function (x) { return !st.cells[x[0]][x[1]]; }) || e.cells[0];
    st.r = target[0]; st.c = target[1];
    paint(); focusCell();
  }
  function focusCell() { var el = cellEl(st.r, st.c); if (el && document.activeElement && document.activeElement.closest && !document.activeElement.closest("#cw-keys")) el.focus({ preventScroll: true }); }

  function setCell(r, c) {
    if (r < 0 || c < 0 || r >= st.n || c >= st.n || st.black[r][c]) return false;
    st.r = r; st.c = c;
    if (!entryAt(r, c, st.dir)) st.dir = st.dir === "across" ? "down" : "across";
    return true;
  }
  function step(dr, dc) {
    var r = st.r, c = st.c;
    do { r += dr; c += dc; } while (r >= 0 && c >= 0 && r < st.n && c < st.n && st.black[r][c]);
    if (r >= 0 && c >= 0 && r < st.n && c < st.n) { st.r = r; st.c = c; }
  }
  function nextInEntry(delta) {
    var e = currentEntry();
    if (!e) return;
    var i = e.cells.findIndex(function (x) { return x[0] === st.r && x[1] === st.c; }) + delta;
    if (i >= 0 && i < e.cells.length) { st.r = e.cells[i][0]; st.c = e.cells[i][1]; }
  }
  function cycleEntry(delta) {
    var cur = currentEntry(), list = st.entries, i = list.indexOf(cur);
    var nxt = list[(i + delta + list.length) % list.length];
    goto(nxt);
  }

  // ---- input ----
  function typeLetter(ch) {
    if (st.done || st.black[st.r][st.c]) return;
    st.cells[st.r][st.c] = ch.toUpperCase();
    delete st.wrong[st.r + "," + st.c];
    if (st.auto && st.cells[st.r][st.c] !== st.sol[st.r][st.c]) st.wrong[st.r + "," + st.c] = 1;
    nextInEntry(1);
    afterEdit();
  }
  function backspace() {
    if (st.done) return;
    if (st.cells[st.r][st.c]) { st.cells[st.r][st.c] = ""; delete st.wrong[st.r + "," + st.c]; }
    else { nextInEntry(-1); st.cells[st.r][st.c] = ""; delete st.wrong[st.r + "," + st.c]; }
    afterEdit();
  }
  function afterEdit() {
    startClock();
    persist();
    paint();
    checkDone();
  }

  function allFilled() { for (var r = 0; r < st.n; r++) for (var c = 0; c < st.n; c++) if (!st.black[r][c] && !st.cells[r][c]) return false; return true; }
  function allRight() { for (var r = 0; r < st.n; r++) for (var c = 0; c < st.n; c++) if (!st.black[r][c] && st.cells[r][c] !== st.sol[r][c]) return false; return true; }

  function checkDone() {
    if (st.done) return;
    if (!allFilled()) { $("cw-status").textContent = ""; return; }
    if (allRight()) { st.done = true; persist(); finish(true); }
    else $("cw-status").textContent = "Every square is filled, but some letters are not right yet. Use Check to see which.";
  }

  // ---- help ----
  // scope: "letter" (the selected square), "word" (the selected entry) or "puzzle". Wrong letters are shown in red until changed.
  function check(scope) {
    var cells = [];
    if (scope === "letter") cells = [[st.r, st.c]];
    else if (scope === "word") { var e = currentEntry(); cells = e ? e.cells : []; }
    else for (var r = 0; r < st.n; r++) for (var c = 0; c < st.n; c++) if (!st.black[r][c]) cells.push([r, c]);
    st.checks += 1;
    var bad = 0, filled = 0;
    cells.forEach(function (x) {
      var key = x[0] + "," + x[1], ch = st.cells[x[0]][x[1]];
      delete st.wrong[key];
      if (!ch) return;
      filled++;
      if (ch !== st.sol[x[0]][x[1]]) { st.wrong[key] = 1; bad++; }
    });
    var what = scope === "letter" ? "That letter" : scope === "word" ? "This word" : "The puzzle";
    $("cw-status").textContent = !filled ? what + " has nothing entered to check yet."
      : bad ? bad + (bad === 1 ? " letter is" : " letters are") + " wrong, shown in red."
      : (scope === "letter" ? "That letter is correct." : "Every letter entered so far is correct.");
    startClock(); persist(); paint();
  }

  // Auto-check marks a wrong letter the moment it is typed. Like Check, it counts as help.
  function setAuto(on) {
    st.auto = on;
    var s = G.getGame(NAME); s.auto = on; G.setGame(NAME, s);
    $("cw-auto").setAttribute("aria-pressed", on ? "true" : "false");
    $("cw-auto").textContent = on ? "Auto-check: on" : "Auto-check: off";
    if (on) { st.checks += 1; flagWrong(); $("cw-status").textContent = "Auto-check is on: wrong letters turn red as you type."; }
    else $("cw-status").textContent = "";
    persist(); paint();
  }
  function flagWrong() {
    for (var r = 0; r < st.n; r++) for (var c = 0; c < st.n; c++) {
      if (!st.black[r][c] && st.cells[r][c] && st.cells[r][c] !== st.sol[r][c]) st.wrong[r + "," + c] = 1;
    }
  }
  function revealLetter() {
    if (st.done || st.black[st.r][st.c]) return;
    st.reveals += 1; st.cells[st.r][st.c] = st.sol[st.r][st.c]; delete st.wrong[st.r + "," + st.c];
    afterEdit();
  }
  var revealArmed = false;
  function revealPuzzle() {
    if (st.done) return;
    var btn = $("cw-reveal-puzzle");
    if (!revealArmed) { revealArmed = true; btn.textContent = "Press again to reveal"; window.setTimeout(function () { revealArmed = false; btn.textContent = "Reveal puzzle"; }, 4000); return; }
    revealArmed = false; btn.textContent = "Reveal puzzle";
    st.reveals += 1; st.wrong = {};
    for (var r = 0; r < st.n; r++) for (var c = 0; c < st.n; c++) if (!st.black[r][c]) st.cells[r][c] = st.sol[r][c];
    afterEdit();
  }
  function revealWord() {
    var e = currentEntry();
    if (st.done || !e) return;
    st.reveals += 1;
    e.cells.forEach(function (x) { st.cells[x[0]][x[1]] = st.sol[x[0]][x[1]]; delete st.wrong[x[0] + "," + x[1]]; });
    afterEdit();
  }

  // ---- clock and saving ----
  function startClock() {
    if (st.ticking || st.done) return;
    st.ticking = true; st.last = Date.now();
    G.track("game_start", NAME);
  }
  function tickClock() {
    if (st.ticking && !st.done && document.visibilityState === "visible") {
      var now = Date.now(); st.elapsed += Math.round((now - st.last) / 1000); st.last = now;
    } else st.last = Date.now();
    $("cw-timer").textContent = fmt(st.elapsed);
    if (st.ticking && st.elapsed % 5 === 0) persist();
  }
  function persist() {
    var s = G.getGame(NAME);
    s.today = { idx: st.idx, key: st.key, cells: st.cells.map(function (r) { return r.map(function (ch) { return ch || "."; }).join(""); }), elapsed: st.elapsed, checks: st.checks, reveals: st.reveals, done: st.done };
    G.setGame(NAME, s);
  }

  function finish(fresh) {
    var saved = G.getGame(NAME), clean = !st.checks && !st.reveals;
    if (fresh) {
      saved.stats = G.recordResult(saved.stats, st.idx, true, 1);
      saved.best = saved.best || {};
      if (clean) saved.clean = (saved.clean || 0) + 1;
      var day = st.p.weekday;
      if (clean && (!saved.best[day] || st.elapsed < saved.best[day])) saved.best[day] = st.elapsed;
      G.setGame(NAME, saved);
      G.track("game_end", NAME + ":" + (clean ? "clean" : "assisted"));
    }
    var s = saved.stats || G.emptyStats();
    if (fresh) {
      var ctx = { game: NAME, idx: st.idx, won: true, clean: clean, seconds: st.elapsed, weekdayName: st.p.weekday };
      if (window.PLAch) window.PLAch.check(ctx);
      if (clean) G.submitScore(NAME, st.idx, Math.min(400, Math.floor(st.elapsed / 20))).then(function (res) {
        $("cw-pct").textContent = G.describePercentile(res);
        if (res && window.PLAch) window.PLAch.check({ game: NAME, idx: st.idx, won: true, clean: true, seconds: st.elapsed, weekdayName: st.p.weekday, pct: res.percentile, total: res.total });
      });
    }
    if (fresh && window.PLConfetti) window.PLConfetti.big();
    var sv = $("cw-saver"); if (sv) sv.textContent = G.saverNote(s, st.idx);
    $("cw-result").hidden = false;
    $("cw-result-head").textContent = "Solved in " + fmt(st.elapsed) + (clean ? "" : " with help");
    $("cw-played").textContent = s.played;
    $("cw-streak").textContent = s.streak;
    $("cw-max").textContent = s.max;
    var best = saved.best && saved.best[st.p.weekday];
    $("cw-best").textContent = best ? fmt(best) : "none";
    $("cw-best-label").textContent = "Best " + st.p.weekday;
    $("cw-status").textContent = "";
    $("cw-timer").textContent = fmt(st.elapsed);
    nextIn();
    if (fresh) $("cw-result").scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
  function nextIn() {
    var el = $("cw-next-in");
    if (!el || $("cw-result").hidden) return;
    var now = new Date(), nx = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
    var ms = nx - now, h = Math.floor(ms / 3600000), m = Math.floor((ms % 3600000) / 60000);
    el.textContent = h + " h " + (m < 10 ? "0" : "") + m + " min";
  }
  function shareText() {
    var clean = !st.checks && !st.reveals;
    return "Crossword " + (st.idx + 1) + " (" + st.p.weekday + ") solved in " + fmt(st.elapsed) + (clean ? ", no help" : ", with help") + "\n\n" + URL_;
  }

  // ---- events ----
  function wire() {
    var grid = $("cw-grid");
    grid.addEventListener("click", function (e) {
      var cell = e.target.closest(".cw-cell");
      if (!cell || cell.hasAttribute("data-black")) return;
      var r = Number(cell.getAttribute("data-r")), c = Number(cell.getAttribute("data-c"));
      if (r === st.r && c === st.c) { var other = st.dir === "across" ? "down" : "across"; if (entryAt(r, c, other)) st.dir = other; }
      else setCell(r, c);
      paint(); focusCell();
    });
    grid.addEventListener("keydown", function (e) {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      var k = e.key, handled = true;
      if (/^[a-zA-Z]$/.test(k)) typeLetter(k);
      else if (k === "Backspace" || k === "Delete") backspace();
      else if (k === "ArrowRight") { if (st.dir !== "across" && entryAt(st.r, st.c, "across")) st.dir = "across"; else step(0, 1); paint(); focusCell(); }
      else if (k === "ArrowLeft") { if (st.dir !== "across" && entryAt(st.r, st.c, "across")) st.dir = "across"; else step(0, -1); paint(); focusCell(); }
      else if (k === "ArrowDown") { if (st.dir !== "down" && entryAt(st.r, st.c, "down")) st.dir = "down"; else step(1, 0); paint(); focusCell(); }
      else if (k === "ArrowUp") { if (st.dir !== "down" && entryAt(st.r, st.c, "down")) st.dir = "down"; else step(-1, 0); paint(); focusCell(); }
      else if (k === "Tab") { cycleEntry(e.shiftKey ? -1 : 1); }
      else if (k === " " || k === "Enter") { var o = st.dir === "across" ? "down" : "across"; if (entryAt(st.r, st.c, o)) st.dir = o; paint(); }
      else handled = false;
      if (handled) e.preventDefault();
    });
    $("cw-keys").addEventListener("click", function (e) {
      var b = e.target.closest("[data-key]");
      if (!b) return;
      var v = b.getAttribute("data-key");
      if (v === "back") backspace(); else typeLetter(v);
    });
    // After a mouse click on a toolbar button, hand focus back to the grid so typing carries on.
    function bar(id, fn, keepFocus) {
      $(id).addEventListener("click", function (e) { fn(); if (!keepFocus && e.detail > 0) { var el = cellEl(st.r, st.c); if (el) el.focus({ preventScroll: true }); } });
    }
    bar("cw-check-letter", function () { check("letter"); });
    bar("cw-check-word", function () { check("word"); });
    bar("cw-check", function () { check("puzzle"); });
    bar("cw-auto", function () { setAuto(!st.auto); });
    bar("cw-reveal-puzzle", revealPuzzle, true);
    bar("cw-reveal-letter", revealLetter);
    bar("cw-reveal-word", revealWord);
    $("cw-share").addEventListener("click", function () {
      var text = shareText();
      G.track("game_share", NAME);
      G.copyText(text).then(function (ok) {
        $("cw-share-note").textContent = ok ? "Copied to the clipboard." : "Copy failed. Select the text below and copy it.";
        var box = $("cw-share-text"); box.value = text; box.hidden = ok;
      });
    });
    window.setInterval(tickClock, 1000);
    window.setInterval(nextIn, 30000);
    document.addEventListener("visibilitychange", function () { st.last = Date.now(); persist(); });
  }

  function start(data) {
    st.key = todayKey();
    st.idx = G.dayIndex(new Date(), EPOCH);
    var p = data.days[st.key];
    $("cw-loading").hidden = true;
    if (!p) {
      var later = Object.keys(data.days).filter(function (k) { return k > st.key; }).sort()[0];
      if (later) { var dt = new Date(later + "T12:00:00"); $("cw-missing").textContent = "No crossword today. The next one is " + dt.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" }) + "."; }
      $("cw-missing").hidden = false; return;
    }
    build(p);
    $("cw-number").textContent = p.weekday + ", puzzle " + (st.idx + 1);
    var saved = G.getGame(NAME).today;
    if (saved && saved.key === st.key) {
      saved.cells.forEach(function (row, r) { row.split("").forEach(function (ch, c) { if (!st.black[r][c]) st.cells[r][c] = ch === "." ? "" : ch; }); });
      st.elapsed = saved.elapsed || 0; st.checks = saved.checks || 0; st.reveals = saved.reveals || 0; st.done = !!saved.done;
      if (st.elapsed > 0 && !st.done) st.ticking = true, st.last = Date.now();
    }
    // the cells string uses "." for empty squares so it keeps its width
    drawGrid(); drawClues(); drawKeys(); wire();
    if (G.getGame(NAME).auto) { st.auto = true; flagWrong(); $("cw-auto").setAttribute("aria-pressed", "true"); $("cw-auto").textContent = "Auto-check: on"; }
    var first = st.entries[0];
    st.dir = first.dir; st.r = first.cells[0][0]; st.c = first.cells[0][1];
    $("cw-game").hidden = false;
    $("cw-timer").textContent = fmt(st.elapsed);
    paint();
    if (st.done) finish(false);
  }

  fetch("/games/data/crossword.json").then(function (r) { if (!r.ok) throw 0; return r.json(); }).then(function (d) { return G.ready.then(function () { start(d); }); }, function () {
    $("cw-loading").textContent = "Today's crossword could not be loaded. Check your connection and reload the page.";
  });
})();
