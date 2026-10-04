/* Hub: today's progress, level, the next puzzle to play, and a status line on each card. */
(function () {
  "use strict";
  var G = window.PLGames;
  if (!G) return;
  var EPOCH = "2026-10-04";
  // Roughly how long each takes, shortest first: the "next up" suggestion walks this list.
  var ORDER = [
    ["daily-photo", "Daily Photo", "/games/daily-photo/", 2],
    ["daily-five", "Daily Five", "/games/daily-five/", 2],
    ["daily-stars", "Daily Stars", "/games/daily-stars/", 1],
    ["linkle", "Linkle", "/games/linkle/", 3],
    ["quadlink", "Quadlink", "/games/quadlink/", 5],
    ["crossword", "the crossword", "/games/crossword/", 10]
  ];

  G.ready.then(function () {
    var idx = G.dayIndex(new Date(), EPOCH), all = G.all(), done = {}, n = 0;

    ORDER.forEach(function (g) {
      var name = g[0], s = all[name] || {};
      var finished = name === "daily-stars"
        ? (s.viewed || []).indexOf(idx) >= 0
        : !!(s.today && s.today.idx === idx && s.today.done);
      done[name] = finished;
      if (finished) n++;
      var card = document.querySelector('.game-card[data-game="' + name + '"]');
      var out = card && card.querySelector("[data-status]");
      if (!out) return;
      var streak = s.stats && s.stats.streak ? s.stats.streak : 0;
      if (finished) out.textContent = "Done today" + (streak > 1 ? ". Streak " + streak + "." : ".");
      else if (streak > 0) out.textContent = "Streak " + streak + ". Keep it going.";
      else out.textContent = "About " + g[3] + (g[3] === 1 ? " minute" : " minutes") + ".";
      card.toggleAttribute("data-done", finished);
    });

    var bar = document.getElementById("hub-progress");
    if (bar) bar.value = n;
    var count = document.getElementById("hub-count");
    var next = ORDER.filter(function (g) { return !done[g[0]]; })[0];
    if (count) count.textContent = n === ORDER.length ? "All six done today. Come back at midnight for new ones." : n + " of " + ORDER.length + " done today.";
    var btn = document.getElementById("hub-next");
    if (btn) {
      if (next) { btn.href = next[2]; btn.textContent = n === 0 ? "Start with " + next[1] : "Next up: " + next[1]; btn.hidden = false; }
      else btn.hidden = true;
    }

    var lvl = G.xpOf(all), lv = document.getElementById("hub-level");
    if (lv) lv.textContent = "Level " + lvl.level + ". " + lvl.into + " of " + lvl.need + " XP to level " + (lvl.level + 1) + ".";

    var line = document.getElementById("hub-ach");
    if (line && window.PLAch) line.textContent = Object.keys(window.PLAch.unlocked()).length + " of " + window.PLAch.defs.length + " achievements unlocked. ";
  });
})();
