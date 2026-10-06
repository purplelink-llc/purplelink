/* Sharing a result, in one tap. Every game sets window.PLShareText to a function that returns the result text.
   This turns the page's share button (id ends in "-share") into a Share button that opens the phone's own share
   sheet where there is one, and adds a row of direct options: Message, WhatsApp, X, Facebook, Reddit, Email and Copy.
   Every message is just a link whose preview image is the result card (see compose); the link lands on the game tagged ?from=share-<channel> so we can count what sharing brings back. */
(function () {
  "use strict";
  var G = window.PLGames;
  var slug = (location.pathname.match(/\/games\/([^/]+)\//) || [])[1] || "games";
  var TITLES = { "daily-five": "Daily Five", "daily-photo": "Daily Photo", "daily-chess": "Daily Chess", "chess-puzzles": "Chess Puzzles", "sudoku-unlimited": "Sudoku Unlimited" };

  function parts() {
    var raw = typeof window.PLShareText === "function" ? window.PLShareText() : "";
    var m = raw.match(/\s*(https?:\/\/\S+)\s*$/), body = (m ? raw.slice(0, m.index) : raw).trim();
    var base = (m ? m[1] : location.origin + location.pathname).replace(/[?#].*$/, "");
    return { body: body, base: base };
  }
  // URL-safe base64 of the UTF-8 text; the share link carries the whole result so the preview card can draw it
  function code(text) {
    var bytes = new TextEncoder().encode(text), bin = "";
    for (var i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }
  // The message is the link alone. Its preview image (netlify/functions/games-share.mjs) shows the
  // headline, grid and score, so nothing else is sent as text (c.body stays for the Reddit title). A result with no text keeps the plain game link.
  function compose(channel) {
    var p = parts(), head = p.body.split("\n")[0].trim(), c = head ? code(p.body) : "", url;
    if (c && c.length <= 1700 && /^[a-z0-9-]+$/.test(slug)) url = location.origin + "/games/r/" + slug + "/" + c + "?f=" + channel;
    else url = p.base + "?from=share-" + channel;
    // the text keeps the headline and any detail lines; lines that are only squares are left to the image
    var short = p.body.split("\n").map(function (l) { return l.replace(/^[■▣□]+\s*/, "").trim(); }).filter(Boolean).join("\n") || head || p.body;
    return { body: short, url: url, full: url, title: (document.getElementById("ag-title") ? document.getElementById("ag-title").textContent : TITLES[slug] || document.title.split(":")[0]) };
  }
  function enc(s) { return encodeURIComponent(s); }
  function track(channel) { if (G && G.track) G.track("game_share", slug + ":" + channel); }

  function note(btn, text) {
    var id = btn.id.replace(/-share$/, "-share-note"), el = document.getElementById(id);
    if (el) el.textContent = text;
  }
  function fallbackBox(btn, text) {
    var id = btn.id.replace(/-share$/, "-share-text"), box = document.getElementById(id);
    if (box) { box.value = text; box.hidden = false; box.focus(); box.select(); }
  }
  function copy(btn) {
    var c = compose("copy");
    track("copy");
    return G.copyText(c.full).then(function (ok) {
      note(btn, ok ? "Copied. Paste it in a message or post." : "Copy failed. Select the text below and copy it.");
      if (!ok) fallbackBox(btn, c.full);
      return ok;
    });
  }

  // a real link click opens a new tab and leaves this page where it is (window.open with noopener returns null even on success)
  function openWin(url) {
    var a = document.createElement("a");
    a.href = url; a.target = "_blank"; a.rel = "noopener noreferrer";
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
  }

  var CHANNELS = [
    { id: "sms", label: "Message", go: function (c) { window.location.href = "sms:?&body=" + enc(c.full); } },
    { id: "whatsapp", label: "WhatsApp", go: function (c) { openWin("https://wa.me/?text=" + enc(c.full)); } },
    { id: "x", label: "X", go: function (c) { openWin("https://x.com/intent/post?url=" + enc(c.url)); } },
    { id: "facebook", label: "Facebook", go: function (c) { openWin("https://www.facebook.com/sharer/sharer.php?u=" + enc(c.url)); } },
    { id: "reddit", label: "Reddit", go: function (c) { openWin("https://www.reddit.com/submit?url=" + enc(c.url) + "&title=" + enc(c.body.split("\n")[0])); } },
    { id: "email", label: "Email", go: function (c) { window.location.href = "mailto:?subject=" + enc(c.title + ": my result") + "&body=" + enc(c.full); } }
  ];

  function upgrade(btn) {
    if (btn.getAttribute("data-share-ready")) return;
    btn.setAttribute("data-share-ready", "1");
    var native = typeof navigator.share === "function";
    btn.textContent = native ? "Share" : "Copy result";
    btn.addEventListener("click", function () {
      if (!native) { copy(btn); return; }
      var c = compose("native");
      track("native");
            navigator.share({ url: c.url }).then(function () { note(btn, "Shared."); }, function (e) {
        if (e && e.name === "AbortError") return;       // the player closed the sheet
        copy(btn);
      });
    });
    // direct options, always visible beside the result
    var row = document.createElement("div");
    row.className = "share-row"; row.setAttribute("role", "group"); row.setAttribute("aria-label", "Share your result");
    var lab = document.createElement("span"); lab.className = "share-label"; lab.textContent = "Share to"; row.appendChild(lab);
    CHANNELS.forEach(function (ch) {
      var b = document.createElement("button");
      b.type = "button"; b.className = "share-btn"; b.textContent = ch.label; b.setAttribute("data-share-channel", ch.id);
      b.addEventListener("click", function () { track(ch.id); ch.go(compose(ch.id)); });
      row.appendChild(b);
    });
    if (native) {
      var cp = document.createElement("button"); cp.type = "button"; cp.className = "share-btn"; cp.textContent = "Copy"; cp.addEventListener("click", function () { copy(btn); }); row.appendChild(cp);
    }
    var holder = btn.closest(".game-actions") || btn.parentNode;
    holder.parentNode.insertBefore(row, holder.nextSibling);
  }

  function init() { Array.prototype.forEach.call(document.querySelectorAll('button[id$="-share"]'), upgrade); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
  window.PLShare = { compose: compose };
})();
