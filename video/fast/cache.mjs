// Shared cache helpers for the fast video pipeline. Everything derived (proxies, bundles, benchmark output) lives
// in one cache root on the INTERNAL drive by default, so repeated renders do not read or write the external SSD.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";
import { execSync } from "node:child_process";

export const CACHE_ROOT = process.env.VFAST_CACHE || path.join(os.homedir(), "Library", "Caches", "purplelink-video");
export const cachePath = (...p) => { const d = path.join(CACHE_ROOT, ...p); fs.mkdirSync(path.dirname(d), { recursive: true }); return d; };

export const sha = (s, n = 16) => crypto.createHash("sha1").update(s).digest("hex").slice(0, n);

/** Stable fingerprint of a file from path, size and mtime (fast: never reads the content). */
export function fileKey(f) {
  const st = fs.statSync(f);
  return sha(`${path.resolve(f)}|${st.size}|${Math.round(st.mtimeMs)}`);
}

/** Fingerprint of a directory tree's source files (names, sizes, mtimes). Used to key bundle caches. */
export function dirKey(dir, exts = [".js", ".jsx", ".mjs", ".ts", ".tsx", ".json", ".css"]) {
  const parts = [];
  const walk = (d) => {
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      if (e.name === "node_modules" || e.name.startsWith(".")) continue;
      const p = path.join(d, e.name);
      if (e.isDirectory()) walk(p);
      else if (exts.includes(path.extname(e.name))) { const st = fs.statSync(p); parts.push(`${p}|${st.size}|${Math.round(st.mtimeMs)}`); }
    }
  };
  walk(dir);
  return sha(parts.sort().join("\n"));
}

export const loadavg1 = () => os.loadavg()[0];

/** Wait until the one-minute load average is at or below `max`, up to `timeoutS`. Returns the load seen at the end. */
export async function waitQuiet(max = 3.5, timeoutS = 180) {
  const t0 = Date.now();
  while (loadavg1() > max && (Date.now() - t0) / 1000 < timeoutS) await new Promise((r) => setTimeout(r, 5000));
  return loadavg1();
}

/** Keep the cache under `maxGB` by deleting the least recently used top-level entries of each cache area. Proxies are cheap to rebuild; segments and bundles too. */
export function pruneCache(maxGB = 8) {
  const entries = [];
  const walk = (d, depth) => {
    if (!fs.existsSync(d)) return;
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      const p = path.join(d, e.name);
      if (depth === 0 && e.isDirectory() && !["segments"].includes(e.name)) { walk(p, 1); continue; }
      if (depth === 0 && e.name === "segments") { walk(p, 1); continue; }
      const du = parseInt(execSync(`du -sk "${p}"`).toString(), 10) * 1024;
      entries.push({ p, du, t: fs.statSync(p).atimeMs });
    }
  };
  walk(CACHE_ROOT, 0);
  let total = entries.reduce((a, e) => a + e.du, 0);
  for (const e of entries.sort((a, b) => a.t - b.t)) {
    if (total <= maxGB * 1073741824) break;
    fs.rmSync(e.p, { recursive: true, force: true }); total -= e.du;
  }
  return total / 1073741824;
}
