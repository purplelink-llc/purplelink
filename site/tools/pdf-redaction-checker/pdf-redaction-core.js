/* PDF Redaction Checker: pure helpers (no DOM, no pdf.js). Loaded as a classic script in the page and by node tests. */
(function (root) {
  "use strict";

  var DARK_LUMA = 70;
  var LIGHT_LUMA = 170;
  var MIN_DARK_FRACTION = 0.8;
  var MAX_LIGHT_FRACTION = 0.06;

  function splitWords(str) {
    var out = [];
    var re = /\S+/g;
    var m;
    while ((m = re.exec(str)) !== null) {
      out.push({ text: m[0], start: m.index, end: m.index + m[0].length });
    }
    return out;
  }

  /* Shows the first two words, hides the middle, never the whole text. */
  function maskSnippet(text) {
    var words = String(text).trim().split(/\s+/).filter(Boolean);
    if (!words.length) return "";
    if (words.length === 1) {
      var w = words[0];
      var keep = Math.min(3, Math.max(1, Math.floor(w.length / 3)));
      return w.slice(0, keep) + "•".repeat(Math.min(8, Math.max(3, w.length - keep)));
    }
    if (words.length === 2) {
      return words[0].slice(0, 6) + " " + words[1].slice(0, 1) + "••••";
    }
    var head = words.slice(0, 2).join(" ");
    if (head.length > 14) head = head.slice(0, 14);
    var hidden = words.slice(2).join(" ").length;
    return head + " " + "•".repeat(Math.min(12, Math.max(4, Math.round(hidden / 2))));
  }

  /* RGBA pixel data, canvas size, and a rect in canvas pixels. Returns fractions of dark and bright pixels. */
  function regionStats(data, width, height, rect) {
    var x0 = Math.max(0, Math.floor(rect.x0));
    var y0 = Math.max(0, Math.floor(rect.y0));
    var x1 = Math.min(width, Math.ceil(rect.x1));
    var y1 = Math.min(height, Math.ceil(rect.y1));
    var total = 0, dark = 0, light = 0;
    for (var y = y0; y < y1; y++) {
      for (var x = x0; x < x1; x++) {
        var i = (y * width + x) * 4;
        var luma = 0.2126 * data[i] + 0.7152 * data[i + 1] + 0.0722 * data[i + 2];
        total++;
        if (luma < DARK_LUMA) dark++;
        else if (luma > LIGHT_LUMA) light++;
      }
    }
    if (!total) return { total: 0, dark: 0, light: 0 };
    return { total: total, dark: dark / total, light: light / total };
  }

  /* A word is covered when its body is almost all dark and no light pixels show through,
     which tells a black box over text apart from black text on white or white text on a dark band. */
  function isCovered(stats) {
    return stats.total >= 6 && stats.dark >= MIN_DARK_FRACTION && stats.light <= MAX_LIGHT_FRACTION;
  }

  /* words: in reading order, each { text, hidden, y, size }. Joins neighbouring hidden words on one line. */
  function groupPlaces(words) {
    var places = [];
    var cur = null;
    for (var i = 0; i < words.length; i++) {
      var w = words[i];
      if (!w.hidden) { cur = null; continue; }
      if (cur && Math.abs(w.y - cur.y) <= 0.5 * Math.max(w.size, cur.size)) {
        cur.parts.push(w.text);
      } else {
        cur = { parts: [w.text], y: w.y, size: w.size };
        places.push(cur);
      }
    }
    return places.map(function (p) {
      var text = p.parts.join(" ");
      return { text: text, words: p.parts.length, masked: maskSnippet(text) };
    });
  }

  function rectsOverlap(a, b) {
    return a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1;
  }

  function classifyPage(info) {
    /* info: { images: boolean, textItems: number, invisibleText: boolean } */
    if (info.images && info.textItems === 0) return "scan-no-text";
    if (info.images && info.invisibleText) return "scan-ocr";
    if (info.textItems === 0) return "empty";
    return "text";
  }

  var api = {
    splitWords: splitWords,
    maskSnippet: maskSnippet,
    regionStats: regionStats,
    isCovered: isCovered,
    groupPlaces: groupPlaces,
    rectsOverlap: rectsOverlap,
    classifyPage: classifyPage
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PLRedactCore = api;
})(typeof window !== "undefined" ? window : this);
