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

  // A referral link (?ref=CODE, from the footer of a shared report) is kept
  // for 30 days so it still counts after the visitor reads the sample or
  // comes back later. The backend decides whether it earns a credit.
  var REF_KEY = "pl_paper_ref";
  var REF_DAYS = 30;
  var referralCode = (new URLSearchParams(window.location.search).get("ref") || "").slice(0, 64);
  try {
    if (referralCode) {
      localStorage.setItem(REF_KEY, JSON.stringify({ code: referralCode, at: Date.now() }));
    } else {
      var saved = JSON.parse(localStorage.getItem(REF_KEY) || "null");
      if (saved && saved.code && Date.now() - saved.at < REF_DAYS * 86400000) referralCode = String(saved.code);
    }
  } catch (e) { /* storage blocked: the URL code still works */ }
  var refNote = document.getElementById("ref-note");
  if (referralCode && refNote) refNote.hidden = false;

  btn.addEventListener("click", function () {
    var product = (document.querySelector('input[name="tier"]:checked') || {}).value || "paper-review-standard";
    btn.disabled = true;
    setStatus("Opening checkout…", false);
    fetch("/.netlify/functions/checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product: product, ref: referralCode }),
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
