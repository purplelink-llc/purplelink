// /vitae/plus/ — the two plan buttons (monthly, annual). Same checkout call as
// /tools/paper-review/paid-tool-landing.js, which handles only one button per
// page. Status text is set with textContent; nothing is parsed as HTML.
(function () {
  var buttons = document.querySelectorAll(".plus-plan-btn[data-product]");
  var statusEl = document.getElementById("checkout-status");
  if (!buttons.length) return;
  var referralCode = new URLSearchParams(window.location.search).get("ref") || "";

  function setStatus(msg, isError) {
    if (!statusEl) return;
    while (statusEl.firstChild) statusEl.removeChild(statusEl.firstChild);
    if (!msg) return;
    if (isError) {
      var err = document.createElement("span");
      err.className = "bib-err";
      err.textContent = msg;
      statusEl.appendChild(err);
      return;
    }
    var spin = document.createElement("span");
    spin.className = "tool-spinner";
    spin.setAttribute("aria-hidden", "true");
    statusEl.appendChild(spin);
    statusEl.appendChild(document.createTextNode(msg));
  }

  function setDisabled(disabled) {
    for (var i = 0; i < buttons.length; i++) buttons[i].disabled = disabled;
  }

  function start(product) {
    setDisabled(true);
    try {
      setStatus("Opening checkout…", false);
    } catch (e) {
      /* status is cosmetic; never block checkout on it */
    }
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
        setDisabled(false);
      });
  }

  // Coming back from Stripe with the Back button can restore this page from the
  // back-forward cache with the buttons still disabled.
  window.addEventListener("pageshow", function (ev) {
    if (ev.persisted) {
      setDisabled(false);
      setStatus("", false);
    }
  });

  for (var i = 0; i < buttons.length; i++) {
    buttons[i].addEventListener("click", function (ev) {
      start(ev.currentTarget.getAttribute("data-product"));
    });
  }
})();
