// Legroom and Keyfeel: after someone clicks a trial download, offer (never require) a setup email and one
// reminder before the trial ends. The download itself is never blocked or delayed, and nothing is stored in the
// browser. Each form says which function it posts to (data-reminder-api) and which download link reveals it
// (data-reminder-link). See netlify/lib/trial-reminder.mjs for what the server stores and for how long.
(function () {
  var forms = Array.prototype.slice.call(document.querySelectorAll("[data-reminder-signup]"));
  if (!forms.length) return;
  var linkKey = forms[0].getAttribute("data-reminder-link");

  document.addEventListener("click", function (e) {
    var a = e.target && e.target.closest && e.target.closest("a[href]");
    if (!a || !linkKey || a.getAttribute("href").indexOf(linkKey) === -1) return;
    var scope = a.closest("section, .app-hero-copy");
    var form = (scope && scope.querySelector("[data-reminder-signup]")) || forms[0];
    form.hidden = false;
  }, true);

  forms.forEach(function (form) {
    var status = form.querySelector("[data-reminder-status]");
    var btn = form.querySelector("button[type=submit]");
    var api = form.getAttribute("data-reminder-api");

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var email = form.email.value.trim();
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        status.textContent = "That address does not look complete.";
        form.email.focus();
        return;
      }
      btn.disabled = true;
      status.textContent = "Sending…";
      fetch(api, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email, website: form.website.value }),
      })
        .then(function (r) {
          if (r.status === 429) throw new Error("rate");
          if (!r.ok) throw new Error("http");
          return r.json();
        })
        .then(function (data) {
          status.textContent = data && data.already
            ? "That address asked for this in the last day. Check your inbox for the setup email."
            : "Thanks. The setup email is on its way to " + email + ".";
          form.email.disabled = true;
        })
        .catch(function () {
          btn.disabled = false;
          status.textContent = "That did not go through. Try again in a minute, or email ben@purplelink.llc.";
        });
    });
  });
})();
