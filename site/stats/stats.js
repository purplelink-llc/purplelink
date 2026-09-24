// Owner dashboard for /stats/. Fetches the token-gated stats endpoint and
// renders the aggregates, leading with tool runs (the reason this exists).
// The token is entered each visit and never stored.
(function () {
  var form = document.getElementById("tokform");
  var msg = document.getElementById("msg");
  var out = document.getElementById("out");

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function table(title, rows, headers) {
    if (!rows || !rows.length) return "<h3>" + esc(title) + "</h3><p>No data yet.</p>";
    var h = "<h3>" + esc(title) + "</h3><div class='stats-scroll'><table class='stats-t'><thead><tr>";
    h += headers.map(function (x, i) { return "<th" + (i ? " class='num'" : "") + ">" + esc(x) + "</th>"; }).join("");
    h += "</tr></thead><tbody>";
    h += rows.map(function (r) {
      return "<tr>" + r.map(function (c, i) { return "<td" + (i ? " class='num'" : "") + ">" + esc(c) + "</td>"; }).join("") + "</tr>";
    }).join("");
    return h + "</tbody></table></div>";
  }

  function money(cents) { return "$" + (Math.round(cents) / 100).toFixed(2); }

  // Sales, follow-up emails and feedback come from the sales function, which
  // takes the same owner token. Buyer addresses in its response are not shown.
  function loadSales(tok, days) {
    var box = document.getElementById("sales-out");
    fetch("/.netlify/functions/sales?days=" + encodeURIComponent(days) + "&token=" + encodeURIComponent(tok))
      .then(function (r) { if (!r.ok) throw new Error(String(r.status)); return r.json(); })
      .then(function (d) {
        var w = d.window || {}, a = d.allTime || {};
        var h = "<h2 class='stats-h2'>Sales</h2><div class='stats-cards'>";
        h += "<div class='stats-card'><span class='n'>" + (w.orders || 0) + "</span><span class='l'>orders, last " + esc(w.days || days) + " days</span></div>";
        h += "<div class='stats-card'><span class='n'>" + money(w.gross || 0) + "</span><span class='l'>gross, last " + esc(w.days || days) + " days</span></div>";
        h += "<div class='stats-card'><span class='n'>" + money(a.gross || 0) + "</span><span class='l'>gross, all time</span></div>";
        h += "</div>";
        h += table("By product", (d.byProduct || []).map(function (x) { return [x.key, x.orders, money(x.gross), x.lastOrder]; }), ["Product", "Orders", "Gross", "Last order"]);
        var lc = d.lifecycle;
        if (lc) {
          h += "<h2 class='stats-h2'>Follow-up emails</h2>";
          h += table("People in a sequence", Object.keys(lc.entries_by_product || {}).map(function (k) { return [k, lc.entries_by_product[k]]; }), ["Sequence", "People"]);
          h += table("Last email sent", Object.keys(lc.last_stage_sent || {}).map(function (k) { return [k, lc.last_stage_sent[k]]; }), ["Email", "People"]);
          var t = lc.moderntex_trial || {};
          h += table("Other counts", [["ModernTex trial sign-ups", t.signups || 0], ["...who then bought", t.bought || 0], ["Decision reminders waiting", lc.decision_reminders_waiting || 0], ["Unsubscribed", lc.unsubscribed || 0]], ["", "Count"]);
          var fb = lc.feedback;
          if (fb) {
            h += "<h2 class='stats-h2'>Feedback</h2>";
            h += table("Ratings", Object.keys(fb.counts || {}).map(function (k) { var c = fb.counts[k]; return [k, c.useful, c.partly, c.not_useful]; }), ["Product", "Useful", "Partly", "Not useful"]);
            h += table("Latest comments", (fb.recent_comments || []).map(function (c) {
              return [c.comment, c.rating + (c.verified ? ", buyer" : ""), c.quote_ok ? "May quote: " + [c.name, c.field].filter(Boolean).join(", ") : "Do not quote"];
            }), ["Comment", "Rating", "Quote"]);
          }
        } else {
          h += "<p class='stats-note'>Follow-up email and feedback counts are unavailable (backend not reachable, or BACKEND_WEBHOOK_SECRET not set).</p>";
        }
        box.innerHTML = h;
      })
      .catch(function () { box.innerHTML = "<p class='stats-note'>Sales could not be loaded.</p>"; });
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var tok = document.getElementById("tok").value.trim();
    var days = document.getElementById("days").value;
    if (!tok) { msg.textContent = "Enter the token."; return; }
    msg.textContent = "Loading…"; out.innerHTML = "";
    fetch("/.netlify/functions/stats?days=" + encodeURIComponent(days) + "&token=" + encodeURIComponent(tok))
      .then(function (r) { if (!r.ok) return r.json().then(function (p) { throw p; }); return r.json(); })
      .then(function (d) {
        msg.textContent = "";
        var t = d.totals || {};
        var html = "<div class='stats-cards'>";
        html += "<div class='stats-card'><span class='n'>" + (t.toolRuns || 0) + "</span><span class='l'>tool runs</span></div>";
        html += "<div class='stats-card'><span class='n'>" + (t.pageviews || 0) + "</span><span class='l'>page views</span></div>";
        html += "<div class='stats-card'><span class='n'>" + (t.events || 0) + "</span><span class='l'>total events</span></div>";
        html += "</div>";
        html += table("Tools used (runs)", (d.toolRuns || []).map(function (x) { return [x.key, x.count]; }), ["Tool", "Runs"]);
        html += table("Most-read pages", (d.topPaths || []).map(function (x) { return [x.key, x.count]; }), ["Page", "Views"]);
        html += table("Where visitors came from", (d.topReferrers || []).map(function (x) { return [x.key, x.count]; }), ["Site", "Views"]);
        html += table("By domain", (d.byHost || []).map(function (x) { return [x.key, x.count]; }), ["Host", "Events"]);
        html += table("Campaign tags", (d.topUtm || []).map(function (x) { return [x.key, x.count]; }), ["utm_source", "Views"]);
        var byDay = Object.keys(d.byDay || {}).sort().reverse().map(function (day) {
          var v = d.byDay[day];
          return [day, v.toolRuns, v.pageviews, v.uniques];
        });
        html += table("Day by day", byDay, ["Day", "Tool runs", "Views", "Visitors"]);
        html += table("Other events", (d.otherEvents || []).map(function (x) { return [x.key, x.count]; }), ["Event", "Count"]);
        html += table("Other events, with detail", (d.otherEventDetail || []).map(function (x) { return [x.key, x.count]; }), ["Event: detail", "Count"]);
        html += "<p class='stats-note'>Updated " + esc(d.generatedAt || "") + "</p>";
        html += "<div id='sales-out'><p class='stats-note'>Loading sales…</p></div>";
        out.innerHTML = html;
        loadSales(tok, days);
      })
      .catch(function (err) {
        msg.innerHTML = "<span class='err'>" + esc((err && (err.error || err.detail)) || "Failed to load.") + "</span>";
      });
  });
})();
