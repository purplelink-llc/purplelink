/* PII Checker core. Pure functions: no DOM, no network, no storage.
   The same file runs in the page, in a Web Worker and under node --test.

   The pattern rules are ported from Outbound Veil (OutboundVeilCore/Heuristics.swift, Validators.swift,
   NoiseFilter.swift, ScanText.swift, Policy.swift, Redactor.swift, LabelNames.swift), which in turn ported
   them from Rampart's heuristics. The app also runs an on-device model for names, street addresses, phone
   numbers, passport, driver's license, tax and bank numbers. That model is not part of this file, so this
   file does not find names or addresses, and the phone rule below is written for this page only; the app
   has no pattern rule for phone numbers.

   Offsets are UTF-16 offsets into the text that was passed in, end exclusive. */
(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module && module.exports) module.exports = api;
  else root.PiiCheck = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // Label names are the raw values Outbound Veil uses in its placeholders (Types.swift).
  var LABELS = ["SSN", "CREDIT_CARD", "IBAN", "EMAIL", "PHONE", "DATE_OF_BIRTH", "MEDICAL_RECORD_NUMBER", "IP_ADDRESS", "URL"];

  // Plain-language names, from LabelNames.swift. URL is shown with what makes it reportable (see isLowRiskURL).
  var DISPLAY = {
    SSN: "Social Security number",
    CREDIT_CARD: "Card number",
    IBAN: "Bank account number (IBAN)",
    EMAIL: "Email address",
    PHONE: "Phone number",
    DATE_OF_BIRTH: "Date of birth",
    MEDICAL_RECORD_NUMBER: "Medical record number",
    IP_ADDRESS: "IP or MAC address",
    URL: "Web address with a query string, login or token"
  };

  // ---------- validators (Validators.swift) ----------

  // Luhn checksum. Gates CREDIT_CARD so arbitrary digit runs do not match.
  function isLuhnValid(digits) {
    if (!digits || !/^[0-9]+$/.test(digits)) return false;
    var sum = 0, dbl = false;
    for (var i = digits.length - 1; i >= 0; i--) {
      var d = digits.charCodeAt(i) - 48;
      if (dbl) { d *= 2; if (d > 9) d -= 9; }
      sum += d;
      dbl = !dbl;
    }
    return sum % 10 === 0;
  }

  // US SSN structure: area is not 000, 666 or 900-999; group is not 00; serial is not 0000.
  function isValidSSN(digits) {
    if (!/^[0-9]{9}$/.test(digits)) return false;
    var area = digits.slice(0, 3), group = digits.slice(3, 5), serial = digits.slice(5);
    if (area === "000" || area === "666") return false;
    if (parseInt(area, 10) >= 900) return false;
    if (group === "00") return false;
    if (serial === "0000") return false;
    return true;
  }

  // IBAN: 15 to 34 characters, two letters, two check digits, mod 97 equals 1.
  function isValidIBAN(value) {
    var s = String(value).replace(/\s+/g, "").toUpperCase();
    if (s.length < 15 || s.length > 34) return false;
    if (!/^[A-Z]{2}[0-9]{2}[A-Z0-9]+$/.test(s)) return false;
    var re = s.slice(4) + s.slice(0, 4), rem = 0;
    for (var i = 0; i < re.length; i++) {
      var c = re.charCodeAt(i);
      var digits = c >= 65 ? String(c - 55) : String.fromCharCode(c);
      for (var j = 0; j < digits.length; j++) rem = (rem * 10 + (digits.charCodeAt(j) - 48)) % 97;
    }
    return rem === 1;
  }

  // A web address is low risk when nothing in it can carry a secret: no credentials, no query string, no long
  // token-like path segment (NoiseFilter.swift). Low-risk addresses are not reported.
  function isLowRiskURL(url) {
    var rest = String(url);
    var i = rest.indexOf("://");
    if (i >= 0) rest = rest.slice(i + 3);
    var m = /[\/?#]/.exec(rest);
    var authorityEnd = m ? m.index : rest.length;
    if (rest.slice(0, authorityEnd).indexOf("@") >= 0) return false;
    if (rest.indexOf("?") >= 0) return false;
    var segs = rest.slice(authorityEnd).split(/[\/#]/);
    for (var k = 0; k < segs.length; k++) {
      var seg = segs[k];
      if (seg.length >= 20 && /^[A-Za-z0-9_\-]+$/.test(seg) && /[0-9]/.test(seg) && /[A-Za-z]/.test(seg)) return false;
    }
    return true;
  }

  // ---------- invisible characters (ScanText.swift) ----------

  // Zero-width spaces, joiners, soft hyphens and tag characters (category Cf) can be pasted between the digits of a
  // number to slip past a pattern. Rules run on the text without them, and findings are mapped back.
  var CF = /\p{Cf}/u;
  function stripInvisible(raw) {
    if (!CF.test(raw)) return { text: raw, identity: true, map: null };
    var out = "", starts = [], ends = [], off = 0;
    for (var i = 0; i < raw.length;) {
      var cp = raw.codePointAt(i), w = cp > 0xffff ? 2 : 1, ch = raw.slice(i, i + w);
      if (!CF.test(ch)) {
        out += ch;
        for (var k = 0; k < w; k++) { starts.push(off); ends.push(off + w); }
      }
      off += w;
      i += w;
    }
    return { text: out, identity: false, map: { starts: starts, ends: ends } };
  }
  function projectToRaw(scan, start, end) {
    if (scan.identity) return end > start ? { start: start, end: end } : null;
    if (end <= start || start < 0 || end > scan.map.starts.length) return null;
    return { start: scan.map.starts[start], end: scan.map.ends[end - 1] };
  }

  // ---------- rules (Heuristics.swift) ----------

  function span(start, end, label, text) { return { start: start, end: end, label: label, score: 1, source: "pattern", text: text }; }

  // Digit-bearing numbers are found over digit runs, so every separator form is one rule: 472-81-0094, 472 81 0094,
  // 472.81.0094 and 472810094. Longest and strictest first, so a 16-digit card is never carved into a 9-digit SSN.
  var DIGIT_RULES = [
    { label: "CREDIT_CARD", lengths: [16, 15, 14], validate: isLuhnValid },
    // Differs from the app: the app takes any nine digits with a single space, dot or hyphen between any two of them.
    // Here the nine digits must be written without separators or as 3-2-4 with one kind of separator. Without this,
    // an IPv4 address such as 192.168.1.10, or a ZIP+4 such as 30303-1234, passes the SSN structure check.
    { label: "SSN", lengths: [9], validate: isValidSSN, shape: /^(?:\d{9}|\d{3}([ .\-])\d{2}\1\d{4})$/ }
  ];
  function detectDigitEntities(raw) {
    var spans = [], re = /[0-9](?:[ .\-]?[0-9])*/g, m;
    while ((m = re.exec(raw))) {
      var digits = "", first = -1, last = -1;
      for (var i = 0; i < m[0].length; i++) {
        var c = m[0].charCodeAt(i);
        if (c >= 48 && c <= 57) { digits += m[0].charAt(i); if (first < 0) first = m.index + i; last = m.index + i; }
      }
      for (var r = 0; r < DIGIT_RULES.length; r++) {
        var rule = DIGIT_RULES[r];
        if (rule.shape && !rule.shape.test(m[0])) continue;
        if (rule.lengths.indexOf(digits.length) >= 0 && rule.validate(digits)) {
          spans.push(span(first, last + 1, rule.label, raw.slice(first, last + 1)));
          break;
        }
      }
    }
    return spans;
  }

  var MONTH = "(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\\.?";
  var DATE_FORMS = [
    "\\d{1,2}[/.\\-]\\d{1,2}[/.\\-]\\d{2,4}",
    "\\d{4}[/.\\-]\\d{1,2}[/.\\-]\\d{1,2}",
    MONTH + "\\s+\\d{1,2}(?:st|nd|rd|th)?,?\\s+\\d{4}",
    "\\d{1,2}(?:st|nd|rd|th)?\\s+" + MONTH + ",?\\s+\\d{4}"
  ].join("|");

  var IPV6 = "(?<![:.\\w])(?:(?:[0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}|(?:[0-9A-Fa-f]{1,4}:){1,7}:|(?:[0-9A-Fa-f]{1,4}:){1,6}:[0-9A-Fa-f]{1,4}|(?:[0-9A-Fa-f]{1,4}:){1,5}(?::[0-9A-Fa-f]{1,4}){1,2}|(?:[0-9A-Fa-f]{1,4}:){1,4}(?::[0-9A-Fa-f]{1,4}){1,3}|(?:[0-9A-Fa-f]{1,4}:){1,3}(?::[0-9A-Fa-f]{1,4}){1,4}|(?:[0-9A-Fa-f]{1,4}:){1,2}(?::[0-9A-Fa-f]{1,4}){1,5}|[0-9A-Fa-f]{1,4}:(?::[0-9A-Fa-f]{1,4}){1,6}|::(?:[0-9A-Fa-f]{1,4}:){0,6}[0-9A-Fa-f]{1,4})(?![:.\\w])";

  // Phone numbers: written for this page. Outbound Veil finds them with its model, not a pattern. Two shapes only:
  // North American numbers with an area code (3-3-4 digits, the area code and exchange not starting with 0 or 1,
  // optional +1), and international numbers that start with + and have 8 to 15 digits. A bare run of 10 digits is
  // not reported, since order numbers and ISBN-10s look the same.
  function phoneDigitsOk(text) {
    var n = text.replace(/\D/g, "").length;
    return n >= 8 && n <= 15;
  }
  var PHONE_US = "(?<![\\w+\\-])(?:\\+?1[ .\\-]?)?(?:\\([2-9]\\d{2}\\)[ .\\-]?|[2-9]\\d{2}[ .\\-])[2-9]\\d{2}[ .\\-]\\d{4}(?![\\w]|-\\d)";
  var PHONE_INTL = "(?<![\\w+])\\+\\d{1,3}(?:[ .\\-]\\(?\\d{1,4}\\)?){2,4}(?![\\w]|-\\d)";
  var PHONE_INTL_PLAIN = "(?<![\\w+])\\+\\d{8,15}(?!\\w)";

  // group is the capture group that holds the value (0 = whole match). Each rule reports only the value, not its cue word.
  var TEXT_RULES = [
    { label: "URL", re: "\\bhttps?://[^\\s<>\"'\\])}]+", flags: "g", trim: true },
    { label: "URL", re: "\\bwww\\.[A-Za-z0-9.\\-]+\\.[A-Za-z]{2,}(?:/[^\\s<>\"'\\])}]*)?", flags: "g", trim: true },
    { label: "IP_ADDRESS", re: "\\b(?:(?:25[0-5]|2[0-4]\\d|1?\\d?\\d)\\.){3}(?:25[0-5]|2[0-4]\\d|1?\\d?\\d)\\b", flags: "g" },
    { label: "IP_ADDRESS", re: IPV6, flags: "g" },
    { label: "IP_ADDRESS", re: "\\b(?:[0-9A-Fa-f]{2}[:\\-]){5}[0-9A-Fa-f]{2}\\b", flags: "g" },
    { label: "DATE_OF_BIRTH", re: "\\b(?:dob|d\\.o\\.b\\.?|date\\s+of\\s+birth|birth\\s?date|birthday|born(?:\\s+on)?)\\b[\\s:\\-]*(?:is\\s+)?(" + DATE_FORMS + ")", flags: "gi", group: 1 },
    { label: "MEDICAL_RECORD_NUMBER", re: "\\b(?:mrn|medical\\s+record(?:\\s+(?:number|no\\.?))?|patient\\s+(?:id|number))\\b[\\s:#]*(?:is\\s+)?((?=[A-Z0-9\\-]*\\d)[A-Z0-9\\-]{5,15})\\b", flags: "gi", group: 1 },
    { label: "IBAN", re: "\\b[A-Z]{2}\\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,3})?\\b", flags: "g", validate: isValidIBAN },
    { label: "PHONE", re: PHONE_US, flags: "g", validate: phoneDigitsOk },
    { label: "PHONE", re: PHONE_INTL, flags: "g", validate: phoneDigitsOk },
    { label: "PHONE", re: PHONE_INTL_PLAIN, flags: "g", validate: phoneDigitsOk }
  ];
  var COMPILED = TEXT_RULES.map(function (r) {
    return { label: r.label, re: new RegExp(r.re, r.flags), group: r.group || 0, validate: r.validate, trim: r.trim };
  });

  // Email. A single regex over the whole text is slow on a long run of address characters with no @ (every word
  // boundary in the run restarts the scan). This finds each @ first and runs the rest of the pattern once, from the
  // leftmost word boundary of the run before it. Same matches, linear time (Heuristics.swift, detectEmails).
  var EMAIL_TAIL = /[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b/y;
  function isAlnum(u) { return (u >= 0x30 && u <= 0x39) || (u >= 0x41 && u <= 0x5a) || (u >= 0x61 && u <= 0x7a); }
  function isLocalPart(u) { return isAlnum(u) || u === 0x2e || u === 0x5f || u === 0x25 || u === 0x2b || u === 0x2d; }
  var WORD_NON_ASCII = /[\p{L}\p{N}\p{M}]/u;
  function isWord(u) { return isAlnum(u) || u === 0x5f || (u > 0x7f && WORD_NON_ASCII.test(String.fromCharCode(u))); }
  function boundaryAt(units, i) {
    var a = i > 0 && isWord(units[i - 1]), b = i < units.length && isWord(units[i]);
    return a !== b;
  }
  function detectEmails(raw) {
    var spans = [];
    if (raw.indexOf("@") < 0) return spans;
    var units = [];
    for (var q = 0; q < raw.length; q++) units.push(raw.charCodeAt(q));
    var searchFrom = 0, at = 0;
    while (at < units.length) {
      if (units[at] !== 0x40) { at++; continue; }
      var here = at;
      at++;
      if (here <= searchFrom) continue;
      var runStart = here;
      while (runStart > searchFrom && isLocalPart(units[runStart - 1])) runStart--;
      if (runStart >= here) continue;
      var start = -1;
      if (boundaryAt(units, runStart)) start = runStart;
      else if (runStart + 1 < here) {
        for (var i = runStart + 1; i < here; i++) { if (isWord(units[i - 1]) !== isWord(units[i])) { start = i; break; } }
      }
      if (start < 0) continue;
      EMAIL_TAIL.lastIndex = start;
      var m = EMAIL_TAIL.exec(raw);
      if (!m) continue;
      spans.push(span(m.index, m.index + m[0].length, "EMAIL", m[0]));
      searchFrom = m.index + m[0].length;
      at = Math.max(at, searchFrom);
    }
    return spans;
  }

  function detectTextEntities(raw) {
    var spans = detectEmails(raw);
    for (var r = 0; r < COMPILED.length; r++) {
      var rule = COMPILED[r], re = rule.re, m;
      re.lastIndex = 0;
      while ((m = re.exec(raw))) {
        if (m[0] === "") { re.lastIndex++; continue; }
        var text = m[rule.group];
        if (text == null) continue;
        var start = m.index + (rule.group ? m[0].lastIndexOf(text) : 0);
        // A sentence's closing punctuation is not part of a web address.
        if (rule.trim) text = text.replace(/[.,;:!?]+$/, "");
        if (rule.validate && !rule.validate(text)) continue;
        spans.push(span(start, start + text.length, rule.label, text));
      }
    }
    return spans;
  }

  function detectHeuristics(raw) { return detectDigitEntities(raw).concat(detectTextEntities(raw)); }

  // ---------- overlaps (Policy.swift) ----------

  function preferred(a, b) {
    if (a.score !== b.score) return a.score > b.score ? a : b;
    var al = a.end - a.start, bl = b.end - b.start;
    if (al !== bl) return al > bl ? a : b;
    return a;
  }
  // Reduce overlapping spans to a disjoint set, ascending by start. The higher score wins, then the longer span.
  // A partial overlap keeps the union under the winner's label, so no matched characters are dropped.
  function mergeSpans(spans) {
    var sorted = spans.slice().sort(function (x, y) { return x.start !== y.start ? x.start - y.start : y.end - x.end; });
    var merged = [];
    for (var i = 0; i < sorted.length; i++) {
      var s = sorted[i], prev = merged[merged.length - 1];
      if (!prev || s.start >= prev.end) { merged.push(s); continue; }
      var winner = preferred(prev, s);
      var prevContains = prev.start <= s.start && prev.end >= s.end;
      var spanContains = s.start <= prev.start && s.end >= prev.end;
      if (prevContains || spanContains) merged[merged.length - 1] = winner;
      else {
        var u = { start: Math.min(prev.start, s.start), end: Math.max(prev.end, s.end), label: winner.label, score: winner.score, source: winner.source, text: "" };
        merged[merged.length - 1] = u;
      }
    }
    return merged;
  }

  // Every finding in raw: disjoint, ascending, with low-risk web addresses left out (OutboundVeilDetector.findings).
  function detect(raw) {
    raw = String(raw == null ? "" : raw);
    var scan = stripInvisible(raw);
    var found = detectHeuristics(scan.text), projected = [];
    for (var i = 0; i < found.length; i++) {
      var r = projectToRaw(scan, found[i].start, found[i].end);
      if (!r) continue;
      projected.push({ start: r.start, end: r.end, label: found[i].label, score: found[i].score, source: found[i].source, text: "" });
    }
    return mergeSpans(projected)
      .map(function (s) { s.text = raw.slice(s.start, s.end); return s; })
      .filter(function (s) { return !(s.label === "URL" && isLowRiskURL(s.text)); });
  }

  // ---------- placeholders (Redactor.swift) ----------

  var IDENTIFIER_LABELS = { SSN: 1, CREDIT_CARD: 1, PHONE: 1, IBAN: 1, MEDICAL_RECORD_NUMBER: 1 };
  // Identifier-like values compare by their letters and digits only, so 472-81-0094 and 472 81 0094 are one value.
  function valueKey(label, value) {
    var lowered = String(value).toLowerCase();
    var norm = IDENTIFIER_LABELS[label] ? lowered.replace(/[^\p{L}\p{N}]/gu, "") : lowered.split(/\s+/).filter(Boolean).join(" ");
    return label + ":" + norm;
  }

  // text with every span replaced by [LABEL_n]. The same value always gets the same number; numbers follow reading order.
  function redact(text, spans) {
    var ordered = spans.slice().sort(function (a, b) { return a.start - b.start; });
    var forward = {}, counters = {}, tokens = [], i;
    for (i = 0; i < ordered.length; i++) {
      var s = ordered[i], key = valueKey(s.label, text.slice(s.start, s.end));
      if (!forward[key]) { counters[s.label] = (counters[s.label] || 0) + 1; forward[key] = "[" + s.label + "_" + counters[s.label] + "]"; }
      tokens.push(forward[key]);
    }
    var out = "", cursor = 0;
    for (i = 0; i < ordered.length; i++) {
      out += text.slice(cursor, ordered[i].start) + tokens[i];
      cursor = ordered[i].end;
    }
    return { text: out + text.slice(cursor), tokens: tokens };
  }

  // ---------- the whole check ----------

  // {total, groups: [{label, name, count, placeholders}], spans, tokens, redacted}. groups follow LABELS order.
  function check(raw) {
    raw = String(raw == null ? "" : raw);
    var spans = detect(raw), red = redact(raw, spans), byLabel = {}, i;
    for (i = 0; i < spans.length; i++) {
      var g = byLabel[spans[i].label] || (byLabel[spans[i].label] = { label: spans[i].label, name: DISPLAY[spans[i].label], count: 0, placeholders: [] });
      g.count++;
      if (g.placeholders.indexOf(red.tokens[i]) < 0) g.placeholders.push(red.tokens[i]);
    }
    var groups = [];
    for (i = 0; i < LABELS.length; i++) if (byLabel[LABELS[i]]) groups.push(byLabel[LABELS[i]]);
    return { total: spans.length, groups: groups, spans: spans, tokens: red.tokens, redacted: red.text };
  }

  // Text from raw bytes, honouring a UTF-8 or UTF-16 byte order mark.
  function decodeBytes(bytes) {
    var enc = "utf-8";
    if (bytes.length >= 2 && bytes[0] === 0xff && bytes[1] === 0xfe) enc = "utf-16le";
    else if (bytes.length >= 2 && bytes[0] === 0xfe && bytes[1] === 0xff) enc = "utf-16be";
    return new TextDecoder(enc).decode(bytes);
  }

  return {
    LABELS: LABELS, DISPLAY: DISPLAY,
    isLuhnValid: isLuhnValid, isValidSSN: isValidSSN, isValidIBAN: isValidIBAN, isLowRiskURL: isLowRiskURL,
    stripInvisible: stripInvisible, projectToRaw: projectToRaw,
    detectHeuristics: detectHeuristics, mergeSpans: mergeSpans, detect: detect,
    redact: redact, check: check, decodeBytes: decodeBytes
  };
});
