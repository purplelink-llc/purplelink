/**
 * Netlify Function: Summonly search model delivery.
 *
 * Summonly can download one small search model (granite-embedding-small-english-r2, Apache 2.0) when the person opts in.
 * The app asks for the manifest first, shows the size, and downloads only after a click. There is no payment gate: the
 * model improves an optional feature and trial users may use it, the same as the rest of the app.
 *
 *   GET /.netlify/functions/summonly-model?manifest=1                -> the signed manifest (JSON)
 *   GET /.netlify/functions/summonly-model?file=summonly-embed-1-<v>.zip  -> the model archive
 *
 * The manifest is signed with an Ed25519 key kept offline (scripts/package-model.swift in the Summonly repo makes and signs it);
 * the app carries the public half and refuses an archive whose size or SHA-256 differ from the signed values. So this function
 * only has to serve bytes: it cannot make the app trust anything. Both files live in the private `summonly-files` Blobs store
 * under `model/`. Downloads are capped per day so a link that spreads cannot use up the bandwidth allowance.
 */
import { getStore } from "@netlify/blobs";

const FILE_STORE = "summonly-files";
const STATS_STORE = "summonly-stats";
const FILE_NAME = /^summonly-embed-[0-9]+-[0-9a-z.]+\.zip$/;
const DAILY_LIMIT = 300;

function json(status, body, extra = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store", ...extra },
  });
}

export default async (req) => {
  if (req.method !== "GET" && req.method !== "HEAD") return json(405, { error: "method_not_allowed" }, { Allow: "GET, HEAD" });
  const url = new URL(req.url);
  const store = getStore(FILE_STORE);

  if (url.searchParams.get("manifest") === "1") {
    const text = await store.get("model/manifest.json");
    if (!text) return json(404, { error: "no_model", detail: "No model is published yet." });
    return new Response(text, { status: 200, headers: { "Content-Type": "application/json", "Cache-Control": "public, max-age=300" } });
  }

  const file = url.searchParams.get("file") || "";
  if (!FILE_NAME.test(file)) return json(400, { error: "bad_request" });

  // a plain counter per day, in the same read-increment-write style as the other doors
  const stats = getStore(STATS_STORE);
  const day = new Date().toISOString().slice(0, 10);
  const key = `model-downloads:${day}`;
  const n = parseInt((await stats.get(key)) || "0", 10) || 0;
  if (n >= DAILY_LIMIT) return json(429, { error: "busy", detail: "The model download is busy today. Try again tomorrow." }, { "Retry-After": "3600" });

  const blob = await store.getWithMetadata(`model/${file}`, { type: "stream" });
  if (!blob) return json(404, { error: "not_found" });
  await stats.set(key, String(n + 1));
  const headers = { "Content-Type": "application/zip", "Cache-Control": "public, max-age=31536000, immutable", "Content-Disposition": `attachment; filename="${file}"` };
  const size = blob.metadata?.size;
  if (size) headers["Content-Length"] = String(size);
  return new Response(req.method === "HEAD" ? null : blob.data, { status: 200, headers });
};
