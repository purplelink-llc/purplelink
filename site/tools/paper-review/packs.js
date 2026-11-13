// Volume-pack checkout — same button pattern as standalone tools, but the
// product comes from the radio group instead of a fixed data-product.
(function () {
  var btn = document.getElementById("checkout-btn");
  var statusEl = document.getElementById("checkout-status");
  if (!btn) return;

  var LABELS = {
    "paper-review-pack-5": "Buy pack — $99",
    "paper-review-pack-20": "Buy pack — $349",
  };

  function updateBtn() {
    var v = (document.querySelector('input[name="pack"]:checked') || {}).value || "paper-review-pack-5";
    btn.textContent = LABELS[v] || "Buy pack";
  }
  document.querySelectorAll('input[name="pack"]').forEach(function (i) {
    i.addEventListener("change", updateBtn);
  });
  updateBtn();

  // Free check run on this device in the last 30 days (set by preview.js): sent to checkout as a flag, never a time.
  function ranFreeCheck() {
    try {
      var at = Number(localStorage.getItem("pl_pr_preview_at"));
      return at > 0 && Date.now() - at < 30 * 86400000;
    } catch (e) { return false; }
  }

  btn.addEventListener("click", function () {
    var product = (document.querySelector('input[name="pack"]:checked') || {}).value || "paper-review-pack-5";
    btn.disabled = true;
    statusEl.innerHTML = '<span class="tool-spinner" aria-hidden="true"></span>Opening checkout…';
    fetch("/.netlify/functions/checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(ranFreeCheck() ? { product: product, pr_preview: 1 } : { product: product }),
    })
      .then(function (resp) {
        if (!resp.ok) return resp.json().then(function (p) { throw p; });
        return resp.json();
      })
      .then(function (data) {
        if (!data || !data.url) throw { detail: "Checkout did not return a URL." };
        window.location.assign(data.url);
      })
      .catch(function (err) {
        statusEl.innerHTML = '<span class="bib-err">' + escapeHtml((err && err.detail) || "Could not start checkout.") + "</span>";
        btn.disabled = false;
      });
  });
})();
