/* Under the Cap: build a roster from any era under a budget, then play a full season and see whether it goes undefeated.
   The season is simulated from each player's rating (our own estimate of his best), a bonus for players who really were
   teammates, and a seeded random draw, so a daily roster always gives the same record. */
(function () {
  "use strict";
  var G = window.PLGames, S = window.PLSports, SE = window.PLSeason, NAME = "under-the-cap";
  var $ = function (id) { return document.getElementById(id); };
  var root = $("sp-root"), FX = window.PLFX;
  var st = null, data = null, daily = null, mode = "daily", rotation = ["nba"], rule = null, active = 0, lastRes = null;

  function P(n) { return data.byName[n]; }
  function cap() { return data.cfg.cap + (rule ? rule.cap : 0); }
  function slotCount() { return data.cfg.slots.length + data.cfg.bench; }
  function slotLabel(i) { return i < data.cfg.slots.length ? ((data.cfg.gname || {})[data.cfg.slots[i]] || data.cfg.slots[i]) : "Bench"; }
  function slotGroup(i) { return i < data.cfg.slots.length ? data.cfg.slots[i] : null; }
  function spent() { return st.r.reduce(function (a, n) { return a + (n ? SE.cost(P(n)) : 0); }, 0); }
  function roster() {
    var k = data.cfg.slots.length;
    return { starters: st.r.slice(0, k).map(function (n) { return n ? P(n) : null; }), bench: st.r.slice(k).map(function (n) { return n ? P(n) : null; }) };
  }
  function ready() { return st.r.slice(0, data.cfg.slots.length).every(Boolean); }
  function save() { if (mode === "daily" && daily) S.saveState(NAME, { idx: daily.idx, sport: daily.sport, st: st }); }
  function newState() { var r = []; for (var i = 0; i < slotCount(); i++) r.push(null); return { t0: Date.now(), r: r, done: false, res: null }; }

  function pct(x) { return x >= 0.1 ? (x * 100).toFixed(1) + "%" : x >= 0.0001 ? (x * 100).toFixed(2) + "%" : x > 0 ? "under 0.01%" : "0%"; }

  function paintSlots() {
    var ol = $("ub-slots"); ol.innerHTML = "";
    st.r.forEach(function (n, i) {
      var li = document.createElement("li"), b = document.createElement("button");
      b.type = "button"; b.className = "ub-slot" + (i === active && !st.done ? " is-active" : "") + (n ? " is-filled" : "") + (i >= data.cfg.slots.length ? " is-bench" : "");
      b.disabled = st.done;
      var lab = document.createElement("span"); lab.className = "ub-slot-label"; lab.textContent = slotLabel(i);
      var nm = document.createElement("span"); nm.className = "ub-slot-name"; nm.textContent = n || "Empty";
      b.appendChild(lab); b.appendChild(nm);
      if (n) { var m = document.createElement("span"); m.className = "ub-slot-meta"; m.textContent = "Rating " + P(n).ovr + ", cost " + SE.cost(P(n)); b.appendChild(m); }
      b.setAttribute("aria-label", slotLabel(i) + ": " + (n ? n + ". Tap to replace." : "empty. Tap to choose."));
      b.addEventListener("click", function () { active = i; paintSlots(); paintOptions(); $("ub-search").focus({ preventScroll: true }); });
      li.appendChild(b); ol.appendChild(li);
    });
  }

  function paintMeters() {
    var left = cap() - spent();
    $("ub-budget").textContent = left + " of " + cap();
    $("ub-budget").parentNode.classList.toggle("is-low", left < 0);
    var r = roster(), s = SE.strength(data, r), filled = r.starters.filter(Boolean).length;
    $("ub-rating").textContent = filled ? s.rating.toFixed(1) : "none yet";
    $("ub-chem").textContent = s.chem.pairs ? s.chem.pairs + (s.chem.pairs === 1 ? " pair" : " pairs") + " played together" : "none yet";
    $("ub-picker").hidden = st.done;
    $("ub-play").disabled = st.done || !ready();
    $("ub-play").textContent = ready() ? "Play the season" : "Fill every starting spot";
  }

  function eligible(p, i) {
    if (st.r.indexOf(p.n) >= 0 && st.r[i] !== p.n) return false;
    var g = slotGroup(i); if (g && p.g !== g) return false;
    return rule.ok(p);
  }

  // Points that must stay free so every other empty starting spot can still be filled with its cheapest eligible player.
  function reserve(skip) {
    var total = 0;
    for (var i = 0; i < data.cfg.slots.length; i++) {
      if (i === skip || st.r[i]) continue;
      var best = 99;
      data.players.forEach(function (p) { if (eligible(p, i) && st.r.indexOf(p.n) < 0) best = Math.min(best, SE.cost(p)); });
      total += best === 99 ? 0 : best;
    }
    return total;
  }

  function paintOptions() {
    var ul = $("ub-options"); ul.innerHTML = "";
    $("ub-picker-title").textContent = "Choose: " + slotLabel(active);
    var q = S.fold($("ub-search").value), toks = q.split(" ").filter(Boolean);
    var list = data.players.filter(function (p) { return eligible(p, active) && toks.every(function (t) { return p.key.indexOf(t) >= 0; }); });
    var held = reserve(active);
    var left = cap() - spent() + (st.r[active] ? SE.cost(P(st.r[active])) : 0) - held;
    $("ub-reserve").textContent = held ? "Keep " + held + " in budget for your other empty starting spots." : "";
    list.sort(function (a, b) { return (SE.cost(b) <= left) - (SE.cost(a) <= left) || b.ovr - a.ovr || (a.n < b.n ? -1 : 1); });
    $("ub-picker").hidden = st.done;
    list.slice(0, 40).forEach(function (p) {
      var li = document.createElement("li"), b = document.createElement("button");
      b.type = "button"; b.className = "ub-opt"; var c = SE.cost(p);
      b.disabled = c > left;
      b.innerHTML = "";
      var n = document.createElement("span"); n.className = "ub-opt-name"; n.textContent = p.n;
      var m = document.createElement("span"); m.className = "ub-opt-meta"; m.textContent = p.pos + ", " + S.career(p) + ". Rating " + p.ovr + (S.honorsText(data, p) ? ". " + S.honorsText(data, p) : "");
      var k = document.createElement("span"); k.className = "ub-opt-cost"; k.textContent = "Cost " + c;
      b.appendChild(n); b.appendChild(m); b.appendChild(k);
      if (c > left) b.setAttribute("aria-label", p.n + ", cost " + c + ", more than you can spend and still fill every starting spot");
      b.addEventListener("click", function () { place(p); });
      li.appendChild(b); ul.appendChild(li);
    });
    $("ub-none").hidden = list.length > 0;
    $("ub-more").textContent = list.length > 40 ? "Showing the 40 highest rated of " + list.length + ". Type to narrow the list." : "";
  }

  function place(p) {
    if (st.done) return;
    st.r[active] = p.n;
    if (FX) { FX.play("place"); FX.vibrate(12); }
    var next = st.r.indexOf(null); if (next >= 0) active = next;
    $("ub-search").value = "";
    paintSlots(); paintMeters(); paintOptions(); save();
    $("ub-msg").textContent = p.n + " added at " + slotLabel(next >= 0 ? active : active) + ".";
  }

  function play() {
    if (!ready() || st.done) return;
    var seed = mode === "daily" ? "d" + daily.idx + data.sport + "|" + st.r.join("|") : "p" + Date.now();
    var res = SE.simulate(data, roster(), seed);
    st.res = res; st.done = true;
    var fresh = mode === "daily" && !(G.getGame(NAME).today && G.getGame(NAME).today.idx === daily.idx && G.getGame(NAME).today.done);
    save();
    if (mode === "daily" && fresh) {
      var hist = S.loadState(NAME + "-hist") || {}; hist[daily.idx] = { w: res.wins, l: res.losses, c: res.champion ? 1 : 0, r: Math.round(res.rating * 10) / 10, p: res.perfect, o: outcomeFor(res, data) };
      Object.keys(hist).sort(function (a, b) { return a - b; }).slice(0, -60).forEach(function (k) { delete hist[k]; }); S.saveState(NAME + "-hist", hist);
      var saved = G.getGame(NAME), tries = Math.min(98, res.losses) + 1;
      saved.stats = G.recordResult(saved.stats, daily.idx, res.champion, tries);
      saved.today = { idx: daily.idx, done: true, won: res.champion };
      G.setGame(NAME, saved);
      G.track("game_end", NAME + ":" + (res.champion ? "win" : "loss"));
      if (window.PLAch) window.PLAch.check({ game: NAME, idx: daily.idx, won: res.champion, tries: tries, losses: res.losses });
      G.submitScore(NAME, daily.idx, Math.min(98, res.losses)).then(function (r2) { $("sp-pct").textContent = G.describePercentile(r2); });
      if (window.PLRating) window.PLRating.report(NAME, { idx: daily.idx, sport: daily.sport, ms: S.elapsed(st.t0), wins: res.wins, games: data.cfg.games, champion: res.champion, roster: st.r.map(function (n) { return n || ""; }) }).then(function (x) { S.paintRating(NAME, x); });
    }
    paintSlots(); paintMeters();
    showResult(res, fresh);
    if (res.losses === 0 && window.PLConfetti) window.PLConfetti.big(); else if (res.champion && window.PLConfetti) window.PLConfetti.small();
    if (FX) FX.play(res.losses === 0 ? "big" : res.champion ? "win" : "lose");
  }

  function recordText(res) { return res.wins + "-" + res.losses; }
  function outcomeFor(res, d) {
    if (res.losses === 0) return "undefeated, and " + (res.champion ? "won the title" : "went out in the playoffs");
    if (!res.made) return "missed the playoffs";
    if (res.champion) return "won the title";
    var lost = res.playoffs.filter(function (x) { return !x.won; })[0];
    return "lost in playoff round " + (lost ? lost.round : "1") + " of " + d.cfg.rounds.length;
  }
  function outcomeText(res) {
    if (res.losses === 0) return "Undefeated. A perfect season, and " + (res.champion ? "the title." : "an early playoff exit.");
    if (!res.made) return "Missed the playoffs.";
    if (res.champion) return "Champions.";
    var lost = res.playoffs.filter(function (x) { return !x.won; })[0];
    return "Lost in playoff round " + (lost ? lost.round : "1") + " of " + data.cfg.rounds.length + ".";
  }

  function showResult(res, fresh) {
    var box = $("sp-result"); box.hidden = false;
    $("sp-result-head").textContent = recordText(res) + ". " + outcomeText(res);
    $("ub-record").textContent = "";
    var big = $("ub-record");
    big.textContent = res.wins + "-" + res.losses; FX && FX.kick(big, "fx-pop", 300);
    var lines = [
      "Best winning streak: " + res.streak + (res.streak === data.cfg.games ? " (every game)" : "") + ".",
      "Team rating " + res.rating.toFixed(1) + ", average chance to win a game " + Math.round(res.avgP * 100) + "%.",
      "Chance of going " + data.cfg.games + "-0 with this roster: " + pct(res.perfect) + "."
    ];
    if (res.firstLoss) lines.push("First loss came in game " + res.firstLoss + ".");
    $("ub-detail").innerHTML = "";
    lines.forEach(function (t) { var li = document.createElement("li"); li.textContent = t; $("ub-detail").appendChild(li); });
    var po = $("ub-playoffs"); po.innerHTML = "";
    res.playoffs.forEach(function (x) {
      var li = document.createElement("li");
      li.textContent = "Round " + x.round + (x.games === 1 ? ": " : ", best of " + x.games + ": ") + (x.won ? "won" : "lost") + (x.games === 1 ? "" : " " + (x.won ? x.a + "-" + x.b : x.b + "-" + x.a));
      po.appendChild(li);
    });
    $("ub-playoffs-wrap").hidden = !res.playoffs.length;
    var s = G.getGame(NAME).stats || G.emptyStats(), d_ = mode === "daily";
    $("sp-statline").hidden = !d_;
    $("sp-played").textContent = s.played; $("sp-winpct").textContent = s.played ? Math.round(100 * s.won / s.played) + "%" : "0%";
    $("sp-streak").textContent = s.streak; $("sp-max").textContent = s.max;
    G.paintNote($("sp-saver"), s, daily.idx, !!d_, NAME);
    $("sp-next-line").hidden = !d_;
    $("sp-practice-again").hidden = false;
    $("sp-practice-again").textContent = d_ ? "Try a practice roster" : "Build another roster";
    if (!fresh && d_) S.paintRating(NAME, null);
    renderWeek();
    tick();
    if (fresh) box.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
  function tick() {
    var el = $("sp-next-in"); if (!el) return;
    var now = new Date(), nx = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1), ms = nx - now;
    el.textContent = Math.floor(ms / 3600000) + " h " + ("0" + Math.floor((ms % 3600000) / 60000)).slice(-2) + " min";
  }

  function shareText() {
    var res = st.res; if (!res) return "";
    var tag = mode === "daily" ? "#" + (daily.idx + 1) + " " : "practice ";
    return "Under the Cap " + tag + data.name + "\n" + recordText(res) + ", " + outcomeText(res).toLowerCase() + "\nChance of " + data.cfg.games + "-0: " + pct(res.perfect) + "\n\n" + root.getAttribute("data-url");
  }

  function begin(d, saved) {
    data = d;
    $("sp-result").hidden = true; $("sp-msg") && ($("sp-msg").textContent = ""); $("sp-pct").textContent = "";
    st = saved || newState();
    active = Math.max(0, st.r.indexOf(null));
    $("ub-rule-name").textContent = rule.name; $("ub-rule-text").textContent = rule.text;
    $("ub-search").value = "";
    paintSlots(); paintMeters(); paintOptions();
    if (st.done && st.res) showResult(st.res, false);
  }

  function startDaily() {
    mode = "daily";
    var idx = S.dayIdx(), sport = S.dailySport(rotation, idx);
    return S.load(sport).then(function (d) {
      daily = { idx: idx, sport: sport };
      rule = SE.constraint(d, new Date().getDay());
      $("sp-number").textContent = "Puzzle " + (idx + 1) + ", " + d.name;
      var saved = S.loadState(NAME);
      var ok = saved && saved.idx === idx && saved.sport === sport && saved.st.r.every(function (n) { return !n || d.byName[n]; });
      begin(d, ok ? saved.st : null);
      var t = G.getGame(NAME).today;
      if (!ok && t && t.idx === idx && t.done) { $("ub-play").disabled = true; $("sp-result").hidden = false; $("sp-result-head").textContent = "You played today's season"; $("sp-reveal").textContent = "Your roster is saved on the device you played on."; $("sp-practice-again").hidden = false; }
    });
  }
  function startPractice() {
    mode = "practice";
    var sport = $("sp-sport").value;
    return S.load(sport).then(function (d) {
      rule = SE.constraint(d, 1);
      daily = daily || { idx: 0, sport: sport };
      $("sp-number").textContent = "Practice, " + d.name;
      begin(d, null);
    });
  }
  function setMode(m) {
    $("sp-mode-daily").setAttribute("aria-pressed", m === "daily" ? "true" : "false");
    $("sp-mode-practice").setAttribute("aria-pressed", m === "practice" ? "true" : "false");
    $("sp-practice-opts").hidden = m !== "practice";
    return m === "daily" ? startDaily() : startPractice();
  }

  // ---- the week's best rosters ----
  var rosterCache = {};
  function rostersOf(sport) {
    return rosterCache[sport] || (rosterCache[sport] = Promise.all([S.load(sport), fetch("/games/data/sports-" + sport + "-rosters.json").then(function (r) { return r.json(); })]).then(function (x) { return { d: x[0], b: x[1].b }; }));
  }
  function weekRow(i, today, hist, todayDone) {
    var li = document.createElement("li"); li.className = "tw-day";
    var sport = rotation[((i % rotation.length) + rotation.length) % rotation.length], dow = i % 7;
    return rostersOf(sport).then(function (x) {
      var d = x.d, rule = SE.constraint(d, dow), pick = x.b[String(dow)], cap = d.cfg.cap + rule.cap;
      var head = document.createElement("p"); head.className = "tw-head";
      var b = document.createElement("strong"); b.textContent = S.dayLabel(i) + ", " + d.name + ": " + rule.name; head.appendChild(b);
      head.appendChild(document.createTextNode(". " + rule.text + " Budget " + cap + "."));
      li.appendChild(head);
      var mine = hist[i], you = document.createElement("p"); you.className = "tw-you";
      you.textContent = mine ? "Your season: " + mine.w + "-" + mine.l + ", " + mine.o + " (team rating " + mine.r + ")." : "You did not play this day.";
      if (i === today && !todayDone) { you.textContent = "Today's best roster is shown here once you finish today's puzzle, or tomorrow."; li.appendChild(you); return li; }
      li.appendChild(you);
      if (!pick) return li;
      var players = pick.s.concat(pick.b).map(function (n) { return d.byName[n]; });
      var starters = players.slice(0, pick.s.length), bench = players.slice(pick.s.length);
      var seed = "d" + i + d.sport + "|" + pick.s.concat(pick.b).concat(new Array(Math.max(0, d.cfg.slots.length + d.cfg.bench - pick.s.length - pick.b.length)).fill("")).join("|");
      var res = SE.simulate(d, { starters: starters, bench: bench }, seed), spent = players.reduce(function (a, p) { return a + SE.cost(p); }, 0);
      var sum = document.createElement("p"); sum.className = "tw-head";
      sum.textContent = "Highest-rated roster we could build (cost " + spent + " of " + cap + "): team rating " + res.rating.toFixed(1) + ". Played out, it goes " + res.wins + "-" + res.losses + " and " + outcomeFor(res, d) + ". Chance of " + d.cfg.games + "-0: " + pct(res.perfect) + ".";
      li.appendChild(sum);
      var ol = document.createElement("ol"); ol.className = "tw-chain";
      players.forEach(function (p, k) {
        var c = document.createElement("li"), lab = k < d.cfg.slots.length ? ((d.cfg.gname || {})[d.cfg.slots[k]] || d.cfg.slots[k]) : "Bench";
        c.textContent = lab + ": " + p.n;
        var m = document.createElement("span"); m.className = "tw-hop"; m.textContent = "Rating " + p.ovr + ", cost " + SE.cost(p) + (S.honorsText(d, p) ? ". " + S.honorsText(d, p) : ""); c.appendChild(m);
        ol.appendChild(c);
      });
      li.appendChild(ol);
      return li;
    });
  }
  function renderWeek() {
    var box = $("ub-week-list"), prev = $("ub-week-prev"); if (!box || !rotation.length) return;
    var w = S.weekRange(), today = w.today, start = w.start;
    var hist = S.loadState(NAME + "-hist") || {}, t = G.getGame(NAME).today, todayDone = !!(t && t.idx === today && t.done);
    function fill(ul, from, to) {
      ul.innerHTML = "";
      var ids = []; for (var i = from; i <= to; i++) if (i >= 0) ids.push(i);
      return Promise.all(ids.map(function (i) { return weekRow(i, today, hist, todayDone); })).then(function (rows) { rows.forEach(function (r) { ul.appendChild(r); }); return rows.length; });
    }
    fill(box, start, today).then(function (n) { $("ub-week").hidden = !n; });
    fill(prev, start - 7, start - 1).then(function (n) { $("ub-week-prev-wrap").hidden = !n; });
  }

  function wire() {
    $("ub-search").addEventListener("input", paintOptions);
    $("ub-play").addEventListener("click", play);
    $("sp-mode-daily").addEventListener("click", function () { setMode("daily"); });
    $("sp-mode-practice").addEventListener("click", function () { setMode("practice"); });
    $("sp-practice-again").addEventListener("click", function () { $("sp-mode-practice").setAttribute("aria-pressed", "true"); $("sp-mode-daily").setAttribute("aria-pressed", "false"); $("sp-practice-opts").hidden = false; startPractice(); window.scrollTo({ top: 0 }); });
    $("sp-new").addEventListener("click", startPractice);
    $("sp-sport").addEventListener("change", startPractice);
    $("ub-clear").addEventListener("click", function () { if (st.done) return; st.r = newState().r; active = 0; paintSlots(); paintMeters(); paintOptions(); save(); });
    window.PLShareText = shareText;
    window.setInterval(tick, 30000);
  }

  S.index().then(function (ix) {
    rotation = ix.rotation || ["nba"];
    var sel = $("sp-sport");
    S.load(rotation[0]).then(function () {
      rotation.forEach(function (s) { var o = document.createElement("option"); o.value = s; o.textContent = s.toUpperCase(); sel.appendChild(o); });
      return G.ready;
    }).then(function () { wire(); renderWeek(); return startDaily(); }).then(function () { $("sp-loading").hidden = true; $("sp-game").hidden = false; }, function () {
      $("sp-loading").textContent = "Today's puzzle could not be loaded. Check your connection and reload the page.";
    });
  });
})();
