/* Runs the Transcript Cleaner off the main thread so a large file does not freeze the page.
   Loads the same core file as the page. It makes no network request of its own. */
"use strict";
var q = new URL(self.location.href).searchParams;
var cv = q.get("c") ? "?v=" + q.get("c") : "";
importScripts("/tools/transcript-cleaner/transcript-cleaner-core.js" + cv);

var docs = {};
self.onmessage = function (e) {
  var m = e.data;
  if (m.drop) { delete docs[m.id]; return; }
  try {
    if (m.text != null) docs[m.id] = TranscriptClean.parse(m.text, m.name);
    var doc = docs[m.id];
    if (!doc) throw new Error("This file is no longer loaded.");
    self.postMessage({ id: m.id, ok: true, res: TranscriptClean.render(doc, m.opts) });
  } catch (err) {
    self.postMessage({ id: m.id, ok: false, message: String((err && err.message) || err) });
  }
};
