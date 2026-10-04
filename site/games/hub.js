/* Hub: show "Played today" / streak on each card from this device's saved progress. */
(function () {
  "use strict";
  var G = window.PLGames;
  if (!G) return;
  var EPOCHS = "2026-10-04";
  var idx = G.dayIndex(new Date(), EPOCHS);
  var cards = document.querySelectorAll(".game-card[data-game]");
  Array.prototype.forEach.call(cards, function (card) {
    var name = card.getAttribute("data-game");
    var s = G.getGame(name), out = card.querySelector("[data-status]");
    if (!out) return;
    var done = s.today && s.today.idx === idx && s.today.done;
    var streak = s.stats && s.stats.streak ? s.stats.streak : 0;
    if (done) out.textContent = "Done today" + (streak > 1 ? ". Streak " + streak + "." : ".");
    else if (streak > 0) out.textContent = "Streak " + streak + ". Play today's puzzle.";
    else out.textContent = "";
  });
})();
