// Local test server for /games/: serves site/ and answers /.netlify/functions/games-api in memory.
// "Emails" are not sent; the latest sign-in link is printed and served at /__lastmail.
//   node scripts/dev-games-server.mjs [port]
import http from "node:http";
import { readFile, stat } from "node:fs/promises";
import { join, extname, normalize } from "node:path";
import { createHandler } from "../netlify/functions/games-api.mjs";

const port = Number(process.argv[2] || 8766);
const root = join(import.meta.dirname, "..", "site");
const mem = new Map();
const getStore = (opt) => { const name = typeof opt === "string" ? opt : opt.name; return {
  get: async (k, o) => { const v = mem.get(`${name}/${k}`); return v === undefined ? null : o?.type === "json" ? JSON.parse(v) : v; },
  set: async (k, v) => { mem.set(`${name}/${k}`, String(v)); },
  setJSON: async (k, v) => { mem.set(`${name}/${k}`, JSON.stringify(v)); },
  delete: async (k) => { mem.delete(`${name}/${k}`); },
}; };
let lastMail = "";
const fetchFn = async (url, opts) => { lastMail = JSON.parse(opts.body).text; console.log("[mail]", lastMail.split("\n")[2]); return new Response("{}"); };
const env = (k) => ({ RESEND_API_KEY: "dev", GAMES_DEV_ORIGIN: `http://127.0.0.1:${port}` })[k];
const handler = createHandler({ getStore, env, fetchFn });
const types = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".txt": "text/plain", ".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp", ".woff2": "font/woff2" };

http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://127.0.0.1:${port}`);
  if (url.pathname === "/.netlify/functions/games-api") {
    const chunks = [];
    for await (const c of req) chunks.push(c);
    const r = await handler(new Request(url, { method: req.method, headers: req.headers, body: ["GET", "HEAD"].includes(req.method) ? undefined : Buffer.concat(chunks) }));
    res.writeHead(r.status, Object.fromEntries(r.headers));
    return res.end(Buffer.from(await r.arrayBuffer()));
  }
  if (url.pathname === "/__lastmail") { res.writeHead(200, { "content-type": "text/plain" }); return res.end(lastMail); }
  let p = normalize(decodeURIComponent(url.pathname)).replace(/^(\.\.[/\\])+/, "");
  let file = join(root, p);
  try { if ((await stat(file)).isDirectory()) file = join(file, "index.html"); } catch (_) { /* fall through */ }
  try {
    const body = await readFile(file);
    res.writeHead(200, { "content-type": types[extname(file)] || "application/octet-stream" });
    res.end(body);
  } catch (_) { res.writeHead(404); res.end("not found"); }
}).listen(port, "127.0.0.1", () => console.log(`games dev server on http://127.0.0.1:${port}`));
