// Search Console (2026-10-09) warned about "uploadDate is missing a timezone"
// and "invalid datetime value for uploadDate": three pages had a bare date.
// Every VideoObject on the site needs a full ISO 8601 datetime with an offset.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const SITE = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "site");
const DATETIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:\d{2}|Z)$/;

function* htmlFiles(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) yield* htmlFiles(p);
    else if (name.endsWith(".html")) yield p;
  }
}

function* nodes(value) {
  if (Array.isArray(value)) for (const v of value) yield* nodes(v);
  else if (value && typeof value === "object") {
    yield value;
    for (const v of Object.values(value)) yield* nodes(v);
  }
}

function videoObjects() {
  const found = [];
  for (const file of htmlFiles(SITE)) {
    const html = readFileSync(file, "utf8");
    for (const m of html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)) {
      let data;
      try { data = JSON.parse(m[1]); } catch { continue; }
      for (const n of nodes(data)) {
        const types = [].concat(n["@type"] || []);
        if (types.includes("VideoObject")) found.push({ file: file.slice(SITE.length), node: n });
      }
    }
  }
  return found;
}

test("the site has VideoObject structured data to check", () => {
  assert.ok(videoObjects().length >= 4);
});

test("every VideoObject uploadDate is a full datetime with a timezone", () => {
  for (const { file, node } of videoObjects()) {
    assert.match(String(node.uploadDate), DATETIME, `${file}: uploadDate ${JSON.stringify(node.uploadDate)}`);
    assert.ok(!Number.isNaN(Date.parse(node.uploadDate)), `${file}: uploadDate does not parse`);
    assert.ok(Date.parse(node.uploadDate) <= Date.now() + 86_400_000, `${file}: uploadDate is in the future`);
  }
});

test("every VideoObject has a name, a thumbnail and a description", () => {
  for (const { file, node } of videoObjects()) {
    assert.ok(node.name, `${file}: name`);
    assert.ok(node.thumbnailUrl, `${file}: thumbnailUrl`);
    assert.ok(node.description, `${file}: description`);
  }
});
