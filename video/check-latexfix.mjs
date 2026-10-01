// node check-latexfix.mjs : asserts every log line and source line in src/latexfix/data.js appears verbatim in
// the matching page (site/latex-errors/<slug>/index.html at origin/main, or the working tree if present).
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { ERRORS } from "./src/latexfix/data.js";
const ROOT = path.dirname(fileURLToPath(import.meta.url));
const dec = (s) => s.replace(/<[^>]+>/g, "").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&#39;|&#x27;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, "&");
let bad = 0;
for (const [slug, E] of Object.entries(ERRORS)) {
  const rel = `site/latex-errors/${slug}/index.html`;
  const local = path.join(ROOT, "..", rel);
  const html = fs.existsSync(local) ? fs.readFileSync(local, "utf8") : execFileSync("git", ["show", `origin/main:${rel}`], { cwd: ROOT, encoding: "utf8" });
  const pres = [...html.matchAll(/<pre[^>]*>([\s\S]*?)<\/pre>/g)].map((m) => dec(m[1]).split("\n")).flat();
  const want = [...E.log, ...E.stages.flatMap((s) => s.lines)];
  for (const l of want) if (!pres.includes(l) && !(E.derived || []).includes(l)) { bad++; console.log(`${slug}: NOT ON PAGE: ${JSON.stringify(l)}`); }
  console.log(`${slug}: ${want.length} lines checked`);
}
process.exit(bad ? 1 : 0);
