// node write-srt.mjs <storyboard.json> <timing.json> [16x9|9x16]  -> SubRip on stdout (src/howto/srt.js; used by tests)
import fs from "node:fs";
import { buildSrt } from "./src/howto/srt.js";
const [sbPath, timingPath, format = "16x9"] = process.argv.slice(2);
if (!sbPath || !timingPath) { console.error("usage: node write-srt.mjs <storyboard.json> <timing.json> [16x9|9x16]"); process.exit(2); }
process.stdout.write(buildSrt(JSON.parse(fs.readFileSync(sbPath, "utf8")), JSON.parse(fs.readFileSync(timingPath, "utf8")), format));
