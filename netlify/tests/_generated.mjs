// site/search-index.json and site/llms-full.txt are build output, not committed (docs/designs/generated-files-at-build.md).
// A test file that reads either imports this first, so it sees a copy built from the current pages. node --test runs
// files in parallel; the generators write to a temp file and rename it, so a reader never sees half a file.
import { execFileSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
for (const gen of ["gen_search_index.py", "gen_llms_full.py"]) {
  execFileSync("python3", [join(ROOT, "scripts", gen)], { cwd: ROOT, stdio: "ignore", timeout: 120_000 });
}
