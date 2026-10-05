/* One engine for Linkle (1 board, 6 guesses) and Quadlink (4 boards, 9 guesses).
   A page sets window.PLWordGame = { name, boards, maxGuesses, title, url, dataFile } before loading this. */
(function () {
  "use strict";
  var G = window.PLGames, C = window.PLWordGame;
  if (!G || !C) return;

  var $ = function (id) { return document.getElementById(id); };
  var ROWS = ["qwertyuiop", "asdfghjkl", "+zxcvbnm-"];
  var LEN = 5;
  var NAMES = { c: "correct", p: "in the word, wrong place", a: "not in the word" };

  // Linkle's weekday twists, keyed by getDay() (Sunday = 0). `max` changes the guess limit,
  // `hard` turns on hard mode, `hint(answer)` is the line shown above the board.
  var VOWELS = /[aeiou]/g;
  var TWISTS = {
    0: { name: "Hard mode", hard: true, text: "Every hint you have found must be used in your next guess." },
    1: { name: "Standard", text: "Standard rules today." },
    2: { name: "Head start", hint: function (a) { return "The word starts with " + a[0].toUpperCase() + "."; } },
    3: { name: "Extra guess", max: 7, text: "You have seven guesses today." },
    4: { name: "Vowel count", hint: function (a) { var n = (a.match(VOWELS) || []).length; return "The word has " + n + (n === 1 ? " vowel" : " vowels") + " (A, E, I, O, U)."; } },
    5: { name: "No repeats", text: "No letter appears twice in today's word." },
    6: { name: "Double up", text: "At least one letter appears twice in today's word." }
  };
  // Quadlink's weekday twists. `hintAll(answers)` is the line shown above the boards; the hard rule uses the first board.
  var QUAD = {
    0: { name: "Hard mode", hard: true, text: "Hints you find on the first board must be used in your next guess." },
    1: { name: "Standard", text: "Standard rules today." },
    2: { name: "Head start", hintAll: function (a) { return "First letters: " + a.map(function (w) { return w[0].toUpperCase(); }).join(", ") + "."; } },
    3: { name: "Extra guess", max: 10, text: "You have ten guesses today." },
    4: { name: "Vowel counts", hintAll: function (a) { return "Vowels in each word: " + a.map(function (w) { return (w.match(VOWELS) || []).length; }).join(", ") + "."; } },
    5: { name: "Last letters", hintAll: function (a) { return "Last letters: " + a.map(function (w) { return w[4].toUpperCase(); }).join(", ") + "."; } },
    6: { name: "Tight squeeze", max: 8, text: "You have eight guesses today." }
  };
  function TW() { return C.twists === "quad" ? QUAD : TWISTS; }
  var state = { idx: 0, twist: null, answers: [], guesses: [], current: "", done: false, won: false, valid: null, busy: false };

  function boardCount() { return C.boards; }
  function solvedAt(b) {
    for (var i = 0; i < state.guesses.length; i++) if (state.guesses[i] === state.answers[b]) return i;
    return -1;
  }
  function allSolved() {
    for (var b = 0; b < boardCount(); b++) if (solvedAt(b) < 0) return false;
    return true;
  }

  // `msg` goes to screen readers. `shown` (optional) is also shown on screen for a few seconds.
  var msgTimer = 0;
  function say(msg, shown) {
    var el = $("wg-status");
    el.textContent = "";
    window.setTimeout(function () { el.textContent = msg; }, 20);
    var vis = $("wg-msg");
    if (!vis) return;
    window.clearTimeout(msgTimer);
    vis.textContent = shown || "";
    if (shown) msgTimer = window.setTimeout(function () { vis.textContent = ""; }, 2500);
  }

  // ---- building the page ----
  function buildBoards() {
    var wrap = $("wg-boards");
    wrap.textContent = "";
    for (var b = 0; b < boardCount(); b++) {
      var board = document.createElement("div");
      board.className = "wg-board";
      board.setAttribute("role", "group");
      board.setAttribute("aria-label", boardCount() > 1 ? "Board " + (b + 1) : "Guesses");
      for (var r = 0; r < C.maxGuesses; r++) {
        var row = document.createElement("div");
        row.className = "wg-row";
        for (var t = 0; t < LEN; t++) {
          var tile = document.createElement("div");
          tile.className = "wg-tile";
          row.appendChild(tile);
        }
        board.appendChild(row);
      }
      wrap.appendChild(board);
    }
    wrap.setAttribute("data-boards", String(boardCount()));
  }

  function buildKeyboard() {
    var kb = $("wg-keys");
    kb.textContent = "";
    ROWS.forEach(function (letters) {
      var row = document.createElement("div");
      row.className = "wg-keyrow";
      letters.split("").forEach(function (ch) {
        var k = document.createElement("button");
        k.type = "button";
        k.className = "wg-key";
        if (ch === "+") { k.textContent = "Enter"; k.setAttribute("data-key", "enter"); k.classList.add("wg-wide"); }
        else if (ch === "-") { k.textContent = "Delete"; k.setAttribute("data-key", "back"); k.classList.add("wg-wide"); }
        else {
          k.setAttribute("data-key", ch);
          k.textContent = ch;
          if (boardCount() > 1) {
            var marks = document.createElement("span");
            marks.className = "wg-marks";
            for (var b = 0; b < boardCount(); b++) marks.appendChild(document.createElement("i"));
            k.appendChild(marks);
          }
        }
        row.appendChild(k);
      });
      kb.appendChild(row);
    });
  }

  // ---- drawing state ----
  function tilesOf(b, r) {
    return $("wg-boards").children[b].children[r].children;
  }

  function paint() {
    var i, b, t, tiles, sc;
    var keyState = [];
    for (b = 0; b < boardCount(); b++) keyState.push({});
    for (b = 0; b < boardCount(); b++) {
      var stopAt = solvedAt(b);
      for (i = 0; i < C.maxGuesses; i++) {
        tiles = tilesOf(b, i);
        var g = state.guesses[i];
        var live = i === state.guesses.length && !state.done && (stopAt < 0);
        for (t = 0; t < LEN; t++) {
          var tile = tiles[t];
          tile.removeAttribute("data-s");
          tile.removeAttribute("aria-label");
          tile.classList.remove("wg-filled");
          if (g !== undefined && (stopAt < 0 || i <= stopAt)) {
            sc = G.score(g, state.answers[b]);
            tile.textContent = g[t];
            tile.setAttribute("data-s", sc[t]);
            tile.setAttribute("aria-label", g[t] + ", " + NAMES[sc[t]]);
            if (t === 0) G.mergeKeys(keyState[b], g, sc);
          } else if (live && state.current[t]) {
            tile.textContent = state.current[t];
            tile.classList.add("wg-filled");
          } else {
            tile.textContent = "";
          }
        }
      }
      $("wg-boards").children[b].classList.toggle("wg-solved", stopAt >= 0);
    }
    var keys = $("wg-keys").querySelectorAll(".wg-key[data-key]");
    Array.prototype.forEach.call(keys, function (k) {
      var ch = k.getAttribute("data-key");
      if (ch.length !== 1) return;
      if (boardCount() === 1) {
        if (keyState[0][ch]) k.setAttribute("data-s", keyState[0][ch]); else k.removeAttribute("data-s");
      } else {
        var marks = k.querySelectorAll(".wg-marks i");
        for (var j = 0; j < marks.length; j++) {
          if (keyState[j][ch]) marks[j].setAttribute("data-s", keyState[j][ch]); else marks[j].removeAttribute("data-s");
        }
        var label = ch;
        for (j = 0; j < boardCount(); j++) if (keyState[j][ch]) label += ", board " + (j + 1) + " " + NAMES[keyState[j][ch]];
        k.setAttribute("aria-label", label);
      }
    });
  }

  // ---- input ----
  function type(ch) {
    if (state.done || state.busy || state.current.length >= LEN) return;
    state.current += ch;
    paint();
    if (window.PLFX) {
      window.PLFX.play("key");
      for (var b = 0; b < boardCount(); b++) window.PLFX.kick(tilesOf(b, state.guesses.length)[state.current.length - 1], "fx-pop", 160);
    }
  }
  function back() {
    if (state.done || state.busy) return;
    state.current = state.current.slice(0, -1);
    paint();
    if (window.PLFX) window.PLFX.play("back");
  }
  function shake() {
    var wrap = $("wg-boards");
    wrap.classList.remove("wg-shake");
    void wrap.offsetWidth;
    wrap.classList.add("wg-shake");
    if (window.PLFX) { window.PLFX.play("bad"); window.PLFX.vibrate(30); }
  }
  // Turn the newest row over tile by tile, showing each colour as its tile passes edge-on. Returns how long that takes.
  function flipRow(row) {
    var FX = window.PLFX;
    if (!FX || FX.reduced()) return 0;
    for (var b = 0; b < boardCount(); b++) {
      var tiles = tilesOf(b, row);
      for (var t = 0; t < tiles.length; t++) (function (tile, t) {
        var s = tile.getAttribute("data-s");
        if (!s) return;
        tile.removeAttribute("data-s");
        tile.classList.add("wg-filled");
        tile.style.animationDelay = (t * 110) + "ms";
        FX.kick(tile, "fx-flip", 900);
        window.setTimeout(function () { tile.setAttribute("data-s", s); tile.classList.remove("wg-filled"); }, t * 110 + 250);
        if (b === 0) window.setTimeout(function () { FX.play("flip", t); }, t * 110 + 220);
      })(tiles[t], t);
    }
    return LEN * 110 + 450;
  }
  function submit() {
    if (state.done || state.busy) return;
    var g = state.current;
    if (g.length < LEN) { say("Not enough letters.", "Not enough letters."); shake(); return; }
    if (!state.valid[g]) { say(g.toUpperCase() + " is not in the word list.", g.toUpperCase() + " is not in the word list."); shake(); return; }
    if (state.twist && state.twist.hard) {
      var hist = state.guesses.map(function (x) { return { guess: x, score: G.score(x, state.answers[0]) }; });
      var err = G.hardModeError(g, hist);
      if (err) { say(err, err); shake(); return; }
    }
    if (state.guesses.length === 0) G.track("game_start", C.name);
    state.guesses.push(g);
    state.current = "";
    var over = allSolved() || state.guesses.length >= C.maxGuesses;
    if (over) { state.done = true; state.won = allSolved(); }
    persist();
    paint();
    announce(g);
    var wait = flipRow(state.guesses.length - 1);
    if (wait) {
      state.busy = true;
      window.setTimeout(function () {
        state.busy = false;
        if (state.won && window.PLFX) for (var b = 0; b < boardCount(); b++) if (solvedAt(b) === state.guesses.length - 1) window.PLFX.wave(tilesOf(b, state.guesses.length - 1), "fx-hop", 70, 700);
        if (over) done();
      }, wait);
    } else if (over) done();
  }

  // ---- practice rounds: any number of extra words, never counted toward streaks or stats ----
  function done() { if (state.practice) finishPractice(); else finish(true); }
  function startPractice() {
    var ds = state.dataset, n;
    state.practice = true; state.twist = TW()[1]; C.maxGuesses = C.baseMax;
    if (C.boards === 1) { n = Math.floor(Math.random() * ds.answers.length); state.answers = [G.decode(ds.answers[n])]; }
    else { n = Math.floor(Math.random() * ds.days.length); state.answers = ds.days[n].map(G.decode); }
    state.guesses = []; state.current = ""; state.done = false; state.won = false; state.busy = false;
    $("wg-result").hidden = true; $("wg-practice").hidden = true;
    var rw = document.getElementById("reward"); if (rw) rw.hidden = true;
    var tw = $("wg-twist");
    if (tw) { tw.hidden = false; $("wg-twist-name").textContent = "Practice"; $("wg-twist-text").textContent = "This round does not count toward your streak."; }
    buildBoards(); buildKeyboard(); paint();
    say("New practice round. Start typing.");
    $("wg-boards").scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
  function finishPractice() {
    $("wg-practice-text").textContent = state.won ? "Solved in " + state.guesses.length + " of " + C.maxGuesses + "." : "The word" + (boardCount() > 1 ? "s were " : " was ") + state.answers.join(", ").toUpperCase() + ".";
    $("wg-practice").hidden = false;
    if (window.PLFX) window.PLFX.play(state.won ? "win" : "lose");
    if (state.won && window.PLConfetti) window.PLConfetti.small();
    $("wg-practice-again").focus({ preventScroll: true });
    $("wg-practice").scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  function announce(g) {
    var parts = [];
    for (var b = 0; b < boardCount(); b++) {
      var sc = G.score(g, state.answers[b]);
      var bits = sc.map(function (s, i) { return g[i] + " " + NAMES[s]; }).join(", ");
      parts.push((boardCount() > 1 ? "Board " + (b + 1) + ": " : "") + bits);
    }
    say(parts.join(". "));
  }

  // ---- persistence and results ----
  function persist() {
    if (state.practice) return;
    var saved = G.getGame(C.name);
    saved.today = { idx: state.idx, guesses: state.guesses, done: state.done, won: state.won };
    G.setGame(C.name, saved);
  }

  function shareText() {
    var lines = [C.title + " " + (state.idx + 1) + " " + (state.won ? state.guesses.length : "X") + "/" + C.maxGuesses + (state.twist && state.twist.name !== "Standard" ? " (" + state.twist.name + ")" : "")];
    for (var b = 0; b < boardCount(); b++) {
      var stop = solvedAt(b);
      var rows = [];
      for (var i = 0; i < state.guesses.length && (stop < 0 || i <= stop); i++) {
        rows.push(G.shareRow(G.score(state.guesses[i], state.answers[b])));
      }
      lines.push("");
      if (boardCount() > 1) lines.push("Board " + (b + 1));
      lines.push(rows.join("\n"));
    }
    lines.push("");
    lines.push(C.url);
    return lines.join("\n");
  }

  function finish(fresh) {
    var saved = G.getGame(C.name);
    if (fresh) {
      saved.stats = G.recordResult(saved.stats, state.idx, state.won, state.guesses.length);
      G.setGame(C.name, saved);
      G.track("game_end", C.name + ":" + (state.won ? "win" : "loss"));
    }
    var s = saved.stats || G.emptyStats();
    var box = $("wg-result");
    box.hidden = false;
    $("wg-result-head").textContent = state.won
      ? "Solved in " + state.guesses.length + " of " + C.maxGuesses
      : "Out of guesses";
    var reveal = $("wg-reveal");
    reveal.textContent = state.won ? "" : "The word" + (boardCount() > 1 ? "s were " : " was ") + state.answers.join(", ").toUpperCase() + ".";
    $("wg-played").textContent = s.played;
    $("wg-winpct").textContent = s.played ? Math.round((100 * s.won) / s.played) + "%" : "0%";
    $("wg-streak").textContent = s.streak;
    $("wg-max").textContent = s.max;
    var dist = $("wg-dist");
    dist.textContent = "";
    var top = 1;
    for (var k in s.dist) if (s.dist[k] > top) top = s.dist[k];
    for (var n = 1; n <= C.maxGuesses; n++) {
      var row = document.createElement("div");
      row.className = "wg-distrow";
      var lab = document.createElement("span");
      lab.textContent = n;
      var m = document.createElement("meter");
      m.min = 0; m.max = top; m.value = s.dist[n] || 0;
      m.setAttribute("aria-label", n + " guesses: " + (s.dist[n] || 0) + " games");
      var num = document.createElement("span");
      num.textContent = s.dist[n] || 0;
      row.appendChild(lab); row.appendChild(m); row.appendChild(num);
      dist.appendChild(row);
    }
    if (C.twists) renderMeta(s);
    if (fresh) reward(saved);
    var sv = $("wg-saver"); if (sv) sv.textContent = G.saverNote(s, state.idx);
    tick();
    if (fresh) box.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  // Unlock achievements, then ask for the percentile and show it.
  function reward(saved) {
    if (state.won && window.PLConfetti) window.PLConfetti[state.guesses.length <= 2 ? "big" : "small"]();
    var ctx = { game: C.name, idx: state.idx, won: state.won, tries: state.guesses.length, weekday: new Date().getDay() };
    if (window.PLAch) window.PLAch.check(ctx);
    G.submitScore(C.name, state.idx, state.won ? state.guesses.length : 99).then(function (res) {
      var el = $("wg-pct");
      if (el) el.textContent = G.describePercentile(res);
      if (res && window.PLAch) window.PLAch.check({ game: ctx.game, idx: ctx.idx, won: ctx.won, tries: ctx.tries, weekday: ctx.weekday, pct: res.percentile, total: res.total });
    });
  }

  var DAYS_ABBR = ["M", "T", "W", "T", "F", "S", "S"];
  // Rank, the Monday-to-Sunday tracker and a teaser for tomorrow's twist: the reasons to come back.
  function renderMeta(s) {
    if (!$("wg-rank")) { $("wg-tomorrow").textContent = "Tomorrow's twist: " + TW()[(new Date().getDay() + 1) % 7].name + "."; return; }
    var wins = s.wins || [];
    var rk = G.rankFor(wins.length);
    $("wg-rank").textContent = "Rank: " + rk.name + (rk.next ? ". " + rk.toNext + (rk.toNext === 1 ? " win" : " wins") + " to " + rk.next + "." : ". You have reached the top rank.");
    var epochDow = (function () { var p = C.epoch.split("-").map(Number); return new Date(p[0], p[1] - 1, p[2]).getDay(); })();
    var wp = G.weekProgress(wins, state.idx, epochDow);
    var row = $("wg-week");
    row.textContent = "";
    for (var i = 0; i < 7; i++) {
      var cell = document.createElement("span");
      cell.className = "wg-weekday";
      cell.textContent = DAYS_ABBR[i];
      if (wp.days[i]) cell.setAttribute("data-won", "1");
      if (i === wp.today) cell.setAttribute("data-today", "1");
      cell.setAttribute("aria-label", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][i] + (wp.days[i] ? ", solved" : ""));
      row.appendChild(cell);
    }
    $("wg-week-note").textContent = wp.count + " of 7 this week." + (wp.fullWeeks ? " Full weeks so far: " + wp.fullWeeks + "." : "");
    var tomorrow = TW()[(new Date().getDay() + 1) % 7];
    $("wg-tomorrow").textContent = "Tomorrow's twist: " + tomorrow.name + ".";
  }

  function tick() {
    var el = $("wg-next");
    if (!el || $("wg-result").hidden) return;
    var now = new Date(), next = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
    var ms = next - now, h = Math.floor(ms / 3600000), m = Math.floor((ms % 3600000) / 60000);
    el.textContent = h + " h " + (m < 10 ? "0" : "") + m + " min";
    if (G.dayIndex(now, C.epoch) !== state.idx) el.textContent = "ready now. Reload the page.";
  }

  // ---- startup ----
  function wire() {
    document.addEventListener("keydown", function (e) {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      var tag = (e.target && e.target.tagName) || "";
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (e.key === "Enter") {
        // Enter on a focused button should press that button, not also submit the guess.
        if (tag === "BUTTON" && (/^wg-(share|practice)/.test(e.target.id) || e.target.classList.contains("share-btn"))) return;
        e.preventDefault(); submit();
      } else if (e.key === "Backspace") { e.preventDefault(); back(); }
      else if (/^[a-zA-Z]$/.test(e.key)) { type(e.key.toLowerCase()); }
    });
    $("wg-keys").addEventListener("click", function (e) {
      var k = e.target.closest("[data-key]");
      if (!k) return;
      var v = k.getAttribute("data-key");
      if (v === "enter") submit(); else if (v === "back") back(); else type(v);
    });
    if ($("wg-practice-btn")) $("wg-practice-btn").addEventListener("click", startPractice);
    if ($("wg-practice-again")) $("wg-practice-again").addEventListener("click", startPractice);
    window.PLShareText = shareText;   // the share row (share.js) reads this when the player taps a button
    window.setInterval(tick, 30000);
  }

  function start(dataset, validText) {
    state.valid = {};
    validText.split("\n").forEach(function (w) { if (w) state.valid[w] = true; });
    C.epoch = dataset.epoch;
    state.idx = G.dayIndex(new Date(), dataset.epoch);
    if (C.boards === 1) state.answers = [G.decode(G.pick(dataset.answers, state.idx))];
    else state.answers = G.pick(dataset.days, state.idx).map(G.decode);
    $("wg-number").textContent = "Puzzle " + (state.idx + 1);
    state.dataset = dataset; C.baseMax = C.maxGuesses;
    if (C.twists) {
      state.twist = TW()[new Date().getDay()];
      if (state.twist.max) C.maxGuesses = state.twist.max;
      var tw = $("wg-twist");
      if (tw) {
        tw.hidden = false;
        $("wg-twist-name").textContent = state.twist.name;
        $("wg-twist-text").textContent = state.twist.hintAll ? state.twist.hintAll(state.answers) : state.twist.hint ? state.twist.hint(state.answers[0]) : state.twist.text;
      }
    }
    var saved = G.getGame(C.name);
    if (saved.today && saved.today.idx === state.idx) {
      state.guesses = saved.today.guesses || [];
      state.done = !!saved.today.done;
      state.won = !!saved.today.won;
    }
    buildBoards();
    buildKeyboard();
    wire();
    paint();
    $("wg-loading").hidden = true;
    $("wg-game").hidden = false;
    if (state.done) finish(false);
  }

  function fail() {
    $("wg-loading").textContent = "The puzzle could not be loaded. Check your connection and reload the page.";
  }

  Promise.all([
    fetch("/games/data/" + C.dataFile).then(function (r) { if (!r.ok) throw 0; return r.json(); }),
    fetch("/games/data/valid5.txt").then(function (r) { if (!r.ok) throw 0; return r.text(); }),
  ]).then(function (res) { return G.ready.then(function () { start(res[0], res[1]); }); }, fail);
})();
