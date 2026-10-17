// Academic email signature generator: page wiring. All logic is in signature-core.js.
// Nothing here sends data anywhere. The only storage is an opt-in draft in localStorage.
(function () {
  "use strict";
  var C = window.SignatureCore;
  if (!C) return;

  var FIELDS = ["name", "pronouns", "title", "dept", "institution", "email", "phone", "orcid", "scholar", "website",
    "paperTitle", "paperDoi", "office", "hoursNote", "custom"];
  var STORE_KEY = "pl-academic-signature-v1";

  var $ = function (id) { return document.getElementById(id); };
  var form = $("sig-form");
  var frame = $("frame");
  var emptyEl = $("empty");
  var countEl = $("count");
  var statusEl = $("status");
  var buttons = { rich: $("copy-rich"), html: $("copy-html"), text: $("copy-text"), dl: $("download") };

  var lastPresetTitle = "";
  var blobUrl = "";
  var current = { html: "", text: "" };
  var counted = false;
  var timer = 0;

  function radioValue(name) {
    var el = document.querySelector('input[name="' + name + '"]:checked');
    return el ? el.value : "";
  }
  function setRadio(name, value) {
    var el = document.querySelector('input[name="' + name + '"][value="' + value + '"]');
    if (el) el.checked = true;
  }
  function accentValue() {
    var v = radioValue("accent");
    if (v === "custom") return $("custom-color").value;
    for (var i = 0; i < C.ACCENTS.length; i++) if (C.ACCENTS[i].name.toLowerCase() === v) return C.ACCENTS[i].value;
    return C.ACCENTS[0].value;
  }

  function readFields() {
    var f = {};
    FIELDS.forEach(function (k) { f[k] = $(k).value; });
    return f;
  }
  function readOptions(preview) {
    return {
      template: $("template").value,
      accent: accentValue(),
      font: $("font").value,
      size: Number($("size").value),
      inheritColor: $("inherit").checked,
      icon: $("icon").checked,
      preset: radioValue("preset"),
      preview: !!preview,
      origin: location.origin
    };
  }

  function say(msg) { statusEl.textContent = msg; }

  function render() {
    var fields = readFields();
    var result = C.build(fields, readOptions(false));
    var previewResult = C.build(fields, readOptions(true));

    FIELDS.forEach(function (k) {
      var err = $(k + "-err");
      var msg = result.errors[k] || "";
      err.textContent = msg;
      $(k).setAttribute("aria-invalid", msg ? "true" : "false");
    });

    // Contrast note for the custom colour.
    var wrap = $("custom-wrap");
    var isCustom = radioValue("accent") === "custom";
    wrap.hidden = !isCustom;
    if (isCustom) {
      var ratio = C.contrastOnWhite($("custom-color").value);
      $("contrast-note").textContent = ratio >= 4.5
        ? "Contrast on a white page: " + ratio.toFixed(1) + " to 1. That passes."
        : "Contrast on a white page: " + ratio.toFixed(1) + " to 1. Below 4.5, so small text in this colour is hard to read. Pick a darker one.";
    }

    current = { html: result.html, text: result.text };
    var has = !result.empty;
    emptyEl.hidden = has;
    frame.hidden = !has;
    Object.keys(buttons).forEach(function (k) { buttons[k].disabled = !has; });
    if (!has) {
      countEl.textContent = "";
      return;
    }
    var dark = radioValue("bg") === "dark";
    var doc = C.previewDocument(previewResult.html, dark);
    var next = URL.createObjectURL(new Blob([doc], { type: "text/html" }));
    var old = blobUrl;
    blobUrl = next;
    frame.src = next;
    if (old) setTimeout(function () { URL.revokeObjectURL(old); }, 2000);

    var n = result.html.length;
    countEl.textContent = n.toLocaleString("en-US") + " characters of HTML. Gmail's limit is 10,000." +
      (n > 10000 ? " This is over it: shorten a line or two." : "");
  }

  frame.addEventListener("load", function () {
    try {
      var d = frame.contentDocument;
      if (d && d.body) frame.style.height = Math.min(Math.max(d.documentElement.scrollHeight, 90), 600) + "px";
    } catch (e) { /* cross-origin frame: leave the CSS height */ }
  });

  function schedule() {
    clearTimeout(timer);
    timer = setTimeout(function () { render(); save(); }, 120);
  }

  // Draft in localStorage, only when the box is ticked.
  function save() {
    try {
      if (!$("remember").checked) return;
      var data = { fields: readFields(), opts: readOptions(false), accentChoice: radioValue("accent"), custom: $("custom-color").value, bg: radioValue("bg") };
      localStorage.setItem(STORE_KEY, JSON.stringify(data));
    } catch (e) { /* storage unavailable: carry on without it */ }
  }
  function forget() {
    try { localStorage.removeItem(STORE_KEY); } catch (e) { /* ignore */ }
  }
  function restore() {
    try {
      var raw = localStorage.getItem(STORE_KEY);
      if (!raw) return false;
      var d = JSON.parse(raw);
      if (!d || typeof d !== "object" || !d.fields) return false;
      FIELDS.forEach(function (k) { if (typeof d.fields[k] === "string") $(k).value = d.fields[k].slice(0, 300); });
      var o = d.opts || {};
      if (["classic", "minimal", "compact", "twocol"].indexOf(o.template) >= 0) $("template").value = o.template;
      if (o.font === "serif" || o.font === "sans") $("font").value = o.font;
      if (o.size === 13 || o.size === 14) $("size").value = String(o.size);
      $("inherit").checked = o.inheritColor !== false;
      $("icon").checked = o.icon !== false;
      if (C.PRESETS[o.preset]) setRadio("preset", o.preset);
      if (typeof d.custom === "string") $("custom-color").value = C.safeColor(d.custom, "#5b2a86");
      if (d.accentChoice) setRadio("accent", d.accentChoice);
      if (d.bg === "dark") setRadio("bg", "dark");
      $("remember").checked = true;
      return true;
    } catch (e) { return false; }
  }

  function applyPreset(userChange) {
    var p = C.PRESETS[radioValue("preset")];
    if (!p) return;
    var titleEl = $("title");
    $("title").placeholder = p.hints.title;
    $("dept").placeholder = p.hints.dept;
    if (userChange && (!titleEl.value.trim() || titleEl.value === lastPresetTitle)) titleEl.value = p.title;
    lastPresetTitle = p.title;
  }

  var EXAMPLE = {
    name: "Alex Rivera", pronouns: "they/them", title: "", dept: "Department of Sociology",
    institution: "Example University", email: "alex.rivera@example.edu", phone: "",
    orcid: "0000-0002-1825-0097", scholar: "https://scholar.google.com/citations?user=EXAMPLE",
    website: "https://example.edu/rivera-lab", paperTitle: "", paperDoi: "", office: "", hoursNote: "", custom: ""
  };

  function fillExample() {
    applyPreset(false);
    var p = C.PRESETS[radioValue("preset")];
    FIELDS.forEach(function (k) { $(k).value = EXAMPLE[k]; });
    $("title").value = p.title;
    lastPresetTitle = p.title;
    if (radioValue("preset") !== "phd") {
      $("paperTitle").value = "Title of the paper";
      $("paperDoi").value = "10.1000/xyz123";
    }
    if (radioValue("preset") === "faculty") $("office").value = "Tue 2 to 4 pm, Hall 214";
    render(); save();
  }

  function clearAll() {
    FIELDS.forEach(function (k) { $(k).value = ""; });
    lastPresetTitle = "";
    render();
    if ($("remember").checked) save();
    say("Cleared.");
  }

  // Copy helpers.
  function countUse() {
    if (counted) return;
    counted = true;
    if (window.plTrack) window.plTrack("tool_use");
  }
  function flash(btn, label) {
    var prev = btn.getAttribute("data-label") || btn.textContent;
    btn.setAttribute("data-label", prev);
    btn.textContent = label;
    setTimeout(function () { btn.textContent = prev; }, 1500);
  }
  function legacyCopy(html, text) {
    var ok = false;
    function onCopy(e) {
      e.clipboardData.setData("text/html", html);
      e.clipboardData.setData("text/plain", text);
      e.preventDefault();
      ok = true;
    }
    document.addEventListener("copy", onCopy);
    try { document.execCommand("copy"); } catch (e) { ok = false; }
    document.removeEventListener("copy", onCopy);
    return ok;
  }
  function copyPlain(str) {
    if (navigator.clipboard && navigator.clipboard.writeText) return navigator.clipboard.writeText(str);
    return legacyCopy(str, str) ? Promise.resolve() : Promise.reject(new Error("copy"));
  }

  function done(btn, label) { flash(btn, label); say(label); countUse(); }
  function failed() { say("Could not copy automatically. Use Download .html or select the preview and copy it by hand."); }

  buttons.rich.addEventListener("click", function () {
    if (!current.html) return;
    var html = current.html;
    var text = current.text;
    if (window.ClipboardItem && navigator.clipboard && navigator.clipboard.write) {
      var item = new ClipboardItem({
        "text/html": new Blob([html], { type: "text/html" }),
        "text/plain": new Blob([text], { type: "text/plain" })
      });
      navigator.clipboard.write([item]).then(function () { done(buttons.rich, "Copied"); }, function () {
        if (legacyCopy(html, text)) done(buttons.rich, "Copied"); else failed();
      });
    } else if (legacyCopy(html, text)) {
      done(buttons.rich, "Copied");
    } else {
      failed();
    }
  });
  buttons.html.addEventListener("click", function () {
    if (!current.html) return;
    copyPlain(current.html).then(function () { done(buttons.html, "Copied"); }, failed);
  });
  buttons.text.addEventListener("click", function () {
    if (!current.text) return;
    copyPlain(current.text).then(function () { done(buttons.text, "Copied"); }, failed);
  });
  buttons.dl.addEventListener("click", function () {
    if (!current.html) return;
    var doc = '<!doctype html>\n<html><head><meta charset="utf-8"><title>Email signature</title></head><body>' + current.html + "</body></html>\n";
    var url = URL.createObjectURL(new Blob([doc], { type: "text/html" }));
    var a = document.createElement("a");
    a.href = url;
    a.download = "email-signature.html";
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 2000);
    say("Downloaded email-signature.html");
    countUse();
  });

  // Events.
  form.addEventListener("submit", function (e) { e.preventDefault(); });
  form.addEventListener("input", schedule);
  form.addEventListener("change", function (e) {
    var t = e.target;
    if (t && t.name === "preset") applyPreset(true);
    if (t && t.id === "remember") { if (t.checked) save(); else forget(); }
    schedule();
  });
  document.querySelectorAll('input[name="bg"]').forEach(function (r) { r.addEventListener("change", schedule); });
  $("example").addEventListener("click", fillExample);
  $("clear").addEventListener("click", clearAll);

  var restored = restore();
  applyPreset(!restored);
  render();
})();
