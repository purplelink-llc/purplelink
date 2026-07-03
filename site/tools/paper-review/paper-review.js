// Paper Review landing page logic.
// Owns the tier-aware checkout button: reads the selected tier radio,
// hits the Netlify checkout function with the product key, redirects to
// Stripe. The success_url returns to /tools/paper-review/upload/?session_id=…
(function () {
  var btn = document.getElementById("checkout-btn");
  var statusEl = document.getElementById("checkout-status");
  if (!btn) return;

  var TIER_LABELS = {
    "paper-review-standard": "Start review — $9",
    "paper-review-journal": "Start review — $11",
    "paper-review-deep": "Start review — $15",
  };

  function updateButton() {
    var chosen = (document.querySelector('input[name="tier"]:checked') || {}).value || "paper-review-standard";
    btn.textContent = TIER_LABELS[chosen] || "Start review";
  }

  document.querySelectorAll('input[name="tier"]').forEach(function (input) {
    input.addEventListener("change", updateButton);
  });
  updateButton();

  function setStatus(msg, isError) {
    if (!statusEl) return;
    if (isError) {
      statusEl.innerHTML = '<span class="bib-err">' + escapeHtml(msg) + "</span>";
    } else {
      statusEl.innerHTML =
        '<span class="tool-spinner" aria-hidden="true"></span>' + escapeHtml(msg);
    }
  }

  btn.addEventListener("click", function () {
    var product = (document.querySelector('input[name="tier"]:checked') || {}).value || "paper-review-standard";
    btn.disabled = true;
    setStatus("Opening checkout…", false);
    fetch("/.netlify/functions/checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product: product }),
    })
      .then(function (resp) {
        if (!resp.ok) return resp.json().then(function (p) { throw p; });
        return resp.json();
      })
      .then(function (data) {
        if (!data || !data.url) throw { detail: "Checkout did not return a redirect URL." };
        window.location.assign(data.url);
      })
      .catch(function (err) {
        var msg = (err && err.detail) || "Could not start checkout. Please try again.";
        setStatus(msg, true);
        btn.disabled = false;
      });
  });
})();
