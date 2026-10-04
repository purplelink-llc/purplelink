/* Daily Stars: today's reading for each sign. Entertainment only. */
(function () {
  "use strict";
  var G = window.PLGames;
  if (!G) return;
  var $ = function (id) { return document.getElementById(id); };
  var SIGNS = [
    ["Aries", "Mar 21 to Apr 19"], ["Taurus", "Apr 20 to May 20"], ["Gemini", "May 21 to Jun 20"],
    ["Cancer", "Jun 21 to Jul 22"], ["Leo", "Jul 23 to Aug 22"], ["Virgo", "Aug 23 to Sep 22"],
    ["Libra", "Sep 23 to Oct 22"], ["Scorpio", "Oct 23 to Nov 21"], ["Sagittarius", "Nov 22 to Dec 21"],
    ["Capricorn", "Dec 22 to Jan 19"], ["Aquarius", "Jan 20 to Feb 18"], ["Pisces", "Feb 19 to Mar 20"]
  ];
  var MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  var today = (function () {
    var d = new Date(), p = function (n) { return (n < 10 ? "0" : "") + n; };
    return { key: d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate()), date: d };
  })();
  var data = null, current = null, tracked = false;
  // Lucky extras: picked from the sign and the date, the same for everyone. Entertainment only, like the readings.
  var COLORS = ["Violet", "Amber", "Teal", "Coral", "Indigo", "Green", "Rose", "Sky"];
  var MOODS = ["Calm", "Curious", "Bold", "Restless", "Generous", "Focused", "Playful", "Reflective"];
  function hash(str) { var h = 2166136261; for (var i = 0; i < str.length; i++) h = Math.imul(h ^ str.charCodeAt(i), 16777619); return h >>> 0; }
  function hour(h) { return (h % 12 === 0 ? 12 : h % 12) + (h < 12 ? " am" : " pm"); }
  function luckyItems(sign) {
    var h = hash(sign + "|" + today.key);
    return [["Lucky number", String(h % 99 + 1)], ["Lucky color", COLORS[(h >>> 7) % COLORS.length]], ["Mood", MOODS[(h >>> 13) % MOODS.length]], ["Best hour", hour(7 + (h >>> 19) % 14)]];
  }
  function lucky(sign) {
    var box = $("st-lucky");
    if (!box) return;
    box.textContent = "";
    var items = luckyItems(sign);
    items.forEach(function (it) {
      var dt = document.createElement("dt"), dd = document.createElement("dd");
      dt.textContent = it[0]; dd.textContent = it[1];
      if (it[0] === "Lucky color") { var sw = document.createElement("i"); sw.className = "stars-sw"; sw.setAttribute("data-c", it[1].toLowerCase()); sw.setAttribute("aria-hidden", "true"); dd.insertBefore(sw, dd.firstChild); }
      var wrap = document.createElement("div"); wrap.appendChild(dt); wrap.appendChild(dd); box.appendChild(wrap);
    });
    pair();
  }
  function pair() {
    var sel = $("st-pair"), out = $("st-pair-out");
    if (!sel || !out || !current) return;
    if (!sel.value) { out.textContent = ""; return; }
    var key = [current, sel.value].sort().join("+"), pct = 40 + hash(key + "|" + today.key) % 61;
    var word = pct >= 85 ? "Easy company today." : pct >= 65 ? "A good match for today." : "Worth a little patience.";
    out.textContent = current + " and " + sel.value + ": " + pct + "%. " + word;
  }

  function show(sign) {
    current = sign;
    lucky(sign);
    var day = data && data.days[today.key];
    Array.prototype.forEach.call(document.querySelectorAll("#st-signs button"), function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-sign") === sign ? "true" : "false");
    });
    var range = "";
    SIGNS.forEach(function (s) { if (s[0] === sign) range = s[1]; });
    $("st-name").textContent = sign;
    $("st-range").textContent = range;
    $("st-text").textContent = day && day.signs[sign] ? day.signs[sign] : "";
    $("st-card").hidden = false;
    window.PLShareText = function () {
      var t = $("st-text").textContent, first = (t.match(/^.*?[.!?](\s|$)/) || [t])[0].trim();
      var li = luckyItems(sign);
      return "Daily Stars, " + sign + " (for entertainment): " + first + "\nLucky number " + li[0][1] + ", lucky color " + li[1][1] + ".\n\nhttps://purplelink.llc/games/daily-stars/";
    };
    var s = G.getGame("daily-stars");
    s.sign = sign;
    var idx = G.dayIndex(new Date(), "2026-10-04");
    var firstToday = (s.viewed || []).indexOf(idx) < 0;
    s.viewed = (s.viewed || []).filter(function (x) { return x !== idx; }).concat([idx]).slice(-120);
    G.setGame("daily-stars", s);
    if (window.PLAch) window.PLAch.check({ game: "daily-stars", idx: idx, fresh: firstToday });
    if (!tracked) { tracked = true; G.track("game_start", "daily-stars"); }
  }

  function start(d) {
    data = d;
    $("st-date").textContent = MONTHS[today.date.getMonth()] + " " + today.date.getDate() + ", " + today.date.getFullYear();
    var day = d.days[today.key];
    var list = $("st-signs");
    SIGNS.forEach(function (s) {
      var li = document.createElement("li");
      var b = document.createElement("button");
      b.type = "button";
      b.setAttribute("data-sign", s[0]);
      b.setAttribute("aria-pressed", "false");
      b.textContent = s[0];
      var sm = document.createElement("span");
      sm.textContent = s[1];
      b.appendChild(sm);
      b.addEventListener("click", function () { show(s[0]); });
      li.appendChild(b);
      list.appendChild(li);
    });
    var sel = $("st-pair");
    if (sel) {
      var first = document.createElement("option"); first.value = ""; first.textContent = "Choose a sign"; sel.appendChild(first);
      SIGNS.forEach(function (s) { var o = document.createElement("option"); o.value = s[0]; o.textContent = s[0]; sel.appendChild(o); });
      sel.addEventListener("change", pair);
    }
    $("st-loading").hidden = true;
    if (!day) {
      $("st-missing").hidden = false;
      return;
    }
    $("st-game").hidden = false;
    $("st-sky").textContent = "The moon today: " + day.moon + " (approximate).";
    var all = $("st-all");
    SIGNS.forEach(function (s) {
      var det = document.createElement("details");
      var sum = document.createElement("summary");
      sum.textContent = s[0];
      var p = document.createElement("p");
      p.textContent = day.signs[s[0]] || "";
      det.appendChild(sum); det.appendChild(p);
      all.appendChild(det);
    });
    var saved = G.getGame("daily-stars").sign;
    var known = SIGNS.some(function (s) { return s[0] === saved; });
    if (known) show(saved);
  }

  fetch("/games/data/stars.json").then(function (r) { if (!r.ok) throw 0; return r.json(); }).then(function (d) { return G.ready.then(function () { start(d); }); }, function () {
    $("st-loading").textContent = "Today's readings could not be loaded. Check your connection and reload the page.";
  });
})();
