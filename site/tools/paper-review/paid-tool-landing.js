// Shared landing-page checkout button for adjacent paid tools.
// Each landing page sets data-product="..." on the checkout button.
(function () {
  var btn = document.getElementById("checkout-btn");
  var statusEl = document.getElementById("checkout-status");
  if (!btn) return;
  var product = btn.dataset.product || "paper-review-standard";
  var referralCode = new URLSearchParams(window.location.search).get("ref") || "";

  function setStatus(msg, isError) {
    if (!statusEl) return;
    if (isError) statusEl.innerHTML = '<span class="bib-err">' + escapeHtml(msg) + "</span>";
    else statusEl.innerHTML = '<span class="tool-spinner" aria-hidden="true"></span>' + escapeHtml(msg);
  }

  btn.addEventListener("click", function () {
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
        setStatus((err && err.detail) || "Could not start checkout.", true);
        btn.disabled = false;
      });
  });
})();
