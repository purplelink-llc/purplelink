// Live "ready to send" list for the draft upload page. It only reads the form (input.files and
// textarea values) and never touches the nodes that paid-tool-upload.js owns.
(function () {
  "use strict";
  var list = document.getElementById("rr-ready-list");
  var live = document.getElementById("rr-ready-live");
  var form = document.getElementById("upload-form");
  if (!list || !live || !form) return;

  var items = Array.prototype.slice.call(list.querySelectorAll("li[data-ready-for]"));
  var lastCount = -1;

  function filled(el) {
    if (!el) return false;
    if (el.type === "file") return !!(el.files && el.files.length > 0);
    return (el.value || "").trim().length > 0;
  }

  function update(announce) {
    var requiredTotal = 0;
    var requiredDone = 0;
    var count = 0;
    items.forEach(function (li) {
      var el = document.getElementById(li.getAttribute("data-ready-for"));
      var done = filled(el);
      var required = li.getAttribute("data-required") === "1";
      li.setAttribute("data-done", done ? "1" : "0");
      var state = li.querySelector(".rr-ready-state");
      if (state) state.textContent = done ? "Added" : (required ? "Needed" : "Optional, left out");
      if (done) count += 1;
      if (required) { requiredTotal += 1; if (done) requiredDone += 1; }
    });
    var ready = requiredDone === requiredTotal;
    list.setAttribute("data-ready", ready ? "1" : "0");
    if (announce && count !== lastCount) {
      live.textContent = ready
        ? "Everything required is added. You can draft your response letter."
        : requiredDone + " of " + requiredTotal + " required items added.";
    }
    lastCount = count;
  }

  function onChange() { update(true); }
  ["file-input", "revised-input", "reviewer-input", "notes-input"].forEach(function (id) {
    var el = document.getElementById(id);
    if (!el) return;
    el.addEventListener("input", onChange);
    el.addEventListener("change", onChange);
  });
  // The drop zones set input.files on drop in the bubble phase, so read after it settles.
  ["file-input-zone", "revised-input-zone"].forEach(function (id) {
    var z = document.getElementById(id);
    if (z) z.addEventListener("drop", function () { setTimeout(onChange, 0); }, true);
  });

  // Run when the form is shown (restoreDraft fills textareas without firing input).
  new MutationObserver(function () { if (!form.hidden) update(false); })
    .observe(form, { attributes: true, attributeFilter: ["hidden"] });
  update(false);
})();
