/* Buddy chat launcher (docs/designs/buddy-chat.md, section 1).
   Adds chat.css and, once it has loaded, draws only the round button; chat.js loads on the first click.
   The stylesheet is added from here, not from <head>, so it never holds up the page. */
(function () {
  "use strict";
  if (window.__buddyChat) return;
  window.__buddyChat = true;

  // Holdout (docs/designs/buddy-chat.md, "Conversion pass", section 3; Ben, 2026-11-04: "start the holdout on 12-28").
  // Paired-day switchback over 56 UTC days from 2026-12-28 to 2027-02-21, drawn by scripts/draw_buddy_schedule.py:
  // seed 20261228, the first seed tried; B days per weekday Mon..Sun 3, 5, 3, 5, 5, 3, 4. On A days the launcher is
  // not drawn. On B days, outside the window, with a malformed schedule, or on any error here, it is drawn as before.
  // The arm is read from the UTC date when the page loads and kept for the page's life; nothing is sent or stored.
  // <html data-exp-buddy-chat> says "A", "B" or "off". To stop early, or to keep the chat every day afterwards, set
  // SCHEDULE to all "B".
  var START = "2026-12-28";
  var SCHEDULE = "BAABBABABAABBAABBABABAABBAABBABABAABBABABAABABBABABABABA";
  var arm = "off";
  try {
    var day = Math.floor((Date.now() - Date.parse(START + "T00:00:00Z")) / 86400000);
    if (/^[AB]+$/.test(SCHEDULE) && day >= 0 && day < SCHEDULE.length) arm = SCHEDULE.charAt(day);
  } catch (e) { arm = "off"; }
  try { document.documentElement.dataset.expBuddyChat = arm; } catch (e) {}
  if (arm === "A") return;

  var BASE = "/buddy-chat/";
  var FACE =
    '<svg class="bc-face" viewBox="0 0 100 100" aria-hidden="true" focusable="false">' +
    '<path class="bc-ear" d="M10 40 L20 6 L42 28 Z"/><path class="bc-ear" d="M90 40 L80 6 L58 28 Z"/>' +
    '<path class="bc-ear-in" d="M17 33 L22 15 L34 28 Z"/><path class="bc-ear-in" d="M83 33 L78 15 L66 28 Z"/>' +
    '<rect class="bc-head" x="3" y="22" width="94" height="72" rx="34"/>' +
    '<ellipse class="bc-muzzle" cx="50" cy="72" rx="22" ry="15"/>' +
    '<g class="bc-eyes"><g class="bc-eye-open"><circle class="bc-ink" cx="32" cy="50" r="6.5"/><circle class="bc-ink" cx="68" cy="50" r="6.5"/>' +
    '<circle class="bc-glint" cx="34.2" cy="47.8" r="2"/><circle class="bc-glint" cx="70.2" cy="47.8" r="2"/></g>' +
    '<g class="bc-eye-happy"><path class="bc-ink-line" d="M25 52 Q32 42 39 52"/><path class="bc-ink-line" d="M61 52 Q68 42 75 52"/></g></g>' +
    '<ellipse class="bc-ink" cx="50" cy="65" rx="7" ry="5"/>' +
    '<rect class="bc-tongue" x="45" y="76" width="10" height="13" rx="5"/>' +
    "</svg>";
  window.__buddyFace = FACE;

  function start() {
    var css = document.createElement("link");
    css.rel = "stylesheet";
    css.href = BASE + "chat.css";
    css.onload = draw;  // an unstyled button would flash in the page; with no stylesheet there is no button
    document.head.appendChild(css);
  }

  function draw() {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "bc-launcher";
    btn.setAttribute("aria-label", "Open chat with Buddy");
    btn.setAttribute("aria-haspopup", "dialog");
    btn.innerHTML = FACE;
    if (document.body.classList.contains("has-sticky-cta")) btn.classList.add("bc-above-cta");
    document.body.appendChild(btn);

    var loading = false;
    btn.addEventListener("click", function () {
      if (window.BuddyChat) { window.BuddyChat.toggle(btn); return; }
      if (loading) return;
      loading = true;
      var s = document.createElement("script");
      s.src = BASE + "chat.js";
      s.onload = function () { window.BuddyChat.toggle(btn); };
      document.head.appendChild(s);
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
