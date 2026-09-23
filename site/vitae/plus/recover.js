// /vitae/plus/recover/ — ask vitae-license to email a current Vitae Plus key to the
// address used at checkout. The answer is the same whether or not a subscription matched.
(function () {
  var form = document.getElementById("recover-form");
  var status = document.getElementById("recover-status");
  if (!form || !status) return;
  var button = form.querySelector("button");

  function show(text, ok) {
    status.textContent = text;
    status.className = "subscribe-status " + (ok ? "subscribe-status--ok" : "subscribe-status--err");
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var email = (form.elements.email.value || "").trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) {
      show("Enter the email address you used at checkout.", false);
      return;
    }
    button.disabled = true;
    show("Sending…", true);
    fetch("/.netlify/functions/vitae-license", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ recover: email })
    })
      .then(function (resp) {
        return resp.json().catch(function () { return {}; }).then(function (body) {
          if (resp.ok) {
            show("If that address has a Vitae Plus subscription, a current key is on its way. It can take a few minutes.", true);
          } else {
            show(body.detail || "Something went wrong. Please try again later.", false);
          }
        });
      })
      .catch(function () {
        show("Could not reach purplelink.llc. Check your connection and try again.", false);
      })
      .then(function () { button.disabled = false; });
  });
})();
