// Keyfeel launch switch. This is the ONE file to edit on release day.
//
// Until `live` is true AND the three facts below are filled in, every Keyfeel page
// ships with the free-trial link and the Buy button switched off, says "Not released
// yet", and shows no version, size or date. Nothing here is a claim about the app:
// the facts are copied from the published release (Blobs store keyfeel-files) by hand.
//
//   live      flip to true only after the DMGs are in the keyfeel-files Blobs store,
//             KEYFEEL_UPDATE_TOKEN is set on Netlify, and a test purchase has been
//             delivered (see docs/products/keyfeel.md, "Launch checklist").
//   version   the number in the paid DMG's name, for example "1.0.0".
//   sizeMb    the paid DMG's size in whole megabytes, for example "14".
//   released  the release date, ISO form, for example "2026-10-20".
//
// If `live` is true but a fact is missing or malformed, the page stays switched off
// and logs why to the console, so a half-filled launch cannot sell anything.
window.KEYFEEL_LAUNCH = {
  live: true,
  version: "1.4.0",
  sizeMb: "7",
  released: "2026-10-08"
};

(function () {
  var cfg = window.KEYFEEL_LAUNCH || {};
  var problems = [];
  if (cfg.live !== true) problems.push("live is not true");
  if (!/^\d+\.\d+\.\d+$/.test(String(cfg.version || ""))) problems.push("version is not x.y.z");
  if (!/^\d{1,4}$/.test(String(cfg.sizeMb || ""))) problems.push("sizeMb is not a whole number");
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(cfg.released || ""))) problems.push("released is not YYYY-MM-DD");
  var live = problems.length === 0;

  function all(sel) { return Array.prototype.slice.call(document.querySelectorAll(sel)); }

  function apply() {
    if (!live) {
      if (cfg.live === true && window.console) console.warn("Keyfeel stays switched off: " + problems.join(", ") + ".");
      // The sticky bar would point at a Buy button that does nothing yet.
      all("[data-kf-sticky]").forEach(function (el) { if (el.parentNode) el.parentNode.removeChild(el); });
      return;
    }
    all("[data-kf-pre-only]").forEach(function (el) { el.hidden = true; });
    all("[data-kf-live-only]").forEach(function (el) { el.hidden = false; });
    all("[data-kf-gated]").forEach(function (el) {
      var text = el.getAttribute("data-kf-live-text");
      if (text) el.textContent = text;
      var href = el.getAttribute("data-kf-href");
      if (href) el.setAttribute("href", href);
      el.removeAttribute("aria-disabled");
      el.removeAttribute("disabled");
      el.disabled = false;
    });
    var date = cfg.released;
    try {
      date = new Date(cfg.released + "T00:00:00Z").toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric", timeZone: "UTC" });
    } catch (e) { /* keep the ISO date */ }
    all("[data-kf-facts]").forEach(function (el) {
      el.textContent = "Version " + cfg.version + ", released " + date + ". " + cfg.sizeMb + " MB disk image.";
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", apply);
  else apply();
})();
