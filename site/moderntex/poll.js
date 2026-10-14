// ModernTex page: after someone clicks a trial download, offer (never require) one question, "what are you trying
// to do with ModernTex?". The answer goes to the count-only function (netlify/functions/signal.mjs) as one of seven
// fixed codes and nothing else: no email, no identifier. The download itself is never blocked or delayed. Without
// scripts the form stays hidden. The form nearest the clicked link is shown.
(function () {
  var forms = [].slice.call(document.querySelectorAll("[data-ask-poll]"));
  if (!forms.length) return;
  var CODES = ["paper", "thesis", "coauthors", "replace-overleaf", "course-notes", "looking", "other"];
  var KEY = "pl_trialpoll_done";
  var done = false;
  try { done = sessionStorage.getItem(KEY) === "1"; } catch (e) { /* ask anyway */ }
  if (done) return;

  // On a phone or a PC the page offers an emailed link instead of a download (site.js); no question then.
  var ua = navigator.userAgent;
  var onMac = /Macintosh/.test(ua) && !/iPhone|iPad|iPod/.test(ua) && !(navigator.maxTouchPoints > 1);
  if (!onMac) return;

  [].slice.call(document.querySelectorAll('a[href*="moderntex-download?trial=1"]')).forEach(function (a) {
    a.addEventListener("click", function () {
      if (done) return;
      var scope = a.closest("section, .app-hero-copy") || document;
      var form = scope.querySelector("[data-ask-poll]") || forms[0];
      form.hidden = false;
    });
  });

  function finish(form, msg) {
    done = true;
    try { sessionStorage.setItem(KEY, "1"); } catch (e) { /* ignore */ }
    if (msg) {
      var s = form.querySelector("[data-ask-status]");
      form.querySelector("fieldset").hidden = true;
      form.querySelector(".ask-poll-actions").hidden = true;
      s.textContent = msg;
      forms.forEach(function (f) { if (f !== form) f.hidden = true; });
    } else {
      forms.forEach(function (f) { f.hidden = true; });
    }
  }

  forms.forEach(function (form) {
    var status = form.querySelector("[data-ask-status]");
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var checked = form.querySelector("input[type=radio]:checked");
      if (!checked || CODES.indexOf(checked.value) === -1) {
        status.textContent = "Choose one, or skip.";
        return;
      }
      var btn = form.querySelector("button[type=submit]");
      btn.disabled = true;
      fetch("/.netlify/functions/signal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind: "trialpoll", value: checked.value }),
        keepalive: true
      }).then(function (r) {
        if (r.ok) finish(form, "Thanks. Counted.");
        else if (r.status === 429) finish(form, "Thanks. That is enough answers from this address for today.");
        else throw new Error("http");
      }).catch(function () {
        btn.disabled = false;
        status.textContent = "That did not go through. You can skip it.";
      });
    });
    form.querySelector("[data-ask-skip]").addEventListener("click", function () { finish(form, ""); });
  });
})();
