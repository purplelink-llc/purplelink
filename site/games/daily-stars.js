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

  function show(sign) {
    current = sign;
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
    var s = G.getGame("daily-stars");
    s.sign = sign;
    G.setGame("daily-stars", s);
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

  fetch("/games/data/stars.json").then(function (r) { if (!r.ok) throw 0; return r.json(); }).then(start, function () {
    $("st-loading").textContent = "Today's readings could not be loaded. Check your connection and reload the page.";
  });
})();
