// Checkout buttons for lab plans and the Publication Pack. Same call as packs.js:
// POST the product key, then send the buyer to the Stripe URL.
(function () {
  var buttons = document.querySelectorAll("[data-lab-product]");
  if (!buttons.length) return;

  function setStatus(group, msg, isError) {
    var el = group && group.querySelector("[data-lab-status]");
    if (!el) return;
    el.textContent = msg;
    el.classList.toggle("error", !!isError);
  }

  function setGroupDisabled(group, disabled) {
    group.querySelectorAll("[data-lab-product]").forEach(function (b) { b.disabled = disabled; });
  }

  buttons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      var group = btn.closest("[data-lab-buy]");
      if (!group) return;
      setGroupDisabled(group, true);
      setStatus(group, "Opening checkout...", false);
      fetch("/.netlify/functions/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ product: btn.getAttribute("data-lab-product") }),
      })
        .then(function (resp) {
          return resp.json().catch(function () { return {}; }).then(function (data) {
            if (!resp.ok) throw data;
            return data;
          });
        })
        .then(function (data) {
          if (!data || !data.url) throw {};
          window.location.assign(data.url);
        })
        .catch(function (err) {
          var detail = err && (err.detail || err.error);
          setStatus(group, (typeof detail === "string" && detail ? detail + " " : "Checkout could not start. ") + "Try again, or email ben@purplelink.llc and I will set it up by invoice.", true);
          setGroupDisabled(group, false);
        });
    });
  });
})();
