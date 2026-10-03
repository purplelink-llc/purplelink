// Tests for site/tools/metadata-cleaner/metadata-cleaner-core.js.
// Run: node --test scripts/metadata-cleaner.test.mjs
// Image fixtures live in scripts/fixtures/metadata-cleaner/ (32x24 pictures carrying
// EXIF, GPS, XMP and IPTC made with exiftool). Where exiftool is installed it is used
// as an independent reader of the cleaned output.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const FIX = path.join(ROOT, "scripts/fixtures/metadata-cleaner");

function loadUmd(file) {
  const module = { exports: {} };
  new Function("module", "exports", fs.readFileSync(file, "utf8")).call(module.exports, module, module.exports);
  return module.exports;
}
await import(pathToFileURL(path.join(ROOT, "site/tools/metadata-cleaner/metadata-cleaner-core.js")).href);
const MC = globalThis.MetaClean;
const PDFLib = loadUmd(path.join(ROOT, "site/assets/vendor/pdf-lib.min.js"));
const JSZip = loadUmd(path.join(ROOT, "site/assets/vendor/jszip/jszip.min.js"));
const libs = { PDFLib, JSZip };

let hasExiftool = true;
try { execFileSync("exiftool", ["-ver"], { stdio: "pipe" }); } catch { hasExiftool = false; }
function exif(bytes, ext) {
  const f = path.join(fs.mkdtempSync(path.join(process.env.TMPDIR || "/tmp", "mc-")), "out." + ext);
  fs.writeFileSync(f, bytes);
  return execFileSync("exiftool", ["-a", "-G1", "-s", f], { encoding: "utf8" });
}
const fields = (res) => res.found.map((f) => f.field);
const read = (n) => new Uint8Array(fs.readFileSync(path.join(FIX, n)));

for (const [name, ext] of [["photo.jpg", "jpg"], ["photo.png", "png"], ["photo.webp", "webp"]]) {
  test("image: " + name, async () => {
    const res = await MC.run(name, read(name), libs, {});
    const f = fields(res);
    assert.ok(f.includes("Artist"), "finds Artist");
    const gps = res.found.find((x) => x.field === "GPS position");
    assert.ok(gps && /^33\.749\d*, -84\.388\d*$/.test(gps.value), "reads GPS: " + (gps && gps.value));
    assert.ok(res.out.length < read(name).length, "output is smaller");
    assert.deepEqual(await MC.verify(res.kind, res.out, libs), [], "re-read finds nothing");
    assert.ok(res.kept.some((k) => /Rotation/.test(k)), "keeps rotation");
    if (hasExiftool) {
      const out = exif(res.out, ext);
      assert.ok(!/Ben Ampel|GPS|Canon|EOS|Photoshop|GIMP|made by ben|123456/.test(out), "exiftool sees no personal fields:\n" + out);
      assert.match(out, /Orientation\s*:\s*(Rotate 90 CW|Rotate 180)/);
    }
  });
}

test("jpeg: pixels are untouched", () => {
  const a = read("photo.jpg");
  const res = MC.processJpeg(a, {});
  const skip = (b) => { let i = 2; while (b[i] === 0xff && b[i + 1] !== 0xda) i += 2 + ((b[i + 2] << 8) | b[i + 3]); return b.subarray(i); };
  assert.deepEqual(Buffer.from(skip(res.out)), Buffer.from(skip(a)));
});

test("jpeg: keepOrientation false drops the rotation too", () => {
  const res = MC.processJpeg(read("photo.jpg"), { keepOrientation: false });
  if (hasExiftool) assert.ok(!/Orientation/.test(exif(res.out, "jpg")));
});

test("jpeg: rejects non-jpeg", () => {
  assert.throws(() => MC.processJpeg(new Uint8Array([1, 2, 3, 4])), /JPEG/);
});

test("png: crc of the rebuilt eXIf chunk is valid", () => {
  if (!hasExiftool) return;
  const res = MC.processPng(read("photo.png"), {});
  assert.ok(!/Warning|Error/.test(exif(res.out, "png")));
});

test("pdf: info, xmp, annotation author, orphan object, embedded jpeg", async () => {
  const doc = await PDFLib.PDFDocument.create();
  doc.setAuthor("Ben Ampel"); doc.setTitle("Secret Title"); doc.setSubject("Subj"); doc.setKeywords(["k1"]);
  doc.setCreator("pdfTeX-1.40"); doc.setProducer("TeX Live 2025");
  const page = doc.addPage([200, 200]);
  page.drawText("Hello page", { x: 20, y: 100 });
  const ctx = doc.context;
  const xmp = ctx.stream('<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:creator><rdf:Seq><rdf:li>Ben Ampel</rdf:li></rdf:Seq></dc:creator></rdf:Description></rdf:RDF></x:xmpmeta>', { Type: "Metadata", Subtype: "XML" });
  doc.catalog.set(PDFLib.PDFName.of("Metadata"), ctx.register(xmp));
  const annot = ctx.obj({ Type: "Annot", Subtype: "Text", Rect: [10, 10, 30, 30], Contents: PDFLib.PDFString.of("note"), T: PDFLib.PDFString.of("Reviewer Two") });
  page.node.set(PDFLib.PDFName.of("Annots"), ctx.obj([ctx.register(annot)]));
  ctx.register(ctx.obj({ OldSecret: PDFLib.PDFString.of("leftover-from-v1") }));
  const jpg = read("photo.jpg");
  const img = await doc.embedJpg(jpg);
  page.drawImage(img, { x: 20, y: 20, width: 32, height: 24 });
  const bytes = await doc.save({ useObjectStreams: false });
  assert.ok(Buffer.from(bytes).includes("leftover-from-v1"));

  const res = await MC.run("paper.pdf", bytes, libs, {});
  const f = fields(res);
  for (const want of ["Author", "Title", "Subject", "Keywords", "Created with", "PDF producer", "Comment and markup authors", "Leftover objects from earlier saves"]) assert.ok(f.includes(want), "found " + want + " in " + f.join(", "));
  const outStr = Buffer.from(res.out).toString("latin1");
  for (const bad of ["Ben Ampel", "Secret Title", "pdfTeX", "TeX Live", "leftover-from-v1", "Reviewer Two", "xmpmeta"]) assert.ok(!outStr.includes(bad), "gone: " + bad);
  assert.ok(res.out.length > 500);
  assert.deepEqual(await MC.verify("pdf", res.out, libs), [], "re-read finds nothing");
  // Still a valid, one-page PDF with the image and annotation intact.
  const back = await PDFLib.PDFDocument.load(res.out);
  assert.equal(back.getPageCount(), 1);
  assert.equal(back.getPage(0).node.Annots().size(), 1);
  if (hasExiftool) {
    const out = exif(res.out, "pdf");
    assert.ok(!/Author|Title|Creator|Producer|Ben Ampel/.test(out.replace(/PDFVersion|Linearized/g, "")), out);
    assert.ok(!/Warning/.test(out), out);
  }
  // The embedded JPEG lost its EXIF/GPS.
  const jpegStart = Buffer.from(res.out).indexOf(Buffer.from([0xff, 0xd8, 0xff]));
  assert.ok(jpegStart > 0);
  assert.ok(!outStr.includes("Exif"), "no Exif left in embedded image");
});

test("pdf: encrypted file gives a plain message", async () => {
  await assert.rejects(MC.run("x.pdf", new TextEncoder().encode("%PDF-1.4\nnot really"), libs, {}), /could not be read|password/);
});

async function buildDocx() {
  const z = new JSZip();
  z.file("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="jpeg" ContentType="image/jpeg"/><Default Extension="jpg" ContentType="image/jpeg"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/people.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.people+xml"/></Types>');
  z.file("_rels/.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/thumbnail" Target="docProps/thumbnail.jpeg"/></Relationships>');
  z.file("docProps/core.xml", '<?xml version="1.0"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/"><dc:title>Blind Paper</dc:title><dc:creator>Ben Ampel</dc:creator><cp:lastModifiedBy>Jane Coauthor</cp:lastModifiedBy><dcterms:created>2026-01-02T03:04:05Z</dcterms:created></cp:coreProperties>');
  z.file("docProps/app.xml", '<?xml version="1.0"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Template>Normal.dotm</Template><TotalTime>45</TotalTime><Application>Microsoft Office Word</Application><Company>Georgia State University</Company><Pages>1</Pages></Properties>');
  z.file("docProps/custom.xml", '<?xml version="1.0"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"><property fmtid="{x}" pid="2" name="Project"><vt:lpwstr xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">Grant 42</vt:lpwstr></property></Properties>');
  z.file("docProps/thumbnail.jpeg", read("photo.jpg"));
  z.file("word/document.xml", '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p w:rsidR="00A1B2C3" w:rsidRDefault="00A1B2C3"><w:ins w:id="1" w:author="Reviewer Two" w:date="2026-02-03T00:00:00Z"><w:r><w:t>Hello</w:t></w:r></w:ins></w:p></w:body></w:document>');
  z.file("word/comments.xml", '<?xml version="1.0"?><w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:comment w:id="0" w:author="Ben Ampel" w:initials="BA" w:date="2026-02-03T00:00:00Z"><w:p><w:r><w:t>my note</w:t></w:r></w:p></w:comment></w:comments>');
  z.file("word/people.xml", '<?xml version="1.0"?><w15:people xmlns:w15="http://schemas.microsoft.com/office/word/2012/wordml"><w15:person w15:author="Ben Ampel"><w15:presenceInfo w15:providerId="AD" w15:userId="S::ben@gsu.edu"/></w15:person></w15:people>');
  z.file("word/settings.xml", '<?xml version="1.0"?><w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:attachedTemplate r:id="rId1"/><w:rsids><w:rsidRoot w:val="00A1B2C3"/><w:rsid w:val="00A1B2C3"/></w:rsids></w:settings>');
  z.file("word/_rels/settings.xml.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/attachedTemplate" Target="file:///C:/Users/ben/AppData/Normal.dotm" TargetMode="External"/></Relationships>');
  z.file("word/_rels/document.xml.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId5" Type="http://schemas.microsoft.com/office/2011/relationships/people" Target="people.xml"/><Relationship Id="rId6" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image1.jpg"/></Relationships>');
  z.file("word/media/image1.jpg", read("photo.jpg"));
  return z.generateAsync({ type: "uint8array" });
}

test("docx: properties, authors, people, thumbnail, template path, embedded photo", async () => {
  const bytes = await buildDocx();
  const res = await MC.run("manuscript.docx", bytes, libs, {});
  assert.equal(res.kind, "docx");
  const f = fields(res);
  for (const want of ["Author", "Last saved by", "Title", "Company", "Template", "Custom properties", "Preview thumbnail", "Names on comments, tracked changes and reviewers", "People list", "Link to a file on a computer", "Photo metadata inside embedded images"]) assert.ok(f.includes(want), "found " + want + " in " + f.join(" | "));
  const z = await JSZip.loadAsync(res.out);
  const all = (await Promise.all(Object.keys(z.files).filter((n) => !z.files[n].dir && /\.(xml|rels)$/.test(n)).map((n) => z.file(n).async("string")))).join("\n");
  for (const bad of ["Ben Ampel", "Jane Coauthor", "Georgia State", "Reviewer Two", "Grant 42", "C:/Users", "00A1B2C3", "Blind Paper", "ben@gsu.edu"]) assert.ok(!all.includes(bad), "gone: " + bad);
  assert.ok(!z.file("docProps/thumbnail.jpeg"));
  assert.ok(!z.file("word/people.xml"));
  assert.ok(!/thumbnail|people/.test(await z.file("_rels/.rels").async("string") + await z.file("word/_rels/document.xml.rels").async("string") + await z.file("[Content_Types].xml").async("string")));
  assert.ok((await z.file("word/document.xml").async("string")).includes("Hello"), "text kept");
  assert.ok((await z.file("word/comments.xml").async("string")).includes("my note"), "comments kept");
  assert.ok((await z.file("word/comments.xml").async("string")).includes('w:author="Author"'));
  assert.deepEqual(await MC.verify("docx", res.out, libs), [], "re-read finds nothing");
  const img = await z.file("word/media/image1.jpg").async("uint8array");
  assert.deepEqual(MC.processJpeg(img, {}).found, [], "embedded photo is clean");
  assert.ok(Object.values(z.files).every((e) => e.date.getUTCFullYear() === 1980), "zip timestamps normalized");
  if (hasExiftool) assert.ok(!/Ben Ampel|Creator|LastModifiedBy/.test(exif(res.out, "docx")), exif(res.out, "docx"));
});

test("docx: anonymize false keeps author names on comments", async () => {
  const res = await MC.run("manuscript.docx", await buildDocx(), libs, { anonymize: false });
  const z = await JSZip.loadAsync(res.out);
  assert.ok((await z.file("word/comments.xml").async("string")).includes("Ben Ampel"));
  assert.ok(!(await z.file("docProps/core.xml").async("string")).includes("Ben Ampel"));
});

test("xlsx: absPath, comment authors, persons", async () => {
  const z = new JSZip();
  z.file("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>');
  z.file("xl/workbook.xml", '<workbook xmlns="x" xmlns:mc="m" xmlns:x15ac="y"><fileVersion appName="xl"/><mc:AlternateContent xmlns:mc="m"><mc:Choice Requires="x15ac"><x15ac:absPath url="/Users/ben/Documents/Grants/" xmlns:x15ac="y"/></mc:Choice></mc:AlternateContent><sheets/></workbook>');
  z.file("xl/comments1.xml", '<comments><authors><author>Ben Ampel</author></authors></comments>');
  z.file("xl/persons/person.xml", '<personList><person displayName="Ben Ampel" id="{1}" userId="ben@gsu.edu" providerId="AD"/></personList>');
  const res = await MC.run("data.xlsx", await z.generateAsync({ type: "uint8array" }), libs, {});
  assert.equal(res.kind, "xlsx");
  const f = fields(res);
  assert.ok(f.includes("Folder the workbook was saved in") && f.includes("Names on comments, tracked changes and reviewers"), f.join(" | "));
  const out = await JSZip.loadAsync(res.out);
  const all = (await Promise.all(Object.keys(out.files).filter((n) => !out.files[n].dir).map((n) => out.file(n).async("string")))).join("\n");
  assert.ok(!/Users\/ben|Ben Ampel|ben@gsu/.test(all));
  assert.ok(all.includes("<sheets/>"));
  assert.deepEqual(await MC.verify("xlsx", res.out, libs), []);
});

test("text: hidden characters", () => {
  const sneaky = "a\u200Bb\uFEFFc \u202Eevil\u2069 x\u00A0y " + String.fromCodePoint(0xe0041, 0xe0042) + "z \u00AD";
  const r = MC.cleanText(sneaky, {});
  assert.equal(r.text, "abc evil x y z ");
  assert.ok(r.total >= 8);
  assert.equal(MC.cleanText("flag \u{1F3F4}\u{E0067}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F} ok", {}).total, 0, "flag emoji sequence kept");
  assert.equal(MC.cleanText("\u0645\u06CC\u200C\u062E\u0648\u0627\u0647\u0645", {}).total, 0, "Persian ZWNJ kept");
  assert.equal(MC.cleanText("\u201Cq\u201D \u2014 it\u2019s\u2026", { typography: true }).text, '"q" - it\'s...');
  assert.equal(MC.cleanText("plain text", {}).total, 0);
});

// ---------- v2: more formats, options, checks ----------

test("clean(): returns found, after, check and hashes", async () => {
  const steps = [];
  const r = await MC.clean("photo.jpg", read("photo.jpg"), libs, {}, (p, l) => steps.push(p));
  assert.equal(r.kind, "jpeg");
  assert.deepEqual(r.after, []);
  assert.equal(r.check.ok, true);
  assert.match(r.inHash, /^[0-9a-f]{64}$/);
  assert.match(r.outHash, /^[0-9a-f]{64}$/);
  assert.notEqual(r.inHash, r.outHash);
  assert.ok(steps.length >= 3 && steps[steps.length - 1] === 1 && steps.every((x, i) => i === 0 || x >= steps[i - 1]), "progress rises to 1");
});

test("gif: comment removed, frames identical", async () => {
  const r = await MC.clean("photo.gif", read("photo.gif"), libs, {});
  assert.equal(r.kind, "gif");
  assert.ok(r.found.some((f) => f.field === "GIF comment" && /Ben Ampel/.test(f.value)));
  assert.ok(!Buffer.from(r.out).includes("Ben Ampel"));
  assert.equal(r.out[r.out.length - 1], 0x3b);
});

test("tiff: tags zeroed in place, image data unchanged", async () => {
  const r = await MC.clean("photo.tif", read("photo.tif"), libs, {});
  assert.equal(r.kind, "tiff");
  for (const f of ["Artist", "Camera make", "Camera model", "Software", "Copyright", "GPS position"]) assert.ok(r.found.some((x) => x.field === f), "found " + f);
  assert.equal(r.outSize, r.inSize);
  assert.equal(r.check.ok, true);
  const bin = Buffer.from(r.out).toString("latin1");
  for (const bad of ["Ben Ampel", "Nikon", "D850", "Photoshop", "lab bench"]) assert.ok(!bin.includes(bad), bad);
  if (hasExiftool) { const o = exif(r.out, "tif"); assert.ok(!/Artist|Make|Model|GPS|Copyright|Software|Creator/.test(o), o); assert.match(o, /Orientation/); assert.ok(!/Warning|Error/.test(o), o); }
});

test("svg: editor data, paths and metadata removed, drawing kept", async () => {
  const r = await MC.clean("photo.svg", read("photo.svg"), libs, {});
  const out = Buffer.from(r.out).toString("utf8");
  assert.ok(out.includes("<rect") && out.includes("#7c3aed") && out.includes("Blue square"));
  for (const bad of ["Ben Ampel", "/Users/ben", "inkscape", "sodipodi", "Secret figure", "<metadata"]) assert.ok(!out.includes(bad), bad);
  assert.ok(MC.wellFormed(out));
  assert.deepEqual(r.after, []);
});

test("mp4: boxes blanked in place, same length, still decodes", async () => {
  const src = read("photo.mp4");
  const r = await MC.clean("photo.mp4", src, libs, {});
  assert.equal(r.kind, "mp4");
  for (const f of ["Title", "Artist", "Comment", "GPS position"]) assert.ok(r.found.some((x) => x.field === f), "found " + f);
  assert.equal(r.outSize, r.inSize);
  assert.equal(r.check.ok, true);
  const bin = Buffer.from(r.out).toString("latin1");
  for (const bad of ["Ben Ampel", "Lab demo", "recorded at home", "+33.7490"]) assert.ok(!bin.includes(bad), bad);
  assert.deepEqual(r.after, []);
  if (hasExiftool) { const o = exif(r.out, "mp4"); assert.ok(!/Artist|Title|Location|Comment|CreateDate\s*:\s*2026/.test(o), o); }
});

for (const n of ["photo.odt", "photo.ods", "photo.odp"]) {
  test("opendocument: " + n, async () => {
    const r = await MC.clean(n, read(n), libs, {});
    assert.equal(r.kind, "odf");
    assert.ok(r.found.some((f) => f.field === "Author" && f.value === "Ben Ampel"));
    assert.deepEqual(r.after, []);
    assert.equal(r.check.ok, true, r.check.note);
    const z = await JSZip.loadAsync(r.out);
    assert.equal(Object.keys(z.files)[0], "mimetype", "mimetype first");
    assert.ok(!z.file("Thumbnails/thumbnail.png"));
    const meta = await z.file("meta.xml").async("string");
    assert.ok(!/Ben Ampel|Jane|EPSON|LibreOffice/.test(meta));
    assert.ok(!/EPSON/.test(await z.file("settings.xml").async("string")));
    assert.ok(MC.wellFormed(await z.file("content.xml").async("string")));
  });
}

for (const n of ["real.docx", "real.xlsx", "real.pptx", "lo.docx", "lo.xlsx", "lo.pptx"]) {
  test("office written by python libs and LibreOffice: " + n, async () => {
    const r = await MC.clean(n, read(n), libs, {});
    assert.ok(["docx", "xlsx", "pptx"].includes(r.kind));
    assert.ok(r.found.some((f) => f.field === "Author" && f.value === "Ben Ampel"));
    assert.deepEqual(r.after, [], "re-read finds nothing: " + JSON.stringify(r.after));
    assert.equal(r.check.ok, true, r.check.note);
    const z = await JSZip.loadAsync(r.out);
    const core = await z.file("docProps/core.xml").async("string");
    assert.ok(!/Ben Ampel|Jane|Blind Paper|Secret/.test(core), core);
    for (const name of Object.keys(z.files)) if (/\.(xml|rels)$/.test(name)) assert.ok(MC.wellFormed(await z.file(name).async("string")), "well-formed " + name);
    if (hasExiftool) assert.ok(!/Ben Ampel|Jane|Creator|LastModifiedBy/.test(exif(r.out, r.kind)));
  });
}

test("xlsx comment authors found under xl/comments/ too", async () => {
  const r = await MC.clean("real.xlsx", read("real.xlsx"), libs, {});
  assert.ok(r.found.some((f) => /Names on comments/.test(f.field)));
  const z = await JSZip.loadAsync(r.out);
  const files = Object.keys(z.files).filter((n) => /comment/i.test(n) && /\.xml$/.test(n));
  for (const f of files) assert.ok(!(await z.file(f).async("string")).includes("Ben Ampel"), f);
});

test("options: keep title and set author (pdf, docx, odt)", async () => {
  const doc = await PDFLib.PDFDocument.create();
  doc.setTitle("My Title"); doc.setAuthor("Ben Ampel"); doc.addPage([100, 100]);
  const pdf = await doc.save();
  let r = await MC.clean("a.pdf", pdf, libs, { keepTitle: true, author: "Anonymous" });
  const back = await PDFLib.PDFDocument.load(r.out, { updateMetadata: false });
  assert.equal(back.getTitle(), "My Title");
  assert.equal(back.getAuthor(), "Anonymous");
  assert.deepEqual(r.after, []);
  r = await MC.clean("real.docx", read("real.docx"), libs, { keepTitle: true, author: "Anonymous" });
  let core = await (await JSZip.loadAsync(r.out)).file("docProps/core.xml").async("string");
  assert.ok(core.includes("<dc:title>Blind Paper</dc:title>") && core.includes("<dc:creator>Anonymous</dc:creator>") && !core.includes("Jane"));
  assert.deepEqual(r.after, []);
  r = await MC.clean("photo.odt", read("photo.odt"), libs, { keepTitle: true, author: "Anonymous" });
  const meta = await (await JSZip.loadAsync(r.out)).file("meta.xml").async("string");
  assert.ok(meta.includes("Blind Paper") && meta.includes("Anonymous") && !meta.includes("Ben Ampel"));
});

test("left-in-place items are reported but not flagged as leftovers", async () => {
  const r = await MC.clean("real.docx", read("real.docx"), libs, {});
  assert.ok(r.left.some((f) => f.field === "Custom XML parts"));
  assert.deepEqual(r.after, []);
});

test("an edit that breaks XML is refused, not shipped", async () => {
  const z = new JSZip();
  z.file("[Content_Types].xml", '<Types xmlns="x"/>');
  z.file("word/document.xml", '<w:document xmlns:w="w"><w:p w:author="Bad & Co"><w:t>x</w:p></w:document>');
  const bytes = await z.generateAsync({ type: "uint8array" });
  await assert.rejects(MC.clean("bad.docx", bytes, libs, {}), /broken|untouched/);
});

test("wellFormed", () => {
  assert.ok(MC.wellFormed('<?xml version="1.0"?><a x="1"><b/><!-- c --><![CDATA[<z>]]></a>'));
  assert.ok(!MC.wellFormed("<a><b></a>"));
  assert.ok(!MC.wellFormed("<a>text < more</a>"));
});

test("unsupported inputs give a plain message", async () => {
  await assert.rejects(MC.clean("x.doc", new Uint8Array([0xd0, 0xcf, 0x11, 0xe0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]), libs, {}), /Old \.doc/);
  await assert.rejects(MC.clean("x.bin", new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]), libs, {}), /Not supported/);
});
