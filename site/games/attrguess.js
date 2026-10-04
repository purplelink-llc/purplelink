/* Attribute-guess engine: Landlink (countries), Atomlink (elements) and Prizelink (Nobel laureates).
   Guess a name from the list; each column of your guess is compared with the day's answer: same, close (with an
   arrow for numbers) or different. The page names its data set in #ag-root[data-ds]. */
(function () {
  "use strict";
  var G = window.PLGames, root = document.getElementById("ag-root");
  if (!G || !root) return;
  var NAME = root.getAttribute("data-ds"), EPOCH = "2026-10-04";
  // Weekday twists, keyed by getDay() (Sunday = 0), the same days as Linkle's. `max` is the guess limit.
  var TWISTS = {
    0: { name: "Hard mode", hard: true, text: "Every guess must be a possible answer, given the clues you already have." },
    1: { name: "Standard", text: "Standard rules today." },
    2: { name: "Head start", head: true },
    3: { name: "Extra guesses", max: 10, text: "You have ten guesses today." },
    4: { name: "Fog", fog: true },
    5: { name: "Compass off", noArrows: true, text: "No arrows today. Numbers show only the colors." },
    6: { name: "Quick draw", max: 6, text: "You have six guesses today." }
  };
  var $ = function (id) { return document.getElementById(id); };
  var data = null, st = { max: 8, twist: TWISTS[1], fogCol: -1, headCol: -1, idx: 0, ans: 0, guesses: [], done: false, won: false, busy: false, matches: [], active: -1 };

  // ---- formatting ----
  function compact(n) {
    if (n === null || n === undefined) return "?";
    var a = Math.abs(n);
    if (a >= 1e9) return (n / 1e9).toFixed(a >= 1e10 ? 0 : 1).replace(/\.0$/, "") + "B";
    if (a >= 1e6) return (n / 1e6).toFixed(a >= 1e7 ? 0 : 1).replace(/\.0$/, "") + "M";
    if (a >= 1e3) return (n / 1e3).toFixed(a >= 1e4 ? 0 : 1).replace(/\.0$/, "") + "K";
    return String(Math.round(n));
  }
  function fmt(col, v) {
    if (v === null || v === undefined) return "Unknown";
    if (Array.isArray(v)) return v.join(", ");
    switch (col.f) {
      case "lat": return Math.abs(v).toFixed(1) + "\u00b0" + (v >= 0 ? "N" : "S");
      case "lon": return Math.abs(v).toFixed(1) + "\u00b0" + (v >= 0 ? "E" : "W");
      case "life": return v === null ? "Living" : v + " yrs";
      case "km": return Math.round(v).toLocaleString("en-US") + " km";
      case "kg": return v >= 1000 ? (v / 1000).toFixed(v >= 10000 ? 0 : 1).replace(/\.0$/, "") + " t" : v >= 1 ? (Math.round(v * 10) / 10) + " kg" : Math.round(v * 1000) + " g";
      case "yrs": return v + " yrs";
      case "m": return Math.round(v).toLocaleString("en-US") + " m";
      case "pop": return compact(v);
      case "area": return compact(v) + " km²";
      case "mass": return String(Math.round(v * 10) / 10);
      case "ayear": return v <= -1000 ? "Ancient" : String(v);
      default: return String(v);
    }
  }

  // ---- comparison: returns { s: "c"|"p"|"a", dir: "up"|"down"|"" } ----
  function compare(col, g, a) {
    if (col.t === "num") {
      if (g === null || a === null || g === undefined || a === undefined) return { s: g === a ? "c" : "a", dir: "" };
      if (g === a) return { s: "c", dir: "" };
      var close = col.rel !== undefined ? Math.abs(g - a) / Math.max(Math.abs(a), 1) <= col.rel : Math.abs(g - a) <= (col.abs || 0);
      return { s: close ? "p" : "a", dir: a > g ? "up" : "down" };
    }
    if (col.t === "set") {
      var inter = g.filter(function (x) { return a.indexOf(x) >= 0; }).length;
      return { s: inter === g.length && inter === a.length ? "c" : inter ? "p" : "a", dir: "" };
    }
    return { s: g === a ? "c" : "a", dir: "" };
  }

  // ---- searching the list ----
  function norm(s) { return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9 ]/g, ""); }
  function find(q) {
    q = norm(q.trim());
    if (!q) return [];
    var starts = [], inside = [];
    data.rows.forEach(function (r, i) {
      if (st.guesses.indexOf(i) >= 0) return;
      var keys = [r.n].concat(r.a || []).map(norm), hit = 0;
      keys.forEach(function (k, j) { if (k.indexOf(q) === 0) hit = Math.max(hit, 2); else if (k.indexOf(q) >= 0 || (j === 0 && k.split(" ").some(function (w) { return w.indexOf(q) === 0; }))) hit = Math.max(hit, 1); });
      if (hit === 2) starts.push(i); else if (hit === 1) inside.push(i);
    });
    return starts.concat(inside).slice(0, 8);
  }
  function showList() {
    var list = $("ag-list"), input = $("ag-input");
    st.matches = find(input.value);
    list.textContent = "";
    st.active = st.matches.length ? 0 : -1;
    st.matches.forEach(function (i, k) {
      var li = document.createElement("li");
      li.id = "ag-opt-" + k; li.setAttribute("role", "option"); li.textContent = data.rows[i].n;
      if (k === 0) li.setAttribute("aria-selected", "true");
      li.addEventListener("mousedown", function (e) { e.preventDefault(); submit(i); });
      list.appendChild(li);
    });
    list.hidden = !st.matches.length;
    input.setAttribute("aria-expanded", st.matches.length ? "true" : "false");
    if (st.matches.length) input.setAttribute("aria-activedescendant", "ag-opt-0"); else input.removeAttribute("aria-activedescendant");
  }
  function moveActive(d) {
    if (!st.matches.length) return;
    var opts = $("ag-list").children;
    opts[st.active].removeAttribute("aria-selected");
    st.active = (st.active + d + st.matches.length) % st.matches.length;
    opts[st.active].setAttribute("aria-selected", "true");
    $("ag-input").setAttribute("aria-activedescendant", opts[st.active].id);
    opts[st.active].scrollIntoView({ block: "nearest" });
  }

  // ---- drawing ----
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }
  function buildHead() {
    var head = $("ag-head"); head.textContent = "";
    head.appendChild(el("span", "ag-name ag-h", "Guess"));
    data.cols.forEach(function (c) { head.appendChild(el("span", "ag-cell ag-h", c.l)); });
  }
  function rowFor(i, reveal, pos) {
    var r = data.rows[i], ans = data.rows[st.ans], li = el("li", "ag-row");
    li.appendChild(el("span", "ag-name", r.n));
    var cells = [];
    data.cols.forEach(function (c, k) {
      var res = compare(c, r.v[k], ans.v[k]), cell = el("span", "ag-cell");
      var fogged = st.twist.fog && k === st.fogCol && pos !== undefined && pos < 3 && !st.done;
      if (st.twist.noArrows) res = { s: res.s, dir: "" };
      if (fogged) res = { s: res.s, dir: "" };
      cell.setAttribute("data-s", reveal ? "" : res.s);
      if (res.dir) cell.setAttribute("data-dir", res.dir);
      var label = el("span", "visually-hidden", c.l + ": ");
      cell.appendChild(label);
      cell.appendChild(document.createTextNode(fogged ? "?" : fmt(c, r.v[k])));
      if (res.dir) { var ar = el("span", "ag-arrow", res.dir === "up" ? "↑" : "↓"); ar.setAttribute("aria-hidden", "true"); cell.appendChild(ar); }
      var word = res.s === "c" ? "correct" : res.s === "p" ? (res.dir ? "close, answer is " + (res.dir === "up" ? "higher" : "lower") : "partly right") : (res.dir ? "answer is " + (res.dir === "up" ? "higher" : "lower") : "wrong");
      cell.appendChild(el("span", "visually-hidden", ", " + word));
      cell._s = res.s;
      cells.push(cell); li.appendChild(cell);
    });
    li._cells = cells;
    return li;
  }
  function paintAll() {
    var rows = $("ag-rows"); rows.textContent = "";
    st.guesses.slice().reverse().forEach(function (i) { rows.appendChild(rowFor(i, false, st.guesses.indexOf(i))); });
    $("ag-count").textContent = st.done ? "" : "Guess " + (st.guesses.length + 1) + " of " + st.max;
    $("ag-wrap").hidden = !st.guesses.length;
    hint();
  }
  function hint() {
    var ans = data.rows[st.ans].n, n = st.guesses.length, t = "";
    if (!st.done && n >= 4) t = "Hint: the name starts with " + ans[0] + (n >= 6 ? " and has " + ans.length + " letters." : ".");
    $("ag-hint").textContent = t;
  }

  // Hard mode: could this name be the answer? It must give every earlier guess the same clues the real answer did.
  function inconsistent(i) {
    var cand = data.rows[i], ans = data.rows[st.ans];
    for (var j = 0; j < st.guesses.length; j++) {
      var g = data.rows[st.guesses[j]];
      for (var k = 0; k < data.cols.length; k++) {
        var want = compare(data.cols[k], g.v[k], ans.v[k]), got = compare(data.cols[k], g.v[k], cand.v[k]);
        if (want.s !== got.s || want.dir !== got.dir) return data.cols[k].l.toLowerCase();
      }
    }
    return "";
  }

  // ---- play ----
  function persist() {
    var s = G.getGame(NAME);
    s.today = { idx: st.idx, guesses: st.guesses.slice(), done: st.done, won: st.won };
    G.setGame(NAME, s);
  }
  function submit(i) {
    if (st.done || st.busy || i === undefined || st.guesses.indexOf(i) >= 0) return;
    if (st.twist.hard) {
      var bad = inconsistent(i);
      if (bad) { $("ag-msg").textContent = "Hard mode: " + data.rows[i].n + " cannot be the answer, because of the " + bad + " clue."; if (window.PLFX) { window.PLFX.play("bad"); window.PLFX.vibrate(30); window.PLFX.kick($("ag-form"), "fx-shake", 400); } return; }
    }
    if (!st.guesses.length) G.track("game_start", NAME);
    st.guesses.push(i);
    st.won = i === st.ans;
    st.done = st.won || st.guesses.length >= st.max;
    persist();
    var rows = $("ag-rows"), li = rowFor(i, true, st.guesses.length - 1), FX = window.PLFX;
    rows.insertBefore(li, rows.firstChild);
    $("ag-wrap").hidden = false;
    $("ag-input").value = ""; showList();
    var wait = 0;
    li._cells.forEach(function (c, k) {
      var s = c._s;
      if (!FX || FX.reduced()) { c.setAttribute("data-s", s); return; }
      c.style.animationDelay = (k * 120) + "ms";
      FX.kick(c, "fx-flip", 900);
      window.setTimeout(function () { c.setAttribute("data-s", s); }, k * 120 + 250);
      window.setTimeout(function () { FX.play("flip", k); }, k * 120 + 220);
      wait = k * 120 + 520;
    });
    $("ag-count").textContent = st.done ? "" : "Guess " + (st.guesses.length + 1) + " of " + st.max;
    hint();
    st.busy = true;
    window.setTimeout(function () {
      st.busy = false;
      if (st.done) finish(true);
      else if (FX && li._cells.every(function (c) { return c._s === "c"; })) FX.play("good");
    }, wait);
  }

  function shareText() {
    var rows = st.guesses.map(function (i) {
      return data.cols.map(function (c, k) { var s = compare(c, data.rows[i].v[k], data.rows[st.ans].v[k]).s; return s === "c" ? "■" : s === "p" ? "▣" : "□"; }).join("");
    });
    return $("ag-title").textContent + " " + (st.idx + 1) + (st.twist.name !== "Standard" ? " (" + st.twist.name + ")" : "") + " " + (st.won ? st.guesses.length : "X") + "/" + st.max + "\n\n" + rows.join("\n") + "\n\n" + root.getAttribute("data-url");
  }

  function finish(fresh) {
    var saved = G.getGame(NAME);
    if (fresh) {
      saved.stats = G.recordResult(saved.stats, st.idx, st.won, st.guesses.length);
      G.setGame(NAME, saved);
      G.track("game_end", NAME + ":" + (st.won ? "win" : "loss"));
      if (st.won && window.PLConfetti) window.PLConfetti[st.guesses.length <= 3 ? "big" : "small"]();
      var ctx = { game: NAME, idx: st.idx, won: st.won, tries: st.guesses.length };
      if (window.PLAch) window.PLAch.check(ctx);
      G.submitScore(NAME, st.idx, st.won ? st.guesses.length : 99).then(function (res) {
        $("ag-pct").textContent = G.describePercentile(res);
        if (res && window.PLAch) window.PLAch.check({ game: NAME, idx: st.idx, won: st.won, tries: st.guesses.length, pct: res.percentile, total: res.total });
      });
    }
    var s = saved.stats || G.emptyStats();
    $("ag-form").hidden = true;
    var box = $("ag-result"); box.hidden = false;
    $("ag-result-head").textContent = st.won ? "Solved in " + st.guesses.length + " of " + st.max : "Out of guesses";
    var tm = $("ag-tomorrow"); if (tm) tm.textContent = "Tomorrow's twist: " + TWISTS[(new Date().getDay() + 1) % 7].name + ".";
    $("ag-reveal").textContent = st.won ? "" : "The answer was " + data.rows[st.ans].n + ".";
    $("ag-played").textContent = s.played; $("ag-winpct").textContent = s.played ? Math.round(100 * s.won / s.played) + "%" : "0%";
    $("ag-streak").textContent = s.streak; $("ag-max").textContent = s.max;
    var sv = $("ag-saver"); if (sv) sv.textContent = G.saverNote(s, st.idx);
    if (!st.won && !$("ag-rows").querySelector(".ag-answer")) {
      var li = rowFor(st.ans, false); li.classList.add("ag-answer"); $("ag-rows").insertBefore(li, $("ag-rows").firstChild); $("ag-wrap").hidden = false;
    }
    tick();
    if (fresh) box.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
  function tick() {
    var el = $("ag-next-in"); if (!el || $("ag-result").hidden) return;
    var now = new Date(), nx = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1), ms = nx - now;
    el.textContent = Math.floor(ms / 3600000) + " h " + ("0" + Math.floor((ms % 3600000) / 60000)).slice(-2) + " min";
  }

  function wire() {
    var input = $("ag-input");
    input.addEventListener("input", showList);
    input.addEventListener("focus", showList);
    input.addEventListener("blur", function () { window.setTimeout(function () { $("ag-list").hidden = true; input.setAttribute("aria-expanded", "false"); }, 120); });
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { e.preventDefault(); moveActive(1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); moveActive(-1); }
      else if (e.key === "Escape") { $("ag-list").hidden = true; }
      else if (e.key === "Enter") { e.preventDefault(); if (st.matches.length) submit(st.matches[st.active]); else { $("ag-msg").textContent = "Choose a name from the list."; } }
      if (e.key.length === 1 || e.key === "Backspace") $("ag-msg").textContent = "";
    });
    $("ag-form").addEventListener("submit", function (e) {
      e.preventDefault();
      if (st.matches.length) submit(st.matches[Math.max(0, st.active)]); else $("ag-msg").textContent = "Choose a name from the list.";
    });
    window.PLShareText = shareText;   // the share row (share.js) reads this when the player taps a button
    window.setInterval(tick, 30000);
  }

  function start(d) {
    data = d;
    st.idx = G.dayIndex(new Date(), d.epoch || EPOCH);
    var seq = G.decodeText(d.seq).split(",");
    st.ans = Number(seq[((st.idx % seq.length) + seq.length) % seq.length]);
    root.setAttribute("data-cols", String(d.cols.length));
    st.twist = TWISTS[new Date().getDay()]; st.max = st.twist.max || 8;
    st.fogCol = (st.idx * 3 + 1) % d.cols.length; st.headCol = st.idx % Math.min(3, d.cols.length);
    var tw = $("ag-twist");
    if (tw) {
      var ans = data.rows[st.ans], text = st.twist.text;
      if (st.twist.head) text = "The answer's " + d.cols[st.headCol].l.toLowerCase() + " is " + fmt(d.cols[st.headCol], ans.v[st.headCol]) + ".";
      if (st.twist.fog) text = "The " + d.cols[st.fogCol].l.toLowerCase() + " column is hidden in your first three guesses.";
      $("ag-twist-name").textContent = st.twist.name; $("ag-twist-text").textContent = text; tw.hidden = false;
    }
    $("ag-number").textContent = "Puzzle " + (st.idx + 1);
    buildHead();
    var saved = G.getGame(NAME).today;
    if (saved && saved.idx === st.idx) { st.guesses = (saved.guesses || []).filter(function (i) { return data.rows[i]; }); st.done = !!saved.done; st.won = !!saved.won; }
    wire(); paintAll();
    $("ag-loading").hidden = true; $("ag-game").hidden = false;
    if (st.done) finish(false); else $("ag-input").focus({ preventScroll: true });
  }

  fetch("/games/data/" + NAME + ".json").then(function (r) { if (!r.ok) throw 0; return r.json(); }).then(function (d) { return G.ready.then(function () { start(d); }); }, function () {
    $("ag-loading").textContent = "Today's puzzle could not be loaded. Check your connection and reload the page.";
  });
})();
