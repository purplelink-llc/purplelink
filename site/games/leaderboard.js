/* Leaderboards: all-time boards for every daily game (wins, best streak, average percentile) and the rating boards
   (all-time and this week) for Chess Puzzles, Sudoku Unlimited, Lockerlink, Gridlink and Under the Cap. */
(function () {
  "use strict";
  var G = window.PLGames, R = window.PLRating;
  if (!G || !R) return;
  var $ = function (id) { return document.getElementById(id); };
  var q = new URLSearchParams(window.location.search);
  var RATED = { chess: ["/games/chess-puzzles/", "chess-puzzles", "Play rated chess puzzles"], sudoku: ["/games/sudoku-unlimited/", "sudoku-unlimited", "Play rated Sudoku"],
    lockerlink: ["/games/lockerlink/", "lockerlink", "Play today's Lockerlink"], gridlink: ["/games/gridlink/", "gridlink", "Play today's Gridlink"], "under-the-cap": ["/games/under-the-cap/", "under-the-cap", "Play today's Under the Cap"] };
  var DAILY_BOARDS = [["wins", "Wins"], ["streak", "Best streak"], ["pct", "Average percentile"]];
  var RATED_BOARDS = [["all", "Rating"], ["week", "This week"]];
  var UNITS = { wins: "wins", streak: "days", pct: "%" };

  // A game is addressed as "daily:linkle" or "rated:chess". Older links carry a bare rated game, e.g. ?g=chess.
  function parseGame(v) {
    var m = /^(daily|rated):([a-z-]+)$/.exec(v || "");
    if (m && (m[1] === "daily" || RATED[m[2]]) && $("lb-game").querySelector('option[value="' + v + '"]')) return { kind: m[1], key: m[2] };
    if (RATED[v]) return { kind: "rated", key: v };
    return { kind: "daily", key: "linkle" };
  }
  var g0 = parseGame(q.get("g"));
  var st = { kind: g0.kind, key: g0.key, board: q.get("b") };

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }
  function boards() { return st.kind === "daily" ? DAILY_BOARDS : RATED_BOARDS; }
  function validBoard() { if (!boards().some(function (b) { return b[0] === st.board; })) st.board = boards()[0][0]; }
  function label() { var o = $("lb-game").querySelector('option[value="' + st.kind + ":" + st.key + '"]'); return o ? o.textContent : st.key; }

  function tabs() {
    validBoard();
    $("lb-game").value = st.kind + ":" + st.key;
    var box = $("lb-boards");
    box.textContent = "";
    boards().forEach(function (b) {
      var btn = el("button", "lb-tab", b[1]); btn.type = "button"; btn.setAttribute("data-board", b[0]);
      btn.setAttribute("aria-pressed", b[0] === st.board ? "true" : "false");
      btn.addEventListener("click", function () { st.board = b[0]; load(); });
      box.appendChild(btn);
    });
    var a = $("lb-play");
    if (st.kind === "rated") { var p = RATED[st.key]; a.href = p[0]; a.setAttribute("data-g", p[1]); a.textContent = p[2]; }
    else { a.href = "/games/" + st.key + "/"; a.setAttribute("data-g", st.key); a.textContent = "Play today's " + label(); }
    var url = window.location.pathname + "?g=" + st.kind + ":" + st.key + "&b=" + st.board;
    try { window.history.replaceState(null, "", url); } catch (e) { /* ignore */ }
    var wkEl = $("lb-week"); if (wkEl) wkEl.hidden = st.kind === "daily";
    var note = $("lb-note");
    note.hidden = st.kind !== "daily";
    note.textContent = st.kind === "daily" ? "Daily boards rank the results each player's browser reports. They are checked for what is possible, not replayed, so treat them as friendly competition." : "";
  }

  function scoreText(row) {
    if (st.kind === "daily") return st.board === "pct" ? row.v + "%" : String(row.v);
    return st.board === "week" ? (row.g >= 0 ? "+" : "−") + Math.abs(row.g) : String(row.r);
  }

  function render(data) {
    var list = $("lb-list"), status = $("lb-status");
    list.textContent = "";
    if (!data) { status.textContent = "The board could not be loaded. Try again in a moment."; return; }
    if (data.rows.length) status.textContent = "";
    else if (st.kind === "daily") status.textContent = "No one is listed on this board yet. Be the first." + (data.total ? " " + data.total + (data.total === 1 ? " player has" : " players have") + " results here so far." : "");
    else status.textContent = st.board === "week" ? "No one has three rated puzzles this week yet. Be the first." : "No one is on this board yet. Be the first.";
    data.rows.forEach(function (row) {
      var li = el("li", "lb-row"); if (row.rank <= 3) li.setAttribute("data-top", String(row.rank));
      if (st.kind === "daily" ? row.me : data.you && data.you.rank === row.rank) li.setAttribute("data-you", "");
      li.appendChild(el("span", "lb-rank", String(row.rank)));
      li.appendChild(el("span", "lb-name", row.name));
      li.appendChild(el("span", "lb-n", row.n + " played"));
      li.appendChild(el("b", "lb-score", scoreText(row)));
      list.appendChild(li);
    });
    var you = $("lb-you");
    if (!data.you) { you.hidden = true; return; }
    you.hidden = false;
    if (st.kind === "daily") {
      var what = st.board === "wins" ? data.you.v + (data.you.v === 1 ? " win" : " wins") : st.board === "streak" ? "a best streak of " + data.you.v + (data.you.v === 1 ? " day" : " days") : "an average percentile of " + data.you.v;
      you.textContent = "You are number " + data.you.rank + " of " + data.you.total + " with " + what + (data.you.total > 1 ? ", ahead of " + data.you.pct + "% of players" : "") + ".";
    } else you.textContent = "You are number " + data.you.rank + (st.board === "week" ? " this week, " + (data.you.g >= 0 ? "up " : "down ") + Math.abs(data.you.g) : " with " + data.you.r) + ".";
  }

  function join(data) {
    var box = $("lb-join"), s = G.session && G.session.get();
    box.textContent = "";
    function p(text) { var e = document.createElement("p"); e.textContent = text; box.appendChild(e); }
    function btn(text, fn) { var b = el("button", "gbtn gbtn--ghost", text); b.type = "button"; b.addEventListener("click", fn); box.appendChild(b); }
    var listed = !!(data && data.you && data.you.listed !== false);
    if (!s) { p("Sign in with an email link to keep your results on the server, see your rank and join the boards."); var a = el("a", "gbtn gbtn--ghost", "Sign in"); a.href = "/games/account/"; box.appendChild(a); return; }
    if (listed) { btn("Leave the leaderboards", function () { R.setPublic(false).then(function () { load(); }); }); return; }
    if (!s.name) { p("Choose a display name on your account page to appear here."); var a2 = el("a", "gbtn gbtn--ghost", "Choose a name"); a2.href = "/games/account/"; box.appendChild(a2); return; }
    p("You are not listed. Show " + s.name + " on the leaderboards?");
    btn("Show me on the leaderboards", function () {
      R.setPublic(true).then(function (res) { if (res.status === 200) load(); else p("That name cannot be shown. Choose another on your account page."); });
    });
  }

  var token = 0;
  function load() {
    tabs();
    var mine = ++token;
    $("lb-status").textContent = "Loading the board.";
    R.leaderboard(st.key, st.board).then(function (data) {
      if (mine !== token) return;                         // a newer choice has replaced this one
      render(data); join(data); if (window.PLDock) window.PLDock.paint();
    });
  }

  $("lb-game").addEventListener("change", function () {
    var m = /^(daily|rated):(.+)$/.exec($("lb-game").value);
    if (!m) return;
    st.kind = m[1]; st.key = m[2]; st.board = null; load();
  });
  var wk = $("lb-week");
  if (wk) { var d = new Date(), off = (d.getDay() + 6) % 7, mon = new Date(d.getFullYear(), d.getMonth(), d.getDate() - off); wk.textContent = "Week of " + mon.toLocaleDateString("en-US", { month: "long", day: "numeric" }); }
  (G.ready || Promise.resolve()).then(load);
})();
