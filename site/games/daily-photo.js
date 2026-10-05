/* Daily Photo: five photographs, pick the country for each. Streak = consecutive days finished. */
(function () {
  "use strict";
  var G = window.PLGames, NAME = "daily-photo", URL_ = "https://purplelink.llc/games/daily-photo/";
  if (!G) return;
  var $ = function (id) { return document.getElementById(id); };
  // Weekday twists (getDay(), Sunday = 0): how the photograph is shown until you answer.
  var TWISTS = {
    0: { name: "Standard", text: "The photographs are shown as they are." },
    1: { name: "Standard", text: "The photographs are shown as they are." },
    2: { name: "Blur reveal", fx: "blur", text: "Each photo starts blurred and sharpens over ten seconds." },
    3: { name: "Standard", text: "The photographs are shown as they are." },
    4: { name: "Zoom out", fx: "zoom", text: "Each photo starts zoomed in and pulls back over nine seconds." },
    5: { name: "Standard", text: "The photographs are shown as they are." },
    6: { name: "Black and white", fx: "mono", text: "Today's photographs are in black and white until you answer." }
  };
  var st = { twist: TWISTS[1], idx: 0, rounds: [], picks: [], cur: 0, done: false, epoch: "" };

  function answerOf(r) { return G.decodeText(r.a); }
  function isRight(i) { return st.picks[i] !== undefined && st.rounds[i].o[st.picks[i]] === answerOf(st.rounds[i]); }
  function score() { var n = 0; for (var i = 0; i < st.rounds.length; i++) if (isRight(i)) n++; return n; }
  function persist() {
    var s = G.getGame(NAME);
    s.today = { idx: st.idx, picks: st.picks, done: st.done };
    G.setGame(NAME, s);
  }

  function dots() {
    var box = $("ph-dots");
    box.textContent = "";
    for (var i = 0; i < st.rounds.length; i++) {
      var d = document.createElement("i");
      if (st.picks[i] !== undefined) d.setAttribute("data-r", isRight(i) ? "right" : "wrong");
      else if (i === st.cur) d.setAttribute("data-now", "1");
      box.appendChild(d);
    }
  }

  function tag(t) { var s = document.createElement("span"); s.className = "quiz-tag"; s.textContent = t; return s; }

  function show() {
    var r = st.rounds[st.cur], answered = st.picks[st.cur] !== undefined, right = answerOf(r);
    $("ph-progress").textContent = "Photo " + (st.cur + 1) + " of " + st.rounds.length;
    var img = $("ph-img");
    img.src = "/assets/photography/hub/" + r.i + "-1200.webp";
    img.srcset = "/assets/photography/hub/" + r.i + "-480.webp 480w, /assets/photography/hub/" + r.i + "-1200.webp 1200w";
    img.sizes = "(max-width: 700px) 100vw, 640px";
    // restart the twist's effect for this photo; answered photos are shown plain
    img.removeAttribute("data-fx"); img.removeAttribute("data-open");
    void img.offsetWidth;
    if (st.twist.fx) {
      if (answered) img.setAttribute("data-open", "1");
      else {
        img.style.setProperty("--ox", (20 + ((st.idx * 37 + st.cur * 23) % 61)) + "%"); img.style.setProperty("--oy", (20 + ((st.idx * 53 + st.cur * 29) % 61)) + "%");
        img.setAttribute("data-fx", st.twist.fx);
      }
    }
    var ul = $("ph-opts");
    ul.textContent = "";
    r.o.forEach(function (name, i) {
      var li = document.createElement("li"), b = document.createElement("button");
      b.type = "button"; b.className = "quiz-opt"; b.textContent = name;
      if (answered) {
        b.disabled = true;
        if (name === right) { b.setAttribute("data-r", "right"); b.appendChild(tag("Correct")); }
        else if (i === st.picks[st.cur]) { b.setAttribute("data-r", "wrong"); b.appendChild(tag("Your answer")); }
      } else b.addEventListener("click", function () { choose(i); });
      li.appendChild(b); ul.appendChild(li);
    });
    var reveal = $("ph-reveal");
    reveal.hidden = !answered;
    if (answered) {
      $("ph-where").textContent = r.p + ".";
      $("ph-caption").textContent = r.c;
      var link = $("ph-more");
      link.href = r.u;
      link.textContent = "More photographs from " + r.p.split(", ")[0];
    }
    var next = $("ph-next");
    next.hidden = !answered;
    next.textContent = st.cur === st.rounds.length - 1 ? "See your score" : "Next photo";
    dots();
    if (answered) next.focus();
  }

  function choose(i) {
    if (st.picks.length === 0) G.track("game_start", NAME);
    st.picks[st.cur] = i;
    persist(); show();
    var im = $("ph-img"); if (im && st.twist.fx) im.setAttribute("data-open", "1");
    if (window.PLConfetti && isRight(st.cur)) window.PLConfetti.small();
    var FX = window.PLFX, ok = isRight(st.cur), opts = document.querySelectorAll(".quiz-opt");
    if (FX) { FX.play(ok ? "good" : "bad"); if (!ok) FX.vibrate(30); FX.kick(opts[i], ok ? "fx-glow" : "fx-shake", 800); }
  }
  function next() {
    if (st.cur < st.rounds.length - 1) { st.cur += 1; show(); return; }
    st.done = true; persist(); finish(true);
  }

  function shareText() {
    var sq = st.rounds.map(function (_, i) { return isRight(i) ? "■" : "□"; }).join("");
    return "Daily Photo " + (st.idx + 1) + (st.twist.name !== "Standard" ? " (" + st.twist.name + ")" : "") + " " + score() + "/" + st.rounds.length + "\n\n" + sq + "\n\n" + URL_;
  }

  function finish(fresh) {
    var saved = G.getGame(NAME), sc = score();
    if (fresh) {
      saved.stats = G.recordResult(saved.stats, st.idx, true, sc);
      G.setGame(NAME, saved);
      G.track("game_end", NAME + ":" + sc);
      var ctx = { game: NAME, idx: st.idx, won: true, score: sc };
      if (window.PLAch) window.PLAch.check(ctx);
      if (sc === st.rounds.length && window.PLConfetti) window.PLConfetti.big();
      G.submitScore(NAME, st.idx, st.rounds.length - sc).then(function (res) {
        $("ph-pct").textContent = G.describePercentile(res);
        if (res && window.PLAch) window.PLAch.check({ game: NAME, idx: st.idx, won: true, score: sc, pct: res.percentile, total: res.total });
      });
    }
    var s = saved.stats || G.emptyStats();
    var sv = $("ph-saver"); if (sv) sv.textContent = G.saverNote(s, st.idx);
    $("ph-quiz").hidden = true;
    $("ph-result").hidden = false;
    $("ph-result-head").textContent = "You placed " + sc + " of " + st.rounds.length;
    var total = 0, n = 0, k;
    for (k in s.dist) { total += Number(k) * s.dist[k]; n += s.dist[k]; }
    $("ph-played").textContent = s.played;
    $("ph-avg").textContent = n ? (total / n).toFixed(1) : "0.0";
    $("ph-streak").textContent = s.streak;
    $("ph-max").textContent = s.max;
    var review = $("ph-review");
    review.textContent = "";
    st.rounds.forEach(function (r, i) {
      var li = document.createElement("li");
      li.textContent = (isRight(i) ? "Correct: " : "Missed: ") + r.p;
      review.appendChild(li);
    });
    tick();
  }

  function tick() {
    var el = $("ph-next-in");
    if (!el || $("ph-result").hidden) return;
    var now = new Date(), nx = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
    var ms = nx - now, h = Math.floor(ms / 3600000), m = Math.floor((ms % 3600000) / 60000);
    el.textContent = h + " h " + (m < 10 ? "0" : "") + m + " min";
  }

  function start(data) {
    st.epoch = data.epoch;
    st.idx = G.dayIndex(new Date(), data.epoch);
    st.rounds = G.pick(data.days, st.idx);
    $("ph-number").textContent = "Set " + (st.idx + 1);
    st.twist = TWISTS[new Date().getDay()];
    var tw = $("ph-twist");
    if (tw) { $("ph-twist-name").textContent = st.twist.name; $("ph-twist-text").textContent = st.twist.text; tw.hidden = false; }
    var saved = G.getGame(NAME);
    if (saved.today && saved.today.idx === st.idx) {
      st.picks = saved.today.picks || []; st.done = !!saved.today.done;
      st.cur = Math.min(st.picks.length, st.rounds.length - 1);
    }
    $("ph-next").addEventListener("click", next);
    window.PLShareText = shareText;   // the share row (share.js) reads this when the player taps a button
    window.setInterval(tick, 30000);
    $("ph-loading").hidden = true;
    $("ph-game").hidden = false;
    if (st.done) finish(false); else { $("ph-quiz").hidden = false; show(); }
  }

  fetch("/games/data/photo.json").then(function (r) { if (!r.ok) throw 0; return r.json(); }).then(function (d) { return G.ready.then(function () { start(d); }); }, function () {
    $("ph-loading").textContent = "Today's photographs could not be loaded. Check your connection and reload the page.";
  });
})();
