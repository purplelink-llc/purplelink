/* Runs the PII Checker off the main thread so a long text does not freeze the page.
   Loads the same core file as the page. It makes no network request of its own. */
"use strict";
var q = new URL(self.location.href).searchParams;
var cv = q.get("c") ? "?v=" + q.get("c") : "";
importScripts("/tools/pii-checker/pii-checker-core.js" + cv);

self.onmessage = function (e) {
  var m = e.data;
  try {
    var r = PiiCheck.check(m.text);
    self.postMessage({
      id: m.id, ok: true, total: r.total, groups: r.groups, redacted: r.redacted,
      spans: r.spans.map(function (s) { return { s: s.start, e: s.end, l: s.label }; })
    });
  } catch (err) {
    self.postMessage({ id: m.id, ok: false, message: String((err && err.message) || err) });
  }
};
