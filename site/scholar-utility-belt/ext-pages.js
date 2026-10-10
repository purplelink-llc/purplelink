// /scholar-utility-belt/start/ and /scholar-utility-belt/uninstalled/
// The extension sends nothing; it only asks the browser to open these two pages (on a fresh install, and on
// uninstall). This file counts the visit as an ext_install / ext_uninstall event, with the extension version from
// ?v= as the detail, using the site's own beacon (analytics.js), and wires the one-tap reason buttons and the optional comment.
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

  // The reason buttons are counted by analytics.js through their data-track attributes. After one is chosen this shows
  // the thanks and an optional comment box. The comment goes to a Netlify Form (scholar-uninstall-feedback) together
  // with the chosen reason and the version; it carries no name or email, and none is asked for.
  var group = document.getElementById("reasons");
  var thanks = document.getElementById("reason-thanks");
  var form = document.getElementById("uninstall-form");
  var wrap = document.getElementById("uf-wrap");   // the form's container carries the hidden state: the site's form styles override [hidden] on the form itself
  if (!group || !thanks) return;
  var chosen = "";
  group.addEventListener("click", function (ev) {
    var btn = ev.target && ev.target.closest && ev.target.closest("button");
    if (!btn) return;
    var buttons = group.querySelectorAll("button");
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].disabled = true;
      if (buttons[i] === btn) buttons[i].setAttribute("aria-pressed", "true");
    }
    chosen = btn.getAttribute("data-track-meta") || "";
    thanks.hidden = false;
    if (form) {
      form.elements["reason"].value = chosen;
      form.elements["version"].value = version;
      wrap.hidden = false;
    }
  });

  if (!form) return;
  var status = document.getElementById("uf-status");
  var done = document.getElementById("uf-done");
  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    if (form.elements["bot-field"].value) return;
    var comment = form.elements["comment"].value.trim();
    if (!comment) {
      status.textContent = "Write a sentence or two first, or just close this page: your choice is already saved.";
      form.elements["comment"].focus();
      return;
    }
    var btn = form.querySelector("button[type=submit]");
    btn.disabled = true;
    status.textContent = "Sending\u2026";
    var body = new URLSearchParams();
    body.set("form-name", "scholar-uninstall-feedback");
    body.set("reason", chosen);
    body.set("version", version);
    body.set("comment", comment.slice(0, 1000));
    fetch("/", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: body.toString() })
      .then(function (r) {
        if (!r.ok) throw new Error(String(r.status));
        wrap.hidden = true;
        done.hidden = false;
        done.focus();
        // only that a comment was left, and under which reason; the text itself never goes to the beacon
        if (typeof window.plTrack === "function") window.plTrack("ext_uninstall_comment", chosen);
      })
      .catch(function () {
        btn.disabled = false;
        status.textContent = "That did not go through. Try again in a minute, or email ben@purplelink.llc.";
      });
  });
})();
