// Post-pack-purchase success page — fetches the token list from the
// redeem-session endpoint (which returns the full list for pack
// purchases) and renders them as a copyable table.
(function () {
  var redeemEl = document.getElementById("redeem-status");
  var pane = document.getElementById("tokens-pane");
  var table = document.getElementById("tokens-table");
  var sessionId = new URLSearchParams(window.location.search).get("session_id");

  function setStatus(msg, isError) {
    if (!redeemEl) return;
    redeemEl.textContent = msg;
    redeemEl.classList.toggle("error", !!isError);
  }

  function showTokens(tokens, unusedTokens) {
    var unused = {};
    (unusedTokens || tokens).forEach(function (t) { unused[t] = true; });
    var rows = '<thead><tr><th>Token</th><th>Status</th><th>Action</th></tr></thead><tbody>';
    tokens.forEach(function (t) {
      var isUsed = !unused[t];
      rows += '<tr>';
      rows += '<td style="font-family:monospace;font-size:0.8rem;word-break:break-all">' + escapeHtml(t) + '</td>';
      rows += '<td>' + (isUsed ? 'Used' : 'Unused') + '</td>';
      rows += '<td>' + (isUsed
        ? '<button class="btn btn-secondary" type="button" disabled aria-disabled="true">Already used</button>'
        : '<a class="btn btn-secondary" href="/tools/paper-review/upload/?direct_token=' + encodeURIComponent(t) + '">Use this token</a>') + '</td>';
      rows += '</tr>';
    });
    rows += '</tbody>';
    table.innerHTML = rows;
    pane.hidden = false;
    redeemEl.hidden = true;
  }

  function redeem(attempt) {
    attempt = attempt || 1;
    fetch(API_BASE + "/paper-review/redeem-session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    })
      .then(function (resp) {
        if (resp.status === 404) {
          if (attempt < 15) {
            setStatus("Waiting on payment confirmation… (retry " + attempt + ")", false);
            setTimeout(function () { redeem(attempt + 1); }, 2000);
            return null;
          }
          throw { detail: "Payment confirmation didn't arrive. Email ben@purplelink.llc with your Stripe receipt." };
        }
        if (!resp.ok) return resp.json().then(function (p) { throw p; });
        return resp.json();
      })
      .then(function (data) {
        if (!data) return;
        var tokens = data.tokens || [];
        if (tokens.length === 0) {
          setStatus("No tokens were minted — please contact support.", true); return;
        }
        showTokens(tokens, data.unused_tokens);
      })
      .catch(function (err) {
        setStatus((err && err.detail) || "Could not load tokens.", true);
      });
  }

  if (!sessionId) {
    setStatus("Missing session ID. Restart from the volume-pack page.", true); return;
  }
  redeem();
})();
