// Seat picker for labs and departments on /moderntex/. The server prices the order from the seat count alone
// (netlify/lib/seats.mjs); this table is only for showing the price, and a test keeps it equal to the server's.
(function () {
  var SEAT_PRICING = {"packs":[[5,1399],[10,1249],[15,1149],[20,1049]],"bulkMin":25,"bulkUnit":999,"max":500};

  var form = document.getElementById("seat-form");
  if (!form) return;
  var summary = document.getElementById("seat-summary");
  var buy = document.getElementById("seat-buy");
  var statusEl = document.getElementById("seat-status");
  var qty = document.getElementById("seat-qty");
  var referralCode = new URLSearchParams(window.location.search).get("ref") || "";

  function money(cents) {
    return "$" + (cents / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function unitFor(seats) {
    for (var i = 0; i < SEAT_PRICING.packs.length; i++) if (SEAT_PRICING.packs[i][0] === seats) return SEAT_PRICING.packs[i][1];
    if (seats >= SEAT_PRICING.bulkMin && seats <= SEAT_PRICING.max) return SEAT_PRICING.bulkUnit;
    return null;
  }
  function chosen() {
    var picked = form.querySelector('input[name="seats"]:checked');
    if (!picked) return null;
    if (picked.value !== "bulk") return parseInt(picked.value, 10);
    var n = parseInt(qty.value, 10);
    return isNaN(n) ? null : n;
  }
  function setStatus(msg, isError) {
    statusEl.textContent = msg;
    statusEl.classList.toggle("seat-error", Boolean(isError));
  }
  function refresh() {
    var seats = chosen();
    var unit = seats === null ? null : unitFor(seats);
    var bulkTotal = document.getElementById("seat-bulk-total");
    var bulkSeats = parseInt(qty.value, 10);
    var bulkUnit = isNaN(bulkSeats) ? null : unitFor(bulkSeats);
    bulkTotal.textContent = bulkUnit === null ? "" : money(bulkUnit * bulkSeats);
    if (unit === null) {
      summary.textContent = seats === null ? "Choose a number of seats." : "Seats from " + SEAT_PRICING.bulkMin + " to " + SEAT_PRICING.max + ". For fewer than 5, buy ModernTex at $19.99 each.";
      buy.disabled = true;
      buy.textContent = "Buy seats";
      return;
    }
    summary.textContent = seats + " seats at " + money(unit) + " each, " + money(unit * seats) + " in total. You receive " + seats + " license keys.";
    buy.disabled = false;
    buy.textContent = "Buy " + seats + " seats, " + money(unit * seats);
  }

  form.addEventListener("change", refresh);
  qty.addEventListener("input", function () {
    form.querySelector('input[value="bulk"]').checked = true;
    refresh();
  });
  buy.addEventListener("click", function () {
    var seats = chosen();
    if (seats === null || unitFor(seats) === null) return;
    buy.disabled = true;
    setStatus("Opening checkout…", false);
    fetch("/.netlify/functions/checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product: "moderntex-seats", seats: seats, ref: referralCode }),
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
        buy.disabled = false;
      });
  });

  form.querySelector('input[value="5"]').checked = true;
  refresh();
})();
