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
        html += "<p class='stats-note'>Updated " + esc(d.generatedAt || "") + "</p>";
        out.innerHTML = html;
      })
      .catch(function (err) {
        msg.innerHTML = "<span class='err'>" + esc((err && (err.error || err.detail)) || "Failed to load.") + "</span>";
      });
  });
})();
