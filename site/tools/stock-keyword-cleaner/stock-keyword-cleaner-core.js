/* Stock Photo Keyword Cleaner core. Pure functions: no DOM, no network, no storage.
   The same file runs in the page and under node --test.

   The agency limits below were read on each agency's own contributor pages on 31 October 2026 (links on the page).
   The generic-word list is ALAMY_ZERO_DEMAND from scripts/platform-keywords.py: the words used most often across
   Purplelink's own stock portfolio that appeared in none of the 238 Alamy buyer searches recorded in September 2026. */
(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.StockKeywords = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var GENERIC = ["travel", "tourism", "nature", "summer", "outdoor", "outdoors", "lifestyle", "landmark", "wilderness"];

  // min: fewest keywords the agency accepts; max: most it accepts; first: how many lead keywords carry extra weight.
  var AGENCIES = [
    { id: "adobe", name: "Adobe Stock", max: 49, first: 10, firstLabel: "carry the most search weight" },
    { id: "shutterstock", name: "Shutterstock", min: 7, max: 50 },
    { id: "alamy", name: "Alamy", min: 5, max: 50, first: 10, firstLabel: "are the suggested supertags" },
    { id: "vecteezy", name: "Vecteezy", min: 5, max: 50, plain: true },
    { id: "dreamstime", name: "Dreamstime", caption: true }
  ];

  var MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

  // Letters that do not decompose into a base letter plus an accent.
  var FOLD = { "ß": "ss", "æ": "ae", "œ": "oe", "ø": "o", "ł": "l", "đ": "d", "ð": "d", "þ": "th", "ı": "i" };

  function normalize(k) {
    return String(k).replace(/^[\s"'`“”‘’]+|[\s"'`“”‘’]+$/g, "").replace(/\s+/g, " ").toLowerCase();
  }

  // Splits on commas, semicolons, pipes, tabs and line breaks. Spaces stay inside a keyword ("hyde park").
  function split(text) {
    return String(text || "").split(/[,;|\t\r\n]+/).map(normalize).filter(Boolean);
  }

  function clean(text, opts) {
    var dropGeneric = !opts || opts.dropGeneric !== false;
    var raw = split(text);
    var seen = Object.create(null);
    var keywords = [], duplicates = [], generic = [];
    raw.forEach(function (k) {
      if (seen[k]) { duplicates.push(k); return; }
      seen[k] = true;
      if (dropGeneric && GENERIC.indexOf(k) !== -1) { generic.push(k); return; }
      keywords.push(k);
    });
    return { input: raw.length, keywords: keywords, duplicates: duplicates, generic: generic };
  }

  // Vecteezy: letters, digits and spaces. Accents fold to the base letter, anything else becomes a space.
  function plain(k) {
    var s = k.normalize("NFD").replace(/[̀-ͯ]/g, "");
    s = s.replace(/[ßæœøłđðþı]/g, function (c) { return FOLD[c]; });
    return s.replace(/[^a-z0-9 ]+/g, " ").replace(/\s+/g, " ").trim();
  }

  function forAgency(keywords, id) {
    var a = AGENCIES.filter(function (x) { return x.id === id; })[0];
    if (!a) throw new Error("unknown agency " + id);
    var list = keywords.slice(), changed = [], merged = [], dropped = [];
    if (a.plain) {
      var seen = Object.create(null), out = [];
      list.forEach(function (k) {
        var p = plain(k);
        if (p !== k) changed.push({ from: k, to: p });
        if (!p) { dropped.push(k); return; }
        if (seen[p]) { merged.push(p); return; }
        seen[p] = true;
        out.push(p);
      });
      list = out;
    }
    var cut = a.max && list.length > a.max ? list.slice(a.max) : [];
    if (cut.length) list = list.slice(0, a.max);
    return {
      agency: a, keywords: list, cut: cut, changed: changed, merged: merged, dropped: dropped,
      under: a.min && list.length < a.min ? a.min - list.length : 0
    };
  }

  // "City, Country - Month YYYY:" (a day is optional: "Month D, YYYY").
  function captionPrefix(p) {
    var place = [p.city, p.country].map(function (s) { return String(s || "").trim(); }).filter(Boolean).join(", ");
    var m = MONTHS[(p.month | 0) - 1];
    var y = String(p.year || "").trim();
    if (!place || !m || !/^\d{4}$/.test(y)) return "";
    var d = String(p.day || "").trim();
    return place + " - " + m + " " + (/^\d{1,2}$/.test(d) && +d >= 1 && +d <= 31 ? (+d) + ", " : "") + y + ":";
  }

  var PREFIX_RE = new RegExp("^[^:\\n]+?\\s[-–]\\s(?:" + MONTHS.join("|") + ")\\s(?:\\d{1,2},\\s)?\\d{4}:\\s");

  function hasPrefix(caption) { return PREFIX_RE.test(String(caption || "")); }

  // Adds the prefix to a caption that has none; replaces one that is already there.
  function editorialCaption(prefix, caption) {
    var c = String(caption || "").trim();
    if (!prefix) return c;
    if (hasPrefix(c + " ")) c = c.replace(/^[^:\n]+?:\s*/, "");
    return c ? prefix + " " + c : prefix;
  }

  return {
    GENERIC: GENERIC, AGENCIES: AGENCIES, MONTHS: MONTHS,
    split: split, clean: clean, plain: plain, forAgency: forAgency,
    captionPrefix: captionPrefix, hasPrefix: hasPrefix, editorialCaption: editorialCaption
  };
});
