/* Affiliate cards for the chess pages. Nothing shows until a link is filled in below, which happens after
   Chess.com and Chessable approve the site. The card says plainly that the links earn us a commission. */
(function () {
  "use strict";
  // Fill these in after approval. Chess.com gives a referral id; Chessable gives a full link.
  var CHESSCOM_REF_ID = "";
  var CHESSABLE_URL = "";

  function link(href, text, name) {
    var a = document.createElement("a");
    a.className = "gbtn gbtn--ghost"; a.href = href; a.textContent = text;
    a.rel = "sponsored noopener"; a.target = "_blank"; a.setAttribute("data-partner", name);
    a.addEventListener("click", function () { if (window.plTrack) window.plTrack("partner_click", name); });
    return a;
  }
  function show() {
    var box = document.getElementById("partner");
    if (!box || box.getAttribute("data-built")) return;
    var items = [];
    if (CHESSABLE_URL) items.push(link(CHESSABLE_URL, "Study tactics on Chessable", "chessable"));
    if (CHESSCOM_REF_ID) items.push(link("https://www.chess.com/membership?ref_id=" + encodeURIComponent(CHESSCOM_REF_ID), "Play and review on Chess.com", "chesscom"));
    if (!items.length) return;
    box.setAttribute("data-built", "1");
    var h = document.createElement("h3"); h.textContent = "Keep improving"; box.appendChild(h);
    var p = document.createElement("p"); p.textContent = "Two places to study and play chess beyond these puzzles."; box.appendChild(p);
    var row = document.createElement("div"); row.className = "partner-row";
    items.forEach(function (a) { row.appendChild(a); });
    box.appendChild(row);
    var d = document.createElement("p"); d.className = "partner-note"; d.textContent = "These are affiliate links. If you subscribe through them we earn a commission, at no cost to you.";
    box.appendChild(d);
    box.hidden = false;
  }
  window.PLPartners = { show: show };
})();
