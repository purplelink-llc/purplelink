// Paper Review landing page logic.
// Owns the tier-aware checkout button: reads the selected tier radio,
// hits the Netlify checkout function with the product key, redirects to
// Stripe. The success_url returns to /tools/paper-review/upload/?session_id=…
(function () {
  // A review started on this device and not yet opened: offer the way back.
  try {
    var resume = document.getElementById("pr-resume");
    var savedStatus = JSON.parse(localStorage.getItem("pl_pr_status") || "null");
    if (resume && savedStatus && typeof savedStatus.url === "string" && Date.now() - savedStatus.at < 86400000 &&
        /^\/tools\/paper-review\/status\/\?token=[^&#\s]+$/.test(savedStatus.url)) {
      var resumeLink = resume.querySelector("a");
      if (resumeLink) resumeLink.href = savedStatus.url;
      resume.hidden = false;
    }
  } catch (e) { /* storage blocked: nothing to offer */ }

  var btn = document.getElementById("checkout-btn");
  var statusEl = document.getElementById("checkout-status");
  if (!btn) return;

  var TIER_LABELS = {
    "paper-review-standard": "Start a review, $9",
    "paper-review-journal": "Start a review, $11",
    "paper-review-deep": "Start a review, $15",
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

  // Free check run on this device in the last 30 days (set by preview.js): sent to checkout as a flag, never a time.
  function ranFreeCheck() {
    try {
      var at = Number(localStorage.getItem("pl_pr_preview_at"));
      return at > 0 && Date.now() - at < 30 * 86400000;
    } catch (e) { return false; }
  }

  function checkoutBody(product, clickSrc) {
    var body = { product: product, ref: referralCode };
    if (ranFreeCheck()) body.pr_preview = 1;
    if (clickSrc) body.src = clickSrc;
    return body;
  }

  btn.addEventListener("click", function () {
    var product = (document.querySelector('input[name="tier"]:checked') || {}).value || "paper-review-standard";
    // The free-check upsell sets data-src="preview" so the click is counted as <product>+preview.
    var clickSrc = btn.dataset.src || "";
    btn.removeAttribute("data-src");
    btn.disabled = true;
    setStatus("Opening checkout…", false);
    fetch("/.netlify/functions/checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(checkoutBody(product, clickSrc)),
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
