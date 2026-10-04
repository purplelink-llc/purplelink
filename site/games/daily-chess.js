/* Daily Chess: one Lichess puzzle a day. Move rules come from the self-hosted chess.js; the puzzle
   data is from the Lichess puzzle database (CC0). Streak = consecutive days solved. */
(function () {
  "use strict";
  var G = window.PLGames, NAME = "daily-chess", URL_ = "https://purplelink.llc/games/daily-chess/";
  if (!G) return;
  var $ = function (id) { return document.getElementById(id); };
  var GLYPH = { k: "♚", q: "♛", r: "♜", b: "♝", n: "♞", p: "♟︎" };
  var NAMES = { k: "king", q: "queen", r: "rook", b: "bishop", n: "knight", p: "pawn" };
  var THEME_LABEL = { mateIn1: "Mate in 1", mateIn2: "Mate in 2", mateIn3: "Mate in 3", mateIn4: "Mate in 4", fork: "Fork", pin: "Pin", skewer: "Skewer", discoveredAttack: "Discovered attack",
    hangingPiece: "Hanging piece", trappedPiece: "Trapped piece", backRankMate: "Back-rank mate", smotheredMate: "Smothered mate", deflection: "Deflection", attraction: "Attraction",
    sacrifice: "Sacrifice", promotion: "Promotion", quietMove: "Quiet move", doubleCheck: "Double check", endgame: "Endgame", middlegame: "Middlegame", opening: "Opening",
    advantage: "Winning advantage", crushing: "Crushing", short: "Short", long: "Long", mate: "Mate", exposedKing: "Exposed king", capturingDefender: "Capturing the defender",
    clearance: "Clearance", interference: "Interference", intermezzo: "In-between move", zugzwang: "Zugzwang", advancedPawn: "Advanced pawn" };

  var Chess = null;
  var st = { idx: 0, pz: null, moves: [], game: null, ply: 1, mistakes: 0, hints: 0, done: false, won: false, sel: null, last: null, orient: "w", busy: false, focus: "e1", pendingPromo: null };

  function save() {
    var s = G.getGame(NAME);
    s.today = { idx: st.idx, done: st.done, won: st.won, ply: st.ply, mistakes: st.mistakes, hints: st.hints };
    G.setGame(NAME, s);
  }
  function sq(f, r) { return "abcdefgh"[f] + (r + 1); }
  function say(t) { $("ch-msg").textContent = t || ""; }

  function build() {
    var b = $("ch-board");
    b.textContent = "";
    for (var row = 0; row < 8; row++) {
      var rank = st.orient === "w" ? 7 - row : row;
      for (var col = 0; col < 8; col++) {
        var file = st.orient === "w" ? col : 7 - col;
        var name = sq(file, rank), cell = document.createElement("button");
        cell.type = "button";
        cell.className = "cb-sq";
        cell.setAttribute("data-sq", name);
        cell.setAttribute("data-shade", (file + rank) % 2 ? "light" : "dark");
        cell.tabIndex = -1;
        if (col === 0) cell.setAttribute("data-rank", String(rank + 1));
        if (row === 7) cell.setAttribute("data-file", "abcdefgh"[file]);
        var piece = document.createElement("span");
        piece.className = "cb-piece";
        piece.setAttribute("aria-hidden", "true");
        cell.appendChild(piece);
        b.appendChild(cell);
      }
    }
  }

  function cellOf(name) { return $("ch-board").querySelector('[data-sq="' + name + '"]'); }

  function paint() {
    var board = st.game.board(), targets = {}, i, j;
    if (st.sel) st.game.moves({ square: st.sel, verbose: true }).forEach(function (m) { targets[m.to] = 1; });
    var cells = $("ch-board").children;
    for (i = 0; i < cells.length; i++) {
      var c = cells[i], name = c.getAttribute("data-sq"), f = name.charCodeAt(0) - 97, r = Number(name[1]) - 1;
      var p = board[7 - r][f], span = c.firstChild;
      span.textContent = p ? GLYPH[p.type] : "";
      if (p) span.setAttribute("data-c", p.color); else span.removeAttribute("data-c");
      c.toggleAttribute("data-sel", st.sel === name);
      c.toggleAttribute("data-target", !!targets[name]);
      c.toggleAttribute("data-last", !!st.last && (st.last.from === name || st.last.to === name));
      c.removeAttribute("data-hint");
      c.setAttribute("aria-label", name + (p ? ", " + (p.color === "w" ? "white " : "black ") + NAMES[p.type] : ", empty") + (targets[name] ? ", legal move" : ""));
      c.tabIndex = name === st.focus ? 0 : -1;
    }
    var side = st.game.turn() === "w" ? "White" : "Black";
    $("ch-turn").textContent = st.done ? "" : side + " to move. " + (st.pz.moves.length - st.ply > 1 ? "Find the best move." : "Find the finishing move.");
    $("ch-fen").textContent = st.game.fen();
  }

  function parse(uci) { return { from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci.length > 4 ? uci[4] : undefined }; }

  function reply() {
    // the opponent's scripted answer, shown after a short pause so the move can be seen
    st.busy = true;
    window.setTimeout(function () {
      var m = st.game.move(parse(st.pz.moves[st.ply]));
      st.last = { from: m.from, to: m.to };
      st.ply += 1;
      st.busy = false;
      save(); paint();
    }, 500);
  }

  function attempt(from, to, promo) {
    var legal = st.game.moves({ square: from, verbose: true }).filter(function (m) { return m.to === to; });
    if (!legal.length) { st.sel = null; paint(); return; }
    if (legal[0].promotion && !promo) { openPromotion(from, to); return; }
    var uci = from + to + (promo || "");
    var expected = st.pz.moves[st.ply];
    var m = st.game.move({ from: from, to: to, promotion: promo });
    var ok = uci === expected || st.game.isCheckmate();
    st.sel = null;
    if (!ok) {
      st.game.undo();
      st.mistakes += 1;
      say("That is not the move. Try again.");
      save(); paint();
      var bad = cellOf(to);
      if (bad) { bad.setAttribute("data-wrong", "1"); window.setTimeout(function () { bad.removeAttribute("data-wrong"); }, 700); }
      return;
    }
    st.last = { from: m.from, to: m.to };
    st.ply += 1;
    say("");
    if (st.game.isCheckmate() || st.ply >= st.pz.moves.length) { win(); return; }
    save(); paint();
    reply();
  }

  function openPromotion(from, to) {
    st.pendingPromo = { from: from, to: to };
    var box = $("ch-promo");
    box.hidden = false;
    box.querySelector("button").focus();
  }

  function onSquare(name) {
    if (st.done || st.busy) return;
    st.focus = name;
    var piece = st.game.get(name);
    if (st.sel && st.sel !== name) {
      var legal = st.game.moves({ square: st.sel, verbose: true }).some(function (m) { return m.to === name; });
      if (legal) { attempt(st.sel, name); return; }
    }
    if (piece && piece.color === st.game.turn()) { st.sel = st.sel === name ? null : name; if (G.track && !st.started) { st.started = true; G.track("game_start", NAME); } }
    else st.sel = null;
    paint();
    var el = cellOf(name); if (el) el.focus();
  }

  function hint() {
    if (st.done || st.busy) return;
    st.hints += 1;
    var m = parse(st.pz.moves[st.ply]);
    paint();
    var el = cellOf(m.from);
    if (el) el.setAttribute("data-hint", "1");
    say("Look at the piece on " + m.from + ".");
    save();
  }

  function giveUp() {
    if (st.done) return;
    st.done = true; st.won = false;
    var chain = st.pz.moves.slice(st.ply);
    var k = 0;
    (function step() {
      if (k >= chain.length) { finish(true); return; }
      var m = st.game.move(parse(chain[k++]));
      st.last = { from: m.from, to: m.to };
      paint();
      window.setTimeout(step, 450);
    })();
  }

  function win() {
    st.done = true; st.won = true;
    paint();
    save();
    if (window.PLConfetti) window.PLConfetti[st.mistakes === 0 && st.hints === 0 ? "big" : "small"]();
    finish(true);
  }

  function themes() {
    return st.pz.themes.filter(function (t) { return THEME_LABEL[t]; }).slice(0, 3).map(function (t) { return THEME_LABEL[t]; });
  }

  function shareText() {
    var res = st.won ? "solved" + (st.mistakes + st.hints ? ", " + (st.mistakes + st.hints) + " slip" + (st.mistakes + st.hints === 1 ? "" : "s") : " first try") : "not solved";
    return "Daily Chess " + (st.idx + 1) + " (" + st.pz.rating + "): " + res + "\n\n" + URL_;
  }

  function finish(fresh) {
    var saved = G.getGame(NAME);
    if (fresh) {
      saved.stats = G.recordResult(saved.stats, st.idx, st.won, Math.min(9, st.mistakes + st.hints));
      G.setGame(NAME, saved);
      save();
      G.track("game_end", NAME + ":" + (st.won ? "win" : "loss"));
      var ctx = { game: NAME, idx: st.idx, won: st.won, clean: st.mistakes === 0 && st.hints === 0, rating: st.pz.rating };
      if (window.PLAch) window.PLAch.check(ctx);
      G.submitScore(NAME, st.idx, st.won ? Math.min(20, st.mistakes + st.hints) : 99).then(function (res) {
        $("ch-pct").textContent = G.describePercentile(res);
        if (res && window.PLAch) window.PLAch.check({ game: NAME, idx: st.idx, won: st.won, clean: ctx.clean, rating: st.pz.rating, pct: res.percentile, total: res.total });
      });
    }
    var s = saved.stats || G.emptyStats();
    var sv = $("ch-saver"); if (sv) sv.textContent = G.saverNote(s, st.idx);
    $("ch-controls").hidden = true;
    var box = $("ch-result"); box.hidden = false;
    $("ch-result-head").textContent = st.won ? (st.mistakes + st.hints === 0 ? "Solved on the first try" : "Solved with " + (st.mistakes + st.hints) + " slip" + (st.mistakes + st.hints === 1 ? "" : "s")) : "Not solved today";
    $("ch-about").textContent = "Puzzle rated " + st.pz.rating + (themes().length ? ". Themes: " + themes().join(", ") + "." : ".");
    var link = $("ch-game-link"); link.href = "https://lichess.org/training/" + st.pz.id; link.textContent = "See this puzzle on Lichess";
    $("ch-played").textContent = s.played; $("ch-won").textContent = s.won; $("ch-streak").textContent = s.streak; $("ch-max").textContent = s.max;
    tick();
  }

  function tick() {
    var el = $("ch-next-in");
    if (!el || $("ch-result").hidden) return;
    var now = new Date(), nx = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
    var ms = nx - now, h = Math.floor(ms / 3600000), m = Math.floor((ms % 3600000) / 60000);
    el.textContent = h + " h " + (m < 10 ? "0" : "") + m + " min";
  }

  function wire() {
    $("ch-board").addEventListener("click", function (e) { var c = e.target.closest(".cb-sq"); if (c) onSquare(c.getAttribute("data-sq")); });
    $("ch-board").addEventListener("keydown", function (e) {
      var c = e.target.closest(".cb-sq"); if (!c) return;
      var name = c.getAttribute("data-sq"), f = name.charCodeAt(0) - 97, r = Number(name[1]) - 1, df = 0, dr = 0;
      if (e.key === "ArrowRight") df = st.orient === "w" ? 1 : -1; else if (e.key === "ArrowLeft") df = st.orient === "w" ? -1 : 1;
      else if (e.key === "ArrowUp") dr = st.orient === "w" ? 1 : -1; else if (e.key === "ArrowDown") dr = st.orient === "w" ? -1 : 1;
      else return;
      e.preventDefault();
      var nf = Math.min(7, Math.max(0, f + df)), nr = Math.min(7, Math.max(0, r + dr));
      st.focus = sq(nf, nr); paint(); cellOf(st.focus).focus();
    });
    $("ch-hint").addEventListener("click", hint);
    $("ch-giveup").addEventListener("click", function () {
      var b = $("ch-giveup");
      if (!b.hasAttribute("data-armed")) { b.setAttribute("data-armed", "1"); b.textContent = "Press again to show the solution"; window.setTimeout(function () { b.removeAttribute("data-armed"); b.textContent = "Show solution"; }, 4000); return; }
      giveUp();
    });
    $("ch-promo").addEventListener("click", function (e) {
      var b = e.target.closest("[data-p]"); if (!b || !st.pendingPromo) return;
      var p = st.pendingPromo; st.pendingPromo = null; $("ch-promo").hidden = true;
      attempt(p.from, p.to, b.getAttribute("data-p"));
    });
    $("ch-share").addEventListener("click", function () {
      var text = shareText(); G.track("game_share", NAME);
      G.copyText(text).then(function (ok) {
        $("ch-share-note").textContent = ok ? "Copied to the clipboard." : "Copy failed. Select the text below and copy it.";
        var box = $("ch-share-text"); box.value = text; box.hidden = ok;
      });
    });
    window.setInterval(tick, 30000);
  }

  function start(data) {
    st.idx = G.dayIndex(new Date(), data.epoch);
    var raw = G.pick(data.days, st.idx);
    st.pz = { id: raw.i, fen: raw.f, moves: G.decodeText(raw.m).split(" "), rating: raw.r, themes: raw.t || [], game: raw.g };
    st.game = new Chess(st.pz.fen);
    var first = st.game.move(parse(st.pz.moves[0]));      // the opponent's move that sets the puzzle
    st.orient = st.game.turn();
    st.last = { from: first.from, to: first.to };
    st.ply = 1;
    var saved = G.getGame(NAME).today;
    if (saved && saved.idx === st.idx) {
      st.mistakes = saved.mistakes || 0; st.hints = saved.hints || 0;
      for (var k = 1; k < (saved.ply || 1) && k < st.pz.moves.length; k++) { var mv = st.game.move(parse(st.pz.moves[k])); st.last = { from: mv.from, to: mv.to }; st.ply = k + 1; }
      st.done = !!saved.done; st.won = !!saved.won;
      if (st.done && !st.won) { for (; st.ply < st.pz.moves.length; st.ply++) st.game.move(parse(st.pz.moves[st.ply])); }
    }
    $("ch-number").textContent = "Puzzle " + (st.idx + 1) + ", rated " + st.pz.rating;
    build(); wire();
    st.focus = st.orient === "w" ? "e2" : "e7";
    $("ch-loading").hidden = true;
    $("ch-game").hidden = false;
    paint();
    if (st.done) finish(false);
    else if (st.game.turn() !== st.orient) reply();
  }

  Promise.all([
    import("/assets/vendor/chessjs/chess-1.4.0.js"),
    fetch("/games/data/chess.json").then(function (r) { if (!r.ok) throw 0; return r.json(); })
  ]).then(function (res) { Chess = res[0].Chess; return G.ready.then(function () { start(res[1]); }); }, function () {
    $("ch-loading").textContent = "Today's puzzle could not be loaded. Check your connection and reload the page.";
  });
})();
