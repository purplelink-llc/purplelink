// The Retraction Checker page (/tools/retraction-check/): a client-side tool that asks Crossref about each DOI.
// Covers the page contract (head, schema, no inline styles, privacy wording, wiring) and the pure logic that
// the page runs: DOI and reference extraction, and retraction detection on Crossref's record shape.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const SITE = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "site");
const read = (p) => readFileSync(join(SITE, p), "utf8");
const html = read("tools/retraction-check/index.html");
const js = read("tools/retraction-check/retraction-check.js");

const ctx = { window: {} };
vm.createContext(ctx);
vm.runInContext(js, ctx);
const rawCore = ctx.window.RetractionCheckCore;
// Values built inside the VM have its own Array and Object prototypes; round-trip them so deepEqual compares structure.
const J = (x) => (x === undefined ? x : JSON.parse(JSON.stringify(x)));
const core = {
  extractDois: (t) => J(rawCore.extractDois(t)),
  extractUndoiedReferences: (t) => J(rawCore.extractUndoiedReferences(t)),
  retractionOf: (r) => J(rawCore.retractionOf(r)),
  trimDoi: rawCore.trimDoi,
  overlap: rawCore.overlap,
};

function jsonLd(h) {
  return [...h.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)].flatMap((m) => {
    const d = JSON.parse(m[1]);
    return d["@graph"] || [d];
  });
}

// ---- the page --------------------------------------------------------------------------------------

test("the page has a title, description, canonical and valid JSON-LD with an FAQ", () => {
  assert.match(html, /<title>Retraction Checker[^<]* \| Purplelink<\/title>/);
  assert.match(html, /<link rel="canonical" href="https:\/\/purplelink\.llc\/tools\/retraction-check\/">/);
  assert.doesNotMatch(html, /noindex/);
  const nodes = jsonLd(html);
  const types = nodes.map((n) => n["@type"]);
  assert.ok(types.includes("WebApplication") && types.includes("BreadcrumbList") && types.includes("FAQPage"));
  const faq = nodes.find((n) => n["@type"] === "FAQPage");
  assert.ok(faq.mainEntity.length >= 5);
  for (const q of faq.mainEntity) assert.ok(q.acceptedAnswer.text.length > 40);
  assert.equal(nodes.find((n) => n["@type"] === "WebApplication").offers.price, "0");
});

test("styles and scripts are external: no inline style attributes or style blocks", () => {
  assert.doesNotMatch(html, /\sstyle="/);
  assert.doesNotMatch(html, /<style[\s>]/);
  assert.match(html, /href="\/tools\/retraction-check\/retraction-check\.css/);
  assert.match(html, /src="\/tools\/retraction-check\/retraction-check\.js/);
});

test("the privacy wording is accurate: not sent to Purplelink, Crossref sees the queries", () => {
  assert.match(html, /not sent to Purplelink/i);
  assert.match(html, /Crossref, a public service, does see the DOIs and titles/);
  assert.doesNotMatch(js, /modal\.run|netlify\/functions/);                // no Purplelink backend is called
  assert.match(js, /https:\/\/api\.crossref\.org\/works/);
});

test("the page links to Paper Review, keeps one h1, and the tool-next prompt is hidden until results", () => {
  assert.equal((html.match(/<h1[ >]/g) || []).length, 1);
  assert.match(html, /<p class="tool-next" data-tool-next="#rc-results" hidden>/);
  assert.match(html, /href="\/tools\/paper-review\/"/);
  assert.match(html, /id="rc-form"[\s\S]*id="rc-text"[\s\S]*id="rc-run"[\s\S]*id="rc-results"/);
  assert.match(html, /<label for="rc-text"/);
});

test("results are written with textContent, never innerHTML", () => {
  assert.doesNotMatch(js, /innerHTML|outerHTML|insertAdjacentHTML|document\.write/);
});

test("the tools index, sitemap and llms.txt list the tool", () => {
  assert.match(read("tools/index.html"), /href="\/tools\/retraction-check\/"/);
  assert.match(read("tools/index.html"), /"name": "Retraction Checker"/);
  assert.match(read("sitemap.xml"), /<loc>https:\/\/purplelink\.llc\/tools\/retraction-check\/<\/loc>/);
  assert.match(read("llms.txt"), /Retraction Checker: https:\/\/purplelink\.llc\/tools\/retraction-check\//);
});

// ---- extraction ------------------------------------------------------------------------------------

test("DOIs are found in URLs, prefixed forms and prose, trimmed of punctuation, de-duplicated", () => {
  const text = "See https://doi.org/10.1016/S0140-6736(97)11096-0. Also doi:10.1038/nature14539, (10.1126/science.1059487); again 10.1038/NATURE14539.";
  assert.deepEqual(core.extractDois(text), ["10.1016/S0140-6736(97)11096-0", "10.1038/nature14539", "10.1126/science.1059487"]);
});

test("a DOI's own parentheses are kept and a wrapping bracket is dropped", () => {
  assert.equal(core.trimDoi("10.1016/S0140-6736(97)11096-0)"), "10.1016/S0140-6736(97)11096-0");
  assert.equal(core.trimDoi("10.1016/S0140-6736(97)11096-0"), "10.1016/S0140-6736(97)11096-0");
  assert.equal(core.trimDoi("10.1000/abc123>"), "10.1000/abc123");
});

test("early Wiley DOIs containing angle brackets survive", () => {
  const doi = "10.1002/(SICI)1097-0258(19980430)17:8<873::AID-SIM779>3.0.CO;2-I";
  assert.deepEqual(core.extractDois(`cited as <${doi}>.`), [doi]);
});

test("references without a DOI are found by line, by paragraph and by BibTeX title", () => {
  const text = `[1] Smith, J. (2020). Learning to cite carefully without a doi in sight. Journal of Things, 4, 1-10.
[2] too short 2020
@article{x, title={A study of {things} that have no doi at all}, year={2019}}
@book{y,
  title = "Another entry about measurement without identifiers",
  doi = {10.1000/xyz123}
}`;
  const refs = core.extractUndoiedReferences(text);
  assert.deepEqual(refs.map((r) => r.title), ["A study of things that have no doi at all", "Learning to cite carefully without a doi in sight"]);
  assert.deepEqual(core.extractDois(text), ["10.1000/xyz123"]);
});

test("empty and non-string input never throws", () => {
  for (const v of ["", null, undefined, 5]) {
    assert.deepEqual(core.extractDois(v), []);
    assert.deepEqual(core.extractUndoiedReferences(v), []);
  }
});

// ---- retraction detection (mirrors the backend's crossref_retraction) -------------------------------

const WAKEFIELD = {
  title: ["RETRACTED: Ileal-lymphoid-nodular hyperplasia"],
  "updated-by": [
    { DOI: "10.1016/s0140-6736(04)15715-2", type: "correction", updated: { "date-parts": [[2004, 3, 6]] } },
    { DOI: "10.1016/s0140-6736(10)60175-4", type: "retraction", updated: { "date-parts": [[2010, 2, 6]] } },
  ],
};

test("a retraction is found with its notice and date; a correction alone is not one", () => {
  assert.deepEqual(core.retractionOf(WAKEFIELD),
    { kind: "retracted", types: ["retraction"], noticeDoi: "10.1016/s0140-6736(10)60175-4", date: "2010-02-06" });
  assert.equal(core.retractionOf({ title: ["A paper"], "updated-by": [{ DOI: "10.1/c", type: "correction" }, { DOI: "10.1/e", type: "erratum" }] }), null);
});

test("expressions of concern and partial retractions are concerns; a retraction outranks them", () => {
  assert.equal(core.retractionOf({ "updated-by": [{ DOI: "10.1/x", type: "expression_of_concern", updated: { "date-parts": [[2021, 5]] } }] }).kind, "concern");
  assert.equal(core.retractionOf({ "updated-by": [{ DOI: "10.1/y", type: "partial_retraction" }] }).kind, "concern");
  const both = core.retractionOf({ "updated-by": [{ DOI: "10.1/a", type: "expression_of_concern" }, { DOI: "10.1/b", type: "withdrawal" }] });
  assert.equal(both.kind, "retracted");
  assert.equal(both.noticeDoi, "10.1/b");
});

test("a record that is itself a retraction notice counts as a retraction", () => {
  const notice = { DOI: "10.1016/s0140-6736(10)60175-4", title: ["Retraction: Ileal-lymphoid-nodular hyperplasia"],
    "update-to": [{ DOI: "10.1016/s0140-6736(97)11096-0", type: "retraction", updated: { "date-parts": [[2010, 2, 6]] } }] };
  const r = core.retractionOf(notice);
  assert.equal(r.kind, "retracted");
  assert.deepEqual(r.types, ["notice_itself"]);
  assert.equal(r.date, "2010-02-06");
  assert.equal(core.retractionOf({ DOI: "10.1/x", "update-to": [{ DOI: "10.1/y", type: "correction" }] }), null);
});

test("the publisher title flag counts only as a prefix, not when a paper is about retraction", () => {
  assert.equal(core.retractionOf({ title: ["RETRACTED: Some result"] }).types[0], "title_flag");
  assert.equal(core.retractionOf({ title: ["Retraction notices in medical journals"] }), null);
  assert.equal(core.retractionOf({ title: ["Withdrawn consent in clinical trials"] }), null);
});

test("malformed records never throw", () => {
  for (const bad of [null, undefined, [], "x", { "updated-by": "retraction" }, { "updated-by": [null, 3] }, { title: null }, { title: [5] }]) {
    assert.equal(core.retractionOf(bad), null);
  }
  assert.equal(core.retractionOf({ "updated-by": [{ DOI: "10.1/z", type: "retraction", updated: { "date-parts": [["x"]] } }] }).date, "");
});

test("title similarity accepts a close match and rejects an unrelated one", () => {
  assert.ok(core.overlap("Deep learning for protein folding", "Deep Learning for Protein Folding") > 0.9);
  assert.ok(core.overlap("Deep learning for protein folding", "Zebra migration across savanna corridors") < 0.2);
});
