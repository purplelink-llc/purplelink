/* Teamlink: join two players, from any era, with a chain of real teammates. Add players at either end of the chain;
   the chain is solved when the two ends are teammates. Shortest possible chain is "par". */
(function () {
  "use strict";
  var G = window.PLGames, S = window.PLSports, NAME = "teamlink";
  var $ = function (id) { return document.getElementById(id); };
  var root = $("sp-root"), FX = window.PLFX;
  var DIFF = { easy: [2], medium: [3], hard: [4, 5, 6] };
  var W = ["Standard", "Standard", "Standard", "Standard", "Standard", "Standard", "Standard"];
  var st = null, data = null, daily = null, mode = "daily", cmb = null, rotation = ["nba"];

  function nameOf(p) { return p.n; }
  function P(n) { return data.byName[n]; }
  function side(arr) { return arr.map(P).filter(Boolean); }

  function newState(a, b) { return { a: a, b: b, L: [a], R: [b], misses: 0, hints: 0, moves: [], done: false, won: false, gave: false, hint: { key: "", level: 0 } }; }
  function par() { var p = S.path(data, P(st.a), P(st.b)); return p ? p.length - 1 : 0; }
  function links() { return st.L.length + st.R.length - 1; }
  function inChain(p) { return st.L.indexOf(p.n) >= 0 || st.R.indexOf(p.n) >= 0; }
  function ends() { return { l: P(st.L[st.L.length - 1]), r: P(st.R[0]) }; }
  function solved() { var e = ends(); return S.areTeammates(data, e.l, e.r); }

  function save() {
    if (mode !== "daily" || !daily) return;
    S.saveState(NAME, { idx: daily.idx, sport: daily.sport, st: st });
  }

  function reasonText(a, b) {
    var s = S.shared(a, b);
    if (!s) return "";
    return S.fname(data, s.f) + ", " + S.span(data, s.from, s.to);
  }

  function card(p, role) {
    var li = document.createElement("li");
    li.className = "tl-node" + (role ? " tl-" + role : "");
    var n = document.createElement("span"); n.className = "tl-name"; n.textContent = p.n;
    var m = document.createElement("span"); m.className = "tl-meta"; m.textContent = (p.pos ? p.pos + ", " : "") + S.career(p) + (p.born ? ", b. " + p.born : "") + ". " + S.teamsLine(data, p);
    li.appendChild(n); li.appendChild(m);
    return li;
  }
  function linkRow(a, b) {
    var li = document.createElement("li");
    li.className = "tl-link"; li.setAttribute("aria-label", "Teammates: " + reasonText(a, b));
    li.textContent = reasonText(a, b);
    return li;
  }

  function paint() {
    var list = $("sp-chain"); list.innerHTML = "";
    var L = side(st.L), R = side(st.R);
    L.forEach(function (p, i) { if (i) list.appendChild(linkRow(L[i - 1], p)); list.appendChild(card(p, i === 0 ? "start" : "")); });
    if (!st.done || !st.won) {
      if (!(st.done && st.won)) {
        var gap = document.createElement("li"); gap.className = "tl-gap";
        gap.textContent = st.done ? "" : "Name a teammate of " + L[L.length - 1].n + " or of " + R[0].n + ".";
        if (!st.done) list.appendChild(gap);
      }
    }
    if (st.done && st.won) list.appendChild(linkRow(L[L.length - 1], R[0]));
    R.forEach(function (p, i) { if (i) list.appendChild(linkRow(R[i - 1], p)); list.appendChild(card(p, i === R.length - 1 ? "target" : "")); });
    $("sp-links").textContent = String(links());
    $("sp-par").textContent = st.done || mode !== "daily" ? String(par()) : "?";
    $("sp-par").parentNode.hidden = false;
    $("sp-misses").textContent = String(st.misses);
    $("sp-hints").textContent = String(st.hints);
    $("tl-undo").disabled = st.done || !st.moves.length;
    $("tl-hint").disabled = st.done;
    $("tl-giveup").disabled = st.done;
    $("sp-form").hidden = st.done;
  }

  function say(text, bad) {
    var m = $("sp-msg"); m.textContent = text; m.classList.toggle("sp-bad", !!bad);
  }

  function pick(p) {
    if (st.done) return;
    if (inChain(p)) { say(p.n + " is already in your chain.", true); return; }
    var e = ends(), left = S.areTeammates(data, e.l, p), right = S.areTeammates(data, e.r, p);
    if (!left && !right) {
      st.misses++;
      say(p.n + " was not a teammate of " + e.l.n + " or " + e.r.n + ".", true);
      if (FX) { FX.play("bad"); FX.vibrate(30); FX.kick($("sp-form"), "fx-shake", 400); }
      paint(); save(); return;
    }
    if (left) { st.L.push(p.n); st.moves.push("L"); } else { st.R.unshift(p.n); st.moves.push("R"); }
    st.hint = { key: "", level: 0 };
    if (FX) { FX.play("good"); FX.vibrate(15); }
    if (solved()) { say("Linked: " + p.n + " closes the chain.", false); finish(true); return; }
    say("Linked: " + (left ? e.l.n : e.r.n) + " and " + p.n + " (" + reasonText(left ? e.l : e.r, p) + ").");
    paint(); save();
  }

  function undo() {
    if (st.done || !st.moves.length) return;
    var s = st.moves.pop();
    if (s === "L") st.L.pop(); else st.R.shift();
    st.hint = { key: "", level: 0 };
    say("Removed the last player.");
    paint(); save();
  }

  function hint() {
    if (st.done) return;
    var e = ends(), p = S.path(data, e.l, e.r);
    if (!p || p.length < 3) { say("The two ends are one step apart: name any teammate they share, or one of the two."); return; }
    var next = p[1], key = e.l.n + ">" + e.r.n;
    if (st.hint.key !== key) st.hint = { key: key, level: 0 };
    st.hint.level++; st.hints++;
    var s = S.shared(e.l, next), team = S.fname(data, s.f);
    if (st.hint.level === 1) say("Hint: a good next player was " + e.l.n + "'s teammate with the " + team + ".");
    else {
      var w = next.n.split(" ");
      say("Hint: " + team + ", " + next.pos + ", initials " + w[0][0] + ". " + w[w.length - 1][0] + ".");
    }
    paint(); save();
  }

  function giveUp() {
    if (st.done) return;
    st.gave = true; finish(false);
  }

  function score() {
    if (!st.won) return 99;
    return Math.min(98, Math.max(0, (links() - par())) * 3 + Math.min(st.misses, 20) + st.hints * 2);
  }
  function stars() {
    if (!st.won) return 0;
    var over = links() - par();
    return over === 0 && st.misses <= 2 && st.hints === 0 ? 3 : over <= 1 ? 2 : 1;
  }

  function shareText() {
    var sq = "", n = par(), i;
    for (i = 0; i < links(); i++) sq += i < n ? "■" : "▣";
    var tag = mode === "daily" ? "#" + (daily.idx + 1) + " " : "practice ";
    return "Teamlink " + tag + data.name + "\n" + st.a + " to " + st.b + "\n" + (st.won ? sq + " " + links() + " links (par " + par() + ")" : "Gave up (par " + par() + ")") + (st.misses ? ", " + st.misses + " miss" + (st.misses === 1 ? "" : "es") : "") + (st.hints ? ", " + st.hints + " hint" + (st.hints === 1 ? "" : "s") : "") + "\n\n" + root.getAttribute("data-url");
  }

  function finish(won) {
    st.done = true; st.won = won;
    var fresh = mode === "daily" && !(G.getGame(NAME).today && G.getGame(NAME).today.idx === daily.idx && G.getGame(NAME).today.done);
    if (!won) st.moves = [];
    paint(); save();
    if (mode === "daily" && fresh) {
      var saved = G.getGame(NAME);
      saved.stats = G.recordResult(saved.stats, daily.idx, won, links());
      saved.today = { idx: daily.idx, done: true, won: won };
      G.setGame(NAME, saved);
      G.track("game_end", NAME + ":" + (won ? "win" : "loss"));
      if (window.PLAch) window.PLAch.check({ game: NAME, idx: daily.idx, won: won, tries: links() });
      G.submitScore(NAME, daily.idx, score()).then(function (res) { $("sp-pct").textContent = G.describePercentile(res); });
    }
    if (won && window.PLConfetti) window.PLConfetti[stars() === 3 ? "big" : "small"]();
    if (FX) FX.play(won ? (stars() === 3 ? "big" : "win") : "lose");
    showResult(fresh);
  }

  function showResult(fresh) {
    var box = $("sp-result"); box.hidden = false;
    var head = st.won ? (links() === par() ? "Par. Linked in " + links() : "Linked in " + links() + ", par was " + par()) : "Not this time";
    $("sp-result-head").textContent = head;
    var best = S.path(data, P(st.a), P(st.b));
    $("sp-reveal").textContent = "One shortest chain: " + (best ? best.map(nameOf).join(", then ") + "." : "none found.");
    var s = G.getGame(NAME).stats || G.emptyStats();
    var daily_ = mode === "daily";
    $("sp-statline").hidden = !daily_;
    $("sp-played").textContent = s.played; $("sp-winpct").textContent = s.played ? Math.round(100 * s.won / s.played) + "%" : "0%";
    $("sp-streak").textContent = s.streak; $("sp-max").textContent = s.max;
    var sv = $("sp-saver"); if (sv) sv.textContent = daily_ ? G.saverNote(s, daily.idx) : "";
    $("sp-star").textContent = st.won ? "Rating: " + ["", "One star", "Two stars", "Three stars"][stars()] + "." : "";
    $("sp-next-line").hidden = !daily_;
    $("sp-practice-again").hidden = daily_;
    tick();
    if (fresh) box.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
  function tick() {
    var el = $("sp-next-in"); if (!el) return;
    var now = new Date(), nx = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1), ms = nx - now;
    el.textContent = Math.floor(ms / 3600000) + " h " + ("0" + Math.floor((ms % 3600000) / 60000)).slice(-2) + " min";
  }

  // ---- starting a game ----
  function begin(d, a, b, saved) {
    data = d;
    st = saved || newState(a, b);
    $("sp-result").hidden = true; $("sp-msg").textContent = ""; $("sp-pct").textContent = "";
    $("tl-from").textContent = st.a; $("tl-to").textContent = st.b;
    paint();
    if (st.done) showResult(false); else if (!$("sp-game").hidden) $("sp-input").focus({ preventScroll: true });
  }

  function startDaily() {
    mode = "daily";
    var idx = S.dayIdx(), sport = S.dailySport(rotation, idx);
    document.body.setAttribute("data-mode", "daily");
    return S.loadAll(sport).then(function (d) {
      var pair = d.tl[S.dailySlot(rotation, idx) % d.tl.length];
      daily = { idx: idx, sport: sport };
      $("sp-number").textContent = "Puzzle " + (idx + 1) + ", " + d.name;
      var saved = S.loadState(NAME);
      var ok = saved && saved.idx === idx && saved.sport === sport && d.byName[saved.st.a] && d.byName[saved.st.b] && saved.st.L.every(function (n) { return d.byName[n]; }) && saved.st.R.every(function (n) { return d.byName[n]; });
      var g = G.getGame(NAME).today;
      begin(d, pair[0], pair[1], ok ? saved.st : null);
      if (!ok && g && g.idx === idx && g.done) { st.done = true; st.won = !!g.won; paint(); showResult(false); }
    });
  }

  function startPractice() {
    mode = "practice";
    document.body.setAttribute("data-mode", "practice");
    var sport = $("sp-sport").value, diff = DIFF[$("sp-diff").value];
    return S.loadAll(sport).then(function (d) {
      var famous = d.players.filter(function (p) { return p.tier >= 3; });
      var r = S.rng(Date.now()), a, b, tries = 0, pool = [];
      while (!pool.length && tries++ < 12) {
        a = famous[Math.floor(r() * famous.length)];
        var dist = S.distances(d, a);
        pool = famous.filter(function (p) { return diff.indexOf(dist[p.i]) >= 0; });
        if (pool.length) b = pool[Math.floor(r() * pool.length)];
      }
      if (!b) { b = famous[Math.floor(r() * famous.length)]; }
      $("sp-number").textContent = "Practice, " + d.name;
      begin(d, a.n, b.n, null);
    });
  }

  function setMode(m) {
    $("sp-mode-daily").setAttribute("aria-pressed", m === "daily" ? "true" : "false");
    $("sp-mode-practice").setAttribute("aria-pressed", m === "practice" ? "true" : "false");
    $("sp-practice-opts").hidden = m !== "practice";
    return m === "daily" ? startDaily() : startPractice();
  }

  function wire() {
    cmb = S.combo({
      input: $("sp-input"), list: $("sp-list"),
      items: function () { return data.players; },
      onPick: pick,
      onNone: function (v) { say(v ? "Choose a player from the list." : "", true); }
    });
    $("sp-form").addEventListener("submit", function (e) { e.preventDefault(); cmb.top(); });
    $("tl-undo").addEventListener("click", undo);
    $("tl-hint").addEventListener("click", hint);
    $("tl-giveup").addEventListener("click", function () { if (window.confirm("Show the answer and end this puzzle?")) giveUp(); });
    $("sp-mode-daily").addEventListener("click", function () { setMode("daily"); });
    $("sp-mode-practice").addEventListener("click", function () { setMode("practice"); });
    $("sp-practice-again").addEventListener("click", startPractice);
    $("sp-new").addEventListener("click", startPractice);
    $("sp-sport").addEventListener("change", startPractice);
    $("sp-diff").addEventListener("change", startPractice);
    window.PLShareText = shareText;
    window.setInterval(tick, 30000);
  }

  S.index().then(function (ix) {
    rotation = ix.rotation || ["nba"];
    var sel = $("sp-sport");
    S.loadAll(rotation[0]).then(function () {
      rotation.forEach(function (s) { var o = document.createElement("option"); o.value = s; o.textContent = s.toUpperCase(); sel.appendChild(o); });
      return G.ready;
    }).then(function () {
      wire();
      return startDaily();
    }).then(function () { $("sp-loading").hidden = true; $("sp-game").hidden = false; if (!st.done) $("sp-input").focus({ preventScroll: true }); }, function () {
      $("sp-loading").textContent = "Today's puzzle could not be loaded. Check your connection and reload the page.";
    });
  });
})();
