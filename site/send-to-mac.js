// "Send to my Mac" (docs/designs/send-to-mac.md). Loaded as a plain script in <head>, before styles.css, only on the
// pages that carry the block (scripts/apply_send_to_mac.py stamps both). It runs before the body is parsed, so when
// the visitor is clearly not on macOS it adds the class "s2m" to <html> and the CSS shows the block in the first
// paint: nothing moves. On a Mac, on an unknown platform, or with scripting off, the class is never added and the page
// is exactly as it was. The rest waits for DOMContentLoaded: it wires the form, which posts to
// /.netlify/functions/send-to-mac, and turns the trial button into a pointer to the form (the disk image is no use on
// a phone or a PC; "Download the disk image anyway" in the block still downloads it).
(function () {
  // Not a Mac, decided from User-Agent Client Hints first and the User-Agent string second. Only a clear answer counts:
  // anything unrecognised is treated as a Mac, so the page stays as it is.
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
  window.plSendToMac = { notMac: notMac };

  var on = false;
  try { on = notMac(navigator); } catch (e) { on = false; }
  if (!on) return;
  document.documentElement.classList.add("s2m");

  var EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
  var TRIAL = 'a[href*="-download?trial=1"], a[href*="-download?download=1"]';

  function attribution() {
    try { return typeof window.plAttribution === "function" ? window.plAttribution() : {}; } catch (e) { return {}; }
  }

  function wire(form) {
    var input = form.querySelector('input[type="email"]');
    var news = form.querySelector('input[name="news"]');
    var trap = form.querySelector('input[name="website"]');
    var btn = form.querySelector('button[type="submit"]');
    var status = form.querySelector("[data-s2m-status]");
    var product = form.getAttribute("data-product") || "";
    var busy = false;
    var done = false;

    function say(text) { status.textContent = text; }

    input.addEventListener("input", function () { input.removeAttribute("aria-invalid"); });

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (busy || done) return;
      var email = input.value.trim();
      if (!EMAIL.test(email)) {
        input.setAttribute("aria-invalid", "true");
        say("That address does not look complete. Check it and try again.");
        input.focus();
        return;
      }
      busy = true;
      btn.setAttribute("aria-disabled", "true");
      say("Sending…");
      var a = attribution();
      fetch("/.netlify/functions/send-to-mac", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email, product: product, news: !!(news && news.checked), website: trap ? trap.value : "",
          ft: a.ft || "", fc: a.fc || "", rdt: a.rdt || "",
        }),
      })
        .then(function (r) {
          if (r.status === 429) throw new Error("rate");
          if (!r.ok) throw new Error("http");
          done = true;
          input.readOnly = true;
          if (news) news.disabled = true;
          say("Sent. Open the email on your Mac. If it is not in your inbox in a few minutes, look in spam." +
            (news && news.checked ? " The same email has a link to confirm product news." : ""));
          if (window.plTrack) window.plTrack("send_to_mac", product);
        })
        .catch(function (err) {
          busy = false;
          btn.removeAttribute("aria-disabled");
          say(err && err.message === "rate"
            ? "This network has asked several times today. Try again tomorrow, or email ben@purplelink.llc."
            : "That did not go through. Try again in a minute, or email ben@purplelink.llc.");
        });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var forms = Array.prototype.slice.call(document.querySelectorAll("[data-send-to-mac]"));
    if (!forms.length) return;
    forms.forEach(function (form) { form.hidden = false; wire(form); });
    var first = forms[0].querySelector('input[type="email"]');
    // The trial buttons point at the block instead of downloading. analytics.js, reddit-pixel.js and site.js read
    // data-s2m-intercept at click time, so such a click is not counted as a ModernTex trial download or a Reddit
    // Lead. The block's own "anyway" link carries no mark and downloads as normal.
    Array.prototype.slice.call(document.querySelectorAll(TRIAL)).forEach(function (a) {
      if (a.hasAttribute("data-s2m-anyway")) return;
      a.setAttribute("data-s2m-intercept", "1");
      a.addEventListener("click", function (e) {
        e.preventDefault();
        first.focus();
        first.scrollIntoView({ block: "center" });
      });
    });
  });
})();
