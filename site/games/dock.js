/* The game dock (the strip of games at the top of every game page) and the reward card that follows a finished
   puzzle. The dock's links are plain HTML so they work without scripts; this adds today's status, the
   spotlight marker, streaks and the level chip. Load after goals.js. */
(function () {
  "use strict";
  var G = window.PLGames, P = window.PLGoals, FX = window.PLFX;
  if (!G || !P) return;
  var SVG = "http://www.w3.org/2000/svg";

  function icon(id, cls) {
    var s = document.createElementNS(SVG, "svg"), u = document.createElementNS(SVG, "use");
    s.setAttribute("class", cls || "gl"); s.setAttribute("aria-hidden", "true"); s.setAttribute("focusable", "false");
    u.setAttribute("href", "/games/glyphs.svg#" + id);
    s.appendChild(u);
    return s;
  }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }

  // ---- the dock ----
  function paintDock() {
    var dock = document.querySelector(".game-dock"), sum = P.summary();
    Array.prototype.forEach.call(dock ? dock.querySelectorAll("a[data-g]") : [], function (a) {
      var id = a.getAttribute("data-g"), done = !!sum.done[id], spot = sum.spotlight.id === id && !done;
      a.toggleAttribute("data-done", done);
      a.toggleAttribute("data-spot", spot);
      var st = a.querySelector(".dock-state"), sr = a.querySelector(".dock-sr");
      if (st) { st.textContent = ""; if (done) st.appendChild(icon("check", "gl gl-sm")); }
      var name = P.BY[id].name;
      if (sr) sr.textContent = done ? ", done today" : spot ? ", today's spotlight, bonus XP" : "";
      a.setAttribute("title", name + (done ? " (done today)" : spot ? " (spotlight: bonus XP)" : ""));
    });
    var chip = document.getElementById("dock-level");
    if (chip) {
      chip.textContent = "";
      chip.appendChild(icon("bolt", "gl gl-sm"));
      chip.appendChild(el("span", "dock-chip-text", "Level " + sum.level.level));
      chip.setAttribute("title", sum.level.title + ": " + sum.level.into + " of " + sum.level.need + " XP to the next level");
    }
    var fl = document.getElementById("dock-streak");
    if (fl) {
      var top = sum.streaks[0];
      fl.hidden = !top;
      if (top) {
        fl.textContent = "";
        fl.appendChild(icon("flame", "gl gl-sm"));
        fl.appendChild(el("span", "dock-chip-text", String(top.streak)));
        fl.setAttribute("title", "Longest live streak: " + top.name + ", " + top.streak + " days");
        fl.toggleAttribute("data-risk", !!top.atRisk);
      }
    }
    // keep the current game in view on a narrow screen
    var cur = dock && dock.querySelector('a[aria-current="page"]'), list = dock && dock.querySelector(".dock-list");
    if (cur && list && list.scrollWidth > list.clientWidth) {
      list.scrollLeft = Math.max(0, cur.offsetLeft - (list.clientWidth - cur.offsetWidth) / 2);
    }
  }

  // ---- the reward card after a finished puzzle ----
  function pips(sum, current) {
    var wrap = el("div", "reward-pips");
    wrap.setAttribute("role", "img");
    wrap.setAttribute("aria-label", sum.count + " of " + sum.total + " puzzles done today");
    sum.games.forEach(function (g) {
      var p = el("i", "reward-pip");
      p.setAttribute("data-g", g.id);
      if (sum.done[g.id]) p.setAttribute("data-done", "");
      if (g.id === current) p.setAttribute("data-new", "");
      wrap.appendChild(p);
    });
    return wrap;
  }

  function line(kind, text, xp) {
    var li = el("li", "reward-line");
    li.setAttribute("data-kind", kind);
    li.appendChild(icon(kind === "level" ? "bolt" : kind === "week" ? "medal" : "check", "gl gl-sm"));
    li.appendChild(el("span", "reward-line-text", text));
    if (xp) li.appendChild(el("b", "reward-line-xp", "+" + xp + " XP"));
    return li;
  }

  function render(info) {
    if (document.getElementById("reward")) return;
    var sum = info.summary, card = el("section", "reward");
    card.id = "reward";
    card.setAttribute("aria-labelledby", "reward-h");
    card.setAttribute("data-g", info.game);
    if (info.levelUp) card.setAttribute("data-levelup", "");

    var head = el("div", "reward-head");
    var h = el("h2", null, info.levelUp ? "Level up" : info.game === "daily-stars" ? "Reading saved" : info.ok ? "Puzzle done" : "Done for today");
    h.id = "reward-h";
    head.appendChild(h);
    if (info.gain > 0) {
      var xp = el("p", "reward-xp");
      var n = el("b", "reward-xp-n", "0");
      xp.appendChild(n); xp.appendChild(document.createTextNode(" XP"));
      head.appendChild(xp);
    }
    card.appendChild(head);

    // level bar: starts where it was before this puzzle, fills to where it is now
    var lv = info.level, before = info.before && !info.levelUp ? Math.max(0, lv.into - info.gain) : 0;
    var lvl = el("div", "reward-level");
    lvl.appendChild(el("span", "reward-level-name", "Level " + lv.level + ": " + lv.title));
    var bar = el("span", "reward-bar"); bar.setAttribute("role", "img");
    bar.setAttribute("aria-label", lv.into + " of " + lv.need + " XP to level " + (lv.level + 1));
    var fill = el("i", "reward-fill");
    fill.style.setProperty("--p", String(before / lv.need));
    bar.appendChild(fill); lvl.appendChild(bar);
    lvl.appendChild(el("span", "reward-level-num", lv.into + " / " + lv.need));
    card.appendChild(lvl);

    var list = el("ul", "reward-lines");
    if (info.newTier) list.appendChild(line("tier", info.newTier.name + ": " + (info.newTier.n === 8 ? "every puzzle finished today" : info.newTier.n + " puzzles finished today"), info.newTier.xp));
    info.newQuests.forEach(function (q) { list.appendChild(line("quest", "Quest done: " + q, G.QUEST_XP)); });
    if (info.spotlight) list.appendChild(line("spot", "Spotlight bonus: " + P.BY[sum.spotlight.id].name, G.QUEST_XP));
    if (info.week) list.appendChild(line("week", "Week complete: five stamped days", G.WEEK_XP));
    if (list.children.length) card.appendChild(list);

    var prog = el("div", "reward-prog");
    prog.appendChild(pips(sum, info.game));
    var msg = sum.count + " of " + sum.total + " done today.";
    if (sum.toNextTier) msg += " " + sum.toNextTier.need + " more for " + sum.toNextTier.name + " (+" + sum.toNextTier.xp + " XP).";
    prog.appendChild(el("p", "reward-prog-text", msg));
    card.appendChild(prog);

    if (info.next) {
      var a = el("a", "next-card"); a.href = info.next.path; a.setAttribute("data-g", info.next.id);
      a.appendChild(icon(info.next.id, "gl gl-lg"));
      var t = el("span", "next-card-text");
      t.appendChild(el("span", "next-card-kicker", "Next puzzle"));
      t.appendChild(el("b", "next-card-name", info.next.name));
      t.appendChild(el("span", "next-card-sub", "About " + info.next.min + (info.next.min === 1 ? " minute" : " minutes") + (sum.spotlight.id === info.next.id ? ". Today's spotlight: bonus XP." : ".")));
      a.appendChild(t); a.appendChild(icon("arrow", "gl next-card-arrow"));
      card.appendChild(a);
    } else {
      card.appendChild(el("p", "reward-done", "Every puzzle is done. New ones arrive at midnight."));
    }

    var anchor = document.querySelector(".game-result:not([hidden])") || document.getElementById("st-card") || document.querySelector(".games-prose");
    if (anchor && anchor.classList.contains("games-prose")) anchor.parentNode.insertBefore(card, anchor);
    else if (anchor) anchor.parentNode.insertBefore(card, anchor.nextSibling);
    else (document.querySelector(".games-wrap") || document.body).appendChild(card);

    // staged entrance: the card, then the numbers, then the bar
    window.requestAnimationFrame(function () {
      card.setAttribute("data-in", "");
      var xpn = card.querySelector(".reward-xp-n");
      if (xpn && FX) { FX.count(xpn, info.gain, 800); } else if (xpn) xpn.textContent = String(info.gain);
      window.setTimeout(function () { fill.style.setProperty("--p", String(lv.into / lv.need)); }, 80);
    });
    if (info.levelUp && window.PLConfetti) window.setTimeout(function () { window.PLConfetti.big(); }, 400);
    paintDock();
  }

  document.addEventListener("pl-reward", function (e) {
    window.setTimeout(function () { render(e.detail); }, window.PLFX && window.PLFX.reduced() ? 0 : 650);
  });

  G.ready.then(function () { try { P.refresh(); } catch (e) { /* ignore */ } paintDock(); });
  // later in the page's life (for example after a game ends) the dock refreshes with the reward card
  window.PLDock = { paint: paintDock };
})();
