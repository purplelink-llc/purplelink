/* Hub: the daily run ring, milestones, quests, a status on each tile, the week's stamps and a few achievements in reach. */
(function () {
  "use strict";
  var G = window.PLGames, P = window.PLGoals, FX = window.PLFX;
  if (!G || !P) return;
  var NS = "http://www.w3.org/2000/svg";
  var $ = function (id) { return document.getElementById(id); };
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }
  function icon(id, cls) {
    var s = document.createElementNS(NS, "svg"), u = document.createElementNS(NS, "use");
    s.setAttribute("class", cls || "gl"); s.setAttribute("aria-hidden", "true"); s.setAttribute("focusable", "false");
    u.setAttribute("href", "/games/glyphs.svg#" + id); s.appendChild(u); return s;
  }

  // The ring is eight arcs, one per game, each lit in that game's colour once it is finished.
  function drawRing(sum) {
    var svg = $("run-svg"); if (!svg) return;
    var R = 72, C = 2 * Math.PI * R, gap = 10, seg = C / sum.games.length - gap;
    svg.textContent = "";
    sum.games.forEach(function (g, i) {
      var c = document.createElementNS(NS, "circle");
      c.setAttribute("cx", "84"); c.setAttribute("cy", "84"); c.setAttribute("r", String(R));
      c.setAttribute("class", "run-seg"); c.setAttribute("data-g", g.id);
      c.setAttribute("stroke-dasharray", seg.toFixed(2) + " " + (C - seg).toFixed(2));
      c.setAttribute("stroke-dashoffset", String(-(i * (seg + gap)) + gap / 2));
      if (sum.done[g.id]) c.setAttribute("data-done", "");
      else if (sum.spotlight.id === g.id) c.setAttribute("data-spot", "");
      var t = document.createElementNS(NS, "title"); t.textContent = g.name + (sum.done[g.id] ? ", done" : ""); c.appendChild(t);
      svg.appendChild(c);
    });
  }

  function paintTiles(sum, all) {
    sum.games.forEach(function (g) {
      var card = document.querySelector('.tile[data-game="' + g.id + '"]');
      if (!card) return;
      var s = all[g.id] || {}, done = !!sum.done[g.id], streak = s.stats && s.stats.streak ? s.stats.streak : 0;
      var alive = streak > 0 && s.stats && (s.stats.last === sum.idx || s.stats.last === sum.idx - 1);
      var started = !done && s.today && s.today.idx === sum.idx;
      card.toggleAttribute("data-done", done);
      card.toggleAttribute("data-spot", sum.spotlight.id === g.id && !done);
      card.toggleAttribute("data-streak", alive);
      var st = card.querySelector("[data-status]"), go = card.querySelector("[data-go]");
      if (st) {
        if (done) st.textContent = alive && streak > 1 ? "Done. " + streak + " day streak" : "Done today";
        else if (alive && streak > 1) st.textContent = streak + " day streak to keep";
        else if (started) st.textContent = "In progress";
        else st.textContent = "About " + g.min + (g.min === 1 ? " minute" : " minutes");
      }
      if (go) go.textContent = done ? "Review" : started ? "Continue" : "Play";
    });
  }

  function paintQuests(sum) {
    var ul = $("quests"); if (!ul) return;
    ul.textContent = "";
    sum.quests.forEach(function (q) {
      var li = el("li", "quest"); if (q.done) li.setAttribute("data-done", "");
      var mark = el("span", "quest-mark"); mark.appendChild(icon("check"));
      li.appendChild(mark);
      li.appendChild(el("span", "quest-text", q.text));
      li.appendChild(el("span", "quest-meta", q.done ? "+" + q.xp + " XP" : q.have + "/" + q.need));
      ul.appendChild(li);
    });
    var sp = P.BY[sum.spotlight.id], li2 = el("li", "quest"); li2.setAttribute("data-g", sp.id); li2.setAttribute("data-spot", "");
    if (sum.spotlight.done) li2.setAttribute("data-done", "");
    var m2 = el("span", "quest-mark"); m2.appendChild(icon("check")); li2.appendChild(m2);
    li2.appendChild(el("span", "quest-text", "Spotlight: " + sp.name));
    li2.appendChild(el("span", "quest-meta", "+" + sum.spotlight.xp + " XP"));
    ul.appendChild(li2);
  }

  function paintWeek(sum) {
    var ol = $("stamps"); if (!ol) return;
    ol.textContent = "";
    var NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
    sum.week.days.forEach(function (d, i) {
      var li = el("li", "stamp");
      if (d.stamped) li.setAttribute("data-stamped", "");
      if (d.today) li.setAttribute("data-today", "");
      if (d.future) li.setAttribute("data-future", "");
      var dot = el("span", "stamp-dot"); dot.appendChild(icon("check"));
      li.appendChild(dot); li.appendChild(el("span", null, NAMES[i]));
      li.setAttribute("aria-label", NAMES[i] + (d.stamped ? ", stamped" : d.future ? ", not yet" : d.today ? ", today" : ", no stamp"));
      ol.appendChild(li);
    });
    var sub = $("week-sub");
    if (sub) sub.textContent = sum.week.count >= 5 ? "Week complete. That is five stamps, worth " + sum.weekXp + " XP." : sum.week.count + " of 5 stamps. Finish two puzzles in a day to stamp it; five stamps in a week is worth " + sum.weekXp + " XP.";
  }

  function paintReach() {
    var ul = $("reach"), A = window.PLAch; if (!ul || !A) return;
    var have = A.unlocked() || {}, locked = A.defs.filter(function (d) { return have[d.id] === undefined; });
    var n = P.todayIdx(), picks = [];
    for (var k = 0; k < locked.length && picks.length < 3; k++) picks.push(locked[(n * 7 + k * 5) % locked.length]);
    var seen = {}; picks = picks.filter(function (d) { return !seen[d.id] && (seen[d.id] = 1); });
    ul.textContent = "";
    picks.forEach(function (d) {
      var li = el("li", "reach"); li.appendChild(icon("lock"));
      var t = el("div"); t.appendChild(el("b", null, d.name)); t.appendChild(el("span", null, d.desc)); li.appendChild(t);
      ul.appendChild(li);
    });
    var line = $("hub-ach");
    if (line) line.textContent = Object.keys(have).length + " of " + A.defs.length + " achievements unlocked. ";
  }

  function paint(first) {
    var all = G.all(), sum = P.summary();
    drawRing(sum);
    var n = $("run-n"); if (n) { if (first && FX) { n.textContent = "0"; FX.count(n, sum.count, 900); } else n.textContent = String(sum.count); }
    var line = $("run-line");
    if (line) {
      if (sum.count === sum.total) line.textContent = "A full run. New puzzles arrive at midnight.";
      else if (sum.toNextTier) line.textContent = sum.count === 0 ? "Finish two puzzles for a Warm-up, four for Steady, all eight for a Full run." : sum.toNextTier.need + " more for " + sum.toNextTier.name + " (+" + sum.toNextTier.xp + " XP).";
    }
    Array.prototype.forEach.call(document.querySelectorAll(".run-tier"), function (li) { li.toggleAttribute("data-got", sum.count >= Number(li.getAttribute("data-n"))); });
    var btn = $("hub-next");
    if (btn) {
      if (sum.next) {
        btn.hidden = false; btn.href = sum.next.path; btn.setAttribute("data-g", sum.next.id);
        $("hub-next-text").textContent = (sum.count === 0 ? "Start with " : "Next: ") + sum.next.name;
      } else btn.hidden = true;
    }
    var lv = $("hub-level");
    if (lv) lv.textContent = "Level " + sum.level.level + ", " + sum.level.title + ". " + sum.level.into + " of " + sum.level.need + " XP to the next.";
    var date = $("hub-date");
    if (date) date.textContent = new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });
    paintTiles(sum, all); paintQuests(sum); paintWeek(sum); paintReach();
    if (window.PLDock) window.PLDock.paint();
  }

  G.ready.then(function () {
    P.refresh();
    paint(true);
  });
  // coming back to the tab after finishing a puzzle elsewhere
  document.addEventListener("visibilitychange", function () { if (!document.hidden) { P.refresh(); paint(false); } });
  window.addEventListener("pageshow", function (e) { if (e.persisted) { P.refresh(); paint(false); } });
})();
