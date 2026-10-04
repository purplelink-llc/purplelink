/* Achievements for the daily games. Unlocks are stored with the rest of the saved progress
   (and follow a signed-in player between devices). Load after core.js. */
(function () {
  "use strict";
  var G = window.PLGames;
  if (!G) return;
  var EPOCH = "2026-10-04", EPOCH_DOW = 0;   // puzzle day 0 is a Sunday

  function stats(all, g) { return (all[g] && all[g].stats) || {}; }
  function wins(all, g) { return stats(all, g).wins || []; }
  var PLAYED = ["linkle", "quadlink", "daily-five", "daily-photo", "daily-chess", "sudoku", "crossword"];
  function best(all) { return PLAYED.reduce(function (n, g) { return Math.max(n, stats(all, g).max || 0); }, 0); }
  function played(all) { return PLAYED.reduce(function (n, g) { return n + (stats(all, g).played || 0); }, 0); }
  function dowOf(idx) { return (EPOCH_DOW + idx) % 7; }

  var DEFS = [
    { id: "first-link", name: "First link", desc: "Win your first Linkle.", test: function (a) { return stats(a, "linkle").won >= 1; } },
    { id: "sharp", name: "Sharp", desc: "Solve Linkle in two guesses or fewer.", test: function (a, c) { return c.game === "linkle" && c.won && c.tries <= 2; } },
    { id: "hard-mode", name: "No shortcuts", desc: "Win a Sunday Linkle in hard mode.", test: function (a, c) { return c.game === "linkle" && c.won && c.weekday === 0; } },
    { id: "every-twist", name: "Every twist", desc: "Win Linkle on all seven weekday twists.", test: function (a) {
      var seen = {}; wins(a, "linkle").forEach(function (d) { seen[dowOf(d)] = 1; }); return Object.keys(seen).length >= 7; } },
    { id: "full-week", name: "Full week", desc: "Solve Linkle on all seven days of a Monday-to-Sunday week.", test: function (a, c) {
      return G.weekProgress(wins(a, "linkle"), c.idx !== undefined ? c.idx : 0, EPOCH_DOW).fullWeeks >= 1; } },
    { id: "scribe", name: "Scribe", desc: "Win 15 Linkle puzzles.", test: function (a) { return stats(a, "linkle").won >= 15; } },
    { id: "sage", name: "Sage", desc: "Win 100 Linkle puzzles.", test: function (a) { return stats(a, "linkle").won >= 100; } },
    { id: "quad-first", name: "Four at once", desc: "Win your first Quadlink.", test: function (a) { return stats(a, "quadlink").won >= 1; } },
    { id: "quad-fast", name: "Quick quad", desc: "Solve Quadlink in seven guesses or fewer.", test: function (a, c) { return c.game === "quadlink" && c.won && c.tries <= 7; } },
    { id: "five-perfect", name: "Perfect five", desc: "Answer all five Daily Five questions correctly.", test: function (a, c) { return c.game === "daily-five" && c.score === 5; } },
    { id: "five-habit", name: "Quiz habit", desc: "Finish Daily Five on ten different days.", test: function (a) { return stats(a, "daily-five").played >= 10; } },
    { id: "photo-perfect", name: "Globetrotter", desc: "Place all five photographs in Daily Photo correctly.", test: function (a, c) { return c.game === "daily-photo" && c.score === 5; } },
    { id: "photo-habit", name: "Armchair traveller", desc: "Finish Daily Photo on ten different days.", test: function (a) { return stats(a, "daily-photo").played >= 10; } },
    { id: "chess-first", name: "First checkmate", desc: "Solve your first Daily Chess puzzle.", test: function (a) { return stats(a, "daily-chess").won >= 1; } },
    { id: "chess-clean", name: "Clean tactic", desc: "Solve a chess puzzle with no wrong moves and no hints.", test: function (a, c) { return c.game === "daily-chess" && c.won && c.clean; } },
    { id: "chess-hard", name: "Grandmaster eyes", desc: "Solve a chess puzzle rated 1900 or higher.", test: function (a, c) { return c.game === "daily-chess" && c.won && c.rating >= 1900; } },
    { id: "sudoku-first", name: "Digits in place", desc: "Solve your first daily Sudoku.", test: function (a) { return stats(a, "sudoku").won >= 1; } },
    { id: "sudoku-hard", name: "No pencil needed", desc: "Solve a Hard or Expert Sudoku with no help.", test: function (a, c) { return c.game === "sudoku" && c.clean && (c.level === "Hard" || c.level === "Expert"); } },
    { id: "sudoku-clean-5", name: "Sharp eyes", desc: "Solve five Sudokus with no help.", test: function (a) { return ((a.sudoku && a.sudoku.clean) || 0) >= 5; } },
    { id: "cw-first", name: "First crossword", desc: "Solve your first daily crossword.", test: function (a) { return stats(a, "crossword").won >= 1; } },
    { id: "cw-monday", name: "Quick Monday", desc: "Solve a Monday crossword with no help in under four minutes.", test: function (a, c) { return c.game === "crossword" && c.clean && c.weekdayName === "Monday" && c.seconds < 240; } },
    { id: "cw-sunday", name: "Sunday finisher", desc: "Solve a Sunday crossword with no help.", test: function (a, c) { return c.game === "crossword" && c.clean && c.weekdayName === "Sunday"; } },
    { id: "cw-clean-5", name: "Unaided", desc: "Solve five crosswords with no help.", test: function (a) { return ((a.crossword && a.crossword.clean) || 0) >= 5; } },
    { id: "streak-3", name: "On a roll", desc: "Keep a three-day streak in any game.", test: function (a) { return best(a) >= 3; } },
    { id: "streak-7", name: "Week streak", desc: "Keep a seven-day streak in any game.", test: function (a) { return best(a) >= 7; } },
    { id: "streak-30", name: "Month streak", desc: "Keep a thirty-day streak in any game.", test: function (a) { return best(a) >= 30; } },
    { id: "full-set", name: "Full set", desc: "Finish Linkle, Quadlink, Daily Five and the crossword on the same day.", test: function (a, c) {
      return ["linkle", "quadlink", "daily-five", "crossword"].every(function (g) { var t = a[g] && a[g].today; return t && t.done && t.idx === c.idx; }); } },
    { id: "daily-set", name: "Daily set", desc: "Finish every daily puzzle and read your sign on the same day.", test: function (a, c) {
      var five = PLAYED.every(function (g) { var t = a[g] && a[g].today; return t && t.done && t.idx === c.idx; });
      var stars = ((a["daily-stars"] && a["daily-stars"].viewed) || []).indexOf(c.idx) >= 0;
      return five && stars; } },
    { id: "close-call", name: "Close call", desc: "Let the weekly streak saver rescue a streak.", test: function (a) {
      return PLAYED.some(function (g) { return (stats(a, g).freezes || []).length > 0; }); } },
    { id: "level-5", name: "Level 5", desc: "Reach level 5.", test: function (a) { return G.xpOf(a).level >= 5; } },
    { id: "top-tenth", name: "Top tenth", desc: "Finish ahead of 90% of the day's players (at least 20 played).", test: function (a, c) { return c.pct >= 90 && c.total >= 20; } },
    { id: "regular", name: "Regular", desc: "Finish 30 daily puzzles.", test: function (a) { return played(a) >= 30; } },
    { id: "centurion", name: "Centurion", desc: "Finish 100 daily puzzles.", test: function (a) { return played(a) >= 100; } },
    { id: "stargazer", name: "Stargazer", desc: "Read your sign on seven different days.", test: function (a) { return ((a["daily-stars"] && a["daily-stars"].viewed) || []).length >= 7; } }
  ];

  function toast(list) {
    var box = document.getElementById("pl-toast");
    if (!box) {
      box = document.createElement("div");
      box.id = "pl-toast";
      box.className = "pl-toast";
      box.setAttribute("role", "status");
      box.setAttribute("aria-live", "polite");
      document.body.appendChild(box);
    }
    list.forEach(function (d) {
      var item = document.createElement("div");
      item.className = "pl-toast-item";
      var b = document.createElement("strong");
      b.textContent = "Achievement unlocked: " + d.name;
      var s = document.createElement("span");
      s.textContent = d.desc;
      item.appendChild(b); item.appendChild(s);
      box.appendChild(item);
      window.setTimeout(function () { if (item.parentNode) item.parentNode.removeChild(item); }, 7000);
    });
  }

  // ctx: { game, idx, won, tries, score, clean, seconds, weekday, weekdayName, pct, total }. Safe to call twice for one game
  // (once at the end, once when the percentile arrives); an achievement only unlocks once.
  function check(ctx) {
    var all = G.all(), have = (all.ach && typeof all.ach === "object") ? all.ach : {}, fresh = [];
    DEFS.forEach(function (d) {
      if (have[d.id] !== undefined) return;
      var ok = false;
      try { ok = !!d.test(all, ctx || {}); } catch (e) { ok = false; }
      if (ok) { have[d.id] = ctx && ctx.idx !== undefined ? ctx.idx : 0; fresh.push(d); }
    });
    if (fresh.length) { G.setGame("ach", have); toast(fresh); if (window.PLFX) window.setTimeout(function () { window.PLFX.play("ach"); }, 350); }
    if (window.PLGoals && ctx && ctx.game) window.setTimeout(function () { window.PLGoals.afterResult(ctx); }, 0);   // after the game has saved its own result
    return fresh;
  }

  window.PLAch = { defs: DEFS, check: check, unlocked: function () { return G.getGame("ach"); } };
})();
