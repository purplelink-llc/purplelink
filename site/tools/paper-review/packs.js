// Volume-pack checkout — same button pattern as standalone tools, but the
// product comes from the radio group instead of a fixed data-product.
(function () {
  var btn = document.getElementById("checkout-btn");
  var statusEl = document.getElementById("checkout-status");
  if (!btn) return;

  var LABELS = {
    "paper-review-pack-5": "Buy pack — $38",
    "paper-review-pack-20": "Buy pack — $150",
  };

  function updateBtn() {
    var v = (document.querySelector('input[name="pack"]:checked') || {}).value || "paper-review-pack-5";
    btn.textContent = LABELS[v] || "Buy pack";
  }
  document.querySelectorAll('input[name="pack"]').forEach(function (i) {
    i.addEventListener("change", updateBtn);
  });
  updateBtn();

  btn.addEventListener("click", function () {
    var product = (document.querySelector('input[name="pack"]:checked') || {}).value || "paper-review-pack-5";
    btn.disabled = true;
    statusEl.innerHTML = '<span class="tool-spinner" aria-hidden="true"></span>Opening checkout…';
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
        if (!data || !data.url) throw { detail: "Checkout did not return a URL." };
        window.location.assign(data.url);
      })
      .catch(function (err) {
        statusEl.innerHTML = '<span class="bib-err">' + escapeHtml((err && err.detail) || "Could not start checkout.") + "</span>";
        btn.disabled = false;
      });
  });
})();
