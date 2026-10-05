/* Leaderboards: the top 100 by rating and by rating gained this week, for Chess Puzzles, Sudoku Unlimited, Lockerlink, Gridlink and Unbeaten. */
(function () {
  "use strict";
  var G = window.PLGames, R = window.PLRating;
  if (!G || !R) return;
  var $ = function (id) { return document.getElementById(id); };
  var q = new URLSearchParams(window.location.search);
  var GAMES = ["chess", "sudoku", "lockerlink", "gridlink", "unbeaten"];
  var st = { game: GAMES.indexOf(q.get("g")) >= 0 ? q.get("g") : "chess", board: q.get("b") === "week" ? "week" : "all" };
  var PAGES = { chess: ["/games/chess-puzzles/", "chess-puzzles", "Play rated chess puzzles"], sudoku: ["/games/sudoku-unlimited/", "sudoku-unlimited", "Play rated Sudoku"],
    lockerlink: ["/games/lockerlink/", "lockerlink", "Play today's Lockerlink"], gridlink: ["/games/gridlink/", "gridlink", "Play today's Gridlink"], unbeaten: ["/games/unbeaten/", "unbeaten", "Play today's Unbeaten"] };

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }

  function tabs() {
    Array.prototype.forEach.call(document.querySelectorAll(".lb-tab[data-game]"), function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-game") === st.game ? "true" : "false"); });
    Array.prototype.forEach.call(document.querySelectorAll(".lb-tab[data-board]"), function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-board") === st.board ? "true" : "false"); });
    var p = PAGES[st.game], a = $("lb-play"); a.href = p[0]; a.setAttribute("data-g", p[1]); a.textContent = p[2];
    var url = window.location.pathname + "?g=" + st.game + "&b=" + st.board;
    try { window.history.replaceState(null, "", url); } catch (e) { /* ignore */ }
  }

  function render(data) {
    var list = $("lb-list"), status = $("lb-status");
    list.textContent = "";
    if (!data) { status.textContent = "The board could not be loaded. Try again in a moment."; return; }
    status.textContent = data.rows.length ? "" : (st.board === "week" ? "No one has three rated puzzles this week yet. Be the first." : "No one is on this board yet. Be the first.");
    data.rows.forEach(function (row) {
      var li = el("li", "lb-row"); if (row.rank <= 3) li.setAttribute("data-top", String(row.rank));
      if (data.you && data.you.rank === row.rank) li.setAttribute("data-you", "");
      li.appendChild(el("span", "lb-rank", String(row.rank)));
      li.appendChild(el("span", "lb-name", row.name));
      li.appendChild(el("span", "lb-n", row.n + " played"));
      var score = el("b", "lb-score", st.board === "week" ? (row.g >= 0 ? "+" : "−") + Math.abs(row.g) : String(row.r));
      li.appendChild(score);
      list.appendChild(li);
    });
    var you = $("lb-you");
    if (data.you) { you.hidden = false; you.textContent = "You are number " + data.you.rank + (st.board === "week" ? " this week, " + (data.you.g >= 0 ? "up " : "down ") + Math.abs(data.you.g) : " with " + data.you.r) + "."; }
    else you.hidden = true;
  }

  function join(data) {
    var box = $("lb-join"), s = G.session && G.session.get();
    box.textContent = "";
    function p(text) { var e = document.createElement("p"); e.textContent = text; box.appendChild(e); }
    function btn(text, fn) { var b = el("button", "gbtn gbtn--ghost", text); b.type = "button"; b.addEventListener("click", fn); box.appendChild(b); }
    if (!s) { p("Sign in with an email link to keep your rating on the server and join the board."); var a = el("a", "gbtn gbtn--ghost", "Sign in"); a.href = "/games/account/"; box.appendChild(a); return; }
    if (data && data.you) { btn("Leave the leaderboards", function () { R.setPublic(false).then(function () { load(); }); }); return; }
    if (!s.name) { p("Choose a display name on your account page to appear here."); var a2 = el("a", "gbtn gbtn--ghost", "Choose a name"); a2.href = "/games/account/"; box.appendChild(a2); return; }
    p("You are not listed. Show " + s.name + " on the leaderboards?");
    btn("Show me on the leaderboards", function () {
      R.setPublic(true).then(function (res) { if (res.status === 200) load(); else p("That name cannot be shown. Choose another on your account page."); });
    });
  }

  function load() {
    tabs();
    $("lb-status").textContent = "Loading the board.";
    R.leaderboard(st.game, st.board).then(function (data) { render(data); join(data); if (window.PLDock) window.PLDock.paint(); });
  }

  Array.prototype.forEach.call(document.querySelectorAll(".lb-tab"), function (b) {
    b.addEventListener("click", function () {
      if (b.hasAttribute("data-game")) st.game = b.getAttribute("data-game"); else st.board = b.getAttribute("data-board");
      load();
    });
  });
  var wk = $("lb-week");
  if (wk) { var d = new Date(), off = (d.getDay() + 6) % 7, mon = new Date(d.getFullYear(), d.getMonth(), d.getDate() - off); wk.textContent = "Week of " + mon.toLocaleDateString("en-US", { month: "long", day: "numeric" }); }
  G.ready.then(load);
})();
