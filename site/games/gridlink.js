/* Gridlink: a 3 by 3 grid. Each cell asks for a player who fits the row and the column (played for a team, played in a
   decade, played a position, and so on). Nine guesses in all, each player once. Rarer players score more. */
(function () {
  "use strict";
  var G = window.PLGames, S = window.PLSports, NAME = "gridlink";
  var $ = function (id) { return document.getElementById(id); };
  var root = $("sp-root"), FX = window.PLFX;
  var MAXG = 9;
  var st = null, data = null, daily = null, mode = "daily", rotation = ["nba"], grid = null, active = 0, cmb = null;

  function P(n) { return data.byName[n]; }
  function filled() { return st.cells.filter(Boolean).length; }
  function rarity() { return st.cells.reduce(function (a, n) { return a + (n ? 6 - P(n).tier : 0); }, 0); }
  function cellCrit(i) { return { r: grid.r[Math.floor(i / 3)], c: grid.c[i % 3] }; }

  function save() { if (mode === "daily" && daily) S.saveState(NAME, { idx: daily.idx, sport: daily.sport, st: st }); }

  function newState() { return { t0: Date.now(), cells: [null, null, null, null, null, null, null, null, null], used: 0, done: false, won: false }; }

  function build(g) {
    grid = { r: g.r.map(function (c) { return S.crit(data, c); }), c: g.c.map(function (c) { return S.crit(data, c); }) };
  }

  function head(c, cls) {
    var d = document.createElement("div");
    d.className = "gl-head " + cls;
    d.setAttribute("title", c.label);
    var s = document.createElement("span"); s.textContent = c.short; d.appendChild(s);
    var v = document.createElement("span"); v.className = "visually-hidden"; v.textContent = " (" + c.label + ")"; d.appendChild(v);
    return d;
  }

  function paint() {
    var box = $("gl-grid"); box.innerHTML = "";
    var corner = document.createElement("div"); corner.className = "gl-corner"; box.appendChild(corner);
    grid.c.forEach(function (c) { box.appendChild(head(c, "gl-col")); });
    for (var r = 0; r < 3; r++) {
      var rh = head(grid.r[r], "gl-row"); box.appendChild(rh);
      for (var c = 0; c < 3; c++) {
        (function (i) {
          var b = document.createElement("button");
          b.type = "button"; b.className = "gl-cell"; b.setAttribute("data-i", i);
          var name = st.cells[i];
          var cr = cellCrit(i);
          b.setAttribute("aria-label", "Cell " + (Math.floor(i / 3) + 1) + "," + (i % 3 + 1) + ": " + cr.r.label + " and " + cr.c.label + (name ? ". Filled with " + name : ". Empty"));
          if (name) { b.classList.add("is-filled"); b.textContent = name; var t = document.createElement("span"); t.className = "gl-tier"; t.textContent = "+" + (6 - P(name).tier); b.appendChild(t); b.disabled = true; }
          else if (st.done) {
            b.classList.add("is-missed");
            var ans = S.cellAnswers(data, cr.r, cr.c).sort(function (a, b2) { return b2.tier - a.tier; }).slice(0, 2).map(function (p) { return p.n; });
            b.textContent = ans.join(", "); b.disabled = true;
          } else { b.textContent = ""; if (i === active) b.classList.add("is-active"); }
          if (!st.done && !name) b.addEventListener("click", function () { active = i; paint(); $("sp-input").focus({ preventScroll: true }); });
          box.appendChild(b);
        })(r * 3 + c);
      }
    }
    $("gl-left").textContent = String(MAXG - st.used);
    $("gl-filled").textContent = filled() + " of 9";
    $("gl-rarity").textContent = String(rarity());
    $("sp-form").hidden = st.done;
    if (!st.done && st.cells[active]) active = st.cells.indexOf(null);
    var cur = $("gl-current");
    if (!st.done && active >= 0) { var cc = cellCrit(active); cur.textContent = "Name a player: " + cc.r.label + " and " + cc.c.label + "."; } else cur.textContent = "";
  }

  function say(t, bad) { var m = $("sp-msg"); m.textContent = t; m.classList.toggle("sp-bad", !!bad); }

  function pick(p) {
    if (st.done) return;
    if (active < 0 || st.cells[active]) { active = st.cells.indexOf(null); }
    if (st.cells.indexOf(p.n) >= 0) { say(p.n + " is already on your grid.", true); return; }
    var cr = cellCrit(active), ok = cr.r.test(p) && cr.c.test(p);
    st.used++;
    var cell = document.querySelector('.gl-cell[data-i="' + active + '"]');
    if (ok) {
      st.cells[active] = p.n;
      say(p.n + " fits. +" + (6 - p.tier) + " for rarity.");
      if (FX) { FX.play("good"); FX.vibrate(15); }
      active = st.cells.indexOf(null);
    } else {
      say(p.n + " does not fit " + cr.r.label + " and " + cr.c.label + ".", true);
      if (FX) { FX.play("bad"); FX.vibrate(30); }
    }
    paint(); save();
    if (!ok && FX) { var c2 = document.querySelector('.gl-cell[data-i="' + active + '"]'); if (c2) FX.kick(c2, "fx-shake", 400); }
    else if (ok && FX) { var c3 = document.querySelector('.gl-cell[data-i="' + st.cells.indexOf(p.n) + '"]'); if (c3) FX.kick(c3, "fx-pop", 300); }
    if (filled() === 9 || st.used >= MAXG) finish();
  }

  function shareText() {
    var rows = [0, 1, 2].map(function (r) { return [0, 1, 2].map(function (c) { return st.cells[r * 3 + c] ? "■" : "□"; }).join(""); });
    var tag = mode === "daily" ? "#" + (daily.idx + 1) + " " : "practice ";
    return "Gridlink " + tag + data.name + " " + filled() + "/9\n\n" + rows.join("\n") + "\nRarity " + rarity() + "\n\n" + root.getAttribute("data-url");
  }

  function finish() {
    st.done = true; st.won = filled() >= 5;
    var fresh = mode === "daily" && !(G.getGame(NAME).today && G.getGame(NAME).today.idx === daily.idx && G.getGame(NAME).today.done);
    paint(); save();
    if (mode === "daily" && fresh) {
      var saved = G.getGame(NAME);
      saved.stats = G.recordResult(saved.stats, daily.idx, st.won, 9 - filled() + 1);
      saved.today = { idx: daily.idx, done: true, won: st.won };
      G.setGame(NAME, saved);
      G.track("game_end", NAME + ":" + (st.won ? "win" : "loss"));
      if (window.PLAch) window.PLAch.check({ game: NAME, idx: daily.idx, won: st.won, tries: 9 - filled() + 1 });
      G.submitScore(NAME, daily.idx, Math.min(98, 9 - filled())).then(function (res) { $("sp-pct").textContent = G.describePercentile(res); });
      if (window.PLRating) window.PLRating.report(NAME, { idx: daily.idx, sport: daily.sport, ms: S.elapsed(st.t0), filled: filled() }).then(function (x) { S.paintRating(NAME, x); });
    }
    if (filled() === 9 && window.PLConfetti) window.PLConfetti.big(); else if (st.won && window.PLConfetti) window.PLConfetti.small();
    if (FX) FX.play(filled() === 9 ? "big" : st.won ? "win" : "lose");
    showResult(fresh);
  }

  function showResult(fresh) {
    var box = $("sp-result"); box.hidden = false;
    $("sp-result-head").textContent = filled() === 9 ? "Perfect grid" : filled() + " of 9 filled";
    $("sp-reveal").textContent = "Rarity score " + rarity() + " of a possible 45. Each cell is worth 1 to 5: the less famous the player, the higher the score.";
    var s = G.getGame(NAME).stats || G.emptyStats(), d_ = mode === "daily";
    $("sp-statline").hidden = !d_;
    $("sp-played").textContent = s.played; $("sp-winpct").textContent = s.played ? Math.round(100 * s.won / s.played) + "%" : "0%";
    $("sp-streak").textContent = s.streak; $("sp-max").textContent = s.max;
    var sv = $("sp-saver"); if (sv) sv.textContent = d_ ? G.saverNote(s, daily.idx) : "";
    $("sp-next-line").hidden = !d_;
    $("sp-practice-again").hidden = d_;
    if (!fresh && d_) S.paintRating(NAME, null);
    tick();
    if (fresh) box.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
  function tick() {
    var el = $("sp-next-in"); if (!el) return;
    var now = new Date(), nx = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1), ms = nx - now;
    el.textContent = Math.floor(ms / 3600000) + " h " + ("0" + Math.floor((ms % 3600000) / 60000)).slice(-2) + " min";
  }

  function begin(d, g, saved) {
    data = d; build(g);
    st = saved || newState();
    active = Math.max(0, st.cells.indexOf(null));
    $("sp-result").hidden = true; $("sp-msg").textContent = ""; $("sp-pct").textContent = "";
    paint();
    if (st.done) showResult(false);
  }

  function startDaily() {
    mode = "daily";
    var idx = S.dayIdx(), sport = S.dailySport(rotation, idx);
    return S.load(sport).then(function (d) {
      var g = d.gr[S.dailySlot(rotation, idx) % d.gr.length];
      daily = { idx: idx, sport: sport };
      $("sp-number").textContent = "Puzzle " + (idx + 1) + ", " + d.name;
      var saved = S.loadState(NAME);
      var ok = saved && saved.idx === idx && saved.sport === sport && saved.st.cells.every(function (n) { return !n || d.byName[n]; });
      begin(d, g, ok ? saved.st : null);
      var t = G.getGame(NAME).today;
      if (!ok && t && t.idx === idx && t.done) { st.done = true; st.won = !!t.won; paint(); showResult(false); }
    });
  }
  function startPractice() {
    mode = "practice";
    var sport = $("sp-sport").value;
    return S.load(sport).then(function (d) {
      var g = d.gr[Math.floor(Math.random() * d.gr.length)];
      daily = daily || { idx: 0, sport: sport };
      $("sp-number").textContent = "Practice, " + d.name;
      begin(d, g, null);
      $("sp-input").focus({ preventScroll: true });
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
      exclude: function (p) { return st && st.cells.indexOf(p.n) >= 0; },
      onPick: pick,
      onNone: function (v) { say(v ? "Choose a player from the list." : "", true); }
    });
    $("sp-form").addEventListener("submit", function (e) { e.preventDefault(); cmb.top(); });
    $("sp-mode-daily").addEventListener("click", function () { setMode("daily"); });
    $("sp-mode-practice").addEventListener("click", function () { setMode("practice"); });
    $("sp-practice-again").addEventListener("click", startPractice);
    $("sp-new").addEventListener("click", startPractice);
    $("sp-sport").addEventListener("change", startPractice);
    $("gl-giveup").addEventListener("click", function () { if (!st.done && window.confirm("End this grid and show the answers?")) finish(); });
    window.PLShareText = shareText;
    window.setInterval(tick, 30000);
  }

  S.index().then(function (ix) {
    rotation = ix.rotation || ["nba"];
    var sel = $("sp-sport");
    S.load(rotation[0]).then(function () {
      rotation.forEach(function (s) { var o = document.createElement("option"); o.value = s; o.textContent = s.toUpperCase(); sel.appendChild(o); });
      return G.ready;
    }).then(function () { wire(); return startDaily(); }).then(function () { $("sp-loading").hidden = true; $("sp-game").hidden = false; if (!st.done) $("sp-input").focus({ preventScroll: true }); }, function () {
      $("sp-loading").textContent = "Today's puzzle could not be loaded. Check your connection and reload the page.";
    });
  });
})();
