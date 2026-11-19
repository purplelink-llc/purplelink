// Guide trial door: the "Try ModernTex free" links on guides, format and LaTeX error pages download the disk image
// directly (moderntex-download?src=guide&trial=1). A disk image is no use on a phone or a PC, so when the visitor is
// clearly not on macOS the link goes to /moderntex/ instead, where "Send to my Mac" takes over. The click is then
// counted as a product-page visit (guide_mtx_click, not guide_mtx_trial) and its meta gains "-not-mac", so trial
// clicks stay trial clicks. Only the closing band (meta ending ":end") is touched; other guide doors keep their href. On a Mac, on an unknown platform, or with scripting off, nothing
// changes. notMac() is a copy of the one in send-to-mac.js (site-tests/test_closing_cta_trial.py keeps them equal).
(function () {
  function notMac(nav) {
    var d = nav && nav.userAgentData;
    var p = d && typeof d.platform === "string" ? d.platform : "";
    if (p && p !== "Unknown") return p !== "macOS";
    var ua = String((nav && nav.userAgent) || "");
    if (/iPhone|iPad|iPod/.test(ua)) return true;
    // iPadOS Safari reports a Mac User-Agent; a Mac has no touch screen.
    if (/Macintosh/.test(ua)) return (nav.maxTouchPoints || 0) > 1;
    return /Windows|Android|CrOS|Linux|X11/.test(ua);
  }

  var on = false;
  try { on = notMac(navigator); } catch (e) { on = false; }
  if (!on) return;
  Array.prototype.slice.call(document.querySelectorAll('a[href*="moderntex-download?src=guide"][data-track-meta$=":end"]')).forEach(function (a) {
    a.setAttribute("href", "/moderntex/");
    a.setAttribute("data-track", "guide_mtx_click");
    var meta = a.getAttribute("data-track-meta");
    if (meta) a.setAttribute("data-track-meta", meta + "-not-mac");
  });
})();
