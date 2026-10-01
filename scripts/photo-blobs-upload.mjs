// Upload the clean originals and calendar PDFs that photo-download.mjs serves
// into the private `photo-files` Blobs store of the purplelink site.
//
// Called by scripts/photo-blobs-upload.sh (which resolves the paths and the
// manifest). Reads the Netlify access token from the CLI's own login
// (~/Library/Preferences/netlify/config.json) at run time; nothing is stored
// in the repo and the token is never printed. Same store/site pattern as
// kits-delivery/upload-to-blobs.mjs.
//
//   node scripts/photo-blobs-upload.mjs MANIFEST.json  < list of "key<TAB>path" lines
import { createRequire } from "node:module";
import { readFile, writeFile, stat } from "node:fs/promises";
import { createInterface } from "node:readline";
import os from "node:os";
import path from "node:path";

const SITE_ID = "b264591f-fbbe-4048-9d9d-7051cf497823"; // purplelink
const STORE = "photo-files";
// @netlify/blobs is installed in the main checkout; resolve it from there
// even when this script runs from a worktree.
const NODE_DIR = process.env.PL_NODE_DIR || process.cwd();
const { getStore } = await import(createRequire(path.join(NODE_DIR, "package.json")).resolve("@netlify/blobs"));

async function token() {
  if (process.env.NETLIFY_AUTH_TOKEN) return process.env.NETLIFY_AUTH_TOKEN;
  const cfg = JSON.parse(await readFile(path.join(os.homedir(), "Library/Preferences/netlify/config.json"), "utf8"));
  const user = cfg.users?.[cfg.userId] || Object.values(cfg.users || {})[0];
  const t = user?.auth?.token;
  if (!t) throw new Error("No Netlify token: run `netlify login` or set NETLIFY_AUTH_TOKEN.");
  return t;
}

const manifestPath = process.argv[2];
let manifest = {};
try { manifest = JSON.parse(await readFile(manifestPath, "utf8")); } catch { manifest = {}; }
const store = getStore({ name: STORE, siteID: SITE_ID, token: await token() });

const todo = [];
for await (const line of createInterface({ input: process.stdin })) {
  const [key, file] = line.split("\t");
  if (key && file) todo.push([key, file]);
}
let up = 0, skip = 0, fail = 0;
for (const [key, file] of todo) {
  const st = await stat(file);
  const sig = `${st.size}:${Math.floor(st.mtimeMs / 1000)}`;
  if (manifest[key] === sig) { skip++; continue; }
  try {
    await store.set(key, await readFile(file));
    manifest[key] = sig; up++;
    await writeFile(manifestPath, JSON.stringify(manifest, null, 1) + "\n");
    console.log(`uploaded ${key} (${Math.round(st.size / 1024)} KB)`);
  } catch (err) {
    fail++;
    console.log(`FAILED ${key}: ${String(err.message || err).slice(0, 160)}`);
  }
}
console.log(`done: ${up} uploaded, ${skip} unchanged, ${fail} failed, ${Object.keys(manifest).length} in store manifest`);
process.exit(fail ? 1 : 0);
