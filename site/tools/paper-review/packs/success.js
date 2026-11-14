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
      rows += '<td class="success-token">' + escapeHtml(t) + '</td>';
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

  var heading = document.querySelector("main h1");
  var lede = document.querySelector(".tools-hero p:not(.eyebrow)");
  var eyebrow = document.querySelector(".tools-hero .eyebrow");
  var intro = document.getElementById("tokens-intro");
  var footnote = document.getElementById("tokens-footnote");
  var groupsPane = document.getElementById("groups-pane");
  var groupsList = document.getElementById("groups-list");

  function setText(el, text) { if (el) el.textContent = text; }

  function showGroups(groups) {
    setText(eyebrow, "Your Publication Pack is ready");
    setText(heading, "Your three links");
    setText(lede, "Each link works once and does not expire. All three were also emailed to the address on your receipt.");
    groupsList.innerHTML = "";
    groups.forEach(function (g) {
      var li = document.createElement("li");
      li.className = "success-group";
      var label = document.createElement("span");
      label.className = "success-group-name";
      label.textContent = g.name || g.category || "Review";
      li.appendChild(label);
      if (g.used || !g.url) {
        var used = document.createElement("span");
        used.className = "success-group-used";
        used.textContent = "Used";
        li.appendChild(used);
      } else {
        var a = document.createElement("a");
        a.className = "btn btn-secondary";
        a.href = g.url;
        a.textContent = "Start";
        a.setAttribute("aria-label", "Start: " + (g.name || g.category || "review"));
        li.appendChild(a);
      }
      groupsList.appendChild(li);
    });
    groupsPane.hidden = false;
    redeemEl.hidden = true;
  }

  function showLabPlan(data, tokens) {
    // valid_until arrives as a finished date label ("13 December 2026"), the same one the plan emails use.
    var by = data.valid_until ? " Use them by " + data.valid_until + "." : "";
    setText(eyebrow, "Payment received");
    setText(heading, "Your " + (data.plan_name || "Lab") + " plan is active");
    setText(lede, "This month's reviews are below." + by + " The same links were emailed to the address on your receipt, with a link to the plan page. The plan page shows the reviews left, turns renewal off or on, and opens billing.");
    setText(intro, "Each link below starts one Paper Review. Send them to your group, or use them yourself.");
    setText(footnote, "Keep that email. Its plan page link is the way back to the reviews and to billing. If it has not arrived, email ben@purplelink.llc.");
    showTokens(tokens, data.unused_tokens);
  }

  // 429 from /paper-review/redeem-session: say how long to wait, in plain words.
  function rateLimitMessage(retryAfter) {
    var safe = " If you paid, your order is safe and you do not need to pay again.";
    var s = parseInt(retryAfter, 10);
    if (!(s > 0)) return "Too many link checks from your network. Reload this page in a few minutes." + safe;
    if (s > 3600) return "Too many link checks from your network today. Reload this page tomorrow, or email ben@purplelink.llc with your Stripe receipt." + safe;
    var m = Math.max(1, Math.ceil(s / 60));
    return "Too many link checks from your network. Reload this page in about " + m + (m === 1 ? " minute." : " minutes.") + safe;
  }

  function rateLimitError(resp) {
    return resp.json().catch(function () { return {}; }).then(function (p) {
      throw { error: "rate_limited", detail: rateLimitMessage((p && p.retry_after) || (resp.headers && resp.headers.get ? resp.headers.get("Retry-After") : null)) };
    });
  }

  var LINK_ERROR_MESSAGES = {
    expired: "This link has expired. Email ben@purplelink.llc with your receipt.",
    revoked: "This order was refunded or disputed, so its links no longer work. Email ben@purplelink.llc if that looks wrong.",
  };

  function redeem(attempt) {
    attempt = attempt || 1;
    fetch(API_BASE + "/paper-review/redeem-session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, want_groups: true }),
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
        if (resp.status === 429) return rateLimitError(resp);
        if (!resp.ok) return resp.json().then(function (p) { throw p; });
        return resp.json();
      })
      .then(function (data) {
        if (!data) return;
        if (data.groups && data.groups.length) { showGroups(data.groups); return; }
        var tokens = data.tokens || [];
        if (tokens.length === 0) {
          setStatus("No tokens were issued for this payment. Email ben@purplelink.llc with your Stripe receipt and they will be sent.", true); return;
        }
        if (data.lab_plan === true) { showLabPlan(data, tokens); return; }
        showTokens(tokens, data.unused_tokens);
      })
      .catch(function (err) {
        setStatus((err && err.detail) || (err && LINK_ERROR_MESSAGES[err.error]) || "Could not load tokens.", true);
      });
  }

  if (!sessionId) {
    setStatus("We couldn't find a payment in this link. Your tokens were also emailed to the address you paid with; if that email has not arrived, email ben@purplelink.llc with your Stripe receipt, with no need to pay again.", true); return;
  }
  redeem();
})();
