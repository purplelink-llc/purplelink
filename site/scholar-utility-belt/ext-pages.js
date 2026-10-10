// /scholar-utility-belt/start/ and /scholar-utility-belt/uninstalled/
// The extension sends nothing; it only asks the browser to open these two pages (on a fresh install, and on
// uninstall). This file counts the visit as an ext_install / ext_uninstall event, with the extension version from
// ?v= as the detail, using the site's own beacon (analytics.js), and wires the one-tap reason buttons.
(function () {
  var page = document.body && document.body.getAttribute("data-ext-page");
  if (page !== "install" && page !== "uninstall") return;

  var m = /[?&]v=(\d{1,3}(?:\.\d{1,3}){1,3})(?:&|$)/.exec(location.search);
  var version = m ? m[1] : "unknown";
  var type = page === "install" ? "ext_install" : "ext_uninstall";

  // Once per tab, so reloading the page does not count it again.
  var key = "pl-" + type + "-" + version;
  var seen = false;
  try {
    seen = sessionStorage.getItem(key) === "1";
    if (!seen) sessionStorage.setItem(key, "1");
  } catch (e) { /* storage blocked: count it */ }
  if (!seen && typeof window.plTrack === "function") window.plTrack(type, version);

  // The reason buttons are tracked by analytics.js through their data-track attributes; this only shows the thanks.
  var group = document.getElementById("reasons");
  var thanks = document.getElementById("reason-thanks");
  if (!group || !thanks) return;
  group.addEventListener("click", function (ev) {
    var btn = ev.target && ev.target.closest && ev.target.closest("button");
    if (!btn) return;
    var buttons = group.querySelectorAll("button");
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].disabled = true;
      if (buttons[i] === btn) buttons[i].setAttribute("aria-pressed", "true");
    }
    thanks.hidden = false;
  });
})();
