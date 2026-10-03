/* Runs the Metadata Cleaner off the main thread so large files do not freeze the page.
   Loads the same core file as the page. Only this site's own scripts are fetched. */
"use strict";
var q = new URL(self.location.href).searchParams;
var cv = q.get("c") ? "?v=" + q.get("c") : "";
importScripts("/tools/metadata-cleaner/metadata-cleaner-core.js" + cv, "/assets/vendor/jszip/jszip.min.js");

self.onmessage = async function (e) {
  var m = e.data;
  try {
    var bytes = new Uint8Array(m.buffer);
    if (MetaClean.kindOf(m.name, bytes) === "pdf" && !self.PDFLib) importScripts("/assets/vendor/pdf-lib.min.js");
    var res = await MetaClean.clean(m.name, bytes, { PDFLib: self.PDFLib, JSZip: self.JSZip }, m.opts, function (p, label) {
      self.postMessage({ id: m.id, type: "progress", p: p, label: label });
    });
    self.postMessage({ id: m.id, type: "done", res: res }, [res.out.buffer]);
  } catch (err) {
    self.postMessage({ id: m.id, type: "error", message: String((err && err.message) || err) });
  }
};
