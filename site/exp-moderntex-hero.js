/*
 * Experiment moderntex-hero-screenshot: paired-day switchback, 56 UTC days, ModernTex page only.
 *
 * On B days the long tagline leaves the text column and sits below the hero, and the editor and PDF
 * screenshot moves up next to the trial button (on narrow screens, directly under the buy buttons).
 * On A days, outside the 56 days, with scripting off, or on any error, the page is untouched.
 *
 * Pre-registered schedule: days 1+2, 3+4, ... are pairs; one seeded fair coin per pair picks the B day
 * (python random.Random(seed); per pair, rng.random() < 0.5 puts B on the first day). The 28 pairs were drawn
 * with seeds counted up from 20261031 and the first draw that met both rules was used (20261039): each weekday has
 * 3 to 5 B days out of 8, and each of the four cells formed with the header-link test (exp-trial-link.js) has 12 to
 * 16 days, so the two tests do not run on the same days by accident. Result: 28 A days and 28 B days; cells
 * AA 15, AB 13, BA 13, BB 15 (header arm, hero arm). Start 2026-10-19 (Monday, UTC), last day 2026-12-13.
 * The arm is derived from the UTC date at analysis time; nothing is sent or stored, and analytics.js is not
 * involved. The page's data-exp-moderntex-hero attribute holds the arm ("A" or "B" inside the window, "off"
 * outside it, "error" if the B change could not be applied).
 *
 * Metric: trial_download events per ModernTex pageview, by day. The day is the unit, so 28 days per arm is
 * the effective sample, not the page views.
 *
 * To stop early: remove the script tag from site/moderntex/index.html, or set SCHEDULE to all "A".
 */
(function () {
  "use strict";

  var START = "2026-10-19";
  var SCHEDULE = "ABABABBAABABABBAABABABBAABBAABBAABABABBABAABBABAABBAABAB";

  var DAY_MS = 86400000;
  var start = Date.parse(START + "T00:00:00Z");

  function armAt(ms) {
    var day = Math.floor((ms - start) / DAY_MS);
    if (!(day >= 0 && day < SCHEDULE.length)) return "off";
    return SCHEDULE.charAt(day);
  }

  var root = document.documentElement;
  try {
    var arm = armAt(Date.now());
    root.dataset.expModerntexHero = arm;
    if (arm !== "B") return;

    var hero = document.querySelector(".app-hero");
    var tagline = hero && hero.querySelector(".app-hero-copy > .app-hero-tagline");
    var shot = hero && hero.querySelector(".app-hero-window");
    if (!tagline || !shot) {
      root.dataset.expModerntexHero = "error";
      return;
    }
    tagline.classList.add("app-hero-tagline-lower");
    hero.appendChild(tagline);
    hero.classList.add("exp-hero-shot");
  } catch (e) {
    root.dataset.expModerntexHero = "error";
  }
})();
