// Outbound Veil: after someone clicks a trial download, offer (never require) a setup email and one reminder
// before the trial ends. The download itself is never blocked or delayed. See
// netlify/functions/outbound-veil-reminder.mjs for what is stored and for how long.
(function () {
  var form = document.querySelector("[data-ov-trial-signup]");
  if (!form) return;
  var status = form.querySelector("[data-ov-trial-status]");
  var btn = form.querySelector("button[type=submit]");
  var API = "/.netlify/functions/outbound-veil-reminder";

  document.addEventListener("click", function (e) {
    var a = e.target && e.target.closest && e.target.closest("a[href]");
    if (a && a.getAttribute("href").indexOf("outbound-veil-download?trial=1") !== -1) form.hidden = false;
  }, true);

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var email = form.email.value.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      status.textContent = "That address does not look complete.";
      form.email.focus();
      return;
    }
    btn.disabled = true;
    status.textContent = "Sending...";
    fetch(API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email, website: form.website.value }),
    })
      .then(function (r) {
        if (r.status === 429) throw new Error("rate");
        if (!r.ok) throw new Error("http");
        status.textContent = "Thanks. The setup guide is on its way to " + email + ".";
        form.email.disabled = true;
      })
      .catch(function () {
        btn.disabled = false;
        status.textContent = "That did not go through. Try again in a minute, or email ben@purplelink.llc.";
      });
  });
})();
