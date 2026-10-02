// node verify-latexfix.mjs : compiles each minimal example with the local pdflatex (one process at a time, 60 s
// timeout) into .cache/latex-check/<slug>/ and reports which log lines in src/latexfix/data.js are not in the real log.
// Also compiles the corrected file where a stage holds a complete file and reports whether the message is gone.
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { ERRORS } from "./src/latexfix/data.js";
const ROOT = path.dirname(fileURLToPath(import.meta.url));
const only = process.argv[2];
const run = (dir, lines) => {
  fs.mkdirSync(dir, { recursive: true });
  for (const f of fs.readdirSync(dir)) fs.rmSync(path.join(dir, f), { force: true });
  fs.writeFileSync(path.join(dir, "main.tex"), lines.join("\n") + "\n");
  spawnSync("pdflatex", ["-interaction=nonstopmode", "main.tex"], { cwd: dir, timeout: 60000, stdio: "ignore" });
  const log = path.join(dir, "main.log");
  return fs.existsSync(log) ? fs.readFileSync(log, "latin1") : "";
};
for (const [slug, E] of Object.entries(ERRORS)) {
  if (only && slug !== only) continue;
  const file = E.file || E.stages[0].lines;
  const log = run(path.join(ROOT, ".cache/latex-check", slug), file);
  const missing = E.log.filter((l) => !log.split("\n").some((x) => x.replace(/\s+$/, "") === l.replace(/\s+$/, "")));
  const first = E.log[0];
  let fixed = "";
  const last = E.stages.at(-1);
  if (last.gutter && last.lines.length === file.length) {
    const flog = run(path.join(ROOT, ".cache/latex-check", `${slug}-fixed`), last.lines);
    fixed = flog.includes(first.replace(/\.$/, "")) ? "fixed file STILL shows the message" : /^!/m.test(flog) ? "fixed file has another error" : "fixed file compiles clean";
  } else fixed = "fix is a partial block, not compiled";
  console.log(`${slug}: ${missing.length ? "MISSING " + JSON.stringify(missing) : "all log lines match the real log"}; ${fixed}`);
}
