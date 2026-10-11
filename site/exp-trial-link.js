/*
 * Experiment trial-link-in-header: paired-day switchback, 70 UTC days.
 *
 * On B days a "Free trial" link to the ModernTex trial section is added to the header.
 * On A days, outside the 70 days, with scripting off, or on any error, the header is untouched.
 *
 * Pre-registered schedule: days 1+2, 3+4, ... are pairs; one seeded fair coin per pair picks the
 * B day (python random.Random(seed); per pair, rng.random() < 0.5 puts B on the first day). The first draw (seed
 * 20261019) was rejected for an uneven weekday split and the draw was repeated with seeds 20261020, 20261021 (used)
 * until each weekday had 4 to 6 B days out of 10 and each half had 16 to 19 B days.
 * 35 pairs, 35 A days and 35 B days. Start 2026-10-19 (Monday, UTC), last day 2026-12-27.
 * The arm is derived from the UTC date at analysis time; nothing is sent or stored, and
 * analytics.js is not involved. The page's data-exp-trial-link attribute holds the arm
 * ("A" or "B" inside the window, "off" outside it).
 *
 * To stop early: remove the exp-trial-link loader from site.js, or set SCHEDULE to all "A".
 */
(function () {
  "use strict";

  var START = "2026-10-19";
  var SCHEDULE = "ABBAABBABABAABBABAABBAABABBABABABAABBABABAABABBABAABBAABBAABBAABBABABA";

  var DAY_MS = 86400000;
  var start = Date.parse(START + "T00:00:00Z");

  function armAt(ms) {
    var day = Math.floor((ms - start) / DAY_MS);
    if (!(day >= 0 && day < SCHEDULE.length)) return "off";
    return SCHEDULE.charAt(day);
  }

  try {
    var arm = armAt(Date.now());
    document.documentElement.dataset.expTrialLink = arm;
    if (arm !== "B") return;

    var nav = document.querySelector('.topbar nav[aria-label="Primary navigation"]');
    if (!nav || nav.querySelector("[data-exp-trial-link]")) return;

    var link = document.createElement("a");
    link.href = "/moderntex/#buy";
    link.textContent = "Free trial";
    link.setAttribute("data-exp-trial-link", "");
    link.setAttribute("aria-label", "Free trial of ModernTex");
    link.title = "The free 7-day trial of ModernTex, a LaTeX editor for Mac";
    nav.appendChild(link);
  } catch (e) {
    /* any failure leaves the header as it is */
  }
})();
