/* Daily Five: five multiple-choice questions a day. Streak = consecutive days completed. */
(function () {
  "use strict";
  var G = window.PLGames, NAME = "daily-five", URL_ = "https://purplelink.llc/games/daily-five/";
  if (!G) return;
  var $ = function (id) { return document.getElementById(id); };
  var st = { idx: 0, qs: [], picks: [], cur: 0, done: false, answered: false, epoch: "" };

  function correctText(q) { return G.decodeText(q[3]); }
  function isRight(qi) { return st.picks[qi] !== undefined && st.qs[qi][2][st.picks[qi]] === correctText(st.qs[qi]); }
  function score() { var n = 0; for (var i = 0; i < st.qs.length; i++) if (isRight(i)) n++; return n; }

  function persist() {
    var s = G.getGame(NAME);
    s.today = { idx: st.idx, picks: st.picks, done: st.done };
    G.setGame(NAME, s);
  }

  function dots() {
    var box = $("qz-dots");
    box.textContent = "";
    for (var i = 0; i < st.qs.length; i++) {
      var d = document.createElement("i");
      if (st.picks[i] !== undefined) d.setAttribute("data-r", isRight(i) ? "right" : "wrong");
      else if (i === st.cur) d.setAttribute("data-now", "1");
      box.appendChild(d);
    }
  }

  function showQuestion() {
    var q = st.qs[st.cur];
    $("qz-progress").textContent = "Question " + (st.cur + 1) + " of " + st.qs.length;
    $("qz-cat").textContent = q[0];
    $("qz-q").textContent = q[1];
    var ul = $("qz-opts");
    ul.textContent = "";
    var answered = st.picks[st.cur] !== undefined;
    var right = correctText(q);
    q[2].forEach(function (text, i) {
      var li = document.createElement("li");
      var b = document.createElement("button");
      b.type = "button";
      b.className = "quiz-opt";
      b.textContent = text;
      if (answered) {
        b.disabled = true;
        if (text === right) { b.setAttribute("data-r", "right"); b.appendChild(tag("Correct")); }
        else if (i === st.picks[st.cur]) { b.setAttribute("data-r", "wrong"); b.appendChild(tag("Your answer")); }
      } else {
        b.addEventListener("click", function () { choose(i); });
      }
      li.appendChild(b);
      ul.appendChild(li);
    });
    $("qz-note").textContent = answered ? (isRight(st.cur) ? "Correct." : "The answer is " + right + ".") : "";
    var next = $("qz-next");
    next.hidden = !answered;
    next.textContent = st.cur === st.qs.length - 1 ? "See your score" : "Next question";
    dots();
    var first = ul.querySelector("button:not(:disabled)") || next;
    if (answered && !next.hidden) next.focus();
  }

  function tag(t) {
    var s = document.createElement("span");
    s.className = "quiz-tag";
    s.textContent = t;
    return s;
  }

  function choose(i) {
    if (st.picks.length === 0) G.track("game_start", NAME);
    st.picks[st.cur] = i;
    persist();
    showQuestion();
  }

  function next() {
    if (st.cur < st.qs.length - 1) { st.cur += 1; showQuestion(); return; }
    st.done = true;
    persist();
    finish(true);
  }

  function shareText() {
    var sq = st.qs.map(function (_, i) { return isRight(i) ? "■" : "□"; }).join("");
    return "Daily Five " + (st.idx + 1) + " " + score() + "/" + st.qs.length + "\n\n" + sq + "\n\n" + URL_;
  }

  function finish(fresh) {
    var saved = G.getGame(NAME);
    var sc = score();
    if (fresh) {
      saved.stats = G.recordResult(saved.stats, st.idx, true, sc);
      G.setGame(NAME, saved);
      G.track("game_end", NAME + ":" + sc);
    }
    var s = saved.stats || G.emptyStats();
    $("qz-quiz").hidden = true;
    var box = $("qz-result");
    box.hidden = false;
    $("qz-result-head").textContent = "You scored " + sc + " of " + st.qs.length;
    var total = 0, n = 0;
    for (var k in s.dist) { total += Number(k) * s.dist[k]; n += s.dist[k]; }
    $("qz-played").textContent = s.played;
    $("qz-avg").textContent = n ? (total / n).toFixed(1) : "0.0";
    $("qz-streak").textContent = s.streak;
    $("qz-max").textContent = s.max;
    var dist = $("qz-dist");
    dist.textContent = "";
    var top = 1;
    for (k in s.dist) if (s.dist[k] > top) top = s.dist[k];
    for (var i = 0; i <= st.qs.length; i++) {
      var row = document.createElement("div");
      row.className = "wg-distrow";
      var lab = document.createElement("span"); lab.textContent = i;
      var m = document.createElement("meter"); m.min = 0; m.max = top; m.value = s.dist[i] || 0;
      m.setAttribute("aria-label", i + " correct: " + (s.dist[i] || 0) + " days");
      var num = document.createElement("span"); num.textContent = s.dist[i] || 0;
      row.appendChild(lab); row.appendChild(m); row.appendChild(num);
      dist.appendChild(row);
    }
    var rev = $("qz-review");
    rev.textContent = "";
    st.qs.forEach(function (q, i) {
      var li = document.createElement("li");
      li.textContent = (isRight(i) ? "Correct: " : "Missed: ") + q[1] + " " + correctText(q);
      rev.appendChild(li);
    });
    tick();
    if (fresh) box.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  function tick() {
    var el = $("qz-next-in");
    if (!el || $("qz-result").hidden) return;
    var now = new Date(), nx = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
    var ms = nx - now, h = Math.floor(ms / 3600000), m = Math.floor((ms % 3600000) / 60000);
    el.textContent = h + " h " + (m < 10 ? "0" : "") + m + " min";
    if (G.dayIndex(now, st.epoch) !== st.idx) el.textContent = "ready now. Reload the page.";
  }

  function start(data) {
    st.epoch = data.epoch;
    st.idx = G.dayIndex(new Date(), data.epoch);
    st.qs = G.pick(data.days, st.idx);
    $("qz-number").textContent = "Quiz " + (st.idx + 1);
    var saved = G.getGame(NAME);
    if (saved.today && saved.today.idx === st.idx) {
      st.picks = saved.today.picks || [];
      st.done = !!saved.today.done;
      st.cur = Math.min(st.picks.length, st.qs.length - 1);
      if (st.picks.length && st.picks.length < st.qs.length) st.cur = st.picks.length;
    }
    // A question answered earlier but not yet advanced past shows its result with Next.
    $("qz-next").addEventListener("click", next);
    $("qz-share").addEventListener("click", function () {
      var text = shareText();
      G.track("game_share", NAME);
      G.copyText(text).then(function (ok) {
        $("qz-share-note").textContent = ok ? "Copied to the clipboard." : "Copy failed. Select the text below and copy it.";
        var box = $("qz-share-text"); box.value = text; box.hidden = ok;
      });
    });
    window.setInterval(tick, 30000);
    $("qz-loading").hidden = true;
    $("qz-game").hidden = false;
    if (st.done) finish(false);
    else { $("qz-quiz").hidden = false; showQuestion(); }
  }

  fetch("/games/data/trivia.json").then(function (r) { if (!r.ok) throw 0; return r.json(); }).then(start, function () {
    $("qz-loading").textContent = "Today's questions could not be loaded. Check your connection and reload the page.";
  });
})();
