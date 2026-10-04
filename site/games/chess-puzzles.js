/* Chess Puzzles: unlimited rated tactics from the Lichess puzzle database (CC0). The first wrong move ends the
   puzzle, like the Lichess trainer. A solve raises your rating, a miss lowers it. Move rules come from the
   self-hosted chess.js. The next puzzle is a fresh page load. */
(function () {
  "use strict";
  var G = window.PLGames, R = window.PLRating, NAME = "chess-puzzles";
  if (!G || !R) return;
  var $ = function (id) { return document.getElementById(id); };
  var GLYPH = { k: "♚", q: "♛", r: "♜", b: "♝", n: "♞", p: "♟︎" };
  var NAMES = { k: "king", q: "queen", r: "rook", b: "bishop", n: "knight", p: "pawn" };
  var THEME_LABEL = { mateIn1: "Mate in 1", mateIn2: "Mate in 2", mateIn3: "Mate in 3", mateIn4: "Mate in 4", fork: "Fork", pin: "Pin", skewer: "Skewer", discoveredAttack: "Discovered attack",
    hangingPiece: "Hanging piece", trappedPiece: "Trapped piece", backRankMate: "Back-rank mate", smotheredMate: "Smothered mate", deflection: "Deflection", attraction: "Attraction",
    sacrifice: "Sacrifice", promotion: "Promotion", quietMove: "Quiet move", doubleCheck: "Double check", endgame: "Endgame", middlegame: "Middlegame", opening: "Opening",
    advantage: "Winning advantage", crushing: "Crushing", short: "Short", long: "Long", mate: "Mate", exposedKing: "Exposed king", capturingDefender: "Capturing the defender",
    clearance: "Clearance", interference: "Interference", intermezzo: "In-between move", zugzwang: "Zugzwang", advancedPawn: "Advanced pawn" };


  var Chess = null;
  var st = { pz: null, bucket: 0, game: null, ply: 1, done: false, won: false, sel: null, last: null, orient: "w", busy: false, focus: "e1", pendingPromo: null, t0: 0, rec: null, signedIn: false };

  function cur() { return { id: st.pz.id, bucket: st.bucket, t0: st.t0, ply: st.ply }; }
  function save() { if (!st.done) R.current("chess", cur()); }
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

  // the sound and a small landing pulse for a move that was just played
  function moveFx(m) {
    var FX = window.PLFX; if (!FX) return;
    FX.play(m.captured ? "capture" : "place");
    if (m.san && /[+#]/.test(m.san)) window.setTimeout(function () { FX.play("check"); }, 110);
    var c = cellOf(m.to); if (c) FX.kick(c.querySelector(".cb-piece"), "fx-pop", 200);
  }

  function reply() {
    // the opponent's scripted answer, shown after a short pause so the move can be seen
    st.busy = true;
    window.setTimeout(function () {
      var m = st.game.move(parse(st.pz.moves[st.ply]));
      st.last = { from: m.from, to: m.to };
      st.ply += 1;
      st.busy = false;
      save(); paint(); moveFx(m);
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
      paint();
      var bad = cellOf(to);
      if (bad) { bad.setAttribute("data-wrong", "1"); window.setTimeout(function () { bad.removeAttribute("data-wrong"); }, 700); }
      if (window.PLFX) { window.PLFX.play("bad"); window.PLFX.vibrate(40); window.PLFX.kick($("ch-board"), "fx-shake", 500); }
      say("That is not the move.");
      reveal(false);
      return;
    }
    st.last = { from: m.from, to: m.to };
    st.ply += 1;
    say("");
    paint(); moveFx(m);
    if (st.game.isCheckmate() || st.ply >= st.pz.moves.length) { st.done = true; st.won = true; save(); finish(true, "solved"); return; }
    save();
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

  // After a miss or "Show solution": play out the real line so the player sees it, then rate.
  function reveal(won) {
    if (st.done) return;
    st.done = true; st.won = won;
    R.current("chess", null);
    var chain = st.pz.moves.slice(st.ply), k = 0;
    (function step() {
      if (k >= chain.length) { finish(true, "failed"); return; }
      var m = st.game.move(parse(chain[k++]));
      st.last = { from: m.from, to: m.to };
      paint();
      if (window.PLFX) window.PLFX.play(m.captured ? "capture" : "place");
      window.setTimeout(step, 520);
    })();
  }

  function themes() {
    return st.pz.themes.filter(function (t) { return THEME_LABEL[t]; }).slice(0, 3).map(function (t) { return THEME_LABEL[t]; });
  }

  function finish(fresh, result) {
    $("ch-controls").hidden = true;
    var ms = Date.now() - st.t0;
    var done = function (out) {
      var rec = out.rec, delta = out.delta;
      R.current("chess", null); R.recentIds("chess", st.pz.id);
      st.rec = rec;
      var up = delta >= 0;
      $("cr-head").textContent = st.won ? "Solved" : "Missed";
      $("cr-delta").textContent = (up ? "+" : "−") + Math.abs(delta);
      $("cr-delta").setAttribute("data-up", up ? "1" : "0");
      $("cr-new").textContent = String(rec.r);
      $("cr-tier").textContent = R.tierFor(rec.r);
      $("cr-streak").textContent = String(rec.streak); $("cr-streak-top").textContent = String(rec.streak);
      $("cr-peak").textContent = String(rec.peak);
      $("cr-about").textContent = "Puzzle rated " + st.pz.rating + (themes().length ? ". Themes: " + themes().join(", ") + "." : ".");
      var link = $("ch-game-link"); link.href = "https://lichess.org/training/" + st.pz.id;
      $("cr-rating").textContent = String(rec.r); $("cr-tier-top").textContent = R.tierFor(rec.r);
      $("cr-result").hidden = false;
      if (window.PLPartners) window.PLPartners.show();
      var FX = window.PLFX;
      if (FX) { FX.play(st.won ? (delta >= 14 ? "big" : "win") : "lose"); FX.vibrate(st.won ? [20, 40, 20] : 60); FX.kick($("cr-delta"), "fx-pop", 300); if (st.won && window.PLConfetti && delta >= 14) window.PLConfetti.small(); }
      join(out);
      if (window.PLAch) window.PLAch.check({ game: NAME, rated: true, idx: G.dayIndex(new Date(), "2026-10-04"), won: st.won, rating: rec.r, streak: rec.streak, n: rec.n, puzzleRating: st.pz.rating });
      G.track("game_end", NAME + ":" + (st.won ? "win" : "loss"));
      $("cr-next").focus({ preventScroll: true });
    };
    R.report("chess", { id: st.pz.id, puzzleRating: st.pz.rating, result: result, ms: ms }).then(done);
  }

  // The leaderboard prompt depends on whether the player is signed in and has opted in.
  function join(out) {
    var box = $("cr-join"), s = G.session && G.session.get();
    box.textContent = "";
    function p(text) { var e = document.createElement("p"); e.textContent = text; box.appendChild(e); return e; }
    function btn(text, fn) { var b = document.createElement("button"); b.type = "button"; b.className = "gbtn gbtn--ghost"; b.textContent = text; b.addEventListener("click", fn); box.appendChild(b); return b; }
    if (!s) {
      p("Your rating is saved on this device. Sign in with an email link to keep it across devices and appear on the leaderboard.");
      var a = document.createElement("a"); a.className = "gbtn gbtn--ghost"; a.href = "/games/account/"; a.textContent = "Sign in"; box.appendChild(a);
    } else if (!out.public && !st.isPublic) {
      p(s.name ? "You are not on the leaderboard. Show " + s.name + " there?" : "Pick a display name on your account page to appear on the leaderboard.");
      if (s.name) btn("Show me on the leaderboard", function () {
        R.setPublic(true).then(function (res) { if (res.status === 200) { st.isPublic = true; box.textContent = ""; p("You are on the leaderboard."); } else p("That name cannot be shown. Choose another on your account page."); });
      });
    } else {
      p("You are on the leaderboard.");
    }
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
    $("ch-giveup").addEventListener("click", function () {
      var b = $("ch-giveup");
      if (!b.hasAttribute("data-armed")) { b.setAttribute("data-armed", "1"); b.textContent = "Press again: counts as a miss"; window.setTimeout(function () { b.removeAttribute("data-armed"); b.textContent = "Show solution"; }, 4000); return; }
      reveal(false);
    });
    $("ch-promo").addEventListener("click", function (e) {
      var b = e.target.closest("[data-p]"); if (!b || !st.pendingPromo) return;
      var p = st.pendingPromo; st.pendingPromo = null; $("ch-promo").hidden = true;
      attempt(p.from, p.to, b.getAttribute("data-p"));
    });
  }

  function pickBucket(target) { return Math.min(2900, Math.max(500, Math.floor(target / 100) * 100)); }

  function loadBucket(b) {
    return fetch("/games/data/chess-pool/" + b + ".json").then(function (r) { if (!r.ok) throw 0; return r.json(); });
  }

  function begin(raw, bucket, resume) {
    st.bucket = bucket;
    st.pz = { id: raw.i, fen: raw.f, moves: G.decodeText(raw.m).split(" "), rating: raw.r, themes: raw.t || [] };
    st.game = new Chess(st.pz.fen);
    var first = st.game.move(parse(st.pz.moves[0]));
    st.orient = st.game.turn();
    st.last = { from: first.from, to: first.to };
    st.ply = 1;
    st.t0 = resume ? resume.t0 : Date.now();
    if (resume) for (var k = 1; k < (resume.ply || 1) && k < st.pz.moves.length; k++) { var mv = st.game.move(parse(st.pz.moves[k])); st.last = { from: mv.from, to: mv.to }; st.ply = k + 1; }
    $("ch-number").textContent = "Puzzle rated " + st.pz.rating;
    build(); wire();
    st.focus = st.orient === "w" ? "e2" : "e7";
    $("ch-loading").hidden = true; $("ch-game").hidden = false;
    paint(); save();
    if (st.game.turn() !== st.orient) reply();
  }

  function start() {
    R.load("chess").then(function (info) {
      st.rec = info.rec; st.signedIn = info.signedIn; st.isPublic = !!info.public;
      $("cr-rating").textContent = String(info.rec.r); $("cr-tier-top").textContent = R.tierFor(info.rec.r);
      $("cr-streak-top").textContent = String(info.rec.streak);
      var saved = R.current("chess");
      if (saved && saved.id) {
        return loadBucket(saved.bucket).then(function (d) {
          var raw = d.p.filter(function (p) { return p.i === saved.id; })[0];
          if (raw) return begin(raw, saved.bucket, saved);
          R.current("chess", null); return fresh(info.rec.r);
        }, function () { R.current("chess", null); return fresh(info.rec.r); });
      }
      return fresh(info.rec.r);
    });
  }

  // Aim a little around the player's rating, away from puzzles seen recently.
  function fresh(rating) {
    var target = rating + Math.round((Math.random() - 0.5) * 240), seen = R.recentIds("chess");
    return loadBucket(pickBucket(target)).then(function (d) {
      var pool = d.p.filter(function (p) { return seen.indexOf(p.i) < 0; });
      if (!pool.length) pool = d.p;
      begin(pool[Math.floor(Math.random() * pool.length)], d.b, null);
    }).catch(fail);
  }
  function fail() { $("ch-loading").textContent = "The puzzles could not be loaded. Check your connection and reload the page."; }

  Promise.all([import("/assets/vendor/chessjs/chess-1.4.0.js")]).then(function (res) { Chess = res[0].Chess; return G.ready.then(start); }, fail);
})();
